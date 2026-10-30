# Phase 1 notes: tablet survey (2026-10-30)

## RAM
- 3.7 GiB usable, 3.9 GiB swapfile (`/swapfile`, no zram).
- With the desktop, Chrome and Claude Desktop open: 3.0 GiB used, 1.4 GiB swapped, ~670 MiB available.
- Chrome and Claude Desktop together use about 2.5 GiB. The final kiosk must run without them.
- Idea for later: zram swap instead of eMMC swapfile (faster, less flash wear).

## CPU
- Pentium 4415Y, 2 cores / 4 threads.
- **No AVX, AVX2 or FMA. SSE4.2 only.** llama.cpp and whisper.cpp must be built with
  `-DGGML_NATIVE=ON` (or AVX flags off). Prebuilt AVX binaries will crash with "illegal instruction".
  Expect slow inference: keep the local LLM tiny (~0.5B Q4) and use whisper `tiny.en`/`base.en`.
  onnxruntime (openWakeWord, Piper) must be checked on this CPU before relying on it.

## Audio
- One card: HDA Intel PCH, Realtek ALC298. PipeWire 1.0.5 with the PulseAudio layer.
- Speakers: `alsa_output.pci-0000_00_1f.3.analog-stereo`, port `analog-output-speaker`. Test tone plays.
- Mic: `alsa_input.pci-0000_00_1f.3.analog-stereo`, port `analog-input-internal-mic`.
- Mic levels (3 s of a quiet room, 16 kHz mono):

  | Internal Mic Boost | Capture | Noise floor | Peak |
  |---|---|---|---|
  | 3 (max, default) | 127 | -2 dBFS, large DC offset | 0 dBFS (clipping) |
  | 1 | 80 | -49 dBFS | -33 dBFS |
  | 0 | 80 | -57 dBFS | -47 dBFS |
  | 0 | 50 | -73 dBFS | -62 dBFS |

- The default (boost 3) is unusable: it saturates. Set to **boost 1, capture 80** for now.
  Needs a speech test at wall distance; a USB far-field mic may still be needed.
- Persist with `sudo alsactl store`.

## Wi-Fi
- Qualcomm Atheros QCA6174 (`ath10k_pci`), interface `wlp1s0`, 5 GHz-capable.
- Connected, signal 75, 130 Mbit/s, ping 1.1.1.1 avg 37 ms, no loss.
- Power saving is **on** (`wifi.powersave = 3` in `/etc/NetworkManager/conf.d/default-wifi-powersave-on.conf`).

## Battery
- `BAT1`, 430 cycles, 88% of design capacity, AC connected.
- No `charge_control_end_threshold` in sysfs, so Linux cannot cap charging.
  Use the Surface UEFI "Enable Battery Limit" option (caps at 50%) for always-plugged use.

## Kernel
- Stock Ubuntu HWE `6.14.0-37-generic`. Secure Boot is disabled, so linux-surface needs no MOK enrollment.

## After reboot (linux-surface 7.2.13)
- Kernel booted fine. Wi-Fi power save stays off.
- **Mic boost resets to 3 (clipping) at every login**, even after `sudo alsactl store`.
  Fix: user unit `deploy/systemd/jarvis-mic-levels.service` sets boost 1 / capture 80 after WirePlumber starts.
- **Power profile was `power-saver`**: CPU pinned at ~600 MHz, everything 3x slower.
  Set to `performance` with `powerprofilesctl set performance` (no sudo). The wall unit is always
  on AC, so keep it there; check it survives reboots.

## Piper TTS (venv `~/jarvis/venv`, piper-tts 1.8.0, onnxruntime 1.31.1)
- onnxruntime works on this no-AVX CPU.
- Voices in `~/jarvis/models/piper/`. Benchmarks with the `performance` profile, voice preloaded:

  | Voice | Load | "Timer set for ten minutes." | 5 s sentence |
  |---|---|---|---|
  | en_GB-alan-low | 6.4 s | 0.67 s (RTF 0.33) | first chunk 0.40 s, RTF 0.30 |
  | en_GB-alan-medium | 6.6 s | 1.17 s (RTF 0.57) | first chunk 0.71 s, RTF 0.43 |

  In `power-saver` the same runs were RTF 1.0 to 1.4 with an 18 s load.
- Keep the voice loaded in the long-running service. Stream chunks to the speaker as they arrive.
- `pip install` of big wheels was OOM-killed once with Chrome and Claude Desktop open; use `--no-cache-dir`.

## whisper.cpp STT (`~/jarvis/src/whisper.cpp` @ 482279b, built in 5 min, `-march=native`)
- Test clip: `samples/jfk.wav`, 11 s. All runs below transcribed it correctly unless noted.

  | Model | `-ac` | Encode | Total |
  |---|---|---|---|
  | base.en (F16) | 1500 | | 60 s |
  | tiny.en (F16) | 1500 | 17.3 s | 25.5 s |
  | tiny.en (F16) | 512 | 5.7 s | 12.0 s |
  | **tiny.en q8_0** | **512** | **2.1 s** | **5.4 s** |
  | tiny.en q8_0 | 256 | 1.0 s | broken: truncated, then loops |

- No F16C/AVX, so F16 weights are slow. Use **q8_0** (`whisper-quantize`, 43 MB).
- `-ac` must cover the clip: about 50 per second of audio (1500 = 30 s). Size it per utterance
  (for example `50 * seconds + 64`). A 3 s command should land around 1.5 s total.
- 2 vs 4 threads makes almost no difference (2 physical cores).

## llama.cpp LLM (`~/jarvis/src/llama.cpp` @ 889f2ec, built in 33 min, `-march=native`)
- Qwen2.5-0.5B-Instruct, `llama-bench -p 128 -n 32`:

  | Quant | Size | Prompt t/s (2 thr) | Gen t/s (2 thr) | Gen t/s (4 thr) |
  |---|---|---|---|---|
  | Q4_K_M | 463 MiB | 2.9 | 2.5 | 2.2 |
  | **Q4_0** | **403 MiB** | **20.6** | **8.5** | 7.3 |
  | Q8_0 | 639 MiB | 9.0 | 5.3 | |

- **Phase 2 must export Q4_0, not Q4_K_M.** K-quants have no fast path without AVX; Q4_0 gets
  the repacked SSE kernels. Use 2 threads.
- Prompt processing is the cost: a 300-token system prompt is ~15 s. Run `llama-server` with the
  system prompt KV-cached so each turn only processes the new utterance (~1 s), plus ~4 s for a
  30-token tool call. Keep the system prompt and tool schema short, and add a regex fast path
  for very common commands (time, timers, volume) that skips the LLM.

## Tools
- Present: git, gcc, g++, make, pkg-config, curl, wget, Python 3.12.3.
- Installed by the user via apt: cmake, build-essential, python3-venv/dev/pip, pipx, ffmpeg,
  sox, jq, htop, iw, git-lfs, OpenBLAS, portaudio and ALSA headers.
- Layout outside the repo: `~/jarvis/venv`, `~/jarvis/models/`, `~/jarvis/src/` (llama.cpp, whisper.cpp).
