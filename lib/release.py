#!/usr/bin/env python3
"""limitline version | update | channel: which build runs here, and how to move it.

Channels are git branches of the marketplace repository, which Claude Code tracks when
the marketplace is added as `venkatvellaichamy/limitline#<branch>`:

    stable  the latest stable release (vX.Y.Z); what you should run day to day
    beta    the latest release of any kind, including vX.Y.Z-beta.N; for trying the next one
    dev     main, every merged pull request; for development

The release workflow (.github/workflows/release.yml) moves `beta` on every tag and
`stable` on stable tags only. These commands are the only ones in limitline that touch
the network, and only when you run them: the status line never does.
"""

import json
import os
import re
import shutil
import subprocess
import sys

REPO = "venkatvellaichamy/limitline"
MARKETPLACE = "limitline"
PLUGIN = "limitline@limitline"
CHANNELS = {"stable": "stable", "beta": "beta", "dev": "main"}
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(-(alpha|beta|rc)\.\d+)?$")


def root():
    return os.environ.get("LIMITLINE_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def version(base=None):
    try:
        with open(os.path.join(base or root(), "bin", "limitline"), encoding="utf-8") as handle:
            for line in handle:
                match = re.match(r"# Version: (\S+)", line)
                if match:
                    return match.group(1)
    except OSError:
        pass
    return "unknown"


def git(*args, cwd=None, timeout=20):
    try:
        proc = subprocess.run(["git", *args], cwd=cwd or root(), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""
    return proc.returncode, proc.stdout.strip()


def known_marketplace():
    path = os.environ.get("LIMITLINE_KNOWN_MARKETPLACES") or os.path.join(
        os.path.expanduser("~"), ".claude", "plugins", "known_marketplaces.json")
    try:
        with open(path, encoding="utf-8") as handle:
            entry = json.load(handle).get(MARKETPLACE)
    except (OSError, ValueError, AttributeError):
        return None
    return entry if isinstance(entry, dict) else None


def marketplace_ref():
    """The ref Claude Code's marketplace was added with ("" = the default branch, main), but
    only when this copy IS that install; a development checkout answers None."""
    entry = known_marketplace()
    if not entry:
        return None
    location = os.path.realpath(str(entry.get("installLocation") or ""))
    if location != os.path.realpath(root()):
        return None
    source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
    return str(source.get("ref") or "")


def channel_of(ref):
    for name, branch in CHANNELS.items():
        if ref == branch:
            return name
    return "dev" if ref in ("", None) else f"custom ({ref})"


def current():
    code, branch = git("rev-parse", "--abbrev-ref", "HEAD")
    _c, commit = git("rev-parse", "--short", "HEAD")
    ref = marketplace_ref()
    if ref is None:
        ref = branch if code == 0 else ""
    return {"version": version(), "channel": channel_of(ref), "ref": ref or "main", "commit": commit or "?", "root": root()}


def cmd_version(_args):
    info = current()
    print(f"limitline {info['version']} · channel {info['channel']} ({info['ref']}) · {info['commit']}")
    print(f"installed at {info['root']}")
    return 0


def claude():
    return shutil.which("claude")


def run(argv, dry):
    print("  $ " + " ".join(argv))
    if dry:
        return 0
    return subprocess.run(argv).returncode


def cmd_update(args):
    dry = "--dry-run" in args
    before = version()
    if claude() and marketplace_ref() is not None:
        steps = [["claude", "plugin", "marketplace", "update", MARKETPLACE], ["claude", "plugin", "update", PLUGIN]]
    else:
        steps = [["git", "-C", root(), "pull", "--ff-only"]]
    print(f"updating limitline {before} ({current()['channel']}):")
    for step in steps:
        if run(step, dry) != 0:
            print("update failed; nothing else was changed", file=sys.stderr)
            return 1
    if not dry:
        print(f"limitline {before} -> {version()}. A new status line shows on the next redraw.")
    return 0


def cmd_channel(args):
    names = [a for a in args if not a.startswith("-")]
    if not names:
        info = current()
        print(f"channel {info['channel']} ({info['ref']}), limitline {info['version']}")
        print("switch with: limitline channel stable | beta | dev   (add --yes to run it)")
        return 0
    name = names[0]
    if name not in CHANNELS:
        print(f"unknown channel {name!r}: use stable, beta, or dev", file=sys.stderr)
        return 2
    ref = CHANNELS[name]
    if not claude():
        print("claude is not on PATH; in a git checkout use: git checkout " + ref, file=sys.stderr)
        return 1
    code, out = git("ls-remote", "--heads", f"https://github.com/{REPO}.git", ref, timeout=30)
    if code != 0 or not out:
        print(f"the {name} channel has no build yet (no branch {ref!r} on GitHub); nothing changed", file=sys.stderr)
        return 1
    dry = "--yes" not in args
    print(f"switching limitline to {name} ({ref}):" + ("  (dry run; add --yes to do it)" if dry else ""))
    steps = [
        ["claude", "plugin", "marketplace", "remove", MARKETPLACE],
        ["claude", "plugin", "marketplace", "add", f"{REPO}#{ref}"],
        ["claude", "plugin", "install", PLUGIN],
    ]
    for step in steps:
        if run(step, dry) != 0:
            print(f"failed at: {' '.join(step)}. Re-run: claude plugin marketplace add {REPO}#{ref} && claude plugin install {PLUGIN}",
                  file=sys.stderr)
            return 1
    if not dry:
        print(f"now on {name}: limitline {version()}. Your status line setting is unchanged.")
    return 0


def main(argv):
    cmd = argv[0] if argv else "version"
    handler = {"version": cmd_version, "--version": cmd_version, "update": cmd_update, "channel": cmd_channel}.get(cmd)
    if handler is None:
        print("usage: limitline version | update [--dry-run] | channel [stable|beta|dev] [--yes]", file=sys.stderr)
        return 2
    return handler(argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
