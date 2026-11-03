#!/usr/bin/env python3
"""Background cache writer. SSH runs here, never on the status-line hot path."""
import json, os, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fleet
import grokline
import machines
import sync
from config import setting

# Snapshots from other machines older than this are ignored.
SYNC_FRESH = 900

# Non-interactive ssh and launchd both start with PATH=/usr/bin:/bin:/usr/sbin:/sbin,
# which hides a Homebrew `ollama`. Add the usual install folders first.
SCRIPT = (
    "PATH=/opt/homebrew/bin:/usr/local/bin:$PATH; export PATH; "
    "echo '## load'; sysctl -n vm.loadavg; "
    "echo '## ncpu'; sysctl -n hw.ncpu; "
    "echo '## mem'; sysctl -n hw.memsize; "
    "echo '## pressure'; memory_pressure; "
    "echo '## ps'; ollama ps; "
    "echo '## list'; ollama list"
)


def write_text(path, text):
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as handle:
        handle.write(text)
        if text and not text.endswith("\n"):
            handle.write("\n")
    os.replace(tmp, path)


def capture_host(host, timeout):
    fixture = os.environ.get("LIMITLINE_MACHINE_DIR")
    if fixture:
        path = os.path.join(fixture, host["name"] + ".txt")
        if not os.path.isfile(path):
            return ""
        try:
            return open(path).read()
        except OSError:
            return ""
    target = host.get("ssh") or ""
    if host["name"] in ("local", "localhost") or target in ("local", "localhost"):
        try:
            proc = subprocess.run(["sh", "-c", SCRIPT], capture_output=True, text=True, timeout=timeout + 1)
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return proc.stdout or ""
    cmd = [
        "ssh", "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=%d" % timeout,
        "-o", "StrictHostKeyChecking=yes",
        target, SCRIPT,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 1)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if proc.returncode != 0 and not (proc.stdout or "").strip():
        return ""
    return proc.stdout or ""


def sync_folder():
    return setting("sync_dir", "LIMITLINE_SYNC_DIR", "")


def now_epoch():
    return fleet.now_epoch()


def publish_cockpit(kind, payload):
    """Write <sync_dir>/<host>/cockpit/<kind>.json. The subfolder keeps these
    out of the provider snapshots that sit beside it."""
    folder = sync_folder()
    if not folder or not os.path.isdir(folder):
        return
    dest = os.path.join(folder, sync.host_name(), "cockpit")
    try:
        os.makedirs(dest, exist_ok=True)
        write_text(os.path.join(dest, kind + ".json"), json.dumps(payload, sort_keys=True))
    except OSError:
        return


def remote_cockpit(kind):
    """Fresh snapshots of one kind from every other machine in the sync folder."""
    folder = sync_folder()
    found = []
    if not folder or not os.path.isdir(folder):
        return found
    me = sync.host_name()
    now = now_epoch()
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return found
    for name in names:
        if sync.clean_host(name) == me:
            continue
        path = os.path.join(folder, name, "cockpit", kind + ".json")
        try:
            data = json.load(open(path))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        stamp = data.get("observed_at")
        if isinstance(stamp, bool) or not isinstance(stamp, (int, float)) or now - stamp > SYNC_FRESH:
            continue
        found.append((sync.clean_host(name), data))
    return found


def write_fleet():
    states = fleet.collect()
    recent, _ = fleet.split_recent(states)
    counts = fleet.summarize(recent)
    publish_cockpit("fleet", {"observed_at": now_epoch(), "counts": counts})
    for _, data in remote_cockpit("fleet"):
        other = data.get("counts")
        if not isinstance(other, dict):
            continue
        for key in ("run", "verify", "failed", "warn", "stopped"):
            value = other.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                counts[key] = counts.get(key, 0) + value
    text = fleet.format_segment(counts)
    path = os.environ.get("LIMITLINE_FLEET_LINE") or os.path.join(machines.cache_dir(), "fleet.line")
    write_text(path, text)


def write_machines():
    hosts = machines.resolve_hosts()
    timeout = machines.ssh_timeout()
    threshold = machines.warn_threshold()
    rows = []
    for host in hosts:
        text = capture_host(host, timeout)
        rows.append(machines.parse_snapshot(host["name"], text, threshold))
    if rows:
        publish_cockpit("machines", {"observed_at": now_epoch(), "hosts": rows})
    seen = set(row.get("name") for row in rows)
    for origin, data in remote_cockpit("machines"):
        for row in data.get("hosts") or []:
            if not isinstance(row, dict) or row.get("name") in seen:
                continue
            item = dict(row)
            item["via"] = origin
            rows.append(item)
            seen.add(item.get("name"))
    payload = {"hosts": rows, "observed_at": now_epoch()}
    path = os.environ.get("LIMITLINE_MACHINES_JSON") or os.path.join(machines.cache_dir(), "machines.json")
    # A caller-supplied JSON path is an input for readers. Refresh writes the cache copy
    # unless that env var is the destination the tests set on purpose.
    write_text(path, json.dumps(payload, sort_keys=True))
    line = machines.format_hosts(rows, long=False)
    line_dest = os.environ.get("LIMITLINE_MACHINES_LINE") or os.path.join(machines.cache_dir(), "machines.line")
    write_text(line_dest, line)


def write_grok():
    """Plan and 7-day tokens from ~/.grok. Written even when empty, so a stale
    line does not outlive the files it came from."""
    text = grokline.segment()
    path = os.environ.get("LIMITLINE_GROK_LINE") or os.path.join(machines.cache_dir(), "grok.line")
    write_text(path, text)


def main():
    for step in (write_grok, write_fleet, write_machines):
        try:
            step()
        except Exception:
            continue


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
