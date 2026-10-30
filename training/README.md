# Training: Jarvis tool-calling model

Fine-tunes Qwen2.5-0.5B-Instruct (LoRA) to turn one spoken request into one tool call or one
short reply. Training runs on Colab; the result is a Q4_0 GGUF for llama.cpp on the tablet.

## Design
- The model only picks the tool and its arguments. Each skill speaks its own confirmation,
  so there is no second LLM pass (each pass costs seconds on the tablet).
- The tool list is not in the prompt: the model learns it from the data. The prompt is 42 tokens
  and llama-server caches it, so prompt processing is under a second.
- Output format: `<tool_call>{"arguments": {...}, "name": "..."}</tool_call>` or plain text.
  The schema, prompt and parser live in [tools.py](tools.py).
- Export **Q4_0**. Q4_K_M is 7x slower on the tablet's no-AVX CPU (see docs/phase1-notes.md).

## Files
| File | What it does |
|---|---|
| `tools.py` | Tool schema, system prompt, tool-call format and parser |
| `generate_dataset.py` | Template-based generator with whisper-style noise. Writes `data/{train,val,eval}.jsonl` |
| `real_eval.py` | Hand-written eval set in real phrasing. Writes `data/eval_real.jsonl` |
| `score.py` | Scores predictions: exact match, tool-name accuracy, invalid output, per-intent |
| `finetune_colab.ipynb` | Colab T4 notebook: baseline, LoRA, eval, merge, GGUF Q4_0 export |
| `eval_gguf.py` | Scores a GGUF on the tablet through llama-server and reports latency |

The `eval` split uses templates and slot values (cities, artists, questions) that never appear
in training, so it measures generalisation.

## Run
1. Open `finetune_colab.ipynb` in Colab (File > Open notebook > GitHub, `mizoyyy/Surface-Go-Jarvis`),
   pick a T4 GPU runtime, and run all cells. It downloads `jarvis-0.5b-q4_0.gguf` and a report.
2. On the tablet, copy the model to `~/jarvis/models/llm/` and run:
   ```bash
   python3 training/eval_gguf.py --model ~/jarvis/models/llm/jarvis-0.5b-q4_0.gguf
   ```
3. If it scores well, publish it as a GitHub Release (`gh release create model-v1 ...`).

## Results

### Baseline (untuned Qwen2.5-0.5B)
- Colab: 8% exact on `eval`, 12.5% on `eval_real` (only small talk passes).
- Tablet, Q4_0, first 12 rows of `eval_real`: 0% exact, it chats instead of calling tools.

### v1 (2026-10-30): LoRA r=16, 2 epochs, 4000 rows, 3.5 min on a T4
Final train loss 0.004, validation loss 0.0073 (still falling, no overfitting).

| Set | Where | Exact | Tool name | Invalid |
|---|---|---|---|---|
| `eval` (400) | Colab, full precision | 89.5% | 93.8% | 2.5% |
| `eval` (first 120) | Tablet, Q4_0 | 89.2% | | |
| `eval_real` (40) | Colab, full precision | 95% | 100% | 0% |
| `eval_real` (40) | Tablet, Q4_0 | 95% | 100% | 0% |

- Q4_0 loses essentially nothing. File size 352 MB.
- Tablet latency (2 threads, prompt cached): median 3.5 s per request
  (prompt 0.7 s, generation 2.7 to 2.9 s), max 8.4 s.
- Weak intents on `eval`: media next/previous/stop, never_mind, get_weather, get_date.

What goes wrong, in order of importance:
1. **Timer arithmetic**: "two hours" became 120 s, "10 minutes and 30 seconds" 90 s,
   "twenty minutes" 120 s. The model has to convert to seconds and gets it wrong.
   Fix for v2: let it copy the numbers (`{"hours": 2}`, `{"minutes": 10, "seconds": 30}`)
   and let the skill add them up.
2. Invented arguments or values: `get_date` with a `day`, `media_control` action `skip`,
   `device_control` action `reset`, `spotify_play` kind `list`.
3. Rare phrasings: "the song before" played a track; "sorry wrong button" became a tool call.
4. Harmless: "Lisboa" for Lisbon, "Kuwait" for Kuwait City, a trimmed `ask_cloud` question.

Ideas for v2: unit-based timer arguments, more examples for the weak intents, and
validating arguments against `TOOLS` at runtime (treat an unknown value as `ask_cloud`).
A shorter output format would also cut generation time (most of the 3.5 s).
