# CLI journey and QA checklist: rows 75 and 92a

Status: plan

Date: 2026-11-17. Author: Opus planner. Base: CLI `origin/main` `b6f8558`. Line numbers below are
from that head.

Revision 2 (2026-11-17), after Codex round 1 NO-GO on `d0eef340`. Owner answers Q1 to Q6 stay as
recommended. Changes: every step command checked against `docs/cli-reference.md` and the Typer
definitions on the base, and corrected (CJ-04 scans files, not a pipeline); installed-bundle mode
runs with a cleaned environment from a temp folder and proves the bundle, not the checkout, is
imported (AT-J12); AT-Q3 pins an independent 204; one exit code per command, checked by an anchored
command parser in both documents (AT-J13, AT-Q8); the shared parser and decorator move to
`tests/cli_journey.py` (CODEMAP line 71); the allowed exit set is derived from the exported `EXIT_`
constants and `RUN_EXIT_MAP`; CJ-12 fixes its command and exit 3 now.

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
   The same test runs against an installed bundle with a cleaned environment and proves the bundle,
   not the checkout, is imported.
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

Size: about 1,300 lines over two slices, all tests and docs. New public names (test side only): the
`journey_step` decorator, the `read_journey` parser, `parse_commands` and `allowed_exit_codes` in
`tests/cli_journey.py`. No production file.

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
person with two related tables on disk, `customers` and `orders` (`orders.customer_id` references
`customers.id`). The project keeps them as CSV in `data/` and as Parquet in `data/parquet/`, written
from the same rows, because a pipeline `subset:` reads relationship tables from Parquet (engine
`subset_requires_parquet`, `src/decoy_engine/subset/_preflight.py` in the engine) and
`decoy report integrity` reads CSV.

Each step is a level-3 heading `### CJ-NN: <title>` followed by exactly these labelled lines:

- `**Stage:**` one of `install`, `project`, `source`, `subset`, `pre-scan`, `mask`, `post-scan`,
  `delivery`, `evidence`, `vault`, `refusal`.
- `**Command:**` one or more commands, each one backtick span that starts with `decoy `, written
  as a user types them, in the order they run. Prose between the spans is allowed; a backtick span
  that does not start with `decoy ` is not a command.
- `**Exit:**` exactly one exit code per command, in the same order, comma separated. Each code is
  in the allowed set (section 4.4).
- `**Expected:**` what the user sees, in the user's words, value-free: tables, columns, files, counts
  and reason codes, never a cell value or the secret.
- `**Lands with:**` `main`, or `row <N>` when the step's behaviour is not on main yet.

The steps, checked on the base against `docs/cli-reference.md` and the Typer definitions (the file
and line of each command's definition is in the last column). Paths are relative to the project
folder `shop/`. `S` stands for `--mask-secret env:JOURNEY_SECRET`.

| Id | Stage | Command | Exit | Expected (value-free) | Lands with | Checked against |
|---|---|---|---|---|---|---|
| CJ-01 | install | `decoy --version` | 0 | Prints `decoy` and a version | main | root callback, `src/decoy/__main__.py` |
| CJ-02 | project | `decoy project new shop --json` | 0 | JSON names the project root and the made folders (`pipelines/`, `out/`, `.decoy/`) | main | `new_command`, `src/decoy/cli/project/_new.py:95` (`DIR`, `--json`) |
| CJ-03 | source | `decoy init customers --source data/customers.csv --json -y` | 0 | `pipelines/customers/pipeline.yaml` written; the record names columns and starter strategies | main | `src/decoy/cli/init.py:420` (`NAME|FILE`), `:432` (`--source`), `:454` (`-y`), `:459` (`--json`) |
| CJ-04 | pre-scan | `decoy scan data/customers.csv data/orders.csv --has-header --json` | 0 | One table per file: row and field counts, PII candidates as suggestions, reid risk; no cell value | main | `_scan` in `src/decoy/cli/scan.py` (`SOURCES...`, `--has-header/--no-header`, `--json` at `src/decoy/cli/scan.py:549`) |
| CJ-05 | refusal | `decoy validate bad --json`, where `pipelines/bad/pipeline.yaml` has an unknown key and a wrong-typed value that carries a marker | 1 | The aggregate validation envelope `{command, status, config, messages}` (`src/decoy/cli/validate.py:317`), with `status` failed and a message naming the key, its code and its location; the marker is not in the envelope; no run folder | main | hidden default command of `validate_app`, `src/decoy/cli/validate.py:396` (`--json` at `:260`) |
| CJ-06 | source | `decoy validate shop` | 0 | Config, compile and preflight pass | main | same as CJ-05 |
| CJ-07 | subset | `decoy run shop S --out-dir jout/shop --evidence-out jout/shop-evidence.json --json`, with a `subset:` block sampling `customers` | 0 | `--json` has a `subset` object with kept and total counts; every kept `orders` row has its parent | main | `decoy run` options in `docs/cli-reference.md` (`--out-dir`, `--evidence-out`, `--mask-secret`, `--json`); subset as in `tests/e2e/test_run_subset.py` |
| CJ-08 | mask | `decoy run shop S --out-dir jout/shop --evidence-out jout/shop-evidence.json --json` (the CJ-07 run; this step checks its outputs and does not run again) | 0 | The CSV targets exist; masked columns differ from the input, passthrough columns match, row counts match the subset, input files unchanged | main | as CJ-07 |
| CJ-09 | post-scan | `decoy report integrity jout/shop/customers.csv --source data/customers.csv --config shop --allow-source-mismatch --json` | 0 | No residual PII finding; names and counts only | main | `_integrity`, registered at `src/decoy/cli/report.py:2294` (`MASKED`, `--source`, `--config`, `--allow-source-mismatch`, `--json`) |
| CJ-10 | evidence | `decoy report verify jout/shop-evidence.json --json`, then `decoy report verify jout/shop-evidence.json --json` after one byte of `jout/shop/orders.csv` changes | 0, 4 | First every fingerprint matches; then the changed file is named | main | `_verify`, registered at `src/decoy/cli/report.py:2292` (`EVIDENCE_FILE`, `--json`; drift exits `EXIT_FINDINGS`) |
| CJ-11 | vault | `decoy run vaulted S --vault jout/vault.bin --out-dir jout/vaulted --json`, then `decoy unmask pipelines/vaulted/pipeline.yaml jout/vaulted/customers.csv S --vault jout/vault.bin -o jout/customers.unmasked.csv --json` | 0, 0 | The recovered column equals the input (checked by the test, never printed) | main | `decoy run --vault`; `decoy unmask CONFIG MASKED` with `--vault`, `--mask-secret`, `-o`, `--json` (`docs/cli-reference.md`, `decoy unmask`) |
| CJ-12 | delivery | `decoy run shop S --out-dir jout/strict --json`, where `jout/strict/orders.csv` is an existing folder, so the `orders` write fails | 3 | Strict delivery: no target file of the run is left under `jout/strict/`; the error names the table and a reason code | row 61 | `RUN_EXIT_MAP[("failed", "runtime")]` is `EXIT_RUNTIME` (`src/decoy/cli/exit_codes.py:142`) |

The fixture writes three pipelines before the steps that use them: `shop` (Parquet sources from
`data/parquet/`, CSV targets, the FK and a `subset:` block sampling `customers`), `bad` (CJ-05) and
`vaulted` (`customers` only, `vault: true` on one `hash` column).

CJ-12's command and exit are fixed now. On main the `customers` target may already be written when
`orders` fails, so the "nothing delivered" fact fails and the step is a strict expected failure
until row 61's stage-then-deliver slices land. Row 61 changes only `Lands with`.

The sentry checks that the stages `source`, `subset`, `pre-scan`, `mask`, `post-scan`, `delivery`
and `vault` each have at least one step, so a baseline stage cannot drop out unseen. CI use is
covered by checklist group 13, not by the journey (owner Q5).

### 4.2 The journey test

`tests/e2e/first_user/journey/test_cli_journey.py` holds the module fixture and one test per step; the package
holds nothing else besides `__init__.py`. The fixture builds the project under `tmp_path_factory`
once and runs the steps in id order, caching each result (exit codes, stdout, stderr, files
written) in a frozen dataclass. Each test is decorated `@journey_step("CJ-NN")` and asserts only its
own step: the exit codes read from the document through `read_journey` (never copied into the test),
and the Expected facts.

Two modes:

- Source mode (default): argv prefix `[sys.executable, "-m", "decoy"]`, cwd the project folder.
- Installed-bundle mode: `DECOY_JOURNEY_BIN` is the installed `decoy` launcher and
  `DECOY_JOURNEY_HOME` is the `DECOY_HOME` of that install; both are required together. The
  environment is built from scratch, the way `packaging_tools/smoke_install.py` builds its bundle
  env: `PYTHONPATH`, `PYTHONHOME`, `PYTHONSTARTUP`, `PYTHONUSERBASE`, `VIRTUAL_ENV`, `CONDA_PREFIX`
  and every `DECOY_*` and `XDG_*` variable of the caller are dropped; `HOME` is a temp folder;
  `DECOY_HOME` is `DECOY_JOURNEY_HOME`; `DECOY_NO_UPDATE_CHECK=1`; `PATH` keeps only entries outside
  the checkout and its virtual environment. Every command runs with a cwd inside the temp root,
  never the checkout. Before the first step the fixture proves the bundle is what runs:
  - the launcher's real path is outside the checkout and outside `sys.prefix`;
  - `$DECOY_JOURNEY_HOME/current/python/bin/python3 -I -c` prints the real paths of
    `decoy.__file__` and `decoy_engine.__file__`, and both are under the real path of
    `DECOY_JOURNEY_HOME`, not under the checkout;
  - `decoy --version` through the launcher equals the version that interpreter reports.
  Any failure stops the module with a message naming the check, and nothing falls back to source
  mode. A hand-built launcher that runs a different interpreter than the install's is deliberate
  evasion and V2-LOG.

Value-free sweep: every text cell of the fixture data carries `jmark` plus a number; the secret is
48 random bytes in `JOURNEY_SECRET`. After each step a sweep checks stdout, stderr, `--json`,
evidence and the run folder (not the masked data files) for any marker or the secret. A hit fails
that step. Each sweep asserts it read at least one non-empty capture.

`journey_step(id)` reads the document once. If the step's `Lands with` is not `main` it applies
`pytest.mark.xfail(strict=True, reason="lands with row N")`. When the row lands the test passes,
strict xfail turns that into a failure, and the slice that lands the row sets `Lands with: main`.

`tests/e2e/test_release_smoke.py` decorates the cells that cover a step: `--version` with CJ-01 and
the canonical run with CJ-08. A step may be cited by the release smoke and by the journey module;
the journey module cites each id exactly once.

### 4.3 The checklist Exit column

Every check table in `docs/qa/cli-v1-checklist.md` gets the header
`| Id | Command | Exit | Expected | Rows | Pass/fail |`. Command and Exit use the same parser as the
journey (`parse_commands` in `tests/cli_journey.py`):

- Each command the check runs is one backtick span that full-matches the command grammar:
  `decoy` with optional arguments, or the installer forms `sh install.sh` and `install.ps1` with
  optional leading `NAME=value` assignments and trailing arguments (group 1). Prose and other spans
  (file names, flags, YAML keys) are not commands. Where a check runs one command over many
  inputs ("`decoy <command> --help` on every command"), the span is written once and has one code.
- The Exit cell is either one code per command span, comma separated, in span order; or `none`
  when the cell has no command span (reading a document, a CI result, an installer script); or
  `tbd` only on a check whose Expected starts with `**Not built.**`, which may also have no span
  yet. A count mismatch is a sentry failure.
- The journey uses the same parser with the `decoy` form only; an installer span in the journey is
  refused.

Checks that run `decoy` but describe it in prose today (GATE-02 "A CSV source with no
`has_header`", RUN-02 and others) are rewritten so each command is a `decoy ...` span. Exit codes move
out of the Expected text where they were written there, so each code is stated once. The builder
sets each code from the code path at the slice base (`exit_code_for`, `RUN_EXIT_MAP`, the command's
own exits), not from memory; "non-zero" (RUN-03 and others) becomes the exact code. A built check
whose exit the builder cannot find in code is listed in the slice report as a finding for the
planner, not set to `tbd`.

DOC-05 changes from "Not built" to: "Run `tests/e2e/first_user/journey/` with `DECOY_JOURNEY_BIN` and
`DECOY_JOURNEY_HOME` set to the installed `decoy`; every step passes or is an expected failure for
its row. Steps in [cli-v1-journey.md](cli-v1-journey.md)." The run template's Results table gains an
`Exit observed` column.

### 4.4 The allowed exit set

`allowed_exit_codes()` in `tests/cli_journey.py` returns the values of every name in
`decoy.cli.exit_codes.__all__` that starts with `EXIT_`, together with the values of
`decoy.cli.exit_codes.RUN_EXIT_MAP`. That gives 0 to 6 and 130 (the `("cancelled", "cancelled")`
entry) without copying any integer. Both sentries and the journey test use it.

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
- `DECOY_JOURNEY_BIN` points at a missing file, or `DECOY_JOURNEY_HOME` is missing: the fixture
  fails with a message naming the variable and never falls back to the source tree.
- The installed-bundle run imports the checkout instead of the bundle (a leaked `PYTHONPATH`, a
  virtual environment with an editable install, a cwd inside the checkout), so the RC pass tests
  the source tree. The cleaned environment, the temp cwd and the import-location probe close it
  (AT-J12).
- A step or check lists two commands and one exit code, so the second command's result is never
  stated. The anchored command parser counts commands (AT-J13, AT-Q8).
- A count that the sentry reads only from the document can be moved with the rows it counts. AT-Q3
  pins its own 204.
- Checklist: a row with a missing or extra cell, which renders and reads wrong. Sentry counts cells.
- An exit code not in the registry (`7`), or a stale `tbd` on a built check. Sentry.
- A pasted fixture value in a check cell, which would teach a tester that echoing is fine. Sentry.
- The Groups table says `INST-01 to INST-19` and the group holds 18. Sentry.
- Steps share state, so one early failure fails later steps. Accepted: the first red step is the
  cause, and each later test names the step it waited on.

## 6. Enumerations

### Exit paths

- Codes the journey and the checklist may name: the values of the exported `EXIT_` names
  (`src/decoy/cli/exit_codes.py:45` to `src/decoy/cli/exit_codes.py:103`, exported in `__all__` at
  `src/decoy/cli/exit_codes.py:308`) and the values of `RUN_EXIT_MAP`
  (`src/decoy/cli/exit_codes.py:135`), which add 130 through the cancelled entry
  (`src/decoy/cli/exit_codes.py:144`). `allowed_exit_codes()` reads both; no integer is copied.
- Journey exits used: 0 (CJ-01 to CJ-11), 1 (CJ-05), 4 (CJ-10, second command), 3 (CJ-12).
- Sentry outcomes: pytest pass or fail only. No new process exit anywhere.

### Routes

- In-memory `decoy run`: CJ-07, CJ-08, CJ-11. The chunked route refuses `subset:`
  (`config.subset_run_unsupported`, see the docstring at `tests/e2e/test_run_subset.py:6`), so the
  journey does not use `--chunked`; route coverage stays with checklist group 5.
- Source checkout (default) and installed bundle (`DECOY_JOURNEY_BIN` with `DECOY_JOURNEY_HOME`,
  cleaned environment, temp cwd): the same test on both. The bundle environment follows
  `_bundle_env` and `_env` in `packaging_tools/smoke_install.py:158` and
  `packaging_tools/smoke_install.py:611`.

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
| 4 | Route parity and silent fallback | Installed-bundle mode uses only the launcher, a cleaned environment and a temp cwd, and proves the bundle's `decoy` and `decoy_engine` are imported; a missing variable fails | AT-J9, AT-J12 | Fall back to `python -m decoy` when the path is missing; point the mode at a launcher and home that run the checkout's editable install |
| 5 | Referential integrity | CJ-07 checks every kept `orders` row has a kept parent after masking | AT-J6 (CJ-07 cell) | Drop the FK from the journey YAML so `orders` subsets on its own |
| 6 | Untrusted producer | The two parsers read only repo docs, full-match every field and refuse an unknown label | AT-J1, AT-Q1 | Accept an unknown `**Owner:**` label silently |
| 7 | Check then use on a path | N/A: the slices read repo documents and `tmp_path` files they wrote themselves; no path is checked and then opened by another party |
| 8 | Weak tests | Every AT names a mutation; sweeps assert non-empty input; the journey reads exits from the doc | AT-J10, AT-J6 | Compare `returncode` with a literal `0` in the journey module |
| 9 | Refactor drift | N/A: nothing is moved or split; the checklist edit adds a column and moves exit text, held by the counts in AT-Q3 |
| 10 | Frozen contract drift | No exit code, JSON shape, command or smoke summary changes; the release smoke gains decorators only | AT-F1 | Rename a `SMOKE_STEPS` entry or add an exit constant |

From the dev-rules catalog: class 1 (anchored validation) applies to every id, stage and exit token,
all checked with `re.fullmatch`. Class 5 (normalized scanners) applies to the citation scanner,
which reads decorator calls through the AST and covers `journey_step("CJ-01")`, an import alias
(`from tests.cli_journey import journey_step as js`) and the attribute form
(`cli_journey.journey_step(...)`). Ids built at run time are deliberate evasion, V2-LOG. Class 11
(no raised caps): no cap, pin, baseline or allowlist moves.

## 8. Hostile corpus / acceptance tests red first

Each test is written first. "Fails before" is why it is red on the base head. A builder may add
tests and must not weaken these. Mutations run on the slice's final head and the head is recorded
in the slice report.

Slice JQ-1 (journey):

| Id | Test | Fails before | Mutation |
|---|---|---|---|
| AT-J1 | `tests/sentry/release/test_journey_ids.py::test_journey_doc_shape`: ids `CJ-01` to `CJ-NN` contiguous and unique; each step has the five labels once; Stage, Exit and Lands with full-match their grammar; the seven baseline stages each have a step | The document does not exist | Delete the pre-scan step; add a stray token after an Exit value |
| AT-J2 | `test_every_journey_id_is_cited`: each id is cited exactly once in `tests/e2e/first_user/journey/` | No citations exist | Remove `@journey_step("CJ-04")` |
| AT-J3 | `test_every_cited_id_exists`: every `journey_step` call under `tests/` names a document id | No scanner | Cite `CJ-99` in `test_release_smoke.py` |
| AT-J4 | `test_exit_tokens_are_registered`: every Exit token is in `allowed_exit_codes()`, which reads the exported `EXIT_` names and `RUN_EXIT_MAP`; a self-test asserts the set is exactly what those two give and that the helper module holds no integer literal outside 0 and 1 used as indexes | No document | Set CJ-05's Exit to `7`; hard-code `{0, 1, 2, 3, 4, 5, 6, 130}` in the helper |
| AT-J5 | `test_unbuilt_steps_are_strict_xfail`: `journey_step` on a `row N` step yields an `xfail` mark with `strict=True`, and on a `main` step yields none | No decorator | Drop `strict=True` in the decorator |
| AT-J6 | `tests/e2e/first_user/journey/test_cli_journey.py`, one test per step, each asserting its exit codes, its Expected facts and a clean sweep | No module | The class 1 and class 5 mutations in section 7 |
| AT-J7 | The fixture asserts the repo tree and `$HOME` gained no file during the module | No fixture | Point the project root at the repo |
| AT-J8 | The fixture records step order; CJ-08's test asserts CJ-07 ran first | No fixture | Swap the order |
| AT-J9 | With `DECOY_JOURNEY_BIN` set to a missing path, or without `DECOY_JOURNEY_HOME`, the fixture errors with a message naming the variable | No fixture | Fall back to `python -m decoy` |
| AT-J10 | `test_journey_module_reads_exits_from_doc`: the journey module's AST has no `returncode` compared with an int literal | No module | Write `assert r.returncode == 0` |
| AT-J11 | `test_release_smoke_cites_journey`: `test_release_smoke.py` cites CJ-01 and CJ-08 | No citations | Remove one decorator |
| AT-J12 | `tests/e2e/first_user/journey/test_cli_journey.py::test_bundle_mode_refuses_the_checkout`: a temp home whose `current/python/bin/python3` is a link to the checkout's interpreter and a launcher script that runs `python -m decoy` with it. With `PYTHONPATH` set to the checkout's `src` in the caller's environment and the cwd at the checkout, the bundle-mode setup refuses, naming the import-location check; the cleaned environment has no `PYTHONPATH`, `PYTHONHOME` or `VIRTUAL_ENV`, and every step cwd is under the temp root | No bundle mode | Each alone turns the test red: keep the caller's `PYTHONPATH` in the built env (the env assertion fails); skip the import-location probe (the setup accepts the checkout); run steps with the checkout as cwd (the cwd assertion fails) |
| AT-J13 | `test_one_exit_per_command`: for each step, the number of `decoy ` spans that `parse_commands` finds equals the number of Exit codes; the parser full-matches each span and ignores other spans | No parser | CJ-10 with two commands and Exit `0`; a span `` `decoyx run` `` counted as a command |

Slice JQ-2 (checklist):

| Id | Test | Fails before | Mutation |
|---|---|---|---|
| AT-Q1 | `tests/sentry/release/test_qa_checklist_shape.py::test_check_tables_have_six_cells`: every table under a group heading has the six-cell header and six cells per row | The header has five cells today | Drop the Exit cell of one row |
| AT-Q2 | `test_exit_cells_parse`: full-match grammar; codes from the registry; `tbd` only with `**Not built.**` | No Exit column | `7`; `tbd` on GATE-01 |
| AT-Q3 | `test_ids_and_counts`: the sentry owns `EXPECTED_CHECKS = 204` and `EXPECTED_GROUPS = 16`; it asserts the parsed check rows and groups equal them, and that the document's "Sixteen groups, 204 checks." states the same; ids unique and contiguous per prefix; each group's range in the Groups table matches its rows | No sentry (true today, guarded from now) | Add one check row and change the document's total to 205 in the same edit: red, because the sentry's 204 did not move. Also: duplicate RUN-05 |
| AT-Q4 | `test_row_index_names_real_checks`: every id or range in the row index exists, and each check's Rows cell lists rows whose index line names that check | No sentry | Remove DOC-05 from row 75's index line |
| AT-Q5 | `test_check_cells_are_value_free`: no check cell holds `qamark` plus digits, an `@example.invalid` address or a `QA_SECRET=` assignment | No sentry | Paste a fixture address in RUN-01 |
| AT-Q6 | `test_doc05_points_at_the_journey`: DOC-05 links `cli-v1-journey.md` and is not marked Not built | DOC-05 is Not built | Restore the old text |
| AT-Q7 | `test_run_template_has_exit_column` | The template has no column | Remove the column |
| AT-Q8 | `test_one_exit_per_command`: for every check, the Exit cell has one code per command span that `parse_commands` finds, `none` only with no span, `tbd` only with **Not built.** | No Exit column | EXIT-02-style row with two `decoy` spans and Exit `0`; `none` on a row with a `decoy` span |

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
| `cli_journey.py` (parser, decorator, command parser, allowed exit set) | `tests/` | "Shared cross-suite test helpers", one module per concern (CODEMAP line 71); used by `tests/e2e/` and `tests/sentry/release/` | `tests/keyed_secret.py`, `tests/command_tree.py` |
| `__init__.py`, `test_cli_journey.py` (the module fixture and the step tests only) | `tests/e2e/first_user/journey/` | CODEMAP line 68 places first-user QA tests under `tests/e2e/first_user/`; it already has 23 direct files, so the journey gets a named sub-package | `tests/e2e/first_user/` |
| `test_journey_ids.py`, `test_qa_checklist_shape.py` | `tests/sentry/release/` | "Sentry test" row: release-gate sentries in `tests/sentry/release/` (CODEMAP line 69) | `test_frozen_surface_map.py` |

Fan-out: `tests/sentry/release/` goes from 2 to 4 modules; `tests/e2e/first_user/journey/` is new with 2;
`tests/` gains one top-level module. All stay under the 25-module cap (the `tests/` top level
counts its existing helper modules and packages, well under it). Every new file stays under 400 lines (cap 800). The CODEMAP row for
`docs/qa/` is edited to name the journey document and its test package;
`tests/sentry/layout/test_codemap_paths.py` checks those paths exist.

## 11. Design notes

New structure: one document parser and one decorator. Principle: one place per fact. Exit codes live
in the journey document and the test reads them; the stage list and field grammar live in
`tests/cli_journey.py` and the sentries read them; the allowed exit set is derived from
`decoy.cli.exit_codes`, never copied. Patterns followed: the platform journey guard for the
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
| JQ-1 | `docs/qa/cli-v1-journey.md`; `tests/cli_journey.py` (parser, decorator, command parser, allowed exit set); `tests/e2e/first_user/journey/` (fixture and step tests); `tests/sentry/release/test_journey_ids.py`; decorators on two cells of `tests/e2e/test_release_smoke.py`; `SENTRIES` entry; CODEMAP `docs/qa/` row | 0 | about 750 | R1 (Codex only) | none; CJ-12 waits on row 61 as a strict xfail |
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

- A step fails on main because a command's behaviour differs from section 4.1 although its flags
  match (revision 2 checked every flag against the Typer definitions). Counter: the builder reports
  it before writing the test; the step is corrected in the plan, not bent to pass.
- The Parquet-source, CSV-target subset run (CJ-07) is refused at run time. Counter: the same
  report; the planner picks Parquet targets and moves CJ-09 to a CSV pipeline.
- A step fails on main because of a real defect (for example a value echoed in CJ-05). Counter: file
  a row and mark the step `Lands with: row N`; never delete the assertion (memory
  builders-route-around-divergence).
- The Exit column work turns up built checks whose exit cannot be found in code. Counter: listed in
  the JQ-2 report as planner findings; only Not built checks may be `tbd`.
- The journey module is slow (about fifteen subprocess calls). Expected under a minute in the
  existing e2e lane. Over two minutes, the builder reports it rather than adding a marker.
- JQ-1 and JQ-2 both touch `SENTRIES` and `CODEMAP.md`. Counter: JQ-2 is built after JQ-1 merges.

## 15. Open items

- CJ-12's command and exit (3) are fixed in this plan. Row 61 changes only its `Lands with` line.
- The canonical bundle smoke citation (Q1 option b) is a follow-up if the owner wants it.
