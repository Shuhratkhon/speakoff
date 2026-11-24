"""App languages: one file per language in i18n/<code>.json, used by the website (keys without "fb_" / "cat_" /
"cam_") and by the spoken feedback (keys starting with "fb_", "cat_", "cam_"). Missing keys fall back to English.

  t("uz", "fb_closing")                     -> the Uzbek sentence
  t("en", "fb_camera", score=88)            -> "On camera, you got 88 out of 100. ..."
  join("ko", ["a", "b", "c"])               -> list joined the way that language does it
"""

import json
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "i18n"

LANGS = {"en": "English", "ko": "한국어", "ru": "Русский", "de": "Deutsch", "id": "Bahasa Indonesia",
         "uz": "O‘zbekcha", "zh": "中文（简体）", "vi": "Tiếng Việt", "hi": "हिन्दी", "ja": "日本語"}

# free Microsoft voices (edge-tts), one female and one male per language
VOICES = {
    "en": {"female": "en-US-AvaMultilingualNeural", "male": "en-US-AndrewMultilingualNeural"},
    "ko": {"female": "ko-KR-SunHiNeural", "male": "ko-KR-InJoonNeural"},
    "ru": {"female": "ru-RU-SvetlanaNeural", "male": "ru-RU-DmitryNeural"},
    "de": {"female": "de-DE-TanjaNeural", "male": "de-DE-ChristophNeural"},
    "id": {"female": "id-ID-GadisNeural", "male": "id-ID-ArdiNeural"},
    "uz": {"female": "uz-UZ-MadinaNeural", "male": "uz-UZ-SardorNeural"},
    "zh": {"female": "zh-CN-XiaoxiaoNeural", "male": "zh-CN-YunxiNeural"},
    "vi": {"female": "vi-VN-HoaiMyNeural", "male": "vi-VN-NamMinhNeural"},
    "hi": {"female": "hi-IN-SwaraNeural", "male": "hi-IN-MadhurNeural"},
    "ja": {"female": "ja-JP-NanamiNeural", "male": "ja-JP-KeitaNeural"},
}


@lru_cache(None)
def _load(lang, mtime):
    return json.loads((DIR / f"{lang}.json").read_text(encoding="utf-8"))


def table(lang):
    """The language file, re-read automatically when it changes (no server restart needed)."""
    path = DIR / f"{lang}.json"
    return _load(lang, path.stat().st_mtime) if path.exists() else {}


def t(lang, key, **kw):
    text = table(lang).get(key) or table("en").get(key) or key
    return text.format(**kw) if kw else text


def join(lang, items):
    """['a', 'b', 'c'] -> 'a, b and c' (separators come from the language file)."""
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return t(lang, "list_sep").join(items[:-1]) + t(lang, "list_last") + items[-1]


def ui(lang):
    """Only the website's texts (sent to the browser)."""
    merged = {**table("en"), **table(lang)}
    return {k: v for k, v in merged.items() if not k.startswith(("fb_", "cat_", "cam_"))}
