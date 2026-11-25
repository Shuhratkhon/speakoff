"""Step 1: speech -> text, with the start and end time of every word."""

from faster_whisper import WhisperModel

# Load the model ONCE when this file is imported (loading is slow, using it is fast).
# small.en = English-only "small" model; int8 = smaller numbers, runs fast on CPU (float16 on a GPU).
from coach.device import DEVICE
model = WhisperModel("small.en", device=DEVICE, compute_type="float16" if DEVICE == "cuda" else "int8")

FILLER_PROMPT = "Um, uh, hmm, I mean, like, you know."
# other learning languages (2026-11-26): the multilingual "small" model, with a filler prompt in that language
PROMPTS = {"ko": "음, 어, 그러니까, 저기요."}
_multi = None


def _multilingual():
    global _multi
    if _multi is None:
        _multi = WhisperModel("small", device=DEVICE, compute_type="float16" if DEVICE == "cuda" else "int8")
    return _multi


def transcribe(path, lang="en"):
    """Return a list of {"word", "start", "end", "probability"} dicts for an audio file."""
    # segments is a generator: the audio is only processed while we loop over it.
    # Whisper was trained on clean subtitles, so it normally DELETES fillers (um, uh, hmm)
    # and some repetitions. Starting it with a prompt that contains fillers makes it
    # write down what was really said, which fluency needs.
    if lang != "en":
        segments, info = _multilingual().transcribe(str(path), language=lang, word_timestamps=True,
                                                    initial_prompt=PROMPTS.get(lang))
    else:
        segments, info = model.transcribe(path, word_timestamps=True, initial_prompt=FILLER_PROMPT)

    words = []
    for segment in segments:
        for w in segment.words:
            words.append({
                "word": w.word.strip(),          # Whisper adds a leading space: " hello"
                "start": round(float(w.start), 2),      # seconds from the beginning
                "end": round(float(w.end), 2),
                "probability": round(float(w.probability), 2),  # how sure Whisper is (0-1)
            })
    return words


if __name__ == "__main__":
    import sys

    audio = sys.argv[1] if len(sys.argv) > 1 else "samples/shuhratkhon_1.ogg"
    result = transcribe(audio)

    for w in result:
        print(f"{w['start']:6.2f} - {w['end']:6.2f}  {w['word']:<15} ({w['probability']})")

    print("\nFull text:", " ".join(w["word"] for w in result))
    print("Word count:", len(result))
