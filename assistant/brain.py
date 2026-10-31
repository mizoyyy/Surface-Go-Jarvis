"""Turns one transcribed request into a tool call or a short reply.

A few very common commands are matched by regex (no model call, instant). Everything else
goes to the fine-tuned model on llama-server. The prompt format, tool schema and parser are
shared with training (training/tools.py), so the assistant sees exactly what the model learned.
"""

import difflib
import re
import sys

import httpx

from . import config
from .skills import prayer

sys.path.insert(0, str(config.REPO / "training"))
from tools import SYSTEM_PROMPT, TOOLS, parse_reply, validate  # noqa: E402

WAKE = re.compile(r"^\W*(hey|hi|ok|okay)?\W*jarvis\W*", re.I)

FAST = [
    (r"(what('s| is) the time|what time is it)( now)?", "get_time", {}),
    (r"(stop|pause)( the)?( music| song| playback)?", "media_control", {"action": "pause"}),
    (r"(resume|continue|unpause)( the)?( music| song| playback)?", "media_control", {"action": "resume"}),
    (r"(next|skip)( song| track| this( song)?)?", "media_control", {"action": "next"}),
    (r"(volume up|louder|turn it up)", "change_volume", {"direction": "up"}),
    (r"(volume down|quieter|softer|turn it down)", "change_volume", {"direction": "down"}),
    (r"(set( the)? )?volume( to)? (\d{1,3})( percent|%)?", "set_volume", None),
    (r"(open|show)( me)?( the| your| my)? settings", "show_settings", {"open": True}),
    (r"(close|hide)( the| your| my)? settings", "show_settings", {"open": False}),
    (r"(close|exit|quit|hide|minimi[sz]e)( the)?( jarvis| display| app| screen| window)|(go|back) to( the)? desktop",
     "close_display", {}),
    (r"(shut down|shutdown|turn off|switch off|power off) jarvis( completely)?|(shut|turn) yourself off",
     "stop_jarvis", {}),
]
FAST = [(re.compile(rf"^{pattern}$", re.I), name, args) for pattern, name, args in FAST]

# General questions skip the local model (3 to 4 s on the tablet) and go straight online,
# unless they mention anything a local tool or Jarvis itself would answer
QUESTION = re.compile(
    r"^(what|who|why|how|when|where|which|whose|explain|define|describe|tell me|find|search|look up|"
    r"using the|use the|do you know|can you tell me|calculate|translate|is|are|was|were|does|did)\b", re.I)
LOCAL = re.compile(
    r"\b(time|date|day|today|tonight|tomorrow|morning|timers?|alarms?|wake me|remind|weather|rain(s|y|ing|fall)?|"
    r"temperature|hot|cold|sunny|cloudy|forecast|wind\w*|humid\w*|umbrella|calendar|schedule|meetings?|"
    r"appointments?|events?|agenda|busy|play\w*|music|songs?|tracks?|album|artist|spotify|pause|resume|"
    r"skip|volume|louder|quieter|mute|screen|night mode|mic|microphone|you|your|yourself|jarvis|my|i|our)\b", re.I)


# with music playing in the room tiny.en mishears short commands: "toss music", "tause music",
# "pause me". Only while music was playing, close matches count as these.
MUSIC_PHRASES = {
    "pause music": "pause", "pause the music": "pause", "stop music": "pause", "stop the music": "pause",
    "pause": "pause", "stop": "pause", "pause it": "pause", "resume music": "resume",
    "next song": "next", "skip song": "next", "skip this song": "next", "previous song": "previous",
}


def music_command(text):
    clean = re.sub(r"[^\w\s']", "", strip_wake(text)).strip().lower()
    if not clean or len(clean.split()) > 4 or clean.startswith("play"):
        return None
    match = difflib.get_close_matches(clean, MUSIC_PHRASES, n=1, cutoff=0.7)
    return ("media_control", {"action": MUSIC_PHRASES[match[0]]}) if match else None


def strip_wake(text):
    return WAKE.sub("", text).strip()


def fast_path(text):
    clean = re.sub(r"[^\w\s%]", "", strip_wake(text)).strip()
    clean = re.sub(r"^(please |can you |could you )|( please| now)$", "", clean, flags=re.I).strip()
    for pattern, name, args in FAST:
        m = pattern.match(clean)
        if m:
            if name == "set_volume":
                args = {"level": min(100, int(m.group(4)))}
            return name, dict(args)
    return None


def chatml(user_text):
    return (f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
            f"<|im_start|>user\n{user_text}<|im_end|>\n<|im_start|>assistant\n")


def ask_model(text):
    r = httpx.post(config.LLM_URL + "/completion", timeout=60, json={
        "prompt": chatml(text), "n_predict": 80, "temperature": 0,
        "cache_prompt": True, "stop": ["<|im_end|>"]})
    r.raise_for_status()
    return r.json()["content"].strip()


def warm_up():
    """Fills llama-server's prompt cache with the system prompt."""
    ask_model("hello")


def decide(text, music_playing=False):
    """Returns ("tool", name, args) or ("say", text, None)."""
    fast = fast_path(text) or (music_playing and music_command(text)) or prayer.asked(strip_wake(text))
    if fast:
        return ("tool", *fast)
    question = strip_wake(text)
    if QUESTION.match(question) and not LOCAL.search(question) and len(question.split()) >= 3:
        return ("tool", "ask_cloud", {"question": question})
    kind, value, args = parse_reply(ask_model(text))
    if kind == "invalid":
        name = re.search(r'"name"\s*:\s*"(\w+)"', value)
        if name and name.group(1) in TOOLS and name.group(1) != "ask_cloud":
            # a local tool with arguments it couldn't fill ("set an alarm for now"): the cloud
            # can't set alarms either, so ask again
            return ("say", "Sorry, I didn't get the details. Could you say that again?", None)
        # the model reached for a tool but got it wrong: let the cloud answer instead
        return ("tool", "ask_cloud", {"question": strip_wake(text)})
    return kind, value, args


__all__ = ["decide", "fast_path", "strip_wake", "validate", "warm_up"]
