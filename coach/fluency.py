"""Step 2: fluency analysis.

Measures (speed, breakdown and repair fluency):
  speed:      words per minute, articulation rate, syllables per second, speed consistency
  breakdown:  pauses (count, %, average, long, mid-phrase), mean length of run, fillers, lengthened words
  repair:     repetitions, self-corrections / restarts
and turns them into a PROVISIONAL score out of 100 (thresholds not yet tested on human ratings).
"""

import re
import statistics

from faster_whisper.audio import decode_audio
from faster_whisper.vad import get_speech_timestamps, VadOptions

from coach.transcribe import transcribe

SAMPLE_RATE = 16000    # decode_audio gives 16000 samples per second
MIN_PAUSE = 0.5        # silences shorter than this are normal breathing, not pauses
LONG_PAUSE = 2.0       # pauses this long are flagged on their own
FILLERS = {"um", "umm", "uh", "uhh", "er", "erm", "ah", "hmm", "mm",
           "음", "음음", "어", "어어", "으", "으음", "아", "에", "엄", "흠"}          # Korean fillers (2026-11-26)
# words that usually START a new clause, so a pause before them sounds natural
CLAUSE_STARTERS = {"and", "but", "so", "because", "then", "or", "i", "we", "it",
                   "this", "that", "now", "also", "after", "when", "if",
                   "그리고", "그런데", "근데", "그래서", "하지만", "그러니까", "그러면", "그럼", "그래도", "왜냐하면", "그리고요", "또"}


# ---------------------------------------------------------------- helpers

def clean(word):
    """Lowercase and remove punctuation: 'Coach.' -> 'coach'."""
    return re.sub(r"[^a-z0-9'\uac00-\ud7a3]", "", word.lower())        # keeps Hangul syllables


def count_syllables(word):
    """Rough syllable count = groups of vowels ('pronunciation' -> 5). Good enough for speed."""
    word = clean(word)
    if not word:
        return 0
    hangul = len(re.findall(r"[\uac00-\ud7a3]", word))
    if hangul:                              # Korean: every Hangul block is one syllable
        return hangul
    if word.isdigit():                      # "100" is said "one hundred"
        return 3
    groups = re.findall(r"[aeiouy]+", word)
    count = len(groups)
    if word.endswith("e") and not word.endswith(("le", "ee")) and count > 1:
        count -= 1                          # silent e: "make", "rate"
    return max(count, 1)


# ---------------------------------------------------------------- part 2a: pauses

def find_pauses(audio):
    """Return a list of {"start", "end", "length"} pauses (seconds) in a decoded audio array."""
    # VAD (voice activity detection) finds where speech is.
    # speech_pad_ms: VAD adds this much extra "speech" on both sides of every chunk.
    # The default (400 ms) would shrink every pause by 0.8 s, so we keep it small.
    chunks = get_speech_timestamps(audio, VadOptions(min_silence_duration_ms=250, speech_pad_ms=50))

    pauses = []
    # zip(chunks, chunks[1:]) gives neighbouring pairs: (chunk0, chunk1), (chunk1, chunk2), ...
    for current, nxt in zip(chunks, chunks[1:]):
        start = current["end"] / SAMPLE_RATE   # speech stops here
        end = nxt["start"] / SAMPLE_RATE       # speech starts again here
        if end - start >= MIN_PAUSE:
            pauses.append({"start": round(start, 2), "end": round(end, 2), "length": round(end - start, 2)})
    return pauses


def split_into_runs(words, pauses):
    """Group words into runs = stretches of speech between two pauses."""
    runs, current, p = [], [], 0
    for w in words:
        # a word that starts after the next pause begins a new run
        while p < len(pauses) and w["start"] >= pauses[p]["start"]:
            if current:
                runs.append(current)
                current = []
            p += 1
        current.append(w)
    if current:
        runs.append(current)
    return runs


def label_pauses(words, pauses):
    """Add the words before/after each pause, and whether it is mid-phrase (sounds hesitant)."""
    # Whisper often stretches the NEXT word back over the silence ("I" 4.10-5.82 while the
    # pause is 4.34-5.68), so we use word END times: the first word ending after the pause
    # is the word after it; the last word ending before that is the word before it.
    for p in pauses:
        after = [w for w in words if w["end"] > p["end"]]
        before = [w for w in words if w["end"] <= p["end"]]
        p["before"] = before[-1]["word"] if before else ""
        p["after"] = after[0]["word"] if after else ""
        sentence_end = p["before"].endswith((".", "?", "!", ","))
        new_clause = clean(p["after"]) in CLAUSE_STARTERS
        p["mid_phrase"] = not (sentence_end or new_clause)
    return pauses


# ---------------------------------------------------------------- part 2c / 2e: word-level problems

def find_fillers(words):
    return [w for w in words if clean(w["word"]) in FILLERS]


def find_repairs(words):
    """Repetitions ("I I think", "rate it rate it") and self-corrections / restarts
    ("he go he goes", "now I deliberately now I will").

    Rule: a word (or 2-word phrase) that is said again within the next 4 words.
      exact same phrase again right away  -> repetition
      otherwise                           -> self-correction / restart
    """
    tokens = [clean(w["word"]) for w in words]
    repairs, i = [], 0
    while i < len(tokens):
        found = False
        for size in (2, 1):                                   # prefer the longer match
            phrase = tokens[i:i + size]
            if len(phrase) < size or phrase[0] in FILLERS or not phrase[0]:
                continue
            for j in range(i + size, min(i + size + 4, len(tokens) - size + 1)):
                if tokens[j:j + size] != phrase:
                    continue
                # single common words repeat naturally ("I think I can"), so a 1-word match
                # that is not directly next to itself only counts when the NEXT words also
                # look alike: "rate it rate its", "he go he goes"
                if size == 1 and j != i + 1:
                    a = tokens[i + 1] if i + 1 < len(tokens) else ""
                    b = tokens[j + 1] if j + 1 < len(tokens) else ""
                    if not (a and b and a[:2] == b[:2]):
                        continue
                    size_end = 2                               # include the next word in the text
                else:
                    size_end = size
                kind = "repetition" if j == i + size else "self-correction"
                text = " ".join(w["word"] for w in words[i:j + size_end])
                repairs.append({"type": kind, "text": text, "start": words[i]["start"]})
                i = j          # continue after the first attempt
                found = True
                break
            if found:
                break
        i += 1 if not found else 0
        if found:
            i += 1
    return repairs


def short_silences(audio):
    """ALL silences of 0.1 s or more (also the short ones that don't count as pauses)."""
    chunks = get_speech_timestamps(audio, VadOptions(min_silence_duration_ms=100, speech_pad_ms=30))
    return [(cur["end"] / SAMPLE_RATE, nxt["start"] / SAMPLE_RATE) for cur, nxt in zip(chunks, chunks[1:])]


def find_lengthened(words, pauses, silences):
    """Words stretched out to stall ("sooo...").

    Whisper stretches a word's timing over the silence next to it ("for" 1.06 s, of which
    0.74 s is silence), so we subtract every silence inside the word first and only judge
    the part where there is actually sound."""
    result = []
    for w in words[1:-1]:                   # first/last word are often stretched into silence
        near_pause = any(w["start"] < p["end"] + 0.3 and w["end"] > p["start"] - 0.3 for p in pauses)
        if near_pause:
            continue
        silent = sum(max(0.0, min(w["end"], e) - max(w["start"], s)) for s, e in silences)
        voiced = (w["end"] - w["start"]) - silent
        # stressed words can take ~0.7 s per syllable; real stalling ("sooo...") is longer
        if voiced / max(count_syllables(w["word"]), 1) > 0.85:
            result.append({"word": w["word"], "start": w["start"], "voiced": round(voiced, 2)})
    return result


# ---------------------------------------------------------------- part 2b / 2d: numbers

def fluency_stats(path):
    audio = decode_audio(path)
    duration = len(audio) / SAMPLE_RATE
    words = transcribe(path)
    pauses = label_pauses(words, find_pauses(audio))
    runs = split_into_runs(words, pauses)

    n_words = len(words)
    syllables = sum(count_syllables(w["word"]) for w in words)
    total_pause = sum(p["length"] for p in pauses)
    # speaking time = from first word to last word, minus the pauses (ignores silence at start/end)
    speech_span = (words[-1]["end"] - words[0]["start"]) if words else 0
    speaking_time = max(speech_span - total_pause, 0.001)

    # speed of each run in syllables per second -> how much it varies
    run_speeds = []
    for run in runs:
        length = run[-1]["end"] - run[0]["start"]
        if length > 0.5:
            run_speeds.append(sum(count_syllables(w["word"]) for w in run) / length)
    speed_variation = (statistics.pstdev(run_speeds) / statistics.mean(run_speeds)) if len(run_speeds) > 1 else 0

    repairs = find_repairs(words)
    return {
        "duration": round(duration, 1),
        "words": n_words,
        "syllables": syllables,
        "pauses": len(pauses),
        "total_pause": round(total_pause, 2),
        "pause_percent": round(total_pause / speech_span * 100, 1) if speech_span else 0,
        "avg_pause": round(total_pause / len(pauses), 2) if pauses else 0,
        "long_pauses": sum(p["length"] >= LONG_PAUSE for p in pauses),
        "mid_phrase_pauses": sum(p["mid_phrase"] for p in pauses),
        "wpm": round(n_words / (duration / 60), 1),
        "articulation_wpm": round(n_words / (speaking_time / 60), 1),
        "syllables_per_sec": round(syllables / speaking_time, 2),
        "speed_variation": round(speed_variation, 2),     # 0 = perfectly even speed
        "mlr": round(n_words / len(runs), 1) if runs else 0,
        "fillers": find_fillers(words),
        "repetitions": [r for r in repairs if r["type"] == "repetition"],
        "self_corrections": [r for r in repairs if r["type"] == "self-correction"],
        "lengthened": find_lengthened(words, pauses, short_silences(audio)),
        "pause_list": pauses,
    }


# ---------------------------------------------------------------- part 2f: score out of 100

def scale(value, bad, good):
    """Map a value to 0..1: 'bad' or worse -> 0, 'good' or better -> 1, linear in between.
    Works both ways (bad < good, e.g. speed; or bad > good, e.g. pause %)."""
    if bad == good:
        return 1.0
    t = (value - bad) / (good - bad)
    return min(max(t, 0.0), 1.0)


# Korean: syllables are short (native ~5-7 a second) and a "word" (eojeol) carries endings, so runs have fewer
# words. PROVISIONAL until tuned on real Korean learner recordings.
SPEED = {"en": (2.0, 3.5), "ko": (2.5, 5.0)}
RUNS = {"en": (3, 10), "ko": (2, 7)}


def fluency_score(s, lang="en"):
    """PROVISIONAL: thresholds come from speech research ranges and must be tuned in part 2g
    against human fluency ratings (speechocean762)."""
    minutes = max(s["duration"] / 60, 0.1)
    parts = {
        # speed: under ~2 syllables/s is slow, ~3.5+ is fluent (English)
        "speed":       (25, scale(s["syllables_per_sec"], *SPEED.get(lang, SPEED["en"]))),
        # pauses: 40% of the time silent is bad, 20% or less is natural
        "pauses":      (20, scale(s["pause_percent"], 40, 20)),
        # mean length of run: 3 words is choppy, 10+ is fluent (English)
        "runs":        (20, scale(s["mlr"], *RUNS.get(lang, RUNS["en"]))),
        # mid-phrase + long pauses per minute
        "hesitations": (15, scale((s["mid_phrase_pauses"] + 2 * s["long_pauses"]) / minutes, 8, 1)),
        # fillers per minute
        "fillers":     (10, scale(len(s["fillers"]) / minutes, 8, 1)),
        # repairs (repetitions + self-corrections + lengthened words) per minute
        "repairs":     (10, scale((len(s["repetitions"]) + len(s["self_corrections"]) + len(s["lengthened"])) / minutes, 6, 1)),
    }
    total = sum(weight * value for weight, value in parts.values())
    details = {name: round(weight * value, 1) for name, (weight, value) in parts.items()}
    return round(total), details


# ---------------------------------------------------------------- test

if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "samples/shuhratkhon_1.ogg"
    stats = fluency_stats(path)

    print("=== numbers ===")
    for key, value in stats.items():
        if not isinstance(value, list):
            print(f"{key:<18} {value}")

    print("\n=== pauses ===")
    for p in stats["pause_list"]:
        where = "MID-PHRASE" if p["mid_phrase"] else "natural"
        print(f"{p['start']:6.2f} -> {p['end']:6.2f}  ({p['length']} s)  '{p['before']}' | '{p['after']}'  {where}")

    for name in ("fillers", "repetitions", "self_corrections", "lengthened"):
        print(f"\n=== {name} ({len(stats[name])}) ===")
        for item in stats[name]:
            print("  ", item)

    score, details = fluency_score(stats)
    print(f"\n=== FLUENCY SCORE: {score}/100 (provisional) ===")
    for name, points in details.items():
        print(f"  {name:<12} {points}")
