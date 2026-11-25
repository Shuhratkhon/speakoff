"""Measure the Korean off-topic signals on evaluate/ko_topic_testset.py (multilingual-e5-small, MIT)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from coach import topic_ko  # noqa: E402
from evaluate.ko_topic_testset import ITEMS  # noqa: E402

rows = []
for q, a, label in ITEMS:
    f = topic_ko.features(q, a)
    v = topic_ko.check(q, a)
    rows.append((label, f, v["verdict"] if v else None, q, a))
for label in ("ok", "off"):
    xs = [r[1] for r in rows if r[0] == label]
    print(label, "sim  min/max", round(min(x["sim"] for x in xs), 3), round(max(x["sim"] for x in xs), 3),
          "| rank  min/max", min(x["rank"] for x in xs), max(x["rank"] for x in xs),
          "| better min/max", round(min(x["better"] for x in xs), 3), round(max(x["better"] for x in xs), 3))
right = sum(r[2] == r[0] for r in rows)
fp = [r for r in rows if r[0] == "ok" and r[2] == "off"]
fn = [r for r in rows if r[0] == "off" and r[2] != "off"]
print(f"right {right}/{len(rows)} | good answers called off: {len(fp)} | off answers missed: {len(fn)}")
for r in fp + fn:
    print("  WRONG", r[0], "->", r[2], {k: round(v, 3) if isinstance(v, float) else v for k, v in r[1].items()}, r[3][:20], "|", r[4][:30])
