"""Speech to text (Moonshine, in process) and text to speech (Piper, kept loaded)."""

import re
import threading

from . import audio, config, vocab

_stt = None
_stt_lock = threading.Lock()


def load_stt():
    global _stt
    with _stt_lock:
        if _stt is None:
            from .moonshine import Moonshine
            _stt = Moonshine(config.MOONSHINE_DIR)
    return _stt


def transcribe(samples):
    """A 16 kHz int16 clip -> text, with names from the word list put right."""
    # the first half second is the end of "hey jarvis" and the chime: with it, Moonshine
    # often returned nothing (7 of 20 recordings)
    if len(samples) > audio.RATE:
        samples = samples[audio.RATE // 2:]
    seconds = len(samples) / audio.RATE
    text = load_stt().transcribe(samples)
    text = re.sub(r"\[[^\]]*\]|\([^)]*\)|\*[^*]*\*", " ", text)  # [music], (wind blowing)
    text = drop_repeats(" ".join(text.split()))
    if looping(text, seconds) or not re.search(r"[a-zA-Z]{2}", text):  # "♪", "...", "x2"
        return ""
    names = [n for n in config.settings.get("vocabulary", []) if isinstance(n, str) and n.strip()]
    return vocab.correct(text, names)


def looping(text, seconds):
    """A short or noisy clip: "I'm not going to be able to be able to be able to ..."."""
    words = re.findall(r"[\w']+", text.lower())
    if len(words) > 5 * seconds + 4:  # people say about 2.5 words a second
        return True
    for n in range(2, 5):  # the same 2 to 4 words three times in a row ("stop stop stop" is fine)
        for i in range(len(words) - 3 * n + 1):
            if words[i:i + n] == words[i + n:i + 2 * n] == words[i + 2 * n:i + 3 * n]:
                return True
    return False


def drop_repeats(text):
    """Speech models sometimes loop: "What's my name? What's my name? What's my name?" -> once."""
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
