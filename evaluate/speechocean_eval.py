"""Step 4d: test our pronunciation and fluency scores against EXPERT TEACHERS (speechocean762).

speechocean762: 5000 short English sentences read by Mandarin-native learners (half children),
each scored by 5 experts: sentence accuracy / fluency / total (0-10) and every sound (0-2).

Part 1 (slow, runs the models once, saves to logs/so762_<split>.jsonl, can be stopped and resumed):
  python -m evaluate.speechocean_eval extract train 500
  python -m evaluate.speechocean_eval extract test 500
Part 2 (fast): correlations with the teachers + tuned thresholds (tuned on train, judged on test):
  python -m evaluate.speechocean_eval report

Note: here the sentence text is known, so the pronunciation part is tested on the teachers' own
expected sounds (no Whisper / dictionary); fluency runs our full pipeline (Whisper + pauses).
"""

import io
import json
import random
import re
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "speechocean762" / "data"
LOGS = ROOT / "logs"
WRONG_HUMAN = 0.8          # teachers' average sound score <= 0.8 (of 2) -> the sound was WRONG


# ---------------------------------------------------------------- part 1: run the models

def to_ipa_with_index(phones):
    """Teachers' ARPAbet sounds of one word -> our IPA sounds, plus which teacher sounds each one covers
    (vowel + R become one IPA sound, e.g. AA R -> ɑːɹ)."""
    from coach.pronunciation import arpabet_to_ipa, R_JOIN
    out, idx = [], []
    for i, p in enumerate(phones):
        ipa = arpabet_to_ipa([p])[0]
        if p.startswith("R") and p[1:2] in ("", "0", "1", "2") and out and out[-1] in R_JOIN:
            out[-1] = R_JOIN[out[-1]]
            idx[-1].append(i)
        else:
            out.append(ipa)
            idx.append([i])
    return out, idx


def extract(split, n):
    import pyarrow.parquet as pq
    from faster_whisper.audio import decode_audio
    from coach import pronunciation, fluency

    out_file = LOGS / f"so762_{split}.jsonl"
    done = set()
    if out_file.exists():
        done = {json.loads(l)["id"] for l in out_file.read_text(encoding="utf-8").splitlines() if l.strip()}

    table = pq.read_table(next(DATA.glob(f"{split}-*.parquet")))
    order = list(range(table.num_rows))
    random.Random(0).shuffle(order)                  # random sentences, not one speaker after another
    order = [i for i in order[:n] if i not in done]
    print(f"{split}: {len(done)} already done, {len(order)} to go", flush=True)

    tmp = Path(tempfile.gettempdir()) / "so762_tmp.wav"
    with out_file.open("a", encoding="utf-8") as f:
        for count, i in enumerate(order, 1):
            row = table.slice(i, 1).to_pylist()[0]
            wav = row["audio"]["bytes"]
            audio = decode_audio(io.BytesIO(wav), sampling_rate=16000)

            # pronunciation: align the teachers' expected sounds to the whole sentence
            phones, human, word_of = [], [], []
            for wi, w in enumerate(row["words"]):
                ipa, idx = to_ipa_with_index(w["phones"])
                phones += ipa
                human += [min(w["phones-accuracy"][j] for j in ix) for ix in idx]
                word_of += [wi] * len(ipa)
            lp = pronunciation.hear_phonemes(audio).numpy()
            sounds = pronunciation.score_sounds(lp, phones) or []

            # fluency: our full pipeline (Whisper + pause detection) on the file
            tmp.write_bytes(wav)
            try:
                stats = fluency.fluency_stats(str(tmp))
                fl = {k: v for k, v in stats.items() if not isinstance(v, list)}
                fl.update({k: len(stats[k]) for k in ("fillers", "repetitions", "self_corrections", "lengthened")})
                fl["score"] = fluency.fluency_score(stats)[0]
            except Exception as e:                       # e.g. Whisper heard no words
                fl = {"error": str(e)}

            rec = {
                "id": i, "age": row["age"], "text": row["text"],
                "h_accuracy": row["accuracy"], "h_fluency": row["fluency"], "h_total": row["total"],
                "phones": phones, "h_phone": human, "word_of": word_of,
                "h_word": [w["accuracy"] for w in row["words"]],
                "gop": [s["gop"] for s in sounds], "heard": [s["heard"] for s in sounds],
                "ok": [s["ok"] for s in sounds], "fluency": fl,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if count % 25 == 0:
                print(f"  {count}/{len(order)}", flush=True)


def english_phone_ids():
    """Model ids of every sound our English pronunciations can use (incl. accepted variants)."""
    from coach import pronunciation as pr
    names = set(pr.VOWELS.values()) | set(pr.UNSTRESSED.values()) | set(pr.CONSONANTS.values()) | set(pr.R_JOIN.values())
    for group in pr.SAME.values():
        names |= set(group.split())
    return sorted(pr._phone2id[n] for n in names if n in pr._phone2id)


def features(split, n):
    """Rich per-sound features for training a scoring model (step 4d+, GOPT-style):
    for every expected sound: GOP, length in frames, and the average log-probability of EVERY English
    sound over its frames (what the model thought it heard). No Whisper here (faster)."""
    import pyarrow.parquet as pq
    from faster_whisper.audio import decode_audio
    from coach import pronunciation

    ids = english_phone_ids()
    out_file = LOGS / f"so762feat_{split}.jsonl"
    done = set()
    if out_file.exists():
        done = {json.loads(l)["id"] for l in out_file.read_text(encoding="utf-8").splitlines() if l.strip()}
    table = pq.read_table(next(DATA.glob(f"{split}-*.parquet")))
    order = [i for i in range(min(n, table.num_rows)) if i not in done]
    print(f"{split}: {len(done)} already done, {len(order)} to go, {len(ids)} English sounds", flush=True)

    with out_file.open("a", encoding="utf-8") as f:
        for count, i in enumerate(order, 1):
            row = table.slice(i, 1).to_pylist()[0]
            audio = decode_audio(io.BytesIO(row["audio"]["bytes"]), sampling_rate=16000)
            phones, human, word_of = [], [], []
            for wi, w in enumerate(row["words"]):
                ipa, idx = to_ipa_with_index(w["phones"])
                phones += ipa
                human += [min(w["phones-accuracy"][j] for j in ix) for ix in idx]
                word_of += [wi] * len(ipa)
            lp = pronunciation.hear_phonemes(audio).numpy()
            frames = pronunciation.force_align(lp, phones)
            if frames is None:
                continue
            sounds = pronunciation.score_sounds(lp, phones)
            feats, dur = [], []
            for f0, f1 in frames:
                feats.append(np.round(lp[f0:f1 + 1][:, ids].mean(0), 2).tolist())
                dur.append(f1 - f0 + 1)
            first, last = frames[0][0], frames[-1][1]
            rec = {
                "id": i, "age": row["age"], "speaker": row["speaker"],
                "h_accuracy": row["accuracy"], "h_fluency": row["fluency"], "h_prosodic": row["prosodic"],
                "h_total": row["total"], "h_completeness": row["completeness"],
                "phones": phones, "h_phone": human, "word_of": word_of,
                "h_word": [w["accuracy"] for w in row["words"]], "h_word_total": [w["total"] for w in row["words"]],
                "gop": [s["gop"] for s in sounds], "dur": dur, "feat": feats,
                "audio_s": round(len(audio) / 16000, 2), "speech_frames": last - first + 1,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if count % 100 == 0:
                print(f"  {count}/{len(order)}", flush=True)


# ---------------------------------------------------------------- part 2: compare with teachers

def load(split):
    path = LOGS / f"so762_{split}.jsonl"
    recs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [r for r in recs if r["gop"]]                 # skip the few the aligner could not handle


def pcc(a, b):
    return float(np.corrcoef(a, b)[0, 1])


def sentence_features(r, threshold):
    g = np.clip(np.array(r["gop"]), -10, 0)
    right = np.mean([(gg > threshold) or (h == p) for gg, h, p in zip(r["gop"], r["heard"], r["phones"])])
    return [right, g.mean(), np.sort(g)[:max(1, len(g) // 5)].mean()]   # share right, mean GOP, worst 20%


def fit(X, y):
    X = np.column_stack([X, np.ones(len(X))])
    w, *_ = np.linalg.lstsq(X, y, rcond=None)
    return w


def predict(w, X):
    return np.column_stack([X, np.ones(len(X))]) @ w


def detection(recs, threshold):
    """Sound level: does our 'wrong' agree with the teachers' 'wrong'?"""
    tp = fp = fn = 0
    for r in recs:
        for gop, heard, p, h in zip(r["gop"], r["heard"], r["phones"], r["h_phone"]):
            ours = gop <= threshold and heard != p
            theirs = h <= WRONG_HUMAN
            tp += ours and theirs; fp += ours and not theirs; fn += theirs and not ours
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    return prec, rec, f1


FLUENCY_KEYS = ["syllables_per_sec", "pause_percent", "mlr", "avg_pause", "long_pauses",
                "mid_phrase_pauses", "fillers", "repetitions", "self_corrections", "lengthened"]


def report():
    from coach.pronunciation import WRONG_GOP, pronunciation_score
    train, test = load("train"), load("test")
    print(f"sentences: train {len(train)}, test {len(test)}  (teacher scores 0-10)\n")

    # --- sound level
    all_g = [g for r in test for g in r["gop"]]
    all_h = [h for r in test for h in r["h_phone"]]
    print("=== SOUNDS ===")
    print(f"PCC(our GOP, teachers' sound score) on test: {pcc(all_g, all_h):.3f}   (published GOP baselines ~0.45-0.6)")
    best_t = max(np.arange(-6, -0.4, 0.25), key=lambda t: detection(train, t)[2])
    for name, t in (("current", WRONG_GOP), ("tuned on train", best_t)):
        p, r, f1 = detection(test, t)
        print(f"  wrong-sound detection, threshold {t:5.2f} ({name}): precision {p:.2f} recall {r:.2f} F1 {f1:.2f}")

    # --- sentence pronunciation
    print("\n=== PRONUNCIATION (sentence) vs teachers' accuracy ===")
    cur = [pronunciation_score([{"sounds": [{"ok": o} for o in r["ok"]]}])[0] for r in test]
    print(f"  current formula (share right, 60%->0, 97%->100): PCC {pcc(cur, [r['h_accuracy'] for r in test]):.3f}")
    Xtr = np.array([sentence_features(r, best_t) for r in train]); ytr = np.array([r["h_accuracy"] for r in train])
    Xte = np.array([sentence_features(r, best_t) for r in test]); yte = np.array([r["h_accuracy"] for r in test])
    w = fit(Xtr, ytr)
    pred = np.clip(predict(w, Xte), 0, 10)
    print(f"  tuned (share right + mean GOP + worst 20%):      PCC {pcc(pred, yte):.3f}   mean error {np.mean(np.abs(pred - yte)):.2f} of 10")
    print(f"    weights {np.round(w, 3).tolist()}  (published speechocean762 GOP baselines: PCC ~0.6-0.7, best deep models ~0.8)")

    # --- fluency
    print("\n=== FLUENCY vs teachers' fluency ===")
    ftr = [r for r in train if "error" not in r["fluency"]]
    fte = [r for r in test if "error" not in r["fluency"]]
    print(f"  current formula: PCC {pcc([r['fluency']['score'] for r in fte], [r['h_fluency'] for r in fte]):.3f}")
    for k in FLUENCY_KEYS:
        print(f"    {k:18} PCC {pcc([r['fluency'][k] for r in fte], [r['h_fluency'] for r in fte]):+.3f}")
    Xtr = np.array([[r["fluency"][k] for k in FLUENCY_KEYS] for r in ftr])
    Xte = np.array([[r["fluency"][k] for k in FLUENCY_KEYS] for r in fte])
    wf = fit(Xtr, np.array([r["h_fluency"] for r in ftr]))
    print(f"  tuned (linear on all numbers): PCC {pcc(predict(wf, Xte), [r['h_fluency'] for r in fte]):.3f}")

    # --- adults vs children
    print("\n=== by age (tuned pronunciation) ===")
    for name, keep in (("children (<15)", lambda r: r["age"] < 15), ("adults", lambda r: r["age"] >= 15)):
        sub = [r for r in test if keep(r)]
        Xs = np.array([sentence_features(r, best_t) for r in sub])
        print(f"  {name:15} n={len(sub):4}  PCC {pcc(np.clip(predict(w, Xs), 0, 10), [r['h_accuracy'] for r in sub]):.3f}")

    json.dump({"wrong_gop": float(best_t), "pron_weights": w.tolist(), "fluency_keys": FLUENCY_KEYS,
               "fluency_weights": wf.tolist()}, open(LOGS / "so762_tuned.json", "w"), indent=1)
    print(f"\nsaved tuned numbers -> logs/so762_tuned.json")


if __name__ == "__main__":
    if sys.argv[1] == "extract":
        extract(sys.argv[2], int(sys.argv[3]))
    elif sys.argv[1] == "features":
        features(sys.argv[2], int(sys.argv[3]))
    else:
        report()
