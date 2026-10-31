"""Speech to text with Moonshine base (8-bit ONNX), in the assistant process.

Moonshine's work grows with the length of the clip, where whisper always encodes 30 s: on
the last 20 commands it took 2.5 s on average against 5.2 s for whisper tiny.en, with about
the same accuracy (docs/assistant.md). Adapted from useful-moonshine-onnx (MIT): greedy
decoding with the merged decoder and its key/value cache.
"""

import numpy as np
import onnxruntime
import tokenizers

LAYERS, HEADS, HEAD_DIM = 8, 8, 52  # moonshine base
START, END = 1, 2
TOKENS_PER_SECOND = 6.5  # caps the output, so a loop stops instead of running to 192 tokens


class Moonshine:
    def __init__(self, folder):
        opts = onnxruntime.SessionOptions()
        opts.intra_op_num_threads = 2
        self.encoder = onnxruntime.InferenceSession(str(folder / "encoder_model.onnx"), opts)
        self.decoder = onnxruntime.InferenceSession(str(folder / "decoder_model_merged.onnx"), opts)
        self.tokenizer = tokenizers.Tokenizer.from_file(str(folder / "tokenizer.json"))

    def transcribe(self, samples, rate=16000):
        """int16 samples -> text"""
        audio = (samples.astype(np.float32) / 32768)[None, :]
        hidden = self.encoder.run(None, {"input_values": audio})[0]
        cache = {f"past_key_values.{i}.{a}.{b}": np.zeros((0, HEADS, 1, HEAD_DIM), dtype=np.float32)
                 for i in range(LAYERS) for a in ("decoder", "encoder") for b in ("key", "value")}
        tokens = [START]
        for step in range(int(len(samples) / rate * TOKENS_PER_SECOND) + 8):
            logits, *present = self.decoder.run(None, {
                "input_ids": [[tokens[-1]]], "encoder_hidden_states": hidden,
                "use_cache_branch": [step > 0], **cache})
            token = int(logits[0, -1].argmax())
            if token == END:
                break
            tokens.append(token)
            for key, value in zip(cache, present):
                if step == 0 or "decoder" in key:  # the encoder part is fixed after the first step
                    cache[key] = value
        return self.tokenizer.decode(tokens[1:]).strip()
