"""Korean grammar check (phase 2, 2026-11-26). There are almost no free Korean grammar-correction models, so a small
multilingual AI model (Apache 2.0, CPU) corrects each sentence, with a strict prompt: fix only grammar (particles,
tense, verb forms, honorifics, connectors), keep the words and the meaning, change nothing in a correct sentence.
The original and the corrected sentence are then compared word by word (Kiwi tells what kind of mistake each change
is). Measured on evaluate/ko_grammar_testset.py (see MODEL below).
"""

import difflib
import re
import os
import threading

MODEL = "Qwen/Qwen3-1.7B"   # Apache-2.0; beat Qwen2.5-1.5B on evaluate/ko_grammar_testset.py (13 vs 8 exact fixes)
SYSTEM = ("너는 한국어 선생님이다. 한국어 학습자가 말한 문장을 받으면 문법 오류(조사, 시제, 활용, 높임말, 연결어미)만 고친 "
          "문장을 출력한다. 오류가 없으면 문장을 그대로 출력한다. 뜻과 단어는 최대한 바꾸지 말고, 설명 없이 문장 하나만 출력한다.")
SHOTS = [("저는 학교을 가요.", "저는 학교에 가요."), ("어제 친구를 만나요.", "어제 친구를 만났어요."),
         ("저는 커피를 좋아해요.", "저는 커피를 좋아해요.")]
MAX_CHANGE = 0.5            # a "correction" that rewrites more than half of the sentence is not trusted
STYLE_GAIN = 6.0           # a "style" change still counts when the original form is clearly wrong (어렵어요 -> 어려워요)
MIN_GAIN = -3.6             # Kiwi's language-model score must not drop more than this (bad "fixes" drop it)
CONTENT = ("NNG", "NNP", "NNB", "NR", "NP", "VV", "VA", "MAG", "MAJ", "MM", "SN", "SL", "XR")
REFUSE = ("죄송", "인공지능", "도와드릴", "처리할 수")
SAME_EF = {"ᆸ니다", "습니다", "어요", "아요", "에요", "어", "아", "다", "지요", "죠", "요"}   # politeness style, not grammar
SAME_J = {"이랑", "랑", "하고", "와", "과"}
TOPIC_SUBJ = {"이", "가", "은", "는", "ᆫ"}      # 제가 <-> 저는: a nuance, not a grammar error (2026-11-26)

# the model needs ~7 GB: on a small machine free it after every recording (set SC_KEEP_KO_GRAMMAR=1 on a big server)
KEEP_LOADED = os.environ.get("SC_KEEP_KO_GRAMMAR") == "1"
_lock = threading.Lock()
_m = {}


def free_memory_gb():
    """Memory the process can still commit (RAM + page file left), in GB; None if unknown."""
    try:
        if os.name == "nt":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong)] +                            [(n, ctypes.c_ulonglong) for n in ("tp", "ap", "tf", "af", "tv", "av", "aev")]
            m = MS()
            m.len = ctypes.sizeof(MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return min(m.ap + m.af // 4, m.af) / 2 ** 30          # free RAM (plus a little page file), capped by commit left
        return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2 ** 30
    except Exception:
        return None


FP32_NEEDS_GB = 9.0         # float32 weights (~7 GB) + working memory


def _load():
    with _lock:
        if not _m:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            _m["tok"] = AutoTokenizer.from_pretrained(MODEL)
            free = free_memory_gb()
            try:      # float32: ~2 s a sentence on CPU but ~7 GB of memory; on a small machine go straight to bf16
                if free is not None and free < FP32_NEEDS_GB:
                    raise MemoryError(f"only {free:.1f} GB free")
                _m["model"] = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.float32).eval()
            except (RuntimeError, MemoryError, OSError):     # not enough memory: bfloat16 needs half, ~20 s a sentence
                import gc
                gc.collect()
                _m["model"] = AutoModelForCausalLM.from_pretrained(MODEL, dtype=torch.bfloat16).eval()
    return _m


def unload():
    with _lock:
        _m.clear()
    import gc
    gc.collect()


def correct(sentence):
    import torch
    m = _load()
    msgs = [{"role": "system", "content": SYSTEM}]
    for a, b in SHOTS:
        msgs += [{"role": "user", "content": a}, {"role": "assistant", "content": b}]
    msgs.append({"role": "user", "content": sentence})
    kw = {"enable_thinking": False} if "Qwen3" in MODEL else {}
    x = m["tok"](m["tok"].apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, **kw), return_tensors="pt")
    with torch.no_grad():
        out = m["model"].generate(**x, max_new_tokens=80, do_sample=False)
    got = m["tok"].decode(out[0, x.input_ids.shape[1]:], skip_special_tokens=True).strip().split("\n")[0].strip()
    return got or sentence


def _norm(s):
    return re.sub(r"[\s.,!?~]", "", s)


def category(wrong, right):
    """What kind of change: particle, tense, ending, honorific or word (from Kiwi's morpheme tags)."""
    from coach.korean_lex import kiwi
    a = [(t.form, t.tag) for t in kiwi().tokenize(wrong)] if wrong else []
    b = [(t.form, t.tag) for t in kiwi().tokenize(right)] if right else []
    diff = set(a) ^ set(b)
    tags = {tag for _, tag in diff}
    forms = {form for form, _ in diff}
    if forms & {"시", "께서", "드리", "세요", "드시", "주무시", "계시", "댁", "진지"}:
        return "Honorific"
    if any(t.startswith("J") for t in tags):
        return "Particle"
    if "EP" in tags:
        return "Tense"
    if any(t.startswith("E") for t in tags):
        return "Verb ending"
    return "Word choice"


def mistakes(original, corrected):
    """Word-level differences between what was said and the correction."""
    a, b = original.split(), corrected.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b).get_opcodes():
        if op == "equal":
            continue
        wrong, right = " ".join(a[i1:i2]), " ".join(b[j1:j2])
        if _norm(wrong) == _norm(right):          # only spacing or punctuation differs
            continue
        out.append({"wrong": wrong, "right": right, "category": category(wrong, right)})
    return out


def trusted(said, fixed):
    """Keep a correction only when it is about grammar: same content words, not just a style swap, and Kiwi
    finds the new sentence about as likely or more. On the test set this took false alarms from 12/15 to 0/15."""
    from collections import Counter
    from coach.korean_lex import kiwi
    if any(w in fixed for w in REFUSE):
        return False
    a = [(t.form, t.tag) for t in kiwi().tokenize(said) if not t.tag.startswith("S") or t.tag in ("SN", "SL")]
    b = [(t.form, t.tag) for t in kiwi().tokenize(fixed) if not t.tag.startswith("S") or t.tag in ("SN", "SL")]

    def content(ms):
        return Counter(m for m in ms if m[1].startswith(CONTENT))

    def style(ms):
        """Spoken style is not grammar: the sentence ending (없고요 / 없어요 / 없습니다), 랑 / 과, 제가 / 저는."""
        out = [("J", "J") if t.startswith("J") and f in SAME_J else ("JT", "JT") if t.startswith("J") and f in TOPIC_SUBJ
               else ("NP", "NP") if t == "NP" and f in ("저", "제", "나", "내") else (f, t) for f, t in ms]
        while out and out[-1][1] in ("EF", "EC", "JX"):    # the final ending (+ 요); tense (EP) stays
            out.pop()
        return out + [("END", "END")]
    if content(a) != content(b):                       # the model changed the words, not the grammar
        return False
    gain = kiwi().analyze(fixed)[0][1] - kiwi().analyze(said)[0][1]
    if style(a) == style(b) and a != b and gain < STYLE_GAIN:   # only a style swap, and what was said is fine too
        return False
    if a == b and len(_norm(fixed)) > len(_norm(said)):     # 줬어요 -> 주었어요 is not a fix
        return False
    if a == b:                                          # same words, only the form changed (어렵어요 -> 어려워요)
        return gain >= STYLE_GAIN
    added, removed = Counter(b) - Counter(a), Counter(a) - Counter(b)
    if added and not removed and all(t.startswith("J") for _, t in added):    # a dropped particle put back: fine in speech
        return False
    return gain >= MIN_GAIN


def check_text(text):
    """Same shape as coach/grammar.py: [{"original", "corrected", "mistakes": [...]}] per sentence."""
    try:
        return _check_text(text)
    finally:
        if not KEEP_LOADED:
            unload()


def _check_text(text):
    from coach.korean_lex import kiwi
    results = []
    for s in kiwi().split_into_sents(text):
        sent = s.text.strip()
        if len(_norm(sent)) < 4:
            continue
        fixed = correct(sent)
        ratio = difflib.SequenceMatcher(a=_norm(sent), b=_norm(fixed)).ratio()
        if _norm(fixed) == _norm(sent) or ratio < 1 - MAX_CHANGE or not trusted(sent, fixed):
            results.append({"original": sent, "corrected": sent, "mistakes": []})
            continue
        results.append({"original": sent, "corrected": fixed, "mistakes": mistakes(sent, fixed)})
    return results
