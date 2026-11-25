"""Korean anti-cheat calibration (2026-11-26): perplexity of learner transcripts vs AI-written answers vs native
read text, and speed / fillers of learners vs natives reading (a stand-in for reading a prepared script)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from coach import anticheat  # noqa: E402

SAMPLES = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))     # ko_samples.json from the baseline run
# polished answers in the style an AI chatbot writes (what a cheater would read out)
AI = [
    "저는 여가 시간에 주로 독서를 즐기는 편입니다. 책을 읽으면 새로운 지식을 얻을 수 있을 뿐만 아니라 스트레스도 해소할 수 있기 때문입니다. 특히 소설을 읽으며 다양한 인물의 삶을 간접적으로 경험하는 것을 좋아합니다. 앞으로도 꾸준히 독서하는 습관을 유지하고 싶습니다.",
    "제 고향은 우즈베키스탄의 사마르칸트입니다. 사마르칸트는 실크로드의 중심지로 오랜 역사와 아름다운 건축물로 유명합니다. 특히 레기스탄 광장은 많은 관광객들이 찾는 대표적인 명소입니다. 또한 사람들이 친절하고 음식이 맛있어서 꼭 한번 방문해 보시기를 추천합니다.",
    "저는 SNS가 장점과 단점을 모두 가지고 있다고 생각합니다. 먼저 SNS를 통해 전 세계 사람들과 쉽게 소통하고 정보를 빠르게 얻을 수 있습니다. 하지만 지나친 사용은 시간 낭비와 개인정보 유출 같은 문제를 일으킬 수 있습니다. 따라서 SNS를 올바르게 사용하는 태도가 중요하다고 생각합니다.",
    "제가 가장 자랑스러웠던 경험은 한국어 능력시험에서 목표 등급을 취득한 것입니다. 처음에는 문법과 어휘가 어려워 포기하고 싶었지만, 매일 꾸준히 공부하며 노력했습니다. 그 결과 원하는 점수를 받을 수 있었고, 이 경험을 통해 노력의 중요성을 깨달았습니다.",
    "건강을 유지하기 위해 저는 규칙적인 운동과 균형 잡힌 식사를 중요하게 생각합니다. 일주일에 세 번 이상 헬스장에 가서 근력 운동과 유산소 운동을 병행하고 있습니다. 또한 충분한 수면을 취하고 스트레스를 관리하려고 노력하고 있습니다.",
]
rows = [("learner", n, v["text"]) for n, v in SAMPLES.items() if not n.startswith("native")]
rows += [("native-read", n, v["text"]) for n, v in SAMPLES.items() if n.startswith("native")]
rows += [("ai", f"ai_{i}", t) for i, t in enumerate(AI, 1)]
for kind, n, text in rows:
    print(f"{kind:12} {n:13} ppl {anticheat.perplexity(text):6.1f}", flush=True)
print("\nspeed / fillers per minute (reading a script = smooth and fast):")
for n, v in SAMPLES.items():
    f, dur = v["fluency"], max(v["seconds"], 1)
    fpm = 60 * ((f.get("fillers") or 0) + (f.get("repairs") or 0)) / dur
    print(f"  {n:13} syll/s {f['syllables_per_sec']:.2f} | fillers+repairs per min {fpm:.1f}")
