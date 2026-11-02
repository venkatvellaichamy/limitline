# Changelog

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
