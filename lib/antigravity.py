#!/usr/bin/env python3
"""Antigravity rows for display. Pharos measures them (`pharos usage`, which runs agy's
read-only `/usage`); limitline only formats what usage.json holds."""
import os, time
from datetime import datetime, timezone


def now_epoch():
    try:
        return int(os.environ.get("LIMITLINE_NOW") or time.time())
    except ValueError:
        return int(time.time())


def number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def to_epoch(value):
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        out = number(value)
        if out is None:
            return None
        # Milliseconds, if the CLI ever sends them.
        return int(out / 1000) if out > 1e11 else int(out)
    text = str(value).strip()
    if text.isdigit():
        return to_epoch(int(text))
    iso = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        stamp = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return int(stamp.timestamp())


def clean(text, limit=40):
    return "".join(ch for ch in str(text or "") if ch.isprintable()).strip()[:limit]


def age_text(seconds):
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "<1m"
    if seconds < 3600:
        return "%dm" % (seconds // 60)
    if seconds < 86400:
        return "%dh" % (seconds // 3600)
    return "%dd" % (seconds // 86400)


def event_text(data, now=None):
    event = data.get("event")
    if not isinstance(event, dict) or to_epoch(event.get("at")) is None:
        return ""
    now = now_epoch() if now is None else now
    text = "last limit hit %s ago (%s" % (age_text(now - to_epoch(event["at"])), clean(event.get("source")) or "log")
    return text + (", stale)" if event.get("stale") else ")")


def brief(data, now=None):
    """`gemini-5h 0% · gemini-weekly 0% · argon-weekly 100% resets Thu 21:35`, or
    `unknown · last limit hit 2h ago (cli.log)`. Never a percent from an event."""
    import timefmt
    now = now_epoch() if now is None else now
    parts = []
    for window in data.get("windows") or []:
        if not isinstance(window, dict):
            continue
        used = number(window.get("used_pct"))
        if used is None:
            continue
        text = "%s %d%%" % (window.get("name") or "limit", int(used + 0.5))
        if used >= 100 and window.get("resets_at") is not None:
            when = timefmt.day_time(window["resets_at"])
            if when:
                text += " resets " + when
        parts.append(text)
    if parts:
        text = " · ".join(parts)
        if data.get("stale"):
            text += " · %s old" % age_text(now - int(data.get("observed_at") or now))
    else:
        text = "unknown"
    extra = event_text(data, now)
    return text + (" · " + extra if extra else "")
