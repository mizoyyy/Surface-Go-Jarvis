"""Timers and alarms. Saved to state.json so they survive a restart."""

import datetime as dt
import time
import uuid

from .. import config
from .common import DAY_NAMES, resolve_day, say_duration, say_time


class Timers:
    def __init__(self, on_change, on_ring):
        self.on_change, self.on_ring = on_change, on_ring
        saved = config.state_file.get("timers", {})
        now = time.time()
        self.timers = [t for t in saved.get("timers", []) if t["end"] > now]
        self.alarms = [a for a in saved.get("alarms", []) if a["at"] > now - 60]

    def snapshot(self):
        return {"timers": sorted(self.timers, key=lambda t: t["end"]),
                "alarms": sorted(self.alarms, key=lambda a: a["at"])}

    def _changed(self):
        config.state_file.update({"timers": self.snapshot()})
        self.on_change(self.snapshot())

    def tick(self):
        """Called every second; rings anything that is due."""
        now = time.time()
        due = [t for t in self.timers if t["end"] <= now] + [a for a in self.alarms if a["at"] <= now]
        if not due:
            return
        self.timers = [t for t in self.timers if t["end"] > now]
        self.alarms = [a for a in self.alarms if a["at"] > now]
        self._changed()
        for item in due:
            self.on_ring(item)

    # tools

    def set_timer(self, hours=0, minutes=0, seconds=0, label=None):
        total = hours * 3600 + minutes * 60 + seconds
        if total > 24 * 3600:
            return "Timers can be at most 24 hours."
        self.timers.append({"id": uuid.uuid4().hex[:8], "kind": "timer", "label": label or "",
                            "duration": total, "end": time.time() + total})
        self._changed()
        named = f"{label} timer" if label else "Timer"
        return f"{named} set for {say_duration(total)}."

    def _find_timers(self, label):
        if label:
            words = set(label.lower().split())
            return [t for t in self.timers if words & set(t["label"].lower().split())]
        return list(self.timers)

    def cancel_timer(self, label=None):
        found = self._find_timers(label)
        if not found:
            return f"You don't have a {label} timer." if label else "You don't have any timers."
        ids = {t["id"] for t in found}
        self.timers = [t for t in self.timers if t["id"] not in ids]
        self._changed()
        if len(found) == 1:
            name = found[0]["label"]
            return f"{name.capitalize()} timer cancelled." if name else "Timer cancelled."
        return f"Cancelled {len(found)} timers."

    def cancel_by_id(self, item_id):
        self.timers = [t for t in self.timers if t["id"] != item_id]
        self.alarms = [a for a in self.alarms if a["id"] != item_id]
        self._changed()

    def timer_status(self):
        if not self.timers:
            return "You don't have any timers running."
        parts = []
        for t in sorted(self.timers, key=lambda t: t["end"]):
            left = say_duration(max(1, round(t["end"] - time.time())))
            parts.append(f"{left} left on the {t['label']} timer" if t["label"] else f"{left} left")
        return "You have " + "; ".join(parts) + "."

    def set_alarm(self, time, day=None):
        hour, minute = (int(x) for x in time.split(":"))
        now = dt.datetime.now()
        if day:
            date = resolve_day(day)
            at = dt.datetime.combine(date, dt.time(hour, minute))
            if at <= now:
                at += dt.timedelta(days=7)
        else:
            at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if at <= now:
                at += dt.timedelta(days=1)
        self.alarms.append({"id": uuid.uuid4().hex[:8], "kind": "alarm", "label": "",
                            "time": time, "at": at.timestamp()})
        self._changed()
        return f"Alarm set for {say_time(at)} {self._day_words(at)}."

    def cancel_alarm(self, time=None):
        if not self.alarms:
            return "You don't have any alarms."
        if time:
            found = [a for a in self.alarms if a["time"] == time]
            if not found:
                return f"You don't have an alarm at {say_time(dt.datetime.strptime(time, '%H:%M'))}."
        else:
            found = [min(self.alarms, key=lambda a: a["at"])]
        ids = {a["id"] for a in found}
        self.alarms = [a for a in self.alarms if a["id"] not in ids]
        self._changed()
        at = dt.datetime.fromtimestamp(found[0]["at"])
        return f"Cancelled the {say_time(at)} alarm."

    @staticmethod
    def _day_words(at):
        days = (at.date() - dt.date.today()).days
        if days == 0:
            return "today"
        if days == 1:
            return "tomorrow"
        return "on " + DAY_NAMES[at.weekday()].capitalize()
