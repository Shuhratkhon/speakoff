"""Calibrate Korean pronunciation (coach/korean_pron.py) on native (samples/native_*) vs learner Korean samples.
Prints the raw measures for several WRONG_GOP thresholds so the score can be set to separate the two groups."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from coach import korean_pron as K  # noqa: E402
from coach import pronunciation as P  # noqa: E402
from coach.transcribe import transcribe  # noqa: E402

CACHE = ROOT / "evaluate" / "results" / "ko_pron_cache_conv.json"
LEARNERS = ["normurod_2", "sherzodbek_1", "rahimjon_2", "rahimjon_3"]
NATIVES = [f"native_{i}" for i in range(1, 7)]
cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
data = {}
CONV = ROOT / "evaluate" / "results" / "ko_conv"
CONV.mkdir(parents=True, exist_ok=True)
from server import media  # noqa: E402
for n in LEARNERS + NATIVES:
    path = CONV / f"{n}.ogg"                  # the same conversion the app does (mono Opus 32 kbit/s)
    if not path.exists():
        media.to_audio(ROOT / "samples" / f"{n}.ogg", path, 300)
    if n not in cache:
        cache[n] = {"words": transcribe(path, lang="ko")}
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    data[n] = (cache[n]["words"], P.hear_phonemes(P.load_audio(path)))
    print("heard", n, flush=True)

for thr in (-4.0,):
    K.WRONG_GOP = thr
    print(f"\nWRONG_GOP {thr}")
    for n in LEARNERS + NATIVES:
        words, lp = data[n]
        res = K.check(words, lp)
        m = K.raw_measures(res, words)
        sc = K.score(m)
        top = [(e, h, len(w)) for (e, h), w in K.common_mistakes(res, top=4)]
        print(f"  {n:13} right {m['right']:.2f} gop {m['gop']:.2f} clear {m['clear']:.2f} -> {sc} | {top}")
