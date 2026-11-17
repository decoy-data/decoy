# CLI journey and QA checklist: rows 75 and 92a

Status: plan

Date: 2026-11-17. Author: Opus planner. Base: CLI `origin/main` `b6f8558`. Line numbers below are
from that head.

Rules consulted: `dev-rules/README.md`, `dev-rules/00-universal.md`,
`dev-rules/risk-and-exceptions.md`, `dev-rules/development-loop.md` (PLAN),
`dev-rules/profiles/local-operations.md`, `dev-rules/catalogs/recurring-defects.md`,
`dev-rules/testing.md` (Test depth), `dev-rules/proportionality.md`, `dev-rules/reuse-first.md`,
`dev-rules/architecture.md`, `dev-rules/cross-cutting-concerns.md`, `dev-rules/documentation.md`,
`dev-rules/workspace-and-vcs.md` (Commit messages); CLI `CLAUDE.md` and `CODEMAP.md` ("Where
Things Go"); memories decoy-v1-pipeline-baseline, decoy-v1-ux-direction-2026-11-05,
plan-defines-acceptance-tests, v1-bar-blocking-criteria, best-practice-becomes-a-sentry.

## 1. Scope and guarantee

Two roadmap rows, nothing else:

- Row 75: "One CLI journey for V1; the CLI smoke cites journey ids". State NOT STARTED, After: CLI
  delivery (row 61).
- Row 92a: CLI-QA-CHECKLIST. State DONE 2026-11-15 (CLI #269, `1825e45a`):
  `docs/qa/cli-v1-checklist.md` and `docs/qa/cli-v1-run-template.md` exist and already mirror the
  engine checklist (groups in place of the engine's sections, stable ids, conventions, a recording
  rule, a run template). The remainder this plan builds is what the brief asks for and the merged
  file does not hold: every check names its exit codes in its own column, and a sentry keeps the
  file's shape true.

Guarantee:

1. `docs/qa/cli-v1-journey.md` defines one CLI V1 journey as numbered steps `CJ-01` to `CJ-12`.
   Each step names a baseline stage, its command, its exit codes, its expected value-free output and
   the slice it lands with.
2. One e2e test per step cites the step id. The release smoke file cites the ids its cells cover.
3. A sentry fails when a journey id is not cited, when a cited id does not exist, when an exit code
   is not in `decoy.cli.exit_codes`, or when a step that is not on main yet is not a strict expected
   failure.
4. Every check row of `docs/qa/cli-v1-checklist.md` has an `Exit` column, and a sentry fails on a
   malformed row, an unknown exit code, a broken id sequence, a wrong count, an index entry that
   names no check, or a fixture value in a check cell.

Non-goals: no production code change (no file under `src/`); no new command, flag, exit code or JSON
shape; no change to the canonical bundle smoke (`packaging_tools/smoke_install.py`) or its
`decoy-release-smoke/v1` summary (owner Q1); no platform change (platform journey J15 stays as it
is, owner Q4); no per-group "Open points" sections like the engine's (the CLI checklist keeps its
notes inline); no QA run. A journey step that fails on main is a finding filed as a roadmap row,
not fixed in these slices.

Size: about 1,250 lines over two slices, all tests and docs. New public names (test side only): the
`journey_step` decorator and the `read_journey` parser in `tests/e2e/journey/journey_doc.py`. No
production file.

Risk: R1 for both slices (tests and docs only, no data handling, no production code, no workflow
change). Approver for the plan: one review round, per the proportion rule for small low-risk rows.

## 2. What already exists (reuse inventory)

- `docs/qa/cli-v1-checklist.md` (615 lines): 16 groups, 204 checks, the table header
  `| Id | Command | Expected | Rows | Pass/fail |` in every group (first at line 149). 120 of the
  204 checks state no exit code in their Expected cell. DOC-05 (line 479) reserves the journey:
  "**Not built.** Each journey id runs end to end; the release smoke cites the ids", row 75.
- `docs/qa/cli-v1-run-template.md`: the per-group record. Its Results table has no exit column.
- `tests/e2e/test_release_smoke.py`: the in-repo release smoke. Cells for `--version`, templates
  list, demo, the canonical run of the minimal template, help and explain. It cites no journey id.
- `.github/workflows/release-smoke.yml`: the wheel smoke on tags and weekly; runs the same three
  cells against a built wheel.
- `packaging_tools/smoke_install.py` with `SMOKE_STEPS` in `packaging_tools/candidate.py`: the
  canonical signed-bundle smoke that REL-GATE counts. Its step names are part of the
  `decoy-release-smoke/v1` summary that `scripts/release/record_smoke.py` checks.
- `src/decoy/cli/exit_codes.py`: the one exit-code registry (public `EXIT_OK` to `EXIT_PARTIAL`,
  private `_EXIT_INTERRUPTED` 130).
- `P:docs/product/journeys.md` and `P:tests/sentry/test_journeys_doc.py`: the platform journey list
  and its shape guard (fixed field labels, numbered Steps and Expected of equal length, a `Lands
  with` field, a mark that fails the guard once it is no longer true). The CLI journey copies that
  shape.
- `E:tests/sentry/test_qa_checklist_reasons.py`: the engine sentry that every reason code its QA
  checklist names is registered. The CLI checklist sentry is its analogue for exit codes.
- Sentry plumbing: `SENTRIES` in `tests/sentry/test_sentry_manifest.py`, and `tests/sentry/release/`
  (two sentries today).
- CI: `pytest tests/e2e` in `.github/workflows/ci.yml` already collects any new
  `tests/e2e/<package>/`; no lane or marker change.
- Subset inside a run (row 57, merged) with an e2e model in `tests/e2e/test_run_subset.py`; the mask
  secret helpers in `tests/keyed_secret.py`.

The only new machinery is the journey document, one small parser and decorator, one journey test
module and two sentries.

## 3. Established solutions

Search run (web and codebase): "pytest requirement traceability marker plugin requirement ids".
Found: jamb (a `requirement` marker taking requirement UIDs, plus a coverage check that lists
unknown UIDs), pytest-requirements, pytest-mark-ac (an acceptance-criteria marker) and pytest-gxp
(IQ/OQ/PQ traceability). All use one pattern: a test carries the requirement id, and a collector
checks both directions (every requirement covered, every cited id known). In the codebase the
platform journey guard and the engine checklist-reasons sentry apply the same pattern to Markdown.

The design follows that pattern without a plugin. Twelve ids and two sentries do not justify a new
dependency, a registered pytest marker (a test-config change, which is a full-suite trigger) or a
traceability tree format. The decorator is a plain function that adds a known attribute and, for a
step not on main, `pytest.mark.xfail(strict=True)`. Strict xfail is pytest's own way to say "this
must fail until X lands" and to fail loudly once X lands.

## 4. Behaviour

### 4.1 The journey document

`docs/qa/cli-v1-journey.md`, `Status: current`. One journey: the V1 pipeline baseline on the CLI
(source, subset, pre-scan, mask per table, post-scan, delivery), plus the vault. The user is one
person with two related CSV files on disk (`customers`, `orders`, `orders.customer_id` referencing
`customers.id`).

Each step is a level-3 heading `### CJ-NN: <title>` followed by exactly these labelled lines:

- `**Stage:**` one of `install`, `project`, `source`, `subset`, `pre-scan`, `mask`, `post-scan`,
  `delivery`, `evidence`, `vault`, `refusal`.
- `**Command:**` the commands in backticks, written as a user types them.
- `**Exit:**` exit codes in order of the commands, comma separated, each a value of
  `decoy.cli.exit_codes` (0 to 6) or 130.
- `**Expected:**` what the user sees, in the user's words, value-free: tables, columns, files, counts
  and reason codes, never a cell value or the secret.
- `**Lands with:**` `main`, or `row <N>` when the step's behaviour is not on main yet.

The steps. The builder confirms each flag against `--help` at the slice base; a step that cannot run
as written on main is reported to the planner, not reworded to pass.

| Id | Stage | Command | Exit | Expected (value-free) | Lands with |
|---|---|---|---|---|---|
| CJ-01 | install | `decoy --version` | 0 | Prints `decoy` and a version | main |
| CJ-02 | project | `decoy project new shop --json` | 0 | The project folder with `.decoy/` and `pipelines/`; JSON names paths only | main |
| CJ-03 | source | `decoy init customers --source data/customers.csv --json -y` | 0 | `pipelines/customers/pipeline.yaml` written; the record names columns and starter strategies | main |
| CJ-04 | pre-scan | `decoy scan shop --json` | 0 | Tables, columns, detected categories and counts; no cell value | main |
| CJ-05 | refusal | `decoy validate bad --json` on a copy with an unknown key and a wrong-typed value | 1 | One `decoy-error/v1` object naming the key and a code; the wrong value is not echoed; no run folder | main |
| CJ-06 | source | `decoy validate shop` | 0 | Config, compile and preflight pass | main |
| CJ-07 | subset | `decoy run shop --mask-secret env:JOURNEY_SECRET --json` with a `subset:` block on `customers` | 0 | `--json` has a `subset` object with kept and total counts across both tables; every kept `orders` row has its parent | main |
| CJ-08 | mask | `decoy run shop --mask-secret env:JOURNEY_SECRET --json` (the CJ-07 run; this step checks its outputs) | 0 | Masked columns differ from the input, passthrough columns match, row counts match the subset, input files unchanged | main |
| CJ-09 | post-scan | `decoy report integrity <masked> --source <input> --json` | 0 | No residual finding; FK check clean; names and counts only | main |
| CJ-10 | evidence | `decoy report verify <manifest>`, then the same after one output byte changes | 0, 4 | First all fingerprints match; then the changed file is named | main |
| CJ-11 | vault | `decoy run` with `vault: true` on one column, then `decoy unmask` on its output | 0, 0 | The unmasked column equals the input (checked by the test, never printed) | main |
| CJ-12 | delivery | `decoy run shop` with a forced failure on `orders` under strict delivery | 3 | Nothing delivered under the delivery root; the reason code names the table | row 61 |

The sentry checks that the stages `source`, `subset`, `pre-scan`, `mask`, `post-scan`, `delivery`
and `vault` each have at least one step, so a baseline stage cannot drop out unseen. CI use is
covered by checklist group 13, not by the journey (owner Q5).

### 4.2 The journey test

`tests/e2e/journey/test_cli_journey.py`. One module fixture builds the project under
`tmp_path_factory` once and runs the steps in id order, caching each result (exit codes, stdout,
stderr, files written). Each test is decorated `@journey_step("CJ-NN")` and asserts only its own
step: the exit codes read from the document through `read_journey` (never copied into the test),
and the Expected facts.

- Commands run as subprocesses. Default argv prefix `[sys.executable, "-m", "decoy"]`. When
  `DECOY_JOURNEY_BIN` is set, its value is the `decoy` executable, so QA (DOC-05) and the release
  candidate pass run the same test against the installed bundle.
- Every text cell of the fixture data carries `jmark` plus a number; the secret is 48 random bytes
  in `JOURNEY_SECRET`. After each step a sweep checks stdout, stderr, `--json`, evidence and the run
  folder (not the masked data files) for any marker or the secret. A hit fails that step.
- `journey_step(id)` reads the document once. If the step's `Lands with` is not `main` it applies
  `pytest.mark.xfail(strict=True, reason="lands with row N")`. When the row lands the test passes,
  strict xfail turns that into a failure, and the slice that lands the row sets `Lands with: main`.
- `tests/e2e/test_release_smoke.py` decorates the cells that cover a step: `--version` with CJ-01
  and the canonical run with CJ-08. A step may be cited by the release smoke and by the journey
  module; the journey module cites each id exactly once.

### 4.3 The checklist Exit column

Every check table in `docs/qa/cli-v1-checklist.md` gets the header
`| Id | Command | Exit | Expected | Rows | Pass/fail |`. The Exit cell grammar (full match):

- a comma-separated list of codes, one per command in the check, in order, each 0 to 6 or 130; or
- `none` when the check runs no `decoy` command (reading a document, a CI result); or
- `tbd` only on a check whose Expected starts with `**Not built.**`; the code is set when its row
  merges, before its group's pass.

Exit codes move out of the Expected text where they were written there, so each code is stated
once. The builder sets each code from the code path at the slice base (`exit_code_for`,
`RUN_EXIT_MAP`, the command's own exits), not from memory; "non-zero" (RUN-03 and others) becomes
the exact code. A built check whose exit the builder cannot find in code is listed in the slice
report as a finding for the planner, not set to `tbd`.

DOC-05 changes from "Not built" to: "Run `tests/e2e/journey/` with `DECOY_JOURNEY_BIN` set to the
installed `decoy`; every step passes or is an expected failure for its row. Steps in
[cli-v1-journey.md](cli-v1-journey.md)." The run template's Results table gains an `Exit observed`
column.

## 5. Failure modes

- A journey id in the document that no test cites: the step silently stops being tested. Sentry.
- A test cites an id the document dropped or renamed. Sentry.
- A step whose behaviour is not on main is written as `Lands with: main`, so the journey goes red on
  every PR. The journey test catches it; the rule is that a red step on main is filed as a row and
  marked with that row, never deleted.
- A step lands but its xfail stays: strict xfail fails the run.
- A builder copies exit codes into the test instead of reading the document, so the two drift.
  Sentry: the journey module compares no `returncode` with an integer literal (AST check).
- The sweep checks the wrong files and passes vacuously. Each sweep asserts it read at least one
  non-empty capture.
- `DECOY_JOURNEY_BIN` points at a missing file: the fixture fails with a message naming the
  variable and never falls back to the source tree.
- Checklist: a row with a missing or extra cell, which renders and reads wrong. Sentry counts cells.
- An exit code not in the registry (`7`), or a stale `tbd` on a built check. Sentry.
- A pasted fixture value in a check cell, which would teach a tester that echoing is fine. Sentry.
- The Groups table says `INST-01 to INST-19` and the group holds 18. Sentry.
- Steps share state, so one early failure fails later steps. Accepted: the first red step is the
  cause, and each later test names the step it waited on.

## 6. Enumerations

### Exit paths

- Codes the journey and the checklist may name: `EXIT_OK` to `EXIT_PARTIAL`
  (`src/decoy/cli/exit_codes.py:45`, `src/decoy/cli/exit_codes.py:82`,
  `src/decoy/cli/exit_codes.py:103`) and 130 (`src/decoy/cli/exit_codes.py:111`). The sentries
  import the public `EXIT_` names and add 130; they keep no list of their own.
- Journey exits used: 0 (CJ-01 to CJ-11), 1 (CJ-05), 4 (CJ-10, second command), 3 (CJ-12).
- Sentry outcomes: pytest pass or fail only. No new process exit anywhere.

### Routes

- In-memory `decoy run`: CJ-07, CJ-08, CJ-11. The chunked route refuses `subset:`
  (`config.subset_run_unsupported`, see the docstring at `tests/e2e/test_run_subset.py:6`), so the
  journey does not use `--chunked`; route coverage stays with checklist group 5.
- Source checkout (default) and installed bundle (`DECOY_JOURNEY_BIN`): the same test on both.

### FK shapes

- One single-column FK, `orders.customer_id` to `customers.id`, both masked with `hash` in one
  namespace, so CJ-07 can check every kept child has its parent after masking.
- Other FK shapes are out of scope here; checklist RUN and DLV checks and engine QA section 11 own
  them.

### Fields

- Journey step fields: `Stage`, `Command`, `Exit`, `Expected`, `Lands with`, each once per step.
- Checklist check cells: `Id`, `Command`, `Exit`, `Expected`, `Rows`, `Pass/fail` (blank in the
  checklist). Today's five-cell header is at `docs/qa/cli-v1-checklist.md:149`.
- Run template Results cells: `Id`, `Platform`, `Exit observed`, `Result`, `Notes (value-free)`.

### Output surfaces

- The journey sweep covers stdout, stderr, `--json` objects, evidence manifests and the run folder
  of each step, as the checklist's marker sweep does (`docs/qa/cli-v1-checklist.md:121`).
- No new output surface: no log site, no file written outside `tmp_path`, no JSON shape. The release
  smoke cells gain decorators only (`tests/e2e/test_release_smoke.py:54`,
  `tests/e2e/test_release_smoke.py:113`).

## 7. Defect-class audit

Classes from the plan contract catalog, cross-checked with `dev-rules/catalogs/recurring-defects.md`.

| # | Class | Closing structure | Sentry or test | Mutation that turns it red |
|---|---|---|---|---|
| 1 | Value-bearing output | Fixture cells carry markers; every step sweeps its captures; the checklist sentry refuses fixture values in check cells | AT-J6, AT-Q5 | Make `emit_error` in `src/decoy/ui/output.py` append the offending value (local, not committed); paste `qamark0001@example.invalid` in an Expected cell |
| 2 | Cleanup missing | Every journey file lives under `tmp_path_factory`; the fixture asserts nothing was written under the repo or `$HOME` | AT-J7 | Point the project root at the repo checkout |
| 3 | State and ordering between steps | One module fixture runs steps in id order and caches results; a test reads only its own step | AT-J8 | Run CJ-08's check before CJ-07 in the fixture |
| 4 | Route parity and silent fallback | `DECOY_JOURNEY_BIN` set means the installed binary only; a missing binary fails | AT-J9 | Fall back to `python -m decoy` when the path is missing |
| 5 | Referential integrity | CJ-07 checks every kept `orders` row has a kept parent after masking | AT-J6 (CJ-07 cell) | Drop the FK from the journey YAML so `orders` subsets on its own |
| 6 | Untrusted producer | The two parsers read only repo docs, full-match every field and refuse an unknown label | AT-J1, AT-Q1 | Accept an unknown `**Owner:**` label silently |
| 7 | Check then use on a path | N/A: the slices read repo documents and `tmp_path` files they wrote themselves; no path is checked and then opened by another party |
| 8 | Weak tests | Every AT names a mutation; sweeps assert non-empty input; the journey reads exits from the doc | AT-J10, AT-J6 | Compare `returncode` with a literal `0` in the journey module |
| 9 | Refactor drift | N/A: nothing is moved or split; the checklist edit adds a column and moves exit text, held by the counts in AT-Q3 |
| 10 | Frozen contract drift | No exit code, JSON shape, command or smoke summary changes; the release smoke gains decorators only | AT-F1 | Rename a `SMOKE_STEPS` entry or add an exit constant |

From the dev-rules catalog: class 1 (anchored validation) applies to every id, stage and exit token,
all checked with `re.fullmatch`. Class 5 (normalized scanners) applies to the citation scanner,
which reads decorator calls through the AST and covers `journey_step("CJ-01")`, an import alias
(`from tests.e2e.journey.journey_doc import journey_step as js`) and the attribute form
(`journey_doc.journey_step(...)`). Ids built at run time are deliberate evasion, V2-LOG. Class 11
(no raised caps): no cap, pin, baseline or allowlist moves.

## 8. Hostile corpus / acceptance tests red first

Each test is written first. "Fails before" is why it is red on the base head. A builder may add
tests and must not weaken these. Mutations run on the slice's final head and the head is recorded
in the slice report.

Slice JQ-1 (journey):

| Id | Test | Fails before | Mutation |
|---|---|---|---|
| AT-J1 | `tests/sentry/release/test_journey_ids.py::test_journey_doc_shape`: ids `CJ-01` to `CJ-NN` contiguous and unique; each step has the five labels once; Stage, Exit and Lands with full-match their grammar; the seven baseline stages each have a step | The document does not exist | Delete the pre-scan step; add a stray token after an Exit value |
| AT-J2 | `test_every_journey_id_is_cited`: each id is cited exactly once in `tests/e2e/journey/` | No citations exist | Remove `@journey_step("CJ-04")` |
| AT-J3 | `test_every_cited_id_exists`: every `journey_step` call under `tests/` names a document id | No scanner | Cite `CJ-99` in `test_release_smoke.py` |
| AT-J4 | `test_exit_tokens_are_registered`: every Exit token is a public `EXIT_` value or 130 | No document | Set CJ-05's Exit to `7` |
| AT-J5 | `test_unbuilt_steps_are_strict_xfail`: `journey_step` on a `row N` step yields an `xfail` mark with `strict=True`, and on a `main` step yields none | No decorator | Drop `strict=True` in the decorator |
| AT-J6 | `tests/e2e/journey/test_cli_journey.py`, one test per step, each asserting its exit codes, its Expected facts and a clean sweep | No module | The class 1 and class 5 mutations in section 7 |
| AT-J7 | The fixture asserts the repo tree and `$HOME` gained no file during the module | No fixture | Point the project root at the repo |
| AT-J8 | The fixture records step order; CJ-08's test asserts CJ-07 ran first | No fixture | Swap the order |
| AT-J9 | With `DECOY_JOURNEY_BIN` set to a missing path the fixture errors with a message naming the variable | No fixture | Fall back to `python -m decoy` |
| AT-J10 | `test_journey_module_reads_exits_from_doc`: the journey module's AST has no `returncode` compared with an int literal | No module | Write `assert r.returncode == 0` |
| AT-J11 | `test_release_smoke_cites_journey`: `test_release_smoke.py` cites CJ-01 and CJ-08 | No citations | Remove one decorator |

Slice JQ-2 (checklist):

| Id | Test | Fails before | Mutation |
|---|---|---|---|
| AT-Q1 | `tests/sentry/release/test_qa_checklist_shape.py::test_check_tables_have_six_cells`: every table under a group heading has the six-cell header and six cells per row | The header has five cells today | Drop the Exit cell of one row |
| AT-Q2 | `test_exit_cells_parse`: full-match grammar; codes from the registry; `tbd` only with `**Not built.**` | No Exit column | `7`; `tbd` on GATE-01 |
| AT-Q3 | `test_ids_and_counts`: ids unique and contiguous per prefix; each group's range in the Groups table matches its rows; the total in "Sixteen groups, 204 checks." equals the row count | No sentry (true today, guarded from now) | Duplicate RUN-05; change 204 to 205 |
| AT-Q4 | `test_row_index_names_real_checks`: every id or range in the row index exists, and each check's Rows cell lists rows whose index line names that check | No sentry | Remove DOC-05 from row 75's index line |
| AT-Q5 | `test_check_cells_are_value_free`: no check cell holds `qamark` plus digits, an `@example.invalid` address or a `QA_SECRET=` assignment | No sentry | Paste a fixture address in RUN-01 |
| AT-Q6 | `test_doc05_points_at_the_journey`: DOC-05 links `cli-v1-journey.md` and is not marked Not built | DOC-05 is Not built | Restore the old text |
| AT-Q7 | `test_run_template_has_exit_column` | The template has no column | Remove the column |

Frozen check (both slices):

| Id | Test | Fails before | Mutation |
|---|---|---|---|
| AT-F1 | Existing guards stay green unchanged: `tests/e2e/release_freeze/test_json_shapes.py`, `tests/unit/test_cli_surface.py`, `tests/unit/release/test_record_smoke.py`, `tests/sentry/release/test_frozen_surface_map.py` | Green before; must stay green | Any edit to `SMOKE_STEPS` or `exit_codes.py` turns one red |

## 9. Frozen contracts

Untouched: the exit-code integers and `PRECEDENCE`, every `--json` shape, the CLI command and flag
surface, `docs/cli-reference.md`, `decoy-release-smoke/v1` and `SMOKE_STEPS`, the smoke log format.
The checklist and the journey are docs, not frozen surfaces, and join no frozen map. No cap, pin,
baseline or allowlist is raised. The two sentries are added to `SENTRIES`, which is a registration
list, not a cap.

## 10. Placement

`src/decoy/cli/` is frozen for new top-level files; these slices add nothing under `src/`.

| New file | Directory | CODEMAP line that places it | Neighbor |
|---|---|---|---|
| `cli-v1-journey.md` | `docs/qa/` | "QA checklists and run templates" (CODEMAP line 80); the row text gains the journey and its test package | `docs/qa/cli-v1-checklist.md` |
| `__init__.py`, `journey_doc.py`, `test_cli_journey.py` | `tests/e2e/journey/` | e2e groups go in a package, not the flat `tests/e2e/` (as "First-user QA item tests", CODEMAP line 68) | `tests/e2e/first_user/` |
| `test_journey_ids.py`, `test_qa_checklist_shape.py` | `tests/sentry/release/` | "Sentry test" row: release-gate sentries in `tests/sentry/release/` (CODEMAP line 69) | `test_frozen_surface_map.py` |

Fan-out: `tests/sentry/release/` goes from 2 to 4 modules; `tests/e2e/journey/` is new with 3. Both
stay under the 25-module cap. Every new file stays under 400 lines (cap 800). The CODEMAP row for
`docs/qa/` is edited to name the journey document and its test package;
`tests/sentry/layout/test_codemap_paths.py` checks those paths exist.

## 11. Design notes

New structure: one document parser and one decorator. Principle: one place per fact. Exit codes live
in the journey document and the test reads them; the stage list and field grammar live in
`journey_doc.py` and the sentry reads them. Patterns followed: the platform journey guard for the
document shape and the `Lands with` mark, and requirement-id markers (jamb, pytest-mark-ac) for
citations. Choke point: `journey_step` is the only way a test cites a step; AT-J3 is the guard; its
mutation is a citation of `CJ-99`. House style: typed results for cached steps (a small frozen
dataclass), single-purpose functions, comments that explain why.

## 12. Slices

Rules for both slices: at most 10 production files and about 400 to 800 lines (here no production
file; tests and docs carry the lines). Tests run on the Mac or a VM through `~/bin/vm-run`, never on
the devbox. T0 per edit, T1 per commit, T2 at the gate on the exact head. No full suite: no
escalation trigger is hit (no shared fixture, test config, lock or frozen contract changes; a
`SENTRIES` entry is not test config). Commits: Conventional Commits subject, no body unless it says
why, final line `cam`. No logging of values, paths or secrets.

| Slice | Content | Production files | Lines | Risk | Depends on |
|---|---|---|---|---|---|
| JQ-1 | `docs/qa/cli-v1-journey.md`; `tests/e2e/journey/` (parser, decorator, journey module); `tests/sentry/release/test_journey_ids.py`; decorators on two cells of `tests/e2e/test_release_smoke.py`; `SENTRIES` entry; CODEMAP `docs/qa/` row | 0 | about 700 | R1 (Codex only) | none; CJ-12 waits on row 61 as a strict xfail |
| JQ-2 | Exit column on all 204 checks, DOC-05 text, run template column; `tests/sentry/release/test_qa_checklist_shape.py`; `SENTRIES` entry; roadmap rows 75 and 92a and `docs/RECENTLY-SHIPPED.md` | 0 | about 550 (about 210 changed table rows) | R1 (Codex only) | JQ-1 (AT-Q6 needs the journey document) |

If the owner answers Q1 with option (b), a third slice JQ-3 edits `packaging_tools/` on the release
path and is R2 (Dennis then Codex).

Row closure: row 75 closes when JQ-1 merges, with the State "DONE except CJ-12, which flips with
row 61". Row 92a's State gains "Exit column and shape sentry (CLI #...)". The row 61 slice that ships
strict delivery sets CJ-12 to `Lands with: main` in the same change; strict xfail forces it.

## 13. Owner questions

| # | Question | Recommendation |
|---|---|---|
| Q1 | Which smoke must cite the journey ids: (a) the in-repo release smoke and the journey test, run against the installed bundle through `DECOY_JOURNEY_BIN` at QA and RC; or (b) also the canonical bundle smoke, through a step-to-id map in `packaging_tools/candidate.py` | (a). It meets the row on every PR and on the bundle, keeps `decoy-release-smoke/v1` frozen and keeps both slices R1. (b) can follow after V1 |
| Q2 | Start row 75 now with the delivery step as a strict expected failure, or wait for row 61 | Start now. The journey is complete from day one, and strict xfail makes row 61 flip it when it lands |
| Q3 | Build the 92a remainder (Exit column and sentry) although row 92a is DONE, in this batch and with no new row | Yes, in this batch; note it on row 92a's State |
| Q4 | Point platform journey J15 at the CLI journey now | No. The platform is parked; record it for Platform V1 |
| Q5 | Add a 13th step for `decoy ci check` | No. Checklist group 13 covers CI; keep the journey to the pipeline a user runs by hand |
| Q6 | Id prefix `CJ-` (distinct from platform `J01` and checklist `CI-`) | Yes |

## 14. Pre-mortem

- A step fails on main because a command's real flags differ from section 4.1. Counter: the builder
  confirms each against `--help` at the base and reports a mismatch before writing the test; the
  step is corrected in the plan, not bent to pass.
- A step fails on main because of a real defect (for example a value echoed in CJ-05). Counter: file
  a row and mark the step `Lands with: row N`; never delete the assertion (memory
  builders-route-around-divergence).
- The Exit column work turns up built checks whose exit cannot be found in code. Counter: listed in
  the JQ-2 report as planner findings; only Not built checks may be `tbd`.
- The journey module is slow (about fifteen subprocess calls). Expected under a minute in the
  existing e2e lane. Over two minutes, the builder reports it rather than adding a marker.
- JQ-1 and JQ-2 both touch `SENTRIES` and `CODEMAP.md`. Counter: JQ-2 is built after JQ-1 merges.

## 15. Open items

- CJ-12's exact refusal code and delivery root come from the DELIV plan (`E:plan/deliv`, CLI slices
  C2a and C2b). The row 61 slice that ships it sets CJ-12's Expected text then.
- The canonical bundle smoke citation (Q1 option b) is a follow-up if the owner wants it.
