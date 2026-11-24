"""Step 6: the final feedback, as a short talk a teacher would give, and read aloud by a free AI voice.
All sentences come from i18n/<lang>.json ("fb_..." keys), so the feedback follows the app language;
the speaker's own English words and the example corrections stay in English.

Which sections get what (chosen sections, sorted by score):
  - all below 80     -> praise the best one, tips for the others (at least 3 when there are 4)
  - otherwise        -> praise the best two, tips for the two lowest
Video: the On camera score (/100, not in overall or level) and its tips come last.

feedback_text(d, result, chosen, lang)  -> plain text (no symbols, so it can be spoken)
speak(text, out_path, voice)            -> mp3 made with edge-tts (Microsoft's free online voices, no key needed)

Run (from the Speaking_Coach folder):
  python -m coach.feedback samples/mumtozkhon_1.ogg [--lang uz] [--male]   # prints it, saves logs/feedback/<name>.mp3
"""

import asyncio
import re
from collections import Counter
from pathlib import Path

from coach.i18n import VOICES, join, t

VOICE = VOICES["en"]["female"]
OUT = Path(__file__).resolve().parent.parent / "logs" / "feedback"


def category_name(lang, english_name):
    """ERRANT category (English, from grammar.TYPE_NAMES) -> name in the app language, without the (a, the, this)."""
    key = "cat_" + re.sub(r"\W+", "_", english_name.split(" (")[0].replace("/", " ")).strip("_").lower()
    name = t(lang, key) if key != t(lang, key) else english_name
    return re.split(r" ?[（(]", name)[0]                      # brackets: "(a, the)" and the full-width "（a、the）"


def _fix_phrase(lang, m):
    """One grammar mistake as a short spoken tip; the English words stay English."""
    wrong, right = m["wrong"].strip(), m["right"].strip()
    if not wrong:
        return t(lang, "fb_fix_add", right=right)
    if not right:
        return t(lang, "fb_fix_remove", wrong=wrong)
    return t(lang, "fb_fix_replace", right=right, wrong=wrong)


def good_words(v, n=4):
    """B2+ words first, then B1 words, so there are at least 2 when the speaker used any."""
    return list(dict.fromkeys(v["advanced_words"] + v.get("b1_words", [])))[:n]


# ------------------------------------------------------------------ praise (the best sections)

def fluency_good(lang, f):
    bits = [t(lang, "fb_flu_pace" if f["syllables_per_sec"] >= 2.8 else "fb_flu_going")]
    if f["pause_percent"] < 20:
        bits.append(t(lang, "fb_flu_short_pauses"))
    if f["fillers"] <= 2:
        bits.append(t(lang, "fb_flu_few_fillers"))
    return t(lang, "fb_flu_good", bits=join(lang, bits))


def grammar_good(lang, clean, complex_percent):
    return t(lang, "fb_gram_good_complex" if complex_percent >= 25 else "fb_gram_good", pct=round(clean * 100))


def vocabulary_good(lang, v):
    words = good_words(v)
    if len(words) >= 2:
        return t(lang, "fb_voc_good", words=join(lang, words))
    return t(lang, "fb_voc_good_none")


def pronunciation_good(lang, p):
    return t(lang, "fb_pron_good", pct=round(p["right"] * 100))


# ------------------------------------------------------------------ tips (the weaker sections)

def fluency_tips(lang, f, minutes):
    tips = []
    if f["fillers"] / minutes >= 4:
        tips.append(t(lang, "fb_flu_fillers", n=f["fillers"]))
    if f["pause_percent"] >= 20:
        tips.append(t(lang, "fb_flu_pauses", pct=round(f["pause_percent"])))
    if f["syllables_per_sec"] < 2.8:
        tips.append(t(lang, "fb_flu_slow"))
    if f["repairs"] >= 4:
        tips.append(t(lang, "fb_flu_repairs", n=f["repairs"]))
    if not tips:
        tips.append(t(lang, "fb_flu_link"))
    return t(lang, "fb_flu_tips", tips=t(lang, "fb_also").join(tips))


def grammar_tips(lang, results, complex_percent, limit=3):
    mistakes = [m for r in results for m in r["mistakes"]]
    out = []
    if mistakes:
        top, n = Counter(m["category"] for m in mistakes).most_common(1)[0]
        if n >= 2:
            out.append(t(lang, "fb_gram_top", category=category_name(lang, top), n=n))
    else:
        out.append(t(lang, "fb_gram_none"))
    examples = list(dict.fromkeys(_fix_phrase(lang, m) for m in mistakes))[:limit]   # in the order spoken
    if len(examples) < 2 or complex_percent < 25:             # always at least 2 examples; range when it is low
        examples.append(t(lang, "fb_range_example"))
    if len(examples) < 2:
        examples.append(t(lang, "fb_basic_example"))
    out.append(t(lang, "fb_gram_improve" if out else "fb_gram_improve_first", examples=join(lang, examples)))
    return " ".join(out)


def vocabulary_tips(lang, v):
    words = good_words(v)
    if len(words) >= 2:
        return t(lang, "fb_voc_tips_words", words=join(lang, words)) + " " + t(lang, "fb_voc_tips_more_first")
    return t(lang, "fb_voc_tips_start") + " " + t(lang, "fb_voc_tips_more")


def pronunciation_tips(lang, p, cam=None, limit=2):
    from coach.delivery import mouth_tip
    mouth = mouth_tip(cam, lang) if cam else None
    tips = [mouth[0].lower() + mouth[1:].rstrip(".") if lang == "en" else mouth.rstrip(".。")] if mouth else []
    used, n_sounds = set(), 0
    for _e, _h, ws in p["mistakes"]:
        words = [w for w in dict.fromkeys(w.lower() for w in ws) if w not in used][:3]
        if words and n_sounds < limit:
            used.update(words)
            n_sounds += 1
            tips.append(t(lang, "fb_pron_sound", words=join(lang, words)))
    if not tips:
        tips.append(t(lang, "fb_pron_rhythm"))
    return t(lang, "fb_pron_tips", tips=join(lang, tips))


# ------------------------------------------------------------------ the whole talk

def pick(scored):
    """-> (praise, improve) lists of section names, following the rule at the top of this file."""
    order = sorted(scored, key=scored.get)                     # lowest first
    if len(order) == 1:
        return ([], order) if scored[order[0]] < 80 else (order, [])
    if all(v < 80 for v in scored.values()):
        return [order[-1]], order[:-1][:3]
    k = max(1, len(order) - 2)
    return order[-k:][::-1], order[:-k][:2]


def level_text(lang, cefr):
    """'B2 (borderline B1)' -> 'B2, close to B1' in the app language."""
    m = re.match(r"(.+?) \(borderline (.+)\)", cefr)
    fix = lambda x: t(lang, "fb_below_a1") if x == "below A1" else x
    return t(lang, "fb_close_to", a=fix(m.group(1)), b=fix(m.group(2))) if m else fix(cefr)


def feedback_text(d, result, chosen, lang="en"):
    """d = rate.analyse(...), result = rate.report(...), chosen = sections the speaker picked."""
    from coach import grammar

    sec, lv = result["sections"], result["level"]
    minutes = max(d["duration"] / 60, 0.5)
    _acc, _per100, clean = grammar.grammar_score(d["grammar_results"], d["n_words"])
    complex_percent = lv["grammar_range"]["complex_percent"]
    cam = (d.get("delivery") or {}).get("stats")

    parts = [t(lang, "fb_intro", overall=result["overall"], level=level_text(lang, lv["cefr"]), ielts=lv["ielts"])]
    if lv["originality"] < 0.85:
        parts.append(t(lang, "fb_repetition"))

    good = {"fluency": lambda: fluency_good(lang, d["fluency"]),
            "grammar": lambda: grammar_good(lang, clean, complex_percent),
            "vocabulary": lambda: vocabulary_good(lang, lv["vocabulary"]),
            "pronunciation": lambda: pronunciation_good(lang, d["pronunciation"])}
    tips = {"fluency": lambda: fluency_tips(lang, d["fluency"], minutes),
            "grammar": lambda: grammar_tips(lang, d["grammar_results"], complex_percent),
            "vocabulary": lambda: vocabulary_tips(lang, lv["vocabulary"]),
            "pronunciation": lambda: pronunciation_tips(lang, d["pronunciation"], cam)}

    scored = {k: sec[k] for k in chosen}
    praise, improve = pick(scored)

    def names(keys):
        return join(lang, [t(lang, "fb_with_score", section=t(lang, f"fb_sec_{k}"), score=scored[k]) for k in keys])

    if praise:
        parts.append(t(lang, "fb_went_well_one" if len(praise) == 1 else "fb_went_well_many", names=names(praise))
                     + " " + " ".join(good[k]() for k in praise))
    if improve:
        parts.append(t(lang, "fb_work_on", names=names(improve)) + " " + " ".join(tips[k]() for k in improve))

    if cam:
        from coach.delivery import camera_score, camera_tips
        parts.append(t(lang, "fb_camera", score=camera_score(cam)) + " " + " ".join(camera_tips(cam, lang)[:2]))
    parts.append(t(lang, "fb_closing"))
    return "\n".join(parts)


async def _save(text, out, voice):
    await __import__("edge_tts").Communicate(text, voice, rate="+0%").save(str(out))


def speak(text, out, voice=VOICE):
    """Save the text as speech to `out` (an .mp3 path, or a bare name -> logs/feedback/<name>.mp3).
    Needs internet (Microsoft's free voices). Returns the path."""
    out = Path(out) if str(out).endswith(".mp3") else OUT / f"{out}.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_save(text.replace("\n", " "), out, voice))
    return out


if __name__ == "__main__":
    import contextlib
    import io
    import sys

    from coach import rate
    from coach.level import SECTIONS

    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    lang = args[args.index("--lang") + 1] if "--lang" in args else "en"
    voice = VOICES.get(lang, VOICES["en"])["male" if "--male" in args else "female"]
    for path in [a for a in args if not a.startswith("--") and a != lang]:
        d = rate.analyse(path)
        with contextlib.redirect_stdout(io.StringIO()):        # only the feedback, not the full report
            result = rate.report(path, d, SECTIONS)
        text = feedback_text(d, result, SECTIONS, lang)
        print(f"\n===== {Path(path).name}\n{text}")
        print("saved", speak(text, f"{Path(path).stem}_{lang}", voice))
