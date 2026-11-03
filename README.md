# limitline

Local usage limits for Claude Code, Codex, Cursor, Grok, and Gemini. The status line is one compact row. Nothing in this tool opens a network connection.

```
Opus 5.5 │ ctx ▓▓░░░ ·41% │ 5h ▓▓▓░░ +62% ↻1h42m │ 7d ▓▓░░░ ·38% ↻Thu 09:00 │ $1.25 │ codex 5h ·12% · 7d +55%
```

Green is under 50% (`·`), yellow is 50–80% (`+`), and red is over 80% (`!`). The mark stays when `NO_COLOR` strips the colour. Reset times are relative under 24 hours (`↻1h42m`) and a weekday plus local time after that (`↻Thu 09:00`).

Missing fields are skipped. Empty input still exits 0.

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

Check Claude's usage screen, note the 5-hour and weekly percents and when they reset, then do the same for Codex, remember that Cursor and Grok do not publish a local quota, and skim the Gemini log for a quota line. Repeat that every time the window moves. limitline reads those local files once per prompt and prints the row. The switches below add pace, a sparkline, a nudge, or a second machine when you want them, and each one can be turned off.

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
    "padding": 0
  }
}
```

Restart Claude Code. The status command receives one JSON object on stdin.

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
| `5h` / `7d` | `.rate_limits.five_hour` and `.seven_day`. Claude Code sends each window only when the account reports it, so a line can show `7d` alone |
| Spend | `.rate_limits.spend_limit` when present |
| Pace | projection from local 5-hour snapshots, such as `pace ~1h35m` |
| Cost | `.cost.total_cost_usd`, duration, and lines added or removed. `$0` is omitted |
| Git | branch, dirty `*`, ahead and behind, from the workspace directory. Cached with the rest of the short-lived files |
| PR | `.pr.number` and review state. OSC 8 links only when `links` is on |
| Cache | `cache cold: <cause>` only when the prompt cache is cold |
| Vim | `.vim.mode` |
| Codex | newest local Codex rate-limit event under 6 hours old |
| Session | first 6 characters of `.session_id`. Off unless you opt in |
| Pace | `▲ ahead of pace` or `▼ under pace` when usage and elapsed time differ by 8 points or more, plus `~15%/day left for 4d` on the weekly window. Off until `pace = "on"` |
| Sparkline | `5h ▁▃▅▆▅ 62%` from local snapshots, and a 7-day daily history. Off until `spark = "on"` |
| Fresh | `fresh in 1h42m`, and `✨` on the first prompt after usage drops into a new window. Off until `fresh = "on"` |
| Nudge | `→ codex 12% · mini idle`, `→ cursor ok`, or `↯ compact soon: /compact`. Off until `nudges = "on"` |
| Fleet | `⚙ 3 run · 1 ✗`, from a local cache of Pharos runs or a process scan. Only runs that are live or were active in the last 12 hours (`fleet_window`). `⚠` when a run is stalled or paused for quota. Off until named |
| Machines | `mini 29% free · qwen3:14b`: free memory, then the loaded Ollama model. Hosts are split by ` / `. Unreachable is `mini ∅`. A loaded model that would leave under 15% free memory adds `⚠`. Off until named |
| Value | `≈ $412 of value this week`, an estimate. Off until `value = "on"` |
| Vitals | session duration, auto-compactions, lines, and the cost trend. Off until `vitals = "on"` |

A second line is `lines = 2` or `LIMITLINE_LINES=2`. When `COLUMNS` or `LIMITLINE_COLUMNS` is set, the lowest-priority segments drop until the row fits.

## Other tools

`limitline status` prints one row per tool from local files only. `limitline --host prompt` is the same data as a single line for tmux, starship, or a shell prompt. Unknown quotas are omitted. They are not guessed.

| Tool | How a status line is installed | What limitline can read locally |
| --- | --- | --- |
| Claude Code | `statusLine` command. `/limitline:install` | The stdin payload, then a snapshot at `~/.cache/limitline/claude.json` for other hosts. Stale after 15 minutes |
| Codex | Built-in `/statusline` items. No external command. `integrations/codex/install.sh` prints the item list and refuses `--write` | Newest `~/.codex/sessions/**/*.jsonl` `rate_limits` event, under 6 hours old |
| Cursor | `statusLine` command in `~/.cursor/cli-config.json`. `integrations/cursor/install.sh` prints the snippet. `--write` is opt-in and backs up the file | Model and context from stdin. No local quota file |
| Grok | `[ui.status_line]` command. `integrations/grok/install.sh` prints the snippet and refuses `--write` | Model, context, and cost from stdin. `usage.json` is a session token ledger, not an account quota |
| Gemini / agy | No status-line command in the build that was checked | Last `quota reached` / `Resets in` line in the CLI log |

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
# cursor_week_tokens = 1000000
```

## Pace

Pace compares the percent you have used with the percent of that window that has already elapsed. The 5-hour window is 5 hours ending at `resets_at`. The weekly window is 7 days ending at its `resets_at`. A gap of 8 points or more is `▲ 5h ahead of pace` (painted with the same yellow and red as the meter) or `▼ 7d under pace` (green). The weekly segment also shows the budget that is left, such as `~15%/day left for 4d`, when at least one day remains. `pace = "off"` or `LIMITLINE_PACE=0` removes it. Naming `pace` in `segments` turns it on without the env var.

## Sparklines

With `spark = "on"`, each status line stores the current percent under `~/.cache/limitline/`. The 5-hour file is the same one the burn projection reads. The 5-hour sparkline is the last five samples (`▁` through `█`). The weekly sparkline keeps the last sample of each UTC day for seven days: `7d ▁▃▃▅▅▇▄ 38%`. One sample is not enough to draw, so the first prompt stays unchanged.

## Nudges

`nudges = "on"` adds a short hint. When the Claude 5-hour meter is over 80%, limitline looks at the other local tools and suggests the one with the most room: `→ codex 12%` when a measured window is under 50%, or `→ cursor ok` when nothing measured is roomy and Cursor has no local quota. If a cached worker is under 20% load and is not low on memory, the hint adds that machine: `→ codex 12% · mini idle`. An idle machine is the hint on its own when every measured window is at 50% or more. When context is at the auto-compact warning line, the nudge is `↯ compact soon: /compact`. A cold prompt cache still prints its reason (`cache cold: tools`). If the cache segment is off, the nudge carries that reason instead.

## Fleet

`fleet` is off on the Claude Code line until `segments` names it or `fleet = "on"`. The segment reads one cached line, `⚙ 3 run · 1 ✗`. Counts are running (including stalled), awaiting verify, and failed. `⚠` is added when any run is stalled or paused for quota.

Only recent runs are counted. A run that is `starting`, `running`, or `paused-quota` always counts. Any other run (awaiting verify, failed, stopped, stalled) counts only when its latest recorded time is inside `fleet_window`, default `12h`. The time used is the newest of `last_activity`, `finished_at`, `ended_at`, `completed_at`, `updated_at`, and `started_at` in `state.json`. File modification times are not used, because Pharos rewrites every `state.json` when it sweeps. Naive timestamps such as `2026-01-02T08:41:27` are read as local time. `fleet_window` takes `90m`, `12h`, `2d`, or a bare number of hours; `off` counts every run. limitline never edits Pharos files. Pharos is optional. When `~/.pharos/runs/*/state.json` exists, those files are the source. Otherwise limitline counts `cursor-agent`, `codex exec`, `claude -p`, `grok`, and `agy` in the process list. `limitline refresh` writes the cache. The status line never waits on that scan.

`limitline status`, `limitline watch`, and the SwiftBar menu add a Runs list: run id, tool, repository basename, status, and age. Runs outside the window move to an `Older` block with their own counts, such as `17 verify · 3 ✗ · 4 stopped, last active over 12h ago`. SwiftBar opens `stdout.log` for that run. Full paths are not printed.

## Machines and local models

`machines` is off on the Claude Code line until it is named or `machines = "on"`. `limitline refresh` collects each host with `ssh`, `BatchMode`, and `ConnectTimeout` (default 2 seconds). The status line only reads the cache, which stays fresh for 180 seconds (`machines_ttl`). A host that does not answer is `mini ∅`.

Each row is free memory, then the Ollama model that is loaded: `mini 29% free · qwen3:14b / laptop 62% free`. The percent is the `System-wide memory free percentage` that `memory_pressure` prints on that host, so you can check it there. When a host has no `memory_pressure` (not macOS), the row falls back to labelled CPU load, `worker-1 load 13%`. `limitline status` adds CPU load (1-minute load average over CPU count) and the installed count: `mini 29% free · qwen3:14b · load 27% · 2 installed`. Before 0.4.1 the line showed that CPU load with no label, which read like memory. If a loaded model leaves under `mem_free_warn` percent of memory free (default 15), either because free memory is already under that line or because the model itself is that large, the row gains `⚠`.

The probe adds `/opt/homebrew/bin` and `/usr/local/bin` to `PATH` before it runs `ollama`, because a non-interactive ssh session and launchd both start without them.

Hosts come from `hosts` or `LIMITLINE_HOSTS` (`mini` or `mini=user@host`). When that list is empty, limitline reads `~/.pharos/machines.json` if the file exists. It does not require Pharos. `name=local` runs the same probe on this Mac and does not use ssh. There is no network on the status-line path.

## Providers

`limitline status` prints the tightest measured window first, then estimates. Claude still comes from the status-line snapshot. Codex still comes from the newest session `rate_limits` event. Grok's `usage.json` is a session token ledger (`inputTokens`, `outputTokens`, `totalTokens`, `costUsdTicks`) and still has no account window. Cursor has no local quota file. When Pharos captured `usage.input_tokens` and `usage.output_tokens` on a cursor run, or a file passed as `LIMITLINE_CURSOR_LOG` has those fields, limitline estimates a weekly percent against `cursor_week_tokens` (default 1,000,000). That number is an estimate, not a quota reading: Cursor does not publish a token budget, and 1,000,000 is only a default you should replace with your own. It is input plus output tokens (cache reads are left out) from cursor run logs that started or were written in the last 7 days, divided by that budget and capped at 100. It is shown with `~` everywhere (`cursor 7d ~100%`), `limitline status` prints the inputs (`7d ~100% (estimate: 3.1M of 1.0M tokens)`), and estimated rows are listed after measured ones. A `~100%` means you used more tokens than the budget you set, not that Cursor will stop you. Antigravity (`agy`) still uses the last `quota reached` / `Resets in` line, and also a Pharos run whose status is `paused-quota`. A local ledger at `~/.pharos/ledger.jsonl` or `research-spend.jsonl` (or `LIMITLINE_LEDGER`) adds an `api` row such as `spend $0.25` when the file exists. Rows with no window stay at the bottom.

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

## Watch

`limitline watch` redraws every tool side by side every 5 seconds. In a terminal it clears the screen first. If stdout is not a terminal, or `LIMITLINE_WATCH_ONCE=1`, it prints one frame and exits.

## More than one Mac

Set `sync_dir` or `LIMITLINE_SYNC_DIR` to a folder you already sync, such as an iCloud or Dropbox directory. Each machine writes its own snapshot there. `limitline status`, `report`, and `watch` keep the higher percent for a shared window and mark it `×2` when two machines reported it. Nothing is uploaded by limitline. `LIMITLINE_HOST` sets the folder name; otherwise the short hostname is used, with characters outside letters, digits, and `-` removed.

## Background refresh

The status line never runs ssh or scans runs. It reads `fleet.line` and `machines.json` from `~/.cache/limitline/`, and when they are older than their TTL it starts one `limitline refresh` in the background and shows nothing for that segment until the next render. If nothing renders for a while, the segment can sit empty.

On macOS, `limitline install-refresher` installs a launchd agent (`~/Library/LaunchAgents/dev.limitline.refresh.plist`) that runs `limitline refresh` every 60 seconds with `ProcessType Background`, low-priority IO, and `Nice 10`. The agent runs a small launcher in `~/.local/share/limitline/`, which follows `claude plugin update` to the newest installed copy, so the agent keeps working after an update. `limitline uninstall-refresher` stops it and removes both files. `limitline doctor` reports whether it is installed and loaded. On Linux, run `limitline refresh` from cron instead; `install-refresher` prints the line.

## Fleet and machines from another machine or session

Every Claude Code session on the same Mac shares one cache, so a second session needs nothing extra. A session on a different machine sees only what that machine can collect. There are two ways to give it fleet and machine data.

1. Collect directly. On that machine, set `fleet = "on"` and `machines = "on"`, list the workers in `hosts` (such as `["mini=user@mini.local", "laptop=local"]`), and make sure `ssh -o BatchMode=yes user@mini.local true` works with a key and a known host entry, because refresh never prompts. Then run `limitline install-refresher`. Fleet counts there come from that machine's own Pharos runs or process list.
2. Share snapshots. Set the same `sync_dir` on each machine to a folder you already sync. Every `limitline refresh` writes `<sync_dir>/<host>/cockpit/fleet.json` and `machines.json`. When refresh runs elsewhere, it adds run counts from other machines' snapshots (each machine publishes only its own runs, so nothing is counted twice) and adds hosts it does not collect itself. Snapshots older than 15 minutes are ignored. The machine that publishes needs the refresher, or snapshots go stale.

A cloud-hosted Claude Code session (for example, one started from claude.ai) runs on a remote container. It cannot ssh to your Macs or read their Pharos runs. It can only show fleet and machine data from `sync_dir` snapshots, and only if that folder is reachable from inside the container, such as a mounted volume or a checked-out repository that a local machine commits snapshots to. Most desktop sync folders are not available there. `limitline doctor` says `session: cloud-hosted` when it detects this.

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
| `LIMITLINE_LEDGER` | JSONL file of `usd` amounts for the api row |
| `LIMITLINE_LINKS` | `1` adds OSC 8 links for a `owner/name` repo |
| `LIMITLINE_CODEX` | `auto` (default), `1`, or `0` |
| `LIMITLINE_COLUMNS` | Width cap. `COLUMNS` is used when this is unset |
| `NO_COLOR` | Disable ANSI colours |
| `LIMITLINE_CONFIG` | Alternate config file. `/dev/null` skips the home file |
| `LIMITLINE_DEBUG` | `1` saves stdin to `~/.cache/limitline/stdin.json` |
| `LIMITLINE_NOW` | Fixed unix time, used by tests |

## Privacy

limitline reads the status JSON a host already pipes in, an optional local config file, a cache directory it writes itself, and the local files named above. It does not send them anywhere. It does not read API keys or OAuth tokens. Debug output stays in the cache file you opted into. Session id display is off unless `LIMITLINE_SESSION=1`. The value file is read only when the value meter is on, and only for cost and token counts. The report and the Runs list keep repository folder names, not full paths. A sync folder is written only when you set one. Pharos is detected and used when its run files or machine list are present, and limitline still runs when they are absent. SSH runs only inside `limitline refresh`, with a timeout, and only for hosts you listed. The background refresher exists only if you run `limitline install-refresher`, and it runs the same `limitline refresh`. Fleet and machine snapshots go to `sync_dir` only when you set one; they hold counts, host names, memory, load, and model names, not paths or user names.

## Tests

```bash
tests/run.sh
```

Fixtures cover a full payload, no rate limits, spend only, a near reset, usage over 80%, a context window near auto-compact, a cold prompt cache, a 60-column row, and every theme. The same script covers pace, sparklines, fresh wording, nudges, the value estimate, session vitals, alerts, the report, watch, and a two-machine merge. Fleet, machine, Cursor, Antigravity, and ledger fixtures are synthetic and use names such as `mini` and `worker-1`. ANSI colour codes are stripped before the comparison. The same fixtures are rendered once with `jq` and once with the python3 fallback. A warm status line, including a warm fleet and machine cache, stays under 50 ms.
