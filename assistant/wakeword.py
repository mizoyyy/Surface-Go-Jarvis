"""'Hey Jarvis' detection with openWakeWord's ONNX models, run directly on onnxruntime.

The openwakeword package imports scikit-learn and wants tflite-runtime (no wheel for this
Python), so this is the same streaming pipeline in ~60 lines:
80 ms of 16 kHz audio -> melspectrogram frames -> one 96-d speech embedding per 80 ms
-> the wake word model scores the last 16 embeddings (1.28 s).
"""

import collections

import numpy as np
import onnxruntime as ort

CHUNK = 1280  # samples per step (80 ms at 16 kHz)


def _session(path):
    opts = ort.SessionOptions()
    opts.inter_op_num_threads = opts.intra_op_num_threads = 1
    return ort.InferenceSession(str(path), sess_options=opts, providers=["CPUExecutionProvider"])


class WakeWord:
    def __init__(self, model_dir, name="hey_jarvis_v0.1"):
        self.mel = _session(model_dir / "melspectrogram.onnx")
        self.emb = _session(model_dir / "embedding_model.onnx")
        self.ww = _session(model_dir / f"{name}.onnx")
        self.ww_input = self.ww.get_inputs()[0].name
        self.n_features = self.ww.get_inputs()[0].shape[1]  # 16
        self.reset()

    def reset(self):
        self.raw = np.zeros(CHUNK + 480, dtype=np.float32)  # 3 extra mel frames of context
        self.mels = np.ones((76, 32), dtype=np.float32)
        self.features = collections.deque(maxlen=self.n_features)
        for _ in range(self.n_features):
            self.features.append(np.zeros(96, dtype=np.float32))
        self.warmup = 5  # the first scores after a reset are unreliable

    def process(self, chunk):
        """Feed exactly CHUNK int16 samples; returns the wake word score (0..1)."""
        self.raw = np.concatenate((self.raw[CHUNK:], chunk.astype(np.float32)))
        mel = self.mel.run(None, {"input": self.raw[None, :]})[0].squeeze() / 10 + 2
        self.mels = np.vstack((self.mels, mel))[-76:]
        emb = self.emb.run(None, {"input_1": self.mels[None, :, :, None]})[0].squeeze()
        self.features.append(emb)
        score = float(self.ww.run(None, {self.ww_input: np.array(self.features)[None, :]})[0].squeeze())
        if self.warmup:
            self.warmup -= 1
            return 0.0
        return score
