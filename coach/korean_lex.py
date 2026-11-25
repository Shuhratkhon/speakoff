"""Korean vocabulary level and grammar range (phase 2, 2026-11-26), using Kiwi (kiwipiepy, a Korean morphological
analyser: 먹었어요 -> 먹 + 었 + 어요) and the learner word lists in coach/data/ko_vocab.tsv:
  NIKL 한국어 학습용 어휘 목록 (2003): A beginner, B intermediate, C advanced
  TOPIK 어휘 목록 (2015): 초급, 중급
(combined by github.com/julienshim/combined_korean_vocabulary_list, MIT; the lists belong to the National Institute
of the Korean Language and the TOPIK institute.)
Word level used here: 1 beginner (NIKL A or TOPIK 초급), 2 intermediate (NIKL B), 3 advanced (NIKL C, or TOPIK 중급
words not in NIKL A/B). Words in neither list are left out, like rare words and names in the English check.
"""

import csv
import re
from pathlib import Path

LIST = Path(__file__).with_name("data") / "ko_vocab.tsv"
CONTENT = {"NNG": "noun", "VV": "verb", "VA": "adj", "MAG": "adv", "XR": "root"}
# connective (EC) and noun-modifying (ETM) / nominal (ETN) endings that make a sentence complex
COMPLEX = {"EC", "ETM", "ETN"}
SIMPLE_EC = {"고", "어", "아", "게", "지"}       # very common linkers: count only when part of a bigger pattern

_kiwi = None
_levels = None


def kiwi():
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    return _kiwi


def levels():
    global _levels
    if _levels is None:
        _levels = {}
        with LIST.open(encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t"):
                word = re.sub(r"\d+$", "", r["word"])           # 가구03 -> 가구
                lv = 1 if (r["nikl_level"] == "A" or r["topik_level"] == "초급") else 2 if r["nikl_level"] == "B" else 3
                _levels[word] = min(_levels.get(word, 9), lv)   # a homograph keeps its easiest level
    return _levels


def lemma(tok):
    return tok.form + "다" if tok.tag in ("VV", "VA") else tok.form


def vocabulary_stats(text):
    toks = [t for t in kiwi().tokenize(text) if t.tag in CONTENT]
    lv = levels()
    graded = [(lemma(t), lv[lemma(t)]) for t in toks if lemma(t) in lv]
    n = max(len(graded), 1)
    lemmas = [lemma(t) for t in toks]
    from coach.level import mattr
    return {
        "b1_plus": round(100 * sum(l >= 2 for _, l in graded) / n, 1),      # % intermediate or advanced
        "b2_plus": round(100 * sum(l >= 3 for _, l in graded) / n, 1),      # % advanced
        "variety": round(mattr(lemmas), 3) if lemmas else 0,
        "levels": {"beginner": sum(l == 1 for _, l in graded), "intermediate": sum(l == 2 for _, l in graded),
                   "advanced": sum(l == 3 for _, l in graded)},
        "advanced_words": sorted({w for w, l in graded if l >= 3}),
        "b1_words": sorted({w for w, l in graded if l == 2}),
    }


def grammar_range(text):
    """Share of sentences using connective / modifying endings (-아서, -니까, -는데, -지만, -(으)면, -는 ...)."""
    sents = kiwi().split_into_sents(text, return_tokens=True)
    complex_n = 0
    for s in sents:
        tags = [(t.tag, t.form) for t in s.tokens]
        if any(tag in COMPLEX and not (tag == "EC" and form in SIMPLE_EC) for tag, form in tags):
            complex_n += 1
    n = max(len(sents), 1)
    return {"sentences": len(sents), "complex": complex_n, "complex_percent": round(100 * complex_n / n, 1)}
