# Quality and evidence

Status: current

Part of the roadmap: [ROADMAP.md](../../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

Rows keep their number from the pre-split track. A row number or section number that is not in a group file is a closed row or old section in the [snapshot](../../archive/2026-11-18-roadmap-before-split.md).

## 1.0

Blocks the 1.0 release.

None.

## Later (1.x)

Additive. Not scheduled until a 1.x release picks it up.

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| 68 | F36: cross-column invariants (finish), entry slices, slice 4 registry | engine | plan rev 8 GO | `E:plan/f36-cross-column-invariants` `9ed7b47f` | F06 (merged) |
| 69 | F35: quality contracts, E1a onward (registry) | engine | plan rev 4 GO | `P:plan/f35-quality-contracts` `7a3471af` | registry order |
| 70 | F32 remainder: engine E1b to E3, CLI C0, C1, C1b | engine, CLI | plan Codex r5 GO, Dennis r4 GO-WITH-FIXES | `P:plan/f32-support-bundles` `39c2772c` | F32 E1 (row 15) |
| 72 | F33 CLI verifier and engine signature envelope | engine, CLI | plan in review: rev 9 (V1 scope E1a, E1b, C1a, C1b; owner 2026-11-11) | `P:plan/f33-v1-scope` `bba8b625`; engine PR #335 (OPEN) | plan review |
| 78 | F10: lock envelope (`lock/v1` with `key_version`), synthetic probe, CLI environment report, fleet comparison | engine, CLI | PARTLY MERGED. Plan `E:plan/f10-lock-envelope` (revision 3). 78-E1 MERGED (engine #618, `1b721aa41`, 2026-11-17): the `lock/v1` runtime lock envelope with `key_version`. 78-E2 MERGED (engine #633, `a50dc56ce`, 2026-11-17): the synthetic probe and an optional `probe` field in `lock/v1`. Left: the engine release and CLI repin, then 78-C1 (CLI environment report and fleet comparison) | `E:plan/f10-lock-envelope` | Phase 1 rows |

## Maintenance

No user-visible change. Merges at any time and never gates a release.

None.
