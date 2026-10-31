"""Runs one tool call and returns the sentence Jarvis says back."""

import datetime as dt

import httpx

from . import cloud, system
from .common import DAY_NAMES, say_time
from .spotify import NotConnected


def get_time():
    return f"It's {say_time(dt.datetime.now())}."


def get_date():
    today = dt.date.today()
    return f"It's {DAY_NAMES[today.weekday()].capitalize()}, {today.strftime('%B')} {today.day}."


def run(jarvis, name, args):
    """`jarvis` is the running core (timers, calendar, spotify, screen and mic state)."""
    try:
        return _run(jarvis, name, args)
    except NotConnected:
        return "Spotify isn't connected yet. You can connect it in the settings."
    except httpx.HTTPError:
        return "I couldn't reach that service right now."
    except (ValueError, KeyError, TypeError):
        return "Sorry, I didn't get that."


def _run(jarvis, name, args):
    timers, spotify = jarvis.timers, jarvis.spotify
    if name == "get_time":
        return get_time()
    if name == "get_date":
        return get_date()
    if name in ("set_timer", "cancel_timer", "timer_status", "set_alarm", "cancel_alarm"):
        return getattr(timers, name)(**args)
    if name == "get_weather":
        from .weather import get_weather
        return get_weather(**args)
    if name == "calendar_events":
        return jarvis.calendar.calendar_events(**args)
    if name == "spotify_play":
        return spotify.play(args["query"], args["kind"])
    if name == "media_control":
        if not spotify.connected:
            raise NotConnected
        ok = spotify.control(args["action"])
        return "" if ok else "Nothing is playing on Spotify."
    if name == "set_volume":
        level = system.set_volume(args["level"])
        return f"Volume {level}."
    if name == "change_volume":
        system.change_volume(args["direction"])
        return ""  # the chime at the new volume is the answer
    if name == "device_control":
        return jarvis.device_control(args["action"])
    if name == "prayer_times":
        from .prayer import prayer_times
        return prayer_times(**args, timers=timers)
    if name in ("close_display", "stop_jarvis"):
        jarvis.closing = name
        return ("Closing the display. Tap the Jarvis icon to bring it back." if name == "close_display"
                else "Turning off. Tap the Jarvis icon to start me again.")
    if name == "show_settings":
        jarvis.emit("show_settings", args["open"])
        return ""
    if name == "ask_cloud":
        return cloud.ask_cloud(args["question"])
    return "I can't do that yet."
