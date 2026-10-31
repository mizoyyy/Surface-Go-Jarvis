"""Speech to text (whisper-server) and text to speech (Piper, kept loaded)."""

import re
import threading

import httpx

from . import audio, config


PROMPT = "Hey Jarvis, what's the formula for kinetic energy?"


def transcribe(samples):
    """Sends a 16 kHz int16 clip to whisper-server and returns the text."""
    seconds = len(samples) / audio.RATE
    # the encoder context must cover the clip, with headroom, or tiny.en repeats itself
    audio_ctx = min(1500, max(320, int(50 * seconds + 200)))
    r = httpx.post(config.STT_URL + "/inference", timeout=60, files={
        "file": ("command.wav", audio.to_wav(samples), "audio/wav")},
        # no temperature fallback: on a short noisy clip it retried for 30 s and still looped.
        # max_tokens (patched into our whisper-server build) stops a loop after about two
        # sentences instead of 224 tokens; the prompt teaches words tiny.en gets wrong
        # ("formula" was heard as "form now" and "format")
        data={"response_format": "json", "temperature": "0", "temperature_inc": "0",
              "suppress_nst": "true", "audio_ctx": str(audio_ctx), "max_tokens": "32",
              "prompt": PROMPT})
    r.raise_for_status()
    text = r.json().get("text", "")
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)|\*[^*]*\*", " ", text)  # [BLANK_AUDIO], (wind blowing)
    text = drop_repeats(" ".join(text.split()))
    return text if re.search(r"[a-zA-Z]{2}", text) else ""  # "♪", "...", "x2"


def drop_repeats(text):
    """tiny.en sometimes loops: "What's my name? What's my name? What's my name?" -> once."""
    sentences = re.findall(r"[^.?!]+[.?!]*", text)
    out = []
    for s in sentences:
        if not out or s.strip().lower() != out[-1].strip().lower():
            out.append(s)
    # the token cap can cut a loop mid-sentence: "What's the formula? What's the"
    if len(out) > 1 and out[0].lower().startswith(out[-1].strip().lower()):
        out.pop()
    return " ".join(s.strip() for s in out)


class Voice:
    def __init__(self, player):
        from piper import PiperVoice

        self.player = player
        self.name = config.settings.get("voice")
        self.voice = PiperVoice.load(str(config.PIPER_DIR / f"{self.name}.onnx"))
        self.rate = self.voice.config.sample_rate
        self.speaking = threading.Event()
        self.cancelled = False

    def say(self, text):
        """Speaks text, streaming each sentence to the speaker as soon as it is ready."""
        if not text:
            return
        self.cancelled = False
        self.speaking.set()
        try:
            proc = self.player.open(self.rate)
            for chunk in self.voice.synthesize(text):
                if self.cancelled or not self.player.write(proc, chunk.audio_int16_bytes):
                    break
            self.player.finish(proc)
        finally:
            self.speaking.clear()

    def play(self, pcm):
        proc = self.player.open(self.rate)
        self.player.write(proc, pcm)
        self.player.finish(proc)

    def stop(self):
        self.cancelled = True
        self.player.stop()
