"""Part 3d: fine-tune the T5 grammar model on our "speech" training pairs.

Starts from vennify/t5-base-grammar-correction (already knows grammar correction) and
continues training on W&I + FCE pairs where punctuation/spelling fixes were removed,
so it learns to fix GRAMMAR only and to leave correct sentences alone.

Works on CPU (slow, ~0.3 s per sentence) and on a GPU (Colab: ~50x faster).
Saves a checkpoint every --save-minutes so a crash / Colab disconnect loses little;
run the same command again and it resumes from the last checkpoint.

Run (from the Speaking_Coach folder):
  python -m training.train_grammar --hours 4.5                 # stop after 4.5 hours
  python -m training.train_grammar --epochs 2 --batch 32        # on a GPU
  # bigger model (Colab T4): Adafactor needs much less memory than AdamW
  python train_grammar.py --base google/flan-t5-large --optim adafactor --lr 3e-4 --batch 16 --epochs 3
"""

import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, get_linear_schedule_with_warmup
from transformers.optimization import Adafactor

ROOT = Path(__file__).resolve().parent.parent
BASE_MODEL = "vennify/t5-base-grammar-correction"


def load_pairs(path):
    pairs = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        src, tgt = line.split("\t")
        pairs.append(("grammar: " + src, tgt))
    return pairs


def make_batches(pairs, batch_size, seed):
    """Group sentences of similar length into the same batch (less padding = faster),
    then shuffle the ORDER of the batches so training still sees a random mix."""
    rng = random.Random(seed)
    pairs = pairs[:]
    rng.shuffle(pairs)
    pairs.sort(key=lambda p: len(p[0]))
    batches = [pairs[i:i + batch_size] for i in range(0, len(pairs), batch_size)]
    rng.shuffle(batches)
    return batches


def encode(tokenizer, batch, max_len, device):
    enc = tokenizer([s for s, _ in batch], return_tensors="pt", padding=True,
                    truncation=True, max_length=max_len).to(device)
    labels = tokenizer([t for _, t in batch], return_tensors="pt", padding=True,
                       truncation=True, max_length=max_len).input_ids.to(device)
    labels[labels == tokenizer.pad_token_id] = -100        # don't learn to predict padding
    return enc, labels


@torch.no_grad()
def dev_loss(model, tokenizer, dev, batch_size, max_len, device):
    """Average loss on the dev set: lower = better. Used to see if training helps."""
    model.eval()
    total, count = 0.0, 0
    for i in range(0, len(dev), batch_size):
        enc, labels = encode(tokenizer, dev[i:i + batch_size], max_len, device)
        total += model(**enc, labels=labels).loss.item() * len(dev[i:i + batch_size])
        count += len(dev[i:i + batch_size])
    model.train()
    return total / count


def save(model, tokenizer, optimizer, scheduler, state, out, light=False):
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out)
    tokenizer.save_pretrained(out)
    if not light:                   # optimizer state = 2x the model size; only needed to resume exactly
        torch.save({"optimizer": optimizer.state_dict(), "scheduler": scheduler.state_dict()}, out / "trainer.pt")
    (out / "state.json").write_text(json.dumps(state, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default=str(ROOT / "data/grammar/train_speech.tsv"))
    ap.add_argument("--dev", default=str(ROOT / "data/grammar/dev_speech.tsv"))
    ap.add_argument("--out", default=str(ROOT / "models/grammar-speech-v1"))
    ap.add_argument("--base", default=BASE_MODEL, help="model to start from, e.g. google/flan-t5-large")
    ap.add_argument("--optim", choices=["adamw", "adafactor"], default="adamw",
                    help="adafactor = much less GPU memory (needed for t5-large on a 16 GB GPU)")
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--hours", type=float, default=0, help="stop after this many hours (0 = no limit)")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--max-len", type=int, default=96)
    ap.add_argument("--save-minutes", type=float, default=30)
    ap.add_argument("--light-save", action="store_true",
                    help="save only the model, not the optimizer (needs 0.9 GB instead of 2.7 GB of disk)")
    ap.add_argument("--dev-size", type=int, default=500, help="dev sentences used for the dev loss")
    args = ap.parse_args()

    # On Windows, tell the OS not to sleep while this process runs (released when it exits).
    import sys
    if sys.platform == "win32":
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    out = Path(args.out)
    resume = (out / "state.json").exists()
    source = str(out) if resume else args.base
    print(f"device={device}  starting from {source}")

    tokenizer = AutoTokenizer.from_pretrained(source)
    model = AutoModelForSeq2SeqLM.from_pretrained(source).to(device)
    model.train()

    train = load_pairs(args.train)
    dev = load_pairs(args.dev)[:args.dev_size]
    total_steps = math.ceil(len(train) / args.batch * args.epochs)

    if args.optim == "adafactor":
        optimizer = Adafactor(model.parameters(), lr=args.lr, scale_parameter=False,
                              relative_step=False, warmup_init=False)
    else:
        optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
    scheduler = get_linear_schedule_with_warmup(optimizer, int(0.03 * total_steps), total_steps)
    state = {"step": 0, "total_steps": total_steps, "log": []}
    if resume:
        state = json.loads((out / "state.json").read_text())
        if (out / "trainer.pt").exists():
            saved = torch.load(out / "trainer.pt")
            optimizer.load_state_dict(saved["optimizer"])
            scheduler.load_state_dict(saved["scheduler"])
        else:                       # light save: fresh optimizer, learning rate schedule moved to the same step
            for _ in range(state["step"]):
                scheduler.step()
        print(f"resuming at step {state['step']}/{total_steps}")
    else:
        d = dev_loss(model, tokenizer, dev, args.batch, args.max_len, device)
        state["log"].append({"step": 0, "dev_loss": round(d, 4)})
        print(f"dev loss before training: {d:.4f}")

    start = time.time()
    last_save = time.time()
    running = []
    epoch = 0
    while state["step"] < total_steps:
        batches = make_batches(train, args.batch, seed=epoch)
        # when resuming, skip the batches of this epoch that were already done
        done_in_epoch = state["step"] - epoch * len(batches)
        if done_in_epoch >= len(batches):
            epoch += 1
            continue
        for batch in batches[max(done_in_epoch, 0):]:
            enc, labels = encode(tokenizer, batch, args.max_len, device)
            loss = model(**enc, labels=labels).loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()
            state["step"] += 1
            running.append(loss.item())

            if state["step"] % 50 == 0:
                hours = (time.time() - start) / 3600
                speed = (time.time() - start) / max(len(running), 1)
                left = (total_steps - state["step"]) * speed / 3600
                print(f"step {state['step']}/{total_steps}  loss {sum(running[-50:]) / 50:.4f}  "
                      f"{hours:.2f} h  (~{left:.1f} h left)", flush=True)

            time_up = args.hours and (time.time() - start) / 3600 >= args.hours
            if time.time() - last_save >= args.save_minutes * 60 or time_up or state["step"] >= total_steps:
                d = dev_loss(model, tokenizer, dev, args.batch, args.max_len, device)
                state["log"].append({"step": state["step"], "train_loss": round(sum(running[-200:]) / len(running[-200:]), 4),
                                     "dev_loss": round(d, 4), "hours": round((time.time() - start) / 3600, 2)})
                save(model, tokenizer, optimizer, scheduler, state, out, args.light_save)
                print(f"  saved checkpoint, dev loss {d:.4f}", flush=True)
                last_save = time.time()
            if time_up:
                print("time limit reached, stopping (run again to continue)")
                return
            if state["step"] >= total_steps:
                break
        epoch += 1
    print("training finished")


if __name__ == "__main__":
    main()
