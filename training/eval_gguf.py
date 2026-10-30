"""Score a GGUF model on the tablet through llama-server and measure latency.

  python3 training/eval_gguf.py --model ~/jarvis/models/llm/jarvis-0.5b-q4_0.gguf [--data training/data/eval_real.jsonl]

Starts llama-server with the settings the assistant will use (2 threads, prompt cache on),
sends each row as a raw ChatML prompt, then prints the score and latency.
Only uses the standard library.
"""

import argparse
import json
import os
import statistics
import subprocess
import time
import urllib.request
from pathlib import Path

import score

HERE = Path(__file__).parent
DEFAULT_SERVER = Path.home() / "jarvis/src/llama.cpp/build/bin/llama-server"


def chatml(rows_messages):
    """Same text Qwen's chat template produces with add_generation_prompt=True."""
    text = "".join(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in rows_messages)
    return text + "<|im_start|>assistant\n"


def post(url, payload):
    req = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def wait_ready(base, proc, timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        if proc.poll() is not None:
            raise RuntimeError("llama-server exited, see its log")
        try:
            with urllib.request.urlopen(base + "/health", timeout=2) as r:
                if r.status == 200:
                    return time.time() - start
        except OSError:
            pass
        time.sleep(0.5)
    raise TimeoutError("llama-server did not become ready")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", default=str(HERE / "data" / "eval_real.jsonl"))
    ap.add_argument("--server", default=str(DEFAULT_SERVER))
    ap.add_argument("--port", type=int, default=8089)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0, help="only the first N rows")
    ap.add_argument("--out", help="write predictions jsonl here")
    a = ap.parse_args()

    rows = [json.loads(line) for line in open(a.data)]
    if a.limit:
        rows = rows[:a.limit]
    base = f"http://127.0.0.1:{a.port}"
    log = open(os.devnull, "w")
    proc = subprocess.Popen([a.server, "-m", os.path.expanduser(a.model), "-t", str(a.threads), "-c", "1024",
                             "--port", str(a.port), "-np", "1"], stdout=log, stderr=log)
    try:
        print(f"server ready in {wait_ready(base, proc):.1f}s")
        predictions, latencies, prompt_ms, gen_ms = [], [], [], []
        for row in rows:
            t = time.time()
            r = post(base + "/completion", {"prompt": chatml(row["messages"][:-1]), "n_predict": 80,
                                            "temperature": 0, "cache_prompt": True, "stop": ["<|im_end|>"]})
            latencies.append(time.time() - t)
            prompt_ms.append(r["timings"]["prompt_ms"])
            gen_ms.append(r["timings"]["predicted_ms"])
            predictions.append(r["content"])
    finally:
        proc.terminate()
        proc.wait()

    if a.out:
        with open(a.out, "w") as f:
            for p in predictions:
                f.write(json.dumps({"prediction": p}) + "\n")
    score.report(score.score(rows, predictions))
    print(f"latency per request: median {statistics.median(latencies):.2f}s, max {max(latencies):.2f}s "
          f"(prompt median {statistics.median(prompt_ms) / 1000:.2f}s, "
          f"generation median {statistics.median(gen_ms) / 1000:.2f}s)")


if __name__ == "__main__":
    main()
