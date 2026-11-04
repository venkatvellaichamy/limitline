#!/usr/bin/env python3
"""The shared xAI plan: one subscription covers Cursor, Grok, Grok Bot, and Grok Build.

Live source: the Grok CLI logs one line to ~/.grok/logs/unified.jsonl each time
its `/usage show` command fetches the plan from xAI:

    {"ts": "...Z", "msg": "billing: fetched credits config",
     "ctx": {"config": {"creditUsagePercent": 74.0,
                        "currentPeriod": {"end": "...+00:00", ...}, ...},
             "subscriptionTier": "SuperGrok Plus"}}

The newest such line is the live reading (source "live"). `limitline refresh`
has Pharos make Grok write a fresh one (`pharos usage --refresh`); this module only reads.

Manual override: ~/.cache/limitline/xai-plan.json, written by
`limitline set xai-plan`. It is always labelled source "manual" and shown
dimmed, so a typed number never passes for live data. The live reading wins
whenever it is at least as new as the manual one.

A reading older than 6 hours is shown dimmed with its age, and so is a live
reading when the last fetch after it failed. One older than 7 days is hidden.
Once resets_at has passed, the percent belongs to an old window and is not
shown. With a reading, Cursor and Grok are one row, and the Cursor token
estimate is not shown at all.
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timefmt

PROVIDER = "xai-plan"
LABEL = "cursor+grok"
STALE_AFTER = 6 * 3600
HIDE_AFTER = 7 * 86400
LOG_MARKER = "fetched credits config"
TAIL_BYTES = 512 * 1024


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "limitline")


def cache_path():
    return os.environ.get("LIMITLINE_XAI_PLAN") or os.path.join(cache_dir(), "xai-plan.json")


def log_path():
    if os.environ.get("LIMITLINE_GROK_LOG"):
        return os.environ["LIMITLINE_GROK_LOG"]
    return os.path.join(os.path.expanduser("~"), ".grok", "logs", "unified.jsonl")


def iso_epoch(text):
    if not isinstance(text, str) or not text:
        return None
    from datetime import datetime
    raw = text.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        return None
    return int(stamp.timestamp())


def parse_log_line(raw):
    """A reading dict from one Grok log line, or None if it is not a usable
    `fetched credits config` line."""
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if LOG_MARKER not in raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict) or LOG_MARKER not in str(data.get("msg") or ""):
        return None
    ctx = data.get("ctx") if isinstance(data.get("ctx"), dict) else {}
    config = ctx.get("config") if isinstance(ctx.get("config"), dict) else {}
    used = number(config.get("creditUsagePercent"))
    observed = iso_epoch(data.get("ts"))
    if used is None or observed is None:
        return None
    period = config.get("currentPeriod") if isinstance(config.get("currentPeriod"), dict) else {}
    reading = {"used_pct": used, "observed_at": observed, "source": "live"}
    reset = iso_epoch(period.get("end")) or iso_epoch(config.get("billingPeriodEnd"))
    if reset is not None:
        reading["resets_at"] = reset
    plan = clean_text(ctx.get("subscriptionTier"))
    if plan:
        reading["plan"] = plan
    return reading


def read_log(path=None):
    """The newest usable reading in the Grok log. Reads backwards from the end
    in 512 KB chunks, so a large log costs one chunk when the line is recent and
    a full scan only when it is not."""
    path = path or log_path()
    try:
        handle = open(path, "rb")
    except OSError:
        return None
    with handle:
        try:
            handle.seek(0, os.SEEK_END)
            end = handle.tell()
        except OSError:
            return None
        carry = b""
        while end > 0:
            start = max(0, end - TAIL_BYTES)
            handle.seek(start)
            chunk = handle.read(end - start) + carry
            lines = chunk.split(b"\n")
            # The first piece may be the tail of a line that starts earlier.
            carry = lines.pop(0) if start > 0 else b""
            for raw in reversed(lines):
                if LOG_MARKER.encode() in raw:
                    found = parse_log_line(raw)
                    if found is not None:
                        return found
            end = start
        if carry and LOG_MARKER.encode() in carry:
            return parse_log_line(carry)
    return None


def fetch_state():
    """What the last Grok plan fetch recorded (Pharos now runs it)."""
    try:
        data = json.load(open(os.path.join(cache_dir(), "xai-fetch.json")))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def read_manual():
    try:
        data = json.load(open(cache_path()))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if number(data.get("used_pct")) is None or number(data.get("observed_at")) is None:
        return None
    # Nothing in this file is live: it was typed in or copied by hand.
    data["source"] = "manual"
    return data


def now_epoch():
    try:
        return int(os.environ.get("LIMITLINE_NOW") or time.time())
    except ValueError:
        return int(time.time())


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return value


def clean_text(value, limit=24):
    if not isinstance(value, str):
        return None
    text = " ".join("".join(ch for ch in value if ch.isprintable()).split())
    return text[:limit] or None


def empty():
    return {"label": LABEL, "observed_at": None, "provider": PROVIDER, "source": "none", "stale": False, "windows": []}


def pick(live, manual):
    """The live reading unless the manual one is strictly newer."""
    if live is None:
        return manual
    if manual is None:
        return live
    return manual if int(manual["observed_at"]) > int(live["observed_at"]) else live


def read(now=None):
    now = now_epoch() if now is None else now
    out = empty()
    data = pick(read_log(), read_manual())
    if data is None:
        return out
    used = number(data.get("used_pct"))
    observed = number(data.get("observed_at"))
    if used is None or observed is None:
        return out
    observed = int(observed)
    age = now - observed
    if age > HIDE_AFTER:
        return out
    used = max(0, min(100, used))
    reset = number(data.get("resets_at"))
    out["observed_at"] = observed
    out["age"] = max(0, age)
    out["source"] = "live" if data.get("source") == "live" else "manual"
    out["stale"] = age > STALE_AFTER
    if out["source"] == "live":
        state = fetch_state()
        attempt = number(state.get("last_attempt"))
        if state.get("error") and attempt is not None and attempt >= observed:
            out["stale"] = True
            out["fetch_error"] = clean_text(state.get("error"), 80)
    plan = clean_text(data.get("plan"))
    if plan:
        out["plan"] = plan
    if reset is not None and int(reset) <= now:
        out["reset_passed"] = int(reset)
        return out
    window = {"name": "week", "used_pct": int(used + 0.5) if float(used).is_integer() else round(used, 1)}
    if reset is not None:
        window["resets_at"] = int(reset)
    out["windows"] = [window]
    return out


def present(row):
    return isinstance(row, dict) and row.get("provider") == PROVIDER and row.get("source") not in (None, "none")


def write(used, resets_at=None, plan=None, source="manual", now=None):
    now = now_epoch() if now is None else now
    path = cache_path()
    previous = {}
    try:
        previous = json.load(open(path))
    except (OSError, ValueError):
        previous = {}
    if not isinstance(previous, dict):
        previous = {}
    data = {"used_pct": used, "observed_at": now, "source": source}
    if resets_at is not None:
        data["resets_at"] = int(resets_at)
    elif number(previous.get("resets_at")) is not None and previous.get("resets_at") > now:
        data["resets_at"] = int(previous["resets_at"])
    plan = plan or clean_text(previous.get("plan"))
    if plan:
        data["plan"] = plan
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(data, handle, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)
    return data


def grok_tokens(row):
    week = row.get("grok_week") if isinstance(row.get("grok_week"), dict) else None
    if not week:
        return None
    tokens = week.get("tokens")
    if isinstance(tokens, bool) or not isinstance(tokens, (int, float)):
        return None
    return tokens


def short_tokens(value):
    value = float(value)
    if value >= 1e6:
        return "%.1fM" % (value / 1e6)
    if value >= 1e3:
        return "%dk" % int(value / 1e3 + 0.5)
    return "%d" % int(value)


def parts(row, long=False):
    """(percent text or "", the rest) so the status line can colour the percent."""
    bits = []
    pct = ""
    windows = row.get("windows") or []
    if windows:
        window = windows[0]
        pct = "%s%%" % window.get("used_pct")
        if row.get("source") == "manual":
            bits.append("manual")
        if window.get("resets_at") is not None:
            label = timefmt.day_time(window["resets_at"])
            bits.append(("resets " + label) if long else label)
    elif row.get("reset_passed"):
        bits.append("reset %s, no newer reading" % timefmt.day_time(row["reset_passed"]))
    if long and row.get("plan"):
        bits.append(row["plan"])
    if long and windows and row.get("source") == "live":
        bits.append("live")
    tokens = grok_tokens(row)
    if tokens is not None:
        bits.append("grok 7d %s tok" % short_tokens(tokens))
    if row.get("stale") and row.get("age") is not None:
        bits.append("%s old" % timefmt.age(row["age"]))
    if long and row.get("fetch_error"):
        bits.append("refresh failed: " + row["fetch_error"])
    return pct, bits


def brief(row, long=False):
    """`74% · Thu 23:22 · grok 7d 1.2M tok`, with `· 9h old` once the reading is
    stale and `· manual` for a typed number."""
    pct, bits = parts(row, long=long)
    return " · ".join(([pct] if pct else []) + bits)


def line_fields(row):
    """grok.line for the status line: the text, then `pct dim source` on line 2.
    A stale or manual reading is dimmed."""
    if not present(row):
        return "", ""
    pct, _bits = parts(row)
    text = LABEL + " " + brief(row)
    dim = row.get("stale") or row.get("source") != "live"
    flags = "%s %d %s" % (pct.rstrip("%") or "-", 1 if dim else 0, row.get("source") or "manual")
    return text, flags


def merge(rows):
    """Swap the cursor and grok rows for one cursor+grok row when the plan cache
    exists. Without it, drop the empty plan row and keep the others."""
    plan = None
    for row in rows:
        if isinstance(row, dict) and row.get("provider") == PROVIDER:
            plan = row
    if not present(plan):
        return [row for row in rows if not (isinstance(row, dict) and row.get("provider") == PROVIDER)]
    merged = dict(plan)
    out = []
    placed = False
    for row in rows:
        name = row.get("provider") if isinstance(row, dict) else None
        if name == "grok" and isinstance(row.get("week"), dict):
            merged["grok_week"] = row["week"]
        if name in ("cursor", "grok", PROVIDER):
            if not placed:
                out.append(merged)
                placed = True
            continue
        out.append(row)
    return out


def label(row):
    if isinstance(row, dict) and row.get("provider") == PROVIDER:
        return row.get("label") or LABEL
    return (row or {}).get("provider") or "tool"


def main():
    json.dump(read(), sys.stdout, sort_keys=True, separators=(",", ":"))
    sys.stdout.write("\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
