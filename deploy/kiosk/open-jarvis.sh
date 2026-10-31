#!/bin/sh
# The "Jarvis" desktop shortcut: starts Jarvis if it was stopped, then shows the wall display,
# or brings it to the front if it is already open (Alt+F4 only closes the display).
systemctl --user start jarvis-llm jarvis
if wmctrl -l | grep -q " Jarvis$"; then
    exec wmctrl -a Jarvis
fi
exec "$(dirname "$0")/jarvis-kiosk.sh"
