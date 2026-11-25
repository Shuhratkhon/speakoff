"""Plans, limits and what each plan unlocks (decided 2026-11-22; ranked matches a day: 3 / 10 / 20 on 2026-11-23)."""

from datetime import date, timedelta

PLANS = {
    "free": {"per_day": 1, "max_s": 70, "ranked": 5, "price_m": 0, "credits_month": 0, "langs": 2},
    "plus": {"per_day": 10, "max_s": 150, "ranked": 15, "price_m": 2.99, "credits_month": 300, "langs": 3},
    "pro": {"per_day": 30, "max_s": 270, "ranked": None, "price_m": 7.99, "credits_month": 800, "langs": None},
}
for _p in PLANS.values():
    _p["price_y"] = round(_p["price_m"] * 10, 2)     # a year costs 10 months (decided 2026-11-24)
FAIR_RANKED = 30          # Pro: unlimited ranked matches, fair use 30 a day (user, 2026-11-26)
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


LANG_COOLDOWN = 30        # days before a removed language's slot can take a new language (user, 2026-11-26)


def lang_cooling(user):
    """{lang: "YYYY-MM-DD" the slot is free again} for languages removed in the last 30 days (not on Pro)."""
    if plan_of(user)["langs"] is None:
        return {}
    out = {}
    for item in filter(None, (user["lang_removed"] or "").split(",")):
        lang, day = item.split(":")
        free = date.fromisoformat(day) + timedelta(days=LANG_COOLDOWN)
        if free > date.today():
            out[lang] = free.isoformat()
    return out


def set_langs(user, new):
    """Check a new list of learning languages. Returns (error, params, cooling) - error None when allowed.
    Free 2 / Plus 3 / Pro all; a removed language's slot takes a NEW language only after 30 days
    (putting back the language that was removed is always fine)."""
    cap = plan_of(user)["langs"]
    old = learn_langs(user)
    if not new:
        return "lang_need_one", {}, None
    if cap and len(new) > cap:
        return "lang_limit", {}, None
    cooling = {k: v for k, v in lang_cooling(user).items() if k not in new}     # re-added ones are free again
    if cap:
        for lang in old:
            if lang not in new:
                cooling[lang] = (date.today() + timedelta(days=LANG_COOLDOWN)).isoformat()
        brand_new = [x for x in new if x not in old]
        if brand_new and len(new) + len(cooling) > cap:
            return "lang_cooldown", {"date": min(cooling.values())}, None
    return None, {}, cooling


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
        out.append({"id": name, **p, "fair_ranked": FAIR_RANKED, "keep": KEEP_AUDIOS, "save_pct": yearly_saving})
    return out
