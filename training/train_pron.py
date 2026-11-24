"""Pronunciation scoring model (GOPT-style), trained on speechocean762 teacher scores.

Input per expected sound (from evaluate/speechocean_eval.py features):
  - average log-probability of every English sound over the sound's frames (61 numbers: what was heard)
  - GOP, length in frames
  - which sound was expected (learned embedding)
A small transformer looks at the whole sentence and predicts what the 5 teachers would give:
  every sound (0-2), every word (0-10), and the sentence: accuracy, fluency, prosody, total (0-10).

Train on the 2500 train sentences, judge on the 2500 test sentences (different speakers):
  python -m training.train_pron            # ~10-20 min on CPU
Saves models/pron-gopt/model.pt (+ settings) and prints correlations (PCC) with the teachers.
Published on speechocean762 for reference (PCC): GOP baseline phone 0.45-0.6 / sentence acc ~0.7,
GOPT (Gong et al. 2022) phone 0.61, word 0.53, sentence accuracy 0.71, total 0.74.
"""

import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
OUT = ROOT / "models" / "pron-gopt"
UTT_KEYS = ["h_accuracy", "h_fluency", "h_prosodic", "h_total"]
torch.set_num_threads(4)


def load(split):
    path = LOGS / f"so762feat_{split}.jsonl"
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def phone_vocab(recs):
    return {p: i + 1 for i, p in enumerate(sorted({p for r in recs for p in r["phones"]}))}    # 0 = padding


def to_tensors(recs, vocab, max_len=64):
    n = len(recs)
    dim = len(recs[0]["feat"][0]) + 3
    x = torch.zeros(n, max_len, dim)
    ph = torch.zeros(n, max_len, dtype=torch.long)
    mask = torch.zeros(n, max_len, dtype=torch.bool)          # True = real sound
    y_ph = torch.zeros(n, max_len)
    y_wd = torch.zeros(n, max_len)
    y_ut = torch.zeros(n, len(UTT_KEYS))
    for i, r in enumerate(recs):
        L = min(len(r["phones"]), max_len)
        feat = np.array(r["feat"][:L])
        gop = np.clip(np.array(r["gop"][:L]), -10, 1)[:, None]
        dur = np.log1p(np.array(r["dur"][:L]))[:, None]
        rate = np.full((L, 1), len(r["phones"]) / max(r["speech_frames"], 1) * 10)    # sounds per 0.2 s: speed
        x[i, :L] = torch.tensor(np.hstack([feat, gop, dur, rate]), dtype=torch.float32)
        ph[i, :L] = torch.tensor([vocab.get(p, 0) for p in r["phones"][:L]])
        mask[i, :L] = True
        y_ph[i, :L] = torch.tensor(r["h_phone"][:L])
        y_wd[i, :L] = torch.tensor([r["h_word"][w] for w in r["word_of"][:L]], dtype=torch.float32)
        y_ut[i] = torch.tensor([r[k] for k in UTT_KEYS], dtype=torch.float32)
    return x, ph, mask, y_ph, y_wd, y_ut


class GOPT(nn.Module):
    def __init__(self, in_dim, n_phones, d=64, layers=3, heads=4, n_utt=len(UTT_KEYS), max_len=64):
        super().__init__()
        self.inp = nn.Linear(in_dim, d)
        self.ph = nn.Embedding(n_phones + 1, d, padding_idx=0)
        self.pos = nn.Parameter(torch.zeros(1, max_len + n_utt, d))
        self.cls = nn.Parameter(torch.zeros(1, n_utt, d))       # one summary token per sentence score
        enc = nn.TransformerEncoderLayer(d, heads, dim_feedforward=4 * d, dropout=0.1, batch_first=True)
        self.encoder = nn.TransformerEncoder(enc, layers)
        self.head_phone = nn.Linear(d, 1)
        self.head_word = nn.Linear(d, 1)
        self.head_utt = nn.ModuleList([nn.Linear(d, 1) for _ in range(n_utt)])
        nn.init.normal_(self.pos, std=0.02); nn.init.normal_(self.cls, std=0.02)

    def forward(self, x, ph, mask):
        h = self.inp(x) + self.ph(ph)
        b = x.shape[0]
        h = torch.cat([self.cls.expand(b, -1, -1), h], 1) + self.pos[:, : h.shape[1] + self.cls.shape[1]]
        pad = torch.cat([torch.zeros(b, self.cls.shape[1], dtype=torch.bool), ~mask], 1)
        h = self.encoder(h, src_key_padding_mask=pad)
        n = self.cls.shape[1]
        utt = torch.cat([head(h[:, i]) for i, head in enumerate(self.head_utt)], 1)
        return self.head_phone(h[:, n:]).squeeze(-1), self.head_word(h[:, n:]).squeeze(-1), utt


def pcc(a, b):
    return float(np.corrcoef(a, b)[0, 1])


def evaluate(model, data):
    x, ph, mask, y_ph, y_wd, y_ut = data
    model.eval()
    with torch.no_grad():
        p_ph, p_wd, p_ut = model(x, ph, mask)
    m = mask.numpy()
    res = {"phone": pcc(p_ph.numpy()[m], y_ph.numpy()[m])}
    # word score: one value per word (average of its sounds' predictions)
    res["word"] = pcc(p_wd.numpy()[m], y_wd.numpy()[m])
    for i, k in enumerate(UTT_KEYS):
        res[k[2:]] = pcc(p_ut[:, i].numpy(), y_ut[:, i].numpy())
    return res


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    torch.manual_seed(seed); random.seed(seed); np.random.seed(seed)
    train, test = load("train"), load("test")
    vocab = phone_vocab(train + test)
    tr, te = to_tensors(train, vocab), to_tensors(test, vocab)
    # normalise inputs with train statistics
    m = tr[2]
    mean = tr[0][m].mean(0); std = tr[0][m].std(0) + 1e-6
    tr = ((tr[0] - mean) / std * m[..., None],) + tr[1:]
    te = ((te[0] - mean) / std * te[2][..., None],) + te[1:]
    print(f"train {len(train)}  test {len(test)}  input {tr[0].shape[-1]} numbers per sound  phones {len(vocab)}")

    model = GOPT(tr[0].shape[-1], len(vocab))
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=0.01)
    epochs, bs = 100, 25
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=1e-3, total_steps=epochs * math.ceil(len(train) / bs))
    best, best_state = -1, None
    for ep in range(epochs):
        model.train()
        order = torch.randperm(len(train))
        for i in range(0, len(train), bs):
            idx = order[i:i + bs]
            x, ph, mask, y_ph, y_wd, y_ut = (t[idx] for t in tr)
            p_ph, p_wd, p_ut = model(x, ph, mask)
            # scores to the same 0-2 range so no task dominates
            loss = ((p_ph - y_ph)[mask] ** 2).mean() + ((p_wd - y_wd / 5)[mask] ** 2).mean() + \
                   ((p_ut - y_ut / 5) ** 2).mean()
            opt.zero_grad(); loss.backward(); opt.step(); sched.step()
        if (ep + 1) % 10 == 0:
            # model selection on the TRAIN set's last 10% would be cleaner; we report test only at the end
            r = evaluate(model, tr)
            score = r["phone"] + r["accuracy"]
            print(f"epoch {ep + 1:3}  train PCC phone {r['phone']:.3f} accuracy {r['accuracy']:.3f}", flush=True)
    r = evaluate(model, te)
    print("\nTEST (unseen speakers) PCC with teachers:")
    for k, v in r.items():
        print(f"  {k:10} {v:.3f}")
    OUT.mkdir(parents=True, exist_ok=True)
    torch.save({"state": model.state_dict(), "vocab": vocab, "mean": mean, "std": std,
                "in_dim": tr[0].shape[-1], "utt_keys": UTT_KEYS, "test": r}, OUT / "model.pt")
    print(f"saved -> {OUT / 'model.pt'}")


if __name__ == "__main__":
    main()
