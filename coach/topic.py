"""Off-topic check, version 2 (2026-11-25): does the answer talk about the question?

Four small free models (Apache 2.0, CPU) each give a signal, and a small trained classifier (coach/topic_model.json,
made by evaluate/topic_train.py from the 100 labelled answers in evaluate/topic_testset.py) combines them:
  * all-MiniLM-L6-v2            meaning of question vs answer, and vs the 1000 bank questions
  * multi-qa-MiniLM-L6-cos-v1   the same, trained on real question/answer pairs
  * ms-marco-MiniLM-L6-v2       "is this text relevant to the question?" (cross-encoder)
  * qnli-distilroberta-base     "does this sentence answer the question?" (cross-encoder)
  * Qwen2.5-0.5B-Instruct       a small AI judge asked "does the answer respond?" (its yes/partly/no probabilities)
The answer is also checked in chunks of ~2 sentences, so answers that drift away are noticed.

Verdicts: "ok"; "partial" (part of the answer is off the question: feedback only, no penalty, because this is
the less certain call); "off" (overall capped at OFF_CAP); "repeated" (a memorised speech: the same text as one of
the player's earlier answers to a different question; treated like "off").
Leave-one-out on the test set (2026-11-25): 89/100 right (84 without the AI judge), no good answer called off-topic,
only 1 good answer given the "partial" tip (5 without the judge), 19/20 off-topic answers caught. Retrain with real answers when there are enough (evaluate/topic_train.py).
"""

import json
import re
import threading
from pathlib import Path

OFF_CAP = 40
MIN_WORDS = 15
SURE_OFF_SIM, SURE_OFF_BETTER = 0.10, 0.30   # no on-topic test answer was below 0.22
REPEAT_SHARE = 0.5          # >= 50% of the answer's 4-word phrases already used in one earlier answer = memorised
MODELS = {"bi": "sentence-transformers/all-MiniLM-L6-v2", "qa": "sentence-transformers/multi-qa-MiniLM-L6-cos-v1",
          "ce": "cross-encoder/ms-marco-MiniLM-L6-v2", "nli": "cross-encoder/qnli-distilroberta-base",
          "llm": "Qwen/Qwen2.5-0.5B-Instruct"}
JUDGE = ("You check speaking-test answers. Decide if the answer responds to the question. "
         "Personal stories and indirect answers that still respond count as yes. "
         "Talking about the same general theme without answering is partly. "
         "Starting on the question and then talking about something unrelated is partly. "
         "A different topic is no. Reply with one word: yes, partly or no.")
MODEL_FILE = Path(__file__).with_name("topic_model.json")

_lock = threading.Lock()
_m = {}


def _load():
    with _lock:
        if not _m:
            from sentence_transformers import CrossEncoder, SentenceTransformer
            from server.question_bank import QUESTIONS
            for k in ("bi", "qa"):
                _m[k] = SentenceTransformer(MODELS[k], device="cpu")
                _m[k + "_bank"] = _m[k].encode(QUESTIONS, normalize_embeddings=True, batch_size=256)
            for k in ("ce", "nli"):
                _m[k] = CrossEncoder(MODELS[k], device="cpu")
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            _m["tok"] = AutoTokenizer.from_pretrained(MODELS["llm"])
            _m["llm"] = AutoModelForCausalLM.from_pretrained(MODELS["llm"], dtype=torch.float32).eval()
            _m["llm_ids"] = [[_m["tok"].encode(w)[0] for w in (" " + c, c)] for c in ("yes", "partly", "no")]
            _m["clf"] = json.loads(MODEL_FILE.read_text(encoding="utf-8")) if MODEL_FILE.exists() else None
    return _m


def chunks(text):
    """Sentences joined into pieces of at least 8 words."""
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    out, cur = [], ""
    for s in sents:
        cur = f"{cur} {s}".strip()
        if len(cur.split()) >= 8:
            out.append(cur)
            cur = ""
    if cur:
        if out and len(cur.split()) < 8:
            out[-1] += " " + cur
        else:
            out.append(cur)
    return out or [text]


def _prob(scores):
    import torch
    t = torch.tensor(scores)
    return (torch.sigmoid(t) if t.dim() == 1 else torch.softmax(t, -1)[:, -1]).tolist()


def judge(question, text):
    """The small AI judge: probabilities of yes / partly / no."""
    import torch
    m = _load()
    msgs = [{"role": "system", "content": JUDGE},
            {"role": "user", "content": f"Question: {question}\nAnswer: {text}\nDoes the answer respond to the question?"}]
    x = m["tok"](m["tok"].apply_chat_template(msgs, tokenize=False, add_generation_prompt=True), return_tensors="pt")
    with torch.no_grad():
        p = torch.softmax(m["llm"](**x).logits[0, -1], -1)
    probs = [float(sum(p[i] for i in ids)) for ids in m["llm_ids"]]
    s = sum(probs) or 1.0
    return [v / s for v in probs]


def features(question, text):
    """The 18 numbers the classifier uses (see evaluate/topic_train.py)."""
    from sentence_transformers import util
    m = _load()
    cs = chunks(text)
    words = [len(c.split()) for c in cs]
    f = {}
    for k in ("bi", "qa"):
        q, a = m[k].encode([question, text], normalize_embeddings=True)
        sim = float(util.cos_sim(q, a))
        f[k + "_sim"] = sim
        f[k + "_better"] = float((util.cos_sim(m[k + "_bank"], a).flatten() > sim).float().mean())
        f[k + "_ch"] = util.cos_sim(q, m[k].encode(cs, normalize_embeddings=True)).flatten().tolist()
    f["ce"] = _prob(m["ce"].predict([(question, text)], convert_to_numpy=True))[0]
    f["ce_ch"] = _prob(m["ce"].predict([(question, c) for c in cs], convert_to_numpy=True))
    f["nli"] = _prob(m["nli"].predict([(question, text)], convert_to_numpy=True))[0]
    f["nli_ch"] = _prob(m["nli"].predict([(question, c) for c in cs], convert_to_numpy=True))

    def cover(key, t):
        return sum(w for w, s in zip(words, f[key]) if s >= t) / sum(words)

    return [f["bi_sim"], f["bi_better"], f["ce"], f["qa_sim"], f["qa_better"], f["nli"],
            cover("bi_ch", .35), cover("ce_ch", .1), cover("qa_ch", .35), cover("nli_ch", .55),
            min(f["qa_ch"]), max(f["qa_ch"]), min(f["nli_ch"]), max(f["nli_ch"])] + _judge_feats(question, text)


def _judge_feats(question, text):
    import math
    yes, part, no = judge(question, text)
    return [yes, part, no, math.log(yes + 1e-6) - math.log(no + 1e-6)]


def _classify(x, clf):
    z = [(v - mu) / sd for v, mu, sd in zip(x, clf["mean"], clf["scale"])]
    scores = {c: b + sum(w * v for w, v in zip(ws, z)) for c, ws, b in zip(clf["classes"], clf["coef"], clf["intercept"])}
    return max(scores, key=scores.get)


def _grams(text, n=4):
    w = re.findall(r"[a-z']+", text.lower())
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def repeated(text, earlier):
    """True if most of this answer was already said, word for word, in one earlier answer (a memorised speech)."""
    g = _grams(text)
    if len(g) < 10:
        return False
    return any(len(g & _grams(e)) / len(g) >= REPEAT_SHARE for e in earlier if e)


def check(question, text, earlier=()):
    """{"verdict": ok|partial|off|repeated, "off": bool, ...} or None when it can't be checked.
    earlier = the player's previous answers to *other* questions (for the memorised-speech check)."""
    if not question or not text or len(text.split()) < MIN_WORDS:
        return None
    if repeated(text, earlier):
        return {"verdict": "repeated", "off": True}
    m = _load()
    x = features(question, text)
    if x[0] < SURE_OFF_SIM and x[1] > SURE_OFF_BETTER:
        verdict = "off"                      # safety rule: extremely far from the question (real recordings are long
                                             # and messy, the classifier was trained on short written answers)
    elif m["clf"]:
        verdict = _classify(x, m["clf"])
    else:                                    # no trained model yet: the simple rule from version 1
        verdict = "off" if x[0] < 0.25 and x[1] > 0.05 else "ok"
    return {"verdict": verdict, "off": verdict == "off", "sim": round(x[0], 3), "nli": round(x[5], 3)}
