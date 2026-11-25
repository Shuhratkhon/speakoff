"""Korean mock speaking test, in the spirit of the TOPIK speaking test (TOPIK 말하기 평가), built from the 1000-question
Korean bank (server/question_bank_ko.py), 2026-11-26. Same 3-part engine as the IELTS mock (server/mock.py):
  Part 1  질문에 대답하기: 4 everyday questions
  Part 2  a "describe / tell about" task with points to cover: 1 minute to prepare, 1-2 minutes to speak
  Part 3  의견 제시하기: 4 opinion questions
Every topic gives two different sets -> 100 sets, so a Pro player (1 test a day) has no repeat for over 3 months.
"""

from server.question_bank_ko import TOPICS

POINTS_STORY = ["언제, 어디에서였는지", "누구와 함께였는지", "무엇을 했는지", "그리고 왜 기억에 남는지 말하세요"]
POINTS_INTRO = ["무엇(누구)인지", "어떻게 알게 되었는지", "어떤 특징이 있는지", "그리고 왜 좋아하는지(중요한지) 말하세요"]


def _kind(q):
    if q.endswith(("까요?", "생각해요?")) or "어떻게 생각" in q:
        return "opinion"
    if q.endswith(("이야기해 주세요.", "소개해 주세요.")):
        return "task"
    return "simple"


def _sets():
    """Two sets per topic, 9 different questions each, no question shared between a topic's two sets."""
    out = []
    for i, (topic, qs) in enumerate(TOPICS.items()):
        used = set()

        def take(cands, n):
            got = [q for q in cands if q not in used][:n]
            used.update(got)
            return got

        for half in (0, 1):
            by = {k: [q for q in qs if _kind(q) == k] for k in ("task", "opinion", "simple")}
            card = (take(by["task"], 1) or take(by["simple"], 1) or take(qs, 1))[0]
            p3 = take(by["opinion"], 4)
            p3 += take(by["simple"] + by["task"], 4 - len(p3))
            p1 = take(by["simple"], 4)
            p1 += take(qs, 4 - len(p1))
            points = POINTS_STORY if card.endswith("이야기해 주세요.") else POINTS_INTRO
            out.append({"id": f"ko_{i}_{half}", "lang": "ko", "p1_topic": topic, "p1": p1,
                        "p2": {"title": card, "points": points}, "p3": p3})
    return out


SETS = _sets()
