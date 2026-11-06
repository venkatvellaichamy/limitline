# Changelog

## 0.16.0-beta.2 - 2026-11-05

- Rebuild Grok, jobs, fleet, and machine display caches in Pharos mode without fetching or falling back to provider readers.
- Read the shared Cursor/Grok plan directly from Pharos; show reading ages from the plan or usage.json instead of grok.line's modification time.
- Keep the 60-second display refresher available with Pharos. Doctor and `uninstall --refresh-jobs` identify and remove only the redundant fetch schedule, preserving the display job.
- Show old readings honestly. If a plan says `stale: true`, or its `observed_at` is older than the new `plan_stale_after` setting (3600 seconds by default), it now shows as unknown with its age, for example `codex ? · 94m old`. Its old percent is no longer drawn. This covers line 1 (codex, cursor+grok) and the five-line view (codex, cursor+grok, agy). A stale Codex plan used to vanish from line 1, or show as current when only the plan was old. **Behaviour change:** an idle Codex reading more than an hour old is now unknown. Raise `plan_stale_after` to keep it.
- A window whose `resets_at` has passed now counts as refilled (0%, no reset time), as Pharos counts it. The old "reset, no newer reading" no longer appears for Pharos plans. Claude's own cached 7d note on line 1 is not Pharos data, so it is unchanged.
- When Pharos is the reader and usage.json is missing, the line says "Pharos usage unavailable". The used line also says it when usage.json is older than `usage_stale_after` (900 seconds by default), for example `Pharos usage unavailable · 60m old`. Each plan then shows `?`. The older text was "pharos not running".
- A plan's reading time is its `observed_at`. usage.json's `generated_at` stands in only when the plan has no `observed_at` key at all. An `observed_at` that is there but not a positive epoch number (an ISO string such as `"2026-11-01T00:00:00Z"`, `0`, `null`, a bool) means the reading time is unknown, so the plan shows `?`. Before, a Codex plan with an ISO `observed_at` in a fresh usage.json drew `codex 5h ·17%`.
- A plan with a malformed `windows` (`"windows": 5`, or non-object entries) shows `?` for that plan, skipping bad entries. Before, an xai-plan with `"windows": 5` raised and blanked the whole used line, Claude and Codex included. Each plan on the used line is now read on its own, so one bad plan never blanks another plan's cells. On line 1, the same bad `windows` made the `grok.line` rewrite raise, which left the old cursor+grok percent on screen; it is now dropped to an empty list and the old percent is cleared.
- Ages under 2 hours are shown in minutes (`94m old`, `114m old`), then hours (`2h old`). Before, 114 minutes read `1h old`. This applies to line 1, the five-line view, and the cursor+grok text.
- README: in Pharos mode the 60-second refresh job (`dev.limitline.refresh`) stays, since refresh rebuilds the display lines; only the fetch schedule job (`com.limitline.refresh`) is redundant.
- Tests: the grok refresh check in `tests/run.sh` gets a real usage.json (it called a shell function through `env`, so it tested nothing) and has a negative control; `tests/layout.sh` checks the `?` unknown cell and the `Pharos usage unavailable` text; the timing checks use the median of 8 runs, not the best.
- `tests/run.sh` now runs `tests/test_reader.py`.
- `docs/audits/USAGE-RENDER-AUDIT-2026-11-05.md` records where each segment's number comes from in Pharos mode, and lists the remaining paths that can shadow Pharos data.

## 0.16.0-beta.1 - 2026-11-05

- Select the usage reader with `reader = "auto" | "pharos" | "limitline"` and `reader_freshness` (900 seconds by default). Fresh Pharos files disable limitline refresh work and the Claude inbox relay. Legacy layouts read Pharos directly.
- Skip refresh launch-agent installation with Pharos selected; doctor identifies redundant jobs. `uninstall --refresh-jobs [--dry-run]` boots out both agents and preserves their plists as `.bak` files.
- Keep existing behavior when Pharos is absent, stale, or explicitly bypassed.

## 0.15.0-beta.1 - 2026-11-05

### A clear first line

```
📁 pharos │ 🌿 main ↓2 │ 🧠 Opus 5.5 │ 🪟 ctx ▓▓░░░ 32% · 678k left │ ⏱ 60h32m · +17,898 −506 · $276.92
```

- **Git ahead/behind fix.** `git rev-list --left-right --count` prints `BEHIND<TAB>AHEAD`; the segment split on a space, so the raw text landed in both slots (`main ↑2	0 ↓2	0` for a branch 2 behind). It now shows only non-zero counts (`main ↓2`, `main ↑3`, `main ↑1 ↓2`), and never a tab.
- **Folder first.** New `dir` segment (the folder name; `dir_style = "home"` for `~/projects/app`) and `project` segment (the repository's name when it differs from the folder, as in a linked worktree; from `git rev-parse`, or `.workspace.project_dir` outside git). Both are on by default; `project` hides itself when it equals the folder.
- **Order.** Without a `segments` list, line 1 is folder, project, git, model, context, then everything else. This includes the five-line view's line 1. Git now ranks just below the folder, so with `lines = 2` it stays on line 1 and is no longer the first segment dropped on a narrow terminal.
- **Plain labels.** Context reads `ctx ▓▓░░░ 32% · 678k left` (the colour carries the level; plan windows keep their `·`/`+`/`!` marks), line counts get thousands separators and a real minus (`+17,898 −506`; ascii keeps `-`), and in the emoji theme vitals is `⏱ 60h32m · …` instead of `♥ session …`, without the cost trend arrow.
- **Old configs.** A config that names its own `segments` keeps 0.14's order and wording byte for byte. `tests/fixtures/legacy/` holds 0.14.0's output for four such configs; `tests/layout.sh` compares against it. That includes a 0.14 quirk kept on purpose: a `segments` list naming `vitals` without `cost` shows no vitals (the layouts below do not have it).

### Codex-style status line configuration

- **Every Codex `/statusline` item maps to a limitline item** where Claude Code sends the data: `current-dir` → `dir`, `project-name` → `project`, `git-branch` → `git`, `model-with-reasoning` → `model` + new `effort` (`.effort.level`), `context-*` → `ctx` (`context-window-size`, or `ctx_size = "on"`, adds `678k left of 1M`), `five-hour-limit`/`weekly-limit` → `5h`/`7d`, `*-tokens` → new `tokens` (`322k in · 2.4k out`), `estimated-thread-cost` → `cost`, `session-id` → `session`, `thread-title` → new `title` (`.session_name`), `codex-version` → new `version` (Claude Code's `.version`), `app-name` → new `app`. Codex ids work anywhere an item id does. `run-state`, `task-progress`, and `thread-credits` are not available in Claude Code; the README and `statusline list` say why.
- **Per-line layouts.** `line1 = [...]` … `line9 = [...]` list each line's items in order. `used`, `today`, `older`, and `hosts` place the Pharos lines. `lineN = []` drops a preset's line. A layout wins over `segments`/`lines`, except that with `lines = 5` and no preset a `lineN` changes only that line of the five-line view. Configs without a layout work unchanged. `LIMITLINE_LINE1`… and `LIMITLINE_PRESET` override the file.
- **Presets.** `preset = "minimal" | "default" | "full" | "pharos"` (pharos is the five-line view). A preset is a named layout; `lineN` overrides one line of it.
- **Picker.** `/limitline:statusline` shows the items with a live preview and asks for a preset, the items per line, and colours, or takes `--clear` / `KEY=VALUE` directly. Without Claude Code: `limitline statusline list | preview [KEY=VALUE…] | set KEY=VALUE… | --clear`. `set` and `--clear` edit only the layout keys (`--clear` keeps `lines`) in the file limitline reads (`config.toml`, the older `config` when it is the only one, a new `config.toml` when there is none; a symlink is followed), keep other settings and comments, write `<file>.bak`, and replace the file atomically. The preview writes nothing (`LIMITLINE_PREVIEW=1`: no cache, history, snapshot, or Pharos inbox file).
- **`colors = "on" | "off"`** (Codex's `status_line_use_colors`) is documented; it was already read as an alias of `color`.

### Also

- The 0.15 checks live in a new `tests/layout.sh`, which CI and the release workflow run after `tests/run.sh`. `tests/run.sh` keeps 0.14's checks. Its only edits: it pins `LIMITLINE_DIR=0`, because its fixtures send `cwd` and predate the folder segment, and it clears the new layout variables. Its expectations for the default line now read `ctx … 41%` without the dot, `−` for removed lines, and vitals without the cost arrow, as the new line 1 specifies.
- `reorder()` in the renderer now moves each segment's kind with it (the five-line view's line-1 filter read stale kinds after a reorder).
- `lib/fivelines.py` takes `LL_PICK=used,hosts` to print chosen lines by name.
- `limitline preview` / `theme` no longer write their sample 62%/38% into the cached Claude reading or relay it to `~/.pharos/inbox` (they now render with `LIMITLINE_PREVIEW=1`).
- Show Pharos 0.8 working (⚙) and blocked (⛔) counts, with blocked in yellow and failed in red. Show the first recent attention reason, capped at 80 characters and dropped first on narrow terminals. `jobs_detail = "counts"` (or `LIMITLINE_JOBS_DETAIL=counts`) hides reasons; the default is `"reason"`. Summary v1 files without the added keys render unchanged.

## 0.14.0 - 2026-11-04

- The `/limits` skill moved to Pharos (planned for Pharos 0.10.0, next to `/ramp`). limitline ships only status-line commands; skills that help an agent pick a tool belong to Pharos, which owns the numbers and the caps.

### The display stays honest when Pharos's files are bad

Every case has a test in `tests/test_hardening.py` (synthetic files in a temp `LIMITLINE_PHAROS_HOME` and `XDG_CACHE_HOME`; nothing reads the real `~/.pharos`), run by `tests/run.sh` as `hardening-unit`. The display changes below are to lines 2-5 of the five-line view (`lines = 5`). Line 1, and the one- and two-line modes, get the same version and clock-skew rules through `pharos_view` (a newer or future `usage.json` is not used for their Codex, Grok, and hosts segments) but no new wording.

- **Pharos files missing.** With a Pharos home but no `usage.json`, the used line ends `· pharos not running`; Claude's own window still shows from the status-line input. With no Pharos home at all, nothing changes: Claude only, no note.
- **Old reading.** When `usage.json` is over 15 minutes old, every plan but Claude, and the hosts line, show `—` with the age (`codex 7d — 1h ago`, `hosts — 1h ago`), never the old percent. A plan Pharos marks `stale` does the same with its own age. A plan's `observed_at` alone does not make it old (Codex's is its last rate-limit event, valid until the window resets): Pharos decides. The cursor+grok cell follows line 1's `grok_ttl` (180 s) for `grok.line`, which the refresher rewrites on every run; it used to keep its percent however old the file was. The cached Claude snapshot, used when the session input has no limits, is `—` with its age after 15 minutes.
- **Reset time already passed.** The window says `5h reset, no newer reading` (`5h reset` when the terminal is narrow) instead of disappearing. With Pharos, Codex now comes from Pharos's own reading in `usage.json`, so this also works through `bin/limitline` (`LIMITLINE_LINES=5`).
- **Partial or invalid JSON.** An unreadable field is `—` (`claude+gpt —`, `✓ — done`, `studio —`); a bool, NaN, infinity, or a negative number is not a reading. A truncated `usage.json` says `· pharos usage.json unreadable`. A bad field in `summary.json` (`older` not an object, `oldest_open` not an object) no longer blanks lines 2-5: each line is drawn on its own.
- **Unknown fields or a newer format.** Unknown fields are ignored. A `usage.json` with `version` above 1 is not drawn and the used line says `· pharos format v2 is newer than this limitline`; the line-1 caches (`pharos_view`) skip it too. A newer `summary.json` shows `today — pharos summary format vN is newer than this limitline`.
- **Clock skew.** A reading more than 2 minutes in the future is not fresh: plans show `—`, the line says `· pharos clock ahead`, and no age is negative. A future `summary.json` is not today's, and a future event is not shown as new. `limitline doctor` says so too.
- **Narrow terminal.** After the existing steps (refill times, the agy claude+gpt bucket, 3-cell bars), the used line drops whole plans from the right (agy, then cursor+grok, then codex; Claude stays), `today` and `older` keep only non-zero counts and then drop retried, done, waiting, running, failed in that order, and `hosts` drops hosts from the right. Every line fits when it can.
- **Slow disk.** Each Pharos file is read at most once per render (it was read up to 7 times while fitting), lines are only drawn as far as the fit needs, and only regular files under 4 MB are read, opened non-blocking, so a FIFO in place of `usage.json` cannot hang the status line. A render with 6 ms per file read stays under 50 ms.

### Linux

The first CI run on Ubuntu (2026-11-04) passed 215 of 226 checks. Every failing segment reads its cache through one function, and that function broke under GNU stat (reproduced on a Mac with GNU-style wrappers; the fix still needs its first Linux CI run to confirm): `bin/limitline` read a cache file's mtime with `stat -f %m FILE || stat -c %Y FILE` in one capture. On macOS (BSD stat) the first form works. GNU stat reads `-f` as `--file-system` and `%m` as a second file, so it printed FILE's file-system block to stdout and exited 1; the fallback then appended the mtime, and the combined text failed the "is a number" check. `fresh_line` treated every cache as missing, so the Grok/plan segment, the fleet and machines segments, the jobs segment on lines 1 and 2, and the two-line fit lost their segment, and `kick_refresh` saw its lock as ancient on every render.

- A new `file_mtime` tries `stat -c %Y` and `stat -f %m` separately and keeps only a numeric answer, so it works with BSD stat, GNU stat, and GNU coreutils on a Mac.
- The other platform-sensitive calls were checked: `date -j` and `date -r EPOCH` already fall back to GNU `date -d`, and the awk code uses no GNU-only features. No `sed -i`, `readlink -f`, or `grep -P` is used.
- `tests/run.sh` adds `gnu-*` checks that rerun the failing segments through GNU-style `stat` and `date` wrappers on macOS (on Linux the real tools run), so this is caught on a Mac before CI.
- The Linux CI job is now required (no `continue-on-error`) and also runs `tests/test_hardening.py`.

## 0.13.1 - 2026-11-04

- **`plan_resets = "always"`** (or `LIMITLINE_PLAN_RESETS=always`) shows when every window refills (`→04:00`, `→Thu 23:22`), not only windows at the cap. The default stays `"near-cap"`: the refill time appears once a plan reaches its cap. On a narrow terminal refill times are still the first thing dropped.

## 0.13.0 - 2026-11-04

### Line 2 shows what is used, in the view you pick

- **Line 2 is now `used`.** It used to print what was left, which read backwards next to the context meter and made Antigravity look inverted (`gemini 100%` meant untouched, `argon 0%` meant spent). Every number Pharos gives is used (Antigravity's `remaining_fraction` becomes `100 - remaining` in Pharos), and every view now fills as a plan is used.
- **Six views**, `plan_view` (or `LIMITLINE_PLAN_VIEW`), shown with live numbers:
  - `bar` (default) `claude 7d ███▌░`: 5 cells in eighths, so 70% and 82% look different;
  - `gauge` `claude 7d ▆`: one character;
  - `dots` `claude 7d ◕`: five steps;
  - `trend` `claude 7d ··▁▂▄▅▆`: the last 7 days from Pharos's `usage-report.json` `daily` (Pharos 0.7.1), today live, `·` before Pharos had a reading;
  - `cap` `cursor+grok ██████│▌░ over cap`: the bar with Pharos's cap (`cap_pct`, default 75) marked, `over cap` at or above it, and `▲` when the window is filling faster than its time is passing;
  - `none`: numbers only.
- `plan_numbers = "on"` adds the percent after any view. `plan_show = "left"` shows `100 - used` with the label `left`; colours, the cap, and the refill time still follow used, so a spent plan stays red either way.
- Colours match the line 1 meters: green, yellow from 50%, red above 80%. The refill time (`→`) appears at the plan's cap or above.
- On a narrow terminal the views drop refill times, then the agy claude+gpt bucket, then shorten bars, and `trend` and `cap` fall back to `gauge`.

### Releases, channels, and updates

- **CI** (`.github/workflows/ci.yml`): every pull request and push to `main` runs the version check, the unit tests, and the full suite on macOS. A Linux run is advisory for now.
- **Release** (`.github/workflows/release.yml`): pushing a tag `vX.Y.Z` or `vX.Y.Z-beta.N` checks the tag against every version file and the CHANGELOG, re-runs the suite on the tagged commit, publishes a GitHub release (a prerelease for beta) from the CHANGELOG section, and moves the channel branches: `beta` on every release (never backwards), `stable` on stable releases.
- **Channels**: `stable`, `beta`, and `dev` (`main`). Install a channel with `claude plugin marketplace add venkatvellaichamy/limitline#stable`.
- **New commands**: `limitline version` (version, channel, commit), `limitline update` (runs Claude Code's marketplace and plugin update), and `limitline channel stable|beta|dev --yes` (re-adds the marketplace on that branch; the status-line setting is untouched). These are the only limitline commands that touch the network, and only when you run them.
- `scripts/version.py check|bump|notes|channel|newer` and `RELEASING.md` describe the release steps.

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
