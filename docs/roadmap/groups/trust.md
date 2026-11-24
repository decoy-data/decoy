# Quality and evidence

Status: current

Part of the roadmap: [ROADMAP.md](../../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

Rows keep their number from the pre-split track. A row number or section number that is not in a group file is a closed row or old section in the [snapshot](../../archive/2026-11-18-roadmap-before-split.md).

## 1.0

Blocks the 1.0 release.

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| POSTMASK-FAIL-CLOSED | G8: the post-mask leak check fails closed (owner 2026-11-24). In `E:verification/postmask/residual_pii.py:240-274`, `_source_identity` returns None on any exception, so a failed identity comparison gives no signal. Fix: report an explicit comparison-failed error finding, and add a test that forces the comparison to raise. The finding came from the F34 FRAME (row 67, closed); see [row-detail.md](../row-detail.md), F34 | engine | NOT STARTED. Verified on engine main 2026-11-24 | none | none |

## Later (1.x)

Additive. Not scheduled until a 1.x release picks it up.

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| 68 | F36: cross-column invariants (finish), entry slices, slice 4 registry | engine | plan rev 8 GO | `E:plan/f36-cross-column-invariants` `9ed7b47f` | F06 (merged) |
| 69 | F35: quality contracts, E1a onward (registry) | engine | plan rev 4 GO | `P:plan/f35-quality-contracts` `7a3471af` | registry order |
| 70 | F32 remainder: engine E1b to E3, CLI C0, C1, C1b | engine, CLI | plan Codex r5 GO, Dennis r4 GO-WITH-FIXES | `P:plan/f32-support-bundles` `39c2772c` | F32 E1 (row 15) |
| 72 | F33 CLI verifier and engine signature envelope | engine, CLI | PARTLY MERGED. E1a and E1b MERGED: the signed-evidence verifier moves into the engine (in engine 0.28.0). Plan rev 9 (V1 scope E1a, E1b, C1a, C1b; owner 2026-11-11). Left: C1a, C1b and the release slice that re-pins the certified stack | `P:plan/f33-v1-scope` `bba8b625`; engine PR #335 (OPEN) | plan review |
| ANON | 1.x (1.9). Formal anonymity, the built part of X-12 and F37: generalization hierarchies (ANON.1, engine draft #672), k-anonymity, l-diversity and t-closeness metrics (ANON.2, #673), model descriptors (ANON.3, #687), least-loss lattice search (ANON.4, #689), MDAV microaggregation (ANON.5, #690), the `risk-utility-report/v1` report (ANON.6, #694). Library only. Was V2-3.1 to 3.5. Detail in [releases-1x.md](../releases-1x.md) | engine, CLI | IN REVIEW, held until after 1.0. One stack in that order; no plan GO recorded. ANON.6 lands dark without its freeze edits; the release that ships ANON.9 freezes `risk-utility-report/v1` and captures its compat corpus (owner 2026-11-22). Left: plan review, EXPERIMENTAL-TIER marking, layer-contract conflicts (2, from ANON.3); not built: ANON.7 config (V2-3.1b), ANON.8 planner wiring (V2-3.3 slice 2), ANON.9 evidence and CLI (V2-3.5 slice 2) | `E:feat/v2-3.1-generalization-hierarchies` to `E:feat/v2-3.5-risk-utility-report` | F35 (row 69) |
| 78 | F10: lock envelope (`lock/v1` with `key_version`), synthetic probe, CLI environment report, fleet comparison | engine, CLI | PARTLY MERGED. Plan `E:plan/f10-lock-envelope` (revision 3). 78-E1 MERGED (engine #618, `1b721aa41`, 2026-11-17): the `lock/v1` runtime lock envelope with `key_version`. 78-E2 MERGED (engine #633, `a50dc56ce`, 2026-11-17): the synthetic probe and an optional `probe` field in `lock/v1`. Left: the engine release and CLI repin, then 78-C1 (CLI environment report and fleet comparison) | `E:plan/f10-lock-envelope` | Phase 1 rows |

### Candidates with no plan yet

Non-breaking ideas, so 1.x by rule. A candidate becomes a row in the table above when a release picks it up.

| Item | Source | Why it does not break |
|---|---|---|
| F12 customer regression suites | Council features | New command and artifact. |
| F37 post-mask privacy risk | Council features | New report under a new tag; k-anonymity and QI in `decoy scan` stay as they are. Built in part: row ANON. |
| F39 OpenLineage export | Council features | New export. |
| X-12 Formal anonymity enforcement | Expansion candidates X-01 to X-25 | New opt-in gate. Built in part: row ANON. |
| 8 Source-versus-output compare and leak check | DuckDB opportunities (vault `v2/duckdb/`, platform `plan/v2-duckdb-plans`) | New command or report. |
| 20 Support bundle as Parquet | DuckDB opportunities (vault `v2/duckdb/`, platform `plan/v2-duckdb-plans`) | New format. Stays 1.x only while the old bundle format stays readable and the default. |

## Maintenance

No user-visible change. Merges at any time and never gates a release.

None.
