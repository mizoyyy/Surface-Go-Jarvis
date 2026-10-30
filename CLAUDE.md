# Surface-Go-Jarvis: project context for Claude

Wall-mounted, Alexa-style voice assistant called **Jarvis**, running on a Microsoft Surface Go (gen 1).

## Hardware (the tablet, hostname `mazen-surface-go`, user `mazen`)
- Intel Pentium 4415Y, 2 cores, 1.6 GHz, Intel HD 615, **no usable GPU for AI**
- **3.9 GB RAM** (the main constraint), 62.5 GB eMMC
- Linux Mint 22.3 Cinnamon, kernel 6.14, X11

## Decisions (agreed with the user)
- **Hybrid brain**: small local model for fast commands, cloud model fallback for hard questions
- **English only**
- **Wake word**: "Hey Jarvis" (openWakeWord ships a pretrained model)
- **Spotify Premium** available (spotifyd / librespot for local playback is allowed)
- GitHub repo: `mizoyyy/Surface-Go-Jarvis` holds code, training notebooks, dataset, CI, and model releases
- Training runs on free GPU notebooks (Colab/Kaggle), never on the tablet or CPU-only GitHub runners
- Org rule: never use em dashes in any text written for the user

## Architecture
```
mic -> openWakeWord ("hey jarvis") -> VAD -> whisper.cpp (STT)
    -> router: local LLM (llama.cpp, ~0.5B Q4 GGUF, tool calling)
               or cloud LLM for complex questions
    -> skills (timers, weather, calendar, spotify, search, system)
    -> Piper (TTS) -> speaker
backend (Python, FastAPI + WebSocket) <-> UI (web app in Chromium kiosk)
```
UI: animated Jarvis logo in the center (states: idle, listening, thinking, speaking), customizable widget grid around it.

## Repo layout
- `training/`  dataset, fine-tune notebook, eval, quantize scripts
- `assistant/` Python backend: audio pipeline, LLM router, skills
- `ui/`        kiosk web UI and widgets
- `deploy/`    install script, systemd units, kiosk session config
- `docs/`      plan and notes

## Rules for working on the tablet
- Keep RAM use low; measure with `free -h` after each new service.
- Everything runs as user services (`systemctl --user`) where possible.
- System changes needing sudo: show the user the exact command and let them run it.
