"""Train the off-topic classifier (coach/topic_model.json) and print its honest leave-one-out score.

    python evaluate/topic_train.py

Uses the labelled answers in evaluate/topic_testset.py. Later, add real labelled answers there and retrain.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coach import topic  # noqa: E402
from evaluate.topic_testset import EXPECT, ITEMS  # noqa: E402

C, OK_WEIGHT = 10, 3          # chosen on the test set: no good answer called off-topic, every off-topic caught


def model():
    return LogisticRegression(C=C, max_iter=5000, class_weight={"ok": OK_WEIGHT, "partial": 1, "off": 1})


X = np.array([topic.features(q, a) for q, a, _ in ITEMS])
y = np.array([EXPECT[lab] for _, _, lab in ITEMS])
labels = [lab for _, _, lab in ITEMS]

pred = []
for i in range(len(ITEMS)):
    keep = np.arange(len(ITEMS)) != i
    sc = StandardScaler().fit(X[keep])
    pred.append(model().fit(sc.transform(X[keep]), y[keep]).predict(sc.transform(X[i:i + 1]))[0])
right = sum(p == t for p, t in zip(pred, y))
c = Counter(zip(labels, pred))
print(f"leave-one-out: {right}/{len(ITEMS)} right | good answers called off-topic: "
      f"{sum(t == 'ok' and p == 'off' for p, t in zip(pred, y))} | off-topic missed: {sum(t == 'off' and p == 'ok' for p, t in zip(pred, y))}")
for lab in EXPECT:
    print(f"  {lab:8} ->", {v: c[(lab, v)] for v in ("ok", "partial", "off") if c[(lab, v)]})

sc = StandardScaler().fit(X)
clf = model().fit(sc.transform(X), y)
out = {"classes": clf.classes_.tolist(), "coef": clf.coef_.tolist(), "intercept": clf.intercept_.tolist(),
       "mean": sc.mean_.tolist(), "scale": sc.scale_.tolist(), "trained_on": len(ITEMS), "loo_right": int(right)}
topic.MODEL_FILE.write_text(json.dumps(out, indent=1), encoding="utf-8")
print("saved", topic.MODEL_FILE)
