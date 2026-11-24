"""Plans, limits and what each plan unlocks (decided 2026-11-22; ranked matches a day: 3 / 10 / 20 on 2026-11-23)."""

from datetime import date

PLANS = {
    "free": {"per_day": 1, "max_s": 70, "keep_days": 14, "ranked": 3, "price_m": 0, "price_y": 0},
    "plus": {"per_day": 10, "max_s": 150, "keep_days": 30, "ranked": 10, "price_m": 2.99, "price_y": 23.99},
    "pro": {"per_day": 30, "max_s": 270, "keep_days": 90, "ranked": 20, "price_m": 7.99, "price_y": 63.99},
}
MIN_SECONDS = 60          # every recording: at least 1:00
DAILY_Q_MAX_S = 70        # the question of the day is free for everyone, at the free length
WELCOME_BONUS = 3         # free recordings for a new account


def plan_of(user):
    return PLANS.get(user["plan"], PLANS["free"])


def today():
    return date.today().isoformat()


def usage(user, db):
    """How many normal recordings the user can still make today (the daily question is separate)."""
    p = plan_of(user)
    used = db.one("SELECT COUNT(*) n FROM recordings WHERE user_id=? AND day=? AND is_daily=0 "
                  "AND used_bonus=0 AND status!='failed'", user["id"], today())["n"]
    daily_left = max(p["per_day"] - used, 0)
    bonus = user["bonus_left"] if user["plan"] == "free" else 0
    daily_answered = db.one("SELECT id FROM recordings WHERE user_id=? AND day=? AND is_daily=1 "
                            "AND status!='failed' ORDER BY created DESC LIMIT 1", user["id"], today())
    return {
        "plan": user["plan"],
        "bonus_left": bonus,
        "left_today": daily_left,
        "can_record": bonus > 0 or daily_left > 0,
        "unlimited": user["plan"] == "pro",
        "max_s": p["max_s"],
        "daily_answered": daily_answered["id"] if daily_answered else None,
    }


def public():
    """Plan list for the website."""
    out = []
    for name, p in PLANS.items():
        yearly_saving = round(100 * (1 - p["price_y"] / (12 * p["price_m"]))) if p["price_m"] else 0
        out.append({"id": name, **p, "save_pct": yearly_saving})
    return out
