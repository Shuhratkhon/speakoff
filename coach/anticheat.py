"""Anti-cheat checks (2026-11-25): is this answer really spoken, in the player's own words, by the player?

Signals (calibrated on the 13 real sample recordings and 6 AI-written answers read by AI voices, 2026-11-25):
  * ai_text     the transcript is very predictable for a small language model (Qwen2.5-0.5B, already used by
                coach/topic.py): perplexity < AI_PPL. AI answers 6-9.5, real spoken answers 18-68.
  * too_smooth  almost no fillers / self-corrections (< 0.5 per minute) AND faster than 4.2 syllables a second.
                AI voices 4.5-5.7 syll/s with 0 fillers; real learners 2.5-3.5 syll/s.
  * voice       a voice fingerprint (microsoft/wavlm-base-plus-sv, CC BY-SA 3.0, used only on our server) compared
                with the player's earlier recordings (needs MIN_PRINTS). Same person >= 0.938; AI voices <= 0.82.
                Two similar human voices can look alike, so only a clearly different voice is flagged (< VOICE_MIN).
  * jump        the overall score is JUMP points above the player's usual level (needs MIN_HISTORY answers).
Verdict: "cheat" (overall capped like an off-topic answer) when the voice is clearly not the player's, or the text is
AI-written AND too smooth, or a big jump comes with either of those signs. "tip" when only one sign shows. A jump alone
is never punished: people do improve. A tested AI-voice detector (Deepfake-audio-detection-V2) was dropped: it called
every AI voice "real" and 3 real video recordings "fake".
"""

import json
import math
import statistics
import threading

AI_PPL = 12.0
SMOOTH_FILLERS_PM, SMOOTH_SPS = 0.5, 4.2
VOICE_MIN, MIN_PRINTS, MAX_PRINTS = 0.88, 3, 10
JUMP, MIN_HISTORY = 25, 5
SV_MODEL = "microsoft/wavlm-base-plus-sv"

_lock = threading.Lock()
_sv = {}


def _load_sv():
    with _lock:
        if not _sv:
            from transformers import AutoFeatureExtractor, WavLMForXVector
            _sv["fx"] = AutoFeatureExtractor.from_pretrained(SV_MODEL)
            _sv["model"] = WavLMForXVector.from_pretrained(SV_MODEL).eval()
    return _sv


def _wav16k(path, seconds=30):
    import av
    import numpy as np
    out, n = [], 0
    with av.open(str(path)) as c:
        rs = av.AudioResampler(format="flt", layout="mono", rate=16000)
        for fr in c.decode(c.streams.audio[0]):
            for f in rs.resample(fr):
                a = f.to_ndarray().reshape(-1)
                out.append(a)
                n += len(a)
            if n > seconds * 16000:
                break
    return np.concatenate(out)[: seconds * 16000].astype("float32") if out else None


def voiceprint(audio_path):
    """A normalised voice fingerprint (list of floats) from the first 30 s, or None."""
    import torch
    wav = _wav16k(audio_path)
    if wav is None or len(wav) < 16000 * 3:
        return None
    sv = _load_sv()
    x = sv["fx"](wav, sampling_rate=16000, return_tensors="pt")
    with torch.no_grad():
        e = sv["model"](**x).embeddings[0]
    return torch.nn.functional.normalize(e, dim=-1).tolist()


def perplexity(text):
    import torch
    from coach import topic
    m = topic._load()
    ids = m["tok"](text, return_tensors="pt").input_ids[:, :512]
    if ids.shape[1] < 20:
        return None
    with torch.no_grad():
        return math.exp(m["llm"](ids, labels=ids).loss.item())


def check(d, audio_path, overall, earlier_prints=(), earlier_scores=()):
    """d = the analysis (text, fluency, duration). Returns the signals, the verdict and this answer's voice print."""
    fl, dur = d.get("fluency") or {}, max(d.get("duration") or 0, 1)
    out = {}
    english = d.get("lang", "en") == "en"          # the text and smoothness limits are calibrated on English
    ppl = perplexity(d.get("text", "")) if english else None
    out["ppl"] = round(ppl, 1) if ppl else None
    out["ai_text"] = bool(ppl and ppl < AI_PPL)
    fpm = 60 * ((fl.get("fillers") or 0) + (fl.get("repairs") or 0)) / dur
    out["too_smooth"] = english and fpm < SMOOTH_FILLERS_PM and (fl.get("syllables_per_sec") or 0) > SMOOTH_SPS
    vp = voiceprint(audio_path)
    out["voice"], out["voice_mismatch"] = None, False
    prints = [p for p in earlier_prints if p][-MAX_PRINTS:]
    if vp and len(prints) >= MIN_PRINTS:
        import numpy as np
        c = np.mean(prints, 0)
        c = c / np.linalg.norm(c)
        out["voice"] = round(float(np.dot(vp, c)), 3)
        out["voice_mismatch"] = out["voice"] < VOICE_MIN
    scores = [s for s in earlier_scores if s is not None]
    out["jump"] = len(scores) >= MIN_HISTORY and overall >= statistics.median(scores) + JUMP
    script = out["ai_text"] and out["too_smooth"]
    if out["voice_mismatch"] or script or (out["jump"] and (out["ai_text"] or out["too_smooth"])):
        out["verdict"] = "cheat"
    elif out["ai_text"] or out["too_smooth"]:
        out["verdict"] = "tip"
    else:
        out["verdict"] = "ok"
    return out, vp
