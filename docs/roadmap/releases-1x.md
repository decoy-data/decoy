# 1.x program and release schedule

Status: plan

Part of the roadmap: [ROADMAP.md](../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

Rules consulted: dev-rules `00-universal.md`, `development-loop.md` (PLAN), `scope-discipline.md`,
`proportionality.md`, `api-and-compatibility.md`, `release-and-rollback.md`, `documentation.md`.

Owner decision, 2026-11-22: all work that was built or planned on a branch under the labels "V1+" or
"V2" is now 1.x work. This page sorts it into categories, puts each category into a 1.x release and
says what each item needs before it lands, so that no built work is lost. It also carries forward the
1.1 to 1.9 order from draft CLI PR #321 (branch `docs/roadmap-1x-schedule`), updated to the roadmap
as it is on 2026-11-22. This page replaces #321.

The facts about the branches come from two read-only inventories taken on 2026-11-22 from the origin
refs (engine main `8c2a194a3`, CLI main `2dfc0233`). No test, build or CI run was made for this page.
Conflict counts are from `git merge-tree` against engine main on that day; they grow as main moves.

## Contents

1. [Names](#names)
2. [The land rule](#the-land-rule)
3. [Alias table](#alias-table)
4. [Categories and releases](#categories-and-releases)
5. [Items](#items)
6. [Flagged items](#flagged-items)
7. [Owner decisions](#owner-decisions)
8. [Cleanup for the orchestrator](#cleanup-for-the-orchestrator)
9. [Draft PR titles](#draft-pr-titles)
10. [Release schedule](#release-schedule)
11. [The upgrade path](#the-upgrade-path)
12. [Corrective backlog by bucket and theme](#corrective-backlog-by-bucket-and-theme)
13. [Not verified](#not-verified)

## Names

| Name | Meaning | Old name |
|---|---|---|
| 1.0 | Blocks the 1.0.0 release. The 1.0 tables of the group files. | v1 |
| 1.x | Keeps the contract. A 1.x minor adds; a 1.x patch fixes. | v1+, and V2 for work built or planned on a branch |
| 2.0 | Breaks the contract. Waits in [2.0-holding.md](2.0-holding.md). Nothing is scheduled. | v2 |

The contract and the four tests that decide the bucket are in [post-1.0-plan.md](post-1.0-plan.md).

Some names keep "V2" because they name a thing, not a bucket. They do not mean 2.0:

- `V2-LOG`: the tag on a review note that does not block 1.0. Triage gives it a bucket.
- Source files: the platform "V2 candidate plan" (`P:docs/backlog/v2-candidate-plan.md`), the vault
  file `handoffs/V2-CORRECTIVE-BACKLOG.md`, the platform branch `plan/v2-duckdb-plans` and the vault
  folder `v2/duckdb/`.
- Engine branch names such as `feat/v2-3.1-generalization-hierarchies`. Branches are not renamed. The
  alias table below maps each one to its 1.x id.
- The placement tags in [v2-v3-expansion-candidates.md](v2-v3-expansion-candidates.md) are now Near,
  Mid and Far (they were V1+, V2 and V3). They say how big a candidate is, not its bucket.

## The land rule

Nothing in this program lands before the 1.0.0 release. This is the build-ahead rule of 2026-11-18,
repeated by the owner on 2026-11-22. Draft PRs stay draft. No branch is rebased for landing until 1.0.0
ships.

After 1.0.0, each item goes through the normal dev loop ([working-rules.md](working-rules.md)): a plan
review where the plan has no recorded GO, the port or rebase, the gates, then the merge. An item that
changes a default, an output, a run-metadata hash or a frozen surface does not start until its owner
decision is made ([Owner decisions](#owner-decisions)).

**Dark landing (proposed, owner decision 6).** An item that is a library only (no config key, CLI flag,
reachable reason code or report tag) may merge after 1.0.0 and before its release slot. It ships in the
next engine release but no config can reach it. Its new package must be private or labelled
experimental (row EXPERIMENTAL-TIER) until the release that wires it, so it is not frozen by accident.
This keeps built branches from drifting further from main. The items that can land dark are marked
"dark" in the tables below.

## Alias table

Engine branches unless marked. "Plan branch" is the `plan/` branch of the same name.

| Old name | Branch | PR | 1.x id |
|---|---|---|---|
| V1P-2.1 | `feat/v1plus-p2.1-check-digit-schemes` | #671 (draft) | INTL-IDS.1 |
| V1P-2.3 | `feat/v1plus-p2.3-national-id-generators` | none | INTL-IDS.2 |
| V1P-2.4 | `feat/v1plus-p2.4-faker-locales` | none | INTL-IDS.3 |
| V1P-3.1 | `feat/v1plus-p3.1-email-keep-domain` | none | MASK-KEEP.1 |
| V1P-3.3 | `feat/v1plus-p3.3-card-keep-bin` | none | MASK-KEEP.2 |
| V1P-3.4 | `feat/v1plus-p3.4-ip-keep-prefix` | none | MASK-KEEP.3 |
| V1P-4.1 | `feat/v1plus-p4.1-avro-orc` | none | AVRO-ORC.1 |
| V1P-4.2 | not built | none | AVRO-ORC.2 |
| V2-2.1 | `feat/v2-2.1-entity-date-offset` | none | DATE-ENTITY.1 |
| V2-3.1 | `feat/v2-3.1-generalization-hierarchies` | #672 (draft) | ANON.1 |
| V2-3.2 | `feat/v2-3.2-anonymity-metrics` | #673 (draft) | ANON.2 |
| V2-3.3 part A | `feat/v2-3.3a-anonymity-models` | #687 (draft) | ANON.3 |
| V2-3.3 part B | `feat/v2-3.3-enforcement-search` | #689 (draft) | ANON.4 |
| V2-3.4 | `feat/v2-3.4-microaggregation` | #690 (draft) | ANON.5 |
| V2-3.5 | `feat/v2-3.5-risk-utility-report` | #694 (draft) | ANON.6 |
| V2-3.1b (config) | not built | none | ANON.7 |
| V2-3.3 slice 2 (config, planner, reason codes) | not built | none | ANON.8 |
| V2-3.5 slice 2 (evidence and CLI) | not built | none | ANON.9 |
| V2-4.2 step 1 | `feat/v2-4.2-copula-foundations` | #703 (draft) | COPULA.1 |
| V2-4.2 and 4.3 | `feat/v2-4.2-4.3-gaussian-copula` | #705 (draft) | COPULA.2 |
| V2-4.4 | `feat/v2-4.4-copula-quality-report` | none | COPULA.3 |
| V2-4.1 (snapshot extension) | not built | none | COPULA.4 |
| V2-4.5 or DPS-4 (DP on the joint model) | not built | none | COPULA.5 |
| (no old name) copula config and CLI wiring | not built | none | COPULA.6 |
| V2-5.4 | `feat/v2-5.4-edge-case-providers` | none | EDGE-CASES.1 |
| F07 82-E3b | `feat/f07-e3b` | #684 (draft) | 82-E3b (row 82) |
| native nested column masking | CLI `docs/roadmap-native-nested-mask` | CLI #385 | NESTED-NATIVE |
| F01 E0 | `feat/f01-e0` | #667 (draft) | 86-E0 (row 86) |
| V2 warehouse, engine half | `claude/v2-warehouse-sources-and-tokenization-vault` | none | WAREHOUSE.1 |
| V2 warehouse, platform half | platform `claude/v2-warehouse-sources-and-tokenization-vault` | none | WAREHOUSE.2 |
| DuckDB plans | platform `plan/v2-duckdb-plans` | none | WAREHOUSE.3 |

Each built item also has a plan branch (`plan/v1plus-*`, `plan/v2-*`). The feat branch carries the
same plan at a later revision, so the plan branches are cleanup ([Cleanup](#cleanup-for-the-orchestrator)).

## Categories and releases

| Category | 1.x ids | Group file | Release | Expansion candidate |
|---|---|---|---|---|
| Identifiers and generators | INTL-IDS.1 to .3, EDGE-CASES.1 | [mask](groups/mask.md), [generate](groups/generate.md) | 1.1 (INTL-IDS.1), 1.2 (the rest) | X-08, X-17 |
| Masking options | MASK-KEEP.1 to .3, DATE-ENTITY.1 | [mask](groups/mask.md) | 1.5 | X-10, X-13 |
| Formats and sources | AVRO-ORC.1, .2 | [connect](groups/connect.md) | 1.4 | X-01 |
| Anonymity and privacy | ANON.1 to .9 | [trust](groups/trust.md) | 1.7 | X-12, F37 |
| Nested data | 82-E3b, NESTED-NATIVE | [connect](groups/connect.md) | 1.1 (82-E3b), 1.9 (NESTED-NATIVE) | X-02, F07 |
| Joint-distribution generation | COPULA.1 to .6 | [generate](groups/generate.md) | 1.10 | X-14, F48 |
| Connectors and warehouse | 86-E0, WAREHOUSE.1 to .3 | [connect](groups/connect.md), [platform-parked](platform-parked.md) | 1.9 (86-E0), 1.11 (WAREHOUSE) | X-06, DuckDB 11 to 13 |

Why these slots:

- Each category joins the #321 release whose theme it fits: identifiers with generate completeness
  (1.2), Avro and ORC with sources (1.4), masking options with policy (1.5), anonymity with quality
  contracts (1.7, where #321 already had F37 and X-12 as fill).
- INTL-IDS.1 merges as it is and is small, so it is fill in 1.1. 82-E3b is held "until 1.1" by the
  owner decision of 2026-11-21 ([decisions.md](decisions.md)), so it is fill in 1.1 too.
- The copula and warehouse work has no #321 release that fits. They get two new minors after 1.9.
  Copula comes first because it is built; the warehouse work needs new plans.
- The library-only parts of anonymity and copula can land dark before their release (owner decision 6).

## Items

State is one of: "built, merge as-is", "built, port to current main" (rebase or re-apply on main and fix
conflicts), "re-plan, old branch as reference" (main moved too far; write a fresh plan that reuses the
branch), or "not built". "PWC" is PASS WITH CONCERNS. Ahead and behind are commits against engine main.
Size is added lines, source / tests, against the merge base.

### Identifiers and generators

| Id | Branch, PR | State | Conflicts | Plan and code review | Size | Dark |
|---|---|---|---|---|---|---|
| INTL-IDS.1 | `feat/v1plus-p2.1-check-digit-schemes`, #671; 9 ahead, 93 behind | built, merge as-is | 0 | plan rev 2 PWC; code review round 2 PWC. Visible CI green; ruff, mypy, regression, layers and prove-regression were skipped (draft), so their result is unknown | 177 / 334; S, 1 slice | yes |
| INTL-IDS.2 | `feat/v1plus-p2.3-national-id-generators`, no PR; 10 ahead, 331 behind | built, port to current main | 5 files, 1 source (`execution/native/_draw_sites_provider_backed.py`); the rest are generated or ledger files | plan rev 2 PWC; code review PWC (4 P2 handled). Last CI 2026-11-06 | 617 / 658 (includes old INTL-IDS.1 commits); S | no (new providers a config can name) |
| INTL-IDS.3 | `feat/v1plus-p2.4-faker-locales`, no PR; 4 ahead, 331 behind | built, port to current main; **flagged** | 3 files, no source | plan rev 3; code review not recorded in the inventory | 354 / 336; S | no |
| EDGE-CASES.1 | `feat/v2-5.4-edge-case-providers`, no PR; 8 ahead, 329 behind | built, port to current main | 6 files, 1 source (the same draw-site catalog file as INTL-IDS.2) | plan rev 3; code review round 2 PWC (3 advisory P2). Not run: the cross-model gate and the full suite | 862 / 707; S | no |

What each does. INTL-IDS.1 adds nine national check-digit schemes (gb_nhs, ca_sin, in_aadhaar, au_tfn,
de_idnr, fr_nir, es_dni, es_nie, it_codice_fiscale) to `checksums.validate` and `calc_check_digit`
through python-stdnum. FPE checksum mode keeps its 7 schemes and refuses the new ones at compile.
INTL-IDS.2 adds nine `decoy_native` providers (`synthetic_gb_nhs` and the rest) whose values pass those
schemes, for `strategy: faker`. The native and out-of-core routes do not admit them yet; they fall back
to Python with a reason code. INTL-IDS.3 makes the capability rows of the 19 Faker providers list only
the locales that work, and maps Faker's two locale failures to `provider.unsupported_locale`.
EDGE-CASES.1 adds edge-case test-data providers (boundary strings, injection strings, odd values) to
the default provider registry, opt-in by name.

Not built: X-08 region disguises (UK GDPR, PIPEDA, LGPD, APPI, DPDP) and detectors for these
identifiers. They stay candidates.

Landing steps:

1. INTL-IDS.1: mark #671 ready, run the full gate once, merge.
2. INTL-IDS.2: rebase onto the INTL-IDS.1 head (`53db68113` fixes the calculator-fault path), regenerate
   the proof manifest and the draw-site catalog pins, move the CHANGELOG entry to `changelog.d`.
3. EDGE-CASES.1: rebase after INTL-IDS.2 and regenerate the same catalog pins.
4. INTL-IDS.3: only after owner decision 3. Regenerate the locale table against the Faker release that
   1.0 ships (row FAKER-MIGRATE moves 1.0 to Faker 40.31; the branch table is for 40.23.0). The inbox
   item of 2026-11-18 (it_IT `address_city` not deterministic across processes) bears on which locales
   the table may list.

INTL-IDS.1 and the 1.0.x row FPE-CHECKSUM-NATIVE both touch `transforms/_fpe_checksum.py`. Whichever
lands second rebases.

### Masking options

| Id | Branch, PR | State | Conflicts | Plan and code review | Size | Dark |
|---|---|---|---|---|---|---|
| MASK-KEEP.1 | `feat/v1plus-p3.1-email-keep-domain`, no PR; 6 ahead, 318 behind | built, port to current main | 20 files, 7 source. `execution/_distribution_behavior.py` moved to `contracts/distribution_behavior.py` (engine #611), so one edit has no target | plan rev 2 PWC; Dennis code review PWC (2 P2, 4 P3). No CI run ever | 887 / 1319; M | no |
| MASK-KEEP.2 | `feat/v1plus-p3.3-card-keep-bin`, no PR; 10 ahead, 318 behind | built, port to current main | 6 files, 3 source | plan rev 2 PWC; code review PWC (2 P2, 5 P3 fixed, one P3 declined) | 383 / 1100; S to M | no |
| MASK-KEEP.3 | `feat/v1plus-p3.4-ip-keep-prefix`, no PR; 9 ahead, 318 behind | built, port to current main | 19 files, 6 source | plan rev 2 PWC; code review round 1 FAIL (2 P1), then fixed; no re-review recorded | 713 / 1643; M | no |
| DATE-ENTITY.1 | `feat/v2-2.1-entity-date-offset`, no PR; 6 ahead, 318 behind | built, port to current main | 19 files, 8 source; touches the chunked and multi-table paths that 1.0 changed | plan rev 2 PASS; code review 1 PWC, re-review FAIL (1 P1) fixed, "awaiting re-review" | 965 / 1776; M to L | no |

What each does. MASK-KEEP.1 is an opt-in email mask that keeps the domain or its class (free mail or
corporate). MASK-KEEP.2 is a `keep_bin` option on Luhn checksum FPE: the card BIN stays and the output
stays Luhn-valid. MASK-KEEP.3 is an opt-in `ip_prefix` strategy (Crypto-PAn style) that keeps the subnet
prefix, with residual-PII and leak-check changes for it. DATE-ENTITY.1 adds `entity_key` to
`date_shift`, so all dates of one entity move by the same offset. All four are opt-in: a config that
does not use them gives the same bytes. They add reason codes (the registry is append-only; use
`since=UNRELEASED`).

Not built: series noise for numeric time series (the rest of X-13), and V2-2.2 DICOM, which needs
DATE-ENTITY.1 (candidate X-21).

Landing steps:

1. Port the three MASK-KEEP branches as one lane, in the order .1, .2, .3. They share the reason
   registry, draw-site and sentry churn.
2. MASK-KEEP.3: check that the residual-PII verifier output does not change for configs that do not use
   `ip_prefix`.
3. DATE-ENTITY.1: port, re-run against the current chunked and multi-table routes, then the re-review
   the branch is waiting for.

### Formats and sources

| Id | Branch, PR | State | Conflicts | Plan and code review | Size | Dark |
|---|---|---|---|---|---|---|
| AVRO-ORC.1 | `feat/v1plus-p4.1-avro-orc`, no PR; 7 ahead, 318 behind | built, port to current main | 15 files, 7 source (`config/_sources.py`, `config/_targets.py`, `fileaccess/adapters/arrow.py`, `profile/_readers.py`, reasons, `run_result/_model.py`). `fileaccess` changed a lot since | plan rev 2 passed re-review; code review not done ("awaiting code review") | 1790 / 4907; M | no |
| AVRO-ORC.2 | not built | not built | n/a | no plan | CLI wiring; S to M (estimate) | no |

AVRO-ORC.1 adds Avro and ORC file sources and targets to the engine: its own Avro container reader
with block caps, ORC through pyarrow. The plan adds no dependency, and `pyproject.toml` and `uv.lock`
show no change on the branch. It adds a field to the run-result model, which needs a compatibility check
([Flagged items](#flagged-items)).

Landing steps: port AVRO-ORC.1 onto the current `fileaccess` package, then its code review, then the
compatibility check, then plan and build AVRO-ORC.2 (the CLI half) after the engine release.

### Anonymity and privacy

One stack. Each branch contains its parent; the GitHub PR bases already follow this order:
main, ANON.1 (#672), ANON.2 (#673), ANON.3 (#687), ANON.4 (#689), ANON.5 (#690), ANON.6 (#694).
CI passed on every PR head (against old bases). No PR has a review or a comment on GitHub.

| Id | Branch, PR | State | Conflicts | Plan and code review | Size (cumulative) | Dark |
|---|---|---|---|---|---|---|
| ANON.1 | `feat/v2-3.1-generalization-hierarchies`, #672; 10 ahead, 93 behind | built, merge as-is | 0 | plan rev 2: review rev 1 FAIL (1 P1), re-review FAIL (1 P1), findings folded in at the coordinator's instruction. No GO recorded | 1162 / 1323; S | yes |
| ANON.2 | `feat/v2-3.2-anonymity-metrics`, #673; 27 ahead | built, merge as-is | 0 | plan rev 3: review FAIL (2 P1, 8 P2), re-check FAIL (2 P1, 2 P2), folded in. No GO recorded. The plan links a stale CLI branch | 2290 / 2676; S | yes |
| ANON.3 | `feat/v2-3.3a-anonymity-models`, #687; 32 ahead | built, port to current main | 2: `.importlinter`, `tests/sentry/layout/test_import_layers.py` | V2-3.3 plan rev 3: review rev 1 PWC (3 P1, 5 P2), folded in. No GO for this half | 2752 / 3063; S to M | yes |
| ANON.4 | `feat/v2-3.3-enforcement-search`, #689; 41 ahead | built, port to current main | the same 2 (from ANON.3) | plan rev 3; code-review gaps fixed in `5b339739`. No GO text found | 3546 / 4783; M | yes |
| ANON.5 | `feat/v2-3.4-microaggregation`, #690; 45 ahead | built, port to current main | the same 2 | plan header says "revision 1 (awaiting plan review)" but a code-review fix commit exists (2026-11-07); header is stale. No plan GO | 4049 / 5574; S | yes |
| ANON.6 | `feat/v2-3.5-risk-utility-report`, #694; 54 ahead | built, port to current main; **flagged** | 5: `.importlinter`, `docs/frozen-surfaces.md`, `compat_corpus/regenerate.py`, `compat_corpus/test_compat_corpus.py`, `test_import_layers.py` | plan rev 4: review rev 1 PWC (1 P1, 5 P2); code review record 2026-11-12. No GO | 4790 / 7515; M | no (adds a frozen tag) |
| ANON.7 | not built (V2-3.1b) | not built | n/a | no plan found | config for hierarchies; size not known | no |
| ANON.8 | not built (V2-3.3 slice 2) | not built | n/a | outlined in the V2-3.3 plan | config keys, planner, reason codes; M (estimate) | no |
| ANON.9 | not built (V2-3.5 slice 2) | not built | n/a | outlined in the V2-3.5 plan | evidence and CLI wiring; M (estimate) | no |

What it does. ANON.1: per-quasi-identifier generalization hierarchies and the lattice of level vectors.
ANON.2: k-anonymity, l-diversity and t-closeness measurement, value-free. ANON.3: privacy-model
descriptors, frequency sets, and a new bottom-tier private package `decoy_engine._value_family`
(main's layer contract forbids the back edge otherwise). ANON.4: the least-information-loss lattice
search with a suppression budget. ANON.5: MDAV microaggregation for numeric quasi-identifiers.
ANON.6: the `risk-utility-report/v1` document (prosecutor, journalist and marketer risk as ARX computes
them, information loss, rows suppressed). ANON.1 to ANON.6 are library only. Without ANON.7 to ANON.9 no
config can reach them.

Landing steps:

1. Owner decision 6 (dark landing) and, for ANON.6, owner decision 1.
2. A fresh plan review for ANON.1 to ANON.6, since no plan records a GO. Check that each folded finding
   is closed. Fix the stale CLI-branch links in the ANON.2 plan and the stale header in the ANON.5 plan.
3. Merge main into ANON.1, then ANON.2 (both clean). Re-run the layer sentry.
4. Fix the two layer-contract conflicts once at ANON.3 (register `_value_family` in the bottom tier of
   main's current contract) and carry the fix up the stack. This is cheaper than a fix per branch.
5. ANON.4: re-capture the dark golden literals against current main.
6. ANON.5, then ANON.6: re-capture the compatibility corpus for the new tag.
7. Plan and build ANON.7, ANON.8 and ANON.9 for release 1.7.

### Nested data

| Id | Branch, PR | State | Conflicts | Plan and code review | Size | Dark |
|---|---|---|---|---|---|---|
| 82-E3b | `feat/f07-e3b`, #684; 20 ahead, 14 behind | built, port to current main | 5 files, 3 source (plan checks moved on main) | plan `E:plan/f07-path-discovery` rev 3; Dennis rounds 1 and 2 fixed; Codex round 3 no 1.0 findings. CI: one failure (companion wheel, Linux 3.11 aarch64), cause not read | 2202 / 1307; S | no (new `rules` key) |
| NESTED-NATIVE | none (candidate from CLI #385) | not built | n/a | no plan | not sized | no |

82-E3b lets a `nested` column carry `provider_config.rules`, a list of `{target, strategy,
strategy_config, namespace?}`. The single-rule form does not change. NESTED-NATIVE is masking fields
inside native Parquet and Arrow struct, list and map columns (`address.street`, `tags[*]`). Today such a
column can only pass through or be dropped. Its first step, from #385, is to confirm and test that a
`nested` rule on a native struct fails closed and to state the limit in the docs.

Landing steps: merge main into #684, fix the 5 conflicts, re-run CI (read the aarch64 failure), merge in
1.1. NESTED-NATIVE needs a plan; it uses the same path selector as X-02 and F07, so plan it with the rest
of row 82 for 1.9.

### Joint-distribution generation

A second stack: main, COPULA.1 (#703), COPULA.2 (#705). COPULA.3 was built on an older copula state
(merge base with #705 is `7a43b04c`) and must be rebased onto the COPULA.2 head.

| Id | Branch, PR | State | Conflicts | Plan and code review | Size | Dark |
|---|---|---|---|---|---|---|
| COPULA.1 | `feat/v2-4.2-copula-foundations`, #703; 6 ahead, 73 behind | built, merge as-is | 0 | plan `plan/v2-4.2-4.3-gaussian-copula` rev 3: review 1 GATE FAIL (4 P1), re-check GATE FAIL (3 P1), orchestrator decisions folded in. No GO | 905 / 5115; S | yes |
| COPULA.2 | `feat/v2-4.2-4.3-gaussian-copula`, #705; 24 ahead | built, port to current main | 2, both list appends (`scripts/dev/sentry_registry.toml`, `tests/sentry/secret_material_census.json`); keep both sides | same plan | 1656 / 6645 (cumulative); S | yes |
| COPULA.3 | `feat/v2-4.4-copula-quality-report`, no PR; 20 ahead, 329 behind | built, port to current main | 3 (`CODEMAP.md`, `docs/methodology-registry.yaml`, the census file), plus the rebase onto COPULA.2 | plan rev 2 (rev 1 FAIL: 2 P1, 6 P2, 3 P3); code review round 1 and re-review recorded 2026-11-08 | 2686 / 8153 cumulative; about 4 quality modules of its own; M | yes |
| COPULA.4 | not built (V2-4.1) | not built | n/a | decision pending (owner decision 5) | not sized | no |
| COPULA.5 | not built (V2-4.5 or DPS-4) | not built | n/a | route not chosen (owner decision 2) | not sized | no |
| COPULA.6 | not built | not built | n/a | no plan. The copula plan adds no config key and no strategy, so a config cannot reach the copula until this is planned | not sized | no |

What it does. COPULA.1: the copula model object, disclosure floors, nearest-correlation fix and normal
numerics. COPULA.2: `fit_gaussian_copula` (marginals from a caller's snapshot, correlation from the
frame) and `sample_gaussian_copula`, with categorical, null-as-state and mixed columns, and seed-wipe
discipline. It adds exactly the two `seed` census rows the owner approved on 2026-11-19. COPULA.3: a
value-free quality report for copula output (marginal fit, pairwise correlation and contingency
similarity, distance to closest record), with every real-data statistic passing the disclosure floors.

Landing steps:

1. Owner decision 6. A fresh plan review for COPULA.1 and COPULA.2 (no GO recorded).
2. Merge main into COPULA.1 (clean); review; merge.
3. COPULA.2: resolve the two append conflicts, re-run the census sentry and confirm exactly two new
   rows, send the mutation table to the owner as the 2026-11-19 reply asks.
4. COPULA.3: rebase onto the COPULA.2 head, drop its two seed census rows with empty reasons (they
   duplicate the approved rows), move the CHANGELOG entry to `changelog.d`, re-capture
   `tests/unit/generation/copula/quality/_dark_golden.json`, fix the plan's stack line, open the PR,
   review.
5. Owner decisions 2 and 5, then plan COPULA.4, COPULA.5 and COPULA.6 for release 1.10.

### Connectors and warehouse

| Id | Branch, PR | State | Conflicts | Plan and code review | Size | Dark |
|---|---|---|---|---|---|---|
| 86-E0 | `feat/f01-e0`, #667; 9 ahead, 94 behind | built; a record, not a feature | 0 | spike against plan `docs/plans/2026-11-17-f01-postgres-target.md` rev 3. pg-gate: 71 pass, 4 fail; cell e fails on all four statement paths by design of the test, fallback cell e2 passes | 1 / 510, record 37 lines | n/a |
| WAREHOUSE.1 | engine `claude/v2-warehouse-sources-and-tokenization-vault`, no PR; 11 ahead, 467 behind | re-plan, old branch as reference | 9 files, 7 source (`_tokenize.py`, `_pipeline.py`, adapters, `connectors/postgres_snapshot.py`, draw-site inventory) | no plan review found | 1365 / 1732 including the tokenize part; L | no |
| WAREHOUSE.2 | platform `claude/v2-warehouse-sources-and-tokenization-vault`, no PR; 22 ahead, 312 behind | re-plan, old branch as reference; parked with the platform | 36 files, nearly all in the vault | none found | about 3.5k added lines outside the vault | no |
| WAREHOUSE.3 | platform `plan/v2-duckdb-plans`, no PR; 32 ahead, 59 behind | built (docs), merge as-is | 0 | 17 plan drafts, an audit and a master note; review state per plan not checked | 5353 doc lines | n/a |

86-E0 tests the F01 Postgres write design. Cell e: `interrupt()` on the DuckDB connection does not cancel
a running `postgres_query` or `postgres_execute` and does not stop a connect. Cell e2 shows that
`pg_cancel_backend(pid)` from a second session works, and cell h shows that `PGCONNECT_TIMEOUT` bounds a
connect. F01 E1 does not start until owner decision 4 (Q15).

WAREHOUSE.1 holds the DuckDB attach core, the catalog browser and the DuckDB-file source
(`connectors/duckdb_attach/`), the multi-part Parquet export reader (`connectors/parquet_dataset.py`) and
a warehouse export fidelity record. It also holds the `tokenize` strategy and `token_vault_writer`,
which main now has in another form (B-6). WAREHOUSE.2 holds the platform DuckDB sources (fence, file
provider, catalog endpoint, `/from-database` route, source picker, multi-part staging, a guide) and the
vault work, which main has as B-6. None of the DuckDB or warehouse parts exist on main.

Landing steps:

1. 86-E0: owner decision 4. Then either mark cell e expected-fail and merge #667 as a record, or keep only
   the record doc. F01 (row 86) is planned for 1.9 with the deadline mechanism the decision picks.
2. WAREHOUSE.3: merge as docs whenever a platform docs merge is allowed. It is the input to the plans.
3. WAREHOUSE.1: write a fresh plan for the DuckDB attach and the multi-part Parquet reader on the current
   connectors and `fileaccess`, using the branch as reference. Leave out every tokenize and vault commit.
4. WAREHOUSE.2: the same for the platform half, when the platform restarts ([platform-parked.md](platform-parked.md)).

## Flagged items

The rule: additive or opt-in work goes in a 1.x minor. An item that changes a default, existing output,
run-metadata hashes or a frozen surface is flagged here with what it needs.

| Id | What changes | Needs |
|---|---|---|
| INTL-IDS.3 | The capability rows that the cockpit and platform read, the run-metadata hashes, and the error a bad-locale config gets. Data output stays byte-identical per the plan (not checked against the frozen-surface docs) | Owner decision 3. As built it is 2.0 after the freeze; it is 1.x only if built a way that keeps the hashes and rows of existing configs, or if it lands with FAKER-MIGRATE before the freeze |
| ANON.6 | Adds the frozen output tag `risk-utility-report/v1` to `docs/frozen-surfaces.md`, the compatibility contract (contract 3.1) and the compat corpus. Additive, but permanent for 1.x once released | Owner decision 1 |
| COPULA.4 | Extending `distribution-snapshot/v1` in place would change a frozen tag | 1.x only as a new snapshot tag or as the standalone model the plan chose; owner decision 5 |
| AVRO-ORC.1 | Adds a field to the run-result model and new reason codes | A compatibility check, not an owner call: 1.x if the field is optional and absent for other formats, else 2.0 |
| MASK-KEEP.3 | Touches the residual-PII verifier | A check that verifier output does not change for configs without `ip_prefix` |
| EDGE-CASES.1 | Adds providers to the default registry (an exception the owner approved). No existing output changes | Nothing more; noted because the names become reserved |
| COPULA.2 | Adds two `seed` rows to the secret-material census | Already approved by the owner (2026-11-19) |

## Owner decisions

1. **`risk-utility-report/v1` (ANON.6).** Freeze the new tag when ANON.6 merges, or keep it out of
   `docs/frozen-surfaces.md` and the compat corpus until the release that ships ANON.9 (the first use a
   user can reach). Recommended: freeze it only in that release.
2. **Copula DP route (COPULA.5).** DPCopula style (the old V2-4.5 outline: noise on the correlation
   release of this model) or PrivBayes (DPS-4 in `E:docs/backlog/dps-dp-synthetic-implementation.md`).
   The copula plan keeps both open. COPULA.1 to COPULA.3 do not depend on it. Recommended: decide at the
   COPULA.5 plan, after the survey of established tools the dev rules ask for.
3. **Faker locales compatibility (INTL-IDS.3).** (a) Land it before the 1.0 freeze, with FAKER-MIGRATE,
   which already regenerates the goldens; this breaks the build-ahead rule. (b) Rebuild it so existing
   configs keep their hashes and capability rows, as a 1.x minor. (c) Hold it for 2.0.
4. **Q15 (#667, row 86 F01).** How the F01 publisher bounds a statement now that DuckDB `interrupt()`
   does not cancel it: a watchdog session with `pg_cancel_backend` plus `statement_timeout` and
   `lock_timeout` (cell e2), and `PGCONNECT_TIMEOUT` for connect (cell h), or another design. Also:
   merge #667 as a record with cell e marked expected-fail, or keep the record doc only. Row 86 says
   "owner 2026-11-06: CLI V1" but sits in Later; confirm it is 1.x (1.9).
5. **Copula snapshot (COPULA.4).** Keep the standalone copula model, or add the copula parameters to the
   snapshot under a new tag.
6. **Dark landing.** May library-only items (INTL-IDS.1, ANON.1 to ANON.5, COPULA.1 to COPULA.3) merge
   after 1.0.0 and before their release slot, marked private or experimental?

## Cleanup for the orchestrator

Not done in this PR. Each needs the orchestrator, and some need the owner's normal approval for deletes.

1. Close engine #333 (`claude/sharp-goodall-ikag71`): superseded by engine #361 and later file-access
   slices. The inventory did not diff it line by line, so check once for a stray piece first, as
   [branch-register.md](branch-register.md) says.
2. Delete the merged CLI branches `docs/v1x-v2-classification` (#284) and `docs/v2-vault-streaming-rows`
   (#232).
3. Delete the 16 engine plan branches (`plan/v1plus-p2.1`, `p2.3`, `p2.4`, `p3.1`, `p3.3`, `p3.4`,
   `p4.1`; `plan/v2-2.1`, `3.1`, `3.2`, `3.3`, `3.4`, `3.5`, `4.2-4.3`, `4.4`, `5.4`, full names on
   origin). Each feat branch has the same plan at a later revision. `plan/v1plus-p2.3` also carries old
   INTL-IDS.1 commits that the feat branch replaces.
4. Drop the tokenize and vault halves of `claude/v2-warehouse-sources-and-tokenization-vault` (engine and
   platform) when WAREHOUSE.1 and WAREHOUSE.2 are re-planned. Keep the branch as reference until then
   (branch-register marks it HIGH lost-work risk).
5. Close CLI #321 as replaced by this page.
6. Retitle the draft engine PRs ([Draft PR titles](#draft-pr-titles)).
7. Update the vault `BRANCH-LIST.md` and the memory note on V1+ and V2 branches to the 1.x ids.
8. Rename `v2-v3-expansion-candidates.md` to `expansion-candidates.md`. Not done here because the archive
   snapshot, the 2026-11-18 handoff and a 2026-11-08 record link to the old name.

## Draft PR titles

New PRs for this program use the prefix "1.x".

| PR | Current title | New title |
|---|---|---|
| engine #671 | V1+ feat(checksums): nine national identifier check-digit schemes | 1.x feat(checksums): nine national identifier check-digit schemes |
| engine #672 | V2 feat(anonymize): generalization hierarchies for quasi-identifiers | 1.x feat(anonymize): generalization hierarchies for quasi-identifiers |
| engine #673 | V2 feat(quality): k-anonymity, l-diversity and t-closeness metrics | 1.x feat(quality): k-anonymity, l-diversity and t-closeness metrics |
| engine #687 | V2 feat(anonymity): model descriptors, frequency sets, _value_family | 1.x feat(anonymity): model descriptors, frequency sets, _value_family |
| engine #689 | V2 feat(anonymize): least-loss lattice search with record suppression | 1.x feat(anonymize): least-loss lattice search with record suppression |
| engine #690 | V2 feat(anonymize): MDAV microaggregation for numeric quasi-identifiers | 1.x feat(anonymize): MDAV microaggregation for numeric quasi-identifiers |
| engine #694 | V2-3.5: risk and utility report (risk-utility-report/v1) | 1.x feat(anonymize): risk and utility report (risk-utility-report/v1) |
| engine #703 | V2-4.2/4.3 part A: copula model, floors and numerical parts | 1.x feat(copula): copula model, disclosure floors and numerics |
| engine #705 | V2-4.2/4.3 part B: copula fit and sample, scoped census exception | 1.x feat(copula): fit and sample with the scoped seed census rows |
| engine #684 | feat(nested): run several rules per nested column (F07 E3b) | 1.x feat(nested): run several rules per nested column (F07 E3b) |
| engine #667 | test(connectors): add the F01 E0 Postgres write spike | 1.x test(connectors): add the F01 E0 Postgres write spike |

## Release schedule

Carried from #321 and updated to 2026-11-22. Changes from #321: rows 24p, 24q and 24s left 1.2 (24p and
24q became 1.0 rows on 2026-11-19, and 24s closed); row 84 closed; the named speed slots of 2026-11-19
([post-1.0-plan.md](post-1.0-plan.md)) are placed; the seven categories above are slotted; 1.10 and 1.11
are new.

How to read it:

- A minor has one headline group from Later, a time budget, and fill: first from that group's
  candidates, then small rows from other groups. Fill that does not fit stays in the pool. It never
  delays the release.
- Size is in slices. A slice is one reviewed pull request of about 800 hand-written lines or fewer
  ([working-rules.md](working-rules.md), 4.2). The numbers are rough.
- "Engine release" says whether the minor needs engine code that is not yet in a release. If so, the
  CLI half waits for the engine release and the repin.
- Before a minor is planned, check each item against [2.0-holding.md](2.0-holding.md).
- The order is a recommendation by user value and dependency. A user request can move a theme earlier.
  Moving one is an edit here plus a line in [decisions.md](decisions.md). Choosing the 1.1 theme is an
  owner call; this page proposes one.
- Dates are not given. A minor is planned as two to three weeks of work.

| Release | Theme | Headline rows and 1.x items | Size (slices) | Engine release |
|---|---|---|---|---|
| 1.0.x | Fixes and byte-identical speed | Maintenance rows, patch entries of the corrective backlog; GEN-VECTOR-STREAMS, TEXT-REDACT-RUST-SPLICE, FPE-CHECKSUM-NATIVE | 1 to 4 each | only if a fix is in the engine |
| 1.1 | Run in production pipelines | 64, 85, 41, PER-COLUMN-ROUTING with SEAM-REASONS; fill 82-E3b, INTL-IDS.1 | about 20 | yes |
| 1.2 | Generate completeness and identifiers | 24r, the Later part of 24n, RUST-DATE-TEXT; INTL-IDS.2, INTL-IDS.3, EDGE-CASES.1 | about 14 | yes |
| 1.3 | More ways to install | 90a, 38, 42, PIP-NATIVE-EXTRA; candidates PYPI, PY-VERSIONS; CHUNK-PARALLEL | about 13 | yes (CHUNK-PARALLEL only) |
| 1.4 | More sources and formats | 64b, 87; AVRO-ORC.1, AVRO-ORC.2 | about 19 | yes |
| 1.5 | Policy, secrets and masking options | 81 with 24zt, 83, the Later part of 79; MASK-KEEP.1 to .3, DATE-ENTITY.1 | about 20 | yes |
| 1.6 | Scan baselines and drift | 30, 31, 32, 80 | about 12 | yes |
| 1.7 | Quality contracts and privacy risk | 69, 68; ANON.1 to ANON.9 | about 18 | yes |
| 1.8 | Evidence you can hand to an auditor | 72, 78, 70 | about 11 | yes |
| 1.9 | Nested data and application-ready databases | 82, 86 (with 86-E0); NESTED-NATIVE | about 16 | yes |
| 1.10 | Joint-distribution synthesis | COPULA.1 to COPULA.6; candidate F48 | about 10 (COPULA.4 to .6 not sized) | yes |
| 1.11 | Warehouses and more databases | WAREHOUSE.1 to .3; candidates X-06, DuckDB 11 to 13 | not sized; needs plans | yes |
| later | Chosen from the pool on evidence | see [The pool](#the-pool-after-111) | | |
| 2.0 | Only contract breaks | see [2.0](#20) | | |

Windows (rows 6 and 89) is 1.0, so it is not on this page.

### 1.0.x patch releases

A patch release carries fixes and internal cleanup. For a config or run that is valid today it never
changes a name, a default, an output byte, an exit code, a reason string, a schema field or a report
tag. Cut one when a fix is ready.

In order:

1. A fix that a user reports and that breaks a function or loses data, in its own patch.
2. Broken-today items from the inbox that miss 1.0, and row 24zr SETUP-NER-JSON ([release](groups/release.md)).
3. The Maintenance rows and maintenance candidates in [health](groups/health.md).
4. The 1.0.x speed slots: GEN-VECTOR-STREAMS ([generate](groups/generate.md)), TEXT-REDACT-RUST-SPLICE
   and FPE-CHECKSUM-NATIVE ([mask](groups/mask.md)), plus FAKER-NATIVE-WIDEN, LARGE-STRING-CAST and
   UF-DOMAIN, and NONFK-OOM part (b) if they miss 1.0. Output bytes must not change.
5. The patch entries of the corrective backlog, by theme, when a builder is free.

### 1.1: run in production pipelines

Theme: the owner's 1.0 goal is "use in production pipelines". Most pipelines read and write cloud
storage and need a failed run to restart without redoing finished tables.

| Row or item | Group | What is left | Slices |
|---|---|---|---|
| 64 CLI-CLOUD | [connect](groups/connect.md) | EC2b to EC5, REL-C, CC1 to CC5 | about 9 |
| 85 F23 resume, CLI half | [run](groups/run.md) | engine release, then C0, C1, C2a, C2b, C3 | 5 |
| 41 L5a-cli progress | [library](groups/library.md) | one slice, plan passed | 1 |
| PER-COLUMN-ROUTING, SEAM-REASONS | [run](groups/run.md) | not planned | about 3 |
| 82-E3b (fill) | [connect](groups/connect.md) | port #684 | 1 |
| INTL-IDS.1 (fill) | [mask](groups/mask.md) | merge #671 | 1 |

Other fill: job-outcome notifications ([run](groups/run.md)); the corrective-backlog minors on chunked
progress events and the subset signal in `decoy.mask()` and `decoy tokenize`.

Depends on: 1.0 rows 61 (CLI delivery) and 59 (F22).

### 1.2: generate completeness and identifiers

Theme: synthetic and masked data that looks like the business, in more countries.

| Row or item | Group | What is left | Slices |
|---|---|---|---|
| 24r GEN-INHERIT | [generate](groups/generate.md) | plan passed; build | about 3 |
| 24n GEN-REL, Later part | [generate](groups/generate.md) | parent-anchored date windows, per-parent aggregates, self-reference as a hierarchy | about 3 |
| RUST-DATE-TEXT | [mask](groups/mask.md) | not planned | about 3 |
| INTL-IDS.2, INTL-IDS.3 | [mask](groups/mask.md) | port; INTL-IDS.3 after owner decision 3 | 2 |
| EDGE-CASES.1 | [generate](groups/generate.md) | port | 1 |

Fill: the generate candidates for per-provider options and `unique`, and HC5-FIT-CLI; the
corrective-backlog minors on `condition_on` with a renamed parent, number-type inference for computed
columns, and `unique_together` on a subset of a composite key.

Depends on: the 1.0 part of row 24n; INTL-IDS.1 (1.1).

### 1.3: more ways to install

Theme: reach. The container image and PyPI are the two ways a pipeline gets Decoy other than the
signed download. L3b and L5b ride here because their plans ask for three OS lanes, which exist once the
1.0 Windows runner (row 6) is in place.

| Row or candidate | Group | What is left | Slices |
|---|---|---|---|
| 90a REL-IMAGE | [release](groups/release.md) | needs a plan | about 3 |
| PIP-NATIVE-EXTRA, PYPI, PY-VERSIONS | [release](groups/release.md) | publish on PyPI with companion wheels; add Python 3.13 | about 3 |
| 38 L3b-cli, 42 L5b-cli | [library](groups/library.md) | plans passed | 2 |
| CHUNK-PARALLEL | [run](groups/run.md) | not planned (owner tag 1.3, 2026-11-19) | about 5 |

L3b and L5b depend on how the release gate settles the `decoy library` commands (row EXPERIMENTAL-TIER).
CHUNK-PARALLEL is the only engine work in this minor. #321 had none; the owner tagged it 1.3 a day later.

### 1.4: more sources and formats

Theme: read from where the data is, in the format it is in.

| Row or item | Group | What is left | Slices |
|---|---|---|---|
| 64b CLI-DB-SRC | [connect](groups/connect.md) | not started; includes a Postgres CI lane | about 5 |
| 87 F02 | [connect](groups/connect.md) | E2 to E5, release, C1 to C4 | about 9 |
| AVRO-ORC.1 | [connect](groups/connect.md) | port, code review, compatibility check | 2 |
| AVRO-ORC.2 | [connect](groups/connect.md) | plan and build the CLI half | about 2 |

Fill: SQL filters on sources, SFTP host-key pinning, subset from non-Parquet sources; the
corrective-backlog minor on one engine retry choke point (F02's retry executor is the same work).

Depends on: 1.1 (CLI-CLOUD, for F02).

### 1.5: policy, secrets and masking options

Theme: governance. A security team states rules once, keeps secrets in its own vault, rotates token
domains, and picks masks that keep the parts of a value a test needs (an email domain, a card BIN, a
subnet, the intervals between one patient's dates).

| Row or item | Group | What is left | Slices |
|---|---|---|---|
| 81 F16, with 24zt | [mask](groups/mask.md) | E2b (engine #642), E1, E3, release, C1, C2 | 5 |
| 83 F13 external adapters | [mask](groups/mask.md) | not started | about 4 |
| 79 F09, Later part | [mask](groups/mask.md) | domain-version object, rotation, remap | about 4 |
| MASK-KEEP.1 to .3 | [mask](groups/mask.md) | port as one lane | about 4 |
| DATE-ENTITY.1 | [mask](groups/mask.md) | port and re-review | about 3 |

This minor is the largest. If it does not fit the budget, DATE-ENTITY.1 moves to 1.6 as fill.

Fill: F17 portable disguise bundles.

Depends on: the 1.0 part of row 79 (the vault header). The vault format is fixed for the life of 1.x.

### 1.6: scan baselines and drift

| Row | Group | What is left | Slices |
|---|---|---|---|
| 30 SCAN-LIB | [scan](groups/scan.md) | the run-evidence hash | 1 |
| 32 DRIFT | [scan](groups/scan.md) | not started | about 3 |
| 31 DIST-INTEGRITY | [scan](groups/scan.md) | DI-2 and the CLI half | about 3 |
| 80 F15 | [scan](groups/scan.md) | the slices after E2 and the CLI half | about 3 |

Fill: DETECT-PROFILES, X-09, trend and drift analytics, the detector set version field.

Depends on: 1.0 rows 29 and 36.

### 1.7: quality contracts and privacy risk

Theme: say what "good output" and "safe enough to share" mean, and have the run check both.

| Row or item | Group | What is left | Slices |
|---|---|---|---|
| 69 F35 | [trust](groups/trust.md) | E1a onward, plan rev 4 GO | about 4 |
| 68 F36 | [trust](groups/trust.md) | finish, entry slices, slice 4 registry; plan rev 8 GO | about 5 |
| ANON.1 to ANON.6 | [trust](groups/trust.md) | review and port (or land dark earlier) | about 6 |
| ANON.7 to ANON.9 | [trust](groups/trust.md) | plan and build the config, planner, evidence and CLI wiring | about 3 to 5 |

F35 goes first, and before F32 in 1.8 (owner Q5, 2026-11-08). The anonymity stack is the delivery of F37
(post-mask privacy risk) and X-12.

Fill: F12 customer regression suites; the generate candidate F46.

### 1.8: evidence you can hand to an auditor

| Row | Group | What is left | Slices |
|---|---|---|---|
| 72 F33 | [trust](groups/trust.md) | C1a, C1b, the release slice | 3 |
| 78 F10 | [trust](groups/trust.md) | release and repin, then 78-C1 | 2 |
| 70 F32 remainder | [trust](groups/trust.md) | E1b to E3, C0, C1, C1b | 6 |

Fill: a Parquet support bundle; F39 OpenLineage export. Depends on: F32 E1b on F35 E1a (1.7).

### 1.9: nested data and application-ready databases

| Row or item | Group | What is left | Slices |
|---|---|---|---|
| 82 F07 | [connect](groups/connect.md) | E2b, E4a, E4b, E5 (E3b lands in 1.1) | 4 |
| NESTED-NATIVE | [connect](groups/connect.md) | plan with row 82; first the fail-closed check | about 3 |
| 86 F01 | [connect](groups/connect.md) | owner decision 4, then E1 onward | about 7 |

Fill: X-02 if F07 lands early. Depends on: 1.4 (64b, the Postgres CI lane).

### 1.10: joint-distribution synthesis

Theme: synthetic tables that keep the correlations between columns.

| Item | Group | What is left | Slices |
|---|---|---|---|
| COPULA.1 to COPULA.3 | [generate](groups/generate.md) | review, port and merge (or land dark earlier) | about 3 |
| COPULA.6 | [generate](groups/generate.md) | plan and build config and CLI wiring | not sized |
| COPULA.4, COPULA.5 | [generate](groups/generate.md) | after owner decisions 5 and 2 | not sized |

Fill: F48 statistical synthesis; the certified DP stack candidate if COPULA.5 is built.

### 1.11: warehouses and more databases

| Item | Group | What is left | Slices |
|---|---|---|---|
| WAREHOUSE.1 | [connect](groups/connect.md) | fresh plan for DuckDB attach and multi-part Parquet | not sized |
| WAREHOUSE.3 | platform docs | merge the DuckDB plans as docs (input to WAREHOUSE.1) | 0 (docs) |
| WAREHOUSE.2 | [platform-parked](platform-parked.md) | with the platform restart | not sized |

Fill: X-06 connectors, DuckDB 12 (write-back) and 13 (SQL source filters).

### The pool (after 1.11)

Every other candidate waits here. Pick each next theme on evidence: a user asked, it unblocks other
rows, or it is cheap next to work in flight.

| Theme | Candidates | Groups |
|---|---|---|
| Larger-than-memory runs | VAULT-STREAM, TOKENIZE-CHUNKED, OOC-QUARANTINE, OOC-DATE-BUCKET, FK-CHUNKED-HASH-CHILD, route-coverage phase 2, chunk-level resume, multi-hop FK chains, FK cycles, bounded reorder, nested relationships out of core, the mixed-job deferrals, F05, F42 | [mask](groups/mask.md), [run](groups/run.md), [connect](groups/connect.md) |
| File formats | X-02 to X-05, F03 | [connect](groups/connect.md) |
| Streams | X-07 | [run](groups/run.md) |
| Masks and detectors | the rest of X-08 (region disguises, detectors), the rest of X-10 and X-13, F47, F50, cross-job joinable masking, `when:` hashing of number columns, the secondary Faker sources, `windowed_date` range, the Faker pool snapshot, value-based FK discovery | [mask](groups/mask.md), [scan](groups/scan.md) |
| Synthesis | X-15 to X-18 (the built part of X-17 is EDGE-CASES.1), dirty output on the mixed route, generate columns on a masked table | [generate](groups/generate.md) |
| Authoring tools | F18, F19, F41; sample preview and dry run | [config](groups/config.md), [run](groups/run.md) |
| Integrations and extension | F49, F40 and X-25 (the plugin SDK), SEAM-EXPLAIN | [connect](groups/connect.md), [mask](groups/mask.md), [run](groups/run.md) |
| Documents and media | X-19 to X-24 | [mask](groups/mask.md), [connect](groups/connect.md) |
| Local library | the user-level store, the local catalog | [library](groups/library.md) |

The plugin SDK builds on custom providers and the connector SDK, which 1.0 labels experimental (row
EXPERIMENTAL-TIER). A 1.x minor may reshape that surface.

### 2.0

2.0 is not a feature release. The 1.0 rows that settle every known break before the freeze are 24zi,
24zj, 24zk, FREEZE-SURFACE, FREEZE-OUTPUT, FAKER-MIGRATE and EXPERIMENTAL-TIER. The items that are 1.x
only if built a named way, and the surfaces fixed for the life of 1.x, are in
[2.0-holding.md](2.0-holding.md). This page added HC1-CORPORA and WIDE-SIGNATURES there (carried from
#321). In this program, only INTL-IDS.3 as built and COPULA.4 built in place would be 2.0.

## The upgrade path

`decoy upgrade` swaps the whole managed runtime (CLI and its pinned engine) to a newer signed bundle,
keeps the old one on disk, and can go back with `decoy upgrade --version`. Every 1.x release must keep:

| Keep | Rule | Where it is stated |
|---|---|---|
| Config schema additive only | A config valid in 1.x loads and gives the same result in every later 1.x. New keys are optional. | [post-1.0-plan.md](post-1.0-plan.md); `E:docs/compatibility-contract.md` sections 3.4 and 4.1 |
| Exit codes and reason strings stable | An exit code keeps its meaning. The reason registry is append-only. | [post-1.0-plan.md](post-1.0-plan.md); [2.0-holding.md](2.0-holding.md) |
| Report tags versioned | A new report shape is a new tag. A reader for every tag 1.0 writes stays. | `E:docs/compatibility-contract.md` sections 3.1 and 4.2 |
| The engine compatibility contract | Artifact formats, the vault, determinism and Faker data within a major, the public API, disguises. | `E:docs/compatibility-contract.md` sections 3, 4 and 8 |

Three points these rules do not cover yet (found 2026-11-18 by #321):

1. **Going back must be safe.** A newer minor may write a new artifact version (a library record, a
   resume store, a scan set, a risk-utility report). Write it only when the new feature is used, and
   make an older 1.x refuse an unknown version with a coded reason.
2. **Later engine code already on main ships in 1.0.** Engine slices of 1.x rows that merge before the
   freeze (F16 E2a, F23 E1 and E2, F10 E1 and E2) are in the engine that 1.0 pins. Each must stay
   unreachable from the frozen surface, or be added to the frozen surface map on purpose at REL-GATE
   (row 93). Dark landing (owner decision 6) is the same case after 1.0.
3. **The local record library is a stored format.** 1.0 freezes the record layout under `.decoy/` (row
   37). Later minors add record kinds and never change an existing one.

The update channel point from #321 is now 1.0 row UPGRADE-KEY ([release](groups/release.md)).

## Corrective backlog by bucket and theme

The vault file `handoffs/V2-CORRECTIVE-BACKLOG.md` holds the corrective backlog. Counts are in
[post-1.0-plan.md](post-1.0-plan.md). This page does not copy the entries. It says where each theme goes
when it is triaged.

| Bucket | Themes | Goes to |
|---|---|---|
| 1.x minor (17) | generate options (renamed parent with `condition_on`, number-type inference, `unique_together`) | 1.2 fill |
| | run and observability (chunked progress events, `RouteSummary` and cap contract exports, a public subset guard, the subset signal in `decoy.mask()` and `tokenize`) | 1.1 fill |
| | connectors (one retry choke point, a readable-sink protocol for wrapper sinks) | 1.4 fill |
| | scan and post-scan (multi-table drift baseline, all-null key columns, gate memory pressure read as out of memory) | 1.6 fill |
| | library and layout (writer sentry edge cases, fsck repair of special files, hard-link-aware layout identity) | 1.3 fill (L3b, L5b) |
| | web client `default_by` | [platform-parked.md](platform-parked.md) |
| either | new refusals and changed reason strings | 1.x if they only warn or add a reason beside the old one, in the minor that touches the code; listed as a class in [2.0-holding.md](2.0-holding.md) |
| patch | review notes from POSTSCAN, DUP-FREEZE, F21, F22, H-1, CLI-CLOUD, SUB-RUN, LIB, the Rust companion audit, distribution-model QA, CI and tooling | 1.0.x patches, by theme |
| V1 (16) | entries that say they stay V1 | check each against the three 1.0 tests; a live one becomes a 1.0 row, else it is 1.x |
| check (10) | owner questions and missing facts | inbox at the next triage |

## Not verified

- No branch was tested or built against current main. Branches with no PR have no recent CI: MASK-KEEP,
  AVRO-ORC.1 and DATE-ENTITY.1 have no CI run at all; INTL-IDS.2, INTL-IDS.3 and EDGE-CASES.1 only runs
  from 2026-11-06 and 2026-11-07.
- CI on the anonymity and copula PRs ran against old bases. It says nothing about a merge with current
  main.
- Whether any folded plan-review finding is still open. No plan in the anonymity or copula stacks
  records a final GO.
- Whether new reason codes and strategy names fit the frozen-surface rules without a registry bump.
- Whether INTL-IDS.3 keeps data output byte-identical (the plan says so; not checked).
- The cause of the #684 aarch64 wheel failure.
- #333 against main line by line, and the review state of each of the 17 DuckDB plans.
- Slice counts for unbuilt items (AVRO-ORC.2, ANON.7 to ANON.9, COPULA.4 to COPULA.6, WAREHOUSE) are
  estimates or not given.
