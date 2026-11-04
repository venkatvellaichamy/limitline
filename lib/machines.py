#!/usr/bin/env python3
"""Host rows Pharos measured (usage.json → hosts), formatted for display. No ssh, no probe."""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import setting

SCALE = {"K": 1 << 10, "M": 1 << 20, "G": 1 << 30, "T": 1 << 40}


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "limitline")


def json_path():
    override = os.environ.get("LIMITLINE_MACHINES_JSON")
    if override:
        return override
    return os.path.join(cache_dir(), "machines.json")


def line_path():
    override = os.environ.get("LIMITLINE_MACHINES_LINE")
    if override:
        return override
    return os.path.join(cache_dir(), "machines.line")


def mem_text(host):
    """Memory is shown as free percent, the same number `memory_pressure` prints."""
    free = host.get("free_pct")
    if isinstance(free, (int, float)) and not isinstance(free, bool):
        return "%d%% free" % int(free)
    load = host.get("load_pct")
    if isinstance(load, (int, float)) and not isinstance(load, bool):
        return "load %d%%" % int(load)
    return ""


def format_host(host, long=False):
    name = host.get("name") or "host"
    if not host.get("reachable"):
        return name + " ∅"
    text = name
    mem = mem_text(host)
    if mem:
        text += " " + mem
    loaded = host.get("loaded") or ""
    if loaded.endswith(":latest"):
        loaded = loaded[: -len(":latest")]
    if loaded:
        text += " · " + loaded
    if long:
        load = host.get("load_pct")
        if host.get("free_pct") is not None and isinstance(load, (int, float)) and not isinstance(load, bool):
            text += " · load %d%%" % int(load)
        count = host.get("installed_count")
        if isinstance(count, int) and count > 0:
            text += " · %d installed" % count
    if host.get("mem_warn"):
        text += " ⚠"
    return text


HOST_SEP = " / "


def format_hosts(hosts, long=False):
    parts = [format_host(host, long=long) for host in hosts if isinstance(host, dict)]
    return HOST_SEP.join(part for part in parts if part)


def default_ttl():
    raw = setting("machines_ttl", "LIMITLINE_MACHINES_TTL", "180")
    try:
        value = int(float(raw))
    except (TypeError, ValueError):
        value = 180
    return value if value > 0 else 180


def read_cache(path=None, ttl=180):
    path = path or json_path()
    if not os.path.isfile(path):
        return None
    if os.environ.get("LIMITLINE_MACHINES_JSON") in (None, ""):
        try:
            age = int(__import__("time").time() - os.path.getmtime(path))
        except OSError:
            return None
        if age > ttl:
            return None
    try:
        data = json.load(open(path))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    hosts = data.get("hosts")
    if not isinstance(hosts, list):
        return None
    return data


def status_text(ttl=None):
    data = read_cache(ttl=default_ttl() if ttl is None else ttl)
    if not data:
        return ""
    return format_hosts(data.get("hosts") or [], long=True)


def idle_hint(ttl=None):
    data = read_cache(ttl=default_ttl() if ttl is None else ttl)
    if not data:
        return ""
    best = None
    for host in data.get("hosts") or []:
        if not isinstance(host, dict) or not host.get("reachable") or host.get("mem_warn"):
            continue
        load = host.get("load_pct")
        if isinstance(load, bool) or not isinstance(load, (int, float)):
            continue
        if load >= 20:
            continue
        if best is None or load < best[0]:
            best = (load, host.get("name") or "host")
    if best is None:
        return ""
    return "%s idle" % best[1]


def main():
    text = format_hosts((read_cache(ttl=default_ttl()) or {}).get("hosts") or [])
    if text:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        main()
    except Exception:
        sys.exit(0)
