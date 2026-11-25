"""Measure the off-topic check on the labelled test set: python evaluate/topic_eval.py"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coach import topic  # noqa: E402
from evaluate.topic_testset import EXPECT, ITEMS  # noqa: E402


def run(verbose=False):
    rows, wrong = Counter(), []
    for q, a, label in ITEMS:
        r = topic.check(q, a)
        got = r["verdict"] if r else "ok"
        rows[(EXPECT[label], got)] += 1
        if got != EXPECT[label]:
            wrong.append((label, got, r, q, a[:70]))
    total = len(ITEMS)
    right = sum(n for (e, g), n in rows.items() if e == g)
    # the costly mistake: punishing a good answer
    false_pen = sum(n for (e, g), n in rows.items() if e == "ok" and g != "ok")
    missed_off = sum(n for (e, g), n in rows.items() if e == "off" and g == "ok")
    print(f"accuracy {right}/{total} = {right / total:.0%} | good answers punished: {false_pen} | off-topic missed: {missed_off}")
    for e in ("ok", "partial", "off"):
        print(f"  expected {e:8}", {g: rows[(e, g)] for g in ("ok", "partial", "off")})
    if verbose:
        for w in wrong:
            print("  WRONG", w)
    return right


if __name__ == "__main__":
    run(verbose="-v" in sys.argv)
