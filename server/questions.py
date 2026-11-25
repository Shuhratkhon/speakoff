"""Questions for the Question of the day and Ranked matches: both use the same 1000-question bank
(server/question_bank.py, 2026-11-25). The daily question walks through the bank in a fixed shuffled order, so
the same question comes back only after 1000 days; it is the same for everyone on the same day."""

import random
from datetime import date

from server.question_bank import QUESTIONS

_ORDER = QUESTIONS[:]
random.Random(20261125).shuffle(_ORDER)      # fixed order: topics are mixed, every day is different


def bank(lang="en"):
    if lang == "ko":
        from server.question_bank_ko import QUESTIONS as KO
        return KO
    return QUESTIONS


_ORDERS = {}


def for_day(day=None, lang="en"):
    day = day or date.today()
    if lang not in _ORDERS:
        order = bank(lang)[:]
        random.Random(20261125).shuffle(order)
        _ORDERS[lang] = order
    return _ORDERS[lang][day.toordinal() % len(_ORDERS[lang])]


# Ranked matches: the same 1000 questions
RANKED = QUESTIONS
