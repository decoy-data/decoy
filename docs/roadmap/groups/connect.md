# Sources and targets

Status: current

Part of the roadmap: [ROADMAP.md](../../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

Rows keep their number from the pre-split track. A row number or section number that is not in a group file is a closed row or old section in the [snapshot](../../archive/2026-11-18-roadmap-before-split.md).

## 1.0

Blocks the 1.0 release.

None.

## Later (1.x)

Additive. Not scheduled until a 1.x release picks it up. The release each row is planned for is in [releases-1x.md](../releases-1x.md).

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| 64 | CLI-CLOUD: S3 and GCS in the CLI through the DELIV cloud run prefix and conditional pointer | CLI | IN PROGRESS; owner 2026-11-06: CLI V1 (UX map Q6 closed). Plan `E:plan/cli-cloud` (`2026-11-12-cli-cloud.md`), 12 slices (EC0 to EC5, REL-C, CC1 to CC5). EC0 MERGED (engine #540, `a6308f2b`, 2026-11-12): S3 and GCS target tables in the delivery plan. EC1 MERGED (engine #542, `c0961a17`, 2026-11-12): one S3 client and classified connector errors. EC2a MERGED (engine #549, `13778a0d`, 2026-11-12): one S3 put path and SDK floors. EC1 and EC2a are in engine 0.23.0, which the CLI now pins (CLI #233). Owner 2026-11-12: one real S3 and one real GCS bucket run approved. Plan revision 3.5 (`bfbcefd6`, 2026-11-13) aligns cloud vaults and evidence with B-6 and DELIV 3.5; plan gate green (Dennis round 1, then a Codex fix pass). Owner Q-H answered (a): after an unknown pointer result, follow DELIV W6 | `E:plan/cli-cloud` `bfbcefd6` | CLI delivery |
| 64b | CLI-DB-SRC: PostgreSQL as a pipeline source (`type: postgres` with a value-free connection reference, a table list and the CONFIG-EXPLICIT column rules) through the engine `postgres_snapshot` primitive; needs a Postgres CI lane (CI-P2 markers, unparked for the engine and CLI) | engine, CLI | NOT STARTED; owner 2026-11-06: CLI V1 | CONFIG-EXPLICIT, CLI-IO | CLI delivery |
| 82 | F07: bounded path-observation discovery, nested-path relations, JSONB coverage | engine | PARTLY MERGED. Plan `E:plan/f07-path-discovery` (revision 3). 82-E1a MERGED (engine #636, `2d01b91af`, 2026-11-17): the nested handler moved to `nested/_handler.py`, no handler line changed. Left: 82-E1, E2a, E2b, E3a, E3b, E4a, E4b, E5 | `E:plan/f07-path-discovery` | NAME-REMOVAL |
| 86 | F01: PostgreSQL application-ready write target (staging, constraint, index and sequence restore, atomic publish) and the type-mapping report | engine, CLI | NOT STARTED; owner 2026-11-06: CLI V1 | none | Phase 2 rows; F22 |
| 87 | F02: SFTP, cloud scan, subset against cloud; retry executor; content digest on `WriteResult` | engine, CLI | NOT STARTED. Plan written 2026-11-17 (revision 3, Dennis round 2 applied): `E:plan/f02-sftp-cloud`, six engine slices E1 to E6, then the release and four CLI slices C1 to C4. No slice is merged | `E:plan/f02-sftp-cloud` | CLI-CLOUD; F22 adapter |
| SQL-FILTER | SQL filters on sources, as a new optional source key (DuckDB opportunity 13) | engine, CLI | NOT STARTED. 1.x minor | [post-1.0-plan](../post-1.0-plan.md) | row 64b |
| SUBSET-ANY-SOURCE | Subset from non-Parquet sources (DuckDB opportunity 19) | engine | NOT STARTED. 1.x minor | [post-1.0-plan](../post-1.0-plan.md) | none |
| SFTP-HOSTKEY | SFTP host-key fingerprint pinning as an option (pinning by default would refuse connections that work today) | engine | NOT STARTED. 1.x minor | [post-1.0-plan](../post-1.0-plan.md) (findings register) | row 87 |
| X-01 | Avro and ORC files | engine | NOT STARTED. 1.x minor | [expansion page](../v2-v3-expansion-candidates.md) | none |
| X-02 | JSON and JSONL with nested path masking | engine | NOT STARTED. 1.x minor | [expansion page](../v2-v3-expansion-candidates.md) | F07, F03 |
| X-03 | Excel workbooks | engine | NOT STARTED. 1.x minor | [expansion page](../v2-v3-expansion-candidates.md) | none |
| X-04 | XML with path masking | engine | NOT STARTED. 1.x minor | [expansion page](../v2-v3-expansion-candidates.md) | X-02 |
| X-05 | Delta Lake and Apache Iceberg tables | engine | NOT STARTED. 1.x minor | [expansion page](../v2-v3-expansion-candidates.md) | F22 |
| X-06 | More databases (MySQL, SQL Server, Snowflake, BigQuery; MongoDB later), read and write. DuckDB opportunities 11 and 12 are the same item | engine, CLI | NOT STARTED. 1.x minor | [expansion page](../v2-v3-expansion-candidates.md) | F01, row 64b |
| X-07 | Streaming and change-data-capture masking | engine, CLI | NOT STARTED. 1.x minor | [expansion page](../v2-v3-expansion-candidates.md) | F42 |
| F03 | File unions: several files as one logical table | engine, CLI | NOT STARTED. 1.x minor | [post-1.0-plan](../post-1.0-plan.md) (Council scope) | none |
| F05 | Fixed-width streaming; turns a refusal on large fixed-width files into a success | engine | NOT STARTED. 1.x minor | [post-1.0-plan](../post-1.0-plan.md) (Council scope) | none |
| X-19 | File metadata scrubbing as an option; the default stays | engine | NOT STARTED. 1.x minor | [expansion page](../v2-v3-expansion-candidates.md) | F38 |
| F38 | Dataset metadata preserve and redact | engine | NOT STARTED. 1.x if preserving metadata is opt-in, else 2.0 | [post-1.0-plan](../post-1.0-plan.md) (Council scope) | none |

## Maintenance

No user-visible change. Merges at any time and never gates a release.

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| CLOUD-COND-WRITES | GCS and S3 conditional writes; the output is the same | engine | NOT STARTED. 1.x patch | [post-1.0-plan](../post-1.0-plan.md) (findings register) | row 64 |
