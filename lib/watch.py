#!/usr/bin/env python3
"""One frame of the side-by-side watch view."""
import os, sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grokline
import xaiplan


def brief(data):
    if data.get("provider") == xaiplan.PROVIDER:
        return xaiplan.brief(data) or "no reading"
    if data.get("provider") == "antigravity":
        import antigravity
        return antigravity.brief(data)
    if data.get("note"):
        return str(data["note"])
    windows = data.get("windows") or []
    if not windows:
        if data.get("provider") == "grok":
            # The plan goes in the Grok block below; the column keeps the short count.
            tokens = grokline.week_tokens(data)
            if tokens is not None:
                return "7d %s tok" % grokline.short_tokens(tokens)
            if data.get("plan"):
                return "plan only"
            if data.get("source") == "usage.json":
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
            if window.get("estimate"):
                text += " estimate"
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
        names.append(xaiplan.label(row)[:width].ljust(width))
        values.append(brief(row)[:width].ljust(width))
    lines = [
        "limitline watch  " + stamp,
        "".join(names).rstrip(),
        "".join(values).rstrip(),
    ]
    for row in rows:
        if row.get("provider") == "grok" and not row.get("windows"):
            text = grokline.brief(row, long=True)
            if text:
                lines.append("Grok")
                lines.append(text)
        if row.get("provider") == xaiplan.PROVIDER:
            text = xaiplan.brief(row, long=True)
            if text:
                lines.append("Cursor + Grok plan")
                lines.append(text)
    for line in extra or []:
        if line:
            lines.append(line)
    return "\n".join(lines) + "\n"
