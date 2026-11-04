#!/usr/bin/env python3
"""Lines 2-5 of the five-line status line (`lines = 5`).

    used  ✻ claude 7d ███▌░ │ ◎ codex 5h ░░░░░ · 7d ███▌░ │ ⬡ cursor+grok ████▏ →Thu │ ✦ agy gemini ░░░░░ · claude+gpt ▍░░░░ · argon █████ →Fri
    today ▶ 1 running │ ✓ 5 done │ ✋ 3 need you │ ✗ 2 failed · ↻ 1 retried │ ⏸ 1 waiting on limit
    older ✋ 4 need you │ ✗ 1 failed │ oldest 6d (pharos-reviews)
    hosts studio 82% free · 22% cpu │ laptop 49% · 45% │ backup 73% · 16%

Every plan bar is the amount USED, like the context meter on line 1: an empty bar is a
fresh allowance, a full bar is spent. `used = "both"` adds the number, `"pct"` shows only
the number. Pharos measures; this only draws:
plans and hosts come from ~/.pharos/usage.json and job counts from ~/.pharos/summary.json.
Without Pharos only Claude's own line is shown (from the status-line input) and the job
and host lines are left out. Nothing here runs a model CLI, ssh, or the network. Inputs
from the status line come in as LL_* environment variables. Always exits 0.
"""

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
        self.animate = env("LL_ANIMATE", "on").strip().lower() not in ("0", "off", "false", "no")
        view = env("LL_PLAN_VIEW", "bar").strip().lower()
        self.view = view if view in VIEWS else "bar"
        self.numbers = self.view == "none" or env("LL_PLAN_NUMBERS", "off").strip().lower() in ("1", "on", "true", "yes")
        self.left = env("LL_PLAN_SHOW", "used").strip().lower() == "left"
        # When to print a window's refill time: "always" (default) or "near-cap" (at the cap)
        self.resets = "near-cap" if env("LL_PLAN_RESETS", "always").strip().lower() in ("near-cap", "cap") else "always"
        self.ascii = env("LL_THEME") == "ascii"

    def paint(self, code, text):
        return f"\x1b[{code}m{text}\x1b[0m" if self.color and code and text else text

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


def used_code(used):
    """The same colours as the meters on line 1: green, yellow from 50, red above 80."""
    if used is None:
        return "2"
    if used > 80:
        return "31"
    if used >= 50:
        return "33"
    return "32"


VIEWS = ("bar", "gauge", "dots", "trend", "cap", "none")
EIGHTHS = " ▏▎▍▌▋▊▉"
LEVELS = "▁▂▃▄▅▆▇█"
DOTS = "○◔◑◕●"
PACE_GAP = 8  # the same gap line 1's pace segment uses


def level(value, ascii=False):
    """One character for 0-100: a vertical eighth, so a row of them is a sparkline."""
    if value is None:
        return "·"
    value = min(100.0, max(0.0, value))
    if ascii:
        return "_.-=+*#@"[min(7, int(value * 8 / 100))]
    return LEVELS[max(0, min(7, -(-int(round(value)) * 8 // 100) - 1))] if value > 0 else LEVELS[0]


def dot(value, ascii=False):
    value = min(100.0, max(0.0, value))
    if ascii:
        return "0" if value < 12.5 else "o" if value < 62.5 else "O"
    return DOTS[int(value / 25 + 0.5)]


def window_seconds(name):
    """5-hour windows are 5h; everything else Pharos reports (7d, week, weekly) is a week."""
    return 5 * 3600 if "5h" in str(name) else 7 * 86400
BAR_WIDTH = 5
RESET_FROM = 75  # show when a window refills once it is this full (Pharos's default cap)


def used_bar(used, cells=BAR_WIDTH, ascii=False):
    """A small meter in eighths of a cell, so 70% and 82% look different in 5 cells."""
    used = min(100.0, max(0.0, used))
    if ascii:
        full = int(used * cells / 100 + 0.5)
        return "#" * full, "-" * (cells - full)
    steps = int(used * cells * 8 / 100 + 0.5)
    full, part = divmod(steps, 8)
    if full >= cells:
        return "█" * cells, ""
    filled = "█" * full + (EIGHTHS[part] if part else "")
    return filled, "░" * (cells - full - (1 if part else 0))


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
    """One plan window. `used` None means no reading. Pharos's numbers are always used; with
    `plan_show = "left"` the display shows 100 - used, but colours and the cap still follow used."""

    def __init__(self, name, used, reset=None, age=None, estimate=False, window=None):
        self.name, self.used, self.reset, self.age, self.estimate = name, used, reset, age, estimate
        self.window = window or name  # the window id in Pharos's files
        self.cap = None               # set from usage.json cap_pct
        self.trend = None             # 7 values from usage-report.json daily, used
        self.fresh_change = False     # set by mark_changes: shown bold for a short while

    def shown(self, used):
        return None if used is None else (100.0 - used if self.left else used)

    def pace_ahead(self, now):
        if not self.reset:
            return False
        length = window_seconds(self.window)
        elapsed = 1 - (self.reset - now) / length
        return 0 <= elapsed <= 1 and self.used - elapsed * 100 >= PACE_GAP

    def meter(self, style, now, code, cells):
        value = self.shown(self.used)
        dim = lambda text: style.paint("2", text)
        if style.view == "gauge":
            return style.paint(code, level(value, style.ascii)) if value > 0 else dim(level(0, style.ascii))
        if style.view == "dots":
            return style.paint(code, dot(value, style.ascii))
        if style.view == "trend":
            days = list(self.trend or [None] * 7)[-7:]
            days = [None] * (7 - len(days)) + days
            days[-1] = self.used  # today is the live reading
            out = ""
            for used in days:
                glyph = level(self.shown(used), style.ascii)
                out += dim(glyph) if used is None else style.paint(used_code(used), glyph)
            return out
        if style.view == "cap":
            cells = 8 if cells == BAR_WIDTH else cells
            filled, empty = used_bar(value, cells, style.ascii)
            cap = self.cap if self.cap is not None else RESET_FROM
            at = int(round(self.shown(cap) * cells / 100))
            if at <= len(filled):
                text = style.paint(code, filled[:at]) + dim("│" if not style.ascii else "|") + style.paint(code, filled[at:]) + dim(empty)
            else:
                gap = at - len(filled)
                text = style.paint(code, filled) + dim(empty[:gap] + ("│" if not style.ascii else "|") + empty[gap:])
            return text
        if style.view == "none":
            return ""
        filled, empty = used_bar(value, cells, style.ascii)
        return style.paint(code, filled) + dim(empty)

    def text(self, style, now, resets=True, cells=BAR_WIDTH):
        self.left = style.left
        if self.used is None:
            age = f" {age_label(self.age)} ago" if self.age else ""
            return f"{self.name} " + style.paint("2", "—" + age)
        code = used_code(self.used)
        if self.fresh_change and style.animate:
            code = "1;" + code
        parts = [self.meter(style, now, code, cells)]
        if style.numbers:
            parts.append(style.paint(code, f"{'~' if self.estimate else ''}{int(round(self.shown(self.used)))}%"))
        elif self.estimate:
            parts[0] = style.paint("2", "~") + parts[0]
        if style.view == "cap":
            cap = self.cap if self.cap is not None else RESET_FROM
            if self.used >= cap:
                parts.append(style.paint("31", "over cap"))
            elif self.pace_ahead(now):
                parts.append(style.paint("33", "▲"))
        out = f"{self.name} " + " ".join(p for p in parts if p)
        threshold = self.cap if self.cap is not None else RESET_FROM
        if resets and self.reset and (style.resets == "always" or self.used >= threshold):
            out += " " + style.paint("2", "→" + reset_label(self.reset, now))
        return out


# ---- line 2: what's used ---------------------------------------------------------------


def window_cell(name, used, reset, now):
    used = num(used)
    reset = int(num(reset) or 0) or None
    if used is None or (reset and reset <= now):
        return None
    return Cell(name, min(100.0, max(0.0, used)), reset)


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
    return Cell("cursor+grok", min(100.0, max(0.0, used)), reset, estimate=estimate, window="week")


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


def usage_file():
    return env("LIMITLINE_PHAROS_USAGE") or os.path.join(pharos_home(), "usage.json")


def read_usage(now):
    data = read_json(usage_file())
    if not isinstance(data, dict) or not isinstance(data.get("plans"), list):
        return None
    data["stale"] = now - int(num(data.get("generated_at")) or 0) > 15 * 60
    return data


def plan_of(usage, provider):
    for plan in (usage or {}).get("plans") or []:
        if isinstance(plan, dict) and plan.get("provider") == provider:
            return plan
    return None


def agy_cells(now, usage=None):
    plan = plan_of(usage, "antigravity")
    if not plan or plan.get("stale") or (usage or {}).get("stale"):
        observed = int(num((plan or {}).get("observed_at")) or 0)
        return [Cell("gemini", None, age=now - observed if observed else None)]
    data = {"buckets": [w for w in plan.get("windows") or [] if isinstance(w, dict)]}
    cells = []
    for group, name in AGY_NAMES:
        best = None
        for bucket in data["buckets"]:
            if not isinstance(bucket, dict) or bucket.get("group") != group:
                continue
            cell = window_cell(name, bucket.get("used_pct"), bucket.get("resets_at"), now)
            if cell:
                cell.window = str(bucket.get("id") or bucket.get("name") or name)
            if cell and (best is None or cell.used > best.used):
                best = cell
        if best:
            cells.append(best)
    return cells or [Cell("gemini", None)]


def used_parts(now):
    """[(mark key, label, [cells])] in the fixed order. Without Pharos, Claude only."""
    parts = [("claude", "claude", claude_cells(now))]
    usage = read_usage(now)
    if usage is None:
        return parts
    parts.append(("codex", "codex", codex_cells(now)))
    cursor = cursor_cell(now)
    if cursor:
        parts.append(("cursor", "", [cursor]))
    parts.append(("agy", "agy", agy_cells(now, usage)))
    add_caps_and_trends(parts, usage)
    return parts


PLAN_KEYS = {"claude": "claude", "codex": "codex", "cursor": "cursor+grok", "agy": "antigravity"}


def report_file():
    return env("LIMITLINE_PHAROS_REPORT") or os.path.join(pharos_home(), "usage-report.json")


def add_caps_and_trends(parts, usage):
    """The cap (usage.json cap_pct) and the 7-day series (usage-report.json daily), both from
    Pharos. A cursor+grok estimate has no plan reading of its own, so it gets no series."""
    caps = {}
    for plan in (usage or {}).get("plans") or []:
        if isinstance(plan, dict) and num(plan.get("cap_pct")) is not None:
            caps[plan.get("key")] = num(plan.get("cap_pct"))
    report = read_json(report_file())
    daily = report.get("daily") if isinstance(report, dict) and isinstance(report.get("daily"), dict) else {}
    for key, _label, cells in parts:
        plan = PLAN_KEYS.get(key)
        series = daily.get(plan) if isinstance(daily.get(plan), dict) else {}
        for cell in cells:
            cell.cap = caps.get(plan)
            values = series.get(cell.window)
            if isinstance(values, list) and not cell.estimate:
                cell.trend = [num(v) for v in values]


CHANGE_SHOW_S = 20  # a number that just moved is bold for this long, then plain again
STALE_NOTE_S = 300  # older than this, the used line says how old Pharos's reading is


def mark_changes(parts, now):
    """Compare with the last render (~/.cache/limitline/five-last.json) and flag what moved.
    One small file, rewritten only when a number changed."""
    path = os.path.join(cache_dir(), "five-last.json")
    seen = read_json(path)
    seen = seen if isinstance(seen, dict) else {}
    dirty = False
    for key, _label, cells in parts:
        for cell in cells:
            if cell.used is None:
                continue
            slot = f"{key}/{cell.name}/used"
            value = int(round(cell.used))
            before = seen.get(slot)
            if not isinstance(before, list) or len(before) != 2:
                seen[slot] = [value, 0]
                dirty = True
            elif before[0] != value:
                seen[slot] = [value, now]
                dirty = True
            cell.fresh_change = bool(seen[slot][1]) and now - seen[slot][1] < CHANGE_SHOW_S
    if dirty:
        try:
            os.makedirs(cache_dir(), exist_ok=True)
            tmp = path + ".%d" % os.getpid()
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(seen, handle)
            os.replace(tmp, path)
        except OSError:
            pass


def render_used(style, now, resets=True, drop_agy_3p=False, cells=BAR_WIDTH):
    out, bar = [], cells
    parts = used_parts(now)
    mark_changes(parts, now)
    for key, label, cells in parts:
        shown = [c for c in cells if c.name != "claude+gpt"] if drop_agy_3p else cells
        body = " · ".join(c.text(style, now, resets, bar) for c in shown)
        out.append(style.mark(key) + (label + " " if label else "") + body)
    line = style.paint("2", "left " if style.left else "used ") + " " + SEP.join(out)
    usage = read_usage(now)
    if usage is not None:
        age = now - int(num(usage.get("generated_at")) or now)
        if age > STALE_NOTE_S:
            line += style.paint("2", f" · {age_label(age)} old")
    return line


# ---- lines 3 and 4: jobs ---------------------------------------------------------------


def job_summary(now):
    """Pharos's own counts (`pharos runs --summary`), when they are from today."""
    data = read_json(os.path.join(pharos_home(), "summary.json"))
    if not isinstance(data, dict) or not isinstance(data.get("today"), dict):
        return None
    generated = num(data.get("generated_at")) or 0
    if datetime.fromtimestamp(generated).date() != datetime.fromtimestamp(now).date():
        return None
    return data


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


SPINNER = "◐◓◑◒"
EVENT_SHOW_S = 30  # a new event stays on the today line this long


def spinner(style, now, running):
    """The ▶ mark turns slowly while jobs run (one step per redraw), and stands still otherwise."""
    if not running or not style.animate or not style.marks:
        return None
    return SPINNER[int(now // 2) % len(SPINNER)]


def latest_event(now, show_s=EVENT_SHOW_S):
    """The newest event worth a glance, from the tail of today's Pharos event file."""
    path = os.path.join(pharos_home(), "events", datetime.fromtimestamp(now).strftime("%Y-%m-%d") + ".jsonl")
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - 16384))
            tail = handle.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    for line in reversed(tail):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict) or now - (num(event.get("ts")) or 0) > show_s:
            return None
        text = event_text(event)
        if text:
            return text
    return None


RUN_WORDS = {"done": ("✓", "verified"), "merged": ("✓", "merged"), "no-changes": ("✓", "no changes"),
             "awaiting-verify": ("✋", "needs review"), "verify-failed": ("✋", "check failed"),
             "failed": ("✗", "failed"), "paused-quota": ("⏸", "waiting on limit"), "running": ("▶", "started")}


def event_text(event):
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    kind = event.get("kind")
    if kind == "run.status":
        mark, word = RUN_WORDS.get(str(data.get("status")), ("", ""))
        if not word:
            return None
        return f"{mark} {data.get('repo') or event.get('subject')} {word}".strip()
    if kind == "usage.threshold":
        return f"⚠ {data.get('plan')} {data.get('window')} {data.get('threshold')}% used"
    if kind == "usage.reset":
        return f"↺ {data.get('plan')} {data.get('window')} reset"
    if kind in ("host.offline", "host.online"):
        return f"{data.get('host')} {kind.split('.')[1]}"
    return None


def render_today(style, summary, now=None, with_event=True):
    now = now_epoch() if now is None else now
    cells = job_cells(style, summary["today"], False)
    turn = spinner(style, now, int(num(summary["today"].get("running")) or 0))
    if turn and cells:
        cells[0] = cells[0].replace(style.marks.get("running", "▶"), turn, 1)
    line = style.paint("2", "today") + " " + join_jobs(cells)
    note = latest_event(now) if with_event else None
    if note:
        line += style.paint("2", " · " + note)
    return line


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
    usage = read_usage(now)
    block = (usage or {}).get("hosts")
    hosts = block.get("hosts") if isinstance(block, dict) else None
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


def narrow_style(style):
    """trend and cap are the widest views; when even short bars do not fit, fall back to gauges."""
    import copy

    small = copy.copy(style)
    small.view = "gauge"
    return small


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
        render_used(style, now),
        render_used(style, now, resets=False),
        render_used(style, now, resets=False, drop_agy_3p=True),
        render_used(style, now, resets=False, drop_agy_3p=True, cells=3),
    ] + ([render_used(narrow_style(style), now, resets=False, drop_agy_3p=True)] if style.view in ("trend", "cap") else []), columns)]
    summary = job_summary(now)
    if summary:
        lines.append(fit([render_today(style, summary, now), render_today(style, summary, now, with_event=False)], columns))
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
