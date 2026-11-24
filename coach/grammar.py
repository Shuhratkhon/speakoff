"""Step 3: grammar.

1. A T5 model rewrites each sentence correctly   ("I studying in" -> "I studied at")
2. ERRANT compares the two and labels each change ("in -> at" = preposition)
3. We drop "mistakes" that are not the speaker's fault:
   - punctuation / capital letters (Whisper wrote those, not the speaker)
   - words Whisper was unsure it heard correctly (could be a hearing error, not a grammar error)
"""

from pathlib import Path

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import errant

# OUR fine-tuned model v3 (v2 + 1 epoch on 20k new-type synthetic + 100k mixed pairs, 8.6 h on CPU).
# Speech test: 95.2% -> 99.3% mistakes fixed; real recordings slightly better; BEA essays slightly lower
# (speech F0.5 0.502 -> 0.487). To go back, change "v3" to "v2" below.
# Falls back to the original model if the folder is missing (e.g. a fresh clone without models/).
_OURS = Path(__file__).resolve().parent.parent / "models" / "grammar-speech-v3"
MODEL_NAME = str(_OURS) if _OURS.exists() else "vennify/t5-base-grammar-correction"
# Mistakes on words Whisper heard with less confidence than this go to "uncertain".
# Tested on our samples: Whisper's confidence is NOT a good hearing-error detector (real words the
# speaker said got 0.24-0.32, mis-heard words got 0.56-0.96), so only very unsure words are held back.
MIN_WORD_PROBABILITY = 0.15

# the T5 model (900 MB) is loaded ONCE, the first time a sentence is corrected
# (so just computing a score from saved results does not load it)
_t5 = None


def _load():
    global _t5
    if _t5 is None:
        from coach.device import DEVICE
        _t5 = (AutoTokenizer.from_pretrained(MODEL_NAME), AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME).to(DEVICE))
    return _t5


annotator = errant.load("en")   # also loads spaCy, which we use to split sentences

# ERRANT type -> words a learner understands
TYPE_NAMES = {
    "VERB:TENSE": "verb tense", "VERB:FORM": "verb form", "VERB:SVA": "subject-verb agreement",
    "VERB": "wrong verb", "NOUN:NUM": "singular/plural", "NOUN": "wrong noun",
    "NOUN:POSS": "possessive", "DET": "article / determiner (a, the, this)", "PREP": "preposition",
    "PRON": "pronoun", "ADJ": "adjective", "ADJ:FORM": "adjective form (big/bigger/biggest)",
    "ADV": "adverb", "CONJ": "conjunction", "PART": "particle", "MORPH": "word form",
    "WO": "word order", "SPELL": "spelling", "CONTR": "contraction", "OTHER": "other",
}
# changes that are about writing, not speaking -> ignore
IGNORED_TYPES = {"PUNCT", "ORTH", "SPELL"}


def correct(sentence):
    """Return the corrected sentence."""
    tokenizer, model = _load()
    ids = tokenizer("grammar: " + sentence, return_tensors="pt").input_ids.to(model.device)   # text -> numbers
    output = model.generate(ids, max_length=128, num_beams=5)                # model writes the answer
    return tokenizer.decode(output[0], skip_special_tokens=True)            # numbers -> text


def describe(error_type):
    """'R:VERB:FORM' -> ('replace', 'verb form')."""
    operation, _, category = error_type.partition(":")
    action = {"R": "wrong word", "M": "missing word", "U": "unnecessary word"}.get(operation, operation)
    return action, TYPE_NAMES.get(category, category.lower())


def find_mistakes(original, corrected):
    """Return a list of {"wrong", "right", "type", "action", "category"} for each difference."""
    # Commas come from Whisper, not from the speaker, so compare WITHOUT them;
    # otherwise "parts," -> "part" becomes an "other" mistake instead of singular/plural.
    orig = annotator.parse(original.replace(",", ""))
    corr = annotator.parse(corrected.replace(",", ""))
    mistakes = []
    for e in annotator.annotate(orig, corr):
        category = e.type.partition(":")[2]
        if category in IGNORED_TYPES:
            continue
        if e.o_str.strip(".?!") == e.c_str.strip(".?!"):   # only a full stop differs
            continue
        action, name = describe(e.type)
        mistakes.append({
            "wrong": e.o_str, "right": e.c_str, "type": e.type,
            "action": action, "category": name,
            "token_start": e.o_start, "token_end": e.o_end,   # position in the sentence (in words)
        })
    return mistakes


def check_text(text):
    """Split text into sentences and check each one."""
    results = []
    sentences = [s.text.strip() for s in annotator.nlp(text).sents]
    for i, original in enumerate(sentences):
        if len(original.split()) < 3:          # "So," / "Ninth," - too short to judge
            continue
        if i == len(sentences) - 1 and not original.endswith((".", "?", "!")):
            continue                           # recording stopped mid-sentence: can't judge it
        corrected = correct(original)
        results.append({"original": original, "corrected": corrected,
                        "mistakes": find_mistakes(original, corrected)})
    return results


def remove_disfluencies(words):
    """Fillers and repetitions are FLUENCY problems (already counted in fluency.py).
    Remove them so the grammar model does not 'correct' them:
    'my university, my university, hmm, I studying' -> 'my university, I studying'."""
    from coach.fluency import FILLERS, clean

    kept = [w for w in words if clean(w["word"]) not in FILLERS]
    result = []
    for w in kept:
        tokens = [clean(x["word"]) for x in result]
        token = clean(w["word"])
        if tokens and token == tokens[-1]:                       # "parts, parts"
            continue
        result.append(w)
        tokens.append(token)
        if len(tokens) >= 4 and tokens[-2:] == tokens[-4:-2]:     # "my university, my university"
            result = result[:-2]
    return result


def check_transcript(words):
    """Check the word list from transcribe(). Mistakes on words Whisper was unsure about
    are moved to 'uncertain' instead of being shown as the speaker's mistakes."""
    words = remove_disfluencies(words)
    text = " ".join(w["word"] for w in words)
    unsure = {w["word"].strip(",.?!").lower() for w in words if w["probability"] < MIN_WORD_PROBABILITY}

    results = check_text(text)
    for r in results:
        sure, uncertain = [], []
        for m in r["mistakes"]:
            touched = {t.strip(",.?!").lower() for t in m["wrong"].split()}
            (uncertain if touched & unsure else sure).append(m)
        r["mistakes"], r["uncertain"] = sure, uncertain
    return results


def print_results(results):
    for r in results:
        if not r["mistakes"] and not r.get("uncertain"):
            continue
        print(f"\n  said:    {r['original']}\n  better:  {r['corrected']}")
        for m in r["mistakes"]:
            print(f"    ✗ {m['category']:<28} '{m['wrong']}' -> '{m['right']}'   ({m['action']}, {m['type']})")
        for m in r.get("uncertain", []):
            print(f"    ? (unsure if heard right)   '{m['wrong']}' -> '{m['right']}'   ({m['type']})")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:                       # python -m coach.grammar samples/file.ogg
        from coach.transcribe import transcribe
        results = check_transcript(transcribe(sys.argv[1]))
    else:
        results = check_text(
            "This is another test of recording to check if the module correctly finds sounds. "
            "I studying in Gachon University. "
            "So this was the last parts of the audio."
        )
    print_results(results)
    total = sum(len(r["mistakes"]) for r in results)
    print(f"\nSentences checked: {len(results)}   Mistakes: {total}")


def grammar_score(results, n_words):
    """PROVISIONAL score out of 100 from the mistakes the model found.
    70% = mistakes per 100 words (0 -> full points, 12+ -> none),
    30% = share of sentences with no mistakes. Uncertain (mis-heard?) mistakes are not counted."""
    mistakes = sum(len(r["mistakes"]) for r in results)
    per_100 = mistakes / max(n_words, 1) * 100
    clean = sum(not r["mistakes"] for r in results) / max(len(results), 1)
    rate_part = min(max(1 - per_100 / 12, 0), 1)
    return round(100 * (0.7 * rate_part + 0.3 * clean)), round(per_100, 1), clean
