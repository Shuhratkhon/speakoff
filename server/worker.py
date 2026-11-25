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
from server.plans import KEEP_AUDIOS, PLANS

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
        res = rate.report("recording", d, sections)
    t = d.get("topic") or {}
    res["topic_verdict"] = t.get("verdict")
    res["integrity"] = (d.get("integrity") or {}).get("verdict")
    if res["integrity"] == "cheat":
        from coach import topic
        res["overall"] = min(res["overall"], topic.OFF_CAP)
    if t.get("off"):          # off-topic or memorised answer: overall capped (coach/topic.py)
        from coach import topic
        res["overall"] = min(res["overall"], topic.OFF_CAP)
        res["off_topic"] = True
    return res


def topic_question(rec):
    """The question an answer should be about: the daily question, or every question of a mock test."""
    if rec["is_mock"]:
        from server import mock
        s = mock.BY_ID.get(rec["mock_set"])
        if s:
            return " ".join(s["p1"] + [s["p2"]["title"]] + s["p2"]["points"] + s["p3"])
    return rec["question"]


def _seen_audio(uid, audio_path):
    """True if this exact audio file was already sent by the player (a recording replayed). Keeps a hash only."""
    import hashlib
    try:
        h = hashlib.sha256(Path(audio_path).read_bytes()).hexdigest()
    except Exception:
        return False
    if db.one("SELECT 1 FROM audio_hashes WHERE user_id=? AND hash=?", uid, h):
        return True
    db.run("INSERT INTO audio_hashes (user_id, hash, created) VALUES (?,?,?)", uid, h, time.time())
    return False


def check_integrity(d, audio_path, uid, sections, original=None):
    """Anti-cheat (coach/anticheat.py): run after scoring; returns the (maybe capped) scores."""
    res = summary(d, sections)
    if not uid:
        return res
    try:
        from coach import anticheat
        from server import biometric
        user = db.one("SELECT voice_consent FROM users WHERE id=?", uid)
        use_voice = bool(user and user["voice_consent"] == 1)       # separate, explicit consent only
        prints = biometric.recent(uid, anticheat.MAX_PRINTS) if use_voice else []
        replay = _seen_audio(uid, original or audio_path)     # the uploaded file: a conversion is never byte-identical
        scores = [r["overall"] for r in db.all_("SELECT overall FROM recordings WHERE user_id=? AND status='done' "
                                                "ORDER BY created DESC LIMIT 10", uid)]
        scores += [r["overall"] for r in db.all_("SELECT p.overall FROM match_players p JOIN matches m ON m.id=p.match_id "
                                                 "WHERE p.user_id=? AND p.is_ghost=0 AND p.overall IS NOT NULL "
                                                 "ORDER BY m.created DESC LIMIT 10", uid)]
        out, vp = anticheat.check(d, audio_path, res["overall"], prints, scores, use_voice=use_voice,
                                  protect=biometric.protect, replay=replay)
        d["integrity"] = out
        if vp and use_voice and out["verdict"] != "cheat":     # only honest answers teach us the player's voice
            biometric.add(uid, vp)
        return summary(d, sections)
    except Exception:
        traceback.print_exc()                       # never block scoring because of this check
        return res


def earlier_answers(uid, question, n=40):
    """The player's recent answers to other questions (for spotting a memorised speech)."""
    out = []
    for r in db.all_("SELECT data, question FROM recordings WHERE user_id=? AND status='done' AND data IS NOT NULL "
                     "ORDER BY created DESC LIMIT ?", uid, n):
        if r["question"] != question:
            out.append((json.loads(r["data"]) or {}).get("text", ""))
    for r in db.all_("SELECT p.extras, m.question FROM match_players p JOIN matches m ON m.id=p.match_id "
                     "WHERE p.user_id=? AND p.is_ghost=0 AND p.extras IS NOT NULL ORDER BY m.created DESC LIMIT ?", uid, n):
        if r["question"] != question:
            out.append((json.loads(r["extras"]) or {}).get("text", ""))
    return [t for t in out if t]


def check_topic(d, question, uid=None):
    if d.get("lang", "en") != "en":
        try:                                       # a memorised / replayed answer is caught in every language
            from coach import topic
            if uid and topic.repeated(d.get("text", ""), earlier_answers(uid, question)):
                d["topic"] = {"verdict": "repeated", "off": True}
            elif d["lang"] == "ko":                 # Korean off-topic check (coach/topic_ko.py, phase 4)
                from coach import topic_ko
                d["topic"] = topic_ko.check(question, d.get("text", ""))
        except Exception:
            traceback.print_exc()
        return
    try:
        from coach import topic
        d["topic"] = topic.check(question, d.get("text", ""), earlier_answers(uid, question) if uid else ())
    except Exception:
        traceback.print_exc()                   # never block scoring because of this check


def _analyse(rec_id):
    rec = db.one("SELECT r.*, u.plan FROM recordings r JOIN users u ON u.id=r.user_id WHERE r.id=?", rec_id)
    if rec is None or rec["status"] not in ("queued", "running"):
        return
    db.run("UPDATE recordings SET status='running' WHERE id=?", rec_id)
    src = Path(rec["src_path"])
    try:
        from coach import rate
        from server import media
        from server import mock
        max_s = mock.MAX_TOTAL if rec["is_mock"] else PLANS[rec["plan"]]["max_s"] if not rec["is_daily"] else 70
        AUDIO.mkdir(parents=True, exist_ok=True)
        audio = AUDIO / f"{rec_id}.ogg"
        media.to_audio(src, audio, max_s)
        video = src if rec["mode"] == "video" and media.has_video(src) else None
        d = rate.analyse(audio, video=video, cache=False, max_seconds=max_s, lang=rec["learn_lang"] or "en")
        if d["n_words"] < MIN_WORDS:
            # silence, music or another language: Whisper may "hear" a few made-up words, and with almost no
            # words there are no mistakes, so the scores would be wrongly high -> refuse it instead
            raise NotEnoughSpeech(d["n_words"])
        sections = rec["sections"].split(",")
        from coach import profanity
        if profanity.find(d.get("text", "")):
            from server import ranked
            ranked.strike(rec["user_id"])
            d["profanity"] = True                        # recordings: a warning on the result, no score change
        check_topic(d, topic_question(rec), rec["user_id"])
        res = check_integrity(d, audio, rec["user_id"], sections, original=src)
        db.run("UPDATE recordings SET status='done', data=?, audio_path=?, overall=?, cefr=?, ielts=?, scores=? "
               "WHERE id=?", json.dumps(d, ensure_ascii=False), str(audio), res["overall"],
               res["level"]["cefr"], res["level"]["ielts"], json.dumps(res["sections"]), rec_id)
        trim_audios(rec["user_id"])
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


def trim_audios(user_id):
    """Keep the audio of the user's newest KEEP_AUDIOS recordings (normal and ranked together); results stay."""
    rows = [("rec", r["id"], datetime.fromisoformat(r["created"]).timestamp(), r["audio_path"])
            for r in db.all_("SELECT id, created, audio_path FROM recordings WHERE user_id=? AND audio_deleted=0 "
                             "AND audio_path IS NOT NULL AND keep_forever=0", user_id)]
    rows += [("match", (r["match_id"], r["slot"]), r["created"], r["audio_path"])
             for r in db.all_("SELECT p.match_id, p.slot, p.audio_path, m.created FROM match_players p "
                              "JOIN matches m ON m.id=p.match_id WHERE p.user_id=? AND p.is_ghost=0 "
                              "AND p.audio_path IS NOT NULL", user_id)]
    rows.sort(key=lambda r: r[2], reverse=True)
    for kind, key, _, path in rows[KEEP_AUDIOS:]:
        Path(path).unlink(missing_ok=True)
        if kind == "rec":
            for f in VOICE.glob(f"{key}_*.mp3"):
                f.unlink(missing_ok=True)
            db.run("UPDATE recordings SET audio_deleted=1 WHERE id=?", key)
        else:
            db.run("UPDATE match_players SET audio_path=NULL WHERE match_id=? AND slot=?", *key)


def cleanup():
    for u in db.all_("SELECT id FROM users"):
        trim_audios(u["id"])
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
