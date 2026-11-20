Status: plan (revision 2, 2026-11-20)

# FREEZE-SURFACE item 3: `decoy.scan()` and `decoy scan` make one engine call

Owner: Cam. Author: Opus (plan author, CLI). Date: 2026-11-20. Roadmap row: FREEZE-SURFACE item (3) in `docs/roadmap/groups/health.md` ("Audit J2: `api.scan` and `decoy scan` use one profile call, so the public scan result cannot drift from the CLI's").

Sources: proportionality audit `docs/records/2026-11-15-proportionality-audit/REMEDIATION.md` row J2 (line 353: "`api.scan` calls `profile_columns` while the CLI calls `scan_sources`. Point `api.scan` at `scan_sources`, share the helpers"); engine freeze batch plan `E:docs/plans/2026-11-18-freeze-batch.md` on branch `plan/freeze-batch` (revision 3.3), sections 1, 4.1 and 4.2, for the format and the X1 experimental tier.

Anchors: a path with no prefix is in this repository (decoy CLI); `E:` is decoy-engine. CLI `origin/main` `1120e39a` (PR #340 and PR #351 merged); engine `origin/main` `2b826e01d`.

Rules consulted: dev-rules `README.md` (routing), `00-universal.md`, `risk-and-exceptions.md` (compatibility is an R2 trigger), `development-loop.md` (PLAN: guarantee, failure modes, acceptance tests first with their mutation, size, placement, design notes, choke point, slices), `cross-cutting-concerns.md` (one choke point, a walk-based guard, its seeded mutation, a ratchet allowlist), `api-and-compatibility.md` (consumer inventory, explicit breaking change, contract tests), `architecture.md` (placement against CODEMAP), `reuse-first.md`, `proportionality.md` (size, deletion test, no forwarding wrapper), `testing.md` (T0 to T2, full-suite escalation triggers).

Risk: R2. `decoy.scan` is public API (`_LAZY_API` in `src/decoy/__init__.py:20`, `docs/release/frozen-surfaces.md:22`, signature pinned in `tests/unit/release/test_api_signatures.py:26`). Slice C2 changes its return value, a default and its accepted inputs. Slice C1 changes two `decoy scan` usage refusals (section 12). Approver: Cam for the plan; Dennis then Codex for the plan gate.

## Revision 2 (review round 1)

Owner answers of 2026-11-20 are binding and recorded in section 13. Changes for each Dennis round 1 finding:

1. Base moved (#340 and #351 merged; `run_scan` now passes `pre_scan` inside `detector_log`). `scan_descriptors` takes `pre_scan: PreScanConfig | None = None`; `run_scan` keeps the preflight and `detector_log` (5.1, 5.2). G2 now reads "same file, same options, regex detectors"; `decoy.scan()` is regex only and its docstring says so (2, 5.4). AT-0 has a `--detectors regex` cell and AT-12 checks that `pre_scan` reaches the engine. Every file:line in sections 1, 9 and 15.2 is re-anchored on `1120e39a`; section 11 is removed.
2. Arrow error leak. `_to_pa_table` (`src/decoy/api.py:203-210`) catches `pa.ArrowException`, `ValueError` and `TypeError`, keeps only the class name, and raises the `TypeError` after the `except` block has closed, so `__cause__` and `__context__` are both `None`. This also covers `decoy.mask()` (5.4 step 2, F7, AT-11).
3. Layout list. `resolve_sources` and `_layout_columns` accept `Path | list[dict]` and check a list with the same rules `_parse_layout` applies; `api.py` builds no descriptor (5.4 step 1, section 9 row for `_multi.py`, AT-13).
4. No third strategy list. `check_scan_options` takes the allowed values from `SampleStrategy` (`src/decoy/cli/scan.py:59-62`); the API default is `rows=DEFAULT_SCAN_ROWS` (5.1, 5.4).
5. Usage before the engine. `check_scan_options(rows, strategy)` in `_engine_call.py` runs in `run_scan` before its engine `try`, so `decoy scan --rows -1` exits 1, not 3. This is a visible C1 change (section 12) with an e2e test (AT-14).
6. Input refusals. `resolve_sources` raises `ScanUsageError` for an unsupported format (allowed list taken from `_FORMAT_FLAG`), a missing path, a directory, and an unknown extension with no format (allowed suffixes listed). Both routes share it (5.4, AT-13, AT-14).
7. Repeated names. A repeated CSV header is renamed by pandas (`a`, `a.1`) and CSV is exempt from the duplicate refusal (`E:src/decoy_engine/execution/_guards.py:73-76`). D9 is corrected; AT-7 uses a Parquet file with a repeated name, and AT-1 has a repeated-header CSV parity cell.
8. AT-0 no longer compares against bytes recorded from the base commit. It compares `decoy scan --output` with a direct engine call made with the pre-refactor arguments in the same test run.
9. Temp name. The DataFrame is staged under the fixed name `scan`, never the caller's `source_label` (5.4 step 2, F13, AT-10 with `tempfile.tempdir` patched).
10. `core_bytes` is the serializer for saved scan files; `--output -` keeps `emit_json_document(..., indent=None)` (`_multi.py:559-561`). Stated in 5.1.
11. Error text names the caller's own spelling. `resolve_sources` takes a `spelling: ScanSpelling` parameter; the CLI passes the flag names, the API passes its keyword names (5.1, 5.4, AT-4).
12. C2 removes the `cli/scan.py::_load_parquet_with_sampling` entry in `CALLER_NAMED` (`tests/sentry/io_policy/test_declared_read_choke_point.py:100-103`); listed in section 9.
13. Section 15 has one "done when" line per slice.

## 1. Current behaviour

Two public routes produce "a scan" of the same file through different engine calls, different readers and different defaults.

### 1.1 `decoy scan` (CLI)

- `src/decoy/cli/scan.py:477-589`: `_scan` declares the options and calls `decoy.cli.scanning.run_scan`. Defaults: `--rows 10000` (`scan.py:490-491`, a literal), `--strategy head` (`SampleStrategy`, `scan.py:59-62`); `--rows 0` means a full read. Typer checks that each path exists and is not a directory (`scan.py:478-484`, exit 2) and limits `--format` to `InputFormat`.
- `src/decoy/cli/scanning/_multi.py:198-241` `resolve_sources`: each path becomes an explicit engine source descriptor. The kind comes from `--format` through `_FORMAT_FLAG` (`_multi.py:49`, `_kind` at `:153-161`); with no format, any suffix that is not Parquet or fixed width is read as CSV (`:161`). A CSV must say `--has-header` or `--no-header` (`_check_header_flags`, `:173-195`); `.tsv` gets `delimiter: "\t"` (`:238-239`); the table name comes from `table_name_from_path` (`:68-77`). `_layout_columns` (`:244-268`) takes only a path and parses it with `scan.py::_parse_layout` (`scan.py:221-292`). The usage texts name CLI flags (`--column-names`, `--no-header`, `--layout`).
- `src/decoy/cli/scanning/_multi.py:485-561` `run_scan`: usage checks and `pre_scan = _detectors.resolve_pre_scan(...)` (`:504-518`); the model preflight (`:520`); the `--rows 0` rule (`:522-524`); then, inside `detector_log(...)` and the progress stages, one call `scan_sources(descriptors, sample_rows=row_cap, strategy=effective, pre_scan=pre_scan)` and `scan_set_to_dict(result, detail=False)` (`:526-541`). `--output FILE` writes `json.dumps(core, indent=2)` (`:544-547`); `--output -` writes `emit_json_document(state, core, indent=None)` (`:559-561`). Any failure in that `try` is exit 3 with a class-only message (`_failure_message`, `:281-290`; `:549-557`). A negative `--rows` reaches the engine and fails there: exit 3.
- The engine reader (`E:src/decoy_engine/profiling/scan_set.py:314-378`) builds the declared source, reads `cap + 1` rows to set `basis` (`:335-345`, `:374`), refuses repeated column names (`:346`), runs the header guard (`:352-360`, a warning), counts leading zeros, and wraps unclassified failures in the value-free `ScanSourceError` (`_scan_one`, `:289-304`). The core renames the fields of a header-suspect table to `c0..cn` (`_core_names`, `:465-474`).

### 1.2 `decoy.scan()` (library API)

- `src/decoy/api.py:653-732`: `scan(data, *, source_label=None, rows=None, strategy="head", format=None, layout=None)`.
- A path is read by the CLI's own pandas loaders in `src/decoy/cli/scan.py:295-377` (`_load_csv_with_sampling`, `_load_parquet_with_sampling`, `_load_fixed_width_with_sampling`, `_load_data`), with `_infer_format` (`scan.py:207-218`), imported at `api.py:53-59`. A DataFrame is cut with `df.head` or `sample_frame` (`api.py:701-707`).
- Then `decoy_engine.profile_columns(df, source_label=..., sample_strategy=..., sample_row_cap=rows)` (`api.py:694`, `:727-732`). It returns the in-memory `ColumnProfile`, which holds cell values (top values, modes, min and max).
- `decoy.mask()` turns a DataFrame into Arrow through `_to_pa_table` (`api.py:203-210`), which lets an Arrow conversion error (its text can quote a cell) reach the caller.

### 1.3 Where the two results drift today

| # | Fact | `decoy scan` | `decoy.scan()` | Where |
|---|---|---|---|---|
| D1 | Engine call | `scan_sources` + `scan_set_to_dict(detail=False)` | `profile_columns` | `_multi.py:526-541`; `api.py:694,727` |
| D2 | Result | value-free `scan-set/v1` core | value-bearing `ColumnProfile` | `api.py:686-692` (the docstring says so) |
| D3 | CSV header | must be stated; never guessed | pandas assumes row 1 is a header | `_multi.py:173-195`; `scan.py:295-308` |
| D4 | Header guard | warns; the core names the fields `c0..cn` | none | `E:scan_set.py:352-360,465-474` |
| D5 | TSV | tab delimiter | read with a comma: one column | `_multi.py:238-239`; `scan.py:295-308` (`pd.read_csv(path)`) |
| D6 | Default rows | 10,000 | all rows | `scan.py:490-491`; `api.py:657` |
| D7 | Basis and totals | `basis`, `row_count` (source total), `row_count_exact`, `scanned_rows` | none; `row_count` is the rows read | `E:scan_set.py:335-345,374` |
| D8 | Key candidates, warnings, leading-zero counts | yes | no | `E:scan_set.py:346-378` |
| D9 | Repeated column names | Parquet: refused (`E:scan_set.py:346`). CSV: pandas renames a repeated header to `a`, `a.1`, and CSV is exempt from the refusal (`E:src/decoy_engine/execution/_guards.py:73-76`) | Parquet: read by pandas, no refusal. CSV: the same `a.1` rename | engine guard; `scan.py:310-327` |
| D10 | Readers | engine declared-source readers (CSV dialect, Parquet, fixed width) | CLI pandas readers, `pd.read_fwf` | `E:scan_set.py:326`; `scan.py:295-377` |
| D11 | Errors | class and table only (`ScanSourceError`) | raw pandas, parser or Arrow exception, whose text can quote a cell | `E:scan_set.py:289-304`; `api.py:720` |
| D12 | Table name | `table_name_from_path` | `source_label`, else the file name, `<dataframe>` for a frame | `_multi.py:68-77`; `api.py:708,721` |
| D13 | Unknown suffix, bad format, missing path | unknown suffix read as CSV; bad format and missing path stopped by Typer | unknown suffix read as CSV; bad format is a `ValueError` from `InputFormat(...)`; missing path is the pandas `FileNotFoundError` | `_multi.py:153-161`; `api.py:715` |

The test that claims parity (`tests/unit/test_api.py:448`, `test_scan_parity_with_cli_scan`) compares only `row_count`, the name stem, `reid_risk_score` and `pii_score` on a three-row CSV with a header, so none of D3 to D13 is exercised.

A third caller, `decoy demo`, calls `scan_sources` and `scan_set_to_dict` itself (`src/decoy/cli/demo.py:153-164`). `decoy init` calls `profile_columns` for strategy inference (`src/decoy/cli/init.py:374-376`); it is not a scan surface (section 2, non-goals).

## 2. Guarantee and non-goals

Guarantees after this work:

- G1. One internal function, `decoy.cli.scanning.scan_descriptors`, is the only first-party caller of `decoy_engine.scan_sources` and `decoy_engine.scan_set_to_dict`. `decoy scan`, `decoy demo` and `decoy.scan()` all call it. A sentry fails on any other call or import of `scan_sources`, `scan_set_to_dict` or `profile_columns` under `src/decoy`, except a named allowlist (`cli/init.py::init` for `profile_columns`, with its reason).
- G2. For the same file, the same options and regex detectors, `decoy.scan()` returns the same `scan-set/v1` core that `decoy scan --output` writes. Serialized with `core_bytes`, the bytes are identical once `scanned_at` (the one wall-clock member) is set to the same value.
- G3. `decoy.scan()` has the CLI's input rules: a CSV path states its header (`has_header`), a headerless CSV gives `column_names`, `.tsv` is tab-delimited, fixed width needs `layout`, an unknown suffix needs `format`, and the default sample is `DEFAULT_SCAN_ROWS` (10,000) rows, with `rows=None` or `rows=0` for a full read.
- G4. `decoy.scan()` returns no cell value and raises no exception whose text, `__cause__` or `__context__` holds a cell value: its result is the value-free core, engine scan errors reach the caller as the engine raises them (class and table only), and the Arrow conversion error is a class-only `TypeError` with no chain. The last part holds for `decoy.mask()` too.
- G5. A DataFrame passed to `decoy.scan()` goes through the same engine reader as a Parquet file: it is written to an owner-only temp Parquet file (the `decoy.mask()` staging helper) under a fixed name, which is removed on success and on failure. The returned core names its source path as `<dataframe>`, never the temp path.
- G6. A usage error (bad rows, bad strategy, bad format, unknown suffix, missing path, header flags, layout) is found before the engine is called, on both routes: `ScanUsageError` (a `ValueError`) in the API, exit 1 in the CLI.

Non-goals:

- No engine change. `scan_sources` and `scan_set_to_dict` are used as they are in the pinned engine.
- No change to `decoy scan` output bytes: card, `--json`, `--output` and `--output -` stay as on `1120e39a`. The two usage changes in section 12 are the only visible CLI changes.
- No multi-table `decoy.scan()` (a mapping of inputs). Additive later (Q6).
- No model detectors in `decoy.scan()`. It is regex only, and its docstring says so; `decoy scan --detectors` keeps its models through `scan_descriptors(pre_scan=...)`. A `detectors` keyword on the API is additive later.
- `decoy init` keeps its direct `profile_columns` call. The init wizard is stopped (owner 2026-11-19), and its profile feeds strategy inference, not a scan result. It is an allowlist entry, not a route.
- `decoy fit` and the `decoy run` pre-scan and post-scan are out of scope; they do not produce a scan document.
- No new public name. `decoy.scan` gains two keyword parameters; no new exception type is exported.
- Compressed `.tsv` files keep today's CLI behaviour (the tab rule reads `p.suffix`); not widened here.

## 3. Established solutions

Search run: the codebase (this repository's choke points and their sentries, `decoy.mask()` staging, the engine scan entry) and the dev-rules pattern catalog. No online search was needed: this is a routing refactor with a known house pattern, not an algorithm, parser or protocol problem.

| Concern | Established solution | What we take |
|---|---|---|
| One route to a shared effect | A choke point plus a walk-based guard (dev-rules `cross-cutting-concerns.md`); in this repo `_outbound.open_url`, `_config_file`, `cli/run/_result.py` (the one result builder, guarded by `tests/sentry/run/test_one_result_builder.py`) | One function owns the engine call and the saved-file serialization; a sentry walks the syntax tree for bypasses, with a ratchet allowlist. |
| Library and CLI share one core | A thin command over a library function (Click and Typer guidance; pip's commands over shared internals) | The command and the library function both call one internal function; neither calls the engine directly. |
| In-memory data through a file-only reader | `decoy.mask()` stages a DataFrame to an owner-only temp Parquet file (`api.py:213-269`, `_stage_source_entry`) | Reuse the same staging helper with a fixed name; no engine in-memory entry (Q4). |
| Contract test for a public result | Consumer-facing golden comparison (dev-rules `api-and-compatibility.md`) | Parity tests compare the API result with the CLI's `--output` bytes over a matrix of inputs. |
| Error text that never quotes data | Raise a fixed-text error outside the handler, as `_layout_columns` does today (`_multi.py:255-266`) | `_to_pa_table` keeps the class name and raises after the handler closes. |

## 4. Reuse inventory

| Need | Existing piece | Path |
|---|---|---|
| Paths to descriptors, header rules, TSV, layout | `resolve_sources`, `_kind`, `_check_header_flags`, `_layout_columns`, `_split_names`, `ScanUsageError` | `src/decoy/cli/scanning/_multi.py:60-65,153-268` |
| Format names | `_FORMAT_FLAG` | `src/decoy/cli/scanning/_multi.py:49` |
| Strategy names | `SampleStrategy` | `src/decoy/cli/scan.py:59-62` |
| Compression suffix split | `split_compression` (as `_format_suffix` uses it) | `src/decoy/cli/io/_targets.py:102-108` |
| Table name from a path | `table_name_from_path` | `src/decoy/cli/scanning/_multi.py:68` |
| Layout rules | `_parse_layout` | `src/decoy/cli/scan.py:221-292` |
| Model detectors | `_detectors.resolve_pre_scan`, `preflight`, `detector_log` | `src/decoy/cli/scanning/_detectors.py:60-90`; `src/decoy/ui/output.py` |
| DataFrame to private temp Parquet | `_stage_source_entry`, `_to_pa_table`, `create_private_temp` | `src/decoy/api.py:203-269`, `src/decoy/_private_file.py:325-335` |
| Engine scan and core | `scan_sources`, `scan_set_to_dict`, `ScanSetCoreRead`, `PreScanConfig` | `E:src/decoy_engine/profiling/scan_set.py:145-215,506` |
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

def check_scan_options(rows: int | None, strategy: str) -> None: ...

def scan_descriptors(
    descriptors: Mapping[str, dict[str, Any]],
    *,
    rows: int | None,
    strategy: str,
    pre_scan: PreScanConfig | None = None,
    on_stage: Callable[[], None] | None = None,
) -> ScanRun: ...

def core_bytes(core: Mapping[str, Any]) -> bytes:   # json.dumps(core, indent=2).encode("utf-8")
```

Rules, each stated once:

1. `check_scan_options`: `strategy` must be a `SampleStrategy` value (the allowed list is `[s.value for s in SampleStrategy]`, imported inside the function, as `_layout_columns` imports `_parse_layout`, because `cli/scan.py` imports `decoy.cli.scanning`), else `ScanUsageError("strategy must be one of ['full', 'head', 'random'], got 'x'.")`. A negative `rows` is `ScanUsageError("rows must be 0 or more, got -1.")`. No other strategy or rows list exists.
2. `scan_descriptors` calls `check_scan_options` first (the API route), then maps rows: `None` or `0`, or `strategy == "full"`, reads every row (`sample_rows=None, strategy="full"`); otherwise `sample_rows=rows, strategy=strategy`. This is the CLI's `--rows 0` rule (`_multi.py:522-524`), moved.
3. It calls `scan_sources(descriptors, sample_rows=..., strategy=..., pre_scan=pre_scan)`, then `on_stage()`, then `scan_set_to_dict(result, detail=False)`, then `on_stage()`. `on_stage` keeps the CLI progress stages without a UI import in the choke point.
4. It catches nothing. Engine errors reach each caller unchanged; the CLI keeps its own class-only message (`_failure_message`, `_multi.py:281-290`).

`core_bytes` is the one serializer of a saved scan file: `run_scan` (`--output FILE`), `decoy demo` (`scan.json`) and the parity tests use it. The one exception is `--output -`, which streams through `emit_json_document(state, core, indent=None)` (`_multi.py:559-561`), the shared stdout JSON writer; its bytes stay as today and AT-0 checks them.

Error spelling. `resolve_sources`, `_check_header_flags`, `_split_names` and `_layout_columns` take `spelling: ScanSpelling` (a frozen dataclass in `_multi.py` with the names `has_header`, `no_header`, `column_names`, `layout`, `format`, and the layout hint). `CLI_SPELLING` holds `--has-header`, `--no-header`, `--column-names`, `--layout`, `--format` and is the default, so today's CLI texts do not change. `API_SPELLING` holds `has_header=True`, `has_header=False`, `column_names=[...]`, `layout=`, `format=`. One template per message; only the names differ. Recommended over a second message set, which would drift.

### 5.2 `decoy scan`

`run_scan` (`_multi.py:485-561`):

- Inside its existing usage `try` (`:504-518`), after `resolve_sources` and `resolve_pre_scan`, it calls `check_scan_options(rows, strategy)`. A bad value is exit 1 with the usual usage error, not exit 3 from the engine.
- It keeps the model preflight (`:520`) and `detector_log(...)`.
- It replaces `:522-541` with `run = scan_descriptors(descriptors, rows=rows, strategy=strategy, pre_scan=pre_scan, on_stage=ms.complete)` inside the same `with detector_log(...), scan_multistage(...)` block, and writes `core_bytes(run.core)` for `--output FILE`. `_table_summary` reads `run.result.tables`.
- `scan.py`'s `--rows` default reads `DEFAULT_SCAN_ROWS`.

Output bytes do not change (AT-0).

### 5.3 `decoy demo`

`demo.py:153-164` calls `scan_descriptors(descriptors, rows=None, strategy="full")` and writes `core_bytes(run.core)` with `Path.write_bytes`. Today it writes `json.dumps(core, indent=2)` with `Path.write_text`, so the file bytes stay the same (AT-9).

### 5.4 `decoy.scan()`

New signature (owner answers, section 13):

```python
def scan(
    data,
    *,
    source_label: str | None = None,
    rows: int | None = DEFAULT_SCAN_ROWS,
    strategy: str = "head",
    format: str | None = None,
    layout: str | Path | list[dict] | None = None,
    has_header: bool | None = None,
    column_names: Sequence[str] | None = None,
) -> dict[str, Any]
```

Steps:

1. A path (`str` or `Path`): `descriptors, _ = resolve_sources([path], fmt=format, layout=layout, has_header=has_header, column_names=column_names, spelling=API_SPELLING)`, the function `decoy scan` uses. `resolve_sources` owns every input rule; `api.py` builds no descriptor:
   - `layout` may be a path or a parsed `columns` list. `_layout_columns(layout: Path | list[dict] | None, spelling)` reads a path with `_parse_layout` and checks a list with the same column rules. To do that, the column loop of `_parse_layout` (`scan.py:251-290`) moves into `_check_layout_columns(columns)`, which `_parse_layout` and `_layout_columns` both call. A bad list gives the same fixed-text `ScanUsageError` as a bad file, raised outside the handler.
   - `column_names` may be a comma string (CLI) or a sequence (API); `_split_names` takes both and applies the same empty and repeated-name rules.
   - `format` not in `_FORMAT_FLAG`: `ScanUsageError("format must be one of ['delimited', 'fixed-width', 'parquet'], got 'x'.")`, the list taken from `_FORMAT_FLAG`. Today the API raises `ValueError` from `InputFormat(...)` and `_kind` would raise a bare `KeyError`.
   - A missing path: `ScanUsageError("<path>: file not found.")`; a directory: `ScanUsageError("<path>: is a directory, not a file.")`. In the CLI, Typer refuses both first (exit 2, unchanged); the check is for the API and for any later caller.
   - No format and a suffix (before any compression suffix, `split_compression`) outside `.csv`, `.tsv`, the Parquet set and the fixed-width set: `ScanUsageError("<path>: cannot tell the format from the suffix '.txt'.", hint "give --format delimited, parquet or fixed-width; known suffixes: .csv, .tsv, .parquet, .pq, .fwf, .dat, .fixed, .fw")`, with the flag named through `spelling`. Today such a file is read as CSV.
   - `source_label`, when given, replaces the derived table name (Q5).
2. A DataFrame: `_stage_source_entry("scan", df, tmp_paths)` writes an owner-only temp Parquet file. The name is the fixed string `scan`, so the file is `.decoy-mask-scan-.decoy-<hex>.tmp` in the temp folder and never holds the caller's `source_label`. `format`, `layout`, `has_header` or `column_names` given with a DataFrame raise `ScanUsageError` (today they are silently ignored, `api.py:676-679`). Table name: `source_label`, else `dataframe`. `_to_pa_table` changes for every caller (`decoy.mask()` included):

   ```python
   if isinstance(value, pd.DataFrame):
       failed: str | None = None
       try:
           return pa.Table.from_pandas(value, preserve_index=False)
       except (pa.ArrowException, ValueError, TypeError) as exc:
           failed = type(exc).__name__   # the class only: Arrow messages quote the cell
       raise TypeError(f"data could not be converted to Arrow: {failed}")
   ```

   The raise sits after the `except` block has closed, so the new error has no `__context__` and no `__cause__`. `_arrow_schema` (`api.py:272-276`, `pa.Schema.from_pandas`) has the same exposure and gets the same shape through one shared helper.
3. `run = scan_descriptors(descriptors, rows=rows, strategy=strategy)`. No `pre_scan`: the API is regex only.
4. For a DataFrame, the returned core's `tables[0].descriptor.path` is set to `"<dataframe>"` (G5).
5. Temp files are removed in a `finally` block.
6. Returns `run.core`. Any other `data` type raises `TypeError`, as today.

`ScanUsageError` becomes a subclass of `ValueError`, so the API raises a `ValueError` with the shared text and exports no new name.

### 5.5 What the API result holds

The `scan-set/v1` core: `scan_schema`, `engine_version`, `scanned_at`, `tables` (each with `name`, `descriptor`, `row_count`, `row_count_exact`, `sample_strategy`, `sample_row_cap`, `fields` (the engine `FieldCore`), `key_candidates`, `warnings`, `reid_risk_score`, `quasi_identifier_groups`, `basis`, `scanned_rows`), `relationships` (empty) and `detectors` (regex only). It no longer holds top values, modes, min and max, or `k_anonymity` (not in the core; the CLI card reads it from the in-memory profile). A caller who needs the value-bearing profile calls `decoy_engine.scan_sources` or `decoy_engine.profile_columns` directly; the docstring says so.

## 6. Failure modes

| # | Failure | Effect | Prevented by |
|---|---|---|---|
| F1 | A new caller (a command, the API, a helper) calls `scan_sources` or `profile_columns` directly | its result drifts from `decoy scan` again | sentry AT-6 with a shrink-only allowlist |
| F2 | The API passes a different default or maps `rows` differently | same call, different sample | the default and the rows mapping live only in `_engine_call.py`; AT-3, AT-12 |
| F3 | The CLI output changes during the refactor | breaks `--json` shapes and saved scans | AT-0, and the existing `tests/e2e/test_scan_command.py`, `tests/e2e/test_scan_basis_labels.py`, `tests/e2e/scan_models/test_scan_detectors.py`, `tests/e2e/release_freeze/test_json_shapes.py` |
| F4 | A CSV path with no `has_header` is scanned with a guess | header row read as data, or the reverse | `resolve_sources` refuses; AT-4 |
| F5 | A DataFrame's temp Parquet file stays on disk after an error | a copy of the caller's data left in the temp folder | `finally` unlink; AT-10 with an injected engine failure |
| F6 | The temp path appears in the returned core | a random, dead path in a result the caller may save; the result is not reproducible | 5.4 step 4; AT-2 |
| F7 | A DataFrame fails the Arrow conversion (a mixed-type object column) | `ArrowTypeError` text, or its `__context__`, quotes the cell | `_to_pa_table` raises a class-only `TypeError` after the handler; AT-11 checks the text and both chain members, for `decoy.scan()` and `decoy.mask()` |
| F8 | Engine error text reaches the API caller with a cell value | leak | the API no longer reads files itself; the engine's `ScanSourceError` is class-only; AT-7 |
| F9 | `decoy.scan()` returns `detail=True` content | cell values in the public result | `scan_descriptors` calls `detail=False` only; AT-5 |
| F10 | A caller relies on today's `ColumnProfile` return | `AttributeError` or `KeyError` after upgrade | Breaking CHANGELOG entry and the docstring; pre-1.0, and `decoy.scan` is in the X1 experimental row of the freeze plan |
| F11 | Staging a large DataFrame briefly doubles memory and disk use | slower, larger temp use | known limit, stated in the docstring; `decoy.mask()` has the same cost |
| F12 | The refactor drops `pre_scan` or moves it out of `detector_log` | `decoy scan --detectors` silently runs regex only, or model logs reach stderr | `run_scan` keeps the preflight and `detector_log`; AT-12 checks forwarding; the existing `tests/e2e/scan_models/` tests stay green |
| F13 | The temp file name holds the caller's `source_label` | a caller-chosen string (possibly sensitive) in a shared temp folder | fixed staging name `scan`; AT-10 |
| F14 | A usage error is found inside the engine call | wrong exit code (3) and a less useful message | `check_scan_options` and the `resolve_sources` refusals run before the engine `try`; AT-13, AT-14 |

## 7. Acceptance tests (red first)

Each test names the mutation that must turn it red. Parity tests compare documents after setting `scanned_at` to `"1970-01-01T00:00:00+00:00"` in both; the byte check compares `core_bytes(cli_doc)` with `core_bytes(api_doc)`. Every test is red on `1120e39a`; the "Red on main because" column says why.

| Id | Test | Red on main because | Mutation that must turn it red | Slice |
|---|---|---|---|---|
| AT-0 | CLI refactor guard, one test run: for each cell, `decoy scan F <flags> --output o.json` against `json.dumps(scan_set_to_dict(scan_sources(descriptors, sample_rows=<pre-refactor row_cap>, strategy=<pre-refactor effective>, pre_scan=None), detail=False), indent=2)` computed in the test from `resolve_sources`, `scanned_at` normalized; the same for `--output -` against `json.dumps(core)` (compact). Cells: CSV `--has-header` default rows; CSV `--rows 0`; CSV `--rows 5 --strategy random`; Parquet; fixed width with a layout file; CSV `--has-header --detectors regex`. A spy on `decoy.cli.scanning._engine_call`'s engine binding records one call per scan | `_engine_call` does not exist: the spy cannot attach | in `scan_descriptors`, pass `sample_rows=None` always | C1 |
| AT-1 | Parity matrix, file inputs: `decoy scan F <flags> --output o.json` against `decoy.scan(F, <same kwargs>)`, byte-identical. Cells: CSV with `has_header=True` and default rows; CSV `rows=0`; CSV `rows=5, strategy="random"`; CSV `rows=5, strategy="full"`; a CSV of 10,050 rows with default rows (basis `sample`, `row_count > scanned_rows`); `.tsv`; a headerless CSV with `column_names`; a header-suspect CSV (warning, `c0..cn` names); a CSV whose header repeats `a` (both routes give fields `a` and `a.1`, D9); Parquet; fixed width with a layout file; fixed width with a parsed layout list | the API calls `profile_columns`; its result is a `ColumnProfile` | the API calls `scan_sources` itself with `sample_rows=rows` and no `rows=0` mapping (the 10,050-row and `rows=0` cells go red) | C2 |
| AT-2 | DataFrame parity: write `df` to `t.parquet`; `decoy scan t.parquet --output` against `decoy.scan(df, source_label="t")`: identical except `tables[0].descriptor.path`, which is `"<dataframe>"` on the API side | the API result is a `ColumnProfile` | drop 5.4 step 4 (the temp path reaches the core) | C2 |
| AT-3 | Defaults: `decoy.scan(F, has_header=True)` with no `rows` equals `decoy scan F --has-header` with no `--rows`, on a 10,050-row file; `inspect.signature(decoy.scan).parameters["rows"].default is DEFAULT_SCAN_ROWS` | the API default reads every row | set the API default to `rows=None` | C2 |
| AT-4 | Header rules with API spelling: `decoy.scan("x.csv")` without `has_header` raises `ValueError` whose text is the CLI template with `has_header=True` / `has_header=False` in place of `--has-header` / `--no-header`, and names no `--` flag; the same for `has_header=False` without `column_names`, for a repeated name in `column_names`, and for `format="fixed-width"` without `layout`. The CLI texts for the same inputs are unchanged (existing e2e) | the API guesses the header | default `has_header=True` in the API; or pass `CLI_SPELLING` from the API | C2 |
| AT-5 | The API result validates against the engine read model (`ScanSetCoreRead`), and a recursive walk finds no `detail`, `top_values`, `mode`, `min` or `max` key | the result is a value-bearing profile | call `scan_set_to_dict(detail=True)` | C2 |
| AT-6 | Sentry G-ONE-SCAN-CALL: a syntax-tree walk over `src/decoy` finds every call, attribute access and import of `scan_sources`, `scan_set_to_dict` and `profile_columns` from `decoy_engine` (`from decoy_engine import x`, `from decoy_engine.profiling import x`, `import decoy_engine as de; de.x(...)`, an `as` alias). A site outside `cli/scanning/_engine_call.py` fails unless its `file::function` is in the `scan-call-allow` baseline. Self-tests seed each spelling in a scratch source and assert the walk finds it | no sentry | add `from decoy_engine import profile_columns` and a call in `api.py::scan` | C1 (the allowlist holds `api.py::scan`); C2 (that entry removed) |
| AT-7 | Error parity: a Parquet file with two columns named `a` (written with `pa.Table.from_arrays(..., names=["a", "a"])`), and a `.parquet` file that is not Parquet. The API raises the engine's error (the duplicate-name refusal or `ScanSourceError`) with the same class, `table` and `cause_class` the CLI prints; the exception text holds no marker value seeded in the data | the API reads the duplicate Parquet with pandas and does not refuse (D9), and raises a pyarrow error for the bad file | wrap the engine error as `ValueError(str(exc))` | C2 |
| AT-8 | Signature pin in `tests/unit/release/test_api_signatures.py`: the parameter list and defaults of 5.4 | old signature | remove `has_header` | C2 |
| AT-9 | `decoy demo` `scan.json` bytes equal `core_bytes` of the run, and the spy of AT-0 records that demo's scan went through `_engine_call` | `_engine_call` does not exist | write with `indent=None` in demo; or call `scan_sources` in demo directly | C1 |
| AT-10 | With `tempfile.tempdir` patched to an empty `tmp_path`: during a DataFrame scan (`source_label="secret_label"`) the engine spy sees exactly one staged file whose name starts with `.decoy-mask-scan-` and does not contain `secret_label`; after a successful scan and after a scan whose engine call is patched to raise, `tmp_path` is empty | the API stages nothing; no staged file exists | remove the `finally` unlink; or stage with `source_label` as the name | C2 |
| AT-11 | A DataFrame with a mixed int and str object column holding a marker string: `decoy.scan(df)` and `decoy.mask(config, data=df)` both raise `TypeError` whose `str(exc)` names the class only and holds no marker, and `exc.__cause__ is None and exc.__context__ is None` | `decoy.scan()` profiles it in pandas; `decoy.mask()` raises the Arrow error, whose text quotes the cell | re-raise inside the `except` (chain kept); or put the Arrow text in the message | C2 |
| AT-12 | Choke point unit test with the engine patched: `rows` of 0 and None both give `sample_rows=None, strategy="full"`; a bad strategy and a negative `rows` raise `ScanUsageError` before the engine is called, the allowed strategies equal `[s.value for s in SampleStrategy]`; a sentinel `pre_scan` object reaches `scan_sources` unchanged; `on_stage` runs twice | no choke point | map `rows=0` to `sample_rows=0`; drop `pre_scan=` from the engine call | C1 |
| AT-13 | API input refusals, each a `ValueError` (`ScanUsageError`) raised before the engine is called (engine patched to fail the test): `format="xml"` (text lists `['delimited', 'fixed-width', 'parquet']`); a missing path; a directory; `notes.txt` with no `format` (text names `format=` and the known suffixes); a DataFrame with `has_header`; a layout list with `width: 0` (same text as a layout file with the same column). `decoy.scan("notes.txt", format="delimited", has_header=True)` scans as CSV | today: `ValueError` from `InputFormat`, `FileNotFoundError`, `IsADirectoryError`, `notes.txt` read as CSV, DataFrame options ignored, the list reaches pandas unchecked | treat an unknown suffix as CSV again in `_kind` | C2 |
| AT-14 | CLI usage exits, e2e: `decoy scan f.csv --has-header --rows -1` exits 1 with the `rows must be 0 or more` usage text; `decoy scan notes.txt --has-header` exits 1 naming `--format` and the known suffixes; `decoy scan notes.txt --format delimited --has-header` exits 0 | today exit 3 (engine) and exit 0 (read as CSV) | call `check_scan_options` inside the engine `try`; treat an unknown suffix as CSV | C1 |

Existing tests that change: `tests/unit/test_api.py:403-449` (`test_scan_dataframe_returns_profile`, `test_scan_path_csv`, `test_scan_invalid_strategy_raises`, `test_scan_parity_with_cli_scan`) are replaced by AT-1 to AT-5 and AT-12. `test_scan_profile_keeps_a_rare_label_but_the_saved_document_floors_it` (`tests/unit/test_api.py:414`, row 24zm) reads a `ColumnProfile` from `decoy.scan()`; C2 changes it to call `decoy_engine.profile_columns` directly, which is the function it tests. The test module docstring (`tests/unit/test_api.py:1-16`) is updated. Any existing e2e that scans a file with an unknown suffix and no `--format` gets `--format delimited` in C1 (the builder greps `tests/` for `decoy scan` on such suffixes and lists them in the PR).

## 8. Mutations (gate set)

Run on the exact head of each slice (T2). M1: `sample_rows=None` always (AT-0, AT-1). M2: API default `rows=None` (AT-3). M3: `detail=True` (AT-5). M4: a direct `profile_columns` call in `api.py` (AT-6). M5: drop the temp-path replacement (AT-2). M6: drop the `finally` unlink (AT-10). M7: `has_header` defaults to `True` (AT-4). M8: `rows=0` maps to `sample_rows=0` (AT-12). M9: drop `pre_scan=` in `scan_descriptors` (AT-12). M10: re-raise the Arrow error inside the `except` (AT-11). M11: stage with `source_label` as the name (AT-10). M12: `check_scan_options` moved inside the engine `try` (AT-14). M13: unknown suffix read as CSV (AT-13, AT-14). Each must turn its test red; the gate ledger records the result.

## 9. Placement (against `CODEMAP.md`)

| Path | Change | CODEMAP row | Notes |
|---|---|---|---|
| `src/decoy/cli/scanning/_engine_call.py` | new (about 80 lines): `DEFAULT_SCAN_ROWS`, `ScanRun`, `check_scan_options`, `scan_descriptors`, `core_bytes` | "`decoy scan` internals" (`CODEMAP.md:52`): `src/decoy/cli/scanning/_<noun>.py`, beside `_multi.py` | add it to the row's examples; the row's sentry cell names the new sentry |
| `src/decoy/cli/scanning/__init__.py` | export `scan_descriptors`, `check_scan_options`, `core_bytes`, `ScanRun`, `DEFAULT_SCAN_ROWS`, `resolve_sources`, `API_SPELLING` | same row ("Other packages import these names") | |
| `src/decoy/cli/scanning/_multi.py` | `run_scan` calls `check_scan_options` before the engine `try` and `scan_descriptors(..., pre_scan=pre_scan)` inside `detector_log`, keeping the preflight; `ScanUsageError(ValueError)`; `ScanSpelling`, `CLI_SPELLING`, `API_SPELLING`; `resolve_sources` gains `spelling` and the format, missing-path, directory and unknown-suffix refusals; `_layout_columns(layout: Path \| list[dict] \| None, spelling)` checks a list with `_check_layout_columns`; `_split_names` takes a string or a sequence | same row | 605 lines today; ends near 640, under the 800 cap |
| `src/decoy/cli/scan.py` | C1: the `--rows` default reads `DEFAULT_SCAN_ROWS`. C2: the column loop of `_parse_layout` becomes `_check_layout_columns`; delete `_infer_format` (`scan.py:207-218`) and the loaders (`scan.py:295-377`); docstring line 26 names `scan_sources` | "Command module" (`CODEMAP.md:49`) | lower the ceiling in `tests/sentry/baselines/module-size.json:17` |
| `src/decoy/api.py` | `scan` rewritten (about 55 lines, was 80); `_to_pa_table` and `_arrow_schema` raise a class-only `TypeError` after the handler; module docstring lines 1-21; imports at `api.py:53-59` | "Python API" (`CODEMAP.md:59`) | `_stage_source_entry` reused unchanged, called with the fixed name `scan` |
| `src/decoy/__init__.py` | docstring lines 7-11 | "Python API" | |
| `src/decoy/cli/demo.py` | `:153-164` calls the choke point and `core_bytes` | "Command module" | |
| `tests/sentry/scan/__init__.py`, `tests/sentry/scan/test_one_scan_call.py` | new (about 120 lines) | "Sentry test" (`CODEMAP.md:71`): add "`decoy scan` choke points in `tests/sentry/scan/`", as for `tests/sentry/run/` | `tests/sentry/io_policy/` is at its fan-out cap; the walk reuses `tests/sentry/io_policy/_calls.py` |
| `tests/sentry/baselines/scan-call-allow.json` | new: `cli/init.py::init` (C1 and C2), `api.py::scan` (C1 only) | "Sentry test" | a row in `scripts/dev/sentry_registry.toml` (`kind = "json"`) |
| `tests/sentry/baselines/csv-read-allow.json` | C2: remove the two `cli/scan.py` entries (lines 9-16) | io_policy | shrink only |
| `tests/sentry/io_policy/test_declared_read_choke_point.py` | C2: remove the `("cli/scan.py", "_load_parquet_with_sampling")` entry from `CALLER_NAMED` (`:100-103`) | io_policy | the function is deleted in the same commit |
| `tests/unit/scanning/__init__.py`, `tests/unit/scanning/test_engine_call.py` | new (AT-12) | "`decoy scan` internals" tests `tests/unit/` | a package, so the flat `tests/unit/` does not grow |
| `tests/e2e/test_scan_one_call.py` | new (AT-0, AT-9, AT-14) | "`decoy scan` internals" tests `tests/e2e/` | |
| `tests/unit/api_scan/__init__.py`, `tests/unit/api_scan/test_parity.py`, `tests/unit/api_scan/test_inputs.py` | new (AT-1 to AT-5, AT-7, AT-10, AT-11, AT-13) | "Python API" tests: add `tests/unit/api_scan/` beside `tests/unit/test_api.py` | the matrix would push `test_api.py` past its size cap |
| `tests/unit/release/test_api_signatures.py` | AT-8 | Python API | |
| `docs/release/frozen-surfaces.md:22` | the row says `scan` returns the `scan-set/v1` core | "Release runbooks, logs and maps" (`CODEMAP.md:76`) | |
| `CHANGELOG.md`, `docs/roadmap/groups/health.md`, `docs/RECENTLY-SHIPPED.md` | entries (C1 and C2) | docs | |

## 10. Design notes

- Principle: one source for a fact that two surfaces show. The concrete pain: D1 to D13 exist because the API reimplemented read and sample steps the engine and `resolve_sources` already own.
- Pattern: a choke point plus a walk-based sentry with a ratchet baseline, as in `tests/sentry/run/test_one_result_builder.py` and `tests/sentry/io_policy/outbound/`. The sentry resolves names through the shared `_calls.py` walker, never a grep.
- Where each fact lives: the default rows, the `rows=0` rule and the rows and strategy checks in `_engine_call.py` (strategy values from `SampleStrategy`); the format, suffix, path, header, TSV, layout and table-name rules in `_multi.py::resolve_sources` (format names from `_FORMAT_FLAG`, layout rules from `_check_layout_columns`); the saved-file serializer in `_engine_call.py::core_bytes`; DataFrame staging and the Arrow error in `api.py`. None is restated.
- Error spelling is a parameter, not a second message set: one template per rule, so the CLI and API texts cannot drift apart.
- Deletion test: `scan_descriptors` is more than a forwarding wrapper. It owns the rows and strategy rules that today sit in `run_scan` and are missing from the API, and it is the one site the sentry allows. `ScanRun` exists because the CLI needs both the in-memory result (for `k_anonymity` and `sample_strategy`) and the core; the API uses only the core.
- The choke point sits in `cli/scanning/`, not in a new `src/decoy/_scan.py`, because its other half (`resolve_sources`, `ScanUsageError`) is there and `api.py` already imports from `decoy.cli.*`.

## 11. (Removed in revision 2)

PR #340 merged on `1120e39a`; the overlap section is no longer needed. Its labels are part of the base that AT-0 compares against.

## 12. Compatibility impact

C1: `decoy scan` output bytes do not change (AT-0, AT-9). Two usage changes, one `CHANGELOG.md` entry under `[Unreleased]`, `### Changed`:

- **`decoy scan` refuses a negative `--rows` and an unknown file suffix as usage errors (exit 1).** A negative `--rows` was refused by the engine with exit 3. A file whose suffix is not `.csv`, `.tsv`, Parquet or fixed width was read as CSV; it now needs `--format`.

C2: `decoy.scan()` changes. One `CHANGELOG.md` entry under `[Unreleased]`, `### Changed`:

- **Breaking: `decoy.scan()` returns the `decoy scan --output` document and follows the CLI's input rules (FREEZE-SURFACE item 3, audit J2).** It now calls the same function as `decoy scan` and returns the value-free `scan-set/v1` core as a dict, not the engine's `ColumnProfile`; it has no top values, modes, minimum or maximum. It runs the regex detectors only. A CSV path needs `has_header=True` or `has_header=False` (with `column_names`). A `.tsv` file is read tab-delimited. A file with an unknown suffix needs `format`. The default is the first 10,000 rows; `rows=None` or `rows=0` reads every row. A Parquet source with a repeated column name is refused. Table names follow `decoy scan` (`source_label` overrides; a DataFrame is `dataframe`, with source path `<dataframe>`). Usage errors are `ValueError`s that name the keyword arguments; scan errors are the engine's class-only errors. `format`, `layout`, `has_header` and `column_names` with a DataFrame now raise `ValueError`. A DataFrame is staged to an owner-only temp Parquet file for the scan and removed afterwards. For the value-bearing profile, call `decoy_engine.profile_columns`.
- **`decoy.mask()` and `decoy.scan()` report a DataFrame that Arrow cannot convert as `TypeError` naming the error class only.** The Arrow message, which can quote a cell, is no longer raised or chained.

If the freeze plan's X1 has merged by then, the `decoy.scan()` entry also starts with "Experimental:", per contract section 3.6 rule 2. Consumers inventoried: `tests/unit/test_api.py`, `tests/unit/release/test_api_signatures.py`, `docs/release/frozen-surfaces.md:22`, `docs/roadmap/groups/scan.md` (row 24zm text), `docs/RECENTLY-SHIPPED.md`, and the `decoy.scan()` mentions in `CHANGELOG.md` (history, unchanged). No README, guide or example calls `decoy.scan(` (grep over `README.md` and `docs/` outside records, plans and archive). No platform consumer (platform parked).

## 13. Owner questions (answered 2026-11-20)

| Q | Question | Answer |
|---|---|---|
| Q0 | Is item 3 in 1.0 scope? | Yes, 1.0 (the health row records this). |
| Q1 | What does `decoy.scan()` return? | The value-free `scan-set/v1` document dict, the same bytes as `decoy scan --output`. A breaking Python API change, fine pre-GA. |
| Q2 | Must a CSV path state its header? | Yes, `has_header` is required for CSV. |
| Q3 | Default `rows` | 10,000; `rows=None` or `rows=0` reads every row. A negative `rows` is a usage error on both routes. |
| Q4 | How does a DataFrame reach the engine? | Through a temp Parquet file, as `decoy.mask()` does. |
| Q5 | Table name and `source_label` | `source_label` sets the table name. |
| Q6 | Several inputs in one `decoy.scan()` call | No: one input per call. |

Design calls made by the author under these answers (no owner question): error texts name the caller's own spelling (5.1); unknown suffixes are refused on both routes (5.4 step 1); the API stays regex only (non-goals).

## 14. Slices

| Slice | Repo | Content | Risk | Tests | After | Gate |
|---|---|---|---|---|---|---|
| C1 | CLI | `_engine_call.py` (`scan_descriptors` with `pre_scan`, `check_scan_options`, `core_bytes`, `ScanRun`, `DEFAULT_SCAN_ROWS`); `run_scan` and `decoy demo` call it; `check_scan_options` before the engine `try`; unknown-suffix, bad-format, missing-path and directory refusals in `resolve_sources`; sentry G-ONE-SCAN-CALL with `scan-call-allow` (`cli/init.py::init`, `api.py::scan`); CODEMAP rows; CHANGELOG C1 entry | R2 (two visible usage changes) | AT-0, AT-6, AT-9, AT-12, AT-14; existing scan, scan-models and demo e2e | owner answers (done) | T2 on the exact head plus M1, M4, M8, M9, M12, M13; Dennis then Codex |
| C2 | CLI | `decoy.scan()` ported (5.4); `ScanUsageError(ValueError)`; `ScanSpelling`; layout list through `_layout_columns`; `_to_pa_table` and `_arrow_schema` class-only errors; `scan.py` loaders deleted; `csv-read-allow`, `CALLER_NAMED` and `scan-call-allow` shrink; module-size ceiling lowered; tests replaced; CHANGELOG Breaking entry; frozen-surface map row; health row and RECENTLY-SHIPPED | R2 | AT-1 to AT-5, AT-7, AT-8, AT-10, AT-11, AT-13 | C1 merged | T2 on the exact head plus M1 to M7, M10, M11, M13; full suite before merge (escalation triggers: a frozen public signature and result, and moved or deleted tests); Dennis then Codex |

Two slices because C1 is a refactor with a small usage change and a guard, and C2 is the public break. If the owner prefers one slice, C1 folds into C2.

Size: C1 adds about 100 source lines, removes about 20, and adds about 250 test lines. C2 adds about 90 source lines, removes about 180 (the old API body and the `scan.py` loaders), and adds about 350 test lines. Public names added: none (`decoy.scan` gains two keyword parameters).

## 15. Done when

- C1: AT-0, AT-6, AT-9, AT-12 and AT-14 pass on the merge head; M1, M4, M8, M9, M12 and M13 are recorded red; `scan-call-allow` holds `cli/init.py::init` and `api.py::scan`; the CHANGELOG C1 entry and `CODEMAP.md` rows 52 and 71 are updated.
- C2: AT-1 to AT-5, AT-7, AT-8, AT-10, AT-11 and AT-13 pass on the merge head, with AT-0 and AT-12 still green; M1 to M7, M10, M11 and M13 are recorded red; `scan-call-allow` holds only `cli/init.py::init`; the Breaking entry, `docs/release/frozen-surfaces.md:22`, `CODEMAP.md` row 59, the FREEZE-SURFACE row in `docs/roadmap/groups/health.md` (item 3 merged) and `docs/RECENTLY-SHIPPED.md` are updated.

## 15.1 Plan defect catalog classes

| Class | Defect | Closing structure | Sentry or property test | Seeded mutation | Slice |
|---|---|---|---|---|---|
| 1 | Value exposure (a cell value in the API result, an exception text or an exception chain) | the API returns only the `detail=False` core; it reads no file itself; engine errors are class-only; the Arrow conversion error is raised by class after the handler, with no chain | AT-5, AT-7, AT-11 | `detail=True`; `ValueError(str(exc))`; re-raise inside the `except` | C2 |
| 2 | Cleanup on every exit (the DataFrame's temp Parquet file left behind) | staging and unlink in one `try`/`finally` in `api.scan` | AT-10 | remove the `finally` unlink | C2 |
| 3 | State completeness (every scan producer goes through the choke point; every allowed bypass has a reason) | `scan-call-allow` baseline with a reason per entry, shrink-only | AT-6 | add a site with no allowlist row | C1, C2 |
| 4 | Route coverage (CLI, demo and API take one path; every input kind has a parity cell) | `scan_descriptors` is the only engine caller; the AT-1 matrix has a cell per drift row and per format | AT-1, AT-2, AT-6, AT-9 | the API calls `scan_sources` itself | C1, C2 |
| 5 | Referential integrity | not applicable: the scan passes no relationships (`relationships` stays empty on both routes) | none | none | - |
| 6 | Untrusted input (caller-given paths, formats, layouts, column names and DataFrames) | `resolve_sources` checks apply to both routes before the engine; the engine validates each descriptor | AT-4, AT-7, AT-11, AT-13, AT-14 | default `has_header=True`; unknown suffix read as CSV | C1, C2 |
| 7 | TOCTOU or check-then-use | not applicable beyond today: the engine opens the descriptor path it validated (the new missing-path check is a usage message, not a guard); the temp file is created owner-only by `create_private_temp` before the write | existing private-file sentries | none new | - |
| 8 | Weak proof (a sentry that passes on an empty walk; a parity test that compares a few members; a guard compared to stale recorded bytes) | the sentry self-tests seed each spelling and assert the walk finds `_engine_call.py` itself; parity compares whole documents byte for byte; AT-0 computes its expected bytes in the same run | AT-6 self-tests, AT-0, AT-1 | make the walk return nothing | C1, C2 |
| 9 | Refactor drift (C1 changes `decoy scan` or `decoy demo` bytes, or drops `pre_scan`, while moving the engine call) | C1 moves the call and the rows rule unchanged, inside `detector_log` | AT-0, AT-9, AT-12 | `sample_rows=None` always; `indent=None` in demo; drop `pre_scan=` | C1 |
| 10 | Frozen contract drift (signature pin, frozen-surface map, CHANGELOG and code disagree) | C2 changes the signature pin, the map row at `docs/release/frozen-surfaces.md:22` and the Breaking entry in the same commit as the code | AT-8; the existing frozen-surface map sentry `tests/sentry/release/test_frozen_surface_map.py` | remove `has_header` | C2 |
| 11 | Caller data in a shared location (the temp file name) | fixed staging name `scan` | AT-10 | stage with `source_label` | C2 |

## 15.2 Enumerations

### 15.2.1 Callers

Callers of the engine scan functions under `src/decoy` on `origin/main` `1120e39a`: `src/decoy/cli/scanning/_multi.py:527-540` (`run_scan`: `scan_sources`, `scan_set_to_dict`), `src/decoy/cli/demo.py:153-163` (`scan_sources`, `scan_set_to_dict`), `src/decoy/api.py:694,727` (`scan`: `profile_columns`), `src/decoy/cli/init.py:374-376` (`init`: `profile_columns`). After C2, only `_engine_call.py::scan_descriptors` remains, plus `cli/init.py::init` on the allowlist.

### 15.2.2 Exit paths

`decoy.scan()` after C2:

- Returns the core dict.
- Raises `ValueError`: a `ScanUsageError` from `resolve_sources` or `check_scan_options` (`src/decoy/cli/scanning/_multi.py:60-65`), or a DataFrame with file-only options.
- Raises `TypeError`: a `data` type other than path or DataFrame (as `src/decoy/api.py:722-725` today), or an Arrow conversion failure, class only.
- Raises engine errors unchanged: `ScanSourceError`, the duplicate-name refusal, the file-access errors and `PipelineConfigError` (`E:src/decoy_engine/profiling/scan_set.py:98-104,289-311`).

`decoy scan` exit codes (`src/decoy/cli/scanning/_multi.py:485-561`):

- Exit 2: a Typer usage error (missing path, directory, bad `--format` value), unchanged.
- Exit 1: a `ScanUsageError` or detector usage error, now including a negative `--rows` (was 3) and an unknown suffix (was 0).
- Exit 3: a scan failure.

### 15.2.3 Routes

One route after C2: descriptor, then `scan_descriptors`, then the engine `scan_sources` (`E:src/decoy_engine/profiling/scan_set.py:145-215`, read through `_read_and_profile` at `:314-378`). Its branches:

- Whole read (`full` or no cap), `:327-334`.
- `random`: whole read, then a seeded sample, `:327-334`.
- `head`: `cap + 1` rows, `:335-345`.
- Model detectors (`pre_scan` not `None`): reached only from the CLI; AT-12 checks the forwarding and `tests/e2e/scan_models/test_scan_detectors.py` covers the models.

AT-1 has a cell for each read branch.

### 15.2.4 FK shapes

N/A: both routes call `scan_sources` without `relationships`, so the integrity pass does not run (`E:src/decoy_engine/profiling/scan_set.py:257-273`) and the core's `relationships` list is empty.

### 15.2.5 Fields

The fields of the returned core are the engine's `TableCore` and `FieldCore` members (`E:src/decoy_engine/profiling/_scan_core.py`), listed in 5.5. Inputs and options, each with an AT-1, AT-2, AT-3, AT-12, AT-13 or AT-14 cell:

- Input kinds: CSV path (with header, or headerless with names), TSV path, Parquet path, fixed-width path (layout file or parsed list), a path with an unknown suffix (with or without `format`), a missing path, a directory, a DataFrame.
- `strategy`: `head`, `random`, `full`, invalid.
- `rows`: default, positive, `0`, `None`, negative.
- `format`: valid, invalid, absent.

### 15.2.6 Output surfaces

- `decoy.scan()` return value: changes in C2.
- `decoy scan` card, `--json`, `--output FILE` and `--output -` (`src/decoy/cli/scanning/_multi.py:544-605`): unchanged bytes.
- `decoy demo` `scan.json` (`src/decoy/cli/demo.py:162-164`): unchanged bytes.
- `decoy scan` usage error texts: unchanged except the two new refusals (C1).
- `decoy.mask()` exception text and chain for an Arrow conversion failure: class only, no chain (C2).

## 15.3 Frozen contracts

- `decoy.scan` signature: `tests/unit/release/test_api_signatures.py:26`, changed in C2 (AT-8).
- Frozen-surface map row `docs/release/frozen-surfaces.md:22`: text updated in C2.
- `scan-set/v1` (engine contract 3.1): not changed; the API now returns it as `decoy scan --output` does.
- `decoy scan` `--json` shapes (`tests/fixtures/release_freeze/json-shapes.json`) and `--output` bytes: not changed (AT-0).
- Exit-code integers (`docs/release/frozen-surfaces.md:16`): not changed; C1 moves two `decoy scan` misuse cases between existing codes.

## 16. Pre-mortem

- "The parity test was green, but users still saw different numbers." The AT-1 matrix has a cell for each drift row D3 to D10; a new input option on either route adds a cell.
- "The sentry missed `import decoy_engine.profiling.scan_set as s; s.scan_sources(...)`." The self-tests seed the module alias form; a runtime-bound name (`getattr`) is a named limit, as in the CSV read sentry.
- "Staging a 5 GB DataFrame filled the temp folder." Known limit (F11), the same as `decoy.mask()`; the docstring says to pass a path for large data.
- "`--detectors classifier` ran regex only after C1." AT-12 checks that `pre_scan` reaches the engine; the `scan_models` e2e tests run in the C1 gate.
- "A user's `.txt` export stopped scanning." The refusal names `--format delimited`; the C1 CHANGELOG entry says so.
