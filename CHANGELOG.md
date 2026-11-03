# Changelog

## 0.8.2

- The `cursor+grok` plan percent is live. It is the newest `billing: fetched credits config` line in `~/.grok/logs/unified.jsonl`: `creditUsagePercent`, the reset from `currentPeriod.end`, the plan from `subscriptionTier`, observed at `ts`. The log is read backwards from the end in 512 KB chunks, so a multi-megabyte log costs one chunk; malformed lines are skipped.
- `limitline refresh` makes the Grok CLI write that line: it opens grok in a pseudo-terminal from an empty folder, types `/usage show` (a local command that uses no tokens and calls only xAI's billing API with the CLI's own login), waits for the new line, and always stops grok and its process group. At most every `xai_ttl` minutes (default 30), one at a time (a lock), with a 45-second limit. Never from the status-line render: the status line's own refresh runs with `--no-fetch`. If grok is missing or the fetch fails, the last reading stays and is marked stale. limitline never reads `~/.grok/auth.json` or any token. `limitline refresh --force` ignores the TTL.
- `limitline set xai-plan` is now a manual override. Its value is always labelled `manual` and dimmed, and the live reading wins whenever it is at least as new. History records live readings only.
- The plan reset shows as a local day and time: `cursor+grok 74% · Thu 23:22`. `limitline status` adds the source: `· live`.
- `limitline schedule install|uninstall|status`: a launchd agent, `com.limitline.refresh`, that runs `limitline refresh` every 15 minutes.
- `limitline doctor` reports the live reading, the last fetch, the manual override, and the schedule agent.

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
