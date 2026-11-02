---
name: install
description: Install limitline as the Claude Code status line
allowed-tools: Read, Write, Bash
---

# Install the limitline status line

Set Claude Code's `statusLine` to this plugin's `bin/limitline`. Do the work below yourself with the tools available in this session. Do not claim it is installed until the file on disk matches.

## Resolve the command

1. The plugin root is the absolute path in `${CLAUDE_PLUGIN_ROOT}`. If that variable is empty, stop and say the command has to be run inside Claude Code after the plugin is installed.
2. The status-line command is `"${CLAUDE_PLUGIN_ROOT}/bin/limitline"`. Confirm that file exists and is executable. If it is not, `chmod +x` it.

Desired value:

```json
{"type":"command","command":"<absolute path to bin/limitline>","padding":0}
```

## Edit settings

Target file: `~/.claude/settings.json`.

1. If the file does not exist, treat the current JSON as `{}`.
2. If the file exists but is not valid JSON, stop. Show the parse error. Do not write.
3. If `statusLine` is already present and is not deeply equal to the desired value, show the current value and ask before replacing it. Stop if the user says no.
4. If `statusLine` is already the desired value, say so and do not write.
5. Before the first write, copy the existing file to `~/.claude/settings.json.bak-limitline-<UTC timestamp YYYYMMDDHHMMSS>`. Skip the backup only when the file does not exist yet.
6. Set `statusLine` to the desired object. Preserve every other key and value, including nested objects and arrays. Write UTF-8 JSON, indented with two spaces, and a trailing newline.

A safe update, after the user agrees when a previous status line is present:

```bash
python3 - "$SETTINGS" "$COMMAND" << 'PY'
import json, sys
path, command = sys.argv[1], sys.argv[2]
with open(path) as fh:
    data = json.load(fh)
if not isinstance(data, dict):
    raise SystemExit("settings root must be an object")
data["statusLine"] = {"type": "command", "command": command, "padding": 0}
with open(path, "w") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
PY
```

Use that only after the backup and the confirmation step. Read the file back and show the user the resulting `statusLine` plus the backup path.
