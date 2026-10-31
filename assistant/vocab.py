"""Fixes names the speech model has never seen, from a word list the user can extend.

The model only knows English spellings, so "Amr Diab" comes out as "armor dab" and "Maghrib"
as "Machado" or "month of the". A run of words that sounds close enough to a listed name is
replaced by it. Prayer names are short and sound like everyday words ("Asr", "Isha"), so they
are only matched right before the word "prayer".
"""

import difflib
import re

PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
# heard on the tablet, too far from the name to match by sound
HEARD_AS = {"machado": "Maghrib", "month of the": "Maghrib", "mother of": "Maghrib"}
# words that really can come before "prayer", or that a question puts there
COMMON = {"next", "the", "a", "my", "your", "our", "last", "first", "this", "that", "of", "for",
          "morning", "evening", "noon", "night", "friday", "eid", "taraweeh", "dawn", "sunset",
          "is", "what", "what's", "whats", "when", "when's", "until", "till", "time", "about",
          "to", "at", "it", "it's", "its", "in", "and", "before", "after", "since"}


def sound(text):
    """A rough spelling of how it sounds: Arabic transliterations and English mishearings meet."""
    s = re.sub(r"[^a-z]", "", text.lower())
    for a, b in (("gh", "g"), ("kh", "k"), ("dh", "d"), ("th", "t"), ("ph", "f"), ("q", "k"),
                 ("ck", "k"), ("c", "k"), ("ee", "i"), ("oo", "u"), ("ou", "u"), ("y", "i"), ("w", "u")):
        s = s.replace(a, b)
    return re.sub(r"(.)\1+", r"\1", s)  # double letters


def similar(a, b):
    return difflib.SequenceMatcher(None, sound(a), sound(b)).ratio()


def correct(text, names):
    """Replaces runs of words that sound like a listed name (or a prayer, before "prayer")."""
    words = text.split()
    if not words:
        return text
    for name in sorted(names, key=len, reverse=True):
        if len(sound(name)) < 5:  # too short to match safely outside the prayer rule
            continue
        k = len(name.split())
        best = None
        for size in range(max(1, k - 1), k + 2):
            for i in range(len(words) - size + 1):
                window = " ".join(words[i:i + size])
                score = similar(window, name)
                if score >= 0.75 and (best is None or score > best[0]):
                    best = (score, i, size)
        if best:
            _, i, size = best
            tail = re.search(r"[^\w']+$", words[i + size - 1])  # keep "?" or "," after the name
            words[i:i + size] = [name + (tail.group() if tail else "")]
    return correct_prayers(" ".join(words))


def correct_prayers(text):
    m = re.search(r"((?:[\w']+\s+){1,3}?)(prayer|prayers|salah|adhan|azan)\b", text, re.I)
    if not m:
        return text
    before = m.group(1).split()
    phrase = " ".join(before).lower()
    for heard, prayer in HEARD_AS.items():
        if phrase.endswith(heard):
            kept = before[:len(before) - len(heard.split())]
            return text[:m.start(1)] + " ".join(kept + [prayer]) + " " + text[m.start(2):]
    # only the name-like words right before "prayer": "what is Machado prayer" -> "Machado"
    n = 0
    while n < len(before) and before[-1 - n].lower().strip("'?,.") not in COMMON:
        n += 1
    if not n:
        return text
    chunk = " ".join(before[-n:])
    score, prayer = max((similar(chunk, p), p) for p in PRAYERS)
    if score < 0.5:
        return text
    return text[:m.start(1)] + " ".join(before[:-n] + [prayer]) + " " + text[m.start(2):]
