---
name: config
description: Print a limitline config template without writing it
allowed-tools: Bash
---

# Show the limitline config template

Print the template. Do not write `~/.config/limitline/config.toml` and do not edit `~/.claude/settings.json`.

1. Resolve the script as `"${CLAUDE_PLUGIN_ROOT}/bin/limitline"`. If `CLAUDE_PLUGIN_ROOT` is empty, use `bin/limitline` from the repository that contains this command.
2. Run `"$SCRIPT" config` and show the stdout.
3. Tell the user to copy it to `~/.config/limitline/config.toml` if they want those settings. Environment variables override the file.

The template sets the minimal theme, a 5-cell bar, one line, and auto-compact at 95. The layout keys (`preset`, `line1` ... `line9`, `dir_style`, `colors`) are printed as comments; without them line 1 starts with the folder, git, model, and context. `/limitline:statusline` picks items with a preview. Session id and other-tool segments stay off on the Claude Code line until the user opts in. Pace, sparklines, nudges, fresh wording, the value meter, vitals, alerts, and the Pharos-fed segments (fleet, machines, grok, jobs, five lines) are printed as comments and stay off until the user uncomments them.
