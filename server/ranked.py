"""Ranked 1v1 matches.

1. A player joins the queue. Two players near each other's rank are paired (the allowed RP gap grows while they wait).
2. Nobody near after 20 s: the player meets a "replay" (a real player's earlier answer to the same question,
   labelled as a replay; it never changes that player's RP) or, if there is none yet, the Speakoff Bot (half RP).
3. Both see the same question at the same moment, get 5 seconds to read it, then speak 30-60 seconds.
4. Both answers are scored by the normal models (fluency, grammar, vocabulary, pronunciation).
   Higher overall score wins; less than 2 points apart = draw. No valid answer (too short, no speech,
   not sent in time) = loss. RP change is Elo-like: beating a stronger player gives more.
Ranked answers do not count as recordings and do not change the level or the Progress charts.
"""

import json
import random
import threading
import time
import traceback
import uuid
from pathlib import Path

from server import cosmetics, db, plans, questions, ranks, rewards

COUNTDOWN = 4            # "opponent found" -> question shown
READ_S = 5               # question shown -> recording starts
MIN_S, MAX_S = 30, 60    # answer length
GRACE = 45               # extra time for the upload after the longest answer
WAIT_PLAYER = 20         # seconds in the queue before a replay / bot match
QUEUE_STALE = 10         # a queued player who stopped asking is removed
K = 40                   # Elo factor
DRAW_GAP = 1             # only the same score is a draw (user, 2026-11-25)
HISTORY = 10             # match log: the last 10 matches, for every plan
SECTIONS = ["fluency", "grammar", "vocabulary", "pronunciation"]
LOCK = threading.RLock()


# ------------------------------------------------------------------ players

def lang_of(user):
    return (user["learn_lang"] if "learn_lang" in user.keys() else None) or "en"


def rating(uid, lang=None):
    """{"rp", "best_rp", "season"}: one rank per player, shared by every language they play Ranked in."""
    u = db.one("SELECT rp, best_rp, season FROM users WHERE id=?", uid)
    return {"rp": u["rp"], "best_rp": u["best_rp"], "season": u["season"]} if u else {"rp": 0, "best_rp": 0, "season": None}


def add_rp(uid, lang, delta):
    db.run("UPDATE users SET rp=rp+?, best_rp=max(best_rp, rp+?) WHERE id=?", delta, delta, uid)


def rated(user):
    return dict(user)


def ensure_season(user):
    """New season: keep half of the RP."""
    sid = ranks.season_id()
    if user["season"] != sid:
        db.run("UPDATE users SET rp=?, season=? WHERE id=?", user["rp"] // 2 if user["season"] else 0, sid, user["id"])
        user = db.one("SELECT * FROM users WHERE id=?", user["id"])
    return dict(user)


def played_today(uid):
    return db.one("SELECT COUNT(*) n FROM match_players p JOIN matches m ON m.id=p.match_id "
                  "WHERE p.user_id=? AND p.is_ghost=0 AND m.day=?", uid, plans.today())["n"]


def limits(user):
    from server import shop
    per_day = plans.plan_of(user)["ranked"] + shop.bought_today(user["id"], "ranked")
    return {"per_day": per_day, "left": max(per_day - played_today(user["id"]), 0)}


def master_wins(uid, sid=None, lang=None):
    """Master players show their wins at Master this season next to the rank (e.g. "Master 27")."""
    return db.one("SELECT COUNT(*) n FROM match_players p JOIN matches m ON m.id=p.match_id WHERE p.user_id=? "
                  "AND p.is_ghost=0 AND p.result='win' AND p.rp_before>=? AND m.kind!='friendly' AND m.season=?",
                  uid, ranks.MASTER_RP, sid or ranks.season_id())["n"]


def rank_for(uid, rp, lang=None):
    r = ranks.rank_of(rp)
    if r["rank"] == "master" and uid:
        r["wins"] = master_wins(uid, lang=lang)
    return r


def card(u, rp=None):
    """What other players see: name, photo, frame, rank, the 2 shown skills."""
    if u is None:
        return {"bot": True, "username": "Speakoff Bot", "rank": ranks.rank_of(rp or 0), "skills": [], "frame": "none",
                "photo": None, "name_style": "", "entrance": "", "sticker": ""}
    rp = rated(u)["rp"] if rp is None else rp
    shown = [s for s in (u["shown_skills"] or "").split(",") if s]
    return {"bot": False, "username": u["username"], "rank": rank_for(u["id"], rp),
            "photo": f"/api/photo/{u['username']}?v={u['photo']}" if u["photo"] else None,
            "frame": u["frame"], "skills": rewards.shown_skills(u["id"], shown),
            "country": u["country"], "display_name": u["display_name"],
            "name_style": cosmetics.worn(u, "name_style"), "entrance": cosmetics.worn(u, "entrance"),
            "sticker": cosmetics.worn(u, "sticker")}


def active_match(uid):
    r = db.one("SELECT m.id FROM matches m JOIN match_players p ON p.match_id=m.id "
               "WHERE p.user_id=? AND p.is_ghost=0 AND m.status='live' ORDER BY m.created DESC LIMIT 1", uid)
    return r["id"] if r else None


# ------------------------------------------------------------------ queue

def join(user):
    user = ensure_season(user)
    live = active_match(user["id"])
    if live:
        return {"state": "found", "match": live}
    if ban_until(user):
        return {"state": "banned", "until": ban_until(user)}
    if limits(user)["left"] <= 0:
        return {"state": "limit"}
    now = time.time()
    with LOCK:
        db.run("INSERT OR REPLACE INTO ranked_queue (user_id, rp, joined, last_poll, match_id, lang) VALUES (?,?,?,?,NULL,?)",
               user["id"], user["rp"], now, now, lang_of(user))
    return poll(user)


def leave(user):
    with LOCK:
        db.run("DELETE FROM ranked_queue WHERE user_id=? AND match_id IS NULL", user["id"])


def poll(user):
    now = time.time()
    with LOCK:
        row = db.one("SELECT * FROM ranked_queue WHERE user_id=?", user["id"])
        if row is None:
            live = active_match(user["id"])
            return {"state": "found", "match": live} if live else {"state": "idle"}
        if row["match_id"]:
            db.run("DELETE FROM ranked_queue WHERE user_id=?", user["id"])
            return {"state": "found", "match": row["match_id"]}
        db.run("UPDATE ranked_queue SET last_poll=? WHERE user_id=?", now, user["id"])
        db.run("DELETE FROM ranked_queue WHERE match_id IS NULL AND last_poll<?", now - QUEUE_STALE)
        match_id = _pair(row, now)
        if match_id is None and now - row["joined"] >= WAIT_PLAYER:
            match_id = _solo_match(user)
            db.run("DELETE FROM ranked_queue WHERE user_id=?", user["id"])
            return {"state": "found", "match": match_id}
        if match_id:
            db.run("DELETE FROM ranked_queue WHERE user_id=?", user["id"])
            return {"state": "found", "match": match_id}
    return {"state": "searching", "waited": round(now - row["joined"])}


def _pair(me, now):
    best = None
    for o in db.all_("SELECT * FROM ranked_queue WHERE match_id IS NULL AND user_id!=? AND lang=?", me["user_id"], me["lang"]):
        waited = max(now - me["joined"], now - o["joined"])
        gap = abs(o["rp"] - me["rp"])
        if gap <= 150 + 20 * waited and (best is None or gap < abs(best["rp"] - me["rp"])):
            best = o
    if best is None:
        return None
    question = _question([me["user_id"], best["user_id"]], me["lang"])
    mid = _create("player", question, [
        {"user_id": me["user_id"], "rp_before": me["rp"]},
        {"user_id": best["user_id"], "rp_before": best["rp"]},
    ], me["lang"])
    db.run("UPDATE ranked_queue SET match_id=? WHERE user_id=?", mid, best["user_id"])
    return mid


def _recent_questions(uid, n=200):
    return {r["question"] for r in db.all_("SELECT m.question FROM matches m JOIN match_players p ON p.match_id=m.id "
                                           "WHERE p.user_id=? AND p.is_ghost=0 ORDER BY m.created DESC LIMIT ?", uid, n)}


def _question(uids, lang="en"):
    seen = set().union(*(_recent_questions(u) for u in uids))
    bank = questions.bank(lang)
    pool = [q for q in bank if q not in seen] or bank
    return random.choice(pool)


def _solo_match(user):
    """No player near: a replay of a real answer near this rank, else the bot."""
    seen = _recent_questions(user["id"])
    lang = lang_of(user)
    ghosts = db.all_("SELECT p.*, m.question FROM match_players p JOIN matches m ON m.id=p.match_id "
                     "WHERE p.status='done' AND p.is_ghost=0 AND p.user_id IS NOT NULL AND p.user_id!=? AND m.lang=? "
                     "AND abs(p.rp_before-?)<=400 ORDER BY random() LIMIT 30", user["id"], lang, user["rp"])
    fresh = [gh for gh in ghosts if gh["question"] not in seen]
    gh = (fresh or ghosts or [None])[0]
    me = {"user_id": user["id"], "rp_before": user["rp"]}
    if gh is not None:
        owner = rating(gh["user_id"], lang)
        return _create("ghost", gh["question"], [me, {
            "user_id": gh["user_id"], "rp_before": owner["rp"] or gh["rp_before"], "is_ghost": 1,
            "status": "done", "duration": gh["duration"], "overall": gh["overall"], "scores": gh["scores"],
            "extras": gh["extras"]}], lang)
    return _create("bot", _question([user["id"]], lang), [me, {"user_id": None, "rp_before": user["rp"], "status": "bot"}], lang)


def _create(kind, question, players, lang="en"):
    mid = uuid.uuid4().hex[:16]
    now = time.time()
    reveal = now + COUNTDOWN
    speak = reveal + READ_S
    db.run("INSERT INTO matches (id, season, kind, question, created, reveal_at, speak_at, deadline, status, day, lang) "
           "VALUES (?,?,?,?,?,?,?,?,'live',?,?)", mid, ranks.season_id(), kind, question, now, reveal, speak,
           speak + MAX_S + GRACE, plans.today(), lang)
    for slot, p in enumerate(players):
        db.run("INSERT INTO match_players (match_id, slot, user_id, is_ghost, rp_before, status, duration, overall, "
               "scores, extras) VALUES (?,?,?,?,?,?,?,?,?,?)", mid, slot, p["user_id"], p.get("is_ghost", 0),
               p["rp_before"], p.get("status", "waiting"), p.get("duration"), p.get("overall"), p.get("scores"),
               p.get("extras"))
    return mid


# ------------------------------------------------------------------ answers

def save_answer(user, match_id, f):
    """The recorded answer arrives (the browser sends it as soon as the player stops)."""
    from server import media, worker
    m = db.one("SELECT * FROM matches WHERE id=?", match_id)
    p = db.one("SELECT * FROM match_players WHERE match_id=? AND user_id=? AND is_ghost=0", match_id, user["id"])
    if m is None or p is None:
        return "not_found"
    now = time.time()
    if p["status"] != "waiting" or m["status"] != "live":
        return "answer_closed"
    if now > m["deadline"]:
        finish(match_id)
        return "answer_late"
    ext = Path(f.filename or "").suffix.lower() or ".webm"
    if ext not in {".webm", ".ogg", ".oga", ".opus", ".mp4", ".m4a", ".wav", ".mp3", ".aac"}:
        return "bad_file"
    worker.UPLOADS.mkdir(parents=True, exist_ok=True)
    src = worker.UPLOADS / f"m_{match_id}_{p['slot']}{ext}"
    f.save(src)
    try:
        length = media.duration(src)
    except Exception:
        length = 0
    # the answer cannot be longer than the time since the recording started (+ a little for timing differences)
    if length < MIN_S - 0.5 or now < m["speak_at"] + MIN_S - 3:
        src.unlink(missing_ok=True)
        db.run("UPDATE match_players SET status='failed', error='ranked_too_short', duration=? WHERE match_id=? "
               "AND slot=?", length, match_id, p["slot"])
        finish(match_id)
        return None
    db.run("UPDATE match_players SET status='uploaded', src_path=?, duration=? WHERE match_id=? AND slot=?",
           str(src), min(length, MAX_S), match_id, p["slot"])
    worker.submit_ranked(match_id, p["slot"])
    return None


def analyse_answer(match_id, slot):
    """Runs in the analysis thread (before normal recordings: a live match is waiting)."""
    from server import media, worker
    from coach import rate
    p = db.one("SELECT * FROM match_players WHERE match_id=? AND slot=?", match_id, slot)
    if p is None or p["status"] not in ("uploaded", "running"):
        return
    db.run("UPDATE match_players SET status='running' WHERE match_id=? AND slot=?", match_id, slot)
    src = Path(p["src_path"])
    audio = worker.AUDIO / f"m_{match_id}_{slot}.ogg"
    try:
        worker.AUDIO.mkdir(parents=True, exist_ok=True)
        media.to_audio(src, audio, MAX_S)
        mlang = db.one("SELECT lang FROM matches WHERE id=?", match_id)["lang"]
        d = rate.analyse(audio, cache=False, max_seconds=MAX_S, lang=mlang)
        if d["n_words"] < worker.MIN_WORDS:
            raise worker.NotEnoughSpeech(d["n_words"])
        from coach import profanity
        warned = False
        if p["user_id"] and profanity.find(d.get("text", "")):
            if not strike(p["user_id"]):
                raise Profane()                          # not the first time: a loss, never played to the opponent
            warned = True                                # first time ever: only a warning
        worker.check_topic(d, db.one("SELECT question FROM matches WHERE id=?", match_id)["question"], p["user_id"])
        res = worker.check_integrity(d, audio, p["user_id"], SECTIONS)
        lv = res["level"]
        extras = {"words": d["n_words"], "fillers": d["fluency"].get("fillers", 0),
                  "mistakes": sum(len(s["mistakes"]) for s in d["grammar_results"]),
                  "b2": lv["vocabulary"]["b2_plus"], "cefr": lv["cefr"], "off_topic": bool(res.get("off_topic")),
                  "topic": res.get("topic_verdict"), "text": d.get("text", "")[:2000],
                  "profanity": "warn" if warned else None, "integrity": res.get("integrity")}
        db.run("UPDATE match_players SET status='done', overall=?, scores=?, extras=?, audio_path=? "
               "WHERE match_id=? AND slot=?", res["overall"], json.dumps(res["sections"]), json.dumps(extras),
               str(audio), match_id, slot)
        audio = None                                    # kept: one of the user's last 10 recordings
        if p["user_id"]:
            worker.trim_audios(p["user_id"])
    except Exception as e:
        if isinstance(e, worker.NotEnoughSpeech):
            error = f"not_enough_speech:{e.args[0]}"
        elif isinstance(e, Profane):
            error = "profanity"
        else:
            traceback.print_exc()
            error = "failed_sub"
        db.run("UPDATE match_players SET status='failed', error=? WHERE match_id=? AND slot=?", error, match_id, slot)
    finally:
        src.unlink(missing_ok=True)
        if audio is not None:
            audio.unlink(missing_ok=True)      # failed answers keep no audio
    finish(match_id)


# ------------------------------------------------------------------ result

def _bot_scores(uid):
    """The bot plays near the player's own recent level, so it is a fair, beatable opponent."""
    recent = [r["overall"] for r in db.all_("SELECT overall FROM match_players WHERE user_id=? AND is_ghost=0 "
                                            "AND overall IS NOT NULL ORDER BY rowid DESC LIMIT 10", uid)]
    if not recent:
        recent = [r["overall"] for r in db.all_("SELECT overall FROM recordings WHERE user_id=? AND status='done' "
                                                "ORDER BY created DESC LIMIT 5", uid)]
    base = sum(recent) / len(recent) if recent else 65
    overall = max(30, min(92, round(random.gauss(base, 6))))
    scores = {s: max(20, min(98, round(random.gauss(overall, 5)))) for s in SECTIONS}
    overall = max(30, min(92, round(sum(scores.values()) / 4)))
    return overall, scores


def finish(match_id):
    """Decide the match once every answer is scored (or its time is over). Safe to call many times."""
    shielded = set()
    new_awards = {}
    with LOCK:
        m = db.one("SELECT * FROM matches WHERE id=?", match_id)
        if m is None or m["status"] != "live":
            return
        now = time.time()
        ps = [dict(p) for p in db.all_("SELECT * FROM match_players WHERE match_id=? ORDER BY slot", match_id)]
        for p in ps:
            if p["status"] == "waiting" and now > m["deadline"]:
                p["status"] = "missed"
                db.run("UPDATE match_players SET status='missed', error='ranked_missed' WHERE match_id=? AND slot=?",
                       match_id, p["slot"])
        if any(p["status"] in ("waiting", "uploaded", "running") for p in ps):
            return
        human = next(p for p in ps if p["user_id"] is not None and not p["is_ghost"])
        for p in ps:
            if p["status"] == "bot":
                p["overall"], sc = _bot_scores(human["user_id"])
                p["scores"], p["status"] = json.dumps(sc), "done"
                db.run("UPDATE match_players SET status='done', overall=?, scores=? WHERE match_id=? AND slot=?",
                       p["overall"], p["scores"], match_id, p["slot"])
        a, b = ps
        ok_a, ok_b = a["status"] == "done", b["status"] == "done"
        if ok_a and ok_b:
            gap = a["overall"] - b["overall"]
            res = ("draw", "draw") if abs(gap) < DRAW_GAP else (("win", "loss") if gap > 0 else ("loss", "win"))
        elif ok_a or ok_b:
            res = ("win", "loss") if ok_a else ("loss", "win")
        else:
            res = ("none", "none")                       # neither answered: no RP change
        for p, r, o in ((a, res[0], b), (b, res[1], a)):
            delta = None
            if p["user_id"] is not None and not p["is_ghost"] and r != "none" and m["kind"] != "friendly":
                u = rating(p["user_id"], m["lang"])
                s = {"win": 1, "draw": .5, "loss": 0}[r]
                expected = 1 / (1 + 10 ** ((o["rp_before"] - p["rp_before"]) / 400))
                delta = round(K * (s - expected))
                if r == "win":
                    delta = max(delta, 5)
                elif r == "loss":
                    delta = min(delta, -5)
                if m["kind"] == "bot":
                    delta = round(delta / 2)
                delta = max(delta, -u["rp"])               # never below 0 RP
                if delta < 0 and db.run("UPDATE users SET shields=shields-1 WHERE id=? AND shields>0",
                                        p["user_id"]).rowcount:
                    delta = 0                              # a rank shield (bought with credits) took the loss
                    shielded.add(p["slot"])
                add_rp(p["user_id"], m["lang"], delta)
            db.run("UPDATE match_players SET result=?, rp_delta=? WHERE match_id=? AND slot=?", r, delta, match_id,
                   p["slot"])
        db.run("UPDATE matches SET status='done' WHERE id=?", match_id)
        players = [p for p in ps if p["user_id"] is not None and not p["is_ghost"]]
    for p in players:                                       # skills / achievements earned by this match
        try:
            new_awards[p["slot"]] = rewards.evaluate(p["user_id"])["new"]
        except Exception:
            traceback.print_exc()
            new_awards[p["slot"]] = []
        row = db.one("SELECT extras FROM match_players WHERE match_id=? AND slot=?", match_id, p["slot"])
        extras = json.loads(row["extras"] or "{}")
        extras["new_awards"] = new_awards[p["slot"]]
        if p["slot"] in shielded:
            extras["shield"] = True
        db.run("UPDATE match_players SET extras=? WHERE match_id=? AND slot=?", json.dumps(extras), match_id, p["slot"])


REPORTS_FOR_BAN, BAN_DAYS = 3, 7


class Profane(Exception):
    pass


def strike(uid):
    """Count one answer with bad language. True if it was the player's first ever (= only a warning)."""
    first = db.one("SELECT profanity_strikes n FROM users WHERE id=?", uid)["n"] == 0
    db.run("UPDATE users SET profanity_strikes=profanity_strikes+1 WHERE id=?", uid)
    return first


def ban_until(user):
    b = user["ranked_ban_until"]
    return b if b and b > time.time() else None


def report(user, match_id):
    """Report the opponent whose answer had bad language. 3 reports = 1-week Ranked ban."""
    me = db.one("SELECT slot FROM match_players WHERE match_id=? AND user_id=? AND is_ghost=0", match_id, user["id"])
    opp = db.one("SELECT user_id, error FROM match_players WHERE match_id=? AND user_id IS NOT NULL AND user_id!=? "
                 "AND is_ghost=0", match_id, user["id"])
    if me is None or opp is None or opp["error"] != "profanity":
        return "not_found"
    if db.one("SELECT 1 FROM reports WHERE match_id=? AND reporter_id=?", match_id, user["id"]):
        return "already_reported"
    db.run("INSERT INTO reports (match_id, reporter_id, reported_id, created) VALUES (?,?,?,?)",
           match_id, user["id"], opp["user_id"], time.time())
    db.run("UPDATE users SET reports_open=reports_open+1 WHERE id=?", opp["user_id"])
    if db.one("SELECT reports_open n FROM users WHERE id=?", opp["user_id"])["n"] >= REPORTS_FOR_BAN:
        db.run("UPDATE users SET reports_open=0, ranked_ban_until=? WHERE id=?", time.time() + BAN_DAYS * 86400, opp["user_id"])
    return None


FREE_EMOTES = ("sticker_wave", "sticker_thumbs")   # everyone can send these two
EMOTE_GAP, EMOTE_MAX, EMOTE_SHOW = 2.5, 12, 6       # seconds between, per match, seconds visible


def send_emote(user, match_id, sticker):
    """A sticker during the match (not while answering). Returns None or an error key."""
    me = db.one("SELECT slot FROM match_players WHERE match_id=? AND user_id=? AND is_ghost=0", match_id, user["id"])
    m = db.one("SELECT status FROM matches WHERE id=?", match_id)
    if me is None or m is None:
        return "not_found"
    if sticker not in FREE_EMOTES and sticker not in cosmetics.owned(user["id"], user):
        return "not_owned"
    sent = db.all_("SELECT at FROM match_emotes WHERE match_id=? AND slot=? ORDER BY at DESC", match_id, me["slot"])
    if len(sent) >= EMOTE_MAX or (sent and time.time() - sent[0]["at"] < EMOTE_GAP):
        return "emote_wait"
    db.run("INSERT INTO match_emotes (match_id, slot, sticker, at) VALUES (?,?,?,?)", match_id, me["slot"], sticker, time.time())
    return None


def view(user, match_id):
    m = db.one("SELECT * FROM matches WHERE id=?", match_id)
    me = db.one("SELECT * FROM match_players WHERE match_id=? AND user_id=? AND is_ghost=0", match_id, user["id"])
    if m is None or me is None:
        return None
    if m["status"] == "done":
        recent = {r["match_id"] for r in db.all_(
            "SELECT p.match_id FROM match_players p JOIN matches mm ON mm.id=p.match_id WHERE p.user_id=? "
            "AND p.is_ghost=0 AND mm.status='done' ORDER BY mm.created DESC LIMIT ?", user["id"], HISTORY)}
        if match_id not in recent:
            return None                                 # only the last 10 matches are kept as a log
    if m["status"] == "live" and time.time() > m["deadline"]:
        finish(match_id)
        m = db.one("SELECT * FROM matches WHERE id=?", match_id)
    now = time.time()
    done = m["status"] == "done"
    players = []
    for p in db.all_("SELECT * FROM match_players WHERE match_id=? ORDER BY slot", match_id):
        u = db.one("SELECT * FROM users WHERE id=?", p["user_id"]) if p["user_id"] else None
        c = card(u, p["rp_before"]) if (u or not p["is_ghost"]) else card(None, p["rp_before"])
        if p["user_id"] and u is None:
            c.update(username="—", bot=False)
        c.update(slot=p["slot"], me=p["slot"] == me["slot"], ghost=bool(p["is_ghost"]),
                 state={"waiting": "speaking", "uploaded": "scoring", "running": "scoring"}
                 .get(p["status"], "ready") if not done else p["status"])
        if done:
            extras = json.loads(p["extras"] or "{}")
            err = p["error"] or ""
            c.update(overall=p["overall"], scores=json.loads(p["scores"] or "null"), result=p["result"],
                     rp_delta=p["rp_delta"], rp_after=p["rp_before"] + (p["rp_delta"] or 0),
                     rank_after=rank_for(p["user_id"], p["rp_before"] + (p["rp_delta"] or 0)),
                     error={"not_enough_speech": "ranked_no_speech", "profanity": "profanity_loss"}.get(err.split(":")[0], err.split(":")[0]) or None, error_n=err.split(":")[1] if ":" in err else None,
                     words=extras.get("words"), cefr=extras.get("cefr"), off_topic=bool(extras.get("off_topic")), topic=extras.get("topic"),
                     integrity=extras.get("integrity"))
            if p["slot"] != me["slot"] and u is not None and u["share_answers"] and not p["is_ghost"]:
                c["audio"] = bool(p["audio_path"]) and Path(p["audio_path"]).exists()   # the opponent shares answers
            if p["slot"] != me["slot"] and err == "profanity" and p["user_id"]:
                c["can_report"] = not db.one("SELECT 1 FROM reports WHERE match_id=? AND reporter_id=?", match_id, user["id"])
            if p["slot"] == me["slot"]:
                c["profanity_warn"] = extras.get("profanity") == "warn"
                c["new_awards"] = extras.get("new_awards", [])
                c["audio"] = bool(p["audio_path"]) and Path(p["audio_path"]).exists()
                c["shield"] = bool(extras.get("shield"))
        players.append(c)
    return {"id": m["id"], "kind": m["kind"], "status": m["status"], "now": now, "reveal_at": m["reveal_at"],
            "speak_at": m["speak_at"], "deadline": m["deadline"], "min_s": MIN_S, "max_s": MAX_S,
            "question": m["question"] if now >= m["reveal_at"] - 0.3 else None,
            "my_state": me["status"], "players": players,
            "emotes": [dict(e) for e in db.all_("SELECT slot, sticker, at FROM match_emotes WHERE match_id=? AND at>? ORDER BY at",
                                                 match_id, now - EMOTE_SHOW)]}


def overview(user):
    user = ensure_season(user)
    start, end = ranks.season_dates()
    history = []
    for r in db.all_("SELECT m.id, m.created, m.kind, m.question, p.result, p.overall, p.rp_delta, o.overall opp, "
                     "o.user_id opp_id, o.is_ghost opp_ghost FROM match_players p JOIN matches m ON m.id=p.match_id "
                     "JOIN match_players o ON o.match_id=p.match_id AND o.slot!=p.slot "
                     "WHERE p.user_id=? AND p.is_ghost=0 AND m.status='done' ORDER BY m.created DESC LIMIT ?",
                     user["id"], HISTORY):
        opp = db.one("SELECT username FROM users WHERE id=?", r["opp_id"]) if r["opp_id"] else None
        history.append({"id": r["id"], "created": r["created"], "result": r["result"], "me": r["overall"],
                        "opp": r["opp"], "rp_delta": r["rp_delta"], "kind": r["kind"],
                        "opp_name": opp["username"] if opp else ("Speakoff Bot" if r["kind"] == "bot" else "—")})
    return {"me": card(user), "lang": lang_of(user), "langs": plans.learn_langs(user), "ban_until": ban_until(user), "max_rank": ranks.rank_of(max(user["best_rp"], user["rp"])),
            "season": ranks.season_id(), "season_no": ranks.season_number(), "season_end": end.isoformat(),
            "limits": limits(user), "live": active_match(user["id"]), "history": history,
            "rules": {"read_s": READ_S, "min_s": MIN_S, "max_s": MAX_S}}


def leaderboard(user, scope="global", limit=50):
    """Highest-rated players this season (who played at least one ranked match), worldwide or in one country."""
    user = ensure_season(user)
    sid = ranks.season_id()
    # one rank per player for all languages, so both boards mix every language (user, 2026-11-25)
    src, rpc, sc = "users u", "u.rp", "u.season"
    where, args = (f"{sc}=? AND EXISTS (SELECT 1 FROM match_players p JOIN matches m ON m.id=p.match_id "
                   "WHERE p.user_id=u.id AND p.is_ghost=0 AND m.kind!='friendly' AND m.season=?)"), [sid, sid]
    if scope == "national":
        if not user["country"]:
            return {"scope": scope, "country": None, "board": [], "me_place": None}
        where += " AND u.country=?"
        args.append(user["country"])
    rows = db.all_(f"SELECT u.* FROM {src} WHERE {where} ORDER BY {rpc} DESC, u.id LIMIT ?", *args, limit)
    board = [{"username": u["username"], "rank": rank_for(u["id"], u["rp"]), "me": u["id"] == user["id"],
              "photo": f"/api/photo/{u['username']}?v={u['photo']}" if u["photo"] else None, "frame": u["frame"],
              "country": u["country"], "name_style": cosmetics.worn(u, "name_style")} for u in rows]
    me_place = None
    if db.one(f"SELECT 1 FROM {src} WHERE {where} AND u.id=?", *args, user["id"]):
        me_place = db.one(f"SELECT COUNT(*) n FROM {src} WHERE {where} AND ({rpc}>? OR ({rpc}=? AND u.id<?))",
                          *args, user["rp"], user["rp"], user["id"])["n"] + 1
    return {"scope": scope, "country": user["country"], "board": board, "me_place": me_place,
            "me": {**card(user), "country": user["country"]}, "season_no": ranks.season_number()}


def sweep_loop():
    """Finish matches whose time ran out while nobody was looking."""
    while True:
        try:
            for m in db.all_("SELECT id FROM matches WHERE status='live' AND deadline<?", time.time()):
                finish(m["id"])
        except Exception:
            traceback.print_exc()
        time.sleep(15)
