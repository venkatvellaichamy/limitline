#!/usr/bin/env python3
"""Antigravity (agy CLI and IDE) usage, live from `agy -p "/usage" --output-format json`.

Google AI Pro has two separate allowances. This is the Antigravity one. The
Gemini app (gemini.google.com and the Mac app) has its own, which no CLI or
local file exposes; see providers/gemini.

`agy -p "/usage"` is a local command. It runs no agent turn and spends no
tokens or quota. Its JSON has `command.data.groups[].buckets[]`, each bucket
with an `id`, a `window` (5h or weekly), a `remaining_fraction`, and a
`reset_time`. limitline keeps only those fields, as
used_pct = round((1 - remaining_fraction) * 100), in
~/.cache/limitline/antigravity.json. It never reads agy's login, cookies, or
any token store.

The fetch runs only from `limitline refresh` (and the background agents that
run it), never from the status line: at most one at a time (a flock), at most
every `agy_ttl` minutes (default 15), with a timeout.

A "quota reached" line in ~/.gemini/antigravity-cli/cli.log is an event, not a
measurement. Without a live reading the row is `unknown`, and the event is shown
as `last limit hit 2h ago (cli.log)`. It is stale after 5 hours, or as soon as
a later live reading or a later finished agy run in Pharos shows up.
"""
import errno, fcntl, json, os, re, shutil, subprocess, sys, time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import setting

PROVIDER = "antigravity"
DEFAULT_TTL_MIN = 15
DEFAULT_TIMEOUT = 30
# A live reading this old is marked stale; one older than a week is ignored.
LIVE_STALE = 3600
LIVE_MAX = 7 * 86400
# A limit-hit event says nothing after this long.
EVENT_STALE = 5 * 3600
# Pharos run states that mean an agy request finished without hitting the limit.
RUN_OK = ("ok", "done", "success", "succeeded", "completed", "complete", "finished", "verified", "awaiting-verify")
SAFE_ID = re.compile(r"[^A-Za-z0-9._-]")


def now_epoch():
    try:
        return int(os.environ.get("LIMITLINE_NOW") or time.time())
    except ValueError:
        return int(time.time())


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "limitline")


def usage_path():
    return os.environ.get("LIMITLINE_AGY_USAGE") or os.path.join(cache_dir(), "antigravity.json")


def state_path():
    return os.path.join(cache_dir(), "agy-fetch.json")


def lock_path():
    return os.path.join(cache_dir(), "agy-fetch.lock")


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


def window_kind(raw):
    text = clean(raw).lower()
    if text in ("weekly", "week", "7d", "1w"):
        return "weekly"
    if text in ("5h", "five_hour", "five-hour", "5-hour"):
        return "5h"
    return SAFE_ID.sub("", text) or "limit"


def parse_usage(text):
    """Buckets from the CLI's JSON, or None. Only id, group name, window,
    used percent, and reset are kept; nothing else of the output is stored."""
    if not text:
        return None
    start = text.find("{")
    if start < 0:
        return None
    try:
        data = json.loads(text[start:])
    except ValueError:
        try:
            data, _ = json.JSONDecoder().raw_decode(text[start:])
        except ValueError:
            return None
    groups = data.get("command") if isinstance(data, dict) else None
    groups = groups.get("data") if isinstance(groups, dict) else None
    groups = groups.get("groups") if isinstance(groups, dict) else None
    if not isinstance(groups, list):
        return None
    buckets = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        name = clean(group.get("name") or group.get("title") or group.get("label") or group.get("display_name"))
        for bucket in group.get("buckets") or []:
            if not isinstance(bucket, dict):
                continue
            left = number(bucket.get("remaining_fraction"))
            if left is None or left < 0 or left > 1:
                continue
            kind = window_kind(bucket.get("window"))
            ident = SAFE_ID.sub("", clean(bucket.get("id"), 60))
            if not ident:
                ident = (SAFE_ID.sub("", name.lower().replace(" ", "-")) or "bucket") + "-" + kind
            item = {"id": ident, "group": name, "window": kind, "used_pct": int((1 - left) * 100 + 0.5)}
            reset = to_epoch(bucket.get("reset_time"))
            if reset is not None:
                item["resets_at"] = reset
            buckets.append(item)
    return buckets or None


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(data, handle, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def read_json(path):
    try:
        with open(path) as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def read_live(now=None):
    """(observed_at, buckets) from the cache, or None when missing or over a week old."""
    now = now_epoch() if now is None else now
    data = read_json(usage_path())
    if not data:
        return None
    observed = to_epoch(data.get("observed_at"))
    buckets = data.get("buckets")
    if observed is None or not isinstance(buckets, list) or now - observed > LIVE_MAX:
        return None
    return observed, [item for item in buckets if isinstance(item, dict)]


# ---- the limit-hit event fallback (cli.log, Pharos runs) ----

STAMP = re.compile(r"^[IWEF](\d{2})(\d{2})\s+(\d{2}):(\d{2}):(\d{2})")


def stamp_epoch(line, now):
    match = STAMP.match(line)
    if not match:
        return None
    month, day, hour, minute, second = (int(part) for part in match.groups())
    # glog stamps are local wall-clock time with no zone.
    year = datetime.fromtimestamp(now).year
    try:
        candidate = datetime(year, month, day, hour, minute, second).timestamp()
    except ValueError:
        return None
    if candidate - now > 2 * 86400:
        try:
            candidate = datetime(year - 1, month, day, hour, minute, second).timestamp()
        except ValueError:
            return None
    return int(candidate)


def is_limit_line(line):
    return "quota reached" in line.lower() and "Resets in" in line


def tail_text(path, limit):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            if size > limit:
                handle.seek(size - limit)
                handle.readline()
            return handle.read().decode("utf-8", "replace")
    except OSError:
        return ""


def log_path():
    return os.environ.get("LIMITLINE_GEMINI_LOG") or os.path.join(
        os.path.expanduser("~"), ".gemini", "antigravity-cli", "cli.log")


def runs_root():
    override = os.environ.get("LIMITLINE_PHAROS_RUNS")
    if override:
        return override
    home = os.environ.get("LIMITLINE_PHAROS_HOME") or os.path.join(os.path.expanduser("~"), ".pharos")
    return os.path.join(home, "runs")


def agy_runs():
    """[(state, folder)] for Pharos runs of agy or gemini."""
    root = runs_root()
    found = []
    try:
        names = os.listdir(root)
    except OSError:
        return found
    for name in names:
        folder = os.path.join(root, name)
        state = read_json(os.path.join(folder, "state.json"))
        if state and state.get("tool") in ("agy", "gemini"):
            found.append((state, folder))
    return found


def last_event(now):
    """The newest limit-hit event as {"at", "source"}, or None."""
    best = None
    text = tail_text(log_path(), 2000000)
    for line in text.splitlines():
        if is_limit_line(line):
            at = stamp_epoch(line, now)
            if at is not None and (best is None or at >= best["at"]):
                best = {"at": at, "source": "cli.log"}
    for state, folder in agy_runs():
        at = None
        if state.get("status") == "paused-quota":
            at = to_epoch(state.get("paused_at") or state.get("updated_at") or state.get("started_at"))
        else:
            for line in tail_text(os.path.join(folder, "stdout.log"), 200000).splitlines():
                if is_limit_line(line):
                    stamp = stamp_epoch(line, now)
                    if stamp is not None:
                        at = stamp
        if at is not None and (best is None or at > best["at"]):
            best = {"at": at, "source": "pharos"}
    return best


def later_success(at):
    """A finished agy run in Pharos that started after the event."""
    for state, _ in agy_runs():
        status = str(state.get("status") or "").lower()
        started = to_epoch(state.get("started_at"))
        if status in RUN_OK and started is not None and started > at:
            return True
    return False


def read(now=None):
    now = now_epoch() if now is None else now
    out = {"label": PROVIDER, "observed_at": None, "plan": PROVIDER, "provider": PROVIDER,
           "source": "none", "stale": False, "windows": []}
    live = read_live(now)
    if live is not None:
        observed, buckets = live
        windows = []
        for item in buckets:
            used = number(item.get("used_pct"))
            if used is None:
                continue
            reset = to_epoch(item.get("resets_at"))
            # A bucket whose reset passed has refilled; its old percent is not current.
            if reset is not None and reset <= now:
                continue
            ident = SAFE_ID.sub("", clean(item.get("id"), 60)) or "bucket"
            window = {"group": clean(item.get("group")), "id": ident, "name": ident,
                      "used_pct": int(used), "window": window_kind(item.get("window"))}
            if reset is not None:
                window["resets_at"] = reset
            windows.append(window)
        out.update({"age": max(0, now - observed), "observed_at": observed, "source": "live",
                    "stale": now - observed > LIVE_STALE, "windows": windows})
    event = last_event(now)
    if event is not None:
        if live is not None and live[0] >= event["at"]:
            event = None
        else:
            event["stale"] = now - event["at"] > EVENT_STALE or later_success(event["at"])
            event["kind"] = "limit hit"
            out["event"] = event
    return out


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


# ---- the fetch ----

def agy_bin():
    override = os.environ.get("LIMITLINE_AGY_BIN")
    if override:
        return override
    return shutil.which("agy") or ""


def ttl_seconds():
    raw = setting("agy_ttl", "LIMITLINE_AGY_TTL", str(DEFAULT_TTL_MIN))
    try:
        return max(0, int(float(raw) * 60))
    except (TypeError, ValueError):
        return DEFAULT_TTL_MIN * 60


def timeout_seconds():
    try:
        return max(1.0, float(os.environ.get("LIMITLINE_AGY_TIMEOUT") or DEFAULT_TIMEOUT))
    except ValueError:
        return float(DEFAULT_TIMEOUT)


def fetch_state():
    return read_json(state_path()) or {}


def fetch(force=False):
    """Run the agy usage command once, if due. Returns a short word for refresh."""
    if str(setting("agy_fetch", "LIMITLINE_AGY_FETCH", "1")).strip().lower() in ("0", "off", "false", "no"):
        return "off"
    binary = agy_bin()
    if not binary or not os.path.isfile(binary) or not os.access(binary, os.X_OK):
        return "no agy"
    now = now_epoch()
    state = fetch_state()
    last = to_epoch(state.get("last_attempt"))
    if not force and last is not None and now - last < ttl_seconds():
        return "fresh"
    os.makedirs(cache_dir(), exist_ok=True)
    handle = open(lock_path(), "a")
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
                return "busy"
            raise
        state = {"last_attempt": now}
        work = os.path.join(cache_dir(), "agy-cwd")
        os.makedirs(work, exist_ok=True)
        try:
            proc = subprocess.run([binary, "-p", "/usage", "--output-format", "json"], cwd=work,
                                  stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout_seconds())
            buckets = parse_usage(proc.stdout.decode("utf-8", "replace"))
        except subprocess.TimeoutExpired:
            buckets = None
            state["error"] = "timeout"
        except OSError as exc:
            buckets = None
            state["error"] = exc.__class__.__name__
        if buckets is None:
            state.setdefault("error", "no usage in output")
            write_json(state_path(), state)
            return "failed: " + state["error"]
        write_json(usage_path(), {"buckets": buckets, "observed_at": now_epoch()})
        state["ok"] = now_epoch()
        write_json(state_path(), state)
        return "fetched"
    finally:
        handle.close()


def main(argv):
    if argv and argv[0] == "fetch":
        print(fetch(force="--force" in argv))
        return
    json.dump(read(), sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception:
        sys.exit(0)
