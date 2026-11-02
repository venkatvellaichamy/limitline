#!/usr/bin/env python3
"""Pick the other local tool with the most room. No network."""
import json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDER = ("codex", "cursor", "grok", "gemini")


def run_provider(name):
    path = os.path.join(ROOT, "providers", name)
    try:
        proc = subprocess.run([path], capture_output=True, timeout=2, env=os.environ.copy())
        data = json.loads(proc.stdout.decode() or "{}")
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("windows", [])
    return data


def lowest_pct(data):
    best = None
    for window in data.get("windows") or []:
        if not isinstance(window, dict):
            continue
        used = window.get("used_pct")
        if isinstance(used, bool) or not isinstance(used, (int, float)):
            continue
        if best is None or used < best:
            best = used
    return best


def idle_machine():
    sys.path.insert(0, os.path.join(ROOT, "lib"))
    try:
        import machines
        return machines.idle_hint(ttl=int(os.environ.get("LIMITLINE_MACHINES_TTL") or "60"))
    except Exception:
        return ""


def suggestion():
    measured = None
    empty = []
    for name in ORDER:
        data = run_provider(name)
        used = lowest_pct(data)
        if used is None:
            empty.append(name)
            continue
        if measured is None or used < measured[0]:
            measured = (used, name)
    hint = idle_machine()
    if measured is not None and measured[0] < 50:
        text = "%s %d%%" % (measured[1], int(measured[0] + 0.5))
        if hint:
            text += " · " + hint
        return text
    if hint:
        return hint
    for name in ("cursor", "codex", "grok", "gemini"):
        if name in empty:
            return name + " ok"
    if measured is not None:
        return "%s %d%%" % (measured[1], int(measured[0] + 0.5))
    return ""


def main():
    text = suggestion()
    if text:
        sys.stdout.write(text + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
