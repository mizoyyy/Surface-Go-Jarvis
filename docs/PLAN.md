# Jarvis build plan

## Phase 0: Setup
- [x] Repo created, specs collected, decisions made
- [ ] Claude GitHub App installed on the repo (so changes can be pushed)

## Phase 1: Prepare the tablet
- [x] linux-surface kernel, disable Wi-Fi power saving
- [x] Audio check: built-in mics and speakers (built-in mic passes at wall distance,
      levels set at login by deploy/systemd/jarvis-mic-levels.service)
- [x] Battery care for always-plugged-in use (Battery Limit enabled in Surface UEFI)
- [x] Python env, build tools, llama.cpp, whisper.cpp, Piper (benchmarks in docs/phase1-notes.md)
- [x] Power profile set to `performance` (power-saver made everything 3x slower)

## Phase 2: Model (GitHub + Colab)
- [x] Dataset: Jarvis persona + tool-calling examples (training/generate_dataset.py, 4000 train rows)
- [x] LoRA fine-tune of a ~0.5B open model (v1: 89.5% held-out, 95% hand-written; see training/README.md)
- [x] v2: unit-based timer arguments, more data for weak intents (95% held-out and hand-written on the tablet)
- [x] Eval set and scoring (held-out eval split, hand-written eval_real, score.py, eval_gguf.py)
- [ ] Quantize to GGUF **Q4_0** (Q4_K_M is 7x slower on this no-AVX CPU), publish as GitHub Release

## Phase 3: Voice pipeline (see docs/assistant.md)
- [x] "Hey Jarvis" wake word (openWakeWord ONNX models on onnxruntime), end-of-speech detection,
      STT (whisper-server, tiny.en q8_0), TTS (Piper, kept loaded)
- [x] Orchestrator service with local/cloud routing (regex fast path, fine-tuned model, Claude fallback)
- [ ] Live voice test at wall distance, tune wake sensitivity

## Phase 4: Skills
- [x] Time, date, timers, alarms, weather (Open-Meteo), calendar (iCal link), Spotify (Web API),
      online answers with web search (Claude), volume, screen, mic mute, night mode
- [ ] Spotify playback device on the tablet (spotifyd), connect Spotify and calendar accounts

## Phase 5: Wall UI
- [x] Central animated logo, widget grid (clock, weather, timers, calendar, music), settings screen, night mode
- [x] Kiosk launcher (Chrome app mode) and user services (deploy/install.sh)
- [ ] Enable at login, disable screen lock and blanking

## Phase 6: Deploy and harden
- [ ] Installer, auto-update from Releases, watchdogs, privacy mute

## Phase 7: Tune
- [ ] A week of real use, retrain on real phrasing
