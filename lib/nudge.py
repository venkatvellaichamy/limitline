#!/usr/bin/env python3
"""Pick the other tool with the most room, from what Pharos measured. No network.

The readings come from ~/.pharos/usage.json; without Pharos there is nothing to
compare, so there is no nudge. limitline never runs another tool's reader here."""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDER = ("codex", "cursor", "grok", "antigravity")


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
    """The other tools' rows from Pharos's usage.json, with Cursor and Grok as the one
    shared plan, so `→ cursor ok` is not offered for a plan that is 90% used."""
    sys.path.insert(0, os.path.join(ROOT, "lib"))
    try:
        import pharos_view
        import xaiplan
    except Exception:
        return []
    usage = pharos_view.read_usage()
    if usage is None or usage.get("stale"):
        return []
    found = [r for r in pharos_view.plan_rows(usage) if r.get("provider") in ORDER + ("xai-plan",)]
    return xaiplan.merge(found)


def suggestion():
    measured = None
    empty = []
    found = rows()
    rows_seen = [bool(found)]
    for data in found:
        name = data.get("label") or data.get("provider")
        found = constraint_window(data)
        if found is None:
            empty.append(name)
            continue
        used, rough = found
        if measured is None or used < measured[0]:
            measured = (used, name, "~" if rough else "", " estimate" if rough else "")
    hint = idle_machine()
    if not rows_seen[0]:
        return hint
    if measured is not None and measured[0] < 50:
        text = "%s %s%d%%%s" % (measured[1], measured[2], int(measured[0] + 0.5), measured[3])
        if hint:
            text += " · " + hint
        return text
    if hint:
        return hint
    # Antigravity without a reading is unknown, not free, so it is never "ok".
    for name in ("cursor", "codex", "grok"):
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
