# limitline verification

Phase 1 checks below record the 0.1.0 line. Phase 2 is the current renderer. Fixture runs use `LIMITLINE_NOW=1762056000`, `TZ=UTC`, `LIMITLINE_CONFIG=/dev/null`, and `NO_COLOR=1` so the text is stable. Codex is off unless a fixture directory is passed.

`tests/run.sh`: 30 passed, 0 failed. A warm run of the full fixture averaged 30 ms.

## Fixture outputs

### full

```
Opus 5.5 │ 5h ▓▓▓░░ 62% ↻1h42m │ 7d ▓▓░░░ 38% ↻Thu 09:00 │ ctx 41%
```

### no rate limits

```
Opus 5.5 │ ctx 41%
```

### spend limit only

```
spend ▓▓░░░ 45% $4.50/$10
```

### near reset

```
Sonnet 4.5 │ 5h ▓▓▓▓▓ 96% ↻8m │ 7d ▓░░░░ 10% ↻30m
```

### over 80%

```
Opus 5.5 │ 5h ▓▓▓▓▓ 91% ↻3h15m │ 7d ▓▓▓▓░ 80% ↻Thu 09:00 │ spend ▓▓▓▓░ 88% $18/$20
```

80% stays yellow. 91% and 88% are red. `NO_COLOR=1` prints the same words with no ANSI codes.

### example line, with the fresh Codex fixture

```
Opus 5.5 │ 5h ▓▓▓░░ 62% ↻1h42m │ 7d ▓▓░░░ 38% ↻Thu 09:00 │ ctx 41% │ codex 5h 12% · 7d 55%
```

The fixture log has an older 99% event and a later non-limit line. The segment uses the last `rate_limits` event (12% and 55%). A log older than 6 hours produces no Codex segment. The same outputs come from the python3 path when `jq` is not on `PATH`.

## Live Codex logs

Checked against the local `~/.codex/sessions/**/*.jsonl` files. No session text and no percentages are copied here.

- Newest event shape: `payload.rate_limits.primary` and `.secondary`, each with `used_percent`, `window_minutes`, and integer `resets_at`.
- Primary `window_minutes` is 300 (5 hour). Secondary is 10080 (7 day).
- The newest event is under 6 hours old, so the segment is shown.
- Rounded percentages from `bin/limitline` matched that event. Exit code 0, stderr empty.

## Plugin manifests

`claude plugin validate` passed for the plugin directory and for `.claude-plugin/marketplace.json`. One non-blocking warning: no marketplace icon (`ICON_MISSING`). `~/.claude/settings.json` was not modified.

## Phase 2

`tests/run.sh`: 60 passed, 0 failed. A warm run of the full fixture averaged 27 ms. The Gemini fixture is `tests/fixtures/providers/gemini-cli.txt` because `*.log` is gitignored.

### Current fixture lines

```
Opus 5.5 │ ctx ▓▓░░░ ·41% │ 5h ▓▓▓░░ +62% ↻1h42m │ 7d ▓▓░░░ ·38% ↻Thu 09:00 │ $1.25
```

```
Opus 5.5 │ ctx ▓▓░░░ ·41% │ $0.12
```

```
spend ▓▓░░░ ·45% $4.50/$10
```

```
Sonnet 4.5 │ 5h ▓▓▓▓▓ !96% ↻8m │ 7d ▓░░░░ ·10% ↻30m
```

```
Opus 5.5 │ 5h ▓▓▓▓▓ !91% ↻3h15m │ 7d ▓▓▓▓░ +80% ↻Thu 09:00 │ spend ▓▓▓▓░ !88% $18/$20
```

```
Test │ ctx ▓▓▓▓░ !86% ↯ auto-compact in ~9%
```

```
Opus 5.5 │ cache cold: tools
```

With the fresh Codex fixture:

```
Opus 5.5 │ ctx ▓▓░░░ ·41% │ 5h ▓▓▓░░ +62% ↻1h42m │ 7d ▓▓░░░ ·38% ↻Thu 09:00 │ $1.25 │ codex 5h ·12% · 7d +55%
```

A 60-column cap keeps the model and the 5-hour window and drops the session id. `pace ~1h35m` appears when a local snapshot from 30 minutes earlier is lower. Themes ascii and powerline, a two-line layout, and `config.toml` are covered by the same script.

Provider fixtures return Claude 5h/7d from the snapshot, Codex 5h/7d from a session log, an empty Cursor quota, Grok session tokens with no window, and a Gemini quota window at 100% with a reset parsed from `Resets in`. A Codex log older than 6 hours is marked stale and has no windows. `limitline status`, `--host prompt`, and `--host swiftbar` were checked against those fixtures.

### Live Codex logs

Checked again for 0.2.0 against the local session logs. No session text and no percentages are copied here. The provider's rounded 5-hour and weekly values matched the newest `rate_limits` event. Exit code 0, stderr empty.

### Plugin manifests

`claude plugin validate` passed again for the plugin directory and for `.claude-plugin/marketplace.json` at version 0.2.0. The same non-blocking `ICON_MISSING` warning remains. `~/.claude/settings.json`, Codex config, Cursor config, and Grok config were not modified. Installers were run only in print mode, plus Codex `--write`, which refuses.

## Phase 3

`tests/run.sh`: 97 passed, 0 failed. A warm run of the full fixture averaged 44 ms. New segments stay off unless the config or an environment variable turns them on, so the 0.2.0 fixture lines are unchanged.

Pace on the full fixture adds `~15%/day left for 4d`. The over-80 fixture is ahead on both windows. The near-reset weekly window is under pace. A seeded history draws `5h ▁▃▅▆▅ 62%` and a seven-day `7d ▁▃▃▅▅▇▄ 38%`. Fresh wording and a single `✨` after a drop are covered. Nudges suggest `cursor ok` or `codex 12%`, and they name `/compact` near auto-compact. The value line is `≈ $412 of value this week` from a local cost field, or `≈ $10 of value this week` from token counts. Session vitals replace the cost segment. Alerts record 80 and 95 once per reset, stay quiet from 22:00 to 07:00, and a bell writes the terminal bell. `report` and `report --md` include project basenames and omit a full path planted in the activity file. `watch` prints one side-by-side frame. Two snapshot folders merge to `5h 80% ×2`. Themes pill, emoji, and mono match the README heroes.

## 0.4.0

Fleet fixtures under `tests/fixtures/fleet/` produce `⚙ 3 run · 1 ✗`, `⚙ 1 run ⚠` for a stalled run, `⚙ ⚠` for a quota pause, and `⚙ 1 verify`. A process-list fixture counts `cursor-agent`, `codex exec`, `claude -p`, `grok`, and `agy` as five running. Repository fields are reduced to a basename. Machine fixtures produce `mini 27% qwen3:14b`, `worker-1 ∅`, and `laptop 10% qwen3:14b ⚠`. The refresh path reads those fixtures and does not invoke `ssh`. Cursor usage of 110,000 tokens against the default million-token week is `7d 11%`. An Antigravity `paused-quota` state and a two-line ledger are covered. With warm fleet and machine caches, a status-line render averaged 32 ms, under the 50 ms budget. Names in the fixtures are `mini`, `worker-1`, `laptop`, and `demo`.

## 0.4.1

Problems found on a real two-Mac setup, each with a test. The installed 0.4.0 line, fed a Claude Code 2.1.317-shaped payload that has only a `seven_day` window, printed `🧠 Opus 5.5 │ 📅 7d ▓▓▓░░ +53% fresh Wed 04:00 │ 📈 7d ▅▅ 53%` even at 130 columns. Two causes: the width fit measured the joined two-line output as one line, and macOS awk measured bytes, so each bar cell counted as three. Claude Code does keep every non-empty line of status output, and it passes the terminal width as `COLUMNS`. The 5-hour segment was absent because that payload carried no `five_hour` window. The `7d` window was the only one Claude Code sent.

The machine number without a label was CPU load (1-minute load average over CPU count), not memory. `limitline refresh` and `memory_pressure`, run back to back on both hosts, now agree on the free percentage. A model loaded on an ssh host was invisible because non-interactive ssh has no Homebrew `PATH`.

Pharos stores `started_at` as naive local time, and 0.4.0 read it as UTC. Ages were off by the UTC offset. `state.json` modification times and the last event in `events.jsonl` all move together on every Pharos sweep, so they are not activity signals. Sweeps also bump `last_activity` on runs that finished hours earlier. A finished run is dated by a recorded finish time, else by its `stdout.log` time, which only the agent writes.

The Cursor `7d 100%` came from about 3.1M input and output tokens in a week of cursor run logs, against the 1,000,000 default denominator, capped at 100. It is a ratio to a number the user picks, not a Cursor limit, so it is now shown as `~`.


## 0.4.2

Grok has no local account quota, and that stays true: its row has no window, no percent, and does not sort with measured quotas. Two local facts are now shown. The plan is `settings.subscription_tier_display`, which sits inside the JSON-encoded `payload` string of `~/.grok/settings_cache.json`; the identity and signature in that file are never printed, and a fixture plants both to check it. Seven-day tokens are `session.totalTokens` from `usage.json` files whose `updatedAt` is in the last 7 days. Fixtures cover a file older than 7 days, a file without `updatedAt`, a malformed payload, and a file without `costUsdTicks` (cost is then left out). The cost conversion comes from Grok's own docs (`docs/user-guide/17-sessions.md` and `14-headless-mode.md`): 1 USD = 10^10 ticks, and billing on a plan lives in the TUI's `/usage`, so the dollar figure is labelled as API rates. On this Mac the line read `grok SuperGrok Plus · 7d 18.3M tok`, and `limitline status` read `SuperGrok Plus · 7d 18.3M tok · $13.48 at API rates · not a quota`.


## 0.5.0

On this Mac, `limitline status` printed `codex no local quota` while Codex was in use. The newest rollout file had no `rate_limits` event: of the last 20 files under `~/.codex/sessions/2026/11/03/`, the newest had 0 events and the next 19 had 1 each, because scripted `codex exec` runs write many short files. The old scan read only the newest file and dropped anything over 6 hours old. With the new scan the live provider returned `5h 63% · 7d 47%` with `plan_type` `plus`, in 32 ms over 65 files. Across the last 7 days there were 989 events with `limit_id` `codex` and 2 with `premium`, so a `codex` event wins within a file. The `stale.jsonl` fixture was 28 hours old but its `resets_at` values were still in the future, so under the new rule it would have shown 99%; its reset times now sit in the past, which is what a real 28-hour-old 5-hour window has, and a separate fixture keeps a 7-day window that has not reset.

The Antigravity log `cli.log` was created at 00:18 local time and its first line is stamped `E1102 00:18:38`, so the glog stamps are local time, not UTC (the file's birth time is also 00:18:34 local). 0.4 parsed them as UTC, which moved the reset by the UTC offset. The live quota line says `Resets in 111h16m45s` after `00:18:38` on Nov 2, which is Fri Nov 6 15:35 local (UTC-6). Read as UTC, the same line gives Fri 09:35, six hours early.

Cursor and Grok bill against one xAI plan whose usage dashboard reads `Weekly included usage 69% used, resets Nov 5`. No local file holds that number, so it is a cache that a person or a browser helper writes, and limitline says how old it is. The Cursor `~100%` came from tokens over the 1,000,000 `cursor_week_tokens` default; it is now shown only without the cache, labelled `estimate`.

Tests: 203 pass. Speed: `speed-31ms`, `warm-cache-32ms`, and a new `jobs-warm-29ms`, all under the 50 ms budget. Pre-existing expectations that changed: `provider-codex` (adds `"plan"`; the `fresh.jsonl` fixture's `limit_id` changed from `sample` to `codex`, the real value), `status-table` and `host-prompt` (Gemini gains `· resets Sun 07:00`), `cursor-estimate-status` (`~11% estimate (110k of 1.0M tokens)`), and the `stale.jsonl` fixture, as above.


## 0.7.0

`pharos --help` on this Mac lists `pause`, `unpause`, `resume`, `stop`, and `logs`. `pharos pause` and `pharos unpause` take no run id: they hold or reopen admissions for new runs. `resume`, `logs`, and `stop` take a `run_id`. So the watch maps `r`, `s`, and `l` to the selected run, and puts the global pause on `P` / `U` rather than pretending to pause one run. Tests replay keys against a fake `pharos` that records its arguments (`resume run-a,stop run-b,pause,unpause,logs run-b`), pause, resume, and stop a real `sleep` process registered as a job (checked with `ps -o stat=`), refuse a job reported from another machine, and run the real loop once in a pseudo-terminal to check that the arrow key moves the selection and `q` restores the cursor. 212 tests pass.


## 0.8.0

History is built only from rows `limitline status` already trusts. Estimated windows (the Cursor token ratio), stale rows, and windows merged from several machines are skipped, so a sparkline cannot be drawn from a guess. Each plan keeps at most one sample per 10 minutes, and every file is pruned to 30 days whenever any sample is written. A day's mark is that local day's peak. "Resets seen" counts samples whose `resets_at` moved later, so it only counts windows that limitline actually observed rolling over. Job history records a job once per `(machine, name, started_at)` when it finishes or when its pid is found gone. 226 tests pass. The speed tests are unchanged, because nothing on the status-line path reads history.
