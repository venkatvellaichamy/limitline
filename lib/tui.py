#!/usr/bin/env python3
"""Interactive `limitline watch`: look at Pharos runs and reported jobs. Read-only.

Keys:  up/down or j/k select   l open the log   q quit

limitline only shows. To act on a run or a job, use Pharos (the Console, or
`pharos resume|stop <id>`, `pharos pause`); a key that would act says so instead
of running anything. Rows come from Pharos's summary.json.

For tests, `LIMITLINE_WATCH_KEYS="down l q"` replays keys without a terminal and
prints each message, and `LIMITLINE_PAGER=cat` prints logs.
"""
import os, shlex, shutil, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fleet
import jobs

REFRESH = 5
HELP = "↑/↓ select · l log · q quit (read-only: act on runs in Pharos)"
ACT_KEYS = ("r", "s", "p", "P", "U")


def items(now=None):
    """Selectable rows: recent Pharos runs, then reported jobs, as Pharos listed them."""
    found = []
    try:
        summary = fleet.read_summary()
        for row in fleet.recent(summary):
            if row.get("id"):
                found.append({"kind": "run", "id": str(row["id"]), "text": fleet.format_run(row),
                              "status": str(row.get("status") or ""), "log": row.get("log") or ""})
        for job in jobs.load(summary):
            found.append({"kind": "job", "id": job["name"], "text": "job  " + str(job.get("text") or job["name"]),
                          "status": job.get("status") or "", "log": ""})
    except Exception:
        pass
    return found


def pager_cmd():
    raw = os.environ.get("LIMITLINE_PAGER") or os.environ.get("PAGER") or ""
    if raw:
        return shlex.split(raw)
    if shutil.which("less"):
        return ["less", "-R", "+G"]
    return ["tail", "-n", "200"]


def show_logs(item, out=None):
    """Hand the terminal to a pager on the run's log file; returns a status-bar message."""
    log = item.get("log")
    if not log or not os.path.isfile(log):
        return "%s: no log file here" % item["id"]
    sys.stdout.flush()
    try:
        subprocess.run(pager_cmd() + [log], stdout=out)
    except OSError as exc:
        return "pager failed (%s)" % exc.__class__.__name__
    return "logs %s" % item["id"]


def act(item, key, out=None):
    if key == "l":
        return "nothing selected" if item is None else show_logs(item, out)
    if key in ACT_KEYS:
        target = ("%s " % item["id"]) if item and item["kind"] == "run" else ""
        return "read-only: use Pharos (pharos resume|stop %s/ pharos pause, or the Console)" % target
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
    elif key in ACT_KEYS or key == "l":
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
