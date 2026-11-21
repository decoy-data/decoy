Status: plan (revision 2, 2026-11-21; Codex r1 NO-GO remediated)

# CHUNKED-STRUCT: `decoy run --chunked` on a struct column

Owner: Cam. Author: Opus (planner). Date: 2026-11-21. Roadmap row: CHUNKED-STRUCT in
`docs/roadmap/groups/run.md`.

Anchors: a path with no prefix is in this repository (decoy CLI); `E:` is decoy-engine. CLI
`origin/main` `7aa69642`; engine `origin/main` `49e5d815b`; the CLI pins `decoy-engine==0.28.2`.
The engine line numbers below are the same on `v0.28.2` and on `origin/main`.

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`,
`development-loop.md`, `bugfix.md`, `testing.md`, `proportionality.md`, `code-review.md`,
`release-and-rollback.md`, `config-secrets-and-supply-chain.md` (dependency pins and locks),
`documentation.md`, `workspace-and-vcs.md`, `catalogs/recurring-defects.md` (11 classes).

Risk: R1. Two private engine functions change, one shared type predicate moves to the engine's
bottom-layer type module, plus tests and a repin. Only nested passthrough columns change behavior.

## Revision 2 changes

| Codex r1 finding | Resolution | Sections |
|---|---|---|
| 1 (V1): passing `arrow_schema` only fixes profiling; a null-only final chunk infers struct and list as Arrow `null`, and `pa.concat_tables` raises `ArrowInvalid` | Reproduced on the test node (section 2.2). S1 now also fixes the output rebuild at its one existing place, `table_from_pandas_keeping_maps` (`E:execution/_fk_keys.py:485-512`): every untouched nested column, not only maps, is rebuilt with its source field type. The same probe shows this fixes every chunk-null shape and also the plain run's nested type drift | 2.2, 4, 5, 6, 10 |
| 2 (V1): list and map coverage must stand alone | AT-1 and AT-2 use deterministic non-null cells for struct, list and map, and the existing engine type catalogue for the other nested kinds; separate mutations remove `is_list` and `is_map`; the null-only single-row final chunk is a regular example; map is in AT-4 and AT-6 | 6 |
| 3 (DESIGN): flat test folders; engine uses `changelog.d/` | Engine cases go in the existing `tests/unit/execution/test_chunked_profile_basis.py` and the existing `tests/native/test_unconfigured_passthrough_types.py`; CLI cases go in `tests/e2e/test_run_chunked_parquet.py`; the engine note is `changelog.d/chunked-struct.md` | 9 |
| 4: the CLI lock is `requirements-dev.lock` | Fixed | 9, 10 |
| 5: make the C2 handoff durable; say what M-4 does if C2 lands first | A note is committed on `plan/run-stream-r6-5` at AT-C2a; section 10 states the C2-first case | 3, 10 |
| 6: use the 11-class catalogue; list the rulebooks | Section 6.2 and the "Rules consulted" line | 6.2 |

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

There are two defects. The first hides the second.

### 2.1 Profile walk

The traceback (`DECOY_DEBUG=1 ... --verbose`) goes from the CLI `_run_chunked_mask`
(`src/decoy/cli/run/_execute.py:132`) into the engine oracle `run_mask_pipeline_chunked`, then
`_oracle_preflight_admitted` (`E:src/decoy_engine/execution/_chunked_oracle.py:240`), then
`first_chunk_profile`, `walk_one_table`, `walk_dataframe` and `_walk_column`.

- The failing call is `sample_series.dropna().nunique()` at
  `E:src/decoy_engine/profile/_walk.py:190`. A struct cell is a Python `dict` in pandas, and
  `nunique` hashes it. A list or map cell fails the same way.
- `_walk_column` already skips `nunique` for nested columns (`_is_nested`, `_walk.py:153-161`, used
  at `:189`), but only when the caller passes `arrow_schema` to `walk_dataframe`.
- `walk_one_table` (`E:src/decoy_engine/execution/_chunked_profile.py:36-49`, the call at `:42`)
  does not pass `arrow_schema=table.schema`. The plain-run profiler does
  (`E:src/decoy_engine/profile/_source.py:245` and `:291`).

### 2.2 Output rebuild

After the pandas adapter masks a chunk, `table_from_pandas_keeping_maps`
(`E:src/decoy_engine/execution/_fk_keys.py:485-512`, called from
`E:execution/_pandas_adapter.py:319-323` and `E:execution/_sequential.py:521`) rebuilds the Arrow
table with `pa.Table.from_pandas`. It gives untouched map columns their source type back, but not
struct or list columns. Those are inferred from the Python cells. The public oracle does not use the
carry plan (`carry_passthrough` is False, `E:execution/_chunked_oracle.py:189-191`), so every
passthrough column goes through pandas.

Probe on engine `origin/main` `49e5d815b` (Mac node, `vm-run engine`): columns `email` (redact),
`addr` struct<city string, zip int32>, `tags` list<string>, `attrs` map<string, string>, all
passthrough; output of `run_mask_pipeline_chunked` concatenated with `pa.concat_tables`.

| Case | Engine main | Profile fix only | Profile fix and rebuild fix |
|---|---|---|---|
| 3 rows, chunk 2, the last row (the single-row final chunk) null in every nested column | `TypeError` | `ArrowInvalid`: schema at index 1 differs (the final chunk infers `null`) | OK, nested columns equal the source |
| 5 rows, chunk 2, no nulls | `TypeError` | runs, but `zip` widens from int32 to int64 | OK, equal the source |
| 3 rows, chunk 2, the first chunk null | `ArrowInvalid` | `ArrowInvalid` | OK, equal the source |
| 3 rows, all null | runs, but `addr` and `tags` come out as type `null` | same | OK, equal the source |

The plain resident run (`run_pipeline(..., auto_chunk=False)`) shows the same rebuild drift on main:
`zip` int32 becomes int64, and an all-null struct or list column becomes type `null`. With the
rebuild fix the resident output types equal the source.

The "profile fix and rebuild fix" column used the S1 design below, patched in at run time. It is the
evidence for S1.

## 3. Overlap with RUN-STREAM (row 63a) slice C2

Plan `plan/run-stream-r6-5:docs/plans/2026-11-08-run-stream.md`, slice C2: "`--chunked` maps to
`execution_mode="stream"`; old fork and class removed".

(a) Does the crash sit in code C2 removes? Only the CLI call site. C2 deletes `_run_chunked_mask`, so
the CLI stops calling `run_mask_pipeline_chunked`. Both defects are in the engine and stay: the
oracle stays public, and the rebuild function also serves the plain resident run and `_sequential`.

(b) Does the engine stream route handle struct columns? Yes. On engine 0.28.2 and on engine main,
`run_pipeline(execution_mode="stream")` with a `LazySource` and a `ParquetTransactionalSink` ran at
50 and 250,000 rows, and with 17 rows, chunk 16, and a null-only final row. The struct (with its
int32 field), list and map columns came back equal to the source. A spy showed the stream route does
not call `table_from_pandas_keeping_maps`: it keeps passthrough columns out of pandas. With a
resident `pa.Table` the stream route refuses with `runtime.streaming_unavailable`, which is the
designed strict refusal.

So C2 would hide the `--chunked` crash in the CLI. It would not fix the public oracle or the plain
run's type drift, and C2 waits on C1l, C1a, C1b, REL-PKG and DELIV C5. Decision: fix both engine
defects now (S1), cover them from the CLI with the repin (S2), and keep the C2 parity set honest
with a nested fixture (S3). The S3 note is committed on `plan/run-stream-r6-5` beside AT-C2a.

Other routes, checked on the same kind of data:

| Route | Result on engine 0.28.2 |
|---|---|
| plain `decoy run`, CLI main | exit 0, but nested types drift (2.2) |
| `run_pipeline` lazy, `auto`, no sink, `resident_fallback=True` (the C1l call) | runs at 50 and 250,000 rows |
| plain `decoy run` on CLI #372 (`feat/run-stream-c1l`) | exit 0; 250,000 rows took "pandas (streamed lane)" |
| `decoy run --chunked` on CLI #372 | exit 3 (the same oracle call as main) |
| `run_pipeline(execution_mode="stream")`, lazy, sink (the C2 route) | OK, types equal the source |

## 4. Guarantee and non-goals

Guarantee:

1. `decoy run --chunked` on a Parquet source that holds nested columns (list, large list,
   fixed-size list, struct, map) as passthrough, with masked scalar siblings, runs. Its output equals
   a plain `decoy run` of the same config, whatever the chunk size and wherever the nulls fall.
2. On every route that rebuilds output from pandas (the plain resident run, `_sequential`, the
   oracle), an untouched nested column comes back with its source field type and values.

Non-goals:

- Masking strategies on a nested column. A masked column holds the strategy's own values and
  converts as it does today.
- Union types, list-view types and other nested kinds outside the shared predicate. Today's handling
  stays. A failure there is a new finding.
- How a CSV target writes a nested cell. The plain and chunked runs write the same text
  (`{'city': 'A', 'zip': '1'}`).
- A refusal. With the fix nothing is refused, so no reason code is added. If a later finding shows a
  nested shape the chunked route cannot run, it must refuse before the first chunk with a registered
  reason code and a value-free message (table, column name and Arrow type only), never exit 3.

Design notes: one predicate, one rebuild point. Today two private copies of "is this type nested"
exist (`E:profile/_walk.py:153` and `E:execution/_mixed_admission.py:306`). S1 adds one public
`is_nested(t)` to `E:src/decoy_engine/_arrow_types.py`, the bottom-layer module for Arrow type
predicates (`.importlinter` line 23), and both sites and the rebuild use it. `_mixed_admission` keeps
its extra union clause as `is_nested(t) or pa.types.is_union(t)`. The rebuild function is renamed
`table_from_pandas_keeping_nested`, because its name would otherwise be wrong. Established pattern:
rebuild Arrow from pandas with the declared source type instead of inference (`pa.array(...,
type=field.type, from_pandas=True)`), which the function already does for maps.

## 5. Behavior and failure modes

| Case | Today | After S1 and S2 |
|---|---|---|
| `--chunked`, struct, list and map passthrough, masked sibling | exit 3, `TypeError` | exit 0; equal to the plain run |
| `--chunked`, a null-only final chunk (including one row) | `ArrowInvalid` after the profile fix | exit 0; types kept |
| `--chunked`, a null-only first chunk | `ArrowInvalid` | exit 0; types kept |
| plain run, struct with an int32 field | int32 widens to int64 | int32 kept |
| plain run, all-null struct or list column | type becomes `null` | source type kept |
| plain run, map column | type kept | unchanged |
| masked nested column (any route) | strategy output | unchanged |
| `--chunked`, Parquet source to CSV target | exit 3 | exit 0; same text as the plain run |
| `--chunked` after C2 (stream route) | not built | equal to the plain run (S3) |

What could go wrong with the fix, and the guard:

- `untouched_columns` marks a column untouched when a strategy did change it, so the rebuild forces
  the source type onto strategy output. Guard: the existing map behavior already relies on
  `untouched_columns`; AT-2 includes a masked scalar sibling, and the existing
  `tests/native/test_unconfigured_passthrough_types.py` runs strategies beside nested columns.
- `pa.array(..., type=field.type)` cannot build a type from its pandas cells. Guard: AT-2 runs every
  nested entry of the existing type catalogue; a type that fails stops the build for a plan
  revision. It is not filtered out.
- The first-chunk profile of a nested column becomes `distinct_count=None`. The chunked admission
  reads no distinct count for a passthrough column (`first_chunk_profile` docstring). AT-2 compares
  the whole output with the resident run.
- No message or log text changes.

## 6. Acceptance tests

Each test fails before the fix. The builder runs each mutation once on the final head and records it
red in the PR (recurring class 9).

Fixture F (deterministic): `email` string; `addr` struct<city string, zip int32>; `tags`
list<string>; `attrs` map<string, string>. Rows 0 and 1 hold non-null cells in every column (for
example `{"city": "c0", "zip": 0}`, `["t0", "x"]`, `[("k", "v0")]`). Row 2 is null in every nested
column. Chunk size 2, so the final chunk is the single null row.

| ID | Slice | Test | Fails before the fix because | Mutations that prove it bites |
|---|---|---|---|---|
| AT-1 | S1 | `first_chunk_profile` on rows 0 and 1 of F: the nested columns have `distinct_count is None`, `email` has 2, every column is `sampled=True`. Parametrized over struct alone, list alone and map alone, so each type stands on its own | `walk_one_table` raises `TypeError` | M-1: remove `arrow_schema=table.schema` from `walk_one_table`. M-L: remove `is_list` from `is_nested` (red on the list cell). M-M: remove `is_map` (red on the map cell). M-S: remove `is_struct` (red on the struct cell) |
| AT-2a | S1 | `run_mask_pipeline_chunked` on F (redact `email`, the rest passthrough), chunk 2. The concatenated output equals the source in every nested column, schema included, and equals `run_pipeline(..., auto_chunk=False)` by `pa.Table.equals`. A regular example, not generated | `TypeError` today; `ArrowInvalid` with M-1 fixed only | M-1; M-R: restore the maps-only rebuild (red with `ArrowInvalid`); M-L, M-M, M-S |
| AT-2b | S1 | The same as AT-2a with the null row first, then with every nested cell null | `ArrowInvalid`; type `null` | M-R |
| AT-2c | S1 | Hypothesis, fixed seed: row count, chunk size (1 up to row count) and null positions drawn; output equals the source and the resident run | as AT-2a | M-R |
| AT-2d | S1 | Every nested entry of the existing type catalogue (`E:tests/native/_rev9_type_catalogue.py`: list, fixed-size list, struct, map and the rest that `is_nested` names), with and without a null, through the public oracle beside a redact column | `TypeError` | M-1, M-R |
| AT-3 | S1 | `walk_one_table` on a one-column table for each of struct, list and map (the `_chunked_carry.diagnose_profile` call shape) returns without error | `TypeError` | M-1 |
| AT-4 | S1 | Resident `run_pipeline(..., auto_chunk=False)` on F: output schema equals the source schema (int32 `zip` kept), and with every nested cell null the struct and list columns keep their types | int64 `zip`; type `null` | M-R |
| AT-5 | S2 | CLI e2e in `tests/e2e/test_run_chunked_parquet.py`: F written as Parquet, config redacts `email` and passes `addr`, `tags`, `attrs` through. `decoy run --chunked --chunk-size 2` exits 0; its output equals a plain `decoy run` of the same config by `pa.Table.equals`; the output schema equals the source schema; `email` holds no source value | exit 3 on engine 0.28.2 | M-4: in the test process, patch `walk_one_table` back to the 0.28.2 body (red with exit 3). M-4b: patch the rebuild back to maps-only (red: exit 3 from `ArrowInvalid`) |
| AT-6 | S2 | The same file, plain `decoy run` only: the output schema equals the source schema | int64 `zip` on engine 0.28.2 | M-4b |
| AT-7 | S2 | The same file with a CSV target: `--chunked` and plain both exit 0 and write the same bytes | exit 3 on the `--chunked` side | M-4 |
| AT-8 | S3 (in 63a C2) | F joins the AT-C2a fixture set. Under C2, `--chunked` (the stream route) exits 0, and its output equals the plain run and the source schema, map included | C2 is not built; it guards the new route | M-6: make the C2 strict preflight refuse a table with a nested column |

The mutations M-L, M-M and M-S act on the one shared `is_nested`. Each is run alone.

### 6.1 Plan contract classes

| Class | Name | Closing structure | Sentry or property test | Mutation |
|---|---|---|---|---|
| 1 | value leak | no message, log or error text is added; AT-5 checks no source `email` value reaches the output | AT-2a, AT-5 | M-1 |
| 2 | cleanup | N/A: no new file, temp path or handle | existing chunked e2e tests | N/A |
| 3 | state | N/A: `walk_one_table` and the rebuild are pure functions of their inputs | AT-1, AT-2a | N/A |
| 4 | route | plain resident, plain lazy (C1l), oracle `--chunked` and stream (C2) were each probed; AT-2 and AT-5 pin chunked equal to plain; AT-8 pins the C2 route | AT-2c (property), AT-5, AT-8 | M-R, M-6 |
| 5 | referential | N/A: no FK or key logic changes; `_sequential` only gains the type rebuild for untouched nested columns | existing sequential tests | N/A |
| 6 | untrusted input | the source file is untrusted data; the fix reads only its Arrow schema, which the reader already holds | AT-1 | N/A |
| 7 | TOCTOU (check-then-use) | the profile uses the schema of the same chunk it converts; the rebuild uses the source schema the adapter already holds | AT-2b | N/A |
| 8 | weak tests | each fail-before test has its own mutation; equality is on whole tables with schema, not values only | AT-1 to AT-7 | M-1, M-R, M-L, M-M, M-S, M-4, M-4b |
| 9 | refactor | the predicate moves to one place and the rebuild is renamed; behavior changes only for untouched nested columns, which AT-2 and AT-4 pin | AT-2a, AT-4, existing map passthrough cells in `E:tests/native/test_unconfigured_passthrough_types.py` | M-R |
| 10 | frozen contracts | no public signature, flag, exit code or reason code changes (6.4) | the existing engine public-API snapshot | N/A |

### 6.2 Recurring defect classes (`catalogs/recurring-defects.md`)

| # | Class | Applies | How this plan meets it |
|---|---|---|---|
| 1 | Anchored validation | No | no pattern validation is added |
| 2 | Strict wire and stored types | No | no persisted or wire model changes |
| 3 | No exception context | No | no error is raised or wrapped |
| 4 | Versioned read models | No | no reader of a persisted format changes |
| 5 | Normalized guard scanners | Yes, one entry | `tests/native/test_column_access_surfaces.py` lists the rebuild by name; the rename updates that one entry and adds nothing |
| 6 | No reaching into private modules | Yes | `is_nested` is public in `_arrow_types` (a bottom-layer module other layers already import); the CLI imports no engine private name. The CLI tests patch an engine private only inside a one-time mutation run, never in a kept test |
| 7 | No hidden CI failures | No | no CI change |
| 8 | One input, one trust class per entry point | No | no new entry point |
| 9 | Mutations on the final head | Yes | every mutation is rerun on the final head; the head is recorded |
| 10 | Allowlisted helpers are still checked | No | no allowlist entry is added |
| 11 | No raised caps | Yes | `_fk_keys.py` is 530 lines and `_walk.py` shrinks; no size cap, ratchet or allowlist grows. A moved line-count pin is listed in the report |

### 6.3 Enumerations

#### 6.3.1 Exit paths

- `--chunked` run succeeds: exit 0 (AT-5, AT-7). The CLI call is `src/decoy/cli/run/_execute.py:132`.
- Engine refusal before the run (compatibility gate, subset, integrity): exit 1, unchanged.
- Internal error: exit 3. Today a nested column reaches it; after S1 it does not (AT-5, M-4, M-4b).
- Stream route without a lazy source (C2 only): `runtime.streaming_unavailable`, unchanged.

#### 6.3.2 Routes

- Plain resident run: pandas rebuild at `E:execution/_pandas_adapter.py:319`, type drift today; fixed by S1 (AT-4, AT-6).
- Plain lazy run, C1l with `resident_fallback=True`: runs today (probe).
- Oracle `--chunked` (`run_mask_pipeline_chunked`, preflight at `E:execution/_chunked_oracle.py:240`): crashes today; fixed by S1 (AT-2, AT-5).
- `_sequential` FK route: calls the same rebuild (`_sequential.py:521`), so it gains the fix.
- Stream `--chunked` (C2): types kept today, no pandas rebuild; pinned by AT-8.
- Callers of `walk_one_table`: `first_chunk_profile` (`E:execution/_chunked_profile.py:99`, AT-2) and
  `_chunked_carry.diagnose_profile` (`E:execution/_chunked_carry.py:117`, AT-3).

#### 6.3.3 FK shapes

N/A: nested columns are passthrough only, and no FK or key logic changes.

#### 6.3.4 Fields

- struct, with a non-default field type (int32): AT-1, AT-2, AT-4, AT-5.
- list: AT-1, AT-2, AT-5.
- map: AT-1, AT-2, AT-5, AT-8.
- large list and fixed-size list: AT-2d through the type catalogue.
- scalar siblings: profile fields unchanged (AT-1), masked output unchanged (AT-2a).

#### 6.3.5 Output surfaces

- Parquet target: values and schema equal the plain run and the source (AT-5, AT-6).
- CSV target: same bytes as plain (AT-7).
- Run summary card and `--json`: unchanged, no new text.

### 6.4 Frozen contracts

`run_mask_pipeline_chunked`, `run_pipeline`, the CLI flags, exit codes and the reason registry are
unchanged. `walk_one_table` and the rebuild function are private. `is_nested` is a new name in a
private module, not in the engine root exports. Output types for nested passthrough columns change
on the plain run, from drifted to the source type. That is a fix, recorded in both changelogs under
Fixed. The repin follows the engine repin checklist.

## 7. Reuse inventory

| Need | Reuse | Where |
|---|---|---|
| Nested type predicate | the existing `_is_nested` body, moved once to the type module | `E:profile/_walk.py:153-161` to `E:_arrow_types.py` |
| Rebuild with the source type | the existing map rebuild, widened to all nested types | `E:execution/_fk_keys.py:485-512` |
| Which columns are untouched | the existing `untouched_columns` | `E:execution/_chunked_carry.py:191` |
| Type coverage | the existing nested type catalogue | `E:tests/native/_rev9_type_catalogue.py` |
| Resident reference output | `run_pipeline(..., auto_chunk=False)` | `E:tests/unit/execution/run_stream/_support.py` (`reference`) |
| CLI chunked e2e harness | the existing chunked Parquet e2e file | `tests/e2e/test_run_chunked_parquet.py` |

## 8. Pre-mortem

Assume a user still hits a nested-column failure on `--chunked` after 1.0. Likely causes and guards:

- **Another pandas-to-Arrow rebuild site.** Guard: section 6.3.2 lists the rebuild's callers; the
  builder greps for other `pa.Table.from_pandas` calls on masked output in `execution/` and lists
  each in the report. A second site is a plan revision, not a quiet extra fix.
- **A nested kind outside the predicate** (union, list view). Non-goal; AT-2d runs the catalogue so
  a crash there shows as a failing case.
- **C2 drops the fixture.** Guard: the note on `plan/run-stream-r6-5` and M-6.

## 9. Placement

| File | Repo | Directory | Sits beside | CODEMAP line | Change |
|---|---|---|---|---|---|
| `_arrow_types.py` | engine | `E:src/decoy_engine/` | `_field_names.py`, `_value_free.py` | the bottom-layer modules in `.importlinter` line 23 | add `is_nested` |
| `_walk.py` | engine | `E:src/decoy_engine/profile/` | | the profile row | use `is_nested`; drop `_is_nested` |
| `_mixed_admission.py` | engine | `E:src/decoy_engine/execution/` | | the `execution/` row | use `is_nested` plus its union clause |
| `_chunked_profile.py` | engine | `E:src/decoy_engine/execution/` | `_chunked_oracle.py`, `_chunked_carry.py` | the `execution/` row: "the Arrow-native column profile lives in `_chunked_profile.py`" | `walk_one_table` passes `arrow_schema=table.schema` |
| `_fk_keys.py` | engine | `E:src/decoy_engine/execution/` | | the `execution/` row | `table_from_pandas_keeping_nested` (renamed and widened) |
| `_pandas_adapter.py`, `_sequential.py` | engine | `E:src/decoy_engine/execution/` | | the `execution/` row | call the renamed function |
| `test_column_access_surfaces.py` | engine | `E:tests/native/` | | | rename one listed name |
| `test_chunked_profile_basis.py` (existing) | engine | `E:tests/unit/execution/` | | | AT-1, AT-3 |
| `test_unconfigured_passthrough_types.py` (existing) | engine | `E:tests/native/` | `_rev9_type_catalogue.py` | | AT-2a to AT-2d, AT-4 (the public oracle and resident cells beside the existing B8 cells) |
| `chunked-struct.md` (new fragment) | engine | `E:changelog.d/` | the other fragments | `E:CODEMAP.md:297` "Changelog fragments" | one `### Fixed` block |
| `test_run_chunked_parquet.py` (existing) | CLI | `tests/e2e/` | | | AT-5, AT-6, AT-7 |
| `pyproject.toml`, `requirements-dev.lock` | CLI | root | | | repin to the engine release that holds S1 |
| `CHANGELOG.md` | CLI | root | | | one Fixed line |
| `docs/roadmap/groups/run.md` | CLI | | | | row status |
| `docs/plans/2026-11-08-run-stream.md` | CLI | branch `plan/run-stream-r6-5` | | | AT-C2a note (committed with this revision) |

No new source or test module. Size: about 30 engine source lines changed, about 150 engine test lines
and about 100 CLI test lines added. New name: `is_nested` (private module); one rename.

## 10. Slices

| Slice | Repo | Risk | Content | Gate |
|---|---|---|---|---|
| S1 | engine | R1 | `is_nested` in `_arrow_types`; `walk_one_table` passes the schema; the rebuild widened and renamed; AT-1 to AT-4; changelog fragment | Codex. T1 impact selection on the head (the rebuild has two callers, so T1 includes the `_sequential` and pandas adapter tests) |
| S2 | CLI | R1. The repin is a version pin, a full-suite trigger | repin (`pyproject.toml`, `requirements-dev.lock`) to the release with S1, through the daily engine release train; AT-5 to AT-7; CHANGELOG; roadmap status | Codex. Full suite on the merge head, diffed against the saved main baseline |
| S3 | CLI, inside 63a C2 | as C2 | F joins AT-C2a (AT-8). No separate PR | C2's own gate |

Order: S1, then an engine release, then S2. S3 is built with C2. S1 and S2 touch no file that C1l or
C2 edits.

If C2 lands before S2: the CLI no longer calls the oracle, and the stream route keeps nested types
without the pandas rebuild (section 3). Then M-4 and M-4b cannot turn AT-5 red, and AT-5 becomes a
guard that M-6 bites. S2 still ships: AT-6 (plain run schema) still fails before S1 and M-4b still
turns it red, and the repin brings the oracle fix to the public engine function. The builder records
which mutations went red on the head it tested.

Row close: CHUNKED-STRUCT closes when S2 merges. S3 stays with row 63a.

## 11. V1 bar check

- A function break (a supported input type makes a documented flag exit 3) blocks 1.0 under the V1
  bar. S1 and S2 are V1. The plain-run type drift (2.2) is a silent output change of a column the
  user asked to pass through, so it is V1 too and ships in the same slices. S3 is V1 because 63a C2
  is.
- No leak: no log or error text is added, and AT-5 checks the masked column.
- No frozen surface changes (6.4).
