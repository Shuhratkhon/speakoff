"""Clean data/grammar/synthetic_v3.tsv: who/which mistakes must only be made where we are SURE whether the
noun is a person. Person-ness is learned from Tatoeba itself: nouns written before "who" (soldier, customer)
are people; nouns only ever written before "which" are things.
  python -m training.filter_v3
"""
import bz2
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "tatoeba" / "eng_sentences.tsv.bz2"
PATH = ROOT / "data" / "grammar" / "synthetic_v3.tsv"
REL = re.compile(r"\b([a-z]+) (who|whom|which)\b")

who, which = Counter(), Counter()
with bz2.open(SRC, "rt", encoding="utf-8") as f:
    for line in f:
        for noun, rel in REL.findall(line.lower()):
            (which if rel == "which" else who)[noun] += 1


def person(noun):
    return who[noun] >= 2 and who[noun] >= which[noun]


def thing(noun):
    return which[noun] >= 2 and who[noun] <= 0.05 * which[noun]


kept, dropped = [], Counter()
for line in PATH.read_text(encoding="utf-8").splitlines():
    wrong, right = line.split("\t")
    wt, rt = wrong.lower().split(), right.lower().split()
    ok = True
    if len(wt) == len(rt):
        for i, (a, b) in enumerate(zip(wt, rt)):
            a, b = a.strip(".,?!"), b.strip(".,?!")
            if a != b and {a, b} & {"who", "which", "that", "what"} and i > 0:
                noun = rt[i - 1].strip(".,?!")
                if b == "who" and not person(noun):
                    ok = False; dropped["who-target, not sure person"] += 1
                elif b in ("that", "which") and a in ("who", "what") and not thing(noun):
                    ok = False; dropped["that-target, not sure thing"] += 1
    if ok:
        kept.append(line)
PATH.write_text("\n".join(kept) + "\n", encoding="utf-8")
print(f"kept {len(kept)}  dropped {dict(dropped)}")
