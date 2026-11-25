"""Speakoff credits: collected once a day from the Home calendar (rules decided by the user 2026-11-23).

Day n = the n-th calendar day since the player's first collection. Missing a day does NOT restart anything:
that day is simply greyed out on the calendar (its reward is lost) and the count goes on.
  days 1-13 : 9, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14, 15 credits (+1 every 2 days)
  day 14    : the "Streak" frame (only on day 14; missed = no frame)
  day 15+   : 15 credits
  every 30th day (30, 60, 90 ...): 100 credits; day 30 also gives the 🎤 sticker (decided 2026-11-24)
The Home bar shows days 1-14 (swipe to scroll, today centred) and a "Future rewards" box in place of day 15.
"""

from datetime import date, datetime, timezone

from server import db

FRAME_DAY = 14


def has_streak_frame(uid):
    return bool(db.one("SELECT 1 FROM daily_claims WHERE user_id=? AND streak_day=? LIMIT 1", uid, FRAME_DAY))


def reward(n):
    """(kind, amount) for calendar day n."""
    if n % 30 == 0:
        return "credits", 100
    if n == FRAME_DAY:
        return "frame", 0
    if n < FRAME_DAY:
        return "credits", 9 + (n - 1) // 2
    return "credits", 15


def state(user):
    uid = user["id"]
    today = date.today()
    first = db.one("SELECT MIN(day) d FROM daily_claims WHERE user_id=?", uid)["d"]
    current = (today - date.fromisoformat(first)).days + 1 if first else 1
    taken = {r["streak_day"] for r in db.all_("SELECT streak_day FROM daily_claims WHERE user_id=?", uid)}
    days = []
    for n in range(1, FRAME_DAY + 1):
        kind, amount = reward(n)
        days.append({"n": n, "kind": kind, "amount": amount,
                     "state": "claimed" if n in taken else "missed" if n < current
                     else "today" if n == current else "later"})
    kind, amount = reward(current)
    credits = db.one("SELECT credits FROM users WHERE id=?", uid)["credits"]
    return {"days": days, "future": {"state": "today" if current > FRAME_DAY else "later", "per_day": 15, "big": 100},
            "current": current, "can_claim": current not in taken, "credits": credits,
            "next_kind": kind, "next_amount": amount}


def claim(user):
    st = state(user)
    if not st["can_claim"]:
        return None, st
    kind, amount = st["next_kind"], st["next_amount"]
    # the day is the server's date, never the phone's; two taps at once: only the first row counts
    if not db.run("INSERT OR IGNORE INTO daily_claims (user_id, day, streak_day, amount, claimed_at) VALUES (?,?,?,?,?)",
                  user["id"], date.today().isoformat(), st["current"], amount,
                  datetime.now(timezone.utc).isoformat(timespec="seconds")).rowcount:
        return None, state(user)
    if amount:
        db.run("UPDATE users SET credits=credits+? WHERE id=?", amount, user["id"])
    got = {"kind": kind, "amount": amount}
    from server import cosmetics
    for item, day in cosmetics.REWARD_ITEMS.items():
        if st["current"] == day:                         # day 30: also the 🎤 sticker
            cosmetics.grant(user["id"], item)
            got["sticker"] = item
    return got, state(user)
