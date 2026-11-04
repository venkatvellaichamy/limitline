#!/usr/bin/env python3
"""Drive the interactive watch in a pseudo-terminal: arrow down, then q."""
import os, pty, select, sys, time
binary = sys.argv[1]
pid, fd = pty.fork()
if pid == 0:
    os.execv(binary, [binary, "watch"])
out = b""
def drain(t):
    global out
    end = time.time() + t
    while time.time() < end:
        r, _, _ = select.select([fd], [], [], 0.1)
        if r:
            try:
                out += os.read(fd, 65536)
            except OSError:
                return
drain(3)
os.write(fd, b"\x1b[B")
drain(1.5)
os.write(fd, b"q")
drain(1.5)
done, status = os.waitpid(pid, os.WNOHANG)
text = out.decode("utf-8", "replace")
print("exited" if done else "running", "selected-second" if "› run-d" in text else "no-move", "cursor-restored" if "\x1b[?25h" in text else "cursor-hidden")
if not done:
    os.kill(pid, 9)
