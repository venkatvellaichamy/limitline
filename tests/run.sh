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
  LIMITLINE_CLAUDE_SNAPSHOT LIMITLINE_GROK_DIR LIMITLINE_GEMINI_LOG LIMITLINE_STALE_MINUTES \
  LIMITLINE_PACE LIMITLINE_SPARK LIMITLINE_NUDGES LIMITLINE_FRESH LIMITLINE_VALUE LIMITLINE_VITALS \
  LIMITLINE_ALERTS LIMITLINE_QUIET LIMITLINE_SYNC_DIR LIMITLINE_HOST LIMITLINE_VALUE_FILE \
  LIMITLINE_ALERT_LOG LIMITLINE_WATCH_ONCE \
  LIMITLINE_FLEET LIMITLINE_MACHINES LIMITLINE_FLEET_LINE LIMITLINE_MACHINES_LINE \
  LIMITLINE_FLEET_TTL LIMITLINE_MACHINES_TTL LIMITLINE_PHAROS_RUNS LIMITLINE_PHAROS_HOME \
  LIMITLINE_HOSTS LIMITLINE_MACHINE_DIR LIMITLINE_MACHINES_JSON LIMITLINE_LEDGER \
  LIMITLINE_CURSOR_LOG LIMITLINE_CURSOR_DIR LIMITLINE_CURSOR_WEEK_TOKENS LIMITLINE_PS_FILE \
  LIMITLINE_SSH_TIMEOUT LIMITLINE_MEM_WARN LIMITLINE_FLEET_WINDOW LIMITLINE_LAUNCHCTL \
  LIMITLINE_LAUNCH_AGENTS XDG_DATA_HOME CLAUDE_CODE_REMOTE LINES \
  LIMITLINE_GROK LIMITLINE_GROK_SETTINGS LIMITLINE_GROK_LINE LIMITLINE_GROK_TTL \
  LIMITLINE_XAI_PLAN LIMITLINE_JOBS LIMITLINE_JOBS_TTL LIMITLINE_JOBS_DIR LIMITLINE_JOBS_LINE
: > "$TEST_HOME/empty-ps"
export LIMITLINE_PS_FILE="$TEST_HOME/empty-ps"
export LIMITLINE_REFRESH=0

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
check "provider-codex" "$codex_got" '{"observed_at":1762054200,"plan":"sample","provider":"codex","source":"session","stale":false,"windows":[{"name":"5h","resets_at":1762062120,"used_pct":12},{"name":"7d","resets_at":1762419600,"used_pct":55}]}'

stale_prov="$TEST_HOME/codex-stale"
mkdir -p "$stale_prov"
cp "$FIX/codex/stale.jsonl" "$stale_prov/stale.jsonl"
stale_got=$(LIMITLINE_CODEX_DIR="$stale_prov" "$ROOT/providers/codex")
stale_got=${stale_got%$'\n'}
check "provider-codex-stale" "$stale_got" '{"observed_at":1761955200,"provider":"codex","source":"session","stale":true,"windows":[]}'

# Many session files: the newest file has no event (a short `codex exec`), one has a
# malformed last line, one ends with a "premium" limit, and an old day folder is pruned.
many="$TEST_HOME/codex-many"
mkdir -p "$many/2025/11/02" "$many/2025/10/20"
rl() { printf '{"timestamp":"%s","type":"event_msg","payload":{"type":"token_count","rate_limits":{"limit_id":"%s","primary":{"used_percent":%s,"window_minutes":300,"resets_at":1762062120},"secondary":{"used_percent":%s,"window_minutes":10080,"resets_at":1762419600},"plan_type":"plus"}}}\n' "$1" "$2" "$3" "$4"; }
{ rl 2025-11-02T03:10:00Z codex 25 39; rl 2025-11-02T03:20:00Z codex 30 40; rl 2025-11-02T03:25:00Z premium 5 5; } > "$many/2025/11/02/rollout-a.jsonl"
printf '%s\n' '{"timestamp":"2025-11-02T03:57:00Z","type":"session_meta","payload":{"cwd":"x"}}' > "$many/2025/11/02/rollout-b.jsonl"
{ rl 2025-11-02T03:00:00Z codex 20 38; printf '%s\n' '{"timestamp":"2025-11-02T03:39:00Z","payload":{"rate_limits":{"primary":{"used_perc'; } > "$many/2025/11/02/rollout-c.jsonl"
rl 2025-10-20T03:00:00Z codex 99 99 > "$many/2025/10/20/rollout-old.jsonl"
touch -t 202511020321 "$many/2025/11/02/rollout-a.jsonl"
touch -t 202511020358 "$many/2025/11/02/rollout-b.jsonl"
touch -t 202511020340 "$many/2025/11/02/rollout-c.jsonl"
touch -t 202510200301 "$many/2025/10/20/rollout-old.jsonl"
many_got=$(LIMITLINE_CODEX_DIR="$many" "$ROOT/providers/codex")
check "provider-codex-many-files" "$many_got" '{"observed_at":1762053600,"plan":"plus","provider":"codex","source":"session","stale":false,"windows":[{"name":"5h","resets_at":1762062120,"used_pct":30},{"name":"7d","resets_at":1762419600,"used_pct":40}]}'
many_line=$(LIMITLINE_CODEX=1 LIMITLINE_CODEX_DIR="$many" LIMITLINE_NOCACHE=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "codex-many-files-jq" "$many_line" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12 │ codex 5h ·30% · 7d ·40%'
many_py=$(PATH="$nojq" LIMITLINE_CODEX=1 LIMITLINE_CODEX_DIR="$many" LIMITLINE_NOCACHE=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "codex-many-files-nojq" "$many_py" "$many_line"
many_status=$(LIMITLINE_CODEX_DIR="$many" "$BIN" status | grep '^codex')
check "codex-many-files-status" "$many_status" 'codex    5h 30% · 7d 40%'

# A 28-hour-old event: the 5h window has reset, the 7d window has not, so 7d stays.
week_dir="$TEST_HOME/codex-week"
mkdir -p "$week_dir"
printf '%s\n' '{"timestamp":"2025-11-01T00:00:00Z","payload":{"rate_limits":{"primary":{"used_percent":80,"window_minutes":300,"resets_at":1761966000},"secondary":{"used_percent":41,"window_minutes":10080,"resets_at":1762419600}}}}' > "$week_dir/r.jsonl"
touch -t 202511010001 "$week_dir/r.jsonl"
week_got=$(LIMITLINE_CODEX_DIR="$week_dir" "$ROOT/providers/codex")
check "provider-codex-7d-only" "$week_got" '{"observed_at":1761955200,"provider":"codex","source":"session","stale":false,"windows":[{"name":"7d","resets_at":1762419600,"used_pct":41}]}'
week_line=$(LIMITLINE_CODEX=1 LIMITLINE_CODEX_DIR="$week_dir" LIMITLINE_NOCACHE=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "codex-7d-only-line" "$week_line" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12 │ codex 7d ·41%'

# No resets_at: the 5h reading lasts five hours from the event, the 7d reading seven days.
nores="$TEST_HOME/codex-nores"
mkdir -p "$nores"
printf '%s\n' '{"timestamp":"2025-11-01T20:00:00Z","payload":{"rate_limits":{"primary":{"used_percent":10,"window_minutes":300},"secondary":{"used_percent":20,"window_minutes":10080}}}}' > "$nores/r.jsonl"
touch -t 202511012001 "$nores/r.jsonl"
nores_got=$(LIMITLINE_CODEX_DIR="$nores" "$ROOT/providers/codex")
check "provider-codex-no-reset" "$nores_got" '{"observed_at":1762027200,"provider":"codex","source":"session","stale":false,"windows":[{"name":"7d","used_pct":20}]}'

cursor_got=$("$ROOT/providers/cursor")
cursor_got=${cursor_got%$'\n'}
check "provider-cursor" "$cursor_got" '{"observed_at":null,"provider":"cursor","source":"none","stale":false,"windows":[]}'

grok_root="$TEST_HOME/grok/sess"
mkdir -p "$grok_root"
cp "$FIX/providers/grok-usage.json" "$grok_root/usage.json"
grok_got=$(LIMITLINE_GROK_DIR="$TEST_HOME/grok" "$ROOT/providers/grok")
grok_got=${grok_got%$'\n'}
check "provider-grok" "$grok_got" '{"observed_at":1762055400,"provider":"grok","source":"usage.json","stale":false,"week":{"cost_usd":0.0,"sessions":1,"tokens":14},"windows":[]}'

gem_got=$(LIMITLINE_GEMINI_LOG="$FIX/providers/gemini-cli.txt" "$ROOT/providers/gemini")
gem_got=${gem_got%$'\n'}
check "provider-gemini" "$gem_got" '{"observed_at":1762052400,"provider":"gemini","source":"cli.log","stale":false,"windows":[{"name":"quota","resets_at":1762066800,"used_pct":100}]}'

export LIMITLINE_CLAUDE_SNAPSHOT="$TEST_HOME/claude-snapshot.json"
export LIMITLINE_CODEX_DIR="$codex_prov"
export LIMITLINE_GROK_DIR="$TEST_HOME/grok"
export LIMITLINE_GEMINI_LOG="$FIX/providers/gemini-cli.txt"
status_got=$("$BIN" status)
check "status-table" "$status_got" "$(printf '%s\n' 'tool     limits' 'gemini   quota 100% · resets Sun 07:00' 'claude   5h 62% · 7d 38%' 'codex    5h 12% · 7d 55%' 'cursor   no local quota' 'grok     7d 14 tok · $0.00 at API rates · not a quota')"

host_got=$("$BIN" --host prompt)
check "host-prompt" "$host_got" 'gemini quota 100% · resets Sun 07:00 | claude 5h 62% · 7d 38% | codex 5h 12% · 7d 55%'

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

# Grok: plan from settings_cache.json and 7-day session tokens. Never a window or a percent.
grok_fix="$TEST_HOME/grok-fix"
cp -R "$FIX/grok" "$grok_fix"
touch -t 202601010000 "$grok_fix"/sessions/*/*/usage.json
touch -t 202601020000 "$grok_fix/sessions/proj-a/s1/usage.json"
grok_env=(LIMITLINE_GROK_DIR="$grok_fix/sessions" LIMITLINE_GROK_SETTINGS="$grok_fix/settings_cache.json")
grok_week=$(env "${grok_env[@]}" "$ROOT/providers/grok")
grok_week=${grok_week%$'\n'}
check "provider-grok-week" "$grok_week" '{"observed_at":1762055400,"plan":"SuperGrok Plus","plan_fetched_at":1762045200,"provider":"grok","source":"usage.json","stale":false,"week":{"cost_usd":3.0,"sessions":2,"tokens":1200000},"windows":[]}'
! printf '%s' "$grok_week" | grep -q -e 'secret-identity' -e 'should-not-print' \
  && check "grok-identity-hidden" "yes" "yes" || check "grok-identity-hidden" "$grok_week" "no identity or signature"
grok_plan_only=$(LIMITLINE_GROK_DIR="$TEST_HOME/missing-grok" LIMITLINE_GROK_SETTINGS="$grok_fix/settings_cache.json" "$ROOT/providers/grok")
grok_plan_only=${grok_plan_only%$'\n'}
check "provider-grok-plan-only" "$grok_plan_only" '{"observed_at":null,"plan":"SuperGrok Plus","plan_fetched_at":1762045200,"provider":"grok","source":"settings_cache","stale":false,"windows":[]}'
grok_broken=$(LIMITLINE_GROK_DIR="$TEST_HOME/missing-grok" LIMITLINE_GROK_SETTINGS="$grok_fix/settings_broken.json" "$ROOT/providers/grok")
grok_broken=${grok_broken%$'\n'}
check "provider-grok-broken-plan" "$grok_broken" '{"observed_at":null,"provider":"grok","source":"none","stale":false,"windows":[]}'
grok_nocost=$(LIMITLINE_GROK_DIR="$FIX/grok-nocost" "$ROOT/providers/grok")
grok_nocost=${grok_nocost%$'\n'}
check "provider-grok-no-cost" "$grok_nocost" '{"observed_at":1762055400,"provider":"grok","source":"usage.json","stale":false,"week":{"sessions":1,"tokens":300000},"windows":[]}'
grok_status=$(env "${grok_env[@]}" "$BIN" status)
printf '%s' "$grok_status" | grep -q -F 'grok     SuperGrok Plus · 7d 1.2M tok · $3.00 at API rates · not a quota' \
  && check "grok-status" "yes" "yes" || check "grok-status" "$grok_status" "plan, tokens, cost, not a quota"
grok_host=$(env "${grok_env[@]}" "$BIN" --host prompt)
! printf '%s' "$grok_host" | grep -q -F 'grok' \
  && check "grok-host-prompt" "yes" "yes" || check "grok-host-prompt" "$grok_host" "no grok in the quota line"
grok_watch=$(env "${grok_env[@]}" LIMITLINE_WATCH_ONCE=1 "$BIN" watch)
printf '%s' "$grok_watch" | grep -q -F '7d 1.2M tok' \
  && printf '%s' "$grok_watch" | grep -q -F 'SuperGrok Plus · 7d 1.2M tok · $3.00 at API rates · not a quota' \
  && check "grok-watch" "yes" "yes" || check "grok-watch" "$grok_watch" "grok column and block"
grok_cache="$TEST_HOME/grok-cache"
env "${grok_env[@]}" XDG_CACHE_HOME="$grok_cache" "$BIN" refresh
check "grok-refresh-line" "$(cat "$grok_cache/limitline/grok.line")" 'grok SuperGrok Plus · 7d 1.2M tok'
grok_off=$(XDG_CACHE_HOME="$grok_cache" NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "grok-segment-off-by-default" "$grok_off" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12'
grok_on=$(XDG_CACHE_HOME="$grok_cache" LIMITLINE_GROK=1 NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "grok-segment-env" "$grok_on" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12 │ grok SuperGrok Plus · 7d 1.2M tok'
grok_cfg="$TEST_HOME/grok.toml"
printf '%s\n' 'grok = "on"' > "$grok_cfg"
grok_cfg_got=$(XDG_CACHE_HOME="$grok_cache" LIMITLINE_CONFIG="$grok_cfg" NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "grok-segment-config" "$grok_cfg_got" "$grok_on"
grok_seg=$(XDG_CACHE_HOME="$grok_cache" LIMITLINE_SEGMENTS="model,grok" NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "grok-segment-named" "$grok_seg" 'Opus 5.5 │ grok SuperGrok Plus · 7d 1.2M tok'
touch -t 202001010000 "$grok_cache/limitline/grok.line"
grok_stale=$(XDG_CACHE_HOME="$grok_cache" LIMITLINE_GROK=1 NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "grok-segment-stale-hidden" "$grok_stale" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12'

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

# Pace compares percent used with percent of the window already elapsed.
pace_got=$(NO_COLOR=1 LIMITLINE_PACE=1 "$BIN" < "$FIX/full.json" | strip_ansi)
pace_got=${pace_got%$'\n'}
check "pace-week" "$pace_got" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ 5h ▓▓▓░░ +62% ↻1h42m │ 7d ▓▓░░░ ·38% ↻Thu 09:00 │ ~15%/day left for 4d │ $1.25'

ahead_got=$(NO_COLOR=1 LIMITLINE_PACE=1 "$BIN" < "$FIX/over_80.json" | strip_ansi)
ahead_got=${ahead_got%$'\n'}
check "pace-ahead" "$ahead_got" 'Opus 5.5 │ 5h ▓▓▓▓▓ !91% ↻3h15m │ 7d ▓▓▓▓░ +80% ↻Thu 09:00 │ ▲ 5h ahead of pace · ▲ 7d ahead of pace · ~5%/day left for 4d │ spend ▓▓▓▓░ !88% $18/$20'
ahead_raw=$(LIMITLINE_PACE=1 "$BIN" < "$FIX/over_80.json")
printf '%s' "$ahead_raw" | grep -q -F $'\033[31m' && printf '%s' "$ahead_raw" | grep -q -F 'ahead of pace' \
  && check "pace-ahead-colour" "yes" "yes" || check "pace-ahead-colour" "no" "yes"

under_got=$(NO_COLOR=1 LIMITLINE_PACE=1 "$BIN" < "$FIX/near_reset.json" | strip_ansi)
under_got=${under_got%$'\n'}
check "pace-under" "$under_got" 'Sonnet 4.5 │ 5h ▓▓▓▓▓ !96% ↻8m │ 7d ▓░░░░ ·10% ↻30m │ ▼ 7d under pace'
under_raw=$(LIMITLINE_PACE=1 "$BIN" < "$FIX/near_reset.json")
printf '%s' "$under_raw" | grep -q -F $'\033[32m' && printf '%s' "$under_raw" | grep -q -F 'under pace' \
  && check "pace-under-colour" "yes" "yes" || check "pace-under-colour" "no" "yes"

pace_off=$(NO_COLOR=1 LIMITLINE_PACE=0 LIMITLINE_SEGMENTS=model,pace,5h,7d "$BIN" < "$FIX/full.json" | strip_ansi)
pace_off=${pace_off%$'\n'}
check "pace-off" "$pace_off" 'Opus 5.5 │ 5h ▓▓▓░░ +62% ↻1h42m │ 7d ▓▓░░░ ·38% ↻Thu 09:00'

pace_only=$(NO_COLOR=1 LIMITLINE_SEGMENTS=model,pace "$BIN" < "$FIX/full.json" | strip_ansi)
pace_only=${pace_only%$'\n'}
check "pace-segment" "$pace_only" 'Opus 5.5 │ ~15%/day left for 4d'

pace_cfg="$TEST_HOME/.config/limitline/pace.toml"
printf '%s\n' 'pace = "on"' > "$pace_cfg"
pace_cfg_got=$(NO_COLOR=1 LIMITLINE_CONFIG="$pace_cfg" "$BIN" < "$FIX/full.json" | strip_ansi)
pace_cfg_got=${pace_cfg_got%$'\n'}
check "pace-config" "$pace_cfg_got" "$pace_got"

# Sparklines from local snapshots, including one bar per day for a week.
rm -f "$XDG_CACHE_HOME/limitline/history-5h.tsv" "$XDG_CACHE_HOME/limitline/history-7d.tsv"
mkdir -p "$XDG_CACHE_HOME/limitline"
printf '%s\n' "1762050000 10" "1762051000 30" "1762052000 50" "1762053000 70" > "$XDG_CACHE_HOME/limitline/history-5h.tsv"
python3 - << 'PY' > "$XDG_CACHE_HOME/limitline/history-7d.tsv"
now = 1762056000
today = now // 86400
for offset, pct in enumerate((12, 25, 37, 50, 62, 75)):
    print((today - 6 + offset) * 86400 + 3600, pct)
PY
spark_got=$(NO_COLOR=1 LIMITLINE_SPARK=1 "$BIN" < "$FIX/full.json" | strip_ansi)
spark_got=${spark_got%$'\n'}
check "sparkline" "$spark_got" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ 5h ▓▓▓░░ +62% ↻1h42m │ 5h ▁▃▅▆▅ 62% │ 7d ▓▓░░░ ·38% ↻Thu 09:00 │ 7d ▁▃▃▅▅▇▄ 38% │ $1.25'
rm -f "$XDG_CACHE_HOME/limitline/history-5h.tsv" "$XDG_CACHE_HOME/limitline/history-7d.tsv"

# Reset wording, and a single sparkle on the first prompt after usage falls.
fresh_got=$(NO_COLOR=1 LIMITLINE_FRESH=1 "$BIN" < "$FIX/full.json" | strip_ansi)
fresh_got=${fresh_got%$'\n'}
check "fresh-wording" "$fresh_got" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ 5h ▓▓▓░░ +62% fresh in 1h42m │ 7d ▓▓░░░ ·38% fresh Thu 09:00 │ $1.25'
rm -f "$XDG_CACHE_HOME/limitline/fresh.state"
high='{"model":{"display_name":"Opus"},"rate_limits":{"five_hour":{"used_percentage":90,"resets_at":1762062120}}}'
low='{"model":{"display_name":"Opus"},"rate_limits":{"five_hour":{"used_percentage":8,"resets_at":1762080000}}}'
first_fresh=$(printf '%s' "$high" | NO_COLOR=1 LIMITLINE_FRESH=1 "$BIN" | strip_ansi)
second_fresh=$(printf '%s' "$low" | NO_COLOR=1 LIMITLINE_FRESH=1 "$BIN" | strip_ansi)
printf '%s' "$first_fresh" | grep -q -F '✨' && check "fresh-not-yet" "no" "yes" || check "fresh-not-yet" "yes" "yes"
printf '%s' "$second_fresh" | grep -q -F '✨ Opus' && check "fresh-sparkle" "yes" "yes" || check "fresh-sparkle" "$second_fresh" "sparkle"
third_fresh=$(printf '%s' "$low" | NO_COLOR=1 LIMITLINE_FRESH=1 "$BIN" | strip_ansi)
printf '%s' "$third_fresh" | grep -q -F '✨' && check "fresh-once" "no" "yes" || check "fresh-once" "yes" "yes"

# Nudges are opt-in and stay short.
nudge_ok=$(NO_COLOR=1 LIMITLINE_NUDGES=1 "$BIN" < "$FIX/over_80.json" | strip_ansi)
printf '%s' "$nudge_ok" | grep -q -F '→ cursor ok' && check "nudge-cursor" "yes" "yes" || check "nudge-cursor" "$nudge_ok" "cursor ok"
nudge_codex=$(NO_COLOR=1 LIMITLINE_NUDGES=1 LIMITLINE_CODEX_DIR="$fresh_dir" "$BIN" < "$FIX/over_80.json" | strip_ansi)
printf '%s' "$nudge_codex" | grep -q -F '→ codex 12%' && check "nudge-codex" "yes" "yes" || check "nudge-codex" "$nudge_codex" "codex 12%"
nudge_ctx=$(NO_COLOR=1 LIMITLINE_NUDGES=1 "$BIN" < "$FIX/near_compact.json" | strip_ansi)
printf '%s' "$nudge_ctx" | grep -q -F '↯ compact soon: /compact' && check "nudge-compact" "yes" "yes" || check "nudge-compact" "$nudge_ctx" "compact"
cold_nudge=$(NO_COLOR=1 LIMITLINE_NUDGES=1 "$BIN" < "$FIX/cold_cache.json" | strip_ansi)
cold_nudge=${cold_nudge%$'\n'}
cold_want=$(cat "$FIX/cold_cache.expected")
cold_want=${cold_want%$'\n'}
check "nudge-cache-reason" "$cold_nudge" "$cold_want"
cache_off=$(printf '%s' '{"prompt_cache":{"warm":false,"last_miss_cause":{"causes":["tools"]}}}' | NO_COLOR=1 LIMITLINE_NUDGES=1 LIMITLINE_SEGMENTS=nudge "$BIN" | strip_ansi)
printf '%s' "$cache_off" | grep -q -F 'cache cold: tools' && check "nudge-cache-segment-off" "yes" "yes" || check "nudge-cache-segment-off" "$cache_off" "reason"

# Value is an estimate from a local cost file. Session text is not read.
val_file="$TEST_HOME/week.json"
printf '%s\n' '{"week_usd":412}' > "$val_file"
val_got=$(printf '%s' '{"model":{"display_name":"Opus"}}' | NO_COLOR=1 LIMITLINE_VALUE=1 LIMITLINE_VALUE_FILE="$val_file" "$BIN" | strip_ansi)
val_got=${val_got%$'\n'}
check "value-week" "$val_got" 'Opus │ ≈ $412 of value this week'
tok_file="$TEST_HOME/tokens.json"
printf '%s\n' '{"model":"opus","input_tokens":2000000,"output_tokens":0}' > "$tok_file"
tok_got=$(printf '%s' '{"model":{"display_name":"Opus"}}' | NO_COLOR=1 LIMITLINE_VALUE=1 LIMITLINE_VALUE_FILE="$tok_file" "$BIN" | strip_ansi)
tok_got=${tok_got%$'\n'}
check "value-tokens" "$tok_got" 'Opus │ ≈ $10 of value this week'

# Session vitals replace the cost segment when the switch is on.
rm -f "$XDG_CACHE_HOME/limitline/history-cost.tsv"
mkdir -p "$XDG_CACHE_HOME/limitline"
printf '%s\n' "1762050000 1.00" > "$XDG_CACHE_HOME/limitline/history-cost.tsv"
vitals_payload='{"model":{"display_name":"Opus"},"cost":{"total_cost_usd":1.25,"total_duration_ms":180000,"total_lines_added":10,"total_lines_removed":2},"context_window":{"used_percentage":40,"auto_compact_count":2}}'
vitals_got=$(printf '%s' "$vitals_payload" | NO_COLOR=1 LIMITLINE_VITALS=1 "$BIN" | strip_ansi)
vitals_got=${vitals_got%$'\n'}
check "vitals" "$vitals_got" 'Opus │ ctx ▓▓░░░ ·40% │ session 3m · compact ×2 · +10 -2 · $1.25↑'
printf '%s\n' "1762050000 1.00" > "$XDG_CACHE_HOME/limitline/history-cost.tsv"
vitals_py=$(printf '%s' "$vitals_payload" | PATH="$nojq" NO_COLOR=1 LIMITLINE_VITALS=1 "$BIN" | strip_ansi)
vitals_py=${vitals_py%$'\n'}
check "vitals-python" "$vitals_py" "$vitals_got"

# Alerts fire once per window, skip quiet hours, and can ring without a notification.
alert_log="$TEST_HOME/alerts.log"
rm -f "$alert_log" "$XDG_CACHE_HOME/limitline/alerts.tsv"
LIMITLINE_ALERTS=test LIMITLINE_ALERT_LOG="$alert_log" LIMITLINE_QUIET=9-17 "$BIN" < "$FIX/over_80.json" >/dev/null
LIMITLINE_ALERTS=test LIMITLINE_ALERT_LOG="$alert_log" LIMITLINE_QUIET=9-17 "$BIN" < "$FIX/over_80.json" >/dev/null
alert_lines=$(wc -l < "$alert_log" | tr -d ' ')
check "alert-once" "$alert_lines" "1"
check "alert-80" "$(cat "$alert_log")" "test 80 5h 91%"
printf '%s' '{"rate_limits":{"five_hour":{"used_percentage":96,"resets_at":1762067700}}}' | LIMITLINE_ALERTS=test LIMITLINE_ALERT_LOG="$alert_log" LIMITLINE_QUIET=9-17 "$BIN" >/dev/null
grep -q -F 'test 95 5h 96%' "$alert_log" && check "alert-95" "yes" "yes" || check "alert-95" "$(cat "$alert_log")" "95"
rm -f "$alert_log" "$XDG_CACHE_HOME/limitline/alerts.tsv"
LIMITLINE_ALERTS=test LIMITLINE_ALERT_LOG="$alert_log" LIMITLINE_QUIET=22-7 "$BIN" < "$FIX/over_80.json" >/dev/null
if [[ -s "$alert_log" ]]; then
  check "alert-quiet" "fired" "quiet"
else
  check "alert-quiet" "quiet" "quiet"
fi
rm -f "$alert_log" "$XDG_CACHE_HOME/limitline/alerts.tsv"
LIMITLINE_ALERTS=bell LIMITLINE_ALERT_LOG="$alert_log" LIMITLINE_QUIET=9-17 "$BIN" < "$FIX/over_80.json" >/dev/null 2>"$TEST_HOME/bell.err"
if [[ -s "$alert_log" ]] && grep -q -F $'\a' "$TEST_HOME/bell.err"; then
  check "alert-bell" "yes" "yes"
else
  check "alert-bell" "no" "yes"
fi

# Themes.
pill_got=$(NO_COLOR=1 LIMITLINE_THEME=pill "$BIN" < "$FIX/full.json" | strip_ansi)
pill_got=${pill_got%$'\n'}
check "theme-pill" "$pill_got" '⟨Opus 5.5⟩ ⟨ctx ▓▓░░░ ·41%⟩ ⟨5h ▓▓▓░░ +62% ↻1h42m⟩ ⟨7d ▓▓░░░ ·38% ↻Thu 09:00⟩ ⟨$1.25⟩'
emoji_got=$(NO_COLOR=1 LIMITLINE_THEME=emoji "$BIN" < "$FIX/full.json" | strip_ansi)
emoji_got=${emoji_got%$'\n'}
check "theme-emoji" "$emoji_got" '🧠 Opus 5.5 │ 🪟 ctx ▓▓░░░ ·41% │ ⏱ 5h ▓▓▓░░ +62% ⏳1h42m │ 📅 7d ▓▓░░░ ·38% ⏳Thu 09:00 │ 💵 $1.25'
mono_raw=$(LIMITLINE_THEME=mono "$BIN" < "$FIX/full.json")
mono_got=$(printf '%s' "$mono_raw" | strip_ansi)
mono_got=${mono_got%$'\n'}
check "theme-mono" "$mono_got" 'Opus 5.5  ctx 41%  5h 62% in 1h42m  7d 38% in Thu 09:00  $1.25'
if printf '%s' "$mono_raw" | grep -q -F $'\033'; then
  check "theme-mono-plain" "ansi" "plain"
else
  check "theme-mono-plain" "plain" "plain"
fi
theme_got=$("$BIN" theme)
printf '%s' "$theme_got" | grep -q -F '## pill' && printf '%s' "$theme_got" | grep -q -F '## emoji' \
  && printf '%s' "$theme_got" | grep -q -F '## mono' && printf '%s' "$theme_got" | grep -q -F 'LIMITLINE_THEME=pill' \
  && check "theme-picker" "yes" "yes" || check "theme-picker" "no" "yes"

# Report, watch, and a synced folder. Project names are basenames only.
printf '%s\n' "1761969600 40" "1762056000 62" > "$XDG_CACHE_HOME/limitline/history-5h.tsv"
printf '%s\n' "1762056000 4 demo" "1762052400 3 demo" "1762048800 3 widget" "1762045200 2 /Users/someone/secret" > "$XDG_CACHE_HOME/limitline/activity.tsv"
report_got=$(LIMITLINE_CLAUDE_SNAPSHOT="$TEST_HOME/claude-snapshot.json" LIMITLINE_CODEX_DIR="$codex_prov" LIMITLINE_GROK_DIR="$TEST_HOME/grok" LIMITLINE_GEMINI_LOG="$FIX/providers/gemini-cli.txt" "$BIN" report)
printf '%s' "$report_got" | grep -q -F '62%' && printf '%s' "$report_got" | grep -q -F 'demo' \
  && printf '%s' "$report_got" | grep -q -F 'widget' && printf '%s' "$report_got" | grep -q -F '1h42m' \
  && ! printf '%s' "$report_got" | grep -q -F '/Users' && ! printf '%s' "$report_got" | grep -q -F 'secret' \
  && check "report" "yes" "yes" || check "report" "$report_got" "dashboard"
md_got=$(LIMITLINE_CLAUDE_SNAPSHOT="$TEST_HOME/claude-snapshot.json" LIMITLINE_CODEX_DIR="$codex_prov" "$BIN" report --md)
printf '%s' "$md_got" | grep -q -F '# limitline report' && printf '%s' "$md_got" | grep -q -F 'demo' \
  && ! printf '%s' "$md_got" | grep -q -F '/Users' && check "report-md" "yes" "yes" || check "report-md" "$md_got" "markdown"
watch_got=$(LIMITLINE_WATCH_ONCE=1 LIMITLINE_CLAUDE_SNAPSHOT="$TEST_HOME/claude-snapshot.json" LIMITLINE_CODEX_DIR="$codex_prov" LIMITLINE_GROK_DIR="$TEST_HOME/grok" LIMITLINE_GEMINI_LOG="$FIX/providers/gemini-cli.txt" "$BIN" watch)
printf '%s' "$watch_got" | grep -q -F 'claude' && printf '%s' "$watch_got" | grep -q -F 'codex' \
  && printf '%s' "$watch_got" | grep -q -F '62%' && check "watch" "yes" "yes" || check "watch" "$watch_got" "side by side"

sync_dir="$TEST_HOME/sync"
mkdir -p "$sync_dir/macbook"
printf '%s\n' '{"observed_at":1762055100,"provider":"claude","source":"statusline","stale":false,"windows":[{"name":"5h","used_pct":80,"resets_at":1762062120},{"name":"7d","used_pct":50,"resets_at":1762419600}]}' > "$sync_dir/macbook/claude.json"
sync_got=$(LIMITLINE_HOST=mini LIMITLINE_SYNC_DIR="$sync_dir" LIMITLINE_CLAUDE_SNAPSHOT="$TEST_HOME/claude-snapshot.json" LIMITLINE_CODEX_DIR="$codex_prov" "$BIN" status)
printf '%s' "$sync_got" | grep -q -F '5h 80% ×2' && printf '%s' "$sync_got" | grep -q -F '7d 50% ×2' \
  && check "sync-merge" "yes" "yes" || check "sync-merge" "$sync_got" "merged"
test -f "$sync_dir/mini/claude.json" && check "sync-publish" "yes" "yes" || check "sync-publish" "no" "yes"

# Fleet from Pharos state files, otherwise a process list. Paths stay as basenames.
fleet_line=$(LIMITLINE_PHAROS_RUNS="$FIX/fleet/runs" "$ROOT/lib/fleet.py")
fleet_line=${fleet_line%$'\n'}
check "fleet-segment" "$fleet_line" '⚙ 3 run · 1 ✗'
stalled_line=$(LIMITLINE_PHAROS_RUNS="$FIX/fleet/stalled" "$ROOT/lib/fleet.py")
stalled_line=${stalled_line%$'\n'}
check "fleet-stalled" "$stalled_line" '⚙ 1 run ⚠'
paused_line=$(LIMITLINE_PHAROS_RUNS="$FIX/fleet/paused" "$ROOT/lib/fleet.py")
paused_line=${paused_line%$'\n'}
check "fleet-paused" "$paused_line" '⚙ ⚠'
verify_line=$(LIMITLINE_PHAROS_RUNS="$FIX/fleet/verify" "$ROOT/lib/fleet.py")
verify_line=${verify_line%$'\n'}
check "fleet-verify" "$verify_line" '⚙ 1 verify'
ps_line=$(LIMITLINE_PHAROS_RUNS="$TEST_HOME/no-such-runs" LIMITLINE_PS_FILE="$FIX/fleet/ps.txt" "$ROOT/lib/fleet.py")
ps_line=${ps_line%$'\n'}
check "fleet-process-scan" "$ps_line" '⚙ 5 run'

fleet_status=$(LIMITLINE_PHAROS_RUNS="$FIX/fleet/runs" "$BIN" status)
printf '%s' "$fleet_status" | grep -q -F '⚙ 3 run · 1 ✗' \
  && printf '%s' "$fleet_status" | grep -q -F 'run-a  cursor  demo  running  12m' \
  && printf '%s' "$fleet_status" | grep -q -F 'run-d  grok  widget  failed  30m' \
  && ! printf '%s' "$fleet_status" | grep -q -F '/var' \
  && check "fleet-status" "yes" "yes" || check "fleet-status" "$fleet_status" "runs section"

# Machines come from a cache. Refresh reads fixtures and does not open ssh.
ssh_dir="$TEST_HOME/sshbin"
mkdir -p "$ssh_dir"
printf '%s\n' '#!/bin/sh' 'echo called > "$HOME/ssh.flag"' 'exit 1' > "$ssh_dir/ssh"
chmod +x "$ssh_dir/ssh"
rm -f "$TEST_HOME/ssh.flag"
PATH="$ssh_dir:$PATH" LIMITLINE_HOSTS=mini,worker-1 LIMITLINE_MACHINE_DIR="$FIX/machines" "$BIN" refresh
if [[ -f "$TEST_HOME/ssh.flag" ]]; then
  check "machines-no-ssh" "called" "quiet"
else
  check "machines-no-ssh" "quiet" "quiet"
fi
machines_line=$(cat "$XDG_CACHE_HOME/limitline/machines.line")
machines_line=${machines_line%$'\n'}
check "machines-segment" "$machines_line" 'mini 41% free · qwen3:14b / worker-1 ∅'
LIMITLINE_HOSTS=laptop LIMITLINE_MACHINE_DIR="$FIX/machines" "$BIN" refresh
laptop_line=$(cat "$XDG_CACHE_HOME/limitline/machines.line")
laptop_line=${laptop_line%$'\n'}
check "machines-mem-warn" "$laptop_line" 'laptop 10% free · qwen3:14b ⚠'
machine_status=$(LIMITLINE_HOSTS=mini LIMITLINE_MACHINE_DIR="$FIX/machines" "$BIN" refresh >/dev/null; "$BIN" status)
printf '%s' "$machine_status" | grep -q -F 'mini 41% free · qwen3:14b · load 27% · 2 installed' \
  && check "machines-installed" "yes" "yes" || check "machines-installed" "$machine_status" "installed"
mkdir -p "$TEST_HOME/.pharos"
cp "$FIX/fleet/pharos-machines.json" "$TEST_HOME/.pharos/machines.json"
env -u LIMITLINE_HOSTS LIMITLINE_MACHINE_DIR="$FIX/machines" "$BIN" refresh
pharos_hosts=$(cat "$XDG_CACHE_HOME/limitline/machines.line")
pharos_hosts=${pharos_hosts%$'\n'}
check "machines-pharos-list" "$pharos_hosts" 'mini 41% free · qwen3:14b / worker-1 ∅'

# Warm caches stay on the hot path: one line each, no python and no ssh.
LIMITLINE_PHAROS_RUNS="$FIX/fleet/runs" LIMITLINE_HOSTS=mini LIMITLINE_MACHINE_DIR="$FIX/machines" "$BIN" refresh
hot_payload='{"model":{"display_name":"Opus"}}'
hot_got=$(printf '%s' "$hot_payload" | NO_COLOR=1 LIMITLINE_SEGMENTS=machines,fleet,model "$BIN" | strip_ansi)
hot_got=${hot_got%$'\n'}
check "hot-fleet-machines" "$hot_got" 'mini 41% free · qwen3:14b │ ⚙ 3 run · 1 ✗ │ Opus'
touch -t 202001010000 "$XDG_CACHE_HOME/limitline/fleet.line" "$XDG_CACHE_HOME/limitline/machines.line"
stale_got=$(printf '%s' "$hot_payload" | NO_COLOR=1 LIMITLINE_SEGMENTS=machines,fleet,model "$BIN" | strip_ansi)
printf '%s' "$stale_got" | grep -q -F '⚙' && check "hot-cache-stale" "shown" "hidden" || check "hot-cache-stale" "hidden" "hidden"
LIMITLINE_PHAROS_RUNS="$FIX/fleet/runs" LIMITLINE_HOSTS=mini LIMITLINE_MACHINE_DIR="$FIX/machines" "$BIN" refresh

sb_root="$TEST_HOME/sb-runs"
mkdir -p "$sb_root/run-a"
cp "$FIX/fleet/runs/run-a/state.json" "$sb_root/run-a/state.json"
printf '%s\n' 'ok' > "$sb_root/run-a/stdout.log"
swift_runs=$(LIMITLINE_PHAROS_RUNS="$sb_root" "$BIN" --host swiftbar)
printf '%s' "$swift_runs" | grep -q -F 'Fleet' && printf '%s' "$swift_runs" | grep -q -F 'bash=/usr/bin/open' \
  && printf '%s' "$swift_runs" | grep -q -F 'stdout.log' \
  && check "swiftbar-run-log" "yes" "yes" || check "swiftbar-run-log" "$swift_runs" "open log"

cursor_got=$(LIMITLINE_CURSOR_LOG="$FIX/providers/cursor-usage.jsonl" "$ROOT/providers/cursor")
cursor_got=${cursor_got%$'\n'}
check "provider-cursor-estimate" "$cursor_got" '{"observed_at":1762056000,"provider":"cursor","source":"estimate","stale":false,"windows":[{"budget":1000000,"estimate":true,"name":"7d","tokens":110000,"used_pct":11}]}'
agy_root="$TEST_HOME/agy-runs"
mkdir -p "$agy_root/run-agy"
cp "$FIX/providers/agy-state.json" "$agy_root/run-agy/state.json"
agy_got=$(LIMITLINE_GEMINI_LOG="$TEST_HOME/missing-gemini-log" LIMITLINE_PHAROS_RUNS="$agy_root" "$ROOT/providers/gemini")
agy_got=${agy_got%$'\n'}
check "provider-agy" "$agy_got" '{"observed_at":1762052400,"provider":"gemini","source":"pharos","stale":false,"windows":[{"name":"quota","resets_at":1762066800,"used_pct":100}]}'
spend_got=$(LIMITLINE_LEDGER="$FIX/providers/ledger.jsonl" "$ROOT/providers/spend")
spend_got=${spend_got%$'\n'}
check "provider-spend" "$spend_got" '{"observed_at":1762056000,"provider":"api","source":"ledger","stale":false,"windows":[{"name":"spend","usd":0.25}]}'
spend_status=$(LIMITLINE_LEDGER="$FIX/providers/ledger.jsonl" LIMITLINE_CLAUDE_SNAPSHOT="$TEST_HOME/claude-snapshot.json" LIMITLINE_CODEX_DIR="$codex_prov" LIMITLINE_GROK_DIR="$TEST_HOME/grok" LIMITLINE_GEMINI_LOG="$FIX/providers/gemini-cli.txt" "$BIN" status)
printf '%s' "$spend_status" | head -n 2 | grep -q -F 'gemini' \
  && printf '%s' "$spend_status" | grep -q -F 'api      spend $0.25' \
  && check "provider-order" "yes" "yes" || check "provider-order" "$spend_status" "constrained first"

nudge_v2=$(NO_COLOR=1 LIMITLINE_NUDGES=1 LIMITLINE_CODEX_DIR="$fresh_dir" LIMITLINE_MACHINES_JSON="$FIX/machines/idle.json" "$BIN" < "$FIX/over_80.json" | strip_ansi)
printf '%s' "$nudge_v2" | grep -q -F '→ codex 12% · mini idle' \
  && check "nudge-v2" "yes" "yes" || check "nudge-v2" "$nudge_v2" "codex and idle machine"
cfg_out=$("$BIN" config)
printf '%s' "$cfg_out" | grep -q -F 'hosts = ["mini", "worker-1"]' \
  && printf '%s' "$cfg_out" | grep -q -F 'mem_free_warn = 15' \
  && check "config-fleet" "yes" "yes" || check "config-fleet" "no" "yes"

# 0.4.1: fleet window. Live runs always count; finished runs only within fleet_window.
win_line=$(LIMITLINE_PHAROS_RUNS="$FIX/fleet/window" "$ROOT/lib/fleet.py")
check "fleet-window-default" "${win_line%$'\n'}" '⚙ 1 run · 1 verify'
win_off=$(LIMITLINE_FLEET_WINDOW=off LIMITLINE_PHAROS_RUNS="$FIX/fleet/window" "$ROOT/lib/fleet.py")
check "fleet-window-off" "${win_off%$'\n'}" '⚙ 1 run · 2 verify · 1 ✗'
win_day=$(LIMITLINE_FLEET_WINDOW=1d LIMITLINE_PHAROS_RUNS="$FIX/fleet/window" "$ROOT/lib/fleet.py")
check "fleet-window-1d" "${win_day%$'\n'}" '⚙ 1 run · 2 verify · 1 ✗'
win_cfg="$TEST_HOME/window.toml"
printf '%s\n' 'fleet_window = "30m"' > "$win_cfg"
win_cfg_got=$(LIMITLINE_CONFIG="$win_cfg" LIMITLINE_PHAROS_RUNS="$FIX/fleet/window" "$ROOT/lib/fleet.py")
check "fleet-window-config" "${win_cfg_got%$'\n'}" '⚙ 1 run'
win_status=$(LIMITLINE_PHAROS_RUNS="$FIX/fleet/window" "$BIN" status)
older_block=$(printf '%s\n' "$win_status" | sed -n '/^Older$/,$p')
runs_block=$(printf '%s\n' "$win_status" | sed -n '/^Runs$/,/^$/p')
printf '%s' "$older_block" | grep -q -F '1 verify · 1 ✗ · 1 stopped, last active over 12h ago' \
  && printf '%s' "$older_block" | grep -q -F 'old-verify  cursor  widget  awaiting-verify' \
  && printf '%s' "$runs_block" | grep -q -F 'recent-verif  cursor  demo  awaiting-verify' \
  && ! printf '%s' "$runs_block" | grep -q -F 'old-verify' \
  && check "fleet-status-older" "yes" "yes" || check "fleet-status-older" "$win_status" "Older block"
LIMITLINE_PHAROS_RUNS="$FIX/fleet/window" LIMITLINE_HOSTS= "$BIN" refresh
check "fleet-window-refresh" "$(cat "$XDG_CACHE_HOME/limitline/fleet.line")" '⚙ 1 run · 1 verify'

# A sweep can bump last_activity on a finished run; the agent's own stdout.log time wins.
sweep_root="$TEST_HOME/sweep-runs/run-swept"
mkdir -p "$sweep_root"
printf '%s\n' '{"id": "run-swept", "status": "awaiting-verify", "tool": "cursor", "repo": "demo", "started_at": "2025-11-01T09:00:00", "last_activity": 1762052400}' > "$sweep_root/state.json"
printf '%s\n' 'done' > "$sweep_root/stdout.log"
TZ=UTC touch -t 202511011000 "$sweep_root/stdout.log"
sweep_line=$(LIMITLINE_PHAROS_RUNS="$TEST_HOME/sweep-runs" "$ROOT/lib/fleet.py")
check "fleet-sweep-ignored" "${sweep_line%$'\n'}" ''
TZ=UTC touch -t 202511020300 "$sweep_root/stdout.log"
sweep_recent=$(LIMITLINE_PHAROS_RUNS="$TEST_HOME/sweep-runs" "$ROOT/lib/fleet.py")
check "fleet-log-recent" "${sweep_recent%$'\n'}" '⚙ 1 verify'

# Pharos writes naive local time. Read it as local time, not UTC.
tz_root="$TEST_HOME/tz-runs/run-tz"
mkdir -p "$tz_root"
printf '%s\n' '{"id": "run-tz", "status": "running", "tool": "codex", "repo": "demo", "started_at": "2025-11-02T09:00:00"}' > "$tz_root/state.json"
tz_status=$(TZ=Asia/Kolkata LIMITLINE_PHAROS_RUNS="$TEST_HOME/tz-runs" "$BIN" status)
printf '%s' "$tz_status" | grep -q -F 'run-tz  codex  demo  running  30m' \
  && check "fleet-local-time" "yes" "yes" || check "fleet-local-time" "$tz_status" "30m in local time"

# Machines: memory is "N% free" as memory_pressure prints it. No pressure output falls back to labelled load.
probe_line=$(LIMITLINE_HOSTS=noprobe LIMITLINE_MACHINE_DIR="$FIX/machines" "$BIN" refresh; cat "$XDG_CACHE_HOME/limitline/machines.line")
check "machines-load-label" "$probe_line" 'noprobe load 13%'
path_ok=$(cd "$ROOT/lib" && python3 -c 'import refresh; print(refresh.SCRIPT.startswith("PATH=/opt/homebrew/bin:/usr/local/bin:$PATH"))')
check "machines-probe-path" "$path_ok" "True"

# Two lines: each line is fitted to the width on its own, so line 2 does not
# push context off line 1. Payload shape from Claude Code 2.1.317 (7d only).
LIMITLINE_PHAROS_RUNS="$FIX/fleet/runs" LIMITLINE_HOSTS=mini LIMITLINE_MACHINE_DIR="$FIX/machines" "$BIN" refresh
two_fit=$(NO_COLOR=1 LIMITLINE_LINES=2 LIMITLINE_COLUMNS=80 LIMITLINE_FLEET=1 LIMITLINE_MACHINES=1 LIMITLINE_THEME=emoji "$BIN" < "$FIX/seven_day_only.json" | strip_ansi)
line_one=$(printf '%s\n' "$two_fit" | sed -n 1p)
line_two=$(printf '%s\n' "$two_fit" | sed -n 2p)
widest=$(printf '%s\n' "$two_fit" | python3 -c 'import sys; print(max(len(l) for l in sys.stdin.read().splitlines()))')
if printf '%s' "$line_one" | grep -q -F 'ctx' && printf '%s' "$line_one" | grep -q -F '7d' \
  && printf '%s' "$line_two" | grep -q -F '⚙ 3 run' && printf '%s' "$line_two" | grep -q -F 'mini 41% free' \
  && [[ "$widest" -le 80 ]]; then
  check "two-line-fit" "yes" "yes"
else
  check "two-line-fit" "$two_fit" "ctx and 7d on line 1, fleet and machines on line 2, each <= 80"
fi
one_fit=$(NO_COLOR=1 LIMITLINE_COLUMNS=64 "$BIN" < "$FIX/seven_day_only.json" | strip_ansi)
printf '%s' "$one_fit" | grep -q -F 'ctx' && printf '%s' "$one_fit" | grep -q -F '7d' \
  && check "ctx-before-spark" "yes" "yes" || check "ctx-before-spark" "$one_fit" "ctx and 7d kept at 64 columns"

# Background refresher: launchd is stubbed, plist goes under the test HOME.
lc_log="$TEST_HOME/launchctl.log"
lc_stub="$TEST_HOME/launchctl"
printf '#!/bin/sh\necho "$@" >> "%s"\nexit 0\n' "$lc_log" > "$lc_stub"
chmod +x "$lc_stub"
agents="$TEST_HOME/Library/LaunchAgents"
inst_out=$(LIMITLINE_LAUNCHCTL="$lc_stub" "$BIN" install-refresher)
plist="$agents/dev.limitline.refresh.plist"
plist_ok=$(python3 -c '
import plistlib, sys
d = plistlib.load(open(sys.argv[1], "rb"))
print(d["StartInterval"] == 60 and d["ProcessType"] == "Background" and d["LowPriorityIO"] and d["Nice"] == 10 and d["ProgramArguments"][1].endswith("refresh-launcher.py"))
' "$plist" 2>/dev/null)
if [[ "$plist_ok" == "True" ]] && grep -q 'bootstrap gui/' "$lc_log" && [[ -x "$TEST_HOME/.local/share/limitline/refresh-launcher.py" ]] \
  && printf '%s' "$inst_out" | grep -q -F 'every 60s'; then
  check "refresher-install" "yes" "yes"
else
  check "refresher-install" "$inst_out" "plist, launcher, bootstrap"
fi
launch_run=$(cd "$TEST_HOME" && LIMITLINE_PHAROS_RUNS="$FIX/fleet/window" LIMITLINE_HOSTS= python3 "$TEST_HOME/.local/share/limitline/refresh-launcher.py"; cat "$XDG_CACHE_HOME/limitline/fleet.line")
check "refresher-launcher-runs" "$launch_run" '⚙ 1 run · 1 verify'
doc_ref=$(LIMITLINE_LAUNCHCTL="$lc_stub" "$BIN" doctor < /dev/null)
printf '%s' "$doc_ref" | grep -q -F 'refresher: installed (launchd every 60s, loaded)' \
  && check "doctor-refresher" "yes" "yes" || check "doctor-refresher" "$doc_ref" "refresher installed"
LIMITLINE_LAUNCHCTL="$lc_stub" "$BIN" uninstall-refresher >/dev/null
[[ ! -f "$plist" ]] && grep -q 'bootout gui/' "$lc_log" \
  && check "refresher-uninstall" "yes" "yes" || check "refresher-uninstall" "still there" "removed"

# Doctor names each fleet source and says why a segment is empty.
rm -f "$XDG_CACHE_HOME/limitline/fleet.line" "$XDG_CACHE_HOME/limitline/machines.json"
doc_empty=$(LIMITLINE_LAUNCHCTL="$lc_stub" LIMITLINE_FLEET=1 LIMITLINE_MACHINES=1 LIMITLINE_HOSTS= LIMITLINE_PHAROS_RUNS="$TEST_HOME/no-runs" "$BIN" doctor < /dev/null)
printf '%s' "$doc_empty" | grep -q -F 'pharos runs: none; process scan sees 0 agent processes' \
  && printf '%s' "$doc_empty" | grep -q -F 'fleet: no cache yet' \
  && printf '%s' "$doc_empty" | grep -q -F 'machines: no hosts' \
  && printf '%s' "$doc_empty" | grep -q -F 'refresher: missing' \
  && printf '%s' "$doc_empty" | grep -q -F 'sync_dir: not set' \
  && check "doctor-fleet-sources" "yes" "yes" || check "doctor-fleet-sources" "$doc_empty" "sources and reasons"
doc_cloud=$(CLAUDE_CODE_REMOTE=true LIMITLINE_LAUNCHCTL="$lc_stub" "$BIN" doctor < /dev/null)
printf '%s' "$doc_cloud" | grep -q -F 'session: cloud-hosted' \
  && check "doctor-cloud" "yes" "yes" || check "doctor-cloud" "$doc_cloud" "cloud session"

# sync_dir carries fleet and machine snapshots between machines.
shared="$TEST_HOME/shared"
mkdir -p "$shared/worker-2/cockpit" "$shared/old-host/cockpit"
printf '%s\n' '{"observed_at": 1762055940, "counts": {"run": 1, "verify": 2, "failed": 0, "warn": 0, "stopped": 0}}' > "$shared/worker-2/cockpit/fleet.json"
printf '%s\n' '{"observed_at": 1762055940, "hosts": [{"name": "worker-2", "reachable": true, "free_pct": 33, "load_pct": 5, "loaded": "qwen3:14b"}]}' > "$shared/worker-2/cockpit/machines.json"
printf '%s\n' '{"observed_at": 1761900000, "counts": {"run": 9}}' > "$shared/old-host/cockpit/fleet.json"
LIMITLINE_SYNC_DIR="$shared" LIMITLINE_HOST=laptop LIMITLINE_HOSTS=mini LIMITLINE_MACHINE_DIR="$FIX/machines" \
  LIMITLINE_PHAROS_RUNS="$FIX/fleet/window" "$BIN" refresh
check "sync-fleet-merge" "$(cat "$XDG_CACHE_HOME/limitline/fleet.line")" '⚙ 2 run · 3 verify'
check "sync-machines-merge" "$(cat "$XDG_CACHE_HOME/limitline/machines.line")" 'mini 41% free · qwen3:14b / worker-2 33% free · qwen3:14b'
[[ -f "$shared/laptop/cockpit/fleet.json" && -f "$shared/laptop/cockpit/machines.json" ]] \
  && check "sync-publish-cockpit" "yes" "yes" || check "sync-publish-cockpit" "missing" "published"
# A machine with no Pharos runs and no hosts (a cloud session with the folder) still sees the others.
LIMITLINE_SYNC_DIR="$shared" LIMITLINE_HOST=cloud LIMITLINE_HOSTS= LIMITLINE_PHAROS_RUNS="$TEST_HOME/no-runs" "$BIN" refresh
check "sync-consumer-only" "$(cat "$XDG_CACHE_HOME/limitline/fleet.line") | $(cat "$XDG_CACHE_HOME/limitline/machines.line")" '⚙ 2 run · 3 verify | mini 41% free · qwen3:14b / worker-2 33% free · qwen3:14b'

# Cursor is an estimate: "~" everywhere, tokens and budget in status, ranked after measured windows.
cur_status=$(LIMITLINE_CURSOR_LOG="$FIX/providers/cursor-usage.jsonl" LIMITLINE_CLAUDE_SNAPSHOT="$TEST_HOME/claude-snapshot.json" "$BIN" status)
printf '%s' "$cur_status" | grep -q -F 'cursor   7d ~11% estimate (110k of 1.0M tokens)' \
  && check "cursor-estimate-status" "yes" "yes" || check "cursor-estimate-status" "$cur_status" "~ and tokens"
cur_host=$(LIMITLINE_CURSOR_LOG="$FIX/providers/cursor-usage.jsonl" "$BIN" --host prompt)
printf '%s' "$cur_host" | grep -q -F 'cursor 7d ~11%' \
  && check "cursor-estimate-host" "yes" "yes" || check "cursor-estimate-host" "$cur_host" "cursor 7d ~11%"
cur_report=$(LIMITLINE_CURSOR_LOG="$FIX/providers/cursor-usage.jsonl" "$BIN" report)
printf '%s' "$cur_report" | grep -q -F '~11%' \
  && check "cursor-estimate-report" "yes" "yes" || check "cursor-estimate-report" "$cur_report" "~11%"

# Shared Cursor + Grok plan (0.5). One subscription, one row, from a cache the user or a
# browser helper writes. The cache path is an override so nothing touches ~/.cache.
plan_home="$TEST_HOME/plan"
mkdir -p "$plan_home"
export LIMITLINE_XAI_PLAN="$plan_home/xai-plan.json"
export LIMITLINE_GROK_LINE="$plan_home/grok.line"
export LIMITLINE_CURSOR_LOG="$FIX/providers/cursor-usage.jsonl"
export LIMITLINE_GROK_DIR="$TEST_HOME/grok"
noplan_status=$("$BIN" status)
printf '%s' "$noplan_status" | grep -q -F 'cursor   7d ~11% estimate (110k of 1.0M tokens)' \
  && printf '%s' "$noplan_status" | grep -q -F 'grok     7d 14 tok' \
  && ! printf '%s' "$noplan_status" | grep -q -F 'cursor+grok' \
  && check "plan-absent-estimate" "yes" "yes" || check "plan-absent-estimate" "$noplan_status" "cursor estimate and grok rows"
noplan_host=$("$BIN" --host prompt)
printf '%s' "$noplan_host" | grep -q -F 'cursor 7d ~11% estimate' \
  && check "plan-absent-host-estimate" "yes" "yes" || check "plan-absent-host-estimate" "$noplan_host" "cursor 7d ~11% estimate"

set_out=$("$BIN" set xai-plan 69 --resets "2025-11-05 09:00" --plan Super)
check "set-xai-plan" "$set_out" 'cursor+grok 69% · resets Nov 5 · Super'
check "set-xai-plan-cache" "$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["used_pct"], d["resets_at"], d["observed_at"], d["plan"], d["source"])' "$LIMITLINE_XAI_PLAN")" '69 1762333200 1762056000 Super manual'
check "provider-xai-plan" "$("$ROOT/providers/xai-plan")" '{"age":0,"label":"cursor+grok","observed_at":1762056000,"plan":"Super","provider":"xai-plan","source":"manual","stale":false,"windows":[{"name":"week","resets_at":1762333200,"used_pct":69}]}'

plan_status=$("$BIN" status)
printf '%s' "$plan_status" | grep -q -F 'cursor+grok 69% · resets Nov 5 · Super · grok 7d 14 tok' \
  && ! printf '%s' "$plan_status" | grep -q -E '^cursor |^grok |estimate' \
  && check "plan-status-one-row" "yes" "yes" || check "plan-status-one-row" "$plan_status" "one cursor+grok row, no estimate"
plan_host=$("$BIN" --host prompt)
printf '%s' "$plan_host" | grep -q -F 'cursor+grok 69% · Nov 5 · grok 7d 14 tok' \
  && ! printf '%s' "$plan_host" | grep -q -F 'estimate' \
  && check "plan-host" "yes" "yes" || check "plan-host" "$plan_host" "cursor+grok 69% · Nov 5"
plan_watch=$(LIMITLINE_WATCH_ONCE=1 "$BIN" watch)
printf '%s' "$plan_watch" | grep -q -F 'cursor+grok' && ! printf '%s' "$plan_watch" | grep -q -F 'estimate' \
  && check "plan-watch" "yes" "yes" || check "plan-watch" "$plan_watch" "cursor+grok column"
check "plan-grok-line" "$(cat "$LIMITLINE_GROK_LINE")" "$(printf '%s\n%s' 'cursor+grok 69% · Nov 5 · grok 7d 14 tok' '69 0')"
plan_line=$(LIMITLINE_GROK=1 "$BIN" < "$FIX/no_rate_limits.json")
check "plan-status-line" "$(printf '%s' "$plan_line" | strip_ansi)" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12 │ cursor+grok +69% · Nov 5 · grok 7d 14 tok'
printf '%s' "$plan_line" | grep -q -F $'\033[33m+69%' \
  && check "plan-status-line-colour" "yes" "yes" || check "plan-status-line-colour" "no" "yes"
plan_seg=$(NO_COLOR=1 LIMITLINE_SEGMENTS="model,cursor+grok" "$BIN" < "$FIX/no_rate_limits.json")
check "plan-segment-alias" "$plan_seg" 'Opus 5.5 │ cursor+grok +69% · Nov 5 · grok 7d 14 tok'
plan_nudge=$(NO_COLOR=1 LIMITLINE_NUDGES=1 "$BIN" < "$FIX/over_80.json" | strip_ansi)
printf '%s' "$plan_nudge" | grep -q -F '→ cursor ok' \
  && check "plan-nudge-no-cursor-ok" "no" "yes" || check "plan-nudge-no-cursor-ok" "yes" "yes"

# Older than 6 hours: dimmed, with its age.
printf '%s\n' '{"used_pct": 69, "resets_at": 1762333200, "observed_at": 1762023600, "plan": "Super", "source": "dashboard"}' > "$LIMITLINE_XAI_PLAN"
stale_status=$("$BIN" status)
printf '%s' "$stale_status" | grep -q -F 'cursor+grok 69% · resets Nov 5 · Super · grok 7d 14 tok · 9h old' \
  && check "plan-stale-age" "yes" "yes" || check "plan-stale-age" "$stale_status" "9h old"
python3 "$ROOT/lib/refresh.py"
check "plan-stale-flags" "$(sed -n 2p "$LIMITLINE_GROK_LINE")" '69 1'
stale_line=$(LIMITLINE_GROK=1 "$BIN" < "$FIX/no_rate_limits.json")
printf '%s' "$stale_line" | grep -q -F $'\033[2mcursor+grok 69% · Nov 5 · grok 7d 14 tok · 9h old' \
  && check "plan-stale-dim" "yes" "yes" || check "plan-stale-dim" "$(printf '%s' "$stale_line" | cat -v)" "dimmed segment"

# The window reset after the reading: no percent.
printf '%s\n' '{"used_pct": 69, "resets_at": 1762020000, "observed_at": 1762016400, "source": "dashboard"}' > "$LIMITLINE_XAI_PLAN"
reset_status=$("$BIN" status)
printf '%s' "$reset_status" | grep -q -F 'cursor+grok reset Nov 1, no newer reading' && ! printf '%s' "$reset_status" | grep -q -F '69%' \
  && check "plan-reset-passed" "yes" "yes" || check "plan-reset-passed" "$reset_status" "no stale percent"

# Older than 7 days: hidden, and the labelled estimate comes back.
printf '%s\n' '{"used_pct": 69, "resets_at": 1762333200, "observed_at": 1761360000}' > "$LIMITLINE_XAI_PLAN"
old_status=$("$BIN" status)
printf '%s' "$old_status" | grep -q -F 'cursor   7d ~11% estimate' && ! printf '%s' "$old_status" | grep -q -F 'cursor+grok' \
  && check "plan-hidden-after-7d" "yes" "yes" || check "plan-hidden-after-7d" "$old_status" "estimate back"

if "$BIN" set xai-plan 150 >/dev/null 2>&1; then check "set-xai-plan-range" "accepted" "refused"; else check "set-xai-plan-range" "refused" "refused"; fi
if "$BIN" set xai-plan 50 --resets "next week" >/dev/null 2>&1; then check "set-xai-plan-date" "accepted" "refused"; else check "set-xai-plan-date" "refused" "refused"; fi
rm -rf "$plan_home"
unset LIMITLINE_XAI_PLAN LIMITLINE_GROK_LINE LIMITLINE_CURSOR_LOG LIMITLINE_GROK_DIR

# Background jobs (0.5): one JSON per job, reported by any script.
export LIMITLINE_JOBS_DIR="$TEST_HOME/jobs"
export LIMITLINE_JOBS_LINE="$TEST_HOME/jobs.line"
export LIMITLINE_HOST=mini
job_out=$("$BIN" job update mining --done 62 --total 1842 --status running)
check "job-update" "$job_out" 'mining 62/1842'
check "job-file" "$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["name"], d["machine"], d["done"], d["total"], d["status"], d["started_at"], d["updated_at"])' "$LIMITLINE_JOBS_DIR/mining.json")" 'mining mini 62 1842 running 1762056000 1762056000'
LIMITLINE_NOW=1762056060 "$BIN" job update mining --done 70 --failed 3 >/dev/null
check "job-merge" "$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["done"], d["total"], d["failed"], d["started_at"], d["updated_at"])' "$LIMITLINE_JOBS_DIR/mining.json")" '70 1842 3 1762056000 1762056060'
"$BIN" job update backup --status ok >/dev/null
check "jobs-line" "$(cat "$LIMITLINE_JOBS_LINE")" 'jobs mining 70/1842 ✗3 · backup ok 04:00'
jobs_line=$(NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json")
check "jobs-status-line" "$jobs_line" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12 │ jobs mining 70/1842 ✗3 · backup ok 04:00'
jobs_off=$(NO_COLOR=1 LIMITLINE_JOBS=off "$BIN" < "$FIX/no_rate_limits.json")
check "jobs-off" "$jobs_off" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12'
jobs_two=$(NO_COLOR=1 LIMITLINE_LINES=2 "$BIN" < "$FIX/full.json" | tail -n 1)
printf '%s' "$jobs_two" | grep -q -F 'jobs mining' && check "jobs-line-two" "yes" "yes" || check "jobs-line-two" "$jobs_two" "jobs on line 2"
jobs_status=$("$BIN" status)
printf '%s' "$jobs_status" | grep -q -F 'jobs: mining 70/1842 ✗3 · backup ok 04:00' \
  && printf '%s' "$jobs_status" | grep -q -F 'mining  mini  running  70/1842  3 failed  updated ' \
  && check "jobs-status-block" "yes" "yes" || check "jobs-status-block" "$jobs_status" "Jobs block"

# A pid that is gone makes an unfinished job "dead"; a live pid stays running.
sleep 0 &
dead_pid=$!
wait "$dead_pid" 2>/dev/null
"$BIN" job update zombie --done 5 --total 10 --pid "$dead_pid" >/dev/null
"$BIN" job update alive --pid "$$" >/dev/null
"$BIN" job update finished --status ok --pid "$dead_pid" >/dev/null
dead_list=$("$BIN" job list)
printf '%s' "$dead_list" | grep -q -F 'zombie  mini  dead  5/10' \
  && printf '%s' "$dead_list" | grep -q -F 'alive  mini  running' \
  && printf '%s' "$dead_list" | grep -q -F 'finished  mini  ok' \
  && check "job-dead-pid" "yes" "yes" || check "job-dead-pid" "$dead_list" "dead, running, ok"
other=$(LIMITLINE_HOST=worker "$BIN" job list)
printf '%s' "$other" | grep -q -F 'zombie  mini  running' \
  && check "job-other-machine-pid" "yes" "yes" || check "job-other-machine-pid" "$other" "no pid check for another machine"
python3 "$ROOT/lib/refresh.py"
printf '%s' "$(cat "$LIMITLINE_JOBS_LINE")" | grep -q -F 'zombie dead 5/10' \
  && check "jobs-refresh-dead" "yes" "yes" || check "jobs-refresh-dead" "$(cat "$LIMITLINE_JOBS_LINE")" "zombie dead"

# Finished jobs leave the line after fleet_window; job list still has them.
printf '%s\n' '{"name": "old", "machine": "mini", "status": "ok", "started_at": 1762000000, "updated_at": 1762000000}' > "$LIMITLINE_JOBS_DIR/old.json"
"$BIN" status | grep -q -F 'old  mini' && check "job-old-hidden" "shown" "hidden" || check "job-old-hidden" "hidden" "hidden"
"$BIN" job list | grep -q -F 'old  mini  ok' && check "job-list-all" "yes" "yes" || check "job-list-all" "no" "yes"
if "$BIN" job update ../escape --done 1 >/dev/null 2>&1; then check "job-name-check" "accepted" "refused"; else check "job-name-check" "refused" "refused"; fi
if "$BIN" job update ok-name --done many >/dev/null 2>&1; then check "job-number-check" "accepted" "refused"; else check "job-number-check" "refused" "refused"; fi
"$BIN" job rm old && [[ ! -f "$LIMITLINE_JOBS_DIR/old.json" ]] && check "job-rm" "yes" "yes" || check "job-rm" "no" "yes"
rm -rf "$LIMITLINE_JOBS_DIR" "$LIMITLINE_JOBS_LINE"
unset LIMITLINE_JOBS_DIR LIMITLINE_JOBS_LINE LIMITLINE_HOST

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

# Warm fleet and machine caches, still with no ssh and no provider scan.
LIMITLINE_PHAROS_RUNS="$FIX/fleet/runs" LIMITLINE_HOSTS=mini LIMITLINE_MACHINE_DIR="$FIX/machines" "$BIN" refresh
warm_ms=$(BIN="$BIN" python3 -c '
import subprocess, time, os
bin = os.environ["BIN"]
payload = b"{\"model\":{\"display_name\":\"Opus\"}}"
env = os.environ.copy()
env["NO_COLOR"] = "1"
env["LIMITLINE_SEGMENTS"] = "model,fleet,machines"
env["LIMITLINE_REFRESH"] = "0"
total = 0.0
runs = 8
subprocess.run([bin], input=payload, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, check=False)
for _ in range(runs):
    start = time.perf_counter()
    subprocess.run([bin], input=payload, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, check=False)
    total += time.perf_counter() - start
print(int(total / runs * 1000))
')
if [[ "$warm_ms" -le 50 ]]; then
  check "warm-cache-${warm_ms}ms" "fast" "fast"
else
  check "warm-cache-${warm_ms}ms" "slow" "fast"
fi

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[[ "$fail" -eq 0 ]]
