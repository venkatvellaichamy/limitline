#!/usr/bin/env python3
"""30-day local history: plan percents and finished jobs. No network.

Plan samples live in ~/.cache/limitline/history/<plan>.tsv as
`epoch pct resets_at` lines, at most one per 10 minutes per plan, kept for
30 days. Plans are measured windows only: claude-5h, claude-7d, codex-5h,
codex-7d, cursor+grok-week, gemini-quota. Estimates and stale rows are not
recorded, so a history line is never built from a guess.

Finished jobs (ok, failed, stopped, or dead) are appended once each to
~/.cache/limitline/jobs-history.jsonl with their machine, so the history and
the weekly report can group them per machine.

`limitline refresh` and `limitline status` record samples. `limitline history`
prints 30-day sparklines and job history; `limitline report --week` is the
weekly report.
"""
import json, os, re, sys, time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timefmt

KEEP_DAYS = 30
MIN_GAP = 600
BLOCKS = "▁▂▃▄▅▆▇█"
MISSING = "."
SAFE = re.compile(r"[^A-Za-z0-9+._-]")


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "limitline")


def history_dir():
    return os.environ.get("LIMITLINE_HISTORY_DIR") or os.path.join(cache_dir(), "history")


def jobs_history_path():
    return os.environ.get("LIMITLINE_JOBS_HISTORY") or os.path.join(cache_dir(), "jobs-history.jsonl")


def now_epoch():
    try:
        return int(os.environ.get("LIMITLINE_NOW") or time.time())
    except ValueError:
        return int(time.time())


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return value


def plan_samples(rows):
    """[(plan key, pct, resets_at)] for measured, current windows."""
    found = []
    for row in rows or []:
        if not isinstance(row, dict) or row.get("stale"):
            continue
        if row.get("source") in (None, "none", "estimate", "manual"):
            continue
        provider = row.get("label") or row.get("provider") or ""
        if provider in ("api",):
            continue
        for window in row.get("windows") or []:
            if not isinstance(window, dict) or window.get("estimate"):
                continue
            used = number(window.get("used_pct"))
            if used is None:
                continue
            if isinstance(window.get("machines"), int) and window.get("machines") > 1:
                continue
            key = SAFE.sub("", "%s-%s" % (provider, window.get("name") or "limit"))
            if key:
                found.append((key, used, number(window.get("resets_at"))))
    return found


def read_tsv(path):
    rows = []
    try:
        handle = open(path)
    except OSError:
        return rows
    with handle:
        for line in handle:
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                stamp = int(float(parts[0]))
                pct = float(parts[1])
            except ValueError:
                continue
            reset = None
            if len(parts) > 2 and parts[2] != "-":
                try:
                    reset = int(float(parts[2]))
                except ValueError:
                    reset = None
            rows.append((stamp, pct, reset))
    return rows


def write_tsv(path, rows):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w") as handle:
        for stamp, pct, reset in rows:
            value = ("%d" % pct) if float(pct).is_integer() else ("%.1f" % pct)
            handle.write("%d %s %s\n" % (stamp, value, "-" if reset is None else int(reset)))
    os.replace(tmp, path)


def record(rows, now=None):
    """Append one sample per plan, no more than one per 10 minutes, and drop
    samples older than 30 days. Returns the plan keys written."""
    now = now_epoch() if now is None else now
    written = []
    cutoff = now - KEEP_DAYS * 86400
    for key, used, reset in plan_samples(rows):
        path = os.path.join(history_dir(), key + ".tsv")
        existing = [item for item in read_tsv(path) if item[0] >= cutoff]
        if existing and now - existing[-1][0] < MIN_GAP and existing[-1][0] <= now:
            continue
        existing.append((now, used, reset))
        try:
            write_tsv(path, existing)
            written.append(key)
        except OSError:
            continue
    prune(cutoff, skip=written)
    return written


def prune(cutoff, skip=()):
    """Drop samples older than 30 days from plans that were not just written."""
    for key in plans():
        if key in skip:
            continue
        path = os.path.join(history_dir(), key + ".tsv")
        rows = read_tsv(path)
        if rows and rows[0][0] < cutoff:
            kept = [item for item in rows if item[0] >= cutoff]
            try:
                if kept:
                    write_tsv(path, kept)
                else:
                    os.remove(path)
            except OSError:
                continue


def plans():
    try:
        names = sorted(os.listdir(history_dir()))
    except OSError:
        return []
    return [name[:-4] for name in names if name.endswith(".tsv")]


def local_day(epoch):
    return datetime.fromtimestamp(int(epoch)).date()


def daily_peaks(samples, now, days):
    """{date: highest percent that day} for the last `days` local days."""
    first = local_day(now) - timedelta(days=days - 1)
    peaks = {}
    for stamp, pct, _reset in samples:
        day = local_day(stamp)
        if day < first or stamp > now + 300:
            continue
        if day not in peaks or pct > peaks[day]:
            peaks[day] = pct
    return first, peaks


def spark(first, peaks, days):
    out = []
    for offset in range(days):
        day = first + timedelta(days=offset)
        if day not in peaks:
            out.append(MISSING)
            continue
        pct = max(0, min(100, peaks[day]))
        out.append(BLOCKS[min(7, int(pct * 8 / 100))])
    return "".join(out)


def resets_seen(samples):
    """Windows that rolled over: a later sample with a later resets_at."""
    count = 0
    last = None
    for _stamp, _pct, reset in samples:
        if reset is None:
            continue
        if last is not None and reset > last:
            count += 1
        last = reset
    return count


def plan_summary(key, now, days):
    samples = [item for item in read_tsv(os.path.join(history_dir(), key + ".tsv")) if item[0] <= now + 300]
    first, peaks = daily_peaks(samples, now, days)
    if not peaks:
        return None
    top_day = max(peaks, key=lambda day: (peaks[day], day))
    values = list(peaks.values())
    return {
        "plan": key,
        "spark": spark(first, peaks, days),
        "peak": peaks[top_day],
        "peak_day": top_day,
        "avg": sum(values) / len(values),
        "days": len(values),
        "over80": sum(1 for value in values if value > 80),
        "now": samples[-1][1] if samples else None,
        "resets": resets_seen([item for item in samples if local_day(item[0]) >= first]),
    }


def day_label(day):
    return "%s %d" % (day.strftime("%b"), day.day)


def pct_text(value):
    return "%d%%" % int(value + 0.5)


# Jobs

def job_record(job, ended_at):
    item = {"name": job.get("name"), "machine": job.get("machine") or "?",
            "status": job.get("shown_status") or job.get("status"), "ended_at": int(ended_at)}
    for key in ("started_at", "done", "total", "failed"):
        value = number(job.get(key))
        if value is not None:
            item[key] = int(value)
    return item


def read_jobs_history():
    found = []
    try:
        handle = open(jobs_history_path())
    except OSError:
        return found
    with handle:
        for line in handle:
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict) and item.get("name"):
                found.append(item)
    return found


def record_jobs(found, now=None):
    """Append finished and dead jobs once each, keyed by (machine, name, started_at)."""
    now = now_epoch() if now is None else now
    try:
        import jobs
    except Exception:
        return 0
    finished = [job for job in found or [] if jobs.kind(job.get("shown_status") or "") != "active"]
    if not finished:
        return 0
    seen = set((item.get("machine"), item.get("name"), item.get("started_at")) for item in read_jobs_history())
    fresh = []
    for job in finished:
        ended = number(job.get("updated_at")) or now
        item = job_record(job, ended)
        key = (item.get("machine"), item.get("name"), item.get("started_at"))
        if key in seen:
            continue
        seen.add(key)
        fresh.append(item)
    if not fresh:
        return 0
    path = jobs_history_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cutoff = now - KEEP_DAYS * 86400
    kept = [item for item in read_jobs_history() if (number(item.get("ended_at")) or 0) >= cutoff]
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w") as handle:
        for item in kept + fresh:
            handle.write(json.dumps(item, sort_keys=True) + "\n")
    os.replace(tmp, path)
    return len(fresh)


def job_groups(now, days):
    cutoff = now - days * 86400
    groups = {}
    for item in read_jobs_history():
        ended = number(item.get("ended_at")) or 0
        if ended < cutoff or ended > now + 300:
            continue
        machine = str(item.get("machine") or "?")
        group = groups.setdefault(machine, {"jobs": 0, "ok": 0, "failed": 0, "stopped": 0, "dead": 0,
                                            "items": 0, "item_failures": 0, "last": None})
        group["jobs"] += 1
        try:
            import jobs
            kind = jobs.kind(str(item.get("status") or ""))
        except Exception:
            kind = "ok"
        if kind in group:
            group[kind] += 1
        group["items"] += int(number(item.get("done")) or 0)
        group["item_failures"] += int(number(item.get("failed")) or 0)
        if group["last"] is None or ended >= (number(group["last"].get("ended_at")) or 0):
            group["last"] = item
    return groups


def job_lines(now, days):
    lines = []
    groups = job_groups(now, days)
    for machine in sorted(groups):
        group = groups[machine]
        bits = ["%d job%s" % (group["jobs"], "" if group["jobs"] == 1 else "s")]
        for key in ("ok", "failed", "stopped", "dead"):
            if group[key]:
                bits.append("%d %s" % (group[key], key))
        if group["items"]:
            bits.append("%d items" % group["items"])
        if group["item_failures"]:
            bits.append("%d item failures" % group["item_failures"])
        last = group["last"]
        if last:
            bits.append("last %s %s %s" % (last.get("name"), last.get("status"),
                                           "%s %s" % (day_label(local_day(last["ended_at"])), timefmt.clock(last["ended_at"]))))
        lines.append("%-*s  %s" % (max(len(name) for name in groups), machine, " · ".join(bits)))
    return lines


# Output

def plan_lines(now, days):
    lines = []
    summaries = [summary for summary in (plan_summary(key, now, days) for key in plans()) if summary]
    width = max([4] + [len(item["plan"]) for item in summaries])
    for item in summaries:
        bits = ["peak %s %s" % (pct_text(item["peak"]), day_label(item["peak_day"]))]
        if item["now"] is not None:
            bits.append("last %s" % pct_text(item["now"]))
        lines.append("%-*s  %s  %s" % (width, item["plan"], item["spark"], " · ".join(bits)))
    return lines


def render_history(now=None, days=KEEP_DAYS):
    now = now_epoch() if now is None else now
    out = ["limitline history  last %d days, one mark per day (daily peak, . = no sample)" % days, ""]
    lines = plan_lines(now, days)
    out.append("plans")
    if lines:
        out.extend("  " + line for line in lines)
    else:
        out.append("  no samples yet; limitline refresh and limitline status record them")
    out.append("")
    out.append("jobs by machine")
    lines = job_lines(now, days)
    if lines:
        out.extend("  " + line for line in lines)
    else:
        out.append("  no finished jobs yet")
    return "\n".join(out) + "\n"


def render_week(now=None, markdown=False):
    now = now_epoch() if now is None else now
    days = 7
    summaries = [summary for summary in (plan_summary(key, now, days) for key in plans()) if summary]
    jobs_text = job_lines(now, days)
    first = local_day(now) - timedelta(days=days - 1)
    span = "%s to %s" % (day_label(first), day_label(local_day(now)))
    if markdown:
        out = ["# limitline weekly report", "", span, "", "## Plans", ""]
        if summaries:
            out.append("| Plan | Days | Peak | Average daily peak | Days over 80% | Resets seen |")
            out.append("| --- | --- | --- | --- | --- | --- |")
            for item in summaries:
                out.append("| %s `%s` | %d | %s on %s | %s | %d | %d |" % (
                    item["plan"], item["spark"], item["days"], pct_text(item["peak"]), day_label(item["peak_day"]),
                    pct_text(item["avg"]), item["over80"], item["resets"]))
        else:
            out.append("No samples this week.")
        out.extend(["", "## Jobs by machine", ""])
        if jobs_text:
            out.extend("- " + line for line in jobs_text)
        else:
            out.append("No finished jobs this week.")
        return "\n".join(out) + "\n"
    out = ["limitline weekly report  " + span, "", "plans"]
    if summaries:
        width = max(len(item["plan"]) for item in summaries)
        for item in summaries:
            out.append("  %-*s  %s  peak %s %s · avg %s · %d day%s over 80%% · %d reset%s seen" % (
                width, item["plan"], item["spark"], pct_text(item["peak"]), day_label(item["peak_day"]),
                pct_text(item["avg"]), item["over80"], "" if item["over80"] == 1 else "s",
                item["resets"], "" if item["resets"] == 1 else "s"))
    else:
        out.append("  no samples this week")
    out.append("")
    out.append("jobs by machine")
    if jobs_text:
        out.extend("  " + line for line in jobs_text)
    else:
        out.append("  no finished jobs this week")
    return "\n".join(out) + "\n"


def main(argv):
    days = KEEP_DAYS
    if "--days" in argv:
        try:
            days = max(1, min(KEEP_DAYS, int(argv[argv.index("--days") + 1])))
        except (IndexError, ValueError):
            print("usage: limitline history [--days N]", file=sys.stderr)
            return 2
    sys.stdout.write(render_history(days=days))
    return 0
