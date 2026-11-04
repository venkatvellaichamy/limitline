---
name: doctor
description: Check local tools and which status-line fields are present
allowed-tools: Bash
---

# Check the limitline setup

Report what is available. Do not edit settings and do not print secret values.

1. Resolve the script as `"${CLAUDE_PLUGIN_ROOT}/bin/limitline"`. If `CLAUDE_PLUGIN_ROOT` is empty, use `bin/limitline` from the repository that contains this command.
2. Run `"$SCRIPT" doctor`. If a status payload is already on stdin, pass it through. Otherwise run doctor with no stdin.
3. Show stdout. It lists whether `jq`, `python3`, `awk`, and `git` are on `PATH`, then the fleet sources: whether the fleet and machines segments are on, whether Pharos's summary and usage files are present and how old they are, cache ages against their TTLs, when the Claude relay last wrote, whether the background refresher is installed, and whether this is a cloud-hosted session. An `empty segments` block explains why fleet or machines would be blank. Then it lists whether known field paths are present. It does not print field values or ssh user names.
4. If a segment is empty because its cache is stale or missing, suggest `"$SCRIPT" install-refresher` on macOS. Do not run it without the user asking.
5. If the script exits non-zero, quote the output and stop.
