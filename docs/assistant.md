# The assistant: how it runs

```
arecord (16 kHz) -> wake word "hey jarvis" -> end of speech -> Moonshine (STT) -> word list
  -> regex fast path, or the fine-tuned model on llama-server -> skill -> Piper (TTS) -> aplay
                                    \-> Gemini or Claude for anything the tools can't answer
FastAPI on 127.0.0.1:8000 <-> WebSocket <-> wall UI (Chrome in kiosk mode)
```

## Services (systemd --user)
| Unit | What | Port | RAM |
|---|---|---|---|
| `jarvis-llm` | llama-server, `jarvis-0.5b-v2-q4_0.gguf`, 2 threads | 8091 | ~320 MB |
| `jarvis` | `python -m assistant`: mic, wake word, Moonshine STT, skills, Piper, UI server | 8000 | ~300 MB |
| `jarvis-mic-levels` | sets the mic boost at login | | |

Install or update: `sh deploy/install.sh`. Logs: `journalctl --user -u jarvis -f`.
The kiosk starts at login from `~/.config/autostart/jarvis-kiosk.desktop`.

## Code (`assistant/`)
| File | Does |
|---|---|
| `core.py` | Mic loop (wake word + endpointing), request worker, timers ringing, night mode, UI events |
| `wakeword.py` | openWakeWord's streaming pipeline on onnxruntime (the package itself needs scikit-learn and tflite) |
| `audio.py` | arecord capture, end-of-speech detection against the room's noise floor, aplay playback, chime |
| `speech.py` | Speech to text (cleanup, loop filter, word list) and the Piper voice |
| `moonshine.py` | Moonshine base 8-bit on onnxruntime: encoder, then greedy decoding with a key/value cache |
| `vocab.py` | Puts names from the word list right ("armor dab" -> Amr Diab), prayer names before "prayer" |
| `brain.py` | Regex fast path, then the fine-tuned model; an invalid tool call goes to `ask_cloud` |
| `skills/` | One module per area; each tool returns the sentence Jarvis says |
| `server.py` | HTTP + WebSocket API for the UI |
| `config.py` | Paths, ports, settings (`~/.config/jarvis/settings.json`), secrets (`secrets.json`, mode 600) |

## Speed on the tablet
- Wake word: ~15 ms per 80 ms of audio.
- STT: Moonshine base, 8-bit (`~/jarvis/models/moonshine`, from `UsefulSensors/moonshine`
  `onnx/merged/base/quantized`, plus its `tokenizer.json`), about 1 to 2 s for a short command.
  Fast-path commands (time, pause, next, volume) then answer at once. General questions ("what
  is", "who", "how", "find") with no word a local tool would handle skip the local model.
- Why Moonshine: its work grows with the clip, where whisper encodes a fixed 30 s window. On the
  last 20 real commands (31 Oct) whisper tiny.en took 5.2 s on average, Moonshine base float 1.9 s,
  8-bit 2.5 s (1.8 s with the in-process runner), all about equally accurate; whisper base.en was
  no better and twice as slow. 8-bit replaces the 110 MB whisper-server at about the same memory.
  The first half second (end of "hey jarvis" and the chime) is cut: with it Moonshine returned
  nothing on 7 of the 20.
- Moonshine takes no vocabulary hint, so names it can't spell are fixed afterwards from the word
  list in Settings, by sound ("armor dab" -> Amr Diab, "mug rib prayer" -> Maghrib prayer).
- Model: ~3.5 s for a tool call. Total from end of speech to answer: about 6 s on the model path.

## Accounts (from the settings screen)
- **Online answers**: by default Gemini Flash Lite (about 1.5 s per answer), with a free API key from
  aistudio.google.com (free tier limits apply, and Google may use free-tier prompts to improve its
  products). Google Search grounding was not in the free quota when tested (429), so Jarvis retries
  without it; Gemini Flash was 11 to 16 s or overloaded (503), and falls back to Flash Lite. LaTeX in
  answers ("$\\frac{1}{2}mv^2$") is turned into words before it is spoken. Picking a Claude model in the list switches to Claude (paid key from
  console.anthropic.com, low effort, server-side refusal fallback). Each provider keeps its own key.
  With no key, "what is / who is" questions get the first two sentences of the Wikipedia article.
- **Calendar**: the private iCal link of a Google (or any) calendar.
- **Spotify** (Premium): an app at developer.spotify.com with redirect URI
  `http://127.0.0.1:8000/spotify/callback`; paste its Client ID, press Connect. Playback goes to the
  device named in the settings ("Jarvis" by default), else the active one.
- **Spotify player on the tablet**: the wall display itself is the Spotify Connect speaker "Jarvis",
  through Spotify's Web Playback SDK (Chrome plays the protected audio; Premium only). It needs the
  `streaming` permission, so connections made before it was added must press Connect again.
  spotifyd and other librespot players were tried and no longer work: Spotify refuses them the
  audio keys ("audio key error", librespot-org/librespot#1649).

## Using it
- Say "Hey Jarvis", wait for the chime, then the request. Or tap the logo to talk.
- "Hey Jarvis" (or a tap) at any time stops what Jarvis is saying or working on and pauses the
  music. While Jarvis is talking, the wake word needs a score of 0.8, so its own voice doesn't
  trigger it.
- Tap the logo while a timer rings to stop it, or say "stop".
- "Turn off the microphone" mutes it; tap the logo to turn it back on.
- Settings (gear icon): location, units, widgets and their order, volume, wake sensitivity, night
  mode schedule, accounts, and a box to type requests.
