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
import math
import os
import re
import stat
import sys
import time
import unicodedata
from datetime import datetime

MARKS = {
    "unicode": {"claude": "✻", "codex": "◎", "cursor": "⬡", "agy": "✦",
                "working": "⚙", "blocked": "⛔", "running": "▶", "done": "✓", "need_you": "✋", "failed": "✗", "retried": "↻", "waiting_limit": "⏸"},
    "none": {},
}
LABELS = {"working": "working", "blocked": "blocked", "running": "running", "done": "done", "need_you": "need you", "failed": "failed",
          "retried": "retried", "waiting_limit": "waiting on limit"}
KEYS = ("running", "working", "done", "blocked", "need_you", "failed", "retried", "waiting_limit")
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
    """A finite number, or None. A bool is not a number here (True is not 1%)."""
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def pct(value):
    """A used percent, or None. Negative is not a reading; above 100 is drawn as full."""
    out = num(value)
    return None if out is None or out < 0 else min(100.0, out)


# ---- reading Pharos's files ------------------------------------------------------------
# Every file is read at most once per build() (the fit tries several variants of a line),
# only if it is a regular file under MAX_BYTES, and opened non-blocking, so a FIFO or a
# device in its place cannot hang the status line.

FORMAT = 1          # the newest usage.json / summary.json version this display understands
STALE_S = 15 * 60   # Pharos refreshes every 2 minutes; a reading older than this is not current
SKEW_S = 120        # a reading up to this far in the future is clock jitter, not a future reading
MAX_BYTES = 4 << 20
GROK_TTL = 180      # bin/limitline's default grok_ttl for the same grok.line (LL_GROK_TTL)
MISSING, BAD = "missing", "bad"
_memo = None        # a dict while build() runs


def read_raw(path, tail=None):
    """(state, bytes, mtime): state is "ok", MISSING, or BAD."""
    key = ("raw", path, tail)
    if _memo is not None and key in _memo:
        return _memo[key]
    out = _read_raw(path, tail)
    if _memo is not None:
        _memo[key] = out
    return out


def _read_raw(path, tail):
    try:
        info = os.stat(path)
    except (OSError, TypeError, ValueError):
        return MISSING, b"", None
    if not stat.S_ISREG(info.st_mode) or (tail is None and info.st_size > MAX_BYTES):
        return BAD, b"", info.st_mtime
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
        with open(fd, "rb") as handle:
            if tail:
                handle.seek(max(0, info.st_size - tail))
            return "ok", handle.read(MAX_BYTES), info.st_mtime
    except OSError:
        return BAD, b"", info.st_mtime


def read_json_state(path):
    key = ("json", path)
    if _memo is not None and key in _memo:
        return _memo[key]
    state, raw, _mtime = read_raw(path)
    data = None
    if state == "ok":
        try:
            data = json.loads(raw.decode("utf-8"))
        except ValueError:
            state = BAD
    out = (state, data)
    if _memo is not None:
        _memo[key] = out
    return out


def read_json(path):
    return read_json_state(path)[1]


def freshness(observed, now):
    """(kind, age) for a reading taken at `observed`: kind is "fresh", "old", "future"
    (beyond SKEW_S ahead of this clock), or None when there is no usable time. age is
    whole seconds and never negative; it is None unless kind is fresh or old."""
    when = num(observed)
    if when is None or when <= 0:
        return None, None
    age = now - when
    if age < -SKEW_S:
        return "future", None
    age = int(max(0, age))
    return ("old" if age > STALE_S else "fresh"), age


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
        # When to print a window's refill time: "near-cap" (default: at the plan's cap) or "always"
        self.resets = "always" if env("LL_PLAN_RESETS", "near-cap").strip().lower() == "always" else "near-cap"
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
    if seconds < 0:  # never a negative age; callers drop future readings before this
        return "0m"
    if seconds < 3600:
        return f"{max(1, seconds // 60)}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


class Cell:
    """One plan window. `used` None means no reading. Pharos's numbers are always used; with
    `plan_show = "left"` the display shows 100 - used, but colours and the cap still follow used."""

    def __init__(self, name, used, reset=None, age=None, estimate=False, window=None, passed=False):
        self.name, self.used, self.reset, self.age, self.estimate = name, used, reset, age, estimate
        self.passed = passed          # the window's reset time has gone by and nothing newer came
        self.window = window or name  # the window id in Pharos's files
        self.cap = None               # set from usage.json cap_pct
        self.trend = None             # 7 values from usage-report.json daily, used
        self.fresh_change = False     # set by mark_changes: shown bold for a short while
        self.held = False             # an old reading, drawn as `?` with its age

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
        if self.passed:
            return f"{self.name} " + style.paint("2", "reset, no newer reading" if resets else "reset")
        if self.used is None and self.held:
            age = f" · {age_label(self.age)} old" if self.age is not None and self.age > 0 else ""
            return (f"{self.name} " if self.name else "") + style.paint("2", "?" + age)
        if self.used is None:
            age = f" {age_label(self.age)} ago" if self.age is not None and self.age > 0 else ""
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
    """One window's cell, or None when there is no reading at all. A window whose reset
    time has gone by counts as refilled, 0% (as Pharos counts it); an unreadable percent is `—`."""
    when = num(reset)
    reset = int(when) if when and when > 0 else None
    if reset and reset <= now:
        return Cell(name, 0.0)
    if used is None or used == "":
        return None
    used = pct(used)
    if used is None:
        return Cell(name, None)
    return Cell(name, used, reset)


def held(usage, plan, now, is_plan=True):
    """None when `plan` (a usage.json plan, or its hosts block) can be drawn as current.
    Otherwise the age to show with `?` (HELD_NO_AGE for none). A plan is held when
    usage.json is stale, the plan says `stale: true`, its reading (observed_at, else
    usage.json's generated_at) is older than `plan_stale_after` (default 1h), or it is from
    the future. An old reading is never drawn as a current percent: tonight's Codex reading
    was 94 minutes old and wrong. The hosts block keeps only the usage.json and flag checks."""
    if usage is not None and (usage.get("stale") or usage.get("skew")):
        # The used line's note already says how old usage.json is; plans just say `?`.
        age = usage.get("age")
        return HELD_NO_AGE if age is None or is_plan else age
    if plan is None:
        return None
    if is_plan:
        import pharos_view
        stale, age = pharos_view.plan_age(plan, usage, now)
        return (HELD_NO_AGE if age is None else age) if stale else None
    kind, age = freshness(plan.get("observed_at"), now)
    if kind == "future":
        return HELD_NO_AGE
    if plan.get("stale") is True:
        return age if age is not None else HELD_NO_AGE
    return None


HELD_NO_AGE = -1  # held() result: hold the plan, show no age


def held_cell(name, hold):
    """An old reading: drawn as unknown with its age (`? · 94m old`), never its percent."""
    cell = Cell(name, None, age=None if hold == HELD_NO_AGE else hold)
    cell.held = True
    return cell


def claude_cells(now):
    cells = []
    for name, used_var, reset_var in (("5h", "LL_CLAUDE5", "LL_CLAUDE5_RESET"), ("7d", "LL_CLAUDE7", "LL_CLAUDE7_RESET")):
        cell = window_cell(name, env(used_var), env(reset_var), now)
        if cell:
            cells.append(cell)
    if not cells:
        # This session's input had no limits; the last status line's own snapshot, if current.
        data = read_json(os.path.join(cache_dir(), "claude.json"))
        if isinstance(data, dict) and isinstance(data.get("windows"), list):
            kind, age = freshness(data.get("observed_at"), now)
            if kind != "fresh":
                return [Cell("7d", None, age=age)]
            for window in data["windows"]:
                if isinstance(window, dict):
                    cell = window_cell(str(window.get("name") or "7d"), window.get("used_pct"), window.get("resets_at"), now)
                    if cell:
                        cells.append(cell)
    return cells or [Cell("7d", None)]


def codex_cells(now, usage=None):
    plan = plan_of(usage, "codex")
    hold = held(usage, plan, now)
    if hold is not None:
        return [held_cell("", hold)]
    if plan is not None:
        # Pharos's own Codex reading, so a window whose reset went by can say so.
        windows = plan.get("windows") if isinstance(plan.get("windows"), list) else []
        by_name = {str(w.get("name")): w for w in windows if isinstance(w, dict)}
        cells = []
        for name in ("5h", "7d"):
            window = by_name.get(name)
            cell = window and window_cell(name, window.get("used_pct"), window.get("resets_at"), now)
            if cell:
                cells.append(cell)
        return cells or [Cell("7d", None)]
    values = [env("LL_CODEX5"), env("LL_CODEX5_RESET"), env("LL_CODEX7"), env("LL_CODEX7_RESET")]
    if not any(values):
        state, raw, _mtime = read_raw(env("LL_CODEX_CACHE"))
        parts = raw.decode("utf-8", "replace").split() if state == "ok" else []
        if len(parts) >= 6 and parts[1] == "1":
            values = [p if p != "-" else "" for p in parts[2:6]]
    cells = [c for c in (window_cell("5h", values[0], values[1], now), window_cell("7d", values[2], values[3], now)) if c]
    return cells or [Cell("7d", None)]


def cursor_cell(now, usage=None):
    if usage is not None:
        plan = plan_of(usage, "xai-plan")
        reading = dict(plan, observed_at=plan.get("observed_at") or usage.get("generated_at")) if plan else None
        hold = held(usage, reading, now)
        if hold is not None:
            return held_cell("cursor+grok", hold)
        if plan is not None:
            windows = plan.get("windows") or []
            window = next((w for w in windows if isinstance(w, dict)), {})
            return window_cell("cursor+grok", window.get("used_pct"), window.get("resets_at"), now)
    state, raw, mtime = read_raw(os.path.join(cache_dir(), "grok.line"))
    if state != "ok":
        return None
    lines = raw.decode("utf-8", "replace").splitlines()
    first = lines[0].strip() if lines else ""
    flags = lines[1].split() if len(lines) > 1 else []
    if not first.startswith("cursor+grok"):
        return None
    hold = held(usage, None, now)
    if hold is not None:
        return held_cell("cursor+grok", hold)
    # The refresher rewrites grok.line every run; line 1 hides it after grok_ttl, and so does this.
    reading_at = usage.get("generated_at") if usage is not None else mtime
    kind, age = freshness(reading_at, now)
    ttl = num(env("LL_GROK_TTL")) or GROK_TTL
    if kind is None or kind == "future" or age > ttl:
        return Cell("cursor+grok", None, age=age)  # an old line, or one from the future: no percent
    used = pct(flags[0]) if flags else None
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


def format_version(data):
    """The file's format version (1 when absent), or None when it is not a number."""
    version = data.get("version", 1)
    value = num(version)
    if value is None or value < 1:
        return None
    return int(value) if value == int(value) else value


def too_new_note(what, version):
    return f"pharos {what}format v{version} is newer than this limitline"


def pharos_state(now):
    """(usage, note). usage is usage.json with `age`, `stale` and `skew` added, or None when
    nothing from it can be drawn; note then says why, for the end of the used line:
    no Pharos home is silence (limitline is used without Pharos), an empty home is "pharos
    not running", a broken file is "unreadable", a newer format is named."""
    key = ("usage", now)
    if _memo is not None and key in _memo:
        return _memo[key]
    out = _pharos_state(now)
    if _memo is not None:
        _memo[key] = out
    return out


def _pharos_state(now):
    import pharos_view
    state, data = read_json_state(usage_file())
    if state == MISSING:
        # Pharos is installed (or forced as the reader) and its file is gone: the service is down.
        return None, (pharos_view.UNAVAILABLE if os.path.isdir(pharos_home()) or forced_pharos() else "")
    if state != "ok" or not isinstance(data, dict) or not isinstance(data.get("plans"), list):
        return None, "pharos usage.json unreadable"
    version = format_version(data)
    if version is None:
        return None, "pharos usage.json unreadable"
    if version > FORMAT:
        return None, too_new_note("", version)
    kind, age = freshness(data.get("generated_at"), now)
    data["age"], data["skew"] = age, kind == "future"
    data["stale"] = kind is None or kind == "future" or age > pharos_view.usage_stale_after()
    return data, ""


def forced_pharos():
    try:
        import config
        return config.values().get("reader", "").strip().lower() == "pharos"
    except Exception:
        return False


def read_usage(now):
    return pharos_state(now)[0]


def plan_of(usage, provider):
    for plan in (usage or {}).get("plans") or []:
        if isinstance(plan, dict) and plan.get("provider") == provider:
            return plan
    return None


def agy_cells(now, usage=None):
    plan = plan_of(usage, "antigravity")
    if not plan:
        return [Cell("gemini", None)]
    hold = held(usage, plan, now)
    if hold is not None:
        return [held_cell("", hold)]
    buckets = [w for w in plan.get("windows") or [] if isinstance(w, dict)] if isinstance(plan.get("windows"), list) else []
    cells = []
    for group, name in AGY_NAMES:
        found = [b for b in buckets if b.get("group") == group]
        if not found:
            continue
        best = passed = None
        for bucket in found:
            cell = window_cell(name, bucket.get("used_pct"), bucket.get("resets_at"), now)
            if cell is None:
                continue
            cell.window = str(bucket.get("id") or bucket.get("name") or name)
            if cell.passed:
                passed = passed or cell
            elif cell.used is not None and (best is None or cell.used > best.used):
                best = cell
        # the fullest live bucket; else say the window reset; else the group is unreadable
        cells.append(best or passed or Cell(name, None))
    return cells or [Cell("gemini", None)]


def used_parts(now, trends=True):
    """[(mark key, label, [cells])] in the fixed order, which is also the priority order
    when the terminal is narrow (the last is dropped first). Without Pharos, Claude only."""
    parts = [("claude", "claude", claude_cells(now))]
    usage = read_usage(now)
    if usage is None:
        return parts
    parts.append(("codex", "codex", codex_cells(now, usage)))
    cursor = cursor_cell(now, usage)
    if cursor:
        parts.append(("cursor", "", [cursor]))
    parts.append(("agy", "agy", agy_cells(now, usage)))
    add_caps_and_trends(parts, usage, trends=trends)
    return parts


PLAN_KEYS = {"claude": "claude", "codex": "codex", "cursor": "cursor+grok", "agy": "antigravity"}


def report_file():
    return env("LIMITLINE_PHAROS_REPORT") or os.path.join(pharos_home(), "usage-report.json")


def add_caps_and_trends(parts, usage, trends=True):
    """The cap (usage.json cap_pct) and the 7-day series (usage-report.json daily), both from
    Pharos. A cursor+grok estimate has no plan reading of its own, so it gets no series."""
    caps = {}
    for plan in (usage or {}).get("plans") or []:
        if isinstance(plan, dict) and num(plan.get("cap_pct")) is not None:
            caps[plan.get("key")] = num(plan.get("cap_pct"))
    report = read_json(report_file()) if trends else None
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
        if _memo is not None:  # the next fit variant in this build sees what was just written
            _memo[("json", path)] = ("ok", seen)


def used_note(now):
    """What the used line says about Pharos's reading as a whole, or ""."""
    usage, note = pharos_state(now)
    if usage is None:
        return note
    if usage.get("skew"):
        return "pharos clock ahead"
    if usage.get("age") is None:
        return "pharos reading has no time"
    if usage.get("stale"):  # Pharos has stopped refreshing usage.json
        import pharos_view
        return f"{pharos_view.UNAVAILABLE} · {age_label(usage['age'])} old"
    if usage["age"] > STALE_NOTE_S:
        return f"{age_label(usage['age'])} old"
    return ""


def render_used(style, now, resets=True, drop_agy_3p=False, cells=BAR_WIDTH, keep=None):
    """`keep` limits how many plans are drawn, from the left (Claude is first and stays)."""
    out, bar = [], cells
    parts = used_parts(now, trends=style.view == "trend")
    mark_changes(parts, now)
    for key, label, cells in parts[:keep]:
        shown = [c for c in cells if c.name != "claude+gpt"] if drop_agy_3p else cells
        body = " · ".join(c.text(style, now, resets, bar) for c in shown)
        out.append(style.mark(key) + (label + " " if label else "") + body)
    line = style.paint("2", "left " if style.left else "used ") + " " + SEP.join(out)
    note = used_note(now)
    if note:
        line += style.paint("2", f" · {note}")
    return line


# ---- lines 3 and 4: jobs ---------------------------------------------------------------


def job_summary(now):
    """Pharos's own counts (`pharos runs --summary`), when they are from today."""
    data = read_json(os.path.join(pharos_home(), "summary.json"))
    if not isinstance(data, dict):
        return None
    version = format_version(data)
    if version is None:
        return None
    if version > FORMAT:
        return {"too_new": version}
    if not isinstance(data.get("today"), dict):
        return None
    kind, _age = freshness(data.get("generated_at"), now)
    if kind not in ("fresh", "old"):  # no time, or from the future: not today's
        return None
    if datetime.fromtimestamp(num(data.get("generated_at"))).date() != datetime.fromtimestamp(now).date():
        return None
    return data


# When a job line is too wide, counts drop in this order (the first goes first).
JOB_DROP = ("retried", "done", "waiting_limit", "running", "working", "failed", "blocked", "need_you")


def count_of(bucket, key):
    """A job count, or None when Pharos's value is missing or not a whole, non-negative number."""
    value = num(bucket.get(key))
    return int(value) if value is not None and value >= 0 and value == int(value) else None


def attention_reason(summary, bucket):
    if env("LL_JOBS_DETAIL", "reason") == "counts":
        return None
    recent = summary.get("recent")
    if not isinstance(recent, list):
        return None
    for row in recent:
        if not isinstance(row, dict):
            continue
        state = row.get("state")
        key = "blocked" if state == "blocked" else "need_you" if row.get("owner") == "you" else None
        reason = row.get("reason")
        if key and count_of(bucket, key) and isinstance(reason, str) and reason.strip():
            reason = " ".join(ANSI.sub("", reason).split())
            return key, reason[:79] + "…" if len(reason) > 80 else reason
    return None


def job_cells(style, bucket, only_nonzero, drop=0, detail=None):
    cells = []
    dropped = set(JOB_DROP[:drop])
    for key in KEYS:
        if key in ("working", "blocked") and key not in bucket:
            continue
        count = count_of(bucket, key)
        if only_nonzero and not count:
            continue
        if key in dropped:
            continue
        text = f"{style.mark(key)}{'—' if count is None else count} {LABELS[key]}"
        if detail and detail[0] == key:
            text += ": " + detail[1]
        if not count:
            text = style.paint("2", text)
        elif key in ("need_you", "blocked", "failed"):
            text = style.paint("31" if key == "failed" else "33", text)
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
    state, raw, _mtime = read_raw(path, tail=16384)
    if state != "ok":
        return None
    for line in reversed(raw.decode("utf-8", "replace").splitlines()):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        kind, age = freshness(event.get("ts"), now)
        if kind == "future":  # a clock ahead of ours: not new, and not shown
            continue
        if age is None or age > show_s:
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


def render_today(style, summary, now=None, with_event=True, only_nonzero=False, drop=0, with_reason=True):
    now = now_epoch() if now is None else now
    if summary.get("too_new"):
        return style.paint("2", "today") + " " + style.paint("2", "— " + too_new_note("summary ", summary["too_new"]))
    cells = job_cells(style, summary["today"], only_nonzero, drop, attention_reason(summary, summary["today"]) if with_reason else None)
    turn = spinner(style, now, count_of(summary["today"], "running") or 0)
    if turn and cells:  # a no-op when the running count was dropped for width
        cells[0] = cells[0].replace(style.marks.get("running", "▶"), turn, 1)
    line = style.paint("2", "today") + " " + join_jobs(cells)
    note = latest_event(now) if with_event else None
    if note:
        line += style.paint("2", " · " + note)
    return line


def render_older(style, summary, with_oldest=True, drop=0, with_reason=True):
    older = summary.get("older")
    if not isinstance(older, dict):
        return ""
    cells = job_cells(style, older, True, drop, attention_reason(summary, older) if with_reason else None)
    if not cells:
        return ""
    line = style.paint("2", "older") + " " + join_jobs(cells)
    oldest = summary.get("oldest_open") if with_oldest else None
    if isinstance(oldest, dict):
        hours = num(oldest.get("age_hours")) or 0
        age = f"{int(hours // 24)}d" if hours >= 24 else f"{int(hours)}h"
        line += SEP + style.paint("2", f"oldest {age} ({oldest.get('repo') or oldest.get('id')})")
    return line


# ---- line 5: hosts ---------------------------------------------------------------------


def host_count(now):
    block = (read_usage(now) or {}).get("hosts")
    hosts = block.get("hosts") if isinstance(block, dict) else None
    return len(hosts) if isinstance(hosts, list) else 0


def render_hosts(style, now, with_cpu=True, keep=None):
    """`keep` limits how many hosts are drawn, from the left (the first is this Mac)."""
    usage = read_usage(now)
    block = (usage or {}).get("hosts")
    hosts = block.get("hosts") if isinstance(block, dict) else None
    if not isinstance(hosts, list) or not hosts:
        return ""
    hold = held(usage, block, now, is_plan=False)
    if hold is not None:  # old host numbers are not shown as current
        age = "" if hold == HELD_NO_AGE else f" {age_label(hold)} ago"
        return style.paint("2", "hosts") + " " + style.paint("2", "—" + age)
    cells = []
    for i, host in enumerate(hosts[:keep]):
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
    """The first variant that fits, else the last one. Variants are functions, drawn only
    as far as needed: a wide terminal draws each line once."""
    if columns <= 0:
        return variants[0]()
    line = ""
    for variant in variants:
        line = variant()
        if width(line) <= columns:
            return line
    return line


def used_variants(style, now):
    """The used line, widest first, in the documented order: drop refill times, then the agy
    claude+gpt bucket, then 3-cell bars (trend and cap become gauges), then whole plans from
    the right: agy, cursor+grok, codex. Claude is never dropped."""
    small = narrow_style(style) if style.view in ("trend", "cap") else style
    out = [
        lambda: render_used(style, now),
        lambda: render_used(style, now, resets=False),
        lambda: render_used(style, now, resets=False, drop_agy_3p=True),
        lambda: render_used(style, now, resets=False, drop_agy_3p=True, cells=3),
    ]
    if small is not style:
        out.append(lambda: render_used(small, now, resets=False, drop_agy_3p=True))
    for keep in (3, 2, 1):
        out.append(lambda keep=keep: render_used(small, now, resets=False, drop_agy_3p=True, cells=3, keep=keep))
    return out


def safe(draw):
    """One line's text, or "" if drawing it failed: a bad field never blanks the other lines."""
    try:
        return draw()
    except Exception:
        return ""


def build(now=None, columns=None):
    global _memo
    now = now_epoch() if now is None else now
    if columns is None:
        columns = int(num(env("LL_COLUMNS")) or 0)
    style = Style()
    _memo = {}
    try:
        return _build(style, now, columns)
    finally:
        _memo = None


def _build(style, now, columns):
    return [text for _name, text in _build_named(style, now, columns) if text]


def build_named(now=None, columns=None):
    """[(name, text)] for used, today, older, hosts; a line with nothing to say is ""."""
    global _memo
    now = now_epoch() if now is None else now
    if columns is None:
        columns = int(num(env("LL_COLUMNS")) or 0)
    style = Style()
    _memo = {}
    try:
        return _build_named(style, now, columns)
    finally:
        _memo = None


def _build_named(style, now, columns):
    drops = range(1, len(JOB_DROP))
    lines = [("used", safe(lambda: fit(used_variants(style, now), columns)))]
    summary = safe(lambda: job_summary(now))
    if summary:
        lines.append(("today", safe(lambda: fit(
            [lambda: render_today(style, summary, now),
             lambda: render_today(style, summary, now, with_reason=False), lambda: render_today(style, summary, now, with_event=False, with_reason=False),
             lambda: render_today(style, summary, now, with_event=False, only_nonzero=True, with_reason=False)]
            + [lambda d=d: render_today(style, summary, now, with_event=False, only_nonzero=True, drop=d, with_reason=False) for d in drops], columns))))
        lines.append(("older", safe(lambda: fit(
            [lambda: render_older(style, summary), lambda: render_older(style, summary, with_reason=False), lambda: render_older(style, summary, with_oldest=False, with_reason=False)]
            + [lambda d=d: render_older(style, summary, with_oldest=False, drop=d, with_reason=False) for d in drops], columns))))
    hosts = safe(lambda: host_count(now)) or 0
    lines.append(("hosts", safe(lambda: fit(
        [lambda: render_hosts(style, now), lambda: render_hosts(style, now, with_cpu=False)]
        + [lambda k=k: render_hosts(style, now, with_cpu=False, keep=k) for k in range(max(0, hosts - 1), 0, -1)], columns))))
    return lines


def main():
    try:
        pick = [name for name in env("LL_PICK").split(",") if name]
        if pick:
            # A layout places these lines itself: "name<TAB>text", one per drawn line.
            out = ["%s\t%s" % (name, text) for name, text in build_named() if name in pick and text]
            sys.stdout.write("".join(line + "\n" for line in out))
            return 0
        sys.stdout.write("\n".join(build()) + "\n")
    except Exception:  # the status line must never fail
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
