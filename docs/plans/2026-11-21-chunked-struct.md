Status: plan (revision 3, 2026-11-21; Codex r2 NO-GO remediated)

# CHUNKED-STRUCT: `decoy run --chunked` on a struct column

Owner: Cam. Author: Opus (planner). Date: 2026-11-21. Roadmap row: CHUNKED-STRUCT in
`docs/roadmap/groups/run.md`.

Anchors: a path with no prefix is in this repository (decoy CLI); `E:` is decoy-engine. CLI
`origin/main` `7aa69642`; engine `origin/main` `713c047db`; the CLI pins `decoy-engine==0.28.2`.
The engine line numbers below are the same on `v0.28.2`, `49e5d815b` and `713c047db`. Probes ran on
pyarrow 24.0.0.

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`,
`development-loop.md`, `bugfix.md`, `testing.md`, `proportionality.md`, `code-review.md`,
`release-and-rollback.md`, `config-secrets-and-supply-chain.md` (dependency pins and locks),
`api-and-compatibility.md` (the output schema change), `documentation.md`, `workspace-and-vcs.md`,
`catalogs/recurring-defects.md` (11 classes).

Risk: R1 for the code size (two private engine functions and tests, plus a repin). The plain-run
output schema of nested passthrough columns changes, which is a frozen-output change, so S1 takes the
engine full suite (section 6.4, section 10).

## Review changes

| Round | Finding | Resolution | Sections |
|---|---|---|---|
| r1-1 (V1) | passing `arrow_schema` only fixes profiling; a null-only final chunk infers struct and list as `null` and `pa.concat_tables` raises `ArrowInvalid` | S1 also fixes the output rebuild at its one existing place (`E:execution/_fk_keys.py:485-512`) | 2.2, 4, 10 |
| r1-2 (V1) | list and map coverage must stand alone | deterministic non-null cells for struct, list and map; separate mutations; the null-only single-row final chunk is a regular example; map in AT-5 and AT-8 | 6 |
| r1-3 (DESIGN) | flat test folders; engine `changelog.d/` | engine cases fold into existing files; CLI cases into `tests/e2e/test_run_chunked_parquet.py`; fragment `E:changelog.d/chunked-struct.md` | 9 |
| r1-4 | CLI lock is `requirements-dev.lock` | fixed | 9, 10 |
| r1-5 | durable C2 handoff; M-4 when C2 lands first | note committed on `plan/run-stream-r6-5` at AT-C2a; section 10 | 3, 10 |
| r1-6 | 11-class catalogue; rulebooks | section 6.2; the "Rules consulted" line | 6.2 |
| r2-1 (V1) | the rebuild drops every column when all are untouched nested, `from_pandas` of the empty frame has zero rows, and the first `add_column` raises `ArrowInvalid: Expected length 0 but got length N` | reproduced, and it is live on main today for a table whose only columns are passthrough maps (2.3). S1 builds the all-nested result directly from the rebuilt arrays, so the row count is kept. AT-4b and AT-2e cover non-empty all-nested tables on the resident and oracle routes, with mutation M-K | 2.3, 4, 6, 10 |
| r2-2 (DESIGN) | do not add a generic `is_nested()`; PyArrow's exists | no new general predicate. The profile walk uses `pa.types.is_nested` (as `E:io/bounded_reader.py:207` and `E:safe_output/_file_metadata.py:152` do). The rebuild has its own narrow, precisely named predicate, `_rebuilds_with_source_type`, and one catalogue guard (AT-2d) | 4, 6, 9 |
| r2-3 | the masked-nested coverage is `E:tests/parity/test_nonfk_dtype_matrix.py:628-693` | named in S1's test selection; mutation M-U removes `f.name in untouched` | 6, 10 |
| r2-4 | the plain-run schema change is a frozen-output change; S1 needs the engine full suite | section 6.4 says so; S1's test depth is T3 | 6.4, 10 |

## 1. The bug

`decoy run --chunked` on a Parquet source with a struct column exits 3 with the internal error
`unhashable type: 'dict'`. The Dennis review of CLI #375 found it. It is on main before that PR.

Reproduced on the Mac test node through `vm-run` on CLI `7aa69642`, engine 0.28.2. Source: 5 rows,
`id` int64 (passthrough), `email` string (redact), `addr` struct<city, zip> with one null
(passthrough). Target: Parquet.

| Route | Result |
|---|---|
| `decoy run cfg.yaml` (plain) | exit 0 |
| `decoy run cfg.yaml --chunked --chunk-size 2` | exit 3, `TypeError: unhashable type: 'dict'` |
| the same two runs at 250,000 rows, `--chunk-size 50000` | plain exit 0; `--chunked` exit 3 |

## 2. Root cause

Three defects. Each one hides the next.

### 2.1 Profile walk

The traceback (`DECOY_DEBUG=1 ... --verbose`) goes from the CLI `_run_chunked_mask`
(`src/decoy/cli/run/_execute.py:132`) into the engine oracle `run_mask_pipeline_chunked`, then
`_oracle_preflight_admitted` (`E:src/decoy_engine/execution/_chunked_oracle.py:240`), then
`first_chunk_profile`, `walk_one_table`, `walk_dataframe` and `_walk_column`.

- The failing call is `sample_series.dropna().nunique()` at
  `E:src/decoy_engine/profile/_walk.py:190`. A struct cell is a Python `dict` in pandas, a map cell
  a Python `list`, a list cell a NumPy array. None of them hash.
- `_walk_column` already skips `nunique` for nested columns (private `_is_nested`, `_walk.py:153-161`,
  used at `:189`), but only when the caller passes `arrow_schema` to `walk_dataframe`.
- `walk_one_table` (`E:src/decoy_engine/execution/_chunked_profile.py:36-49`, the call at `:42`)
  does not pass `arrow_schema=table.schema`. The plain-run profiler does
  (`E:src/decoy_engine/profile/_source.py:245` and `:291`).

### 2.2 Output rebuild keeps only maps

After the pandas adapter masks a frame, `table_from_pandas_keeping_maps`
(`E:src/decoy_engine/execution/_fk_keys.py:485-512`, called from
`E:execution/_pandas_adapter.py:319-323` and `E:execution/_sequential.py:521`) rebuilds Arrow with
`pa.Table.from_pandas`. Untouched map columns get their source type back. Untouched struct and list
columns are inferred from the Python cells. The public oracle does not use the carry plan
(`carry_passthrough` is False, `E:execution/_chunked_oracle.py:189-191`), so every passthrough column
goes through pandas.

### 2.3 Output rebuild loses the row count when every column is a rebuilt one

The rebuild drops the rebuilt columns, converts the rest with `from_pandas`, and adds the rebuilt
arrays back (`_fk_keys.py:503-510`). When no column is left, `from_pandas` of the empty frame has zero
rows, and the first `add_column` raises `ArrowInvalid: Added column's length must match table's
length. Expected length 0 but got length N`. On main this already breaks a plain run of a table whose
only columns are passthrough maps.

### 2.4 Probe evidence

Engine `713c047db`, Dell node, `vm-run engine`. "Resident" is `run_pipeline(..., auto_chunk=False)`;
"oracle" is `run_mask_pipeline_chunked` with chunk size 2 and `pa.concat_tables`. EXACT means every
passthrough column equals the source, type included. "Fixed" is the S1 design (section 4), patched in
at run time.

| Case | Main, resident | Main, oracle | Fixed, resident and oracle |
|---|---|---|---|
| map only (3 rows) | `ArrowInvalid` length 0 (2.3) | `TypeError` | EXACT |
| struct, list and map only, no scalar column | struct int32 field widens to int64 | `TypeError` | EXACT |
| struct, list, map beside a redact column, final row null | struct field widens | `TypeError`; with only 2.1 fixed, `ArrowInvalid` at concat | EXACT |
| catalogue `struct`, final row null | `struct<a: int64>` becomes `struct<a: double>` | `TypeError` | EXACT |
| catalogue `large_list`, with and without null | becomes `list` | `TypeError` | EXACT |
| catalogue `fixed_size_list` | becomes `list` | `TypeError` | EXACT |
| catalogue `list`, `map`, with and without null | EXACT | `TypeError` | EXACT |
| catalogue `list_view`, `large_list_view`, `dense_union`, `sparse_union` | Parquet cannot store the type (`ArrowNotImplementedError` on write) | same | not reachable from a Parquet source |
| catalogue `fixed_size_list` with a null cell | `ArrowInvalid: Expected all lists to be of size=1` (also on main, from an earlier step) | `TypeError` | the same `ArrowInvalid`; see section 4, follow-up |

Mutation probe: rebuilding every column, masked or not (dropping `f.name in untouched`), makes a
redacted map column fail with `ArrowTypeError: Could not convert 'R' ... expecting tuple of (key,
value) pair` on both routes.

## 3. Overlap with RUN-STREAM (row 63a) slice C2

Plan `plan/run-stream-r6-5:docs/plans/2026-11-08-run-stream.md`, slice C2: "`--chunked` maps to
`execution_mode="stream"`; old fork and class removed".

(a) Does the crash sit in code C2 removes? Only the CLI call site. C2 deletes `_run_chunked_mask`, so
the CLI stops calling `run_mask_pipeline_chunked`. All three defects are in the engine and stay. The
oracle stays public, and the rebuild also serves the plain resident run and `_sequential`.

(b) Does the engine stream route handle struct columns? Yes. On engine 0.28.2 and on `49e5d815b`,
`run_pipeline(execution_mode="stream")` with a `LazySource` and a `ParquetTransactionalSink` ran at
50 and 250,000 rows, and with 17 rows, chunk 16 and a null-only final row. Struct (with its int32
field), list and map came back equal to the source. A spy showed the stream route does not call the
rebuild function: it keeps passthrough columns out of pandas. With a resident `pa.Table` the stream
route refuses with `runtime.streaming_unavailable`, the designed strict refusal.

So C2 would hide the `--chunked` crash in the CLI and fix none of the engine defects. It also waits
on C1l, C1a, C1b, REL-PKG and DELIV C5. Decision: fix the engine now (S1), cover it from the CLI with
the repin (S2), and keep C2's parity set honest with a nested fixture (S3, note committed on
`plan/run-stream-r6-5` beside AT-C2a).

Other routes on the same data: the C1l lazy call (`resident_fallback=True`) ran at 50 and 250,000
rows; plain `decoy run` on CLI #372 exited 0 and took "pandas (streamed lane)" at 250,000 rows;
`decoy run --chunked` on CLI #372 exits 3 like main.

## 4. Guarantee, design and non-goals

Guarantee:

1. `decoy run --chunked` on a Parquet source whose nested columns (list, large list, fixed-size list
   without null cells, struct, map) are passthrough runs, with or without masked scalar siblings, and
   also when every column is nested. Its output equals a plain `decoy run` of the same config,
   whatever the chunk size and wherever the nulls fall.
2. On every route that rebuilds output from pandas (the plain resident run, `_sequential`, the
   oracle), an untouched column of those types comes back with its source field type and values, and
   the table keeps its row count.

Design:

- Profile walk: `walk_one_table` passes `arrow_schema=table.schema`. `_walk_column` uses PyArrow's
  `pa.types.is_nested` in place of its private `_is_nested`, the same predicate
  `E:io/bounded_reader.py:207` and `E:safe_output/_file_metadata.py:152` use. Skipping `nunique` for
  unions and list views too is correct: their cells do not hash either. `_mixed_admission.py` keeps
  its own check; this row does not touch it.
- Output rebuild: `table_from_pandas_keeping_maps` becomes `table_from_pandas_keeping_source_types`.
  It rebuilds each untouched column whose type passes a private predicate,
  `_rebuilds_with_source_type(t)` (list, large list, fixed-size list, struct, map: the types a Parquet
  source can hold and the probe rebuilt exactly), with `pa.array(frame[name], type=field.type,
  from_pandas=True)`. Other columns convert with `pa.Table.from_pandas` as today. When no other column
  is left, the result is built directly from the rebuilt arrays in frame column order, so the row
  count is the frame's. One catalogue guard (AT-2d) fails when a nested type that Parquet can store
  is outside the predicate, or inside it and not rebuilt exactly.
- Established pattern: rebuild Arrow from pandas with the declared source type instead of inference,
  which the function already does for maps.

Non-goals:

- Masking strategies on a nested column. A masked column converts as today (pinned by
  `E:tests/parity/test_nonfk_dtype_matrix.py:628-693`).
- List views and unions. Parquet cannot store them, so no CLI source reaches the rebuild with them.
- A fixed-size list with a null cell. It fails on main from an earlier step than the rebuild
  (`ArrowInvalid: Expected all lists to be of size=1`), on the plain run as well. It is a separate
  defect with its own root cause. It goes to the coordinator for a roadmap row; this row does not fix
  it, and AT-2d records it as the one known exception.
- How a CSV target writes a nested cell. The plain and chunked runs write the same text.
- A refusal. Nothing is refused, so no reason code is added. If a later finding shows a nested shape
  the chunked route cannot run, it must refuse before the first chunk with a registered reason code
  and a value-free message (table, column name and Arrow type only), never exit 3.

## 5. Behavior and failure modes

| Case | Today | After S1 and S2 |
|---|---|---|
| `--chunked`, struct, list and map passthrough, masked sibling | exit 3, `TypeError` | exit 0; equal to the plain run |
| `--chunked`, only nested columns | exit 3 | exit 0; row count and types kept |
| `--chunked`, a null-only final chunk (one row) or first chunk | `ArrowInvalid` once 2.1 is fixed | exit 0; types kept |
| plain run, only passthrough map columns | `ArrowInvalid` length 0 | exit 0 |
| plain run, struct with an int32 field, or a struct whose last row is null | field widens to int64 or double | source type kept |
| plain run, large list or fixed-size list | becomes `list` | source type kept |
| plain run, all-null struct or list column | type becomes `null` | source type kept |
| masked nested column (any route) | strategy output | unchanged |
| `--chunked`, Parquet source to CSV target | exit 3 | exit 0; same text as the plain run |
| `--chunked` after C2 (stream route) | not built | equal to the plain run (S3) |

What could go wrong with the fix, and the guard:

- `untouched_columns` marks a strategy-changed column untouched, and the rebuild forces the source
  type onto strategy output. Guard: `E:tests/parity/test_nonfk_dtype_matrix.py:628-693` (masked map
  on full frame, sequential and FK routes) in S1's selection; M-U turns it red (probe in 2.4).
- `pa.array(..., type=field.type)` cannot rebuild a type in the predicate. Guard: AT-2d runs every
  `pa.types.is_nested` entry of the type catalogue.
- The all-nested path builds a table without pandas schema metadata. Output equality in AT-2e and
  AT-4b compares data and types; the Parquet writer does not need the pandas metadata.
- The first-chunk profile of a nested column becomes `distinct_count=None`. The chunked admission
  reads no distinct count for a passthrough column (`first_chunk_profile` docstring). AT-2 compares
  the whole output with the resident run.
- No message or log text changes.

## 6. Acceptance tests

Each test fails before the fix. The builder runs each mutation alone on the final head and records it
red, with the head, in the PR (recurring class 9).

Fixture F (deterministic): `email` string; `addr` struct<city string, zip int32>; `tags`
list<string>; `attrs` map<string, string>. Rows 0 and 1 hold non-null cells in every column
(`{"city": "c0", "zip": 0}`, `["t0", "x"]`, `[("k", "v0")]` and so on). Row 2 is null in every
nested column. Chunk size 2, so the final chunk is the single null row. Fixture F-N is F without
`email`: every column is nested.

| ID | Slice | Test | Fails before the fix because | Mutations that prove it bites |
|---|---|---|---|---|
| AT-1 | S1 | `first_chunk_profile` on rows 0 and 1 of F: nested columns have `distinct_count is None`, `email` has 2, every column is `sampled=True`. Parametrized over struct alone, list alone and map alone | `TypeError` | M-1: remove `arrow_schema=table.schema` from `walk_one_table` |
| AT-2a | S1 | `run_mask_pipeline_chunked` on F (redact `email`), chunk 2: output equals the source in every nested column, schema included, and equals the resident run by `pa.Table.equals`. A regular example | `TypeError`; `ArrowInvalid` with only M-1 fixed | M-1; M-R: restore the maps-only rebuild; M-L: drop `is_list` from `_rebuilds_with_source_type` (red on `tags`); M-S: drop `is_struct` (red on `addr`); M-M: drop `is_map` (red on `attrs`) |
| AT-2b | S1 | AT-2a with the null row first, then with every nested cell null | `ArrowInvalid`; type `null` | M-R |
| AT-2c | S1 | Hypothesis, fixed seed: row count, chunk size (1 up to row count) and null positions drawn; output equals the source and the resident run | as AT-2a | M-R |
| AT-2d | S1 | catalogue guard: every entry of `E:tests/native/_rev9_type_catalogue.py` whose type passes `pa.types.is_nested`, with and without a null, beside a redact column, through the resident run and the oracle. A type Parquet can store must be in `_rebuilds_with_source_type` and come back exact. A type Parquet cannot store (list views, unions) must be outside it. The fixed-size list with a null cell is the one listed exception (section 4), asserted to fail as on main so a later fix shows | `TypeError`; resident type drift for `large_list`, `fixed_size_list`, `struct` with a final null | M-1, M-R, M-L |
| AT-2e | S1 | oracle on F-N (no scalar column), chunk 2: row count 3, every column equals the source | `TypeError`; then `ArrowInvalid` length 0 | M-K: build the all-nested result through `from_pandas` of the empty frame, as today |
| AT-3 | S1 | `walk_one_table` on a one-column table for each of struct, list and map (the `_chunked_carry.diagnose_profile` call shape) returns | `TypeError` | M-1 |
| AT-4a | S1 | resident run on F: output schema equals the source schema (int32 `zip` kept); with every nested cell null, struct and list keep their types | int64 `zip`; type `null` | M-R |
| AT-4b | S1 | resident run on a map-only table and on F-N: exit clean, row count kept, columns equal the source | `ArrowInvalid` length 0 | M-K |
| AT-5 | S2 | CLI e2e in `tests/e2e/test_run_chunked_parquet.py`: F as Parquet, config redacts `email`, passes the rest. `decoy run --chunked --chunk-size 2` exits 0; output equals a plain `decoy run` by `pa.Table.equals`; output schema equals the source schema; `email` holds no source value. Second cell: F-N | exit 3 on engine 0.28.2 | M-4: patch `walk_one_table` back to the 0.28.2 body; M-4b: patch the rebuild back to maps-only. One-time runs, not kept tests |
| AT-6 | S2 | the same files, plain `decoy run` only: the output schema equals the source schema; F-N exits 0 | int64 `zip` on engine 0.28.2 | M-4b |
| AT-7 | S2 | F with a CSV target: `--chunked` and plain both exit 0 and write the same bytes | exit 3 on the `--chunked` side | M-4 |
| AT-8 | S3 (in 63a C2) | F and F-N join the AT-C2a fixture set. Under C2, `--chunked` (stream route) exits 0, and the output equals the plain run and the source schema, map included | C2 not built; guards the new route | M-6 (M-C2a6 in the run-stream plan): refuse a table with a nested column in the strict preflight |

Existing tests that S1 must keep green and names in its selection: the masked map cells in
`E:tests/parity/test_nonfk_dtype_matrix.py:628-693` (mutation M-U: remove `f.name in untouched` from
the rebuild; red with `ArrowTypeError`), `E:tests/native/test_unconfigured_passthrough_types.py`, and
the `_sequential` and pandas adapter tests (the rebuild's two callers).

### 6.1 Plan contract classes

| Class | Name | Closing structure | Sentry or property test | Mutation |
|---|---|---|---|---|
| 1 | value leak | no message, log or error text is added; AT-5 checks no source `email` value reaches the output | AT-2a, AT-5 | M-1 |
| 2 | cleanup | N/A: no new file, temp path or handle | existing chunked e2e tests | N/A |
| 3 | state | N/A: `walk_one_table` and the rebuild are pure functions of their inputs | AT-1, AT-2a | N/A |
| 4 | route | plain resident, plain lazy (C1l), oracle `--chunked` and stream (C2) were each probed; AT-2 and AT-5 pin chunked equal to plain; AT-8 pins the C2 route | AT-2c (property), AT-5, AT-8 | M-R, M-6 |
| 5 | referential | N/A: no FK or key logic changes; `_sequential` gains only the rebuild fix, kept green by the masked map FK cells | `E:tests/parity/test_nonfk_dtype_matrix.py:628-693` | M-U |
| 6 | untrusted input | the source file is untrusted data; the fix reads only the Arrow schema the reader already holds | AT-1 | N/A |
| 7 | TOCTOU (check-then-use) | the profile uses the schema of the same chunk it converts; the rebuild uses the source schema the adapter already holds | AT-2b | N/A |
| 8 | weak tests | each fail-before test has its own mutation; equality is on whole tables with schema; the all-nested shape has its own cells | AT-1 to AT-7 | M-1, M-R, M-L, M-S, M-M, M-K, M-U, M-4, M-4b |
| 9 | refactor | the private `_is_nested` gives way to `pa.types.is_nested`; the rebuild is renamed; behavior changes only for untouched nested columns | AT-2a, AT-4a, AT-2d | M-R |
| 10 | frozen contracts | the plain-run output schema of nested passthrough columns changes (6.4); no signature, flag, exit code or reason code changes | AT-4a, AT-6; engine full suite on S1 | M-R |

### 6.2 Recurring defect classes (`catalogs/recurring-defects.md`)

| # | Class | Applies | How this plan meets it |
|---|---|---|---|
| 1 | Anchored validation | No | no pattern validation is added |
| 2 | Strict wire and stored types | No | no persisted or wire model changes |
| 3 | No exception context | No | no error is raised or wrapped |
| 4 | Versioned read models | No | no reader of a persisted format changes |
| 5 | Normalized guard scanners | Yes, one entry | `E:tests/native/test_column_access_surfaces.py:262` lists the rebuild by name; the rename edits that one entry and adds nothing |
| 6 | No reaching into private modules | Yes | the engine uses PyArrow's public `pa.types.is_nested`; the new predicate is private to `_fk_keys.py`; the CLI imports no engine private name. CLI mutations patch an engine private only in a one-time run, never in a kept test |
| 7 | No hidden CI failures | No | no CI change |
| 8 | One input, one trust class per entry point | No | no new entry point |
| 9 | Mutations on the final head | Yes | every mutation is rerun on the final head; the head is recorded |
| 10 | Allowlisted helpers are still checked | No | no allowlist entry is added |
| 11 | No raised caps | Yes | `_fk_keys.py` is 530 lines and grows by about 10; `_walk.py` shrinks; no size cap, ratchet or allowlist grows. A moved line-count pin is listed in the report |

### 6.3 Enumerations

#### 6.3.1 Exit paths

- `--chunked` run succeeds: exit 0 (AT-5, AT-7). The CLI call is `src/decoy/cli/run/_execute.py:132`.
- Engine refusal before the run (compatibility gate, subset, integrity): exit 1, unchanged.
- Internal error: exit 3. Today a nested column reaches it; after S1 it does not (AT-5, M-4, M-4b).
- Stream route without a lazy source (C2 only): `runtime.streaming_unavailable`, unchanged.

#### 6.3.2 Routes

- Plain resident run: rebuild at `E:execution/_pandas_adapter.py:319`; type drift and the map-only
  crash today; fixed by S1 (AT-4a, AT-4b, AT-6).
- Plain lazy run, C1l with `resident_fallback=True`: runs today (probe).
- Oracle `--chunked` (`run_mask_pipeline_chunked`, preflight at `E:execution/_chunked_oracle.py:240`):
  crashes today; fixed by S1 (AT-2, AT-5).
- `_sequential` FK route: the same rebuild (`E:execution/_sequential.py:521`); kept green by the
  masked map FK cells.
- Stream `--chunked` (C2): types kept today, no pandas rebuild; pinned by AT-8.
- Callers of `walk_one_table`: `first_chunk_profile` (`E:execution/_chunked_profile.py:99`, AT-2) and
  `_chunked_carry.diagnose_profile` (`E:execution/_chunked_carry.py:117`, AT-3).

#### 6.3.3 FK shapes

N/A: nested columns are passthrough only, and no FK or key logic changes.

#### 6.3.4 Fields

- struct, with an int32 field and with a final null: AT-1, AT-2a, AT-2d, AT-4a, AT-5.
- list: AT-1, AT-2a, AT-5.
- map: AT-1, AT-2a, AT-4b, AT-5, AT-8.
- large list and fixed-size list: AT-2d.
- list views and unions: AT-2d (outside the predicate; Parquet cannot store them).
- fixed-size list with a null cell: AT-2d (the listed exception).
- scalar siblings: profile unchanged (AT-1), masked output unchanged (AT-2a); no scalar at all: AT-2e,
  AT-4b.

#### 6.3.5 Output surfaces

- Parquet target: values and schema equal the plain run and the source (AT-5, AT-6).
- CSV target: same bytes as plain (AT-7).
- Run summary card and `--json`: unchanged, no new text.

### 6.4 Frozen contracts

The output schema of a plain run changes for untouched nested passthrough columns: an inferred type
(int64 or double struct fields, `list` for a large or fixed-size list, `null` for an all-null column)
becomes the source type. That is a frozen-output change. It is recorded as a `Breaking:` line plus a
`### Fixed` block in `E:changelog.d/chunked-struct.md` and as a Fixed entry in the CLI `CHANGELOG.md`
that names the schema change. A downstream reader that expected the inferred type must read the
source type. Because it is a frozen-output change, S1 runs the engine full suite on its merge head
(T3), diffed against the saved main baseline.

No public signature changes: `run_mask_pipeline_chunked`, `run_pipeline`, the CLI flags, exit codes
and the reason registry are unchanged. `walk_one_table`, the rebuild and its predicate are private.
The repin follows the engine repin checklist.

## 7. Reuse inventory

| Need | Reuse | Where |
|---|---|---|
| Nested type test in the profile walk | PyArrow `pa.types.is_nested` | as at `E:io/bounded_reader.py:207`, `E:safe_output/_file_metadata.py:152` |
| Rebuild with the source type | the existing map rebuild, widened | `E:execution/_fk_keys.py:485-512` |
| Which columns are untouched | the existing `untouched_columns` | `E:execution/_chunked_carry.py:191` |
| Type coverage | the existing type catalogue | `E:tests/native/_rev9_type_catalogue.py` |
| Masked nested coverage | the existing masked map cells | `E:tests/parity/test_nonfk_dtype_matrix.py:628-693` |
| Resident reference output | `run_pipeline(..., auto_chunk=False)` | `E:tests/unit/execution/run_stream/_support.py` (`reference`) |
| CLI chunked e2e harness | the existing chunked Parquet e2e file | `tests/e2e/test_run_chunked_parquet.py` |

## 8. Pre-mortem

Assume a user still hits a nested-column failure after 1.0. Likely causes and guards:

- **Another pandas-to-Arrow rebuild site.** The builder greps `E:src/decoy_engine/execution/` for
  `pa.Table.from_pandas` on masked output and lists each hit in the report. A second site is a plan
  revision, not a quiet extra fix.
- **A table with only nested columns.** AT-2e and AT-4b, with M-K.
- **A new nested type in a later PyArrow.** AT-2d iterates the catalogue through `pa.types.is_nested`,
  so a new catalogue entry fails until it is placed.
- **The fixed-size list with a null cell.** Known and handed to the coordinator; AT-2d shows when it
  changes.
- **C2 drops the fixture.** The note on `plan/run-stream-r6-5` and M-C2a6.

## 9. Placement

| File | Repo | Directory | Sits beside | CODEMAP line | Change |
|---|---|---|---|---|---|
| `_walk.py` | engine | `E:src/decoy_engine/profile/` | | the profile row | `pa.types.is_nested`; drop `_is_nested` |
| `_chunked_profile.py` | engine | `E:src/decoy_engine/execution/` | `_chunked_oracle.py`, `_chunked_carry.py` | the `execution/` row: "the Arrow-native column profile lives in `_chunked_profile.py`" | `walk_one_table` passes `arrow_schema=table.schema` |
| `_fk_keys.py` | engine | `E:src/decoy_engine/execution/` | | the `execution/` row | `table_from_pandas_keeping_source_types` and private `_rebuilds_with_source_type` |
| `_pandas_adapter.py`, `_sequential.py` | engine | `E:src/decoy_engine/execution/` | | the `execution/` row | call the renamed function |
| `test_column_access_surfaces.py` | engine | `E:tests/native/` | | | rename one listed name |
| `test_chunked_profile_basis.py` (existing) | engine | `E:tests/unit/execution/` | | | AT-1, AT-3 |
| `test_unconfigured_passthrough_types.py` (existing) | engine | `E:tests/native/` | `_rev9_type_catalogue.py` | | AT-2a to AT-2e, AT-4a, AT-4b, beside the existing B8 cells |
| `chunked-struct.md` (new fragment) | engine | `E:changelog.d/` | the other fragments | `E:CODEMAP.md:297` "Changelog fragments" | `Breaking:` line and one `### Fixed` block |
| `test_run_chunked_parquet.py` (existing) | CLI | `tests/e2e/` | | | AT-5, AT-6, AT-7 |
| `pyproject.toml`, `requirements-dev.lock` | CLI | root | | | repin to the engine release that holds S1 |
| `CHANGELOG.md` | CLI | root | | | one Fixed entry naming the schema change |
| `docs/roadmap/groups/run.md` | CLI | | | | row status |
| `docs/plans/2026-11-08-run-stream.md` | CLI | branch `plan/run-stream-r6-5` | | | AT-C2a note, committed |

No new source or test module, no new public name. Size: about 35 engine source lines changed, about
180 engine test lines and about 110 CLI test lines added; one rename.

## 10. Slices

| Slice | Repo | Risk | Content | Test depth and gate |
|---|---|---|---|---|
| S1 | engine | R1 code, with a frozen-output change | the profile fix, the rebuild fix (types and row count), AT-1 to AT-4b, the changelog fragment | T0 and T1, with the named selection: `tests/unit/execution/test_chunked_profile_basis.py`, `tests/native/test_unconfigured_passthrough_types.py`, `tests/parity/test_nonfk_dtype_matrix.py`, `tests/native/test_column_access_surfaces.py` and the `_sequential` and pandas adapter tests. T3: the engine full suite on the merge head, because the output schema is frozen. Codex review |
| S2 | CLI | R1. The repin is a version pin, a full-suite trigger | repin (`pyproject.toml`, `requirements-dev.lock`) to the release with S1, through the daily engine release train; AT-5 to AT-7; CHANGELOG; roadmap status | Codex. Full suite on the merge head, diffed against the saved main baseline |
| S3 | CLI, inside 63a C2 | as C2 | F and F-N join AT-C2a (AT-8). No separate PR | C2's own gate |

Order: S1, then an engine release, then S2. S3 is built with C2. S1 and S2 touch no file that C1l or
C2 edits.

If C2 lands before S2: the CLI no longer calls the oracle, and the stream route keeps nested types
without the pandas rebuild (section 3). Then M-4 and M-4b cannot turn AT-5 red, and AT-5 becomes a
guard that M-C2a6 bites. S2 still ships: AT-6 (plain-run schema and the F-N plain run) still fails
before S1, M-4b still turns it red, and the repin brings the fix to the public engine function. The
builder records which mutations went red on the head it tested.

Row close: CHUNKED-STRUCT closes when S2 merges. S3 stays with row 63a. The fixed-size list with a
null cell is reported to the coordinator for its own row.

## 11. V1 bar check

- A function break (a supported input type makes a documented flag exit 3, or a plain run of a
  map-only table fail) blocks 1.0. S1 and S2 are V1. The plain-run type drift is a silent change to a
  column the user asked to pass through, so it is V1 too and ships in the same slices. S3 is V1
  because 63a C2 is.
- No leak: no log or error text is added, and AT-5 checks the masked column.
- The one frozen-surface change is the output schema fix in 6.4, recorded in both changelogs.
