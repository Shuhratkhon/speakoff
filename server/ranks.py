"""Ranks and seasons for Ranked mode.

7 ranks, each with 3 divisions of 100 RP (III -> II -> I), Master has no divisions:
  Copper 0-299 · Bronze 300-599 · Silver 600-899 · Gold 900-1199 · Platinum 1200-1499 · Diamond 1500-1799 · Master 1800+
A season lasts 1 calendar month (decided 2026-11-23). At a new season everyone keeps half of their RP.
"""

from datetime import date

RANKS = ["copper", "bronze", "silver", "gold", "platinum", "diamond", "master"]
RANK_SIZE = 300
DIV_SIZE = 100
MASTER_RP = RANK_SIZE * (len(RANKS) - 1)        # 1800


def rank_of(rp):
    rp = max(0, int(rp or 0))
    if rp >= MASTER_RP:
        return {"rank": "master", "index": 6, "div": None, "rp": rp, "floor": MASTER_RP, "next": None}
    index = rp // RANK_SIZE
    step = (rp % RANK_SIZE) // DIV_SIZE           # 0, 1, 2
    floor = index * RANK_SIZE + step * DIV_SIZE
    return {"rank": RANKS[index], "index": index, "div": 3 - step, "rp": rp, "floor": floor, "next": floor + DIV_SIZE}


def rank_floor(name):
    return RANKS.index(name) * RANK_SIZE


def season_id(d=None):
    d = d or date.today()
    return f"{d.year}-{d.month}"


FIRST_SEASON = (2026, 11)                     # Season 1 = November 2026 (launch)


def season_number(sid=None):
    year, month = (int(x) for x in (sid or season_id()).split("-"))
    return (year - FIRST_SEASON[0]) * 12 + month - FIRST_SEASON[1] + 1


def season_dates(sid=None):
    sid = sid or season_id()
    year, month = (int(x) for x in sid.split("-"))
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)   # first day of the next season
    return start, end
