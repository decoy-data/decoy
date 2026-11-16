# CLI-QA1 close-out: the distribution-integrity items of row 24e

Status: plan (2026-11-16, not built). CLI and engine. Roadmap row 24e (CLI-QA1).

Every slice of `C:plan/cli-qa1` is merged. Row 24e stays open only for the items it lists under
"Also from the distribution-integrity QA". This plan checks each of those items against `origin/main`
(CLI `d8805373`, pins `decoy-engine==0.27.0`; engine `be2d36e0`, release `v0.27.0`) and plans the
ones that are still open. When the slices below merge, row 24e closes.

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
the owner keeps them in this row (owner question Q1).

| # | Item (row 24e text) | Source | Status on main | Bar | Slice |
|---|---|---|---|---|---|
| 1 | Traceback for a generate-only relationship with no `namespace` | DI:86-88 (H5) | FIXED. CLI #145 (`df418657`) root traceback guard, #148 (`6a175432`) uncompilable plan as a preflight fail, #181 (`6fafa5cd`) compile carries the config's relationships. Probe: `validate`, `validate compile`, `validate preflight` and `run` each exit 1 with one `namespace_missing` line and no traceback | - | none |
| 2 | `namespace` must not be required when nothing is masked | DI:88-89 (H5) | OPEN. Engine `NamespaceRegistry.for_relationship` (`relationships/_namespace.py:124-153`) raises `namespace_missing` for every edge with no namespace, whatever the table kinds. Probe: a two-table generate pipeline with a `relationships:` block and no namespace is refused (exit 1) by `validate` and `run`; the same pipeline without the block runs | V1 (a valid generate config cannot run; checklist GATE-12 expects exit 0) | E1, C1 |
| 3 | Fidelity "intended" marker: hash key columns not flagged | DI:93-101 (M1, M2) | PARTLY FIXED. "PASS grade F" is fixed by CLI #147 (`4eb43a52`): report mode prints `REPORT ONLY`. OPEN: `quality/policy.py` `_DEFAULT_STRATEGY_EXPECTATIONS` sets a 0.05 minimum for `hash`, `faker` and `redact`, whose value sets are disjoint by design. Probe: `report fidelity patients.csv out.csv --config mask.yaml --mode fail` on a correct hash and faker masking prints two violations (`patient_id`, `full_name`: expected 0.05, actual 0.0) and exits 4. No column is marked intended | V1 (a fidelity gate in fail mode fails a correct mask) | E2, C1 |
| 4 | No joint score across id spaces | DI:103-106 (M3) | OPEN, narrower than reported. Since CLI #189 a joint is scored only when the user passes `--joint`. Probe: `--joint patient_id,diagnosis` with `patient_id` hashed prints `diagnosisxpatient_id 0.000`. `fidelity --generate` without `--joint` prints no joint | V2-LOG | E2, C1 |
| 5 | `integrity` says configured columns are "not configured to be masked" | DI:119-121 (M6) | OPEN without `--config`. With `--config` the text is right (probe: `faker` info, `fpe` warning). Without it the CLI passes a config with no tables, and the engine (`verification/postmask/residual_pii.py:359-364`) says "was not configured to be masked", which it cannot know | V2-LOG | E2 |
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
  11. C2 corrects the checklist text (owner question Q4).

## 2. V1 behaviour

1. A relationship whose parent and child tables are both generate tables needs no `namespace`.
   `decoy validate`, `validate compile`, `validate preflight` and `run` accept it. The generated
   bytes are the same as for the same pipeline without the `relationships:` block. A relationship
   with a mask table on either side still needs a namespace and is refused with `namespace_missing`,
   as today.
2. Under `report fidelity --config`, a column masked with a strategy that replaces values by design
   (`hash`, `faker`, `fpe`, `redact`, `tokenize`) has no value-identity minimum. The policy result
   lists it as intended. The terminal marks it `intended` and prints one line: "Columns marked
   intended were masked with a strategy that replaces values, so a low score there is expected."
   The shape check (`shape_strategy_expectations`) does not change. `--mode fail` on a correct
   masking exits 0.
3. A `--joint` pair that names an intended column is listed as intended, is left out of the pairwise
   policy check, and prints `intended` in place of a score.
4. `report integrity` without `--config` does not claim a column was not configured. It says the
   config has no entry for the table, so the strategy is unknown. The residual-PII table shows the
   share of rows equal to the source (`source_identity_rate`) for each finding.
5. No user text (help, explain, templates) carries a source line reference, a `BF<n>` id or a
   platform reference. `explain keys` starts with which key goes with which job and fits about one
   screen. The CLI `faker` line says that the default draw does not keep equal values equal. No
   user-facing doc or template tells the user to write `mode: generate`. One bundled example
   generates a parent and a child table joined by a `reference` column.

## 3. Failure modes

- F1. The namespace exemption is too wide: a mixed edge (masked parent and generated child, or the
  reverse) passes without a namespace, and FK masking then has no key. Guard: AT-E1.3.
- F2. The derived namespace changes generated bytes or collides with a user namespace. Guard: AT-E1.2
  (bytes equal to the run without the block) and AT-E1.5 (a name a user cannot declare).
- F3. One of the five places that build a relationship graph (`plan/_compile.py`,
  `execution/capacity.py`, `execution/_job_estimate.py`, `execution/pipeline/_routing_facts.py`,
  `execution/physical/_snapshot.py`) builds its registry another way and still refuses. Guard:
  AT-E1.2 and AT-E1.4 go through `run_pipeline` and the capacity estimate.
- F4. The intended set is too wide and hides real drift on a shape-keeping strategy (`shuffle`,
  `bucketize`, `date_shift`). Guard: AT-E2.2.
- F5. The policy output changes in a way that breaks a reader of `quality-policy/v1`. The change only
  adds keys; goldens are re-pinned in the same slice with a reason, and the CLI `--json` shape
  snapshot is re-pinned in C1. Guard: AT-E2.6, AT-C1.6.
- F6. A new banned-text pattern also hits a legitimate user string (for example a file name a user
  gave). The patterns are limited to the shapes in section 11, with seeded self-tests. Guard: AT-C2.1.
- F7. Moving `_render_residual_pii` out of `report.py` changes the table for existing tests. Guard:
  the existing `test_integrity_human_output_*` tests stay green unchanged.

## 4. Acceptance tests (written first)

Each test fails on `origin/main` before its slice, unless it is marked "guard" (it passes before and
catches the named mutation). Builders may add tests; no builder may weaken these.

E1 (engine):

- AT-E1.1 `compile_plan` on a two-table generate config (`patients.patient_id` sequence,
  `visits.patient_id` reference) with a `relationships:` entry and no namespace returns a plan whose
  graph has one edge. Fail before: `NamespaceConfigError(namespace_missing)` (probe, same path).
- AT-E1.2 `run_pipeline` on that config writes the same bytes as on the same config with no
  `relationships:` block, same seed. Fail before: refused.
- AT-E1.3 (guard) a mask-only edge and both mixed edges with no namespace still raise
  `namespace_missing`, also when compiled in the same process right after the AT-E1.1 config.
  Mutation: drop the table-kind test in the exemption, or cache the generate-table set; red.
- AT-E1.4 the capacity estimate (`execution/capacity.py`) accepts the AT-E1.1 config. Fail before:
  `namespace_missing`.
- AT-E1.5 a user cannot declare the derived name (refused by the namespace name rule), and two
  generate-only edges get two different names. Fail before: no derived name exists.
- Review check (no new test): no file under engine `docs/` outside `docs/plans/`, `docs/records/` and
  `docs/audit/` tells the user to set a top-level `mode:` key or pass `--mode generate`. Before:
  `docs/recipes.md:154`.

E2 (engine):

- AT-E2.1 `apply_quality_policy` with `strategy_map={"patient_id": "hash", "full_name": "faker"}` and
  both similarities 0.0: no `column` violation; the result lists both in `intended_columns`. Fail
  before: two violations, expected 0.05, actual 0.0 (probe).
- AT-E2.2 (guard) a `shuffle` column at 0.5 still gives a `column` violation; a `bucketize` column
  below 0.30 still does. Mutation: skip every mapped strategy; red.
- AT-E2.3 a report with joint `(diagnosis, patient_id)` and `patient_id: hash`: the joint is listed
  as intended and a `pairwise` minimum does not fail on it. Fail before: no marker; the pairwise
  minimum fails.
- AT-E2.4 (guard) the shape check for `hash` still applies its 0.95 shape minimum.
- AT-E2.5 `check_residual_pii` with a config that has no entry for the table: the message for a hit
  says the config has no entry for the table, and never "was not configured to be masked". With the
  table present and the column absent, the message does not change (guard). Fail before: probe text.
- AT-E2.6 the `tests/snapshots/golden/quality_policy/` goldens: each golden that moves is re-pinned
  in this slice with a one-line reason per file; the `quality-policy/v1` tag does not change.

C1 (CLI, after the repin to the engine release that carries E1 and E2):

- AT-C1.1 (GATE-12) `decoy validate` on the AT-E1.1 config exits 0; `decoy run` writes both tables
  and every `visits.patient_id` is in `patients.patient_id`. Fail before: exit 1 (probe).
- AT-C1.2 (EVD-12) `decoy report fidelity src out --config cfg --mode fail` on a correct hash and
  faker masking exits 0; the table shows `intended` for both columns and prints the note line once.
  Fail before: exit 4 with two violations (probe).
- AT-C1.3 `--joint patient_id,diagnosis` with `patient_id` hashed prints `intended` for that joint,
  not `0.000`. Fail before: `0.000` (probe).
- AT-C1.4 (EVD-13) `decoy report integrity` without `--json` shows a "Same as source" column with
  the rate for each residual-PII row. Fail before: no such column (probe).
- AT-C1.5 (EVD-13) `decoy report integrity` without `--config` prints no "not configured to be
  masked". Fail before: two such lines (probe).
- AT-C1.6 the `--json` shape snapshot (`tests/fixtures/release_freeze/json-shapes.json`) is re-pinned
  for `report fidelity` with the added policy keys, and nothing else in it moves.
- AT-C1.7 (guard) `src/decoy/cli/report.py` does not grow (2,309 lines, over the cap).

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

## 5. Slices

| Slice | Repo | Risk | Content | Production files (estimate) | Lines | Depends on |
|---|---|---|---|---|---|---|
| E1 | engine | R2 | Item 2: generate-only edges get a derived namespace. Item 11 engine docs (`recipes.md`, `strategies.md:1251`) and a `docs/relationships.md` note. Changelog fragment | `src/decoy_engine/relationships/_namespace.py`, `docs/recipes.md`, `docs/strategies.md`, `docs/relationships.md` (4) | ~120 | none |
| E2 | engine | R2 | Items 3 and 4: intended-loss strategies in `quality/policy.py` (one table beside `_DEFAULT_STRATEGY_EXPECTATIONS`), `intended_columns` and intended joints in the policy result. Item 5: residual-PII text when the config has no entry for the table. One doc paragraph. Changelog fragment | `src/decoy_engine/quality/policy.py`, `src/decoy_engine/verification/postmask/residual_pii.py`, `docs/distribution-integrity/snapshot-and-fidelity.md` (3) | ~150 | none |
| R | engine, CLI | standard repin | Engine release with E1 and E2, then the CLI repin by the engine repin checklist | release files only | - | E1, E2 |
| C1 | CLI | R2 (frozen `--json` shape re-pin) | Items 2, 3, 4, 6 in the CLI: render `intended` and the note, intended joints, the "Same as source" column; move `_render_residual_pii` to `src/decoy/ui/summary.py`; GATE-12 e2e; CHANGELOG | `src/decoy/ui/summary.py`, `src/decoy/cli/report.py` (2) | ~120 | R |
| C2 | CLI | R1 | Items 8 to 12 in the CLI: docstrings of `report fidelity` and `report integrity`, banned patterns, template comment, `explain keys` rewrite, `faker` note, `explain modes` history line, FK example, checklist GEN-16 text; CHANGELOG | `src/decoy/cli/report.py`, `src/decoy/cli/explain.py`, `src/decoy/templates/generate.yaml`, `examples/generate_example.yaml`, `docs/qa/cli-v1-checklist.md` (5) | ~200 | none |

E1, E2 and C2 can run in parallel (different repos or different files). C1 and C2 both touch
`report.py`; C2 changes only two docstrings, so whichever merges second rebases. C1 merges last, and
the row closes when C1 merges.

New public names: none. E2 adds two keys to the `quality-policy/v1` result dict
(`intended_columns`, and an `intended` flag on joint entries).

Design notes:

- E1: `build_namespace_registry(config, profile)` already reads the config. It records the set of
  generate tables from `config.classify_table_kinds` (the one table-kind classifier, guarded by
  `tests/sentry/test_table_kind_classifier.py`). Only when both tables are generate tables does
  `for_relationship` return a derived name in place of the raise. The name follows the composite
  precedent (`composite/<table>/<members>`, `_namespace.py:333`): `generated/<parent_table>/<columns
  joined by __>`. No column is bound to it, so a generate path that reads `for_column` sees no
  change. No new reason code. Every graph builder goes through `build_namespace_registry`; the
  builder confirms this for the five sites in F3 and names them in the PR.
- E2: the intended set lives in `quality/policy.py`, beside the expectation table. It replaces three
  entries of that table (`hash`, `faker`, `redact`) and adds `fpe` and `tokenize`, which have no
  entry today. The strategy trait sets elsewhere (`residual_pii.py`, `_leakage.py`) answer other
  questions and stay as they are; this slice does not widen that class.
- C1: `report.py` is over the size cap, so C1 moves `_render_residual_pii` into `ui/summary.py` (the
  CODEMAP "Terminal output" line already places `report fidelity` text there) and adds the new column
  in the moved code.

## 6. Class table

| # | Class | Applies here | Structure that closes it | Test | Mutation that turns it red |
|---|---|---|---|---|---|
| 1 | Value-bearing output | the new "Same as source" column, the intended note, the derived namespace name, residual-PII text | the column prints a rate, the note is fixed text, the derived name is built from table and column names only, residual-PII text names detector, table and strategy only | AT-C1.4, AT-E1.5, AT-E2.5 | print the finding's `message` from the source frame in place of the rate |
| 2 | Cleanup missing on an exit path | `decoy run` on a generate-only FK config, the only path these slices newly open | the existing run publication (atomic run folder) is reused; no slice adds a write | AT-C1.1 (a run writes both tables in one run folder) | write the child table outside the run folder |
| 3 | Stale state | the namespace registry, rebuilt on every compile from config and profile | the generate-table set is computed inside `build_namespace_registry` from the same config, never cached | AT-E1.3 (same process: a generate config then a mixed config, the second still refused) | cache the generate-table set at module level |
| 4 | Route parity | the five graph builders in F3; `validate` vs `run` | one registry builder for every route | AT-E1.2, AT-E1.4, AT-C1.1 | build the exemption inside `compile_plan` only |
| 5 | Referential integrity | mixed and mask FK edges keep their namespace rule; generated child keys resolve | exemption only when both tables are generate tables | AT-E1.3, AT-C1.1 | drop the table-kind test |
| 6 | Untrusted producer | none new: config input is already parsed by `PipelineConfig`; a user cannot declare the derived name | the namespace name rule | AT-E1.5 | allow `/` in a declared namespace |
| 7 | Check then use (TOCTOU) | the table-kind test and the edge resolution read the same config dict in one call | one call reads both; no file is checked then used | AT-E1.1 and AT-E1.3 run on one config object | read table kinds from a second parse of the YAML |
| 8 | Weak tests and overclaimed evidence | every acceptance test | each fail-before claim cites the probe or a file line; guards name their mutation | reviewer reruns the named mutations on the final head (catalog class 9) | removing a named mutation from the evidence record is a gate finding |
| 9 | Behavior-preserving refactor drift | C1 moves `_render_residual_pii` from `report.py` to `ui/summary.py` | move first with no change, then add the column; existing tests stay unchanged | existing `test_integrity_human_output_names_each_residual_pii_column` and `..._survives_markup_like_column_names` | drop the Rich `escape` call in the moved code |
| 10 | Frozen contract drift | `quality-policy/v1` result, `report fidelity --json`, quality-policy goldens | keys only added, tag unchanged, goldens and the shape snapshot re-pinned with a reason in the same slice; no cap or allowlist raised (catalog class 11) | AT-E2.6, AT-C1.6 | rename an existing policy key |

## 7. Enumerations

### 7.1 Exit paths

1. `decoy validate` / `validate compile` / `validate preflight` on a generate-only FK config: exit 0
   after E1 (today exit 1, `namespace_missing` from `relationships/_namespace.py:142`).
2. The same commands on a mask or mixed edge with no namespace: exit 1, unchanged.
3. `decoy run` on a generate-only FK config: exit 0 after E1 (today exit 1 at the pre-run gate).
4. `report fidelity --mode fail` on a correct masking: exit 0 after E2 (today 4, from the check in
   `quality/policy.py:315-357` and the exit in `src/decoy/cli/report.py:1835`).
5. `report fidelity --mode fail` with real drift on a kept-minimum strategy: exit 4, unchanged.
6. `report integrity`: exit codes unchanged (`src/decoy/cli/report.py:2046`).

### 7.2 Routes

The five relationship-graph builders, all fed by `build_namespace_registry`:

1. `plan/_compile.py:272` (compile, `validate compile`, the pre-run gate).
2. `execution/capacity.py:353` (`validate preflight`).
3. `execution/_job_estimate.py:139` (job estimate).
4. `execution/pipeline/_routing_facts.py:106` (route choice in `run_pipeline`).
5. `execution/physical/_snapshot.py:168` (physical plan snapshot).

### 7.3 FK shapes

1. Generate parent, generate child: derived namespace (new).
2. Mask parent, mask child: rule unchanged.
3. Mask parent, generate child: rule unchanged.
4. Generate parent, mask child: rule unchanged.
5. Composite keys follow the same rule; the derived name joins the columns with `__`, as the
   composite precedent does (`relationships/_namespace.py:333`).

### 7.4 Fields

- Policy result (`quality-policy/v1`): new `intended_columns` (list of column names) and an
  `intended` flag on each joint entry the pairwise check skips.
- Strategy rule after E2: intended loss, no minimum: `hash`, `faker`, `fpe`, `redact`, `tokenize`.
  Minimum kept (`quality/policy.py:98-107`): `identity` 1.00, `shuffle` 0.85, `bucketize` 0.30,
  `date_shift` 0.50, `generate` 0.30. Any other strategy: no default minimum, as today.
- Residual-PII finding: `source_identity_rate` (already in the record, `types.py:63`) gains a
  terminal column.

### 7.5 Output surfaces

1. `report fidelity` table and note (`src/decoy/ui/summary.py:381`).
2. `report integrity` table (`src/decoy/cli/report.py:2063`, moved to `ui/summary.py` in C1).
3. `--help` of `report fidelity` and `report integrity`.
4. Explain topics `keys`, `transforms`, `modes` (`src/decoy/cli/explain.py`).
5. The `generate` template and `examples/generate_example.yaml`.
6. Engine docs `recipes.md`, `strategies.md`, `relationships.md`,
   `distribution-integrity/snapshot-and-fidelity.md`.

## 8. Pre-mortem

- The derived namespace leaks into a masking path because a later change masks a column of a
  generate table. Today a table is mask or generate, never both (`config/_tables.py:476-494`), so a
  generate edge has no masked column. AT-E1.3 keeps the mixed cases refused.
- Platform or CI users read `quality-policy/v1` verdicts and see fewer failures. That is the fix for
  replaced-value columns; drift on kept-minimum strategies still fails (AT-E2.2).
- The new banned pattern for `name.py:123` hits a path a user typed that is echoed in an error. The
  sentry scans string constants and help, not runtime messages, so user input is out of its scope.
- C1 and C2 conflict on `report.py`. C2 edits two docstrings only; the second to merge rebases.

## 9. Reuse inventory

- `config.classify_table_kinds`: the one table-kind classifier (E1).
- The composite derived-namespace pattern in `relationships/_namespace.py` (E1 name shape).
- `_DEFAULT_STRATEGY_EXPECTATIONS` in `quality/policy.py`: the one place for per-strategy fidelity
  rules; the intended set sits beside it (E2).
- `report_warning_records`, `render_fidelity_report` and `make_table` in `src/decoy/ui/` (C1).
- `BANNED_USER_TEXT` and its sentry in `tests/sentry/cli_text/` (C2); no second scanner.
- The `_STRATEGY_NOTES` table in `explain.py` for the `faker` line (C2).

## 10. Frozen contracts

- `quality-policy/v1` (engine `docs/compatibility-contract.md` section 3.1): keys added only, tag
  unchanged, verdicts change for intended-loss columns (owner question Q3).
- `report fidelity --json` and `report integrity --json` shapes (CLI release-freeze snapshot):
  `report fidelity` gains the added policy keys; `report integrity` does not change.
- Exit codes: unchanged. A correct masking under `--mode fail` moves from 4 to 0, which is the fix.
- Engine public API: no new or removed names. Reason codes: none added.

## 11. Placement

No new production module. New test files and their places:

| File | Directory | Map line that places it | Sits beside |
|---|---|---|---|
| `test_generate_only_edges.py` | engine `tests/unit/relationships/` | engine CODEMAP "Where Things Go" (unit tests mirror the package) | `test_namespace.py` |
| `test_policy_intended.py` | engine `tests/unit/quality/` | same | `test_fidelity.py` |
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
  `quality-policy/v1` goldens and the `--json` shape snapshot), so each runs the full suite once on
  its merge head against the saved main baseline. Tests run on the Mac or a test VM through
  `~/bin/vm-run`, never on the devbox.
- Review: E1, E2 and C1 (R2) get Dennis and Codex; C2 (R1) gets Codex only.
- Each merge updates row 24e in `docs/ROADMAP.md`, and the CHANGELOG (CLI) or a changelog fragment
  (engine).

## 13. Owner questions

- Q1. Items 4 to 6 and 8 to 12 are V2-LOG under the V1 bar. Build them in this row, or move them to
  the V2 backlog and strike checklist rows DOC-02, DOC-09, EVD-13 and GEN-16? Recommended: build
  them here. They are about 350 lines, mostly text. The owner called this row's bugs V1 on
  2026-11-08, and five checklist rows in waiting QA groups test them.
- Q2. Generate-only edges: derive an internal namespace (E1), or keep the refusal and change GATE-12
  to expect exit 1? Recommended: derive. Nothing is masked on such an edge, so a namespace means
  nothing there; mixed and mask edges keep the rule.
- Q3. Fidelity: treat `hash`, `faker`, `fpe`, `redact` and `tokenize` as intended loss (no
  value-identity minimum, shape check kept), add `intended_columns` and intended joints to
  `quality-policy/v1` without a tag change, and re-pin the goldens? Recommended: yes. The keys are
  additions, the product is pre-release, and today a correct masking fails `--mode fail`.
- Q4. Checklist GEN-16 asks that the written YAML "says `mode: generate`". Change it to "carries no
  stale `mode:` text and validates"? Recommended: yes, in C2.
