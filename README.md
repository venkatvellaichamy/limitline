# limitline

A status line for AI plan limits. limitline **shows** usage; it does not measure other tools.

- **On its own,** it shows the tool it runs in: Claude Code's limits, model, context, and cost from the status-line input, or, inside Codex, Grok, or Cursor (`LIMITLINE_TOOL=codex|grok|cursor`), that tool's own local files.
- **With [Pharos](https://github.com/venkatvellaichamy/pharos),** it shows everything Pharos measured: every plan (Claude, Codex, Cursor + Grok, Antigravity), every host, and the job counts. Pharos writes `~/.pharos/usage.json` and `~/.pharos/summary.json`; limitline reads them.
- Claude Code hands its limits only to the status-line program, so limitline relays that one reading, as-is, to `~/.pharos/inbox/claude.json` when Pharos is installed.

Nothing in this tool opens a network connection, runs ssh, or starts another tool's CLI.

```
Opus 5.5 │ ctx ▓▓░░░ ·41% │ 5h ▓▓▓░░ +62% ↻1h42m │ 7d ▓▓░░░ ·38% ↻Thu 09:00 │ $1.25 │ codex 5h ·12% · 7d +55%
```

Green is under 50% (`·`), yellow is 50–80% (`+`), and red is over 80% (`!`). The mark stays when `NO_COLOR` strips the colour. Reset times are relative under 24 hours (`↻1h42m`) and a weekday plus local time after that (`↻Thu 09:00`).

Missing fields are skipped. Empty input still exits 0.

See [ROADMAP.md](ROADMAP.md) for shipped releases, hardening, and planned work.

## Themes

`minimal` (default):

```
Opus 5.5 │ ctx ▓▓░░░ ·41% │ 5h ▓▓▓░░ +62% ↻1h42m │ 7d ▓▓░░░ ·38% ↻Thu 09:00 │ $1.25
```

`powerline`:

```
Opus 5.5  ctx ██░░░ ·41%  5h ███░░ +62% ↻1h42m  7d ██░░░ ·38% ↻Thu 09:00  $1.25
```

`ascii`, also forced by `LIMITLINE_ASCII=1`:

```
Opus 5.5 | ctx ##--- ·41% | 5h ###-- +62% in 1h42m | 7d ##--- ·38% in Thu 09:00 | $1.25
```

`pill` puts each segment in a rounded chip:

```
⟨Opus 5.5⟩ ⟨ctx ▓▓░░░ ·41%⟩ ⟨5h ▓▓▓░░ +62% ↻1h42m⟩ ⟨7d ▓▓░░░ ·38% ↻Thu 09:00⟩ ⟨$1.25⟩
```

`emoji`:

```
🧠 Opus 5.5 │ 🪟 ctx ▓▓░░░ ·41% │ ⏱ 5h ▓▓▓░░ +62% ⏳1h42m │ 📅 7d ▓▓░░░ ·38% ⏳Thu 09:00 │ 💵 $1.25
```

`mono` is plain text. It stays plain even when colour is on:

```
Opus 5.5  ctx 41%  5h 62% in 1h42m  7d 38% in Thu 09:00  $1.25
```

Presets live in `examples/`. `limitline preview` and `limitline theme` print every theme from the same sample. `/limitline:theme` is the same picker inside Claude Code.

With pace, sparklines, and fresh wording turned on, the same session looks like this:

```
Opus 5.5 │ ctx ▓▓░░░ ·41% │ 5h ▓▓▓░░ +62% fresh in 1h42m │ 5h ▁▃▅▆▅ 62% │ 7d ▓▓░░░ ·38% fresh Thu 09:00 │ 7d ▁▃▃▅▅▇▄ 38% │ ~15%/day left for 4d │ $1.25
```

## Why limitline

The number you care about is already on the machine: the status payload Claude Code just handed you, the newest Codex log line, a snapshot from the last prompt. limitline turns that into one row you can read without opening a dashboard. It does not phone home, and a missing field is skipped instead of guessed.

## Doing it by hand

Check Claude's usage screen, note the 5-hour and weekly percents and when they reset, then do the same for Codex, remember that Cursor and Grok do not publish a local quota, and check Antigravity's usage per model group. Repeat that every time the window moves. limitline reads those local files once per prompt and prints the row. The switches below add pace, a sparkline, a nudge, or a second machine when you want them, and each one can be turned off.

## Install with the plugin

Inside Claude Code:

```
/plugin marketplace add venkatvellaichamy/limitline
/plugin install limitline@limitline
/limitline:install
```

`/limitline:install` backs up `~/.claude/settings.json`, keeps every other key, and asks before replacing an existing `statusLine`. It points `statusLine` at the installed `bin/limitline`.

`/limitline:preview` prints a sample line. `/limitline:theme` previews every theme. `/limitline:config` prints a config template and does not write it. `/limitline:doctor` names the tools on `PATH` and which stdin fields are present, without printing their values. `/limitline:uninstall` removes the limitline status line and leaves the rest of the file alone.

## Manual install

```bash
git clone https://github.com/venkatvellaichamy/limitline.git
cd limitline
chmod +x bin/limitline providers/*
```

Add this to `~/.claude/settings.json` (merge it with the keys you already have):

```json
{
  "statusLine": {
    "type": "command",
    "command": "/absolute/path/to/limitline/bin/limitline",
    "padding": 0,
    "refreshInterval": 30
  }
}
```

Restart Claude Code. The status command receives one JSON object on stdin.

`refreshInterval` is a documented Claude Code `statusLine` field: it re-runs the command every N seconds (minimum 1), in addition to the usual redraws. Without it, Claude Code redraws a session's status line only on events in that session (a new message, a model or vim-mode change, a rate-limit reset), so an idle terminal keeps showing the fleet, machine, and plan numbers it last drew, and two idle terminals can disagree. With `refreshInterval: 30`, every terminal re-reads the shared caches at least every 30 seconds. A warm render takes about 30 ms. `limitline install` sets it.

```bash
echo '{"model":{"display_name":"Opus 5.5"},"rate_limits":{"five_hour":{"used_percentage":62,"resets_at":1762062120}},"context_window":{"used_percentage":41}}' \
  | LIMITLINE_NOW=1762056000 TZ=UTC bin/limitline
```

## What the Claude Code line can show

Each segment can be turned off or reordered with `segments` in the config file.

| Segment | Source |
| --- | --- |
| Model | `.model.display_name`, with a leading `Claude ` removed |
| Style | `.output_style.name` when it is not `default` |
| Context | used percent, a bar, tokens left when the window size is known, and `↯ auto-compact in ~N%` once usage reaches the warn line (default 80, compact default 95) |
| `5h` / `7d` | `.rate_limits.five_hour` and `.seven_day`. Claude Code sends each window only when the account reports it, so a line can show `7d` alone. A new session gets no `rate_limits` until its first reply, so `7d` then shows the last reading any session cached in `~/.cache/limitline/claude.json`, with its age: `7d 67% · 4m ago`. A reply that carries only the 5-hour window keeps that cached week and its age. A cached week whose reset has passed is last week's number, so the segment says `7d reset Fri 08:40 · no newer reading` instead of a percent. `LIMITLINE_CLAUDE_CACHE=0` turns the fallback off |
| Spend | `.rate_limits.spend_limit` when present |
| Pace | projection from local 5-hour snapshots, such as `pace ~1h35m` |
| Cost | `.cost.total_cost_usd`, duration, and lines added or removed. `$0` is omitted |
| Git | branch, dirty `*`, ahead and behind, from the workspace directory. Cached with the rest of the short-lived files |
| PR | `.pr.number` and review state. OSC 8 links only when `links` is on |
| Cache | `cache cold: <cause>` only when the prompt cache is cold |
| Vim | `.vim.mode` |
| Codex | newest `rate_limits` event across every Codex session file from the last 8 days, scanned by `providers/codex` (python3) at most every 30 seconds. Each window shows until its own reset time, so `codex 7d ·41%` can stay after the 5-hour window has reset |
| Jobs | `jobs mining 62/1842 · backup ok 08:36`, from `limitline job update`. On by default, but nothing is read until a job is reported. `jobs = "off"` hides it |
| Grok / Cursor plan | With a plan reading: `cursor+grok +74% · Thu 23:22 · grok 7d 1.2M tok`, live from the Grok CLI log, dimmed with its age (`· 9h old`) after 6 hours. A manual value says `manual` and is always dimmed. Without it: `grok SuperGrok Plus · 7d 1.2M tok`, the plan name and the session tokens Grok recorded in the last 7 days, never a percent. Read from a line `limitline refresh` writes. Off until `grok = "on"` or `grok` (or `cursor+grok`) is named |
| Session | first 6 characters of `.session_id`. Off unless you opt in |
| Pace | `▲ ahead of pace` or `▼ under pace` when usage and elapsed time differ by 8 points or more, plus `~15%/day left for 4d` on the weekly window. Off until `pace = "on"` |
| Sparkline | `5h ▁▃▅▆▅ 62%` from local snapshots, and a 7-day daily history. Off until `spark = "on"` |
| Fresh | `fresh in 1h42m`, and `✨` on the first prompt after usage drops into a new window. Off until `fresh = "on"` |
| Nudge | `→ codex 12% · mini idle`, `→ cursor ok`, or `↯ compact soon: /compact`. Off until `nudges = "on"` |
| Fleet | `⚙ 3 run · 1 ✗`, from a local cache of Pharos runs or a process scan. Only runs that are live or were active in the last 12 hours (`fleet_window`). `⚠` when a run is stalled or paused for quota. Off until named |
| Machines | `mini 29% free · qwen3:14b`: free memory, then the loaded Ollama model. Hosts are split by ` / `. Unreachable is `mini ∅`. A loaded model that would leave under 15% free memory adds `⚠`. Off until named |
| Value | `≈ $412 of value this week`, an estimate. Off until `value = "on"` |
| Vitals | session duration, auto-compactions, lines, and the cost trend. Off until `vitals = "on"` |

Five lines are `lines = 5`:

```
🧠 Opus 5.5 │ 🪟 ctx ▓▓▓░░ +58% 84k left │ ♥ session 2h10m · +312 -40 · $4.20
left  ✻ claude 7d 30% │ ◎ codex 5h 1% →18:14 · 7d 31% │ ⬡ cursor+grok 19% →Thu 23:22 │ ✦ agy gemini 100% · claude+gpt 93% · argon 0% →Fri 15:35
today ▶ 0 running │ ✓ 7 done │ ✋ 6 need you │ ✗ 3 failed · ↻ 0 retried │ ⏸ 1 waiting on limit
older ✋ 5 need you │ ✗ 2 failed │ ⏸ 1 waiting on limit │ oldest 1d (website)
hosts mini 82% mem free · 25% cpu │ macbook 34% · 52% │ silver 73% · 13%
```

While Pharos jobs run, `▶` turns slowly (◐ ◓ ◑ ◒). A new Pharos event (a run merged or failed, a plan crossing 75/90/100%, a host offline) shows dimmed at the end of `today` for 30 seconds, a plan number that just moved is bold for 20 seconds, and a Pharos reading older than 5 minutes adds its age to `left`. `animate = "off"` drops the motion. Claude Code redraws on activity and every `refreshInterval` seconds; 10 keeps the motion visible at about 0.2 s of CPU per redraw.

Every plan number on `left` is the amount left. The reset (`→`) appears at 25% or less. Job counts follow Pharos: done is done, merged, or a run with no changes; need you is a run with commits waiting for a check, or a failed check; retried is a run another run replaced. `older` only counts open jobs from the last 7 days. Hosts use the nicknames in `hosts = ["studio=local", "backup=user@host"]`. When the terminal is narrow, `left` drops reset times first, then the agy claude+gpt bucket; `older` drops the oldest-job note; `hosts` drops CPU load. `marks = "none"` prints plain names.

A second line is `lines = 2` or `LIMITLINE_LINES=2`. When `COLUMNS` or `LIMITLINE_COLUMNS` is set, the lowest-priority segments drop until the row fits.

## Other tools

`limitline status` prints one row per tool from local files only. `limitline --host prompt` is the same data as a single line for tmux, starship, or a shell prompt. Unknown quotas are omitted. They are not guessed.

| Tool | How a status line is installed | What limitline can read locally |
| --- | --- | --- |
| Claude Code | `statusLine` command. `/limitline:install` | The stdin payload, then a snapshot at `~/.cache/limitline/claude.json` for other hosts. Stale after 15 minutes |
| Codex | Built-in `/statusline` items. No external command. `integrations/codex/install.sh` prints the item list and refuses `--write` | Newest `rate_limits` event across `~/.codex/sessions/YYYY/MM/DD/*.jsonl` from the last 8 days, 5h and 7d, each until its reset |
| Cursor | `statusLine` command in `~/.cursor/cli-config.json`. `integrations/cursor/install.sh` prints the snippet. `--write` is opt-in and backs up the file | Model and context from stdin. No local quota file. The plan percent is the shared `cursor+grok` reading below; without one, a labelled token estimate |
| Grok | `[ui.status_line]` command. `integrations/grok/install.sh` prints the snippet and refuses `--write` | Model, context, and cost from stdin. The plan name from `~/.grok/settings_cache.json`, and 7-day tokens and ledger cost summed from `~/.grok/sessions/**/usage.json`. The plan percent is the shared `cursor+grok` reading, live from `~/.grok/logs/unified.jsonl` |
| Antigravity (agy CLI and IDE) | No status-line command in the build that was checked | Live from `agy -p "/usage" --output-format json`, which `limitline refresh` runs (see [Antigravity and the Gemini app](#antigravity-and-the-gemini-app)) |
| Gemini app | None | `not measured (see gemini.google.com/usage)`; no CLI or local file exposes it |

Host snippets:

| Host | File |
| --- | --- |
| tmux | `integrations/tmux/status.conf` |
| starship | `integrations/starship/limitline.toml` |
| bash or zsh | `integrations/prompt/limitline.sh` |
| SwiftBar / xbar | `integrations/swiftbar/limitline.30s.sh` |
| JSON | `limitline --host json` |

With `lines = 2`, line 1 holds the model, context, and Claude windows, and line 2 holds the rest (fleet and machines come first there). Each line is fitted to the terminal width on its own. Claude Code passes the width as `COLUMNS`; when a line is too wide, the lowest-priority segment on that line is dropped first. Widths are counted in display columns, so bars and emoji no longer count as several characters.

Cursor and Grok can also run `limitline` with no arguments so the line is that tool's own stdin (model and context) instead of the multi-tool summary.

## Configuration

`~/.config/limitline/config.toml` is preferred. The older `config` key=value file still works. Environment variables win over either file.

```toml
theme = "minimal"
bar_width = 5
lines = 1
auto_compact = 95
auto_compact_warn = 80
segments = ["model", "style", "context", "limits", "burn", "cost", "git", "pr", "cache", "vim"]
```

`limitline config` prints that template and does not write it. The block below is the quiet default. `examples/delight.toml` turns on pace, sparklines, fresh wording, nudges, and vitals.

```toml
# pace = "on"
# spark = "on"
# nudges = "on"
# fresh = "on"
# value = "on"
# vitals = "on"
# alerts = "off"
# quiet = "22-7"
# sync_dir = ""
# fleet = "on"
# machines = "on"
# hosts = ["mini", "worker-1"]
# fleet_window = "12h"
# fleet_ttl = 180
# machines_ttl = 180
# ssh_timeout = 2
# mem_free_warn = 15
# cursor_week_tokens = 1000000   # only used when there is no cursor+grok reading
# grok = "on"
# grok_ttl = 180
# xai_ttl = 30                    # minutes between Grok plan fetches in limitline refresh
# jobs = "on"
# jobs_ttl = 180
```

## Pace

Pace compares the percent you have used with the percent of that window that has already elapsed. The 5-hour window is 5 hours ending at `resets_at`. The weekly window is 7 days ending at its `resets_at`. A gap of 8 points or more is `▲ 5h ahead of pace` (painted with the same yellow and red as the meter) or `▼ 7d under pace` (green). The weekly segment also shows the budget that is left, such as `~15%/day left for 4d`, when at least one day remains. `pace = "off"` or `LIMITLINE_PACE=0` removes it. Naming `pace` in `segments` turns it on without the env var.

## Sparklines

With `spark = "on"`, each status line stores the current percent under `~/.cache/limitline/`. The 5-hour file is the same one the burn projection reads. The 5-hour sparkline is the last five samples (`▁` through `█`). The weekly sparkline keeps the last sample of each UTC day for seven days: `7d ▁▃▃▅▅▇▄ 38%`. One sample is not enough to draw, so the first prompt stays unchanged.

## Nudges

`nudges = "on"` adds a short hint. When the Claude 5-hour meter is over 80%, limitline looks at the other local tools and suggests the one with the most room. Each tool counts by its most-used window, because a quiet 5-hour window cannot make up for an exhausted week. The hint is `→ codex 40%` when a tool's tightest window is under 50%, or `→ cursor ok` when nothing measured is roomy and Cursor has no local quota. If a cached worker is under 20% load and is not low on memory, the hint adds that machine: `→ codex 40% · mini idle`. An idle machine is the hint on its own when every measured window is at 50% or more. When context is at the auto-compact warning line, the nudge is `↯ compact soon: /compact`. A cold prompt cache still prints its reason (`cache cold: tools`). If the cache segment is off, the nudge carries that reason instead.

## Fleet

`fleet` is off on the Claude Code line until `segments` names it or `fleet = "on"`. The segment reads one cached line, `⚙ 3 run · 1 ✗`. Counts are running (including stalled), awaiting verify, and failed. `⚠` is added when any run is stalled or paused for quota.

Only recent runs are counted. A run that is `starting`, `running`, or `paused-quota` always counts. Any other run (awaiting verify, failed, stopped, stalled) counts only when its latest recorded time is inside `fleet_window`, default `12h`. The time used is a recorded finish time (`finished_at`, `ended_at`, or `completed_at`) when there is one, otherwise the modification time of the run's `stdout.log`, which only the agent writes, otherwise `last_activity`, `updated_at`, or `started_at`. `last_activity` is only a fallback because Pharos sweeps bump it on runs that finished hours earlier, and `state.json` and `events.jsonl` times are never used because every sweep rewrites them. Naive timestamps such as `2026-01-02T08:41:27` are read as local time. `fleet_window` takes `90m`, `12h`, `2d`, or a bare number of hours; `off` counts every run. limitline never edits Pharos files. Pharos is optional. When `~/.pharos/runs/*/state.json` exists, those files are the source. Otherwise limitline counts `cursor-agent`, `codex exec`, `claude -p`, `grok`, and `agy` in the process list. `limitline refresh` writes the cache. The status line never waits on that scan.

`limitline status`, `limitline watch`, and the SwiftBar menu add a Runs list: run id, tool, repository basename, status, and age. Runs outside the window move to an `Older` block with their own counts, such as `17 verify · 3 ✗ · 4 stopped, last active over 12h ago`. SwiftBar opens `stdout.log` for that run. Full paths are not printed.

## Machines and local models

`machines` is off on the Claude Code line until it is named or `machines = "on"`. The rows come from Pharos (`usage.json` → `hosts`), which probes each host; limitline never runs ssh. `limitline refresh` copies them into `machines.line`. Without Pharos there is no machines segment.

Each row is free memory, then the Ollama model that is loaded: `mini 29% free · qwen3:14b / laptop 62% free`. A host Pharos could not reach is `mini ∅`. `limitline status` adds CPU load and the installed count. If a loaded model leaves under `mem_free_warn` percent of memory free (default 15), the row gains `⚠`. Host nicknames and the ssh targets are Pharos settings (`hosts = [...]` in `~/.pharos/usage.toml`).

## Shared Cursor + Grok plan

Cursor and Grok are one subscription. The xAI plan covers Cursor, Grok, Grok Bot, and Grok Build, and xAI reports one number for it: the percent of this week's included usage.

### Live source: the Grok CLI log

The Grok CLI fetches that number from xAI whenever its interactive `/usage show` command runs, and logs one line to `~/.grok/logs/unified.jsonl` (`LIMITLINE_GROK_LOG`):

```json
{"ts":"2026-11-03T15:30:48.617Z","msg":"billing: fetched credits config","ctx":{"config":{"creditUsagePercent":74.0,"currentPeriod":{"type":"USAGE_PERIOD_TYPE_WEEKLY","end":"2026-11-06T05:22:35.070+00:00"}},"subscriptionTier":"SuperGrok Plus"}}
```

limitline reads the newest such line: `creditUsagePercent` is the percent, `currentPeriod.end` is the reset, `subscriptionTier` is the plan, and `ts` is when it was observed. The log is several megabytes and grows, so it is read backwards from the end in 512 KB chunks; a line that does not parse is skipped and the search goes further back.

Pharos keeps that line fresh (`pharos usage --refresh`). It opens `~/.grok/bin/grok` (`LIMITLINE_GROK_BIN`; `PATH` is not searched) in a pseudo-terminal, from an empty folder in limitline's cache, types `/usage show`, waits for the new log line, and exits. `grok -p "/usage show"` would not work: headless mode sends the text to the model. `/usage show` is a local command, so it uses no model tokens; it calls only xAI's billing API, with the Grok CLI's own login. limitline never reads `~/.grok/auth.json` or any token, and it opens no network connection itself.

limitline itself never starts grok. It reads the log only when it runs inside Grok or Cursor without Pharos (`LIMITLINE_TOOL=grok`); otherwise the reading comes from Pharos.

### Manual override

`limitline set xai-plan` writes a typed number to `~/.cache/limitline/xai-plan.json` (`LIMITLINE_XAI_PLAN`):

```bash
limitline set xai-plan 69 --resets "2026-11-05 09:00" --plan Super
```

`--resets` is local time. Anything in that file is labelled `manual`, whatever its `source` field says, so a typed number never passes for live data. The live reading wins whenever it is at least as new as the manual one. A newer manual value is shown, but with `manual` after the percent, and dimmed on the status line. `set` rewrites the status-line cache at once.

### Display

With a reading, Cursor and Grok are one row everywhere:

- `limitline status`: `cursor+grok 74% · resets Thu 23:22 · SuperGrok Plus · live · grok 7d 1.2M tok`
- host lines: `cursor+grok 74% · Thu 23:22 · grok 7d 1.2M tok`
- the Claude Code line (the `grok` segment): `cursor+grok +74% · Thu 23:22 · grok 7d 1.2M tok`
- a manual value: `cursor+grok 69% · manual · Thu 23:22 · ...`, dimmed

The reset is a local day and time. Grok's 7-day tokens stay as a detail. After 6 hours the reading is stale: it gains its age (`· 9h old`) and the status-line segment is dimmed. After 7 days it is hidden. Once the reset has passed, the percent belongs to an old window, so it is not shown: `cursor+grok reset Thu 23:22, no newer reading`. Nudges use the plan percent and no longer offer `→ cursor ok` for a plan that is nearly used up. History records live readings only.

Without a live or manual reading, Cursor falls back to the token estimate below, and every place that prints it says `estimate`. `grok = "on"` keeps working in both cases.

## Background jobs

Pharos runs show up in Fleet. Anything else, such as a mining pass or a backup, can report itself:

```bash
limitline job update mining --done 62 --total 1842 --failed 0 --status running --pid $$ --log ~/logs/mining.log
limitline job update backup --status ok
limitline job list
limitline job rm backup
```

Each job is one JSON file in `~/.cache/limitline/jobs/<name>.json` (`LIMITLINE_JOBS_DIR`): `name`, `machine` (this host unless `--machine`), `pid`, `pid_start` (when that pid's process started, looked up with `ps -o lstart=` on this machine), `started_at`, `done`, `total`, `failed`, `status`, `log`, and `updated_at`. Updates merge, so a script can send only `--done`. Names are letters, digits, `.`, `-`, and `_`. A job on this machine whose `pid` is gone, and whose status is not finished (`ok`, `done`, `failed`, `stopped`, and similar), is shown as `dead`. So is one whose pid is alive but belongs to a process that started after `pid_start`: pids are reused, and a recycled pid is not the job. Another machine's pid is never checked.

The Claude Code line shows `jobs mining 62/1842 ✗3 · backup ok 08:36`: running and dead jobs first, then finished jobs with their finish time, at most three and then `+N`. Finished jobs stay for `fleet_window` (default 12 hours); `limitline job list` shows all of them. The segment is on unless `jobs = "off"` or `segments` leaves it out, and it reads `jobs.line`, which `job update` and `limitline refresh` write, so the status line never parses job files. With no jobs folder, nothing is read. `limitline status`, `watch`, and the SwiftBar menu add a Jobs block with machine, status, counts, age, and the log file name.

## Providers

`limitline status` prints the tightest measured window first, then estimates. Claude still comes from the status-line snapshot. Codex comes from the newest session `rate_limits` event across every session file modified in the last 8 days, not only the newest file: `codex exec` runs from scripts leave many short files, and the newest one often has no event. Files are read newest first, the last line that parses in each is used (a half-written or malformed line is skipped, and a `codex` limit wins over another limit id such as `premium`), and the scan stops once a file is older than the best event found. A window is shown while its `resets_at` is ahead; without `resets_at`, while the event is younger than the window. When every window has reset, the row says `no current window (last reading 28h ago)`. Grok has no account window, so its row is never a percent and never sorts as a quota: `grok     SuperGrok Plus · 7d 1.2M tok · $3.00 at API rates · not a quota`. The plan is `settings.subscription_tier_display` inside the JSON-encoded `payload` of `~/.grok/settings_cache.json` (`LIMITLINE_GROK_SETTINGS`); no other field of that file is printed, and `~/.grok/auth.json` is never opened. Tokens are `session.totalTokens` summed over `~/.grok/sessions/**/usage.json` (`LIMITLINE_GROK_DIR`) whose `updatedAt` is in the last 7 days. A file without `updatedAt` or a numeric `totalTokens` is skipped, not dated by its modification time. Grok's own session docs say a session total includes history inherited by resume or fork, so a resumed or forked session can count that history twice. The dollar figure is `costUsdTicks` divided by 10^10 (Grok documents 1 USD = 10^10 ticks). It is what that usage would cost at API rates, not what a SuperGrok plan charges, and it is left out unless every counted file has `costUsdTicks`. It appears in `limitline status` and `watch` only; the status line shows the plan and tokens. A missing settings file or tier skips the plan, and a missing sessions folder skips the tokens. Cursor has no local quota file. When Pharos captured `usage.input_tokens` and `usage.output_tokens` on a cursor run, or a file passed as `LIMITLINE_CURSOR_LOG` has those fields, limitline estimates a weekly percent against `cursor_week_tokens` (default 1,000,000). That number is an estimate, not a quota reading: Cursor does not publish a token budget, and 1,000,000 is only a default you should replace with your own. It is input plus output tokens (cache reads are left out), each `usage` object counted once and added up, from cursor run logs that started or were written in the last 7 days, divided by that budget and capped at 100. It is shown with `~` everywhere (`cursor 7d ~100%`), `limitline status` prints the inputs (`7d ~100% estimate (3.1M of 1.0M tokens)`), the word `estimate` is printed in every host line, and estimated rows are listed after measured ones. A `~100%` means you used more tokens than the budget you set, not that Cursor will stop you. Antigravity and the Gemini app are described in their own section below. A local ledger at `~/.pharos/ledger.jsonl` or `research-spend.jsonl` (or `LIMITLINE_LEDGER`) adds an `api` row such as `spend $0.25` when the file exists. Rows with no window stay at the bottom.

## Antigravity and the Gemini app

Antigravity's buckets (Gemini models, Claude and GPT models, Gemini 4 Argon) come from Pharos, which runs agy's read-only `agy -p "/usage" --output-format json` (no agent turn, no tokens). limitline shows each bucket by name, with the reset when a bucket is low:

```
antigravity gemini-5h 0% · gemini-weekly 0% · 3p-5h 7% · 3p-weekly 5% · argon-weekly 100% resets Thu 21:35
```

The Gemini app's allowance (gemini.google.com) is not shown: no tool can read it.

## Reset moments

`fresh = "on"` replaces `↻1h42m` with `fresh in 1h42m`, and a later reset with `fresh Thu 09:00`. When a 5-hour reading falls from 40% or more to 20% or less, the next line starts with `✨`. That mark is stored next to the reset time and is not shown again for the same window.

## Value meter

`value = "on"` reads a local cost file and prints `≈ $412 of value this week`. The default file is `~/.claude/stats-cache.json`. `LIMITLINE_VALUE_FILE` points somewhere else. A `week_usd` (or `total_cost`) field is used as the number. Token counts are priced with the estimate table below, which is not an invoice. Amounts of $10 or more are rounded to the dollar.

| Family | Input / million | Output / million |
| --- | --- | --- |
| opus | $5 | $25 |
| sonnet | $3 | $15 |
| haiku | $1 | $5 |
| anything else | $3 | $15 |

## Session vitals

`vitals = "on"` replaces the cost segment with one session summary: `session 3m · compact ×2 · +10 -2 · $1.25↑`. Duration and line counts come from the cost object. The compaction count is `context_window.auto_compact_count` or `cost.auto_compactions`. The arrow compares this cost with the previous local sample: `↑` higher, `↓` lower, `·` flat.

## Alerts

`alerts` is `off`, `bell`, or `notify`. `bell` rings the terminal. `notify` asks macOS Notification Center through `osascript`. A crossing of 80% and of 95% on the 5-hour window alerts once for that reset time. Jumping straight past 95% marks 80% as already sent. `quiet = "22-7"` is quiet from 22:00 inclusive until 07:00, including overnight. A quiet hour does not count as the one alert, so it can still fire later in the same window. `LIMITLINE_ALERTS` overrides the file.

## Report

`limitline report` prints usage bars for each tool, the last week of local 5-hour samples by day, the busiest hours, the project folder names that showed up most, and the resets that are still ahead. Names are the last path segment only. A full path is dropped. `limitline report --md` prints the same facts as Markdown.

## History

`limitline refresh` (so the background refresher, every minute) and `limitline status` each record one sample per plan, at most every 10 minutes, into `~/.cache/limitline/history/<plan>.tsv` (`LIMITLINE_HISTORY_DIR`) as `epoch percent resets_at`. Samples older than 30 days are dropped. Plans are measured windows only: `claude-5h`, `claude-7d`, `codex-5h`, `codex-7d`, `cursor+grok-week`, and one per live Antigravity bucket, such as `antigravity-gemini-weekly`. A limit-hit event is not a measurement and is never recorded. A stale row, a Cursor token estimate, or a window merged from several machines is never recorded.

Finished jobs (ok, failed, stopped) and jobs found dead are appended once each to `~/.cache/limitline/jobs-history.jsonl` (`LIMITLINE_JOBS_HISTORY`), with their machine, counts, and finish time.

`limitline history [--days N]` prints one mark per day (the day's peak, `.` for a day with no sample) and the job history per machine:

```
plans
  claude-7d  ........................█.▄▁▅▅  peak 92% Oct 28 · last 58%

jobs by machine
  mini    2 jobs · 1 ok · 1 dead · 123 items · last crawler dead Nov 2 04:00
  worker  1 job · 1 failed · 1800 items · 42 item failures · last mining failed Nov 2 04:00
```

`limitline report --week` (and `--week --md`) is the weekly report: for each plan, the 7-day sparkline, the peak and its day, the average daily peak, the days over 80%, and how many window resets the samples saw, then the week's jobs by machine. Days are local days.

## Watch

`limitline watch` redraws every tool side by side every 5 seconds. In a terminal it is interactive: below the tools is a list of recent Pharos runs and background jobs, and keys act on the selected one.

| Key | Pharos run | Job on this machine |
| --- | --- | --- |
| `↑` `↓` or `k` `j` | select | select |
| `r` | `pharos resume <id>` | `SIGCONT`, status `running` |
| `s`, then `y` | `pharos stop <id>` | `SIGTERM`, status `stopped` |
| `p` | not available: Pharos has no per-run pause | `SIGSTOP`, status `paused` |
| `l` | `pharos logs <id>` in the pager | the job's `log` in the pager |
| `P` / `U` | `pharos pause` / `pharos unpause` (new runs are held or let in) | same |
| `q` | quit | quit |

`pharos` is found on `PATH`, or set `pharos = "/path/to/pharos"` in the config (or `LIMITLINE_PHAROS`) when it is not on `PATH`, as when it lives in a project's `bin/`. The pager is `$PAGER`, else `less -R +G`. A job is only signalled when it runs on this machine and its pid is still the reported process. Just before the signal, watch re-reads the job file and checks that the `pid`, `started_at`, and process start time all still match; otherwise it says so and sends nothing. After the signal, the status is written only if the file still names that pid and run, so a job that restarted meanwhile keeps its new file. A job file without `pid_start` (reported before 0.9.0) is not signalled; report the job again. A job reported from another machine says so instead. Stop always asks `y/n`. The status line itself never runs these commands.

If stdout is not a terminal, or `LIMITLINE_WATCH_ONCE=1`, it prints one plain frame and exits. `LIMITLINE_WATCH_KEYS="down s y q"` replays keys without a terminal, which is how the tests drive it.

## More than one Mac

Set `sync_dir` or `LIMITLINE_SYNC_DIR` to a folder you already sync, such as an iCloud or Dropbox directory. Each machine writes its own snapshot there. `limitline status`, `report`, and `watch` keep the higher percent for a shared window and mark it `×2` when two machines reported it. Only readings that can still be current are compared. A snapshot marked stale, a window whose reset has passed, and a window with no reset in a snapshot older than 15 minutes are all ignored, so an offline machine cannot hold an old number in place. Readings are compared only within one reset cycle (resets within 10 minutes of each other), and the newest cycle wins. Nothing is uploaded by limitline. `LIMITLINE_HOST` sets the folder name; otherwise the short hostname is used, with characters outside letters, digits, and `-` removed.

## Background refresh

The status line never runs ssh, a provider, or another tool's CLI. It reads `fleet.line`, `machines.line`, and `grok.line` from `~/.cache/limitline/`, and when they are old it starts one `limitline refresh` in the background. That refresh only re-reads Pharos's files (`usage.json`, run states) and `limitline job` reports. Measuring is Pharos's job: its `com.venkat.pharos.usage` launchd agent runs `pharos usage --refresh` every 2 minutes.

On macOS, `limitline install-refresher` installs a launchd agent (`~/Library/LaunchAgents/dev.limitline.refresh.plist`) that runs `limitline refresh` every 60 seconds, so idle terminals stay current. `limitline uninstall-refresher` removes it.

## Fleet and machines from another machine or session

Every Claude Code session on the same Mac shares one cache, so a second session needs nothing extra. Other machines appear because Pharos probes them (`hosts` in `~/.pharos/usage.toml`). A cloud-hosted session cannot reach your Macs or their Pharos files, so it shows only Claude's own line. `limitline doctor` says `session: cloud-hosted` when it detects this.

## Doctor

`limitline doctor` lists the tools on `PATH`, then the fleet sources it can see: whether the fleet and machines segments are on and why, Pharos runs inside and outside the window (or the process scan count), each cache's age against its TTL, the host list and where it came from, which hosts were reachable at the last refresh, whether the refresher is installed and loaded, and how many machines publish into `sync_dir`. When a segment would be empty, an `empty segments` block says why, such as `fleet: cache older than fleet_ttl; install-refresher keeps it fresh` or `machines: no hosts`. With a status payload on stdin it also lists which known fields are present. Host names are printed; ssh user names and addresses are not.

| Variable | Meaning |
| --- | --- |
| `LIMITLINE_THEME` | `minimal`, `powerline`, `ascii`, `pill`, `emoji`, or `mono` |
| `LIMITLINE_ASCII` | `1` forces `ascii` |
| `LIMITLINE_LINES` | `1` or `2` |
| `LIMITLINE_SEGMENTS` | Comma-separated segment names. Include `pace`, `spark`, `fresh`, `nudge`, `value`, or `vitals` to turn that segment on |
| `LIMITLINE_BAR_WIDTH` | Bar length, 1–40, default 5 |
| `LIMITLINE_GIT` | `1` or `0`. Default on, but only when the payload has a directory |
| `LIMITLINE_SESSION` | `1` shows the short session id |
| `LIMITLINE_BURN` | `0` hides the `pace ~1h35m` projection from recent 5-hour samples |
| `LIMITLINE_PACE` | `1` shows ahead/under pace. `0` hides it |
| `LIMITLINE_SPARK` | `1` draws sparklines |
| `LIMITLINE_FRESH` | `1` uses fresh wording and the sparkle |
| `LIMITLINE_NUDGES` | `1` adds the short hints |
| `LIMITLINE_VALUE` | `1` shows the weekly estimate |
| `LIMITLINE_VALUE_FILE` | Cost or token JSON for the estimate |
| `LIMITLINE_VITALS` | `1` shows session vitals |
| `LIMITLINE_ALERTS` | `off`, `bell`, or `notify` |
| `LIMITLINE_QUIET` | Quiet hours, such as `22-7` |
| `LIMITLINE_SYNC_DIR` | Folder of per-machine snapshots |
| `LIMITLINE_HOST` | This machine's name inside that folder |
| `LIMITLINE_FLEET` | `1` shows the fleet segment. `0` hides it |
| `LIMITLINE_MACHINES` | `1` shows the machines segment. `0` hides it |
| `LIMITLINE_HOSTS` | Comma-separated workers, such as `mini,worker-1` |
| `LIMITLINE_SSH_TIMEOUT` | SSH connect timeout in seconds, default 2 |
| `LIMITLINE_MEM_WARN` | Warn when a loaded model would leave free memory under this percent, default 15 |
| `LIMITLINE_FLEET_TTL` | Seconds a fleet cache line stays fresh, default 180 |
| `LIMITLINE_MACHINES_TTL` | Seconds a machine cache stays fresh, default 180 |
| `LIMITLINE_FLEET_WINDOW` | Count finished runs active within this window, default `12h`. `off` counts all |
| `LIMITLINE_REFRESH` | `0` stops the status line from starting a background refresh |
| `LIMITLINE_CURSOR_WEEK_TOKENS` | Denominator for the Cursor weekly estimate, default 1000000 |
| `LIMITLINE_GROK` | `1` shows the Grok plan and 7-day tokens on the status line. `0` hides it |
| `LIMITLINE_GROK_TTL` | Seconds the Grok cache line stays fresh, default 180 |
| `LIMITLINE_GROK_DIR` | Grok sessions folder, default `~/.grok/sessions` |
| `LIMITLINE_GROK_SETTINGS` | Grok settings cache, default `~/.grok/settings_cache.json` |
| `LIMITLINE_GROK_LOG` | Grok CLI log with the live plan reading, default `~/.grok/logs/unified.jsonl` |
| `LIMITLINE_GROK_BIN` | Grok CLI that `limitline refresh` opens for `/usage show`, default `~/.grok/bin/grok` |
| `LIMITLINE_XAI_TTL` | Minutes between plan fetches, default 30 (`xai_ttl`) |
| `LIMITLINE_XAI_TIMEOUT` | Seconds one plan fetch may take, default 45 |
| `LIMITLINE_XAI_FETCH` | `0` turns the plan fetch off |
| `LIMITLINE_AGY_FETCH` | `0` turns the Antigravity usage fetch off |
| `LIMITLINE_AGY_BIN` | agy binary for the fetch (config `agy`), default `agy` on `PATH` or in the usual install folders |
| `LIMITLINE_AGY_USAGE` | Antigravity usage cache, default `~/.cache/limitline/antigravity.json` |
| `LIMITLINE_AGY_TTL` | Minutes between Antigravity fetches, default 15 |
| `LIMITLINE_AGY_TIMEOUT` | Seconds before the agy command is stopped, default 30 |
| `LIMITLINE_CLAUDE_CACHE` | `0` turns off the cached Claude 7d fallback |
| `LIMITLINE_XAI_PLAN` | Manual override file, default `~/.cache/limitline/xai-plan.json` |
| `LIMITLINE_LEDGER` | JSONL file of `usd` amounts for the api row |
| `LIMITLINE_LINKS` | `1` adds OSC 8 links for a `owner/name` repo |
| `LIMITLINE_CODEX` | `auto` (default), `1`, or `0` |
| `LIMITLINE_COLUMNS` | Width cap. `COLUMNS` is used when this is unset |
| `NO_COLOR` | Disable ANSI colours |
| `LIMITLINE_CONFIG` | Alternate config file. `/dev/null` skips the home file |
| `LIMITLINE_DEBUG` | `1` saves stdin to `~/.cache/limitline/stdin.json` |
| `LIMITLINE_NOW` | Fixed unix time, used by tests |

## Privacy

limitline reads the status JSON a host already pipes in, an optional local config file, a cache directory it writes itself, and the local files named above. It does not send them anywhere. It does not read API keys or OAuth tokens. Debug output stays in the cache file you opted into. Session id display is off unless `LIMITLINE_SESSION=1`. The value file is read only when the value meter is on, and only for cost and token counts. The report and the Runs list keep repository folder names, not full paths. A sync folder is written only when you set one. From Grok it reads the plan name in `settings_cache.json` and the token and cost counters in `usage.json`; it never opens `~/.grok/auth.json`, and it does not print the identity or signature in the settings file. For the plan percent it reads the `fetched credits config` lines in `~/.grok/logs/unified.jsonl`. `limitline refresh` (and only refresh) starts the Grok CLI and types `/usage show`; the Grok CLI then calls xAI's billing API with its own login. `limitline refresh` also runs `agy -p "/usage" --output-format json`, a local command that spends no tokens; agy answers with its own login, and limitline keeps only the bucket percents and resets. It never opens agy's or the Gemini app's cookies, keychains, credential stores, or LevelDB/IndexedDB data. limitline itself opens no network connection and reads no token. Pharos is detected and used when its run files or machine list are present, and limitline still runs when they are absent. SSH runs only inside `limitline refresh`, with a timeout, and only for hosts you listed. The background refresher exists only if you run `limitline install-refresher` or `limitline schedule install`, and both run the same `limitline refresh`. Fleet and machine snapshots go to `sync_dir` only when you set one; they hold counts, host names, memory, load, and model names, not paths or user names.

## Tests

```bash
tests/run.sh
```

Fixtures cover a full payload, no rate limits, spend only, a near reset, usage over 80%, a context window near auto-compact, a cold prompt cache, a 60-column row, and every theme. The same script covers pace, sparklines, fresh wording, nudges, the value estimate, session vitals, alerts, the report, watch, and a two-machine merge. Fleet, machine, Cursor, Antigravity, Grok, and ledger fixtures are synthetic and use names such as `mini` and `worker-1`. ANSI colour codes are stripped before the comparison. The same fixtures are rendered once with `jq` and once with the python3 fallback. Codex fixtures cover many session files of mixed ages, a newest file with no event, a malformed last line, a second limit id, a 7-day window that outlives its 5-hour one, and events with no reset time. The shared plan has fixtures for a fresh, stale, reset, and week-old reading; jobs have fixtures for merging updates, a dead pid, a reused pid, another machine's pid, the finished-job window, and bad names. History has fixtures for the 10-minute sample gap, 30-day pruning, daily peaks, the weekly table, and jobs per machine, including a dead pid. The interactive watch is driven with replayed keys against a fake `pharos` and a real `sleep` process for job signals, and once in a pseudo-terminal. A warm status line, including a warm fleet, machine, or jobs cache, stays under 50 ms.
