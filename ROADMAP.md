# Roadmap

limitline makes no network calls of its own and never reads tokens or auth files. Every number comes from a file on this machine, or from the vendor's own CLI asked to refresh its usage (for example Grok's `/usage show`). A number that isn't live is labelled `estimate` or `manual`.

## How versions work

- **The version number is set when a release ships, never earlier.** Planned work below has no version until it ships.
- **Minor version (0.x.0):** new features or behaviour. **Patch version (0.x.y):** bug fixes only.
- **One merge to `main` is one release:** bump `bin/limitline`, `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` together, add a CHANGELOG entry, and tag `vX.Y.Z` on the merge commit.
- **Version branches:** a PR may not use a version that another open PR already claims. If two PRs are open at once, they ship together in one release.
- **No 0.6.0:** releases went 0.5.0 → 0.7.0 because the planned "0.6" was deferred. The number is retired so the sequence stays monotonic.

## Shipped

| Version | Date | What |
|---|---|---|
| 0.1.0 | 2026-11-02 | Plugin scaffold, context/cost status line, fixture tests |
| 0.2.0 | 2026-11-02 | Themes, hosts, the provider matrix |
| 0.3.0 | 2026-11-02 | Pace, sparklines, nudges, local report |
| 0.4.0 | 2026-11-02 | Fleet cockpit: Pharos runs, machines, provider caches |
| 0.4.1 | 2026-11-02 | Two-line fit, machine memory labels, background refresher |
| 0.4.2 | 2026-11-03 | Grok plan and 7-day session tokens |
| 0.5.0 | 2026-11-03 | Codex across all sessions, one Cursor+Grok plan row, Gemini reset dates, jobs registry |
| 0.7.0 | 2026-11-03 | Interactive `limitline watch` for Pharos runs and jobs |
| 0.8.0 | 2026-11-03 | 30-day history, weekly report, per-machine job history |
| 0.8.1 | 2026-11-03 | Fix: Codex windows hidden by empty "premium" events |

Each version has a `vX.Y.Z` git tag.

## Next release: 0.9.0 (in review)

- **Live Cursor+Grok plan:** read from the Grok CLI's own billing fetch (`/usage show` in a pseudo-terminal), at most every 30 minutes, without reading tokens. A typed-in `set xai-plan` value is labelled `manual`.
- **Scheduled refresh:** `limitline schedule install` runs `limitline refresh` every 15 minutes through launchd, so readings stay fresh when no CLI is open.
- **Safer jobs:** a reused pid is never taken for a job, and `watch` never signals a process it can't prove is the job.

## Planned (no version numbers yet)

- **Budgets and forecasts:**
  - a per-plan "runs out at" forecast from the burn rate;
  - configurable caps that follow the owner's ramp (75% → 80% → full);
  - `limitline advise`, which prints the provider and machine to use now;
  - `limitline status --json` for the Pharos router and guard scripts.
- **Console feed:** publish the status snapshot through `sync_dir`, so the Pharos Console on the Mac mini can show budgets.
- **More live sources:** wherever a vendor exposes its own usage, read it the same way, and label everything else as an estimate.
- **Menu bar:** SwiftBar/menu-bar parity for every segment.
- **Sync across machines:** over the existing `sync_dir`.
