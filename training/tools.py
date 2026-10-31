"""Tool schema and prompt format shared by the dataset, the notebook and the assistant.

The model never sees this schema at runtime: it learns the tools from the training data,
so the system prompt stays short (prompt processing is ~20 tokens/s on the tablet).
The model answers with exactly one of:
  - a tool call:   <tool_call>{"name":...,"arguments":{...}}</tool_call>
  - a short spoken reply (greetings, thanks, questions about Jarvis itself)
Skills produce their own spoken confirmation, so there is no second LLM pass.
"""

import json
import re

SYSTEM_PROMPT = "You are Jarvis, a home voice assistant. Reply with one tool call or one short sentence."

DAYS = ["today", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# name -> {argument: description}. Optional arguments are marked with "?".
TOOLS = {
    "get_time": {},
    "get_date": {},
    # units copied from the request ("an hour and a half" -> hours 1, minutes 30); the skill adds them up
    "set_timer": {"hours?": "int", "minutes?": "int", "seconds?": "int", "label?": "str"},
    "cancel_timer": {"label?": "str"},
    "timer_status": {},
    "set_alarm": {"time": "HH:MM, 24-hour", "day?": "one of DAYS"},
    "cancel_alarm": {"time?": "HH:MM, 24-hour"},
    "get_weather": {"day": "one of DAYS", "location?": "str, only if the user names a place"},
    "calendar_events": {"day": "one of DAYS"},
    "spotify_play": {"query": "str", "kind": "track | artist | album | playlist"},
    "media_control": {"action": "pause | resume | next | previous | stop"},
    "set_volume": {"level": "int 0-100"},
    "change_volume": {"direction": "up | down"},
    "device_control": {"action": "screen_off | screen_on | mute_mic | night_mode_on | night_mode_off"},
    "ask_cloud": {"question": "str, the user's request, for anything the tools above cannot answer"},
}


# Allowed values for enum-like arguments. Anything else is an invalid call.
ENUMS = {
    ("spotify_play", "kind"): {"track", "artist", "album", "playlist"},
    ("media_control", "action"): {"pause", "resume", "next", "previous", "stop"},
    ("change_volume", "direction"): {"up", "down"},
    ("device_control", "action"): {"screen_off", "screen_on", "mute_mic", "night_mode_on", "night_mode_off"},
    ("get_weather", "day"): set(DAYS),
    ("calendar_events", "day"): set(DAYS),
    ("set_alarm", "day"): set(DAYS),
}
TIMER_UNITS = ("hours", "minutes", "seconds")


def tool_call(name, **arguments):
    """The exact assistant text for a tool call.

    The name comes first so the model picks the tool before filling in arguments;
    arguments keep a fixed (sorted) order and the JSON has no spaces, to keep generation short.
    """
    assert validate(name, arguments), (name, arguments)
    body = json.dumps(dict(sorted(arguments.items())), separators=(",", ":"), ensure_ascii=False)
    return f'<tool_call>{{"name":"{name}","arguments":{body}}}</tool_call>'


def validate(name, arguments):
    """True when the tool exists and every argument is known, required ones present, enums valid."""
    if name not in TOOLS or not isinstance(arguments, dict):
        return False
    spec = TOOLS[name]
    known = {k.rstrip("?") for k in spec}
    required = {k for k in spec if not k.endswith("?")}
    if not required <= arguments.keys() or not arguments.keys() <= known:
        return False
    for key, value in arguments.items():
        allowed = ENUMS.get((name, key))
        if allowed is not None and value not in allowed:
            return False
        if name == "set_timer" and key in TIMER_UNITS and not (isinstance(value, int) and value >= 0):
            return False
        if key == "time" and not (isinstance(value, str) and re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", value)):
            return False
    if name == "set_timer" and timer_seconds(arguments) <= 0:
        return False
    return True


def timer_seconds(arguments):
    return (arguments.get("hours", 0) * 3600 + arguments.get("minutes", 0) * 60
            + arguments.get("seconds", 0))


def parse_reply(text):
    """Turn model output into ("tool", name, arguments) or ("say", text, None).

    Returns ("invalid", text, None) when a tool call is present but is not valid JSON
    or fails validate().
    """
    text = text.strip()
    start = text.find("<tool_call>")
    if start == -1:
        return ("say", text, None)
    end = text.find("</tool_call>", start)
    body = text[start + len("<tool_call>"):end if end != -1 else None].strip()
    try:
        payload = json.loads(body)
        name, arguments = payload["name"], payload.get("arguments", {})
    except (ValueError, KeyError, TypeError):
        return ("invalid", text, None)
    if not validate(name, arguments):
        return ("invalid", text, None)
    return ("tool", name, arguments)


def messages(user_text, assistant_text):
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": assistant_text},
    ]
