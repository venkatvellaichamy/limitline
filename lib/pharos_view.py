#!/usr/bin/env python3
"""What Pharos measured, for display. limitline measures nothing but its own tool.

Pharos writes ~/.pharos/usage.json (`pharos usage`): every plan's windows, Grok
tokens, API spend, and every host. limitline reads that file and draws it. Without
Pharos, limitline shows only the tool it runs in: Claude Code's own limits from the
status-line input, or, with `LIMITLINE_TOOL=codex|grok|cursor`, that tool's local
reader.

Claude Code gives its limits only to the status-line program, so the status line
relays that reading, as-is, to ~/.pharos/inbox/claude.json for Pharos (`relay`).
"""
import json, math, os, stat, sys, time

STALE_AFTER = 15 * 60       # usage.json older than this: the Pharos service is not refreshing it
PLAN_STALE_AFTER = 60 * 60  # a plan reading older than this is drawn as unknown, with its age
SKEW_S = 120                # further in the future than this is a skewed clock, not a fresh reading
FORMAT = 1                  # the newest usage.json version this display understands
MAX_BYTES = 4 << 20
UNAVAILABLE = "Pharos usage unavailable"


def _seconds(name, env, default):
    """A positive number of seconds from the config (`name`) or the environment (`env`)."""
    try:
        import config
        value = float(config.setting(name, env, default))
    except (ImportError, TypeError, ValueError):
        return default
    return int(value) if math.isfinite(value) and value > 0 else default


def usage_stale_after():
    """`usage_stale_after` (seconds, default 900): when usage.json itself counts as old."""
    return _seconds("usage_stale_after", "LIMITLINE_USAGE_STALE_AFTER", STALE_AFTER)


def plan_stale_after():
    """`plan_stale_after` (seconds, default 3600): when one plan's reading counts as old."""
    return _seconds("plan_stale_after", "LIMITLINE_PLAN_STALE_AFTER", PLAN_STALE_AFTER)


def epoch(value, strings=False):
    """A positive, finite epoch-seconds number, else None. A bool is not a time. With
    `strings`, a numeric string ("1762056000") counts too (usage.json's generated_at)."""
    if isinstance(value, bool):
        return None
    if strings and isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return None
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        return None
    return float(value)


def plan_age(plan, usage, now):
    """(stale, age) for one usage.json plan. The reading time is the plan's observed_at;
    usage.json's generated_at stands in only when the plan has no observed_at key at all.
    An observed_at that is there but not a positive epoch number (an ISO string, 0, null,
    a bool) means the reading time is unknown: stale, age None. Never a cache file's mtime.
    Stale when usage.json is stale, the plan says `stale: true`, its reading is older than
    plan_stale_after, or it is from the future. age is whole seconds, or None."""
    usage = usage or {}
    if isinstance(plan, dict) and "observed_at" in plan:
        when = epoch(plan["observed_at"])
    else:
        when = epoch(usage.get("generated_at"), strings=True)
    age = None
    if when is not None:
        age = now - when
        if age < -SKEW_S:
            return True, None
        age = int(max(0, age))
    stale = bool(usage.get("stale")) or (isinstance(plan, dict) and plan.get("stale") is True)
    stale = stale or age is None or age > plan_stale_after()
    if usage.get("stale") and isinstance(usage.get("age"), (int, float)):
        age = max(age or 0, int(usage["age"]))
    return stale, age


def no_data(plan):
    """True for a plan that has read nothing yet: observed_at null and no windows. It is
    shown as `—` (no data), not `?` (data that is there but can't be trusted)."""
    return (isinstance(plan, dict) and "observed_at" in plan and plan["observed_at"] is None
            and plan.get("windows") in (None, []))


def refilled(windows, now):
    """Windows with a reset time that has gone by count as refilled: 0% used, no reset."""
    out = []
    for window in windows if isinstance(windows, list) else []:
        if not isinstance(window, dict):
            continue
        reset = window.get("resets_at")
        if isinstance(reset, (int, float)) and not isinstance(reset, bool) and 0 < reset <= now:
            window = dict(window, used_pct=0)
            window.pop("resets_at", None)
        out.append(window)
    return out


def pharos_home():
    return os.environ.get("LIMITLINE_PHAROS_HOME") or os.path.join(os.path.expanduser("~"), ".pharos")


def usage_path():
    return os.environ.get("LIMITLINE_PHAROS_USAGE") or os.path.join(pharos_home(), "usage.json")


def now_epoch():
    try:
        return int(os.environ.get("LIMITLINE_NOW") or time.time())
    except ValueError:
        return int(time.time())


def load_json(path):
    """A regular file's JSON, or None. Opened non-blocking, so a FIFO in its place cannot hang."""
    try:
        info = os.stat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            return None
        with open(os.open(path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def read_usage(now=None):
    """usage.json with `age`, or None when Pharos is not installed, the file is unreadable,
    or its format is newer than this display understands (nothing from it is drawn).
    A reading from the future (beyond SKEW_S) has no age and is stale, never fresh."""
    now = now_epoch() if now is None else now
    data = load_json(usage_path())
    if not isinstance(data, dict) or not isinstance(data.get("plans"), list):
        return None
    version = data.get("version", 1)
    if isinstance(version, bool) or not isinstance(version, (int, float)) or not 1 <= version <= FORMAT:
        return None
    try:
        generated = int(data.get("generated_at") or 0)
    except (TypeError, ValueError):
        generated = 0
    age = now - generated if generated > 0 else None
    data["skew"] = age is not None and age < -SKEW_S
    data["age"] = None if age is None or data["skew"] else max(0, age)
    data["stale"] = data["age"] is None or data["age"] > usage_stale_after()
    return data


def _own_claude():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    path = os.environ.get("LIMITLINE_CLAUDE_SNAPSHOT") or os.path.join(base, "limitline", "claude.json")
    data = load_json(path)
    return data if isinstance(data, dict) else None


def plan_rows(usage, now=None):
    """Provider-shaped rows (as the readers print them) from usage.json. The status
    line's own Claude reading wins when it is newer than Pharos's copy. Every row gets
    `stale` and `age` from plan_age(), and a window whose reset went by reads 0%."""
    now = now_epoch() if now is None else now
    rows = []
    for plan in usage.get("plans") or []:
        if not isinstance(plan, dict):
            continue
        row = dict(plan)
        row["stale"], age = plan_age(plan, usage, now)
        if age is not None:
            row["age"] = age
        if "windows" in plan:  # a non-list or non-dict entries are dropped, so readers never raise on them
            row["windows"] = refilled(plan["windows"], now)
        rows.append(row)
    mine = _own_claude()
    mine_at = epoch(mine.get("observed_at")) if mine else None
    if mine and mine.get("windows") and mine_at is not None:  # a snapshot with no time is not current
        for i, row in enumerate(rows):
            if row.get("provider") == "claude" and mine_at >= (epoch(row.get("observed_at")) or 0):
                rows[i] = dict(mine, provider="claude", stale=False)
    for extra in ("grok", "spend"):
        item = usage.get(extra)
        if isinstance(item, dict) and item.get("source") not in (None, "none"):
            rows.append(dict(item))
    return rows


def hosts(usage):
    block = usage.get("hosts") if isinstance(usage, dict) else None
    items = block.get("hosts") if isinstance(block, dict) else None
    return [h for h in items or [] if isinstance(h, dict)]


def codex_fields(usage, now=None):
    """`codex5 12` / `codex5_reset 1762…` lines for the status line, from Pharos's codex reading.
    A stale reading gives no percent, only `codex_age <seconds>` (`codex_age ?` without a
    time), so the line says `codex ? · 94m old` instead of an old number. A window whose
    reset went by reads 0."""
    now = now_epoch() if now is None else now
    by_name = {}
    for plan in usage.get("plans") or []:
        if isinstance(plan, dict) and plan.get("provider") == "codex":
            if no_data(plan) and not usage.get("stale"):
                continue  # nothing read yet: no fields, so the line shows `—`
            stale, age = plan_age(plan, usage, now)
            if stale:
                return "codex_age %s" % ("?" if age is None else age)
            for window in refilled(plan.get("windows"), now):
                by_name[window.get("name")] = window
    lines = []
    for key, name in (("codex5", "5h"), ("codex7", "7d")):
        item = by_name.get(name) or {}
        used, reset = item.get("used_pct"), item.get("resets_at")
        lines.append(key if used is None else "%s %s" % (key, used))
        lines.append(key + "_reset" if reset is None else "%s_reset %s" % (key, reset))
    return "\n".join(lines)


def relay(snapshot_path):
    """Copy the status line's Claude snapshot into Pharos's inbox, atomically, when Pharos is installed."""
    import reader
    if reader.is_pharos():
        return False
    home = pharos_home()
    if not os.path.isdir(home):
        return False
    try:
        with open(snapshot_path, encoding="utf-8") as handle:
            text = handle.read()
        json.loads(text)
    except (OSError, ValueError):
        return False
    inbox = os.path.join(home, "inbox")
    try:
        os.makedirs(inbox, exist_ok=True)
        tmp = os.path.join(inbox, ".claude-%d.tmp" % os.getpid())
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, os.path.join(inbox, "claude.json"))
    except OSError:
        return False
    return True


def main(argv):
    if argv[:1] == ["--codex-fields"]:
        usage = read_usage()
        if usage is None:
            import reader
            if reader.is_pharos():  # Pharos is the reader and its file is gone: say so
                sys.stdout.write("pharos_note %s\n" % UNAVAILABLE)
                return 0
            return 1
        sys.stdout.write(codex_fields(usage) + "\n")
        return 0
    if argv[:1] == ["--relay"] and len(argv) > 1:
        return 0 if relay(argv[1]) else 1
    usage = read_usage()
    json.dump(usage or {}, sys.stdout, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception:
        sys.exit(0)
