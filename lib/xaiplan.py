#!/usr/bin/env python3
"""The shared xAI plan: one subscription covers Cursor, Grok, Grok Bot, and Grok Build.

No local CLI exposes the plan's percent. The number comes from a small cache at
~/.cache/limitline/xai-plan.json, written by `limitline set xai-plan` or by a
browser helper that reads the usage dashboard:

    {"used_pct": 69, "resets_at": <epoch>, "observed_at": <epoch>,
     "plan": "Super", "source": "dashboard"}

A reading older than 6 hours is shown dimmed with its age. One older than 7 days
is hidden. Once resets_at has passed, the percent belongs to an old window and
is not shown. When the cache is present, Cursor and Grok are one row, and the
Cursor token estimate is not shown at all.
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timefmt

PROVIDER = "xai-plan"
LABEL = "cursor+grok"
STALE_AFTER = 6 * 3600
HIDE_AFTER = 7 * 86400


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "limitline")


def cache_path():
    return os.environ.get("LIMITLINE_XAI_PLAN") or os.path.join(cache_dir(), "xai-plan.json")


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


def read(now=None):
    now = now_epoch() if now is None else now
    out = empty()
    try:
        data = json.load(open(cache_path()))
    except (OSError, ValueError):
        return out
    if not isinstance(data, dict):
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
    out["source"] = clean_text(data.get("source")) or "dashboard"
    out["stale"] = age > STALE_AFTER
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
        if window.get("resets_at") is not None:
            label = timefmt.month_day(window["resets_at"])
            bits.append(("resets " + label) if long else label)
    elif row.get("reset_passed"):
        bits.append("reset %s, no newer reading" % timefmt.month_day(row["reset_passed"]))
    if long and row.get("plan"):
        bits.append(row["plan"])
    tokens = grok_tokens(row)
    if tokens is not None:
        bits.append("grok 7d %s tok" % short_tokens(tokens))
    if row.get("stale") and row.get("age") is not None:
        bits.append("%s old" % timefmt.age(row["age"]))
    return pct, bits


def brief(row, long=False):
    """`69% · Nov 5 · grok 7d 1.2M tok`, with `· 9h old` once the reading is stale."""
    pct, bits = parts(row, long=long)
    return " · ".join(([pct] if pct else []) + bits)


def line_fields(row):
    """grok.line for the status line: the text, then `pct stale` on line 2."""
    if not present(row):
        return "", ""
    pct, _bits = parts(row)
    text = LABEL + " " + brief(row)
    flags = "%s %d" % (pct.rstrip("%") or "-", 1 if row.get("stale") else 0)
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
