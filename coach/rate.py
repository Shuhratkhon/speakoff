"""Rate recordings: fluency, grammar, pronunciation (out of 100), overall, plus the speaker's level
(IELTS Speaking band, CEFR A1-C2, TOEFL Speaking).
Video files (.mp4, .webm, .mov, ...) also get an "On camera" score /100 with tips (eye contact, expression, head)
and a mouth-opening hint under pronunciation. The On camera score is NOT in the overall score or the level, so
these are the same for audio and video (exams judge only sound).

Run (from the Speaking_Coach folder):
  python -m coach.rate samples/mumtozkhon_1.ogg samples/mumtozkhon_2.ogg
  python -m coach.rate (Get-ChildItem samples\\*.ogg).FullName        # PowerShell: every sample
The slow model results are cached in logs/rate_cache/ (re-run with --fresh to redo them).
"""

import json
import sys
from pathlib import Path

CACHE = Path(__file__).resolve().parent.parent / "logs" / "rate_cache"


def is_video(path):
    import av
    try:
        with av.open(str(path)) as c:
            return any(s.type == "video" and s.frames != 1 and (s.average_rate or 0) > 1 for s in c.streams)
    except Exception:
        return False


def analyse(path, fresh=False, video=None, cache=True, max_seconds=None):
    """Run all models on one file (slow) and keep only what the scores need (cached in logs/rate_cache).
    video       = a separate video file for the face part (the web app analyses a converted audio file;
                  default: `path` itself when it is a video)
    cache       = False: do not read or write logs/rate_cache (the web app keeps results in its database)
    max_seconds = only the first N seconds of the video are used for the face (the audio is already cut)."""
    p = Path(path)
    cache_file = CACHE / (p.stem + ".json")
    if cache and cache_file.exists() and not fresh and             json.loads(cache_file.read_text(encoding="utf-8"))["mtime"] == p.stat().st_mtime:
        return json.loads(cache_file.read_text(encoding="utf-8"))

    from coach.transcribe import transcribe
    from coach import fluency, grammar, pronunciation
    words = transcribe(path)
    fluency.transcribe = lambda _p: words                    # fluency would transcribe again otherwise
    stats = fluency.fluency_stats(path)
    f_score, f_parts = fluency.fluency_score(stats)
    g_res = grammar.check_transcript(words)
    p_res = pronunciation.analyse(path, words)
    p_score, right = pronunciation.pronunciation_score(p_res)
    # fluency = 60% our pause/speed/filler formula + 40% the trained model (step 4d: teachers' fluency
    # PCC 0.49 formula alone, 0.78 model alone, 0.72 blend; the formula sees pauses, the model does not)
    m_flu = pronunciation.model_fluency(p_res)
    f_formula = f_score
    if m_flu is not None:
        f_score = round(0.6 * f_score + 0.4 * m_flu)
    kept = grammar.remove_disfluencies(words)
    data = {
        "mtime": p.stat().st_mtime, "duration": stats["duration"], "n_words": len(words),
        "text": " ".join(w["word"] for w in kept),
        "fluency": {"score": f_score, "formula": f_formula, "model": m_flu, "parts": f_parts, **{k: stats[k] for k in
                    ("syllables_per_sec", "pause_percent", "mlr")},
                    "fillers": len(stats["fillers"]), "repairs": len(stats["repetitions"]) + len(stats["self_corrections"])},
        "grammar_results": g_res,
        "delivery": None,
        "pronunciation": {"score": p_score, "right": right,
                          "mistakes": [[e, h, ws] for (e, h), ws in pronunciation.common_mistakes(p_res, 8)]},
    }
    video = video or (path if is_video(path) else None)
    if video:
        from coach import delivery
        data["delivery"] = delivery.analyse_video(video, words, max_seconds)
    if cache:
        CACHE.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def report(path, d, chosen=None):
    """chosen = sections the speaker picked (fluency, grammar, vocabulary, pronunciation; default all).
    A section not picked scores 0, as in an exam where a criterion is not assessed; the overall score
    and the IELTS / CEFR / TOEFL estimate include those zeros. Video adds a separate On camera score."""
    from coach import delivery, grammar, level
    chosen = chosen or level.SECTIONS
    acc, per100, clean = grammar.grammar_score(d["grammar_results"], d["n_words"])
    f, p = d["fluency"], d["pronunciation"]
    dv = d.get("delivery")
    lv = level.estimate_level(f["score"], p["score"], d["grammar_results"], d["n_words"], d["text"], chosen)
    v, r = lv["vocabulary"], lv["grammar_range"]
    g_score, range_score = level.grammar_total(acc, r)
    sec = {"fluency": f["score"], "grammar": g_score, "vocabulary": lv["vocabulary_score"],
           "pronunciation": p["score"]}
    score_cap, _ = level.repetition_cap(lv["originality"])
    sec = {k: (min(val, round(score_cap)) if k in chosen else 0) for k, val in sec.items()}
    overall = round(sum(sec.values()) / len(sec))
    cam = dv["stats"] if dv else None

    def head(name):
        return f"{name.upper():<13} " + (f"{sec[name]}/100" if name in chosen else "0/100   (not chosen)")

    print(f"\n===== {Path(path).name}  ({d['duration']} s, {d['n_words']} words)   sections: {', '.join(chosen)}")
    print(head("fluency") + ("" if "fluency" not in chosen else
          f"   {f['syllables_per_sec']} syll/s, pauses {f['pause_percent']}%, run {f['mlr']} words, "
          f"fillers {f['fillers']}, repairs {f['repairs']}"
          + (f"   (pauses/speed {f['formula']}, smoothness {f['model']})" if f.get("model") is not None else "")))
    print(head("grammar") + ("" if "grammar" not in chosen else
          f"   accuracy {acc} ({per100} mistakes per 100 words, {clean:.0%} sentences correct), "
          f"range {range_score} ({r['complex_percent']}% complex sentences)"))
    print(head("vocabulary") + ("" if "vocabulary" not in chosen else
          f"   {v['b1_plus']}% B1+ words, {v['b2_plus']}% B2+, variety {v['variety']}   "
          f"e.g. {', '.join(v['advanced_words'][:8])}"))
    print(head("pronunciation") + ("" if "pronunciation" not in chosen else f"   {p['right']:.0%} of sounds right"))
    if "pronunciation" in chosen:
        if cam and delivery.mouth_tip(cam):
            print(f"     {delivery.mouth_tip(cam)}")
        for e, h, ws in p["mistakes"][:4]:
            said = "unclear" if h == "?" else f"heard /{h}/"
            print(f"     practise /{e}/ ({said}) x{len(ws)}: {', '.join(list(dict.fromkeys(ws))[:5])}")
    if cam:
        print(f"ON CAMERA     {delivery.camera_score(cam)}/100   (not in overall or level)" + ("" if "error" in cam else
              f"   eye contact {cam['eye_contact']}%, smiling {cam['smile']}%, "
              f"head movement {cam['head_motion']} deg/2s, face visible {cam['face_visible']}%"))
        for tip in delivery.camera_tips(cam):
            print(f"     - {tip}")
    if score_cap < 100:
        print(f"REPETITION    only {lv['originality']:.0%} of the speech is new (natural speech: 94%+): "
              f"every score is capped at {round(score_cap)}/100. Answer with varied sentences.")
    print(f"OVERALL       {overall}/100   (average of {len(sec)} sections)")
    parts = ", ".join(f"{k} {b}" for k, b in lv["ielts_parts"].items())
    print(f"LEVEL         CEFR {lv['cefr']}  |  IELTS Speaking {lv['ielts']} ({parts})  |  "
          f"TOEFL Speaking {lv['toefl']}/6 (old scale {lv['toefl_old']}/30)   [estimate"
          + (", answer too short for a reliable level]" if lv["too_short"] else "]"))
    return {"overall": overall, "sections": sec, "level": lv,
            "on_camera": delivery.camera_score(cam) if cam else None}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")          # IPA symbols (/ð/) crash Windows' default console encoding
    argv = sys.argv[1:]
    chosen = None
    if "--sections" in argv:                     # e.g. --sections grammar,fluency
        i = argv.index("--sections")
        chosen = [x.strip().lower() for x in argv[i + 1].split(",") if x.strip()]
        del argv[i:i + 2]
        from coach.level import SECTIONS
        bad = [x for x in chosen if x not in SECTIONS]
        if bad:
            sys.exit(f"unknown section(s) {bad}; choose from {SECTIONS}")
    for path in [a for a in argv if not a.startswith("--")]:
        report(path, analyse(path, fresh="--fresh" in argv), chosen)
