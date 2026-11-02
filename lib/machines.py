#!/usr/bin/env python3
"""Machine load and local models. The status line reads a cache; SSH stays in refresh."""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import parse_list, setting

SIZE = re.compile(r"^(\S+)\s+\S+\s+([0-9.]+)\s*([KMGT]i?B)\b", re.I)
FREE = re.compile(r"free percentage:\s*([0-9.]+)\s*%", re.I)
NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?")
HOST_NAME = re.compile(r"^[A-Za-z0-9_.:@%-]+$")
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


def warn_threshold():
    raw = setting("mem_free_warn", "LIMITLINE_MEM_WARN", "15")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 15.0
    if value < 0:
        value = 0
    if value > 100:
        value = 100
    return value


def ssh_timeout():
    raw = setting("ssh_timeout", "LIMITLINE_SSH_TIMEOUT", "2")
    try:
        value = int(float(raw))
    except (TypeError, ValueError):
        value = 2
    if value < 1:
        value = 1
    if value > 15:
        value = 15
    return value


def split_host(raw):
    text = (raw or "").strip()
    if not text:
        return None
    if "=" in text:
        name, ssh = text.split("=", 1)
        name, ssh = name.strip(), ssh.strip()
    else:
        name = ssh = text
    if "@" in name and "=" not in (raw or ""):
        name = name.split("@", 1)[-1]
    name = name.split(".", 1)[0] if name == ssh and "." in name and "@" not in name else name
    if not name or not HOST_NAME.match(name) or not ssh or not HOST_NAME.match(ssh):
        return None
    return {"name": name, "ssh": ssh}


def pharos_home():
    override = os.environ.get("LIMITLINE_PHAROS_HOME")
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".pharos")


def hosts_from_pharos():
    path = os.path.join(pharos_home(), "machines.json")
    if not os.path.isfile(path):
        return []
    try:
        data = json.load(open(path))
    except (OSError, ValueError):
        return []
    rows = data.get("hosts") if isinstance(data, dict) else data
    if isinstance(rows, str):
        rows = parse_list(rows)
    found = []
    if not isinstance(rows, list):
        return found
    for row in rows:
        if isinstance(row, str):
            item = split_host(row)
        elif isinstance(row, dict):
            name = str(row.get("name") or "").strip()
            ssh = str(row.get("ssh") or name).strip()
            item = split_host("%s=%s" % (name, ssh) if name else ssh)
        else:
            item = None
        if item:
            found.append(item)
    return found


def resolve_hosts():
    if "LIMITLINE_HOSTS" in os.environ:
        raw = os.environ.get("LIMITLINE_HOSTS") or ""
    else:
        raw = setting("hosts", "LIMITLINE_HOSTS_FROM_FILE", "")
    items = []
    for piece in parse_list(raw):
        item = split_host(piece)
        if item:
            items.append(item)
    if items or "LIMITLINE_HOSTS" in os.environ:
        return items
    return hosts_from_pharos()


def section_split(text):
    parts = {}
    current = ""
    bucket = []
    for line in (text or "").splitlines():
        if line.startswith("## "):
            if current:
                parts[current] = "\n".join(bucket).strip()
            current = line[3:].strip()
            bucket = []
            continue
        bucket.append(line)
    if current:
        parts[current] = "\n".join(bucket).strip()
    return parts


def parse_size(number, unit):
    key = unit[:1].upper()
    factor = SCALE.get(key)
    if not factor:
        return 0
    try:
        return int(float(number) * factor)
    except ValueError:
        return 0


def parse_models(text):
    loaded = []
    for line in (text or "").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("NAME") or raw.startswith("##"):
            continue
        match = SIZE.match(raw)
        if not match:
            continue
        loaded.append({"name": match.group(1), "bytes": parse_size(match.group(2), match.group(3))})
    return loaded


def parse_load(text, ncpu):
    nums = NUMBER.findall(text or "")
    if not nums:
        return None
    load = float(nums[0])
    if ncpu and ncpu > 0:
        return int(load / ncpu * 100 + 0.5)
    return int(load * 100 + 0.5)


def parse_snapshot(name, text, threshold):
    if not text or text.lstrip().startswith("(unavailable") or text.lstrip().startswith("(exit"):
        return {"name": name, "reachable": False}
    parts = section_split(text)
    if "load" not in parts and "ps" not in parts and "pressure" not in parts:
        return {"name": name, "reachable": False}
    try:
        ncpu = int(float(NUMBER.findall(parts.get("ncpu") or "")[0]))
    except (IndexError, ValueError):
        ncpu = 0
    try:
        total = int(float(NUMBER.findall(parts.get("mem") or "")[0]))
    except (IndexError, ValueError):
        total = 0
    free_match = FREE.search(parts.get("pressure") or "")
    free_pct = float(free_match.group(1)) if free_match else None
    models = parse_models(parts.get("ps") or "")
    installed = parse_models(parts.get("list") or "")
    loaded = models[0]["name"] if models else ""
    loaded_bytes = models[0]["bytes"] if models else 0
    warn = False
    if loaded:
        if free_pct is not None and free_pct < threshold:
            warn = True
        if loaded_bytes and total and (total - loaded_bytes) / float(total) * 100 < threshold:
            warn = True
    return {
        "name": name,
        "reachable": True,
        "load_pct": parse_load(parts.get("load") or "", ncpu),
        "free_pct": None if free_pct is None else int(free_pct + 0.5),
        "total_bytes": total,
        "loaded": loaded,
        "loaded_bytes": loaded_bytes,
        "installed": [item["name"] for item in installed],
        "installed_count": len(installed),
        "mem_warn": warn,
    }


def format_host(host, long=False):
    name = host.get("name") or "host"
    if not host.get("reachable"):
        return name + " ∅"
    bits = [name]
    load = host.get("load_pct")
    if isinstance(load, (int, float)) and not isinstance(load, bool):
        bits.append("%d%%" % int(load))
    loaded = host.get("loaded") or ""
    if loaded:
        bits.append(loaded)
    text = " ".join(bits)
    count = host.get("installed_count")
    if long and isinstance(count, int) and count > 0:
        text += " · %d installed" % count
    if host.get("mem_warn"):
        text += " ⚠"
    return text


def format_hosts(hosts, long=False):
    parts = [format_host(host, long=long) for host in hosts if isinstance(host, dict)]
    return " · ".join(part for part in parts if part)


def read_cache(path=None, ttl=60):
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


def status_text(ttl=60):
    data = read_cache(ttl=ttl)
    if not data:
        return ""
    return format_hosts(data.get("hosts") or [], long=True)


def idle_hint(ttl=60):
    data = read_cache(ttl=ttl)
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
    text = format_hosts((read_cache(ttl=int(os.environ.get("LIMITLINE_MACHINES_TTL") or "60")) or {}).get("hosts") or [])
    if text:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        main()
    except Exception:
        sys.exit(0)
