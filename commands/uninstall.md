---
name: uninstall
description: Remove limitline from the Claude Code status line
allowed-tools: Read, Write, Bash
---

# Uninstall the limitline status line

Remove limitline from `~/.claude/settings.json` without touching any other setting.

1. If `~/.claude/settings.json` does not exist, say there is nothing to remove and stop.
2. If the file is not valid JSON, stop and show the parse error. Do not write.
3. If there is no `statusLine` key, say so and stop.
4. If `statusLine.command` does not contain `bin/limitline`, show the current value, leave the file unchanged, and tell the user this status line is not limitline.
5. Copy the file to `~/.claude/settings.json.bak-limitline-<UTC timestamp YYYYMMDDHHMMSS>` before writing.
6. Delete only the `statusLine` key. Preserve every other key and value. Write UTF-8 JSON, indented with two spaces, and a trailing newline.
7. Read the file back and confirm `statusLine` is gone and the backup path exists.

```bash
python3 - "$SETTINGS" << 'PY'
import json, sys
path = sys.argv[1]
with open(path) as fh:
    data = json.load(fh)
data.pop("statusLine", None)
with open(path, "w") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
PY
```

Run that only after the backup and only when the command path contains `bin/limitline`.
