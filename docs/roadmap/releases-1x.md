# 1.x program and release schedule

Status: plan

Part of the roadmap: [ROADMAP.md](../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

Rules consulted: dev-rules `00-universal.md`, `development-loop.md` (PLAN), `scope-discipline.md`,
`proportionality.md`, `api-and-compatibility.md`, `release-and-rollback.md`, `documentation.md`.

Owner decision, 2026-11-22: all work that was built or planned on a branch under the labels "V1+" or
"V2" is now 1.x work. This page sorts that work into categories. It puts each category into a 1.x
release. It says what each item needs before it lands, so that no built work is lost.

This page also carries forward the 1.1 to 1.9 order from CLI PR #321 (branch
`docs/roadmap-1x-schedule`). The order is updated to the roadmap as it is on 2026-11-22. This page
replaces #321, which is closed.

Owner rule, 2026-11-22: a common use case does not wait for 2.0 when it could ship in V1. A separate
evaluation is under way (vault `V2-TO-V1-EVALUATION-2026-11-22.md`). This page does not move items into
1.0, except INTL-IDS.3 ([Decided 2026-11-22](#decided-2026-11-22), decision 3).

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
7. [Decided 2026-11-22](#decided-2026-11-22)
8. [Cleanup for the orchestrator](#cleanup-for-the-orchestrator)
9. [Release schedule](#release-schedule)
10. [The upgrade path](#the-upgrade-path)
11. [Corrective backlog by bucket and theme](#corrective-backlog-by-bucket-and-theme)
12. [Not verified](#not-verified)

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

One named exception: INTL-IDS.3 (Faker locale capability rows) lands before the 1.0 freeze, together
with row FAKER-MIGRATE (decision 3). FAKER-MIGRATE already regenerates the determinism goldens. If
INTL-IDS.3 lands in the same act, the capability rows and run-metadata hashes change once, before
they are frozen.

After 1.0.0, each item goes through the normal dev loop ([working-rules.md](working-rules.md)): a plan
review where the plan has no recorded GO, the port or rebase, the gates, then the merge. An item that
changes a default, an output, a run-metadata hash or a frozen surface needs an owner decision first.
The decisions made so far are in [Decided 2026-11-22](#decided-2026-11-22).

**Dark landing (allowed after 1.0.0, decision 6).** An item that is a library only (no config key, CLI
flag, reachable reason code or report tag) may merge after 1.0.0 and before its release slot. It ships
in the next engine release, but no config can reach it. Before it merges, its new package or names are
marked private or experimental (row EXPERIMENTAL-TIER), so they are not frozen by accident. They stay so
until the release that wires them. This keeps built branches from drifting further from main. The
items that can land dark are marked "yes" in the Dark column of the tables below.

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
| V2-4.1 (snapshot extension) | not built; not needed (decision 5) | none | COPULA.4 |
| V2-4.5 or DPS-4 (DP on the joint model) | not built | none | COPULA.5 |
| (no old name) copula config and CLI wiring | not built | none | COPULA.6 |
| V2-5.4 | `feat/v2-5.4-edge-case-providers` | none | EDGE-CASES.1 |
| F07 82-E3b | `feat/f07-e3b` | #684 (draft) | 82-E3b (row 82) |
| native nested column masking | CLI `docs/roadmap-native-nested-mask` | CLI #385 (closed, folded into #386) | NESTED-NATIVE |
| F01 E0 | `feat/f01-e0` | #667 (draft) | 86-E0 (row 86) |
| V2 warehouse, engine half | `claude/v2-warehouse-sources-and-tokenization-vault` | none | WAREHOUSE.1 |
| V2 warehouse, platform half | platform `claude/v2-warehouse-sources-and-tokenization-vault` | none | WAREHOUSE.2 |
| DuckDB plans | platform `plan/v2-duckdb-plans` | none | WAREHOUSE.3 |

Each built item had a plan branch (`plan/v1plus-*`, `plan/v2-*`). The feat branch carries the same
plan at a later revision. Fourteen plan branches are deleted. Two are kept because they hold commits
their feat branches lack ([Cleanup](#cleanup-for-the-orchestrator)).

## Categories and releases

| Category | 1.x ids | Group file | Release | Expansion candidate |
|---|---|---|---|---|
| Identifiers and generators | INTL-IDS.1 to .3, EDGE-CASES.1 | [mask](groups/mask.md), [generate](groups/generate.md) | 1.0 (INTL-IDS.3, with FAKER-MIGRATE), 1.1 (INTL-IDS.1), 1.2 (INTL-IDS.2, EDGE-CASES.1) | X-08, X-17 |
| Masking options | MASK-KEEP.1 to .3, DATE-ENTITY.1 | [mask](groups/mask.md) | 1.7 | X-10, X-13 |
| Formats and sources | AVRO-ORC.1, .2 | [connect](groups/connect.md) | 1.4 | X-01 |
| Anonymity and privacy | ANON.1 to .9 | [trust](groups/trust.md) | 1.9 | X-12, F37 |
| Nested data | 82-E3b, NESTED-NATIVE | [connect](groups/connect.md) | 1.0 (NESTED-FREEZE, the refusal half), 1.1 (82-E3b), 1.11 (NESTED-NATIVE) | X-02, F07 |
| Joint-distribution generation | COPULA.1 to .6 | [generate](groups/generate.md) | 1.6 | X-14, F48 |
| Connectors and warehouse | 86-E0, WAREHOUSE.1 to .3 | [connect](groups/connect.md), [platform-parked](platform-parked.md) | 1.5 (WAREHOUSE.1, .3, with DB-NEXT and SNOWFLAKE), 1.11 (86-E0) | X-06, DuckDB 11 to 13 |

Why these slots:

- Each category joins the #321 release whose theme it fits: identifiers with generate completeness
  (1.2), Avro and ORC with file sources (1.4), masking options with policy (1.7), anonymity with quality
  contracts (1.9, where #321 already had F37 and X-12 as fill). The numbers are after the reorder of
  2026-11-22 ([Release schedule](#release-schedule)).
- INTL-IDS.1 needs only a clean merge of main and is small, so it is fill in 1.1. 82-E3b is held "until 1.1" by the
  owner decision of 2026-11-21 ([decisions.md](decisions.md)), so it is fill in 1.1 too.
- The copula and warehouse work has no #321 release that fits. Each gets a new minor. The owner moved
  both early on 2026-11-22: the databases and warehouse release is 1.5 and the copula is 1.6.
- INTL-IDS.3 is in 1.0, with FAKER-MIGRATE (decision 3). It is the only built item of this program in
  1.0. The refusal half of NESTED-NATIVE is in 1.0 too, as row NESTED-FREEZE (b) (decision 7).
- The library-only parts of anonymity and copula can land dark after 1.0.0 and before their release
  (decision 6).

## Items

State is one of: "built, merge as-is", "built, merge main and review" (a clean merge of main, then the
review the branch has not had), "built, port to current main" (rebase or re-apply on main and fix
conflicts), "re-plan, old branch as reference" (main moved too far; write a fresh plan that reuses the
branch), or "not built". "PWC" is PASS WITH CONCERNS. Ahead and behind are commits against engine main.
Size is added lines, source / tests, against the merge base.

### Identifiers and generators

| Id | Branch, PR | State | Conflicts | Plan and code review | Size | Dark |
|---|---|---|---|---|---|---|
| INTL-IDS.1 | `feat/v1plus-p2.1-check-digit-schemes`, #671; 9 ahead, 93 behind | built, merge main and review | 0 | plan rev 2 PWC; code review round 2 PWC. Visible CI green; ruff, mypy, regression, layers and prove-regression were skipped (draft), so their result is unknown | 177 / 334; S, 1 slice | yes |
| INTL-IDS.2 | `feat/v1plus-p2.3-national-id-generators`, no PR; 10 ahead, 331 behind | built, port to current main | 5 files, 1 source (`execution/native/_draw_sites_provider_backed.py`); the rest are generated or ledger files | plan rev 2 PWC; code review PWC (4 P2 handled). Last CI 2026-11-06 | 617 / 658 (includes old INTL-IDS.1 commits); S | no (new providers a config can name) |
| INTL-IDS.3 | `feat/v1plus-p2.4-faker-locales`, no PR; 4 ahead, 331 behind | built, port to current main; lands in 1.0 with FAKER-MIGRATE (decision 3) | 3 files, no source | plan rev 3; code review not recorded in the inventory | 354 / 336; S | no (lands in 1.0) |
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

1. INTL-IDS.3 (1.0, before the freeze): port onto the FAKER-MIGRATE S2 head. Regenerate the locale
   table against the Faker release that 1.0 ships (FAKER-MIGRATE moves 1.0 to Faker 40.31; the branch
   table is for 40.23.0). The inbox item of 2026-11-18 (it_IT `address_city` not deterministic across
   processes) bears on which locales the table may list. Move the CHANGELOG entry to `changelog.d`. Run
   a code review (none is recorded), then the gates. Merge with FAKER-MIGRATE S2 or right after it,
   before row 93.
2. INTL-IDS.1 (after 1.0.0): merge main into #671 (93 behind). Run the gates that the draft skipped:
   ruff, mypy, regression, layers and prove-regression. Check that a config that names a new scheme
   under FPE checksum mode gets the same reason code as today (`plan/_checks.py` reads
   `_KNOWN_SCHEMES`). Mark the nine new scheme names experimental (row EXPERIMENTAL-TIER) if it lands
   dark before 1.1. Then the Dennis and Codex gate, then the full gate, then merge.
3. INTL-IDS.2: rebase onto the INTL-IDS.1 head (`53db68113` fixes the calculator-fault path), regenerate
   the proof manifest and the draw-site catalog pins, move the CHANGELOG entry to `changelog.d`.
4. EDGE-CASES.1: rebase after INTL-IDS.2, regenerate the same catalog pins and move the CHANGELOG entry
   to `changelog.d`. Then the cross-model gate and the full suite, which were not run.

INTL-IDS.1 and the 1.0 row FPE-CHECKSUM-NATIVE both touch `transforms/_fpe_checksum.py`. Whichever
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
2. MASK-KEEP.1: its first CI run (the branch has never had one).
3. MASK-KEEP.3: a re-review after the P1 fix (none is recorded). Check that the residual-PII verifier
   output does not change for configs that do not use `ip_prefix`.
4. DATE-ENTITY.1: port, re-run against the current chunked and multi-table routes, then the re-review
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
| ANON.1 | `feat/v2-3.1-generalization-hierarchies`, #672; 10 ahead, 93 behind | built, merge main and review | 0 | plan rev 2: review rev 1 FAIL (1 P1), re-review FAIL (1 P1), findings folded in at the coordinator's instruction. No GO recorded | 1162 / 1323; S | yes |
| ANON.2 | `feat/v2-3.2-anonymity-metrics`, #673; 27 ahead | built, merge main and review | 0 | plan rev 3: review FAIL (2 P1, 8 P2), re-check FAIL (2 P1, 2 P2), folded in. No GO recorded. The plan links a stale CLI branch | 2290 / 2676; S | yes |
| ANON.3 | `feat/v2-3.3a-anonymity-models`, #687; 32 ahead | built, port to current main | 2: `.importlinter`, `tests/sentry/layout/test_import_layers.py` | V2-3.3 plan rev 3: review rev 1 PWC (3 P1, 5 P2), folded in. No GO for this half | 2752 / 3063; S to M | yes |
| ANON.4 | `feat/v2-3.3-enforcement-search`, #689; 41 ahead | built, port to current main | the same 2 (from ANON.3) | plan rev 3; code-review gaps fixed in `5b339739`. No GO text found | 3546 / 4783; M | yes |
| ANON.5 | `feat/v2-3.4-microaggregation`, #690; 45 ahead | built, port to current main | the same 2 | plan header says "revision 1 (awaiting plan review)" but a code-review fix commit exists (2026-11-07); header is stale. No plan GO | 4049 / 5574; S | yes |
| ANON.6 | `feat/v2-3.5-risk-utility-report`, #694; 54 ahead | built, port to current main without the freeze edits (decision 1) | 5: `.importlinter`, `docs/frozen-surfaces.md`, `compat_corpus/regenerate.py`, `compat_corpus/test_compat_corpus.py`, `test_import_layers.py`. The port drops the edits to the last three, so 2 are left | plan rev 4: review rev 1 PWC (1 P1, 5 P2); code review record 2026-11-12. No GO | 4790 / 7515; M | yes, once the freeze edits are dropped |
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
config can reach them. The public names `decoy_engine.anonymize` and `quality.anonymity` need the
EXPERIMENTAL-TIER marking before any of them lands dark.

Landing steps:

1. A fresh plan review for ANON.1 to ANON.6, since no plan records a GO. Check that each folded finding
   is closed. Fix the stale CLI-branch links in the ANON.2 plan and the stale header in the ANON.5 plan.
2. Merge main into ANON.1, then ANON.2 (both clean). Re-run the layer sentry. Review each.
3. Mark `decoy_engine.anonymize` and `quality.anonymity` private or experimental (row EXPERIMENTAL-TIER)
   before the first item lands dark.
4. Fix the two layer-contract conflicts once at ANON.3 (register `_value_family` in the bottom tier of
   main's current contract) and carry the fix up the stack. This is cheaper than a fix per branch.
5. ANON.4: re-capture the dark golden literals against current main.
6. ANON.5, then ANON.6. The ANON.6 port drops its edits to `docs/frozen-surfaces.md`, the compatibility
   contract and the compat corpus, so ANON.6 lands dark and `risk-utility-report/v1` is not frozen yet.
7. Plan and build ANON.7, ANON.8 and ANON.9 for release 1.9. The release that ships ANON.9 (the first use
   a user can reach) freezes `risk-utility-report/v1`: it adds the tag to `docs/frozen-surfaces.md` and
   the compatibility contract (contract 3.1), and captures the compat corpus for it (decision 1).

### Nested data

| Id | Branch, PR | State | Conflicts | Plan and code review | Size | Dark |
|---|---|---|---|---|---|---|
| 82-E3b | `feat/f07-e3b`, #684; 20 ahead, 14 behind | built, port to current main | 5 files, 3 source (plan checks moved on main) | plan `E:plan/f07-path-discovery` rev 3; Dennis rounds 1 and 2 fixed; Codex round 3 no 1.0 findings. CI: one failure (companion wheel, Linux 3.11 aarch64), cause not read | 2202 / 1307; S | no (new `rules` key) |
| NESTED-NATIVE | none (candidate from CLI #385) | not built | n/a | no plan | not sized | no |

82-E3b lets a `nested` column carry `provider_config.rules`, a list of `{target, strategy,
strategy_config, namespace?}`. The single-rule form does not change. NESTED-NATIVE is masking fields
inside native Parquet and Arrow struct, list and map columns (`address.street`, `tags[*]`). Today such a
column can only pass through or be dropped. Its first step, from #385, was to confirm and test that a
native struct, list or map column fails closed. That refusal half is now 1.0 row NESTED-FREEZE (b) in
[connect](groups/connect.md) (decision 7). NESTED-NATIVE keeps the masking half, in 1.x.

Landing steps: merge main into #684, fix the 5 conflicts, re-run CI (read the aarch64 failure), merge in
1.1. Before the merge, check that every `target` in the branch fits the closed path subset of 1.0 row
NESTED-FREEZE (a). NESTED-NATIVE needs a plan; it uses the same path selector as X-02 and F07, so plan it with the rest
of row 82 for 1.11.

### Joint-distribution generation

A second stack: main, COPULA.1 (#703), COPULA.2 (#705). COPULA.3 was built on an older copula state
(merge base with #705 is `7a43b04c`) and must be rebased onto the COPULA.2 head.

| Id | Branch, PR | State | Conflicts | Plan and code review | Size | Dark |
|---|---|---|---|---|---|---|
| COPULA.1 | `feat/v2-4.2-copula-foundations`, #703; 6 ahead, 73 behind | built, merge main and review | 0 | plan `plan/v2-4.2-4.3-gaussian-copula` rev 3: review 1 GATE FAIL (4 P1), re-check GATE FAIL (3 P1), orchestrator decisions folded in. No GO | 905 / 5115; S | yes |
| COPULA.2 | `feat/v2-4.2-4.3-gaussian-copula`, #705; 24 ahead | built, port to current main | 2, both list appends (`scripts/dev/sentry_registry.toml`, `tests/sentry/secret_material_census.json`); keep both sides | same plan | 1656 / 6645 (cumulative); S | yes |
| COPULA.3 | `feat/v2-4.4-copula-quality-report`, no PR; 20 ahead, 329 behind | built, port to current main | 3 (`CODEMAP.md`, `docs/methodology-registry.yaml`, the census file), plus the rebase onto COPULA.2 | plan rev 2 (rev 1 FAIL: 2 P1, 6 P2, 3 P3); code review round 1 and re-review recorded 2026-11-08 | 2686 / 8153 cumulative; about 4 quality modules of its own; M | yes |
| COPULA.4 | not built (V2-4.1) | not needed: standalone model kept (decision 5) | n/a | none; `distribution-snapshot/v1` does not change | n/a | n/a |
| COPULA.5 | not built (V2-4.5 or DPS-4) | not built | n/a | route chosen at the COPULA.5 plan, after a survey (decision 2) | not sized | no |
| COPULA.6 | not built | not built | n/a | no plan. The copula plan adds no config key and no strategy, so a config cannot reach the copula until this is planned | not sized | no |

What it does. COPULA.1: the copula model object, disclosure floors, nearest-correlation fix and normal
numerics. COPULA.2: `fit_gaussian_copula` (marginals from a caller's snapshot, correlation from the
frame) and `sample_gaussian_copula`, with categorical, null-as-state and mixed columns, and seed-wipe
discipline. It adds exactly the two `seed` census rows the owner approved on 2026-11-19. COPULA.3: a
value-free quality report for copula output (marginal fit, pairwise correlation and contingency
similarity, distance to closest record), with every real-data statistic passing the disclosure floors.
The public name `generation.copula` needs the EXPERIMENTAL-TIER marking before COPULA.1 lands dark.

Landing steps:

1. A fresh plan review for COPULA.1 and COPULA.2 (no GO recorded).
2. Mark `generation.copula` private or experimental (row EXPERIMENTAL-TIER).
3. Merge main into COPULA.1 (clean); review; merge.
4. COPULA.2: resolve the two append conflicts, re-run the census sentry and confirm exactly two new
   rows, send the mutation table to the owner as the 2026-11-19 reply asks.
5. COPULA.3: rebase onto the COPULA.2 head, drop its two seed census rows with empty reasons (they
   duplicate the approved rows), move the CHANGELOG entry to `changelog.d`, re-capture
   `tests/unit/generation/copula/quality/_dark_golden.json`, fix the plan's stack line, open the PR,
   review.
6. Plan COPULA.5 (survey of established tools first; the DP route is chosen in that plan) and COPULA.6
   for release 1.6. COPULA.4 is not needed (decision 5).

### Connectors and warehouse

| Id | Branch, PR | State | Conflicts | Plan and code review | Size | Dark |
|---|---|---|---|---|---|---|
| 86-E0 | `feat/f01-e0`, #667; 9 ahead, 94 behind | built; a record, not a feature | 0 | spike against plan `docs/plans/2026-11-17-f01-postgres-target.md` rev 3. pg-gate: 71 pass, 4 fail. Cell e fails on all four statement paths: a real negative result (DuckDB `interrupt()` does not cancel the server statement). It needs an expected-fail marker. Fallback cell e2 passes | 1 / 510, record 37 lines | n/a |
| WAREHOUSE.1 | engine `claude/v2-warehouse-sources-and-tokenization-vault`, no PR; 11 ahead, 467 behind | re-plan, old branch as reference | 9 files, 7 source (`_tokenize.py`, `_pipeline.py`, adapters, `connectors/postgres_snapshot.py`, draw-site inventory) | no plan review found | 1365 / 1732 including the tokenize part; L | no |
| WAREHOUSE.2 | platform `claude/v2-warehouse-sources-and-tokenization-vault`, no PR; 22 ahead, 312 behind | re-plan, old branch as reference; parked with the platform | 36 files, nearly all in the vault | none found | about 3.5k added lines outside the vault | no |
| WAREHOUSE.3 | platform `plan/v2-duckdb-plans`, no PR; 32 ahead, 59 behind | built (docs), merge as-is | 0 | 17 plan drafts, an audit and a master note; review state per plan not checked | 5353 doc lines | n/a |

86-E0 tests the F01 Postgres write design. Cell e: `interrupt()` on the DuckDB connection does not cancel
a running `postgres_query` or `postgres_execute` and does not stop a connect. Cell e2 shows that
`pg_cancel_backend(pid)` from a second session works, and cell h shows that `PGCONNECT_TIMEOUT` bounds a
connect. Q15 is decided (decision 4): F01 uses a watchdog session with `pg_cancel_backend`, plus
`statement_timeout`, `lock_timeout` and `PGCONNECT_TIMEOUT`.

WAREHOUSE.1 holds the DuckDB attach core, the catalog browser and the DuckDB-file source
(`connectors/duckdb_attach/`), the multi-part Parquet export reader (`connectors/parquet_dataset.py`) and
a warehouse export fidelity record. It also holds the `tokenize` strategy and `token_vault_writer`,
which main now has in another form (B-6). WAREHOUSE.2 holds the platform DuckDB sources (fence, file
provider, catalog endpoint, `/from-database` route, source picker, multi-part staging, a guide) and the
vault work, which main has as B-6. None of the DuckDB or warehouse parts exist on main.

Landing steps:

1. 86-E0: mark cell e expected-fail (it records that DuckDB `interrupt()` does not cancel the server
   statement), then merge #667 as a record (decision 4). F01 (row 86) is 1.x, planned for 1.11 (1.9 before the reorder) with the
   watchdog design.
2. WAREHOUSE.3: merge as docs whenever a platform docs merge is allowed. It is the input to the plans.
3. WAREHOUSE.1 (release 1.5, with DB-NEXT and SNOWFLAKE): write a fresh plan for the DuckDB attach and the multi-part Parquet reader on the current
   connectors and `fileaccess`, using the branch as reference. Leave out every tokenize and vault commit.
4. WAREHOUSE.2: the same for the platform half, when the platform restarts ([platform-parked.md](platform-parked.md)).

## Flagged items

The rule: additive or opt-in work goes in a 1.x minor. An item that changes a default, existing output,
run-metadata hashes or a frozen surface is flagged here with what it needs.

| Id | What changes | Needs |
|---|---|---|
| INTL-IDS.3 | The capability rows that the cockpit and platform read, the run-metadata hashes, and the error a bad-locale config gets. Data output stays byte-identical per the plan (not checked against the frozen-surface docs) | Decided (decision 3): lands before the 1.0 freeze with FAKER-MIGRATE, so the change happens once, before the freeze |
| ANON.6 | Would add the frozen output tag `risk-utility-report/v1` to `docs/frozen-surfaces.md`, the compatibility contract (contract 3.1) and the compat corpus. Additive, but permanent for 1.x once released | Decided (decision 1): ANON.6 lands dark without these edits; the release that ships ANON.9 freezes the tag |
| AVRO-ORC.1 | Adds a field to the run-result model and new reason codes | A compatibility check, not an owner call: 1.x if the field is optional and absent for other formats, else 2.0 |
| MASK-KEEP.3 | Touches the residual-PII verifier | A check that verifier output does not change for configs without `ip_prefix` |
| EDGE-CASES.1 | Adds providers to the default registry (an exception the owner approved). No existing output changes | Nothing more; noted because the names become reserved |
| COPULA.2 | Adds two `seed` rows to the secret-material census | Already approved by the owner (2026-11-19) |

## Decided 2026-11-22

The owner said "go with recommended on all of it" on 2026-11-22. These are now decisions, recorded in
[decisions.md](decisions.md).

1. **`risk-utility-report/v1` (ANON.6).** Freeze the tag only in the release that ships ANON.9 (the
   first use a user can reach). ANON.6 lands dark without the edits to `docs/frozen-surfaces.md`, the
   compatibility contract and the compat corpus. That release adds them.
2. **Copula DP route (COPULA.5).** Decide at the COPULA.5 plan, after the survey of established tools
   the dev rules ask for. The two routes are DPCopula style (the old V2-4.5 outline: noise on the
   correlation release of this model) and PrivBayes (DPS-4 in
   `E:docs/backlog/dps-dp-synthetic-implementation.md`). COPULA.1 to COPULA.3 do not depend on it.
3. **Faker locales (INTL-IDS.3).** Land it before the 1.0 freeze, together with FAKER-MIGRATE, which
   already regenerates the goldens. This is a named exception to the land rule.
4. **Q15 (#667, row 86 F01).** The F01 publisher bounds a statement with a watchdog session that calls
   `pg_cancel_backend` (cell e2), plus `statement_timeout` and `lock_timeout`, and `PGCONNECT_TIMEOUT`
   for connect (cell h). #667 merges as a record, with cell e marked expected-fail. Row 86 is 1.x (1.9).
5. **Copula snapshot (COPULA.4).** Keep the standalone copula model. `distribution-snapshot/v1` does not
   change, so COPULA.4 is not needed.
6. **Dark landing.** Library-only items (INTL-IDS.1, ANON.1 to ANON.6, COPULA.1 to COPULA.3) may merge
   after 1.0.0 and before their release slot. Their new names are marked private or experimental (row
   EXPERIMENTAL-TIER) until the release that wires them.

The owner then decided on the V2-to-V1 evaluation (vault `V2-TO-V1-EVALUATION-2026-11-22.md`) on the
same day. The rule behind it: a common use case does not wait for 2.0 when it could ship in V1.

7. **New 1.0 rows (evaluation ranks 2 to 4).** NESTED-FREEZE in [connect](groups/connect.md), 2 slices:
   (a) the nested `target` path is limited to a closed RFC 9535 subset, checked at compile; (b) a native
   struct, list or map column with no rule fails with a coded reason. FIT-CODES-TEXT in
   [generate](groups/generate.md), 1 slice: `decoy fit` keeps zero-padded codes such as ZIPs as text.
   NESTED-NATIVE stays 1.x for masking inside native nested columns.
8. **The 3 standby items are 1.x, not 1.0.** FIT-DATE-SHAPE (backlog M3) and FIDELITY-ONE-INFERENCE
   (backlog M5) go to 1.2, opt-in through BEHAVIOR-VERSION. TARGET-DUP-REFUSE goes to 1.1 as a warning,
   pending a check: if main (engine #589) still loses data when two tables write to one target, it moves
   to 1.0.
9. **1.x reorder.** 64b moves to 1.1. One more database (DB-NEXT: MySQL or SQL Server) and Snowflake
   come in 1.5, before the copula and anonymity releases. The copula moves from 1.10 to 1.6. One
   behavior-version key (BEHAVIOR-VERSION) for generation, detection and profiling goes in 1.1. The
   other themes keep their order ([Release schedule](#release-schedule)).

## Cleanup for the orchestrator

Done on 2026-11-22:

- Deleted 14 engine plan branches. Each feat branch carries the same plan at a later revision.
- Deleted the merged CLI branches `docs/v1x-v2-classification` (#284) and `docs/v2-vault-streaming-rows`
  (#232).
- Closed engine #333, and CLI #321 (replaced by this page) and #385 (folded into #386).
- Retitled the 11 draft engine PRs (#671, #672, #673, #687, #689, #690, #694, #703, #705, #684, #667)
  with the prefix "1.x". New PRs for this program use the same prefix.

Still to do:

1. Two engine plan branches are kept, because they hold commits that their feat branches lack:
   `plan/v2-3.3-enforcement-search` and `plan/v2-3.5-risk-utility-report`. Fold those commits into the
   feat branch at the ANON.4 and ANON.6 plan review, or keep the branch. Then delete it.
2. Drop the tokenize and vault halves of `claude/v2-warehouse-sources-and-tokenization-vault` (engine and
   platform) when WAREHOUSE.1 and WAREHOUSE.2 are re-planned. Keep the branch as reference until then
   (branch-register marks it HIGH lost-work risk).
3. Update the vault `BRANCH-LIST.md` and the memory note on V1+ and V2 branches to the 1.x ids.
4. Rename `v2-v3-expansion-candidates.md` to `expansion-candidates.md`. Not done here because the archive
   snapshot, the 2026-11-18 handoff and a 2026-11-08 record link to the old name.
5. Platform branch `fix/file-access-authz-v2`: an old plan-doc branch (4 commits, 2026-10-02, plan rev 1
   to 3.1 of `docs/plans/2026-10-02-file-access-authz-engine-platform.md`). Main has the same plan file
   at a later revision, so the branch holds no lost work. It is not part of this program. Delete it with
   the next platform branch cleanup.

Related open PR: CLI #361 adds row STRUCTURE-REVIEW, the end-of-1.x structure review, to the health
group. It is the last 1.x item and merges on its own.

## Release schedule

Carried from #321 and updated to 2026-11-22. Changes from #321: rows 24p, 24q and 24s left 1.2 (24p and
24q became 1.0 rows on 2026-11-19, and 24s closed); row 84 closed; the named speed slots of 2026-11-19
([post-1.0-plan.md](post-1.0-plan.md)) are placed; the seven categories above are slotted; two new
minors (databases and copula) are added; the order changed on 2026-11-22 (see below the table).

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
| 1.0 | (not 1.x) | INTL-IDS.3 lands with FAKER-MIGRATE, before the freeze. The V2-to-V1 cut adds 1.0 rows NESTED-FREEZE and FIT-CODES-TEXT | 4 | yes, the launch engine |
| 1.0.x | Fixes and byte-identical speed | Maintenance rows, patch entries of the corrective backlog; NONFK-OOM part (b) if its plan is not small | 1 to 4 each | only if a fix is in the engine |
| 1.1 | Run in production pipelines | 64, 64b, 85, 41, BEHAVIOR-VERSION, SEAM-REASONS; scope cut: 36, then 29, 32c (opt-in model), LANG-SIDECAR; fill 82-E3b, INTL-IDS.1, TARGET-DUP-REFUSE | about 30 | yes |
| 1.2 | Generate completeness and identifiers | 24r, the Later part of 24n, 24qb, RUST-DATE-TEXT, FIT-DATE-SHAPE, FIDELITY-ONE-INFERENCE, 79b; INTL-IDS.2, EDGE-CASES.1 | about 22 | yes |
| 1.3 | More ways to install | 90a, 38, 42, PIP-NATIVE-EXTRA; candidates PYPI, PY-VERSIONS; CHUNK-PARALLEL; scope cut: 58b, 61b, 74b | about 18 | yes |
| 1.4 | More file sources and formats | 87; AVRO-ORC.1, AVRO-ORC.2 | about 13 | yes |
| 1.5 | More databases and a warehouse | DB-NEXT (MySQL or SQL Server), SNOWFLAKE; WAREHOUSE.1, WAREHOUSE.3 | not sized; needs plans | yes |
| 1.6 | Joint-distribution synthesis | COPULA.1 to COPULA.3, COPULA.5, COPULA.6 (COPULA.4 not needed); candidate F48 | about 10 (COPULA.5 and .6 not sized) | yes |
| 1.7 | Policy, secrets and masking options | 81 with 24zt, 83; MASK-KEEP.1 to .3, DATE-ENTITY.1 | about 16 | yes |
| 1.8 | Scan baselines and drift | 30, 31, 32, 80 | about 12 | yes |
| 1.9 | Quality contracts and privacy risk | 69, 68; ANON.1 to ANON.9 | about 18 | yes |
| 1.10 | Evidence you can hand to an auditor | 72, 78, 70 | about 11 | yes |
| 1.11 | Nested data and application-ready databases | 82, 86 (with 86-E0); NESTED-NATIVE | about 16 | yes |
| later | Chosen from the pool on evidence | see [The pool](#the-pool-after-111) | | |
| 2.0 | Only contract breaks | see [2.0](#20) | | |

Windows (rows 6 and 89) is 1.0, so it is not on this page. The 1.0 line lists only the 1.0 work that
comes from this program or from the V2-to-V1 cut.

The order changed on 2026-11-22 (owner, after the V2-to-V1 evaluation, vault
`V2-TO-V1-EVALUATION-2026-11-22.md`). Database to database is the most common test-data use, so 64b
moves to 1.1, and one more database and Snowflake come before the copula and anonymity releases. The
copula is mostly built, so it moves from 1.10 to 1.6. The other themes keep their order and move down
by the two inserted releases: policy 1.5 to 1.7, scan 1.6 to 1.8, quality and privacy 1.7 to 1.9,
evidence 1.8 to 1.10, nested data and row 86 F01 1.9 to 1.11.

Dependencies after the move:

- 1.1 holds 64b and its Postgres CI lane, which 1.5 (more databases) and 1.11 (86 F01) need.
- 1.1 holds BEHAVIOR-VERSION, which 1.2 (FIT-DATE-SHAPE, FIDELITY-ONE-INFERENCE) needs.
- 1.4 (87 F02) needs 64 CLI-CLOUD from 1.1.
- 1.9 holds F35, which comes before F32 in 1.10 (owner Q5, 2026-11-08).
- 1.11 (82 F07, NESTED-NATIVE) uses the path grammar that 1.0 row NESTED-FREEZE fixes.
- The copula (1.6) depends on no other 1.x release. The anonymity stack (1.9) needs only F35, which is
  in the same release.

### 1.0.x patch releases

A patch release carries fixes and internal cleanup. For a config or run that is valid today it never
changes a name, a default, an output byte, an exit code, a reason string, a schema field or a report
tag. Cut one when a fix is ready.

In order:

1. A fix that a user reports and that breaks a function or loses data, in its own patch.
2. Broken-today items from the inbox that miss 1.0, and row 24zr SETUP-NER-JSON ([release](groups/release.md)).
3. The Maintenance rows and maintenance candidates in [health](groups/health.md).
4. NONFK-OOM part (b) if its plan is not small. GEN-VECTOR-STREAMS, TEXT-REDACT-RUST-SPLICE,
   FPE-CHECKSUM-NATIVE, PER-COLUMN-ROUTING, FAKER-NATIVE-WIDEN, LARGE-STRING-CAST and UF-DOMAIN are
   1.0 rows (owner 2026-11-22, fast path), not 1.0.x. Output bytes must not change.
5. The patch entries of the corrective backlog, by theme, when a builder is free.

### 1.1: run in production pipelines

Theme: the owner's 1.0 goal is "use in production pipelines". Most pipelines read and write cloud
storage or a database, and need a failed run to restart without redoing finished tables.

| Row or item | Group | What is left | Slices |
|---|---|---|---|
| 64 CLI-CLOUD | [connect](groups/connect.md) | EC2b to EC5, REL-C, CC1 to CC5 | about 9 |
| 64b CLI-DB-SRC | [connect](groups/connect.md) | not started; includes a Postgres CI lane (moved from 1.4, owner 2026-11-22) | about 5 |
| 85 F23 resume, CLI half | [run](groups/run.md) | engine release, then C0, C1, C2a, C2b, C3 | 5 |
| 41 L5a-cli progress | [library](groups/library.md) | one slice, plan passed | 1 |
| SEAM-REASONS | [run](groups/run.md) | not planned; PER-COLUMN-ROUTING moved to 1.0 and the first decline reason ships inside 1.0 row ROUTE-LABEL-TRUTH (owner 2026-11-22) | about 2 |
| 36 L2-cli, then 29 SCAN-MULTI S3-cli | [library](groups/library.md), [scan](groups/scan.md) | moved from 1.0 (owner 2026-11-22); plans passed | about 2 |
| 32c SCAN-ML-MD | [scan](groups/scan.md) | moved from 1.0: md as an opt-in model, the small model stays the default; M-2a3, M-2b re-cut, M-3 | about 3 |
| LANG-SIDECAR | [config](groups/config.md) | DECOY-LANG S7, moved from 1.0 (owner 2026-11-22) | 1 |
| BEHAVIOR-VERSION | this page | one behavior-version key for generation, detection and profiling (not three keys). No key means 1.0 behavior; `decoy init` writes the newest version. Additive, so not a 1.0 row. Not planned | about 2 |
| 82-E3b (fill) | [connect](groups/connect.md) | port #684 | 1 |
| INTL-IDS.1 (fill) | [mask](groups/mask.md) | merge #671 | 1 |
| TARGET-DUP-REFUSE (fill) | this page | two tables written to one target: warn at compile (a new refusal would break configs valid today). Pending check, see below | 1 |

Other fill: job-outcome notifications ([run](groups/run.md)); the corrective-backlog minors on chunked
progress events and the subset signal in `decoy.mask()` and `decoy tokenize`.

This minor is the largest. If it does not fit, SEAM-REASONS moves to 1.2 as fill.

TARGET-DUP-REFUSE is pending a check. Data loss is a V1 blocker under the V1 bar, so the orchestrator
first checks whether main already refuses two tables written to one target (engine #589 added
`target_identity`). If main loses data, the item moves to 1.0 as a refusal.

Depends on: 1.0 rows 61 (CLI delivery) and 59 (F22).

### 1.2: generate completeness and identifiers

Theme: synthetic and masked data that looks like the business, in more countries.

| Row or item | Group | What is left | Slices |
|---|---|---|---|
| 24r GEN-INHERIT | [generate](groups/generate.md) | plan passed; build | about 3 |
| 24n GEN-REL, Later part | [generate](groups/generate.md) | parent-anchored date windows, per-parent aggregates, self-reference as a hierarchy | about 3 |
| RUST-DATE-TEXT | [mask](groups/mask.md) | not planned | about 3 |
| 24qb GEN-TYPES E1b | [generate](groups/generate.md) | the other `distribution` families; needs a portable-sampling design (moved from 1.0, owner 2026-11-22) | about 2 |
| 79b F09 rotation and remap | [mask](groups/mask.md) | domain-version object, rotation, remap (moved from 1.0 to 1.2, owner 2026-11-22; was planned for 1.7) | about 4 |
| FIT-DATE-SHAPE (backlog M3) | this page | fitted dates keep the month and weekday mix, not only the year mix (66.5% January became 8.4%). Opt-in through BEHAVIOR-VERSION | about 2 |
| FIDELITY-ONE-INFERENCE (backlog M5) | this page | one column-kind inference for `run --fidelity` and `report fidelity`. Opt-in through BEHAVIOR-VERSION | about 2 |
| INTL-IDS.2 | [mask](groups/mask.md) | port (INTL-IDS.3 is in 1.0) | 1 |
| EDGE-CASES.1 | [generate](groups/generate.md) | port | 1 |

Fill: the generate candidates for per-provider options and `unique`, and HC5-FIT-CLI; the
corrective-backlog minors on `condition_on` with a renamed parent, number-type inference for computed
columns, and `unique_together` on a subset of a composite key.

Depends on: the 1.0 part of row 24n; INTL-IDS.1 and BEHAVIOR-VERSION (1.1). FIT-DATE-SHAPE and
FIDELITY-ONE-INFERENCE change output, so a config without the new behavior version keeps the 1.0 output.
They were standby items of the V2-to-V1 cut; the owner put them in 1.x on 2026-11-22.

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
| 58b F25 quotas | [run](groups/run.md) | opt-in, no default quota (moved from 1.0, owner 2026-11-22) | about 1 |
| 61b DELIV best-effort | [run](groups/run.md) | DELIV C3 and exit 6; lifts the 1.0 refusal (moved from 1.0, owner 2026-11-22) | 1 |
| 74b F26 `decoy cleanup` | [run](groups/run.md) | stage half of E2b, C1a, C1b (moved from 1.0, owner 2026-11-22) | about 3 |

L3b and L5b depend on how the release gate settles the `decoy library` commands (row EXPERIMENTAL-TIER).
CHUNK-PARALLEL, 58b, 61b and 74b are the engine work in this minor. #321 had none; the owner tagged CHUNK-PARALLEL 1.3 a day later and the 2026-11-22 scope cut added the other three.

### 1.4: more file sources and formats

Theme: read files from where they are, in the format they are in.

| Row or item | Group | What is left | Slices |
|---|---|---|---|
| 87 F02 | [connect](groups/connect.md) | E2 to E5, release, C1 to C4 | about 9 |
| AVRO-ORC.1 | [connect](groups/connect.md) | port, code review, compatibility check | 2 |
| AVRO-ORC.2 | [connect](groups/connect.md) | plan and build the CLI half | about 2 |

Fill: SFTP host-key pinning, subset from non-Parquet sources; the
corrective-backlog minor on one engine retry choke point (F02's retry executor is the same work).

Depends on: 1.1 (CLI-CLOUD, for F02).

### 1.5: more databases and a warehouse

Theme: database to database is the most common test-data use. Competitors list MySQL, SQL Server and
Snowflake among their standard connectors (evaluation section 3).

| Item | Group | What is left | Slices |
|---|---|---|---|
| DB-NEXT | [connect](groups/connect.md) (candidate X-06) | one more database as a source, MySQL or SQL Server; the choice is made at the plan | not sized |
| SNOWFLAKE | [connect](groups/connect.md) (candidate X-06) | Snowflake as a source | not sized |
| WAREHOUSE.1 | [connect](groups/connect.md) | fresh plan for DuckDB attach and multi-part Parquet; it may be the route for DB-NEXT | not sized |
| WAREHOUSE.3 | platform docs | merge the DuckDB plans as docs (input to WAREHOUSE.1) | 0 (docs) |

WAREHOUSE.2 (the platform half) waits for the platform restart ([platform-parked.md](platform-parked.md)).

Fill: DuckDB 12 (write-back) and 13 (SQL filters on sources), the rest of X-06.

Depends on: 1.1 (64b, the CLI database source pattern and the Postgres CI lane).

### 1.6: joint-distribution synthesis

Theme: synthetic tables that keep the correlations between columns.

| Item | Group | What is left | Slices |
|---|---|---|---|
| COPULA.1 to COPULA.3 | [generate](groups/generate.md) | review, port and merge (or land dark earlier) | about 3 |
| COPULA.6 | [generate](groups/generate.md) | plan and build config and CLI wiring | not sized |
| COPULA.5 | [generate](groups/generate.md) | plan after a survey; the DP route is chosen in the plan (decision 2) | not sized |

Fill: F48 statistical synthesis; the certified DP stack candidate if COPULA.5 is built.

### 1.7: policy, secrets and masking options

Theme: governance. A security team states rules once, keeps secrets in its own vault and picks masks that keep the parts of a value a test needs (an email domain, a card BIN, a
subnet, the intervals between one patient's dates).

| Row or item | Group | What is left | Slices |
|---|---|---|---|
| 81 F16, with 24zt | [mask](groups/mask.md) | E2b (engine #642), E1, E3, release, C1, C2 | 5 |
| 83 F13 external adapters | [mask](groups/mask.md) | not started | about 4 |
| MASK-KEEP.1 to .3 | [mask](groups/mask.md) | port as one lane | about 4 |
| DATE-ENTITY.1 | [mask](groups/mask.md) | port and re-review | about 3 |

This minor is the largest. If it does not fit the budget, DATE-ENTITY.1 moves to 1.8 as fill.

Fill: F17 portable disguise bundles.

Depends on: the 1.0 part of row 79 (the vault header) and 79b (1.2). The vault format is fixed for the life of 1.x.

### 1.8: scan baselines and drift

| Row | Group | What is left | Slices |
|---|---|---|---|
| 30 SCAN-LIB | [scan](groups/scan.md) | the run-evidence hash | 1 |
| 32 DRIFT | [scan](groups/scan.md) | not started | about 3 |
| 31 DIST-INTEGRITY | [scan](groups/scan.md) | DI-2 and the CLI half | about 3 |
| 80 F15 | [scan](groups/scan.md) | the slices after E2 and the CLI half | about 3 |

Fill: DETECT-PROFILES, X-09, trend and drift analytics, the detector set version field.

Depends on: rows 29 and 36 (1.1).

### 1.9: quality contracts and privacy risk

Theme: say what "good output" and "safe enough to share" mean, and have the run check both.

| Row or item | Group | What is left | Slices |
|---|---|---|---|
| 69 F35 | [trust](groups/trust.md) | E1a onward, plan rev 4 GO | about 4 |
| 68 F36 | [trust](groups/trust.md) | finish, entry slices, slice 4 registry; plan rev 8 GO | about 5 |
| ANON.1 to ANON.6 | [trust](groups/trust.md) | review and port (or land dark earlier) | about 6 |
| ANON.7 to ANON.9 | [trust](groups/trust.md) | plan and build the config, planner, evidence and CLI wiring; the ANON.9 release freezes `risk-utility-report/v1` and captures its compat corpus | about 3 to 5 |

F35 goes first, and before F32 in 1.10 (owner Q5, 2026-11-08). The anonymity stack is the delivery of F37
(post-mask privacy risk) and X-12.

Fill: F12 customer regression suites; the generate candidate F46.

### 1.10: evidence you can hand to an auditor

| Row | Group | What is left | Slices |
|---|---|---|---|
| 72 F33 | [trust](groups/trust.md) | C1a, C1b, the release slice | 3 |
| 78 F10 | [trust](groups/trust.md) | release and repin, then 78-C1 | 2 |
| 70 F32 remainder | [trust](groups/trust.md) | E1b to E3, C0, C1, C1b | 6 |

Fill: a Parquet support bundle; F39 OpenLineage export. Depends on: F32 E1b on F35 E1a (1.9).

### 1.11: nested data and application-ready databases

| Row or item | Group | What is left | Slices |
|---|---|---|---|
| 82 F07 | [connect](groups/connect.md) | E2b, E4a, E4b, E5 (E3b lands in 1.1) | 4 |
| NESTED-NATIVE | [connect](groups/connect.md) | plan with row 82; the fail-closed refusal is 1.0 row NESTED-FREEZE (b) | about 3 |
| 86 F01 | [connect](groups/connect.md) | E1 onward, with the watchdog design (decision 4) | about 7 |

Fill: X-02 if F07 lands early. Depends on: 1.1 (64b, the Postgres CI lane); 1.0 row NESTED-FREEZE (the path grammar).

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
#321). Nothing in this program is 2.0: INTL-IDS.3 lands in 1.0 (decision 3), and COPULA.4 is not
needed because the standalone copula model is kept (decision 5).

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
   (row 93). Dark landing (decision 6) is the same case after 1.0.
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
| | scan and post-scan (multi-table drift baseline, all-null key columns, gate memory pressure read as out of memory) | 1.8 fill |
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
- #333 against main line by line (it was closed on 2026-11-22 as superseded), and the review state of
  each of the 17 DuckDB plans.
- From the V2-to-V1 evaluation, not checked here: whether a native nested column with no rule already
  fails closed (NESTED-FREEZE (b)), and whether main refuses two tables written to one target
  (TARGET-DUP-REFUSE).
- Slice counts for unbuilt items (AVRO-ORC.2, ANON.7 to ANON.9, COPULA.5, COPULA.6, WAREHOUSE, DB-NEXT, SNOWFLAKE, BEHAVIOR-VERSION and the
  standby items) are
  estimates or not given.
