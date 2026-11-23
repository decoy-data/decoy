# Fit and generate

Status: current

Part of the roadmap: [ROADMAP.md](../../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

Rows keep their number from the pre-split track. A row number or section number that is not in a group file is a closed row or old section in the [snapshot](../../archive/2026-11-18-roadmap-before-split.md).

## 1.0

Blocks the 1.0 release.

Engine fast-path gaps are due 2026-12-15 (owner 2026-11-22). Every masking strategy and generation provider runs its fastest path by default in V1; pandas is not a shipped default. The named pandas exceptions are shuffle, geo_generalize, joint_mask, nested and tokenize. They show on the run card and in the docs.

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| 24n | GEN-REL (owner 2026-11-08, all V1): a date window anchored to a parent column; per-parent `derived_aggregate`; self-reference (`manager_id`) as a hierarchy, not a cycle; an empty parent fails under `orphan_policy: fail`; impossible or contradictory `min/max_per_parent` refused; weighted `reference` with no weights refused. Fan-out from a fit is row 24h | engine | CLOSED (every slice merged, 2026-11-21). Plan on `E:plan/gen-rel`. Slice 0 MERGED (engine #506, `7d2cd2dc`, 2026-11-12): pending reason codes and the release stamp. Slice 1 MERGED (engine #523, 2026-11-20): per-parent bounds are exact and honor `orphan_policy`. Slice 2 MERGED (engine #546, 2026-11-21): self-reference trees. #555 (windowed dates anchored to a parent row) and #561 (per-parent categorical mix) merged inside engine #596 (`8b133015`, 2026-11-21). GC3 MERGED (engine #643, CLI #373) | [GEN QA report](../../records/2026-11-08-cli-qa-generation.md) High | row 24h |
| 24p | GEN-PROVIDERS (completeness audit, owner 2026-11-08): includes census item A9 (owner 2026-11-12): each identifier provider declares its real locale scope, with a guard test on the declarations; generation can use every masking domain provider (NPI, MRN, ICD-10, NDC, PAN, IBAN, CUSIP, EIN, SSN and the rest of the 34) and the correlated person and address composites (email matches name, ZIP matches state, sex matches first name, age matches birth date); an unknown provider name fails at validate. Existing code, reused from the masking registry, not copied | engine | PARTLY MERGED. Plan `E:plan/gen-providers` (slices E1, E2, E3). E1 MERGED (engine #661, `efeb56df8`, 2026-11-20): the `provider` generate type for the masking identifier providers, each provider's locale scope declared and guarded (A9), and an unknown provider name refused at validate. E2 (composite handler refactor for the person and address bundles) is engine #778, in its final gate. E3 (`sex` and `age` fields) is in build. Owner questions taken on the recommended answers under standing approval (2026-11-10): `type: provider`; per-provider options and `unique` are V2; `composite_custom` is refused; sex values are F and M | [GEN completeness audit](../../records/2026-11-08-generation-completeness-audit.md) Decision 1, 2 | row 24i, row 24k |
| 24q | GEN-TYPES (owner 2026-11-08): new generate types and options: `constant`; parametric `distribution` with the `uniform` family (the other families are row 24qb, 1.x); a weighted lookup list from a file; per-column output type (int, decimal(n), date, bool); conditional `derived` (`if()`) | engine | IN PROGRESS. Plan passed 2026-11-10 (`E:plan/gen-types`). E1 MERGED (engine #467, `45533490`, 2026-11-10): `constant`, and `distribution` with the `uniform` family only, drawn from a new `dist` RNG family; normal, lognormal, exponential, poisson, beta and zipf are refused at compile (`generate_option_value_unknown`) and move to E1b. Owner answer (recommended, standing approval, 2026-11-10): drop the families that are not portable instead of adding a per-architecture caveat. E1 is in engine `v0.22.0` (#472). E2 MERGED (engine #477, `82d00f4e`, 2026-11-11): `output_type` on generate columns. Next: E1b (more families) needs a portable-sampling design first; E3 MERGED (engine #501, `ee156764`, 2026-11-12): the `lookup` generate type. E4 MERGED (engine #490, `72b75489`, 2026-11-12): `if()` and lazy conditionals in derived columns. Left in 1.0: nothing; E1b (the other distribution families) moved to row 24qb, 1.2 (owner 2026-11-22). The row closes at the next close-out | [GEN completeness audit](../../records/2026-11-08-generation-completeness-audit.md) A | rows 24i, 24j, 24k |
| FIT-CODES-TEXT | `decoy fit` keeps zero-padded codes such as ZIPs and account numbers as text. Today it reads them as numbers, and 10.9% of generated ZIPs came out short (corrective backlog M4). It changes fit output, which is cheap before the freeze and a 2.0 change after it (V2-to-V1 cut, evaluation rank 3) | CLI, engine | IN PROGRESS. Engine slice MERGED (engine #765, 2026-11-23): `decoy fit` keeps zero-padded codes as text. Left: the CLI picks it up with the engine 0.28.4 pin bump. Owner 2026-11-22 (V2-to-V1 cut) | vault `handoffs/V2-CORRECTIVE-BACKLOG.md` entry M4; vault `V2-TO-V1-EVALUATION-2026-11-22.md` section 4.4 | none |
| GEN-WINDOWED-BATCH | Batch the `windowed_date` derive with the batched derive the pool sampler already uses, and vectorize the offsets and formatting. `windowed_date` takes about 87% of pure generation time (measured). The plan first decides whether the batch keeps the per-row bytes identical. V1, before the freeze (owner 2026-11-19, Q2). Record item F1 | engine | CLOSED (every slice merged). S1 MERGED (engine #718, 2026-11-19): `windowed_date` derives its row keys in one batch and parses, shifts and formats as vectors; output bytes are unchanged. S2 MERGED (engine #727, 2026-11-21): offsets from the keyed index kernel, which changes bytes | plan `E:docs/plans/2026-11-19-speed-batch-f1-f3-f4.md` (branch `plan/speed-batch-f1-f3-f4`); record `E:docs/records/2026-11-19-engine-speed-and-route-completeness.md` (engine #715) section 5.2 F1 | none |
| GEN-STREAM-ALL | Every generate column type runs on the streamed lane. Key-like Faker types (email, user_name, phone, url, domain, ipv4, street_address, postcode) are pooled on ordinary columns; `unique`, `reference` and `inherit` key columns opt out automatically. Output bytes may change before the freeze. Owner 2026-11-22 (V1 fast path) | engine | IN REVIEW. Plan in review | `E:plan/gen-stream-all` | none |
| GEN-PER-COLUMN | Generation routes per column, so one excepted column no longer sends the whole job to the legacy path. Owner 2026-11-22 (V1 fast path) | engine | NOT STARTED. Plan being written | plan not written | GEN-STREAM-ALL |
| GEN-VECTOR-STREAMS | Vectorize the generation `sequence`, `reference` and null-mask streams: numpy indices, one RNG call per batch. 2x to 5x on those columns (estimate). Moved from 1.0.x. Record item C2. Owner 2026-11-22 (V1 fast path) | engine | NOT STARTED. Plan being written | record `E:docs/records/2026-11-19-engine-speed-and-route-completeness.md` (engine #715) section 5.3 C2 | none |
| GEN-NONFAKER-DRAWS | Non-Faker draws (uuid, int and choice) are made per batch instead of per row. Owner 2026-11-22 (V1 fast path) | engine | IN REVIEW. Engine #775 (computed uuid, `random_int_range` and `random_choice` draws) is in its final gate. Plan passed | engine #775 | GEN-VECTOR-STREAMS |

Row 24n is split. 1.0 holds only the new failures (an empty parent under `orphan_policy: fail`, impossible settings). The new capabilities (a date window anchored to a parent column, per-parent aggregates, self-reference as a hierarchy) are Later.

Rows 24p, 24q and 24s moved here from Later on 2026-11-19. The 2026-11-08 owner decision made generate providers, types and catalog V1; the Later placement was drift (owner 2026-11-19, Q5).

## Later (1.x)

Additive. Not scheduled until a 1.x release picks it up.

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| 24qb | 1.2. GEN-TYPES E1b: the `distribution` families normal, lognormal, exponential, poisson, beta and zipf. Split from row 24q (owner 2026-11-22). 1.x because they are refused at compile today (`generate_option_value_unknown`), so this turns a refusal into a success. Needs a portable-sampling design first, so values match across x86 and arm64 | engine | NOT STARTED. Design not written | `E:plan/gen-types` | row 24q |
| 24r | GEN-INHERIT (owner 2026-11-08): a child column takes a parent row's attribute (`claims.state` = the member's state); conditional categoricals declared in YAML, not only from a fitted snapshot | engine | NOT STARTED. Plan passed 2026-11-10 (`E:plan/gen-inherit`); build not started | [GEN completeness audit](../../records/2026-11-08-generation-completeness-audit.md) B | row 24n |
| EDGE-CASES | 1.x (1.2). Edge-case test-data providers (boundary strings, injection strings, odd values) in the default provider registry, opt-in by name; the built part of X-17. Was V2-5.4. Detail in [releases-1x.md](../releases-1x.md) | engine | IN REVIEW, held until after 1.0. Built; code review round 2 PASS WITH CONCERNS. Left: port to current main (6 conflict files, one shared with INTL-IDS.2), PR, full suite | `E:feat/v2-5.4-edge-case-providers` | INTL-IDS.2 (same catalog file) |
| COPULA | 1.x (1.6). Gaussian copula synthesis, the built part of X-14: model and disclosure floors (COPULA.1, engine draft #703), fit and sample (COPULA.2, #705), a value-free quality report (COPULA.3, no PR). Library only. Was V2-4.2, 4.3, 4.4. Detail in [releases-1x.md](../releases-1x.md) | engine | IN REVIEW, held until after 1.0. No plan GO recorded. Left: plan review; COPULA.3 rebase onto #705; EXPERIMENTAL-TIER marking; not built: COPULA.5 DP route (chosen at its plan, after a survey), COPULA.6 config and CLI wiring. COPULA.4 (snapshot extension, V2-4.1) is not needed: the standalone model is kept (owner 2026-11-22) | `E:feat/v2-4.2-copula-foundations`, `E:feat/v2-4.2-4.3-gaussian-copula`, `E:feat/v2-4.4-copula-quality-report` | none |

### Candidates with no plan yet

Non-breaking ideas, so 1.x by rule. A candidate becomes a row in the table above when a release picks it up.

| Item | Source | Why it does not break |
|---|---|---|
| F46 reusable QA scenarios | Council features | New scenario compiler and case library. |
| F48 statistical synthesis | Council features | New opt-in backend and evaluation; existing generation unchanged. |
| X-14 Joint-distribution synthesis (Gaussian copula) | Expansion candidates X-01 to X-25 | New generation method; existing configs unchanged. The library is built: row COPULA. |
| X-15 Multi-table synthesis | Expansion candidates X-01 to X-25 | New generation method. |
| X-16 Generate from a schema | Expansion candidates X-01 to X-25 | New source of generation specs. |
| X-17 Edge-case test data | Expansion candidates X-01 to X-25 | New generators. The providers are built: row EDGE-CASES. |
| X-18 Sequential and event data synthesis | Expansion candidates X-01 to X-25 | New generation method. |
| A certified DP stack for normal users (a DP fit on a default install works) | ROADMAP row 24g | Turns the `dp_stack_uncertified` message into a success. Exit code 3 stays for the cases still refused. |
| GEN-PROVIDERS per-provider options and `unique` | ROADMAP row 24p | New optional keys on `type: provider`. |
| F2 follow-up: dirty generated output (nullable, NaN, nested) on the mixed route | Platform V2 candidate plan (`P:docs/backlog/v2-candidate-plan.md`) | Lifts a decline. |
| HC5-FIT-CLI: `decoy fit` wiring for `high_cardinality_columns`; the engine half is merged (carried from CLI #321) | `E:docs/backlog/hc-5-cli-fit-wiring.md` | A new option on `fit`. |
| Generate columns on a masked table: a masked table declares generate columns that add new columns beside its masked ones (today a table is either masked through `columns` or generated through `generate_columns`, never both) | Owner, 2026-11-19 | New optional config on a masked table; existing configs unchanged. |

## Maintenance

No user-visible change. Merges at any time and never gates a release.

None.
