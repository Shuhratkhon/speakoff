"""Mock IELTS Speaking test (added 2026-11-24): the 3 parts of the real test, recorded in the app.

  Part 1  4 short questions about the player's life     (each answer: 10-45 s, the player taps Next)
  Part 2  a cue card: 1 minute to prepare, then 1-2 minutes of speaking
  Part 3  4 discussion questions linked to the Part 2 topic   (each answer: 15-75 s)

The three parts are joined into one audio file and scored like a normal recording (all 4 sections), so the
result page shows the usual scores, IELTS band (+ the 4 IELTS criteria) and feedback.
How many tests: Free 1 a month, Plus 1 a week, Pro 1 a day. All questions below are written for Speakoff.
"""

import random
from datetime import date, timedelta

from server import db

LIMITS = {"free": ("month", 1), "plus": ("week", 1), "pro": ("day", 1)}
PART1_ANSWER = (10, 45)       # seconds per answer (min before Next, max = moves on by itself)
PART2_PREP, PART2_TALK = 60, (60, 120)
PART3_ANSWER = (15, 75)
MAX_TOTAL = 15 * 60

SETS = [
    {"id": "home", "p1_topic": "Your home",
     "p1": ["Do you live in a house or an apartment?", "What is your favourite room in your home, and why?",
            "Is there anything you would like to change about your home?", "Do you think you will live in the same place in five years?"],
     "p2": {"title": "Describe a place in your city where you like to spend time.",
            "points": ["where it is", "how often you go there", "what you do there", "and explain why you like this place"]},
     "p3": ["Why do some people prefer to live in big cities?", "How have cities in your country changed in the last twenty years?",
            "Should governments spend more money on public parks? Why or why not?", "What problems might cities face in the future?"]},
    {"id": "work", "p1_topic": "Work or studies",
     "p1": ["Do you work or are you a student?", "What do you like most about your work or studies?",
            "What did you want to be when you were a child?", "Would you like to change your job or subject in the future?"],
     "p2": {"title": "Describe a skill you learned that has been useful to you.",
            "points": ["what the skill is", "when and how you learned it", "who helped you learn it", "and explain why it has been useful"]},
     "p3": ["Which skills do young people need to find a good job today?", "Is it better to learn skills at school or at work?",
            "How will technology change the jobs people do?", "Should older people keep learning new skills? Why?"]},
    {"id": "food", "p1_topic": "Food",
     "p1": ["What kind of food do you like to eat?", "Do you usually cook at home or eat out?",
            "Is there any food you did not like as a child but like now?", "What is a typical breakfast in your country?"],
     "p2": {"title": "Describe a special meal you remember well.",
            "points": ["when and where it was", "who you were with", "what you ate", "and explain why you remember it"]},
     "p3": ["How have people's eating habits changed in recent years?", "Why do some families no longer eat together?",
            "Should schools teach children how to cook?", "Is fast food a serious problem in your country?"]},
    {"id": "travel", "p1_topic": "Travel",
     "p1": ["Do you like travelling?", "How do you usually travel to other cities?",
            "Do you prefer travelling alone or with other people?", "Where would you like to go next?"],
     "p2": {"title": "Describe a trip that did not go as planned.",
            "points": ["where you were going", "who you were with", "what went wrong", "and explain how you felt about it"]},
     "p3": ["What are the benefits of visiting other countries?", "How does tourism affect the places people visit?",
            "Will people travel more or less in the future? Why?", "Is it important to learn about a country before visiting it?"]},
    {"id": "tech", "p1_topic": "Your phone",
     "p1": ["How often do you use your phone each day?", "What do you mostly use your phone for?",
            "Do you remember your first phone?", "Could you live without your phone for a week?"],
     "p2": {"title": "Describe an app or website you find very useful.",
            "points": ["what it is called", "how you found it", "what you use it for", "and explain why it is useful to you"]},
     "p3": ["Do people spend too much time on their phones?", "How has the internet changed the way people make friends?",
            "Should children be allowed to use smartphones?", "What are the risks of sharing personal information online?"]},
    {"id": "friends", "p1_topic": "Friends",
     "p1": ["Do you have many friends?", "How often do you meet your friends?",
            "What do you usually do together?", "Is it easy to make new friends in your city?"],
     "p2": {"title": "Describe a person who has had a good influence on you.",
            "points": ["who this person is", "how you know them", "what they did", "and explain how they influenced you"]},
     "p3": ["What makes someone a good friend?", "Are friendships today different from friendships in the past?",
            "Who has more influence on young people: parents or friends?", "Can people be real friends online?"]},
    {"id": "free_time", "p1_topic": "Free time",
     "p1": ["What do you like to do in your free time?", "Do you have more free time now than before?",
            "Do you prefer spending free time indoors or outdoors?", "Is there a new hobby you would like to try?"],
     "p2": {"title": "Describe a hobby you enjoy.",
            "points": ["what the hobby is", "when you started it", "how much time you spend on it", "and explain why you enjoy it"]},
     "p3": ["Why do some people not have any hobbies?", "Are expensive hobbies better than cheap ones?",
            "How do hobbies help people with stress?", "Should employers give workers more free time?"]},
    {"id": "nature", "p1_topic": "Weather",
     "p1": ["What is the weather like where you live?", "What is your favourite season?",
            "Does the weather change your mood?", "Do you check the weather forecast every day?"],
     "p2": {"title": "Describe a beautiful natural place you have visited.",
            "points": ["where it is", "when you went there", "what you saw and did", "and explain why you think it is beautiful"]},
     "p3": ["Why is it important to protect nature?", "What can ordinary people do to help the environment?",
            "Should some natural places be closed to tourists?", "Who is more responsible for climate change: people or companies?"]},
    {"id": "learning", "p1_topic": "Learning English",
     "p1": ["How long have you been learning English?", "What is the most difficult part of English for you?",
            "How do you practise English outside class?", "Would you like to learn another language?"],
     "p2": {"title": "Describe a teacher you remember well.",
            "points": ["who the teacher was", "what they taught", "what they were like", "and explain why you remember them"]},
     "p3": ["What makes a good teacher?", "Will online lessons replace classrooms?",
            "Should children start learning foreign languages very young?", "Are exams the best way to measure what students know?"]},
    {"id": "shopping", "p1_topic": "Shopping",
     "p1": ["Do you enjoy shopping?", "Do you prefer shopping online or in shops?",
            "What was the last thing you bought?", "Do you ever buy things you do not need?"],
     "p2": {"title": "Describe something you bought that you were very happy with.",
            "points": ["what it was", "where you bought it", "how much it cost", "and explain why you were happy with it"]},
     "p3": ["Why do people buy more things than they need?", "How does advertising affect what people buy?",
            "Is online shopping bad for small shops?", "Are people today happier than in the past because they own more things?"]},
    {"id": "sport", "p1_topic": "Sport and health",
     "p1": ["Do you play any sports?", "How do you stay healthy?",
            "Did you do much sport at school?", "Do you like watching sport on TV?"],
     "p2": {"title": "Describe a time you achieved something difficult.",
            "points": ["what you achieved", "when it happened", "what was difficult about it", "and explain how you felt afterwards"]},
     "p3": ["Why do some people find it hard to exercise regularly?", "Should famous athletes be paid so much money?",
            "What can schools do to make children healthier?", "Is winning the most important thing in sport?"]},
    {"id": "celebrations", "p1_topic": "Celebrations",
     "p1": ["How do you usually celebrate your birthday?", "What is the most important holiday in your country?",
            "Do you like big parties or small gatherings?", "Do you give gifts on special days?"],
     "p2": {"title": "Describe a celebration you enjoyed.",
            "points": ["what the celebration was", "where it took place", "who was there", "and explain why you enjoyed it"]},
     "p3": ["Why are traditional festivals important?", "Have celebrations in your country become too commercial?",
            "How do young and old people celebrate differently?", "Should public holidays be the same for everyone in a country?"]},
]
from server.mock_sets_more import MORE   # noqa: E402  (48 more sets: 60 in total)

SETS += [s for s in MORE if s["id"] not in {x["id"] for x in SETS}]
from server.mock_ko import SETS as SETS_KO   # noqa: E402  (100 Korean TOPIK-style sets)

BY_LANG = {"en": SETS, "ko": SETS_KO}
BY_ID = {s["id"]: s for sets in BY_LANG.values() for s in sets}


def lang_of_set(s):
    return s.get("lang", "en")


def _period_start(kind):
    today = date.today()
    if kind == "month":
        start = today.replace(day=1)
    elif kind == "week":
        start = today - timedelta(days=6)
    else:
        start = today
    return start.isoformat()


def limits(user):
    kind, n = LIMITS.get(user["plan"], LIMITS["free"])
    used = db.one("SELECT COUNT(*) n FROM recordings WHERE user_id=? AND is_mock=1 AND status!='failed' AND day>=?",
                  user["id"], _period_start(kind))["n"]
    return {"per": kind, "total": n, "left": max(n - used, 0)}


def pick(user):
    # never a set from the player's last (number of sets - 1) tests in this language: no repeat for months
    sets = BY_LANG.get(user["learn_lang"] or "en", SETS)
    recent = {r["mock_set"] for r in db.all_("SELECT mock_set FROM recordings WHERE user_id=? AND is_mock=1 "
                                             "ORDER BY created DESC LIMIT ?", user["id"], len(sets) - 1)}
    pool = [s for s in sets if s["id"] not in recent] or sets
    return random.choice(pool)


def public(s):
    return {"id": s["id"], "lang": lang_of_set(s), "p1_topic": s["p1_topic"], "p1": s["p1"], "p2": s["p2"], "p3": s["p3"],
            "timing": {"p1": PART1_ANSWER, "p2_prep": PART2_PREP, "p2": PART2_TALK, "p3": PART3_ANSWER}}
