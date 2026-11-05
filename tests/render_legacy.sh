#!/usr/bin/env bash
# Render tests/fixtures/rich.json with one config file in a clean, fixed environment.
# The .expected files next to each tests/fixtures/legacy/*.toml were made with this
# script from limitline 0.14.0, before 0.15 changed the default line, so a config that
# names its own segments must keep rendering byte for byte the same.
#   tests/render_legacy.sh CONFIG [BIN]
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cfg="$1"
bin="${2:-$ROOT/bin/limitline}"
home=$(mktemp -d)
trap 'rm -rf "$home"' EXIT
mkdir -p "$home/tmp" "$home/.cache" "$home/.config"
env -i PATH="$PATH" HOME="$home" TMPDIR="$home/tmp" XDG_CACHE_HOME="$home/.cache" \
  XDG_CONFIG_HOME="$home/.config" TZ=UTC LC_ALL=C NO_COLOR=1 \
  LIMITLINE_NOW=1762056000 LIMITLINE_CONFIG="$cfg" LIMITLINE_CODEX=0 LIMITLINE_REFRESH=0 \
  LIMITLINE_CLAUDE_CACHE=0 LIMITLINE_XAI_FETCH=0 LIMITLINE_AGY_FETCH=0 \
  LIMITLINE_PHAROS_HOME="$home/no-pharos" \
  "$bin" < "$ROOT/tests/fixtures/rich.json"
