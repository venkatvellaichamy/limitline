# Roadmap

## What limitline is

limitline is a **display**. It shows, in the terminal, what Pharos has measured: what is left on each plan, today's and older jobs, and the hosts. It does not measure, fetch, schedule, cap or decide anything.

It runs in one of two modes:

| Mode | Where every number comes from |
|---|---|
| **With Pharos** (`~/.pharos/usage.json` exists) | Pharos only, including the Claude row. limitline reads Pharos's files and writes nothing into `~/.pharos`. |
| **Without Pharos** | Only the tool it runs in. In Claude Code, the Claude 5h and 7d numbers come from the status line input. Other plans, jobs and hosts are not shown. |

| limitline (display) | Pharos (manages) |
|---|---|
| Draws the Claude Code status line, `status`, `watch` and the menu bar | Measures every plan and host, writes `~/.pharos/usage.json` and `summary.json` |
| Reads Pharos's files, or the status line input when Pharos is absent | Captures Claude Code's own limits, fetches vendor usage (agy, Grok, Codex, Cursor), probes hosts over ssh |
| Labels missing or old data as such, never guesses | Caps, the 75% → 80% → full ramp, forecasts, routing advice, admission |
| | History, reports, alerts, sync between machines, the Console |

If a feature measures, stores, or decides, it belongs in Pharos.

## How versions work

- Every piece of planned work has a **target version**. If plans change, the work moves to another version; the table below is updated in the same PR.
- **Minor (0.x.0):** features or behaviour. **Patch (0.x.y):** bug fixes only.
- Each release bumps `bin/limitline`, `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` together, adds a CHANGELOG entry, and is tagged `vX.Y.Z` on the merge commit. Nothing on `main` stays untagged.
- Shipped or retired numbers are never reused. 0.6.0 is retired.
- Every change goes through a PR. All model work goes through Pharos.

## Versions

| Version | Theme | Status |
|---|---|---|
| 0.1.0 – 0.9.0 | Status line, themes, fleet, watch, history, live Cursor+Grok | Shipped |
| **0.10.0** | Display only: the five-line view, Pharos as the source | Merged, **needs tag** |
| **0.11.0** | Live, but quiet | Merged (PR #11), **needs tag** |
| **0.12.0** | Finish the split | Merged (PR #13), **needs tag** |
| **0.13.0** | Plan views (used or left), CI, releases, channels, update | Released |
| **0.13.1** | Refill time on every window, behind `plan_resets = "always"` | This PR |
| **0.14.0** | Display hardening | This PR (version bump; release after merge) |
| **0.15.0** | Every surface shows the same thing | Planned |
| **0.16.0** | A settings menu, and an icon on every line | Planned |
| **1.0.0** | Stable display of a versioned Pharos contract | Planned |

### Shipped

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

### 0.10.0 — Display only (merged, needs tag)

Already on `main` (PRs #9 and #10) but still labelled 0.9.0. Release it as-is.

- Five-line status line: session, `left` per plan, `today` and `older` jobs, `hosts`.
- Plans, hosts and job counts come from Pharos (`usage.json`, `summary.json`).
- agy `/usage`, the Grok plan fetch, the hosts ssh probe and the cross-tool readers moved to `pharos usage`.
- Review fixes F1–F5 and the owner items O1–O3 from the 2026-11-03 whole-repo review.

### 0.11.0 — Live, but quiet (merged, PR #11, needs tag)

- The `▶` turns while jobs run and stands still when nothing runs.
- A new Pharos event (run merged or failed, a plan crossing 75/90/100%, a host offline) shows dimmed for 30 seconds.
- A plan number that just moved is bold for 20 seconds.
- The `left` line shows the age of Pharos's reading when it is over 5 minutes old.
- `animate = "off"` keeps the information and drops the motion.

### 0.13.0 — Plan views, releases, and channels (this PR)

- Line 2 reads `used` (or `left` with `plan_show`), in one of six views: `bar`, `gauge`, `dots`, `trend` (7 days, from Pharos 0.7.1 `daily`), `cap` (Pharos's `cap_pct` marked, pace `▲`), or `none`; `plan_numbers` adds the percent.
- CI on every pull request; tagged releases with a GitHub release, moving `stable` and `beta` branches; `limitline version`, `update`, and `channel`. See RELEASING.md.
- The first release cut this way should be `v0.13.0`. Earlier versions 0.10.0 to 0.12.0 were merged without tags; they can be tagged on their merge commits for history, with no release.

### 0.12.0 — Finish the split

Done here, each with Pharos covering it first (Pharos 0.7.0):

- Fleet, Runs, jobs, `watch`, and the job lines read Pharos's `summary.json` (v1, with `recent` and `jobs`). No run-file parsing, process scan, or fleet window.
- The jobs registry moved to Pharos: `pharos job update|list|rm`. `limitline job` only points there.
- History and the weekly report: Pharos stores them (`usage-report.json`); `limitline history` and `report --week` draw them. limitline keeps no plan or job history.
- Nudges read the other tools' numbers from `usage.json`; without Pharos there is no tool nudge.
- Sync between machines (`sync_dir`) is removed; other Macs come through Pharos.
- Machine probes are gone from limitline; hosts come from `usage.json`.
- `watch` is read-only: it lists runs and jobs and opens a log. Acting on runs is Pharos's (its CLI or Console); the keys say so and run nothing. (The owner chose read-only over "call Pharos commands".)
- The Cursor reader no longer reads Pharos's run logs. Pharos makes that estimate.
- Old config keys (`hosts`, `sync_dir`, `fleet_window`, `ssh_timeout`, `xai_ttl`, `agy_ttl`, `pharos`, ...) get a one-line notice in `limitline doctor`.
- The background refresher stays, but only re-reads Pharos's files into the status line's small caches; Pharos's own launchd job does all measuring. The value meter stays: it reads Claude Code's own `~/.claude/stats-cache.json`, the tool limitline runs in.

Still open, because it depends on Pharos 0.8.0 (`pharos statusline`):

- With Pharos, the Claude row should come from `usage.json`, and limitline should stop writing `~/.pharos/inbox/claude.json`. Claude Code gives its limits only to the status-line command, so this needs Pharos to own that slot and pass the same input to limitline to draw. Until then the relay stays, and it is the one file limitline writes.

### 0.14.0 — Display hardening

- [x] **Linux becomes a required CI check.** The first CI run (2026-11-04) passed 215 of 226 checks on Ubuntu; the 11 failures are the Grok/plan segment, the hot fleet and machines segment, jobs on line 1 and 2, and the two-line fit, all of which drop their segment on Linux. Fixed (GNU `stat -f` read a cache's mtime as text; see CHANGELOG), `gnu-*` checks in `tests/run.sh`, and the Linux job is required.

Prove the display stays honest when Pharos's files are bad. Synthetic files and a disposable cache only. Tests: `tests/test_hardening.py` (`hardening-unit` in `tests/run.sh`), plus `five-pharos-not-running` and `five-codex-reset-passed` end to end.

| Case | Expected display | Done |
|---|---|---|
| Pharos files missing | Says Pharos is not running; Claude's own line still works | ✓ `· pharos not running` |
| Old reading | Shows the age; never shows an old percent as current | ✓ `— 1h ago`, `· 1h old` (Pharos's age and `stale` decide) |
| Reset time already passed | Says the window reset and there is no newer reading | ✓ `5h reset, no newer reading` |
| Partial or invalid JSON | Shows `—` for that field; never crashes, never guesses | ✓ per field and per line |
| Unknown fields or a newer format | Ignores unknown fields; says when the format is too new | ✓ `pharos format v2 is newer than this limitline` |
| Clock skew | No negative ages, no future readings shown as fresh | ✓ `· pharos clock ahead` (over 2 minutes ahead) |
| Narrow terminal | Drops the lowest-priority segment first, as documented | ✓ whole plans, job counts, hosts from the right |
| Slow disk | Render stays under 50 ms | ✓ each file read once, non-blocking, regular files only |

### 0.15.0 — Every surface shows the same thing

- `status`, `watch`, the menu bar and the status line read one shared view, so they never disagree.
- Menu bar parity for every segment.

### 0.16.0 — A settings menu, and an icon on every line

- **An icon on every line**, like line 1's 🧠 and 🪟: for example `◔` before `used`, `▶` before `today`, `⏳` before `older`, `🖥` before `hosts`, with a `marks = "none"` and ascii fallback and the same width rules.
- **`limitline settings`**: a full-screen menu for every setting (lines, theme, marks, plan view, numbers, used or left, animate, segments, widths), each shown as a live example drawn from your own numbers before you pick it. Saving writes `~/.config/limitline/config.toml` with a backup and shows the diff. It replaces hand-editing for most people, and `limitline config` stays as the template.

### 1.0.0 — Stable

- Pharos's files carry a schema version; limitline states which versions it reads.
- The 0.13.0 checks pass on every release.
- Install and upgrade through the plugin with no manual steps.

## Moved to Pharos

These were on the limitline roadmap before the split. They are tracked in the Pharos roadmap now.

- Per-plan caps and the 75% → 80% → full ramp.
- "Runs out at" forecasts from the burn rate.
- `advise`: which provider and machine to use now.
- `status --json` for admission (Pharos measures directly).
- The feed for the Pharos Console.
- More live usage sources.
- Self-hosted ntfy and public endpoints (both need a VPS).
- API model providers (parked).

## Skills

Built when token budget allows; each lives at `skills/<name>/SKILL.md`.

limitline ships only status-line commands (`/limitline:install`, `theme`, `doctor`, `config`, `preview`, `uninstall`). Skills that help an agent choose a tool belong to Pharos, which owns the numbers and the caps: `/limits` and `/ramp` are planned in Pharos 0.10.0 (decided 2026-11-04). Without Pharos, `limitline status` already shows the tool's own usage.

- [x] Pharos 0.8 attention: working/blocked counts, owner-based need you, and the first recent attention reason; `jobs_detail` selects reason or counts. Legacy summary v1 output is preserved.
