#!/usr/bin/env python3
"""Reported jobs, from Pharos's summary.json (`pharos job update ...`). Display only.

`limitline job` moved to Pharos on 2026-11-03: `pharos job update <name> --done N --total N`.
"""
import json, os, sys

SEGMENT_LIMIT = 3
MOVED = "limitline job moved to Pharos: pharos job update <name> [--done N] [--total N] ... | pharos job list | pharos job rm <name>"


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "limitline")


def line_path():
    return os.environ.get("LIMITLINE_JOBS_LINE") or os.path.join(cache_dir(), "jobs.line")


def load(summary=None):
    if summary is None:
        import fleet
        summary = fleet.read_summary()
    rows = (summary or {}).get("jobs")
    return [j for j in rows or [] if isinstance(j, dict) and j.get("name")]


def summary(found, limit=SEGMENT_LIMIT):
    if not found:
        return ""
    shown = [str(job.get("text") or job.get("name")) for job in found[:limit]]
    if len(found) > limit:
        shown.append("+%d" % (len(found) - limit))
    return " · ".join(shown)


def segment(found=None):
    text = summary(load() if found is None else found)
    return ("jobs " + text) if text else ""


def detail_lines(found):
    lines = []
    for job in found:
        bits = [str(job.get("name")), str(job.get("machine") or "-"), str(job.get("status") or "-")]
        done, total = job.get("done"), job.get("total")
        if isinstance(done, int):
            bits.append("%d/%d" % (done, total) if isinstance(total, int) and total else str(done))
        if job.get("log"):
            bits.append(str(job["log"]))
        lines.append("  ".join(bits))
    return lines


def write_line(found=None):
    text = segment(found)
    path = line_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w") as handle:
        if text:
            handle.write(text + "\n")
    os.replace(tmp, path)
    return text


def main(argv):
    print(MOVED, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
