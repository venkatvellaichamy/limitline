---
name: preview
description: Preview the limitline status line with sample data
allowed-tools: Bash
---

# Preview limitline

Render the status line with the sample session below. Do not edit settings.

1. Resolve the script as `"${CLAUDE_PLUGIN_ROOT}/bin/limitline"`. If `CLAUDE_PLUGIN_ROOT` is empty, use `bin/limitline` from the repository that contains this command.
2. Run the command below and show the user the exact stdout. Then run it again with `NO_COLOR=1` so they can see the plain line.
3. Explain the segments in one sentence each: model, 5-hour limit, weekly limit, context, and that Codex is omitted here because this sample has no local Codex log.

```bash
LIMITLINE_NOW=1762056000 TZ=UTC LIMITLINE_CODEX=0 LIMITLINE_CONFIG=/dev/null \
  "$SCRIPT" << 'EOF'
{"model":{"display_name":"Opus 5.5"},"rate_limits":{"five_hour":{"used_percentage":62,"resets_at":1762062120},"seven_day":{"used_percentage":38,"resets_at":1762419600}},"context_window":{"used_percentage":41}}
EOF
```

Expected plain text after colour codes are removed:

```
Opus 5.5 │ 5h ▓▓▓░░ 62% ↻1h42m │ 7d ▓▓░░░ 38% ↻Thu 09:00 │ ctx 41%
```

If the script exits non-zero or prints a traceback, quote the output and stop. Do not change `~/.claude/settings.json`.
