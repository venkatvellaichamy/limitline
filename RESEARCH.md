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
