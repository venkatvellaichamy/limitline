#!/usr/bin/env python3
"""The fleet segment and the Runs list, from Pharos's summary.json. Reads nothing else.

Pharos decides what each run is (running, needs review, failed, waiting on a limit)
and which runs are recent; this only formats it. Without Pharos there is no fleet.
"""
import json, os, sys, time


def now_epoch():
    try:
        return int(os.environ.get("LIMITLINE_NOW") or time.time())
    except ValueError:
        return int(time.time())


def pharos_home():
    return os.environ.get("LIMITLINE_PHAROS_HOME") or os.path.join(os.path.expanduser("~"), ".pharos")


def summary_path():
    return os.environ.get("LIMITLINE_PHAROS_SUMMARY") or os.path.join(pharos_home(), "summary.json")


def read_summary():
    try:
        with open(summary_path(), encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("today"), dict) else None


def counts(summary):
    """Open work, today and older: run, verify (needs you), failed, warn (waiting on a limit)."""
    out = {"run": 0, "verify": 0, "failed": 0, "warn": 0}
    for bucket in ("today", "older"):
        block = summary.get(bucket) if isinstance(summary.get(bucket), dict) else {}
        for key, name in (("running", "run"), ("need_you", "verify"), ("failed", "failed"), ("waiting_limit", "warn")):
            value = block.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                out[name] += value
    return out


def format_segment(found):
    parts = []
    if found.get("run"):
        parts.append("%d run" % found["run"])
    if found.get("verify"):
        parts.append("%d verify" % found["verify"])
    if found.get("failed"):
        parts.append("%d ✗" % found["failed"])
    if not parts and not found.get("warn"):
        return ""
    if not parts:
        return "⚙ ⚠"
    text = "⚙ " + " · ".join(parts)
    if found.get("warn"):
        text += " ⚠"
    return text


def segment_text(summary=None):
    summary = read_summary() if summary is None else summary
    return format_segment(counts(summary)) if summary else ""


def age_text(seconds):
    seconds = max(0, int(seconds or 0))
    if seconds < 60:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm" % (seconds // 60)
    if seconds < 86400:
        hours, minutes = divmod(seconds // 60, 60)
        return "%dh%02dm" % (hours, minutes)
    return "%dd" % (seconds // 86400)


def format_run(row):
    return "%s  %s  %s  %s  %s" % (str(row.get("id") or "-")[:12], row.get("tool") or "-", row.get("repo") or "-",
                                   row.get("status") or "-", age_text(row.get("age_s")))


def recent(summary=None):
    summary = read_summary() if summary is None else summary
    rows = (summary or {}).get("recent")
    return [r for r in rows or [] if isinstance(r, dict)]


def run_lines(rows=None, swiftbar=False):
    lines = []
    for row in recent() if rows is None else rows:
        line = format_run(row)
        log = row.get("log")
        if swiftbar and log and os.path.isfile(log):
            line += " | bash=/usr/bin/open param1=%s terminal=false" % log
        lines.append(line)
    return lines


def main():
    text = segment_text()
    if text:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
