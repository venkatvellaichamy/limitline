# limitline

A status line for AI plan limits. limitline **shows** usage; it does not measure other tools.

- **On its own,** it shows the tool it runs in: Claude Code's limits, model, context, and cost from the status-line input, or, inside Codex, Grok, or Cursor (`LIMITLINE_TOOL=codex|grok|cursor`), that tool's own local files.
- **With [Pharos](https://github.com/venkatvellaichamy/pharos),** it shows everything Pharos measured: every plan (Claude, Codex, Cursor + Grok, Antigravity), every host, and the job counts. Pharos writes `~/.pharos/usage.json` and `~/.pharos/summary.json`; limitline reads them.
- Claude Code hands its limits only to the status-line program, so limitline relays that one reading, as-is, to `~/.pharos/inbox/claude.json` when Pharos is installed.

Nothing in this tool opens a network connection, runs ssh, or starts another tool's CLI.

```
demo │ main ↓2 │ Opus 5.5 │ ctx ▓▓░░░ 41% · 590k left │ 5h ▓▓▓░░ +62% ↻1h42m │ 7d ▓▓░░░ ·38% ↻Thu 09:00 │ $1.25 │ codex 5h ·12% · 7d +55%
```

Line 1 starts with the folder, the git branch (only non-zero `↑ahead ↓behind`, `*` when dirty), the model, and the context. Green is under 50% (`·`), yellow is 50–80% (`+`), and red is over 80% (`!`). The mark on the plan windows stays when `NO_COLOR` strips the colour. Reset times are relative under 24 hours (`↻1h42m`) and a weekday plus local time after that (`↻Thu 09:00`).

Missing fields are skipped. Empty input still exits 0.

See [ROADMAP.md](ROADMAP.md) for shipped releases, hardening, and planned work.

## Themes

`minimal` (default):

```
Opus 5.5 │ ctx ▓▓░░░ 41% │ 5h ▓▓▓░░ +62% ↻1h42m │ 7d ▓▓░░░ ·38% ↻Thu 09:00 │ $1.25
```

`powerline`:

```
Opus 5.5  ctx ██░░░ 41%  5h ███░░ +62% ↻1h42m  7d ██░░░ ·38% ↻Thu 09:00  $1.25
```

`ascii`, also forced by `LIMITLINE_ASCII=1`:

```
Opus 5.5 | ctx ##--- 41% | 5h ###-- +62% in 1h42m | 7d ##--- ·38% in Thu 09:00 | $1.25
```

`pill` puts each segment in a rounded chip:

```
⟨Opus 5.5⟩ ⟨ctx ▓▓░░░ 41%⟩ ⟨5h ▓▓▓░░ +62% ↻1h42m⟩ ⟨7d ▓▓░░░ ·38% ↻Thu 09:00⟩ ⟨$1.25⟩
```

`emoji`:

```
🧠 Opus 5.5 │ 🪟 ctx ▓▓░░░ 41% │ ⏱ 5h ▓▓▓░░ +62% ⏳1h42m │ 📅 7d ▓▓░░░ ·38% ⏳Thu 09:00 │ 💵 $1.25
```

`mono` is plain text. It stays plain even when colour is on:

```
Opus 5.5  ctx 41%  5h 62% in 1h42m  7d 38% in Thu 09:00  $1.25
```

Example configs live in `examples/`. `limitline preview` and `limitline theme` print every theme from the same sample. `/limitline:theme` is the same picker inside Claude Code.

With pace, sparklines, and fresh wording turned on, the same session looks like this:

```
Opus 5.5 │ ctx ▓▓░░░ 41% │ 5h ▓▓▓░░ +62% fresh in 1h42m │ 5h ▁▃▅▆▅ 62% │ 7d ▓▓░░░ ·38% fresh Thu 09:00 │ 7d ▁▃▃▅▅▇▄ 38% │ ~15%/day left for 4d │ $1.25
```


## Why limitline

The number you care about is already on the machine: the status payload Claude Code just handed you, the newest Codex log line, a snapshot from the last prompt. limitline turns that into one row you can read without opening a dashboard. It does not phone home, and a missing field is skipped instead of guessed.

## Doing it by hand

Check Claude's usage screen, note the 5-hour and weekly percents and when they reset, then do the same for Codex, remember that Cursor and Grok do not publish a local quota, and check Antigravity's usage per model group. Repeat that every time the window moves. limitline reads those local files once per prompt and prints the row. The switches below add pace, a sparkline, a nudge, or a second machine when you want them, and each one can be turned off.


## Install, update, and channels

limitline ships as a Claude Code plugin from this repository. Pick a channel when you add it:

| Channel | Branch | Gets | Use it for |
|---|---|---|---|
| `stable` | `stable` | each stable release, `vX.Y.Z` | day to day |
| `beta` | `beta` | every release, including `vX.Y.Z-beta.N` | trying the next version |
| `dev` | `main` | every merged pull request | developing limitline |

```sh
claude plugin marketplace add venkatvellaichamy/limitline#stable
claude plugin install limitline@limitline
```

Then `/limitline:install` sets it as the status line. Later:

- `limitline version` prints the version, channel, and commit;
- `limitline update` runs `claude plugin marketplace update limitline` and `claude plugin update limitline@limitline`;
- `limitline channel beta --yes` moves to another channel (without `--yes` it only prints the steps). Your status-line setting stays as it is.

Releases are cut from tags; see [RELEASING.md](RELEASING.md). The status line itself never touches the network: only `update` and `channel` do, when you run them.

## Install with the plugin

Inside Claude Code:

```
/plugin marketplace add venkatvellaichamy/limitline#stable
/plugin install limitline@limitline
/limitline:install
```

Use `#beta` or no suffix (`main`, the dev channel) for the other channels above.

`/limitline:install` backs up `~/.claude/settings.json`, keeps every other key, and asks before replacing an existing `statusLine`. It points `statusLine` at the installed `bin/limitline`.

`/limitline:preview` prints a sample line. `/limitline:theme` previews every theme. `/limitline:config` prints a config template and does not write it. `/limitline:doctor` names the tools on `PATH` and which stdin fields are present, without printing their values. `/limitline:uninstall` removes the limitline status line and leaves the rest of the file alone.

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
    "padding": 0,
    "refreshInterval": 30
  }
}
```

Restart Claude Code. The status command receives one JSON object on stdin.

`refreshInterval` is a documented Claude Code `statusLine` field: it re-runs the command every N seconds (minimum 1), in addition to the usual redraws. Without it, Claude Code redraws a session's status line only on events in that session (a new message, a model or vim-mode change, a rate-limit reset), so an idle terminal keeps showing the fleet, machine, and plan numbers it last drew, and two idle terminals can disagree. With `refreshInterval: 30`, every terminal re-reads the shared caches at least every 30 seconds. A warm render takes about 30 ms. `limitline install` sets it.

```bash
echo '{"model":{"display_name":"Opus 5.5"},"rate_limits":{"five_hour":{"used_percentage":62,"resets_at":1762062120}},"context_window":{"used_percentage":41}}' \
  | LIMITLINE_NOW=1762056000 TZ=UTC bin/limitline
```

## What the Claude Code line can show

Each line's segments and their order are set with `line1` ... `line9`, a `preset`, or `/limitline:statusline` (see [Choosing what each line shows](#choosing-what-each-line-shows)).

| Segment | Source |
| --- | --- |
| Folder (`dir`) | the last part of `.workspace.current_dir` (or `.cwd`): `📁 pharos`. `dir_style = "home"` shows the path from your home folder (`~/projects/pharos`). On by default; `dir = "off"` hides it |
| Project (`project`) | the repository's name when it differs from the folder, as in a linked worktree (`feature-x │ limitline`) or a subfolder. From `git rev-parse` (the shared `.git` directory names the repository); outside git, the last part of `.workspace.project_dir`. On by default; hidden when it equals the folder |
| Model | `.model.display_name`, with a leading `Claude ` removed |
| Effort (`effort`) | `.effort.level`: `effort high`. Off until named. Codex's `model-with-reasoning` is `model` then `effort` |
| Tokens (`tokens`) | `.context_window.total_input_tokens` and `total_output_tokens`: `322k in · 2.4k out`. Off until named |
| Title (`title`) | `.session_name` (the `/rename` name or the AI title), cut at 40 characters. Off until named |
| Version (`version`) | `.version`, Claude Code's version: `v2.1.317`. Off until named |
| App (`app`) | `Claude Code`. Off until named |
| Style | `.output_style.name` when it is not `default` |
| Context | used percent, a bar, tokens left when the window size is known, and `↯ auto-compact in ~N%` once usage reaches the warn line (default 80, compact default 95) |
| `5h` / `7d` | `.rate_limits.five_hour` and `.seven_day`. Claude Code sends each window only when the account reports it, so a line can show `7d` alone. A new session gets no `rate_limits` until its first reply, so `7d` then shows the last reading any session cached in `~/.cache/limitline/claude.json`, with its age: `7d 67% · 4m ago`. A reply that carries only the 5-hour window keeps that cached week and its age. A cached week whose reset has passed is last week's number, so the segment says `7d reset Fri 08:40 · no newer reading` instead of a percent. `LIMITLINE_CLAUDE_CACHE=0` turns the fallback off |
| Spend | `.rate_limits.spend_limit` when present |
| Pace | projection from local 5-hour snapshots, such as `pace ~1h35m` |
| Cost | `.cost.total_cost_usd`, duration, and lines added or removed. `$0` is omitted |
| Git | branch, dirty `*`, and only the non-zero counts of commits ahead (`↑3`) and behind (`↓2`) the upstream, from the workspace directory |
| PR | `.pr.number` and review state. OSC 8 links only when `links` is on |
| Cache | `cache cold: <cause>` only when the prompt cache is cold |
| Vim | `.vim.mode` |
| Codex | newest `rate_limits` event across every Codex session file from the last 8 days, scanned by `providers/codex` (python3) at most every 30 seconds. Each window shows until its own reset time, so `codex 7d ·41%` can stay after the 5-hour window has reset |
| Jobs | `jobs mining 62/1842 · backup ok 08:36`, the jobs Pharos lists in `summary.json` (reported with `pharos job update`). `jobs = "off"` hides it |
| Grok / Cursor plan | With a plan reading: `cursor+grok +74% · Thu 23:22 · grok 7d 1.2M tok`, live from the Grok CLI log, dimmed with its age (`· 9h old`) after 6 hours. A manual value says `manual` and is always dimmed. Without it: `grok SuperGrok Plus · 7d 1.2M tok`, the plan name and the session tokens Grok recorded in the last 7 days, never a percent. Read from a line `limitline refresh` writes. Off until `grok = "on"` or `grok` (or `cursor+grok`) is named |
| Session | first 6 characters of `.session_id`. Off unless you opt in |
| Pace | `▲ ahead of pace` or `▼ under pace` when usage and elapsed time differ by 8 points or more, plus `~15%/day left for 4d` on the weekly window. Off until `pace = "on"` |
| Sparkline | `5h ▁▃▅▆▅ 62%` from local snapshots, and a 7-day daily history. Off until `spark = "on"` |
| Fresh | `fresh in 1h42m`, and `✨` on the first prompt after usage drops into a new window. Off until `fresh = "on"` |
| Nudge | `→ codex 12% · mini idle`, `→ cursor ok`, or `↯ compact soon: /compact`. Off until `nudges = "on"` |
| Fleet | `⚙ 3 run · 1 ✗`: Pharos's open work from `summary.json` (running, needs review, failed). `⚠` when a run waits on a plan limit. Off until named |
| Machines | `mini 29% free · qwen3:14b`: free memory, then the loaded Ollama model. Hosts are split by ` / `. Unreachable is `mini ∅`. A loaded model that would leave under 15% free memory adds `⚠`. Off until named |
| Value | `≈ $412 of value this week`, an estimate. Off until `value = "on"` |
| Vitals | how long the session has run, auto-compactions, lines changed, and cost: `session 60h32m · +17,898 −506 · $276.92` (`⏱ 60h32m · …` in the emoji theme). It takes the cost segment's place. Off until `vitals = "on"` |

Five lines are `lines = 5`:

```
📁 pharos │ 🌿 main ↓2 │ 🧠 Opus 5.5 │ 🪟 ctx ▓▓▓░░ 58% · 84k left │ ⏱ 2h10m · +312 −40 · $4.20
used  ✻ claude 7d ███▌░ │ ◎ codex 5h ░░░░░ · 7d ███▌░ │ ⬡ cursor+grok ████▏ →Thu 23:22 │ ✦ agy gemini ░░░░░ · claude+gpt ▍░░░░ · argon █████ →Fri 15:35
today ▶ 0 running │ ✓ 7 done │ ✋ 6 need you │ ✗ 3 failed · ↻ 0 retried │ ⏸ 1 waiting on limit
older ✋ 5 need you │ ✗ 2 failed │ ⏸ 1 waiting on limit │ oldest 1d (website)
hosts mini 82% mem free · 25% cpu │ macbook 34% · 52% │ silver 73% · 13%
```

While Pharos jobs run, `▶` turns slowly (◐ ◓ ◑ ◒). A new Pharos event (a run merged or failed, a plan crossing 75/90/100%, a host offline) shows dimmed at the end of `today` for 30 seconds, a plan number that just moved is bold for 20 seconds, and a Pharos reading older than 5 minutes adds its age to `used`. `animate = "off"` drops the motion. Claude Code redraws on activity and every `refreshInterval` seconds; 10 keeps the motion visible at about 0.2 s of CPU per redraw.

Every view on `used` shows the amount used, like the context meter on line 1: empty is a fresh allowance, full is spent, and the colours are the same (green, yellow from 50%, red above 80%). Pick one with `plan_view`:

| `plan_view` | Looks like | Notes |
|---|---|---|
| `bar` (default) | `claude 7d ███▌░` | 5 cells in eighths, so 70% and 82% (`████▏`) look different |
| `gauge` | `claude 7d ▆` | one character per window |
| `dots` | `claude 7d ◕` | five steps: ○ ◔ ◑ ◕ ● |
| `trend` | `claude 7d ··▁▂▄▅▆` | the last 7 days from Pharos (`usage-report.json` `daily`), today live; `·` is no reading yet |
| `cap` | `cursor+grok ██████│▌░ over cap` | `│` is Pharos's cap for that plan; `▲` means filling faster than the window's time passes |
| `none` | `claude 7d 70%` | numbers only |

`plan_numbers = "on"` adds the percent after any view (`claude 7d ▆ 70%`). `plan_show = "left"` shows `100 - used` instead and labels the line `left`; colours, the cap, and the refill time still follow used. The refill time (`→`) appears at the plan's cap (Pharos's `cap_pct`, default 75%) or above; `plan_resets = "always"` shows it for every window. Pharos 0.8 adds `⚙ working` (system or agent acting) and `⛔ blocked` (needs its owner). Blocked and need you are yellow; failed is red. `need_you` counts only owner `you`. By default, the first matching recent row’s reason follows its attention count (up to 80 characters); `jobs_detail = "counts"` or `LIMITLINE_JOBS_DETAIL=counts` hides it. Narrow terminals drop the reason first. Older summary files keep their existing display. Job counts follow Pharos: done is done, merged, or a run with no changes; need you means Pharos assigned the next action to you; retried is a run another run replaced. `older` only counts open jobs from the last 7 days. Hosts use the nicknames set in Pharos (`hosts = [...]` in `~/.pharos/usage.toml`). When the terminal is narrow, `used` drops refill times first, then the agy claude+gpt bucket, then shortens the bars to 3 cells (and `trend` or `cap` becomes `gauge`), then whole plans from the right (agy, cursor+grok, codex; Claude stays); `today` drops the event note, then zero counts, then retried, done, waiting, running, working, failed and blocked in that order; `older` drops the oldest-job note, then counts in the same order; `hosts` drops CPU load, then hosts from the right. `marks = "none"` prints plain names.

With `lines = 5`, limitline never shows a number it cannot vouch for. When Pharos's `usage.json` is over 15 minutes old, or Pharos marks a plan stale, the plan shows `—` and its age (`codex 7d — 1h ago`); cursor+grok follows `grok_ttl` like line 1; a window whose reset time has passed says `5h reset, no newer reading`; an unreadable field is `—`; a reading more than 2 minutes in the future is not fresh (`· pharos clock ahead`). The end of `used` says when Pharos is installed but not running (`· pharos not running`), when `usage.json` is unreadable, and when its format is newer than this limitline understands (`version` above 1; unknown fields are ignored). Each Pharos file is read once per redraw, and only if it is a regular file.

A second line is `lines = 2` or `LIMITLINE_LINES=2`. When `COLUMNS` or `LIMITLINE_COLUMNS` is set, the lowest-priority segments drop until the row fits.

## Choosing what each line shows

Like Codex's `/statusline`, you pick the items on each line and their order.

```toml
# ~/.config/limitline/config.toml
preset = "full"                              # a named layout (below)
line1 = ["dir", "git", "model", "ctx"]       # overrides the preset's line 1
line2 = ["5h", "7d", "cost"]
line3 = []                                   # drops the preset's line 3
colors = "on"                                # or "off", like Codex's status_line_use_colors
```

- `lineN = [...]` lists line N's items in order (`line1` to `line9`; a comma string works too). Items are limitline ids or Codex ids (table below). Only listed items show; `cost` and `vitals` share one slot, so `vitals = "on"` fills a `cost` slot. Each line drops its lowest-priority items when the terminal is narrow.
- `used`, `today`, `older`, and `hosts` are whole lines from Pharos (the five-line view's lines 2-5); a line that names one is that line.
- A layout (`preset` or any `lineN`) wins over `segments` and `lines`, with one exception: with `lines = 5` and no `preset`, `lineN` changes only that line of the five-line view (the `pharos` preset). `LIMITLINE_PRESET` and `LIMITLINE_LINE1` ... `LIMITLINE_LINE9` override the file.
- Without a layout, line 1 is folder, project, git, model, context, then everything else, with the wording shown above (`ctx ▓▓░░░ 32% · 678k left`, `+17,898 −506`).
- **A config with its own `segments` list renders exactly as before 0.15**: its order, and 0.14's wording (`ctx ▓▓░░░ ·32% 678k left`, `+17898 -506`). `tests/fixtures/legacy/` holds 0.14.0's output for such configs.

### Presets

| `preset` | Lines |
| --- | --- |
| `minimal` | 1: `dir`, `git`, `model`, `ctx` |
| `default` | 1: `dir`, `project`, `git`, `model`, `ctx`, `style`, `5h`, `7d`, `spend`, `burn`, `cost`, `jobs`, `pr`, `cache`, `vim`, `codex` (the same as no layout, without the opt-in extras) |
| `full` | 1: `dir`, `project`, `git`, `model`, `effort`, `style`, `ctx`, `tokens`, `cost` · 2: `5h`, `7d`, `spend`, `codex`, `grok`, `jobs`, `pr`, `cache`, `vim`, `title`, `version`, `session` |
| `pharos` | the five-line view: 1: `dir`, `project`, `git`, `model`, `ctx`, `style`, `cost`, `pr`, `cache`, `vim` · 2: `used` · 3: `today` · 4: `older` · 5: `hosts` |

### Every item, and Codex's names for it

Codex 0.166's `/statusline` items, and what limitline shows for each in Claude Code. Every limitline id also works in `segments`.

| limitline id | Codex item | Data |
| --- | --- | --- |
| `dir` | `current-dir` | `.workspace.current_dir` (`.cwd`) |
| `project` | `project`, `project-name` | `git rev-parse --show-toplevel --git-common-dir`; else `.workspace.project_dir` |
| `git` | `git-branch` | `git` in the current folder |
| `model` | `model-with-reasoning` (= `model`, `effort`) | `.model.display_name` |
| `effort` | `reasoning` | `.effort.level` |
| `ctx` | `context-remaining`, `context-used`, `context-window-size` | `.context_window.used_percentage`, `context_window_size`, `total_input_tokens`: used % and tokens left in one segment. `context-window-size` (or `ctx_size = "on"`) adds the window: `678k left of 1M` |
| `5h` | `five-hour-limit` | `.rate_limits.five_hour` |
| `7d` | `weekly-limit` | `.rate_limits.seven_day` (or the last cached reading) |
| `tokens` | `used-tokens`, `total-input-tokens`, `total-output-tokens` | `.context_window.total_input_tokens`, `total_output_tokens` |
| `cost` | `estimated-thread-cost` | `.cost.total_cost_usd`, `total_duration_ms`, lines |
| `session` | `session-id` | `.session_id` (first 6 characters) |
| `title` | `thread-title` | `.session_name` |
| `version` | `codex-version` | `.version` (Claude Code's version) |
| `app` | `app-name` | `Claude Code` (the only host of this status line) |
| `style`, `spend`, `vitals`, `pr`, `cache`, `vim`, `burn`, `pace`, `spark`, `codex`, `grok`, `jobs`, `fleet`, `machines`, `nudge`, `value` | none | see the table above |
| `used`, `today`, `older`, `hosts` | none | whole Pharos lines |
| not available | `run-state` | Claude Code's status-line input has no running/idle state, and limitline does not read the transcript |
| not available | `task-progress` | the input has no task list or progress |
| not available | `thread-credits` | Claude Code has no credit balance; `spend` shows a spend limit when the account has one |

### The picker

`/limitline:statusline` lists the items, shows a live preview, asks for a preset, the items on each line, and colours, previews the result, and saves it. `/limitline:statusline --clear` goes back to the default line; `/limitline:statusline line1=dir,git,model,ctx` sets it directly. The same, without Claude Code:

```sh
limitline statusline list                                   # every item, its Codex id, presets, and the current layout
limitline statusline preview                                # the line as configured, for a sample session in this folder
limitline statusline preview line1=dir,git,model,ctx        # with changes, not saved
limitline statusline set line1=dir,git,model,ctx line2=5h,7d colors=off
limitline statusline set preset=pharos
limitline statusline --clear                                # removes preset, line1-9, segments, colors (keeps lines)
```

`set` and `--clear` change only those keys in the config file limitline reads (`config.toml`, the older `config` when that is the only one, or a new `config.toml` when there is none; a symlinked file is edited where it lives), keep every other setting and comment, save the previous file as `<file>.bak`, and replace the file in one step. An unknown item is refused and nothing is written. The preview renders a sample session (in the folder you run it from) and writes nothing: no cache, history, Claude snapshot, or Pharos inbox file.

## Other tools

`limitline status` prints one row per tool from local files only. `limitline --host prompt` is the same data as a single line for tmux, starship, or a shell prompt. Unknown quotas are omitted. They are not guessed.

| Tool | How a status line is installed | What limitline can read locally |
| --- | --- | --- |
| Claude Code | `statusLine` command. `/limitline:install` | The stdin payload, then a snapshot at `~/.cache/limitline/claude.json` for other hosts. Stale after 15 minutes |
| Codex | Built-in `/statusline` items. No external command. `integrations/codex/install.sh` prints the item list and refuses `--write` | Newest `rate_limits` event across `~/.codex/sessions/YYYY/MM/DD/*.jsonl` from the last 8 days, 5h and 7d, each until its reset |
| Cursor | `statusLine` command in `~/.cursor/cli-config.json`. `integrations/cursor/install.sh` prints the snippet. `--write` is opt-in and backs up the file | Model and context from stdin. No local quota file. The plan percent is the shared `cursor+grok` reading below; without one, a labelled token estimate |
| Grok | `[ui.status_line]` command. `integrations/grok/install.sh` prints the snippet and refuses `--write` | Model, context, and cost from stdin. The plan name from `~/.grok/settings_cache.json`, and 7-day tokens and ledger cost summed from `~/.grok/sessions/**/usage.json`. The plan percent is the shared `cursor+grok` reading, live from `~/.grok/logs/unified.jsonl` |
| Antigravity (agy CLI and IDE) | No status-line command in the build that was checked | Live from `agy -p "/usage" --output-format json`, which `limitline refresh` runs (see [Antigravity and the Gemini app](#antigravity-and-the-gemini-app)) |
| Gemini app | None | `not measured (see gemini.google.com/usage)`; no CLI or local file exposes it |

Host snippets:

| Host | File |
| --- | --- |
| tmux | `integrations/tmux/status.conf` |
| starship | `integrations/starship/limitline.toml` |
| bash or zsh | `integrations/prompt/limitline.sh` |
| SwiftBar / xbar | `integrations/swiftbar/limitline.30s.sh` |
| JSON | `limitline --host json` |

With `lines = 2`, line 1 holds the model, context, and Claude windows, and line 2 holds the rest (fleet and machines come first there). Each line is fitted to the terminal width on its own. Claude Code passes the width as `COLUMNS`; when a line is too wide, the lowest-priority segment on that line is dropped first. Widths are counted in display columns, so bars and emoji no longer count as several characters.

Cursor and Grok can also run `limitline` with no arguments so the line is that tool's own stdin (model and context) instead of the multi-tool summary.

## Configuration

`~/.config/limitline/config.toml` is preferred. The older `config` key=value file still works. Environment variables win over either file.

```toml
theme = "minimal"
bar_width = 5
lines = 1
auto_compact = 95
auto_compact_warn = 80
# preset = "minimal"                       # minimal, default, full, pharos
# line1 = ["dir", "git", "model", "ctx"]   # what each line shows, in order
# dir_style = "home"                       # ~/projects/app instead of app
# colors = "off"
```

Hosts, plan prices, and every measuring setting are Pharos's (`~/.pharos/usage.toml`), not limitline's. `limitline config` prints that template and does not write it. The block below is the quiet default. `examples/delight.toml` turns on pace, sparklines, fresh wording, nudges, and vitals.

```toml
# pace = "on"
# spark = "on"
# nudges = "on"
# fresh = "on"
# value = "on"
# vitals = "on"
# alerts = "off"
# quiet = "22-7"
# lines = 5                       # session, what's used, today, older, hosts (needs Pharos for 3-5)
# plan_view = "bar"               # line 2: bar, gauge, dots, trend, cap, none
# plan_numbers = "off"            # "on" adds the percent
# plan_show = "used"              # or "left"
# plan_resets = "near-cap"        # or "always"
# animate = "off"
# fleet = "on"                    # these four show what Pharos measured
# machines = "on"
# grok = "on"
# jobs_detail = "reason"           # or "counts": hide attention reasons
# jobs = "on"
# fleet_ttl = 180
# machines_ttl = 180
# grok_ttl = 180
# jobs_ttl = 180
# cursor_week_tokens = 1000000   # inside Cursor without Pharos (LIMITLINE_TOOL=cursor) only
```

## Pace

Pace compares the percent you have used with the percent of that window that has already elapsed. The 5-hour window is 5 hours ending at `resets_at`. The weekly window is 7 days ending at its `resets_at`. A gap of 8 points or more is `▲ 5h ahead of pace` (painted with the same yellow and red as the meter) or `▼ 7d under pace` (green). The weekly segment also shows the budget that is left, such as `~15%/day left for 4d`, when at least one day remains. `pace = "off"` or `LIMITLINE_PACE=0` removes it. Naming `pace` in `segments` turns it on without the env var.

## Sparklines

With `spark = "on"`, each status line stores the current percent under `~/.cache/limitline/`. The 5-hour file is the same one the burn projection reads. The 5-hour sparkline is the last five samples (`▁` through `█`). The weekly sparkline keeps the last sample of each UTC day for seven days: `7d ▁▃▃▅▅▇▄ 38%`. One sample is not enough to draw, so the first prompt stays unchanged.

## Nudges

`nudges = "on"` adds a short hint. When the Claude 5-hour meter is over 80%, limitline looks at the other local tools and suggests the one with the most room. Each tool counts by its most-used window, because a quiet 5-hour window cannot make up for an exhausted week. The hint is `→ codex 40%` when a tool's tightest window is under 50%, or `→ cursor ok` when nothing measured is roomy and Cursor has no local quota. If a cached worker is under 20% load and is not low on memory, the hint adds that machine: `→ codex 40% · mini idle`. An idle machine is the hint on its own when every measured window is at 50% or more. When context is at the auto-compact warning line, the nudge is `↯ compact soon: /compact`. A cold prompt cache still prints its reason (`cache cold: tools`). If the cache segment is off, the nudge carries that reason instead.

## Fleet

`fleet` is off on the Claude Code line until `segments` names it or `fleet = "on"`. The segment reads one cached line, `⚙ 3 run · 1 ✗`: Pharos's open work from `~/.pharos/summary.json`, today's and the older still-open runs together. Counts are running, needs review (`verify`), and failed; `⚠` is added when a run waits on a plan limit. Pharos decides what each run is and which runs are recent (see its `docs/CONTRACT.md`); limitline reads no run files and scans no processes. Without Pharos there is no fleet segment. `limitline refresh` writes the cache; the status line never waits on it.

## Machines and local models

`machines` is off on the Claude Code line until it is named or `machines = "on"`. The rows come from Pharos (`usage.json` → `hosts`), which probes each host; limitline never runs ssh. `limitline refresh` copies them into `machines.line`. Without Pharos there is no machines segment.

Each row is free memory, then the Ollama model that is loaded: `mini 29% free · qwen3:14b / laptop 62% free`. A host Pharos could not reach is `mini ∅`. `limitline status` adds CPU load and the installed count. If a loaded model leaves under `mem_free_warn` percent of memory free (default 15), the row gains `⚠`. Host nicknames and the ssh targets are Pharos settings (`hosts = [...]` in `~/.pharos/usage.toml`).

## Shared Cursor + Grok plan

Cursor and Grok are one subscription. The xAI plan covers Cursor, Grok, Grok Bot, and Grok Build, and xAI reports one number for it: the percent of this week's included usage.

### Live source: the Grok CLI log

The Grok CLI fetches that number from xAI whenever its interactive `/usage show` command runs, and logs one line to `~/.grok/logs/unified.jsonl` (`LIMITLINE_GROK_LOG`):

```json
{"ts":"2026-11-03T15:30:48.617Z","msg":"billing: fetched credits config","ctx":{"config":{"creditUsagePercent":74.0,"currentPeriod":{"type":"USAGE_PERIOD_TYPE_WEEKLY","end":"2026-11-06T05:22:35.070+00:00"}},"subscriptionTier":"SuperGrok Plus"}}
```

limitline reads the newest such line: `creditUsagePercent` is the percent, `currentPeriod.end` is the reset, `subscriptionTier` is the plan, and `ts` is when it was observed. The log is several megabytes and grows, so it is read backwards from the end in 512 KB chunks; a line that does not parse is skipped and the search goes further back.

Pharos keeps that line fresh (`pharos usage --refresh`). It opens `~/.grok/bin/grok` (`LIMITLINE_GROK_BIN`; `PATH` is not searched) in a pseudo-terminal, from an empty folder in limitline's cache, types `/usage show`, waits for the new log line, and exits. `grok -p "/usage show"` would not work: headless mode sends the text to the model. `/usage show` is a local command, so it uses no model tokens; it calls only xAI's billing API, with the Grok CLI's own login. limitline never reads `~/.grok/auth.json` or any token, and it opens no network connection itself.

limitline itself never starts grok. It reads the log only when it runs inside Grok or Cursor without Pharos (`LIMITLINE_TOOL=grok`); otherwise the reading comes from Pharos.

### Manual override

`limitline set xai-plan` writes a typed number to `~/.cache/limitline/xai-plan.json` (`LIMITLINE_XAI_PLAN`):

```bash
limitline set xai-plan 69 --resets "2026-11-05 09:00" --plan Super
```

`--resets` is local time. Anything in that file is labelled `manual`, whatever its `source` field says, so a typed number never passes for live data. The live reading wins whenever it is at least as new as the manual one. A newer manual value is shown, but with `manual` after the percent, and dimmed on the status line. `set` rewrites the status-line cache at once.

### Display

With a reading, Cursor and Grok are one row everywhere:

- `limitline status`: `cursor+grok 74% · resets Thu 23:22 · SuperGrok Plus · live · grok 7d 1.2M tok`
- host lines: `cursor+grok 74% · Thu 23:22 · grok 7d 1.2M tok`
- the Claude Code line (the `grok` segment): `cursor+grok +74% · Thu 23:22 · grok 7d 1.2M tok`
- a manual value: `cursor+grok 69% · manual · Thu 23:22 · ...`, dimmed

The reset is a local day and time. Grok's 7-day tokens stay as a detail. After 6 hours the reading is stale: it gains its age (`· 9h old`) and the status-line segment is dimmed. After 7 days it is hidden. Once the reset has passed, the percent belongs to an old window, so it is not shown: `cursor+grok reset Thu 23:22, no newer reading`. Nudges use the plan percent and no longer offer `→ cursor ok` for a plan that is nearly used up. History records live readings only.

Without a live or manual reading, Cursor falls back to the token estimate below, and every place that prints it says `estimate`. `grok = "on"` keeps working in both cases.

## Background jobs

Jobs that are not Pharos runs (a mining pass, a backup) are reported to Pharos, which owns them:

```bash
pharos job update mining --done 62 --total 1842 --failed 0 --status running --pid $$ --log ~/logs/mining.log
pharos job update backup --status ok
```

The Claude Code line shows them from Pharos's `summary.json`: `jobs mining 62/1842 ✗3 · backup ok 08:36`, running and dead jobs first, at most three and then `+N`. Pharos decides when a job is `dead` (its pid is gone on its own machine) and keeps finished jobs listed for 12 hours. `limitline status`, `watch`, and the SwiftBar menu add a Jobs block. `limitline job` now only points at `pharos job`.

## Providers

`limitline status` prints the tightest measured window first, then estimates. Claude still comes from the status-line snapshot. Codex comes from the newest session `rate_limits` event across every session file modified in the last 8 days, not only the newest file: `codex exec` runs from scripts leave many short files, and the newest one often has no event. Files are read newest first, the last line that parses in each is used (a half-written or malformed line is skipped, and a `codex` limit wins over another limit id such as `premium`), and the scan stops once a file is older than the best event found. A window is shown while its `resets_at` is ahead; without `resets_at`, while the event is younger than the window. When every window has reset, the row says `no current window (last reading 28h ago)`. Grok has no account window, so its row is never a percent and never sorts as a quota: `grok     SuperGrok Plus · 7d 1.2M tok · $3.00 at API rates · not a quota`. The plan is `settings.subscription_tier_display` inside the JSON-encoded `payload` of `~/.grok/settings_cache.json` (`LIMITLINE_GROK_SETTINGS`); no other field of that file is printed, and `~/.grok/auth.json` is never opened. Tokens are `session.totalTokens` summed over `~/.grok/sessions/**/usage.json` (`LIMITLINE_GROK_DIR`) whose `updatedAt` is in the last 7 days. A file without `updatedAt` or a numeric `totalTokens` is skipped, not dated by its modification time. Grok's own session docs say a session total includes history inherited by resume or fork, so a resumed or forked session can count that history twice. The dollar figure is `costUsdTicks` divided by 10^10 (Grok documents 1 USD = 10^10 ticks). It is what that usage would cost at API rates, not what a SuperGrok plan charges, and it is left out unless every counted file has `costUsdTicks`. It appears in `limitline status` and `watch` only; the status line shows the plan and tokens. A missing settings file or tier skips the plan, and a missing sessions folder skips the tokens. Cursor has no local quota file. When Pharos captured `usage.input_tokens` and `usage.output_tokens` on a cursor run, or a file passed as `LIMITLINE_CURSOR_LOG` has those fields, limitline estimates a weekly percent against `cursor_week_tokens` (default 1,000,000). That number is an estimate, not a quota reading: Cursor does not publish a token budget, and 1,000,000 is only a default you should replace with your own. It is input plus output tokens (cache reads are left out), each `usage` object counted once and added up, from cursor run logs that started or were written in the last 7 days, divided by that budget and capped at 100. It is shown with `~` everywhere (`cursor 7d ~100%`), `limitline status` prints the inputs (`7d ~100% estimate (3.1M of 1.0M tokens)`), the word `estimate` is printed in every host line, and estimated rows are listed after measured ones. A `~100%` means you used more tokens than the budget you set, not that Cursor will stop you. Antigravity and the Gemini app are described in their own section below. A local ledger at `~/.pharos/ledger.jsonl` or `research-spend.jsonl` (or `LIMITLINE_LEDGER`) adds an `api` row such as `spend $0.25` when the file exists. Rows with no window stay at the bottom.

## Antigravity and the Gemini app

Antigravity's buckets (Gemini models, Claude and GPT models, Gemini 4 Argon) come from Pharos, which runs agy's read-only `agy -p "/usage" --output-format json` (no agent turn, no tokens). limitline shows each bucket by name, with the reset when a bucket is low:

```
antigravity gemini-5h 0% · gemini-weekly 0% · 3p-5h 7% · 3p-weekly 5% · argon-weekly 100% resets Thu 21:35
```

The Gemini app's allowance (gemini.google.com) is not shown: no tool can read it.

## Reset moments

`fresh = "on"` replaces `↻1h42m` with `fresh in 1h42m`, and a later reset with `fresh Thu 09:00`. When a 5-hour reading falls from 40% or more to 20% or less, the next line starts with `✨`. That mark is stored next to the reset time and is not shown again for the same window.

## Value meter

`value = "on"` reads a local cost file and prints `≈ $412 of value this week`. The default file is `~/.claude/stats-cache.json`. `LIMITLINE_VALUE_FILE` points somewhere else. A `week_usd` (or `total_cost`) field is used as the number. Token counts are priced with the estimate table below, which is not an invoice. Amounts of $10 or more are rounded to the dollar.

| Family | Input / million | Output / million |
| --- | --- | --- |
| opus | $5 | $25 |
| sonnet | $3 | $15 |
| haiku | $1 | $5 |
| anything else | $3 | $15 |

## Session vitals

`vitals = "on"` replaces the cost segment with one session summary: `session 3m · compact ×2 · +10 -2 · $1.25↑`. Duration and line counts come from the cost object. The compaction count is `context_window.auto_compact_count` or `cost.auto_compactions`. The arrow compares this cost with the previous local sample: `↑` higher, `↓` lower, `·` flat.

## Alerts

`alerts` is `off`, `bell`, or `notify`. `bell` rings the terminal. `notify` asks macOS Notification Center through `osascript`. A crossing of 80% and of 95% on the 5-hour window alerts once for that reset time. Jumping straight past 95% marks 80% as already sent. `quiet = "22-7"` is quiet from 22:00 inclusive until 07:00, including overnight. A quiet hour does not count as the one alert, so it can still fire later in the same window. `LIMITLINE_ALERTS` overrides the file.

## Report

`limitline report` prints usage bars for each tool, the last week of local 5-hour samples by day, the busiest hours, the project folder names that showed up most, and the resets that are still ahead. Names are the last path segment only. A full path is dropped. `limitline report --md` prints the same facts as Markdown.

## History

Usage history is Pharos's. Its 2-minute job writes the weekly report to `~/.pharos/usage-report.json` (the same numbers as `pharos usage --report`), and limitline only shows it:

```
limitline history (weekly peaks from Pharos, since 2026-05-04)

claude       ▄█▆  avg peak 70% · 1 at limit · 1 over 75% · $60/month unused
```

`limitline report --week` (and `--week --md`) prints each plan's peak this week and its weeks at the limit. limitline keeps no plan history of its own. The 5h and 7d sparklines on the Claude Code line use only the status line's own input.

## Watch

`limitline watch` redraws every tool side by side every 5 seconds. In a terminal, below the tools is a list of recent Pharos runs and reported jobs, taken from Pharos's `summary.json`. It is read-only:

| Key | What it does |
| --- | --- |
| `↑` `↓` or `k` `j` | select |
| `l` | open the run's `stdout.log` in the pager (`$PAGER`, else `less -R +G`) |
| `r`, `s`, `p`, `P`, `U` | says to act in Pharos (`pharos resume|stop <id>`, `pharos pause`, or the Console); runs nothing |
| `q` | quit |

limitline never runs `pharos` or signals a process. If stdout is not a terminal, or `LIMITLINE_WATCH_ONCE=1`, it prints one plain frame and exits. `LIMITLINE_WATCH_KEYS="down l q"` replays keys without a terminal, which is how the tests drive it.

## More than one Mac

Pharos measures every Mac it lists (`hosts` in `~/.pharos/usage.toml`) and every plan, so any terminal on a Mac with Pharos sees all of them. limitline has no sync folder of its own; earlier `sync_dir` settings are ignored.

## Background refresh

The status line never runs ssh, a provider, or another tool's CLI. It reads `fleet.line`, `machines.line`, `grok.line`, and `jobs.line` from `~/.cache/limitline/`, and when they are old it starts one `limitline refresh` in the background. That refresh only re-reads Pharos's files (`usage.json`, `summary.json`). Measuring is Pharos's job: its `com.venkat.pharos.usage` launchd agent runs `pharos usage --refresh` every 2 minutes.

On macOS, `limitline install-refresher` installs a launchd agent (`~/Library/LaunchAgents/dev.limitline.refresh.plist`) that runs `limitline refresh` every 60 seconds, so idle terminals stay current. `limitline uninstall-refresher` removes it.

## Fleet and machines from another machine or session

Every Claude Code session on the same Mac shares one cache, so a second session needs nothing extra. Other machines appear because Pharos probes them (`hosts` in `~/.pharos/usage.toml`). A cloud-hosted session cannot reach your Macs or their Pharos files, so it shows only Claude's own line. `limitline doctor` says `session: cloud-hosted` when it detects this.

## Doctor

`limitline doctor` lists the tools on `PATH`, then what it can see of Pharos: whether `summary.json` and `usage.json` exist and how old they are, when the Claude relay last wrote, each cache's age against its TTL, and whether the refresher is installed and loaded. When a segment would be empty, an `empty segments` block says why, such as `fleet: no Pharos summary.json; fleet needs Pharos` or `machines: no hosts in Pharos's usage.json`. With a status payload on stdin it also lists which known fields are present.

## Privacy

limitline reads the status JSON a host already pipes in, an optional local config file, a cache directory it writes itself, Pharos's `usage.json`, `summary.json`, `usage-report.json`, and the tail of today's event file. It writes one file for Pharos, `~/.pharos/inbox/claude.json` (Claude's own reading, only when `~/.pharos` exists). It does not send anything anywhere, opens no network connection, runs no ssh, and starts no other tool's CLI; Pharos does all measuring. It does not read API keys or OAuth tokens. Inside Grok or Cursor without Pharos (`LIMITLINE_TOOL`), it reads that tool's own local files: the plan name and token counters Grok keeps, the `fetched credits config` lines in Grok's log, or Cursor token counts in a log you name. It never opens `~/.grok/auth.json`, cookies, keychains, or credential stores. The report and the Runs list keep repository folder names, not full paths. Debug output stays in the cache file you opted into. Session id display is off unless `LIMITLINE_SESSION=1`.

## Tests

```bash
tests/run.sh
bash tests/layout.sh
```

`tests/layout.sh` holds the 0.15 checks: line 1's order, git ahead/behind against a real repo, `dir`, `project` and the other new segments with and without their fields, per-line layouts, presets, `colors`, the `limitline statusline` picker, and `tests/fixtures/legacy/`, which holds configs rendered by 0.14.0 that must still render byte for byte.

Fixtures cover a full payload, no rate limits, spend only, a near reset, usage over 80%, a context window near auto-compact, a cold prompt cache, a 60-column row, and every theme. The same script covers pace, sparklines, fresh wording, nudges, the value estimate, session vitals, alerts, the report, watch, and a two-machine merge. Fleet, machine, Cursor, Antigravity, Grok, and ledger fixtures are synthetic and use names such as `mini` and `worker-1`. ANSI colour codes are stripped before the comparison. The same fixtures are rendered once with `jq` and once with the python3 fallback. Codex fixtures cover many session files of mixed ages, a newest file with no event, a malformed last line, a second limit id, a 7-day window that outlives its 5-hour one, and events with no reset time. The shared plan has fixtures for a fresh, stale, reset, and week-old reading; jobs have fixtures for merging updates, a dead pid, a reused pid, another machine's pid, the finished-job window, and bad names. History has fixtures for the 10-minute sample gap, 30-day pruning, daily peaks, the weekly table, and jobs per machine, including a dead pid. The interactive watch is driven with replayed keys against a fake `pharos` and a real `sleep` process for job signals, and once in a pseudo-terminal. A warm status line, including a warm fleet, machine, or jobs cache, stays under 50 ms.
