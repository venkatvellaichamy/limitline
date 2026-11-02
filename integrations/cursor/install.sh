#!/bin/bash
# Prints the Cursor CLI statusLine entry. Does not edit ~/.cursor/cli-config.json
# unless you pass --write, which backs up the file first.
set -u
BIN="${LIMITLINE_BIN:-$(cd "$(dirname "$0")/../.." && pwd)/bin/limitline}"
cat << EOF
Add this to ~/.cursor/cli-config.json without removing other keys:

"statusLine": {"type": "command", "command": "$BIN", "padding": 0}

That renders model and context from Cursor's own stdin payload.
For every tool's cached quota instead, set command to:

"$BIN --host cursor"

Cursor does not write a local usage-limit file.
EOF
if [[ "${1:-}" != "--write" ]]; then
  exit 0
fi
python3 - "$BIN" << 'PY'
import json, os, shutil, sys, time
command = sys.argv[1]
path = os.path.expanduser("~/.cursor/cli-config.json")
if not os.path.exists(path):
    data = {}
else:
    stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    shutil.copyfile(path, path + ".bak-limitline-" + stamp)
    data = json.load(open(path))
if not isinstance(data, dict):
    raise SystemExit("cli-config root must be an object")
data["statusLine"] = {"type": "command", "command": command, "padding": 0}
with open(path, "w") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
print("updated", path)
PY
