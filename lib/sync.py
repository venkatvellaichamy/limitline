#!/usr/bin/env python3
"""Publish local snapshots into a synced folder and merge them. No servers."""
import json, os, re, sys


def clean_host(name):
    text = re.sub(r"[^A-Za-z0-9-]", "", str(name or ""))
    return text or "local"


def host_name():
    env = os.environ.get("LIMITLINE_HOST")
    if env:
        return clean_host(env)
    try:
        raw = os.uname().nodename.split(".")[0]
    except Exception:
        raw = "local"
    return clean_host(raw)


def publish(sync_dir, provider, data, host=None):
    if not sync_dir or not isinstance(data, dict):
        return
    dest_dir = os.path.join(sync_dir, host or host_name())
    try:
        os.makedirs(dest_dir, exist_ok=True)
        path = os.path.join(dest_dir, provider + ".json")
        tmp = path + ".tmp"
        with open(tmp, "w") as handle:
            json.dump(data, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
        os.replace(tmp, path)
    except Exception:
        return


def _read(path):
    try:
        with open(path) as handle:
            data = json.load(handle)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def collect(sync_dir):
    found = []
    if not sync_dir or not os.path.isdir(sync_dir):
        return found
    try:
        hosts = sorted(os.listdir(sync_dir))
    except Exception:
        return found
    for host in hosts:
        folder = os.path.join(sync_dir, host)
        if not os.path.isdir(folder):
            continue
        try:
            names = os.listdir(folder)
        except Exception:
            continue
        for name in names:
            if not name.endswith(".json"):
                continue
            data = _read(os.path.join(folder, name))
            if not data:
                continue
            provider = data.get("provider") or name[:-5]
            found.append((clean_host(host), provider, data))
    return found


# A snapshot window with no reset counts only while the snapshot is this young.
FRESH = 900
# Two readings belong to the same reset cycle when their resets are this close.
# Resets derived from `resets_in_seconds` drift by seconds between machines.
SAME_CYCLE = 600


def _epoch(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _now():
    import time
    try:
        return int(os.environ.get("LIMITLINE_NOW") or time.time())
    except ValueError:
        return int(time.time())


def eligible(data, window, now):
    """A synced reading counts only while it can still be current: not marked
    stale, its reset still ahead, or (with no reset) a fresh snapshot. The
    `stale` flag alone is not enough, because an offline host never updates it."""
    if data.get("stale"):
        return False
    reset = _epoch(window.get("resets_at"))
    if reset is not None:
        return reset > now
    observed = _epoch(data.get("observed_at"))
    return observed is not None and now - observed <= FRESH


def merge_rows(rows, sync_dir, now=None):
    """Raise each window to the highest current reading from any machine, comparing
    readings only within one reset cycle. The newest cycle wins, so an old cycle
    never replaces the current one, and the local reading stays when nothing synced
    is eligible."""
    if now is None:
        now = _now()
    grouped = {}
    for host, provider, data in collect(sync_dir):
        for window in data.get("windows") or []:
            if not isinstance(window, dict):
                continue
            used = window.get("used_pct")
            if isinstance(used, bool) or not isinstance(used, (int, float)):
                continue
            if not eligible(data, window, now):
                continue
            key = (provider, window.get("name") or "limit")
            grouped.setdefault(key, []).append((host, used, _epoch(window.get("resets_at"))))
    if not grouped:
        return rows
    local = {}
    for row in rows:
        for window in row.get("windows") or []:
            if isinstance(window, dict):
                local[(row.get("provider"), window.get("name") or "limit")] = _epoch(window.get("resets_at"))
    for key in list(grouped):
        readings = grouped[key]
        resets = [item[2] for item in readings if item[2] is not None]
        if local.get(key) is not None:
            resets.append(local[key])
        if resets:
            # The latest reset is the current cycle; readings with another reset are dropped.
            latest = max(resets)
            readings = [item for item in readings if item[2] is None or latest - item[2] <= SAME_CYCLE]
        if not readings:
            del grouped[key]
            continue
        top = max(readings, key=lambda item: item[1])
        grouped[key] = {"used": top[1], "resets_at": top[2], "hosts": set(item[0] for item in readings),
                        "local_reset": local.get(key)}
    if not grouped:
        return rows
    by_provider = {}
    for row in rows:
        by_provider[row.get("provider")] = row
    for (provider, name), bucket in grouped.items():
        row = by_provider.get(provider)
        if row is None:
            continue
        windows = []
        replaced = False
        for window in row.get("windows") or []:
            if isinstance(window, dict) and (window.get("name") or "limit") == name:
                updated = dict(window)
                mine = window.get("used_pct")
                theirs = bucket["used"]
                mine_reset = bucket.get("local_reset")
                newer = (bucket.get("resets_at") is not None and mine_reset is not None
                         and bucket["resets_at"] - mine_reset > SAME_CYCLE)
                if newer or isinstance(mine, bool) or not isinstance(mine, (int, float)) or theirs > mine:
                    updated["used_pct"] = int(theirs + 0.5) if float(theirs).is_integer() else theirs
                    if bucket.get("resets_at") is not None:
                        updated["resets_at"] = bucket["resets_at"]
                updated["machines"] = len(bucket["hosts"])
                windows.append(updated)
                replaced = True
            else:
                windows.append(window)
        if not replaced:
            item = {"name": name, "used_pct": bucket["used"], "machines": len(bucket["hosts"])}
            if bucket.get("resets_at") is not None:
                item["resets_at"] = bucket["resets_at"]
            windows.append(item)
        row["windows"] = windows
    return rows


def main():
    if len(sys.argv) < 2:
        return
    if sys.argv[1] == "publish":
        provider = sys.argv[2] if len(sys.argv) > 2 else "claude"
        sync_dir = os.environ.get("LIMITLINE_SYNC_DIR") or ""
        raw = sys.stdin.read()
        try:
            data = json.loads(raw or "{}")
        except Exception:
            return
        publish(sync_dir, provider, data)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
