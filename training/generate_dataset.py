"""Generate the Jarvis tool-calling dataset.

Writes training/data/{train,val,eval}.jsonl. Each row is
  {"intent": ..., "messages": [system, user, assistant]}

The eval split uses held-out templates and slot values (cities, artists, questions),
so it measures generalisation, not memorisation. Utterances get the same kind of noise
whisper produced on the tablet: lowercase, no punctuation, "hey jarvis" left in,
and slips like "time of" for "timer".

Usage: python3 training/generate_dataset.py [--seed 7] [--train 6000] [--val 300] [--eval 400]
"""

import argparse
import json
import random
import re
from pathlib import Path

from tools import DAYS, messages, tool_call

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def number_words(n):
    if n < 20:
        return ONES[n]
    if n >= 100:
        hundreds, rest = divmod(n, 100)
        head = "a hundred" if hundreds == 1 else ONES[hundreds] + " hundred"
        return head if rest == 0 else f"{head} and {number_words(rest)}"
    tens, ones = divmod(n, 10)
    return TENS[tens] + ("" if ones == 0 else "-" + ONES[ones])


def say_number(rng, n):
    # whisper mostly writes digits, but not always
    return str(n) if rng.random() < 0.7 else number_words(n)


# Slot values: (train, eval). Eval values never appear in training.
CITIES = (
    ["London", "Paris", "Riyadh", "Dubai", "New York", "Tokyo", "Cairo", "Berlin", "Toronto", "Sydney",
     "Jeddah", "Madrid", "Istanbul", "Chicago", "Singapore", "Mumbai", "Rome", "Amman", "Doha", "Seoul"],
    ["Dhahran", "Lisbon", "Boston", "Manama", "Vienna", "Kuwait City", "Oslo", "Bangkok"],
)
ARTISTS = (
    ["Coldplay", "Adele", "Drake", "Taylor Swift", "Ed Sheeran", "Queen", "The Weeknd", "Daft Punk",
     "Billie Eilish", "Imagine Dragons", "Arctic Monkeys", "Bruno Mars", "Hans Zimmer", "Radiohead",
     "Dua Lipa", "Linkin Park", "Fairuz", "Amr Diab", "Kendrick Lamar", "Pink Floyd"],
    ["Muse", "Sia", "Eminem", "Ludovico Einaudi", "Mohammed Abdu", "Gorillaz", "Lorde", "AC/DC"],
)
TRACKS = (
    ["Bohemian Rhapsody", "Blinding Lights", "Yellow", "Shape of You", "Hello", "Believer",
     "Levitating", "Numb", "Get Lucky", "Time", "Bad Guy", "Do I Wanna Know", "Uptown Funk",
     "Someone Like You", "Hotel California", "Viva la Vida"],
    ["Starlight", "Clocks", "Thunderstruck", "Feeling Good", "Nuvole Bianche", "Feel Good Inc"],
)
ALBUMS = (
    ["Abbey Road", "Thriller", "Rumours", "A Night at the Opera", "Random Access Memories",
     "Divide", "25", "Hybrid Theory", "The Dark Side of the Moon", "After Hours"],
    ["Origin of Symmetry", "Back in Black", "Demon Days", "Melodrama"],
)
PLAYLISTS = (
    ["chill vibes", "workout", "focus", "lo-fi beats", "dinner jazz", "morning coffee", "road trip",
     "sleep", "top hits", "classical essentials", "rock classics", "Arabic hits"],
    ["deep focus", "rainy day", "study music", "acoustic covers"],
)
TIMER_LABELS = (
    ["pasta", "eggs", "laundry", "tea", "oven", "pizza", "homework", "break", "rice", "workout"],
    ["bread", "nap", "coffee", "chicken"],
)
QUESTIONS = (
    ["who wrote Romeo and Juliet", "how far away is the moon", "what is the capital of Australia",
     "how many ounces are in a pound", "why is the sky blue", "who won the last World Cup",
     "what's the population of Japan", "explain how vaccines work", "how do I boil an egg",
     "what's fifteen percent of eighty", "tell me a fun fact about octopuses",
     "what's the difference between a virus and bacteria", "how tall is the Burj Khalifa",
     "who invented the telephone", "what does photosynthesis mean", "how many calories are in a banana",
     "translate thank you into French", "what's the latest news", "how do I fix a leaking tap",
     "recommend a good science fiction book", "what's the square root of 144",
     "when did the Second World War end", "how long should I rest between workouts",
     "what's a good recipe for dinner tonight", "search the web for cheap flights to London",
     "what's the exchange rate from dollars to riyals", "who is the richest person in the world",
     "how does a black hole form", "tell me a joke", "write a short poem about the sea"],
    ["who painted the Mona Lisa", "how many bones are in the human body", "what is quantum computing",
     "how do I make hummus", "what time is sunset in Tokyo", "explain the offside rule",
     "who was the first person on the moon", "how hot is the sun", "search for the best laptops this year",
     "what's the meaning of the word serendipity", "tell me a story", "how far is Riyadh from Dubai"],
)

# Templates: (train, eval). {placeholders} are filled per intent.
TEMPLATES = {
    "get_time": (
        ["what time is it", "what's the time", "tell me the time", "time please", "what's the time now",
         "do you know what time it is", "current time", "can you tell me the time", "what time is it now"],
        ["got the time", "how late is it", "what's the time right now"],
    ),
    "get_date": (
        ["what's the date", "what's today's date", "what day is it", "what's the date today",
         "which day is it today", "tell me the date", "what day of the week is it",
         "is today friday", "is it the weekend yet", "what month is it"],
        ["what's the date today please", "is it monday today", "today's date"],
    ),
    "set_timer": (
        ["set a timer for {d}", "timer for {d}", "start a timer for {d}", "set a {d} timer",
         "can you set a timer for {d}", "put a timer on for {d}", "remind me in {d}",
         "set a timer for {d} for the {label}", "{label} timer for {d}", "start a {d} {label} timer",
         "set the {label} timer for {d}", "count down {d}"],
        ["could you time {d} for me", "I need a timer for {d}", "{d} timer please",
         "set up a {label} timer of {d}", "give me {d} on the clock"],
    ),
    "cancel_timer": (
        ["cancel the timer", "stop the timer", "cancel my timer", "delete the timer", "turn off the timer",
         "cancel the {label} timer", "stop the {label} timer", "remove the {label} timer"],
        ["kill the timer", "get rid of the {label} timer", "I don't need the timer anymore"],
    ),
    "timer_status": (
        ["how much time is left", "how long is left on the timer", "check the timer", "timer status",
         "how much time is left on my timer", "is my timer still running"],
        ["how's the timer doing", "how many minutes are left"],
    ),
    "set_alarm": (
        ["set an alarm for {t}", "wake me up at {t}", "alarm at {t}", "set an alarm at {t}",
         "set an alarm for {t} {day}", "wake me up {day} at {t}", "I need an alarm at {t} {day}",
         "can you set an alarm for {t}"],
        ["get me up at {t}", "make an alarm for {t} {day}", "please wake me {day} at {t}"],
    ),
    "cancel_alarm": (
        ["cancel my alarm", "turn off the alarm", "delete the alarm", "cancel the {t} alarm",
         "remove my alarm for {t}", "turn off my {t} alarm"],
        ["I don't need the alarm", "get rid of the {t} alarm"],
    ),
    "get_weather": (
        ["what's the weather", "what's the weather like {day}", "weather {day}", "will it rain {day}",
         "how hot is it going to be {day}", "what's the forecast for {day}", "is it cold outside",
         "what's the weather in {city}", "weather in {city} {day}", "how's the weather in {city}",
         "do I need an umbrella {day}", "what's the temperature outside", "what's the temperature in {city}",
         "how warm is it in {city} {day}", "is it windy {day}", "any rain in {city} {day}"],
        ["what's it like outside", "is it going to be sunny {day}", "forecast for {city} {day}",
         "should I wear a jacket {day}", "temperature in {city}"],
    ),
    "calendar_events": (
        ["what's on my calendar {day}", "what do I have {day}", "do I have any meetings {day}",
         "what's my schedule {day}", "any events {day}", "what's on my agenda {day}", "am I busy {day}"],
        ["what have I got on {day}", "read me my calendar for {day}", "anything planned {day}"],
    ),
    "spotify_play_track": (
        ["play {track}", "play the song {track}", "play {track} by {artist}", "put on {track}",
         "can you play {track}", "I want to hear {track}"],
        ["play me {track}", "queue up {track} by {artist}"],
    ),
    "spotify_play_artist": (
        ["play {artist}", "play some {artist}", "play music by {artist}", "put on some {artist}",
         "I want to listen to {artist}", "play songs by {artist}"],
        ["let's hear some {artist}", "shuffle {artist}"],
    ),
    "spotify_play_album": (
        ["play the album {album}", "play {album} album", "put on the album {album}",
         "play the album {album} by {artist}"],
        ["I want the album {album}", "start the {album} album"],
    ),
    "spotify_play_playlist": (
        ["play my {playlist} playlist", "play the {playlist} playlist", "put on some {playlist} music",
         "play {playlist} playlist on spotify", "start my {playlist} playlist"],
        ["shuffle the {playlist} playlist", "I want my {playlist} playlist"],
    ),
    "media_pause": (["pause", "pause the music", "pause it", "hold the music", "pause spotify"],
                    ["pause playback", "freeze the song"]),
    "media_resume": (["resume", "resume the music", "continue playing", "unpause", "play again", "keep playing"],
                     ["carry on playing", "start the music again"]),
    "media_next": (["next song", "skip", "skip this song", "next track", "play the next one", "skip this",
                    "skip it", "skip that one", "move on to the next song", "change the song"],
                   ["next one please", "I don't like this song skip it"]),
    "media_previous": (["previous song", "go back", "play the last song again", "previous track", "back one song",
                        "play the one before", "go back to the last song", "the previous one please"],
                       ["the song before", "go back a track"]),
    "media_stop": (["stop the music", "stop playing", "stop spotify", "turn off the music", "stop the song",
                    "stop", "music off", "no more music"],
                   ["enough music", "kill the music"]),
    "set_volume": (["set the volume to {n}", "volume {n}", "volume to {n} percent", "turn the volume to {n}",
                    "change the volume to {n}", "set volume at {n} percent"],
                   ["make the volume {n}", "put the volume on {n}"]),
    "volume_up": (["turn it up", "volume up", "louder", "turn up the volume", "make it louder", "increase the volume"],
                  ["a bit louder please", "I can't hear it turn it up"]),
    "volume_down": (["turn it down", "volume down", "quieter", "turn down the volume", "make it quieter",
                     "lower the volume"],
                    ["a bit quieter please", "too loud turn it down"]),
    "screen_off": (["turn off the screen", "screen off", "turn the display off", "switch off the screen"],
                   ["blank the screen", "kill the display"]),
    "screen_on": (["turn on the screen", "screen on", "wake up the screen", "turn the display on"],
                  ["light up the screen", "switch the display on"]),
    "mute_mic": (["mute the microphone", "stop listening", "mute your mic", "turn off the microphone",
                  "privacy mode"],
                 ["don't listen for a while", "switch off your mic"]),
    "night_mode_on": (["turn on night mode", "night mode", "dim the screen for the night", "enable night mode"],
                      ["go into night mode", "switch to night mode"]),
    "night_mode_off": (["turn off night mode", "disable night mode", "exit night mode", "day mode"],
                       ["leave night mode", "switch back to day mode"]),
    "ask_cloud": (["{q}", "can you tell me {q}", "I have a question {q}", "{q} please", "quick question {q}"],
                  ["{q}", "do you know {q}", "help me with this {q}"]),
}

# Short spoken replies. (utterances_train, utterances_eval, replies)
SMALL_TALK = {
    "greeting": (["hello", "hi", "hey", "good morning", "good evening", "hi jarvis", "hello there", "hey there"],
                 ["morning", "yo jarvis", "greetings"],
                 ["Hello. How can I help?", "Hello, sir. What can I do for you?", "Good to hear from you. How can I help?"]),
    "thanks": (["thank you", "thanks", "thanks a lot", "cheers", "thank you jarvis", "perfect thanks"],
               ["much appreciated", "thanks mate", "great thank you"],
               ["You're welcome.", "My pleasure.", "Happy to help."]),
    "identity": (["who are you", "what's your name", "what are you", "what can you do", "are you a robot",
                  "introduce yourself"],
                 ["what should I call you", "tell me about yourself", "what are you able to do"],
                 ["I'm Jarvis, your home assistant. I can handle timers, alarms, weather, your calendar and music.",
                  "I'm Jarvis. Ask me about timers, alarms, weather, your calendar or music."]),
    "never_mind": (["never mind", "nothing", "forget it", "cancel", "ignore that", "nothing never mind",
                    "oops", "my mistake", "I didn't mean to say that", "pressed it by accident", "not you"],
                   ["no it's fine", "sorry wrong button", "oh forget about it"],
                   ["Very well.", "Of course.", "No problem."]),
    "how_are_you": (["how are you", "how's it going", "how are you doing", "you alright"],
                    ["how are things", "how have you been"],
                    ["All systems running smoothly, thank you.", "Very well, thank you. How can I help?"]),
}

# Intent weights for sampling (relative).
WEIGHTS = {
    "get_time": 4, "get_date": 5, "set_timer": 16, "cancel_timer": 4, "timer_status": 3, "set_alarm": 10,
    "cancel_alarm": 3, "get_weather": 11, "calendar_events": 5, "spotify_play_track": 5,
    "spotify_play_artist": 5, "spotify_play_album": 3, "spotify_play_playlist": 5, "media_pause": 2,
    "media_resume": 2, "media_next": 4, "media_previous": 3, "media_stop": 3, "set_volume": 3,
    "volume_up": 2, "volume_down": 2, "screen_off": 2, "screen_on": 1, "mute_mic": 2, "night_mode_on": 1,
    "night_mode_off": 1, "ask_cloud": 12, "greeting": 2, "thanks": 2, "identity": 2, "never_mind": 4,
    "how_are_you": 1,
}

SIMPLE = {
    "media_pause": ("media_control", {"action": "pause"}), "media_resume": ("media_control", {"action": "resume"}),
    "media_next": ("media_control", {"action": "next"}), "media_previous": ("media_control", {"action": "previous"}),
    "media_stop": ("media_control", {"action": "stop"}), "volume_up": ("change_volume", {"direction": "up"}),
    "volume_down": ("change_volume", {"direction": "down"}),
    "screen_off": ("device_control", {"action": "screen_off"}), "screen_on": ("device_control", {"action": "screen_on"}),
    "mute_mic": ("device_control", {"action": "mute_mic"}),
    "night_mode_on": ("device_control", {"action": "night_mode_on"}),
    "night_mode_off": ("device_control", {"action": "night_mode_off"}),
    "get_time": ("get_time", {}), "get_date": ("get_date", {}), "timer_status": ("timer_status", {}),
}

# Template-level slips seen from whisper or likely from it.
ASR_SLIPS = [("a timer for", "a time of"), ("timer for", "timer of"), ("weather", "whether"),
             ("pause", "paws"), ("next song", "next on"), ("louder", "lauder"), ("alarm", "alarms")]


def duration(rng):
    """(spoken text, unit arguments). Units are copied as said, never converted."""
    kind = rng.choice(["sec", "min", "min", "min", "hour", "combo", "hour_combo", "phrase"])
    if kind == "sec":
        n = rng.choice([5, 10, 15, 20, 30, 40, 45, 60, 90, 120])
        return f"{say_number(rng, n)} {rng.choice(['seconds', 'seconds', 'secs'])}", {"seconds": n}
    if kind == "min":
        n = rng.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 18, 20, 25, 30, 35, 40, 45, 50, 60, 75, 90, 100])
        unit = "minute" if n == 1 else rng.choice(["minutes", "minutes", "mins"])
        return f"{'a' if n == 1 and rng.random() < 0.5 else say_number(rng, n)} {unit}", {"minutes": n}
    if kind == "hour":
        n = rng.choice([1, 2, 3, 4, 5, 6, 8, 12])
        unit = "hour" if n == 1 else "hours"
        return f"{'an' if n == 1 and rng.random() < 0.5 else say_number(rng, n)} {unit}", {"hours": n}
    if kind == "combo":
        m, s = rng.choice([1, 2, 3, 4, 5, 6, 8, 10, 12, 15]), rng.choice([10, 15, 20, 30, 45])
        joiner = rng.choice([" and ", " "])
        return (f"{say_number(rng, m)} minute{'s' if m > 1 else ''}{joiner}{say_number(rng, s)} seconds",
                {"minutes": m, "seconds": s})
    if kind == "hour_combo":
        h, m = rng.choice([1, 2, 3]), rng.choice([5, 10, 15, 20, 30, 40, 45])
        joiner = rng.choice([" and ", " "])
        return (f"{say_number(rng, h)} hour{'s' if h > 1 else ''}{joiner}{say_number(rng, m)} minutes",
                {"hours": h, "minutes": m})
    return rng.choice([
        ("half an hour", {"minutes": 30}), ("an hour and a half", {"hours": 1, "minutes": 30}),
        ("a minute and a half", {"minutes": 1, "seconds": 30}), ("quarter of an hour", {"minutes": 15}),
        ("two and a half minutes", {"minutes": 2, "seconds": 30}), ("a couple of minutes", {"minutes": 2}),
        ("two and a half hours", {"hours": 2, "minutes": 30}), ("half a minute", {"seconds": 30}),
        ("three quarters of an hour", {"minutes": 45}),
    ])


def clock_time(rng):
    """(spoken text, "HH:MM")."""
    h = rng.randint(1, 12)
    m = rng.choice([0, 0, 0, 15, 30, 45, rng.randint(1, 59)])
    pm = rng.random() < 0.4
    h24 = (h % 12) + (12 if pm else 0)
    style = rng.random()
    if style < 0.45:
        clock = f"{h}" if m == 0 else f"{h}:{m:02d}"
        text = f"{clock} {'pm' if pm else 'am'}" if rng.random() < 0.6 else f"{clock} {'p.m.' if pm else 'a.m.'}"
    elif style < 0.75:
        words = number_words(h) + ("" if m == 0 else " " + ("oh " + number_words(m) if m < 10 else number_words(m)))
        part = "in the evening" if pm and h >= 6 else "in the afternoon" if pm else "in the morning"
        text = f"{words} {part}"
    else:
        if m not in (15, 30):
            m = 30
            h24 = (h % 12) + (12 if pm else 0)
        text = f"{'half' if m == 30 else 'quarter'} past {h} {'pm' if pm else 'am'}"
    return text, f"{h24:02d}:{m:02d}"


def pick(rng, pool, split):
    return rng.choice(pool[1] if split == "eval" else pool[0])


def build(rng, intent, split):
    """Return (utterance template filled, assistant text, copied_args) for one intent.

    copied_args lists argument keys whose values are copied from the utterance text,
    so the casing noise can be applied to them too.
    """
    if intent in SMALL_TALK:
        train_u, eval_u, replies = SMALL_TALK[intent]
        return rng.choice(eval_u if split == "eval" else train_u), rng.choice(replies), None, None

    template = pick(rng, TEMPLATES[intent], split)
    if rng.random() < 0.12:
        a, b = rng.choice(ASR_SLIPS)
        template = template.replace(a, b)

    if intent in SIMPLE:
        name, args = SIMPLE[intent]
        return template, None, name, dict(args)
    if intent == "set_timer":
        text, args = duration(rng)
        label = pick(rng, TIMER_LABELS, split)
        if "{label}" in template:
            args["label"] = label
        return template.format(d=text, label=label), None, "set_timer", args
    if intent == "cancel_timer":
        label = pick(rng, TIMER_LABELS, split)
        args = {"label": label} if "{label}" in template else {}
        return template.format(label=label), None, "cancel_timer", args
    if intent == "set_alarm":
        text, hhmm = clock_time(rng)
        day = rng.choice(["today", "tomorrow", "tomorrow", "monday", "friday", "saturday", "sunday"])
        args = {"time": hhmm}
        if "{day}" in template:
            args["day"] = day
        return template.format(t=text, day=day), None, "set_alarm", args
    if intent == "cancel_alarm":
        text, hhmm = clock_time(rng)
        args = {"time": hhmm} if "{t}" in template else {}
        return template.format(t=text), None, "cancel_alarm", args
    if intent in ("get_weather", "calendar_events"):
        day = rng.choice(DAYS[:2] * 3 + DAYS[2:])
        city = pick(rng, CITIES, split)
        args = {"day": day if "{day}" in template else "today"}
        if "{city}" in template:
            args["location"] = city
        return template.format(day=day, city=city), None, intent, args
    if intent.startswith("spotify_play_"):
        kind = intent.removeprefix("spotify_play_")
        artist, track = pick(rng, ARTISTS, split), pick(rng, TRACKS, split)
        album, playlist = pick(rng, ALBUMS, split), pick(rng, PLAYLISTS, split)
        query = {"track": track, "artist": artist, "album": album, "playlist": playlist}[kind]
        if kind in ("track", "album") and "{artist}" in template:
            query = f"{query} {artist}"
        filled = template.format(track=track, artist=artist, album=album, playlist=playlist)
        return filled, None, "spotify_play", {"query": query, "kind": kind}
    if intent == "set_volume":
        n = rng.choice([10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90, 100])
        return template.format(n=say_number(rng, n)), None, "set_volume", {"level": n}
    if intent == "ask_cloud":
        q = pick(rng, QUESTIONS, split)
        filled = template.format(q=q)
        return filled, None, "ask_cloud", {"question": filled}
    raise ValueError(intent)


COPIED = {"label", "location", "query", "question"}


def clean(text):
    """Lowercase and drop sentence punctuation, the way short whisper outputs often look."""
    return re.sub(r"[.,?!]", "", text.lower()).strip()


def finish(text):
    text = text[0].upper() + text[1:]
    return text + ("?" if text.split()[0].lower() in {"what", "what's", "who", "how", "why", "when", "is",
                                                      "do", "will", "can", "could", "am", "are"} else ".")


def example(rng, intent, split):
    filled, reply, name, args = build(rng, intent, split)
    lower = rng.random() < 0.5
    wake = rng.random() < 0.3
    utterance = clean(filled) if lower else finish(filled)
    if wake:
        utterance = (rng.choice(["hey jarvis ", "jarvis "]) + utterance if lower
                     else rng.choice(["Hey Jarvis, ", "Jarvis, "]) + utterance[0].lower() + utterance[1:])
    if name is None:
        return {"intent": intent, "messages": messages(utterance, reply)}
    for key in COPIED & args.keys():
        if key == "question":
            # the question is the request itself, without the wake word
            args[key] = clean(filled) if lower else finish(filled)
        elif lower:
            args[key] = clean(args[key])
    return {"intent": intent, "messages": messages(utterance, tool_call(name, **args))}


def sample(rng, n, split):
    intents, weights = zip(*WEIGHTS.items())
    rows, seen = [], set()
    while len(rows) < n:
        row = example(rng, rng.choices(intents, weights)[0], split)
        key = row["messages"][1]["content"]
        if key in seen and rng.random() < 0.8:
            continue  # keep a few duplicates, but mostly distinct utterances
        seen.add(key)
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--train", type=int, default=6000)
    ap.add_argument("--val", type=int, default=300)
    ap.add_argument("--eval", type=int, default=400)
    ap.add_argument("--out", default=str(Path(__file__).parent / "data"))
    a = ap.parse_args()

    rng = random.Random(a.seed)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    train = sample(rng, a.train + a.val, "train")
    splits = {"train": train[:a.train], "val": train[a.train:], "eval": sample(rng, a.eval, "eval")}
    for name, rows in splits.items():
        with open(out / f"{name}.jsonl", "w") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{name}: {len(rows)} rows -> {out / f'{name}.jsonl'}")


if __name__ == "__main__":
    main()
