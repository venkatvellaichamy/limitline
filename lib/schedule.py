#!/usr/bin/env python3
"""`limitline schedule install|uninstall|status`: a launchd agent,
com.limitline.refresh, that runs `limitline refresh` every 15 minutes.

That is cheap: each refresh reads local files, and the xAI plan fetch inside it
keeps its own `xai_ttl` (30 minutes by default) and lock. The agent runs the
same launcher as `install-refresher`, so it follows `claude plugin update` to the
newest installed copy. Tests point LIMITLINE_LAUNCH_AGENTS and
LIMITLINE_LAUNCHCTL at a temp folder and a fake launchctl.
"""
import os, plistlib, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refresher

LABEL = "com.limitline.refresh"
INTERVAL = 15 * 60


def plist_path():
    return os.path.join(refresher.agents_dir(), LABEL + ".plist")


def launcher_path():
    return os.path.join(refresher.data_dir(), "schedule-launcher.py")


def plist_dict():
    data = refresher.plist_dict()
    data["Label"] = LABEL
    data["ProgramArguments"] = [refresher.python_bin(), launcher_path()]
    data["StartInterval"] = INTERVAL
    return data


def install():
    if not refresher.supported():
        print("schedule needs macOS launchd. Elsewhere, run this from cron every 15 minutes:")
        print("  */15 * * * * nice -n 10 %s refresh" % os.path.join(refresher.root_dir(), "bin", "limitline"))
        return 1
    os.makedirs(refresher.data_dir(), exist_ok=True)
    with open(launcher_path(), "w") as handle:
        handle.write(refresher.LAUNCHER % {"root": refresher.root_dir()})
    os.chmod(launcher_path(), 0o755)
    os.makedirs(refresher.agents_dir(), exist_ok=True)
    path = plist_path()
    refresher.run(["bootout", refresher.domain(), path])
    with open(path, "wb") as handle:
        plistlib.dump(plist_dict(), handle)
    proc = refresher.run(["bootstrap", refresher.domain(), path])
    if proc is None or proc.returncode != 0:
        detail = "" if proc is None else (proc.stderr or proc.stdout or "").strip()
        print("wrote %s, but launchctl bootstrap failed%s" % (path, (": " + detail) if detail else ""))
        return 1
    print("installed %s: limitline refresh every %d minutes" % (LABEL, INTERVAL // 60))
    print("plist: %s" % path)
    print("remove with: limitline schedule uninstall")
    return 0


def uninstall():
    path = plist_path()
    if refresher.supported():
        refresher.run(["bootout", refresher.domain(), path])
    removed = False
    for item in (path, launcher_path()):
        if os.path.isfile(item):
            os.remove(item)
            removed = True
    print("removed %s" % LABEL if removed else "%s was not installed" % LABEL)
    return 0


def status():
    if not os.path.isfile(plist_path()):
        return "missing", "not installed (limitline schedule install)"
    if not os.path.isfile(launcher_path()):
        return "broken", "plist exists but the launcher is gone; run limitline schedule install"
    detail = "launchd every %d minutes" % (INTERVAL // 60)
    if refresher.supported():
        proc = refresher.run(["print", "%s/%s" % (refresher.domain(), LABEL)])
        if proc is not None:
            if proc.returncode != 0:
                return "broken", detail + ", not loaded; run limitline schedule install"
            detail += ", loaded"
    return "installed", detail


def main(argv):
    cmd = argv[0] if argv else "status"
    if cmd == "install":
        return install()
    if cmd == "uninstall":
        return uninstall()
    if cmd == "status":
        state, detail = status()
        print("%s: %s" % (state, detail))
        return 0
    print("usage: limitline schedule install|uninstall|status", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
