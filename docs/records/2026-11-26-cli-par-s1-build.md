Status: record

# CLI-PAR S1 build record

Date: 2026-11-26. Branch `feat/cli-par-s1`. Slice: run the CLI test suite on 4 pytest-xdist workers.

## What changed

- `scripts/dev/gates.sh` runs the `tests` step in two passes: `-n W --dist loadfile -m "not serial"`, then a plain `-m serial` pass. `GATES_WORKERS` sets W (a number or `auto`). W = 1, or a venv without pytest-xdist, gives one plain run as before.
- `ci.yml` job `pytest` runs the same two passes. The serial step runs even after a red parallel step.
- The `serial` mark covers tests that need the whole host. `tests/sentry/tooling/required_serial.toml` lists the known ones, and the new sentry `test_serial_resources.py` fails on an unmarked test that looks like one.
- Hypothesis storage is moved out of the checkout, one root per pytest process.
- `_gates_report.py` reads both JUnit files, records workers and dist in a baseline, and writes `--outcomes-file`.

## Step 0

On the Linux test node, in the lock venv: `current_row_is_certified()` is False. Adding xdist does not change a certified row.

## Runs

| Run | Result |
|---|---|
| `GATES_WORKERS=4 gates.sh --steps tests` over `tests/unit/scripts`, `tests/sentry/tooling`, vendored files, sentry manifest, CI lock installs, bootstrap gates (Dell, Linux) | 391 passed, 0 failed, both passes ran with `-n 4 --dist loadfile` and `-m serial` |
| Mutations (below) | each one turns its named test red |

## Mutations

| Mutation | Red test |
|---|---|
| remove `serial` from the journey file | `test_the_required_serial_registry_is_marked` |
| drop `not serial` from the parallel pass | `test_gates_parallel.py` (AT-3, AT-4 cells) |
| delete the CI serial step | `test_ci_lanes.py::test_real_tree_has_no_findings` (M1) |
| drop `--ignore` from the CI parallel pass only | same (M5) |
| remove `--dist` from `_VALUE_OPTS` | same |
| remove the Hypothesis storage redirect (both lines) | `test_each_process_gets_its_own_storage_root_outside_the_checkout` |
| remove `.hypothesis/` from `.gitignore` | `test_the_checkout_ignores_the_hypothesis_folder`; checked with `git check-ignore` on the devbox (exit 1). The GCP VM that ran it did not go red, so that node probably ignores the folder through a global exclude. |
| reporter reads one JUnit file only | `test_reporter_counts_are_identical_for_one_or_two_junit_files` |
| baseline `dist` forced to `no` | `test_a_parallel_baseline_records_workers_and_dist` |

## Not done in S1

AT-13 (proof on the merge head), AT-14 (hosted CI) and the S1-T and S1-OPS steps belong to the orchestrator.
