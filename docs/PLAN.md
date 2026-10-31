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

## Phase 3: Voice pipeline
- [ ] "Hey Jarvis" wake word, VAD, STT, TTS
- [ ] Orchestrator service with local/cloud routing

## Phase 4: Skills
- [ ] Time, timers, alarms, weather, calendar, Spotify, search, system controls

## Phase 5: Wall UI
- [ ] Kiosk session, central animated logo, widget grid, settings screen, night mode

## Phase 6: Deploy and harden
- [ ] Installer, auto-update from Releases, watchdogs, privacy mute

## Phase 7: Tune
- [ ] A week of real use, retrain on real phrasing
