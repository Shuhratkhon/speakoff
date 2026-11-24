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

from server import db, plans, questions, ranks, rewards

COUNTDOWN = 4            # "opponent found" -> question shown
READ_S = 5               # question shown -> recording starts
MIN_S, MAX_S = 30, 60    # answer length
GRACE = 45               # extra time for the upload after the longest answer
WAIT_PLAYER = 20         # seconds in the queue before a replay / bot match
QUEUE_STALE = 10         # a queued player who stopped asking is removed
K = 40                   # Elo factor
DRAW_GAP = 2             # less than 2 points apart = draw
HISTORY = 10             # match log: the last 10 matches, for every plan
SECTIONS = ["fluency", "grammar", "vocabulary", "pronunciation"]
LOCK = threading.RLock()


# ------------------------------------------------------------------ players

def ensure_season(user):
    """New season: keep half of the RP. Returns the fresh user row."""
    sid = ranks.season_id()
    if user["season"] != sid:
        rp = user["rp"] // 2 if user["season"] else 0
        db.run("UPDATE users SET rp=?, season=? WHERE id=?", rp, sid, user["id"])
        user = db.one("SELECT * FROM users WHERE id=?", user["id"])
    return user


def played_today(uid):
    return db.one("SELECT COUNT(*) n FROM match_players p JOIN matches m ON m.id=p.match_id "
                  "WHERE p.user_id=? AND p.is_ghost=0 AND m.day=?", uid, plans.today())["n"]


def limits(user):
    per_day = plans.plan_of(user)["ranked"]
    return {"per_day": per_day, "left": max(per_day - played_today(user["id"]), 0)}


def card(u, rp=None):
    """What other players see: name, photo, frame, rank, the 2 shown skills."""
    if u is None:
        return {"bot": True, "username": "Speakoff Bot", "rank": ranks.rank_of(rp or 0), "skills": [], "frame": "none",
                "photo": None}
    rp = u["rp"] if rp is None else rp
    shown = [s for s in (u["shown_skills"] or "").split(",") if s]
    return {"bot": False, "username": u["username"], "rank": ranks.rank_of(rp),
            "photo": f"/api/photo/{u['username']}?v={u['photo']}" if u["photo"] else None,
            "frame": u["frame"], "skills": rewards.shown_skills(u["id"], shown)}


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
    if limits(user)["left"] <= 0:
        return {"state": "limit"}
    now = time.time()
    with LOCK:
        db.run("INSERT OR REPLACE INTO ranked_queue (user_id, rp, joined, last_poll, match_id) VALUES (?,?,?,?,NULL)",
               user["id"], user["rp"], now, now)
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
    for o in db.all_("SELECT * FROM ranked_queue WHERE match_id IS NULL AND user_id!=?", me["user_id"]):
        waited = max(now - me["joined"], now - o["joined"])
        gap = abs(o["rp"] - me["rp"])
        if gap <= 150 + 20 * waited and (best is None or gap < abs(best["rp"] - me["rp"])):
            best = o
    if best is None:
        return None
    question = _question([me["user_id"], best["user_id"]])
    mid = _create("player", question, [
        {"user_id": me["user_id"], "rp_before": me["rp"]},
        {"user_id": best["user_id"], "rp_before": best["rp"]},
    ])
    db.run("UPDATE ranked_queue SET match_id=? WHERE user_id=?", mid, best["user_id"])
    return mid


def _recent_questions(uid, n=20):
    return {r["question"] for r in db.all_("SELECT m.question FROM matches m JOIN match_players p ON p.match_id=m.id "
                                           "WHERE p.user_id=? AND p.is_ghost=0 ORDER BY m.created DESC LIMIT ?", uid, n)}


def _question(uids):
    seen = set().union(*(_recent_questions(u) for u in uids))
    pool = [q for q in questions.RANKED if q not in seen] or questions.RANKED
    return random.choice(pool)


def _solo_match(user):
    """No player near: a replay of a real answer near this rank, else the bot."""
    seen = _recent_questions(user["id"])
    ghosts = db.all_("SELECT p.*, m.question FROM match_players p JOIN matches m ON m.id=p.match_id "
                     "WHERE p.status='done' AND p.is_ghost=0 AND p.user_id IS NOT NULL AND p.user_id!=? "
                     "AND abs(p.rp_before-?)<=400 ORDER BY random() LIMIT 30", user["id"], user["rp"])
    fresh = [gh for gh in ghosts if gh["question"] not in seen]
    gh = (fresh or ghosts or [None])[0]
    me = {"user_id": user["id"], "rp_before": user["rp"]}
    if gh is not None:
        owner = db.one("SELECT rp FROM users WHERE id=?", gh["user_id"])
        return _create("ghost", gh["question"], [me, {
            "user_id": gh["user_id"], "rp_before": owner["rp"] if owner else gh["rp_before"], "is_ghost": 1,
            "status": "done", "duration": gh["duration"], "overall": gh["overall"], "scores": gh["scores"],
            "extras": gh["extras"]}])
    return _create("bot", _question([user["id"]]), [me, {"user_id": None, "rp_before": user["rp"], "status": "bot"}])


def _create(kind, question, players):
    mid = uuid.uuid4().hex[:16]
    now = time.time()
    reveal = now + COUNTDOWN
    speak = reveal + READ_S
    db.run("INSERT INTO matches (id, season, kind, question, created, reveal_at, speak_at, deadline, status, day) "
           "VALUES (?,?,?,?,?,?,?,?,'live',?)", mid, ranks.season_id(), kind, question, now, reveal, speak,
           speak + MAX_S + GRACE, plans.today())
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
        d = rate.analyse(audio, cache=False, max_seconds=MAX_S)
        if d["n_words"] < worker.MIN_WORDS:
            raise worker.NotEnoughSpeech(d["n_words"])
        res = worker.summary(d, SECTIONS)
        lv = res["level"]
        extras = {"words": d["n_words"], "fillers": d["fluency"].get("fillers", 0),
                  "mistakes": sum(len(s["mistakes"]) for s in d["grammar_results"]),
                  "b2": lv["vocabulary"]["b2_plus"], "cefr": lv["cefr"]}
        db.run("UPDATE match_players SET status='done', overall=?, scores=?, extras=? WHERE match_id=? AND slot=?",
               res["overall"], json.dumps(res["sections"]), json.dumps(extras), match_id, slot)
    except Exception as e:
        if isinstance(e, worker.NotEnoughSpeech):
            error = f"not_enough_speech:{e.args[0]}"
        else:
            traceback.print_exc()
            error = "failed_sub"
        db.run("UPDATE match_players SET status='failed', error=? WHERE match_id=? AND slot=?", error, match_id, slot)
    finally:
        src.unlink(missing_ok=True)
        audio.unlink(missing_ok=True)          # ranked answers are not kept (only their scores)
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
                u = db.one("SELECT rp, best_rp FROM users WHERE id=?", p["user_id"])
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
                db.run("UPDATE users SET rp=rp+?, best_rp=max(best_rp, rp+?) WHERE id=?", delta, delta, p["user_id"])
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
        db.run("UPDATE match_players SET extras=? WHERE match_id=? AND slot=?", json.dumps(extras), match_id, p["slot"])


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
                     rank_after=ranks.rank_of(p["rp_before"] + (p["rp_delta"] or 0)),
                     error={"not_enough_speech": "ranked_no_speech"}.get(err.split(":")[0], err.split(":")[0]) or None, error_n=err.split(":")[1] if ":" in err else None,
                     words=extras.get("words"), cefr=extras.get("cefr"))
            if p["slot"] == me["slot"]:
                c["new_awards"] = extras.get("new_awards", [])
        players.append(c)
    return {"id": m["id"], "kind": m["kind"], "status": m["status"], "now": now, "reveal_at": m["reveal_at"],
            "speak_at": m["speak_at"], "deadline": m["deadline"], "min_s": MIN_S, "max_s": MAX_S,
            "question": m["question"] if now >= m["reveal_at"] - 0.3 else None,
            "my_state": me["status"], "players": players}


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
    return {"me": card(user), "season": ranks.season_id(), "season_no": ranks.season_number(), "season_end": end.isoformat(),
            "limits": limits(user), "live": active_match(user["id"]), "history": history,
            "rules": {"read_s": READ_S, "min_s": MIN_S, "max_s": MAX_S}}


def leaderboard(user, scope="global", limit=50):
    """Highest-rated players this season (who played at least one ranked match), worldwide or in one country."""
    user = ensure_season(user)
    sid = ranks.season_id()
    where, args = "u.season=? AND EXISTS (SELECT 1 FROM match_players p JOIN matches m ON m.id=p.match_id "                   "WHERE p.user_id=u.id AND p.is_ghost=0 AND m.kind!='friendly' AND m.season=?)", [sid, sid]
    if scope == "national":
        if not user["country"]:
            return {"scope": scope, "country": None, "board": [], "me_place": None}
        where += " AND u.country=?"
        args.append(user["country"])
    rows = db.all_(f"SELECT u.* FROM users u WHERE {where} ORDER BY u.rp DESC, u.id LIMIT ?", *args, limit)
    board = [{"username": u["username"], "rank": ranks.rank_of(u["rp"]), "me": u["id"] == user["id"],
              "photo": f"/api/photo/{u['username']}?v={u['photo']}" if u["photo"] else None, "frame": u["frame"],
              "country": u["country"]} for u in rows]
    me_place = None
    if db.one(f"SELECT 1 FROM users u WHERE {where} AND u.id=?", *args, user["id"]):
        me_place = db.one(f"SELECT COUNT(*) n FROM users u WHERE {where} AND (u.rp>? OR (u.rp=? AND u.id<?))",
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
