#!/usr/bin/env python3
"""Ask the Grok CLI to fetch the xAI plan, so its log gains a fresh reading.

Grok logs `billing: fetched credits config` to ~/.grok/logs/unified.jsonl when
its interactive `/usage show` command runs. Headless `grok -p "/usage show"`
sends the text to the model instead, so this opens grok in a pseudo-terminal,
types the command, waits for the new log line, and exits. `/usage show` is a
local command: it uses no model tokens and calls only xAI's billing API, with
the CLI's own login. limitline itself opens no socket and never reads
~/.grok/auth.json or any token.

This runs only from `limitline refresh` (and the launchd agents that run it),
never inside the status-line render. At most one fetch runs at a time (a flock),
and at most one every `xai_ttl` minutes (default 30).
"""
import errno, fcntl, json, os, select, signal, struct, sys, termios, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xaiplan
from config import setting

DEFAULT_TTL_MIN = 30
MARKER = xaiplan.LOG_MARKER


def grok_bin():
    """LIMITLINE_GROK_BIN, else ~/.grok/bin/grok. PATH is not searched, so a
    test home or a Mac without Grok never starts some other grok."""
    override = os.environ.get("LIMITLINE_GROK_BIN")
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), ".grok", "bin", "grok")


def ttl_seconds():
    raw = setting("xai_ttl", "LIMITLINE_XAI_TTL", str(DEFAULT_TTL_MIN))
    try:
        minutes = float(raw)
    except (TypeError, ValueError):
        minutes = DEFAULT_TTL_MIN
    return max(0, int(minutes * 60))


def env_seconds(name, default):
    try:
        return max(0.0, float(os.environ.get(name) or default))
    except ValueError:
        return float(default)


def state_path():
    return os.path.join(xaiplan.cache_dir(), "xai-fetch.json")


def lock_path():
    return os.path.join(xaiplan.cache_dir(), "xai-fetch.lock")


def work_dir():
    """An empty folder of limitline's own, so grok never starts inside a project."""
    path = os.path.join(xaiplan.cache_dir(), "grok-cwd")
    os.makedirs(path, exist_ok=True)
    return path


def read_state():
    return xaiplan.fetch_state()


def write_state(data):
    path = state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as handle:
        json.dump(data, handle, sort_keys=True)
        handle.write("\n")
    os.replace(tmp, path)


def log_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def new_reading(path, start):
    """True once a marker line that parses appears past byte `start`. A log that
    shrank (rotated) is read from the beginning."""
    size = log_size(path)
    if size < start:
        start = 0
    if size <= start:
        return False
    try:
        with open(path, "rb") as handle:
            handle.seek(start)
            data = handle.read()
    except OSError:
        return False
    for raw in data.split(b"\n"):
        if MARKER.encode() in raw and xaiplan.parse_log_line(raw) is not None:
            return True
    return False


def set_winsize(fd, rows=40, cols=120):
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    except OSError:
        pass


def drain(fd, seconds, until=None):
    """Read and discard output for up to `seconds`; stop early when `until()`
    is true. Returns False once the child closed the terminal."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if until is not None and until():
            return True
        ready, _, _ = select.select([fd], [], [], 0.2)
        if ready:
            try:
                if not os.read(fd, 65536):
                    return False
            except OSError:
                return False
    return True


def settle(fd, quiet, limit):
    """Wait for the start-up screen: some output, then `quiet` seconds of none,
    or `limit` seconds in all."""
    end = time.monotonic() + limit
    last = None
    while time.monotonic() < end:
        ready, _, _ = select.select([fd], [], [], 0.2)
        if ready:
            try:
                if not os.read(fd, 65536):
                    return False
            except OSError:
                return False
            last = time.monotonic()
        elif last is not None and time.monotonic() - last >= quiet:
            return True
    return True


def stop_child(pid, fd):
    """Always end grok and everything it started: it leads its own session."""
    for keys in (b"\x03", b"\x03", b"\x04"):
        try:
            os.write(fd, keys)
        except OSError:
            break
        drain(fd, 0.3)
    for sig, grace in ((signal.SIGTERM, 2.0), (signal.SIGKILL, 2.0)):
        try:
            os.killpg(pid, sig)
        except OSError:
            try:
                os.kill(pid, sig)
            except OSError:
                pass
        end = time.monotonic() + grace
        while time.monotonic() < end:
            try:
                done, _ = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                done = pid
            if done:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except OSError:
                    pass
                return
            time.sleep(0.05)


def run_pty(binary, log, timeout):
    """Start grok in a pty, type `/usage show`, and wait for a new log reading.
    Returns None on success, or a short reason."""
    import pty
    start = log_size(log)
    deadline = time.monotonic() + timeout
    cwd = work_dir()
    pid, fd = pty.fork()
    if pid == 0:
        try:
            os.chdir(cwd)
            env = dict(os.environ)
            env["TERM"] = env.get("TERM") or "xterm-256color"
            if env["TERM"] == "dumb":
                env["TERM"] = "xterm-256color"
            env["COLUMNS"], env["LINES"] = "120", "40"
            os.execve(binary, [binary], env)
        except BaseException:
            os._exit(127)
    try:
        set_winsize(fd)
        boot = min(env_seconds("LIMITLINE_XAI_BOOT", 12), max(0.0, deadline - time.monotonic()))
        quiet = env_seconds("LIMITLINE_XAI_QUIET", 2)
        if not settle(fd, quiet, boot):
            return "grok exited at start-up"
        os.write(fd, b"/usage show")
        drain(fd, env_seconds("LIMITLINE_XAI_TYPE_PAUSE", 1))
        os.write(fd, b"\r")
        remaining = max(0.0, deadline - time.monotonic())
        found = lambda: new_reading(log, start)
        drain(fd, remaining, until=found)
        if found():
            return None
        return "no new reading in the grok log within %ds" % int(timeout)
    except OSError as exc:
        return "pty error: %s" % (exc.strerror or exc)
    finally:
        stop_child(pid, fd)
        try:
            os.close(fd)
        except OSError:
            pass


def due(now=None):
    """(True, "") when a fetch should run, else (False, why not)."""
    now = xaiplan.now_epoch() if now is None else now
    ttl = ttl_seconds()
    state = read_state()
    last = state.get("last_attempt") if isinstance(state.get("last_attempt"), (int, float)) else 0
    live = xaiplan.read_log()
    newest = live.get("observed_at") if live else 0
    since = now - max(last or 0, newest or 0)
    if since < ttl:
        return False, "fetched %ds ago, xai_ttl %ds" % (max(0, since), ttl)
    return True, ""


def fetch(force=False, now=None):
    """Run one fetch if due. Returns a short status string, never raises."""
    if os.environ.get("LIMITLINE_XAI_FETCH", "1") == "0":
        return "skipped: LIMITLINE_XAI_FETCH=0"
    now = xaiplan.now_epoch() if now is None else now
    if not force:
        ok, why = due(now)
        if not ok:
            return "skipped: " + why
    os.makedirs(xaiplan.cache_dir(), exist_ok=True)
    try:
        lock = open(lock_path(), "a")
    except OSError as exc:
        return "skipped: no lock file (%s)" % exc
    with lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
                return "skipped: another fetch is running"
            return "skipped: lock failed"
        state = read_state()
        binary = grok_bin()
        if not (os.path.isfile(binary) and os.access(binary, os.X_OK)):
            error = "grok not found at %s" % binary
        else:
            error = run_pty(binary, xaiplan.log_path(), env_seconds("LIMITLINE_XAI_TIMEOUT", 45))
        state["last_attempt"] = now
        if error is None:
            state["last_ok"] = now
            state.pop("error", None)
        else:
            state["error"] = error
        try:
            write_state(state)
        except OSError:
            pass
        return "fetched" if error is None else "failed: " + error


def main(argv):
    print(fetch(force="--force" in argv))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
