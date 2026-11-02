# Local usage sources

Checked on this machine, with no network calls and no auth files opened. Versions: Claude Code 2.1.316, Codex CLI 0.166.0, Cursor Agent 2026.10.22, Grok 1.0.70, Antigravity CLI (`agy`) 1.4.12.

Nothing below is copied from a real session. Paths are the usual home locations.

## Claude Code

The live limits for a Claude Code session arrive on the status-line stdin object: `rate_limits.five_hour`, `rate_limits.seven_day`, and `rate_limits.spend_limit` when the account has one. The same object can carry model, context, cost, workspace, pull request, prompt-cache, and vim fields. All of them are optional.

There is no local file of the last rate-limit snapshot. `~/.claude/stats-cache.json` is an activity rollup (message counts, token totals, a cost figure per model). It has no `five_hour`, `seven_day`, or reset time. A search of `~/.claude` outside project transcripts found no `rate_limits` or `five_hour` cache. When limitline is not running inside Claude Code, the only Claude numbers it can show are the ones it saved itself on the previous status-line run.

## Codex CLI

Session logs under `~/.codex/sessions/**/*.jsonl` contain `event_msg` lines whose `payload.rate_limits` object has:

- `primary.used_percent`, `primary.window_minutes` (300), `primary.resets_at` (unix seconds)
- `secondary.used_percent`, `secondary.window_minutes` (10080), `secondary.resets_at`
- `credits`, `plan_type`, and several nullable account fields

The event `timestamp` is ISO-8601. Primary is the 5-hour window and secondary is the weekly window.

Codex does not run an arbitrary status command. The TUI has a built-in footer, configured with `/statusline` and stored as `tui.status_line`, an array of item ids. Item ids seen in the installed binary include `five-hour-limit`, `weekly-limit`, `context-remaining`, `context-used`, `used-tokens`, `model`, and `git-branch`. Those items read Codex's own live limits. `tui.status_line_use_colors` toggles theme colours. There is no command or script field. A limitline wrapper can still print `limitline status` in a normal shell, and the session log remains the source for Codex numbers outside the TUI.

## Cursor CLI

`cursor-agent` (`agent`) supports `--output-format stream-json` with `--print`. The installed help text does not document a usage object on those events, and this check did not start a session to look for one.

Cursor's own CLI status line is a command in `~/.cursor/cli-config.json`:

```json
{"statusLine": {"type": "command", "command": "limitline", "padding": 0}}
```

The stdin payload includes model, context window, workspace, vim mode, and version. It does not include rate limits or a spend cap. No local quota file turned up under `~/.cursor` (the config that is present has no usage block). Cursor usage inside this IDE is not available offline. limitline can still render the Cursor payload's model and context, and can show other tools from their local caches.

## Grok

Grok has a status line. In `~/.grok/config.toml`:

```toml
[ui.status_line]
type = "command"
command = "limitline"
```

The bundled user guide is explicit: the stdin JSON has model, context, cost, and workspace fields, and it does not include a rate-limit summary. `type = "disabled"` is the default. The command is read only from the user config, at startup.

`~/.grok/sessions/<scope>/<id>/usage.json` is a session ledger: token counts, `costUsdTicks`, and the model id. It is not an account quota and it has no reset time, so limitline does not turn those token totals into a percent.

## Gemini / Antigravity

`agy` 1.4.12 writes `~/.gemini/antigravity-cli/cli.log`. When the account is exhausted the log contains an error like `RESOURCE_EXHAUSTED (code 429): Individual quota reached. … Resets in <duration>`. The line is prefixed with a Go log stamp (`EMMDD HH:MM:SS`, month and day, no year). `~/.gemini/state.json` only tracks banner and tip counters. There is no structured quota file. limitline can read that one log line as "quota reached, 100%, reset after the stated duration" and otherwise reports nothing. It does not read OAuth files or conversation transcripts.

A Pharos run whose `tool` is `agy` and whose `status` is `paused-quota` carries `resume_at`. That is the same 100% window. Run logs can also contain the `quota reached` / `Resets in` line.

## Grok session ledger

`~/.grok/sessions/<scope>/<id>/usage.json` is still not an account quota. The fields present are `sessionId`, `updatedAt`, and `session` / `turns` objects with `inputTokens`, `outputTokens`, `cachedReadTokens`, `cacheCreationTokens`, `reasoningTokens`, `totalTokens`, `modelCalls`, `costUsdTicks`, `turnCount`, and `primaryModelId`. `modelUsage` repeats those counters per model id. There is no reset time and no used-percent. limitline keeps the Grok window empty and labels the source `usage.json`.

## Cursor usage objects

No quota file turned up in a shallow listing of `~/.cursor` (`usage.json` / `ai-usage.json` at the top of that directory would be read if one is added later). Pharos stores cursor-agent stream-json on `~/.pharos/runs/<id>/stdout.log`. Usage objects on those lines use `input_tokens`, `output_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, and `reasoning_output_tokens`. limitline sums input and output tokens from cursor runs in the last seven days, or from `LIMITLINE_CURSOR_LOG`, and divides by `cursor_week_tokens` (default 1,000,000) to estimate a weekly percent. The estimate is capped at 100. It is not an account balance.

## Pharos runs

Pharos is optional. Each run is `~/.pharos/runs/<id>/state.json` with `id`, `status`, `tool`, `repo`, `started_at`, and sometimes `resume_at`. Status values limitline counts are `starting`, `running`, `stalled`, `awaiting-verify`, `failed`, `verify-failed`, and `paused-quota`. `stalled` means no log or commit growth. `paused-quota` means a usage-limit line with a clock time to retry. `done` is only after verify. A machine list, when present, is `~/.pharos/machines.json` as `{"hosts":[{"name":"mini","ssh":"mini"}]}`. There is no hard dependency: missing files produce an empty segment.

## Ollama on a worker

`limitline refresh` asks each configured host, over SSH with `BatchMode` and a connect timeout, for load average, CPU count, physical memory, `memory_pressure`, `ollama ps`, and `ollama list`. Load percent is the one-minute load divided by the CPU count. The loaded model is the first `ollama ps` row. A warning is recorded when that model would leave free memory under 15% (the free percentage from `memory_pressure`, or total memory minus the model size). The status line reads the cached summary and does not open SSH.
