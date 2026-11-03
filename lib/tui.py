#!/usr/bin/env python3
"""Interactive `limitline watch`: pick a Pharos run or a job and act on it.

Keys:  up/down or j/k select   r resume   s stop (asks y/n)   l logs
       p pause (jobs; Pharos runs have no per-run pause)
       P pause Pharos admissions   U unpause Pharos admissions   q quit

Pharos actions shell out to `pharos resume|stop|logs <id>` and `pharos
pause|unpause` (`LIMITLINE_PHAROS` names another binary). Pharos has no
per-run pause: `pharos pause` stops new runs from starting, so it is `P`.

Job actions only touch a job on this machine whose pid is still the reported
process (same pid, run, and process start time): `p` sends
SIGSTOP, `r` SIGCONT, `s` SIGTERM, and the job file's status follows. `l`
opens the job's log in `$PAGER` (default `less +G`).

The status line never does any of this; it stays display-only.

For tests, `LIMITLINE_WATCH_KEYS="down s y q"` replays keys without a
terminal and prints each message, and `LIMITLINE_PAGER=cat` prints logs.
"""
import os, shlex, shutil, signal, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fleet
import jobs

REFRESH = 5
HELP = "↑/↓ select · r resume · s stop · l logs · p pause job · P/U pause/unpause Pharos · q quit"
LIVE_RUN = ("starting", "running", "paused-quota", "stalled")


def pharos_bin():
    """LIMITLINE_PHAROS, else `pharos = "/path/to/pharos"` in the config, else PATH."""
    try:
        from config import setting
        override = setting("pharos", "LIMITLINE_PHAROS", "")
    except Exception:
        override = os.environ.get("LIMITLINE_PHAROS", "")
    if override:
        return os.path.expanduser(override)
    return shutil.which("pharos") or ""


def items(now=None):
    """Selectable rows: recent Pharos runs that have an id, then jobs."""
    found = []
    try:
        now = fleet.now_epoch() if now is None else now
        recent, _older = fleet.split_recent(fleet.load_states(fleet.pharos_runs_root()), now=now)
        for state in recent:
            ident = state.get("id")
            if not ident:
                continue
            found.append({"kind": "run", "id": str(ident), "text": fleet.format_run(state, now),
                          "status": str(state.get("status") or ""), "log": fleet.log_path(state)})
    except Exception:
        pass
    try:
        for job in jobs.load():
            found.append({"kind": "job", "id": job["name"], "text": "job  " + jobs.short(job),
                          "status": job.get("shown_status") or "", "job": job})
    except Exception:
        pass
    return found


def run_cmd(args, capture=True):
    try:
        proc = subprocess.run(args, capture_output=capture, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, exc.__class__.__name__
    out = ""
    if capture:
        out = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
        out = out[-1] if out else ""
    return proc.returncode == 0, out


def pharos(args):
    binary = pharos_bin()
    if not binary:
        return "pharos not found on PATH"
    ok, out = run_cmd([binary] + args)
    label = "pharos " + " ".join(args)
    if ok:
        return label + (": " + out if out else ": done")
    return label + " failed" + (": " + out if out else "")


def local_pid(job):
    """The job's pid when it runs on this machine and is still the process that
    was reported (same recorded start time), else None."""
    pid = jobs.whole(job.get("pid"))
    machine = jobs.clean(job.get("machine"), 40)
    if machine not in (None, jobs.host_name()):
        return None
    if jobs.same_process(job) is not True:
        return None
    return pid


def job_signal(job, sig, status, verb):
    """Signal a job's process only if the job file still names the same pid and
    run (started_at) that watch showed, and that pid is still the same process.
    The status is written back only if the file still names that pid and run."""
    name = job["name"]
    current = jobs.read_job(jobs.path_for(name))
    if current is None:
        return "%s: the job file is gone; not %s" % (name, verb)
    if current.get("pid") != job.get("pid") or current.get("started_at") != job.get("started_at") \
            or current.get("pid_start") != job.get("pid_start"):
        return "%s: the job file changed; not %s" % (name, verb)
    pid = local_pid(current)
    if pid is None:
        return "%s: no live pid on this machine" % name
    try:
        os.kill(pid, sig)
    except OSError as exc:
        return "%s: %s failed (%s)" % (name, verb, exc.__class__.__name__)
    message = "%s: %s (pid %d)" % (name, verb, pid)
    try:
        expect = {"pid": current.get("pid"), "started_at": current.get("started_at")}
        if jobs.update(name, {"status": status}, expect=expect) is None:
            message += "; the job restarted, its file was left as is"
        jobs.write_line()
    except Exception:
        pass
    return message


def pager_cmd():
    raw = os.environ.get("LIMITLINE_PAGER") or os.environ.get("PAGER") or ""
    if raw:
        return shlex.split(raw)
    if shutil.which("less"):
        return ["less", "-R", "+G"]
    return ["tail", "-n", "200"]


def show_logs(item, out=None):
    """Hand the terminal to a pager; returns a message for the status bar."""
    sys.stdout.flush()
    pager = pager_cmd()
    if item["kind"] == "run":
        binary = pharos_bin()
        if not binary:
            if item.get("log"):
                subprocess.run(pager + [item["log"]], stdout=out)
                return "logs %s (stdout.log)" % item["id"]
            return "pharos not found on PATH"
        try:
            first = subprocess.Popen([binary, "logs", item["id"]], stdout=subprocess.PIPE)
            subprocess.run(pager, stdin=first.stdout, stdout=out)
            first.stdout.close()
            first.wait(timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return "pharos logs failed (%s)" % exc.__class__.__name__
        return "pharos logs %s" % item["id"]
    log = item["job"].get("log")
    if not isinstance(log, str) or not os.path.isfile(log):
        return "%s: no log file" % item["id"]
    try:
        subprocess.run(pager + [log], stdout=out)
    except OSError as exc:
        return "pager failed (%s)" % exc.__class__.__name__
    return "logs %s" % item["id"]


def act(item, key, out=None):
    """Run one action key on one item. Returns the message to show."""
    if key == "P":
        return pharos(["pause"])
    if key == "U":
        return pharos(["unpause"])
    if item is None:
        return "nothing selected"
    if key == "l":
        return show_logs(item, out)
    if item["kind"] == "run":
        if key == "r":
            return pharos(["resume", item["id"]])
        if key == "s":
            return pharos(["stop", item["id"]])
        if key == "p":
            return "Pharos has no per-run pause; P pauses new runs, s stops this one"
        return ""
    job = item["job"]
    if key == "p":
        return job_signal(job, signal.SIGSTOP, "paused", "paused")
    if key == "r":
        return job_signal(job, signal.SIGCONT, "running", "resumed")
    if key == "s":
        return job_signal(job, signal.SIGTERM, "stopped", "stopped")
    return ""


class State(object):
    def __init__(self):
        self.index = 0
        self.confirm = None
        self.message = ""

    def clamp(self, count):
        if count <= 0:
            self.index = 0
        elif self.index >= count:
            self.index = count - 1
        elif self.index < 0:
            self.index = 0


def handle(state, key, rows, out=None):
    """Apply one key. Returns False when the loop should end."""
    state.clamp(len(rows))
    current = rows[state.index] if rows else None
    if state.confirm is not None:
        target, action = state.confirm
        state.confirm = None
        if key in ("y", "Y"):
            state.message = act(target, action, out)
        else:
            state.message = "cancelled"
        return True
    if key in ("q", "Q", "\x03"):
        return False
    if key in ("down", "j"):
        state.index += 1
    elif key in ("up", "k"):
        state.index -= 1
    elif key == "s":
        if current is None:
            state.message = "nothing selected"
        else:
            state.confirm = (current, "s")
            state.message = "stop %s %s? y/n" % (current["kind"], current["id"])
    elif key in ("P", "U", "p", "r", "l"):
        state.message = act(current, key, out)
    elif key in ("?", "h"):
        state.message = HELP
    state.clamp(len(rows))
    return True


def screen(header, rows, state):
    lines = [header.rstrip("\n"), "", "Runs and jobs"]
    if not rows:
        lines.append("  (no recent Pharos runs or jobs)")
    for i, row in enumerate(rows):
        lines.append(("› " if i == state.index else "  ") + row["text"])
    lines.append("")
    lines.append(state.message or HELP)
    return "\n".join(lines) + "\n"


def read_key(fd, timeout):
    import select
    ready, _, _ = select.select([fd], [], [], timeout)
    if not ready:
        return None
    ch = os.read(fd, 1).decode("utf-8", "replace")
    if ch != "\x1b":
        return ch
    ready, _, _ = select.select([fd], [], [], 0.05)
    if not ready:
        return "esc"
    rest = os.read(fd, 2).decode("utf-8", "replace")
    return {"[A": "up", "[B": "down"}.get(rest, "esc")


def scripted(header_fn, keys):
    """Replay keys without a terminal: print the screen once, then each message."""
    state = State()
    sys.stdout.write(screen(header_fn(), items(), state))
    sys.stdout.flush()
    for key in keys:
        rows = items()
        alive = handle(state, key, rows, out=sys.stdout)
        if state.message:
            sys.stdout.write("> %s\n" % state.message)
            state.message = ""
        sys.stdout.flush()
        if not alive:
            break
    rows = items()
    state.clamp(len(rows))
    if rows:
        sys.stdout.write("selected: %s\n" % rows[state.index]["text"])
    sys.stdout.flush()


def interactive(header_fn):
    import termios, tty
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    state = State()
    try:
        tty.setcbreak(fd)
        sys.stdout.write("\033[?25l")
        while True:
            rows = items()
            state.clamp(len(rows))
            sys.stdout.write("\033[H\033[2J" + screen(header_fn(), rows, state))
            sys.stdout.flush()
            key = read_key(fd, REFRESH)
            if key is None:
                continue
            if key == "l" or (state.confirm and key in ("y", "Y")):
                # A pager or a pharos command gets a normal terminal.
                termios.tcsetattr(fd, termios.TCSADRAIN, saved)
                sys.stdout.write("\033[?25h\033[H\033[2J")
                sys.stdout.flush()
                try:
                    alive = handle(state, key, rows)
                finally:
                    tty.setcbreak(fd)
                    sys.stdout.write("\033[?25l")
            else:
                alive = handle(state, key, rows)
            if not alive:
                break
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()


def main(header_fn):
    keys = os.environ.get("LIMITLINE_WATCH_KEYS")
    if keys is not None:
        scripted(header_fn, keys.split())
        return
    interactive(header_fn)
