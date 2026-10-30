# Jarvis build plan

## Phase 0: Setup
- [x] Repo created, specs collected, decisions made
- [ ] Claude GitHub App installed on the repo (so changes can be pushed)

## Phase 1: Prepare the tablet
- [ ] linux-surface kernel, disable Wi-Fi power saving
- [ ] Audio check: built-in mics and speakers (consider USB far-field mic)
- [ ] Battery care for always-plugged-in use
- [ ] Python env, build tools, llama.cpp, whisper.cpp, Piper

## Phase 2: Model (GitHub + Colab)
- [ ] Dataset: Jarvis persona + tool-calling examples
- [ ] LoRA fine-tune of a ~0.5B open model
- [ ] Eval set and scoring
- [ ] Quantize to GGUF Q4, publish as GitHub Release

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
