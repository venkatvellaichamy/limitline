#!/usr/bin/env python3
"""Rebuild the status line's small caches from what Pharos measured. Measures nothing.

grok.line and machines.line come from ~/.pharos/usage.json, fleet.line from Pharos's run
states, jobs.line from `limitline job` reports. No provider command, no ssh, no network:
Pharos does that (`pharos usage --refresh`).
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fleet
import grokline
import jobs
import machines
import pharos_view
import xaiplan


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


def write_fleet():
    states = fleet.collect()
    recent, _ = fleet.split_recent(states)
    text = fleet.format_segment(fleet.summarize(recent))
    path = os.environ.get("LIMITLINE_FLEET_LINE") or os.path.join(machines.cache_dir(), "fleet.line")
    write_text(path, text)


def write_machines(usage):
    rows = pharos_view.hosts(usage) if usage else []
    path = os.environ.get("LIMITLINE_MACHINES_JSON") or os.path.join(machines.cache_dir(), "machines.json")
    write_text(path, json.dumps({"hosts": rows, "observed_at": (usage or {}).get("generated_at")}, sort_keys=True))
    line_dest = os.environ.get("LIMITLINE_MACHINES_LINE") or os.path.join(machines.cache_dir(), "machines.line")
    write_text(line_dest, machines.format_hosts(rows, long=False))


def _cli():
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cli.py")
    spec = importlib.util.spec_from_file_location("limitline_cli", path)
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    return cli


def write_grok(usage=None):
    """grok.line: `cursor+grok 74% · Thu 23:22 · grok 7d 1.2M tok`, then `pct dim source`.
    The rows come from Pharos, or, inside Grok or Cursor without Pharos, from that
    tool's own files. Written even when empty, so a stale line does not outlive them."""
    text, flags = "", ""
    rows = _cli().load_all()
    for row in rows:
        if row.get("provider") == xaiplan.PROVIDER:
            text, flags = xaiplan.line_fields(row)
    if not text:
        grok = next((r for r in rows if r.get("provider") == "grok"), None)
        text = grokline.segment(grok) if grok else ""
    path = os.environ.get("LIMITLINE_GROK_LINE") or os.path.join(machines.cache_dir(), "grok.line")
    write_text(path, text + ("\n" + flags if flags else ""))


def write_jobs():
    if os.path.isdir(jobs.jobs_dir()):
        jobs.write_line()


def write_history():
    import history
    history.record(_cli().load_all())


def main(argv=None):
    usage = pharos_view.read_usage()
    for step in (lambda: write_grok(usage), write_jobs, write_fleet, lambda: write_machines(usage), write_history):
        try:
            step()
        except Exception:
            continue
    return ""


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
