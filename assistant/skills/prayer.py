"""Prayer times by the Umm al-Qura method, computed on the tablet (no internet needed).

Umm al-Qura: Fajr when the sun is 18.5 degrees below the horizon, Dhuhr at solar noon, Asr when
an object's shadow equals its length plus its noon shadow (standard), Maghrib at sunset, Isha
90 minutes after Maghrib (120 in Ramadan). The sun's position follows the PrayTimes.org
algorithm. Ramadan comes from the tabular Hijri calendar, which can be a day off the official
Umm al-Qura calendar at the start or end of the month.
"""

import datetime as dt
import math
import re
import time

from .. import config
from .common import say_duration, say_time

PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]
FAJR_ANGLE = 18.5
SUNSET_ANGLE = 0.833  # refraction and the sun's radius


def _sin(d): return math.sin(math.radians(d))
def _cos(d): return math.cos(math.radians(d))
def _tan(d): return math.tan(math.radians(d))
def _asin(x): return math.degrees(math.asin(x))
def _acos(x): return math.degrees(math.acos(max(-1.0, min(1.0, x))))
def _atan2(y, x): return math.degrees(math.atan2(y, x))


def _sun(jd):
    """(declination, equation of time in hours) for a Julian day."""
    d = jd - 2451545.0
    g = (357.529 + 0.98560028 * d) % 360
    q = (280.459 + 0.98564736 * d) % 360
    lon = (q + 1.915 * _sin(g) + 0.020 * _sin(2 * g)) % 360
    e = 23.439 - 0.00000036 * d
    ra = (_atan2(_cos(e) * _sin(lon), _cos(lon)) / 15) % 24
    eqt = q / 15 - ra
    eqt = (eqt + 12) % 24 - 12
    return _asin(_sin(e) * _sin(lon)), eqt


def _julian(date):
    y, m = date.year, date.month
    if m <= 2:
        y, m = y - 1, m + 12
    a = y // 100
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + date.day + 2 - a + a // 4 - 1524.5


def hijri(date):
    """(year, month, day) in the tabular Islamic calendar."""
    l = int(_julian(date) + 0.5) - 1948440 + 10632
    n = (l - 1) // 10631
    l = l - 10631 * n + 354
    j = ((10985 - l) // 5316) * ((50 * l) // 17719) + (l // 5670) * ((43 * l) // 15238)
    l = l - ((30 - j) // 15) * ((17719 * j) // 50) - (j // 16) * ((15238 * j) // 43) + 29
    m = (24 * l) // 709
    return 30 * n + j - 30, m, l - (709 * m) // 24


def times(date, lat, lon, utc_offset):
    """{prayer: datetime} for one day, in local time (utc_offset in hours)."""
    jd = _julian(date) - lon / (15 * 24)

    def noon(t):
        return (12 - _sun(jd + t)[1]) % 24

    def angle_time(angle, t, before_noon):
        decl = _sun(jd + t)[0]
        h = _acos((-_sin(angle) - _sin(decl) * _sin(lat)) / (_cos(decl) * _cos(lat))) / 15
        return noon(t) - h if before_noon else noon(t) + h

    def asr_time(t):
        decl = _sun(jd + t)[0]
        angle = -math.degrees(math.atan(1 / (1 + _tan(abs(lat - decl)))))
        return angle_time(angle, t, False)

    hours = {  # one refinement from rough guesses, as PrayTimes does
        "Fajr": angle_time(FAJR_ANGLE, 5 / 24, True),
        "Sunrise": angle_time(SUNSET_ANGLE, 6 / 24, True),
        "Dhuhr": noon(12 / 24),
        "Asr": asr_time(13 / 24),
        "Maghrib": angle_time(SUNSET_ANGLE, 18 / 24, False),
    }
    shift = utc_offset - lon / 15
    hours = {k: v + shift for k, v in hours.items()}
    hours["Isha"] = hours["Maghrib"] + (2 if hijri(date)[1] == 9 else 1.5)
    start = dt.datetime.combine(date, dt.time())
    # rounded to the minute, as published timetables are
    return {k: start + dt.timedelta(minutes=round(v * 60)) for k, v in hours.items()}


def _here(date):
    loc = config.settings.get("location")
    offset = -time.altzone if time.localtime().tm_isdst > 0 else -time.timezone
    return times(date, loc["latitude"], loc["longitude"], offset / 3600)


def today_and_next(now=None):
    """Today's five prayers and the next one (tomorrow's Fajr after Isha), for the widget."""
    now = now or dt.datetime.now()
    today = _here(now.date())
    upcoming = [(p, today[p]) for p in PRAYERS if today[p] > now]
    nxt = upcoming[0] if upcoming else ("Fajr", _here(now.date() + dt.timedelta(days=1))["Fajr"])
    return {
        "times": [{"name": p, "at": today[p].strftime("%H:%M")} for p in PRAYERS],
        "sunrise": today["Sunrise"].strftime("%H:%M"),
        "next": {"name": nxt[0], "at": nxt[1].strftime("%H:%M"), "in": int((nxt[1] - now).total_seconds())},
    }


# voice

NAMES = {"fajr": "Fajr", "fajir": "Fajr", "dhuhr": "Dhuhr", "duhr": "Dhuhr", "zuhr": "Dhuhr", "thuhr": "Dhuhr",
         "asr": "Asr", "maghrib": "Maghrib", "magrib": "Maghrib", "isha": "Isha", "ishaa": "Isha"}
ASKED = re.compile(r"\b(prayers?|salah|salat|adhan|azan|athan|" + "|".join(NAMES) + r")\b", re.I)


def asked(text):
    """The prayer request in a sentence, or None: ("prayer_times", {"prayer": ..., "alarm": ...})."""
    if not ASKED.search(text):
        return None
    name = next((NAMES[w.lower()] for w in re.findall(r"[\w']+", text) if w.lower() in NAMES), None)
    return "prayer_times", {
        "prayer": name,
        "alarm": bool(re.search(r"\b(alarm|wake me|remind me)\b", text, re.I)),
        "tomorrow": bool(re.search(r"\btomorrow\b", text, re.I)),
        "all": name is None and bool(re.search(r"\b(times|all|schedule|timetable)\b", text, re.I)),
    }


def prayer_times(prayer=None, alarm=False, tomorrow=False, all=False, timers=None, now=None):
    now = now or dt.datetime.now()
    today = _here(now.date())
    next_day = _here(now.date() + dt.timedelta(days=1))
    if all:
        day, label = (next_day, "Tomorrow") if tomorrow else (today, "Today")
        return f"{label}: " + ", ".join(f"{p} at {say_time(day[p])}" for p in PRAYERS) + "."
    if prayer is None and not alarm:
        upcoming = [p for p in PRAYERS if today[p] > now]
        if not upcoming:
            return f"Isha has passed. Fajr tomorrow is at {say_time(next_day['Fajr'])}."
        p = upcoming[0]
        left = say_duration(round((today[p] - now).total_seconds() / 60) * 60)
        rest = ", ".join(f"{q} at {say_time(today[q])}" for q in upcoming[1:])
        return f"{p} is in {left}, at {say_time(today[p])}." + (f" Then {rest}." if rest else "")
    prayer = prayer or "Fajr"
    if tomorrow or today[prayer] <= now:
        at, day = next_day[prayer], "tomorrow"
    else:
        at, day = today[prayer], "today"
    if alarm and timers is not None:
        return timers.set_alarm(at.strftime("%H:%M"), None if day == "today" else "tomorrow")
    when = "" if day == "today" else " tomorrow"
    seconds = (at - now).total_seconds()
    if seconds > 12 * 3600:  # "in 25 hours" doesn't help
        return f"{prayer} is{when} at {say_time(at)}."
    return f"{prayer} is{when} at {say_time(at)}, in {say_duration(round(seconds / 60) * 60)}."
