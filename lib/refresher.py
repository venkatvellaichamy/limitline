#!/usr/bin/env python3
"""Optional launchd agent that runs `limitline refresh` every 60 seconds.

The status line only reads caches. Without this agent the caches are refreshed
when the status line notices they are stale, so a quiet session shows nothing.
"""
import glob, os, plistlib, shutil, subprocess, sys

LABEL = "dev.limitline.refresh"
INTERVAL = 60
LAUNCH_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# The launcher keeps working after `claude plugin update` moves limitline to a new
# versioned folder: a plugin install follows the newest cached version, and a
# checkout keeps using the folder it was installed from.
LAUNCHER = '''#!/usr/bin/env python3
"""limitline refresher launcher, written by `limitline install-refresher`."""
import glob, os, runpy, sys

ROOT = %(root)r


def version_key(path):
    name = os.path.basename(os.path.dirname(os.path.dirname(path)))
    parts = []
    for piece in name.split("."):
        parts.append(int(piece) if piece.isdigit() else -1)
    return parts


def target():
    first = os.path.join(ROOT, "lib", "refresh.py")
    cache = os.path.join(os.path.expanduser("~"), ".claude", "plugins", "cache", "limitline", "limitline")
    found = sorted(glob.glob(os.path.join(cache, "*", "lib", "refresh.py")), key=version_key)
    # Installed from the plugin cache: follow plugin updates to the newest copy.
    if ROOT.startswith(cache + os.sep) and found:
        return found[-1]
    if os.path.isfile(first):
        return first
    return found[-1] if found else ""


path = target()
if path:
    sys.path.insert(0, os.path.dirname(path))
    sys.argv = [path]
    runpy.run_path(path, run_name="__main__")
'''


def root_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def agents_dir():
    override = os.environ.get("LIMITLINE_LAUNCH_AGENTS")
    if override:
        return override
    return os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents")


def plist_path():
    return os.path.join(agents_dir(), LABEL + ".plist")


def data_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "limitline")


def launcher_path():
    return os.path.join(data_dir(), "refresh-launcher.py")


def launchctl():
    return os.environ.get("LIMITLINE_LAUNCHCTL") or "/bin/launchctl"


def domain():
    return "gui/%d" % os.getuid()


def python_bin():
    found = shutil.which("python3")
    if found:
        return found
    return sys.executable or "/usr/bin/python3"


def plist_dict():
    return {
        "Label": LABEL,
        "ProgramArguments": [python_bin(), launcher_path()],
        "StartInterval": INTERVAL,
        "RunAtLoad": True,
        "ProcessType": "Background",
        "LowPriorityIO": True,
        "LowPriorityBackgroundIO": True,
        "Nice": 10,
        "EnvironmentVariables": {"PATH": LAUNCH_PATH},
        "StandardOutPath": "/dev/null",
        "StandardErrorPath": "/dev/null",
    }


def run(args):
    try:
        return subprocess.run([launchctl()] + args, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None


def supported():
    if os.environ.get("LIMITLINE_LAUNCHCTL"):
        return True
    return sys.platform == "darwin" and os.path.exists(launchctl())


def install():
    if not supported():
        print("install-refresher needs macOS launchd. Elsewhere, run this from cron every minute:")
        print("  * * * * * nice -n 10 %s refresh" % os.path.join(root_dir(), "bin", "limitline"))
        return 1
    os.makedirs(data_dir(), exist_ok=True)
    with open(launcher_path(), "w") as handle:
        handle.write(LAUNCHER % {"root": root_dir()})
    os.chmod(launcher_path(), 0o755)
    os.makedirs(agents_dir(), exist_ok=True)
    path = plist_path()
    run(["bootout", domain(), path])
    with open(path, "wb") as handle:
        plistlib.dump(plist_dict(), handle)
    proc = run(["bootstrap", domain(), path])
    if proc is None or proc.returncode != 0:
        detail = "" if proc is None else (proc.stderr or proc.stdout or "").strip()
        print("wrote %s, but launchctl bootstrap failed%s" % (path, (": " + detail) if detail else ""))
        return 1
    print("installed %s: limitline refresh every %ds at low priority" % (LABEL, INTERVAL))
    print("plist: %s" % path)
    print("remove with: limitline uninstall-refresher")
    return 0


def uninstall():
    path = plist_path()
    if supported():
        run(["bootout", domain(), path])
    removed = False
    for item in (path, launcher_path()):
        if os.path.isfile(item):
            os.remove(item)
            removed = True
    print("removed %s" % LABEL if removed else "%s was not installed" % LABEL)
    return 0


def status():
    """(state, detail) for doctor. state is installed, broken, or missing."""
    path = plist_path()
    if not os.path.isfile(path):
        return "missing", "not installed; caches refresh only when the status line finds them stale"
    if not os.path.isfile(launcher_path()):
        return "broken", "plist exists but the launcher is gone; run limitline install-refresher"
    try:
        text = open(launcher_path()).read()
    except OSError:
        text = ""
    root = ""
    for line in text.splitlines():
        if line.startswith("ROOT = "):
            root = line[len("ROOT = "):].strip().strip("'\"")
    target = os.path.join(root, "lib", "refresh.py") if root else ""
    fallback = glob.glob(os.path.join(os.path.expanduser("~"), ".claude", "plugins", "cache", "limitline", "limitline", "*", "lib", "refresh.py"))
    if target and not os.path.isfile(target) and not fallback:
        return "broken", "the limitline folder it points to is gone; run limitline install-refresher"
    loaded = ""
    if supported():
        proc = run(["print", "%s/%s" % (domain(), LABEL)])
        if proc is not None:
            loaded = "loaded" if proc.returncode == 0 else "not loaded"
    detail = "launchd every %ds" % INTERVAL
    if loaded:
        detail += ", " + loaded
    if loaded == "not loaded":
        return "broken", detail + "; run limitline install-refresher"
    return "installed", detail


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "install":
        return install()
    if cmd == "uninstall":
        return uninstall()
    state, detail = status()
    print("%s: %s" % (state, detail))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
