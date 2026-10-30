"""Hand-written eval set in real spoken phrasing, written to training/data/eval_real.jsonl.

These are not generated from templates. Add real transcripts from the tablet here
during Phase 7 (keep the whisper output as-is, slips included).
"""

import json
from pathlib import Path

from tools import messages, tool_call

ROWS = [
    # from the Phase 1 speech test, as whisper heard it
    ("set_timer", "Hey Jarvis, set a timer for 10 minutes.", tool_call("set_timer", seconds=600)),
    ("set_timer", "Hey Jarvis, set a time of 10 minutes.", tool_call("set_timer", seconds=600)),
    ("get_weather", "What's the weather like today?", tool_call("get_weather", day="today")),
    ("set_timer", "um set a timer for like twenty minutes", tool_call("set_timer", seconds=1200)),
    ("set_timer", "Jarvis, three minute timer for the noodles.", tool_call("set_timer", seconds=180, label="noodles")),
    ("set_timer", "can you do a 45 second timer", tool_call("set_timer", seconds=45)),
    ("cancel_timer", "okay cancel the noodles timer", tool_call("cancel_timer", label="noodles")),
    ("timer_status", "how long's left on the timer", tool_call("timer_status")),
    ("set_alarm", "Wake me up at 6:15 am tomorrow.", tool_call("set_alarm", time="06:15", day="tomorrow")),
    ("set_alarm", "set an alarm for seven thirty in the morning", tool_call("set_alarm", time="07:30")),
    ("set_alarm", "alarm for 5 pm", tool_call("set_alarm", time="17:00")),
    ("cancel_alarm", "turn off tomorrow's alarm", tool_call("cancel_alarm")),
    ("get_time", "Jarvis, what time is it?", tool_call("get_time")),
    ("get_date", "what's the date", tool_call("get_date")),
    ("get_weather", "is it going to rain tomorrow", tool_call("get_weather", day="tomorrow")),
    ("get_weather", "What's the weather in Khobar?", tool_call("get_weather", day="today", location="Khobar")),
    ("get_weather", "how hot will it be on friday", tool_call("get_weather", day="friday")),
    ("calendar_events", "what's on my schedule tomorrow", tool_call("calendar_events", day="tomorrow")),
    ("calendar_events", "do I have anything today", tool_call("calendar_events", day="today")),
    ("spotify_play_artist", "play some Coldplay", tool_call("spotify_play", query="Coldplay", kind="artist")),
    ("spotify_play_track", "play Blinding Lights by The Weeknd",
     tool_call("spotify_play", query="Blinding Lights The Weeknd", kind="track")),
    ("spotify_play_playlist", "put on my chill playlist", tool_call("spotify_play", query="chill", kind="playlist")),
    ("spotify_play_album", "play the album Parachutes", tool_call("spotify_play", query="Parachutes", kind="album")),
    ("media_pause", "pause", tool_call("media_control", action="pause")),
    ("media_next", "skip this one", tool_call("media_control", action="next")),
    ("media_stop", "stop the music please", tool_call("media_control", action="stop")),
    ("set_volume", "volume 40", tool_call("set_volume", level=40)),
    ("volume_up", "turn it up a bit", tool_call("change_volume", direction="up")),
    ("volume_down", "it's too loud", tool_call("change_volume", direction="down")),
    ("night_mode_on", "goodnight jarvis turn on night mode", tool_call("device_control", action="night_mode_on")),
    ("mute_mic", "stop listening for now", tool_call("device_control", action="mute_mic")),
    ("ask_cloud", "who is the president of France",
     tool_call("ask_cloud", question="who is the president of France")),
    ("ask_cloud", "How many teaspoons are in a tablespoon?",
     tool_call("ask_cloud", question="How many teaspoons are in a tablespoon?")),
    ("ask_cloud", "what's the best way to cook salmon",
     tool_call("ask_cloud", question="what's the best way to cook salmon")),
    ("ask_cloud", "explain what an API is", tool_call("ask_cloud", question="explain what an API is")),
    ("greeting", "hey jarvis good morning", "Good morning. How can I help?"),
    ("thanks", "thanks jarvis", "You're welcome."),
    ("identity", "what can you do", "I'm Jarvis. Ask me about timers, alarms, weather, your calendar or music."),
    ("never_mind", "oh never mind", "Very well."),
    ("how_are_you", "how are you today", "Very well, thank you. How can I help?"),
]


def main():
    out = Path(__file__).parent / "data" / "eval_real.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        for intent, utterance, reply in ROWS:
            f.write(json.dumps({"intent": intent, "messages": messages(utterance, reply)}, ensure_ascii=False) + "\n")
    print(f"eval_real: {len(ROWS)} rows -> {out}")


if __name__ == "__main__":
    main()
