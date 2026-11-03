#!/usr/bin/env python3
"""Count agent runs from Pharos state files, or from a process list."""
import json, os, re, sys, time
from datetime import datetime, timezone

RUN_STATES = {"starting", "running", "stalled"}
# Counted no matter how old: the run is still live, or waiting to resume.
ACTIVE_STATES = {"starting", "running", "paused-quota"}
FINISH_KEYS = ("finished_at", "ended_at", "completed_at")
FALLBACK_KEYS = ("last_activity", "updated_at", "started_at")
DEFAULT_WINDOW = 12 * 3600
VERIFY_STATES = {"awaiting-verify"}
FAIL_STATES = {"failed", "verify-failed"}
WARN_STATES = {"stalled", "paused-quota"}
PS_LINE = re.compile(r"^(\d+)\s+(\d+)\s+(\S+)\s+(.*)$")


def now_epoch():
    raw = os.environ.get("LIMITLINE_NOW")
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    return int(time.time())


def pharos_runs_root():
    override = os.environ.get("LIMITLINE_PHAROS_RUNS")
    if override:
        return override
    home = os.environ.get("LIMITLINE_PHAROS_HOME")
    if not home:
        home = os.path.join(os.path.expanduser("~"), ".pharos")
    return os.path.join(home, "runs")


def epoch_of(value):
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    iso = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        stamp = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        # Pharos writes naive local time (2026-01-02T08:41:27). Read it as local,
        # not UTC, or every age is off by the UTC offset.
        return int(time.mktime(stamp.timetuple()))
    return int(stamp.timestamp())


def repo_name(value):
    text = str(value or "").strip().rstrip("/")
    if not text:
        return "-"
    name = text.split("/")[-1]
    if name in ("", ".", ".."):
        return "-"
    return name


def classify_command(command):
    parts = (command or "").split()
    if not parts:
        return ""
    name = parts[0].rsplit("/", 1)[-1]
    if name == "cursor-agent":
        return "cursor"
    if name == "codex" and "exec" in parts[1:]:
        return "codex"
    if name == "claude" and "-p" in parts[1:]:
        return "claude"
    if name == "grok" or name.startswith("grok-"):
        return "grok"
    if name == "agy":
        return "agy"
    return ""


def load_states(root):
    states = []
    if not root or not os.path.isdir(root):
        return states
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return states
    for name in names:
        path = os.path.join(root, name, "state.json")
        if not os.path.isfile(path):
            continue
        try:
            data = json.load(open(path))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            data["_dir"] = os.path.join(root, name)
            states.append(data)
    return states


def from_ps(text):
    runs = []
    for line in (text or "").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("PID"):
            continue
        match = PS_LINE.match(raw)
        command = match.group(4) if match else raw
        tool = classify_command(command)
        if not tool:
            continue
        runs.append({
            "id": match.group(1) if match else "ps",
            "status": "running",
            "tool": tool,
            "repo": "",
            "started_at": None,
        })
    return runs


def read_ps():
    override = os.environ.get("LIMITLINE_PS_FILE")
    if override is not None:
        if override in ("", "/dev/null") or not os.path.isfile(override):
            return ""
        try:
            return open(override).read()
        except OSError:
            return ""
    import subprocess
    try:
        proc = subprocess.run(
            ["ps", "-ax", "-o", "pid=,ppid=,etime=,command="],
            capture_output=True, text=True, timeout=1.5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout or ""


def collect():
    root = pharos_runs_root()
    states = load_states(root)
    if states:
        return states
    return from_ps(read_ps())


def parse_window(raw):
    """`12h`, `90m`, `2d`, `3600s`, or a bare number of hours. `0` or `off` keeps every run."""
    text = str(raw if raw is not None else "").strip().lower()
    if text in ("", "default"):
        return DEFAULT_WINDOW
    if text in ("0", "off", "none", "all"):
        return 0
    unit = 3600
    if text[-1:] in ("s", "m", "h", "d"):
        unit = {"s": 1, "m": 60, "h": 3600, "d": 86400}[text[-1]]
        text = text[:-1]
    try:
        value = float(text)
    except ValueError:
        return DEFAULT_WINDOW
    if value <= 0:
        return 0
    return int(value * unit)


def window_seconds():
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from config import setting
        raw = setting("fleet_window", "LIMITLINE_FLEET_WINDOW", "")
    except Exception:
        raw = os.environ.get("LIMITLINE_FLEET_WINDOW", "")
    return parse_window(raw)


def window_label(seconds):
    if seconds % 86400 == 0:
        return "%dd" % (seconds // 86400)
    if seconds % 3600 == 0:
        return "%dh" % (seconds // 3600)
    if seconds % 60 == 0:
        return "%dm" % (seconds // 60)
    return "%ds" % seconds


def activity_epoch(state):
    """When the run last did something.

    1. An explicit finish time, when Pharos records one.
    2. The modification time of the run's stdout.log, which only the agent writes.
    3. last_activity, updated_at, or started_at.

    last_activity is only a fallback: Pharos sweeps bump it on runs that finished
    hours earlier. state.json and events.jsonl mtimes are never used, because
    every sweep rewrites them."""
    best = None
    for key in FINISH_KEYS:
        stamp = epoch_of(state.get(key))
        if stamp is not None and (best is None or stamp > best):
            best = stamp
    if best is not None:
        return best
    folder = state.get("_dir")
    if folder:
        try:
            log_mtime = int(os.path.getmtime(os.path.join(folder, "stdout.log")))
        except OSError:
            log_mtime = None
        if log_mtime is not None:
            started = epoch_of(state.get("started_at"))
            return max(log_mtime, started) if started is not None else log_mtime
    for key in FALLBACK_KEYS:
        stamp = epoch_of(state.get(key))
        if stamp is not None and (best is None or stamp > best):
            best = stamp
    return best


def is_recent(state, now, window):
    status = str(state.get("status") or "")
    if status in ACTIVE_STATES:
        return True
    if not window:
        return True
    stamp = activity_epoch(state)
    if stamp is None:
        return True
    return now - stamp <= window


def split_recent(states, now=None, window=None):
    if now is None:
        now = now_epoch()
    if window is None:
        window = window_seconds()
    recent, older = [], []
    for state in states:
        (recent if is_recent(state, now, window) else older).append(state)
    return recent, older


def summarize(states):
    counts = {"run": 0, "verify": 0, "failed": 0, "warn": 0, "stopped": 0}
    for state in states:
        status = str(state.get("status") or "")
        if status == "stopped":
            counts["stopped"] += 1
        if status in RUN_STATES:
            counts["run"] += 1
        elif status in VERIFY_STATES:
            counts["verify"] += 1
        elif status in FAIL_STATES:
            counts["failed"] += 1
        if status in WARN_STATES:
            counts["warn"] += 1
    return counts


def format_segment(counts):
    parts = []
    if counts.get("run"):
        parts.append("%d run" % counts["run"])
    if counts.get("verify"):
        parts.append("%d verify" % counts["verify"])
    if counts.get("failed"):
        parts.append("%d ✗" % counts["failed"])
    if not parts and not counts.get("warn"):
        return ""
    if not parts:
        return "⚙ ⚠"
    text = "⚙ " + " · ".join(parts)
    if counts.get("warn"):
        text += " ⚠"
    return text


def segment_text(states=None, now=None, window=None):
    if states is None:
        states = collect()
    recent, _ = split_recent(states, now=now, window=window)
    return format_segment(summarize(recent))


def older_summary(states):
    counts = summarize(states)
    parts = []
    if counts.get("run"):
        parts.append("%d run" % counts["run"])
    if counts.get("verify"):
        parts.append("%d verify" % counts["verify"])
    if counts.get("failed"):
        parts.append("%d ✗" % counts["failed"])
    if counts.get("stopped"):
        parts.append("%d stopped" % counts["stopped"])
    other = len(states) - counts["run"] - counts["verify"] - counts["failed"] - counts["stopped"]
    if other > 0:
        parts.append("%d other" % other)
    return " · ".join(parts)


def age_of(state, now):
    stamp = epoch_of(state.get("started_at"))
    if stamp is None:
        stamp = activity_epoch(state)
    if stamp is None or not now:
        return "-"
    delta = int(now - stamp)
    if delta < 0:
        delta = 0
    if delta < 60:
        return "%ds" % delta
    if delta < 3600:
        return "%dm" % (delta // 60)
    if delta < 86400:
        hours, minutes = divmod(delta // 60, 60)
        return "%dh%02dm" % (hours, minutes)
    return "%dd" % (delta // 86400)


def format_run(state, now):
    ident = str(state.get("id") or "-")[:12]
    tool = str(state.get("tool") or "-")
    repo = repo_name(state.get("repo"))
    status = str(state.get("status") or "-")
    return "%s  %s  %s  %s  %s" % (ident, tool, repo, status, age_of(state, now))


def log_path(state):
    folder = state.get("_dir")
    if not folder:
        return ""
    path = os.path.join(folder, "stdout.log")
    return path if os.path.isfile(path) else ""


def run_lines(states=None, now=None, swiftbar=False):
    if states is None:
        states = collect()
    if now is None:
        now = now_epoch() or 0
    lines = []
    for state in states:
        line = format_run(state, now)
        if swiftbar:
            log = log_path(state)
            if log:
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
