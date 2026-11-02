# limitline verification

Phase 1 checks. Fixture runs use `LIMITLINE_NOW=1762056000`, `TZ=UTC`, `LIMITLINE_CONFIG=/dev/null`, and `NO_COLOR=1` so the text is stable. Codex is off unless a fixture directory is passed.

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
