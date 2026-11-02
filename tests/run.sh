#!/usr/bin/env bash
# Fixture tests for limitline. ANSI colour is stripped before comparison.
set -u

ROOT=$(cd "$(dirname "$0")/.." && pwd)
BIN="$ROOT/bin/limitline"
FIX="$ROOT/tests/fixtures"

if [[ ! -x "$BIN" ]]; then
  echo "bin/limitline is not executable" >&2
  exit 1
fi

TEST_HOME=$(mktemp -d)
cleanup() { rm -rf "$TEST_HOME"; }
trap cleanup EXIT

export HOME="$TEST_HOME"
export XDG_CONFIG_HOME="$TEST_HOME/.config"
export XDG_CACHE_HOME="$TEST_HOME/.cache"
export TMPDIR="$TEST_HOME/tmp"
mkdir -p "$TMPDIR" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME"
export LIMITLINE_NOW=1762056000
export LIMITLINE_CONFIG=/dev/null
export LIMITLINE_CODEX=0
export LIMITLINE_GIT=0
export TZ=UTC
export LC_ALL=C
unset NO_COLOR LIMITLINE_DEBUG LIMITLINE_DEBUG_FILE LIMITLINE_CODEX_DIR LIMITLINE_BAR_WIDTH LIMITLINE_NOCACHE \
  LIMITLINE_THEME LIMITLINE_ASCII LIMITLINE_SESSION LIMITLINE_COLUMNS COLUMNS LIMITLINE_LINES \
  LIMITLINE_CLAUDE_SNAPSHOT LIMITLINE_GROK_DIR LIMITLINE_GEMINI_LOG LIMITLINE_STALE_MINUTES

fail=0
pass=0

strip_ansi() {
  sed $'s/\033\\[[0-9;]*m//g'
}

check() {
  local name="$1"
  local got="$2"
  local want="$3"
  if [[ "$got" == "$want" ]]; then
    pass=$((pass + 1))
    printf 'ok  %s\n' "$name"
  else
    fail=$((fail + 1))
    printf 'FAIL %s\n' "$name" >&2
    printf '  want: %s\n' "$want" >&2
    printf '  got:  %s\n' "$got" >&2
  fi
}

render() {
  "$BIN" 2>"$TEST_HOME/err"
}

for f in "$FIX"/*.json; do
  base=$(basename "$f" .json)
  exp="$FIX/$base.expected"
  [[ -f "$exp" ]] || continue
  got=$(render < "$f" | strip_ansi)
  want=$(strip_ansi < "$exp")
  # Drop a single trailing newline from both sides.
  got=${got%$'\n'}
  want=${want%$'\n'}
  check "$base" "$got" "$want"
  if [[ -s "$TEST_HOME/err" ]]; then
    fail=$((fail + 1))
    printf 'FAIL %s wrote stderr\n' "$base" >&2
    cat "$TEST_HOME/err" >&2
  fi
done

# Colours: under 50 green, 50-80 yellow, over 80 red. 80 itself stays yellow.
raw=$(LIMITLINE_CODEX=0 "$BIN" < "$FIX/full.json")
printf '%s' "$raw" | grep -q -F $'\033[33m' && printf '%s' "$raw" | grep -q -F $'\033[32m' \
  && check "full-colours" "yes" "yes" \
  || check "full-colours" "no" "yes"

raw=$(LIMITLINE_CODEX=0 "$BIN" < "$FIX/over_80.json")
printf '%s' "$raw" | grep -q -F $'\033[31m' && printf '%s' "$raw" | grep -q -F $'\033[33m' \
  && check "over-80-colours" "yes" "yes" \
  || check "over-80-colours" "no" "yes"

nocolor=$(NO_COLOR=1 "$BIN" < "$FIX/over_80.json" | strip_ansi)
plain=$("$BIN" < "$FIX/over_80.json" | strip_ansi)
check "no-color-same-text" "$nocolor" "$plain"
if printf '%s' "$(NO_COLOR=1 "$BIN" < "$FIX/over_80.json")" | grep -q -F $'\033'; then
  check "no-color-strips-ansi" "no" "yes"
else
  check "no-color-strips-ansi" "yes" "yes"
fi

# Invalid JSON and a closed empty stdin must not crash.
if printf '{bad' | "$BIN" >/dev/null 2>"$TEST_HOME/err"; then
  check "invalid-json-exit" "0" "0"
else
  check "invalid-json-exit" "$?" "0"
fi
if [[ -s "$TEST_HOME/err" ]]; then
  check "invalid-json-stderr" "noise" "quiet"
else
  check "invalid-json-stderr" "quiet" "quiet"
fi

# ISO-8601 reset matches the unix timestamp used in full.json (2025-11-02T05:42:00Z).
iso_got=$(printf '%s' '{"model":{"display_name":"Opus 5.5"},"rate_limits":{"five_hour":{"used_percentage":62,"resets_at":"2025-11-02T05:42:00Z"}}}' | "$BIN" | strip_ansi)
iso_got=${iso_got%$'\n'}
check "iso-reset" "$iso_got" "Opus 5.5 │ 5h ▓▓▓░░ +62% ↻1h42m"

# Alternate context field name.
alt_got=$(printf '%s' '{"context":{"used_percentage":12}}' | "$BIN" | strip_ansi)
alt_got=${alt_got%$'\n'}
check "alt-context" "$alt_got" "ctx ▓░░░░ ·12%"

# Spend computed from dollars when the percentage is absent.
spend_got=$(printf '%s' '{"rate_limits":{"spend_limit":{"used_usd":2,"limit_usd":8}}}' | "$BIN" | strip_ansi)
spend_got=${spend_got%$'\n'}
check "spend-computed" "$spend_got" 'spend ▓░░░░ ·25% $2/$8'

# Codex segment uses the last rate_limits event in the newest log, when it is under 6h old.
fresh_dir="$TEST_HOME/fresh"
stale_dir="$TEST_HOME/stale"
mkdir -p "$fresh_dir/sub" "$stale_dir"
cp "$FIX/codex/fresh.jsonl" "$fresh_dir/sub/session.jsonl"
cp "$FIX/codex/stale.jsonl" "$stale_dir/session.jsonl"
# Older file in the same tree must lose to the newest mtime.
printf '%s\n' '{"timestamp":"2025-11-02T03:40:00.000Z","type":"event_msg","payload":{"type":"token_count","rate_limits":{"primary":{"used_percent":1,"window_minutes":300,"resets_at":1},"secondary":{"used_percent":2,"window_minutes":10080,"resets_at":1}}}}' > "$fresh_dir/old.jsonl"
touch -t 202511020300 "$fresh_dir/old.jsonl"
touch -t 202511020350 "$fresh_dir/sub/session.jsonl"

example_got=$(LIMITLINE_CODEX=1 LIMITLINE_CODEX_DIR="$fresh_dir" LIMITLINE_NOCACHE=1 "$BIN" < "$FIX/full.json" | strip_ansi)
example_got=${example_got%$'\n'}
example_want=$(cat "$FIX/example.expected")
example_want=${example_want%$'\n'}
check "codex-fresh" "$example_got" "$example_want"

stale_got=$(LIMITLINE_CODEX=1 LIMITLINE_CODEX_DIR="$stale_dir" LIMITLINE_NOCACHE=1 "$BIN" < "$FIX/full.json" | strip_ansi)
stale_got=${stale_got%$'\n'}
full_want=$(cat "$FIX/full.expected")
full_want=${full_want%$'\n'}
check "codex-stale-hidden" "$stale_got" "$full_want"

# Config file, then an env override.
cfg="$TEST_HOME/.config/limitline/config"
mkdir -p "$(dirname "$cfg")"
cat > "$cfg" << 'EOF'
# sample
bar_width = 1
codex = off
color = on
EOF
cfg_got=$(LIMITLINE_CONFIG="$cfg" LIMITLINE_CODEX=0 "$BIN" < "$FIX/full.json" | strip_ansi)
cfg_got=${cfg_got%$'\n'}
check "config-bar-width" "$cfg_got" 'Opus 5.5 │ ctx ░ ·41% │ 5h ▓ +62% ↻1h42m │ 7d ░ ·38% ↻Thu 09:00 │ $1.25'

env_got=$(LIMITLINE_CONFIG="$cfg" LIMITLINE_BAR_WIDTH=5 LIMITLINE_CODEX=0 "$BIN" < "$FIX/full.json" | strip_ansi)
env_got=${env_got%$'\n'}
check "env-overrides-config" "$env_got" "$full_want"

# Seeded Codex cache, with no session directory present.
cache="$TMPDIR/limitline-codex-$(id -u).cache"
printf '%s\n' "$(date +%s) 1 12 - 55 -" > "$cache"
cached_got=$(LIMITLINE_CONFIG=/dev/null LIMITLINE_CODEX=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
cached_got=${cached_got%$'\n'}
check "codex-cache" "$cached_got" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12 │ codex 5h ·12% · 7d +55%'
rm -f "$cache"

# Debug dump writes stdin and does not change the line.
debug_file="$TEST_HOME/debug.json"
debug_got=$(LIMITLINE_DEBUG=1 LIMITLINE_DEBUG_FILE="$debug_file" "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
debug_got=${debug_got%$'\n'}
check "debug-stdout" "$debug_got" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12'
if cmp -s "$FIX/no_rate_limits.json" "$debug_file"; then
  check "debug-file" "match" "match"
else
  check "debug-file" "mismatch" "match"
fi

# python3 fallback matches jq output on every fixture.
# Hide jq without dropping awk, date, and the other tools the script still needs.
nojq="$TEST_HOME/nojq"
mkdir -p "$nojq"
for tool in bash python3 awk date find grep id sed tail cat tr; do
  src=$(command -v "$tool" 2>/dev/null) || continue
  ln -s "$src" "$nojq/$tool"
done
if [[ -e "$nojq/jq" ]] || PATH="$nojq" command -v jq >/dev/null 2>&1; then
  echo "failed to hide jq" >&2
  exit 1
fi
if ! PATH="$nojq" command -v python3 >/dev/null 2>&1; then
  echo "python3 is required for the fallback test" >&2
  exit 1
fi
for f in "$FIX"/*.json; do
  base=$(basename "$f" .json)
  with_jq=$(LIMITLINE_CODEX=0 "$BIN" < "$f" | strip_ansi)
  no_jq=$(PATH="$nojq" LIMITLINE_CODEX=0 "$BIN" < "$f" | strip_ansi)
  check "python-fallback-$base" "$no_jq" "$with_jq"
done
py_codex=$(PATH="$nojq" LIMITLINE_CODEX=1 LIMITLINE_CODEX_DIR="$fresh_dir" LIMITLINE_NOCACHE=1 "$BIN" < "$FIX/full.json" | strip_ansi)
py_codex=${py_codex%$'\n'}
check "python-fallback-codex" "$py_codex" "$example_want"

# Themes, width, burn, git, and the other providers.
ascii_got=$(NO_COLOR=1 LIMITLINE_THEME=ascii "$BIN" < "$FIX/full.json" | strip_ansi)
ascii_got=${ascii_got%$'\n'}
check "theme-ascii" "$ascii_got" 'Opus 5.5 | ctx ##--- ·41% | 5h ###-- +62% in 1h42m | 7d ##--- ·38% in Thu 09:00 | $1.25'

ascii_env=$(NO_COLOR=1 LIMITLINE_ASCII=1 "$BIN" < "$FIX/full.json" | strip_ansi)
ascii_env=${ascii_env%$'\n'}
check "theme-ascii-env" "$ascii_env" "$ascii_got"

power_got=$(NO_COLOR=1 LIMITLINE_THEME=powerline "$BIN" < "$FIX/full.json" | strip_ansi)
power_got=${power_got%$'\n'}
check "theme-powerline" "$power_got" 'Opus 5.5  ctx ██░░░ ·41%  5h ███░░ +62% ↻1h42m  7d ██░░░ ·38% ↻Thu 09:00  $1.25'

two_got=$(NO_COLOR=1 LIMITLINE_LINES=2 "$BIN" < "$FIX/full.json" | strip_ansi)
printf '%s' "$two_got" | grep -q $'\n' && printf '%s' "$two_got" | grep -q -F '5h' \
  && check "two-line" "yes" "yes" || check "two-line" "no" "yes"

narrow_got=$(NO_COLOR=1 LIMITLINE_SESSION=1 LIMITLINE_COLUMNS=60 "$BIN" < "$FIX/narrow.json" | strip_ansi)
narrow_got=${narrow_got%$'\n'}
narrow_len=$(printf '%s' "$narrow_got" | python3 -c 'import sys; print(len(sys.stdin.read()))')
if [[ "$narrow_len" -le 60 ]] && printf '%s' "$narrow_got" | grep -q -F 'Opus 5.5' \
  && printf '%s' "$narrow_got" | grep -q -F '5h' \
  && ! printf '%s' "$narrow_got" | grep -q -F 'abcdef'; then
  check "narrow-60" "yes" "yes"
else
  check "narrow-60" "$narrow_got" "width<=60 with model and 5h, session dropped"
fi

hist="$XDG_CACHE_HOME/limitline/history-5h.tsv"
mkdir -p "$(dirname "$hist")"
printf '%s\n' "1762054200 50" > "$hist"
burn_got=$(NO_COLOR=1 "$BIN" < "$FIX/full.json" | strip_ansi)
burn_got=${burn_got%$'\n'}
printf '%s' "$burn_got" | grep -q -F 'pace ~1h35m' \
  && check "burn-pace" "yes" "yes" || check "burn-pace" "$burn_got" "pace ~1h35m"
rm -f "$hist"

git_repo="$TEST_HOME/repo"
mkdir -p "$git_repo"
git -C "$git_repo" init -q -b demo
git -C "$git_repo" -c user.name=limitline -c user.email=limitline@example.com commit -q --allow-empty -m init
printf 'x\n' > "$git_repo/file"
git_payload=$(printf '{"workspace":{"current_dir":"%s","repo":{"owner":"example","name":"demo"}}}' "$git_repo")
git_got=$(printf '%s' "$git_payload" | LIMITLINE_GIT=1 NO_COLOR=1 "$BIN" | strip_ansi)
git_got=${git_got%$'\n'}
check "git-branch" "$git_got" "example/demo demo*"

toml="$TEST_HOME/.config/limitline/config.toml"
mkdir -p "$(dirname "$toml")"
printf '%s\n' 'theme = "ascii"' 'bar_width = 5' > "$toml"
toml_got=$(LIMITLINE_CONFIG="$toml" NO_COLOR=1 "$BIN" < "$FIX/full.json" | strip_ansi)
toml_got=${toml_got%$'\n'}
check "config-toml" "$toml_got" "$ascii_got"

# Providers. Home stays on the test directory, so real session logs are not read.
cp "$FIX/providers/claude-snapshot.json" "$TEST_HOME/claude-snapshot.json"
claude_got=$(LIMITLINE_CLAUDE_SNAPSHOT="$TEST_HOME/claude-snapshot.json" "$ROOT/providers/claude")
claude_got=${claude_got%$'\n'}
check "provider-claude" "$claude_got" '{"observed_at":1762055100,"provider":"claude","source":"statusline","stale":false,"windows":[{"name":"5h","resets_at":1762062120,"used_pct":62},{"name":"7d","resets_at":1762419600,"used_pct":38}]}'

codex_prov="$TEST_HOME/codex-prov"
mkdir -p "$codex_prov"
cp "$FIX/codex/fresh.jsonl" "$codex_prov/fresh.jsonl"
codex_got=$(LIMITLINE_CODEX_DIR="$codex_prov" "$ROOT/providers/codex")
codex_got=${codex_got%$'\n'}
check "provider-codex" "$codex_got" '{"observed_at":1762054200,"provider":"codex","source":"session","stale":false,"windows":[{"name":"5h","resets_at":1762062120,"used_pct":12},{"name":"7d","resets_at":1762419600,"used_pct":55}]}'

stale_prov="$TEST_HOME/codex-stale"
mkdir -p "$stale_prov"
cp "$FIX/codex/stale.jsonl" "$stale_prov/stale.jsonl"
stale_got=$(LIMITLINE_CODEX_DIR="$stale_prov" "$ROOT/providers/codex")
stale_got=${stale_got%$'\n'}
check "provider-codex-stale" "$stale_got" '{"observed_at":1761955200,"provider":"codex","source":"session","stale":true,"windows":[]}'

cursor_got=$("$ROOT/providers/cursor")
cursor_got=${cursor_got%$'\n'}
check "provider-cursor" "$cursor_got" '{"observed_at":null,"provider":"cursor","source":"none","stale":false,"windows":[]}'

grok_root="$TEST_HOME/grok/sess"
mkdir -p "$grok_root"
cp "$FIX/providers/grok-usage.json" "$grok_root/usage.json"
grok_got=$(LIMITLINE_GROK_DIR="$TEST_HOME/grok" "$ROOT/providers/grok")
grok_got=${grok_got%$'\n'}
check "provider-grok" "$grok_got" '{"observed_at":1762055400,"provider":"grok","source":"usage.json","stale":false,"windows":[]}'

gem_got=$(LIMITLINE_GEMINI_LOG="$FIX/providers/gemini.log" "$ROOT/providers/gemini")
gem_got=${gem_got%$'\n'}
check "provider-gemini" "$gem_got" '{"observed_at":1762052400,"provider":"gemini","source":"cli.log","stale":false,"windows":[{"name":"quota","resets_at":1762066800,"used_pct":100}]}'

export LIMITLINE_CLAUDE_SNAPSHOT="$TEST_HOME/claude-snapshot.json"
export LIMITLINE_CODEX_DIR="$codex_prov"
export LIMITLINE_GROK_DIR="$TEST_HOME/grok"
export LIMITLINE_GEMINI_LOG="$FIX/providers/gemini.log"
status_got=$("$BIN" status)
check "status-table" "$status_got" "$(printf '%s\n' 'tool     limits' 'claude   5h 62% · 7d 38%' 'codex    5h 12% · 7d 55%' 'cursor   no local quota' 'grok     session tokens only' 'gemini   quota 100%')"

host_got=$("$BIN" --host prompt)
check "host-prompt" "$host_got" 'claude 5h 62% · 7d 38% | codex 5h 12% · 7d 55% | gemini quota 100%'

swift_got=$("$BIN" --host swiftbar)
printf '%s' "$swift_got" | grep -q -F '5h 62%' && printf '%s' "$swift_got" | grep -q -F -- '---' \
  && printf '%s' "$swift_got" | grep -q -F 'cursor  no local quota' \
  && check "host-swiftbar" "yes" "yes" || check "host-swiftbar" "$swift_got" "swiftbar menu"

preview_got=$("$BIN" preview)
printf '%s' "$preview_got" | grep -q -F '## minimal' && printf '%s' "$preview_got" | grep -q -F '## ascii' \
  && printf '%s' "$preview_got" | grep -q -F '## powerline' \
  && check "preview-themes" "yes" "yes" || check "preview-themes" "no" "yes"

doctor_got=$("$BIN" doctor < "$FIX/full.json")
printf '%s' "$doctor_got" | grep -q -F 'model.display_name present' \
  && printf '%s' "$doctor_got" | grep -q -F 'jq: yes' \
  && check "doctor" "yes" "yes" || check "doctor" "no" "yes"

# A status-line run writes the Claude snapshot other hosts read back.
rm -f "$XDG_CACHE_HOME/limitline/claude.json"
env -u LIMITLINE_CLAUDE_SNAPSHOT NO_COLOR=1 "$BIN" < "$FIX/full.json" >/dev/null
snap_got=$(LIMITLINE_CLAUDE_SNAPSHOT="$XDG_CACHE_HOME/limitline/claude.json" "$ROOT/providers/claude")
printf '%s' "$snap_got" | grep -q -F '"source":"statusline"' && printf '%s' "$snap_got" | grep -q -F '"used_pct":62' \
  && check "claude-snapshot" "yes" "yes" || check "claude-snapshot" "$snap_got" "snapshot"

unset LIMITLINE_CLAUDE_SNAPSHOT LIMITLINE_CODEX_DIR LIMITLINE_GROK_DIR LIMITLINE_GEMINI_LOG

if "$ROOT/integrations/codex/install.sh" | grep -q -F 'five-hour-limit'; then
  check "codex-install-print" "yes" "yes"
else
  check "codex-install-print" "no" "yes"
fi
if "$ROOT/integrations/codex/install.sh" --write >/dev/null 2>&1; then
  check "codex-install-write" "wrote" "refused"
else
  check "codex-install-write" "refused" "refused"
fi
if "$ROOT/integrations/cursor/install.sh" | grep -q -F 'statusLine'; then
  check "cursor-install-print" "yes" "yes"
else
  check "cursor-install-print" "no" "yes"
fi
if "$ROOT/integrations/grok/install.sh" | grep -q -F 'ui.status_line'; then
  check "grok-install-print" "yes" "yes"
else
  check "grok-install-print" "no" "yes"
fi

# Typical speed without the Codex scan: average of 8 runs after one warmup.
"$BIN" < "$FIX/full.json" >/dev/null
speed_ms=$(BIN="$BIN" FIX="$FIX" python3 -c '
import subprocess, time, os
bin = os.environ["BIN"]
fixture = os.environ["FIX"] + "/full.json"
env = os.environ.copy()
total = 0.0
runs = 8
for _ in range(runs):
    start = time.perf_counter()
    subprocess.run([bin], stdin=open(fixture, "rb"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, check=False)
    total += time.perf_counter() - start
print(int(total / runs * 1000))
' )
if [[ "$speed_ms" -le 50 ]]; then
  check "speed-${speed_ms}ms" "fast" "fast"
else
  check "speed-${speed_ms}ms" "slow" "fast"
fi

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[[ "$fail" -eq 0 ]]
