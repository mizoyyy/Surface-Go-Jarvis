"""The running assistant: mic loop, request handling, timers, and state for the UI.

Threads: one reads the mic and runs wake word + endpointing (cheap, every 80 ms); requests
are handled one at a time on a worker thread (STT, model, skill, speech). The asyncio loop
only serves the UI and runs periodic refreshes.
"""

import asyncio
import datetime as dt
import logging
import queue
import re
import threading
import time
import traceback

from . import audio, brain, config, skills, speech
from .skills import cloud, system
from .skills.calendar import Calendar
from .skills.spotify import NotConnected, Spotify
from .skills.timers import Timers
from .skills.weather import home_forecast

log = logging.getLogger("jarvis")

STARTED = time.time()  # the UI reloads when this changes, to pick up new code after a restart
STOP_WORDS = re.compile(r"\b(stop|cancel|dismiss|enough|okay|ok|thanks|thank you|quiet|shut up|snooze)\b", re.I)


class Jarvis:
    def __init__(self):
        self.loop = None
        self.clients = set()
        self.state = "starting"  # idle | listening | thinking | speaking | ringing | muted
        self.mic_muted = False
        self.night = False
        self.night_override = None  # set by voice / UI until the next scheduled switch
        self.screen_off = False
        self.listen_request = False  # tap on the logo: listen without the wake word
        self.ringing = None
        self.transcript = []
        self.weather = None
        self.music = None
        self.player = audio.Player()
        self.voice = None
        self.wake = None
        self.requests = queue.Queue()
        self.timers = Timers(on_change=lambda snap: self.emit("timers", snap), on_ring=self.ring)
        self.calendar = Calendar()
        self.spotify = Spotify()

    # UI events

    def emit(self, kind, data):
        msg = {"type": kind, "data": data}
        if self.loop:
            self.loop.call_soon_threadsafe(self._broadcast, msg)

    def _broadcast(self, msg):
        for ws in list(self.clients):
            asyncio.ensure_future(self._send(ws, msg))

    async def _send(self, ws, msg):
        try:
            await ws.send_json(msg)
        except Exception:
            self.clients.discard(ws)

    def set_state(self, state):
        if self.mic_muted and state == "idle":
            state = "muted"
        if self.ringing and state == "idle":
            state = "ringing"
        self.state = state
        self.emit("state", state)

    def snapshot(self):
        public = dict(config.settings.data)
        return {
            "started": STARTED, "state": self.state, "night": self.night, "mic_muted": self.mic_muted,
            "timers": self.timers.snapshot(), "weather": self.weather, "music": self.music,
            "calendar": self.calendar.upcoming() if self.calendar.events else [],
            "transcript": self.transcript[-6:], "ringing": self.ringing,
            "settings": public,
            "status": {"cloud_key": bool(cloud.api_key()), "spotify_connected": self.spotify.connected,
                       "volume": system.get_volume()},
        }

    def add_transcript(self, who, text):
        if not text:
            return
        entry = {"who": who, "text": text, "at": time.time()}
        self.transcript = (self.transcript + [entry])[-20:]
        self.emit("transcript", entry)

    # startup

    def start(self, loop):
        self.loop = loop
        threading.Thread(target=self._load_and_listen, name="mic", daemon=True).start()
        threading.Thread(target=self._worker, name="worker", daemon=True).start()
        loop.create_task(self._every(1, self._tick))
        loop.create_task(self._every(60, self._night_check))
        loop.create_task(self._every(900, self._refresh_weather))
        loop.create_task(self._every(900, self._refresh_calendar))
        loop.create_task(self._every(5, self._refresh_music))

    async def _every(self, seconds, fn):
        while True:
            try:
                await asyncio.to_thread(fn)
            except Exception as e:
                log.warning("%s failed: %s", getattr(fn, "__name__", fn), e)
            await asyncio.sleep(seconds)

    def _tick(self):
        if self.state != "starting":  # nothing can ring before the voice is loaded
            self.timers.tick()

    def _load_and_listen(self):
        from .wakeword import WakeWord

        self.voice = speech.Voice(self.player)
        self.wake = WakeWord(config.WAKE_DIR)
        self.chime = audio.chime(self.voice.rate)
        for attempt in range(60):
            try:
                brain.warm_up()
                break
            except Exception:
                time.sleep(2)  # llama-server is still loading
        self.set_state("idle")
        log.info("ready")
        while True:
            try:
                self._listen()
            except Exception:
                log.error("mic loop crashed:\n%s", traceback.format_exc())
                time.sleep(2)

    def _listen(self):
        mic = audio.Mic()
        endpoint = audio.Endpointer()
        recording = False
        cooldown = 0
        try:
            for chunk in mic.chunks():
                if recording:
                    self.emit("level", round(audio.level_db(chunk), 1))
                    result = endpoint.feed(chunk)
                    if result is not None:
                        recording = False
                        self.wake.reset()
                        cooldown = 12
                        if len(result):
                            self.requests.put(("audio", result))
                        else:
                            self.set_state("idle")
                    continue
                speaking = self.voice.speaking.is_set()
                if not speaking:
                    endpoint.track_noise(chunk)
                score = self.wake.process(chunk)
                if cooldown:
                    cooldown -= 1
                    continue
                tapped, self.listen_request = self.listen_request, False
                if self.mic_muted or self.state == "thinking" or (speaking and not tapped):
                    continue
                if tapped or score >= config.settings.get("wake_threshold", 0.5):
                    log.info("tap to talk" if tapped else "wake word (%.2f)", score)
                    self.on_wake()
                    endpoint.reset()
                    recording = True
        finally:
            mic.close()

    def on_wake(self):
        if self.screen_off:
            self.device_control("screen_on", quiet=True)
        self.player.stop()  # cut off a ringing chime or a long answer
        self.set_state("listening")
        threading.Thread(target=self.voice.play, args=(self.chime,), daemon=True).start()

    # requests

    def submit_text(self, text):
        self.requests.put(("text", text))

    def _worker(self):
        while True:
            kind, payload = self.requests.get()
            try:
                self._handle(kind, payload)
            except Exception:
                log.error("request failed:\n%s", traceback.format_exc())
                self._say("Sorry, something went wrong.")
            self.set_state("idle")

    def _handle(self, kind, payload):
        self.set_state("thinking")
        t0 = time.time()
        if kind == "audio":
            self._keep_recording(payload)
            text = speech.transcribe(payload)
            log.info("heard %r (%.1fs of audio, stt %.1fs)", text, len(payload) / audio.RATE, time.time() - t0)
        else:
            text = payload
        if not brain.strip_wake(text):
            if kind == "audio" and len(payload) > audio.RATE * 1.5:
                self._say("Sorry, I didn't catch that.")
            return
        self.add_transcript("user", text)
        if self.ringing:
            self.stop_ringing()
            if STOP_WORDS.search(text) or len(brain.strip_wake(text).split()) <= 2:
                return
        t1 = time.time()
        decision, value, args = brain.decide(text)
        log.info("decided %s %s %s (%.1fs)", decision, value, args, time.time() - t1)
        if decision == "say":
            reply = value
        else:
            if value == "ask_cloud":
                self.emit("thinking_online", True)
            reply = skills.run(self, value, args)
            if value == "change_volume":
                self.voice.play(self.chime)
        self._say(reply)

    @staticmethod
    def _keep_recording(samples, keep=20):
        """The last few commands as WAV files, for tuning the mic and endpointing. Never uploaded."""
        folder = config.RECORDINGS
        folder.mkdir(parents=True, exist_ok=True)
        (folder / time.strftime("%Y%m%d-%H%M%S.wav")).write_bytes(audio.to_wav(samples))
        for old in sorted(folder.glob("*.wav"))[:-keep]:
            old.unlink()

    def _say(self, text):
        if not text:
            return
        log.info("said %r", text)
        self.add_transcript("jarvis", text)
        self.set_state("speaking")
        self.voice.say(text)

    # ringing timers and alarms

    def ring(self, item):
        self.ringing = item
        self.emit("ringing", item)
        self.set_state("ringing")
        if self.screen_off:
            self.device_control("screen_on", quiet=True)
        threading.Thread(target=self._ring_loop, args=(item,), daemon=True).start()

    def _ring_loop(self, item):
        label = item.get("label")
        start = time.time()
        if label:
            self.voice.say(f"Your {label} timer is done.")
        while self.ringing is item and time.time() - start < 120:
            if not self.voice.speaking.is_set() and self.state not in ("listening", "thinking"):
                self.voice.play(self.chime * 3)
            time.sleep(1.2)
        if self.ringing is item:
            self.stop_ringing()

    def stop_ringing(self):
        if self.ringing:
            self.ringing = None
            self.player.stop()
            self.emit("ringing", None)
            self.set_state("idle")

    # device control

    def device_control(self, action, quiet=False):
        if action == "screen_off":
            self.screen_off = True
            system.screen(False)
            return "" if quiet else "Okay."
        if action == "screen_on":
            self.screen_off = False
            system.screen(True)
            return "" if quiet else "Screen on."
        if action == "mute_mic":
            self.set_mic_muted(True)
            return "Microphone off. Tap the screen to turn it back on."
        if action in ("night_mode_on", "night_mode_off"):
            self.night_override = action == "night_mode_on"
            self._night_check()
            return "Night mode on." if self.night else "Night mode off."
        return "I can't do that yet."

    def set_mic_muted(self, muted):
        self.mic_muted = muted
        self.emit("mic_muted", muted)
        self.set_state("idle")

    def _night_check(self):
        night = config.settings.get("night_mode")
        scheduled = False
        if night.get("auto"):
            now = dt.datetime.now().strftime("%H:%M")
            start, end = night["start"], night["end"]
            scheduled = (start <= now or now < end) if start > end else (start <= now < end)
        if self.night_override is not None and self.night_override == scheduled:
            self.night_override = None  # the schedule caught up with the manual switch
        value = scheduled if self.night_override is None else self.night_override
        if value != self.night:
            self.night = value
            self.emit("night", value)

    # periodic refreshes

    def _refresh_weather(self):
        self.weather = home_forecast()
        self.emit("weather", self.weather)

    def _refresh_calendar(self):
        self.calendar.refresh()
        self.emit("calendar", self.calendar.upcoming())

    def _refresh_music(self):
        if not self.spotify.connected:
            if self.music:
                self.music = None
                self.emit("music", None)
            return
        try:
            music = self.spotify.now_playing()
        except NotConnected:
            music = None
        if music != self.music:
            self.music = music
            self.emit("music", music)

    def refresh_now(self):
        """After a settings change: fetch weather and calendar again right away."""
        for fn in (self._refresh_weather, lambda: self.calendar.refresh(force=True) or self.emit(
                "calendar", self.calendar.upcoming())):
            try:
                fn()
            except Exception as e:
                log.warning("refresh failed: %s", e)
