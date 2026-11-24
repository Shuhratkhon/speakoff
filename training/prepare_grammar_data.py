"""Part 3c: turn the M2 files into (wrong sentence -> correct sentence) pairs for training.

Sources (all free, from the BEA-2019 shared task, Cambridge):
  train: W&I+LOCNESS train (~34k sentences) + FCE train (~28k) + FCE test (~2.7k)
  dev:   FCE dev (~2.2k)  -> used during training to watch progress
  NOT used: W&I+LOCNESS dev (ABCN.dev) -> that is our benchmark in evaluate/grammar_eval.py,
            training on it would be cheating (the model would have seen the answers).

Two versions are written:
  *_full.tsv   : every teacher correction (punctuation, capitals, spelling, grammar)
  *_speech.tsv : punctuation / capitals / spelling corrections NOT applied, so the model only
                 learns grammar. In our app those come from Whisper, not the speaker.

Output: data/grammar/{train,dev}_{full,speech}.tsv   (columns: input <TAB> target)

Run (from the Speaking_Coach folder):
  python -m training.prepare_grammar_data
"""

import random
from pathlib import Path

from evaluate.grammar_eval import detokenize, read_m2

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "grammar"

TRAIN_FILES = [
    DATA / "wi+locness" / "m2" / "ABC.train.gold.bea19.m2",
    DATA / "fce" / "m2" / "fce.train.gold.bea19.m2",
    DATA / "fce" / "m2" / "fce.test.gold.bea19.m2",
]
DEV_FILES = [DATA / "fce" / "m2" / "fce.dev.gold.bea19.m2"]

NOT_SPEECH = ("PUNCT", "ORTH", "SPELL")
MAX_TOKENS = 64          # very long sentences are rare in speech and slow down training


def apply_edits(tokens, edits):
    """Apply M2 edits to a token list. Edits are applied from the END backwards,
    so the positions of earlier edits do not shift."""
    tokens = list(tokens)
    for start, end, correction in sorted(edits, reverse=True):
        tokens[start:end] = correction.split() if correction else []
    return tokens


def pairs_from_m2(path, speech):
    """Yield (wrong, correct) sentence pairs from one M2 file (first annotator only)."""
    for block in read_m2(path):
        tokens = block[0][2:].split()
        edits = []
        for line in block[1:]:
            span, etype, correction, *_, annotator = line[2:].split("|||")
            start, end = map(int, span.split())
            if start == -1 or etype == "noop" or annotator != "0":
                continue
            if speech and etype.split(":")[-1] in NOT_SPEECH:
                continue
            edits.append((start, end, correction))
        if not tokens or len(tokens) > MAX_TOKENS:
            continue
        yield detokenize(tokens), detokenize(apply_edits(tokens, edits))


def build(files, speech):
    seen, pairs = set(), []
    for f in files:
        for src, tgt in pairs_from_m2(f, speech):
            if src in seen:                      # skip exact duplicates
                continue
            seen.add(src)
            pairs.append((src, tgt))
    return pairs


def write(pairs, path):
    path.write_text("".join(f"{s}\t{t}\n" for s, t in pairs if "\t" not in s + t), encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for variant, speech in (("full", False), ("speech", True)):
        train = build(TRAIN_FILES, speech)
        dev = build(DEV_FILES, speech)
        random.Random(42).shuffle(train)
        write(train, OUT / f"train_{variant}.tsv")
        write(dev, OUT / f"dev_{variant}.tsv")

        changed = sum(s != t for s, t in train)
        print(f"{variant:<7} train {len(train):>6} pairs ({changed / len(train):.0%} have a mistake)"
              f"   dev {len(dev):>5} pairs")

    print("\nExamples (speech version):")
    for s, t in [p for p in build(TRAIN_FILES[:1], True) if p[0] != p[1]][:5]:
        print(f"  wrong:   {s}\n  correct: {t}\n")


if __name__ == "__main__":
    main()
