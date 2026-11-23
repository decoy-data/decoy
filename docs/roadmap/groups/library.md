# Local record library

Status: current

Part of the roadmap: [ROADMAP.md](../../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

Rows keep their number from the pre-split track. A row number or section number that is not in a group file is a closed row or old section in the [snapshot](../../archive/2026-11-18-roadmap-before-split.md).

## 1.0

Blocks the 1.0 release.

None. Row 36 moved to 1.1 (owner 2026-11-22).

## Later (1.x)

Additive. Not scheduled until a 1.x release picks it up.

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| 36 | 1.1. L2-cli: scan snapshots on the library (~380 lines; replaces SCAN-MULTI S1d) | CLI | NOT STARTED. Moved from 1.0 (owner 2026-11-22). Plan passed 2026-11-06. L1c and L1d are merged (rows 34 and 35); it now waits only on SCAN-MULTI S1c | same | SCAN-MULTI S1c (L1c and L1d merged) |
| 38 | L3b-cli: sample-run records and scratch lifecycle (~450 lines); three OS lanes | CLI | Plan passed 2026-11-06; the CSV reader, REG-RENUMBER and L1a (engine 0.20.0, which the CLI pins since CLI #164) are in place; waits on the rows in After | same | L1c; SAMPLE |
| 41 | L5a-cli: wire the engine `ProgressSink` into `decoy run` (~380 lines) | CLI | Plan passed 2026-11-06; the CSV reader, REG-RENUMBER and L1a (engine 0.20.0, which the CLI pins since CLI #164) are in place; waits on the rows in After | same | L1c |
| 42 | L5b-cli: job logs (~500 lines); three OS lanes | CLI | Plan passed 2026-11-06; the CSV reader, REG-RENUMBER and L1a (engine 0.20.0, which the CLI pins since CLI #164) are in place; waits on the rows in After | same | L5a, L3a |

### Candidates with no plan yet

Non-breaking ideas, so 1.x by rule. A candidate becomes a row in the table above when a release picks it up.

| Item | Source | Why it does not break |
|---|---|---|
| User-level library store (LIB Q7) | Post-V1 on demand (old list) | New location for the library; the project library is unchanged. |
| 15 Local catalog of scans, runs and evidence | DuckDB opportunities (vault `v2/duckdb/`, platform `plan/v2-duckdb-plans`) | New local store. |

## Maintenance

No user-visible change. Merges at any time and never gates a release.

None.

## Notes carried from the track

LIB plan: `C:docs/plans/2026-11-05-local-record-library.md` on CLI branch `plan/local-record-library`
`6b50e72` (revision 2 records the owner answers). Dennis GO-WITH-FIXES; in a fix round. Four
retention classes under one project root `.decoy/`; `decoy run` writes records by default
(`--no-library` turns it off).

The L4a and L4b command split above is this roadmap's reading of the fix round; the plan's next
revision is the authority.
