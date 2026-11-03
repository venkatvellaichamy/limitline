# Changelog

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
