# limitline usage render audit, 2026-11-05 (0.16.0-beta.2)

Scope: where each status-line number comes from when Pharos is the reader, how old data is drawn, and which paths can still put limitline's own readers or caches in front of Pharos data. This is a report only. The fixes from this run are listed in CHANGELOG 0.16.0-beta.2.

How Pharos mode is chosen (`lib/reader.py:is_pharos`):
- `reader = "pharos"` always selects it.
- `reader = "limitline"` never does.
- `reader = "auto"` (the default) selects it while `usage.json` exists and its mtime is within `reader_freshness` (900 s).

The bash status line works this out once per render as `PHAROS_READER`.

Staleness settings (new in this run, `lib/pharos_view.py`):
- `usage_stale_after` (900 s): usage.json older than this means the Pharos service is not refreshing it. The used line says `Pharos usage unavailable · 60m old` and every plan shows `?`. Ages under 2 hours are in minutes, then hours (`2h old`).
- `plan_stale_after` (3600 s): one plan whose `observed_at` is older than this, or that has `stale: true`, shows `? · 94m old`. usage.json's `generated_at` stands in only when the plan has no `observed_at` key; an `observed_at` that is not a positive epoch number shows `?`.
- A window whose `resets_at` has passed counts as 0% with no reset time.

## Segments

| Segment | Number in Pharos mode comes from | Old data is drawn as | Can limitline's own data shadow Pharos? |
|---|---|---|---|
| **5h** (line 1) | Claude Code's status-line input (`rate_limits.five_hour`). Pharos is not involved. | The input is always current. | No. This is Claude Code's own number. |
| **7d** (line 1) | The status-line input. When the input has no 7d, the last snapshot in `~/.cache/limitline/claude.json`. | A cached value shows `· 12m ago`. A cached value whose reset has passed shows `7d reset Fri 08:40 · no newer reading`. | Yes, by design: the snapshot is limitline's own cache. It is Claude Code's own reading, which Pharos receives through the inbox relay, so this is not a Pharos shadow. |
| **claude** (five-line used line) | The status-line input, else `claude.json` while fresh (15 min). `pharos_view.plan_rows` prefers the status line's snapshot over Pharos's claude plan when the snapshot is newer. | Older than 15 min: `7d — 2h ago`. | Yes, intentionally (newer wins). |
| **codex** (line 1) | `pharos_view.py --codex-fields` reads usage.json's codex plan and runs on every render, in any mode, whenever the codex segment is on. | `codex ? · 94m old` when usage.json, the plan's `stale`, or the plan's age says it is old (new). Reset passed: `5h 0%`. | **Partly.** `$TMPDIR/limitline-codex-<uid>.cache` holds the parsed fields for 30 s, and now carries `codex_age` too. A render inside that 30 s can show the previous reading. The cache is bypassed when `LIMITLINE_PHAROS_USAGE` is set, which is why the tests never see it. |
| **codex** (five-line) | The same fields, passed as `LL_CODEX*`. `codex_cells` reads usage.json's codex plan directly and uses those fields only when there is no codex plan. | `◎ codex ? · 30m old` (new). | Only through the line-1 fields when usage.json has no codex plan (the `LL_CODEX_CACHE` fallback). |
| **grok / cursor+grok** (line 1) | `PHAROS_READER=1`: `reader.display_fields()` reads usage.json directly on every render. Otherwise: `grok.line`, rewritten by `refresh`. In Pharos mode `refresh` builds it from `plan_rows`. | `cursor+grok ? · 9h old`, dimmed, with no percent (new; previously the old percent was dimmed). | **Partly.** With `reader = "auto"` and usage.json past `reader_freshness`, `grok.line` comes from `cli.load_all()`. While usage.json exists, that is still Pharos rows, now marked stale. Only when usage.json is **missing** does it run limitline's own providers. |
| **cursor+grok** (five-line) | usage.json `xai-plan` plan. When there is none, `grok.line`, aged by usage.json's `generated_at` rather than the file's mtime (5bce916). | `? · Xm old`. | Only through `grok.line` when Pharos has no xai-plan plan. |
| **antigravity** (five-line only) | usage.json `antigravity` plan. There is no line-1 segment. | `✦ agy ? · 1d old` (new). Reset-passed buckets read 0%. | No. |
| **spend** (line 1) | The status-line input (`rate_limits.spend_limit`). Pharos's `spend`/`api` rows appear only in `limitline status`. | The input is always current. | No. |
| **jobs / fleet** | `~/.pharos/summary.json`. `jobs.line` and `fleet.line` are rebuilt by `refresh` and, in Pharos mode, read directly by `reader.display_fields()`. | Outside Pharos mode, a line older than `jobs_ttl`/`fleet_ttl` (file mtime) is hidden and a refresh starts. | No other source exists; `limitline job` moved to Pharos. |
| **machines / hosts** | usage.json `hosts`. `machines.json`/`machines.line` are rebuilt by `refresh` with `observed_at` = `generated_at`. | Five-line: `hosts — 1h ago`. Line 1, outside Pharos mode: hidden after `machines_ttl` by mtime. | No. |

## Left for a later run

### P0
- None known. Tonight's bug was a 94-minute-old Codex reading drawn as current. It is now drawn as unknown on line 1 and in the five-line view, by its own age, even when Pharos does not mark it stale.

### P1
- **Auto mode silently drops to limitline's readers when usage.json is missing.** With `reader = "auto"`:
  - `is_pharos()` turns false.
  - `refresh` then runs `cli.load_all()` → `run_provider` for every own provider.
  - Line 1 shows no Pharos note, because `--codex-fields` writes `Pharos usage unavailable` only when `is_pharos()` is true.

  The five-line used line does say `Pharos usage unavailable` (the Pharos home exists). Suggested fix: in auto mode, treat an existing `~/.pharos` home as Pharos mode, or add a `pharos_note` to line 1 whenever the home exists. Either one changes `test_detection`, so it needs a decision.
- **`reader_freshness` uses usage.json's mtime, while the stale settings use `generated_at`.** A `touch` or copy can disagree with the content. Pick one clock; `generated_at` is the honest one.
- **The 1 h `plan_stale_after` default is a trade-off.** Codex writes a reading only when it is used, so an idle but correct reading turns into `?` after an hour. Once Pharos 0c9c ships live Codex readings with its own `stale` flag, consider trusting Pharos's flag and raising the default.

### P2
- The 30 s codex cache in `$TMPDIR` can lag usage.json by up to 30 s, and older 6-field cache rows are read without `codex_age`. That is harmless and self-healing in 30 s. Drop the cache in Pharos mode: usage.json is a single small read.
- Line 1 outside Pharos mode hides `fleet`/`machines`/`jobs`/`grok` lines by **file mtime** (`fresh_line`), not by Pharos's reading time. In Pharos mode they are read directly, so this affects only the limitline fallback.
- `fivelines.STALE_S` (15 min) still decides whether the Claude snapshot is fresh and whether a job summary or event is today's. Those are not Pharos plan ages, but they are a third hard-coded age.
- `tests/run.sh` prints `env: pharos_usage: No such file or directory` near line 544, because a shell function is called through `env`. This predates this run. The check still passes, but that grok case gets no usage.json.
- `tests/layout.sh` and `python3 -m pytest` could not be run in this run's sandbox. pytest is not installed for the Homebrew Python, and layout.sh needed approval. Run them on the next pass.
