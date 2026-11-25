"""Cosmetics bought with credits (chosen by the user 2026-11-24): name styles, match entrance effects,
victory stickers. Other players see them: names everywhere, the entrance on the VS screen, the sticker on the
result screen when its owner wins. One of each kind can be worn at a time.
"""

import time

from server import db

ITEMS = {
    # name styles (colour / effect of the username)
    "name_ocean": 40, "name_sunset": 40, "name_mint": 40, "name_royal": 65,
    "name_gold": 95, "name_neon": 105, "name_aurora": 135,
    # entrance effects (player card on the VS screen)
    "enter_slide": 40, "enter_lightning": 80, "enter_flame": 95,
    "enter_shockwave": 105, "enter_stars": 120, "enter_portal": 135,
    # victory stickers (result screen, after a win)
    "sticker_gg": 40, "sticker_fire": 50, "sticker_cool": 65, "sticker_crown": 80,
    "sticker_rocket": 80, "sticker_target": 95, "sticker_trophy": 120,
    "sticker_clap": 50, "sticker_hundred": 65, "sticker_diamond": 105,
}
# earned, never sold: the 🎤 sticker is the reward for day 30 of the daily calendar (server/credits.py)
REWARD_ITEMS = {"sticker_mic": 30}
# members' items (added 2026-11-24): free with the plan, not sold for credits; hidden again if the plan ends
PLAN_ITEMS = {
    "name_frost": "plus", "name_candy": "plus", "enter_comet": "plus", "sticker_native": "plus",
    "name_galaxy": "pro", "name_lava": "pro", "enter_royal": "pro", "enter_vortex": "pro",
    "sticker_goat": "pro", "sticker_shush": "pro",
}
PLAN_LEVEL = {"free": 0, "plus": 1, "pro": 2}
KINDS = {"name": "name_style", "enter": "entrance", "sticker": "sticker"}     # item prefix -> users column


# Prices (2026-11-24): a Plus member can buy every credit cosmetic within 3 months:
# daily rewards days 1-90 = 1548 + Plus join bonus 300 = 1848 credits >= 1845 (all items together).


class CosmeticError(Exception):
    pass


def kind_of(item):
    return item.split("_", 1)[0]


def has_plan_item(user, item):
    return PLAN_LEVEL.get(user["plan"], 0) >= PLAN_LEVEL[PLAN_ITEMS[item]]


def owned(uid, user=None):
    have = {r["item"] for r in db.all_("SELECT item FROM user_items WHERE user_id=?", uid)}
    if user is not None:
        have |= {i for i in PLAN_ITEMS if has_plan_item(user, i)}
    return have


def worn(user, col):
    """What other players see: a members' item only while the plan is active."""
    item = user[col] or ""
    return "" if item in PLAN_ITEMS and not has_plan_item(user, item) else item


def state(user):
    have = owned(user["id"], user)
    on = {k: worn(user, col) for k, col in KINDS.items()}
    items = [{"id": i, "kind": kind_of(i), "price": 0, "plan": PLAN_ITEMS[i], "owned": i in have, "worn": on[kind_of(i)] == i}
             for i in PLAN_ITEMS]
    items += [{"id": i, "kind": kind_of(i), "price": 0, "plan": None, "reward_day": d, "owned": i in have, "worn": on[kind_of(i)] == i}
              for i, d in REWARD_ITEMS.items()]
    items += [{"id": i, "kind": kind_of(i), "price": p, "plan": None, "owned": i in have, "worn": on[kind_of(i)] == i}
              for i, p in ITEMS.items()]
    return {"credits": user["credits"], "worn": on, "plan": user["plan"], "items": items}


def buy(user, item):
    if item in PLAN_ITEMS:
        raise CosmeticError("plan_item")
    if item in REWARD_ITEMS:
        raise CosmeticError("reward_item")
    if item not in ITEMS:
        raise CosmeticError("bad_item")
    if item in owned(user["id"]):
        raise CosmeticError("already_owned")
    price = ITEMS[item]
    if db.run("UPDATE users SET credits=credits-? WHERE id=? AND credits>=?", price, user["id"], price).rowcount != 1:
        raise CosmeticError("not_enough_credits")
    db.run("INSERT INTO user_items (user_id, item, created) VALUES (?,?,?)", user["id"], item, time.time())
    db.run("INSERT INTO credit_buys (user_id, item, day, created, price, ref) VALUES (?,?,date('now','localtime'),?,?,?)",
           user["id"], "cosmetic", time.time(), price, item)
    db.run(f"UPDATE users SET {KINDS[kind_of(item)]}=? WHERE id=?", item, user["id"])       # wear it right away
    return db.one("SELECT * FROM users WHERE id=?", user["id"])


def grant(uid, item):
    """Give an earned item (e.g. the day-30 sticker); nothing happens if the player already has it."""
    db.run("INSERT OR IGNORE INTO user_items (user_id, item, created) VALUES (?,?,?)", uid, item, time.time())


def wear(user, kind, item):
    """item = '' takes it off."""
    if kind not in KINDS or (item and ((item not in ITEMS and item not in PLAN_ITEMS and item not in REWARD_ITEMS) or kind_of(item) != kind)):
        raise CosmeticError("bad_item")
    if item and item not in owned(user["id"], user):
        raise CosmeticError("not_owned")
    db.run(f"UPDATE users SET {KINDS[kind]}=? WHERE id=?", item, user["id"])
    return db.one("SELECT * FROM users WHERE id=?", user["id"])
