"""Speaker level: IELTS Speaking band, CEFR level (A1-C2) and TOEFL Speaking score.

IELTS Speaking is marked on 4 equal criteria, which map onto what our app measures:
  Fluency & Coherence        <- fluency.py score
  Lexical Resource           <- vocabulary level (CEFR-J word list) + variety of words   (this file)
  Grammatical Range & Acc.   <- grammar.py mistakes + share of complex sentences          (this file)
  Pronunciation              <- pronunciation.py score (tuned on teacher scores in step 4d)
Overall band = average of the 4, rounded the IELTS way (.25 -> .5, .75 -> next whole band).
CEFR and TOEFL are then read from the band with the published comparison tables.

ESTIMATES: the band cut-offs below come from the public IELTS band descriptors and have not yet been
checked against examiner-graded recordings (Speak & Improve corpus would allow that).

Word lists: CEFR-J Vocabulary Profile 1.5 (A1-B2) + Octanove C1/C2 profile, CC BY-SA,
github.com/openlanguageprofiles/olp-en-cefrj  (data/cefr/)
"""

import csv
from pathlib import Path

import numpy as np
import spacy

CEFR_DIR = Path(__file__).resolve().parent.parent / "data" / "cefr"
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
POS_MAP = {"NOUN": "noun", "VERB": "verb", "ADJ": "adjective", "ADV": "adverb", "PRON": "pronoun",
           "ADP": "preposition", "DET": "determiner", "CCONJ": "conjunction", "SCONJ": "conjunction",
           "NUM": "number", "AUX": "verb"}
CONTENT = {"NOUN", "VERB", "ADJ", "ADV"}
COMPLEX_DEPS = {"advcl", "relcl", "ccomp", "csubj", "acl"}     # subordinate clauses: because..., which..., that...

nlp = spacy.load("en_core_web_sm")


def _load_wordlist():
    """(word, pos) -> lowest CEFR level, and word -> lowest level for any part of speech."""
    by_pos, by_word = {}, {}
    for name in ("cefrj-vocabulary-profile-1.5.csv", "octanove-vocabulary-profile-c1c2-1.0.csv"):
        with open(CEFR_DIR / name, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                level = LEVELS.index(row["CEFR"])
                for word in row["headword"].lower().split("/"):          # "a.m./am/AM"
                    word = word.strip()
                    for key, table in (((word, row["pos"]), by_pos), (word, by_word)):
                        table[key] = min(table.get(key, 9), level)
    return by_pos, by_word


WORD_POS, WORD_ANY = _load_wordlist()


def interp(x, xs, ys):
    """Straight lines between the points (xs, ys). xs may go down (e.g. fewer mistakes = higher band):
    np.interp itself needs increasing xs."""
    if xs[0] > xs[-1]:
        return float(np.interp(-x, [-v for v in xs], ys))
    return float(np.interp(x, xs, ys))


# ---------------------------------------------------------------- Lexical Resource

def word_level(token):
    lemma = token.lemma_.lower()
    level = WORD_POS.get((lemma, POS_MAP.get(token.pos_, "")))
    return WORD_ANY.get(lemma) if level is None else level


def mattr(items, window=50):
    """Moving-average type-token ratio: variety of words, fair for texts of different length."""
    if len(items) <= window:
        return len(set(items)) / max(len(items), 1)
    return float(np.mean([len(set(items[i:i + window])) / window for i in range(len(items) - window + 1)]))


def vocabulary_stats(text):
    doc = nlp(text)
    content = [t for t in doc if t.pos_ in CONTENT and t.is_alpha and not t.is_stop]
    levels = [lv for lv in (word_level(t) for t in content) if lv is not None]
    counts = {LEVELS[i]: levels.count(i) for i in range(6)}
    advanced = sorted({t.text.lower() for t in content if (word_level(t) or 0) >= 3})     # B2+
    lemmas = [t.lemma_.lower() for t in doc if t.is_alpha]
    return {
        "b1_plus": round(100 * sum(lv >= 2 for lv in levels) / max(len(levels), 1), 1),   # % content words B1+
        "b2_plus": round(100 * sum(lv >= 3 for lv in levels) / max(len(levels), 1), 1),
        "variety": round(mattr(lemmas), 3),
        "levels": counts,
        "advanced_words": advanced,
        "b1_words": sorted({t.text.lower() for t in content if word_level(t) == 2}),   # B1: backup "good words"
    }


def lexical_band(v):
    # IELTS 5: limited vocabulary, mostly everyday words; 6: enough to discuss topics at length;
    # 7: some less common words; 8: wide range, uncommon words used skilfully.
    soph = interp(v["b1_plus"], [2, 6, 11, 17, 24, 32], [3.5, 4.5, 5.5, 6.5, 7.5, 8.5])   # speech: fewer rare words than writing
    var = interp(v["variety"], [0.55, 0.62, 0.67, 0.72, 0.77, 0.82], [3, 4, 5, 6, 7, 8.5])
    return 0.6 * soph + 0.4 * var


# ---------------------------------------------------------------- Grammatical Range & Accuracy

def grammar_range(results):
    """Share of sentences that use a subordinate clause, and average sentence length."""
    sents = [r["original"] for r in results if len(r["original"].split()) >= 3]
    complex_n = sum(any(t.dep_ in COMPLEX_DEPS for t in nlp(s)) for s in sents)
    return {
        "complex_percent": round(100 * complex_n / max(len(sents), 1), 1),
        "words_per_sentence": round(float(np.mean([len(s.split()) for s in sents])) if sents else 0, 1),
    }


def grammar_band(results, n_words, rng):
    # IELTS 5: basic sentences, frequent errors; 6: mix of simple + complex, errors in complex ones;
    # 7: range of complex structures, frequent error-free sentences; 8: majority error-free.
    mistakes = sum(len(r["mistakes"]) for r in results)
    per_100 = 100 * mistakes / max(n_words, 1)
    error_free = 100 * sum(not r["mistakes"] for r in results) / max(len(results), 1)
    accuracy = 0.5 * interp(error_free, [20, 40, 55, 70, 82, 92], [3, 4, 5, 6, 7, 8.5]) + \
               0.5 * interp(per_100, [12, 8, 6, 4, 2.5, 1], [3, 4, 5, 6, 7, 8.5])
    range_ = interp(rng["complex_percent"], [0, 10, 25, 40, 55, 70], [3, 4, 5, 6, 7, 8.5])
    return 0.6 * accuracy + 0.4 * range_


# ---------------------------------------------------------------- 0-100 section scores

SECTIONS = ["fluency", "grammar", "vocabulary", "pronunciation"]
# same score <-> band table as fluency_band, used the other way round for vocabulary
SCORE_PTS = [0, 25, 40, 55, 70, 85, 95, 100]
BAND_PTS = [2, 3, 4, 5, 6, 7, 8, 9]


def originality(text):
    """Share of 3-word phrases that are new (not said before in this answer). Our 11 natural recordings:
    0.94-1.0. Saying "I go to school" 100 times: ~0.01."""
    import re
    w = re.findall(r"[a-z']+", text.lower())
    tri = [tuple(w[i:i + 3]) for i in range(len(w) - 2)]
    return round(len(set(tri)) / len(tri), 3) if len(tri) >= 10 else 1.0


def repetition_cap(orig):
    """Repeating the same sentences is not real speaking (IELTS marks memorised / repeated language down):
    above 0.85 no cap; below, every language score (0-100) and band is capped, down to 20 / band 2."""
    return interp(orig, [0.3, 0.85], [20, 100]), interp(orig, [0.3, 0.85], [2, 9])


def grammar_total(accuracy_score, rng):
    """Grammar out of 100 = 70% accuracy (grammar.grammar_score: few mistakes) + 30% range (share of
    sentences with a subordinate clause: because..., which..., that...). Like IELTS 'Grammatical Range AND
    Accuracy': 100 simple error-free sentences ("I go to school") get ~70, not 100."""
    range_score = interp(rng["complex_percent"], [0, 10, 25, 40, 55], [0, 30, 60, 85, 100])
    return round(0.7 * accuracy_score + 0.3 * range_score), round(range_score)


def vocabulary_score(band):
    return round(interp(band, BAND_PTS, SCORE_PTS))


# ---------------------------------------------------------------- bands -> CEFR / TOEFL

def fluency_band(score):
    return interp(score, [0, 25, 40, 55, 70, 85, 95, 100], [2, 3, 4, 5, 6, 7, 8, 9])


def pronunciation_band(score):
    # our score ~ teachers' accuracy x10 (step 4d). In speechocean762 "8 of 10" is the most common score
    # even for children (understandable, clear L1 accent) -> about IELTS 6; near-native needs 90+.
    # shown score anchors (pronunciation.py): 35 ~ teacher 3-5, 55 ~ 6, 65 ~ 7, 78 ~ 8, 88 ~ 9, 97 ~ native
    return interp(score, [0, 35, 55, 65, 78, 88, 97, 100], [2, 4, 5, 5.5, 6, 7, 8.5, 9])


def ielts_round(x):
    return float(np.floor(x * 2 + 0.5) / 2)


def cefr_from_ielts(band):
    # IELTS official comparison: C2 8.5-9, C1 7-8, B2 5.5-6.5, B1 4-5, A2 3-3.5, A1 below
    for cut, level in ((8.5, "C2"), (7.0, "C1"), (5.5, "B2"), (4.0, "B1"), (3.0, "A2"), (2.0, "A1")):
        if band >= cut:
            return level
    return "below A1"


def toefl_from_ielts(band):
    """TOEFL iBT Speaking: the 1-6 band scale used since January 2026 (1 = A1 ... 6 = C2, halves between)
    and the older 0-30 section score (ETS CEFR cut scores: B1 16, B2 20, C1 25)."""
    new = interp(band, [0, 2, 3, 4, 5.5, 7, 8.5, 9], [1, 1, 2, 3, 4, 5, 6, 6])        # lowest TOEFL band is 1
    old = interp(band, [0, 2, 3, 4, 5.5, 7, 8.5, 9], [0, 4, 10, 16, 20, 25, 29, 30])
    return round(new * 2) / 2, round(old)


def estimate_level(f_score, p_score, g_results, n_words, text, chosen=SECTIONS):
    """chosen = the sections the speaker asked to be rated. Like an exam, a criterion that is not
    assessed counts as band 0 (IELTS), so the overall band / CEFR / TOEFL drop accordingly."""
    vocab = vocabulary_stats(text)
    rng = grammar_range(g_results)
    bands = {
        "fluency": fluency_band(f_score),
        "vocabulary": lexical_band(vocab),
        "grammar": grammar_band(g_results, n_words, rng),
        "pronunciation": pronunciation_band(p_score),
    }
    # a few rare words in a very short answer say little: trust vocabulary less when there are few words
    n = sum(vocab["levels"].values())
    trust = n / (n + 25)
    others = np.mean([b for k, b in bands.items() if k != "vocabulary"])
    bands["vocabulary"] = trust * bands["vocabulary"] + (1 - trust) * others
    orig = originality(text)
    _, band_cap = repetition_cap(orig)
    bands = {k: min(b, band_cap) for k, b in bands.items()}
    vocab_100 = vocabulary_score(bands["vocabulary"])
    for k in bands:
        if k not in chosen:
            bands[k] = 0.0
    raw = float(np.mean(list(bands.values())))
    overall = ielts_round(raw)
    toefl_new, toefl_old = toefl_from_ielts(overall)
    # close to a CEFR boundary (within a quarter band): say which neighbour level it borders
    cefr = cefr_from_ielts(overall)
    for other in (cefr_from_ielts(raw - 0.3), cefr_from_ielts(raw + 0.3)):
        if other != cefr:
            cefr = f"{cefr} (borderline {other})"
            break
    return {
        "too_short": n_words < 100,          # IELTS/TOEFL answers are 1-2 minutes: shorter = less reliable
        "ielts": overall,
        "ielts_parts": {k: ielts_round(v) for k, v in bands.items()},
        "cefr": cefr,
        "toefl": toefl_new,
        "toefl_old": toefl_old,
        "vocabulary": vocab,
        "vocabulary_score": vocab_100,
        "originality": orig,
        "grammar_range": rng,
    }
