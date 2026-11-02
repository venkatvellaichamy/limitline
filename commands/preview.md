---
name: preview
description: Preview every limitline theme with sample data
allowed-tools: Bash
---

# Preview limitline

Render the status line with the sample session below. Do not edit settings.

1. Resolve the script as `"${CLAUDE_PLUGIN_ROOT}/bin/limitline"`. If `CLAUDE_PLUGIN_ROOT` is empty, use `bin/limitline` from the repository that contains this command.
2. Run `preview` so the user sees minimal, ascii, and powerline. Then run the sample once more with colour left on, and once with `NO_COLOR=1`.
3. Explain the segments in one sentence each: model, context, 5-hour limit, weekly limit. Codex is omitted here because this sample has no local Codex log.

```bash
"$SCRIPT" preview
```

Expected plain text:

```
## minimal
Opus 5.5 │ ctx ▓▓░░░ ·41% │ 5h ▓▓▓░░ +62% ↻1h42m │ 7d ▓▓░░░ ·38% ↻Thu 09:00
## ascii
Opus 5.5 | ctx ##--- ·41% | 5h ###-- +62% in 1h42m | 7d ##--- ·38% in Thu 09:00
## powerline
Opus 5.5  ctx ██░░░ ·41%  5h ███░░ +62% ↻1h42m  7d ██░░░ ·38% ↻Thu 09:00
```

The same sample, if you need to call the renderer directly:

```bash
LIMITLINE_NOW=1762056000 TZ=UTC LIMITLINE_CODEX=0 LIMITLINE_GIT=0 LIMITLINE_CONFIG=/dev/null \
  "$SCRIPT" << 'EOF'
{"model":{"display_name":"Opus 5.5"},"rate_limits":{"five_hour":{"used_percentage":62,"resets_at":1762062120},"seven_day":{"used_percentage":38,"resets_at":1762419600}},"context_window":{"used_percentage":41}}
EOF
```

If the script exits non-zero or prints a traceback, quote the output and stop. Do not change `~/.claude/settings.json`.
