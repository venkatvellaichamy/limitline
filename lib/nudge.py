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


def constraint_pct(data):
    found = constraint_window(data)
    return None if found is None else found[0]


def constraint_window(data):
    """The most-used window. A provider is only as free as its tightest window:
    a quiet 5h window cannot make up for an exhausted week. lib/cli.py sorts
    status rows by the same maximum."""
    best = None
    for window in data.get("windows") or []:
        if not isinstance(window, dict):
            continue
        used = window.get("used_pct")
        if isinstance(used, bool) or not isinstance(used, (int, float)):
            continue
        if best is None or used > best[0]:
            best = (used, bool(window.get("estimate")))
    return best


def idle_machine():
    sys.path.insert(0, os.path.join(ROOT, "lib"))
    try:
        import machines
        return machines.idle_hint()
    except Exception:
        return ""


def rows():
    """Provider rows, with Cursor and Grok folded into the shared plan when its
    cache exists, so `→ cursor ok` is not offered for a plan that is 90% used."""
    found = [dict(run_provider(name), provider=name) for name in ORDER]
    plan = run_provider("xai-plan")
    plan.setdefault("provider", "xai-plan")
    sys.path.insert(0, os.path.join(ROOT, "lib"))
    try:
        import xaiplan
        return xaiplan.merge(found + [plan])
    except Exception:
        return found


def suggestion():
    measured = None
    empty = []
    for data in rows():
        name = data.get("label") or data.get("provider")
        found = constraint_window(data)
        if found is None:
            empty.append(name)
            continue
        used, rough = found
        if measured is None or used < measured[0]:
            measured = (used, name, "~" if rough else "", " estimate" if rough else "")
    hint = idle_machine()
    if measured is not None and measured[0] < 50:
        text = "%s %s%d%%%s" % (measured[1], measured[2], int(measured[0] + 0.5), measured[3])
        if hint:
            text += " · " + hint
        return text
    if hint:
        return hint
    for name in ("cursor", "codex", "grok", "gemini"):
        if name in empty:
            return name + " ok"
    if measured is not None:
        return "%s %s%d%%%s" % (measured[1], measured[2], int(measured[0] + 0.5), measured[3])
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
