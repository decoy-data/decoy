# Sources and targets

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
| 64 | CLI-CLOUD: S3 and GCS in the CLI through the DELIV cloud run prefix and conditional pointer | CLI | IN PROGRESS; owner 2026-11-06: CLI V1 (UX map Q6 closed). Plan `E:plan/cli-cloud` (`2026-11-12-cli-cloud.md`), 12 slices (EC0 to EC5, REL-C, CC1 to CC5). EC0 MERGED (engine #540, `a6308f2b`, 2026-11-12): S3 and GCS target tables in the delivery plan. EC1 MERGED (engine #542, `c0961a17`, 2026-11-12): one S3 client and classified connector errors. EC2a MERGED (engine #549, `13778a0d`, 2026-11-12): one S3 put path and SDK floors. EC1 and EC2a are in engine 0.23.0, which the CLI now pins (CLI #233). Owner 2026-11-12: one real S3 and one real GCS bucket run approved. Plan revision 3.5 (`bfbcefd6`, 2026-11-13) aligns cloud vaults and evidence with B-6 and DELIV 3.5; plan gate green (Dennis round 1, then a Codex fix pass). Owner Q-H answered (a): after an unknown pointer result, follow DELIV W6 | `E:plan/cli-cloud` `bfbcefd6` | CLI delivery |
| 64b | CLI-DB-SRC: PostgreSQL as a pipeline source (`type: postgres` with a value-free connection reference, a table list and the CONFIG-EXPLICIT column rules) through the engine `postgres_snapshot` primitive; needs a Postgres CI lane (CI-P2 markers, unparked for the engine and CLI) | engine, CLI | NOT STARTED; owner 2026-11-06: CLI V1 | CONFIG-EXPLICIT, CLI-IO | CLI delivery |
| 82 | F07: bounded path-observation discovery, nested-path relations, JSONB coverage | engine | PARTLY MERGED. Plan `E:plan/f07-path-discovery` (revision 3). 82-E1a MERGED (engine #636, `2d01b91af`, 2026-11-17): the nested handler moved to `nested/_handler.py`, no handler line changed. Left: 82-E1, E2a, E2b, E3a, E3b, E4a, E4b, E5 | `E:plan/f07-path-discovery` | NAME-REMOVAL |
| 86 | F01: PostgreSQL application-ready write target (staging, constraint, index and sequence restore, atomic publish) and the type-mapping report | engine, CLI | NOT STARTED; owner 2026-11-06: CLI V1 | none | Phase 2 rows; F22 |
| 87 | F02: SFTP, cloud scan, subset against cloud; retry executor; content digest on `WriteResult` | engine, CLI | NOT STARTED. Plan written 2026-11-17 (revision 3, Dennis round 2 applied): `E:plan/f02-sftp-cloud`, six engine slices E1 to E6, then the release and four CLI slices C1 to C4. No slice is merged | `E:plan/f02-sftp-cloud` | CLI-CLOUD; F22 adapter |

## Maintenance

No user-visible change. Merges at any time and never gates a release.

None.
