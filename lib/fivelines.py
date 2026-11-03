#!/usr/bin/env python3
"""Lines 2-5 of the five-line status line (`lines = 5`).

    left  ✻ claude 7d 30% →Wed 04:00 │ ◎ codex 5h 1% →18:14 · 7d 31% │ ⬡ cursor+grok 19% →Thu │ ✦ agy gemini 100% · claude+gpt 93% · argon 0% →Fri
    today ▶ 1 running │ ✓ 5 done │ ✋ 3 need you │ ✗ 2 failed · ↻ 1 retried │ ⏸ 1 waiting on limit
    older ✋ 4 need you │ ✗ 1 failed │ oldest 6d (pharos-reviews)
    hosts studio 82% free · 22% cpu │ laptop 49% · 45% │ backup 73% · 16%

Every plan number is the amount LEFT (100 - used). Only caches are read: the codex
cache the status line writes, grok.line, antigravity.json, machines.json from
`limitline refresh`, and ~/.pharos/summary.json (or Pharos run states). Nothing here
runs a model CLI, ssh, or the network. Inputs from the status line come in as
LL_* environment variables. Always prints something sane and exits 0.
"""

import glob
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime

MARKS = {
    "unicode": {"claude": "✻", "codex": "◎", "cursor": "⬡", "agy": "✦",
                "running": "▶", "done": "✓", "need_you": "✋", "failed": "✗", "retried": "↻", "waiting_limit": "⏸"},
    "none": {},
}
LABELS = {"running": "running", "done": "done", "need_you": "need you", "failed": "failed",
          "retried": "retried", "waiting_limit": "waiting on limit"}
KEYS = ("running", "done", "need_you", "failed", "retried", "waiting_limit")
OPEN = ("running", "need_you", "failed", "waiting_limit")
AGY_NAMES = (("Gemini Models", "gemini"), ("Claude and GPT models", "claude+gpt"), ("Gemini 4 Argon", "argon"))
SEP = " │ "
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def env(name, default=""):
    return os.environ.get(name, default)


def now_epoch():
    try:
        return int(env("LIMITLINE_NOW") or time.time())
    except ValueError:
        return int(time.time())


def cache_dir():
    base = env("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "limitline")


def pharos_home():
    return env("LIMITLINE_PHAROS_HOME") or os.path.join(os.path.expanduser("~"), ".pharos")


def num(value):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if out != out else out


def read_json(path):
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data


# ---- drawing -------------------------------------------------------------------------


class Style:
    def __init__(self):
        self.color = env("LL_COLOR", "1") == "1" and env("LL_THEME") != "mono"
        theme = env("LL_MARKS", "unicode").strip().lower() or "unicode"
        self.marks = MARKS.get(theme, MARKS["unicode"])

    def paint(self, code, text):
        return f"\x1b[{code}m{text}\x1b[0m" if self.color and code else text

    def mark(self, key):
        glyph = self.marks.get(key, "")
        return glyph + " " if glyph else ""


def width(text):
    total = 0
    for ch in ANSI.sub("", text):
        if unicodedata.combining(ch):
            continue
        total += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return total


def left_code(left):
    if left is None:
        return "2"
    if left <= 10:
        return "31"
    if left <= 25:
        return "33"
    return ""


def reset_label(epoch, now):
    if not epoch:
        return ""
    at = datetime.fromtimestamp(epoch)
    if epoch - now < 20 * 3600 and at.date() == datetime.fromtimestamp(now).date():
        return at.strftime("%H:%M")
    return at.strftime("%a %H:%M")


def age_label(seconds):
    if seconds < 3600:
        return f"{max(1, seconds // 60)}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


class Cell:
    """One plan window. `left` None means no reading."""

    def __init__(self, name, left, reset=None, age=None, estimate=False):
        self.name, self.left, self.reset, self.age, self.estimate = name, left, reset, age, estimate

    def text(self, style, now, resets=True):
        if self.left is None:
            age = f" {age_label(self.age)} ago" if self.age else ""
            return f"{self.name} " + style.paint("2", "—" + age)
        pct = f"{'~' if self.estimate else ''}{int(round(self.left))}%"
        out = f"{self.name} " + style.paint(left_code(self.left), pct)
        if resets and self.reset and self.left <= 25:
            out += " " + style.paint("2", "→" + reset_label(self.reset, now))
        return out


# ---- line 2: what's left ---------------------------------------------------------------


def window_cell(name, used, reset, now):
    used = num(used)
    reset = int(num(reset) or 0) or None
    if used is None or (reset and reset <= now):
        return None
    return Cell(name, max(0.0, 100.0 - used), reset)


def claude_cells(now):
    cells = []
    for name, used_var, reset_var in (("5h", "LL_CLAUDE5", "LL_CLAUDE5_RESET"), ("7d", "LL_CLAUDE7", "LL_CLAUDE7_RESET")):
        cell = window_cell(name, env(used_var), env(reset_var), now)
        if cell:
            cells.append(cell)
    if not cells:
        data = read_json(os.path.join(cache_dir(), "claude.json")) or {}
        for window in data.get("windows") or []:
            cell = window_cell(str(window.get("name") or "7d"), window.get("used_pct"), window.get("resets_at"), now)
            if cell:
                cells.append(cell)
    return cells or [Cell("7d", None)]


def codex_cells(now):
    values = [env("LL_CODEX5"), env("LL_CODEX5_RESET"), env("LL_CODEX7"), env("LL_CODEX7_RESET")]
    if not any(values):
        path = env("LL_CODEX_CACHE")
        try:
            with open(path, encoding="utf-8") as handle:
                parts = handle.read().split()
            if len(parts) >= 6 and parts[1] == "1":
                values = [p if p != "-" else "" for p in parts[2:6]]
        except (OSError, TypeError):
            pass
    cells = [c for c in (window_cell("5h", values[0], values[1], now), window_cell("7d", values[2], values[3], now)) if c]
    return cells or [Cell("7d", None)]


def cursor_cell(now):
    path = os.path.join(cache_dir(), "grok.line")
    try:
        with open(path, encoding="utf-8") as handle:
            first = handle.readline().strip()
            flags = handle.readline().split()
        age = now - int(os.path.getmtime(path))
    except OSError:
        return None
    if not first.startswith("cursor+grok"):
        return None
    used = num(flags[0]) if flags else None
    if used is None:
        match = re.search(r"(\d+)%", first)
        used = num(match.group(1)) if match else None
    estimate = "~" in first.split("·")[0]
    reset = None
    match = re.search(r"·\s*(?:resets\s+)?([A-Z][a-z]{2})\s+(\d{1,2}):(\d{2})", first)
    if match:
        reset = next_weekday(match.group(1), int(match.group(2)), int(match.group(3)), now)
    if used is None:
        return Cell("cursor+grok", None, age=age)
    return Cell("cursor+grok", max(0.0, 100.0 - used), reset, estimate=estimate)


def next_weekday(day, hour, minute, now):
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    if day not in names:
        return None
    base = datetime.fromtimestamp(now)
    for ahead in range(8):
        cand = base.replace(hour=hour, minute=minute, second=0, microsecond=0).timestamp() + ahead * 86400
        if datetime.fromtimestamp(cand).strftime("%a") == day and cand > now:
            return int(cand)
    return None


def agy_cells(now):
    data = read_json(env("LIMITLINE_AGY_USAGE") or os.path.join(cache_dir(), "antigravity.json"))
    if not isinstance(data, dict) or not isinstance(data.get("buckets"), list):
        return [Cell("gemini", None)]
    observed = int(num(data.get("observed_at")) or 0)
    if now - observed > 7 * 86400:
        return [Cell("gemini", None, age=now - observed if observed else None)]
    cells = []
    for group, name in AGY_NAMES:
        best = None
        for bucket in data["buckets"]:
            if not isinstance(bucket, dict) or bucket.get("group") != group:
                continue
            cell = window_cell(name, bucket.get("used_pct"), bucket.get("resets_at"), now)
            if cell and (best is None or cell.left < best.left):
                best = cell
        if best:
            cells.append(best)
    return cells or [Cell("gemini", None)]


def left_parts(now):
    """[(mark key, label, [cells])] in the fixed order."""
    parts = [("claude", "claude", claude_cells(now)), ("codex", "codex", codex_cells(now))]
    cursor = cursor_cell(now)
    if cursor:
        parts.append(("cursor", "", [cursor]))
    parts.append(("agy", "agy", agy_cells(now)))
    return parts


def render_left(style, now, resets=True, drop_agy_3p=False):
    out = []
    for key, label, cells in left_parts(now):
        if drop_agy_3p:
            cells = [c for c in cells if c.name != "claude+gpt"]
        body = " · ".join(c.text(style, now, resets) for c in cells)
        out.append(style.mark(key) + (label + " " if label else "") + body)
    return style.paint("2", "left ") + " " + SEP.join(out)


# ---- lines 3 and 4: jobs ---------------------------------------------------------------


def classify(state, retried):
    status = state.get("status") or ""
    if str(state.get("id")) in retried and status not in ("done", "merged", "no-changes"):
        return "retried"
    if status in ("starting", "running", "stalled"):
        return "running"
    if status in ("done", "merged", "no-changes"):
        return "done"
    if status == "awaiting-verify":
        commits = state.get("commits")
        count = len(commits) if isinstance(commits, list) else int(num(commits) or 0)
        return "need_you" if count else "done"
    if status == "verify-failed":
        return "need_you"
    if status == "paused-quota":
        return "waiting_limit"
    if status == "failed":
        return "failed"
    if status == "stopped" and state.get("exit_code") not in (None, 0, -15, 143):
        return "failed"
    return None


def started_at(state):
    value = num(state.get("started_at"))
    if value:
        return value
    try:
        return datetime.strptime(str(state.get("id") or "")[:15], "%Y%m%d-%H%M%S").timestamp()
    except ValueError:
        return None


def summarize_states(states, now, window_days=7.0):
    midnight = datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    floor = now - window_days * 86400
    retried = set()
    for s in states:
        for key in ("retried_by", "handoff_to"):
            if s.get(key):
                retried.add(str(s.get("id")))
        for key in ("retry_of", "continued_from"):
            if s.get(key):
                retried.add(str(s.get(key)))
    today, older, oldest = dict.fromkeys(KEYS, 0), dict.fromkeys(KEYS, 0), None
    for s in states:
        bucket, start = classify(s, retried), started_at(s)
        if bucket is None or start is None:
            continue
        if start >= midnight:
            today[bucket] += 1
        elif bucket in OPEN and start >= floor:
            older[bucket] += 1
            if oldest is None or start < oldest[0]:
                oldest = (start, s.get("id"), os.path.basename(str(s.get("repo") or "").rstrip("/")))
    oldest_open = None
    if oldest:
        oldest_open = {"id": oldest[1], "repo": oldest[2], "age_hours": round((now - oldest[0]) / 3600, 1)}
    return {"today": today, "older": older, "oldest_open": oldest_open}


def job_summary(now):
    home = pharos_home()
    path = os.path.join(home, "summary.json")
    data = read_json(path)
    try:
        fresh = now - os.path.getmtime(path) < 600
    except OSError:
        fresh = False
    if isinstance(data, dict) and fresh and isinstance(data.get("today"), dict):
        generated = num(data.get("generated_at")) or now
        same_day = datetime.fromtimestamp(generated).date() == datetime.fromtimestamp(now).date()
        if same_day:
            return data
    states = []
    for name in glob.glob(os.path.join(home, "runs", "*", "state.json")):
        state = read_json(name)
        if isinstance(state, dict):
            states.append(state)
    if not states:
        return None
    return summarize_states(states, now)


def job_cells(style, bucket, only_nonzero):
    cells = []
    for key in KEYS:
        count = int(num(bucket.get(key)) or 0)
        if only_nonzero and not count:
            continue
        text = f"{style.mark(key)}{count} {LABELS[key]}"
        if not count:
            text = style.paint("2", text)
        elif key in ("need_you", "failed"):
            text = style.paint("33" if key == "need_you" else "31", text)
        cells.append(text)
    return cells


def join_jobs(cells):
    # "failed · retried" sit together, as in the approved mockup.
    out, i = [], 0
    while i < len(cells):
        plain = ANSI.sub("", cells[i])
        if "failed" in plain and i + 1 < len(cells) and "retried" in ANSI.sub("", cells[i + 1]):
            out.append(cells[i] + " · " + cells[i + 1])
            i += 2
            continue
        out.append(cells[i])
        i += 1
    return SEP.join(out)


def render_today(style, summary):
    return style.paint("2", "today") + " " + join_jobs(job_cells(style, summary["today"], False))


def render_older(style, summary, with_oldest=True):
    cells = job_cells(style, summary.get("older") or {}, True)
    if not cells:
        return ""
    line = style.paint("2", "older") + " " + join_jobs(cells)
    oldest = summary.get("oldest_open") if with_oldest else None
    if oldest:
        hours = num(oldest.get("age_hours")) or 0
        age = f"{int(hours // 24)}d" if hours >= 24 else f"{int(hours)}h"
        line += SEP + style.paint("2", f"oldest {age} ({oldest.get('repo') or oldest.get('id')})")
    return line


# ---- line 5: hosts ---------------------------------------------------------------------


def render_hosts(style, now, with_cpu=True):
    data = read_json(os.path.join(cache_dir(), "machines.json"))
    hosts = data.get("hosts") if isinstance(data, dict) else None
    if not isinstance(hosts, list) or not hosts:
        return ""
    cells = []
    for i, host in enumerate(hosts):
        if not isinstance(host, dict):
            continue
        name = str(host.get("name") or "host")
        if host.get("reachable") is False:
            cells.append(f"{name} " + style.paint("2", "offline"))
            continue
        free, load = num(host.get("free_pct")), num(host.get("load_pct"))
        bits = []
        if free is not None:
            code = "31" if host.get("mem_warn") else ""
            bits.append(style.paint(code, f"{int(free)}%") + (" mem free" if i == 0 else ""))
        if with_cpu and load is not None:
            bits.append(f"{int(load)}%" + (" cpu" if i == 0 else ""))
        cells.append(f"{name} " + (" · ".join(bits) if bits else style.paint("2", "—")))
    return style.paint("2", "hosts") + " " + SEP.join(cells)


# ---- fit and print ---------------------------------------------------------------------


def fit(variants, columns):
    """The first variant that fits, else the last one."""
    if columns <= 0:
        return variants[0]
    for line in variants:
        if width(line) <= columns:
            return line
    return variants[-1]


def build(now=None, columns=None):
    now = now_epoch() if now is None else now
    if columns is None:
        columns = int(num(env("LL_COLUMNS")) or 0)
    style = Style()
    lines = [fit([
        render_left(style, now),
        render_left(style, now, resets=False),
        render_left(style, now, resets=False, drop_agy_3p=True),
    ], columns)]
    summary = job_summary(now)
    if summary:
        lines.append(fit([render_today(style, summary)], columns))
        older = fit([render_older(style, summary), render_older(style, summary, with_oldest=False)], columns)
        if older:
            lines.append(older)
    hosts = fit([render_hosts(style, now), render_hosts(style, now, with_cpu=False)], columns)
    if hosts:
        lines.append(hosts)
    return lines


def main():
    try:
        sys.stdout.write("\n".join(build()) + "\n")
    except Exception:  # the status line must never fail
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
