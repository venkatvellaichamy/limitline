#!/usr/bin/env bash
# 0.15 tests: line 1 order, git ahead/behind, dir/project and the new segments, per-line
# layouts, presets, the statusline picker, and 0.14 configs rendering as before.
# Kept apart from tests/run.sh so the existing suite stays as it was; CI runs both.
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
# The folder segment is on by default; fixtures predate it, so it is opted into where tested.
export LIMITLINE_DIR=0
unset LIMITLINE_PRESET LIMITLINE_DIR_STYLE LIMITLINE_LINE1 LIMITLINE_LINE2 LIMITLINE_LINE3 \
  LIMITLINE_LINE4 LIMITLINE_LINE5
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

# Hide jq without dropping the tools the script still needs (the python3 fallback).
nojq="$TEST_HOME/nojq"
mkdir -p "$nojq"
for tool in bash python3 awk date find grep id sed tail cat tr; do
  src=$(command -v "$tool" 2>/dev/null) || continue
  ln -s "$src" "$nojq/$tool"
done
make_summary() {  # make_summary <path> <today json> [<recent json>] [<jobs json>]
  printf '{"version":1,"generated_at":1762056000,"today":%s,"older":{},"oldest_open":null,"recent":%s,"jobs":%s}\n' "$2" "${3:-[]}" "${4:-[]}" > "$1"
}
# The five-line view's inputs (the same as tests/run.sh sets up for its five-line checks).
five_cache="$TEST_HOME/five-cache"; mkdir -p "$five_cache/limitline" "$TEST_HOME/five-pharos/runs"
printf 'cursor+grok 81%% · Thu 23:22 · grok 7d 1M tok\n81 0 live\n' > "$five_cache/limitline/grok.line"
touch -t 202511020359 "$five_cache/limitline/grok.line"  # a minute before LIMITLINE_NOW (TZ=UTC)
five_in='{"model":{"display_name":"Opus"},"context_window":{"used_percentage":40},"rate_limits":{"seven_day":{"used_percentage":70,"resets_at":1762100000}}}'
make_summary "$TEST_HOME/five-pharos/summary.json" '{"running":0,"done":0,"need_you":1,"failed":0,"retried":0,"waiting_limit":0}'

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

# 0.15 line 1: folder, git, model, context first, plain labels.
rich="$FIX/rich.json"
r15() { NO_COLOR=1 "$@" < "$rich" | strip_ansi; }
check "default-order" "$(LIMITLINE_DIR=1 r15 "$BIN")" \
  'demo │ Opus 5.5 │ ctx ▓▓░░░ 32% · 678k left │ Explanatory │ 5h ▓▓▓░░ +62% ↻1h42m │ 7d ▓▓░░░ ·38% ↻Thu 09:00 │ $276.92 60h32m +17,898 −506 │ PR #19 pending │ vim INSERT'
check "default-order-dir-off" "$(r15 "$BIN")" \
  'Opus 5.5 │ ctx ▓▓░░░ 32% · 678k left │ Explanatory │ 5h ▓▓▓░░ +62% ↻1h42m │ 7d ▓▓░░░ ·38% ↻Thu 09:00 │ $276.92 60h32m +17,898 −506 │ PR #19 pending │ vim INSERT'
check "ascii-minus" "$(LIMITLINE_THEME=ascii LIMITLINE_SEGMENTS= LIMITLINE_DIR=1 r15 "$BIN")" \
  'demo | Opus 5.5 | ctx ##--- 32% · 678k left | Explanatory | 5h ###-- +62% in 1h42m | 7d ##--- ·38% in Thu 09:00 | $276.92 60h32m +17,898 -506 | PR #19 pending | vim INSERT'

# The owner's line: emoji theme, five lines, vitals on, in a repo 2 commits behind.
own_root="$TEST_HOME/own"
own="$own_root/pharos"
mkdir -p "$own"
ogit() { git -C "$own" -c user.name=limitline -c user.email=limitline@example.com "$@"; }
ogit init -q -b main
ogit commit -q --allow-empty -m one
ogit commit -q --allow-empty -m two
ogit commit -q --allow-empty -m three
ogit branch -q up
ogit reset -q --hard HEAD~2
ogit branch -q -u up main
own_cfg="$TEST_HOME/own.toml"
printf '%s\n' 'theme = "emoji"' 'lines = 5' 'vitals = "on"' > "$own_cfg"
own_payload=$(printf '{"model":{"display_name":"Opus 5.5"},"workspace":{"current_dir":"%s"},"cost":{"total_cost_usd":276.92,"total_duration_ms":217920000,"total_lines_added":17898,"total_lines_removed":506},"context_window":{"used_percentage":32,"context_window_size":1000000,"total_input_tokens":322000}}' "$own")
own_got=$(printf '%s' "$own_payload" | env -u LIMITLINE_GIT -u LIMITLINE_DIR LIMITLINE_CONFIG="$own_cfg" LIMITLINE_PHAROS_HOME="$TEST_HOME/no-pharos" NO_COLOR=1 "$BIN" | strip_ansi | head -n 1)
check "owner-line-1" "$own_got" '📁 pharos │ 🌿 main ↓2 │ 🧠 Opus 5.5 │ 🪟 ctx ▓▓░░░ 32% · 678k left │ ⏱ 60h32m · +17,898 −506 · $276.92'

# dir: the folder name, or the path from ~ with dir_style = "home".
mkdir -p "$TEST_HOME/projects/pharos"
dir_home=$(printf '{"workspace":{"current_dir":"%s"}}' "$TEST_HOME/projects/pharos" | LIMITLINE_DIR=1 LIMITLINE_DIR_STYLE=home LIMITLINE_SEGMENTS=dir NO_COLOR=1 "$BIN" | strip_ansi)
check "dir-home" "$dir_home" '~/projects/pharos'
check "dir-name" "$(printf '{"workspace":{"current_dir":"/work/demo/"}}' | LIMITLINE_DIR=1 LIMITLINE_SEGMENTS=dir NO_COLOR=1 "$BIN")" 'demo'
check "dir-cwd-field" "$(printf '{"cwd":"/work/other"}' | LIMITLINE_DIR=1 LIMITLINE_SEGMENTS=dir NO_COLOR=1 "$BIN")" 'other'
check "dir-none" "$(printf '{"model":{"display_name":"Opus 5.5"}}' | LIMITLINE_DIR=1 NO_COLOR=1 "$BIN")" 'Opus 5.5'
check "dir-off" "$(printf '{"cwd":"/work/other"}' | LIMITLINE_DIR=0 LIMITLINE_SEGMENTS=dir,model NO_COLOR=1 "$BIN")" ''

# project: the repository's name when it differs from the folder (a linked worktree).
proj_repo="$TEST_HOME/limitline"
mkdir -p "$proj_repo"
git -C "$proj_repo" init -q -b main
git -C "$proj_repo" -c user.name=limitline -c user.email=limitline@example.com commit -q --allow-empty -m init
git -C "$proj_repo" worktree add -q -b feature "$TEST_HOME/wt/feature-x" 2>/dev/null
mkdir -p "$proj_repo/sub/dir"
proj() { printf '{"workspace":{"current_dir":"%s"}}' "$1" | LIMITLINE_DIR=1 LIMITLINE_SEGMENTS="${2:-dir,project}" NO_COLOR=1 "$BIN" | strip_ansi; }
check "project-worktree" "$(proj "$TEST_HOME/wt/feature-x")" 'feature-x │ limitline'
check "project-subdir" "$(proj "$proj_repo/sub/dir")" 'dir │ limitline'
check "project-same-as-dir" "$(proj "$proj_repo")" 'limitline'
check "project-not-a-repo" "$(proj "$TEST_HOME/projects/pharos")" 'pharos'
check "project-from-project-dir" "$(printf '{"workspace":{"current_dir":"/work/demo/src","project_dir":"/work/demo"}}' | LIMITLINE_DIR=1 LIMITLINE_SEGMENTS=dir,project NO_COLOR=1 "$BIN")" 'src │ demo'

# Data Claude Code sends that 0.14 never showed. Each is absent without its field.
seg() { LIMITLINE_SEGMENTS="$1" NO_COLOR=1 "$BIN" < "${2:-$rich}" | strip_ansi; }
check "segment-version" "$(seg version)" 'v2.1.317'
check "segment-tokens" "$(seg tokens)" '322k in · 2.4k out'
check "segment-effort" "$(seg model,effort)" 'Opus 5.5 │ effort high'
check "segment-title" "$(seg title)" 'statusline picker'
check "segment-app" "$(seg app)" 'Claude Code'
check "segment-session-id" "$(seg session-id)" 'abcdef'
check "segment-codex-ids" "$(seg current-dir,git-branch,model-with-reasoning,context-used,codex-version)" 'Opus 5.5 │ effort high │ ctx ▓▓░░░ ·32% 678k left │ v2.1.317'
for one in version tokens effort title; do
  check "segment-$one-absent" "$(seg "model,$one" "$FIX/full.json")" 'Opus 5.5'
done
check "segment-version-nojq" "$(PATH="$nojq" seg version,tokens,effort,title)" 'v2.1.317 │ 322k in · 2.4k out │ effort high │ statusline picker'
check "segment-emoji" "$(LIMITLINE_THEME=emoji LIMITLINE_DIR=1 seg dir,version,tokens,effort,title,app)" '📁 demo │ 🏷 v2.1.317 │ 🔢 322k in · 2.4k out │ 💭 effort high │ 📝 statusline picker │ Claude Code'


# 0.15 layouts: line1 = [...] ... lineN = [...], and presets that are named layouts.
lay() { NO_COLOR=1 LIMITLINE_DIR=1 LIMITLINE_REFRESH=0 "$BIN" < "$rich" | strip_ansi; }
check "preset-minimal" "$(LIMITLINE_PRESET=minimal lay)" 'demo │ Opus 5.5 │ ctx ▓▓░░░ 32% · 678k left'
check "preset-default-is-default" "$(LIMITLINE_PRESET=default lay)" "$(lay)"
check "preset-full" "$(LIMITLINE_PRESET=full lay)" "$(printf '%s\n' \
  'demo │ Opus 5.5 │ effort high │ Explanatory │ ctx ▓▓░░░ 32% · 678k left │ 322k in · 2.4k out │ $276.92 60h32m +17,898 −506' \
  '5h ▓▓▓░░ +62% ↻1h42m │ 7d ▓▓░░░ ·38% ↻Thu 09:00 │ PR #19 pending │ vim INSERT │ statusline picker │ v2.1.317 │ abcdef')"
check "preset-line-override" "$(LIMITLINE_PRESET=minimal LIMITLINE_LINE2=7d,5h lay)" "$(printf '%s\n' \
  'demo │ Opus 5.5 │ ctx ▓▓░░░ 32% · 678k left' '7d ▓▓░░░ ·38% ↻Thu 09:00 │ 5h ▓▓▓░░ +62% ↻1h42m')"
check "preset-line-removed" "$(LIMITLINE_PRESET=full LIMITLINE_LINE2='[]' lay)" \
  'demo │ Opus 5.5 │ effort high │ Explanatory │ ctx ▓▓░░░ 32% · 678k left │ 322k in · 2.4k out │ $276.92 60h32m +17,898 −506'
check "preset-unknown-is-default" "$(LIMITLINE_PRESET=nope lay)" "$(lay)"
lay_cfg="$TEST_HOME/layout.toml"
printf '%s\n' 'line1 = ["current-dir", "git-branch", "model-with-reasoning", "context-remaining"]' 'line2 = ["vitals"]' 'colors = "off"' > "$lay_cfg"
check "layout-config" "$(LIMITLINE_CONFIG="$lay_cfg" LIMITLINE_DIR=1 LIMITLINE_REFRESH=0 "$BIN" < "$rich")" "$(printf '%s\n' \
  'demo │ Opus 5.5 │ effort high │ ctx ▓▓░░░ 32% · 678k left' 'session 60h32m · +17,898 −506 · $276.92')"
if LIMITLINE_CONFIG="$lay_cfg" "$BIN" < "$rich" | grep -q $'\033\\['; then check "colors-off" "colour" "plain"; else check "colors-off" "plain" "plain"; fi
printf '%s\n' 'colors = "on"' 'line1 = "ctx"' > "$lay_cfg"
if LIMITLINE_CONFIG="$lay_cfg" "$BIN" < "$rich" | grep -q $'\033\\['; then check "colors-on" "colour" "colour"; else check "colors-on" "plain" "colour"; fi
printf '%s\n' 'segments = ["model"]' 'line1 = ["ctx"]' > "$lay_cfg"
check "layout-wins-over-segments" "$(LIMITLINE_CONFIG="$lay_cfg" lay)" 'ctx ▓▓░░░ 32% · 678k left'
check "layout-narrow" "$(LIMITLINE_PRESET=full LIMITLINE_COLUMNS=60 lay | head -n 1)" 'demo │ Opus 5.5 │ ctx ▓▓░░░ 32% · 678k left'
# preset "pharos" is today's five-line view: line 1, then used, today, older, hosts.
printf '%s' '{"version":1,"generated_at":1762056000,"plans":[],"hosts":{"hosts":[{"name":"studio","free_pct":82,"load_pct":22,"reachable":true}]}}' > "$TEST_HOME/five-pharos/usage.json"
five_lay() { printf '%s' "$five_in" | NO_COLOR=1 LIMITLINE_ANIMATE=off XDG_CACHE_HOME="$five_cache" LIMITLINE_PHAROS_HOME="$TEST_HOME/five-pharos" LIMITLINE_COLUMNS=500 LIMITLINE_REFRESH=0 "$BIN"; }
check "preset-pharos-is-five-lines" "$(LIMITLINE_PRESET=pharos five_lay)" "$(LIMITLINE_LINES=5 five_lay)"
check "preset-pharos-lines" "$(LIMITLINE_PRESET=pharos five_lay | wc -l | tr -d ' ')" "4"
pharos_order=$(LIMITLINE_PRESET=pharos LIMITLINE_LINE2=hosts LIMITLINE_LINE3=used LIMITLINE_LINE4='[]' LIMITLINE_LINE5='[]' five_lay | cut -c1-5)
check "pharos-lines-reordered" "$pharos_order" "$(printf '%s\n' 'Opus ' 'hosts' 'used ')"
check "pharos-line-only" "$(LIMITLINE_LINE1=hosts five_lay)" 'hosts studio 82% mem free · 22% cpu'
# With lines = 5 and no preset, a lineN changes only its line: the Pharos lines stay.
five_own=$(LIMITLINE_CONFIG="$own_cfg" LIMITLINE_LINE1=model five_lay)
check "lines5-line1-keeps-pharos" "$(printf '%s\n' "$five_own" | sed -n 1p; printf '%s\n' "$five_own" | wc -l | tr -d ' ')" \
  "$(printf '%s\n' '🧠 Opus' "$(LIMITLINE_CONFIG="$own_cfg" five_lay | wc -l | tr -d ' ')")"
check "lines5-line1-hosts-last" "$(printf '%s\n' "$five_own" | tail -n 1 | cut -c1-5)" 'hosts'
# context-window-size shows the window's size after what is left.
check "ctx-window-size-legacy" "$(seg context-window-size)" 'ctx ▓▓░░░ ·32% 678k left of 1M'
check "ctx-window-size-layout" "$(LIMITLINE_LINE1=context-window-size lay)" 'ctx ▓▓░░░ 32% · 678k left of 1M'
check "ctx-size-config" "$(printf 'ctx_size = "on"\n' > "$lay_cfg"; LIMITLINE_CONFIG="$lay_cfg" lay | awk -F ' │ ' '{ print $3 }')" 'ctx ▓▓░░░ 32% · 678k left of 1M'
# Two lines without a layout: folder, git, model, context stay together on line 1.
two_git=$(printf '%s' "$own_payload" | LIMITLINE_DIR=1 LIMITLINE_GIT=1 LIMITLINE_LINES=2 NO_COLOR=1 "$BIN" | strip_ansi | head -n 1)
check "two-lines-git-on-line-1" "$two_git" 'pharos │ main ↓2 │ Opus 5.5 │ ctx ▓▓░░░ 32% · 678k left'

# 0.16.0-beta.2: a reading that may be wrong is `?`, never a plausible number.
unk_home="$TEST_HOME/unknown-pharos"
mkdir -p "$unk_home/runs"
unk_used() { printf '%s' "$five_in" | NO_COLOR=1 LIMITLINE_ANIMATE=off XDG_CACHE_HOME="$TEST_HOME/unknown-cache" LIMITLINE_PHAROS_HOME="$unk_home" LIMITLINE_COLUMNS=500 LIMITLINE_REFRESH=0 LIMITLINE_PRESET=pharos "$BIN" | grep '^used'; }
unk_usage() { printf '{"version":1,"generated_at":%s,"plans":[{"provider":"codex","observed_at":%s,"windows":[{"name":"5h","used_pct":17,"resets_at":1762060000}]},{"provider":"xai-plan","observed_at":1762055940,"windows":%s}],"hosts":{"hosts":[]}}' "$1" "$2" "$3" > "$unk_home/usage.json"; }
unk_usage 1762055940 1762055900 '[{"used_pct":40,"resets_at":1762100000}]'
check "unknown-fresh-has-numbers" "$(unk_used | grep -c -F '◎ codex 5h')" "1"
unk_usage 1762055940 '"2026-11-01T00:00:00Z"' '[{"used_pct":40,"resets_at":1762100000}]'
unk_line=$(unk_used)
check "unknown-iso-observed-at" "$(printf '%s' "$unk_line" | grep -c -F '◎ codex ? │')$(printf '%s' "$unk_line" | grep -c -F '◎ codex 5h')" "10"
unk_usage 1762055940 1762055900 '5'
unk_line=$(unk_used)
check "unknown-bad-windows" "$(printf '%s' "$unk_line" | grep -c -F 'cursor+grok ?')$(printf '%s' "$unk_line" | grep -c -F '◎ codex 5h')$(printf '%s' "$unk_line" | grep -c -F '✻ claude 7d')" "111"
unk_usage 1762056000 $((1762056000 - 114 * 60)) '[]'
check "unknown-age-minutes" "$(unk_used | grep -c -F '◎ codex ? · 114m old')" "1"
unk_usage $((1762056000 - 3600)) $((1762056000 - 3600)) '[]'
unk_line=$(unk_used)
check "pharos-usage-unavailable-stale" "$(printf '%s' "$unk_line" | grep -c -E ' · Pharos usage unavailable · 60m old$')$(printf '%s' "$unk_line" | grep -c -F '◎ codex 5h')" "10"
rm -f "$unk_home/usage.json"
unk_line=$(unk_used)
check "pharos-usage-unavailable-missing" "$(printf '%s' "$unk_line" | grep -c -E '^used  ✻ claude 7d .* · Pharos usage unavailable$')$(printf '%s' "$unk_line" | grep -c -F 'codex')" "10"

# limitline statusline: the non-interactive side of /limitline:statusline.
pick_dir="$TEST_HOME/picker"
mkdir -p "$pick_dir"
pick_cfg="$pick_dir/config.toml"
printf '%s\n' '# my settings' 'theme = "ascii"   # keep me' 'lines = 2' 'colour = "on"' > "$pick_cfg"
cp "$pick_cfg" "$pick_dir/original"
pick() { (cd "$TEST_HOME/projects/pharos" && env -u LIMITLINE_DIR LIMITLINE_CONFIG="$pick_cfg" NO_COLOR=1 "$BIN" statusline "$@"); }
pick_list=$(pick list)
check "statusline-list-ids" "$(printf '%s\n' "$pick_list" | grep -c -E '^(dir|git|model|ctx|project|version|tokens|effort|title) ')" "9"
check "statusline-list-codex" "$(printf '%s\n' "$pick_list" | grep -E '^dir ' | grep -c 'current-dir')" "1"
check "statusline-list-unavailable" "$(printf '%s\n' "$pick_list" | grep -E '^ *run-state ' | grep -c 'not available')" "1"
check "statusline-list-presets" "$(printf '%s\n' "$pick_list" | grep -c -E '^ *(minimal|default|full|pharos) ')" "4"
pick set line1=dir,git-branch,model,ctx > "$pick_dir/out" 2>&1
check "statusline-set-line" "$(grep -E '^line1' "$pick_cfg")" 'line1 = ["dir", "git", "model", "ctx"]'
check "statusline-set-keeps" "$(grep -c -E '^# my settings$|^theme = "ascii"   # keep me$|^lines = 2$' "$pick_cfg")" "3"
check "statusline-set-backup" "$(cat "$pick_dir/config.toml.bak")" "$(cat "$pick_dir/original")"
check "statusline-set-renders" "$(LIMITLINE_CONFIG="$pick_cfg" LIMITLINE_DIR=1 NO_COLOR=1 "$BIN" < "$rich")" 'demo | Opus 5.5 | ctx ##--- 32% · 678k left'
cp "$pick_cfg" "$pick_dir/before-bad"
pick set line1=dir,warp-drive > "$pick_dir/bad" 2>&1
check "statusline-set-unknown-exit" "$?" "2"
check "statusline-set-unknown-unchanged" "$(cat "$pick_cfg")" "$(cat "$pick_dir/before-bad")"
check "statusline-set-unknown-says" "$(grep -c 'warp-drive' "$pick_dir/bad")" "1"
pick set line2=run-state > "$pick_dir/bad" 2>&1
check "statusline-set-unavailable" "$(grep -c 'not available in Claude Code' "$pick_dir/bad")" "1"
pick set preset=full colors=off line2=none > /dev/null 2>&1
check "statusline-set-preset" "$(grep -E '^(preset|colors|colour|line2)' "$pick_cfg")" "$(printf '%s\n' 'colors = "off"' 'preset = "full"' 'line2 = []')"
check "statusline-preview" "$(pick preview)" 'pharos | Opus 5.5 | ctx ##--- 32% · 678k left'
check "statusline-preview-proposed" "$(pick preview line1=model,effort)" 'Opus 5.5 | effort high'
check "statusline-preview-no-write" "$(grep -c '^line1 = \["dir", "git", "model", "ctx"\]$' "$pick_cfg")" "1"
pick_cache="$TEST_HOME/picker-cache"
mkdir -p "$pick_cache"
(cd "$TEST_HOME/projects/pharos" && XDG_CACHE_HOME="$pick_cache" LIMITLINE_PHAROS_HOME="$TEST_HOME/picker-pharos" LIMITLINE_CONFIG="$pick_cfg" "$BIN" statusline preview >/dev/null)
mkdir -p "$TEST_HOME/picker-pharos"
(cd "$TEST_HOME/projects/pharos" && XDG_CACHE_HOME="$pick_cache" LIMITLINE_PHAROS_HOME="$TEST_HOME/picker-pharos" LIMITLINE_CONFIG="$pick_cfg" "$BIN" statusline preview >/dev/null)
check "statusline-preview-writes-nothing" "$(find "$pick_cache" "$TEST_HOME/picker-pharos" -type f | wc -l | tr -d ' ')" "0"
pick --clear > /dev/null 2>&1
check "statusline-clear" "$(cat "$pick_cfg")" "$(printf '%s\n' '# my settings' 'theme = "ascii"   # keep me' 'lines = 2')"
check "statusline-clear-renders-default" "$(LIMITLINE_CONFIG="$pick_cfg" LIMITLINE_DIR=1 NO_COLOR=1 "$BIN" < "$rich" | head -n 1 | cut -c1-40)" 'demo | Opus 5.5 | ctx ##--- 32% · 678k '
fresh_xdg="$pick_dir/fresh-xdg"
mkdir -p "$fresh_xdg"
(cd "$TEST_HOME" && env -u LIMITLINE_CONFIG XDG_CONFIG_HOME="$fresh_xdg" "$BIN" statusline set preset=minimal > /dev/null 2>&1)
check "statusline-first-set-is-toml" "$(ls "$fresh_xdg/limitline"; cat "$fresh_xdg/limitline/config.toml")" "$(printf '%s\n' 'config.toml' 'preset = "minimal"')"
mkdir -p "$pick_dir/dotfiles"
printf 'theme = "mono"\n' > "$pick_dir/dotfiles/limitline.toml"
ln -s "$pick_dir/dotfiles/limitline.toml" "$pick_dir/linked.toml"
LIMITLINE_CONFIG="$pick_dir/linked.toml" "$BIN" statusline set line1=model > /dev/null 2>&1
check "statusline-keeps-symlink" "$([[ -L "$pick_dir/linked.toml" ]] && echo link || echo file) $(grep -c '^line1' "$pick_dir/dotfiles/limitline.toml")" 'link 1'
check "statusline-help" "$(pick 2>&1 | grep -c 'statusline set')" "1"
legacy_only="$pick_dir/xdg"
mkdir -p "$legacy_only/limitline"
printf 'theme = "pill"\n' > "$legacy_only/limitline/config"
(cd "$TEST_HOME" && env -u LIMITLINE_CONFIG XDG_CONFIG_HOME="$legacy_only" "$BIN" statusline set line1=model > /dev/null 2>&1)
check "statusline-legacy-file" "$(cat "$legacy_only/limitline/config"; ls "$legacy_only/limitline")" "$(printf '%s\n' 'theme = "pill"' 'line1 = ["model"]' 'config' 'config.bak')"

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[[ "$fail" -eq 0 ]]
