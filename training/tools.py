"""Tool schema and prompt format shared by the dataset, the notebook and the assistant.

The model never sees this schema at runtime: it learns the tools from the training data,
so the system prompt stays short (prompt processing is ~20 tokens/s on the tablet).
The model answers with exactly one of:
  - a tool call:   <tool_call>{"name": ..., "arguments": {...}}</tool_call>
  - a short spoken reply (greetings, thanks, questions about Jarvis itself)
Skills produce their own spoken confirmation, so there is no second LLM pass.
"""

import json

SYSTEM_PROMPT = "You are Jarvis, a home voice assistant. Reply with one tool call or one short sentence."

DAYS = ["today", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# name -> {argument: description}. Optional arguments are marked with "?".
TOOLS = {
    "get_time": {},
    "get_date": {},
    "set_timer": {"seconds": "int, total duration", "label?": "str"},
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


def tool_call(name, **arguments):
    """The exact assistant text for a tool call. Keys are sorted so the format is stable."""
    assert name in TOOLS, name
    payload = {"name": name, "arguments": arguments}
    return "<tool_call>" + json.dumps(payload, sort_keys=True, ensure_ascii=False) + "</tool_call>"


def parse_reply(text):
    """Turn model output into ("tool", name, arguments) or ("say", text, None).

    Returns ("invalid", text, None) when a tool call is present but is not valid JSON
    or names an unknown tool.
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
    if name not in TOOLS or not isinstance(arguments, dict):
        return ("invalid", text, None)
    return ("tool", name, arguments)


def messages(user_text, assistant_text):
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": assistant_text},
    ]
