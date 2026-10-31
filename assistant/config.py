"""Paths, ports and user settings.

Settings the user changes from the wall UI live in ~/.config/jarvis/settings.json.
Secrets (API keys, Spotify tokens) live next to them in secrets.json (mode 600) and are
never sent to the UI.
"""

import copy
import json
import os
import pathlib
import threading

REPO = pathlib.Path(__file__).resolve().parent.parent
HOME = pathlib.Path(os.environ.get("JARVIS_HOME", pathlib.Path.home() / "jarvis"))
MODELS = HOME / "models"
CONFIG_DIR = pathlib.Path(os.environ.get("JARVIS_CONFIG", pathlib.Path.home() / ".config" / "jarvis"))

LLM_MODEL = MODELS / "llm" / "jarvis-0.5b-v2-q4_0.gguf"
WHISPER_MODEL = MODELS / "whisper" / "ggml-tiny.en-q8_0.bin"
WAKE_DIR = MODELS / "wakeword"
PIPER_DIR = MODELS / "piper"
RECORDINGS = pathlib.Path.home() / ".cache" / "jarvis" / "recordings"

LLM_URL = "http://127.0.0.1:8091"
STT_URL = "http://127.0.0.1:8092"
UI_HOST, UI_PORT = "127.0.0.1", 8000

DEFAULTS = {
    "location": {"name": "Dhahran", "latitude": 26.2361, "longitude": 50.0393},
    "units": "metric",
    "voice": "en_GB-alan-medium",
    "wake_threshold": 0.5,
    "widgets": ["clock", "weather", "timers", "calendar", "music"],
    "night_mode": {"auto": True, "start": "22:00", "end": "07:00"},
    "calendar_ics_url": "",
    "cloud": {"enabled": True, "model": "gemini-flash-latest", "effort": "low", "web_search": True},
    "spotify": {"client_id": "", "device_name": ""},
}


def _merge(base, override):
    out = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


class Store:
    """A JSON file with defaults, saved atomically on every change."""

    def __init__(self, path, defaults=None, private=False):
        self.path, self.defaults, self.private = path, defaults or {}, private
        self.lock = threading.Lock()
        try:
            self.data = _merge(self.defaults, json.loads(path.read_text()))
        except (FileNotFoundError, ValueError):
            self.data = copy.deepcopy(self.defaults)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update(self, changes):
        with self.lock:
            self.data = _merge(self.data, changes)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=2))
            if self.private:
                tmp.chmod(0o600)
            tmp.replace(self.path)
        return self.data


settings = Store(CONFIG_DIR / "settings.json", DEFAULTS)
secrets = Store(CONFIG_DIR / "secrets.json", private=True)
state_file = Store(CONFIG_DIR / "state.json")
