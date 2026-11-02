---
name: doctor
description: Check local tools and which status-line fields are present
allowed-tools: Bash
---

# Check the limitline setup

Report what is available. Do not edit settings and do not print secret values.

1. Resolve the script as `"${CLAUDE_PLUGIN_ROOT}/bin/limitline"`. If `CLAUDE_PLUGIN_ROOT` is empty, use `bin/limitline` from the repository that contains this command.
2. Run `"$SCRIPT" doctor`. If a status payload is already on stdin, pass it through. Otherwise run doctor with no stdin.
3. Show stdout. It lists whether `jq`, `python3`, `awk`, and `git` are on `PATH`, then whether known field paths are present. It does not print the field values.
4. If the script exits non-zero, quote the output and stop.
