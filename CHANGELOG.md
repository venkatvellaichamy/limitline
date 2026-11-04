# Changelog

## 0.12.1 - 2026-11-04

- **Line 2 is now `used`, drawn as small bars.** It used to print what was left, which read backwards next to the context meter, and made Antigravity look inverted (`gemini 100%` meant untouched, `argon 0%` meant spent). Every plan now shows how much is used, as a 5-cell bar in eighths with the same colours as the line 1 meters: `✻ claude 7d ███▌░ │ ⬡ cursor+grok ████▏ │ ✦ agy gemini ░░░░░ · argon █████`.
- `used = "both"` adds the number after each bar; `used = "pct"` shows numbers only (`LIMITLINE_USED` overrides). The ascii theme draws `###--`.
- The refill time (`→`) now appears at 75% used or more (Pharos's default cap), instead of at 25% left.
- On a narrow terminal the bars shrink to 3 cells after the refill times and the agy claude+gpt bucket are dropped.

## 0.12.0 - 2026-11-03

- **The split is complete: limitline shows, Pharos owns the data.** limitline now reads only Pharos's documented files (`usage.json`, `summary.json`, `usage-report.json`, the tail of today's event file) and writes only Claude's own reading to Pharos's inbox. It runs no Pharos command, reads no Pharos run file, scans no processes, and runs no ssh.
- Fleet and the Runs list come from `summary.json` (`recent`). The process scan, `fleet_window`, and the run-file parsing are gone; Pharos decides what is recent.
- Reported jobs moved to Pharos: `pharos job update|list|rm`. The `jobs` segment, the Jobs block, and watch show them from `summary.json`. `limitline job` only points at `pharos job`.
- `limitline watch` is read-only: it lists runs and jobs and opens a run's log, and the keys that used to resume, stop, pause, or signal now say to use Pharos.
- `limitline history` and `report --week` show Pharos's weekly report. limitline records no plan or job history of its own.
- Removed: `sync_dir` (and `lib/sync.py`); readings from other Macs come through Pharos. The Cursor reader no longer reads Pharos run logs; Pharos makes that estimate.
- `limitline config` and the docs no longer list host, ssh, or window settings; those are Pharos's (`~/.pharos/usage.toml`). `limitline doctor` gives a one-line notice for each old key still in your config.
- Nudges read the other tools' numbers from Pharos's `usage.json`; without Pharos there is no tool nudge.
- Still to do (needs Pharos 0.8.0 `pharos statusline`): with Pharos, take the Claude row from `usage.json` and stop relaying into `~/.pharos/inbox`.

- **Live, but quiet.** With `lines = 5`, the status line now shows that things are moving without asking for attention:
  - while Pharos jobs run, the `▶` on the `today` line turns slowly (◐ ◓ ◑ ◒), one step per redraw; it stands still when nothing runs;
  - a new event from Pharos's event log (a run merged or failed, a plan crossing 75/90/100%, a host going offline) appears dimmed at the end of the `today` line for 30 seconds; routine percent moves are not announced;
  - a plan number that just moved is bold for 20 seconds, then plain;
  - when Pharos's reading is older than 5 minutes, the `left` line ends with its age (`· 10m old`).
  `animate = "off"` (or `LIMITLINE_ANIMATE=off`) keeps the event note and the age but drops the motion and bold. The event note reads only the last 16 KB of today's event file; the change marker is one small cache file rewritten only when a number moves.
- **limitline shows usage; Pharos measures it.** The status line, `status`, `watch`, `report`, host lines, and the five-line view read Pharos's `~/.pharos/usage.json` (every plan and host) and `summary.json` (job counts). limitline no longer runs agy (`/usage`), the Grok plan fetch, the hosts ssh probe, or any reader for a tool it is not running in. Those moved to `pharos usage`, with their tests.
- On its own, limitline shows only the tool it runs in: Claude Code's limits from the status-line input, or with `LIMITLINE_TOOL=codex|grok|cursor` that tool's own local files.
- The status line relays Claude's reading, as-is, to `~/.pharos/inbox/claude.json` when `~/.pharos` exists. Claude Code gives these numbers only to the status-line program, so this is how Pharos sees them.
- Removed: `providers/antigravity`, `providers/gemini`, `lib/xai_fetch.py`, the hosts probe in `limitline refresh`, and the sync-folder fleet and machine snapshots. The Gemini app row is gone.
- `limitline doctor` reports whether Pharos's usage file is present and how old it is, and when the Claude relay last wrote.

- Five lines (`lines = 5`), the layout approved on 2026-11-03. Line 1 is this session only (model, context, time, cost, lines). Line 2, `left`, shows what is **left** on every plan in a fixed order with a mark per company: ✻ claude, ◎ codex, ⬡ cursor+grok, ✦ agy (gemini, claude+gpt, argon). A reset time is shown only at 25% or less left; red at 10% or less, yellow at 25% or less; a missing reading is `—`, never a guess. Line 3, `today`, counts Pharos jobs started today: running, done, need you, failed, retried, waiting on limit. Line 4, `older`, counts jobs from the last 7 days that are still open, and hides itself when there are none. Line 5, `hosts`, shows each computer by its nickname with free memory and CPU load. `marks = "none"` drops the marks. `lines = 1` and `lines = 2` are unchanged.
- Job counts come from Pharos's `~/.pharos/summary.json` (today's only).
- The Gemini app is no longer shown; no tool can read it.
- Machine readings fall back to `/proc` on Linux and WSL.
- `/limitline:install` asks for a nickname for this computer and any others, and turns on five lines.

## 0.9.0

Live data and safer jobs. (Briefly numbered 0.8.2 and 0.8.3 on two unmerged branches; released together as 0.9.0.)

- The `cursor+grok` plan percent is live. It is the newest `billing: fetched credits config` line in `~/.grok/logs/unified.jsonl`: `creditUsagePercent`, the reset from `currentPeriod.end`, the plan from `subscriptionTier`, observed at `ts`. The log is read backwards from the end in 512 KB chunks, so a multi-megabyte log costs one chunk; malformed lines are skipped.
- `limitline refresh` makes the Grok CLI write that line: it opens grok in a pseudo-terminal from an empty folder, types `/usage show` (a local command that uses no tokens and calls only xAI's billing API with the CLI's own login), waits for the new line, and always stops grok and its process group. At most every `xai_ttl` minutes (default 30), one at a time (a lock), with a 45-second limit. Never from the status-line render: the status line's own refresh runs with `--no-fetch`. If grok is missing or the fetch fails, the last reading stays and is marked stale. limitline never reads `~/.grok/auth.json` or any token. `limitline refresh --force` ignores the TTL.
- `limitline set xai-plan` is now a manual override. Its value is always labelled `manual` and dimmed, and the live reading wins whenever it is at least as new. History records live readings only.
- The plan reset shows as a local day and time: `cursor+grok 74% · Thu 23:22`. `limitline status` adds the source: `· live`.
- `limitline schedule install|uninstall|status`: a launchd agent, `com.limitline.refresh`, that runs `limitline refresh` every 15 minutes.
- `limitline doctor` reports the live reading, the last fetch, the manual override, and the schedule agent.
- Jobs: a reused pid is no longer taken for the job. `job update --pid` records `pid_start`, the process start time (`ps -o lstart=`). A live pid whose process started later is shown as `dead`.
- `watch` signals a job only after re-reading its file: the `pid`, `started_at`, and process start time must still match what was shown, or nothing is sent. A reused pid is never paused or killed.
- After a signal, the job's status is written only if the file still names the same pid and run, so a job that restarted in between is not marked `stopped`.

## 0.8.1

- Codex: an event that carries a 5h/7d window now always beats one without. Codex also writes `limit_id: "premium"` events with null windows, and when the newest session file held only one of those, the status showed "no current window".

## 0.8.0

- 30-day local history per plan. `limitline refresh` and `limitline status` record one sample per plan at most every 10 minutes into `~/.cache/limitline/history/`; estimates and stale rows are never recorded.
- `limitline history [--days N]` prints a daily-peak sparkline per plan and the job history per machine.
- `limitline report --week [--md]`: per-plan peak, average daily peak, days over 80%, and resets seen, plus the week's jobs by machine.
- Finished and dead jobs are kept in `~/.cache/limitline/jobs-history.jsonl`, once each, for 30 days.

## 0.7.0

- `limitline watch` is interactive in a terminal. It lists recent Pharos runs and jobs; `r` resumes, `s` stops (after `y`), and `l` opens logs, through `pharos resume|stop|logs <id>` for runs and signals for jobs on this machine. `p` pauses a job; Pharos has no per-run pause, so `P` and `U` run `pharos pause` and `pharos unpause`. Piped output and `LIMITLINE_WATCH_ONCE=1` still print one plain frame. The status line stays display-only.
- 0.6 (budgets and forecasts) is deferred; see ROADMAP.md.

## 0.5.0

- Cursor and Grok are one xAI plan. A new `xai-plan` provider reads `~/.cache/limitline/xai-plan.json` (`used_pct`, `resets_at`, `observed_at`, `plan`, `source`), and Cursor and Grok then render as one row: `cursor+grok 69% · Nov 5 · grok 7d 1.2M tok`. The reading is dimmed with its age after 6 hours, hidden after 7 days, and its percent is dropped once `resets_at` has passed. `limitline set xai-plan <pct> [--resets "YYYY-MM-DD HH:MM"] [--plan NAME]` writes the cache. Nudges use the plan percent.
- The Cursor token estimate shows only when there is no plan cache, and every printer now says `estimate` (`cursor 7d ~11% estimate`). Before, Cursor read as `~100%` against an invented 1M-token budget.
- Codex reads the newest `rate_limits` event across every session file modified in the last 8 days, not only the newest file, which is often a short `codex exec` run with no event. Malformed lines are skipped, a `codex` limit wins over `premium`, and each window lasts until its own `resets_at` instead of a 6-hour log cutoff. The status line, its python fallback, and `limitline status` all use the one scan in `providers/codex`.
- Background jobs: `limitline job update <name> --done N --total N --failed N --status running [--pid P] [--log PATH]`, `job list`, and `job rm`. One JSON file per job in `~/.cache/limitline/jobs/`. A job whose pid is gone on this machine is `dead`. A `jobs` segment (`jobs mining 62/1842 · backup ok 08:36`) is on by default once a job exists, and `limitline status`, `watch`, and SwiftBar gain a Jobs block.
- Gemini resets show as a local time, `quota 100% · resets Fri 09:35`. Antigravity's log stamps are now read as local time; they were read as UTC. `limitline report` dates resets in local time.
- `limitline doctor` reports the plan cache and jobs. ROADMAP.md lists what comes next.

## 0.4.2

- Grok shows its plan and 7-day usage: `grok SuperGrok Plus · 7d 1.2M tok`. The plan is the subscription tier in `~/.grok/settings_cache.json`; tokens are `session.totalTokens` from `usage.json` files updated in the last 7 days. `limitline status` and `watch` add the ledger cost (`costUsdTicks` / 10^10, at API rates) and say `not a quota`. Grok still has no window or percent, and `auth.json` is never read.
- Optional `grok` segment on the Claude Code line, off until `grok = "on"`, `LIMITLINE_GROK=1`, or `grok` in `segments`. It reads `grok.line`, which `limitline refresh` writes, so the status line never walks `~/.grok`.

## 0.4.1

- Two-line status lines fit each line to the width on its own, and widths are counted in display columns instead of bytes. Before, macOS awk counted every bar cell as three characters, so context, fleet, and machines were dropped even on a wide terminal. Context now outranks sparklines and pace; fleet and machines lead line 2.
- Machines show free memory, labelled: `mini 29% free · qwen3:14b`. It is the `memory_pressure` free percentage. The old unlabelled number was CPU load (1-minute load average over CPU count); it moved to `limitline status`. Hosts are split by ` / `. The probe adds Homebrew to `PATH`, so a model loaded on an ssh host is no longer missed.
- Fleet counts only live runs and runs active within `fleet_window` (default `12h`). Older runs are listed under `Older` in `limitline status`. Naive Pharos timestamps are read as local time, which also fixes run ages.
- `limitline install-refresher` and `uninstall-refresher`: an optional launchd agent that runs `limitline refresh` every 60 seconds at low priority. Cache TTLs default to 180 seconds.
- `sync_dir` now carries fleet and machine snapshots, so another machine can show them. `limitline doctor` reports each fleet source and why a segment is empty, and detects cloud-hosted sessions.
- The Cursor weekly number is marked as an estimate (`~`) everywhere, `limitline status` shows the tokens and budget behind it, and estimates sort after measured windows.

## 0.4.0

- Fleet segment for Pharos runs, or a local process scan when Pharos is absent. `⚠` marks a stalled or quota-paused run. Status, watch, and SwiftBar list runs and can open a run log.
- Machines segment from a background SSH refresh (60-second cache, strict timeout). Load, the loaded Ollama model, installed models, and a memory warning under 15% free. Unreachable hosts show `∅`.
- Cursor weekly estimate from local usage objects, Antigravity pause times from run state, and an API ledger row when one exists. The tightest provider is listed first.
- Nudges name the roomiest measured tool and an idle worker, such as `→ codex 12% · mini idle`.

## 0.3.0

- Pace against the window, sparklines from local snapshots, fresh reset wording, and a one-time sparkle after a reset.
- Opt-in nudges, an estimated weekly value, and session vitals. Each one can be turned off.
- Optional terminal bell or macOS notification at 80% and 95%, once per window, with quiet hours.
- `limitline report` (and `--md`), `limitline watch`, and an opt-in synced folder so two Macs share snapshots. No network.
- Themes `pill`, `emoji`, and `mono`, and a `/limitline:theme` picker.

## 0.2.0

- Claude Code line can show style, a context bar, auto-compact warning, spend, cost, pace, git, PR, cold cache, and vim mode. Segments are toggleable. Themes are minimal, powerline, and ascii.
- Providers for Claude, Codex, Cursor, Grok, and Gemini, plus `limitline status` and host lines for tmux, starship, a shell prompt, SwiftBar, and JSON.
- `preview`, `config`, and `doctor` commands. Config may be TOML. Version is 0.2.0.

## 0.1.0

- Initial release: Claude Code status line for 5-hour, weekly, and spend limits, plus context and an optional local Codex segment.
- Plugin marketplace, install, uninstall, and preview commands.
