#!/bin/bash
# Codex CLI 0.166 has a built-in footer, not a status command.
# This prints the items that show the same 5-hour and weekly windows.
# It does not edit ~/.codex/config.toml unless you pass --write.
set -u
cat << 'EOF'
Codex reads limits itself. In the TUI, /statusline toggles items.
Or set this in ~/.codex/config.toml:

[tui]
status_line = ["model", "five-hour-limit", "weekly-limit", "context-remaining"]

There is no field for an external script. Outside the TUI, run:

  limitline status

Session logs under ~/.codex/sessions are the local source limitline already reads.
EOF
if [[ "${1:-}" == "--write" ]]; then
  echo "Refusing to rewrite Codex config from this installer." >&2
  echo "Add the snippet above yourself so the rest of the file stays intact." >&2
  exit 1
fi
