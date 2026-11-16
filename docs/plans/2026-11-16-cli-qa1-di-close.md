# CLI-QA1 close-out: the distribution-integrity items of row 24e

Status: plan (2026-11-16, not built; round 1 review resolved). CLI and engine. Roadmap row 24e
(CLI-QA1).

Every slice of `C:plan/cli-qa1` is merged. Row 24e stays open only for the items it lists under
"Also from the distribution-integrity QA". This plan checks each of those items against `origin/main`
(CLI `d8805373`, pins `decoy-engine==0.27.0`; engine main `13c95c7de`, last release `v0.27.0`) and
plans the ones that are still open. Every engine file:line below was re-read at `13c95c7de`. When the
slices below merge, row 24e closes.

Rules consulted: `~/dev-rules/README.md` (routing), `00-universal.md`, `risk-and-exceptions.md`
(R1, R2), `development-loop.md` (PLAN, Proportion, Placement), `bugfix.md`, `proportionality.md`,
`api-and-compatibility.md` (`quality-policy/v1` and `--json` are consumed outside the unit),
`catalogs/recurring-defects.md` (classes 4, 5, 9, 11). Memory: `v1-bar-blocking-criteria`,
`plan-defines-acceptance-tests`, `develop-correctly-registries-and-sizing`,
`v1-scope-no-new-features`. Inputs: roadmap rows 24a to 24zm, the DI QA record
`docs/records/2026-11-08-cli-qa-distribution-integrity.md` (cited below as "DI:line"), the first-user
QA record, the DI models QA record, the readiness map, and `docs/qa/cli-v1-checklist.md`.

Evidence method: code read on `origin/main` of both repos, plus one read-only probe with
`~/bin/vm-run cli` on 2026-11-16 (Mac and decoy-test-6, CLI `d8805373`, engine 0.27.0). Probe results
are quoted as "probe" below. No production code was changed.

## 1. Item list and verdict

V1 bar: only function breaks, data loss and non-admin leaks block V1. The others are V2-LOG unless
the owner keeps them in this row (owner question Q1, decided: build them here).

| # | Item (row 24e text) | Source | Status on main | Bar | Slice |
|---|---|---|---|---|---|
| 1 | Traceback for a generate-only relationship with no `namespace` | DI:86-88 (H5) | FIXED. CLI #145 (`df418657`) root traceback guard, #148 (`6a175432`) uncompilable plan as a preflight fail, #181 (`6fafa5cd`) compile carries the config's relationships. Probe: `validate`, `validate compile`, `validate preflight` and `run` each exit 1 with one `namespace_missing` line and no traceback | - | none |
| 2 | `namespace` must not be required when nothing is masked | DI:88-89 (H5) | OPEN. Engine `NamespaceRegistry.for_relationship` (`relationships/_namespace.py:124-153`) raises `namespace_missing` for every edge with no namespace, whatever the table kinds. Probe: a two-table generate pipeline with a `relationships:` block and no namespace is refused (exit 1) by `validate` and `run`; the same pipeline without the block runs | V1 (a valid generate config cannot run; checklist GATE-12 expects exit 0) | E1, C1 |
| 3 | Fidelity "intended" marker: hash key columns not flagged | DI:93-101 (M1, M2) | PARTLY FIXED. "PASS grade F" is fixed by CLI #147 (`4eb43a52`): report mode prints `REPORT ONLY`. OPEN: `quality/policy.py` `_DEFAULT_STRATEGY_EXPECTATIONS` sets a 0.05 minimum for `hash`, `faker` and `redact`, whose value sets are disjoint by design. Probe: `report fidelity patients.csv out.csv --config mask.yaml --mode fail` on a correct hash and faker masking prints two violations (`patient_id`, `full_name`: expected 0.05, actual 0.0) and exits 4. No column is marked intended | V1 (a fidelity gate in fail mode fails a correct mask) | E0, E2, C1 |
| 4 | No joint score across id spaces | DI:103-106 (M3) | OPEN, narrower than reported. Since CLI #189 a joint is scored only when the user passes `--joint`. Probe: `--joint patient_id,diagnosis` with `patient_id` hashed prints `diagnosisxpatient_id 0.000`. `fidelity --generate` without `--joint` prints no joint | V2-LOG | E2, C1 |
| 5 | `integrity` says configured columns are "not configured to be masked" | DI:119-121 (M6) | OPEN without `--config`. With `--config` the text is right (probe: `faker` info, `fpe` warning). Without it the CLI passes a config with no tables, and the engine says "was not configured to be masked", which it cannot know. Two sites carry that text in `verification/postmask/residual_pii.py`: `_escalate` at `:291` (configured is `None`, output positionally identical to source on a high-confidence detector: severity `fail`) and `_classify` at `:362` (severity `warning`). Without `--config`, the `_escalate` branch is the only leak alarm, so only its wording may change | V2-LOG (wording); the `:291` fail is a V1 leak guard and must not weaken | E2 |
| 6 | `integrity` hides `source_identity_rate` | DI:122-123 (M6) | OPEN. Column names show since CLI #147; the rate is only in `--json` (probe: `0.0` per finding in JSON, absent from the table) | V2-LOG | C1 |
| 7 | Internal ids in help: FC-1, S22-CL-V1GRAPHRUNNER | DI:134-138 | FIXED. CLI #146 (`cfdee4ef`), #149 (`d5ff37dd`); sentry `tests/sentry/cli_text/test_user_text_internal_names.py` bans `FC-\d` and `\bS\d+-[A-Z]`. Probe: `explain modes` carries neither | - | none |
| 8 | Internal ids in help: `report.py:97`, `BF1` | DI:135-137 | OPEN. The `report fidelity` docstring (`src/decoy/cli/report.py:1702-1717`) is its `--help` text. Probe: lines 7 and 12 of `decoy report fidelity --help`. `report integrity --help` says "the platform's mask job" (probe line 8). The sentry has no pattern for a source line reference or `BF\d`. "Storm integrity" and `JobStormReport` are STORM wording and go with row 56 | V2-LOG | C2 |
| 9 | `explain keys` length | DI:139-141 | OPEN. 52 lines at 200 columns (probe). The point "use `--master-key` for generation, `--mask-secret` for masking" is in the summary but not at the top of the body. The summary is 117 characters, so the panel subtitle is cut on a narrow terminal. Key length (checklist DOC-09): the topic says "32-byte hex", `--master-key` help says "64-char hex", `_prepare.py:108` checks 32 bytes; both are true but read differently | V2-LOG | C2 |
| 10 | Docs on which strategies keep frequency and joint structure | DI:108-117 (M4, M5) | PARTLY FIXED. `shuffle`: CLI `explain transforms` (#189, `aa05799d`) says "Keeps the distribution, breaks the row link"; engine `docs/strategies.md:322-330` says the same. `faker`: engine `docs/strategies.md:22-27` says the default draw is by row position and does not keep joins. OPEN: the CLI `faker` line (`explain.py:599`) says nothing about it | V2-LOG | C2 |
| 11 | `mode: generate` in the generate template and engine `recipes.md` | DI:147-150 | OPEN. CLI `src/decoy/templates/generate.yaml:8`; engine `docs/recipes.md:154` and `:184`, and `docs/strategies.md:1251`. `PipelineConfig` refuses a top-level `mode:` key, so a user who follows `recipes.md` gets a config error | V2-LOG | C2, E1 |
| 12 | A generate-with-FK example | DI:156-159 | PARTLY FIXED. The `type: reference` syntax is in `explain pipeline` and `explain yaml` (#189). OPEN: no template and no file in `examples/` has a child table with a `reference` column | V2-LOG | C2 |

Found while checking, not in row 24e (V2-LOG candidates, not planned here):

- `report fidelity` prints `gof_unavailable (column, metric, reason)`: the fallback branch of
  `report_warning_records` (`src/decoy/ui/summary.py:188-191`) prints the detail key names, not the
  column name.
- `report integrity --config` on a correct `fpe` SSN column gives a warning, "configured strategy
  'fpe' does not have a documented residual-PII expectation". `fpe` keeps the SSN format by design.
- Checklist GEN-16 says "The written YAML says `mode: generate` and validates". That contradicts item
  11. C2 corrects the checklist text (owner question Q4, decided: yes).

V2-LOG items this plan creates (logged in row 24e's closing note, not built):

- V2-LOG-a. Treat generate-only edges as non-FK for routing, so such a job can take the chunked and
  shadow-generation routes (section 2.1).
- V2-LOG-b. Leave intended columns out of `marginal.score`, `overall_score` and the grade (owner
  item; it moves frozen numbers, section 2.2).
- V2-LOG-c. Flag an intended column whose value similarity is near 1.0 (the strategy did not
  replace values). Today the `intended` marker shows next to such a score with no warning; the
  residual-PII check in `report integrity` is the leak guard for that case.

## 2. V1 behaviour

1. A relationship whose parent and child tables are both generate tables needs no `namespace`.
   `decoy validate`, `validate compile`, `validate preflight` and `run` accept it. The generated
   bytes are the same as for the same pipeline without the `relationships:` block. A relationship
   with a mask table on either side still needs a namespace and is refused with `namespace_missing`,
   as today. A relationship to a table that is not in `tables:` is still refused, as today.
   Routing: such a job is accepted on the full-frame route. A non-empty `relationships:` block sets
   `has_fk` (`execution/_planner.py:229`), refuses the chunked route (`_planner.py:337`) and makes
   shadow generation decline (`execution/physical/_shadow_generation.py:402`). This row does not
   change routing (V2-LOG-a). The route the run reports and the capacity estimate agree on that
   full-frame route.
2. Under `report fidelity --config`, a column masked with a strategy that replaces values by design
   has no DEFAULT value-identity minimum. "Replaces values by design" is not a new list: it is every
   strategy whose static class in the distribution-behaviour table is `preserves_cardinality_only`,
   `destroys_frequency` or `collapses` (today `hash`, `fpe`, `tokenize`, `group_key`, `faker`,
   `grouped_series`, `redact`, `text_redact`). `categorical` is left out, because its class depends
   on provider config that the policy does not see. Override precedence is unchanged: an explicit
   `thresholds.columns` entry for the column, or a `strategy_expectations` override for the
   strategy, still sets a minimum and still gives a violation (`quality/policy.py:166-182` and the
   column lookup in `_check_per_column`, `:336-341`). `intended_columns` lists only intended-class
   columns that end with no resolved minimum. The terminal marks them `intended` and prints one
   line: "Columns marked intended were masked with a strategy that replaces values, so a low score
   there is expected." The shape check (`shape_strategy_expectations`) does not change. `--mode
   fail` on a correct masking with no overrides exits 0.
   Aggregates do not change in V1: intended columns still count in `marginal.score`,
   `overall_score` and the grade, so no frozen number moves. A `--min-grade` (or `overall` minimum)
   on a correct hash masking can still fail. The help line for `--min-grade` and the note line say
   so. Leaving them out of the aggregates is V2-LOG-b.
3. A `--joint` pair that names an intended column is an intended joint. The policy result gains
   `intended_joints: [[a, b], ...]` (sorted pairs). `quality-fidelity/v1` and `quality-report/v1`
   do not change: the joints stay in the report's `pairwise.joints` (`quality/fidelity.py:222`)
   with their scores. `_check_pairwise` (`quality/policy.py:292-312`) today compares the aggregate
   `pairwise.score`. After E2 it compares a recomputed score: the mean of the joint scores that are
   not intended, with the same formula the report uses. When every joint is intended, the pairwise
   check is skipped, not failed, and the result says so (`pairwise_skipped: "all_joints_intended"`
   in the policy result). The terminal prints `intended` in place of the joint's score.
4. `report integrity` without `--config` does not claim a column was not configured. Both message
   sites (`residual_pii.py:291` and `:362`) say the config has no entry for the table, so the
   strategy is unknown. Only the wording changes: with no config entry and an output positionally
   identical to source on a high-confidence detector, the finding stays severity `fail` and the
   command exits 4. The residual-PII table shows the share of rows equal to the source
   (`source_identity_rate`) for each finding; a finding with no rate prints `-`.
5. No user text (help, explain, templates) carries a source line reference, a `BF<n>` id or a
   platform reference. `explain keys` starts with which key goes with which job and fits about one
   screen. The CLI `faker` line says that the default draw does not keep equal values equal. No
   user-facing doc or template tells the user to write `mode: generate`. One bundled example
   generates a parent and a child table joined by a `reference` column.

## 3. Failure modes

- F1. The namespace exemption is too wide: a mixed edge (masked parent and generated child, or the
  reverse) passes without a namespace, and FK masking then has no key. Guard: AT-E1.3.
- F2. The derived namespace changes generated bytes or reaches a masking path. Different parent keys
  get different derived names; fan-out children of one parent key share one. A user may declare a
  namespace with the same text; the derived name is never registered, so it cannot meet a user
  namespace. Guard: AT-E1.2 (bytes equal to the run without the block) and AT-E1.5 (the derived name
  is absent from `registry.declared()`, plan namespaces and the seed envelope; a user mask edge with
  the same text masks the same bytes).
- F3. One of the seven places that build a relationship graph (section 7.2) builds its registry
  another way and still refuses, or reports a route the run does not take. Guard: AT-E1.2 and AT-E1.4
  go through `run_pipeline` and the capacity estimate and assert the full-frame route.
- F4. The intended set is too wide and hides real drift on a shape-keeping strategy (`shuffle`,
  `bucketize`, `date_shift`), or hides a minimum the user set. Guard: AT-E2.2 and AT-E2.7.
- F5. The policy output changes in a way that breaks a reader of `quality-policy/v1`. The change only
  adds keys; all four goldens are re-pinned in E2 with a reason, a fifth golden pins the intended
  case, and the CLI `--json` shape snapshot is re-pinned in C1. Guard: AT-E2.6, AT-C1.6.
- F6. A new banned-text pattern also hits a legitimate user string (for example a file name a user
  gave). The patterns are limited to the shapes in section 11, with seeded self-tests. Guard: AT-C2.1.
- F7. Moving `_render_residual_pii` out of `report.py` changes the table for existing tests. Guard:
  the existing `test_integrity_human_output_*` tests stay green unchanged.
- F8. The residual-PII wording change also weakens the no-entry leak alarm (`residual_pii.py:291`).
  Guard: AT-E2.5 part (b).
- F9. A second hand-kept list of "value-replacing" strategies drifts from the distribution-behaviour
  table. Closed by construction: E0 moves the table to a tier both `quality` and `execution` may
  import, and E2 derives the intended set from it (section 5, design notes).

## 4. Acceptance tests (written first)

Each test fails on `origin/main` before its slice, unless it is marked "guard" (it passes before and
catches the named mutation). Builders may add tests; no builder may weaken these.

E0 (engine, pure move):

- AT-E0.1 (guard) the existing `tests/unit/providers_v2/test_distribution_behavior_metadata.py` and
  `tests/unit/transforms/test_derived_aggregate.py` pass with only their import path changed.
  Mutation: change one label in the moved table; red.
- AT-E0.2 the import-layer contract passes with the ignore line
  `decoy_engine.plan._seed_envelope -> decoy_engine.execution._distribution_behavior` removed from
  `.importlinter` and from `tests/sentry/baselines/import-layers.json`. Fail before: the ignore line
  is needed (the import goes up a tier).
- AT-E0.3 (guard) `quality` may import the new module: `lint-imports` passes with a scratch import
  from `decoy_engine.quality.policy`. Mutation: put the module back under `execution/`; red.

E1 (engine):

- AT-E1.1 `compile_plan` on a two-table generate config (`patients.patient_id` sequence,
  `visits.patient_id` reference) with a `relationships:` entry and no namespace returns a plan whose
  graph has one edge. Fail before: `NamespaceConfigError(namespace_missing)` (probe, same path).
- AT-E1.2 `run_pipeline` on that config writes the same bytes as on the same config with no
  `relationships:` block, same seed, and reports the full-frame route (not chunked, not shadow
  generation). Fail before: refused.
- AT-E1.3 (guard) a mask-only edge and both mixed edges with no namespace still raise
  `namespace_missing`, also when compiled in the same process right after the AT-E1.1 config. An
  edge whose parent or child table is not in `tables:` is still refused with its reason today.
  Mutation: drop the table-kind test in the exemption, or cache the generate-table set; red.
- AT-E1.4 the capacity estimate (`execution/capacity.py`) accepts the AT-E1.1 config, and the route
  it estimates is the route AT-E1.2 reports. Fail before: `namespace_missing`.
- AT-E1.5 for the AT-E1.1 config: the derived name is absent from `registry.declared()`, from the
  plan's namespaces and from the seed envelope. Two generate-only edges from different parent keys
  get different derived names; two child edges to one parent key get the same one. A second config
  that declares a namespace whose text equals the derived name and uses it on a mask edge writes the
  same masked bytes with and without a generate-only edge in the config. Fail before: compile
  refuses the generate-only edge.
- Review check (no new test): no file under engine `docs/` outside `docs/plans/`, `docs/records/` and
  `docs/audit/` tells the user to set a top-level `mode:` key or pass `--mode generate`. Before:
  `docs/recipes.md:154`.

E2 (engine):

- AT-E2.1 `apply_quality_policy` with `strategy_map={"patient_id": "hash", "full_name": "faker"}` and
  both similarities 0.0: no `column` violation; the result lists both in `intended_columns`. Fail
  before: two violations, expected 0.05, actual 0.0 (probe).
- AT-E2.2 (guard) a `shuffle` column at 0.5 still gives a `column` violation; a `bucketize` column
  below 0.30 still does. Mutation: skip every mapped strategy; red.
- AT-E2.3 a report with joint `(diagnosis, patient_id)` and `patient_id: hash`: `intended_joints` is
  `[["diagnosis", "patient_id"]]`, and a `pairwise` minimum does not fail on it. Case (b): two
  joints, one intended at 0.0 and one not at 0.9, with minimum 0.8: no violation (recomputed score
  0.9). Case (c): every joint intended: no `pairwise` violation and `pairwise_skipped` is
  `all_joints_intended`. The report dict is byte-equal before and after the policy call. Fail
  before: the pairwise minimum fails on the aggregate.
- AT-E2.4 (guard) the shape check for `hash` still applies its 0.95 shape minimum.
- AT-E2.5 `check_residual_pii` with a config that has no entry for the table: (a) the message for a
  hit says the config has no entry for the table, and never "was not configured to be masked", at
  both sites; (b, guard) an output identical to source on a high-confidence detector still gives
  severity `fail`. With the table present and the column absent, the message does not change
  (guard). Mutation: drop the `configured is None` escalation in `_escalate`; (b) goes red. Fail
  before: probe text.
- AT-E2.6 the `tests/snapshots/golden/quality_policy/` goldens: all four
  (`all_checks_violate_warn_mode`, `empty_policy_pass`, `overall_fail`,
  `per_column_strategy_violation`) are re-pinned in this slice with a one-line reason per file (the
  added keys); a fifth golden, `intended_hash_faker`, pins the AT-E2.1 result; the
  `quality-policy/v1` tag does not change.
- AT-E2.7 a `hash` column at 0.0 with (a) `strategy_expectations: {hash: 0.5}` and (b)
  `thresholds.columns: [{column: patient_id, min: 0.5}]` each still gives a `column` violation, and
  the column is not in `intended_columns`. Guard for the precedence rule. Mutation: check the
  intended class before the override lookup; red.
- AT-E2.8 (guard) on the AT-E2.1 input, `marginal.score`, `overall_score` and the grade are equal
  to their values on `origin/main`, and an `overall` minimum above that score still fails.
  Mutation: drop intended columns from the marginal mean; red.
- AT-E2.9 (guard) the intended set equals the set of strategies whose class in the moved table is
  one of the three replacing classes, minus `categorical`. Mutation: add a strategy to the table as
  `destroys_frequency` and do not touch `policy.py`; the strategy is intended with no other edit.

C1 (CLI, after the repin to the engine release that carries E0, E1 and E2):

- AT-C1.1 (GATE-12) `decoy validate` on the AT-E1.1 config exits 0; `decoy run` writes both tables
  and every `visits.patient_id` is in `patients.patient_id`. Fail before: exit 1 (probe).
- AT-C1.2 (EVD-12) `decoy report fidelity src out --config cfg --mode fail` on a correct hash and
  faker masking exits 0; the table shows `intended` for both columns and prints the note line once.
  Fail before: exit 4 with two violations (probe).
- AT-C1.3 `--joint patient_id,diagnosis` with `patient_id` hashed prints `intended` for that joint,
  not `0.000`. Fail before: `0.000` (probe).
- AT-C1.4 (EVD-13) `decoy report integrity` without `--json` shows a "Same as source" column with
  the rate for each residual-PII row, and `-` for a finding whose rate is `None`. Fail before: no
  such column (probe).
- AT-C1.5 (EVD-13) `decoy report integrity` without `--config` prints no "not configured to be
  masked". Fail before: two such lines (probe).
- AT-C1.6 the `--json` shape snapshot (`tests/fixtures/release_freeze/json-shapes.json`) is re-pinned
  for `report fidelity` with the added policy keys (`intended_columns`, `intended_joints`,
  `pairwise_skipped`), and nothing else in it moves. `quality-fidelity/v1` and `quality-report/v1`
  fields in the snapshot do not move.
- AT-C1.7 (guard) `src/decoy/cli/report.py` shrinks: C1 lowers its `SIZE_ALLOWLIST` entry in
  `tests/sentry/layout/test_module_size.py` and its entry in
  `tests/sentry/baselines/module-size.json` to the new line count after the move. Mutation: leave
  the entry at 2,309; the may-only-shrink check is red.
- AT-C1.8 `report fidelity --min-grade A --mode fail` on a correct hash masking still fails, and the
  `--min-grade` help line says intended columns count in the grade. Guard for section 2.2.

C2 (CLI, can start now):

- AT-C2.1 `BANNED_USER_TEXT` gains a source line reference (`\b\w+\.py:\d+`), `\bBF\d+\b` and
  `the platform's`; a seeded self-test for each pattern fails when the pattern is removed. The sentry
  then passes over the whole tree. Fail before: `report fidelity --help` lines 7 and 12, `report
  integrity --help` line 8 (probe).
- AT-C2.2 `decoy show template generate` and every file in `examples/` carry no `mode: generate`.
  Fail before: `generate.yaml:8`.
- AT-C2.3 (DOC-09) `decoy explain keys`: the first three body lines name `--master-key` for
  generation and `--mask-secret` for masking; the body is at most 30 lines at 100 columns; the
  summary is at most 70 characters; the key length is written as "64 hex characters (32 bytes)",
  the same as `--master-key` help and the check in `src/decoy/cli/run/_prepare.py`. Fail before: 52
  lines, 117-character summary.
- AT-C2.4 `decoy explain transforms`: the `faker` line says equal source values get different fakes
  unless the column is deterministic. Fail before: no such text.
- AT-C2.5 `examples/generate_example.yaml` has a child table with a `type: reference` column; it
  validates (existing parametrized test), and an e2e run writes both tables with no orphan key. Fail
  before: no `reference` column under `examples/`.
- AT-C2.6 `decoy explain modes` carries no "V1 had" history line. Fail before: probe line 15.
- AT-C2.7 (guard) C2 adds no net lines to `src/decoy/cli/report.py` (docstring edits only).

## 5. Slices

| Slice | Repo | Risk | Content | Production files (estimate) | Lines | Depends on |
|---|---|---|---|---|---|---|
| E0 | engine | R1 (pure move) | Move `execution/_distribution_behavior.py` to `contracts/distribution_behavior.py` with `git mv`, body unchanged. Update the one importer, the two test imports and the two doc references. Remove the `.importlinter` ignore line, its `import-layers.json` baseline entry and the physical-seam allowlist entry (`tests/sentry/test_physical_seam_disconnection.py:953`); all three lists shrink. Repoint the mutation ledger path | `src/decoy_engine/contracts/distribution_behavior.py` (moved), `src/decoy_engine/plan/_seed_envelope.py`, `.importlinter`, `docs/distribution-integrity/extending.md`, `docs/distribution-integrity/index.md` (5) | ~20 changed (185 moved) | none |
| E1 | engine | R2 | Item 2: generate-only edges get a derived namespace. Item 11 engine docs (`recipes.md`, `strategies.md:1251`) and a `docs/relationships.md` note, including the full-frame route. Changelog fragment | `src/decoy_engine/relationships/_namespace.py`, `docs/recipes.md`, `docs/strategies.md`, `docs/relationships.md` (4) | ~120 | none |
| E2 | engine | R2 | Items 3 and 4: intended set derived from the moved table in `quality/policy.py`; `intended_columns`, `intended_joints`, `pairwise_skipped` in the policy result; recomputed pairwise score. Item 5: residual-PII wording at both sites, severity unchanged. One doc paragraph. Changelog fragment | `src/decoy_engine/quality/policy.py`, `src/decoy_engine/verification/postmask/residual_pii.py`, `docs/distribution-integrity/snapshot-and-fidelity.md` (3) | ~170 | E0 |
| R | engine, CLI | standard repin | Engine release with E0, E1 and E2, then the CLI repin by the engine repin checklist | release files only | - | E0, E1, E2 |
| C1 | CLI | R2 (frozen `--json` shape re-pin) | Items 2, 3, 4, 6 in the CLI: render `intended` and the note, intended joints, the "Same as source" column, the `--min-grade` help line; move `_render_residual_pii` to `src/decoy/ui/summary.py`; lower the `report.py` size entries; GATE-12 e2e; CHANGELOG | `src/decoy/ui/summary.py`, `src/decoy/cli/report.py` (2) | ~130 | R |
| C2 | CLI | R1 | Items 8 to 12 in the CLI: docstrings of `report fidelity` and `report integrity`, banned patterns, template comment, `explain keys` rewrite, `faker` note, `explain modes` history line, FK example, checklist GEN-16 text; CHANGELOG | `src/decoy/cli/report.py`, `src/decoy/cli/explain.py`, `src/decoy/templates/generate.yaml`, `examples/generate_example.yaml`, `docs/qa/cli-v1-checklist.md` (5) | ~200 | none |

E0, E1 and C2 can run in parallel (different repos or different files); E2 starts when E0 merges.
C1 and C2 both touch `report.py`; C2 changes only two docstrings and adds no net lines, so whichever
merges second rebases, and C1 sets the size entry to the count on its own merge head. C1 merges
last, and the row closes when C1 merges.

New public names: `decoy_engine.contracts.distribution_behavior` (moved module; the old
`execution._distribution_behavior` path is deleted, pre-GA hard delete, no shim). E2 adds three keys
to the `quality-policy/v1` result dict (`intended_columns`, `intended_joints`, `pairwise_skipped`).
No change to `quality-fidelity/v1` or `quality-report/v1`. No new reason code.

Design notes:

- E0 (finding H4: one table, not two). `_STATIC_BEHAVIOR` in `execution/_distribution_behavior.py`
  already says which strategies replace values. `quality` (tier 3 in `.importlinter`) may not
  import `execution` (tier 2), so E2 cannot read the table where it is. The file imports only
  `typing` and has one production importer (`plan/_seed_envelope.py`, through an ignore line). Moving
  it to `contracts/` (tier 4, "engine-owned contracts that CLI and platform consume") lets both
  tiers import it and removes one ignore line. The move is 185 lines with a five-line diff
  elsewhere, inside the slice limits, so the fallback (a parity test between two lists) is not
  needed.
- E1: `build_namespace_registry(config, profile)` already reads the config. It records the set of
  generate tables from `config.classify_table_kinds` (the one table-kind classifier, guarded by
  `tests/sentry/test_table_kind_classifier.py`). Only when both tables are generate tables does
  `for_relationship` return a derived name in place of the raise. The name follows the composite
  precedent (`composite/<table>/<members>`, `_namespace.py:333`): `generated/<parent_table>/<columns
  joined by __>`. Different parent keys get different names; fan-out children of one parent key
  share one. The name is not added to `declared()`, not bound to any column and not written to the
  plan or the seed envelope, so a generate path that reads `for_column` sees no change and a user
  namespace with the same text is a separate thing. No new reason code. Every graph builder goes
  through `build_namespace_registry`; the seven in section 7.2 inherit the exemption, and the
  builder names them in the PR.
- E2: `policy.py` imports `distribution_behavior_for` from `contracts` and builds the intended set
  once at import from the three replacing classes, minus `categorical`. The three default entries
  for `hash`, `faker` and `redact` in `_DEFAULT_STRATEGY_EXPECTATIONS` are deleted (they were the
  only replacing strategies with a default); explicit overrides still win (section 2.2). The
  strategy trait sets elsewhere (`residual_pii.py`, `_leakage.py`) answer other questions and stay
  as they are.
- C1: `report.py` is over the size cap, so C1 moves `_render_residual_pii` into `ui/summary.py` (the
  CODEMAP "Terminal output" line already places `report fidelity` text there) and adds the new column
  in the moved code. "Same as source" renders `None` as `-`.

## 6. Class table

| # | Class | Applies here | Structure that closes it | Test | Mutation that turns it red |
|---|---|---|---|---|---|
| 1 | Value-bearing output | the new "Same as source" column, the intended note, the derived namespace name, residual-PII text | the column prints a rate, the note is fixed text, the derived name is built from table and column names only and never leaves the registry, residual-PII text names detector, table and strategy only | AT-C1.4, AT-E1.5, AT-E2.5 | print the finding's `message` from the source frame in place of the rate |
| 2 | Cleanup missing on an exit path | `decoy run` on a generate-only FK config, the only path these slices newly open | the existing run publication (atomic run folder) is reused; no slice adds a write | AT-C1.1 (a run writes both tables in one run folder) | write the child table outside the run folder |
| 3 | Stale state | the namespace registry, rebuilt on every compile from config and profile | the generate-table set is computed inside `build_namespace_registry` from the same config, never cached | AT-E1.3 (same process: a generate config then a mixed config, the second still refused) | cache the generate-table set at module level |
| 4 | Route parity | the seven graph builders in section 7.2; `validate` vs `run`; reported route vs capacity estimate | one registry builder for every route; no routing change in this row | AT-E1.2, AT-E1.4, AT-C1.1 | build the exemption inside `compile_plan` only |
| 5 | Referential integrity | mixed and mask FK edges keep their namespace rule; edges to unknown tables stay refused; generated child keys resolve | exemption only when both tables are generate tables | AT-E1.3, AT-C1.1 | drop the table-kind test |
| 6 | Untrusted producer | none new: config input is already parsed by `PipelineConfig`; a user namespace with the derived name's text cannot reach the derived name, which is never registered | the derived name stays inside `for_relationship` and is absent from `declared()`, plan namespaces and the seed envelope | AT-E1.5 | add the derived name to `registry.declared()` |
| 7 | Check then use (TOCTOU) | the table-kind test and the edge resolution read the same config dict in one call | one call reads both; no file is checked then used | AT-E1.1 and AT-E1.3 run on one config object | read table kinds from a second parse of the YAML |
| 8 | Weak tests and overclaimed evidence | every acceptance test | each fail-before claim cites the probe or a file line; guards name their mutation | reviewer reruns the named mutations on the final head (catalog class 9) | removing a named mutation from the evidence record is a gate finding |
| 9 | Behavior-preserving refactor drift | E0 moves the behaviour table; C1 moves `_render_residual_pii` from `report.py` to `ui/summary.py` | move first with no change, then edit; existing tests stay unchanged apart from import paths | AT-E0.1; existing `test_integrity_human_output_names_each_residual_pii_column` and `..._survives_markup_like_column_names` | change a label in the moved table; drop the Rich `escape` call in the moved code |
| 10 | Frozen contract drift | `quality-policy/v1` result, `report fidelity --json`, quality-policy goldens, aggregate scores | keys only added, tag unchanged, aggregates unchanged, goldens and the shape snapshot re-pinned with a reason in the same slice; no cap or allowlist raised (catalog class 11) | AT-E2.6, AT-E2.8, AT-C1.6, AT-C1.7 | rename an existing policy key |

## 7. Enumerations

### 7.1 Exit paths

1. `decoy validate` / `validate compile` / `validate preflight` on a generate-only FK config: exit 0
   after E1 (today exit 1, `namespace_missing` from `relationships/_namespace.py:142`).
2. The same commands on a mask or mixed edge with no namespace, or an edge to an unknown table:
   exit 1, unchanged.
3. `decoy run` on a generate-only FK config: exit 0 after E1 on the full-frame route (today exit 1
   at the pre-run gate).
4. `report fidelity --mode fail` on a correct masking with no overrides: exit 0 after E2 (today 4,
   from the check in `quality/policy.py:315-357` and the exit in `src/decoy/cli/report.py:1835`).
5. `report fidelity --mode fail` with real drift on a kept-minimum strategy, an explicit override on
   an intended column, or a `--min-grade` the aggregate misses: exit 4, unchanged.
6. `report integrity`: exit codes unchanged (`src/decoy/cli/report.py:2046`); a no-entry leak stays
   exit 4.

### 7.2 Routes

The seven relationship-graph builders, all fed by `build_namespace_registry`, so all inherit the
exemption:

1. `plan/_compile.py:272` (compile, `validate compile`, the pre-run gate).
2. `execution/capacity.py:353` (`validate preflight`).
3. `execution/_job_estimate.py:139` (job estimate).
4. `execution/pipeline/_routing_facts.py:106` (route choice in `run_pipeline`).
5. `execution/physical/_snapshot.py:168` (physical plan snapshot).
6. `execution/_chunked_oracle.py:301` (chunked oracle; not reached for these jobs, see below).
7. CLI `src/decoy/cli/demo.py:257` (demo pipeline).

Route facts for a generate-only job with a `relationships:` block (unchanged in this row):

- `has_fk` is true (`execution/_planner.py:229`).
- The chunked route is refused with `chunked_relationships_unsupported` (`_planner.py:337`).
- Shadow generation declines with `config.relationships is non-empty`
  (`execution/physical/_shadow_generation.py:402`).
- Result: accepted on the full-frame route. V2-LOG-a covers treating these edges as non-FK.

### 7.3 FK shapes

1. Generate parent, generate child: derived namespace (new).
2. Mask parent, mask child: rule unchanged.
3. Mask parent, generate child: rule unchanged.
4. Generate parent, mask child: rule unchanged.
5. Composite keys follow the same rule; the derived name joins the columns with `__`, as the
   composite precedent does (`relationships/_namespace.py:333`).
6. Fan-out (several child tables to one parent key): one derived name for that parent key.
7. Edge to a table not in `tables:`: refused, unchanged.

### 7.4 Fields

- Policy result (`quality-policy/v1`): new `intended_columns` (list of column names with an
  intended-class strategy and no resolved minimum), `intended_joints` (list of sorted column pairs)
  and `pairwise_skipped` (absent, or `all_joints_intended`). Report schemas
  (`quality-fidelity/v1`, `quality-report/v1`) unchanged.
- Strategy rule after E2: intended loss, no default minimum: every strategy whose class in
  `contracts/distribution_behavior.py` is `preserves_cardinality_only`, `destroys_frequency` or
  `collapses`, minus `categorical`. Default minimum kept (`quality/policy.py:98-107`): `identity`
  1.00, `shuffle` 0.85, `bucketize` 0.30, `date_shift` 0.50, `generate` 0.30. Any other strategy:
  no default minimum, as today. Explicit overrides win over the intended class.
- Aggregates (`marginal.score`, `overall_score`, grade): unchanged; intended columns still count.
- Residual-PII finding: `source_identity_rate` (already in the record, `types.py:63`) gains a
  terminal column; `None` prints `-`.

### 7.5 Output surfaces

1. `report fidelity` table and note (`src/decoy/ui/summary.py:381`).
2. `report integrity` table (`src/decoy/cli/report.py:2063`, moved to `ui/summary.py` in C1).
3. `--help` of `report fidelity` (including `--min-grade`) and `report integrity`.
4. Explain topics `keys`, `transforms`, `modes` (`src/decoy/cli/explain.py`).
5. The `generate` template and `examples/generate_example.yaml`.
6. Engine docs `recipes.md`, `strategies.md`, `relationships.md`,
   `distribution-integrity/snapshot-and-fidelity.md`, `distribution-integrity/extending.md`,
   `distribution-integrity/index.md`.

## 8. Pre-mortem

- The derived namespace leaks into a masking path because a later change masks a column of a
  generate table. Today a table is mask or generate, never both (`config/_tables.py:476-494`), so a
  generate edge has no masked column. AT-E1.3 keeps the mixed cases refused, and AT-E1.5 keeps the
  name out of `declared()` and the seed envelope.
- Platform or CI users read `quality-policy/v1` verdicts and see fewer failures. That is the fix for
  replaced-value columns; drift on kept-minimum strategies and explicit overrides still fail
  (AT-E2.2, AT-E2.7).
- A user sets `--min-grade` and expects a correct hash masking to pass. It can still fail, because
  aggregates are unchanged in V1. The help line and note say so (AT-C1.8); V2-LOG-b is the fix.
- A new strategy is added to the behaviour table and is silently intended in fidelity. That is the
  wanted result (one table), and AT-E2.9 pins it; `extending.md` says so.
- The new banned pattern for `name.py:123` hits a path a user typed that is echoed in an error. The
  sentry scans string constants and help, not runtime messages, so user input is out of its scope.
- C1 and C2 conflict on `report.py`. C2 edits two docstrings only; the second to merge rebases.

## 9. Reuse inventory

- `config.classify_table_kinds`: the one table-kind classifier (E1).
- The composite derived-namespace pattern in `relationships/_namespace.py` (E1 name shape).
- `_STATIC_BEHAVIOR` and `distribution_behavior_for` (moved by E0): the one per-strategy statement
  of what a strategy does to values; E2 reads it in place of a new list.
- `_DEFAULT_STRATEGY_EXPECTATIONS` in `quality/policy.py`: the one place for per-strategy fidelity
  minimums (E2 deletes three entries from it).
- `report_warning_records`, `render_fidelity_report` and `make_table` in `src/decoy/ui/` (C1).
- `BANNED_USER_TEXT` and its sentry in `tests/sentry/cli_text/` (C2); no second scanner.
- The `_STRATEGY_NOTES` table in `explain.py` for the `faker` line (C2).

## 10. Frozen contracts

- `quality-policy/v1` (engine `docs/compatibility-contract.md` section 3.1): three keys added
  (`intended_columns`, `intended_joints`, `pairwise_skipped`), tag unchanged, verdicts change for
  intended-loss columns with no override and for pairwise checks over intended joints (owner
  question Q3, decided: yes).
- `quality-fidelity/v1` and `quality-report/v1`: unchanged, including `pairwise.joints`,
  `pairwise.score`, `marginal.score`, `overall_score` and the grade.
- `report fidelity --json` and `report integrity --json` shapes (CLI release-freeze snapshot):
  `report fidelity` gains the three policy keys; `report integrity` does not change.
- Exit codes: unchanged. A correct masking under `--mode fail` with no overrides moves from 4 to 0,
  which is the fix.
- Engine public API: `execution._distribution_behavior` is a private module; its move to
  `contracts.distribution_behavior` is the only path change. Reason codes: none added.

## 11. Placement

New production module: none. E0 moves one module from `execution/` to `contracts/` (engine CODEMAP
"Where Things Go": `contracts/` holds engine-owned contracts consumed across tiers; the
`.importlinter` tier list places it below both `quality` and `execution`). New test files and their
places:

| File | Directory | Map line that places it | Sits beside |
|---|---|---|---|
| `test_generate_only_edges.py` | engine `tests/unit/relationships/` | engine CODEMAP "Where Things Go" (unit tests mirror the package) | `test_namespace.py` |
| intended-loss cells (AT-E2.1 to AT-E2.4, AT-E2.7 to AT-E2.9) | extend engine `tests/unit/quality/test_policy.py` | same | - |
| `intended_hash_faker.sha256` | engine `tests/snapshots/golden/quality_policy/` | same | the four existing goldens |
| residual-PII cells | extend engine `tests/unit/detection_verification/test_bf4_residual_pii.py` | same | - |
| `test_items_di_reports.py` | CLI `tests/e2e/first_user/` | CLI CODEMAP line 68 (first-user QA item tests) | `test_items_reports.py` |
| `test_items_generate_fk.py` | CLI `tests/e2e/first_user/` | CLI CODEMAP line 68 | `test_items_generate.py` |
| new patterns and self-tests | extend CLI `tests/sentry/cli_text/_banned_text.py` and `test_user_text_internal_names.py` | CLI CODEMAP line 62 | - |

Banned-text shapes covered (class 5, listed before building): `name.py:123`, `BF1` to `BF99`, `the
platform's`. Not covered: line references written without `.py`, and ids in comments or in
docstrings of functions that are not commands (no user reads them).

## 12. Builder rules

- Commits: Conventional Commits subject, at most 72 characters, no body unless it explains why,
  final line `cam`. No file lists, test counts or tool trailers.
- Test depth: T0 the touched file's tests per edit, T1 impact-selected tests per commit and slice
  head, T2 gates on the exact head. E2 and C1 hit an escalation trigger (a frozen contract: the
  `quality-policy/v1` goldens and the `--json` shape snapshot), and E0 moves a module, so each runs
  the full suite once on its merge head against the saved main baseline. Tests run on the Mac or a
  test VM through `~/bin/vm-run`, never on the devbox.
- Review: E1, E2 and C1 (R2) get Dennis and Codex; E0 and C2 (R1) get Codex only.
- Each merge updates row 24e in `docs/ROADMAP.md`, and the CHANGELOG (CLI) or a changelog fragment
  (engine). The C1 merge also writes V2-LOG-a, V2-LOG-b and V2-LOG-c into the row's closing note.

## 13. Owner questions

All four are decided as recommended (coordinator, 2026-11-16).

- Q1. Items 4 to 6 and 8 to 12 are V2-LOG under the V1 bar. Build them in this row, or move them to
  the V2 backlog and strike checklist rows DOC-02, DOC-09, EVD-13 and GEN-16? Decided: build them
  here. They are about 350 lines, mostly text. The owner called this row's bugs V1 on 2026-11-08,
  and five checklist rows in waiting QA groups test them.
- Q2. Generate-only edges: derive an internal namespace (E1), or keep the refusal and change GATE-12
  to expect exit 1? Decided: derive. Nothing is masked on such an edge, so a namespace means nothing
  there; mixed and mask edges keep the rule.
- Q3. Fidelity: treat the value-replacing strategy classes as intended loss (no default
  value-identity minimum, overrides and shape check kept), add `intended_columns`,
  `intended_joints` and `pairwise_skipped` to `quality-policy/v1` without a tag change, and re-pin
  the goldens? Decided: yes. The keys are additions, the product is pre-release, and today a
  correct masking fails `--mode fail`.
- Q4. Checklist GEN-16 asks that the written YAML "says `mode: generate`". Change it to "carries no
  stale `mode:` text and validates"? Decided: yes, in C2.
- Q5 (new, not blocking this row). V2-LOG-b: leave intended columns out of `marginal.score`,
  `overall_score` and the grade in V2? It moves frozen numbers. Recommended: yes, in V2, with a
  `quality-fidelity/v2` tag.
