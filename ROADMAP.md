# Roadmap

limitline stays local: no network calls, no account logins, and every number either read from a file on this machine or labelled as an estimate.

## 0.5 Accuracy + jobs (done)

- Cursor and Grok are one xAI plan. A `cursor+grok` row reads its percent from `~/.cache/limitline/xai-plan.json`, written by `limitline set xai-plan` or a browser helper. It is stale after 6 hours and hidden after 7 days. The Cursor token estimate shows only when there is no cache, and says `estimate`.
- Codex reads the newest `rate_limits` event across every recent session file, so short `codex exec` files no longer hide it. 5h and 7d each last until their own reset.
- A jobs registry for non-Pharos work: `limitline job update <name> --done N --total N --failed N --status running`, `dead` when the pid is gone, and a Jobs row on the status line and in `limitline status`.
- Gemini resets show as a local time, `Fri 09:35`.

## 0.7 Interactive watch (done)

- `limitline watch` is a TUI with keys to stop, resume, or open the logs of Pharos runs (`pharos stop|resume|logs <id>`) and to pause, stop, resume, or read the logs of jobs. Pharos only pauses admissions as a whole (`pharos pause` takes no run id), so that is `P` / `U`.
- The status line itself stays display-only.

## 0.8 History (done)

- A 30-day local history per plan, with sparklines: `limitline history`.
- A weekly report: `limitline report --week [--md]`.
- Per-machine job history from finished and dead jobs.

## Later

- Budgets and forecasts (was 0.6): a per-plan "runs out at" forecast from the burn rate, a configurable budget cap (for example, stop recommending a provider at 75%), `limitline advise` to print which provider and machine to use now, and `limitline status --json` for guard scripts.
- SwiftBar and menu-bar parity for everything above.
- Sync across machines over the existing `sync_dir`.
