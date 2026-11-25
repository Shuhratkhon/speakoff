"""Korean spelling -> how it is really said (2026-11-26), for pronunciation scoring (coach/korean_pron.py).

Rule-based, following the main rules of 표준 발음법 (Standard Korean Pronunciation):
  연음 liaison, 받침 neutralisation (7 final sounds), 겹받침 simplification, 비음화 nasalisation,
  유음화 lateralisation, ㄹ->ㄴ after ㅁ/ㅇ (and ㄱ/ㅂ), 격음화 aspiration with ㅎ, ㅎ dropping,
  경음화 tensing after ㄱ/ㄷ/ㅂ, 구개음화 palatalisation (굳이 -> 구지).
Inside one word (eojeol); liaison also joins a word to the next one starting with a vowel, as in natural speech.
Output: a list of syllables, each (onset, vowel, coda) in compatibility jamo, e.g. 한국어 -> 한 구 거.
"""

import re

ONSETS = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
VOWELS = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
CODAS = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ",
         "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]

# 겹받침 = (first, second): before a vowel the first stays and the second moves on (닭이 -> 달기);
# before a consonant one of them is said (ㄺ ㄻ ㄿ: the second, 닭 -> 닥; the others: the first, 앉다 -> 안따)
CLUSTERS = {"ㄳ": ("ㄱ", "ㅅ"), "ㄵ": ("ㄴ", "ㅈ"), "ㄶ": ("ㄴ", "ㅎ"), "ㄺ": ("ㄹ", "ㄱ"), "ㄻ": ("ㄹ", "ㅁ"),
            "ㄼ": ("ㄹ", "ㅂ"), "ㄽ": ("ㄹ", "ㅅ"), "ㄾ": ("ㄹ", "ㅌ"), "ㄿ": ("ㄹ", "ㅍ"), "ㅀ": ("ㄹ", "ㅎ"), "ㅄ": ("ㅂ", "ㅅ")}
# 7 final sounds
NEUTRAL = {"ㄱ": "ㄱ", "ㄲ": "ㄱ", "ㅋ": "ㄱ", "ㄴ": "ㄴ", "ㄷ": "ㄷ", "ㅅ": "ㄷ", "ㅆ": "ㄷ", "ㅈ": "ㄷ", "ㅊ": "ㄷ",
           "ㅌ": "ㄷ", "ㅎ": "ㄷ", "ㄹ": "ㄹ", "ㅁ": "ㅁ", "ㅂ": "ㅂ", "ㅍ": "ㅂ", "ㅇ": "ㅇ", "": ""}
TENSE = {"ㄱ": "ㄲ", "ㄷ": "ㄸ", "ㅂ": "ㅃ", "ㅅ": "ㅆ", "ㅈ": "ㅉ"}
ASPIRATE = {"ㄱ": "ㅋ", "ㄷ": "ㅌ", "ㅂ": "ㅍ", "ㅈ": "ㅊ"}
NASAL = {"ㄱ": "ㅇ", "ㄷ": "ㄴ", "ㅂ": "ㅁ"}


def split(text):
    """'한국' -> [('ㅎ','ㅏ','ㄴ'), ('ㄱ','ㅜ','ㄱ')]; non-Hangul characters are dropped."""
    out = []
    for ch in text:
        c = ord(ch) - 0xAC00
        if 0 <= c < 11172:
            out.append([ONSETS[c // 588], VOWELS[(c % 588) // 28], CODAS[c % 28]])
    return out


def join(syl):
    o, v, c = syl
    return chr(0xAC00 + (ONSETS.index(o) * 21 + VOWELS.index(v)) * 28 + CODAS.index(c))


def _word(sy, next_onset_vowel=False):
    """Apply the rules inside one word. sy = list of [onset, vowel, coda] (changed in place)."""
    n = len(sy)
    for i in range(n):
        o, v, c = sy[i]
        nxt = sy[i + 1] if i + 1 < n else None
        # ㅎ + ㄱㄷㅈ -> ㅋㅌㅊ ; ㄶ/ㅀ likewise
        if nxt and c in ("ㅎ", "ㄶ", "ㅀ") and nxt[0] in ASPIRATE:
            nxt[0] = ASPIRATE[nxt[0]]
            sy[i][2] = {"ㅎ": "", "ㄶ": "ㄴ", "ㅀ": "ㄹ"}[c]
            continue
        if nxt and c in ("ㅎ", "ㄶ", "ㅀ") and nxt[0] == "ㅇ":                 # 좋아 -> 조아, 않아 -> 아나
            sy[i][2] = {"ㅎ": "", "ㄶ": "ㄴ", "ㅀ": "ㄹ"}[c]
            c = sy[i][2]
        if nxt and c in ("ㅎ",) and nxt[0] == "ㅅ":                          # 좋습니다 -> 조씀니다
            sy[i][2], nxt[0] = "", "ㅆ"
            continue
        # ㄱㄷㅂㅈ (or a cluster ending in ㄱ/ㅂ) + ㅎ -> aspirated onset (입학 -> 이팍, 밝히다 -> 발키다)
        if nxt and nxt[0] == "ㅎ":
            first, last = CLUSTERS.get(c, ("", c))
            key = NEUTRAL.get(last, "") if last not in ASPIRATE else last
            if key in ASPIRATE:
                nxt[0] = ASPIRATE[key]
                sy[i][2] = first
                continue
        # liaison: coda moves to an empty onset
        if nxt and nxt[0] == "ㅇ" and c and c != "ㅇ":
            if c in CLUSTERS:
                sy[i][2], moved = CLUSTERS[c]
            else:
                sy[i][2], moved = "", c
            # 구개음화: ㄷ/ㅌ + 이 -> 지/치
            if moved in ("ㄷ", "ㅌ") and nxt[1] == "ㅣ":
                moved = "ㅈ" if moved == "ㄷ" else "ㅊ"
            nxt[0] = moved
            continue
    # final sounds (neutralisation) and clusters before a consonant / at the end
    stem_nm = [sy[i][2] in ("ㄵ", "ㄻ", "ㄼ", "ㄾ", "ㄺ") for i in range(n)]   # 앉다 -> 안따, 넓다 -> 널따
    for i in range(n):
        c = sy[i][2]
        if c == "ㄺ" and i + 1 < n and sy[i + 1][0] == "ㄱ":        # 읽고 -> 일꼬
            sy[i][2] = "ㄹ"
            continue
        if c in CLUSTERS:
            first, second = CLUSTERS[c]
            # ㄺ/ㄻ/ㄿ keep the second sound before a consonant in common words (닭 -> 닥, 삶 -> 삼, 읊 -> 읍)
            sy[i][2] = second if c in ("ㄺ", "ㄻ", "ㄿ") else first
        sy[i][2] = NEUTRAL.get(sy[i][2], sy[i][2])
    # consonant + consonant rules between syllables
    for i in range(n - 1):
        c, o = sy[i][2], sy[i + 1][0]
        if c in ("ㅁ", "ㅇ") and o == "ㄹ":                                    # 음료 -> 음뇨, 종로 -> 종노
            sy[i + 1][0] = "ㄴ"
        elif c in ("ㄱ", "ㅂ") and o == "ㄹ":                                  # 국립 -> 궁닙, 협력 -> 혐녁
            sy[i + 1][0] = "ㄴ"
            sy[i][2] = NASAL[c]
        elif c == "ㄴ" and o == "ㄹ" or c == "ㄹ" and o == "ㄴ":               # 신라 -> 실라, 설날 -> 설랄
            sy[i][2], sy[i + 1][0] = "ㄹ", "ㄹ"
        elif c in NASAL and o in ("ㄴ", "ㅁ"):                                 # 합니다 -> 함니다, 국물 -> 궁물
            sy[i][2] = NASAL[c]
        elif c in ("ㄱ", "ㄷ", "ㅂ") and o in TENSE or stem_nm[i] and o in TENSE:   # 학교 -> 학꾜, 앉다 -> 안따
            sy[i + 1][0] = TENSE[o]
    return sy


def pronounce(text):
    """Text -> list of words, each a list of pronounced syllables (onset, vowel, coda)."""
    words = [w for w in re.split(r"[^가-힣]+", text) if w]
    out = [_word(split(w)) for w in words]
    # liaison across words: a final consonant joins a next word that starts with a vowel (밥 없어 -> 바 범서)
    for a, b in zip(out, out[1:]):
        if a and b and a[-1][2] and a[-1][2] != "ㅇ" and b[0][0] == "ㅇ":
            b[0][0] = a[-1][2]
            a[-1][2] = ""
    return out


def pronounce_text(text):
    """'한국어를 공부합니다' -> '한구거를 공부함니다' (readable check)."""
    return " ".join("".join(join(s) for s in w) for w in pronounce(text))


if __name__ == "__main__":
    for t in ["한국어", "합니다", "학교", "국물", "신라", "음료", "좋아요", "좋다", "굳이", "같이", "닭이", "읽다",
              "많이", "없어요", "국립", "밥 없어", "놓고", "입학", "꽃잎"]:
        print(t, "->", pronounce_text(t))
