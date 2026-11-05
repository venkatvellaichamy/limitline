#!/usr/bin/env bash
# Fixture tests for limitline. ANSI colour is stripped before comparison.
set -u

ROOT=$(cd "$(dirname "$0")/.." && pwd)
BIN="$ROOT/bin/limitline"
# The status line must redraw in about 50 ms on a Mac. Shared CI runners are slower, so CI
# raises this (LIMITLINE_SPEED_MS=200); a real slowdown still fails there.
SPEED_MS="${LIMITLINE_SPEED_MS:-50}"
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
  LIMITLINE_XAI_PLAN LIMITLINE_JOBS LIMITLINE_JOBS_TTL LIMITLINE_JOBS_DIR LIMITLINE_JOBS_LINE \
  LIMITLINE_PHAROS LIMITLINE_PAGER LIMITLINE_WATCH_KEYS PAGER \
  LIMITLINE_HISTORY_DIR LIMITLINE_JOBS_HISTORY \
  LIMITLINE_GROK_LOG LIMITLINE_GROK_BIN LIMITLINE_XAI_TTL LIMITLINE_XAI_BOOT LIMITLINE_XAI_QUIET \
  LIMITLINE_XAI_TYPE_PAUSE LIMITLINE_XAI_TIMEOUT FAKE_PCT FAKE_TS FAKE_STUBBORN FAKE_SILENT \
  LIMITLINE_AGY_BIN LIMITLINE_AGY_USAGE LIMITLINE_AGY_TTL LIMITLINE_AGY_TIMEOUT LIMITLINE_CLAUDE_CACHE
: > "$TEST_HOME/empty-ps"
export LIMITLINE_PS_FILE="$TEST_HOME/empty-ps"
export LIMITLINE_REFRESH=0
# A payload without rate_limits falls back to the cached Claude 7d reading. The fixture
# renders write that cache in file order, so the fallback is off except where tested.
export LIMITLINE_CLAUDE_CACHE=0
# The Grok plan fetch starts a CLI in a pty; only the refresher tests turn it on.
export LIMITLINE_XAI_FETCH=0
# The Antigravity fetch runs agy; only the agy tests turn it on, with a fake binary.
export LIMITLINE_AGY_FETCH=0

fail=0
pass=0
# Stand in for `pharos usage`: what Pharos would write to usage.json, made from limitline's
# own readers with the current environment. limitline itself never runs them for the status line.
pharos_usage() {
  local out
  out=$(mktemp "$TEST_HOME/usage.XXXXXX")
  python3 - "$ROOT" "$out" "$@" << 'PY'
import json, os, subprocess, sys
root, out, names = sys.argv[1], sys.argv[2], sys.argv[3:]
usage = {"version": 1, "generated_at": int(os.environ.get("LIMITLINE_NOW") or 0), "plans": [], "hosts": {"hosts": []}}
for name in names:
    proc = subprocess.run([sys.executable, os.path.join(root, "providers", name)], capture_output=True, text=True)
    try:
        data = json.loads(proc.stdout or "{}")
    except ValueError:
        data = {}
    data.setdefault("provider", name)
    data.setdefault("windows", [])
    if name in ("grok", "spend"):
        usage[name] = data
    else:
        usage["plans"].append(data)
json.dump(usage, open(out, "w"))
PY
  printf '%s' "$out"
}

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

# GNU coreutils as on Linux, for the checks that broke there (CI, 2026-11-04). On a Mac
# these wrappers make stat and date answer the way GNU does; on Linux the real tools are used.
GNU_PATH="$PATH"
if [[ "$(uname -s)" == "Darwin" ]]; then
  gnu_bin="$TEST_HOME/gnubin"
  mkdir -p "$gnu_bin"
  cat > "$gnu_bin/stat" << 'SH'
#!/bin/sh
# GNU stat: -c FORMAT prints file fields; -f means --file-system and takes no argument,
# so `stat -f %m FILE` reports the file system of "%m" (missing) and of FILE, and exits 1.
if [ "$1" = "-c" ]; then
  [ "$2" = "%Y" ] || exit 1
  shift 2
  exec /usr/bin/stat -f %m "$@"
fi
if [ "$1" = "-f" ]; then
  shift
  rc=0
  for f in "$@"; do
    if [ -e "$f" ]; then
      printf '  File: "%s"\n    ID: 0 Namelen: 255 Type: ext2/ext3\n' "$f"
    else
      echo "stat: cannot read file system information for '$f'" >&2
      rc=1
    fi
  done
  exit $rc
fi
exec /usr/bin/stat "$@"
SH
  cat > "$gnu_bin/date" << 'SH'
#!/bin/sh
# GNU date: no -j; -r names a reference FILE; -d @EPOCH formats an epoch.
prev=""
for a in "$@"; do
  case "$a" in -j|-j*|-*j) echo "date: invalid option -- 'j'" >&2; exit 1 ;; esac
  if [ "$prev" = "-r" ] && [ ! -e "$a" ]; then echo "date: $a: No such file or directory" >&2; exit 1; fi
  prev="$a"
done
# Rotate the arguments, rewriting `-d @EPOCH` to BSD `-r EPOCH`; other -d forms are not emulated.
n=$#
i=0
while [ "$i" -lt "$n" ]; do
  a=$1; shift; i=$((i + 1))
  if [ "$a" = "-d" ]; then
    v=$1; shift; i=$((i + 1))
    case "$v" in @*) set -- "$@" -r "${v#@}" ;; *) exit 1 ;; esac
    continue
  fi
  set -- "$@" "$a"
done
exec /bin/date "$@"
SH
  chmod +x "$gnu_bin/stat" "$gnu_bin/date"
  GNU_PATH="$gnu_bin:$PATH"
fi

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

# A config that names its own segments renders exactly as 0.14.0 did. The .expected files
# were recorded from 0.14.0 by tests/render_legacy.sh; a missing one is recorded, not passed.
for cfg in "$FIX"/legacy/*.toml; do
  name=$(basename "$cfg" .toml)
  exp="${cfg%.toml}.expected"
  got=$(bash "$ROOT/tests/render_legacy.sh" "$cfg")
  if [[ ! -f "$exp" ]]; then
    printf '%s\n' "$got" > "$exp"
    fail=$((fail + 1))
    printf 'FAIL legacy-%s recorded (no .expected yet):\n%s\n' "$name" "$got" >&2
    continue
  fi
  check "legacy-$name" "$got" "$(cat "$exp")"
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

example_got=$(LIMITLINE_CODEX=1 LIMITLINE_PHAROS_USAGE="$(LIMITLINE_CODEX_DIR="$fresh_dir" pharos_usage codex)" LIMITLINE_NOCACHE=1 "$BIN" < "$FIX/full.json" | strip_ansi)
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
fresh_usage=$(LIMITLINE_CODEX_DIR="$fresh_dir" pharos_usage codex)
py_codex=$(PATH="$nojq" LIMITLINE_CODEX=1 LIMITLINE_PHAROS_USAGE="$fresh_usage" LIMITLINE_NOCACHE=1 "$BIN" < "$FIX/full.json" | strip_ansi)
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

# Ahead/behind: `git rev-list --left-right --count` prints "BEHIND<TAB>AHEAD". 0.14 split
# on a space, so the raw "0<TAB>2" landed in both slots (`main ↑2	0 ↓2	0`).
ab_repo="$TEST_HOME/ab"
mkdir -p "$ab_repo"
gitc() { git -C "$ab_repo" -c user.name=limitline -c user.email=limitline@example.com "$@"; }
gitc init -q -b main
gitc commit -q --allow-empty -m one
gitc branch base
gitc commit -q --allow-empty -m two
gitc commit -q --allow-empty -m three
gitc branch -q -u base main
ab_render() { printf '{"workspace":{"current_dir":"%s"}}' "$ab_repo" | LIMITLINE_GIT=1 LIMITLINE_SEGMENTS=git NO_COLOR=1 "$BIN" | strip_ansi; }
check "git-ahead-2" "$(ab_render)" "main ↑2"
gitc branch -q -f base main
gitc commit -q --allow-empty -m four
gitc commit -q --allow-empty -m five
gitc commit -q --allow-empty -m six
check "git-ahead-3" "$(ab_render)" "main ↑3"
gitc branch -q -f base main
gitc reset -q --hard base~2
check "git-behind-2" "$(ab_render)" "main ↓2"
gitc commit -q --allow-empty -m diverge
check "git-ahead-behind" "$(ab_render)" "main ↑1 ↓2"
if ab_render | grep -q $'\t'; then check "git-no-tabs" "tab in output" "no tabs"; else check "git-no-tabs" "no tabs" "no tabs"; fi
gitc branch -q -f base main
check "git-even" "$(ab_render)" "main"

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
# malformed last line, one ends with a "premium" limit, and an old file is skipped by its mtime.
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
many_usage=$(LIMITLINE_CODEX_DIR="$many" pharos_usage codex)
many_line=$(LIMITLINE_CODEX=1 LIMITLINE_PHAROS_USAGE="$many_usage" LIMITLINE_NOCACHE=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "codex-many-files-jq" "$many_line" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12 │ codex 5h ·30% · 7d ·40%'
many_py=$(PATH="$nojq" LIMITLINE_CODEX=1 LIMITLINE_PHAROS_USAGE="$many_usage" LIMITLINE_NOCACHE=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "codex-many-files-nojq" "$many_py" "$many_line"
many_status=$(LIMITLINE_TOOL=codex LIMITLINE_CODEX_DIR="$many" "$BIN" status | grep '^codex')
check "codex-many-files-status" "$(printf '%s' "$many_status" | tr -s ' ')" 'codex 5h 30% · 7d 40%'

# Real-world shape (2026-11): the newest file holds only a "premium" event whose windows
# are null. It must not hide the older "codex" event that carries the windows.
prem="$TEST_HOME/codex-premium"
mkdir -p "$prem/2025/11/02"
rl 2025-11-02T03:20:00Z codex 30 40 > "$prem/2025/11/02/rollout-a.jsonl"
printf '%s\n' '{"timestamp":"2025-11-02T03:50:00Z","type":"event_msg","payload":{"type":"token_count","rate_limits":{"limit_id":"premium","limit_name":null,"primary":null,"secondary":null,"credits":{"has_credits":false}}}}' > "$prem/2025/11/02/rollout-z.jsonl"
touch -t 202511020321 "$prem/2025/11/02/rollout-a.jsonl"
touch -t 202511020351 "$prem/2025/11/02/rollout-z.jsonl"
prem_got=$(LIMITLINE_CODEX_DIR="$prem" "$ROOT/providers/codex")
check "provider-codex-premium-null" "$prem_got" '{"observed_at":1762053600,"plan":"plus","provider":"codex","source":"session","stale":false,"windows":[{"name":"5h","resets_at":1762062120,"used_pct":30},{"name":"7d","resets_at":1762419600,"used_pct":40}]}'

# A 28-hour-old event: the 5h window has reset, the 7d window has not, so 7d stays.
week_dir="$TEST_HOME/codex-week"
mkdir -p "$week_dir"
printf '%s\n' '{"timestamp":"2025-11-01T00:00:00Z","payload":{"rate_limits":{"primary":{"used_percent":80,"window_minutes":300,"resets_at":1761966000},"secondary":{"used_percent":41,"window_minutes":10080,"resets_at":1762419600}}}}' > "$week_dir/r.jsonl"
touch -t 202511010001 "$week_dir/r.jsonl"
week_got=$(LIMITLINE_CODEX_DIR="$week_dir" "$ROOT/providers/codex")
check "provider-codex-7d-only" "$week_got" '{"observed_at":1761955200,"provider":"codex","source":"session","stale":false,"windows":[{"name":"7d","resets_at":1762419600,"used_pct":41}]}'
week_line=$(LIMITLINE_CODEX=1 LIMITLINE_PHAROS_USAGE="$(LIMITLINE_CODEX_DIR="$week_dir" pharos_usage codex)" LIMITLINE_NOCACHE=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
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

export LIMITLINE_CLAUDE_SNAPSHOT="$TEST_HOME/claude-snapshot.json"
export LIMITLINE_CODEX_DIR="$codex_prov"
export LIMITLINE_GROK_DIR="$TEST_HOME/grok"
export LIMITLINE_TOOL=codex
# Without Pharos, limitline inside Codex shows Claude and Codex only.
status_got=$("$BIN" status)
check "status-table" "$status_got" "$(printf '%s\n' 'tool     limits' 'claude   5h 62% · 7d 38%' 'codex    5h 12% · 7d 55%')"
# With Pharos, every plan Pharos measured, in the same table. Antigravity comes from Pharos only.
all_usage=$(pharos_usage claude codex cursor grok)
python3 - "$all_usage" << 'PY'
import json, sys
path = sys.argv[1]
data = json.load(open(path))
data["plans"].append({"provider": "antigravity", "label": "antigravity", "source": "live", "observed_at": 1762056000, "stale": False,
                      "windows": [{"group": "Gemini 4 Argon", "id": "argon-weekly", "name": "argon-weekly", "used_pct": 100, "resets_at": 1762464900}]})
json.dump(data, open(path, "w"))
PY
pharos_status=$(env -u LIMITLINE_TOOL LIMITLINE_PHAROS_USAGE="$all_usage" "$BIN" status)
check "status-table-pharos" "$pharos_status" "$(printf '%s\n' 'tool        limits' 'antigravity argon-weekly 100% resets Thu 21:35' 'claude      5h 62% · 7d 38%' 'codex       5h 12% · 7d 55%' 'cursor      no local quota' 'grok        7d 14 tok · $0.00 at API rates · not a quota')"
! printf '%s' "$pharos_status" | grep -q -F 'gemini ' && check "no-gemini-app-row" "yes" "yes" || check "no-gemini-app-row" "$pharos_status" "no gemini app row"

host_got=$("$BIN" --host prompt)
check "host-prompt" "$host_got" 'claude 5h 62% · 7d 38% | codex 5h 12% · 7d 55%'

swift_got=$("$BIN" --host swiftbar)
printf '%s' "$swift_got" | grep -q -F '5h 62%' && printf '%s' "$swift_got" | grep -q -F -- '---' \
  && printf '%s' "$swift_got" | grep -q -F 'codex  5h 12%' \
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

unset LIMITLINE_CLAUDE_SNAPSHOT LIMITLINE_CODEX_DIR LIMITLINE_GROK_DIR LIMITLINE_TOOL

# Grok: plan from settings_cache.json and 7-day session tokens. Never a window or a percent.
grok_fix="$TEST_HOME/grok-fix"
cp -R "$FIX/grok" "$grok_fix"
touch -t 202601010000 "$grok_fix"/sessions/*/*/usage.json
touch -t 202601020000 "$grok_fix/sessions/proj-a/s1/usage.json"
grok_env=(LIMITLINE_TOOL=grok LIMITLINE_GROK_DIR="$grok_fix/sessions" LIMITLINE_GROK_SETTINGS="$grok_fix/settings_cache.json")
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
grok_status=$(env "${grok_env[@]}" "$BIN" status | tr -s " ")
printf '%s' "$grok_status" | grep -q -F 'grok SuperGrok Plus · 7d 1.2M tok · $3.00 at API rates · not a quota' \
  && check "grok-status" "yes" "yes" || check "grok-status" "$grok_status" "plan, tokens, cost, not a quota"
grok_host=$(env "${grok_env[@]}" "$BIN" --host prompt)
! printf '%s' "$grok_host" | grep -q -F 'grok' \
  && check "grok-host-prompt" "yes" "yes" || check "grok-host-prompt" "$grok_host" "no grok in the quota line"
grok_watch=$(env "${grok_env[@]}" LIMITLINE_WATCH_ONCE=1 "$BIN" watch)
printf '%s' "$grok_watch" | grep -q -F '7d 1.2M tok' \
  && printf '%s' "$grok_watch" | grep -q -F 'SuperGrok Plus · 7d 1.2M tok · $3.00 at API rates · not a quota' \
  && check "grok-watch" "yes" "yes" || check "grok-watch" "$grok_watch" "grok column and block"
grok_cache="$TEST_HOME/grok-cache"
env "${grok_env[@]}" XDG_CACHE_HOME="$grok_cache" LIMITLINE_PHAROS_USAGE="$(env "${grok_env[@]}" pharos_usage grok)" "$BIN" refresh
check "grok-refresh-line" "$(cat "$grok_cache/limitline/grok.line")" 'grok SuperGrok Plus · 7d 1.2M tok'
grok_off=$(XDG_CACHE_HOME="$grok_cache" NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "grok-segment-off-by-default" "$grok_off" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12'
grok_on=$(XDG_CACHE_HOME="$grok_cache" LIMITLINE_GROK=1 NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "grok-segment-env" "$grok_on" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12 │ grok SuperGrok Plus · 7d 1.2M tok'
check "gnu-grok-segment-env" "$(PATH="$GNU_PATH" XDG_CACHE_HOME="$grok_cache" LIMITLINE_GROK=1 NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)" "$grok_on"
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
# The other tools' numbers come from Pharos's usage.json; without it there is no tool nudge.
nudge_none=$(NO_COLOR=1 LIMITLINE_NUDGES=1 LIMITLINE_PHAROS_USAGE="$TEST_HOME/none.json" "$BIN" < "$FIX/over_80.json" | strip_ansi)
! printf '%s' "$nudge_none" | grep -q -F '→' && check "nudge-needs-pharos" "yes" "yes" || check "nudge-needs-pharos" "$nudge_none" "no tool nudge without Pharos"
nudge_ok=$(NO_COLOR=1 LIMITLINE_NUDGES=1 LIMITLINE_PHAROS_USAGE="$(LIMITLINE_CODEX_DIR="$TEST_HOME/none" pharos_usage codex cursor)" "$BIN" < "$FIX/over_80.json" | strip_ansi)
printf '%s' "$nudge_ok" | grep -q -F '→ cursor ok' && check "nudge-cursor" "yes" "yes" || check "nudge-cursor" "$nudge_ok" "cursor ok"
nudge_codex=$(NO_COLOR=1 LIMITLINE_NUDGES=1 LIMITLINE_PHAROS_USAGE="$(LIMITLINE_CODEX_DIR="$fresh_dir" pharos_usage codex cursor)" "$BIN" < "$FIX/over_80.json" | strip_ansi)
# Codex at 5h 12% · 7d 55% is constrained by its week, so it is not offered as "codex 12%".
printf '%s' "$nudge_codex" | grep -q -F '→ cursor ok' && ! printf '%s' "$nudge_codex" | grep -q -F 'codex 12%' \
  && check "nudge-codex-week-constrains" "yes" "yes" || check "nudge-codex-week-constrains" "$nudge_codex" "→ cursor ok, no codex 12%"
nudge_room=$(NO_COLOR=1 LIMITLINE_NUDGES=1 LIMITLINE_PHAROS_USAGE="$many_usage" "$BIN" < "$FIX/over_80.json" | strip_ansi)
printf '%s' "$nudge_room" | grep -q -F '→ codex 40%' && check "nudge-codex" "yes" "yes" || check "nudge-codex" "$nudge_room" "codex 40%"
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
watch_got=$(LIMITLINE_TOOL=codex LIMITLINE_WATCH_ONCE=1 LIMITLINE_CLAUDE_SNAPSHOT="$TEST_HOME/claude-snapshot.json" LIMITLINE_CODEX_DIR="$codex_prov" LIMITLINE_GROK_DIR="$TEST_HOME/grok" LIMITLINE_GEMINI_LOG="$FIX/providers/gemini-cli.txt" "$BIN" watch)
printf '%s' "$watch_got" | grep -q -F 'claude' && printf '%s' "$watch_got" | grep -q -F 'codex' \
  && printf '%s' "$watch_got" | grep -q -F '62%' && check "watch" "yes" "yes" || check "watch" "$watch_got" "side by side"

# Review F2: a provider is as constrained as its most-used window.
f2_got=$(python3 -c 'import sys
sys.path.insert(0, sys.argv[1])
import nudge
nudge.idle_machine = lambda: ""
nudge.rows = lambda: [
    {"provider": "codex", "windows": [{"name": "5h", "used_pct": 1}, {"name": "7d", "used_pct": 100}]},
    {"provider": "cursor", "source": "estimate", "windows": [{"name": "7d", "used_pct": 30, "estimate": True}]},
]
print(nudge.suggestion())' "$ROOT/lib")
check "nudge-exhausted-window" "$f2_got" 'cursor ~30% estimate'

# Review F3: a resumed session in an old date folder still counts when its file is fresh.
resumed="$TEST_HOME/codex-resumed"
mkdir -p "$resumed/2025/10/01"
rl 2025-11-02T03:59:00Z codex 50 20 > "$resumed/2025/10/01/rollout-resumed.jsonl"
touch -t 202511020359 "$resumed/2025/10/01/rollout-resumed.jsonl"
check "provider-codex-resumed-old-folder" "$(LIMITLINE_CODEX_DIR="$resumed" "$ROOT/providers/codex")" '{"observed_at":1762055940,"plan":"plus","provider":"codex","source":"session","stale":false,"windows":[{"name":"5h","resets_at":1762062120,"used_pct":50},{"name":"7d","resets_at":1762419600,"used_pct":20}]}'

# Review F4: increasing per-request usage events are summed, not read as a running total.
printf '%s\n' '{"usage":{"input_tokens":100,"output_tokens":0}}' '{"usage":{"input_tokens":200,"output_tokens":0}}' > "$TEST_HOME/cursor-rising.jsonl"
f4_got=$(LIMITLINE_CURSOR_LOG="$TEST_HOME/cursor-rising.jsonl" LIMITLINE_CURSOR_WEEK_TOKENS=1000 "$ROOT/providers/cursor" | python3 -c 'import json,sys; w=json.load(sys.stdin)["windows"][0]; print(w["tokens"], w["used_pct"])')
check "cursor-rising-events-summed" "$f4_got" '300 30'
printf '%s\n' '{"turn":{"usage":{"input_tokens":50,"output_tokens":0}},"result":{"usage":{"input_tokens":70,"output_tokens":0}}}' > "$TEST_HOME/cursor-nested.jsonl"
f4_nested=$(LIMITLINE_CURSOR_LOG="$TEST_HOME/cursor-nested.jsonl" LIMITLINE_CURSOR_WEEK_TOKENS=1000 "$ROOT/providers/cursor" | python3 -c 'import json,sys; print(json.load(sys.stdin)["windows"][0]["tokens"])')
check "cursor-nested-usage-summed" "$f4_nested" '120'
# Records that say they are running totals keep only the last total.
printf '%s\n' '{"usage":{"cumulative":true,"input_tokens":100,"output_tokens":0}}' '{"usage":{"cumulative":true,"input_tokens":250,"output_tokens":0}}' > "$TEST_HOME/cursor-cumulative.jsonl"
f4_cum=$(LIMITLINE_CURSOR_LOG="$TEST_HOME/cursor-cumulative.jsonl" LIMITLINE_CURSOR_WEEK_TOKENS=1000 "$ROOT/providers/cursor" | python3 -c 'import json,sys; print(json.load(sys.stdin)["windows"][0]["tokens"])')
check "cursor-cumulative-last-total" "$f4_cum" '250'

# Idle terminals redraw on a timer: limitline install sets Claude Code's refreshInterval.
install_refresh=$(grep -c '"refreshInterval": *30' "$ROOT/commands/install.md")
check "install-refresh-interval" "$install_refresh" '2'

# A new Claude Code session has no rate_limits before its first reply. The 7d segment
# falls back to the reading another session cached, with its age.
seven_snap="$TEST_HOME/seven-snapshot.json"
printf '%s\n' '{"observed_at":1762055760,"provider":"claude","source":"statusline","stale":false,"windows":[{"name":"5h","used_pct":20,"resets_at":1762062120},{"name":"7d","used_pct":67,"resets_at":1762419600}]}' > "$seven_snap"
seven_new=$(LIMITLINE_CLAUDE_CACHE=1 LIMITLINE_CLAUDE_SNAPSHOT="$seven_snap" NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "claude-7d-cached-new-session" "$seven_new" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ 7d ▓▓▓░░ +67% ↻Thu 09:00 · 4m ago │ $0.12'
seven_nojq=$(PATH="$nojq" LIMITLINE_CLAUDE_CACHE=1 LIMITLINE_CLAUDE_SNAPSHOT="$seven_snap" NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "claude-7d-cached-nojq" "$seven_nojq" "$seven_new"
# A reply that carries only the 5h window keeps the cached week, and its real age.
seven_five=$(printf '%s' '{"model":{"display_name":"Opus 5.5"},"rate_limits":{"five_hour":{"used_percentage":30,"resets_at":1762062120}}}' | LIMITLINE_CLAUDE_CACHE=1 LIMITLINE_CLAUDE_SNAPSHOT="$seven_snap" NO_COLOR=1 "$BIN" | strip_ansi)
check "claude-7d-cached-five-only" "$seven_five" 'Opus 5.5 │ 5h ▓▓░░░ ·30% ↻1h42m │ 7d ▓▓▓░░ +67% ↻Thu 09:00 · 4m ago'
grep -q -F '{"name":"7d","used_pct":67,"resets_at":1762419600,"observed_at":1762055760}' "$seven_snap" \
  && check "claude-7d-cache-kept" "yes" "yes" || check "claude-7d-cache-kept" "$(cat "$seven_snap")" "7d carried with its observed_at"
seven_again=$(LIMITLINE_CLAUDE_CACHE=1 LIMITLINE_CLAUDE_SNAPSHOT="$seven_snap" NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "claude-7d-cached-age-kept" "$seven_again" "$seven_new"
# Once the cached week has reset, its percent is last week's: the segment says so instead.
printf '%s\n' '{"observed_at":1761400000,"provider":"claude","source":"statusline","stale":false,"windows":[{"name":"7d","used_pct":90,"resets_at":1761900000}]}' > "$seven_snap"
seven_old=$(LIMITLINE_CLAUDE_CACHE=1 LIMITLINE_CLAUDE_SNAPSHOT="$seven_snap" NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "claude-7d-cached-reset-passed" "$seven_old" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ 7d reset Fri 08:40 · no newer reading │ $0.12'
seven_old_py=$(PATH="$nojq" LIMITLINE_CLAUDE_CACHE=1 LIMITLINE_CLAUDE_SNAPSHOT="$seven_snap" NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json" | strip_ansi)
check "claude-7d-cached-reset-passed-nojq" "$seven_old_py" "$seven_old"
# A live 7d reading never shows an age.
seven_live=$(LIMITLINE_CLAUDE_CACHE=1 LIMITLINE_CLAUDE_SNAPSHOT="$seven_snap" NO_COLOR=1 "$BIN" < "$FIX/full.json" | strip_ansi)
check "claude-7d-live-no-age" "$seven_live" "$full_want"

# Fleet and Runs come from Pharos's summary.json; limitline reads no run files and scans no processes.
summary_fix="$TEST_HOME/summary.json"
mkdir -p "$TEST_HOME/runlogs/run-a"
printf '%s\n' 'ok' > "$TEST_HOME/runlogs/run-a/stdout.log"
make_summary() {  # make_summary <path> <today json> [<recent json>] [<jobs json>]
  printf '{"version":1,"generated_at":1762056000,"today":%s,"older":{},"oldest_open":null,"recent":%s,"jobs":%s}\n' "$2" "${3:-[]}" "${4:-[]}" > "$1"
}
make_summary "$summary_fix" '{"running":3,"failed":1}' "[{\"id\":\"run-a\",\"tool\":\"cursor\",\"repo\":\"demo\",\"status\":\"running\",\"age_s\":720,\"log\":\"$TEST_HOME/runlogs/run-a/stdout.log\"},{\"id\":\"run-d\",\"tool\":\"grok\",\"repo\":\"widget\",\"status\":\"failed\",\"age_s\":1800,\"log\":\"/nowhere/stdout.log\"}]"
export LIMITLINE_PHAROS_SUMMARY="$summary_fix"
check "fleet-segment" "$("$ROOT/lib/fleet.py")" '⚙ 3 run · 1 ✗'
make_summary "$TEST_HOME/s-warn.json" '{"running":1,"waiting_limit":1}'
check "fleet-waiting-on-limit" "$(LIMITLINE_PHAROS_SUMMARY="$TEST_HOME/s-warn.json" "$ROOT/lib/fleet.py")" '⚙ 1 run ⚠'
make_summary "$TEST_HOME/s-paused.json" '{"waiting_limit":1}'
check "fleet-paused" "$(LIMITLINE_PHAROS_SUMMARY="$TEST_HOME/s-paused.json" "$ROOT/lib/fleet.py")" '⚙ ⚠'
printf '%s\n' '{"version":1,"generated_at":1762056000,"today":{},"older":{"need_you":1},"recent":[],"jobs":[]}' > "$TEST_HOME/s-older.json"
check "fleet-counts-older-open" "$(LIMITLINE_PHAROS_SUMMARY="$TEST_HOME/s-older.json" "$ROOT/lib/fleet.py")" '⚙ 1 verify'
check "fleet-without-pharos" "$(LIMITLINE_PHAROS_SUMMARY="$TEST_HOME/none.json" "$ROOT/lib/fleet.py")" ''
ps_spy="$TEST_HOME/psbin"
mkdir -p "$ps_spy"
printf '#!/bin/sh\necho ps >> "%s/calls"\n' "$ps_spy" > "$ps_spy/ps"; chmod +x "$ps_spy/ps"
PATH="$ps_spy:$PATH" "$ROOT/lib/fleet.py" >/dev/null
[[ ! -e "$ps_spy/calls" ]] && check "fleet-no-process-scan" "yes" "yes" || check "fleet-no-process-scan" "ran ps" "no process scan"

fleet_status=$("$BIN" status)
printf '%s' "$fleet_status" | grep -q -F '⚙ 3 run · 1 ✗' \
  && printf '%s' "$fleet_status" | grep -q -F 'run-a  cursor  demo  running  12m' \
  && printf '%s' "$fleet_status" | grep -q -F 'run-d  grok  widget  failed  30m' \
  && check "fleet-status" "yes" "yes" || check "fleet-status" "$fleet_status" "runs section"

# Machines come from Pharos's usage.json; refresh copies them into the cache and never opens ssh.
ssh_dir="$TEST_HOME/sshbin"
mkdir -p "$ssh_dir"
printf '%s\n' '#!/bin/sh' 'echo called > "$HOME/ssh.flag"' 'exit 1' > "$ssh_dir/ssh"
chmod +x "$ssh_dir/ssh"
rm -f "$TEST_HOME/ssh.flag"
hosts_usage="$TEST_HOME/hosts-usage.json"
printf '%s\n' '{"version":1,"generated_at":1762056000,"plans":[],"hosts":{"hosts":[{"name":"mini","reachable":true,"free_pct":41,"load_pct":12,"loaded":"qwen3:14b"},{"name":"worker-1","reachable":false}]}}' > "$hosts_usage"
PATH="$ssh_dir:$PATH" LIMITLINE_PHAROS_USAGE="$hosts_usage" "$BIN" refresh
[[ -f "$TEST_HOME/ssh.flag" ]] && check "machines-no-ssh" "called" "quiet" || check "machines-no-ssh" "quiet" "quiet"
check "machines-from-pharos" "$(cat "$XDG_CACHE_HOME/limitline/machines.line")" 'mini 41% free · qwen3:14b / worker-1 ∅'
hot_payload='{"model":{"display_name":"Claude Opus 5.5"}}'
hot_got=$(printf '%s' "$hot_payload" | NO_COLOR=1 LIMITLINE_SEGMENTS=machines,fleet,model "$BIN" | strip_ansi)
check "hot-fleet-machines" "$hot_got" 'mini 41% free · qwen3:14b / worker-1 ∅ │ ⚙ 3 run · 1 ✗ │ Opus 5.5'
gnu_hot=$(printf '%s' "$hot_payload" | PATH="$GNU_PATH" NO_COLOR=1 LIMITLINE_SEGMENTS=machines,fleet,model "$BIN" | strip_ansi)
check "gnu-hot-fleet-machines" "$gnu_hot" "$hot_got"

swift_runs=$("$BIN" --host swiftbar)
printf '%s' "$swift_runs" | grep -q -F 'Fleet' && printf '%s' "$swift_runs" | grep -q -F 'bash=/usr/bin/open' \
  && printf '%s' "$swift_runs" | grep -q -F 'run-a/stdout.log' && ! printf '%s' "$swift_runs" | grep -q -F '/nowhere' \
  && check "swiftbar-run-log" "yes" "yes" || check "swiftbar-run-log" "$swift_runs" "open log only when the file exists"

cursor_got=$(LIMITLINE_CURSOR_LOG="$FIX/providers/cursor-usage.jsonl" "$ROOT/providers/cursor")
cursor_got=${cursor_got%$'\n'}
check "provider-cursor-estimate" "$cursor_got" '{"observed_at":1762056000,"provider":"cursor","source":"estimate","stale":false,"windows":[{"budget":1000000,"estimate":true,"name":"7d","tokens":110000,"used_pct":11}]}'
spend_got=$(LIMITLINE_LEDGER="$FIX/providers/ledger.jsonl" "$ROOT/providers/spend")
spend_got=${spend_got%$'\n'}
check "provider-spend" "$spend_got" '{"observed_at":1762056000,"provider":"api","source":"ledger","stale":false,"windows":[{"name":"spend","usd":0.25}]}'
spend_status=$(LIMITLINE_PHAROS_USAGE="$(LIMITLINE_LEDGER="$FIX/providers/ledger.jsonl" LIMITLINE_CLAUDE_SNAPSHOT="$TEST_HOME/claude-snapshot.json" LIMITLINE_CODEX_DIR="$codex_prov" LIMITLINE_GROK_DIR="$TEST_HOME/grok" pharos_usage claude codex grok spend)" "$BIN" status | tr -s " ")
printf '%s' "$spend_status" | sed -n 2p | grep -q -F 'claude' \
  && printf '%s' "$spend_status" | grep -q -F 'api spend $0.25' \
  && check "provider-order" "yes" "yes" || check "provider-order" "$spend_status" "constrained first"

nudge_v2=$(NO_COLOR=1 LIMITLINE_NUDGES=1 LIMITLINE_PHAROS_USAGE="$many_usage" LIMITLINE_MACHINES_JSON="$FIX/machines/idle.json" "$BIN" < "$FIX/over_80.json" | strip_ansi)
printf '%s' "$nudge_v2" | grep -q -F '→ codex 40% · mini idle' \
  && check "nudge-v2" "yes" "yes" || check "nudge-v2" "$nudge_v2" "codex and idle machine"
cfg_out=$("$BIN" config)
printf '%s' "$cfg_out" | grep -q -F '# fleet = "on"' && printf '%s' "$cfg_out" | grep -q -F '~/.pharos/usage.toml' \
  && ! printf '%s' "$cfg_out" | grep -q -F 'sync_dir' && ! printf '%s' "$cfg_out" | grep -q -F 'hosts = ' \
  && check "config-fleet" "yes" "yes" || check "config-fleet" "no" "yes"

# Two lines: each line is fitted to the width on its own, so line 2 does not
# push context off line 1. Payload shape from Claude Code 2.1.317 (7d only).
LIMITLINE_PHAROS_USAGE="$hosts_usage" "$BIN" refresh
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
gnu_two=$(PATH="$GNU_PATH" NO_COLOR=1 LIMITLINE_LINES=2 LIMITLINE_COLUMNS=80 LIMITLINE_FLEET=1 LIMITLINE_MACHINES=1 LIMITLINE_THEME=emoji "$BIN" < "$FIX/seven_day_only.json" | strip_ansi)
check "gnu-two-line-fit" "$gnu_two" "$two_fit"
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
launch_run=$(cd "$TEST_HOME" && LIMITLINE_PHAROS_SUMMARY="$TEST_HOME/s-warn.json" python3 "$TEST_HOME/.local/share/limitline/refresh-launcher.py"; cat "$XDG_CACHE_HOME/limitline/fleet.line")
check "refresher-launcher-runs" "$launch_run" '⚙ 1 run ⚠'
doc_ref=$(LIMITLINE_LAUNCHCTL="$lc_stub" "$BIN" doctor < /dev/null)
printf '%s' "$doc_ref" | grep -q -F 'refresher: installed (launchd every 60s, loaded)' \
  && check "doctor-refresher" "yes" "yes" || check "doctor-refresher" "$doc_ref" "refresher installed"
LIMITLINE_LAUNCHCTL="$lc_stub" "$BIN" uninstall-refresher >/dev/null
[[ ! -f "$plist" ]] && grep -q 'bootout gui/' "$lc_log" \
  && check "refresher-uninstall" "yes" "yes" || check "refresher-uninstall" "still there" "removed"

# Doctor names each fleet source and says why a segment is empty.
rm -f "$XDG_CACHE_HOME/limitline/fleet.line" "$XDG_CACHE_HOME/limitline/machines.json"
doc_empty=$(LIMITLINE_LAUNCHCTL="$lc_stub" LIMITLINE_FLEET=1 LIMITLINE_MACHINES=1 LIMITLINE_PHAROS_SUMMARY="$TEST_HOME/none.json" "$BIN" doctor < /dev/null)
printf '%s' "$doc_empty" | grep -q -F 'pharos summary: not found' \
  && printf '%s' "$doc_empty" | grep -q -F 'fleet: no cache yet' \
  && printf '%s' "$doc_empty" | grep -q -F 'machines: no hosts in Pharos' \
  && printf '%s' "$doc_empty" | grep -q -F 'refresher: missing' \
  && ! printf '%s' "$doc_empty" | grep -q -F 'sync_dir' \
  && check "doctor-fleet-sources" "yes" "yes" || check "doctor-fleet-sources" "$doc_empty" "sources and reasons"
doc_cloud=$(CLAUDE_CODE_REMOTE=true LIMITLINE_LAUNCHCTL="$lc_stub" "$BIN" doctor < /dev/null)
printf '%s' "$doc_cloud" | grep -q -F 'session: cloud-hosted' \
  && check "doctor-cloud" "yes" "yes" || check "doctor-cloud" "$doc_cloud" "cloud session"

# Cursor is an estimate: "~" everywhere, tokens and budget in status, ranked after measured windows.
cur_status=$(LIMITLINE_TOOL=cursor LIMITLINE_CURSOR_LOG="$FIX/providers/cursor-usage.jsonl" LIMITLINE_CLAUDE_SNAPSHOT="$TEST_HOME/claude-snapshot.json" "$BIN" status | tr -s " ")
printf '%s' "$cur_status" | grep -q -F 'cursor 7d ~11% estimate (110k of 1.0M tokens)' \
  && check "cursor-estimate-status" "yes" "yes" || check "cursor-estimate-status" "$cur_status" "~ and tokens"
cur_host=$(LIMITLINE_TOOL=cursor LIMITLINE_CURSOR_LOG="$FIX/providers/cursor-usage.jsonl" "$BIN" --host prompt)
printf '%s' "$cur_host" | grep -q -F 'cursor 7d ~11%' \
  && check "cursor-estimate-host" "yes" "yes" || check "cursor-estimate-host" "$cur_host" "cursor 7d ~11%"
cur_report=$(LIMITLINE_TOOL=cursor LIMITLINE_CURSOR_LOG="$FIX/providers/cursor-usage.jsonl" "$BIN" report)
printf '%s' "$cur_report" | grep -q -F '~11% estimate' \
  && check "cursor-estimate-report" "yes" "yes" || check "cursor-estimate-report" "$cur_report" "~11% estimate"
cur_nudge=$(NO_COLOR=1 LIMITLINE_NUDGES=1 LIMITLINE_PHAROS_USAGE="$(LIMITLINE_CURSOR_LOG="$FIX/providers/cursor-usage.jsonl" LIMITLINE_CODEX_DIR="$TEST_HOME/no-codex" pharos_usage codex cursor)" "$BIN" < "$FIX/over_80.json" | strip_ansi)
printf '%s' "$cur_nudge" | grep -q -F '→ cursor ~11% estimate' \
  && check "cursor-estimate-nudge" "yes" "yes" || check "cursor-estimate-nudge" "$cur_nudge" "→ cursor ~11% estimate"

# Shared Cursor + Grok plan. Live source (0.9.0): the newest "fetched credits config"
# line in the Grok log. Manual override: the xai-plan.json cache, always labelled manual.
# Every path is an override, so nothing touches ~/.grok or ~/.cache.
plan_home="$TEST_HOME/plan"
mkdir -p "$plan_home"
export LIMITLINE_XAI_PLAN="$plan_home/xai-plan.json"
export LIMITLINE_GROK_LINE="$plan_home/grok.line"
export LIMITLINE_GROK_LOG="$plan_home/unified.jsonl"
# These plan checks run as limitline inside Grok (own-tool readers, no Pharos).
export LIMITLINE_TOOL=grok
export LIMITLINE_CURSOR_LOG="$FIX/providers/cursor-usage.jsonl"
export LIMITLINE_GROK_DIR="$TEST_HOME/grok"
rm -f "$XDG_CACHE_HOME/limitline/xai-fetch.json"

# Missing log and no manual cache: no plan row, the Cursor estimate stays.
check "xai-log-missing" "$("$ROOT/providers/xai-plan")" '{"label":"cursor+grok","observed_at":null,"provider":"xai-plan","source":"none","stale":false,"windows":[]}'
noplan_status=$("$BIN" status | tr -s " ")
printf '%s' "$noplan_status" | grep -q -F 'cursor 7d ~11% estimate (110k of 1.0M tokens)' \
  && printf '%s' "$noplan_status" | grep -q -F 'grok 7d 14 tok' \
  && ! printf '%s' "$noplan_status" | grep -q -F 'cursor+grok' \
  && check "plan-absent-estimate" "yes" "yes" || check "plan-absent-estimate" "$noplan_status" "cursor estimate and grok rows"
noplan_host=$("$BIN" --host prompt)
printf '%s' "$noplan_host" | grep -q -F 'cursor 7d ~11% estimate' \
  && check "plan-absent-host-estimate" "yes" "yes" || check "plan-absent-host-estimate" "$noplan_host" "cursor 7d ~11% estimate"

# Live: the newest line that parses wins. A later marker line with a bad percent and a
# truncated one are skipped; an older 61% reading is not used.
cp "$FIX/xai/unified.jsonl" "$LIMITLINE_GROK_LOG"
check "provider-xai-live" "$("$ROOT/providers/xai-plan")" '{"age":1800,"label":"cursor+grok","observed_at":1762054200,"plan":"SuperGrok Plus","provider":"xai-plan","source":"live","stale":false,"windows":[{"name":"week","resets_at":1762492955,"used_pct":74}]}'
live_status=$("$BIN" status)
printf '%s' "$live_status" | grep -q -F 'cursor+grok 74% · resets Fri 05:22 · SuperGrok Plus · live · grok 7d 14 tok' \
  && ! printf '%s' "$live_status" | grep -q -E '^cursor |^grok |estimate|manual' \
  && check "plan-live-status" "yes" "yes" || check "plan-live-status" "$live_status" "one live cursor+grok row"
live_host=$("$BIN" --host prompt)
printf '%s' "$live_host" | grep -q -F 'cursor+grok 74% · Fri 05:22 · grok 7d 14 tok' \
  && check "plan-live-host" "yes" "yes" || check "plan-live-host" "$live_host" "cursor+grok 74% · Fri 05:22"
plan_watch=$(LIMITLINE_WATCH_ONCE=1 "$BIN" watch)
printf '%s' "$plan_watch" | grep -q -F 'cursor+grok' && ! printf '%s' "$plan_watch" | grep -q -F 'estimate' \
  && check "plan-watch" "yes" "yes" || check "plan-watch" "$plan_watch" "cursor+grok column"
python3 "$ROOT/lib/refresh.py" --no-fetch
check "plan-live-grok-line" "$(cat "$LIMITLINE_GROK_LINE")" "$(printf '%s\n%s' 'cursor+grok 74% · Fri 05:22 · grok 7d 14 tok' '74 0 live')"
plan_line=$(LIMITLINE_GROK=1 "$BIN" < "$FIX/no_rate_limits.json")
check "plan-status-line" "$(printf '%s' "$plan_line" | strip_ansi)" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12 │ cursor+grok +74% · Fri 05:22 · grok 7d 14 tok'
printf '%s' "$plan_line" | grep -q -F $'\033[33m+74%' \
  && check "plan-status-line-colour" "yes" "yes" || check "plan-status-line-colour" "$(printf '%s' "$plan_line" | cat -v)" "coloured live percent"
plan_seg=$(NO_COLOR=1 LIMITLINE_SEGMENTS="model,cursor+grok" "$BIN" < "$FIX/no_rate_limits.json")
check "plan-segment-alias" "$plan_seg" 'Opus 5.5 │ cursor+grok +74% · Fri 05:22 · grok 7d 14 tok'
plan_nudge=$(NO_COLOR=1 LIMITLINE_NUDGES=1 LIMITLINE_PHAROS_USAGE="$(pharos_usage cursor grok xai-plan)" "$BIN" < "$FIX/over_80.json" | strip_ansi)
printf '%s' "$plan_nudge" | grep -q -F '→ cursor ok' \
  && check "plan-nudge-no-cursor-ok" "no" "yes" || check "plan-nudge-no-cursor-ok" "yes" "yes"

# Live beats an older manual value.
printf '%s\n' '{"used_pct": 69, "resets_at": 1762333200, "observed_at": 1762052400, "plan": "Super", "source": "dashboard"}' > "$LIMITLINE_XAI_PLAN"
older_manual=$("$BIN" status)
printf '%s' "$older_manual" | grep -q -F 'cursor+grok 74% · resets Fri 05:22 · SuperGrok Plus · live' && ! printf '%s' "$older_manual" | grep -q -F '69%' \
  && check "plan-live-over-older-manual" "yes" "yes" || check "plan-live-over-older-manual" "$older_manual" "live 74%"

# A newer manual value is shown, but labelled manual and dimmed, never as live.
set_out=$("$BIN" set xai-plan 69 --resets "2025-11-05 09:00" --plan Super)
check "set-xai-plan" "$set_out" 'cursor+grok 69% · manual · resets Wed 09:00 · Super'
check "set-xai-plan-cache" "$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["used_pct"], d["resets_at"], d["observed_at"], d["plan"], d["source"])' "$LIMITLINE_XAI_PLAN")" '69 1762333200 1762056000 Super manual'
check "provider-xai-manual" "$("$ROOT/providers/xai-plan")" '{"age":0,"label":"cursor+grok","observed_at":1762056000,"plan":"Super","provider":"xai-plan","source":"manual","stale":false,"windows":[{"name":"week","resets_at":1762333200,"used_pct":69}]}'
check "plan-manual-grok-line" "$(cat "$LIMITLINE_GROK_LINE")" "$(printf '%s\n%s' 'cursor+grok 69% · manual · Wed 09:00 · grok 7d 14 tok' '69 1 manual')"
manual_line=$(LIMITLINE_GROK=1 "$BIN" < "$FIX/no_rate_limits.json")
printf '%s' "$manual_line" | grep -q -F $'\033[2mcursor+grok 69% · manual · Wed 09:00 · grok 7d 14 tok' \
  && check "plan-manual-dim" "yes" "yes" || check "plan-manual-dim" "$(printf '%s' "$manual_line" | cat -v)" "dimmed manual segment"
# A cache with no source at all is still manual.
printf '%s\n' '{"used_pct": 69, "resets_at": 1762333200, "observed_at": 1762056000}' > "$LIMITLINE_XAI_PLAN"
check "plan-manual-default-source" "$("$ROOT/providers/xai-plan" | python3 -c 'import json,sys; print(json.load(sys.stdin)["source"])')" 'manual'
rm -f "$LIMITLINE_XAI_PLAN"

# Huge log: the line inside the last 512 KB, and one just past it (full-scan fallback).
python3 - "$plan_home/huge-tail.jsonl" "$plan_home/huge-deep.jsonl" "$FIX/xai/unified.jsonl" << 'PY'
import sys
line = open(sys.argv[3]).read().splitlines()[2] + "\n"
filler = '{"ts":"2025-11-02T03:00:00.000Z","msg":"render: frame","ctx":{"pad":"%s"}}\n' % ("x" * 200)
with open(sys.argv[1], "w") as h:
    h.write(filler * 14000)
    h.write(line.replace("74.0", "75.0"))
    h.write(filler * 100)
with open(sys.argv[2], "w") as h:
    h.write(filler * 14000)
    h.write(line.replace("74.0", "76.0"))
    h.write(filler * 2800)
PY
huge_tail=$(LIMITLINE_GROK_LOG="$plan_home/huge-tail.jsonl" "$ROOT/providers/xai-plan" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["windows"][0]["used_pct"], d["source"])')
check "xai-huge-log-tail" "$huge_tail" '75 live'
huge_deep=$(LIMITLINE_GROK_LOG="$plan_home/huge-deep.jsonl" "$ROOT/providers/xai-plan" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["windows"][0]["used_pct"], d["source"])')
check "xai-huge-log-past-tail" "$huge_deep" '76 live'
deep_gap=$(python3 -c 'import os,sys; print(os.path.getsize(sys.argv[1]) - open(sys.argv[1],"rb").read().rfind(b"fetched credits") > 512*1024)' "$plan_home/huge-deep.jsonl")
check "xai-huge-log-past-tail-is-deep" "$deep_gap" 'True'
huge_ms=$(LIMITLINE_GROK_LOG="$plan_home/huge-tail.jsonl" python3 -c '
import subprocess, time, sys
start = time.perf_counter()
subprocess.run([sys.argv[1]], stdout=subprocess.DEVNULL)
print(int((time.perf_counter() - start) * 1000))' "$ROOT/providers/xai-plan")
[[ "$huge_ms" -le 500 ]] && check "xai-huge-log-fast" "yes" "yes" || check "xai-huge-log-fast" "${huge_ms}ms" "under 500ms"

# Older than 6 hours: dimmed, with its age.
sed 's/2025-11-02T03:30:00.000Z/2025-11-01T19:00:00.000Z/' "$FIX/xai/unified.jsonl" | grep -v 'creditUsagePercent":61' > "$LIMITLINE_GROK_LOG"
stale_status=$("$BIN" status)
printf '%s' "$stale_status" | grep -q -F 'cursor+grok 74% · resets Fri 05:22 · SuperGrok Plus · live · grok 7d 14 tok · 9h old' \
  && check "plan-stale-age" "yes" "yes" || check "plan-stale-age" "$stale_status" "9h old"
python3 "$ROOT/lib/refresh.py" --no-fetch
check "plan-stale-flags" "$(sed -n 2p "$LIMITLINE_GROK_LINE")" '74 1 live'
stale_line=$(LIMITLINE_GROK=1 "$BIN" < "$FIX/no_rate_limits.json")
printf '%s' "$stale_line" | grep -q -F $'\033[2mcursor+grok 74% · Fri 05:22 · grok 7d 14 tok · 9h old' \
  && check "plan-stale-dim" "yes" "yes" || check "plan-stale-dim" "$(printf '%s' "$stale_line" | cat -v)" "dimmed segment"

# The window reset after the reading: no percent.
printf '%s\n' '{"ts":"2025-11-01T17:00:00.000Z","msg":"billing: fetched credits config","ctx":{"config":{"creditUsagePercent":74.0,"currentPeriod":{"end":"2025-11-01T18:00:00.000+00:00"}}}}' > "$LIMITLINE_GROK_LOG"
reset_status=$("$BIN" status)
printf '%s' "$reset_status" | grep -q -F 'cursor+grok reset Sat 18:00, no newer reading' && ! printf '%s' "$reset_status" | grep -q -F '74%' \
  && check "plan-reset-passed" "yes" "yes" || check "plan-reset-passed" "$reset_status" "no stale percent"

# Older than 7 days: hidden, and the labelled estimate comes back.
printf '%s\n' '{"ts":"2025-10-25T00:00:00.000Z","msg":"billing: fetched credits config","ctx":{"config":{"creditUsagePercent":74.0,"currentPeriod":{"end":"2025-11-07T05:22:35.070+00:00"}}}}' > "$LIMITLINE_GROK_LOG"
old_status=$("$BIN" status | tr -s " ")
printf '%s' "$old_status" | grep -q -F 'cursor 7d ~11% estimate' && ! printf '%s' "$old_status" | grep -q -F 'cursor+grok' \
  && check "plan-hidden-after-7d" "yes" "yes" || check "plan-hidden-after-7d" "$old_status" "estimate back"

if "$BIN" set xai-plan 150 >/dev/null 2>&1; then check "set-xai-plan-range" "accepted" "refused"; else check "set-xai-plan-range" "refused" "refused"; fi
if "$BIN" set xai-plan 50 --resets "next week" >/dev/null 2>&1; then check "set-xai-plan-date" "accepted" "refused"; else check "set-xai-plan-date" "refused" "refused"; fi
rm -f "$LIMITLINE_XAI_PLAN"

# limitline schedule: com.limitline.refresh every 15 minutes, launchd stubbed.
sched_out=$(LIMITLINE_LAUNCHCTL="$lc_stub" "$BIN" schedule install)
sched_plist="$agents/com.limitline.refresh.plist"
sched_ok=$(python3 -c '
import plistlib, sys
d = plistlib.load(open(sys.argv[1], "rb"))
print(d["Label"] == "com.limitline.refresh" and d["StartInterval"] == 900 and d["ProgramArguments"][1].endswith("schedule-launcher.py"))
' "$sched_plist" 2>/dev/null)
if [[ "$sched_ok" == "True" ]] && [[ -x "$TEST_HOME/.local/share/limitline/schedule-launcher.py" ]] \
  && printf '%s' "$sched_out" | grep -q -F 'installed com.limitline.refresh: limitline refresh every 15 minutes'; then
  check "schedule-install" "yes" "yes"
else
  check "schedule-install" "$sched_out" "plist every 900s, launcher"
fi
check "schedule-status" "$(LIMITLINE_LAUNCHCTL="$lc_stub" "$BIN" schedule status)" 'installed: launchd every 15 minutes, loaded'
LIMITLINE_LAUNCHCTL="$lc_stub" "$BIN" schedule uninstall >/dev/null
[[ ! -f "$sched_plist" && ! -f "$TEST_HOME/.local/share/limitline/schedule-launcher.py" ]] \
  && check "schedule-uninstall" "yes" "yes" || check "schedule-uninstall" "still there" "removed"
check "schedule-status-missing" "$(LIMITLINE_LAUNCHCTL="$lc_stub" "$BIN" schedule status)" 'missing: not installed (limitline schedule install)'

rm -rf "$plan_home"
unset LIMITLINE_TOOL
unset LIMITLINE_XAI_PLAN LIMITLINE_GROK_LINE LIMITLINE_CURSOR_LOG LIMITLINE_GROK_DIR LIMITLINE_GROK_LOG

# Reported jobs moved to Pharos (`pharos job update`); limitline shows them from summary.json.
job_moved=$("$BIN" job update mining --done 1 2>&1); job_code=$?
[[ "$job_code" -ne 0 ]] && printf '%s' "$job_moved" | grep -q -F 'pharos job update' \
  && check "job-moved-to-pharos" "yes" "yes" || check "job-moved-to-pharos" "$job_code $job_moved" "points at pharos job"
make_summary "$TEST_HOME/s-jobs.json" '{"running":3,"failed":1}' '[]' '[{"name":"mining","machine":"mini","status":"running","kind":"active","done":70,"total":1842,"failed":3,"text":"mining 70/1842 ✗3","log":"mining.log"},{"name":"backup","machine":"mini","status":"ok","kind":"ok","text":"backup ok 04:00"}]'
export LIMITLINE_PHAROS_SUMMARY="$TEST_HOME/s-jobs.json"
"$BIN" refresh >/dev/null
check "jobs-line" "$(cat "$XDG_CACHE_HOME/limitline/jobs.line")" 'jobs mining 70/1842 ✗3 · backup ok 04:00'
jobs_line=$(NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json")
check "jobs-status-line" "$jobs_line" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12 │ jobs mining 70/1842 ✗3 · backup ok 04:00'
check "gnu-jobs-status-line" "$(PATH="$GNU_PATH" NO_COLOR=1 "$BIN" < "$FIX/no_rate_limits.json")" "$jobs_line"
jobs_off=$(NO_COLOR=1 LIMITLINE_JOBS=off "$BIN" < "$FIX/no_rate_limits.json")
check "jobs-off" "$jobs_off" 'Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12'
jobs_two=$(NO_COLOR=1 LIMITLINE_LINES=2 "$BIN" < "$FIX/full.json" | tail -n 1)
printf '%s' "$jobs_two" | grep -q -F 'jobs mining' && check "jobs-line-two" "yes" "yes" || check "jobs-line-two" "$jobs_two" "jobs on line 2"
jobs_status=$("$BIN" status)
printf '%s' "$jobs_status" | grep -q -F 'jobs: mining 70/1842 ✗3 · backup ok 04:00' \
  && printf '%s' "$jobs_status" | grep -q -F 'mining  mini  running  70/1842  mining.log' \
  && check "jobs-status-block" "yes" "yes" || check "jobs-status-block" "$jobs_status" "Jobs block from Pharos"
export LIMITLINE_PHAROS_SUMMARY="$summary_fix"
"$BIN" refresh >/dev/null

# Watch (read-only): rows from Pharos's summary, logs in a pager, and keys that would act say so.
pharos_spy="$TEST_HOME/pharos-spy"
mkdir -p "$pharos_spy"
printf '#!/bin/sh\necho "$@" >> "%s/calls"\n' "$pharos_spy" > "$pharos_spy/pharos"; chmod +x "$pharos_spy/pharos"
tui_out=$(PATH="$pharos_spy:$PATH" LIMITLINE_PAGER=cat LIMITLINE_WATCH_KEYS="l r down s P l q" "$BIN" watch)
printf '%s' "$tui_out" | grep -q -F '› run-a  cursor  demo  running  12m' \
  && printf '%s' "$tui_out" | grep -q -F '> logs run-a' && printf '%s' "$tui_out" | grep -q -x 'ok' \
  && printf '%s' "$tui_out" | grep -q -F '> read-only: use Pharos (pharos resume|stop run-a' \
  && printf '%s' "$tui_out" | grep -q -F '> run-d: no log file here' \
  && check "tui-read-only" "yes" "yes" || check "tui-read-only" "$tui_out" "rows, log, read-only messages"
[[ ! -e "$pharos_spy/calls" ]] && check "tui-never-runs-pharos" "yes" "yes" || check "tui-never-runs-pharos" "$(cat "$pharos_spy/calls")" "no pharos call"
tui_none=$(LIMITLINE_PHAROS_SUMMARY="$TEST_HOME/none.json" LIMITLINE_WATCH_KEYS="q" "$BIN" watch)
printf '%s' "$tui_none" | grep -q -F '(no recent Pharos runs or jobs)' \
  && check "tui-no-pharos" "yes" "yes" || check "tui-no-pharos" "$tui_none" "empty list"
pty_got=$(HOME="$TEST_HOME" python3 "$ROOT/tests/pty_watch.py" "$BIN")
check "tui-pty" "$pty_got" "exited selected-second cursor-restored"

# History is Pharos's (`pharos usage --report`); limitline shows ~/.pharos/usage-report.json.
report_fix="$TEST_HOME/usage-report.json"
printf '%s\n' '{"generated_at":1762056000,"since":"2025-10-06","plans":[{"plan":"claude","weeks":[{"week":"2025-10-20","peak_pct":40},{"week":"2025-10-27","peak_pct":100},{"week":"2025-11-03","peak_pct":70}],"weeks_measured":3,"avg_peak_pct":70,"weeks_at_limit":1,"weeks_over_cap":1,"price_month":200,"unused_month":60}]}' > "$report_fix"
check "history-from-pharos" "$(LIMITLINE_PHAROS_REPORT="$report_fix" "$BIN" history | sed -n 3p)" 'claude       ▄█▆  avg peak 70% · 1 at limit · 1 over 75% · $60/month unused'
check "report-week-plan" "$(LIMITLINE_PHAROS_REPORT="$report_fix" "$BIN" report --week | sed -n 3p)" "claude: this week's peak 70%, 1 weeks at the limit of 3 measured"
LIMITLINE_PHAROS_REPORT="$report_fix" "$BIN" report --week --md | grep -q -F "# limitline weekly report" \
  && check "report-week-md" "yes" "yes" || check "report-week-md" "no" "markdown"
LIMITLINE_PHAROS_REPORT="$TEST_HOME/none.json" "$BIN" history | grep -q -F 'no usage history from Pharos yet' \
  && check "history-empty" "yes" "yes" || check "history-empty" "no" "empty message"
hist_spy="$TEST_HOME/hist-spy"
LIMITLINE_HISTORY_DIR="$hist_spy" LIMITLINE_TOOL=codex LIMITLINE_CLAUDE_SNAPSHOT="$TEST_HOME/claude-snapshot.json" LIMITLINE_CODEX_DIR="$codex_prov" "$BIN" status >/dev/null
[[ ! -e "$hist_spy" ]] && check "status-keeps-no-plan-history" "yes" "yes" || check "status-keeps-no-plan-history" "wrote $(ls "$hist_spy")" "no plan history in limitline"
unset LIMITLINE_HISTORY_DIR LIMITLINE_JOBS_HISTORY LIMITLINE_JOBS_DIR LIMITLINE_JOBS_LINE LIMITLINE_HOST

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
if [[ "$speed_ms" -le "$SPEED_MS" ]]; then
  check "speed-${speed_ms}ms" "fast" "fast"
else
  check "speed-${speed_ms}ms" "slow" "fast"
fi

# Warm fleet and machine caches, still with no ssh and no provider scan.
"$BIN" refresh
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
if [[ "$warm_ms" -le "$SPEED_MS" ]]; then
  check "warm-cache-${warm_ms}ms" "fast" "fast"
else
  check "warm-cache-${warm_ms}ms" "slow" "fast"
fi

# A warm jobs line costs one stat and one read on the status line.
jobs_speed_dir="$TEST_HOME/speed-jobs"
LIMITLINE_JOBS_DIR="$jobs_speed_dir" LIMITLINE_JOBS_LINE="$TEST_HOME/speed-jobs.line" "$BIN" job update mining --done 1 --total 9 >/dev/null
jobs_ms=$(BIN="$BIN" LIMITLINE_JOBS_DIR="$jobs_speed_dir" LIMITLINE_JOBS_LINE="$TEST_HOME/speed-jobs.line" python3 -c '
import subprocess, time, os
bin = os.environ["BIN"]
payload = b"{\"model\":{\"display_name\":\"Opus\"}}"
env = os.environ.copy()
env["NO_COLOR"] = "1"
env["LIMITLINE_SEGMENTS"] = "model,jobs"
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
if [[ "$jobs_ms" -le "$SPEED_MS" ]]; then
  check "jobs-warm-${jobs_ms}ms" "fast" "fast"
else
  check "jobs-warm-${jobs_ms}ms" "slow" "fast"
fi

# Five lines: line 1 is the session only; lines 2-5 come from lib/fivelines.py.
five_cache="$TEST_HOME/five-cache"; mkdir -p "$five_cache/limitline" "$TEST_HOME/five-pharos/runs"
printf 'cursor+grok 81%% · Thu 23:22 · grok 7d 1M tok\n81 0 live\n' > "$five_cache/limitline/grok.line"
touch -t 202511020359 "$five_cache/limitline/grok.line"  # a minute before LIMITLINE_NOW (TZ=UTC)
printf '%s' '{"version":1,"generated_at":1762056000,"plans":[],"hosts":{"hosts":[{"name":"studio","free_pct":82,"load_pct":22,"reachable":true}]}}' > "$TEST_HOME/five-pharos/usage.json"
five_in='{"model":{"display_name":"Opus"},"context_window":{"used_percentage":40},"rate_limits":{"seven_day":{"used_percentage":70,"resets_at":1762100000}}}'
five_out=$(printf '%s' "$five_in" | NO_COLOR=1 XDG_CACHE_HOME="$five_cache" LIMITLINE_PHAROS_HOME="$TEST_HOME/five-pharos" LIMITLINE_LINES=5 LIMITLINE_REFRESH=0 "$BIN")
five_l1=$(printf '%s\n' "$five_out" | sed -n 1p)
five_l2=$(printf '%s\n' "$five_out" | sed -n 2p)
check "five-line1-session-only" "$([[ "$five_l1" == *Opus* && "$five_l1" != *7d* ]] && echo yes || echo no)" "yes"
check "five-line2-used" "$([[ "$five_l2" == "used  ✻ claude 7d ███▌░"* && "$five_l2" == *"cursor+grok ████░"* ]] && echo yes || echo no)" "yes"
five_pct=$(printf '%s' "$five_in" | NO_COLOR=1 XDG_CACHE_HOME="$five_cache" LIMITLINE_PHAROS_HOME="$TEST_HOME/five-pharos" LIMITLINE_LINES=5 LIMITLINE_REFRESH=0 LIMITLINE_PLAN_NUMBERS=on "$BIN" | sed -n 2p)
check "five-line2-both" "$([[ "$five_pct" == *"claude 7d ███▌░ 70%"* ]] && echo yes || echo no)" "yes"
check "five-hosts-line" "$(printf '%s\n' "$five_out" | tail -1)" "hosts studio 82% mem free · 22% cpu"
# Hardening, end to end: Pharos installed but not running, and a Codex window that reset.
mkdir -p "$TEST_HOME/five-down"
five_down=$(printf '%s' "$five_in" | NO_COLOR=1 XDG_CACHE_HOME="$five_cache" LIMITLINE_PHAROS_HOME="$TEST_HOME/five-down" LIMITLINE_LINES=5 LIMITLINE_REFRESH=0 "$BIN")
check "five-pharos-not-running" "$five_down" "$(printf '%s\n' "$five_l1" 'used  ✻ claude 7d ███▌░ · pharos not running')"
printf '%s' '{"version":1,"generated_at":1762056000,"plans":[{"provider":"codex","observed_at":1762055900,"windows":[{"name":"5h","used_pct":90,"resets_at":1762055000},{"name":"7d","used_pct":40,"resets_at":1762400000}]}]}' > "$TEST_HOME/five-pharos/usage.json"
five_reset=$(printf '%s' "$five_in" | NO_COLOR=1 LIMITLINE_CODEX=1 XDG_CACHE_HOME="$five_cache" LIMITLINE_PHAROS_HOME="$TEST_HOME/five-pharos" LIMITLINE_LINES=5 LIMITLINE_REFRESH=0 "$BIN" | sed -n 2p)
check "five-codex-reset-passed" "$([[ "$five_reset" == *"codex 5h reset, no newer reading · 7d ██░░░"* ]] && echo yes || echo "$five_reset")" "yes"
# A Codex reading from 30 minutes ago is still current when Pharos does not call it stale.
printf '%s' '{"version":1,"generated_at":1762056000,"plans":[{"provider":"codex","observed_at":1762054200,"stale":false,"windows":[{"name":"7d","used_pct":40,"resets_at":1762400000}]}]}' > "$TEST_HOME/five-pharos/usage.json"
five_old_obs=$(printf '%s' "$five_in" | NO_COLOR=1 LIMITLINE_CODEX=1 XDG_CACHE_HOME="$five_cache" LIMITLINE_PHAROS_HOME="$TEST_HOME/five-pharos" LIMITLINE_LINES=5 LIMITLINE_REFRESH=0 "$BIN" | sed -n 2p)
check "five-codex-observed-30m" "$([[ "$five_old_obs" == *"codex 7d ██░░░"* ]] && echo yes || echo "$five_old_obs")" "yes"
check "two-lines-unchanged" "$(printf '%s' "$five_in" | NO_COLOR=1 XDG_CACHE_HOME="$five_cache" LIMITLINE_LINES=2 LIMITLINE_REFRESH=0 "$BIN" | grep -c 'left ')" "0"
make_summary "$TEST_HOME/five-pharos/summary.json" '{"running":0,"done":0,"need_you":1,"failed":0,"retried":0,"waiting_limit":0,"working":2,"blocked":1}' '[{"state":"blocked","owner":"you","reason":"ready to merge (PR #40)","next":"merge","kind":"run"}]'
printf 'jobs_detail = "counts"\n' > "$TEST_HOME/attention.toml"
five_attention() {
  printf '%s' "$five_in" | NO_COLOR=1 LIMITLINE_ANIMATE=off XDG_CACHE_HOME="$five_cache" LIMITLINE_PHAROS_HOME="$TEST_HOME/five-pharos" LIMITLINE_LINES=5 LIMITLINE_COLUMNS=500 LIMITLINE_REFRESH=0 "$BIN" | sed -n 3p
}
check "five-attention-reason" "$(five_attention)" 'today ▶ 0 running │ ⚙ 2 working │ ✓ 0 done │ ⛔ 1 blocked: ready to merge (PR #40) │ ✋ 1 need you │ ✗ 0 failed · ↻ 0 retried │ ⏸ 0 waiting on limit'
check "five-attention-config-counts" "$(LIMITLINE_CONFIG="$TEST_HOME/attention.toml" five_attention)" 'today ▶ 0 running │ ⚙ 2 working │ ✓ 0 done │ ⛔ 1 blocked │ ✋ 1 need you │ ✗ 0 failed · ↻ 0 retried │ ⏸ 0 waiting on limit'
make_summary "$TEST_HOME/five-pharos/summary.json" '{"running":0,"done":0,"need_you":1,"failed":0,"retried":0,"waiting_limit":0}'
check "five-attention-legacy" "$(five_attention)" 'today ▶ 0 running │ ✓ 0 done │ ✋ 1 need you │ ✗ 0 failed · ↻ 0 retried │ ⏸ 0 waiting on limit'
if five_unit=$(python3 -m unittest -q "$ROOT/tests/test_fivelines.py" 2>&1); then
  check "fivelines-unit" "ok" "ok"
else
  check "fivelines-unit" "failed" "ok"
  printf '%s\n' "$five_unit" | grep -E '^(FAIL|ERROR):|Error: |^Ran|^FAILED' >&2
fi
# 0.14.0: the display stays honest when Pharos's files are bad (synthetic files only).
if hard_out=$(python3 -m unittest -q "$ROOT/tests/test_hardening.py" 2>&1); then
  check "hardening-unit" "ok" "ok"
else
  check "hardening-unit" "failed" "ok"
  printf '%s\n' "$hard_out" | grep -E '^(FAIL|ERROR):|Error: |^Ran|^FAILED' >&2
fi
if python3 -m unittest -q "$ROOT/tests/test_release.py" >/dev/null 2>&1; then
  check "release-unit" "ok" "ok"
else
  check "release-unit" "failed" "ok"
fi

# Display only (2026-11-03): the status line relays Claude's reading to Pharos and
# refresh never starts agy, grok, or ssh. Pharos measures; limitline draws.
relay_home="$TEST_HOME/relay"
mkdir -p "$relay_home/.pharos"
printf '%s' '{"model":{"display_name":"Opus"},"rate_limits":{"seven_day":{"used_percentage":44,"resets_at":1762100000}}}' \
  | HOME="$relay_home" XDG_CACHE_HOME="$relay_home/.cache" LIMITLINE_REFRESH=0 "$BIN" >/dev/null
check "relay-claude-to-pharos" "$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["source"], d["windows"][0]["used_pct"])' "$relay_home/.pharos/inbox/claude.json" 2>/dev/null)" "statusline 44"
no_pharos="$TEST_HOME/no-pharos"
mkdir -p "$no_pharos"
printf '%s' '{"model":{"display_name":"Opus"},"rate_limits":{"seven_day":{"used_percentage":44,"resets_at":1762100000}}}' \
  | HOME="$no_pharos" XDG_CACHE_HOME="$no_pharos/.cache" LIMITLINE_REFRESH=0 "$BIN" >/dev/null
[[ ! -e "$no_pharos/.pharos" ]] && check "relay-needs-pharos" "yes" "yes" || check "relay-needs-pharos" "created" "no ~/.pharos made"
spy="$TEST_HOME/spybin"
mkdir -p "$spy"
for tool in agy grok ssh codex; do printf '#!/bin/sh\necho %s >> "%s/calls"\n' "$tool" "$spy" > "$spy/$tool"; chmod +x "$spy/$tool"; done
PATH="$spy:$PATH" "$BIN" refresh >/dev/null 2>&1
[[ ! -s "$spy/calls" ]] && check "refresh-measures-nothing" "yes" "yes" || check "refresh-measures-nothing" "$(cat "$spy/calls")" "no agy, grok, ssh, or codex"
[[ ! -e "$ROOT/providers/antigravity" && ! -e "$ROOT/providers/gemini" && ! -e "$ROOT/lib/xai_fetch.py" ]] \
  && check "cross-tool-readers-gone" "yes" "yes" || check "cross-tool-readers-gone" "still there" "moved to Pharos"

# Old settings that moved to Pharos get a one-line notice from doctor.
old_cfg="$TEST_HOME/old.toml"
printf '%s\n' 'hosts = ["mini=me@mini"]' 'sync_dir = "/x"' 'theme = "emoji"' > "$old_cfg"
old_doc=$(LIMITLINE_CONFIG="$old_cfg" "$BIN" doctor < /dev/null)
printf '%s' "$old_doc" | grep -q -F 'config: hosts is no longer used (set hosts in ~/.pharos/usage.toml)' \
  && printf '%s' "$old_doc" | grep -q -F 'config: sync_dir is no longer used' && ! printf '%s' "$old_doc" | grep -q -F 'config: theme' \
  && check "doctor-obsolete-keys" "yes" "yes" || check "doctor-obsolete-keys" "$old_doc" "notices for moved keys only"

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[[ "$fail" -eq 0 ]]
