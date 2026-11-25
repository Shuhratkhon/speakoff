"""Korean pronunciation (2026-11-26, phase 4).

1. What the words SHOULD sound like: coach/korean_g2p.py applies the standard pronunciation rules to the transcript
   (연음, 비음화, 경음화 ...) and gives the jamo really said, syllable by syllable.
2. What was REALLY said: the same wav2vec2 phoneme model as English (facebook/wav2vec2-lv-60-espeak-cv-ft). It was not
   trained on Korean, so it writes Korean sounds with symbols from other languages (ㅏ as a / ɑ / a5 ...). Each Korean
   sound therefore has a GROUP of acceptable symbols (GROUPS, built from what the model hears in native Korean speech).
3. The expected sounds are force-aligned to the audio and each gets a goodness score (GOP), like English.
   Sounds the model cannot tell apart are merged (ㄱ/ㄲ, ㄷ/ㄸ ...); unreleased final ㄱ/ㄷ/ㅂ and a weak ㅎ between
   vowels are not judged (natives drop them too).
4. Score = how clearly the sounds came out (share of sounds right + average GOP) blended with how sure Whisper was
   about each word, calibrated on 6 native speakers (Zeroth-Korean, CC BY 4.0) and 4 learners (samples/).
"""

import numpy as np

from coach import korean_g2p as G

# Korean sound -> symbols the phoneme model uses for it (only symbols in its vocabulary are kept)
GROUPS = {
    "ㄱ": "k ɡ q ɣ kʰ", "ㄲ": "k ɡ q", "ㅋ": "kʰ k x q",
    "ㄷ": "t d ɾ ð", "ㄸ": "t d", "ㅌ": "tʰ th t",
    "ㅂ": "p b β", "ㅃ": "p b", "ㅍ": "pʰ ph p f",
    "ㅈ": "tʃ dʒ tɕ ts dz ʒ tɕʲ", "ㅉ": "tʃ dʒ tɕ ts", "ㅊ": "tʃʰ tɕh ts.h tʃ tɕ ts",
    "ㅅ": "s ɕ ʃ z sʲ ɕʲ", "ㅆ": "s ɕ ʃ", "ㅎ": "h x ɦ ç",
    "ㄴ": "n ɲ nʲ d", "ㅁ": "m b",       # natives soften a word-initial ㄴ/ㅁ toward [d]/[b]
    "ㅇ": "ŋ n ɴ", "ㄹ": "l r ɾ ɭ ɹ ɫ lʲ",
    "ㅏ": "a ɑ a5 ɑ5 aː ɐ ɑː a1 a2 a3 a4", "ㅓ": "ʌ ə əɜ ə5 ɔ ɜ ɐ ɤ", "ㅗ": "o oː ɔ o5 ɔː ʊ",
    "ㅜ": "u uː u5 ʉ ʊ ɯᵝ", "ㅡ": "ɯ ɨ ʉ ə ɯɯ ɯᵝ ɘ", "ㅣ": "i iː i5 i.5 ɪ ɨ",
    "ㅐ": "e ɛ e̞ eː ɛː e5 æ", "ㅔ": "e ɛ e̞ eː ɛː e5",
    "J": "j i iɑ5 iɛ5 i5 ɪ", "W": "w u ʊ uei5 ʋ", "ㅚ": "ø we e ɛ", "ㅟ": "y ʏ wi i", "ㅢ": "ɯ i ɨ j e",
}
# compound vowels = glide + simple vowel
COMPOUND = {"ㅑ": ("J", "ㅏ"), "ㅕ": ("J", "ㅓ"), "ㅛ": ("J", "ㅗ"), "ㅠ": ("J", "ㅜ"), "ㅒ": ("J", "ㅐ"), "ㅖ": ("J", "ㅔ"),
            "ㅘ": ("W", "ㅏ"), "ㅝ": ("W", "ㅓ"), "ㅙ": ("W", "ㅐ"), "ㅞ": ("W", "ㅔ")}
SKIP_CODA = {"ㄱ", "ㄷ", "ㅂ"}          # unreleased finals: often silent for the phoneme model
CLEAR_WORD = 0.80                       # Whisper confidence of clearly said words (natives ~0.9)


def expected_sounds(word):
    """Pronounced sounds of one word (after the rules), as labels like 'ㅎ', 'ㅏ', 'ㄴ' (glides as 'J' / 'W')."""
    out = []
    for sylls in G.pronounce(word):
        for i, (o, v, c) in enumerate(sylls):
            if o != "ㅇ" and not (o == "ㅎ" and i > 0):            # silent ㅇ; weak ㅎ inside a word
                out.append(o)
            out.extend(COMPOUND.get(v, (v,)))
            if c and c not in SKIP_CODA:
                out.append(c)
    return out


def _ids_factory():
    from coach import pronunciation as P
    cache = {}

    def ids(label):
        if label not in cache:
            cache[label] = [P._phone2id[s] for s in GROUPS.get(label, label).split() if s in P._phone2id]
        return cache[label]
    return ids


def _align(lp, labels, ids):
    """CTC forced alignment of the expected sounds (same method as English, with Korean sound groups)."""
    from coach import pronunciation as P
    saved = P.group_ids
    P.group_ids = ids                    # force_align looks up each sound's symbols through group_ids
    try:
        return P.force_align(lp, labels)
    finally:
        P.group_ids = saved


def _symbol_to_jamo():
    back = {}
    for label, syms in GROUPS.items():
        for s in syms.split():
            back.setdefault(s, label)
    return back


def check(words, logprobs):
    """words = Whisper words with times; returns per-word results like coach/pronunciation.check_pronunciation."""
    from coach import pronunciation as P
    from coach.fluency import FILLERS, clean
    ids = _ids_factory()
    back = _symbol_to_jamo()
    lp_all = logprobs.numpy()
    segments, cur = [], []
    for w in words:
        labels = [] if clean(w["word"]) in FILLERS else expected_sounds(w["word"])
        labels = [x for x in labels if ids(x)]
        if not labels:
            segments.append(cur); cur = []
            continue
        if cur and w["start"] - cur[-1][0]["end"] > 0.25:
            segments.append(cur); cur = []
        cur.append((w, labels))
    segments.append(cur)
    results = []
    for seg in filter(None, segments):
        a = max(0, int((seg[0][0]["start"] - 0.1) / P.FRAME))
        b = min(len(lp_all), int((seg[-1][0]["end"] + 0.1) / P.FRAME) + 1)
        labels = [x for _, lab in seg for x in lab]
        lp = lp_all[a:b]
        frames = _align(lp, labels, ids)
        if frames is None:
            continue
        sounds = []
        for lab, (f0, f1) in zip(labels, frames):
            seg_lp = lp[f0:f1 + 1]
            gid = ids(lab)
            gop = float(np.mean(np.logaddexp.reduce(seg_lp[:, gid], axis=1) - seg_lp[:, 1:].max(1)))
            best = int(seg_lp[:, 1:].sum(0).argmax()) + 1
            ok = best in gid or gop > WRONG_GOP
            heard = lab if ok else back.get(P._id2phone[best], "?")
            sounds.append({"expected": lab, "heard": heard, "ok": ok, "gop": round(gop, 2)})
        k = 0
        for w, lab in seg:
            results.append({"word": w["word"], "start": w["start"], "prob": w.get("probability"),
                            "sounds": sounds[k:k + len(lab)]})
            k += len(lab)
    return results


WRONG_GOP = -4.0            # set on the samples (evaluate/ko_pron_eval.py): -3 flags natives too, -5 misses learners


def raw_measures(results, words):
    sounds = [s for r in results for s in r["sounds"]]
    if not sounds:
        return None
    right = sum(s["ok"] for s in sounds) / len(sounds)
    gop = float(np.mean(np.clip([s["gop"] for s in sounds], -10, 0)))
    probs = [w["probability"] for w in words if w.get("probability") is not None]
    clear = float(np.mean([p >= CLEAR_WORD for p in probs])) if probs else 0.0
    return {"right": right, "gop": gop, "clear": clear, "n": len(sounds)}


# score = interpolation of a combined clarity index, calibrated so natives land 90-100 and learners spread below
# samples (2026-11-26): 4 Uzbek learners (TOPIK ~1-3) index 0.78-0.79, 6 natives 0.80-0.95
INDEX_POINTS = ([0.0, 0.55, 0.70, 0.78, 0.80, 0.85, 0.92, 1.0], [10, 25, 50, 68, 78, 88, 96, 100])


def score(m):
    if not m:
        return None
    index = 0.30 * m["right"] + 0.50 * m["clear"] + 0.20 * (1 + m["gop"] / 10)
    return int(round(np.interp(index, *INDEX_POINTS))), round(index, 3)


def common_mistakes(results, top=5, habit=3):
    """Korean sounds said unclearly or as another sound, most frequent first, with example words."""
    from collections import defaultdict
    swaps = defaultdict(list)
    for r in results:
        for s in r["sounds"]:
            if not s["ok"]:
                swaps[(s["expected"], s["heard"])].append(r["word"].strip(",.?!"))
    items = [(k, v) for k, v in swaps.items() if len(v) >= habit]
    return sorted(items, key=lambda kv: -len(kv[1]))[:top]


def analyse(path, words):
    """Pronunciation for a Korean recording whose Whisper words are already known."""
    from coach import pronunciation as P
    lp = P.hear_phonemes(P.load_audio(path))
    results = check(words, lp)
    m = raw_measures(results, words)
    sc = score(m)
    return {"score": sc[0] if sc else None, "index": sc[1] if sc else None, "measures": m,
            "mistakes": [{"expected": e, "heard": h, "words": list(dict.fromkeys(ws))[:4], "count": len(ws)}
                         for (e, h), ws in common_mistakes(results)],
            "words": [{"word": r["word"], "ok": all(s["ok"] for s in r["sounds"]),
                       "wrong": [s["expected"] for s in r["sounds"] if not s["ok"]]} for r in results]}
