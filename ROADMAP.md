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
| **0.11.0** | Live, but quiet | Built on a branch |
| **0.12.0** | Finish the split | Planned |
| **0.13.0** | Display hardening | Planned |
| **0.14.0** | Every surface shows the same thing | Planned |
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

### 0.11.0 — Live, but quiet (branch `feat/live-events`)

- The `▶` turns while jobs run and stands still when nothing runs.
- A new Pharos event (run merged or failed, a plan crossing 75/90/100%, a host offline) shows dimmed for 30 seconds.
- A plan number that just moved is bold for 20 seconds.
- The `left` line shows the age of Pharos's reading when it is over 5 minutes old.
- `animate = "off"` keeps the information and drops the motion.

### 0.12.0 — Finish the split

Remove what still measures or decides, after Pharos has an equivalent. Each item is either moved to Pharos or deleted; nothing is removed before Pharos covers it.

**The two modes, exactly.** Today, with Pharos present, the Claude row still comes from the status line input (`lib/fivelines.py` `claude_cells`), and limitline copies that reading into `~/.pharos/inbox/claude.json` (`bin/limitline`, "Relay them, as-is, to Pharos"). Both change:

- With Pharos, the Claude row comes from `usage.json` like every other plan.
- limitline stops writing to `~/.pharos/inbox`. Claude Code gives its limits only to the status line command, so Pharos captures them itself: **depends on Pharos** providing a `pharos statusline` command that saves Claude's reading and then hands the same input to limitline to draw. `pharos install` sets the status line to it.
- Without Pharos, nothing changes: the Claude row comes from the status line input.
- Tests cover both modes, and the switch between them when Pharos is installed or removed.

- Providers (`providers/claude`, `codex`, `cursor`, `grok`, `spend`, `xai-plan`): keep only what the stand-alone "the tool I run in" mode needs.
- Background refresher and its schedule: Pharos owns refresh.
- History and the weekly report: Pharos stores history; limitline draws it.
- Nudges and the value meter: advice comes from Pharos.
- Sync between machines (`sync_dir`): Pharos owns it.
- Machine probes and the jobs registry: read from Pharos.
- `watch` actions (stop, verify, retry): call Pharos commands instead of acting on runs directly.
- Drop config keys that no longer do anything, with a one-line notice when an old key is found.

### 0.13.0 — Display hardening

Prove the display stays honest when Pharos's files are bad. Synthetic files and a disposable cache only.

| Case | Expected display |
|---|---|
| Pharos files missing | Says Pharos is not running; Claude's own line still works |
| Old reading | Shows the age; never shows an old percent as current |
| Reset time already passed | Says the window reset and there is no newer reading |
| Partial or invalid JSON | Shows `—` for that field; never crashes, never guesses |
| Unknown fields or a newer format | Ignores unknown fields; says when the format is too new |
| Clock skew | No negative ages, no future readings shown as fresh |
| Narrow terminal | Drops the lowest-priority segment first, as documented |
| Slow disk | Render stays under 50 ms |

### 0.14.0 — Every surface shows the same thing

- `status`, `watch`, the menu bar and the status line read one shared view, so they never disagree.
- Menu bar parity for every segment.

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

| Name | What it does | Target |
|---|---|---|
| `/limits` | Show what is left on every plan, with source, age and reset, as Pharos measured it | 0.14.0 |

The `/ramp` skill applies caps, so it moved to Pharos.
