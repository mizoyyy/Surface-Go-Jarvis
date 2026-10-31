#!/bin/sh
# Opens the Jarvis UI full screen once the assistant answers. Started at login (autostart).
# ?speaker: this window is the Spotify speaker "Jarvis" (other open Jarvis tabs are not)
URL=http://127.0.0.1:8000/?speaker
for i in $(seq 1 120); do
    curl -sf -o /dev/null "http://127.0.0.1:8000/" && break
    sleep 1
done
exec google-chrome \
    --kiosk --app="$URL" \
    --user-data-dir="$HOME/.config/jarvis/kiosk-chrome" \
    --force-device-scale-factor=1.5 \
    --noerrdialogs --disable-infobars --disable-session-crashed-bubble \
    --disable-features=Translate,TouchpadOverscrollHistoryNavigation \
    --overscroll-history-navigation=0 --disable-pinch \
    --no-first-run --password-store=basic \
    --autoplay-policy=no-user-gesture-required \
    --check-for-update-interval=31536000
