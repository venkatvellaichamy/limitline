---
name: theme
description: Pick a limitline theme from a live preview of each one
allowed-tools: Bash
---

# Pick a limitline theme

Show a live preview of every theme. Do not edit settings.

1. Resolve the script as `"${CLAUDE_PLUGIN_ROOT}/bin/limitline"`. If `CLAUDE_PLUGIN_ROOT` is empty, use `bin/limitline` from the repository that contains this command.
2. Run `theme`. The user should see minimal, ascii, powerline, pill, emoji, and mono, then one line that names `LIMITLINE_THEME`.
3. Tell them to set `theme` in `~/.config/limitline/config.toml` or export `LIMITLINE_THEME`. `pill` is rounded chips, `emoji` adds a mark on each segment, and `mono` stays plain text.

```bash
"$SCRIPT" theme
```

The picker ends with:

```
Set one with theme = "pill" or LIMITLINE_THEME=pill
```

If the script exits non-zero or prints a traceback, quote the output and stop. Do not change `~/.claude/settings.json`.
