"""Bad-language check on transcripts (2026-11-25).

Rules (server/ranked.py, server/worker.py): the first time a player ever uses bad language they only get a warning.
After that, a ranked answer with bad language counts as a loss and is never played to the opponent, who may report
the player; 3 reports = a 1-week Ranked ban. Normal recordings only show a warning.
Whole words only, so "class", "assess", "Scunthorpe" or "cocktail" are fine.
"""

import re

WORDS = {
    # swearing
    "fuck", "fucks", "fucked", "fucker", "fuckers", "fucking", "fuckin", "motherfucker", "motherfuckers", "motherfucking",
    "shit", "shits", "shitty", "bullshit", "horseshit", "bitch", "bitches", "bitching", "bastard", "bastards",
    "asshole", "assholes", "arsehole", "dickhead", "dickheads", "prick", "pricks", "wanker", "wankers", "twat",
    "cunt", "cunts", "bollocks", "goddamn", "damnit", "piss", "pissed", "jackass", "dumbass", "douchebag",
    # sexual / 18+
    "porn", "porno", "pornography", "dick", "dicks", "cock", "cocks", "pussy", "pussies", "tits", "titties", "boobs",
    "blowjob", "handjob", "dildo", "orgasm", "horny", "slut", "sluts", "whore", "whores", "nude", "nudes", "sexting",
    "cum", "jizz", "masturbate", "masturbating", "rape", "raped", "rapist",
    # slurs
    "nigger", "niggers", "nigga", "niggas", "faggot", "faggots", "fag", "fags", "retard", "retarded", "spastic",
    "tranny", "chink", "chinks", "kike", "spic", "wetback",
}
_word = re.compile(r"[a-z]+(?:'[a-z]+)?")


def find(text):
    """The bad words in a transcript (lowercase, in order, repeats kept)."""
    return [w for w in _word.findall((text or "").lower()) if w in WORDS]
