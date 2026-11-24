"""Part 3b: measure the grammar model on the BEA-2019 dev set (W&I+LOCNESS).

How it works
  1. Read N learner sentences + the teachers' corrections from the M2 file (fixed random sample).
  2. Let our grammar model correct each sentence.
  3. ERRANT turns our corrections into M2 edits and compares them with the teachers' edits
     -> precision, recall, F0.5.

We report two scores:
  official : every edit counts (how research papers report it)
  speech   : punctuation / capitals / spelling ignored, because in our app those come from
             Whisper, not the speaker (same rule as coach/grammar.py)

Run (from the Speaking_Coach folder):
  python -m evaluate.grammar_eval            # 300 sentences
  python -m evaluate.grammar_eval 1000       # more sentences = more reliable, slower
"""

import random
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD_M2 = ROOT / "data" / "wi+locness" / "m2" / "ABCN.dev.gold.bea19.m2"
OUT = ROOT / "evaluate" / "results"
SEED = 42                 # same seed = same sentences every run, so results are comparable
BATCH = 16                # sentences corrected at once (faster than one by one)
# ERRANT's -filt needs full type names: M:PUNCT, R:PUNCT, U:PUNCT, ...
SPEECH_IGNORE = [f"{op}:{cat}" for op in "MRU" for cat in ("PUNCT", "ORTH", "SPELL")]


def read_m2(path):
    """Return a list of blocks; each block = lines of one sentence ("S ..." + "A ..." lines)."""
    return [b.strip().splitlines() for b in path.read_text(encoding="utf-8").split("\n\n") if b.strip()]


def detokenize(tokens):
    """M2 sentences are split into tokens ("do n't", "it 's", "home ."); the model was trained
    on normal text, so glue them back: "don't", "it's", "home."."""
    text = " ".join(tokens)
    text = re.sub(r" (n't|'s|'re|'ve|'ll|'d|'m)\b", r"\1", text)
    text = re.sub(r" ([.,!?;:%)])", r"\1", text)
    text = re.sub(r"([($]) ", r"\1", text)
    text = re.sub(r"(\w) - (\w)", r"\1-\2", text)          # "medium - sized" -> "medium-sized"
    return text


def errant_compare(hyp_m2, ref_m2, ignore=None):
    """Run ERRANT's scorer and return (precision, recall, F0.5)."""
    exe = Path(sys.executable).parent / "errant_compare"
    cmd = [str(exe), "-hyp", str(hyp_m2), "-ref", str(ref_m2)]
    if ignore:
        cmd += ["-filt", *ignore]
    out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    # last table line: TP FP FN Prec Rec F0.5
    numbers = out.strip().splitlines()[-2].split()
    tp, fp, fn = map(int, numbers[:3])
    p, r, f = map(float, numbers[3:6])
    return {"TP": tp, "FP": fp, "FN": fn, "precision": p, "recall": r, "F0.5": f}


def main(n, model_path=None):
    import errant
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

    name = model_path or "vennify/t5-base-grammar-correction"
    print(f"model: {name}")
    tokenizer = AutoTokenizer.from_pretrained(name)
    model = AutoModelForSeq2SeqLM.from_pretrained(name)
    model.eval()
    annotator = errant.load("en")

    global OUT
    OUT = OUT / (Path(model_path).name if model_path else "baseline")
    OUT.mkdir(parents=True, exist_ok=True)
    blocks = read_m2(GOLD_M2)
    random.Random(SEED).shuffle(blocks)
    blocks = blocks[:n]

    # reference: the teachers' edits for exactly these sentences
    (OUT / "ref.m2").write_text("\n\n".join("\n".join(b) for b in blocks) + "\n\n", encoding="utf-8")
    originals = [b[0][2:].split() for b in blocks]                # "S It 's ..." -> tokens

    # our model's corrections, in batches
    corrected = []
    start = time.time()
    for i in range(0, n, BATCH):
        batch = ["grammar: " + detokenize(t) for t in originals[i:i + BATCH]]
        enc = tokenizer(batch, return_tensors="pt", padding=True)
        outputs = model.generate(**enc, max_length=256, num_beams=5)
        corrected += tokenizer.batch_decode(outputs, skip_special_tokens=True)
        print(f"  {min(i + BATCH, n)}/{n} sentences  ({time.time() - start:.0f} s)", end="\r")
    print()

    # ERRANT needs both sides tokenized the same way: original = M2 tokens, ours = spaCy tokens
    (OUT / "orig.txt").write_text("\n".join(" ".join(t) for t in originals) + "\n", encoding="utf-8")
    hyp_tokens = [" ".join(tok.text for tok in annotator.parse(c, tokenise=True)) for c in corrected]
    (OUT / "hyp.txt").write_text("\n".join(hyp_tokens) + "\n", encoding="utf-8")

    exe = Path(sys.executable).parent / "errant_parallel"
    subprocess.run([str(exe), "-orig", str(OUT / "orig.txt"), "-cor", str(OUT / "hyp.txt"),
                    "-out", str(OUT / "hyp.m2")], check=True, capture_output=True)

    official = errant_compare(OUT / "hyp.m2", OUT / "ref.m2")
    speech = errant_compare(OUT / "hyp.m2", OUT / "ref.m2", ignore=SPEECH_IGNORE)

    print(f"\nSentences: {n}    Time: {time.time() - start:.0f} s")
    print(f"{'':<10}{'TP':>6}{'FP':>6}{'FN':>6}{'Precision':>11}{'Recall':>9}{'F0.5':>8}")
    for name, s in (("official", official), ("speech", speech)):
        print(f"{name:<10}{s['TP']:>6}{s['FP']:>6}{s['FN']:>6}{s['precision']:>11.3f}{s['recall']:>9.3f}{s['F0.5']:>8.3f}")
    print("\nTP = correct fixes, FP = false alarms, FN = missed mistakes")
    print(f"Files written to {OUT}")


if __name__ == "__main__":
    # python -m evaluate.grammar_eval [N] [model_folder]
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300, sys.argv[2] if len(sys.argv) > 2 else None)
