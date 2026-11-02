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

Presets live in `examples/`. `limitline preview` prints all three from the same sample.

## Install with the plugin

Inside Claude Code:

```
/plugin marketplace add venkatvellaichamy/limitline
/plugin install limitline@limitline
/limitline:install
```

`/limitline:install` backs up `~/.claude/settings.json`, keeps every other key, and asks before replacing an existing `statusLine`. It points `statusLine` at the installed `bin/limitline`.

`/limitline:preview` prints a sample line. `/limitline:config` prints a config template and does not write it. `/limitline:doctor` names the tools on `PATH` and which stdin fields are present, without printing their values. `/limitline:uninstall` removes the limitline status line and leaves the rest of the file alone.

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
| `5h` / `7d` | `.rate_limits.five_hour` and `.seven_day` |
| Spend | `.rate_limits.spend_limit` when present |
| Pace | projection from local 5-hour snapshots, such as `pace ~1h35m` |
| Cost | `.cost.total_cost_usd`, duration, and lines added or removed. `$0` is omitted |
| Git | branch, dirty `*`, ahead and behind, from the workspace directory. Cached with the rest of the short-lived files |
| PR | `.pr.number` and review state. OSC 8 links only when `links` is on |
| Cache | `cache cold: <cause>` only when the prompt cache is cold |
| Vim | `.vim.mode` |
| Codex | newest local Codex rate-limit event under 6 hours old |
| Session | first 6 characters of `.session_id`. Off unless you opt in |

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

`limitline config` prints that template and does not write it.

| Variable | Meaning |
| --- | --- |
| `LIMITLINE_THEME` | `minimal`, `powerline`, or `ascii` |
| `LIMITLINE_ASCII` | `1` forces `ascii` |
| `LIMITLINE_LINES` | `1` or `2` |
| `LIMITLINE_SEGMENTS` | Comma-separated segment names |
| `LIMITLINE_BAR_WIDTH` | Bar length, 1–40, default 5 |
| `LIMITLINE_GIT` | `1` or `0`. Default on, but only when the payload has a directory |
| `LIMITLINE_SESSION` | `1` shows the short session id |
| `LIMITLINE_BURN` | `0` hides the pace projection |
| `LIMITLINE_LINKS` | `1` adds OSC 8 links for a `owner/name` repo |
| `LIMITLINE_CODEX` | `auto` (default), `1`, or `0` |
| `LIMITLINE_COLUMNS` | Width cap. `COLUMNS` is used when this is unset |
| `NO_COLOR` | Disable ANSI colours |
| `LIMITLINE_CONFIG` | Alternate config file. `/dev/null` skips the home file |
| `LIMITLINE_DEBUG` | `1` saves stdin to `~/.cache/limitline/stdin.json` |
| `LIMITLINE_NOW` | Fixed unix time, used by tests |

## Privacy

limitline reads the status JSON a host already pipes in, an optional local config file, a cache directory it writes itself, and the local files named above. It does not send them anywhere. It does not read API keys or OAuth tokens. Debug output stays in the cache file you opted into. Session id display is off unless `LIMITLINE_SESSION=1`.

## Tests

```bash
tests/run.sh
```

Fixtures cover a full payload, no rate limits, spend only, a near reset, usage over 80%, a context window near auto-compact, a cold prompt cache, a 60-column row, and the three themes. ANSI colour codes are stripped before the comparison. The same fixtures are rendered once with `jq` and once with the python3 fallback. Provider fixtures are synthetic.
