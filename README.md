# limitline

A compact, colour-coded status line for Claude Code usage limits. Everything stays on this machine. limitline never opens a network connection.

```
Opus 5.5 │ 5h ▓▓▓░░ 62% ↻1h42m │ 7d ▓▓░░░ 38% ↻Thu 09:00 │ ctx 41% │ codex 5h 12% · 7d 55%
```

Green is under 50%, yellow is 50–80%, and red is over 80%. `NO_COLOR` turns the colours off. Reset times are relative under 24 hours (`↻1h42m`) and a weekday plus local time after that (`↻Thu 09:00`).

Missing fields are skipped. API-key sessions, older Claude Code builds, and empty input print nothing and still exit 0.

## Install with the plugin

Inside Claude Code:

```
/plugin marketplace add venkatvellaichamy/limitline
/plugin install limitline@limitline
/limitline:install
```

`/limitline:install` backs up `~/.claude/settings.json`, keeps every other key, and asks before replacing an existing `statusLine`. It points `statusLine` at the installed `bin/limitline`.

`/limitline:preview` prints a sample line. `/limitline:uninstall` removes the limitline status line and leaves the rest of the file alone.

## Manual install

```bash
git clone https://github.com/venkatvellaichamy/limitline.git
cd limitline
chmod +x bin/limitline
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

Restart Claude Code. The status line command receives one JSON object on stdin and must finish quickly, so limitline does no network I/O.

Try it:

```bash
echo '{"model":{"display_name":"Opus 5.5"},"rate_limits":{"five_hour":{"used_percentage":62,"resets_at":1762062120}},"context_window":{"used_percentage":41}}' \
  | LIMITLINE_NOW=1762056000 TZ=UTC bin/limitline
```

## What each segment reads

| Segment | Source |
| --- | --- |
| Model | `.model.display_name` |
| `5h` | `.rate_limits.five_hour.used_percentage` and `.resets_at` |
| `7d` | `.rate_limits.seven_day.used_percentage` and `.resets_at` |
| `spend` | `.rate_limits.spend_limit.used_usd`, `.limit_usd`, `.used_percentage` (only when present) |
| `ctx` | `.context_window.used_percentage`, with a few alternate names if that field is absent |
| `codex` | Newest `~/.codex/sessions/**/*.jsonl` rate-limit event, when it is under 6 hours old |

`resets_at` may be a unix timestamp or an ISO-8601 string. Codex primary window is the 5-hour limit and the secondary window is the weekly limit (`used_percent`, `resets_at`). That scan is cached for 30 seconds under `$TMPDIR`.

Set `LIMITLINE_DEBUG=1` to write the raw stdin JSON to `~/.cache/limitline/stdin.json` (override with `LIMITLINE_DEBUG_FILE`).

## Configuration

Optional file `~/.config/limitline/config` (`XDG_CONFIG_HOME` when set):

```
bar_width=5
codex=auto
color=on
```

Environment variables win over the file:

| Variable | Meaning |
| --- | --- |
| `LIMITLINE_BAR_WIDTH` | Bar length (1–40, default 5) |
| `LIMITLINE_CODEX` | `auto` (default), `1`, or `0` |
| `LIMITLINE_CONFIG` | Alternate config file. `/dev/null` skips the home file |
| `NO_COLOR` | Disable ANSI colours when set to any value |
| `LIMITLINE_DEBUG` | `1` saves stdin for field checks |
| `LIMITLINE_NOW` | Fixed unix time, used by tests |

## Cursor

There is no reliable local Cursor usage file that limitline can read without calling an API. A Cursor segment is left for later. Codex is included because its CLI already writes rate-limit events to local session logs.

## Privacy

limitline reads the status-line JSON Claude Code already pipes in, an optional local config file, and, when enabled, local Codex session logs. It does not send those anywhere. It does not read API keys. Debug output stays in the local cache file you opted into.

## Tests

```bash
tests/run.sh
```

Fixtures cover a full payload, no rate limits, spend only, a near reset, and usage over 80%. ANSI colour codes are stripped before the comparison. The same fixtures are rendered once with `jq` and once with the python3 fallback.
