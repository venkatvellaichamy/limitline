#!/bin/bash
# Grok can run limitline as its status command. Rate limits are not in that payload.
# This does not edit ~/.grok/config.toml.
set -u
BIN="${LIMITLINE_BIN:-$(cd "$(dirname "$0")/../.." && pwd)/bin/limitline}"
cat << EOF
Add this to ~/.grok/config.toml and restart Grok:

[ui.status_line]
type = "command"
command = "$BIN"

The guide for this Grok build says the stdin object has no rate-limit summary.
Account quota is not in ~/.grok/sessions/*/usage.json either. The row can still
show model, context, and cost from that payload.
EOF
if [[ "${1:-}" == "--write" ]]; then
  echo "Refusing to rewrite Grok config. Paste the snippet so other keys stay put." >&2
  exit 1
fi
