"""Small helpers shared by the skills: days and how to say numbers out loud."""

import datetime as dt

DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def resolve_day(day):
    """'today' | 'tomorrow' | weekday name -> the next matching date (today counts)."""
    today = dt.date.today()
    if day in (None, "", "today"):
        return today
    if day == "tomorrow":
        return today + dt.timedelta(days=1)
    return today + dt.timedelta(days=(DAY_NAMES.index(day) - today.weekday()) % 7)


def day_phrase(day):
    if day in (None, "", "today", "tomorrow"):
        return day or "today"
    return "on " + day.capitalize()


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def say_duration(seconds):
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    parts = [plural(n, w) for n, w in ((hours, "hour"), (minutes, "minute"), (secs, "second")) if n]
    if len(parts) > 1:
        return ", ".join(parts[:-1]) + " and " + parts[-1]
    return parts[0] if parts else "0 seconds"


def say_time(t):
    """7:05 AM style, which Piper reads naturally."""
    hour = t.hour % 12 or 12
    suffix = "AM" if t.hour < 12 else "PM"
    return f"{hour} {suffix}" if t.minute == 0 else f"{hour}:{t.minute:02d} {suffix}"
