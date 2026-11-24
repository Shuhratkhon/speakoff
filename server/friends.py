"""Friends: search players, friend requests, friends list (with rank and who is online), friendly challenges.

A friendly match is a normal 1v1 match (same question, 5 s to read, 30-60 s of speaking, same scoring), but it
gives no RP and does not count for statistics or skills. It does count toward the matches a day (the models cost
the same). A challenge waits 2 minutes for the friend to accept.
"""

import time
import uuid

from server import db, ranked

ONLINE_S = 120             # seen in the last 2 minutes = online
CHALLENGE_TTL = 120        # a challenge waits 2 minutes


def _uid(username):
    r = db.one("SELECT id FROM users WHERE username=?", (username or "").strip())
    return r["id"] if r else None


def relation(me, other):
    """'friend' | 'sent' | 'received' | None"""
    if db.one("SELECT 1 FROM friendships WHERE user_id=? AND friend_id=? AND status='accepted'", me, other):
        return "friend"
    if db.one("SELECT 1 FROM friendships WHERE user_id=? AND friend_id=? AND status='pending'", me, other):
        return "sent"
    if db.one("SELECT 1 FROM friendships WHERE user_id=? AND friend_id=? AND status='pending'", other, me):
        return "received"
    return None


def _card(u):
    c = ranked.card(ranked.ensure_season(u))
    c["online"] = bool(u["last_seen"] and time.time() - u["last_seen"] < ONLINE_S)
    return c


def overview(me):
    friends = [_card(u) for u in db.all_(
        "SELECT u.* FROM friendships f JOIN users u ON u.id=f.friend_id WHERE f.user_id=? AND f.status='accepted'", me)]
    friends.sort(key=lambda c: (not c["online"], -c["rank"]["rp"]))
    incoming = [_card(u) for u in db.all_(
        "SELECT u.* FROM friendships f JOIN users u ON u.id=f.user_id WHERE f.friend_id=? AND f.status='pending' "
        "ORDER BY f.created DESC", me)]
    outgoing = [_card(u) for u in db.all_(
        "SELECT u.* FROM friendships f JOIN users u ON u.id=f.friend_id WHERE f.user_id=? AND f.status='pending' "
        "ORDER BY f.created DESC", me)]
    return {"friends": friends, "incoming": incoming, "outgoing": outgoing, "challenges": pending_challenges(me)}


def search(me, q):
    q = (q or "").strip()
    if len(q) < 2:
        return []
    rows = db.all_("SELECT * FROM users WHERE username LIKE ? ESCAPE '\\' AND id!=? ORDER BY length(username), username "
                   "LIMIT 10", q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%", me)
    return [{**_card(u), "relation": relation(me, u["id"])} for u in rows]


def request(me, username):
    other = _uid(username)
    if other is None or other == me:
        return "user_not_found"
    rel = relation(me, other)
    if rel == "friend":
        return None
    if rel == "received":                      # they already asked: this accepts it
        return respond(me, username, True)
    db.run("INSERT OR IGNORE INTO friendships (user_id, friend_id, status, created) VALUES (?,?,'pending',?)",
           me, other, time.time())
    return None


def respond(me, username, accept):
    other = _uid(username)
    if other is None or relation(me, other) != "received":
        return "user_not_found"
    if accept:
        db.run("UPDATE friendships SET status='accepted' WHERE user_id=? AND friend_id=?", other, me)
        db.run("INSERT OR REPLACE INTO friendships (user_id, friend_id, status, created) VALUES (?,?,'accepted',?)",
               me, other, time.time())
    else:
        db.run("DELETE FROM friendships WHERE user_id=? AND friend_id=?", other, me)
    return None


def remove(me, username):
    other = _uid(username)
    if other is not None:
        db.run("DELETE FROM friendships WHERE (user_id=? AND friend_id=?) OR (user_id=? AND friend_id=?)",
               me, other, other, me)


# ------------------------------------------------------------------ friendly challenges

def pending_challenges(me):
    now = time.time()
    out = []
    for c in db.all_("SELECT c.*, u.username FROM challenges c JOIN users u ON u.id=c.from_id WHERE c.to_id=? "
                     "AND c.status='pending' AND c.created>?", me, now - CHALLENGE_TTL):
        out.append({"id": c["id"], "from": _card(db.one("SELECT * FROM users WHERE id=?", c["from_id"])),
                    "expires_in": round(c["created"] + CHALLENGE_TTL - now)})
    return out


def challenge(me_user, username):
    me = me_user["id"]
    other = _uid(username)
    if other is None or relation(me, other) != "friend":
        return None, "user_not_found"
    if ranked.limits(me_user)["left"] <= 0:
        return None, "no_matches_left"
    db.run("UPDATE challenges SET status='cancelled' WHERE from_id=? AND status='pending'", me)
    cid = uuid.uuid4().hex[:12]
    db.run("INSERT INTO challenges (id, from_id, to_id, created, status) VALUES (?,?,?,?,'pending')",
           cid, me, other, time.time())
    return cid, None


def challenge_state(me, cid):
    c = db.one("SELECT * FROM challenges WHERE id=? AND (from_id=? OR to_id=?)", cid, me, me)
    if c is None:
        return None
    status = c["status"]
    if status == "pending" and time.time() > c["created"] + CHALLENGE_TTL:
        status = "expired"
        db.run("UPDATE challenges SET status='expired' WHERE id=?", cid)
    to = db.one("SELECT * FROM users WHERE id=?", c["to_id"])
    return {"id": cid, "status": status, "match": c["match_id"], "to": _card(to),
            "expires_in": max(0, round(c["created"] + CHALLENGE_TTL - time.time()))}


def answer_challenge(me_user, cid, accept):
    me = me_user["id"]
    c = db.one("SELECT * FROM challenges WHERE id=? AND to_id=?", cid, me)
    if c is None or c["status"] != "pending" or time.time() > c["created"] + CHALLENGE_TTL:
        return None, "challenge_gone"
    if not accept:
        db.run("UPDATE challenges SET status='declined' WHERE id=?", cid)
        return None, None
    if ranked.limits(me_user)["left"] <= 0:
        return None, "no_matches_left"
    with ranked.LOCK:
        a = db.one("SELECT * FROM users WHERE id=?", c["from_id"])
        mid = ranked._create("friendly", ranked._question([a["id"], me]), [
            {"user_id": a["id"], "rp_before": a["rp"]}, {"user_id": me, "rp_before": me_user["rp"]}])
        db.run("UPDATE challenges SET status='accepted', match_id=? WHERE id=?", mid, cid)
    return mid, None


def cancel_challenge(me, cid):
    db.run("UPDATE challenges SET status='cancelled' WHERE id=? AND from_id=? AND status='pending'", cid, me)
