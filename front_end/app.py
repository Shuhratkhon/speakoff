"""Temporary minimal front end (until the real app). Runs in PyCharm's Run window or any terminal:
it asks for a sample's name and the sections to rate, prints the report and spoken-style feedback
(read aloud on request), then asks again.

Run (from the Speaking_Coach folder):
  python front_end/app.py
In PyCharm: open this file and press Run.

Sample name: "mumtozkhon_1" (looked up in samples/ and data/test_videos/), or a full path to any audio/video.
The first analysis of a file is slow (models load, ~1-3 min); after that it comes from logs/rate_cache/.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FOLDERS = [ROOT / "samples", ROOT / "data" / "test_videos"]
MEDIA = {".ogg", ".wav", ".mp3", ".m4a", ".flac", ".mp4", ".webm", ".mov", ".mkv"}
SECTIONS = ["fluency", "grammar", "vocabulary", "pronunciation"]


def known_samples():
    return sorted(p.stem for f in FOLDERS if f.exists() for p in f.iterdir() if p.suffix.lower() in MEDIA)


def find_file(name):
    p = Path(name.strip().strip('"'))
    if p.is_file():
        return p
    for folder in FOLDERS:
        for f in sorted(folder.glob(p.stem + ".*")) if folder.exists() else []:
            if f.suffix.lower() in MEDIA:
                return f
    return None


def ask_sections():
    """'1 3' or 'grammar fluency' or Enter for all. Overall is always included."""
    for i, s in enumerate(SECTIONS, 1):
        print(f"  {i}) {s}")
    while True:
        raw = input("Sections (numbers or names, Enter = all): ").replace(",", " ").lower().split()
        if not raw:
            return SECTIONS
        chosen, bad = [], []
        for x in raw:
            s = SECTIONS[int(x) - 1] if x.isdigit() and 1 <= int(x) <= len(SECTIONS) else x
            (chosen if s in SECTIONS else bad).append(s)
        if not bad:
            return [s for s in SECTIONS if s in chosen]
        print(f"  unknown: {', '.join(bad)}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")       # IPA symbols (/ð/) in the report
    print("Speaking Coach\nSamples:", ", ".join(known_samples()))
    while True:
        name = input("\nSample name (Enter = quit): ").strip().lstrip("﻿")
        if not name:
            break
        path = find_file(name)
        if not path:
            print(f"  no sample called '{name}' in samples/ or data/test_videos/")
            continue
        chosen = ask_sections()
        print(f"Analysing {path.name} ... (first time for a file: 1-3 minutes)")
        try:
            from coach import feedback, rate
            d = rate.analyse(path)
            result = rate.report(path, d, chosen)
            text = feedback.feedback_text(d, result, chosen)
            print("\nFEEDBACK\n" + text)
            if input("\nHear it read aloud? (y/N): ").strip().lower().startswith("y"):
                mp3 = feedback.speak(text, path.stem)             # needs internet (free edge-tts voice)
                print(f"  saved {mp3}")
                os.startfile(mp3)                                   # opens in the default player
        except Exception as e:                      # show the problem and keep going
            print(f"  failed: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
