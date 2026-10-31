"""Speaker volume (PipeWire through pactl) and the screen (X11 DPMS)."""

import os
import re
import subprocess

SINK = "@DEFAULT_SINK@"


def _run(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=5,
                          env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")})


def get_volume():
    out = _run("pactl", "get-sink-volume", SINK).stdout
    m = re.search(r"(\d+)%", out)
    return int(m.group(1)) if m else None


def set_volume(level):
    level = max(0, min(100, int(level)))
    _run("pactl", "set-sink-mute", SINK, "0")
    _run("pactl", "set-sink-volume", SINK, f"{level}%")
    return level


def change_volume(direction, step=10):
    current = get_volume() or 50
    return set_volume(current + step if direction == "up" else current - step)


def screen(on):
    _run("xset", "dpms", "force", "on" if on else "off")
    if on:
        _run("xset", "s", "reset")
