"""What Speakoff credits buy (prices decided 2026-11-24). Credits are only earned in the app, never sold for money.

  ranked      +1 ranked match today          30   (at most 1 a day; not for Pro, who has unlimited)
  recording   +1 recording (Free plan)       50   (at most 2 a day)
  shield      rank shield                   110   one lost ranked match costs no RP (1 a day, hold at most 3)
  plus_day    1 day of Plus                 290   Free plan only; buying again adds another day
  keep_audio  keep one recording's audio     40   on top of the last 10 (at most 5 kept for good)
Frames and other cosmetics: later.
"""

import time
from datetime import datetime, timedelta, timezone

from server import db, plans

ITEMS = {
    "ranked": {"price": 30, "per_day": 1},
    "recording": {"price": 50, "per_day": 2},
    "shield": {"price": 110, "per_day": 1, "hold": 3},
    "plus_day": {"price": 290},
    "keep_audio": {"price": 40, "hold": 5},
}


class ShopError(Exception):
    pass


def bought_today(uid, item):
    return db.one("SELECT COUNT(*) n FROM credit_buys WHERE user_id=? AND item=? AND day=?",
                  uid, item, plans.today())["n"]


def kept_count(uid):
    return db.one("SELECT COUNT(*) n FROM recordings WHERE user_id=? AND keep_forever=1 AND audio_deleted=0",
                  uid)["n"]


def plus_until(user):
    """End of the Plus time bought with credits (ISO, UTC) or None."""
    if user["plan"] == "plus" and user["plan_period"] == "credits" and user["plan_renews"]:
        return user["plan_renews"]
    return None


def expire(user):
    """Plus bought with credits ends by itself. Returns the (maybe updated) user row."""
    until = plus_until(user)
    if until and until <= datetime.now(timezone.utc).isoformat(timespec="seconds"):
        db.run("UPDATE users SET plan='free', plan_period=NULL, plan_renews=NULL WHERE id=?", user["id"])
        user = db.one("SELECT * FROM users WHERE id=?", user["id"])
    return user


def member_credits(user):
    """Yearly Plus / Pro: bonus credits every calendar month (Plus 300, Pro 800). Monthly plans get them once,
    when joining (see join_bonus)."""
    month = datetime.now().strftime("%Y-%m")
    n = plans.plan_of(user)["credits_month"]
    if n and user["plan_period"] == "yearly" and user["plan_credit_month"] != month:
        db.run("UPDATE users SET credits=credits+?, plan_credit_month=? WHERE id=? AND (plan_credit_month IS NULL OR plan_credit_month!=?)",
               n, month, user["id"], month)
        user = db.one("SELECT * FROM users WHERE id=?", user["id"])
    return user


def join_bonus(user):
    """Monthly Plus / Pro: the bonus credits once per account for each plan (Plus once, Pro once)."""
    plan = user["plan"]
    n = plans.plan_of(user)["credits_month"]
    given = set(filter(None, (user["plan_bonus_given"] or "").split(",")))
    if n and user["plan_period"] == "monthly" and plan not in given:
        db.run("UPDATE users SET credits=credits+?, plan_bonus_given=? WHERE id=?", n, ",".join(sorted(given | {plan})), user["id"])
        return n
    return 0


def state(user):
    uid = user["id"]
    out = {}
    for name, it in ITEMS.items():
        row = {"price": it["price"]}
        if "per_day" in it:
            row["left_today"] = max(it["per_day"] - bought_today(uid, name), 0)
            row["ok"] = row["left_today"] > 0
        if name == "recording":
            row["ok"] = row["ok"] and user["plan"] == "free"
        if name == "ranked":                              # Pro already has unlimited ranked matches
            row["ok"] = row["ok"] and user["plan"] != "pro"
        if name == "shield":
            row["have"] = user["shields"]
            row["ok"] = row["ok"] and user["shields"] < it["hold"]
        if name == "plus_day":
            row["until"] = plus_until(user)
            row["ok"] = user["plan"] == "free" or bool(row["until"])
        if name == "keep_audio":
            row["have"] = kept_count(uid)
            row["ok"] = row["have"] < it["hold"]
        out[name] = row
    return {"credits": user["credits"], "items": out}


def buy(user, item, ref=None):
    """Spend credits. Raises ShopError(code)."""
    if item not in ITEMS:
        raise ShopError("bad_item")
    it, uid = ITEMS[item], user["id"]
    st = state(user)["items"][item]
    if not st["ok"]:
        raise ShopError("shop_unavailable")
    rec = None
    if item == "keep_audio":
        rec = db.one("SELECT * FROM recordings WHERE id=? AND user_id=?", ref, uid)
        if rec is None or rec["keep_forever"] or rec["audio_deleted"] or not rec["audio_path"]:
            raise ShopError("shop_unavailable")
    # take the credits first, in one statement, so two taps at once cannot spend the same credits twice
    cur = db.run("UPDATE users SET credits=credits-? WHERE id=? AND credits>=?", it["price"], uid, it["price"])
    if cur.rowcount != 1:
        raise ShopError("not_enough_credits")
    db.run("INSERT INTO credit_buys (user_id, item, day, created, price, ref) VALUES (?,?,?,?,?,?)",
           uid, item, plans.today(), time.time(), it["price"], ref)
    if item == "recording":
        db.run("UPDATE users SET bonus_left=bonus_left+1 WHERE id=?", uid)
    elif item == "shield":
        db.run("UPDATE users SET shields=shields+1 WHERE id=?", uid)
    elif item == "plus_day":
        now = datetime.now(timezone.utc)
        start = max(now, datetime.fromisoformat(st["until"])) if st["until"] else now
        db.run("UPDATE users SET plan='plus', plan_period='credits', plan_renews=? WHERE id=?",
               (start + timedelta(days=1)).isoformat(timespec="seconds"), uid)
    elif item == "keep_audio":
        db.run("UPDATE recordings SET keep_forever=1 WHERE id=?", rec["id"])
    return db.one("SELECT * FROM users WHERE id=?", uid)
