"""Korean off-topic check (2026-11-26): does a Korean answer talk about the question?

One free multilingual model, intfloat/multilingual-e5-small (MIT, CPU, ~470 MB), embeds the question, the answer,
and all 1000 Korean bank questions (server/question_bank_ko.py). Signals:
  sim     how close the answer is to its own question
  rank    how many bank questions the answer fits better than its own question
  better  how much closer the best other bank question is than its own question
An answer is "off" only when it is clearly about something else (low sim AND many other questions fit better), so a
short, simple or indirect learner answer is never punished. Calibrated on evaluate/ko_topic_testset.py
(evaluate/ko_topic_eval.py). "repeated" (a memorised speech) is checked in server/worker.py for every language.
"""

import re
import threading

MODEL = "intfloat/multilingual-e5-small"
MIN_CHARS = 25           # Hangul syllables; shorter answers are not judged
OFF_RANK, OFF_BETTER = 100, 0.042   # evaluate/ko_topic_eval.py (2026-11-26): 39/40 right, no good answer called off;
                                     # good answers: rank <= 158 with gap <= 0.032, off answers: gap >= 0.049 from rank 170

_lock = threading.Lock()
_m = {}


def _load():
    with _lock:
        if not _m:
            from sentence_transformers import SentenceTransformer
            from server.question_bank_ko import TOPICS
            _m["model"] = SentenceTransformer(MODEL, device="cpu")
            _m["bank"] = [q for qs in TOPICS.values() for q in qs]
            _m["bank_emb"] = _m["model"].encode(["query: " + q for q in _m["bank"]], normalize_embeddings=True,
                                                batch_size=64)
    return _m


def features(question, text):
    import numpy as np
    m = _load()
    a = m["model"].encode(["passage: " + text], normalize_embeddings=True)[0]
    q = m["model"].encode(["query: " + question], normalize_embeddings=True)[0]
    sim = float(a @ q)
    others = m["bank_emb"] @ a
    rank = int((others > sim + 1e-6).sum())
    return {"sim": sim, "rank": rank, "better": float(np.max(others) - sim)}


def check(question, text):
    """{"verdict": "ok"|"off", "off": bool, "sim", "rank"} or None when the answer is too short to judge."""
    if not question or not text or len(re.findall(r"[가-힣]", text)) < MIN_CHARS:
        return None
    f = features(question, text)
    off = f["rank"] >= OFF_RANK and f["better"] >= OFF_BETTER
    return {"verdict": "off" if off else "ok", "off": off, "sim": round(f["sim"], 3), "rank": f["rank"]}
