# Roadmap

limitline makes no network calls of its own and never reads tokens or auth files. Every number comes from a file on this machine, or from the vendor's own CLI asked to refresh its usage (for example Grok's `/usage show`). A number that isn't live is labelled `estimate` or `manual`.

## How versions work

- **The version number is set when a release ships, never earlier.** Planned work below has no version until it ships.
- **Minor version (0.x.0):** new features or behaviour. **Patch version (0.x.y):** bug fixes only.
- **One merge to `main` is one release:** bump `bin/limitline`, `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` together, add a CHANGELOG entry, and tag `vX.Y.Z` on the merge commit.
- Planned work and branches do not reserve version numbers. Retired numbers stay retired, including 0.6.0 and the unmerged 0.8.2/0.8.3 labels.
- Every repository change goes through a PR. All model work goes through Pharos.
- **No 0.6.0:** releases went 0.5.0 → 0.7.0 because the planned "0.6" was deferred. The number is retired so the sequence stays monotonic.

## Shipped

| Version | Date | What |
|---|---|---|
| 0.1.0 | 2026-11-02 | Claude Code status line, marketplace, install, uninstall, preview |
| 0.2.0 | 2026-11-02 | Themes, hosts, the provider matrix |
| 0.3.0 | 2026-11-02 | Pace, sparklines, nudges, local report |
| 0.4.0 | 2026-11-02 | Fleet cockpit: Pharos runs, machines, provider caches |
| 0.4.1 | 2026-11-02 | Two-line fit, machine memory labels, background refresher |
| 0.4.2 | 2026-11-03 | Grok plan and 7-day session tokens |
| 0.5.0 | 2026-11-03 | Codex across all sessions, one Cursor+Grok plan row, Gemini reset dates, jobs registry |
| 0.7.0 | 2026-11-03 | Interactive `limitline watch` for Pharos runs and jobs |
| 0.8.0 | 2026-11-03 | 30-day history, weekly report, per-machine job history |
| 0.8.1 | 2026-11-03 | Fix: Codex windows hidden by empty "premium" events |
| 0.9.0 | 2026-11-03 | Live Cursor+Grok plan, scheduled refresh, safer job process checks |

Each version has a `vX.Y.Z` git tag. Dates follow the tagged commits; release details come from CHANGELOG.md and git history, including merged PRs #1–4 and #7. The GitHub merged-PR query could not be completed during this update because the API was unreachable.

## Now

1. **Break limitline, then fix what breaks.** Run the test plan below, record failures, and fix and retest them before adding providers.
2. **Pharos admission:** add `limitline status --json` with stable fields for plan usage, source, freshness, reset time, and unavailable readings. Pharos 0.5.4 reads provider scripts directly today; test the JSON contract before switching admission to it.
3. **Keep operations local:** use only the MacBook, Mac mini, and silver-line. No VPS for now. Stability comes before more sources or features.

### Break limitline test plan

Use synthetic logs, a disposable cache, and fake CLIs on the existing machines. Do not read credentials or private data. Record the command, expected result, actual result, and regression check for each failure. This is planned work, not a claim that these checks have passed.

| Case | Check |
|---|---|
| Stale logs | Age readings past freshness, reset, and expiry boundaries. Label stale data, drop expired percentages, and keep stale data out of history and admission decisions. |
| Missing CLI | Remove the vendor CLI from the test PATH. Refresh finishes with a clear reason and preserves the last reading with its actual age. |
| Clock skew | Put observations and resets ahead of and behind the local clock. Flag suspect timestamps; never turn future data into fresh headroom or a negative age. |
| Vendor log format changes | Rename fields, change types, and add malformed lines. Skip bad records without crashing or inventing a percentage; report unavailable data if none remain valid. |
| Two machines | Refresh on the MacBook and Mac mini with overlapping and delayed snapshots. Avoid double-counting shared plans, retain source and age, and never signal another machine's PID. |
| Pty fetch timeout | Make a fake CLI hang during the fetch. Enforce the timeout, stop the child process group, release the lock, preserve the last reading, and let the next refresh run. |
| Full cache directory | Simulate no space and failed writes in a disposable cache. Report the write failure, preserve valid files, and recover after space returns. |
| Partial JSON file | Interrupt a cache write and supply truncated JSON. Readers do not crash or accept partial values; a later valid refresh recovers. |

For every case, check status rendering and the planned JSON output. Unknown, stale, or invalid data must remain distinguishable from measured headroom for Pharos admission. Hardening is done when failures have fixes and repeatable regression checks, fetches leave no child processes or stuck locks, and valid cache data survives failed writes.

## Next

- Per-plan caps following the owner's ramp: 75% → 80% → full.
- A per-plan “runs out at” forecast from the burn rate.
- `limitline advise`: suggest the provider and machine to use now.
- Console feed: publish the status snapshot through `sync_dir` for the Pharos Console on the Mac mini.

## Later

- More live sources, after hardening; label estimates clearly.
- Menu bar parity for every segment.
- Sync across machines through the existing `sync_dir`.
- Self-hosted ntfy server — **needs VPS**.
- Public endpoints — **needs VPS**. Revisit only if the owner changes the no-VPS decision.

## Parked

- **0.8 API-provider work: parked.** API model providers are deferred until Pharos and limitline are stable and robust. The old planning label does not reserve a release number or change the shipped 0.8.0 history release.

## Open questions for the owner

- What evidence should allow the cap to move from 75% to 80%, then full?
- When admission data is unavailable or stale, should Pharos wait or choose another measured plan?

## Skills

Build these only when token budget allows. Once built, each lives at `skills/<name>/SKILL.md` in this repository.

| Name | What it does | When an agent should use it | Status |
|---|---|---|---|
| `/limits` | Show a live table of every plan, including source, freshness, usage, and reset. | Before admitting or routing work, or when the owner asks about remaining limits. | planned — to be built when token budget allows |
| `/ramp` | Show and apply the owner's per-plan cap ramp: 75% → 80% → full. | When checking a cap or applying an owner-approved ramp change. | planned — to be built when token budget allows |
