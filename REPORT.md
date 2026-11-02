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
