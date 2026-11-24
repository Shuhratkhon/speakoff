"""Background work.

1) Analysis queue: ONE recording at a time (ranked match answers go first: two players are waiting) (the models need most of the CPU / GPU). For each recording:
   upload -> small audio file (cut at the plan's length) -> all models (+ face, for video)
   -> results saved in the database -> the upload (e.g. the video) is deleted, the audio is kept.
2) Cleanup, every hour: audio older than the plan allows (Free 14 / Plus 30 / Pro 90 days) is deleted,
   with the AI-voice files made for it. The results (scores, text) are kept forever.
"""

import contextlib
import io
import itertools
import json
import queue
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from server import db
from server.plans import PLANS

AUDIO = db.DATA / "audio"
VOICE = db.DATA / "voice"
UPLOADS = db.DATA / "uploads"
_jobs = queue.PriorityQueue()      # (priority, order, job): 0 = ranked answer, 1 = normal recording
_order = itertools.count()
_started = False
MIN_WORDS = 25          # fewer recognised English words in a 1+ minute recording = no real answer (our samples: 108-239)


class NotEnoughSpeech(Exception):
    pass


def summary(d, sections):
    """Scores, level and the report's numbers for one analysis (fast: the models already ran)."""
    from coach import rate
    with contextlib.redirect_stdout(io.StringIO()):
        return rate.report("recording", d, sections)


def _analyse(rec_id):
    rec = db.one("SELECT r.*, u.plan FROM recordings r JOIN users u ON u.id=r.user_id WHERE r.id=?", rec_id)
    if rec is None or rec["status"] not in ("queued", "running"):
        return
    db.run("UPDATE recordings SET status='running' WHERE id=?", rec_id)
    src = Path(rec["src_path"])
    try:
        from coach import rate
        from server import media
        max_s = PLANS[rec["plan"]]["max_s"] if not rec["is_daily"] else 70
        AUDIO.mkdir(parents=True, exist_ok=True)
        audio = AUDIO / f"{rec_id}.ogg"
        media.to_audio(src, audio, max_s)
        video = src if rec["mode"] == "video" and media.has_video(src) else None
        d = rate.analyse(audio, video=video, cache=False, max_seconds=max_s)
        if d["n_words"] < MIN_WORDS:
            # silence, music or another language: Whisper may "hear" a few made-up words, and with almost no
            # words there are no mistakes, so the scores would be wrongly high -> refuse it instead
            raise NotEnoughSpeech(d["n_words"])
        sections = rec["sections"].split(",")
        res = summary(d, sections)
        db.run("UPDATE recordings SET status='done', data=?, audio_path=?, overall=?, cefr=?, ielts=?, scores=? "
               "WHERE id=?", json.dumps(d, ensure_ascii=False), str(audio), res["overall"],
               res["level"]["cefr"], res["level"]["ielts"], json.dumps(res["sections"]), rec_id)
        try:
            from server import rewards
            rewards.evaluate(rec["user_id"])                    # achievements for recordings / levels
        except Exception:
            traceback.print_exc()
    except Exception as e:
        if isinstance(e, NotEnoughSpeech):
            error = f"not_enough_speech:{e.args[0]}"
        else:
            traceback.print_exc()
            error = f"{type(e).__name__}: {e}"
        db.run("UPDATE recordings SET status='failed', error=? WHERE id=?", error, rec_id)
        (AUDIO / f"{rec_id}.ogg").unlink(missing_ok=True)       # nothing to keep for a failed analysis
        if rec["used_bonus"]:                                   # a failed analysis does not use up a recording
            db.run("UPDATE users SET bonus_left = bonus_left + 1 WHERE id=?", rec["user_id"])
    finally:
        src.unlink(missing_ok=True)                             # the video / original upload is not kept


def _loop():
    while True:
        _prio, _n, job = _jobs.get()
        try:
            if job[0] == "ranked":
                from server import ranked
                ranked.analyse_answer(job[1], job[2])
            else:
                _analyse(job[1])
        except Exception:
            traceback.print_exc()


def cleanup():
    """Delete recording files older than the user's plan allows; keep the results."""
    now = datetime.now(timezone.utc)
    rows = db.all_("SELECT r.id, r.created, r.audio_path, u.plan FROM recordings r JOIN users u ON u.id=r.user_id "
                   "WHERE r.audio_deleted=0 AND r.audio_path IS NOT NULL")
    for r in rows:
        keep = PLANS.get(r["plan"], PLANS["free"])["keep_days"]
        if now - datetime.fromisoformat(r["created"]) > timedelta(days=keep):
            Path(r["audio_path"]).unlink(missing_ok=True)
            for f in VOICE.glob(f"{r['id']}_*.mp3"):
                f.unlink(missing_ok=True)
            db.run("UPDATE recordings SET audio_deleted=1 WHERE id=?", r["id"])
    for f in UPLOADS.glob("*"):                                 # uploads left behind by a crash
        if time.time() - f.stat().st_mtime > 24 * 3600:
            f.unlink(missing_ok=True)


def _cleanup_loop():
    while True:
        try:
            cleanup()
        except Exception:
            traceback.print_exc()
        time.sleep(3600)


def _warm_up():
    """Load the models once at start-up so the first user does not wait for it."""
    try:
        from coach import grammar, pronunciation, rate, transcribe  # noqa: F401  (loading = importing)
        grammar._load()
        print("models loaded")
    except Exception:
        traceback.print_exc()


def submit(rec_id):
    _jobs.put((1, next(_order), ("rec", rec_id)))


def submit_ranked(match_id, slot):
    _jobs.put((0, next(_order), ("ranked", match_id, slot)))


def start(warm_up=True):
    global _started
    if _started:
        return
    _started = True
    # recordings that were waiting when the server stopped: analyse them now
    for r in db.all_("SELECT id FROM recordings WHERE status IN ('queued','running') ORDER BY created"):
        if Path(db.one("SELECT src_path FROM recordings WHERE id=?", r["id"])["src_path"] or "").exists():
            db.run("UPDATE recordings SET status='queued' WHERE id=?", r["id"])
            submit(r["id"])
        else:
            db.run("UPDATE recordings SET status='failed', error='server restarted' WHERE id=?", r["id"])
    for p in db.all_("SELECT match_id, slot, src_path FROM match_players WHERE status IN ('uploaded','running')"):
        if p["src_path"] and Path(p["src_path"]).exists():
            db.run("UPDATE match_players SET status='uploaded' WHERE match_id=? AND slot=?", p["match_id"], p["slot"])
            submit_ranked(p["match_id"], p["slot"])
        else:
            db.run("UPDATE match_players SET status='failed', error='failed_sub' WHERE match_id=? AND slot=?",
                   p["match_id"], p["slot"])

    def worker():
        if warm_up:
            _warm_up()
        _loop()

    threading.Thread(target=worker, daemon=True, name="analysis").start()
    threading.Thread(target=_cleanup_loop, daemon=True, name="cleanup").start()
    from server import ranked
    threading.Thread(target=ranked.sweep_loop, daemon=True, name="ranked-sweep").start()
