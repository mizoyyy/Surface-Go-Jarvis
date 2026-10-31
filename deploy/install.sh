#!/bin/sh
# Installs Jarvis for the current user: systemd user services and the kiosk at login.
# Needs no sudo. Run from anywhere: sh deploy/install.sh
set -e
REPO=$(cd "$(dirname "$0")/.." && pwd)
UNITS="$HOME/.config/systemd/user"
J="$HOME/jarvis"

for f in "$J/venv/bin/python" "$J/src/llama.cpp/build/bin/llama-server" \
         "$J/models/llm/jarvis-0.5b-v2-q4_0.gguf" "$J/models/moonshine/encoder_model.onnx" \
         "$J/models/wakeword/hey_jarvis_v0.1.onnx" "$J/models/piper/en_GB-alan-medium.onnx"; do
    [ -e "$f" ] || { echo "missing: $f (see docs/PLAN.md and training/README.md)"; exit 1; }
done

mkdir -p "$UNITS" "$HOME/.config/autostart"
# speech to text now runs inside the assistant (Moonshine): retire the old whisper-server unit
# (stop works from memory even when the unit file is already a dangling link; disable doesn't)
systemctl --user stop jarvis-stt 2>/dev/null || true
rm -f "$UNITS/jarvis-stt.service" "$UNITS/default.target.wants/jarvis-stt.service"
for unit in jarvis-llm jarvis-mic-levels; do
    ln -sf "$REPO/deploy/systemd/$unit.service" "$UNITS/$unit.service"
done
sed "s|@REPO@|$REPO|" "$REPO/deploy/systemd/jarvis.service" > "$UNITS/jarvis.service"

systemctl --user daemon-reload
systemctl --user enable jarvis-mic-levels jarvis-llm jarvis
systemctl --user restart jarvis-llm jarvis

chmod +x "$REPO/deploy/kiosk/jarvis-kiosk.sh"
cat > "$HOME/.config/autostart/jarvis-kiosk.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Jarvis kiosk
Exec=$REPO/deploy/kiosk/jarvis-kiosk.sh
X-GNOME-Autostart-enabled=true
EOF

echo "Installed. Logs: journalctl --user -u jarvis -f"
echo "The kiosk opens at the next login, or now with: $REPO/deploy/kiosk/jarvis-kiosk.sh &"
