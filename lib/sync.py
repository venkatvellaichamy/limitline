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


def merge_rows(rows, sync_dir):
    """Raise each window to the highest reading from any machine on that window."""
    grouped = {}
    for host, provider, data in collect(sync_dir):
        for window in data.get("windows") or []:
            if not isinstance(window, dict):
                continue
            name = window.get("name") or "limit"
            used = window.get("used_pct")
            if isinstance(used, bool) or not isinstance(used, (int, float)):
                continue
            key = (provider, name)
            bucket = grouped.setdefault(key, {"used": used, "resets_at": window.get("resets_at"), "hosts": set()})
            bucket["hosts"].add(host)
            if used >= bucket["used"]:
                bucket["used"] = used
                if window.get("resets_at") is not None:
                    bucket["resets_at"] = window.get("resets_at")
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
                updated["used_pct"] = int(bucket["used"] + 0.5) if float(bucket["used"]).is_integer() else bucket["used"]
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
