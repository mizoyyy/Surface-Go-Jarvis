"""Calendar events from an iCal (.ics) link, such as Google Calendar's "secret address in iCal format".

Handles single events, all-day events, time zones, and daily/weekly repeats with UNTIL,
COUNT, INTERVAL and EXDATE. Other repeat rules are shown on their first date only.
"""

import datetime as dt
import re
import time
from zoneinfo import ZoneInfo

import httpx

from .. import config
from .common import DAY_NAMES, day_phrase, resolve_day, say_time

WEEKDAYS = {d[:2].upper(): i for i, d in enumerate(DAY_NAMES)}
LOCAL = dt.datetime.now().astimezone().tzinfo


def _unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()


def _parse_dt(value, params):
    """Returns (datetime in local time, all_day)."""
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        return dt.datetime.strptime(value[:8], "%Y%m%d"), True
    stamp = dt.datetime.strptime(value[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        stamp = stamp.replace(tzinfo=dt.timezone.utc)
    elif "TZID" in params:
        try:
            stamp = stamp.replace(tzinfo=ZoneInfo(params["TZID"]))
        except Exception:
            stamp = stamp.replace(tzinfo=LOCAL)
    else:
        stamp = stamp.replace(tzinfo=LOCAL)
    return stamp.astimezone(LOCAL).replace(tzinfo=None), False


def parse_ics(text):
    events, cur = [], None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {"exdates": set()}
        elif line == "END:VEVENT" and cur is not None:
            if "start" in cur:
                events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            head, value = line.split(":", 1)
            name, *raw_params = head.split(";")
            params = dict(p.split("=", 1) for p in raw_params if "=" in p)
            if name == "SUMMARY":
                cur["title"] = value.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ")
            elif name == "DTSTART":
                cur["start"], cur["all_day"] = _parse_dt(value, params)
            elif name == "RRULE":
                cur["rrule"] = dict(p.split("=", 1) for p in value.split(";") if "=" in p)
            elif name == "EXDATE":
                for v in value.split(","):
                    cur["exdates"].add(_parse_dt(v, params)[0].date())
            elif name == "STATUS" and value == "CANCELLED":
                cur["cancelled"] = True
    return [e for e in events if not e.get("cancelled")]


def _occurs_on(event, date):
    start = event["start"].date()
    if date < start or date in event["exdates"]:
        return False
    rule = event.get("rrule")
    if not rule:
        return date == start
    if "UNTIL" in rule and date > _parse_dt(rule["UNTIL"], {})[0].date():
        return False
    interval = int(rule.get("INTERVAL", 1))
    freq = rule.get("FREQ")
    if freq == "DAILY":
        n = (date - start).days
        ok = n % interval == 0
        index = n // interval
    elif freq == "WEEKLY":
        days = [WEEKDAYS[d[-2:]] for d in rule.get("BYDAY", "").split(",") if d[-2:] in WEEKDAYS] \
            or [start.weekday()]
        week = ((date - start).days + start.weekday()) // 7
        ok = date.weekday() in days and week % interval == 0
        index = week // interval * len(days) + sorted(days).index(date.weekday()) if ok else 0
    elif freq == "YEARLY":
        ok = (date.month, date.day) == (start.month, start.day)
        index = date.year - start.year
    else:
        return date == start
    return ok and ("COUNT" not in rule or index < int(rule["COUNT"]))


class Calendar:
    def __init__(self):
        self.events, self.fetched, self.url = [], 0.0, None

    def refresh(self, force=False):
        url = config.settings.get("calendar_ics_url")
        if not url:
            self.events = []
            return
        if force or url != self.url or time.time() - self.fetched > 900:
            r = httpx.get(url, timeout=20, follow_redirects=True)
            r.raise_for_status()
            self.events, self.fetched, self.url = parse_ics(r.text), time.time(), url

    def on(self, date):
        out = []
        for e in self.events:
            if _occurs_on(e, date):
                start = dt.datetime.combine(date, e["start"].time())
                out.append({"title": e.get("title", "(no title)"), "all_day": e["all_day"],
                            "start": start.isoformat(timespec="minutes")})
        return sorted(out, key=lambda e: (not e["all_day"], e["start"]))

    def upcoming(self, days=3):
        today = dt.date.today()
        return [{"date": (today + dt.timedelta(days=i)).isoformat(),
                 "events": self.on(today + dt.timedelta(days=i))} for i in range(days)]

    def calendar_events(self, day="today"):
        if not config.settings.get("calendar_ics_url"):
            return "Your calendar isn't connected yet. You can add it in the settings."
        self.refresh()
        events = self.on(resolve_day(day))
        when = day_phrase(day)
        if not events:
            return f"You have nothing on your calendar {when}."
        parts = []
        for e in events[:5]:
            if e["all_day"]:
                parts.append(e["title"])
            else:
                parts.append(f"{e['title']} at {say_time(dt.datetime.fromisoformat(e['start']))}")
        more = f", and {len(events) - 5} more" if len(events) > 5 else ""
        count = "one event" if len(events) == 1 else f"{len(events)} events"
        return f"You have {count} {when}: " + "; ".join(parts) + more + "."
