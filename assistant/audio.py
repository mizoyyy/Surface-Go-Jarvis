"""Microphone capture, end-of-speech detection, and playback.

The mic stream stays open all the time (opening it from suspend gives ~0.4 s of garbage,
see docs/phase1-notes.md). It is read in 80 ms chunks of 16 kHz mono int16 audio.
"""

import io
import math
import subprocess
import threading
import wave

import numpy as np

RATE = 16000
CHUNK = 1280


def level_db(chunk):
    rms = math.sqrt(float(np.mean(chunk.astype(np.float32) ** 2)) + 1e-9)
    return 20 * math.log10(rms / 32768)


def to_wav(samples, rate=RATE):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(samples.astype(np.int16).tobytes())
    return buf.getvalue()


class Mic:
    """Yields CHUNK-sample int16 arrays from arecord (PipeWire's default source)."""

    def __init__(self):
        self.proc = None

    def chunks(self):
        self.proc = subprocess.Popen(
            ["arecord", "-q", "-t", "raw", "-f", "S16_LE", "-r", str(RATE), "-c", "1", "--buffer-time=200000"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        warmup = 7  # drop the first ~0.5 s
        while True:
            data = self.proc.stdout.read(CHUNK * 2)
            if len(data) < CHUNK * 2:
                raise RuntimeError("microphone stream ended")
            if warmup:
                warmup -= 1
                continue
            yield np.frombuffer(data, dtype=np.int16)

    def close(self):
        if self.proc:
            self.proc.kill()


class Endpointer:
    """Collects one spoken command after the wake word.

    Speech is any chunk well above the room's noise floor, which is tracked while idle.
    The command ends after `silence_s` of quiet, or gives up if nobody speaks.
    """

    def __init__(self, start_timeout_s=5.0, silence_s=1.0, max_s=12.0, margin_db=10.0, grace_s=0.5):
        self.noise_db = -55.0
        # the tail of "hey jarvis" and the chime fall in the first half second: kept, but they
        # don't count as the command, or a pause after the chime would end the recording
        self.grace = int(grace_s * RATE / CHUNK)
        self.start_timeout = int(start_timeout_s * RATE / CHUNK)
        self.silence = int(silence_s * RATE / CHUNK)
        self.max_chunks = int(max_s * RATE / CHUNK)
        self.margin = margin_db
        self.reset()

    def track_noise(self, chunk):
        db = level_db(chunk)
        # follows quiet quickly, loud sounds slowly, so speech barely moves it
        rate = 0.1 if db < self.noise_db else 0.005
        self.noise_db += rate * (db - self.noise_db)

    def reset(self):
        self.audio, self.heard, self.quiet = [], 0, 0

    def feed(self, chunk):
        """Returns None while listening, the audio (np.int16) when done, or an empty array on timeout."""
        self.audio.append(chunk)
        if len(self.audio) <= self.grace:
            return None
        speech = level_db(chunk) > max(self.noise_db + self.margin, -50.0)
        if speech:
            self.heard += 1
            self.quiet = 0
        else:
            self.quiet += 1
        if not self.heard and len(self.audio) >= self.start_timeout:
            return np.zeros(0, dtype=np.int16)
        if (self.heard >= 2 and self.quiet >= self.silence) or len(self.audio) >= self.max_chunks:
            audio = np.concatenate(self.audio[: len(self.audio) - max(self.quiet - 3, 0)])
            return audio
        return None


class Player:
    """Plays raw int16 audio through aplay; stop() cuts it off."""

    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None

    def open(self, rate):
        with self.lock:
            self.stop_locked()
            self.proc = subprocess.Popen(
                ["aplay", "-q", "-t", "raw", "-f", "S16_LE", "-r", str(rate), "-c", "1"],
                stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            return self.proc

    def write(self, proc, data):
        try:
            proc.stdin.write(data)
            return True
        except (BrokenPipeError, ValueError):
            return False

    def finish(self, proc):
        try:
            proc.stdin.close()
        except (BrokenPipeError, ValueError):
            pass
        proc.wait()

    def stop_locked(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        self.proc = None

    def stop(self):
        with self.lock:
            self.stop_locked()


def chime(rate=22050, notes=(880, 1175), note_s=0.18, gap_s=0.05, volume=0.35):
    """A short two-note chime as int16 bytes (wake acknowledgement, timers)."""
    parts = []
    for freq in notes:
        t = np.arange(int(rate * note_s)) / rate
        env = np.minimum(1, t / 0.01) * np.exp(-t * 9)
        parts.append(np.sin(2 * np.pi * freq * t) * env)
        parts.append(np.zeros(int(rate * gap_s)))
    return (np.concatenate(parts) * volume * 32767).astype(np.int16).tobytes()
