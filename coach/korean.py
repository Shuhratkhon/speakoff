"""Korean as a learning language (started 2026-11-26). Built in phases, and only the parts that are really built
count in the score:
  phase 1  transcript (multilingual Whisper "small") + fluency (Hangul syllables, Korean fillers)   done
  phase 2  grammar (coach/korean_grammar.py) + vocabulary and range (coach/korean_lex.py)              done
  phase 3  Korean questions, TOPIK mock test, Korean Ranked
  phase 4  pronunciation, off-topic / anti-cheat for Korean, tuned on real Korean learner recordings
Level: TOPIK speaking level 1-6 (TOPIK 말하기 평가) and CEFR, instead of IELTS / TOEFL.
"""

from pathlib import Path

AVAILABLE = ["fluency", "grammar", "vocabulary"]     # sections that work for Korean so far (see the phases above)
SECTIONS = ["fluency", "grammar", "vocabulary", "pronunciation"]
TOPIK_CEFR = {1: "A1", 2: "A2", 3: "B1", 4: "B2", 5: "C1", 6: "C2"}


def analyse(path, video=None, max_seconds=None):
    from coach import fluency
    from coach.transcribe import transcribe
    words = transcribe(path, lang="ko")
    fluency.transcribe = lambda _p: words
    stats = fluency.fluency_stats(path)
    f_score, f_parts = fluency.fluency_score(stats, lang="ko")
    kept = [w for w in words if fluency.clean(w["word"]) not in fluency.FILLERS]
    data = {
        "lang": "ko", "mtime": Path(path).stat().st_mtime, "duration": stats["duration"], "n_words": len(words),
        "text": " ".join(w["word"] for w in kept),
        "fluency": {"score": f_score, "formula": f_score, "model": None, "parts": f_parts,
                    **{k: stats[k] for k in ("syllables_per_sec", "pause_percent", "mlr")},
                    "fillers": len(stats["fillers"]), "repairs": len(stats["repetitions"]) + len(stats["self_corrections"])},
        "grammar_results": [], "pronunciation": None, "delivery": None,
    }
    from coach import korean_grammar
    data["grammar_results"] = korean_grammar.check_text(data["text"])
    if video:
        from coach import delivery
        data["delivery"] = delivery.analyse_video(video, words, max_seconds)
    return data


def topik_level(score):
    """Overall /100 -> TOPIK speaking level 1-6 (0 = below level 1). PROVISIONAL until tuned on real recordings."""
    for cut, lvl in ((90, 6), (78, 5), (65, 4), (52, 3), (38, 2), (25, 1)):
        if score >= cut:
            return lvl
    return 0


def vocab_score(v):
    """0-100 from the share of intermediate+ words (spoken Korean uses mostly beginner words) and variety.
    PROVISIONAL until tuned on real learner recordings."""
    from coach.level import interp
    soph = interp(v["b1_plus"], [5, 12, 20, 28, 36, 45], [20, 40, 55, 70, 85, 100])
    var = interp(v["variety"], [0.5, 0.6, 0.67, 0.74, 0.8], [20, 45, 65, 85, 100])
    return round(0.6 * soph + 0.4 * var)


def scores(d):
    """Grammar and vocabulary for Korean, in the same shape as the English ones (grammar.grammar_score etc.)."""
    from coach import grammar, korean_lex, level
    acc, per100, clean = grammar.grammar_score(d["grammar_results"], d["n_words"])
    rng = korean_lex.grammar_range(d["text"])
    g_total, range_score = level.grammar_total(acc, rng)
    v = korean_lex.vocabulary_stats(d["text"])
    return {"grammar": g_total, "accuracy": acc, "per100": per100, "clean": clean, "range": range_score, "rng": rng,
            "vocabulary": vocab_score(v), "vocab": v}


def report(d, chosen=None):
    chosen = [s for s in (chosen or SECTIONS) if s in AVAILABLE] or ["fluency"]
    x = scores(d)
    sec = {"fluency": d["fluency"]["score"], "grammar": x["grammar"], "vocabulary": x["vocabulary"], "pronunciation": None}
    vals = [sec[s] for s in chosen if sec[s] is not None]
    overall = round(sum(vals) / len(vals)) if vals else 0
    lvl = topik_level(overall)
    return {"overall": overall, "sections": sec, "on_camera": None,
            "level": {"exam": "topik", "topik": lvl, "cefr": TOPIK_CEFR.get(lvl, "below A1"), "ielts": None,
                      "too_short": d["n_words"] < 60, "available": AVAILABLE, "coming": [s for s in SECTIONS if s not in AVAILABLE],
                      "vocabulary": x["vocab"], "grammar_range": x["rng"], "ko": x}}
