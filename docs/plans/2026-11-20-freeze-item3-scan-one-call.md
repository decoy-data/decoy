Status: plan (revision 1, 2026-11-20)

# FREEZE-SURFACE item 3: `decoy.scan()` and `decoy scan` make one engine call

Owner: Cam. Author: Opus (plan author, CLI). Date: 2026-11-20. Roadmap row: FREEZE-SURFACE item (3) in `docs/roadmap/groups/health.md` ("Audit J2: `api.scan` and `decoy scan` use one profile call, so the public scan result cannot drift from the CLI's").

Sources: proportionality audit `docs/records/2026-11-15-proportionality-audit/REMEDIATION.md` row J2 (line 353: "`api.scan` calls `profile_columns` while the CLI calls `scan_sources`. Point `api.scan` at `scan_sources`, share the helpers"); engine freeze batch plan `E:docs/plans/2026-11-18-freeze-batch.md` on branch `plan/freeze-batch` (revision 3.3), sections 1, 4.1 and 4.2, for the format and the X1 experimental tier.

Anchors: a path with no prefix is in this repository (decoy CLI); `E:` is decoy-engine. CLI `origin/main` `c87ab295`; engine `origin/main` `017b168be`; the CLI pins `decoy-engine==0.28.1` (CLI #327).

Rules consulted: dev-rules `README.md` (routing), `00-universal.md`, `risk-and-exceptions.md` (compatibility is an R2 trigger), `development-loop.md` (PLAN: guarantee, failure modes, acceptance tests first with their mutation, size, placement, design notes, choke point, slices), `cross-cutting-concerns.md` (one choke point, a walk-based guard, its seeded mutation, a ratchet allowlist), `api-and-compatibility.md` (consumer inventory, explicit breaking change, contract tests), `architecture.md` (placement against CODEMAP), `reuse-first.md`, `proportionality.md` (size, deletion test, no forwarding wrapper), `testing.md` (T0 to T2, full-suite escalation triggers).

Risk: R2. `decoy.scan` is public API (`_LAZY_API` in `src/decoy/__init__.py:20`, `docs/release/frozen-surfaces.md:22`, signature pinned in `tests/unit/release/test_api_signatures.py:26`). Slice C2 changes its return value, a default and its accepted inputs. Approver: Cam for the plan and the owner questions; Dennis then Codex for the plan gate.

## 0. Scope conflict to settle first (Q0)

The engine freeze plan moved J2 to v1+ (`E:docs/plans/2026-11-18-freeze-batch.md` section 1 non-goals and section 4.2 item 3, owner Q4 "yes"). The durable roadmap row in `docs/roadmap/groups/health.md` still lists item 3 as "Left". This plan is written so the owner can choose. Recommended: do it before 1.0 (section 13, Q0).

## 1. Current behaviour

Two public routes produce "a scan" of the same file through different engine calls, different readers and different defaults.

### 1.1 `decoy scan` (CLI)

- `src/decoy/cli/scan.py:480-583`: `_scan` declares the options and calls `decoy.cli.scanning.run_scan`. Defaults: `--rows 10000` (`scan.py:494`), `--strategy head`; `--rows 0` means a full read.
- `src/decoy/cli/scanning/_multi.py:145-188` `resolve_sources`: each path becomes an explicit engine source descriptor. A CSV must say `--has-header` or `--no-header` (`_multi.py:132-142`); `.tsv` gets `delimiter: "\t"` (`_multi.py:185`); the table name comes from `table_name_from_path` (`_multi.py:66-75`).
- `src/decoy/cli/scanning/_multi.py:442-453`: one call to `decoy_engine.scan_sources(descriptors, sample_rows=row_cap, strategy=effective)`, then `scan_set_to_dict(result, detail=False)`, the value-free `scan-set/v1` core. `--output` writes `json.dumps(core, indent=2)` (`_multi.py:456-459`).
- The engine reader (`E:src/decoy_engine/profiling/scan_set.py:314-371`) builds the declared source, reads `cap + 1` rows to set `basis` (`:336-344`, `:370`), refuses repeated column names (`:345`), runs the header guard and renames suspect headers to `c0..cn` (`:352-358`), counts leading zeros, and wraps unclassified failures in the value-free `ScanSourceError` (`:289-304`).

### 1.2 `decoy.scan()` (library API)

- `src/decoy/api.py:653-729`: `scan(data, *, source_label=None, rows=None, strategy="head", format=None, layout=None)`.
- A path is read by the CLI's own pandas loaders in `src/decoy/cli/scan.py:298-385` (`_load_csv_with_sampling`, `_load_parquet_with_sampling`, `_load_fixed_width_with_sampling`, `_load_data`), imported at `api.py:53-59`. A DataFrame is cut with `df.head` or `sample_frame` (`api.py:699-705`).
- Then `decoy_engine.profile_columns(df, source_label=..., sample_strategy=..., sample_row_cap=rows)` (`api.py:724-729`). It returns the in-memory `ColumnProfile`, which holds cell values (top values, modes, min and max).

### 1.3 Where the two results drift today

| # | Fact | `decoy scan` | `decoy.scan()` | Where |
|---|---|---|---|---|
| D1 | Engine call | `scan_sources` + `scan_set_to_dict(detail=False)` | `profile_columns` | `_multi.py:443-452`; `api.py:691,724` |
| D2 | Result | value-free `scan-set/v1` core | value-bearing `ColumnProfile` | `api.py:683-689` (the docstring says so) |
| D3 | CSV header | must be stated; never guessed | pandas assumes row 1 is a header | `_multi.py:132-142`; `scan.py:298-310` |
| D4 | Header guard | warns, renames to `c0..cn` | none | `E:scan_set.py:352-358` |
| D5 | TSV | tab delimiter | read with a comma: one column | `_multi.py:185`; `scan.py:302` (`pd.read_csv(path)`) |
| D6 | Default rows | 10,000 | all rows | `scan.py:494`; `api.py:657` |
| D7 | Basis and totals | `basis`, `row_count` (source total), `row_count_exact`, `scanned_rows` | none; `row_count` is the rows read | `E:scan_set.py:336-344,370` |
| D8 | Key candidates, warnings, leading-zero counts | yes | no | `E:scan_set.py:347-371` |
| D9 | Repeated column names | refused | pandas renames to `a.1` silently | `E:scan_set.py:345` |
| D10 | Readers | engine declared-source readers (CSV dialect, Parquet, fixed width) | CLI pandas readers, `pd.read_fwf` | `E:scan_set.py:326`; `scan.py:298-385` |
| D11 | Errors | class and table only (`ScanSourceError`) | raw pandas or parser exception, whose text can quote a cell | `E:scan_set.py:289-304`; `api.py:717` |
| D12 | Table name | `table_name_from_path` | `source_label`, else the file name, `<dataframe>` for a frame | `_multi.py:66-75`; `api.py:706,718` |

The test that claims parity (`tests/unit/test_api.py:435-449`) compares only `row_count`, the name stem, `reid_risk_score` and `pii_score` on a three-row CSV with a header, so none of D3 to D12 is exercised.

A third caller, `decoy demo`, calls `scan_sources` and `scan_set_to_dict` itself (`src/decoy/cli/demo.py:162-173`). `decoy init` calls `profile_columns` for strategy inference (`src/decoy/cli/init.py:374-376`); it is not a scan surface (section 2, non-goals).

## 2. Guarantee and non-goals

Guarantees after this work:

- G1. One internal function, `decoy.cli.scanning.scan_descriptors`, is the only first-party caller of `decoy_engine.scan_sources` and `decoy_engine.scan_set_to_dict`. `decoy scan`, `decoy demo` and `decoy.scan()` all call it. A sentry fails on any other call or import of `scan_sources`, `scan_set_to_dict` or `profile_columns` under `src/decoy`, except a named allowlist (`cli/init.py::init` for `profile_columns`, with its reason).
- G2. For the same file and the same options, `decoy.scan()` returns the same `scan-set/v1` core that `decoy scan --output` writes. Serialized with the same function, the bytes are identical once `scanned_at` (the one wall-clock member) is set to the same value.
- G3. `decoy.scan()` has the CLI's input rules: a CSV path states its header (`has_header`), a headerless CSV gives `column_names`, `.tsv` is tab-delimited, fixed width needs `layout`, and the default sample is 10,000 rows, with `rows=None` or `rows=0` for a full read.
- G4. `decoy.scan()` returns no cell value and raises no exception whose text holds a cell value: its result is the value-free core, and engine scan errors reach the caller as the engine raises them (class and table only).
- G5. A DataFrame passed to `decoy.scan()` goes through the same engine reader as a Parquet file: it is written to an owner-only temp Parquet file (the `decoy.mask()` staging pattern), which is removed on success and on failure. The returned core names its source path as `<dataframe>`, never the temp path.

Non-goals:

- No engine change. `scan_sources` and `scan_set_to_dict` are used as they are in 0.28.1.
- No change to `decoy scan` output: card, `--json`, `--output` and `--output -` bytes stay as on the base the slice lands on (PR #340's labels included).
- No multi-table `decoy.scan()` (a mapping of inputs). Additive later (Q6).
- No `pre_scan` model detectors in `decoy.scan()`; both routes stay regex only, as today.
- `decoy init` keeps its direct `profile_columns` call. The init wizard is stopped (owner 2026-11-19), and its profile feeds strategy inference, not a scan result. It is an allowlist entry, not a route.
- `decoy fit` and the `decoy run` pre-scan and post-scan are out of scope; they do not produce a scan document.
- No new public name. `decoy.scan` gains two keyword parameters; no new exception type is exported.

## 3. Established solutions

Search run: the codebase (this repository's choke points and their sentries, `decoy.mask()` staging, the engine scan entry) and the dev-rules pattern catalog. No online search was needed: this is a routing refactor with a known house pattern, not an algorithm, parser or protocol problem.

| Concern | Established solution | What we take |
|---|---|---|
| One route to a shared effect | A choke point plus a walk-based guard (dev-rules `cross-cutting-concerns.md`); in this repo `_outbound.open_url`, `_config_file`, `cli/run/_result.py` (the one result builder, guarded by `tests/sentry/run/test_one_result_builder.py`) | One function owns the engine call and the serialization; a sentry walks the syntax tree for bypasses, with a ratchet allowlist. |
| Library and CLI share one core | A thin command over a library function (Click and Typer guidance; pip's commands over shared internals) | The command and the library function both call one internal function; neither calls the engine directly. |
| In-memory data through a file-only reader | `decoy.mask()` stages a DataFrame to an owner-only temp Parquet file (`api.py:213-269`, `_stage_source_entry`) | Reuse the same staging helper; no engine in-memory entry (Q4). |
| Contract test for a public result | Consumer-facing golden comparison (dev-rules `api-and-compatibility.md`) | Parity tests compare the API result with the CLI's `--output` bytes over a matrix of inputs. |

## 4. Reuse inventory

| Need | Existing piece | Path |
|---|---|---|
| Paths to descriptors, header rules, TSV, layout | `resolve_sources`, `_layout_columns`, `_split_names`, `ScanUsageError` | `src/decoy/cli/scanning/_multi.py:58-63,111-214` |
| Table name from a path | `table_name_from_path` | `src/decoy/cli/scanning/_multi.py:66` |
| Layout file parse | `_parse_layout` | `src/decoy/cli/scan.py:224` |
| DataFrame to private temp Parquet | `_stage_source_entry`, `_to_pa_table`, `create_private_temp` | `src/decoy/api.py:203-269`, `src/decoy/_private_file.py` |
| Engine scan and core | `scan_sources`, `scan_set_to_dict`, `ScanSetCoreRead` | `E:src/decoy_engine/profiling/scan_set.py:145,506` |
| Call-site walk for the sentry | `sites`, `call_sites`, `qualified`, `bindings` | `tests/sentry/io_policy/_calls.py` |
| Ratchet allowlist | `load_allowlist`, `scripts/dev/sentry_registry.toml`, `scripts/dev/ratchet_check.py` | `tests/sentry/_ratchet.py` |
| Signature pin | `test_scan_signature_is_frozen` | `tests/unit/release/test_api_signatures.py:26` |

## 5. Behaviour

### 5.1 The choke point

New module `src/decoy/cli/scanning/_engine_call.py`, exported from `decoy.cli.scanning` (other packages never import `_engine_call` directly, as the package docstring requires):

```python
DEFAULT_SCAN_ROWS: Final = 10_000

@dataclass(frozen=True)
class ScanRun:
    result: ScanSet          # in-memory and value-bearing: the CLI summary only, never returned by the API
    core: dict[str, Any]     # scan_set_to_dict(result, detail=False): value-free

def scan_descriptors(
    descriptors: Mapping[str, dict[str, Any]],
    *,
    rows: int | None,
    strategy: str,
    on_stage: Callable[[], None] | None = None,
) -> ScanRun: ...

def core_bytes(core: Mapping[str, Any]) -> bytes:   # json.dumps(core, indent=2).encode("utf-8")
```

Rules inside `scan_descriptors`, each stated once:

1. `rows` of `None` or `0`, or `strategy == "full"`, reads every row: `sample_rows=None, strategy="full"`. Otherwise `sample_rows=rows, strategy=strategy`. This is the CLI's `--rows 0` rule (`_multi.py:438-440`), moved.
2. `strategy` must be `head`, `random` or `full`, else `ScanUsageError("strategy must be one of ['full', 'head', 'random'], got ...")`. A negative `rows` is a `ScanUsageError` too (Q3 note).
3. It calls `scan_sources(descriptors, sample_rows=..., strategy=...)`, then `on_stage()`, then `scan_set_to_dict(result, detail=False)`, then `on_stage()`. `on_stage` keeps the CLI progress stages without a UI import in the choke point.
4. It catches nothing. Engine errors reach each caller unchanged; the CLI keeps its own class-only message (`_multi.py:228-236`).

`core_bytes` is the one serializer of a scan document: `run_scan` (`--output`), `decoy demo` (`scan.json`) and the parity tests use it.

### 5.2 `decoy scan`

`run_scan` replaces `_multi.py:442-453` with `scan_descriptors(descriptors, rows=row_cap, strategy=strategy, on_stage=ms.complete)` and writes `core_bytes(run.core)`. `_table_summary` reads `run.result.tables`. The output does not change.

### 5.3 `decoy demo`

`demo.py:162-173` calls `scan_descriptors(descriptors, rows=None, strategy="full")` and writes `core_bytes(run.core)`. Today it writes `json.dumps(core, indent=2)` through `Path.write_text`, so the file bytes stay the same.

### 5.4 `decoy.scan()`

New signature (Q1 to Q5 recommended answers):

```python
def scan(
    data,
    *,
    source_label: str | None = None,
    rows: int | None = 10_000,
    strategy: str = "head",
    format: str | None = None,
    layout=None,
    has_header: bool | None = None,
    column_names: Sequence[str] | None = None,
) -> dict[str, Any]
```

Steps:

1. A path (`str` or `Path`): `resolve_sources([path], fmt=format, layout=..., has_header=..., column_names=...)`, the function `decoy scan` uses. `layout` may be a path (parsed by `_layout_columns`, as in the CLI) or an already-parsed `columns` list (kept from today's API; it becomes `{"columns": layout}` in the descriptor). `column_names` goes through the same check as `--column-names` (`_split_names`, given a list form), so both routes refuse an empty or repeated name with the same text. `source_label`, when given, replaces the derived table name (Q5).
2. A DataFrame: `_stage_source_entry(name, df, tmp_paths)` writes an owner-only temp Parquet file. `format`, `layout`, `has_header` or `column_names` given with a DataFrame raise `ValueError` (today they are silently ignored, `api.py:676-678`). Table name: `source_label`, else `dataframe`.
3. `run = scan_descriptors(descriptors, rows=rows, strategy=strategy)`.
4. For a DataFrame, the returned core's `tables[0].descriptor.path` is set to `"<dataframe>"` (G5).
5. Temp files are removed in a `finally` block.
6. Returns `run.core`. Any other `data` type raises `TypeError`, as today.

`ScanUsageError` becomes a subclass of `ValueError`, so the API raises a `ValueError` with the CLI's own text and exports no new name.

### 5.5 What the API result holds

The `scan-set/v1` core: `scan_schema`, `engine_version`, `scanned_at`, `tables` (each with `name`, `descriptor`, `row_count`, `row_count_exact`, `sample_strategy`, `sample_row_cap`, `fields` (the engine `FieldCore`), `key_candidates`, `warnings`, `reid_risk_score`, `quasi_identifier_groups`, `basis`, `scanned_rows`), `relationships` (empty) and `detectors`. It no longer holds top values, modes, min and max, or `k_anonymity` (not in the core; the CLI card reads it from the in-memory profile). A caller who needs the value-bearing profile calls `decoy_engine.scan_sources` or `decoy_engine.profile_columns` directly; the docstring says so.

## 6. Failure modes

| # | Failure | Effect | Prevented by |
|---|---|---|---|
| F1 | A new caller (a command, the API, a helper) calls `scan_sources` or `profile_columns` directly | its result drifts from `decoy scan` again | sentry AT-6 with a shrink-only allowlist |
| F2 | The API passes a different default or maps `rows` differently | same call, different sample | the default and the rows mapping live only in `_engine_call.py`; AT-3, AT-12 |
| F3 | The CLI output changes during the refactor | breaks `--json` shapes and saved scans | AT-0, and the existing `tests/e2e/test_scan_command.py`, `tests/e2e/test_scan_basis_labels.py` (PR #340), `tests/e2e/release_freeze/test_json_shapes.py` |
| F4 | A CSV path with no `has_header` is scanned with a guess | header row read as data, or the reverse | `resolve_sources` refuses; AT-4 |
| F5 | A DataFrame's temp Parquet file stays on disk after an error | a copy of the caller's data left in the temp folder | `finally` unlink; AT-10 with an injected engine failure |
| F6 | The temp path appears in the returned core | a random, dead path in a result the caller may save; the result is not reproducible | 5.4 step 4; AT-2 |
| F7 | A DataFrame fails the Arrow conversion (a mixed-type object column) | `ArrowTypeError` with value text | raised as `TypeError("data could not be converted to Arrow: <class>")`, class only; AT-11 |
| F8 | Engine error text reaches the API caller with a cell value | leak | the API no longer reads files itself; the engine's `ScanSourceError` is class-only; AT-7 |
| F9 | `decoy.scan()` returns `detail=True` content | cell values in the public result | `scan_descriptors` calls `detail=False` only; AT-5 |
| F10 | A caller relies on today's `ColumnProfile` return | `AttributeError` or `KeyError` after upgrade | Breaking CHANGELOG entry and the docstring; pre-1.0, and `decoy.scan` is in the X1 experimental row of the freeze plan |
| F11 | Staging a large DataFrame briefly doubles memory and disk use | slower, larger temp use | known limit, stated in the docstring; `decoy.mask()` has the same cost |
| F12 | PR #340 and this work edit `_multi.py` and `api.py` together | merge conflict or a lost label change | C1 is cut from `origin/main` after #340 merges (section 11) |

## 7. Acceptance tests (red first)

Each test names the mutation that must turn it red. Parity tests compare documents after setting `scanned_at` to `"1970-01-01T00:00:00+00:00"` in both; the byte check compares `core_bytes(cli_doc)` with `core_bytes(api_doc)`.

| Id | Test | Red on main because | Mutation that must turn it red | Slice |
|---|---|---|---|---|
| AT-0 | Guard: `decoy scan --output` bytes for the AT-1 file matrix equal bytes recorded from the slice's base commit (`scanned_at` normalized); `--json` and the card unchanged | green (guard) | in `scan_descriptors`, pass `sample_rows=None` always | C1 |
| AT-1 | Parity matrix, file inputs: `decoy scan F <flags> --output o.json` against `decoy.scan(F, <same kwargs>)`, byte-identical. Cells: CSV with `has_header=True` and default rows; CSV `rows=0`; CSV `rows=5, strategy="random"`; CSV `rows=5, strategy="full"`; a CSV of 10,050 rows with default rows (basis `sample`, `row_count > scanned_rows`); `.tsv`; a headerless CSV with `column_names`; a header-suspect CSV (warning, `c0..cn` names); Parquet; fixed width with a layout file; fixed width with a parsed layout list | the API calls `profile_columns`; its result is a `ColumnProfile` | the API calls `scan_sources` itself with `sample_rows=rows` and no `rows=0` mapping (the 10,050-row and `rows=0` cells go red) | C2 |
| AT-2 | DataFrame parity: write `df` to `t.parquet`; `decoy scan t.parquet --output` against `decoy.scan(df, source_label="t")`: identical except `tables[0].descriptor.path`, which is `"<dataframe>"` on the API side | the API result is a `ColumnProfile` | drop 5.4 step 4 (the temp path reaches the core) | C2 |
| AT-3 | Defaults: `decoy.scan(F, has_header=True)` with no `rows` equals `decoy scan F --has-header` with no `--rows`, on a 10,050-row file | the API default reads every row | set the API default to `rows=None` | C2 |
| AT-4 | `decoy.scan("x.csv")` without `has_header` raises `ValueError` whose text equals the CLI usage error for the same input; the same for `has_header=False` without `column_names`, and for `format="fixed-width"` without `layout` | the API guesses the header | default `has_header=True` in the API | C2 |
| AT-5 | The API result validates against the engine read model (`ScanSetCoreRead`), and a recursive walk finds no `detail`, `top_values`, `mode`, `min` or `max` key | the result is a value-bearing profile | call `scan_set_to_dict(detail=True)` | C2 |
| AT-6 | Sentry G-ONE-SCAN-CALL: a syntax-tree walk over `src/decoy` finds every call, attribute access and import of `scan_sources`, `scan_set_to_dict` and `profile_columns` from `decoy_engine` (`from decoy_engine import x`, `from decoy_engine.profiling import x`, `import decoy_engine as de; de.x(...)`, an `as` alias). A site outside `cli/scanning/_engine_call.py` fails unless its `file::function` is in the `scan-call-allow` baseline. Self-tests seed each spelling in a scratch source and assert the walk finds it | no sentry | add `from decoy_engine import profile_columns` and a call in `api.py::scan` | C1 (the allowlist holds `api.py::scan`); C2 (that entry removed) |
| AT-7 | Error parity: a CSV with a repeated column name, and a `.parquet` file that is not Parquet. The API raises the engine's error class (`ScanSourceError` or the file-access class) with the same `table` and `cause_class` the CLI prints; the exception text holds no marker value seeded in the data | the API raises a pandas error, or renames silently (D9) | wrap the engine error as `ValueError(str(exc))` | C2 |
| AT-8 | Signature pin in `tests/unit/release/test_api_signatures.py`: the parameter list and defaults of 5.4 | old signature | remove `has_header` | C2 |
| AT-9 | `decoy demo` `scan.json` bytes equal `core_bytes` of the run (guard; the existing demo tests stay green) | green (guard) | write with `indent=None` in demo | C1 |
| AT-10 | A DataFrame scan whose engine call is patched to raise leaves no file under the private temp prefix; a successful scan leaves none either | new behaviour | remove the `finally` unlink | C2 |
| AT-11 | A DataFrame with a mixed int and str object column raises `TypeError` that names the class only; the seeded marker value is not in the text | the API profiles it in pandas | re-raise the Arrow error text | C2 |
| AT-12 | Choke point unit test: `rows` of 0 and None both give `sample_rows=None, strategy="full"`; a bad strategy and a negative `rows` raise `ScanUsageError` before the engine is called; `on_stage` runs twice | no choke point | map `rows=0` to `sample_rows=0` | C1 |

Existing tests that change: `tests/unit/test_api.py:403-449` (`test_scan_dataframe_returns_profile`, `test_scan_path_csv`, `test_scan_parity_with_cli_scan`) are replaced by AT-1 to AT-5. PR #340 adds a `decoy.scan()` floor test (row 24zm: "`profile_document` floors a rare label while the in-memory profile keeps it") that reads a `ColumnProfile` from `decoy.scan()`; C2 changes it to call `decoy_engine.profile_columns` directly, which is the function it tests. The test module docstring (`tests/unit/test_api.py:1-16`) is updated.

## 8. Mutations (gate set)

Run on the exact head of each slice (T2). M1: `sample_rows=None` always (AT-0, AT-1). M2: API default `rows=None` (AT-3). M3: `detail=True` (AT-5). M4: a direct `profile_columns` call in `api.py` (AT-6). M5: drop the temp-path replacement (AT-2). M6: drop the `finally` unlink (AT-10). M7: `has_header` defaults to `True` (AT-4). M8: `rows=0` maps to `sample_rows=0` (AT-12). Each must turn its test red; the gate ledger records the result.

## 9. Placement (against `CODEMAP.md`)

| Path | Change | CODEMAP row | Notes |
|---|---|---|---|
| `src/decoy/cli/scanning/_engine_call.py` | new (about 70 lines) | "`decoy scan` internals" (`CODEMAP.md:52`): `src/decoy/cli/scanning/_<noun>.py`, beside `_multi.py` | add it to the row's examples; the row's sentry cell names the new sentry |
| `src/decoy/cli/scanning/__init__.py` | export `scan_descriptors`, `core_bytes`, `ScanRun`, `DEFAULT_SCAN_ROWS`, `resolve_sources` | same row ("Other packages import these names") | |
| `src/decoy/cli/scanning/_multi.py` | `run_scan` calls the choke point; `ScanUsageError(ValueError)`; a list form of the `column_names` check | same row | about 580 lines after PR #340; shrinks by about 10 |
| `src/decoy/cli/scan.py` | delete `_infer_format` and the loaders (`scan.py:210-221`, `298-385`); docstring line 26 names `scan_sources`; the `--rows` default reads `DEFAULT_SCAN_ROWS` | "Command module" (`CODEMAP.md:49`) | lower the ceiling in `tests/sentry/baselines/module-size.json` |
| `src/decoy/api.py` | `scan` rewritten (about 60 lines, was 77); module docstring lines 1-21; imports at `api.py:53-59` | "Python API" (`CODEMAP.md:59`) | `_stage_source_entry` reused unchanged |
| `src/decoy/__init__.py` | docstring lines 7-11 | "Python API" | |
| `src/decoy/cli/demo.py` | `:162-173` calls the choke point | "Command module" | |
| `tests/sentry/scan/__init__.py`, `tests/sentry/scan/test_one_scan_call.py` | new (about 120 lines) | "Sentry test" (`CODEMAP.md:71`): add "`decoy scan` choke points in `tests/sentry/scan/`", as for `tests/sentry/run/` | `tests/sentry/io_policy/` is at its fan-out cap; the walk reuses `tests/sentry/io_policy/_calls.py` |
| `tests/sentry/baselines/scan-call-allow.json` | new: `cli/init.py::init` (C1 and C2), `api.py::scan` (C1 only) | "Sentry test" | a row in `scripts/dev/sentry_registry.toml` (`kind = "json"`) |
| `tests/sentry/baselines/csv-read-allow.json` | remove the two `cli/scan.py` entries (lines 9-16) | io_policy | shrink only |
| `tests/unit/scanning/__init__.py`, `tests/unit/scanning/test_engine_call.py` | new (AT-12) | "`decoy scan` internals" tests `tests/unit/` | a package, so the flat `tests/unit/` does not grow |
| `tests/unit/api_scan/__init__.py`, `tests/unit/api_scan/test_parity.py`, `tests/unit/api_scan/test_inputs.py` | new (AT-1 to AT-5, AT-7, AT-10, AT-11) | "Python API" tests: add `tests/unit/api_scan/` beside `tests/unit/test_api.py` | the matrix would push `test_api.py` past its size cap |
| `tests/unit/release/test_api_signatures.py` | AT-8 | Python API | |
| `docs/release/frozen-surfaces.md:22` | the row says `scan` returns the `scan-set/v1` core | "Release runbooks, logs and maps" (`CODEMAP.md:76`) | |
| `CHANGELOG.md`, `docs/roadmap/groups/health.md`, `docs/RECENTLY-SHIPPED.md` | entries | docs | |

## 10. Design notes

- Principle: one source for a fact that two surfaces show. The concrete pain: D1 to D12 exist because the API reimplemented read and sample steps the engine already owns.
- Pattern: a choke point plus a walk-based sentry with a ratchet baseline, as in `tests/sentry/run/test_one_result_builder.py` and `tests/sentry/io_policy/outbound/`. The sentry resolves names through the shared `_calls.py` walker, never a grep.
- Where each fact lives: the default rows, the `rows=0` rule and the strategy check in `_engine_call.py`; the header, TSV, layout and table-name rules in `_multi.py::resolve_sources`; the serializer in `_engine_call.py::core_bytes`; DataFrame staging in `api.py::_stage_source_entry`. None is restated.
- Deletion test: `scan_descriptors` is more than a forwarding wrapper. It owns the rows and strategy rules that today sit in `run_scan` and are missing from the API, and it is the one site the sentry allows. `ScanRun` exists because the CLI needs both the in-memory result (for `k_anonymity` and `sample_strategy`) and the core; the API uses only the core.
- The choke point sits in `cli/scanning/`, not in a new `src/decoy/_scan.py`, because its other half (`resolve_sources`, `ScanUsageError`) is there and `api.py` already imports from `decoy.cli.*`.

## 11. Overlap with PR #340

PR #340 (`feat/cli-halves-0281`, open, under remediation) changes the same files:

- `src/decoy/cli/scanning/_multi.py`: adds `is_sample`, `rows_scanned_text`, `key_candidates_text`, `scanned_rows_note`, `saved_field_facts`. `_table_summary` reads `row_count`, `row_count_exact`, `scanned_rows` and `basis` from the core instead of `scan.profile.row_count`. `--json` gains `basis`, `scanned_rows` and `row_count_exact`, and `row_count` becomes the source total (breaking). It does not touch `run_scan`'s engine call (`_multi.py:442-453`).
- `src/decoy/api.py`: only the `scan` docstring (the `profile_document` floor), which C2 rewrites.
- `src/decoy/cli/scan.py`: `scan show`, the epilog, and a 3-line shrink with a lower module-size ceiling.
- `tests/unit/test_api.py`: adds the row 24zm floor test that reads `decoy.scan()` as a `ColumnProfile`.

Plan: C1 and C2 branch from `origin/main` after #340 merges. AT-0 records the CLI bytes from that base, so #340's labels are the baseline, not a change. The `basis`, `scanned_rows` and `row_count` meaning in the API result come from the engine core, so they match #340's `--json` meaning with no extra work. If #340 is still open when C1 is ready to build, C1 waits; it does not stack on #340.

## 12. Compatibility impact

C1: none visible. CLI bytes do not change (AT-0, AT-9).

C2: `decoy.scan()` changes. One `CHANGELOG.md` entry under `[Unreleased]`, `### Changed`:

- **Breaking: `decoy.scan()` returns the `decoy scan --output` document and follows the CLI's input rules (FREEZE-SURFACE item 3, audit J2).** It now calls the same function as `decoy scan` and returns the value-free `scan-set/v1` core as a dict, not the engine's `ColumnProfile`; it has no top values, modes, minimum or maximum. A CSV path needs `has_header=True` or `has_header=False` (with `column_names`). A `.tsv` file is read tab-delimited. The default is the first 10,000 rows; `rows=None` or `rows=0` reads every row. A source with a repeated column name is refused. Table names follow `decoy scan` (`source_label` overrides; a DataFrame is `dataframe`, with source path `<dataframe>`). Scan errors are the engine's class-only errors. `format`, `layout`, `has_header` and `column_names` with a DataFrame now raise `ValueError`. A DataFrame is staged to an owner-only temp Parquet file for the scan and removed afterwards. For the value-bearing profile, call `decoy_engine.profile_columns`.

If the freeze plan's X1 has merged by then, the entry also starts with "Experimental:", per contract section 3.6 rule 2. Consumers inventoried: `tests/unit/test_api.py`, `tests/unit/release/test_api_signatures.py`, `docs/release/frozen-surfaces.md:22`, `docs/roadmap/groups/scan.md:16` (row 24zm text), `docs/RECENTLY-SHIPPED.md`, and the `decoy.scan()` mentions in `CHANGELOG.md` (history, unchanged). No README, guide or example calls `decoy.scan(` (grep over `README.md` and `docs/` outside records, plans and archive). No platform consumer (platform parked). If Q3 is taken, the CLI's negative `--rows` moves from exit 3 (`PipelineConfigError` from the engine) to exit 1 (usage error); the entry says so.

## 13. Owner questions

| Q | Question | Options | Recommended |
|---|---|---|---|
| Q0 | Is item 3 in 1.0 scope? The freeze plan's Q4 moved J2 to v1+, but the health row lists it as left | (a) 1.0, before row 93; (b) v1+, and the health row says so | (a). Each fix changes the public return type or a default. After 1.0 that is a 2.0 change, or an experimental-tier minor change that 1.0 users still feel. Today's API also returns cell values and reads `.tsv` files as one column (D5); these are defects, not features |
| Q1 | What does `decoy.scan()` return? | (a) the `scan-set/v1` core dict, the bytes `decoy scan --output` writes; (b) the engine `ScanSet` object (value-bearing profile inside); (c) keep `ColumnProfile`, taken from `scan_sources` | (a). It is the only option that makes "cannot drift" testable byte for byte. It is value-free like every other public scan output, and `scan fields`, `show` and `diff` read it. Option (c) still differs from the CLI in every core-only member |
| Q2 | Must a CSV path state its header? | (a) yes, `has_header` is required for CSV, as in the CLI; (b) default `True` | (a). "Scan never guesses" has been a CLI rule since SCAN-MULTI S1c.1; a default would bring back D3 |
| Q3 | Default `rows` | (a) 10,000, as in the CLI; (b) keep `None` (all rows) | (a). Same call, same sample. `rows=None` and `rows=0` both read every row. A negative `rows` becomes a usage error on both routes (exit 1 on the CLI, was exit 3) |
| Q4 | How does a DataFrame reach the engine? | (a) an owner-only temp Parquet file, the `decoy.mask()` pattern; (b) a new engine in-memory scan entry (engine slice, release and repin) | (a). No engine release, and the reader is then the Parquet reader the CLI uses, so AT-2 can prove parity. (b) can replace it later with no public change |
| Q5 | Table name and `source_label` | (a) keep the parameter; it sets the table name; the default is `table_name_from_path(path)` or `dataframe`; (b) rename the parameter to `table` | (a). No extra rename; the docstring says what it names |
| Q6 | Several inputs in one `decoy.scan()` call | (a) not now; additive in 1.x; (b) now | (a). No consumer asks for it, and it is additive |

## 14. Slices

| Slice | Repo | Content | Risk | Tests | After | Gate |
|---|---|---|---|---|---|---|
| C1 | CLI | `_engine_call.py` (`scan_descriptors`, `core_bytes`, `ScanRun`, `DEFAULT_SCAN_ROWS`); `run_scan` and `decoy demo` call it; sentry G-ONE-SCAN-CALL with `scan-call-allow` (`cli/init.py::init`, `api.py::scan`); CODEMAP rows; no output change | R1 | AT-0, AT-6, AT-9, AT-12; existing scan and demo e2e | PR #340 merged; owner Q0 | T1 plus the mutations of its tests; Codex |
| C2 | CLI | `decoy.scan()` ported (5.4); `ScanUsageError(ValueError)`; scan.py loaders deleted; `csv-read-allow` and `scan-call-allow` shrink; module-size ceiling lowered; tests replaced; CHANGELOG Breaking entry; frozen-surface map row; health row and RECENTLY-SHIPPED | R2 | AT-1 to AT-5, AT-7, AT-8, AT-10, AT-11 | C1; owner Q1 to Q5 | T2 on the exact head plus M1 to M8; full suite before merge (escalation triggers: a frozen public signature and result, and moved or deleted tests); Dennis then Codex |

Two slices because they carry different risk: C1 is a refactor with no output change plus a guard; C2 is the public break. If the owner prefers one slice, C1 folds into C2 and the gate is R2.

Size: C1 adds about 70 source lines, removes about 15, and adds about 200 test lines. C2 adds about 60 source lines, removes about 175 (the old API body and the scan.py loaders), and adds about 300 test lines. Public names added: none (`decoy.scan` gains two keyword parameters).

## 15. Done when

- `scan-call-allow` holds only `cli/init.py::init`, and the sentry's seeded mutation was shown red.
- AT-0 to AT-12 pass on the merge head of each slice; M1 to M8 are recorded red.
- `CHANGELOG.md` has the Breaking entry; `docs/release/frozen-surfaces.md:22` and `CODEMAP.md` rows 52, 59 and 71 are updated.
- The FREEZE-SURFACE row in `docs/roadmap/groups/health.md` records item 3 as merged, and `docs/RECENTLY-SHIPPED.md` lists it.

## 15.1 Plan defect catalog classes

| Class | Defect | Closing structure | Sentry or property test | Seeded mutation | Slice |
|---|---|---|---|---|---|
| 1 | Value exposure (a cell value in the API result or in an exception text) | the API returns only the `detail=False` core; it reads no file itself; engine errors are class-only; the Arrow conversion error is re-raised by class | AT-5, AT-7, AT-11 | `detail=True`; `ValueError(str(exc))` | C2 |
| 2 | Cleanup on every exit (the DataFrame's temp Parquet file left behind) | staging and unlink in one `try`/`finally` in `api.scan` | AT-10 | remove the `finally` unlink | C2 |
| 3 | State completeness (every scan producer goes through the choke point; every allowed bypass has a reason) | `scan-call-allow` baseline with a reason per entry, shrink-only | AT-6 | add a site with no allowlist row | C1, C2 |
| 4 | Route coverage (CLI, demo and API take one path; every input kind has a parity cell) | `scan_descriptors` is the only engine caller; the AT-1 matrix has a cell per drift row and per format | AT-1, AT-2, AT-6, AT-9 | the API calls `scan_sources` itself | C1, C2 |
| 5 | Referential integrity | not applicable: the scan passes no relationships (`relationships` stays empty on both routes) | none | none | - |
| 6 | Untrusted input (caller-given paths, layouts, column names and DataFrames) | the CLI's `resolve_sources` checks apply to the API; the engine validates each descriptor | AT-4, AT-7, AT-11 | default `has_header=True` | C2 |
| 7 | TOCTOU or check-then-use | not applicable beyond today: the engine opens the descriptor path it validated; the temp file is created owner-only by `create_private_temp` before the write | existing private-file sentries | none new | - |
| 8 | Weak proof (a sentry that passes on an empty walk; a parity test that compares a few members) | the sentry self-tests seed each spelling and assert the walk finds `_engine_call.py` itself; parity compares whole documents byte for byte | AT-6 self-tests, AT-1 | make the walk return nothing | C1, C2 |

## 16. Pre-mortem

- "The parity test was green, but users still saw different numbers." The AT-1 matrix has a cell for each drift row D3 to D10; a new input option on either route adds a cell.
- "The sentry missed `import decoy_engine.profiling.scan_set as s; s.scan_sources(...)`." The self-tests seed the module alias form; a runtime-bound name (`getattr`) is a named limit, as in the CSV read sentry.
- "Staging a 5 GB DataFrame filled the temp folder." Known limit (F11), the same as `decoy.mask()`; the docstring says to pass a path for large data.
