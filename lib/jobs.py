#!/usr/bin/env python3
"""Background jobs that are not Pharos runs: mining passes, backups, anything a
script wants to report. One JSON file per job in ~/.cache/limitline/jobs/:

    {"name": "mining", "machine": "mini", "pid": 4242, "started_at": <epoch>,
     "done": 62, "total": 1842, "failed": 0, "status": "running",
     "log": "/path/to/log", "updated_at": <epoch>}

Scripts report with `limitline job update <name> --done N --total N ...`.
A job on this machine whose pid is gone, and whose status is not finished, is
shown as "dead". Finished jobs stay visible for `fleet_window` (default 12h).
"""
import json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timefmt

FINISHED_OK = ("ok", "done", "finished", "complete", "completed", "success", "succeeded")
FINISHED_BAD = ("failed", "error", "errored")
FINISHED_STOP = ("stopped", "cancelled", "canceled", "killed")
FINISHED = FINISHED_OK + FINISHED_BAD + FINISHED_STOP
SEGMENT_LIMIT = 3
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def cache_dir():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache")
    return os.path.join(base, "limitline")


def jobs_dir():
    return os.environ.get("LIMITLINE_JOBS_DIR") or os.path.join(cache_dir(), "jobs")


def line_path():
    return os.environ.get("LIMITLINE_JOBS_LINE") or os.path.join(cache_dir(), "jobs.line")


def now_epoch():
    try:
        return int(os.environ.get("LIMITLINE_NOW") or time.time())
    except ValueError:
        return int(time.time())


def host_name():
    try:
        import sync
        return sync.host_name()
    except Exception:
        return "local"


def valid_name(name):
    return bool(NAME.match(name or "")) and ".." not in name


def whole(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    return int(value)


def clean(value, limit=40):
    if not isinstance(value, str):
        return None
    text = " ".join("".join(ch for ch in value if ch.isprintable()).split())
    return text[:limit] or None


def path_for(name):
    return os.path.join(jobs_dir(), name + ".json")


def read_job(path):
    try:
        data = json.load(open(path))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    name = clean(data.get("name"), 64)
    if not name:
        name = os.path.basename(path)[:-5]
    data["name"] = name
    return data


def write_job(data):
    folder = jobs_dir()
    os.makedirs(folder, exist_ok=True)
    path = path_for(data["name"])
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w") as handle:
        json.dump(data, handle, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def pid_alive(pid):
    if pid is None or pid <= 0:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def status_of(job, here=None):
    """The status to show. A finished status is kept; a live-looking job whose
    pid is gone on this machine is "dead"."""
    raw = (clean(job.get("status"), 20) or "running").lower()
    if raw in FINISHED:
        return raw
    here = host_name() if here is None else here
    machine = clean(job.get("machine"), 40)
    if machine in (None, here):
        if pid_alive(whole(job.get("pid"))) is False:
            return "dead"
    return raw


def kind(status):
    if status in FINISHED_OK:
        return "ok"
    if status in FINISHED_BAD:
        return "failed"
    if status in FINISHED_STOP:
        return "stopped"
    if status == "dead":
        return "dead"
    return "active"


def update(name, fields, now=None):
    if not valid_name(name):
        raise ValueError("job names use letters, digits, dot, dash, and underscore")
    now = now_epoch() if now is None else now
    job = read_job(path_for(name)) or {}
    fresh = not job
    status = fields.get("status")
    if status is not None:
        status = clean(status, 20)
        if status:
            status = status.lower()
    restarted = (not fresh and status and kind(status) == "active"
                 and kind((clean(job.get("status"), 20) or "running").lower()) != "active")
    job["name"] = name
    if fresh or restarted:
        job["started_at"] = now
        if restarted:
            for key in ("done", "failed"):
                job.pop(key, None)
    for key in ("done", "total", "failed", "pid"):
        if fields.get(key) is not None:
            job[key] = int(fields[key])
    if status:
        job["status"] = status
    job.setdefault("status", "running")
    if fields.get("log"):
        job["log"] = os.path.abspath(os.path.expanduser(fields["log"]))
    machine = clean(fields.get("machine"), 40) if fields.get("machine") else None
    job["machine"] = machine or clean(job.get("machine"), 40) or host_name()
    job["updated_at"] = now
    write_job(job)
    return job


def remove(name):
    if not valid_name(name):
        return False
    try:
        os.remove(path_for(name))
        return True
    except OSError:
        return False


def window_seconds():
    try:
        import fleet
        return fleet.window_seconds()
    except Exception:
        return 12 * 3600


def load(now=None, window=None, every=False):
    """Jobs to show, active first, each with a computed `shown_status`."""
    now = now_epoch() if now is None else now
    window = window_seconds() if window is None else window
    folder = jobs_dir()
    found = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return found
    here = host_name()
    for name in names:
        if not name.endswith(".json"):
            continue
        job = read_job(os.path.join(folder, name))
        if job is None:
            continue
        job["shown_status"] = status_of(job, here)
        updated = whole(job.get("updated_at")) or whole(job.get("started_at")) or 0
        job["updated_at"] = updated
        if not every and kind(job["shown_status"]) != "active" and window and now - updated > window:
            continue
        found.append(job)
    found.sort(key=lambda job: (0 if kind(job["shown_status"]) in ("active", "dead") else 1, -job["updated_at"], job["name"]))
    return found


def progress(job):
    done = whole(job.get("done"))
    total = whole(job.get("total"))
    if done is not None and total:
        return "%d/%d" % (done, total)
    if done is not None:
        return "%d" % done
    return ""


def short(job):
    """`mining 62/1842`, `mining 62/1842 ✗3`, `mining dead 62/1842`, `backup ok 08:36`."""
    status = job.get("shown_status") or job.get("status") or "running"
    group = kind(status)
    count = progress(job)
    failed = whole(job.get("failed")) or 0
    bits = [job["name"]]
    if group == "active":
        if status != "running":
            bits.append(status)
        if count:
            bits.append(count)
        elif status == "running":
            bits.append("running")
        if failed:
            bits.append("✗%d" % failed)
        return " ".join(bits)
    if group == "dead":
        bits.append("dead")
        if count:
            bits.append(count)
        return " ".join(bits)
    bits.append("ok" if group == "ok" else status)
    if failed and group == "ok":
        bits.append("✗%d" % failed)
    stamp = timefmt.clock(job.get("updated_at"))
    if stamp:
        bits.append(stamp)
    return " ".join(bits)


def summary(found, limit=SEGMENT_LIMIT):
    if not found:
        return ""
    shown = [short(job) for job in found[:limit]]
    if len(found) > limit:
        shown.append("+%d" % (len(found) - limit))
    return " · ".join(shown)


def segment(found=None):
    found = load() if found is None else found
    text = summary(found)
    return ("jobs " + text) if text else ""


def detail_lines(found, now=None):
    now = now_epoch() if now is None else now
    lines = []
    for job in found:
        bits = [job["name"], clean(job.get("machine"), 40) or "?", job.get("shown_status") or "running"]
        count = progress(job)
        if count:
            bits.append(count)
        failed = whole(job.get("failed"))
        if failed:
            bits.append("%d failed" % failed)
        bits.append("updated %s ago" % timefmt.age(now - job["updated_at"]))
        log = job.get("log")
        if isinstance(log, str) and log:
            bits.append("log " + os.path.basename(log))
        lines.append("  ".join(bits))
    return lines


def write_line(found=None):
    try:
        import history
        history.record_jobs(load(every=True))
    except Exception:
        pass
    text = segment(found)
    path = line_path()
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w") as handle:
        if text:
            handle.write(text + "\n")
    os.replace(tmp, path)
    return text


USAGE = ("usage: limitline job update <name> [--done N] [--total N] [--failed N] "
         "[--status running|ok|failed|stopped] [--pid PID] [--log PATH] [--machine NAME]\n"
         "       limitline job list | limitline job rm <name>")


def parse_update(args):
    fields = {}
    ints = ("done", "total", "failed", "pid")
    texts = ("status", "log", "machine")
    i = 0
    while i < len(args):
        flag = args[i]
        if not flag.startswith("--"):
            raise ValueError("unexpected %s" % flag)
        key = flag[2:]
        if "=" in key:
            key, value = key.split("=", 1)
        else:
            if i + 1 >= len(args):
                raise ValueError("%s needs a value" % flag)
            value = args[i + 1]
            i += 1
        i += 1
        if key in ints:
            try:
                number = int(value)
            except ValueError:
                raise ValueError("--%s needs a whole number" % key)
            if number < 0:
                raise ValueError("--%s cannot be negative" % key)
            fields[key] = number
        elif key in texts:
            fields[key] = value
        else:
            raise ValueError("unknown option --%s" % key)
    return fields


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    cmd = argv[0]
    if cmd == "update":
        if len(argv) < 2:
            print(USAGE, file=sys.stderr)
            return 2
        try:
            fields = parse_update(argv[2:])
            job = update(argv[1], fields)
        except ValueError as exc:
            print("limitline job: %s" % exc, file=sys.stderr)
            return 2
        try:
            write_line()
        except OSError:
            pass
        job["shown_status"] = status_of(job)
        print(short(job))
        return 0
    if cmd in ("list", "ls"):
        found = load(every=True)
        if not found:
            print("no jobs")
            return 0
        for line in detail_lines(found):
            print(line)
        return 0
    if cmd in ("rm", "remove"):
        if len(argv) < 2 or not remove(argv[1]):
            print("limitline job: no such job", file=sys.stderr)
            return 1
        try:
            write_line()
        except OSError:
            pass
        return 0
    print(USAGE, file=sys.stderr)
    return 2
