Status: plan

# CHUNKED-STRUCT: `decoy run --chunked` on a struct column

Owner: Cam. Author: Opus (planner). Date: 2026-11-21. Roadmap row: CHUNKED-STRUCT in
`docs/roadmap/groups/run.md`.

Anchors: a path with no prefix is in this repository (decoy CLI); `E:` is decoy-engine. CLI
`origin/main` `7aa69642`; engine `origin/main` `49e5d815b`; the CLI pins `decoy-engine==0.28.2`.
The engine line numbers below are the same on `v0.28.2` and on `origin/main`.

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`,
`development-loop.md`, `bugfix.md`, `testing.md`, `proportionality.md`.

Risk: R1. One keyword argument in a private engine function, plus tests and a repin. Only columns
that crash today change behavior.

## 1. The bug

`decoy run --chunked` on a Parquet source with a struct column exits 3 with the internal error
`unhashable type: 'dict'`. The Dennis review of CLI #375 found it. It is on main before that PR.

Reproduced on the Mac test node through `vm-run` on CLI `7aa69642`, engine 0.28.2. Source: 5 rows,
`id` int64 (passthrough), `email` string (redact), `addr` struct<city, zip> with one null
(passthrough). Target: Parquet.

| Route | Result |
|---|---|
| `decoy run cfg.yaml` (plain) | exit 0, struct kept |
| `decoy run cfg.yaml --chunked --chunk-size 2` | exit 3, `TypeError: unhashable type: 'dict'` |
| the same two runs at 250,000 rows, `--chunk-size 50000` | plain exit 0; `--chunked` exit 3 |

## 2. Root cause

The traceback (`DECOY_DEBUG=1 ... --verbose`) goes from the CLI `_run_chunked_mask`
(`src/decoy/cli/run/_execute.py:132`) into the engine oracle `run_mask_pipeline_chunked`, then
`_oracle_preflight_admitted` (`E:src/decoy_engine/execution/_chunked_oracle.py:240`), then
`first_chunk_profile`, `walk_one_table`, `walk_dataframe` and `_walk_column`.

- The failing call is `sample_series.dropna().nunique()` at
  `E:src/decoy_engine/profile/_walk.py:190`. A struct cell is a Python `dict` in pandas, and
  `nunique` hashes it.
- `_walk_column` already skips `nunique` for list, struct and map columns (`_is_nested`,
  `_walk.py:154-161`, used at `:189`). It can only do that when the caller passes `arrow_schema` to
  `walk_dataframe`.
- The defect: `walk_one_table` (`E:src/decoy_engine/execution/_chunked_profile.py:36-49`, the
  `walk_dataframe(...)` call at `:42`) converts the chunk with `table.to_pandas()` and does not pass
  `arrow_schema=table.schema`. The plain-run profiler passes it (`E:src/decoy_engine/profile/_source.py:245`
  and `:291`), so the plain run works.

The defect is in engine code. The CLI only calls the public engine function.

Proof of the fix: a probe on the test node replaced `walk_one_table` with the same call plus
`arrow_schema=table.schema`. `run_mask_pipeline_chunked` then ran at 50 and 250,000 rows, and the
struct column was value-equal to the source. Through the CLI with the same patch, `--chunked` exited 0
for a Parquet target and a CSV target. The chunked Parquet output equalled the plain run's output
(`pa.Table.equals` true, type `struct<city: string, zip: string>`).

## 3. Overlap with RUN-STREAM (row 63a) slice C2

Plan `plan/run-stream-r6-5:docs/plans/2026-11-08-run-stream.md`, slice C2: "`--chunked` maps to
`execution_mode="stream"`; old fork and class removed".

(a) Does the crash sit in code that C2 removes? Only the CLI call site. C2 deletes
`_run_chunked_mask`, so the CLI stops calling `run_mask_pipeline_chunked`. The defect stays: it is in
the engine, and `run_mask_pipeline_chunked` and the other callers of `first_chunk_profile` and
`walk_one_table` (`_chunked_oracle.py:240` and `:250`, `_chunked_carry.py:117`) are not removed.

(b) Does the engine stream route handle struct columns? Yes. Probed on engine 0.28.2 with
`run_pipeline(execution_mode="stream", chunk_size_rows=16)`, a `LazySource` and a
`ParquetTransactionalSink`: it ran at 50 and 250,000 rows, and the struct was value-equal to the
source. With a resident `pa.Table` it refuses with `runtime.streaming_unavailable` ("a lazy source is
required"). That is the designed strict refusal and is not about the struct.

So C2 alone would fix the CLI symptom. It is not the right fix for V1:

- C2 is the last CLI slice of 63a. It waits on C1l, C1a, C1b, the REL-PKG wheel and DELIV C5. A
  function break must not wait on that chain.
- The engine defect stays live in the public `run_mask_pipeline_chunked` after C2.
- The engine fix is one keyword argument.

Decision: fix the engine now (S1), cover it from the CLI with the repin (S2), and add one fixture to
C2's parity set so C2 keeps the behavior (S3).

Other routes, checked on the same data:

| Route | Result on engine 0.28.2 |
|---|---|
| plain `decoy run`, CLI main | OK (resident pandas route) |
| `run_pipeline` resident, `auto` | OK at 50 and 250,000 rows |
| `run_pipeline` lazy, `auto`, no sink, `resident_fallback=True` (the C1l call) | OK at 50 and 250,000 rows |
| `run_pipeline` lazy, `auto`, with sink | OK at 250,000 rows (at 50 rows the output stays resident) |
| plain `decoy run` on CLI #372 (`feat/run-stream-c1l`) | OK; 250,000 rows took "pandas (streamed lane)" |
| `decoy run --chunked` on CLI #372 | exit 3 (the same oracle call as main) |
| `run_pipeline(execution_mode="stream")`, lazy, sink (the C2 route) | OK at 50 and 250,000 rows |

## 4. Guarantee and non-goals

Guarantee: `decoy run --chunked` on a Parquet source that holds list, struct or map columns as
passthrough, with masked scalar siblings, runs and writes the same values as a plain `decoy run` of
the same config. A Parquet target keeps the Arrow type of each nested column.

Non-goals:

- Masking strategies on a nested column. Validation and the plan compiler decide that today. This
  row does not change it.
- How a CSV target writes a nested cell. The plain run and the fixed chunked run write the same text
  (`{'city': 'A', 'zip': '1'}`). A CSV encoding for nested values is a separate question.
- A struct refusal. With the fix nothing is refused, so no reason code or message is added. If a
  later finding shows a nested shape that the chunked route cannot run, it must refuse before the
  first chunk with a registered reason code and a value-free message (table, column name and Arrow
  type only), never exit 3. That is a rule for the follow-up, not work in this row.

Design notes: none. No new structure. The fix reuses the existing `_is_nested` guard the same way
the plain profiler does. Established solutions: not applicable to an R1 one-argument fix.

## 5. Behavior and failure modes

| Case | Today | After S1 and S2 |
|---|---|---|
| `--chunked`, struct passthrough, masked sibling, Parquet to Parquet | exit 3, `unhashable type: 'dict'` | exit 0; values equal the plain run; struct type kept |
| `--chunked`, list or map passthrough | same crash class (list and map cells are not hashable in pandas) | exit 0; values equal the plain run |
| `--chunked`, struct column all null in the first chunk | no values to hash, so no crash | unchanged |
| `--chunked`, nested column, empty source | `empty_input_profile` walks an empty frame; no crash | unchanged |
| `--chunked`, Parquet source to CSV target | exit 3 | exit 0; same text as the plain run |
| plain run, every route | OK | unchanged |
| `--chunked` after C2 (stream route) | not built | output equals the plain run (S3) |

What could go wrong with the fix, and the guard for it:

- The first-chunk profile of a nested column changes from a crash to `distinct_count=None`. The
  chunked admission reads no distinct count for a passthrough column (`first_chunk_profile`
  docstring: faker pools size from the declared `pool_size`). AT-2 compares the whole output with the
  resident run, so any change to how the sibling column is masked shows there.
- Scalar columns must keep their distinct counts. AT-1 checks the string sibling's count.
- No message text changes, so log hygiene is not affected.

## 6. Acceptance tests

Each test fails before the fix. The builder runs each mutation once and records it red in the PR.

| ID | Slice | Test | Fails before the fix because | Mutation that proves it bites |
|---|---|---|---|---|
| AT-1 | S1 | `first_chunk_profile` on a chunk with `addr` struct (one null), `tags` list<string>, `attrs` map<string,string> and `email` string returns a profile. The three nested columns have `distinct_count is None`. `email` has its real distinct count. Every column is `sampled=True` | `walk_one_table` raises `TypeError` | M-1: remove `arrow_schema=table.schema` from `walk_one_table` (red with `TypeError`) |
| AT-2 | S1 | `run_mask_pipeline_chunked` on the AT-1 columns (redact `email`, the rest passthrough). Hypothesis with a fixed seed draws the row count, the chunk size (including 1 and sizes that do not divide the row count) and the null positions. The concatenated output equals `run_pipeline(..., auto_chunk=False)` on the same table by `pa.Table.equals`, and every nested Arrow type is kept | the preflight raises `TypeError` | M-1; M-2: drop `pat.is_struct(arrow_type)` from `_is_nested` in `_walk.py` (red on the struct column only) |
| AT-3 | S1 | `walk_one_table` on a one-column struct table (the call shape of `_chunked_carry.diagnose_profile`) returns without error | the same `TypeError` | M-1 |
| AT-4 | S2 | CLI e2e `tests/e2e/test_run_chunked_struct.py`. Parquet source with `id` int64, `email` string, `addr` struct (one null) and `tags` list<string>; the config redacts `email` and passes the rest through. `decoy run --chunked --chunk-size 2` exits 0. Its output equals a plain `decoy run` of the same config by `pa.Table.equals`. `addr` and `tags` keep their types. `email` holds no source value | exit 3 on engine 0.28.2 | M-4: in the test process, patch `decoy_engine.execution._chunked_profile.walk_one_table` back to the 0.28.2 body (no `arrow_schema`); red with exit 3. A one-time run, not a kept test |
| AT-5 | S2 | The same source with a CSV target: `--chunked` and plain both exit 0 and write the same bytes | exit 3 on the `--chunked` side | M-4 |
| AT-6 | S3 (in 63a C2) | The AT-4 source and config join the AT-C2a fixture set. Under C2, `--chunked` (the stream route) exits 0 and its output equals the plain run | C2 is not built; after C2 it guards the new route | M-6: make the C2 strict preflight refuse a table with a nested column; AT-6 turns red |

Guard, not a fail-before test: the plain run of the AT-4 source stays exit 0. That is true today.
When CLI #372 (C1l) merges, its AT-C1l cells take the same source at 250,000 rows, which runs on the
streamed lane (seen in the probe).

### 6.1 Defect catalog classes

| Class | Name | Closing structure | Sentry or property test | Mutation |
|---|---|---|---|---|
| 1 | value leak | no message, log or error text is added; the masked sibling is pinned equal to the plain run, and AT-4 checks no source `email` value reaches the output | AT-2, AT-4 | M-1 |
| 2 | cleanup | N/A: no new file, temp path or handle; the chunked writer and its staging are unchanged | existing chunked e2e tests | N/A |
| 3 | state | N/A: `walk_one_table` is a pure function of its input table; no shared state is added | AT-1 | N/A |
| 4 | route | the plain, lazy (C1l), oracle `--chunked` and stream (C2) routes were each probed with a struct column; AT-2 and AT-4 pin chunked equal to plain, AT-6 pins the C2 route | AT-2 (Hypothesis over chunk size and nulls), AT-4, AT-6 | M-1, M-6 |
| 5 | referential | N/A: no FK or key logic changes; nested columns are passthrough only | none needed | N/A |
| 6 | untrusted input | the source file is untrusted data; the fix reads only its Arrow schema, which the reader already holds | AT-1 | N/A |
| 7 | TOCTOU (check-then-use) | the schema passed is the schema of the same in-memory chunk that is converted, so nothing is checked on one object and used on another | AT-3 | N/A |
| 8 | weak tests | each fail-before test has a named mutation that turns it red; AT-2 compares whole tables, not values only | AT-1 to AT-5 | M-1, M-2, M-4 |
| 9 | refactor | N/A: no code moves | none needed | N/A |
| 10 | frozen contracts | `walk_one_table` is private; `run_mask_pipeline_chunked` keeps its signature; no CLI flag, exit code or reason code changes | the existing engine public-API snapshot | N/A |

### 6.2 Enumerations

#### 6.2.1 Exit paths

- `--chunked` run succeeds: exit 0 (AT-4, AT-5).
- Engine refusal before the run (compatibility gate, subset, integrity): exit 1, unchanged.
- Internal error: exit 3. Today a nested column reaches it; after S1 it does not (AT-4, M-4).
- Stream route without a lazy source (C2 only): `runtime.streaming_unavailable`, exit 1, unchanged.

#### 6.2.2 Routes

- Plain resident run: OK today (probe, section 3).
- Plain lazy run, C1l with `resident_fallback=True`: OK today (probe).
- Oracle `--chunked` (`run_mask_pipeline_chunked`): crashes today; fixed by S1 (AT-2, AT-4).
- Stream `--chunked` (C2, `execution_mode="stream"`): OK in the probe; pinned by AT-6.
- `walk_one_table` caller `first_chunk_profile` (`_chunked_profile.py:99`, reached from
  `_chunked_oracle.py:240` and `:250`): AT-2.
- `walk_one_table` caller `_chunked_carry.diagnose_profile` (`_chunked_carry.py:117`): AT-3.

#### 6.2.3 FK shapes

N/A: nested columns are passthrough only, and the fix touches no FK or key logic.

#### 6.2.4 Fields

- struct: AT-1, AT-2, AT-4.
- list and large list, fixed-size list: AT-1, AT-2 and AT-4 use list; the other two take the same
  `_is_nested` branch (`_walk.py:154-161`).
- map: AT-1, AT-2.
- scalar siblings (string, int64): profile fields unchanged (AT-1), masked output unchanged (AT-2).

#### 6.2.5 Output surfaces

- Parquet target: values equal plain, nested types kept (AT-4).
- CSV target: same bytes as plain (AT-5).
- Run summary card and `--json`: unchanged, no new text.

### 6.3 Frozen contracts

None change. `walk_one_table` is private. `run_mask_pipeline_chunked`, `run_pipeline`, the CLI
flags, the exit codes and the reason registry are unchanged. The repin follows the engine repin
checklist.

## 7. Reuse inventory

| Need | Reuse | Where |
|---|---|---|
| Skip `nunique` on nested columns | the existing `_is_nested` guard in `_walk_column` | `E:src/decoy_engine/profile/_walk.py:154-161`, `:189` |
| Pass the schema to the walk | the existing `arrow_schema` keyword, as the plain profiler passes it | `E:src/decoy_engine/profile/_source.py:245`, `:291` |
| Resident reference output for AT-2 | `run_pipeline(..., auto_chunk=False)`, as the RUN-STREAM tests use it | `E:tests/unit/execution/run_stream/_support.py` (`reference`) |
| CLI chunked e2e harness | the existing chunked Parquet e2e pattern (`CliRunner`, `app`, `mask_secret` fixture) | `tests/e2e/test_run_chunked_parquet.py` |

## 8. Pre-mortem

Assume a user still hits a nested-column crash on `--chunked` after 1.0. Likely causes and guards:

- **Another unhashable walk on chunk 0.** A second profile call that converts to pandas without the
  schema. Guard: section 6.2 lists every `walk_one_table` caller, and AT-2 runs the whole oracle
  preflight, not only the profile function.
- **A nested column inside a masked column's input.** Out of scope (section 4). Validation decides
  today; a crash there is a new finding with a coded refusal, never exit 3.
- **C2 drops the fixture.** Guard: S3 puts the source in the AT-C2a fixture set, and M-6 proves the
  cell bites.

## 9. Placement

| File | Repo | Directory | Sits beside | CODEMAP line | Change |
|---|---|---|---|---|---|
| `_chunked_profile.py` | engine | `E:src/decoy_engine/execution/` | `_chunked_oracle.py`, `_chunked_carry.py` | the `execution/` row: "the Arrow-native column profile lives in `_chunked_profile.py`" | `walk_one_table` passes `arrow_schema=table.schema` |
| `test_chunked_profile_nested.py` (new) | engine | `E:tests/unit/execution/` | `test_auto_chunk_*.py` | the `tests/unit/execution/` tree | AT-1, AT-2, AT-3 |
| `CHANGELOG.md` | engine | root | | | one Fixed line under Unreleased |
| `pyproject.toml`, `uv.lock` | CLI | root | | | repin to the engine release that holds S1; the engine repin checklist applies |
| `test_run_chunked_struct.py` (new) | CLI | `tests/e2e/` | `test_run_chunked.py`, `test_run_chunked_parquet.py` | the e2e tree | AT-4, AT-5 |
| `CHANGELOG.md` | CLI | root | | | one Fixed line |
| `docs/roadmap/groups/run.md` | CLI | | | | row CHUNKED-STRUCT status; a note on row 63a that AT-C2a carries the struct fixture |
| `docs/plans/2026-11-08-run-stream.md` | CLI | branch `plan/run-stream-r6-5` | | | AT-C2a names the struct fixture (S3) |

Size: about 5 engine source lines, about 120 engine test lines and about 120 CLI test lines. No new
source module, no new public name, no new reason code.

## 10. Slices

| Slice | Repo | Risk | Content | Gate |
|---|---|---|---|---|
| S1 | engine | R1 | the `walk_one_table` fix, AT-1 to AT-3, CHANGELOG | Codex. T1 impact selection on the head |
| S2 | CLI | R1. The repin is a version pin, which is a full-suite trigger | repin to the release with S1 (ride the daily engine release train and its normal repin), AT-4, AT-5, CHANGELOG, roadmap status | Codex. Full suite on the merge head, diffed against the saved main baseline |
| S3 | CLI, inside 63a C2 | as C2 | the struct fixture joins AT-C2a. No separate PR | C2's own gate |

Order: S1, then an engine release, then S2. S3 is a note on the 63a plan now; whoever builds C2
builds it. S1 and S2 touch no file that C1l or C2 edits, so they neither block 63a nor wait for it.
If C2 merges first (not expected), S2 still ships: AT-4 then runs on the stream route, and the
repin still fixes the public engine function.

Row close: CHUNKED-STRUCT closes when S2 merges. S3 stays with row 63a.

## 11. V1 bar check

- A function break (a supported input type makes a documented flag exit 3) blocks 1.0 under the V1
  bar. S1 and S2 are V1. S3 is V1 because 63a C2 is.
- No data loss and no leak. The fix runs a passthrough column the user asked to pass through. The
  masked sibling's output is pinned equal to the plain run (AT-2, AT-4). No log or error text is
  added.
- No frozen surface changes. `walk_one_table` is private, and `run_mask_pipeline_chunked` keeps its
  signature.
