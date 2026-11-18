# Config, validation and the init wizard

Status: current

Part of the roadmap: [ROADMAP.md](../../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

Rows keep their number from the pre-split track. A row number or section number that is not in a group file is a closed row or old section in the [snapshot](../../archive/2026-11-18-roadmap-before-split.md).

## 1.0

Blocks the 1.0 release.

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| 24b | QA-GATE (first-user QA, owner 2026-11-08): `decoy validate` refuses what `run` would refuse. A declared column missing from the source and a rule missing a required setting (`fpe` with no namespace) fail at the gate with exit 1, the config-error code, never exit 3 at run. Folded into CONFIG-EXPLICIT E2's declaration gate (same pre-read boundary). Added 2026-11-10 (DI models QA 2026-11-10 M7): a DP release with no labels for a sampled column is refused at `decoy validate`, not at run with `statistical_stats_degenerate` | engine, CLI | NOT STARTED; scope added to E2 | [QA report](../../records/2026-11-08-cli-qa-first-user.md) H2, H3; DI models QA 2026-11-10 M7 | row 22 E1 |
| 24e | CLI-QA1 (owner 2026-11-08: bugs are V1): the validate and preflight traceback when a relationship has no resolvable namespace (and `validate compile` reporting no FK while one is declared); internal names in user text (`_scan`, `_gate`, ticket ids, the platform doc path); `explain pipeline` says version 1; `list disguises` tip names presets `init` rejects; stray `logs/` in the working directory; false "output directory does not exist" warning; fidelity "PASS grade F"; `integrity` column detail outside `--json`; reid risk unit; `explain vault` vs the plaintext tokenize store; `ci check` with no manifest; `validate compile --json(an identifier kept in the pre-split snapshot)namespace` (namespace must not be required when nothing is masked); fidelity "intended" marker (hash key columns not flagged, no joint score across id spaces); `integrity` saying configured columns are "not configured to be masked" and hiding `source_identity_rate`; internal ids in help (FC-1, S22-CL-V1GRAPHRUNNER, report.py:97, BF1); `explain keys` length; docs on which strategies keep frequency and joint structure (faker is row-positional, shuffle breaks pairing); `mode: generate` in the generate template and engine recipes.md; a generate-with-FK example | CLI, engine | IN PROGRESS. MERGED 2026-11-09: engine #429 (`3b1b285d`, `profile_relationships_from_config` export, engine logger NullHandler), CLI #145 (`df418657`, root-app traceback guard), CLI #146 (`cfdee4ef`, C2a group paths and internal names out of user text), CLI #147 (`4eb43a52`, C4 report verdicts and integrity findings), CLI #148 (`6a175432`, C0b uncompilable plan as preflight capacity fail), CLI #149 (`d5ff37dd`, C2b internal names out of user text, old-engine refusals via guidance registry), CLI #150 (`a565bded`, C3a real command name in `--json`), CLI #151 (`9f752825`, C5 run reports published paths only). C1 MERGED (CLI #181, `6fafa5cd`, 2026-11-10): no-profile compiles carry the config's relationships, so `validate compile` orders parents first and reports a relationship it cannot resolve; in `decoy validate`, a `capacity.plan_uncompilable` row that repeats a compile error becomes a warning. C3b MERGED (CLI #224, `62798427`, 2026-11-12): `decoy validate` checks output targets. Every slice of `C:plan/cli-qa1` is now merged (E1, C0a, C0b, C1, C2a, C2b, C3a, C3b, C4, C5). The row stays open for its distribution-integrity QA items, which are outside that plan and have no plan or merged PR yet | QA report sections 2 to 4; [DI QA report](../../records/2026-11-08-cli-qa-distribution-integrity.md) MEDIUM, LANGUAGE, High 5 | none |
| 32b | INIT-WIZARD: `decoy init` becomes a guided wizard (owner 2026-11-06: V1, was post-V1 spec #73). It scans the source with the selected detectors (SCAN-ML), scaffolds the pipeline YAML, then walks the user section by section and column by column to confirm or reject each suggestion. After a run, post-scan findings are shown the same way to confirm or reject | CLI | BUILDING; spec v3 (#119); Phase 1a plan `docs/plans/2026-11-08-init-wizard-phase-1a.md` MERGED (#120, Dennis GO r2, Codex GO). Engine part E3 (`keyed_columns_for_config`) MERGED (engine #407). E1 and the CLI slices wait on SCAN-MULTI S3-engine and S3a.1 (plan section 2) | none | SCAN-ML; SCAN-MULTI S3 `starter_config` |

## Later (1.x)

Additive. Not scheduled until a 1.x release picks it up.

None.

### Candidates with no plan yet

Non-breaking ideas, so v1+ by rule. A candidate becomes a row in the table above when a release picks it up.

| Item | Source | Why it does not break |
|---|---|---|
| F18 config composition (includes, inheritance) | Council features | New optional keys; complete inline configs unchanged. |
| F19 semantic diff and repair | Council features | New command; no change to how a reviewed pipeline runs. |
| F41 expression evaluator preview | Council features | New command. |

## Maintenance

No user-visible change. Merges at any time and never gates a release.

None.
