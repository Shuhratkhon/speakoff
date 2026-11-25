"""Skills, achievements, avatar frames and the profile statistics.

Skills (like PLAB's player skills): after every 20 ranked matches the player gets ONE skill that describes how they
played in those 20 matches (e.g. Grammar Guard = grammar averaged 80+). Skills stack: getting a skill you already
own adds x1. The same skill can be gained only once per season (then the next best-fitting one is given).
  x1-x4 = blue, x5-x14 = green, x15+ = purple. A player shows at most 2 skills on the profile.
Achievements have 3 tiers, e.g. "Play ranked matches" x10 (blue) -> x50 (green) -> x200 (purple).
Everything is computed from the database: evaluate(user_id) saves whatever is newly earned.
"""

import json
import statistics
from datetime import datetime, timezone

from server import credits, db
from server.ranks import RANKS, rank_floor

BLOCK = 20                                  # ranked matches per skill
RARITY = ["blue", "green", "purple"]
SECTIONS = ["fluency", "grammar", "vocabulary", "pronunciation"]


def skill_rarity(count):
    return "purple" if count >= 15 else "green" if count >= 5 else "blue"


# ------------------------------------------------------------------ skills: how well each one fits 20 matches
# each function gets the 20 match rows and returns a fit: >= 1 means the player qualifies (higher = stronger fit)

def _avg(rows, key):
    vals = [r["scores"].get(key, 0) for r in rows if r["overall"] is not None]
    return statistics.mean(vals) if vals else 0


def _done(rows):
    return [r for r in rows if r["overall"] is not None]


def _longest(results, what="win"):
    best = cur = 0
    for res in results:
        cur = cur + 1 if res == what else 0
        best = max(best, cur)
    return best


def _gap(r):
    return (r["overall"] or 0) - (r["opp_overall"] or 0)


def _comebacks(rows):
    n, losses = 0, 0
    for r in rows:
        if r["result"] == "win" and losses >= 3:
            n += 1
        losses = losses + 1 if r["result"] == "loss" else 0
    return n


def _improvement(rows):
    d = [r["overall"] for r in _done(rows)]
    return (statistics.mean(d[-5:]) - statistics.mean(d[:5])) if len(d) >= 10 else 0


SKILLS = [  # id, icon, fit
    ("smooth_talker", "🌊", lambda rs: _avg(rs, "fluency") / 80),
    ("grammar_guard", "🛡️", lambda rs: _avg(rs, "grammar") / 80),
    ("word_smith", "📚", lambda rs: _avg(rs, "vocabulary") / 80),
    ("crystal_clear", "💎", lambda rs: _avg(rs, "pronunciation") / 80),
    ("all_rounder", "⭐", lambda rs: min(_avg(rs, s) for s in SECTIONS) / 75),
    ("perfectionist", "🏆", lambda rs: sum(1 for r in _done(rs) if r["overall"] >= 90) / 2),
    ("unstoppable", "🔥", lambda rs: _longest([r["result"] for r in rs]) / 5),
    ("giant_slayer", "⚔️", lambda rs: sum(1 for r in rs if r["result"] == "win" and r["kind"] != "bot"
                                          and (r["opp_rp"] or 0) - r["rp_before"] >= 200) / 2),
    ("iron_voice", "🎙️", lambda rs: sum(1 for r in _done(rs) if (r["duration"] or 0) >= 58) / 15),
    ("zero_slip", "✔️", lambda rs: sum(1 for r in _done(rs) if r["extras"].get("mistakes") == 0
                                        and r["extras"].get("words", 0) >= 60) / 5),
    ("rich_words", "🎨", lambda rs: sum(1 for r in _done(rs) if r["extras"].get("b2", 0) >= 20) / 8),
    ("no_filler", "🤫", lambda rs: sum(1 for r in _done(rs) if r["extras"].get("fillers") == 0) / 12),
    ("steady", "📏", lambda rs: min(1.6, 4 / max(statistics.pstdev([r["overall"] for r in _done(rs)]), 0.5))
     if len(_done(rs)) >= 10 else 0),
    ("comeback", "🔁", lambda rs: float(_comebacks(rs))),
    ("clutch", "🎯", lambda rs: sum(1 for r in rs if r["result"] == "win" and 0 < _gap(r) < 5) / 4),
    ("dominator", "🦁", lambda rs: sum(1 for r in rs if r["result"] == "win" and _gap(r) >= 15) / 4),
    ("fast_learner", "📈", lambda rs: _improvement(rs) / 5),
    ("long_talker", "🗣️", lambda rs: statistics.mean([r["extras"].get("words", 0) for r in _done(rs)] or [0]) / 120),
    ("champion", "👑", lambda rs: (sum(1 for r in rs if r["result"] == "win") / len(rs)) / 0.65 if rs else 0),
    ("fighter", "🥊", lambda rs: 0.5),       # everyone who plays 20 matches can get this one
]
SKILL_ICON = {s: ic for s, ic, _f in SKILLS}

# achievements: id, icon, measure, three tiers
ACHIEVEMENTS = [
    ("ranked_matches", "⚔️", "matches", [10, 50, 200]),
    ("ranked_wins", "🥇", "wins", [5, 25, 100]),
    ("win_streak", "🔥", "win_streak", [3, 5, 10]),
    ("giant_wins", "🗡️", "upsets", [1, 10, 50]),
    ("best_rank", "🛡️", "best_rp", [rank_floor("silver"), rank_floor("platinum"), rank_floor("master")]),
    ("seasons", "🗓️", "seasons", [1, 3, 6]),
    ("skills_total", "✨", "skills_total", [1, 5, 15]),
    ("high_scores", "🌟", "high_scores", [5, 25, 100]),
    ("ranked_words", "💬", "ranked_words", [1000, 10000, 50000]),
    ("recordings", "🎤", "recordings", [5, 25, 100]),
    ("dailies", "📅", "dailies", [7, 30, 100]),
    ("videos", "🎥", "videos", [1, 10, 50]),
]

# frame id -> what unlocks it (None = always)
FRAMES = [("none", None)] + [(r, ("rank", r)) for r in RANKS] + [
    ("flame", ("ach", "win_streak", 2)), ("crystal", ("ach", "high_scores", 2)),
    ("veteran", ("ach", "ranked_matches", 3)), ("streak", ("daily", 14)),
]


# ------------------------------------------------------------------ data

def match_rows(uid, season=None):
    """The user's finished ranked matches, oldest first (their answers used as replays are not counted)."""
    rows = db.all_(
        "SELECT m.created, m.kind, m.season, m.day, p.result, p.overall, p.scores, p.extras, p.duration, p.rp_before, "
        "p.rp_delta, o.rp_before opp_rp, o.overall opp_overall FROM match_players p JOIN matches m ON m.id=p.match_id "
        "JOIN match_players o ON o.match_id=p.match_id AND o.slot!=p.slot "
        "WHERE p.user_id=? AND p.is_ghost=0 AND m.kind!='friendly' AND p.result IN ('win','loss','draw')"
        + (" AND m.season=?" if season else "") + " ORDER BY m.created", *((uid, season) if season else (uid,)))
    out = []
    for r in rows:
        d = dict(r)
        d["scores"] = json.loads(r["scores"] or "{}")
        d["extras"] = json.loads(r["extras"] or "{}")
        out.append(d)
    return out


def skill_counts(uid):
    return {r["skill"]: r["n"] for r in db.all_("SELECT skill, COUNT(*) n FROM skill_grants WHERE user_id=? "
                                                "GROUP BY skill", uid)}


def _grant_skills(uid, rows):
    """One skill for every finished block of 20 ranked matches. Returns the new ones."""
    new = []
    have = {r["block"] for r in db.all_("SELECT block FROM skill_grants WHERE user_id=?", uid)}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for block in range(1, len(rows) // BLOCK + 1):
        if block in have:
            continue
        chunk = rows[(block - 1) * BLOCK: block * BLOCK]
        season = chunk[-1]["season"]
        taken = {r["skill"] for r in db.all_("SELECT skill FROM skill_grants WHERE user_id=? AND season=?", uid, season)}
        fits = sorted(((f(chunk), sid) for sid, _ic, f in SKILLS), reverse=True)
        choice = next((sid for fit, sid in fits if fit >= 1 and sid not in taken), None)
        if choice is None and "fighter" not in taken:
            choice = "fighter"
        if choice is None:
            continue
        db.run("INSERT OR IGNORE INTO skill_grants (user_id, block, skill, season, earned) VALUES (?,?,?,?,?)",
               uid, block, choice, season, now)
        n = db.one("SELECT COUNT(*) n FROM skill_grants WHERE user_id=? AND skill=?", uid, choice)["n"]
        new.append({"kind": "skill", "id": choice, "icon": SKILL_ICON[choice], "count": n, "rarity": skill_rarity(n)})
    return new


def measures(uid, rows=None):
    u = db.one("SELECT * FROM users WHERE id=?", uid)
    rows = match_rows(uid) if rows is None else rows
    results = [r["result"] for r in rows]
    done = _done(rows)
    rec = db.one("SELECT COUNT(*) n, SUM(mode='video') v, SUM(is_daily) d, SUM(overall>=80) hi "
                 "FROM recordings WHERE user_id=? AND status='done'", uid)
    per_season = {}
    for r in rows:
        per_season[r["season"]] = per_season.get(r["season"], 0) + 1
    return {
        "matches": len(rows), "wins": results.count("win"), "win_streak": _longest(results),
        "upsets": sum(1 for r in rows if r["result"] == "win" and r["kind"] != "bot" and (r["opp_rp"] or 0) > r["rp_before"]),
        "best_rp": u["best_rp"], "seasons": sum(1 for n in per_season.values() if n >= BLOCK),
        "skills_total": db.one("SELECT COUNT(*) n FROM skill_grants WHERE user_id=?", uid)["n"],
        "high_scores": sum(1 for r in done if r["overall"] >= 80) + (rec["hi"] or 0),
        "ranked_words": sum(r["extras"].get("words", 0) for r in done),
        "recordings": rec["n"] or 0, "dailies": rec["d"] or 0, "videos": rec["v"] or 0,
    }


def evaluate(uid):
    """Give new skills / achievement tiers. Returns {skills, achs, new} for the profile page."""
    rows = match_rows(uid)
    new = _grant_skills(uid, rows)
    m = measures(uid, rows)
    have = {r["award"]: r["earned"] for r in db.all_("SELECT award, earned FROM user_awards WHERE user_id=? AND "
                                                     "kind='ach'", uid)}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    achs = []
    for aid, ic, key, tiers in ACHIEVEMENTS:
        value = m.get(key, 0)
        tier = 0
        for i, target in enumerate(tiers, 1):
            if value >= target:
                tier = i
                if f"{aid}:{i}" not in have:
                    db.run("INSERT OR IGNORE INTO user_awards (user_id, kind, award, earned) VALUES (?, 'ach', ?, ?)",
                           uid, f"{aid}:{i}", now)
                    new.append({"kind": "ach", "id": aid, "icon": ic, "tier": i, "rarity": RARITY[i - 1],
                                "target": target})
        achs.append({"id": aid, "icon": ic, "value": value, "tiers": tiers, "tier": tier,
                     "rarity": RARITY[tier - 1] if tier else None,
                     "next": tiers[tier] if tier < 3 else None, "rank_tiers": aid == "best_rank"})
    counts = skill_counts(uid)
    last = {r["skill"]: r["earned"] for r in db.all_("SELECT skill, MAX(earned) earned FROM skill_grants "
                                                     "WHERE user_id=? GROUP BY skill", uid)}
    skills = [{"id": sid, "icon": ic, "count": counts.get(sid, 0),
               "rarity": skill_rarity(counts[sid]) if sid in counts else None, "earned": last.get(sid)}
              for sid, ic, _f in SKILLS]
    return {"skills": skills, "achs": achs, "new": new, "next_skill_in": BLOCK - len(rows) % BLOCK,
            "matches": len(rows)}


def frames(uid):
    u = db.one("SELECT best_rp FROM users WHERE id=?", uid)
    have = {r["award"] for r in db.all_("SELECT award FROM user_awards WHERE user_id=? AND kind='ach'", uid)}
    out = []
    for fid, need in FRAMES:
        ok = need is None or (need[0] == "rank" and u["best_rp"] >= rank_floor(need[1])) or \
            (need[0] == "ach" and f"{need[1]}:{need[2]}" in have) or \
            (need[0] == "daily" and credits.has_streak_frame(uid))
        out.append({"id": fid, "unlocked": bool(ok), "need": list(need) if need else None})
    return out


def earned_skills(uid):
    return set(skill_counts(uid))


def shown_skills(uid, ids):
    counts = skill_counts(uid)
    return [{"id": s, "icon": SKILL_ICON[s], "count": counts[s], "rarity": skill_rarity(counts[s])}
            for s in ids if s in counts]


def stats(uid, season=None):
    """Profile statistics (like a game's season stats), for one season or all seasons."""
    rows = match_rows(uid, season)
    done = _done(rows)
    results = [r["result"] for r in rows]
    n = len(rows)
    wins = results.count("win")
    avg = {s: round(_avg(done, s)) for s in SECTIONS}
    overalls = [r["overall"] for r in done]
    consistency = max(0, min(100, round(100 - 4 * statistics.pstdev(overalls)))) if len(overalls) >= 2 else 0
    win_rate = round(100 * (wins + results.count("draw")) / n, 1) if n else 0   # a draw counts as a win here
    cur = 0
    for res in reversed(results):
        if res == "draw" or (cur > 0 and res != "win") or (cur < 0 and res != "loss"):
            break
        cur += 1 if res == "win" else -1
    return {
        "matches": n, "wins": wins, "losses": results.count("loss"), "draws": results.count("draw"),
        "win_rate": win_rate, "top_score": max(overalls, default=0),
        "average": round(statistics.mean(overalls)) if overalls else 0,
        "longest_streak": _longest(results), "current_streak": cur,
        "upsets": sum(1 for r in rows if r["result"] == "win" and r["kind"] != "bot" and (r["opp_rp"] or 0) > r["rp_before"]),
        "perfect": sum(1 for r in done if r["overall"] >= 90),
        "talk_time": round(statistics.mean([r["duration"] for r in done if r["duration"]])) if any(r["duration"] for r in done) else 0,
        "radar": {**avg, "consistency": consistency, "win_rate": round(win_rate)},
    }
