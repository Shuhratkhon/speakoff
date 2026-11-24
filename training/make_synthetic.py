"""Part 3f: make MORE training data by adding learner-style mistakes to correct sentences.

Source: Tatoeba English sentences (free, CC-BY 2.0 FR, https://tatoeba.org), short everyday
sentences, close to how people speak.  data/tatoeba/eng_sentences.tsv.bz2

For each correct sentence we add 1-2 typical learner mistakes ("She goes" -> "She go")
and train the model to turn it back:  wrong <TAB> correct.  ~20% stay unchanged so the
model also learns to leave correct sentences alone.

Rule for every mistake type: only make a change that is CLEARLY wrong. E.g. "I went" -> "I go"
only if the sentence says "yesterday / ago / last ...", because "I go to school" alone is
correct, and teaching the model to "fix" it would create false alarms.

Run (from the Speaking_Coach folder):
  python -m training.make_synthetic              # 200,000 pairs -> data/grammar/synthetic.tsv
  python -m training.make_synthetic 5000 --show  # small test, prints examples
"""

import bz2
import random
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "tatoeba" / "eng_sentences.tsv.bz2"
OUT = ROOT / "data" / "grammar" / "synthetic.tsv"
TEST = ROOT / "evaluate" / "speech_test.tsv"         # never train on our test sentences
SEED = 42

# Tatoeba has MANY sentences about these names; keep only some of them
NAMES = {"Tom", "Mary", "Sami", "Layla", "Ziri", "Yanni", "Skura", "Rima", "John", "Mennad", "Baya"}

# ---------------------------------------------------------------- word lists
UNCOUNTABLE = {"information", "advice", "homework", "furniture", "hair", "money", "music", "luggage",
               "baggage", "equipment", "knowledge", "research", "traffic", "weather", "experience",
               "news", "progress", "evidence", "bread", "rice", "water", "work", "fun", "help"}
IRREGULAR_PLURAL_ERRORS = {"children": "childrens", "people": "peoples", "men": "mans", "women": "womans",
                           "feet": "foots", "teeth": "tooths", "mice": "mouses"}
MANY_WORDS = {"many", "several", "few", "these", "those", "both", "two", "three", "four", "five", "six",
              "seven", "eight", "nine", "ten", "twenty", "hundred", "a lot of", "various"}
SINGLE_WORDS = {"a", "an", "one", "this", "that", "each", "every", "another"}
SVA_SWAP = {"is": "are", "are": "is", "was": "were", "were": "was", "has": "have", "have": "has",
            "does": "do", "do": "does"}
PREP_CONFUSE = {"in": ["at", "on"], "on": ["in", "at"], "at": ["in", "on", "to"], "to": ["at", "in", "for"],
                "for": ["to", "of"], "of": ["for", "from"], "with": ["to", "by"],
                "about": ["of", "on"], "from": ["of"], "into": ["in", "to"]}
PREP_AFTER = {"listen": "to", "wait": "for", "look": "at", "talk": "to", "belong": "to", "depend": "on"}
PREP_INSERT = {"discuss": "about", "marry": "with", "enter": "into", "reach": "to", "contact": "to",
               "attend": "to", "visit": "to", "call": "to"}
ED_ING = {"bored": "boring", "interested": "interesting", "tired": "tiring", "excited": "exciting",
          "surprised": "surprising", "confused": "confusing", "worried": "worrying", "amazed": "amazing",
          "embarrassed": "embarrassing", "annoyed": "annoying", "disappointed": "disappointing",
          "frightened": "frightening", "satisfied": "satisfying", "shocked": "shocking"}
ED_ING.update({v: k for k, v in list(ED_ING.items())})
GERUND_VERBS = {"enjoy", "finish", "avoid", "suggest", "mind", "keep", "practise", "practice", "consider",
                "imagine", "miss", "recommend", "quit"}
NO_TO_VERBS = {"want", "need", "hope", "decide", "plan", "try", "learn", "promise", "refuse", "would like"}
FREQ = {"always", "usually", "often", "never", "sometimes", "rarely", "seldom", "also", "just", "already"}
STATIVE = {"want", "know", "like", "need", "understand", "believe", "love", "hate", "own", "mean",
           "prefer", "remember", "seem", "belong"}
PAST_MARKERS = {"yesterday", "ago", "last", "1990", "2000", "2010", "2015", "2018", "2019", "2020"}
PERSON = {"father": "he", "mother": "she", "brother": "he", "sister": "she", "friend": "he", "teacher": "she",
          "boss": "he", "man": "he", "woman": "she", "boy": "he", "girl": "she", "son": "he",
          "daughter": "she", "wife": "she", "husband": "he", "doctor": "he", "dog": "it", "cat": "it",
          "friends": "they", "parents": "they", "people": "they", "students": "they", "children": "they",
          "neighbor": "he", "neighbour": "he", "uncle": "he", "aunt": "she", "grandmother": "she"}
CHOICE = {"borrow": "lend", "lend": "borrow", "teach": "learn", "rob": "steal", "bring": "take"}
MAKE_NOUNS = {"mistake", "mistakes", "noise", "decision", "progress", "money", "friends", "effort", "plan"}
DO_NOUNS = {"homework", "favor", "favour", "exercise", "research", "best", "job", "shopping", "dishes"}
NEG_SWAP = {"anything": "nothing", "anybody": "nobody", "anyone": "nobody", "any": "no", "ever": "never",
            "anywhere": "nowhere"}
SUBJ_PRON = {"i", "you", "he", "she", "it", "we", "they"}
ORDINALS = {"first", "second", "third", "fourth", "fifth", "last", "next", "same", "only", "most"}
COUNTABLE = {"station", "store", "shop", "door", "window", "bus", "car", "house", "city", "world", "sun", "moon",
             "beach", "gym", "cinema", "park", "office", "room", "table", "box", "airport", "hospital",
             "library", "kitchen", "bank", "train", "phone", "teacher", "doctor", "end", "top", "mat",
             "bottom", "middle", "street", "road", "river", "sea", "sky", "floor", "wall", "museum",
             "restaurant", "hotel", "computer", "internet", "radio", "movie", "film", "book", "man",
             "woman", "boy", "girl", "dog", "cat", "key", "bed", "class", "meeting", "party", "game", "problem"}


def infl(lemma, tag):
    from lemminflect import getInflection
    r = getInflection(lemma, tag=tag)
    return r[0] if r else None


def be_form(subject, past=False):
    s = subject.lower()
    if past:
        return "was" if s in {"i", "he", "she", "it"} else "were"
    return {"i": "am", "he": "is", "she": "is", "it": "is"}.get(s, "are" if s in {"you", "we", "they"} else "is")


def low(tok):
    """Lowercase a word that is moved away from the sentence start (but keep 'I' and names)."""
    return tok.text if tok.text == "I" or tok.pos_ == "PROPN" else tok.text.lower()


# ---------------------------------------------------------------- mistake makers
# Each one gets the spaCy doc and returns {token index: new text} ("" = delete), or None.

def sva(doc, rng):
    c = [t for t in doc if t.lower_ in SVA_SWAP and t.tag_ in ("VBZ", "VBP", "VBD")
         and not (t.i > 0 and doc[t.i - 1].tag_ in ("MD", "TO"))]
    c += [t for t in doc if t.pos_ == "VERB" and t.tag_ in ("VBZ", "VBP") and t.lower_ not in SVA_SWAP]
    if not c:
        return None
    t = rng.choice(c)
    if t.lower_ in SVA_SWAP:
        new = SVA_SWAP[t.lower_]
    elif t.tag_ == "VBZ":
        new = t.lemma_
    else:
        new = infl(t.lemma_, "VBZ")
    return {t.i: match(new, t.text)} if new and new.lower() != t.lower_ else None


def tense(doc, rng):
    if not any(t.lower_ in PAST_MARKERS for t in doc):
        return None
    c = [t for t in doc if t.tag_ == "VBD" and t.pos_ == "VERB"
         and not any(ch.lower_ in ("if", "wish") for ch in doc[:t.i])]
    if not c:
        return None
    t = rng.choice(c)
    subj = [ch for ch in t.children if ch.dep_ == "nsubj"]
    if rng.random() < 0.3 and subj:                       # "I saw him yesterday" -> "I have seen him yesterday"
        vbn = infl(t.lemma_, "VBN")
        have = "has" if subj[0].tag_ in ("NN", "NNP") or subj[0].lower_ in ("he", "she", "it") else "have"
        return {t.i: f"{have} {vbn}"} if vbn else None
    third = subj and (subj[0].tag_ in ("NN", "NNP") or subj[0].lower_ in ("he", "she", "it"))
    new = infl(t.lemma_, "VBZ") if third else t.lemma_
    return {t.i: new} if new and new != t.text else None


def verb_form(doc, rng):
    options = []
    for t in doc:
        prev = doc[t.i - 1] if t.i > 0 else None
        prev2 = doc[t.i - 2] if t.i > 1 else None
        if t.tag_ == "VB" and prev is not None:
            modal = prev.tag_ == "MD" or (prev.lower_ in ("n't", "not") and prev2 is not None and prev2.tag_ == "MD")
            did = prev.lower_ in ("did", "does", "do") or (prev.lower_ in ("n't", "not") and prev2 is not None
                                                          and prev2.lower_ in ("did", "does", "do"))
            if modal and t.lemma_ != "be":
                options.append({t.i: rng.choice([infl(t.lemma_, "VBZ"), "to " + t.text, infl(t.lemma_, "VBD")])})
            elif did and prev.lower_ != "do" and t.lemma_ != "be":
                options.append({t.i: infl(t.lemma_, "VBD") if "did" in (prev.lower_, prev2.lower_ if prev2 else "")
                                else infl(t.lemma_, "VBZ")})
            elif prev.tag_ == "TO" and prev2 is not None and prev2.lemma_ in NO_TO_VERBS:
                options.append({t.i: infl(t.lemma_, "VBG")})
        if t.tag_ == "VBG" and prev is not None and prev.lemma_ in GERUND_VERBS and prev.pos_ == "VERB":
            options.append({t.i: "to " + t.lemma_})
        if t.tag_ == "VBG" and t.dep_ == "pcomp" and prev is not None and prev.pos_ == "ADP":
            options.append({t.i: t.lemma_})                               # "for helping" -> "for help"
        if t.tag_ == "VBG" and prev is not None and prev.lemma_ == "be" and prev.dep_ == "aux":
            options.append({t.i: t.lemma_})                               # "I am studying" -> "I am study"
            options.append({prev.i: ""})                                  # "I am studying" -> "I studying"
        if t.tag_ == "VBN" and prev is not None and prev.lower_ in ("have", "has", "had", "'ve", "'s") \
                and prev.dep_ == "aux":
            vbd = infl(t.lemma_, "VBD")
            options.append({t.i: vbd if vbd != t.text and rng.random() < 0.6 else t.lemma_})
        if t.tag_ == "VBN" and prev is not None and prev.lemma_ == "be" and prev.dep_ == "auxpass":
            vbd = infl(t.lemma_, "VBD")
            if vbd and vbd != t.text:
                options.append({t.i: vbd})                                # "was written" -> "was wrote"
    options = [o for o in options if all(v is not None for v in o.values())]
    return rng.choice(options) if options else None


def noun_num(doc, rng):
    options = []
    for t in doc:
        if t.pos_ != "NOUN" or not t.is_alpha:
            continue
        before = " ".join(x.lower_ for x in doc[max(0, t.i - 3):t.i])
        prev = doc[t.i - 1].lower_ if t.i > 0 else ""
        if t.lower_ in IRREGULAR_PLURAL_ERRORS:
            options.append({t.i: IRREGULAR_PLURAL_ERRORS[t.lower_]})
        elif t.tag_ == "NN" and t.lower_ in UNCOUNTABLE and t.lower_ != "news":
            options.append({t.i: t.text + "s"})
        elif t.tag_ == "NN" and prev in SINGLE_WORDS:
            pl = infl(t.lemma_, "NNS")
            if pl and pl != t.text:
                options.append({t.i: pl})
        elif t.tag_ == "NNS" and (prev in MANY_WORDS or doc[t.i - 1].tag_ == "CD" or "one of" in before):
            if t.lemma_ != t.lower_:
                options.append({t.i: t.lemma_})
    return rng.choice(options) if options else None


def determiner(doc, rng):
    options = []
    for t in doc:
        nxt = doc[t.i + 1] if t.i + 1 < len(doc) else None
        if t.lower_ in ("a", "an") and t.dep_ == "det" and t.i > 0:
            options.append({t.i: ""})                                       # "a new phone" -> "new phone"
            options.append({t.i: match("an" if t.lower_ == "a" else "a", t.text)})
        # "the" is only CLEARLY needed before superlatives / ordinals / "same", before "X of ...",
        # and before common countable nouns ("Birds disturb soil" without "the" is still correct)
        if t.lower_ == "the" and t.dep_ == "det" and t.head.tag_ == "NN" and t.i > 0 \
                and doc[t.i - 1].lower_ not in ("of", "all"):
            after = doc[t.i + 1] if t.i + 1 < len(doc) else None
            needed = (after is not None and (after.tag_ == "JJS" or after.lower_ in ORDINALS)) \
                or any(c.lower_ == "of" for c in t.head.children) or t.head.lower_ in COUNTABLE
            if needed:
                options.append({t.i: ""})                                   # "the best student" -> "best student"
        if t.tag_ == "PRP$" and t.i > 0 and doc[t.i - 1].pos_ in ("ADP", "VERB"):
            options.append({t.i: "the " + t.text})                          # "to my friend" -> "to the my friend"
        if t.lower_ in ("football", "tennis", "basketball", "soccer", "baseball", "golf", "chess") \
                and t.i > 0 and doc[t.i - 1].lemma_ == "play":
            options.append({t.i: "the " + t.text})                          # "play football" -> "play the football"
        if t.lower_ in ("bus", "car", "train", "taxi", "plane", "bike", "subway") and t.i > 0 \
                and doc[t.i - 1].lower_ == "by":
            options.append({t.i: "the " + t.text})
        if t.i == 0 and t.lower_ in ("life", "love", "time", "money", "music", "nature", "history", "happiness"):
            options.append({t.i: "The " + t.text.lower()})                  # "Life is beautiful" -> "The life is"
        # only for people/names: "the government lies" without 's is still correct English
        if t.tag_ == "POS" and t.lower_ == "'s" and t.i > 0 \
                and (doc[t.i - 1].tag_ == "NNP" or doc[t.i - 1].lower_ in PERSON):
            options.append({t.i: ""})                                       # "my father's car" -> "my father car"
        if t.lower_ == "the" and nxt is not None and nxt.lower_ == "gym":
            options.append({t.i: ""})
    return rng.choice(options) if options else None


def preposition(doc, rng):
    options = []
    for t in doc:
        prev = doc[t.i - 1] if t.i > 0 else None
        if t.lower_ in PREP_CONFUSE and t.dep_ == "prep" and t.pos_ == "ADP":
            options.append({t.i: rng.choice(PREP_CONFUSE[t.lower_])})
        if prev is not None and prev.lemma_ in PREP_AFTER and t.lower_ == PREP_AFTER[prev.lemma_] and t.dep_ == "prep":
            options.append({t.i: ""})                                       # "listen to music" -> "listen music"
        if t.pos_ == "VERB" and t.lemma_ in PREP_INSERT and t.i + 1 < len(doc) \
                and doc[t.i + 1].dep_ in ("dobj", "det", "poss", "compound", "amod") and doc[t.i + 1].lower_ != "me":
            options.append({t.i: t.text + " " + PREP_INSERT[t.lemma_]})    # "discuss the" -> "discuss about the"
        if t.lower_ in ("home", "there", "here") and prev is not None and prev.lemma_ in ("go", "come", "get", "be") \
                and prev.pos_ in ("VERB", "AUX"):
            options.append({t.i: "to " + t.text})                           # "went home" -> "went to home"
        if t.lower_ == "ago" and t.i >= 2:
            # "five years ago" -> "before five years"
            start = t.i - 2 if doc[t.i - 2].tag_ in ("CD", "DT") or doc[t.i - 2].lower_ in ("a", "many", "few") else t.i - 1
            e = {t.i: ""}
            e[start] = "before " + (low(doc[start]) if start == 0 else doc[start].text)
            options.append(e)
    return rng.choice(options) if options else None


def adjective_adverb(doc, rng):
    options = []
    for t in doc:
        if t.tag_ == "JJR" and t.text.endswith("er") and t.lemma_ != t.lower_ and t.lower_ not in ("other", "former"):
            options.append({t.i: "more " + t.lemma_})                       # "taller" -> "more tall"
        if t.tag_ == "JJS" and t.text.endswith("est") and t.lemma_ != t.lower_:
            options.append({t.i: "most " + t.lemma_})                       # "cheapest" -> "most cheap"
        if t.tag_ == "JJR" and t.text.endswith("er") and t.lemma_ != t.lower_ and rng.random() < 0.3:
            options.append({t.i: "more " + t.text})                         # "easier" -> "more easier"
        if t.lower_ in ED_ING and t.i > 0 and doc[t.i - 1].lemma_ in ("be", "feel", "get", "look", "very", "so",
                                                                      "really", "become"):
            options.append({t.i: ED_ING[t.lower_]})                         # "I am bored" -> "I am boring"
        if t.tag_ == "RB" and t.lower_.endswith("ly") and len(t.text) > 5 and t.head.pos_ == "VERB" \
                and t.i > t.head.i:
            w = t.lower_
            adj = w[:-3] + "y" if w.endswith("ily") else w[:-2] + "e" if w.endswith("bly") else w[:-2]
            if not adj.endswith(("al", "ical")):
                options.append({t.i: adj})                                  # "drives carefully" -> "careful"
        if t.lower_ == "well" and t.head.pos_ == "VERB" and t.i > t.head.i and t.dep_ == "advmod":
            options.append({t.i: "good"})
        if t.lower_ == "late" and t.dep_ == "advmod":
            options.append({t.i: "lately"})
    return rng.choice(options) if options else None


def word_order(doc, rng):
    options = []
    for t in doc:
        nxt = doc[t.i + 1] if t.i + 1 < len(doc) else None
        if t.lemma_ == "be" and t.pos_ == "AUX" and nxt is not None and nxt.lower_ in FREQ and t.i > 0:
            options.append({t.i: nxt.text, nxt.i: t.text})                  # "is always" -> "always is"
        if t.lower_ == "really" and nxt is not None and nxt.pos_ == "VERB":
            options.append({t.i: "very"})                                   # "really like" -> "very like"
        if t.lower_ == "enough" and nxt is not None and nxt.pos_ == "NOUN" and t.dep_ in ("amod", "det"):
            options.append({t.i: nxt.text, nxt.i: "enough"})                # "enough money" -> "money enough"
        if t.lower_ in FREQ - {"also", "just", "already"} and nxt is not None and nxt.pos_ == "VERB" \
                and nxt.tag_ in ("VBZ", "VBP", "VBD") and t.i > 0:
            obj = [c for c in nxt.children if c.dep_ == "dobj"]
            if obj and obj[0].i == nxt.i + 1 or (obj and doc[nxt.i + 1].dep_ == "det"):
                options.append({t.i: nxt.text, nxt.i: t.lower_})            # "always eats" -> "eats always"
    # questions: "Where are you going?" -> "Where you are going?"
    if len(doc) > 3 and doc[-1].text == "?" and doc[0].tag_ in ("WRB", "WP", "WDT"):
        aux, subj = doc[1], doc[2]
        if subj.lower_ in SUBJ_PRON and aux.pos_ == "AUX":
            if aux.lower_ in ("do", "does", "did"):
                verb = next((x for x in doc[3:] if x.tag_ == "VB"), None)
                if verb is not None and verb.lemma_ != "be":
                    form = {"did": infl(verb.lemma_, "VBD"), "does": infl(verb.lemma_, "VBZ")}.get(aux.lower_, verb.text)
                    options.append({1: "", verb.i: form})                   # "What did you do?" -> "What you did?"
            elif aux.lower_ not in ("'s", "'re", "'m"):
                options.append({1: subj.text, 2: aux.text.lower()})
    # embedded question: "I don't know where the station is." -> "... where is the station."
    if len(doc) > 5 and doc[-1].is_punct and doc[-2].lemma_ == "be" and doc[-2].pos_ == "AUX":
        wh = [x for x in doc[1:-3] if x.tag_ in ("WRB",) and x.i < len(doc) - 3]
        if wh and doc[wh[-1].i + 1].pos_ in ("DET", "PRON", "NOUN", "PROPN"):
            w = wh[-1]
            options.append({w.i: w.text + " " + doc[-2].text, doc[-2].i: ""})
    return rng.choice(options) if options else None


def word_choice(doc, rng):
    options = []
    for t in doc:
        if t.pos_ == "VERB" and t.lemma_ in CHOICE:
            new = infl(CHOICE[t.lemma_], t.tag_) if t.tag_ != "VB" else CHOICE[t.lemma_]
            if new:
                options.append({t.i: new})                                  # "borrowed" -> "lent"
        if t.pos_ == "VERB" and t.lemma_ == "tell" and t.i + 1 < len(doc) and doc[t.i + 1].tag_ == "PRP":
            new = infl("say", t.tag_) if t.tag_ != "VB" else "say"
            if new:
                options.append({t.i: new})                                  # "told me" -> "said me"
        if t.pos_ == "VERB" and t.lemma_ in ("make", "do"):
            objs = {c.lower_ for c in t.children if c.dep_ == "dobj"}
            other = "do" if t.lemma_ == "make" else "make"
            if (t.lemma_ == "make" and objs & MAKE_NOUNS) or (t.lemma_ == "do" and objs & DO_NOUNS):
                new = infl(other, t.tag_) if t.tag_ != "VB" else other
                if new:
                    options.append({t.i: new})                              # "make a mistake" -> "do a mistake"
        if t.lower_ in NEG_SWAP and any(x.lower_ in ("n't", "not") for x in doc[:t.i]):
            options.append({t.i: NEG_SWAP[t.lower_]})                       # "didn't eat anything" -> "nothing"
    return rng.choice(options) if options else None


def structure(doc, rng):
    """Missing / extra words and clause-level mistakes."""
    options = []
    has_will = any(t.lower_ in ("will", "'ll") for t in doc)
    has_would = any(t.lower_ in ("would", "'d") for t in doc)
    for t in doc:
        prev = doc[t.i - 1] if t.i > 0 else None
        nxt = doc[t.i + 1] if t.i + 1 < len(doc) else None
        # stative verbs in -ing: "I want" -> "I am wanting"
        if t.pos_ == "VERB" and t.lemma_ in STATIVE and t.tag_ in ("VBZ", "VBP"):
            subj = [c for c in t.children if c.dep_ == "nsubj"]
            if subj and not any(c.dep_ == "aux" for c in t.children):
                options.append({t.i: be_form(subj[0].text if subj[0].tag_ != "NNS" else "they") + " " + infl(t.lemma_, "VBG")})
        # "If I have time, I will" -> "If I will have time"
        if t.lower_ in ("if", "when", "after", "before") and has_will and nxt is not None and nxt.lower_ in SUBJ_PRON:
            verb = doc[t.i + 2] if t.i + 2 < len(doc) else None
            if verb is not None and verb.tag_ in ("VBP", "VBZ") and verb.pos_ in ("VERB", "AUX"):
                options.append({verb.i: "will " + (verb.lemma_ if verb.lemma_ != "be" else "be")})
        # "If I knew, I would" -> "If I would know"
        if t.lower_ == "if" and has_would and nxt is not None and nxt.lower_ in SUBJ_PRON:
            verb = doc[t.i + 2] if t.i + 2 < len(doc) else None
            if verb is not None and verb.tag_ == "VBD" and verb.lemma_ != "be":
                options.append({verb.i: "would " + verb.lemma_})
        # "I wish I could" -> "I wish I can"
        if t.lemma_ == "wish" and nxt is not None and nxt.lower_ in SUBJ_PRON and t.i + 2 < len(doc):
            v = doc[t.i + 2]
            new = {"could": "can", "had": "have", "were": "am" if nxt.lower_ == "i" else "are", "would": "will"}.get(v.lower_)
            if new:
                options.append({v.i: new})
        # "It is very hot" -> "Is very hot"
        if t.i == 0 and t.lower_ == "it" and nxt is not None and nxt.lemma_ == "be" and nxt.tag_ in ("VBZ", "VBD"):
            options.append({0: "", 1: "Is" if nxt.lower_ in ("is", "'s") else nxt.text.capitalize()})
        # "My father works" -> "My father he works"
        if t.dep_ == "nsubj" and t.lower_ in PERSON and nxt is not None and nxt.i == t.head.i and t.head.pos_ == "VERB":
            options.append({t.i: t.text + " " + PERSON[t.lower_]})
        # "I can come" -> "I can't to come" handled in verb_form; "want to become" -> "want become"
        if t.tag_ == "TO" and prev is not None and (prev.lemma_ in NO_TO_VERBS or prev.pos_ == "ADJ") \
                and nxt is not None and nxt.tag_ == "VB":
            options.append({t.i: ""})
        # "came here to study" -> "came here for study"
        if t.tag_ == "TO" and nxt is not None and nxt.tag_ == "VB" and prev is not None \
                and prev.lower_ in ("here", "there", "abroad", "school", "university", "Korea", "London") :
            options.append({t.i: "for"})
        # "made me wait" -> "made me to wait"
        if t.tag_ == "VB" and prev is not None and prev.tag_ == "PRP" and t.i > 1 \
                and doc[t.i - 2].lemma_ in ("make", "let") and doc[t.i - 2].pos_ == "VERB":
            options.append({t.i: "to " + t.text})
        # "I agree" -> "I am agree"
        if t.lemma_ == "agree" and t.tag_ in ("VBP", "VBZ") and prev is not None and prev.lower_ in SUBJ_PRON:
            options.append({t.i: be_form(prev.text) + " " + t.lemma_})
        # "I have lived here since 2020" -> "I live here since 2020"
        if t.tag_ == "VBN" and prev is not None and prev.lower_ in ("have", "has", "'ve") \
                and any(x.lower_ in ("since", "for") for x in doc[t.i:]):
            new = infl(t.lemma_, "VBZ") if prev.lower_ == "has" else t.lemma_
            if t.lemma_ == "be":
                new = "is" if prev.lower_ == "has" else "am" if t.i > 1 and doc[t.i - 2].lower_ == "i" else "are"
            options.append({prev.i: "", t.i: new})
        # "was going to" -> "will going to" (I am going to travel -> I will going to travel)
        if t.lower_ == "going" and prev is not None and prev.lemma_ == "be" and nxt is not None and nxt.lower_ == "to":
            options.append({prev.i: "will"})
    return rng.choice(options) if options else None


# ---------------------------------------------------------------- v3: types v2 still missed
PEOPLE = set(PERSON) | {"man", "men", "woman", "women", "boy", "boys", "girl", "girls", "person", "people",
                        "student", "students", "doctor", "child", "children", "kid", "kids", "guy", "lady",
                        "friends", "teachers", "someone", "somebody", "anyone", "everyone", "nobody"}
NOW_WORDS = {"now", "currently", "moment"}
DATIVE_TO = {"explain", "describe", "say", "suggest", "introduce", "mention", "report", "announce", "repeat"}
LONG_ADJ_END = ("ful", "ous", "ive", "ing", "able", "ible", "ent", "ant", "al", "ic", "ed")


def is_long_adj(t):
    return t.tag_ == "JJ" and (len(t.text) >= 8 or t.lower_.endswith(LONG_ADJ_END))


def v3_types(doc, rng):
    options = []
    first = doc[0].lower_
    now = any(t.lower_ in NOW_WORDS for t in doc) or first in ("look", "listen")
    for t in doc:
        prev = doc[t.i - 1] if t.i > 0 else None
        nxt = doc[t.i + 1] if t.i + 1 < len(doc) else None
        # relative pronoun: "the girl who" -> "the girl what / which", "the book that" -> "the book who"
        rel = next((a for a in t.ancestors if a.dep_ == "relcl"), None)
        if t.tag_ in ("WDT", "WP") and t.lower_ in ("who", "which", "that") and rel is not None:
            ante = rel.head
            person = ante.lower_ in PEOPLE
            if ante.pos_ == "NOUN" and t.i == ante.i + 1:
                if person and t.lower_ in ("who", "that"):
                    options.append({t.i: rng.choice(["which", "what"]) if t.lower_ == "who" else "what"})
                elif not person and t.lower_ in ("which", "that"):
                    options.append({t.i: rng.choice(["who", "who", "what"])})
        # present progressive with "now / look,": "it's raining" -> "it rains"
        if now and t.tag_ == "VBG" and prev is not None and prev.dep_ == "aux" \
                and prev.lower_ in ("am", "is", "are", "'m", "'s", "'re") and t.lemma_ not in STATIVE \
                and not (nxt is not None and nxt.lower_ == "to"):
            subj = [c for c in t.children if c.dep_ in ("nsubj", "expl")] or                    [x for x in doc[max(prev.i - 1, 0):prev.i] if x.dep_ == "nsubj"]
            if subj:
                s = subj[0]
                third = s.lower_ in ("he", "she", "it") or s.tag_ in ("NN", "NNP")
                new = infl(t.lemma_, "VBZ") if third else t.lemma_
                if new:
                    options.append({prev.i: "", t.i: new})
        # "explained the rules to me" -> "explained me the rules", "explain to me" -> "explain me"
        if t.lower_ == "to" and t.head.pos_ == "VERB" and t.head.lemma_ in DATIVE_TO and nxt is not None \
                and nxt.tag_ == "PRP" and nxt.lower_ not in ("i", "it") and t.i > t.head.i:
            v = t.head
            if t.i == v.i + 1:
                options.append({t.i: ""})
            elif nxt.i + 1 < len(doc) and doc[nxt.i + 1].is_punct:
                options.append({v.i: v.text + " " + nxt.lower_, t.i: "", nxt.i: ""})
        # borrow / lend, learn / teach (rare in the data, so they get their own maker)
        if t.pos_ == "VERB" and t.lemma_ in ("lend", "borrow", "teach"):
            other = {"lend": "borrow", "borrow": "lend", "teach": "learn"}[t.lemma_]
            new = infl(other, t.tag_) if t.tag_ != "VB" else other
            if new:
                options.append({t.i: new})
        # long adjectives: "most beautiful" -> "beautifulest", "more careful" -> "carefuller"
        if t.lower_ in ("most", "more") and nxt is not None and is_long_adj(nxt) and t.head.i == nxt.i:
            w = nxt.text
            stem = w[:-1] + "i" if w.endswith("y") else w[:-1] if w.endswith("e") else w
            options.append({t.i: "", nxt.i: stem + ("est" if t.lower_ == "most" else "er")})
    return rng.choice(options) if options else None


def keep_clean_bonus(doc):
    """Sentences the model must learn to LEAVE ALONE (v2 'fixed' "most hardworking" into "hardestworking")."""
    return any(t.lower_ in ("most", "more") and i + 1 < len(doc) and is_long_adj(doc[i + 1])
               for i, t in enumerate(doc))


MAKERS = [  # (function, weight): more weight = more examples of that mistake
    (sva, 8), (tense, 14), (verb_form, 12), (noun_num, 10), (determiner, 10), (preposition, 10),
    (adjective_adverb, 16), (word_order, 16), (word_choice, 16), (structure, 12), (v3_types, 30),
]


def match(new, old):
    return new[:1].upper() + new[1:] if old[:1].isupper() else new


def render(doc, edits):
    out = ""
    for t in doc:
        if t.i in edits:
            text = edits[t.i]
            if text == "":
                if out and not out.endswith(" "):
                    out += t.whitespace_
                continue
            if t.i == 0 or (t.i == 1 and edits.get(0) == ""):
                text = text[:1].upper() + text[1:]
            elif t.i > 0 and doc[t.i - 1].text in (".", "?", "!"):
                pass
            out += text + t.whitespace_
        else:
            text = t.text
            if 0 in edits and t.i == 1 and edits[0] == "":
                text = text[:1].upper() + text[1:]
            out += text + t.whitespace_
    out = re.sub(r" {2,}", " ", out).strip()
    out = re.sub(r" ([.,?!])", lambda m: m.group(1), out)
    return out[:1].upper() + out[1:]


def corrupt(doc, rng, makers=None):
    """Add 1 or 2 mistakes (on different words). Returns (wrong sentence, kinds) or (None, [])."""
    n = 1 if rng.random() < 0.75 else 2
    edits, kinds = {}, []
    # ask every maker for a candidate, then pick among the ones that FIT this sentence
    # (so rare types like word order still get picked when a sentence allows them)
    found = []
    for f, w in makers or MAKERS:
        e = f(doc, rng)
        if e and all(v is not None for v in e.values()):
            found.append((f.__name__, w, e))
    while found and len(kinds) < n:
        name, _, e = rng.choices(found, [w for _, w, _ in found])[0]
        found = [x for x in found if x[0] != name]
        # two mistakes must not touch neighbouring words: "a way" -> "ways" (delete "a" + plural)
        # would turn into a CORRECT sentence
        if any(abs(i - j) <= 1 for i in e for j in edits):
            continue
        edits.update(e)
        kinds.append(name)
    if not kinds:
        return None, []
    wrong = render(doc, edits)
    return (wrong, kinds) if wrong != doc.text else (None, [])


def load_sentences(rng, limit):
    test = set()
    for line in TEST.read_text(encoding="utf-8").splitlines():
        for part in line.split("\t")[-1].split("||"):
            test.add(part.strip().lower())
    out = []
    with bz2.open(SRC, "rt", encoding="utf-8") as f:
        for line in f:
            text = line.rstrip("\n").split("\t")[-1].strip()
            words = text.split()
            if not (4 <= len(words) <= 25) or not text.isascii() or not text[:1].isupper():
                continue
            if not text.endswith((".", "?", "!")) or '"' in text or text.lower() in test:
                continue
            if any(w.strip(".,?!'s") in NAMES for w in words) and rng.random() < 0.8:
                continue
            out.append(text)
    rng.shuffle(out)
    return out[:limit]


def main():
    import spacy
    target = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 200_000
    show = "--show" in sys.argv
    out_path = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else OUT
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else SEED
    rng = random.Random(seed)
    # --only-v3: scan ALL sentences, keep only the v3 mistake types (+ "most beautiful" kept correct)
    only = "--only-v3" in sys.argv
    sentences = load_sentences(rng, 10**8 if only else int(target * 1.15))
    print(f"loaded {len(sentences)} clean sentences")

    nlp = spacy.load("en_core_web_sm", disable=["ner"])
    pairs, kinds_count = [], Counter()
    for k, doc in enumerate(nlp.pipe(sentences, batch_size=1000)):
        if only:
            wrong, kinds = corrupt(doc, rng, [(v3_types, 1)])
            if keep_clean_bonus(doc) and (not wrong or rng.random() < 0.45):
                pairs.append((doc.text, doc.text))
            elif wrong:
                pairs.append((wrong, doc.text))
                kinds_count.update(kinds)
        elif rng.random() < (0.45 if keep_clean_bonus(doc) else 0.18):     # leave ~18% correct
            pairs.append((doc.text, doc.text))
        else:
            wrong, kinds = corrupt(doc, rng)
            if wrong:
                pairs.append((wrong, doc.text))
                kinds_count.update(kinds)
        if k % 20000 == 0:
            print(f"  {k}/{len(sentences)}", flush=True)
        if len(pairs) >= target:
            break

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(f"{w}\t{c}\n" for w, c in pairs if "\t" not in w + c), encoding="utf-8")
    changed = sum(w != c for w, c in pairs)
    print(f"\nwrote {len(pairs)} pairs ({changed / len(pairs):.0%} with mistakes) -> {out_path}")
    print("mistakes per type:", dict(kinds_count.most_common()))
    if show:
        for w, c in [p for p in pairs if p[0] != p[1]][:60]:
            print(f"  {w}\n    -> {c}")


if __name__ == "__main__":
    main()
