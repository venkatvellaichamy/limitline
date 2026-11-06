---
name: install
description: Install limitline as the Claude Code status line
allowed-tools: Read, Write, Bash
---

# Install the limitline status line

Set Claude Code's `statusLine` to this plugin's `bin/limitline`. Do the work below yourself with the tools available in this session. Do not claim it is installed until the file on disk matches.

## With Pharos as the reader

Check `reader` and `reader_freshness` in limitline's config and the modification age of `~/.pharos/usage.json` (auto freshness defaults to 900 seconds). If the reader is `pharos`, or auto detects a fresh file, preserve `pharos statusline` in Claude Code settings: it forwards stdin to limitline. Skip refresh-agent installation and all writes to `~/.pharos`; Pharos manages host settings and saves Claude's reading. Run `limitline doctor` to identify redundant agents and show `limitline uninstall --refresh-jobs --dry-run` for review. In this mode stop here; do not follow the standalone installation steps below.

## Resolve the command

1. The plugin root is the absolute path in `${CLAUDE_PLUGIN_ROOT}`. If that variable is empty, stop and say the command has to be run inside Claude Code after the plugin is installed.
2. The status-line command is `"${CLAUDE_PLUGIN_ROOT}/bin/limitline"`. Confirm that file exists and is executable. If it is not, `chmod +x` it.

Desired value:

```json
{"type":"command","command":"<absolute path to bin/limitline>","padding":0,"refreshInterval":30}
```

`refreshInterval` is Claude Code's documented `statusLine` timer: it re-runs the command every N seconds (minimum 1) as well as on session events. Without it an idle terminal keeps the fleet, machine, and plan numbers it last drew, so two idle terminals can show different numbers. 30 seconds keeps every terminal on the shared caches; a warm render takes about 30 ms.

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
data["statusLine"] = {"type": "command", "command": command, "padding": 0, "refreshInterval": 30}
with open(path, "w") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
PY
```

Use that only after the backup and the confirmation step. Read the file back and show the user the resulting `statusLine` plus the backup path.

## Name your computers

The `hosts` line of the status line shows each computer by a nickname you choose, on any system (macOS, Linux, Windows through WSL or Git Bash). After the status line is set:

1. Read `~/.config/limitline/config.toml` if it exists. If it already has a `hosts =` line, show it and ask whether to keep it.
2. Otherwise ask: "What do you call this computer?" Offer the short hostname (`hostname -s`) as the default.
3. Ask whether there are other computers to show. For each one, ask for a nickname and its ssh target (`user@host`). Skip this when the user says no.
4. When Pharos is the selected reader, skip this step and tell the user host names are configured in Pharos. Otherwise, hosts are measured by Pharos, so the nicknames go in Pharos's settings: write `hosts = ["<nickname>=local", "<nickname>=<user@host>", ...]` into `~/.pharos/usage.toml`, keeping every other line, and back it up first as `usage.toml.bak-limitline-<UTC timestamp>`. If `~/.pharos` does not exist, say that host and job lines need Pharos and skip this step.
5. Write `lines = 5` into `~/.config/limitline/config.toml`, keeping every other line, after backing it up as `config.toml.bak-limitline-<UTC timestamp>`.
6. Run `pharos usage --refresh` (if Pharos is installed), then `limitline refresh`, so the first render has the readings.
