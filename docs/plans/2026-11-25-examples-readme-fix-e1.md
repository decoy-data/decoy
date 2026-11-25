Status: plan

# EXAMPLES-README-FIX E1: the bundled mask example passes the gate, and the README names the real output paths

Owner: Cam. Author: Opus plan agent. Date: 2026-11-25. Revision 1. Source: `docs/roadmap/inbox.md` items EXAMPLES-FIX and README-FIX (outside review, CLI PR #319). Repo: decoy (CLI). Branch: docs/plans-inbox-triage-1125. Read at CLI `origin/main` `fffca916`.

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md` (PLAN, Proportion), `bugfix.md`, `testing.md` (Test depth), `documentation.md`.

Classification: 1.0 fix row for both items. A user who follows the shipped example or the README gets a gate failure or looks in the wrong folder. That is a broken documented first-run flow. The fix is cheap. The second half of EXAMPLES-FIX (`decoy init --preset generate` fails on the demo CSV) is a code defect in the generate scaffold. It is planned in `docs/plans/2026-11-25-gen-scaffold-fidelity-g1-g4.md` (slice G1), not here. Risk: R1. Docs, one example file, one sample CSV and tests.

## 1. Problem

1. `examples/mask_example.yaml` fails `decoy validate config`: column `account_number` uses `strategy: hash` with no `namespace` (`examples/mask_example.yaml:64`), and the engine refuses it with `hash_requires_namespace`. The file's own header (`examples/mask_example.yaml:6`) tells the user to run `decoy validate config` on it. The full gate also fails, because `./input.csv` (`examples/mask_example.yaml:37`) is not in the repo. Reproduced on the Mac node: exit 1, `hash_requires_namespace`.
2. `tests/unit/test_bundled_examples.py:56` only runs `PipelineConfig.model_validate`. It does not run the plan or preflight layers, so it missed item 1.
3. `README.md:94-95` says `decoy run` writes to the path under `targets:`. A relative target goes to `out/<pipeline>/<run-id>/` with a `current` link (`open_run_layout`, `src/decoy/cli/io/_layout.py`). `README.md:147` scores `source.csv synthetic.csv`, but the scaffold writes `<stem>.synthetic.csv` into the run folder. The exit-code half of README-FIX is already done by RG-X (CLI #270) and guarded by `tests/sentry/cli_text/test_exit_code_docs.py`.

## 2. Behavior

- `examples/mask_example.yaml`: `account_number` gets `namespace: account_identity`. A new `examples/input.csv` holds 20 synthetic rows with the six columns the example names, made with fixed fake values (no real data). The output target stays `./masked_output.csv`.
- `decoy validate examples/mask_example.yaml` (full gate) and `decoy run examples/mask_example.yaml` both exit 0 from any working folder.
- The bundled-examples test runs the full gate (config, compile, preflight) on every `examples/*.yaml`, so a new example that fails the gate fails CI.
- `README.md`: the run paragraph says where output goes (`out/<pipeline>/<run-id>/`, the `current` link, and that an absolute target path is written as given). The generate block uses `decoy report fidelity source.csv out/pipeline/current/source.synthetic.csv --generate`. The "Status" version line is checked against `pyproject.toml` and corrected if it differs.
- REL-DOCS (row 92) owns the public docs site. This row touches only `README.md` and `examples/`.

Non-goals: no change to the run layout, the exit codes or the scaffold code.

## 3. Failure modes

- F1: a gate test that resolves `./input.csv` from the test's working folder instead of the YAML's folder. The gate resolves relative paths from the YAML's folder, so the test must run from a different `cwd` (AT-2).
- F2: `examples/input.csv` is picked up by a scan or sentry that forbids CSV fixtures outside `tests/`. The builder checks the repo sentries in T1.
- F3: the README path text drifts again. AT-4 runs the README's generate commands as written.

## 4. Defect classes

| # | Class | Applies | Structure that closes it | Proof and the mutation that turns it red |
|---|---|---|---|---|
| 1 | value | N/A: the sample CSV is made-up data and no error text changes | none | none |
| 2 | cleanup | N/A: tests write into `tmp_path` only | none | none |
| 3 | state | N/A: no state | none | none |
| 4 | route | Yes: a schema-only check is a weaker route than the gate users run | the bundled-examples test calls the same gate entry as `decoy validate` | AT-2; mutation: drop `namespace` from the example |
| 5 | referential | N/A: one table | none | none |
| 6 | untrusted | N/A: no new input path | none | none |
| 7 | toctou | N/A: no path checks | none | none |
| 8 | weak | Yes: a README test could grep for one word | AT-4 runs the documented commands and opens the documented file | AT-4; mutation: change the README path back |
| 9 | refactor drift | N/A: no refactor | none | none |
| 10 | frozen contract | N/A: no frozen surface changes; exit codes and layout unchanged | none | none |

## 5. Acceptance tests

| AT | Test | Mutation that turns it red |
|---|---|---|
| AT-1 | `decoy validate config examples/mask_example.yaml` exits 0 (e2e, through the CLI runner). | Remove `namespace` from `account_number` |
| AT-2 | `tests/unit/test_bundled_examples.py` gains a parametrized test: for each `examples/*.yaml`, copy `examples/` into `tmp_path`, `chdir` to another folder and run the full gate (`run_gate_on_config` or the `decoy validate` runner). No error findings. | Delete `examples/input.csv` |
| AT-3 | `decoy run examples/mask_example.yaml` from a copy in `tmp_path` exits 0. The output CSV under `out/` has 20 rows, and no `ssn` value from `input.csv` appears in it. | Change `ssn` to `passthrough` |
| AT-4 | A README test reads the generate block from `README.md` and runs it on a small CSV in `tmp_path`: `init --preset generate`, `run`, then the `report fidelity` line exactly as written. Each exits 0, and the file the README names exists. Depends on G1 of the scaffold plan, because the scaffold fails on many CSVs today. Until G1 merges, the test uses a CSV with numeric and category columns only. | Restore `synthetic.csv` in the README |
| AT-5 | A text check: `README.md` names `out/<pipeline>/<run-id>/` in the run paragraph and the version on the Status line equals `pyproject.toml`. | Put "the path under `targets:`" back |

## 6. Files allowed to change

`examples/mask_example.yaml`, new `examples/input.csv` (21 lines), `README.md`, `tests/unit/test_bundled_examples.py` (about 40 lines added; the file is under 100), one README e2e test file under `tests/e2e/first_user/`.

## 7. Test selection

- T0: `tests/unit/test_bundled_examples.py` and the new README test.
- T1: those, plus `tests/e2e/first_user/test_items_generate_fk.py` (reads `examples/generate_example.yaml`), `tests/sentry/`, and import-impact selection.
- T2 gate: T1 on the exact head with the mutations above.
- Full suite: not triggered. No shared fixture, schema, pin or frozen surface changes. `examples/` is not a test fixture directory.

## 8. Enumerations

### Exit paths

- `decoy validate` on the example: 1 today, 0 after.
- `decoy run` on the example: 1 today (missing source), 0 after.

### Routes

- `validate config` (config layer only) and the hidden full gate: both covered.
- `run` in memory: covered by AT-3. `--chunked` is not documented for this example.

### FK shapes

N/A: the example has one table and no relations.

### Fields

- `account_number.namespace` added in the example (`examples/mask_example.yaml:64`).
- Seven CSV columns in `examples/input.csv`: `first_name`, `last_name`, `email`, `phone`, `ssn`, `account_number`, `account_status`. The builder takes the list from the example's `columns:`, not from this line.

### Output surfaces

- `README.md` run paragraph (`README.md:94`) and generate block (`README.md:147`), Status line (`README.md:21`).
- The example's header comments.

## 9. Reuse inventory

`run_gate_on_config` (`src/decoy/cli/gate`), the CLI test runner, `open_run_layout` for the documented path, the existing bundled-examples test file. No new source module.

## 10. Frozen contracts

None change. The exit-code table in the README stays as RG-X left it and its sentry keeps passing.

## 11. Slices

One slice, E1, CLI repo, no source code, about 40 lines of docs and example and 80 lines of tests. AT-4 waits on scaffold slice G1 for its full CSV. If G1 has not merged, E1 merges with the reduced CSV and G1 widens AT-4. No open PR touches these files.

## 12. Pre-mortem

- The builder adds `input.csv` but leaves the test schema-only, and the next example breaks the same way. AT-2 runs the real gate.
- The builder fixes the README by naming an absolute target path, which hides the run-folder behavior. AT-5 checks the run-folder text.
- REL-DOCS rewrites the README at the same time. Whichever lands second rebases; AT-4 and AT-5 hold the facts.
