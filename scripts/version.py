#!/usr/bin/env python3
"""Release helpers. Never pushes or tags; the release workflow does that from a tag.

    scripts/version.py check [X.Y.Z]   every version file agrees (and equals X.Y.Z, e.g. from a tag)
    scripts/version.py bump X.Y.Z      write X.Y.Z into every version file
    scripts/version.py notes X.Y.Z     print the CHANGELOG section for X.Y.Z
    scripts/version.py channel X.Y.Z   "stable" or "beta" (a -alpha.N, -beta.N, or -rc.N version)
    scripts/version.py newer A B       exit 0 when A >= B (so a stable hotfix never moves beta back)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^\d+\.\d+\.\d+(-(alpha|beta|rc)\.\d+)?$")
BIN = ROOT / "bin" / "limitline"
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
MARKET = ROOT / ".claude-plugin" / "marketplace.json"
CHANGELOG = ROOT / "CHANGELOG.md"


def found():
    out = {}
    match = re.search(r"^# Version: (\S+)$", BIN.read_text(encoding="utf-8"), re.M)
    out["bin/limitline"] = match.group(1) if match else None
    out[".claude-plugin/plugin.json"] = json.loads(PLUGIN.read_text(encoding="utf-8")).get("version")
    market = json.loads(MARKET.read_text(encoding="utf-8"))
    out[".claude-plugin/marketplace.json"] = next((p.get("version") for p in market.get("plugins", []) if p.get("name") == "limitline"), None)
    return out


def notes(version):
    text = CHANGELOG.read_text(encoding="utf-8")
    match = re.search(r"^## " + re.escape(version) + r"\b.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return match.group(1).strip() if match else None


def check(want=None):
    versions = found()
    problems = []
    values = set(versions.values())
    if len(values) != 1:
        problems.append("version files disagree: " + ", ".join(f"{k}={v}" for k, v in versions.items()))
    version = want or next(iter(values))
    if not version or not SEMVER.match(version):
        problems.append(f"not a release version: {version!r} (X.Y.Z or X.Y.Z-beta.N)")
    if want and values != {want}:
        problems.append(f"tag says {want}, files say " + ", ".join(sorted(str(v) for v in values)))
    if version and not notes(version):
        problems.append(f"CHANGELOG.md has no '## {version}' section")
    for line in problems:
        print("release check: " + line, file=sys.stderr)
    if not problems:
        print(f"release check: {version} ok ({channel(version)})")
    return 1 if problems else 0


def bump(version):
    if not SEMVER.match(version):
        print(f"not a release version: {version}", file=sys.stderr)
        return 2
    BIN.write_text(re.sub(r"^# Version: \S+$", f"# Version: {version}", BIN.read_text(encoding="utf-8"), count=1, flags=re.M), encoding="utf-8")
    for path in (PLUGIN, MARKET):
        text = path.read_text(encoding="utf-8")
        text = re.sub(r'("version":\s*")[^"]*(")', lambda m: m.group(1) + version + m.group(2), text)
        path.write_text(text, encoding="utf-8")
    print(f"version files set to {version}; add a '## {version}' section to CHANGELOG.md")
    return 0


def key(version):
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-(alpha|beta|rc)\.(\d+))?$", version or "")
    if not match:
        return None
    major, minor, patch, pre, num = match.groups()
    rank = {"alpha": 0, "beta": 1, "rc": 2, None: 3}[pre]
    return (int(major), int(minor), int(patch), rank, int(num or 0))


def channel(version):
    return "beta" if "-" in version else "stable"


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, arg = argv[0], (argv[1] if len(argv) > 1 else None)
    if arg and arg.startswith("v"):
        arg = arg[1:]
    if cmd == "check":
        return check(arg)
    if cmd == "bump" and arg:
        return bump(arg)
    if cmd == "notes" and arg:
        text = notes(arg)
        if text is None:
            return 1
        print(text)
        return 0
    if cmd == "newer" and len(argv) > 2:
        a, b = key(argv[1].lstrip("v")), key(argv[2].lstrip("v"))
        return 0 if a is not None and (b is None or a >= b) else 1
    if cmd == "channel" and arg:
        print(channel(arg))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
