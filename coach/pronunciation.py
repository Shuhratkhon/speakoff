"""Step 4: pronunciation.

4a  hear_phonemes(path)    : what sounds the speaker REALLY made (wav2vec2 phoneme model, IPA, 20 ms frames)
4b  expected_phonemes(word): what sounds the word SHOULD have (CMUdict, ARPAbet -> the same IPA symbols)
4c  (next) compare the two per word -> "want: /v/ instead of /w/"

Run (from the Speaking_Coach folder):
  python -m coach.pronunciation samples/shuhratkhon_1.ogg
"""

import json
from pathlib import Path
import re
import sys

import cmudict
import numpy as np
import torch
from huggingface_hub import hf_hub_download
from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForCTC

# ---------------------------------------------------------------- 4b: expected sounds
DICT = cmudict.dict()          # 126k words: "want" -> [['W','AA1','N','T'], ['W','AO1','N','T']]

# ARPAbet (CMUdict) -> IPA, written the way the phoneme model writes it (espeak en-us style).
# Vowels end in a stress number: 1 = main stress, 2 = second stress, 0 = no stress.
VOWELS = {
    "AA": "ɑː", "AE": "æ", "AH": "ʌ", "AO": "ɔː", "AW": "aʊ", "AY": "aɪ", "EH": "ɛ",
    "ER": "ɜː", "EY": "eɪ", "IH": "ɪ", "IY": "iː", "OW": "oʊ", "OY": "ɔɪ", "UH": "ʊ", "UW": "uː",
}
UNSTRESSED = {"AH": "ə", "ER": "ɚ", "IH": "ɪ", "IY": "i"}   # weak forms: "about" = ə, "better" = ɚ
CONSONANTS = {
    "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ", "HH": "h", "JH": "dʒ", "K": "k",
    "L": "l", "M": "m", "N": "n", "NG": "ŋ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ", "T": "t",
    "TH": "θ", "V": "v", "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}
# vowel + R joined into one symbol, as the model does ("car" = k ɑːɹ)
R_JOIN = {"ɑː": "ɑːɹ", "ɔː": "ɔːɹ", "ɛ": "ɛɹ", "ɪ": "ɪɹ", "ʊ": "ʊɹ"}


def arpabet_to_ipa(arpa):
    """['W','AA1','N','T'] -> ['w','ɑː','n','t']"""
    out = []
    for p in arpa:
        base, stress = re.match(r"([A-Z]+)(\d?)", p).groups()
        if base in VOWELS:
            out.append(UNSTRESSED.get(base, VOWELS[base]) if stress == "0" else VOWELS[base])
        elif base == "R" and out and out[-1] in R_JOIN:
            out[-1] = R_JOIN[out[-1]]
        else:
            out.append(CONSONANTS[base])
    return out


def expected_phonemes(word):
    """All correct pronunciations of a word (IPA lists), or [] if the word is not in the dictionary
    (names like "Gachon", made-up words): we skip those instead of guessing."""
    key = re.sub(r"[^a-z']", "", word.lower())
    return [arpabet_to_ipa(a) for a in DICT.get(key, [])]


# ---------------------------------------------------------------- 4a: heard sounds
PHONE_MODEL = "facebook/wav2vec2-lv-60-espeak-cv-ft"
FRAME = 0.02                   # the model gives one prediction every 20 ms
torch.set_num_threads(4)

_extractor = Wav2Vec2FeatureExtractor.from_pretrained(PHONE_MODEL)
from coach.device import DEVICE                                   # GPU when the server has one
_model = Wav2Vec2ForCTC.from_pretrained(PHONE_MODEL).eval().to(DEVICE)
with open(hf_hub_download(PHONE_MODEL, "vocab.json"), encoding="utf-8") as f:
    _id2phone = {i: p for p, i in json.load(f).items()}


def load_audio(path):
    """Any audio file -> mono float32 at 16 kHz (decoded with faster-whisper's helper, no ffmpeg needed)."""
    from faster_whisper.audio import decode_audio
    return decode_audio(path, sampling_rate=16000)


def hear_phonemes(audio, chunk_s=20):
    """Return log-probabilities [frames x 392 phonemes]. Long audio is cut into 20 s pieces to save memory."""
    parts = []
    step = chunk_s * 16000
    for i in range(0, len(audio), step):
        piece = audio[i:i + step]
        if len(piece) < 400:
            break
        inputs = _extractor(piece, sampling_rate=16000, return_tensors="pt")
        with torch.no_grad():
            parts.append(torch.log_softmax(_model(inputs.input_values.to(DEVICE)).logits[0], -1).cpu())
    return torch.cat(parts)


def greedy(logprobs):
    """Most likely phoneme in every frame, repeats and blanks removed (simple CTC decoding)."""
    ids = logprobs.argmax(-1).tolist()
    out, prev = [], None
    for i in ids:
        if i != prev and i != 0:            # 0 = <pad> = CTC blank
            out.append(_id2phone[i])
        prev = i
    return out


def heard_in_word(logprobs, start, end, pad=0.04):
    """Phonemes heard between a word's Whisper start/end time (a little padding on both sides)."""
    a = max(0, int((start - pad) / FRAME))
    b = min(len(logprobs), int((end + pad) / FRAME) + 1)
    return greedy(logprobs[a:b])


# ---------------------------------------------------------------- 4c: compare sound by sound
_phone2id = {p: i for i, p in _id2phone.items()}

# The model writes some sounds in several ways that are all fine for English
# (weak vowels, American "t" flap in "better", cot/caught). An expected sound counts as
# said right if the model heard ANY sound of its group.
SAME = {
    "ə": "ə ɐ ʌ ᵻ ɪ əl ɚ", "ʌ": "ʌ ɐ ə", "ɪ": "ɪ ᵻ i ə", "i": "i iː ɪ ᵻ", "iː": "iː i",
    "t": "t ɾ ʔ", "d": "d ɾ", "ɑː": "ɑː ɑ ɔː ɑːɹ", "ɔː": "ɔː ɑː ɔ ɔːɹ", "ɚ": "ɚ ɜː ə ɐ əl", "ɜː": "ɜː ɚ",
    "ɔːɹ": "ɔːɹ oːɹ", "uː": "uː u", "ʊ": "ʊ u", "oʊ": "oʊ o əʊ", "eɪ": "eɪ e", "l": "l ɫ əl",
    "ɛɹ": "ɛɹ ɛ", "ɪɹ": "ɪɹ iə", "ɹ": "ɹ ɚ", "ɡ": "ɡ",
}
# Tuned in step 4d on speechocean762 (teacher-scored learner speech, evaluate/speechocean_eval.py):
# a sound is marked WRONG when it was at least e^5.25 (~190x) less likely than the best one.
# (-2.0 flagged 71% of real mistakes but 83% of its flags were false; -5.25 gives best F1.)
WRONG_GOP = -5.25


def group_ids(phone):
    return [_phone2id[p] for p in SAME.get(phone, phone).split() if p in _phone2id]


def force_align(lp, phones):
    """CTC Viterbi forced alignment: which frames belong to which expected sound.
    lp: [T x vocab] numpy log-probs, phones: list of IPA symbols. Returns [(first, last frame)] or None."""
    T, L = len(lp), len(phones)
    em = np.stack([np.logaddexp.reduce(lp[:, group_ids(p)], axis=1) for p in phones], 1)   # [T x L]
    S = 2 * L + 1                                     # blank, p1, blank, p2, ..., blank
    emis = np.empty((T, S))
    emis[:, 0::2] = lp[:, :1]                          # id 0 = blank
    emis[:, 1::2] = em
    can_skip = np.zeros(S, bool)                       # jump over a blank only between DIFFERENT sounds
    for k in range(1, L):
        can_skip[2 * k + 1] = phones[k] != phones[k - 1]
    NEG = -1e9
    score = np.full(S, NEG)
    score[0], score[1] = emis[0, 0], emis[0, 1]
    back = np.zeros((T, S), np.int8)
    for t in range(1, T):
        stay = score
        step = np.concatenate([[NEG], score[:-1]])
        skip = np.where(can_skip, np.concatenate([[NEG, NEG], score[:-2]]), NEG)
        best = np.stack([stay, step, skip])
        choice = best.argmax(0)
        score = best[choice, np.arange(S)] + emis[t]
        back[t] = choice
    s = S - 1 if score[S - 1] >= score[S - 2] else S - 2
    if score[s] < NEG / 2:
        return None                                    # segment too short for these sounds
    frames = [[None, None] for _ in phones]
    for t in range(T - 1, -1, -1):
        if s % 2:
            k = s // 2
            frames[k][0] = t
            frames[k][1] = frames[k][1] if frames[k][1] is not None else t
        s -= int(back[t, s])          # int(): numpy int8 would overflow above 127
    return frames


def edit_distance(a, b):
    d = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, y in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (x != y))
    return d[-1]


def check_pronunciation(words, logprobs):
    """For every dictionary word: each expected sound -> ok / heard something else.
    Words are aligned in segments (split at pauses and at words not in the dictionary)."""
    lp_all = logprobs.numpy()
    segments, cur = [], []
    for w in words:
        from coach.fluency import FILLERS, clean
        options = [] if clean(w["word"]) in FILLERS else expected_phonemes(w["word"])
        if not options:                                # name / number: skip and cut the segment here
            segments.append(cur); cur = []
            continue
        if cur and w["start"] - cur[-1][0]["end"] > 0.25:
            segments.append(cur); cur = []
        # pick the dictionary variant closest to what was heard (e.g. "the" = ðə or ðiː)
        heard = heard_in_word(logprobs, w["start"], w["end"])
        cur.append((w, min(options, key=lambda o: edit_distance(o, heard))))
    segments.append(cur)

    results = []
    for seg in filter(None, segments):
        a = max(0, int((seg[0][0]["start"] - 0.1) / FRAME))
        b = min(len(lp_all), int((seg[-1][0]["end"] + 0.1) / FRAME) + 1)
        phones = [p for _, ph in seg for p in ph]
        frames = force_align(lp_all[a:b], phones)
        if frames is None:
            continue
        scored = score_sounds(lp_all[a:b], phones, frames)
        model_scores(lp_all[a:b], phones, frames, scored)
        k = 0
        for w, ph in seg:
            results.append({"word": w["word"], "start": w["start"], "sounds": scored[k:k + len(ph)]})
            k += len(ph)
    return results


# ---------------------------------------------------------------- trained scoring model (step 4d+)
# GOPT-style transformer trained on speechocean762 teacher scores (training/train_pron.py).
# Test PCC with teachers: sounds 0.64, sentence accuracy 0.75 (simple formula: 0.42 / 0.56).
GOPT_PATH = Path(__file__).resolve().parent.parent / "models" / "pron-gopt" / "model.pt"
MODEL_WRONG = 1.1        # predicted teacher sound score (0-2) below this -> sound marked wrong
_gopt = None


def english_phone_ids():
    names = set(VOWELS.values()) | set(UNSTRESSED.values()) | set(CONSONANTS.values()) | set(R_JOIN.values())
    for group in SAME.values():
        names |= set(group.split())
    return sorted(_phone2id[n] for n in names if n in _phone2id)


def _load_gopt():
    global _gopt
    if _gopt is None and GOPT_PATH.exists():
        from training.train_pron import GOPT
        ck = torch.load(GOPT_PATH, weights_only=False)
        model = GOPT(ck["in_dim"], len(ck["vocab"]))
        model.load_state_dict(ck["state"])
        _gopt = (model.eval(), ck, english_phone_ids())
    return _gopt


def model_scores(lp_seg, phones, frames, sounds, chunk=60):
    """Add the trained model's opinion: every sound's score (0-2, like the teachers) and, per piece of
    speech, the sentence accuracy / fluency (0-10). Long pieces are cut into 60-sound chunks."""
    loaded = _load_gopt()
    if loaded is None:
        return
    model, ck, ids = loaded
    for c in range(0, len(phones), chunk):
        ph, fr, so = phones[c:c + chunk], frames[c:c + chunk], sounds[c:c + chunk]
        speech_frames = fr[-1][1] - fr[0][0] + 1
        rows = []
        for (f0, f1), s in zip(fr, so):
            feat = np.round(lp_seg[f0:f1 + 1][:, ids].mean(0), 2)
            rows.append(np.concatenate([feat, [np.clip(s["gop"], -10, 1), np.log1p(f1 - f0 + 1),
                                               len(ph) / max(speech_frames, 1) * 10]]))
        x = torch.tensor(np.array(rows), dtype=torch.float32)[None]
        x = (x - ck["mean"]) / ck["std"]
        idx = torch.tensor([[ck["vocab"].get(p, 0) for p in ph]])
        mask = torch.ones(1, len(ph), dtype=torch.bool)
        with torch.no_grad():
            p_ph, _, p_ut = model(x, idx, mask)
        utt = (p_ut[0] * 5).tolist()                               # back to the teachers' 0-10 scale
        for s, v in zip(so, p_ph[0].tolist()):
            s["model"] = round(v, 2)
            s["gop_ok"], s["gop_heard"] = s["ok"], s["heard"]      # what the simple sound comparison said
            s["ok"] = v >= MODEL_WRONG
            s["piece"] = {"accuracy": utt[0], "fluency": utt[1], "n": len(ph)}
            s["heard"] = s["expected"] if s["ok"] or s["heard"] == s["expected"] else s["heard"]


def score_sounds(lp_seg, phones, frames=None):
    """Align the expected sounds to a piece of audio and judge each one.
    gop = 'goodness of pronunciation': log(prob of the expected sound / prob of the best sound),
    0 = the expected sound was the most likely, -3 = it was 20x less likely than something else."""
    frames = frames or force_align(lp_seg, phones)
    if frames is None:
        return None
    sounds = []
    for p, (f0, f1) in zip(phones, frames):
        lp = lp_seg[f0:f1 + 1]
        ids = group_ids(p)
        gop = float(np.mean(np.logaddexp.reduce(lp[:, ids], axis=1) - lp[:, 1:].max(1)))
        best = int(lp[:, 1:].sum(0).argmax()) + 1
        ok = best in ids or gop > WRONG_GOP
        sounds.append({"expected": p, "heard": p if ok else _id2phone[best], "ok": ok, "gop": round(gop, 2),
                       "best": p if best in ids else _id2phone[best]})      # most likely sound, for habits
    return sounds


def model_fluency(results):
    """The trained model's fluency (smooth, steady speech inside each piece; pauses are judged by
    fluency.py), as 0-100, or None without the model. Teachers' fluency score vs average prediction on
    unseen speechocean762 speech: 4 -> 5.0, 5 -> 5.3, 6 -> 6.4, 7 -> 7.4, 8 -> 8.2, 9 -> 8.8, 10 -> 9.1."""
    sounds = [s for r in results for s in r["sounds"] if "piece" in s]
    if not sounds:
        return None
    flu = float(np.mean([s["piece"]["fluency"] for s in sounds]))
    return round(float(np.interp(flu, [4.96, 5.34, 6.41, 7.41, 8.23, 8.79, 9.11], [40, 50, 60, 70, 80, 90, 100])))


def pronunciation_score(results):
    """Score out of 100. With the trained model: its predicted teachers' accuracy (0-10) per piece of
    speech, averaged by length, then stretched like the teachers' scale. Without it: the simple formula."""
    sounds = [s for r in results for s in r["sounds"]]
    if not sounds:
        return 0, 0.0
    right = sum(s["ok"] for s in sounds) / len(sounds)
    if "piece" in sounds[0]:
        acc = float(np.mean([s["piece"]["accuracy"] for s in sounds]))     # each sound = its piece's score
        # average prediction per teacher score on unseen test speech: 3-5 -> 5.3, 6 -> 6.5, 7 -> 7.3,
        # 8 -> 8.2, 9 -> 8.7, 10 -> 8.9 (predictions lean to the middle) -> stretch back
        shown = np.interp(acc, [4.0, 5.3, 6.5, 7.3, 8.2, 8.7, 9.0, 9.4], [15, 35, 55, 65, 78, 88, 97, 100])
        return round(float(shown)), right
    return formula_score(sounds, right)


def formula_score(sounds, right):
    """Score out of 100, fitted in step 4d to predict expert teachers' accuracy score (0-10, x10).
    Uses: share of sounds said right, average GOP, and the average of the worst 20% of sounds.
    On unseen test speech: correlation with teachers 0.56 (adults 0.66), average error ~9 points."""
    g = np.sort(np.clip([s["gop"] for s in sounds], -10, 0))
    worst = g[:max(1, len(g) // 5)].mean()
    predicted = 2.933 * right + 0.04 * g.mean() + 0.331 * worst + 5.914      # teachers' 0-10 scale
    # The fit predicts the AVERAGE teacher score, which squeezes everyone toward the middle
    # (teacher 8, 9 and 10 sentences all came out 78-83). Stretch it back using the average prediction
    # per teacher score (speechocean762 test: 3-5 -> 61, 6 -> 66, 7 -> 71, 8 -> 78.5, 9 -> 82) and two
    # native speakers (86), so the shown score spreads like the teachers' scores do.
    shown = np.interp(predicted * 10, [50, 61, 66, 71, 78.5, 82, 86, 90], [15, 35, 55, 65, 78, 88, 97, 100])
    return round(float(shown)), right


# swaps native speakers make too (accent variants, weak vowels): never reported as habits
NATIVE_VARIANTS = {("ɑː", "ɔ"), ("ɑː", "ɒ"), ("ɔː", "ɔ"), ("ə", "uː"), ("ə", "ʊ"), ("ə", "u"), ("ɪ", "ɛ"),
                   ("i", "ɪ"), ("ʊ", "uː")}


def common_mistakes(results, top=6, habit=3):
    """Sounds to practise, most frequent first, with example words:
    - every sound the trained model scored below the teachers' 'wrong' level ('?' = unclear, no clear other sound)
    - plus any swap the sound comparison heard at least `habit` times: a repeated swap
      (e.g. /th/ -> /z/ in 'the, that, they') is a habit even if each single case sounded acceptable."""
    from collections import defaultdict
    swaps = defaultdict(list)
    habits = defaultdict(list)
    for r in results:
        word = r["word"].strip(",.?!")
        for s in r["sounds"]:
            if not s["ok"]:
                heard = s["heard"] if s["heard"] != s["expected"] else "?"
                swaps[(s["expected"], heard)].append(word)
            elif s.get("best", s["expected"]) != s["expected"] and (s["expected"], s["best"]) not in NATIVE_VARIANTS:
                habits[(s["expected"], s["best"])].append(word)
    for key, words in habits.items():
        if len(words) >= habit:
            swaps[key] += words
    return sorted(swaps.items(), key=lambda kv: -len(kv[1]))[:top]


def analyse(path, words=None):
    from coach.transcribe import transcribe
    words = words or transcribe(path)
    results = check_pronunciation(words, hear_phonemes(load_audio(path)))
    return results


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "samples/shuhratkhon_1.ogg"
    results = analyse(path)
    score, right = pronunciation_score(results)
    print(f"PRONUNCIATION: {score}/100   sounds right: {right:.0%}")
    for (exp, heard), ws in common_mistakes(results):
        print(f"  /{exp}/ -> /{heard}/  x{len(ws)}: {', '.join(dict.fromkeys(ws))}")
