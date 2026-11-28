# Handoff: external review of the testing setup

Status: current. Written 2026-11-28. For the orchestrator that owns `TESTING-METHODOLOGY` and
`TEST-REDUCTION-REPORT-2026-11-28`, and for the owner, who signs off on anything marked
"owner decision".

This is the reviewer's answer to section 10 of `TESTING-METHODOLOGY`. It was written from those two
documents plus a read of `decoy-engine` at `395c1c6`. No test was run and no file outside this one
was changed. Every saving below is an estimate until it is measured.

## The main point

The reduction report is right that cutting tests saves at most about 10%. The larger loss is that a
full engine run takes 1.2 to 5 hours against an ideal of 56 to 94 minutes. That gap is 2 to 4 times
the whole suite and it comes from how runs share the nodes, not from the tests. Fix the nodes first,
selection second, and the matrices last.

## What was checked in the engine repo

| Claim | Result | Where |
|---|---|---|
| G1: companion-gated `tests/physical` tests run nowhere | Confirmed. The workflow names 9 of the 62 files in `tests/physical`. Whole-directory steps cover only `tests/native`, `tests/parity` and `tests/unit/execution`. `test_shadow_group_key`, `test_c8_iii_a_when_unified` and `test_unified_route_evidence` appear in no workflow file. | `.github/workflows/native-companion.yml` lines 367, 379, 412, 442 |
| E1: the proof manifest is built 8 times | Confirmed. All 8 tests call `gen.build()`. | `tests/sentry/test_proof_manifest.py` |
| `serial` tests run alone | Only inside one run. `gates.sh` runs the serial pass without xdist, but only the gate workflow takes a host lock (`~/.cache/pytest-one.lock`). Other slots on the same node keep running. | `scripts/dev/gates.sh` lines 455 to 456, `gate-selfhosted.yml` line 158 |
| Thread pools are capped per worker | Not found. No `POLARS_MAX_THREADS`, `OMP_NUM_THREADS` or `RAYON_NUM_THREADS` in `gates.sh`, `tests/conftest.py`, the workflows or `dev-loop/bin`. | `vm-run` was not visible to the reviewer. Check it before acting on item 1. |
| Files run longest first | Confirmed, when `DECOY_TEST_ORDER_FILE` is set. | `tests/conftest.py`, `pytest_collection_modifyitems` |

## Work items, in order

Each item says what it saves, what could be lost, and how to prove the loss is zero.

### 1. Stop oversubscribing the Dell

- **Do:** set `POLARS_MAX_THREADS`, `OMP_NUM_THREADS`, `RAYON_NUM_THREADS` and the Arrow CPU count to
  1 or 2 for every xdist worker. Size the slot list so that workers times slots, plus the two gate
  runners, stays under the core count. Today 6 slots of 4 workers is 24 processes on 26 threads
  before any library thread pool starts.
- **Saves:** most of the gap between ideal and real wall-clock on full runs, and most load flakes.
  This is the largest item on the list.
- **Could lose:** nothing in coverage. A test that asserts a thread count or a speedup ratio may
  need the cap lifted; those already carry `serial`.
- **Prove:** run one head twice, before and after. Same failing ids, same collected count, lower
  wall-clock, lower load average.

### 2. Give the gate and T3 exclusive capacity, then raise their workers

- **Do:** pin cores per slot (cgroup v2 `AllowedCPUs`, for example through `systemd-run`), or give
  the gate its own machine. Then run T3 and the gate at more than 4 workers. `_gate_workers.py`
  measures about 1.3 GB peak per worker, so 12 workers fit in 43 GB.
- **Saves:** the ideal full run drops from about 56 minutes toward 20 to 25.
- **Could lose:** nothing in coverage. The baseline refuses a run at a different worker count, so
  this needs a fresh main baseline at the new count. Raising `LARGE_HOST_MAX_WORKERS` is an owner
  decision, since "raising workers" was set aside before.
- **Prove:** the new baseline's failing-id set equals the old one on the same main commit.

### 3. Make `serial` mean alone on the host

- **Do:** take the host lock around the serial pass in every run, not only in the gate.
- **Saves:** the wall-clock flake class and the triage time it costs. Serial tests wait for the
  lock; they no longer fail under load.
- **Could lose:** nothing. Watch for the stall guard: a run waiting on the lock must print a
  heartbeat.
- **Prove:** repeat the known load-sensitive ids 20 times on a busy node, before and after.

### 4. Add xdist to the CLI (CLI-PAR S1)

- **Saves:** 42 minutes serial to roughly 12 to 15 at 4 workers.
- **Could lose:** nothing, but tests that share state will fail on the first parallel run.
- **Prove:** same pass and fail set as the serial baseline, three runs in a row.

### 5. Replace the import-graph selector with a recorded coverage map (input to ENGINE-SELECT)

- **Do:** in the nightly run, record which source files each test file executes (coverage.py
  dynamic contexts). T1 selects the test files whose recorded coverage touches a changed file,
  plus the current near selection, plus the pins. Fall back to the full suite for any change the
  map cannot see: Rust, data and fixture files, the lock, `conftest.py`, a new test file, or a map
  older than its limit.
- **Why:** an import graph cannot separate tests when the package root imports most modules.
  Recorded execution can.
- **Saves:** a smaller T1 that also closes the "two or more hops away" blind spot of the near
  selection. The size is unknown until measured.
- **Could lose:** a test whose dependency is not visible as executed lines (a data file, a
  subprocess, an entry point).
- **Prove:** shadow mode for two weeks. Compute the selection, run what you run today, and record
  every failing id from full runs and gates. Each one must be inside the selection that would have
  been made. One miss is a finding, and its cause becomes a fallback rule.

### 6. E1, E2 and a tooling lane

- **E1 and E2:** do them as the report says. No coverage question.
- **E4:** move the release tooling tests to a lane that runs when their paths change, nightly, and
  on every push to main. About 34 of 222 test-minutes leave ordinary runs.
- **Could lose:** a registry or carrier edit that does not trigger the lane.
- **Prove:** a sentry that fails when a file the tooling tests import is missing from the lane's
  trigger list.

### 7. Close G1 by rule, not by name

- **Do:** do not add `tests/physical` to the workflow by hand. Add a check that every test id
  skipped for "companion not installed" in the companion-absent run appears as executed in the
  companion-present junit. `scripts/dev/junit_ran.py` and `scripts/ci/pytest_must_not_skip.py`
  already do most of this.
- **Saves:** no time. It adds about 720 tests of coverage and stops the same gap opening in a new
  directory.
- **Order:** before any cut to a native or physical matrix, as the report already says.

### 8. Matrix cuts E3 to E7 (each an owner decision)

- **Rule:** run the full product at the cheapest level that has it, pairwise plus every boundary
  cell end to end, and the full end-to-end product nightly.
- **Safe where:** the same product already runs cheaply lower down, as in E3 (299 kernel and
  chunked tests in 0.4 minutes).
- **Not zero loss:** a break that only one dropped end-to-end cell would catch is found the next
  night, not at merge. State this in the sign-off request.
- **Keep at full product:** leak and redaction matrices.
- **Prove:** the mutation check the report describes, on the glue the kept cells cover.

## Answers to the seven questions

1. **Selection.** Not sound as an import graph for this package shape. Use recorded coverage with
   fallbacks (item 5).
2. **`--dist loadfile` with 4 workers.** Keep `loadfile`. The ideal time of 222 test-minutes over
   4 workers shows distribution is already close to perfect, and files run longest first.
   Per-test distribution would rebuild module fixtures in each worker for little gain. The worker
   count is the part to change (item 2).
3. **Matrix sizing.** Pairwise is a safe reduction only under the rule in item 8.
4. **Slow tooling tests.** Yes (item 6).
5. **Shared, loaded nodes.** Items 1, 2 and 3, in that order. Buy dedicated gate hardware only if
   pinning is not enough.
6. **Baseline rule.** Two holes.
   - A test that stops running is not a new failing id. The collected count can stay equal while
     ids change (one added, one lost). Diff the id sets: every id that passed in the baseline and
     is now missing, skipped or deselected must be explained by the diff.
   - A flaky id recorded as failing in the baseline hides a real regression in that test. Give
     every baseline-failing id an expiry date, as quarantined tests already have.
7. **Cost above protection.** The derandomized Hypothesis tests. With `derandomize=True` they are
   fixed parametrized cases at 70 to 150 seconds each, so they pay the Hypothesis price without
   the exploration. Keep the fixed set on PRs. Add a randomized nightly run with a larger budget,
   and pin every failure it finds as an explicit `@example`. This adds coverage and costs no PR
   time. Nothing else in sections 3, 4 or 7 looked overpriced; the sentries are 8,100 tests but
   cheap.

## Open questions for the owner

1. Is `native-companion` a required check for an engine merge? The nodes skip 5,489 native tests,
   so if it is not required, the product's default route is not part of the merge evidence.
2. Does `vm-run` already cap thread pools or pin cores? If it does, item 1 shrinks to slot sizing.
3. May the worker cap for T3 and the gate be raised once those runs have exclusive cores (item 2)?

## Not done

- Nothing was measured. Items 1 and 2 rest on the load figures in the methodology page (load 22 to
  25) and on the absence of thread caps in the files listed above.
- `dev-rules/testing.md` and the roadmap were not edited. If items are adopted, they go through
  the normal roadmap triage; this page does not add roadmap entries.
- The CLI suite was not inspected beyond the figures in the report.
