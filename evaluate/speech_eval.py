"""Grammar test on SPOKEN-style sentences (evaluate/speech_test.tsv).

The BEA benchmark (grammar_eval.py) is written essays. This test is what our app hears:
short spoken sentences with typical learner mistakes, plus CORRECT sentences
(to count false alarms). Each line: wrong <TAB> correct [ || other correct version ...]

Scores (mistakes compared exactly like coach/grammar.py shows them: punctuation,
capitals and spelling ignored):
  fixed     : model found the mistake AND gave the right fix
  found     : model marked the right place (fix may differ), what the learner sees highlighted
  false     : model "fixed" something that was not wrong
  clean ok  : correct sentences left untouched (higher = fewer false alarms)
  perfect   : wrong sentences fully corrected

Run (from the Speaking_Coach folder):
  python -m evaluate.speech_eval                                   # our model (from coach/grammar.py)
  python -m evaluate.speech_eval vennify/t5-base-grammar-correction
  python -m evaluate.speech_eval models/grammar-speech-v1 --passes 2
"""

import argparse
import time
from pathlib import Path

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

from coach import grammar

TEST = Path(__file__).resolve().parent / "speech_test.tsv"
BATCH = 16


def load_test():
    items = []
    for line in TEST.read_text(encoding="utf-8").splitlines():
        if line.strip():
            wrong, right = line.split("\t")
            items.append((wrong, [r.strip() for r in right.split("||")]))
    return items


def correct_all(sentences, tokenizer, model, passes):
    """Correct many sentences in batches; passes=2 runs the model again on its own output."""
    for _ in range(passes):
        out = []
        for i in range(0, len(sentences), BATCH):
            enc = tokenizer(["grammar: " + s for s in sentences[i:i + BATCH]], return_tensors="pt", padding=True)
            ids = model.generate(**enc, max_length=128, num_beams=5)
            out += tokenizer.batch_decode(ids, skip_special_tokens=True)
        sentences = out
    return sentences


def edits(original, corrected):
    return {(m["token_start"], m["token_end"], m["right"].lower()) for m in grammar.find_mistakes(original, corrected)}


def overlaps(a, b):
    """Same place in the sentence (spans touch, or both are insertions at the same spot)."""
    if a[0] == a[1] or b[0] == b[1]:
        return a[0] == b[0] or (a[0] < b[1] and b[0] < a[1])
    return a[0] < b[1] and b[0] < a[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model", nargs="?", default=grammar.MODEL_NAME)
    ap.add_argument("--passes", type=int, default=1)
    ap.add_argument("--show", action="store_true", help="print every sentence the model got wrong")
    args = ap.parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model)
    model.eval()

    items = load_test()
    start = time.time()
    hyps = correct_all([w for w, _ in items], tokenizer, model, args.passes)

    tp = fp = fn = found = gold_total = 0
    clean_total = clean_ok = wrong_total = perfect = 0
    problems = []
    for (wrong, rights), hyp in zip(items, hyps):
        h = edits(wrong, hyp)
        # several correct versions may exist: compare with the one that matches best
        best = max((edits(wrong, r) for r in rights), key=lambda g: (len(h & g), -len(h ^ g)))
        if not best:                                     # a correct sentence
            clean_total += 1
            clean_ok += not h
        else:
            wrong_total += 1
            perfect += h == best
            gold_total += len(best)
            found += sum(any(overlaps(g, x) for x in h) for g in best)
        tp += len(h & best)
        fp += len(h - best)
        fn += len(best - h)
        if h != best:
            problems.append((wrong, hyp, rights[0]))

    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    f05 = 1.25 * p * r / (0.25 * p + r) if p + r else 0.0
    print(f"model: {args.model}   passes: {args.passes}   ({time.time() - start:.0f} s)")
    print(f"  sentences: {wrong_total} with mistakes, {clean_total} correct")
    print(f"  mistakes fixed : {tp}/{gold_total} = {tp / gold_total:.1%}   (recall)")
    print(f"  mistakes found : {found}/{gold_total} = {found / gold_total:.1%}   (right place, any fix)")
    print(f"  false alarms   : {fp}    precision {p:.3f}    F0.5 {f05:.3f}")
    print(f"  clean ok       : {clean_ok}/{clean_total} = {clean_ok / clean_total:.1%}   correct sentences left alone")
    print(f"  perfect        : {perfect}/{wrong_total} = {perfect / wrong_total:.1%}   wrong sentences fully fixed")
    if args.show:
        print("\nwrong / model / expected:")
        for wrong, hyp, right in problems:
            print(f"  {wrong}\n    model: {hyp}\n    want:  {right}")


if __name__ == "__main__":
    main()
