#!/usr/bin/env python3
"""Background cache writer. SSH runs here, never on the status-line hot path."""
import json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fleet
import machines

SCRIPT = (
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


def write_fleet():
    text = fleet.segment_text()
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
    payload = {"hosts": rows}
    path = os.environ.get("LIMITLINE_MACHINES_JSON") or os.path.join(machines.cache_dir(), "machines.json")
    # A caller-supplied JSON path is an input for readers. Refresh writes the cache copy
    # unless that env var is the destination the tests set on purpose.
    write_text(path, json.dumps(payload, sort_keys=True))
    line = machines.format_hosts(rows, long=False)
    line_dest = os.environ.get("LIMITLINE_MACHINES_LINE") or os.path.join(machines.cache_dir(), "machines.line")
    write_text(line_dest, line)


def main():
    write_fleet()
    write_machines()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
