"""Plans, limits and what each plan unlocks (decided 2026-11-22; ranked matches a day: 3 / 10 / 20 on 2026-11-23)."""

from datetime import date

PLANS = {
    "free": {"per_day": 1, "max_s": 70, "ranked": 3, "price_m": 0, "credits_month": 0, "langs": 2},
    "plus": {"per_day": 10, "max_s": 150, "ranked": 10, "price_m": 2.99, "credits_month": 300, "langs": 3},
    "pro": {"per_day": 30, "max_s": 270, "ranked": 20, "price_m": 7.99, "credits_month": 800, "langs": None},
}
for _p in PLANS.values():
    _p["price_y"] = round(_p["price_m"] * 10, 2)     # a year costs 10 months (decided 2026-11-24)
KEEP_AUDIOS = 10          # every plan: the last 10 recordings (normal + ranked answers) keep their audio
MIN_SECONDS = 60          # every recording: at least 1:00
DAILY_Q_MAX_S = 70        # the question of the day is free for everyone, at the free length
WELCOME_BONUS = 3         # free recordings for a new account


def plan_of(user):
    return PLANS.get(user["plan"], PLANS["free"])


def learn_langs(user):
    """The languages a player learns (Free 2, Plus 3, Pro all; user, 2026-11-25). The active one comes first and
    always stays; after a downgrade only the first ones that fit the plan are kept."""
    active = user["learn_lang"] or "en"
    out = [active] + [x for x in (user["learn_langs"] or "").split(",") if x and x != active]
    n = plan_of(user)["langs"]
    return out[:n] if n else out


def today():
    return date.today().isoformat()


def usage(user, db):
    """How many normal recordings the user can still make today (the daily question is separate)."""
    p = plan_of(user)
    used = db.one("SELECT COUNT(*) n FROM recordings WHERE user_id=? AND day=? AND is_daily=0 "
                  "AND used_bonus=0 AND is_mock=0 AND status!='failed'", user["id"], today())["n"]
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
        out.append({"id": name, **p, "keep": KEEP_AUDIOS, "save_pct": yearly_saving})
    return out
