#!/usr/bin/env python3
"""Terminal and markdown usage report from local snapshots only."""
import os
from datetime import datetime, timezone


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "limitline")


def now_epoch():
    try:
        return int(os.environ.get("LIMITLINE_NOW") or "0")
    except ValueError:
        return 0


def bar(pct, width=10):
    try:
        value = float(pct)
    except (TypeError, ValueError):
        value = 0
    if value < 0:
        value = 0
    if value > 100:
        value = 100
    filled = int(value * width / 100 + 0.5)
    return "█" * filled + "░" * (width - filled)


def rel(epoch, now):
    if not isinstance(epoch, (int, float)):
        return ""
    delta = int(epoch) - now
    if delta >= 86400:
        return datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%a %H:%M")
    if delta < 0:
        delta = 0
    hours, minutes = divmod(delta // 60, 60)
    if hours:
        return "%dh%dm" % (hours, minutes)
    return "%dm" % minutes


def read_tsv(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    try:
        handle = open(path)
    except OSError:
        return rows
    with handle:
        for line in handle:
            parts = line.split()
            if len(parts) >= 2:
                rows.append(parts)
    return rows


def day_bars(path):
    last = {}
    for parts in read_tsv(path):
        try:
            stamp = int(float(parts[0]))
            pct = float(parts[1])
        except ValueError:
            continue
        day = datetime.fromtimestamp(stamp, timezone.utc).strftime("%Y-%m-%d")
        last[day] = pct
    return sorted(last.items())


def activity_rows():
    rows = []
    for parts in read_tsv(os.path.join(cache_dir(), "activity.tsv")):
        if len(parts) < 3:
            continue
        project = parts[2]
        if "/" in project or project in (".", "..") or "@" in project:
            continue
        try:
            hour = int(parts[1])
        except ValueError:
            continue
        rows.append((hour, project))
    return rows


def busiest(rows):
    counts = {}
    for hour, _project in rows:
        counts[hour] = counts.get(hour, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def projects(rows):
    counts = {}
    for _hour, project in rows:
        counts[project] = counts.get(project, 0) + 1
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:5]


def window_lines(rows, now):
    lines = []
    resets = []
    for row in rows:
        provider = row.get("provider") or "tool"
        windows = [item for item in (row.get("windows") or []) if isinstance(item, dict)]
        if not windows:
            continue
        lines.append(provider)
        for window in windows:
            name = window.get("name") or "limit"
            used = window.get("used_pct")
            if not isinstance(used, (int, float)) or isinstance(used, bool):
                continue
            shown = int(used + 0.5)
            extra = ""
            machines = window.get("machines")
            if isinstance(machines, int) and machines > 1:
                extra = " ×%d" % machines
            when = rel(window.get("resets_at"), now)
            reset = ("  " + when) if when else ""
            mark = "~" if window.get("estimate") else ""
            lines.append("  %s  %s  %s%d%%%s%s" % (name, bar(shown), mark, shown, extra, reset))
            if when:
                resets.append("%s %s  %s" % (provider, name, when))
    return lines, resets


def render(rows, markdown=False):
    now = now_epoch() or int(datetime.now(timezone.utc).timestamp())
    windows, resets = window_lines(rows, now)
    days = day_bars(os.path.join(cache_dir(), "history-5h.tsv"))
    events = activity_rows()
    hours = busiest(events)
    names = projects(events)
    if markdown:
        return _markdown(windows, days, hours, names, resets)
    return _plain(windows, days, hours, names, resets)


def _plain(windows, days, hours, names, resets):
    out = ["limitline report", ""]
    if windows:
        out.append("usage")
        out.extend(windows)
    else:
        out.append("usage")
        out.append("  no local windows yet")
    out.append("")
    out.append("by day")
    if days:
        for day, pct in days[-7:]:
            shown = int(pct + 0.5)
            out.append("  %s  %s  %d%%" % (day, bar(shown), shown))
    else:
        out.append("  no local history yet")
    out.append("")
    out.append("busiest hours")
    if hours:
        peak = hours[0][1] or 1
        for hour, count in hours[:6]:
            width = int(count * 10 / peak + 0.5)
            if width < 1:
                width = 1
            out.append("  %02d  %s  %d" % (hour, "█" * width, count))
    else:
        out.append("  no local history yet")
    out.append("")
    out.append("projects")
    if names:
        for name, count in names:
            out.append("  %s  %d" % (name, count))
    else:
        out.append("  no local history yet")
    out.append("")
    out.append("resets")
    if resets:
        for item in resets:
            out.append("  " + item)
    else:
        out.append("  none scheduled")
    return "\n".join(out) + "\n"


def _markdown(windows, days, hours, names, resets):
    out = ["# limitline report", "", "## Usage"]
    if windows:
        for line in windows:
            if line.startswith("  "):
                out.append("- " + line.strip())
            else:
                out.append("")
                out.append("### " + line)
    else:
        out.append("")
        out.append("No local windows yet.")
    out.extend(["", "## By day"])
    if days:
        for day, pct in days[-7:]:
            out.append("- %s: %d%%" % (day, int(pct + 0.5)))
    else:
        out.append("")
        out.append("No local history yet.")
    out.extend(["", "## Busiest hours"])
    if hours:
        for hour, count in hours[:6]:
            out.append("- %02d: %d" % (hour, count))
    else:
        out.append("")
        out.append("No local history yet.")
    out.extend(["", "## Projects"])
    if names:
        for name, count in names:
            out.append("- %s: %d" % (name, count))
    else:
        out.append("")
        out.append("No local history yet.")
    out.extend(["", "## Resets"])
    if resets:
        for item in resets:
            out.append("- " + item)
    else:
        out.append("")
        out.append("None scheduled.")
    out.append("")
    return "\n".join(out)
