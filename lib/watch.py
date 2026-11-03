#!/usr/bin/env python3
"""One frame of the side-by-side watch view."""
import os
from datetime import datetime, timezone


def brief(data):
    windows = data.get("windows") or []
    if not windows:
        if data.get("provider") == "grok" and data.get("source") == "usage.json":
            return "session tokens only"
        if data.get("source") == "none":
            return "no local quota"
        return "no window"
    parts = []
    for window in windows:
        if not isinstance(window, dict):
            continue
        name = window.get("name") or "limit"
        used = window.get("used_pct")
        text = name
        if isinstance(used, (int, float)) and not isinstance(used, bool):
            text += " %s%d%%" % ("~" if window.get("estimate") else "", int(used + 0.5))
        machines = window.get("machines")
        if isinstance(machines, int) and machines > 1:
            text += " ×%d" % machines
        parts.append(text)
    text = " · ".join(parts)
    if data.get("stale"):
        text += " stale"
    return text or "no window"


def frame(rows, extra=None):
    try:
        now = int(os.environ.get("LIMITLINE_NOW") or "0")
    except ValueError:
        now = 0
    if now:
        stamp = datetime.fromtimestamp(now, timezone.utc).strftime("%H:%M:%S")
    else:
        stamp = datetime.now().strftime("%H:%M:%S")
    width = 22
    names = []
    values = []
    for row in rows:
        names.append(str(row.get("provider") or "tool")[:width].ljust(width))
        values.append(brief(row)[:width].ljust(width))
    lines = [
        "limitline watch  " + stamp,
        "".join(names).rstrip(),
        "".join(values).rstrip(),
    ]
    for line in extra or []:
        if line:
            lines.append(line)
    return "\n".join(lines) + "\n"
