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

## Baseline (untuned Qwen2.5-0.5B Q4_0 on the tablet, first 12 rows of eval_real)
0% exact: it chats instead of calling tools. Median latency 2.4 s (prompt 0.8 s, generation 1.7 s).
