Status: plan (revision 2, 2026-11-21; Dennis round 1 GO-WITH-FIXES remediated: E0 split out, one backstop rule, windowed_date dropped)

# COLUMN-SHAPE-RULE: declare a column's type and format only where the engine would otherwise guess

Owner: Cam. Author: Opus (plan author). Date: 2026-11-21. Roadmap row: COLUMN-SHAPE-RULE, to be added to the 1.0 table of `docs/roadmap/groups/mask.md` by slice C0.

Anchors: a path with no prefix is in this repository (decoy CLI); `E:` is decoy-engine. Read at CLI `origin/main` `697ce68a` and engine `origin/main` `4a07e8a2c`.

Rules consulted: dev-rules `README.md`, `00-universal.md`, `development-loop.md` (PLAN contract), `profiles/local-operations.md`, `risk-and-exceptions.md`, `feature-dev.md`, `api-and-compatibility.md`, `cross-cutting-concerns.md`, `architecture.md`, `testing.md`, `reuse-first.md`, `scope-discipline.md`, `proportionality.md`, `security.md` (value-free messages), `documentation.md`, `workspace-and-vcs.md`.

## 1. Frame

### 1.1 Problem

The engine reads a date or a number out of a cell in several different ways today:

- `date_shift` refuses at plan compile when `provider_config.date_format` is missing (`date_shift_requires_date_format`, engine #728). The check is config-only (`E:src/decoy_engine/contracts/strategy_requirements.py`), so it also refuses a Parquet or DuckDB column that is already a native date and has nothing to parse. The only exemption is an F06 declared column (`date_shift_owns_declared_format`).
- `bucket_perturb` detects a format from the cells when `date_format` is missing (`_detect_format`). When detection fails it returns the whole column unchanged with a log line (`E:src/decoy_engine/transforms/bucket_perturb.py:165-170`). A non-null cell that does not parse is kept as it was, with no row error (`:181`). The native path does the same (`E:src/decoy_engine/execution/native/_bucket_perturb_ext.py:7`, `:227`). Both pass source values through. Slice E0 fixes this on its own, first.
- `bucketize` coerces with `pd.to_numeric(errors="coerce")` and `top_code` uses its own exact parser. Both accept CSV text with no declaration.
- `windowed_date` accepts text anchors only in one fixed ISO grammar (`_ISO_ANCHOR`). That grammar is a fixed, documented format, not a guess, so this row leaves `windowed_date` as it is (open question Q9).

Typed sources have a second problem. `date_shift` on a typed column calls `_canonicalize_source` on the raw value. A `datetime.date` digests as its ISO text, but a tz-naive `pd.Timestamp` hard-errors at run time (`timezone_naive_datetime`). The typed path writes `shifted.astype(str)`, so a typed date comes out as text.

### 1.2 Owner decisions (quoted)

Owner, 2026-11-21, "go with recommended":

> Column type and format declarations are optional by default and required only where the engine would otherwise guess:
> - Typed sources (Parquet, DuckDB, database, Arrow) with a native date or number column: type and format come from the source schema; no declaration needed. A declaration is an explicit override and a mismatch is refused.
> - Untyped input (CSV, or a string column holding dates or numbers) used by a strategy that interprets the value (date: `date_shift`, `windowed_date`, `bucket_perturb` on dates; numeric: `bucketize`, `top_code`, `bucket_perturb` numeric; `fpe` where it depends on charset/shape): the type plus its format is required, refused at plan compile with a coded reason if missing.
> - Value-opaque strategies (`hash`, `redact`, `tokenize`, faker replacement, `shuffle`, `categorical`): never need a declaration.
> - Never guess at run time. Detection happens only in `decoy scan` and the starter config, which write the detected format for the user to confirm (`.decoy` uses the `?` review marker so `decoy run` refuses until cleared).
> - One rule in one place: extend `src/decoy_engine/contracts/strategy_requirements.py` (today config-only) so a requirement can depend on the resolved source column type; the check runs at plan compile against the source schema. No per-strategy copies.
>
> Concrete changes: (1) `date_shift` stops requiring `date_format` on native date columns; (2) `bucket_perturb` stops auto-detecting a date format from cells and requires it on text dates (adds a refusal: freeze item, must land before 1.0); (3) the numeric strategies follow the same rule.

Owner, 2026-11-21, on the language:

> Since decoy language is primary pipeline writer now, we can express more details in code far easier than devs writing YAML, so we should watch for ways to abstract details or explicitly inform the engine now that we have this format to compile down to a plan.

Two facts from the code change how the decision reads:

- The engine has no numeric `bucket_perturb`. `VALID_BUCKETS` is week, month and quarter, and the module docstring calls it a datetime strategy. This plan treats `bucket_perturb` as a date strategy only (open question Q1).
- The engine already has one declared-type system: F06 (`logical_type` plus `parse_format`, `E:src/decoy_engine/contracts/declared_casting.py`). It parses text into a typed value at the boundary on every route (`pre_mask_cast` is in every route's capability set in `E:src/decoy_engine/declared_casting/_eligibility.py`). This plan uses F06 as the numeric declaration instead of adding a second parser.

### 1.3 The guarantee

After this row, for every column whose strategy reads the value:

1. The plan compiler knows the column's shape (text, date, timestamp, integer, float, decimal, boolean, other, unknown) from one resolver that reads the source format and the Arrow schema.
2. On a text column, the strategy runs only with an explicit declaration. A missing declaration is a coded refusal at plan compile. When the source format alone proves the column is text (CSV, fixed width), the refusal comes before any data row is read.
3. On a typed column, no declaration is needed. A declaration of the wrong kind is a coded refusal.
4. No strategy detects a format from cells at run time. No strategy returns a source value unchanged because it could not parse it.
5. The rule is one table in `contracts/strategy_requirements.py`, read by the plan check, the handler backstops, the strategy catalog, the starter config and the language. Strategies with a rule: `date_shift`, `bucket_perturb`, `bucketize`, `top_code`, `fpe`.

Non-goals: date spans in free text under `text_mask` and `text_redact` (detection inside free text is not a column shape, so their `_detect_format` stays); `windowed_date` (keeps its fixed ISO anchor grammar); generate tables (generators make typed values); `truncate`, `geo_generalize`, `code_set`; typed CSV reading (the CSV reader stays all-text); a canonical digest for tz-naive timestamps; the F06 output formatter. `nested` children are in scope: they resolve to `text`, so a `bucket_perturb` or `date_shift` child needs `date_format`, and the shape check walks them the way `E:src/decoy_engine/plan/_checks_bucket_perturb.py:71` walks `nested` entries today.

## 2. Established solutions

Search run 2026-11-21 (web, plus engine and CLI code).

- Frictionless Table Schema: each field has a `type` and an optional `format`. A `date` takes `default` (ISO), a strptime pattern, or `any` (guess). A `number` takes `decimalChar` and `groupChar`. Source: https://specs.frictionlessdata.io/table-schema/ . The design follows its pair of type plus format, and drops `any`, which is the guess the owner forbids.
- Apache Spark CSV: `inferSchema` is off by default, and `dateFormat` applies only to columns typed as dates. Inference has had bugs in both directions (SPARK-19228, SPARK-45424). Source: https://spark.apache.org/docs/3.5.6/sql-data-sources-csv.html . This supports "never infer at run time; text stays text unless declared".
- dbt model contracts: with `contract: enforced`, every column needs a `data_type`, and a mismatch with the built model fails the build. Source: https://docs.getdbt.com/reference/resource-configs/contract . This is the "declaration is checked against the real type; a mismatch is refused" half.
- In the engine: F06 already has strict integer and decimal lexers (`integer/ascii/v1`, `decimal/plain/v1`, `decimal/grouped/v1`) and date parse formats, routed through one eligibility decision. `strategy_requirements.py` is already the one table of required settings, read by the plan check, `strategy_catalog` and `starter_config`. `DeclarationRequest.for_run` already reads every source schema from headers and footers before any data row.

Custom code that remains: the shape resolver (a short mapping from source format and Arrow type to a closed enum) and the shape-aware descriptor. No new parser is written.

## 3. Behaviour

### 3.1 Shape resolution

One function, `resolve_column_shape(source_format, arrow_type, declared_logical)`, in a new leaf `E:src/decoy_engine/contracts/column_shape.py`. It uses `is_text` from `E:src/decoy_engine/_arrow_types.py` for the text test and does not repeat it.

One call site. The resolver is called only from `walk_dataframe` in `E:src/decoy_engine/profile/_walk.py`, which already receives `arrow_schema` from `profile/_source.py` (`:226` and `:290`). `walk_dataframe` gains a `source_format` argument. `profile_source` passes the source config's `format` (`csv`, `fixed_width`, `parquet`) for file sources, including the S3 and GCS readers, and the source kind for database, DuckDB and caller tables. The chunked path goes through the same function: `first_chunk_profile` and `walk_one_table` in `E:src/decoy_engine/execution/_chunked_profile.py` pass `first_chunk.schema` and the source format. The resolver table:

| Input | Shape |
|---|---|
| F06 declared column (`logical_type` set) | the declared logical type (`date`, `integer`, `decimal`; `currency` counts as `decimal`, `string` as `text`), because the boundary casts it before the strategy runs |
| `nested` child | `text` |
| Source format `csv` or `fixed_width` (known from the config) | `text`, whatever the reader inferred. The cloud CSV reader infers numbers; this keeps CSV untyped on every reader |
| Arrow `string`, `large_string` | `text` |
| Arrow `date32`, `date64` | `date` |
| Arrow `timestamp` with a time zone | `timestamp_tz` |
| Arrow `timestamp` with no time zone | `timestamp_naive` |
| Arrow signed or unsigned int | `integer` |
| Arrow float | `float` |
| Arrow decimal | `decimal` |
| Arrow bool | `boolean` |
| Any other Arrow type | `other` |
| No schema available (config-only check on a Parquet, database or caller-table source) | `unknown` |

A column made by a `derive` transform takes the Arrow type the transform produced (open question Q6). `unknown` is never treated as typed. The config-only pass defers it. At compile, `unknown` gets the same rule as `text`: a declaration is required.

### 3.2 Behaviour table (source kind by strategy family)

"Text declaration" means:

- date strategies: `provider_config.date_format`. For `date_shift` only, an F06 date declaration also counts (today's exemption).
- numeric strategies: an F06 declaration with `logical_type` `integer` or `decimal`.

| Strategy | `text` (CSV, fixed width, string column, nested child) | `date` | `timestamp_tz` | `timestamp_naive` | `integer`, `float`, `decimal` | `boolean`, `other` |
|---|---|---|---|---|---|---|
| `date_shift` | text declaration required, else `date_shift_requires_date_format` (kept) | runs with no declaration; output keeps the source type | runs; whole-day shift, zone kept | refused `column_shape_mismatch` (today it fails at run time with `timezone_naive_datetime`) | refused `column_shape_mismatch` | refused `column_shape_mismatch` |
| `bucket_perturb` | `date_format` required, else `column_shape_required` (new refusal; today it detects) | runs with no declaration; output keeps the source type | refused `column_shape_mismatch` (Q5) | refused `column_shape_mismatch` | refused `column_shape_mismatch` | refused `column_shape_mismatch` |
| `windowed_date` | unchanged: no shape rule in this row; text anchors use the fixed ISO grammar; typed anchors as today | unchanged | unchanged | unchanged | unchanged | unchanged |
| `bucketize` | F06 `integer` or `decimal` declaration required, else `column_shape_required` | refused `column_shape_mismatch` | refused | refused | runs with no declaration (as today) | refused `column_shape_mismatch` |
| `top_code` | same as `bucketize` | refused | refused | refused | runs with no declaration | refused |
| `fpe` | runs. The charset (default `digits`) is the shape; a value outside the charset is refused per row (as today) | refused `column_shape_mismatch` | refused | refused | `integer` runs (base-10 text, as today); `float` and `decimal` refused `column_shape_mismatch` (Q4) | refused |
| `hash`, `redact`, `tokenize`, `faker`, `shuffle`, `categorical`, `passthrough` and every other strategy | no declaration, no check | same | same | same | same | same |

A declaration on a typed column:

| Declaration | On a typed column of the same kind | On a typed column of another kind |
|---|---|---|
| `date_format` on a `date` column | accepted and not used; value-free plan warning `column_shape_format_unused`; output keeps the source type | refused `column_shape_mismatch` |
| F06 declaration on any non-string column | refused by F06 as today (`declared_cast_input_type_incompatible`): F06 parses text only | same |

This is how the plan reads "a declaration is an explicit override and a mismatch is refused": on a typed column the declaration is checked, and it is never used to parse the value again (open question Q2).

### 3.3 Outputs on typed columns

- `date_shift` and `bucket_perturb` on a `date` column write a date of the same Arrow type (`date32` stays `date32`). On `timestamp_tz`, `date_shift` keeps the unit, the zone and the time of day.
- The digest input of a typed date is `_canonicalize_source(date)`, which is its ISO text. So a Parquet date and the CSV text `2024-01-15` in the same namespace get the same offset. The builder must make sure the handler passes `datetime.date` values (or the calendar date) to the digest, never a tz-naive `Timestamp`.
- `preserve_values` on a typed date column needs no `date_format`. The sentinel stays a typed date (`date_preserve._is_typed_date` exists).

### 3.4 `windowed_date` anchors

No change in this row. Text anchors keep the fixed `_ISO_ANCHOR` grammar (`E:src/decoy_engine/transforms/windowed_date.py:77`) with no declaration. A required `anchor_format` with one allowed value would be ceremony. A later optional `anchor_format` (default `iso8601`, strftime values allowed) is additive and is listed in section 9.4.

### 3.5 When the check runs

- Config-only (`run_config_only_checks` at `E:src/decoy_engine/plan/_compile.py:565`, and the early call in `build_run_context`): shapes come from the config alone (CSV, fixed width, nested, F06). `unknown` columns are deferred, not refused. So `decoy validate` on a CSV pipeline still refuses a missing `date_format` before any read. On a Parquet pipeline the refusal moves from `decoy validate` to compile. This move lands in E1a and is in E1a's compatibility note.
- Plan compile (`compile_plan`, `_compile.py:254`): shapes come from the profile, which carries the resolved shape per column. Every compile site gets it, including the chunked first-chunk profile. `empty_input_profile` (`E:src/decoy_engine/execution/_chunked_profile.py:120`) builds object placeholders from config names, so it cannot give a shape. E1a changes it to take shapes from the source's footer or header schema, which `DeclarationRequest.for_run` has already read. When no schema exists (a caller table with zero rows), the shape is `unknown` and the declaration rule for `text` applies. A zero-row typed source therefore behaves the same as a non-empty one.
- The plan records the shape of each column under a shape-reading strategy (`Plan.column_shapes`).
- The one backstop rule: a handler skips the declaration only when the plan lists the column as typed (`date`, `timestamp_tz`, or a number shape). In every other case (`text`, `unknown`, a column the plan does not list, a `--no-profile` run, a caller that skipped compile) the handler refuses when the declaration is missing. Handlers never look at the pandas dtype: a Parquet date and a CSV string both arrive as `object`. `declared_date_shift_columns(plan)` becomes `typed_date_columns(plan)`: F06 dates plus native dates.

## 4. Failure modes and reason codes

All new codes are registered with `since` unreleased. Messages name the table, column, strategy and config field. They never hold a cell value or a config value.

| # | Failure | Code | Where | Message (fixed text, by family) |
|---|---|---|---|---|
| F1 | `date_shift` on text with no date declaration | `plan/date_shift_requires_date_format` (kept) | compile; runtime twin kept | "date_shift needs provider_config.date_format, the strftime format of its dates." |
| F2 | date or numeric strategy on text or `unknown` with no declaration | `plan/column_shape_required` (new) | compile | date: "`<strategy>` reads dates from text; set provider_config.date_format." numeric: "`<strategy>` reads numbers from text; declare logical_type integer or decimal with a parse_format." |
| F3 | The strategy family or declaration kind does not match a typed source column | `plan/column_shape_mismatch` (new) | compile | "column `<c>` in table `<t>` is a `<shape>` column; `<strategy>` cannot read it." Plus one hint per cell of 3.2. For `timestamp_naive`: "cast it to a date or a zoned timestamp, or write it as text with a date_format." |
| F4 | `bucket_perturb` gets no usable format: in E0, no `date_format` and detection found none; from E2, no `date_format` on a column the plan does not list as typed | `runtime/bucket_perturb_requires_date_format` (new) | handler and transform, both backends | "bucket_perturb needs provider_config.date_format, the strftime format of its dates." |
| F5 | `date_format` on a typed date column | `plan/column_shape_format_unused` (new, warning) | compile warning | "date_format is not used: the source column is already a date." |
| F6 | A handler receives a column the plan does not list as typed, with no declaration | `runtime/column_shape_required` (new) | `bucketize`, `top_code` backstops (E3); `bucket_perturb` uses F4 | same text as F2 |
| F7 | A non-null `bucket_perturb` cell does not parse under `date_format` | existing `RowError`, trigger `format_error` | handler, both backends | "value is not a parseable date under bucket_perturb" (as `date_shift`) |
| F8 | The resolver meets an Arrow type it does not list | shape `other`, never a crash | resolver | none |

Removed in E0: the `bucket_perturb` path "could not detect date format; column values passed through unchanged", and the per-cell keep of unparseable values. Removed in E2: every use of `_detect_format` by `bucket_perturb`.

## 5. Design notes

- One place per fact. The shape vocabulary and the resolver are in `contracts/column_shape.py`. The per-strategy rule (family, subject path, declaration fields, code) is in `contracts/strategy_requirements.py` as a new frozen descriptor `ShapeRequirement` in a second table, `SHAPE_REQUIREMENTS_BY_STRATEGY`. Descriptors are data only, with no callable predicate, so a refusal cannot echo config data (the module's existing rule).
- Typed context over flags. The check takes a `ColumnShapes` mapping `(table, column) -> ColumnShape`, built once from the profile (or from the config for the config-only pass). No strategy function gets a `typed: bool` flag. `preserve_config_problem` takes the resolved shape.
- Handlers do not learn about shapes. They read the plan's `typed_date_columns` set, which is the existing seam made wider.
- Extend the existing check; do not add a sibling. `check_required_strategy_settings(config, shapes=None)` walks both tables. `_compile.py` (670 lines, ceiling 700) changes by one argument and one plan field.
- Principles applied: one source of truth (the requirement table), open for new strategies without edits elsewhere (a strategy adds one descriptor row), fail closed on an unknown shape at run time.
- Rejected alternative: a per-strategy `number_format` option with its own parser. It would be a second numeric parser beside F06 and a per-strategy copy of the rule.

## 6. Choke point and sentries

| Concern | Choke point | Guard test | Mutation that must turn it red |
|---|---|---|---|
| No run-time format detection (main sentry) | import rule: `transforms.date_shift._detect_format` is imported only by `transforms/text_mask.py` and `transforms/text_redact.py` (allowlist) | `E:tests/sentry/test_no_runtime_format_detection.py` (new), import-graph walk of `src/decoy_engine/` including `execution/native/` | import `_detect_format` in `transforms/bucket_perturb.py` |
| Date parsing reads the declared format | `shape_declaration(plan, ...)` | same sentry, AST case: in `execution/_strategies/`, `transforms/` and `execution/native/`, every `pd.to_datetime(` call under a strategy in `SHAPE_REQUIREMENTS_BY_STRATEGY` passes `format=` from that helper or from the transform's required `date_format` parameter. `pd.to_numeric` has no format argument, so numeric strategies are covered by the F06 boundary and the E3 refusal tests, not by this case. `text_mask` and `text_redact` are allowlisted | add `fmt = cfg.get("date_format") or _detect_format(series)` back to `bucket_perturb` |
| No value pass-through on a parse failure | the `bucket_perturb` row-error channel | `E:tests/unit/strategies/test_bucket_perturb_safety.py::test_unparseable_cell_is_row_error` (E0) | restore `continue  # preserve null / unparseable values` for non-null cells |
| One resolver | `resolve_column_shape`, called only from `profile/_walk.py` | `E:tests/sentry/test_column_shape_resolver_single.py` (new): `resolve_column_shape` has one caller, and within `plan/` and `profile/` the `pa.types.is_date` and `is_timestamp` predicates are used for shape only in `contracts/column_shape.py` | add an `is_date32` branch in `plan/checks/_required_settings.py` |
| Catalog and starter agree with the table | `strategy_catalog()` `StrategyInfo.shape` | `E:tests/unit/test_strategy_catalog.py::test_shape_matches_requirement_table` | drop `top_code` from the table |

### 6.1 Class table

These rows use the defect classes of the plan contract.

| # | Class | Applies here | Structure that closes it | Test | Mutation that turns it red |
|---|---|---|---|---|---|
| 1 | Value-bearing output | the new refusal and warning messages; row errors from `bucket_perturb` | messages are fixed text plus table, column, strategy and field names; row errors use the existing value-free `RowError` | `::test_messages_value_free` in E1b, E2, E3, E4 (marker values in fixtures) | put the bad cell into the F7 message |
| 2 | Cleanup missing on an exit path | a compile refusal after a partial read | refusals happen at plan compile, before any output is opened; no new write path | existing run-refusal tests extended by `test_codes_reach_cli_with_exit_1` (C1) | none new: no write path is added |
| 3 | Stale state | a shape recorded in the plan that no longer matches the source at run time | `Plan.column_shapes` is part of `plan_hash`; the run reads the same profile the plan was built from; the one backstop rule refuses any column the plan does not list as typed when its declaration is missing | `::test_handler_backstop_keys_on_plan` (E1b), `::test_handler_refuses_unlisted_column` (E2) | make the backstop skip the check on an `object` dtype |
| 4 | Route parity | full frame, sequential, chunked, native and mixed routes | one check at compile; handlers read one plan field; the native `bucket_perturb` path keeps parity with pandas | `::test_parquet_date32_runs_without_format` over three routes; `::test_unparseable_cell_is_row_error` on both backends; `::test_csv_top_code_with_integer_declaration_runs_on_every_route` | drop the row-error branch in the native ext only |
| 5 | Referential integrity | `date_shift` on a key column shared by a CSV table and a Parquet table | the digest input of a typed date is its ISO text, the same bytes as the text form, so one namespace gives one offset | `::test_typed_offset_equals_iso_text_offset` | digest `str(pd.Timestamp(v))` for typed dates |
| 6 | Untrusted producer | a source schema from a file footer; a `.decoy` `as` clause | the resolver maps every Arrow type to a closed enum (unknown types become `other`); the language checks the shape name and family before lowering | `::test_unlisted_arrow_type_is_other`, `test_shapes.py` error tests | map an unlisted type to `date` |
| 7 | Check then use (TOCTOU) | the schema read at compile, then the data read at run | the schema read and the data read are the same files the declaration gate already pins (`prepare_declared_sources`); a changed type between them meets the handler backstop and fails closed | `::test_handler_backstop_keys_on_plan` | remove the backstop |
| 8 | Weak tests and overclaimed evidence | every acceptance test in section 10 | each slice names its mutation; tests assert output types and bytes, not only the absence of an error | reviewer reruns the named mutations on the final head | removing a named mutation from the evidence is a gate finding |
| 9 | Behavior-preserving refactor drift | E1a moves the `date_shift` rule into the new descriptor and renames `declared_date_columns` | E1a keeps today's rule for every shape; the existing #728 tests run unchanged | `::test_date_shift_rule_unchanged_on_every_shape`; the existing `date_shift_requires_date_format` tests | make the E1a descriptor skip `date` shapes |
| 10 | Frozen contract drift | reason registry, `StrategyRequirement`, `StrategyInfo`, `strategy_catalog`, plan format | codes are append-only; `StrategyRequirement` keeps its fields; `StrategyInfo.shape` is additive with a default; `plan_hash` move is recorded in the compatibility contract | `tests/sentry/test_reason_baseline_frozen.py`, `tests/sentry/release/test_public_census.py` | rename `date_shift_requires_date_format` |

## 6.2 Enumerations

### Fields

| Set | Members | Owner |
|---|---|---|
| `ColumnShape` | `text`, `date`, `timestamp_tz`, `timestamp_naive`, `integer`, `float`, `decimal`, `boolean`, `other`, `unknown` | `contracts/column_shape.py` (new) |
| `TEXT_SOURCE_FORMATS` | `csv`, `fixed_width` | `contracts/column_shape.py`, checked against `FILE_FORMATS` in `E:src/decoy_engine/profile/_lazy_build.py` by the resolver test |
| Config fields read | `provider_config.date_format`, F06 `logical_type` and `parse_format` | `SHAPE_REQUIREMENTS_BY_STRATEGY` beside `REQUIREMENTS_BY_STRATEGY` at `E:src/decoy_engine/contracts/strategy_requirements.py:60` |
| Profile field added | `ColumnProfile.shape`, beside `avg_length` at `E:src/decoy_engine/profile/_types.py:103` (both out of `profile_hash`) | `profile/_types.py` |
| Strategies with a shape rule | `date_shift`, `bucket_perturb`, `bucketize`, `top_code`, `fpe` | `SHAPE_REQUIREMENTS_BY_STRATEGY` |
| Language shapes | `date(fmt)`, `integer`, `decimal(precision, scale)` | `src/decoy/lang/_shapes.py`; YAML targets come from `StrategyInfo.shape` |
| New reason codes | the five in section 4 | `reasons/plan/_part3.py`, `reasons/runtime/_part3.py` |

### Routes

Every route reads the shape from the plan; none resolves it again.

| Route | Where the shape check runs | Evidence |
|---|---|---|
| Config-only (`decoy validate`, early `build_run_context`) | `check_required_strategy_settings(config, shapes=config_shapes)` | today's config-only call |
| Compile in a run | both calls in `compile_plan`, `E:src/decoy_engine/plan/_compile.py:254` and `:565` | the profile comes from `build_routing_facts`, `E:src/decoy_engine/execution/pipeline/_routing_facts.py:74` (`DeclarationRequest.for_run`) then `:97` (`compile_plan`) |
| Full frame, sequential, chunked, mixed, out of core | the one backstop rule on `typed_date_columns`, today `declared_date_columns` at `E:src/decoy_engine/execution/_strategies/_date_shift.py:102` | F06 `pre_mask_cast` is in every route's set, `E:src/decoy_engine/declared_casting/_eligibility.py:43` and `:52` |
| Native `bucket_perturb` and `date_shift` | admits explicit formats only today; E2 adds row-error parity | native parity tests |

### Exit paths

| Path | Outcome |
|---|---|
| Compile refusal (F1 to F4) | `PlanValidationError` with the code; CLI config-refusal exit; no output opened |
| Compile warning (F5) | plan warning; run continues |
| Handler backstop (F4, F6) | runtime refusal with the code; the run stops before writing that table |
| Row error (F7) | existing row-error accounting; never a pass-through. Today the whole-column pass-through is at `E:src/decoy_engine/transforms/bucket_perturb.py:165-170` and the per-cell keep at `:181`; native at `E:src/decoy_engine/execution/native/_bucket_perturb_ext.py:7` and `:227` |
| F06 cast failure on a declared numeric column | F06 `error_policy` (default fail) |

### FK shapes

A `date_shift` column used as a key across tables keeps one offset per value only when every table gives the digest the same bytes.

- CSV text and Parquet `date32` in one namespace: same ISO bytes, same offset (`::test_typed_offset_equals_iso_text_offset`).
- Two Parquet tables with `date32` keys: same type, same bytes.
- A `timestamp_tz` key: UTC ISO bytes, as today.
- A `timestamp_naive` key: refused at compile (F3).
- Numeric strategies as keys: not join-safe today, and unchanged.

### Output surfaces

| Surface | Change |
|---|---|
| Masked data, typed date columns | keeps the Arrow type; today text from `shifted.astype(str)` at `E:src/decoy_engine/execution/_strategies/_date_shift.py:340` |
| Masked data, `bucket_perturb` text | unchanged for valid configs; unparseable cells become row errors |
| Plan JSON | adds `column_shapes` |
| Refusal and warning messages | fixed text plus names (class 1) |
| Starter YAML and `.decoy` init output | `date_format` or `as date(...)` for text only |
| `strategy_catalog()` | `StrategyInfo.shape` |

## 6.3 Reuse inventory

| Need | Reused | Not built |
|---|---|---|
| Parse integers and decimals from text | F06 lexers `integer/ascii/v1`, `decimal/plain/v1`, `decimal/grouped/v1` | a `number_format` option |
| Read the source schema before data | `DeclarationRequest.for_run` and the profile built in `build_routing_facts` | a second schema reader |
| One table of strategy requirements | `contracts/strategy_requirements.py` and its readers | a per-strategy check |
| Typed dates in sentinels | `date_preserve._is_typed_date` | new sentinel code |
| Row errors | the existing `RowError` channel and `format_error` trigger | a new error type |
| Review gate on detected formats | the `.decoy` `?` mark and `lang.unreviewed` (DECOY-LANG) | a new confirm step |
| Shape mapping from Arrow | `pyarrow.types` predicates | a hand-written type parser |

## 6.4 Frozen contracts

Touched frozen or public surfaces, and what stays fixed:

- `plan.checks.StrategyRequirement` (public census): fields unchanged. `ShapeRequirement` is a new name and is listed as documented internal until 1.0.
- `strategy_catalog()` and `StrategyInfo`: one additive field, `shape`, with a default of `None` for value-opaque strategies.
- Reason registry: append-only. `date_shift_requires_date_format` keeps its code, path and text.
- Plan format: `column_shapes` is added; `plan_hash` moves for configs with shape-reading strategies; `pipeline_config_hash` does not move. Recorded as a pre-GA note.
- `.decoy` syntax: `as` is added before the 1.0 syntax freeze (C2).
- CLI exit codes: unchanged. Every new refusal uses the existing config-refusal exit.

## 6.5 Pre-mortem

Assume the row shipped and failed. The likely causes, and what in the plan stops each:

| Failure | Stopped by |
|---|---|
| A Parquet `date_shift` run gives offsets that differ from the CSV run of the same data, breaking joins | `::test_typed_offset_equals_iso_text_offset`; class 5 |
| Cloud CSV reads infer `int64`, so a CSV `top_code` runs with no declaration on S3 but is refused locally | shape keys on source format first; `::test_csv_is_text_even_when_reader_inferred_int` |
| A new strategy reads dates with its own `pd.to_datetime` and skips the rule | the section 6 sentry over `execution/_strategies/` and `transforms/` |
| `bucket_perturb` users with dirty dates see runs fail after the upgrade | the refusal and row errors are listed freeze items with compatibility notes and docs; the starter writes the format |
| Doc examples break, so new users hit the refusal on the first try | C1 runs every doc snippet through `test_docs.py` |
| `decoy validate` passes a Parquet config that `decoy run` then refuses | documented as a moved refusal; `validate compile` catches it; `::test_config_only_defers_unknown` pins the split |
| `_serialize.py` or `_compile.py` passes the size ceiling | the Placement table names the sibling file and the line budget |

## 7. Placement

| File | Change | Why there | Size after (goal 600, ceiling 700) |
|---|---|---|---|
| `E:src/decoy_engine/contracts/column_shape.py` (new) | `ColumnShape` enum, `TEXT_SOURCE_FORMATS`, `resolve_column_shape`, `ColumnShapes` | CODEMAP "Versioned contracts" row: a leaf contract beside `strategy_requirements.py`; imports `pyarrow`, `_arrow_types` (for `is_text`) and `reasons` only | about 80 |
| `E:src/decoy_engine/contracts/strategy_requirements.py` | `ShapeRequirement`, `SHAPE_REQUIREMENTS_BY_STRATEGY`, `shape_requirement_for`, `shape_problem` | named by the owner; the existing one table of strategy requirements | 124 to about 230 |
| `E:src/decoy_engine/plan/checks/_required_settings.py` | `check_required_strategy_settings(config, shapes=None)` walks the shape table; the `date_format` special case moves into the descriptor | the existing check; no sibling copy | 126 to about 210 |
| `E:src/decoy_engine/profile/_types.py`, `profile/_walk.py`, `profile/_source.py`, `execution/_chunked_profile.py` | `ColumnProfile.shape` (defaulted, excluded from `profile_hash` like `avg_length`); `walk_dataframe` is the one resolver call site and gains `source_format`; `profile_source` passes it; `first_chunk_profile` and `walk_one_table` pass `first_chunk.schema`; `empty_input_profile` takes shapes from the footer or header schema | every compile site already receives the profile | +15, +15, +10, +20 |
| `E:src/decoy_engine/plan/_types.py`, `plan/_serialize.py`, `plan/_compile.py` | `Plan.column_shapes`; serialized; built in compile | handlers key on the plan | +20, +12 (586 to 598; if it would pass 600, a sibling `_serialize_shapes.py` beside `_serialize_declared.py`), +3 |
| `E:src/decoy_engine/declared_casting/_boundary.py` | `declared_date_shift_columns` becomes `typed_date_columns(plan)` | the existing seam the routes call | +10 |
| `E:src/decoy_engine/execution/_adapter.py` | rename `declared_date_columns` to `typed_date_columns` | internal context field | 0 |
| `E:src/decoy_engine/execution/_strategies/_date_shift.py` | typed output keeps the source type; backstop keys on `typed_date_columns` | the handler | 355 to about 380 |
| `E:src/decoy_engine/transforms/date_preserve.py` | `preserve_config_problem(cfg, shape)` | its one rule site | +10 |
| `E:src/decoy_engine/transforms/bucket_perturb.py`, `execution/_strategies/_bucket_perturb.py`, `execution/native/_bucket_perturb_ext.py` | E0: refusal on a `None` format and row errors on both backends. E2: remove detection, make `date_format` a required parameter, typed path | the strategy | 254 to about 250; 141 to about 170; native +15 |
| `E:src/decoy_engine/plan/_checks_declared_casting.py` | `strategy_output_logical`: `top_code` on integer or decimal gives `string`; `bucketize` on decimal gives `string` for `range` and `midpoint` | F06 owns which strategies are proven for a declared column | 266 to about 280 |
| `E:src/decoy_engine/execution/_strategies/_bucketize.py`, `_top_code.py` | backstop through `shape_problem` | the strategies | +10 each |
| `E:src/decoy_engine/profiling/_starter_config.py`, `_starter_inference.py`, `profiling/recommendations.py` | write `date_format` only for a text column; a typed date gets `date_shift` with no format | the one starter | 457 to about 475 |
| `E:src/decoy_engine/execution/_strategies/__init__.py` (catalog) | `StrategyInfo.shape` (family, declaration field) | the public catalog the language reads | +15 |
| `E:src/decoy_engine/reasons/plan/_part3.py`, `reasons/runtime/_part3.py` | the new codes | the registry | +12 |
| `src/decoy/lang/_grammar.py`, `_ast.py`, `_parse.py`, `_print.py`, `_convert.py`, `_codes.py`, new `src/decoy/lang/_shapes.py` | the `as <shape>` clause (section 9). `_lower.py` is 380 lines, so the lowering goes in `_shapes.py` beside `_links.py` and `_subset.py` | the language package | `_shapes.py` about 120; others +10 to +30 |

No directory gains a module past its fan-out limit. The new engine file is in `contracts/` (8 modules). No module is added to `plan/` (frozen at 30).

Consumer pairs (proportionality exception): `ColumnProfile.shape` and `Plan.column_shapes` land in E1a; their behaviour consumers are E1b, E2 and E3, which must merge before the row closes. `StrategyInfo.shape` lands in E5; its consumer is C2.

## 8. Slices

Engine slices first, then CLI. Each merges alone and leaves main green.

| Slice | What | Risk | After | Size (code, tests) |
|---|---|---|---|---|
| E0 | `bucket_perturb` safety fix, on its own: when the format resolves to `None` the transform raises the coded runtime refusal F4 instead of returning the column unchanged; a non-null cell that does not parse becomes a `RowError` (F7) instead of keeping its value. Both backends (pandas transform and native ext). Detection itself stays until E2 | R2 (safety, output change) | none | about 40, 150 |
| E1a | Shape vocabulary, resolver, `ColumnProfile.shape`, `Plan.column_shapes`, `ShapeRequirement` table, `check_required_strategy_settings(config, shapes)`, sentries. The table holds only `date_shift` with today's rule (every shape requires `date_format`), so no behaviour moves. Only `plan_hash` moves, for configs with `date_shift` | R2 (plan format) | DATE-SHIFT-FORMAT release 0.28.2 | about 350, 350 |
| E1b | `date_shift` on typed dates: no declaration, typed output, `timestamp_naive` refused at compile, `date_format` unused warning, `preserve_values` on typed columns, backstop on `typed_date_columns` | R2 | E1a | about 200, 300 |
| E2 | `bucket_perturb`: `date_format` required on text at compile, detection removed, `date_format` becomes a required parameter of `apply_bucket_perturb`, typed date path for plan-listed columns | R2 (refusal) | E0, E1a | about 150, 300 |
| E3 | `bucketize` and `top_code` on text need an F06 numeric declaration; typed mismatch; F06 proof widened for `top_code` and decimal `bucketize`; `fpe` typed rule | R2 | E1a | about 150, 300 |
| E5 | Starter and scan: shape on `FieldStats`, starter writes formats only for text, `StrategyInfo.shape`, engine docs (`strategies.md`, `compatibility-contract.md`, CHANGELOG, CODEMAP), engine release | R1 | E1b, E2, E3 | about 120, 200 |
| C0 | Roadmap row, link to this plan | R1 | none | docs |
| C1 | Repin to the release with E0 to E5; CLI docs and templates (section 11); error table | R1 | E5 | about 40, docs |
| C2 | Language `as <shape>` clause: grammar, lowering through `StrategyInfo.shape`, printer and converter round trip, codes, guide pages | R2 (language syntax is frozen at 1.0) | C1; DECOY-LANG S1 | about 250, 300 |
| C3 | `decoy init` and scan output: `.decoy` rules carry `as date("...")` for text sources and no `as` for typed ones, under the `?` mark; YAML init writes `date_format` only for text | R1 | C2; DECOY-LANG S6 | about 40, 150 |

E0 has no dependency and should merge first; it can ship in the 0.28.x train. E2 and E3 do not depend on each other and can run in parallel after E1a. The former E4 (`windowed_date` `anchor_format`) is dropped (Q9).

## 9. The language side

### 9.1 What the user writes today

`date_format` is a plain option: `dob : date_shift(min_days: -30, max_days: 30, date_format: "%m/%d/%Y") in dates`. F06 fields are column fields, so `logical_type` and `parse_format` can also be written as options. But `parse_format: {id: "integer/ascii/v1"}` is noise for a CSV age column.

### 9.2 The smallest addition: `as <shape>` on a rule

```decoy-mask
dob, admitted as date("%m/%d/%Y") : date_shift(min_days: -30, max_days: 30) in dates
age as integer                    : top_code(upper: 89)
income as decimal(precision: 12, scale: 2) : bucketize(width: 10000)
```

Grammar: `mask: names [shape] ":" treatment [REVIEW_MARK]` with `shape: AS call`. `as` becomes a contextual keyword: it is a keyword only in the position after the names, so a column named `as` still works unquoted (C2 tests this). The shape describes the column (the data), so it is on the column side of `:`, apart from the treatment. A `let` treatment stays free of shapes, so one `let` serves a CSV table and a Parquet table. A `group` gets no shape: shapes go on the rule's column names only.

Shapes in V1: `date("<strftime>")`, `integer`, `decimal(precision: p, scale: s)`. Nothing else.

Lowering: the compiler asks the engine catalog (`StrategyInfo.shape`) which field carries the declaration for the rule's strategy. The language keeps no list of its own.

| Shape | Strategy family | YAML it compiles to |
|---|---|---|
| `date("F")` | date (`date_shift`, `bucket_perturb`) | `provider_config.date_format: "F"` |
| `integer` | numeric | `logical_type: integer`, `parse_format: {id: integer/ascii/v1}` |
| `decimal(precision: p, scale: s)` | numeric | `logical_type: decimal`, `parse_format: {id: decimal/plain/v1, precision: p, scale: s}` |

`date(...)` lowers to `date_format`, not to an F06 date, on purpose: `date_format` writes the shifted date back in the same text format, which is what a CSV user expects.

New language codes:

- `lang.shape_unknown`: not one of the three shapes.
- `lang.shape_not_read`: the strategy does not read the value, for example `hash` ("remove `as`; hash does not read the value").
- `lang.shape_wrong_family`: for example `as integer` on `date_shift`.
- The existing `lang.option_repeated` when a rule has both `as date(...)` and a `date_format:` option.

All are compile-time language errors with a span. `lang.shape_unknown` and `lang.option_repeated` are pure language checks. `lang.shape_not_read` and `lang.shape_wrong_family` read `StrategyInfo.shape` from the engine catalog, the same data the lowering uses, so they need the engine package but no data and no plan.

Converter and printer: a column with `date_format` under a date strategy prints as `as date("...")`. An F06 `integer/ascii/v1` with default parameters prints as `as integer`. `decimal/plain/v1` prints as `as decimal(...)`. Every other F06 contract (grouped, currency, COBOL, sentinels, error policy, output format) prints as options, as today. The converter's round-trip proof covers each case.

YAML stays fully explicit. The engine never sees `as`; it sees only the fields in the table.

### 9.3 Scan and starter output

The starter YAML already carries `date_format` for a text date. Through the DECOY-LANG S6 converter path with review marks, that becomes:

```decoy-mask
# REVIEW: The scan detected US-format dates (%m/%d/%Y in every value). ...
dob as date("%m/%d/%Y") : date_shift(min_days: -365, max_days: 365) in dob ?
```

A typed date column gets no `as`: `dob : date_shift(min_days: -365, max_days: 365) in dob ?`. `decoy run` refuses while the `?` is there (DECOY-LANG rule 3), so a detected format never runs unconfirmed.

### 9.4 Later candidates (not in scope)

- Named shapes: `shape us_date = date("%m/%d/%Y")` at pipeline level, then `dob as us_date : ...`.
- A table-level shape block (`columns { dob: date("%m/%d/%Y"), age: integer }`) that also feeds `keep` columns and `windowed_date` anchors.
- Source-level type hints, `csv("a.csv", types: {...})`, that make the reader produce typed Arrow columns (typed CSV reading).
- `as` on `keep` and on link columns, which needs F06 on `passthrough` anchors.
- `as date(iso)` mapped to F06 `date/iso8601/v1`.
- An optional `windowed_date` `anchor_format` (default `iso8601`, strftime values allowed), with `as date(...)` on the anchor column.

## 10. Acceptance tests first

Each slice's tests are written before its code. "Proves" says what a red test would mean. Fixtures use marker values so the value-free checks can search messages for them.

### E1a

| Test | Proves |
|---|---|
| `E:tests/unit/contracts/test_column_shape.py::test_resolver_table` (parametrised over every row of 3.1) | the resolver gives each listed shape |
| `::test_csv_is_text_even_when_reader_inferred_int` (cloud CSV path yields `int64`) | CSV stays untyped on every reader |
| `::test_unlisted_arrow_type_is_other` (`list<int>`, `struct`) | F8: no crash on an unknown type |
| `E:tests/unit/plan/test_required_settings_shapes.py::test_date_shift_rule_unchanged_on_every_shape` | E1a moves no behaviour: every shape still requires `date_format` |
| `::test_config_only_defers_unknown` | the config-only pass on a Parquet source does not refuse; the compile pass does |
| `E:tests/unit/plan/test_plan_column_shapes.py::test_plan_records_shapes_for_reading_strategies_only` | the plan lists shapes for shape-reading strategies and no others |
| `::test_plan_is_deterministic` | the same config and profile give byte-identical plans |
| `E:tests/unit/profile/test_profile_shape.py::test_shape_not_in_profile_hash` | pinned profile hashes do not move |
| `::test_chunked_first_chunk_shape_matches_full_frame` (Parquet `date32`, CSV) | the chunked profile passes `first_chunk.schema` and the source format, so both paths give the same shape |
| `::test_empty_typed_source_takes_footer_shape` (zero-row Parquet with a `date32` column) | a zero-row typed source behaves like a non-empty one; it is not refused as `unknown` |
| `::test_s3_csv_shape_is_text` (cloud reader stub that infers `int64`) | the source format reaches the resolver on the cloud path |
| The sentries of section 6 | the choke points hold |

Mutation: drop `csv` from `TEXT_SOURCE_FORMATS`; `test_csv_is_text_even_when_reader_inferred_int` turns red.

### E1b

| Test | Proves |
|---|---|
| `E:tests/unit/strategies/test_date_shift_typed.py::test_parquet_date32_runs_without_format` (full frame, sequential, chunked) | change (1): native dates need no declaration on every route |
| `::test_output_keeps_date32` and `::test_timestamp_tz_keeps_unit_zone_and_time` | typed in, same type out |
| `::test_typed_offset_equals_iso_text_offset` (same namespace, Parquet `2024-01-15` and CSV `"2024-01-15"`) | the digest input of a typed date is its ISO text |
| `::test_timestamp_naive_refused_at_compile` | F3 replaces the run-time `timezone_naive_datetime` |
| `::test_integer_column_refused` | F3 on a typed number |
| `::test_date_format_on_typed_date_warns_and_is_unused` | F5; output is a date, not formatted text |
| `::test_csv_without_format_still_refused` | F1 is kept for text |
| `::test_preserve_values_on_typed_date_without_format` | sentinels work on typed dates |
| `::test_handler_backstop_keys_on_plan` (a Parquet `date32` column the plan lists as typed runs with no format; the same column with the plan entry removed is refused; a text column with no format is refused) | the one backstop rule: only a plan-listed typed column skips the declaration |
| `::test_messages_value_free` | no marker value in any message |

Mutation: in `_shift_rows`, keep `shifted.astype(str)` for typed columns; `test_output_keeps_date32` turns red.

### E0

| Test | Proves |
|---|---|
| `E:tests/unit/strategies/test_bucket_perturb_safety.py::test_transform_refuses_when_format_resolves_to_none` (calls `apply_bucket_perturb` directly on values detection cannot read) | F4: no whole-column pass-through, at the transform itself, not only behind a handler |
| `::test_handler_refuses_when_format_resolves_to_none` (full frame, sequential, chunked) | the refusal reaches every route with the code |
| `::test_unparseable_cell_is_row_error` (pandas and native backends, same rows) | F7: no source value passes through, on both backends |
| `::test_null_stays_null` | nulls are not row errors |
| `::test_explicit_format_output_unchanged` (pandas and native) | output bytes for today's valid rows do not move |
| `::test_messages_value_free` | no marker value in the refusal or row error |

Mutations: restore `return series.copy()` on `fmt is None` (`bucket_perturb.py:165-170`), and `test_transform_refuses_when_format_resolves_to_none` turns red. Restore the per-cell `continue` at `:181`, and `test_unparseable_cell_is_row_error` (pandas case) turns red. Keep unparseable rows unchanged in `_bucket_perturb_ext.py` (`:227`), and the native case turns red.

### E2

| Test | Proves |
|---|---|
| `E:tests/unit/strategies/test_bucket_perturb_shape.py::test_text_without_format_refused` (config-only and compile) | change (2): the new refusal, before any read for CSV |
| `::test_transform_does_not_detect` (calls `apply_bucket_perturb` directly with no `date_format` on clean ISO values that detection would read) | no run-time detection, at the transform, whatever the handler does |
| `::test_typed_date_runs_without_format_and_keeps_type` | the typed path for a plan-listed column |
| `::test_handler_refuses_unlisted_column` (a Parquet date column with its plan entry removed, no format) | the one backstop rule |
| `::test_native_parity_unchanged_for_explicit_format` | output bytes for today's valid configs do not move |
| the section 6 import sentry | `_detect_format` cannot be reached from `bucket_perturb` |

Mutation: restore `fmt = date_format or _detect_format(series)` in the transform; `test_transform_does_not_detect` and the import sentry turn red. The test calls the transform directly, so the handler backstop cannot hide the mutation.

### E3

| Test | Proves |
|---|---|
| `E:tests/unit/strategies/test_numeric_shape.py::test_csv_top_code_without_declaration_refused` and the `bucketize` twin | change (3) |
| `::test_csv_top_code_with_integer_declaration_runs_on_every_route` | the F06 path admits `top_code` |
| `::test_csv_bucketize_decimal_declaration_range_format` | the widened F06 proof |
| `::test_parquet_int_runs_without_declaration` | typed numbers need nothing |
| `::test_parquet_date_under_bucketize_refused` | F3 |
| `::test_fpe_float_refused_integer_runs_text_runs` | the `fpe` row of 3.2 |
| `::test_bad_cell_follows_error_policy_fail` | a non-numeric CSV cell under a declared column fails the run (F06 default) and never passes through |

Mutation: remove `top_code` from `SHAPE_REQUIREMENTS_BY_STRATEGY`; `test_csv_top_code_without_declaration_refused` and the catalog test turn red.

### E5

| Test | Proves |
|---|---|
| `E:tests/unit/profiling/test_starter_shape.py::test_csv_date_gets_detected_format` | the starter writes the format for text |
| `::test_parquet_date_gets_no_format` | and not for typed dates |
| `::test_every_starter_config_compiles` (CSV and Parquet fixtures) | the starter never writes a config its own compiler refuses |
| `E:tests/unit/test_strategy_catalog.py::test_shape_matches_requirement_table` | the catalog and the table agree |

Mutation: make the starter write `date_format` for every date; `test_parquet_date_gets_no_format` turns red.

### C1

| Test | Proves |
|---|---|
| `tests/unit/lang/test_docs.py` (existing; runs every snippet) after the cheat-sheet and guide fixes | no doc example is refused by the new rule |
| `tests/e2e/test_column_shape_codes.py::test_codes_reach_cli_with_exit_1` | the new codes reach `validate` and `run` with the config-refusal exit |

### C2

| Test | Proves |
|---|---|
| `tests/unit/lang/test_shapes.py::test_as_date_lowers_to_date_format` | lowering |
| `::test_as_integer_lowers_to_f06` and `::test_as_decimal_lowers_to_f06` | lowering |
| `::test_as_on_hash_is_shape_not_read`, `::test_as_integer_on_date_shift_is_wrong_family`, `::test_as_and_option_repeated` | the three language errors, each with its span |
| `::test_lowering_reads_catalog` (monkeypatch `StrategyInfo.shape`) | the language keeps no strategy list |
| `tests/unit/lang/test_convert_roundtrip.py::test_shapes_print_and_round_trip` | the converter prints `as` and proves the program |
| `::test_column_named_as_works_unquoted` | `as` stays a contextual keyword: `as : hash` and `as as integer : top_code(upper: 89)` both parse |

Mutation: make `_shapes.py` lower `date(...)` to an F06 date; `test_as_date_lowers_to_date_format` and the round-trip test turn red.

### C3

| Test | Proves |
|---|---|
| `tests/e2e/test_init_shapes.py::test_csv_init_writes_as_date_under_review_mark` | detected formats are written for the user to confirm |
| `::test_parquet_init_writes_no_as` | typed sources get no declaration |
| `::test_run_refuses_until_mark_removed_then_runs` | the `?` gate holds |
| `::test_yaml_init_unchanged_for_csv` | the `--yaml` snapshot moves only for typed sources |

Mutation: write `as date(...)` for Parquet dates too; `test_parquet_init_writes_no_as` turns red.

## 11. Docs to update

- Engine: `docs/strategies.md` (the `date_shift`, `bucket_perturb`, `bucketize`, `top_code` and `fpe` sections; a note that `windowed_date` anchors keep the fixed ISO grammar: what each needs on text and on typed columns; remove "auto-detected from the column"), `docs/compatibility-contract.md` (one pre-GA note per freeze item below), `CHANGELOG.md`, `CODEMAP.md` (contracts row), and `docs/frozen-surfaces.md` if it lists `Plan` fields.
- CLI: `docs/guides/decoy-language/cheat-sheet.md` and `02-masking.md` (the `date_shift(min_days: -30, max_days: 30)` examples have no `date_format` and are refused on CSV today; fix them and add the `as` form), `agent-card.md`, `06-from-yaml.md`, `07-errors.md` (new codes), the template comments in `src/decoy/templates/hipaa.yaml` and `pci.yaml` (the format is for text sources only), the roadmap row and the shipped log.
- Vault: the `date_shift` section of `30_Resources/Decoy-Language-to-Delivery.md`, after merge.

## 12. Compatibility and freeze

Every item lands before the 1.0 freeze. Each gets a pre-GA note in `E:docs/compatibility-contract.md`.

| Item | Kind | Slice |
|---|---|---|
| `date_shift` on a typed date with no `date_format` now runs | refusal removed (a success) | E1b |
| `date_shift` or `bucket_perturb` on a typed date with `date_format`: output stays a date instead of formatted text; warning added | output change | E1b, E2 |
| `date_shift` on a tz-naive timestamp is refused at compile instead of failing at run time | earlier refusal, same outcome | E1b |
| `bucket_perturb` on text with no `date_format` | new refusal (owner freeze item) | E2 |
| `bucket_perturb` refuses at run time when no format resolves, instead of passing the column through; unparseable cells become row errors instead of passing through | new refusal and output change, safety | E0 |
| `bucketize` and `top_code` on text with no F06 numeric declaration | new refusal | E3 |
| Numeric strategies on typed dates, booleans and other types | new compile refusal (today every row fails) | E3 |
| `fpe` on typed float, decimal, date and timestamp | new refusal | E3 |
| F06 admits `top_code` and decimal `bucketize` | refusal removed | E3 |
| `Plan.column_shapes`: `plan_hash` moves for configs with shape-reading strategies; `pipeline_config_hash` does not | stored format, additive | E1a |
| New reason codes (section 4), registered unreleased | registry | E0 to E3 |
| `StrategyInfo.shape` | public name, additive | E5 |
| Config-only `decoy validate` (`run_config_only_checks`, `_compile.py:565`) on a Parquet pipeline no longer refuses a missing `date_format`; `validate compile` and `run` do. Recorded in E1a's compatibility note | moved refusal | E1a |
| `.decoy` keyword `as` and the shape clause | language syntax | C2 |

Platform repin checklist (platform is parked): fixtures with `bucket_perturb`, `bucketize` or `top_code` on CSV, and the disguise application path (parked row PLATFORM-DISGUISE-DATE-FORMAT).

## 13. Fold or stand alone

Stand alone. DATE-SHIFT-FORMAT is PARTLY MERGED with only its release and CLI repin left. Reopening it would keep a near-done row open (closing-set rule) and would mix a reversal of its typed-column behaviour into its release. This row depends on that release (E1a After 0.28.2) and replaces the config-only `date_format` descriptor with the shape-aware one. DATE-SHIFT-FORMAT closes when its repin merges; COLUMN-SHAPE-RULE then owns the rule.

## 13.1 Follow-up candidates (not in this row)

- Move the pandas-dtype classifiers in `E:src/decoy_engine/plan/_checks_correctness.py:84` and `:104` and `E:src/decoy_engine/plan/_checks.py:209` onto `ColumnProfile.shape`, so plan checks have one notion of column type. Log it as a structure-review item after this row closes.

## 14. Open questions (recommended answer for each)

| # | Question | Recommended |
|---|---|---|
| Q1 | The owner lists "`bucket_perturb` numeric", which the engine does not have. Add one? | No. Treat `bucket_perturb` as a date strategy. A numeric perturb is a new strategy and a 1.x candidate. |
| Q2 | "A declaration is an explicit override": should a `date_format` on a typed date column turn the output into text (today's effect), or be checked and not used? | Checked and not used, with the `column_shape_format_unused` warning. One meaning per field, and the same YAML runs on CSV and Parquet. |
| Q3 | The numeric declaration on text: F06 (`logical_type` plus `parse_format`) or a new strategy option such as `number_format`? | F06. It already has strict lexers on every route. A new option would be a second parser and a per-strategy copy. The language form `as integer` removes the YAML noise. |
| Q4 | `fpe` on typed float and decimal columns (today it encrypts `str(value)`). | Refuse with `column_shape_mismatch`. The text form of a float is a rendering choice. Typed integers keep working. |
| Q5 | `bucket_perturb` on zoned timestamps. | Refuse in V1. It formats dates only; admitting timestamps later is additive. |
| Q6 | A column made by a `derive` transform: which shape? | The Arrow type the transform produced, read after transforms. If the profile sees only pre-transform sources (the E1a builder confirms), treat derived columns as `unknown` at compile and require the declaration. |
| Q7 | F06's default `error_policy: fail` means one bad cell in a declared CSV numeric column fails the run, where `bucketize` today records a row error. Accept? | Yes. A bad cell under a declared type is a data problem the user must see. `error_policy: quarantine` exists for dirty data. Document it in `strategies.md`. |
| Q8 | One generic `column_shape_required` code, or one code per strategy like `date_shift_requires_date_format`? | Generic for the new ones; keep the shipped `date_shift` code. Fewer codes, one message per family, and the strategy name is in the path. |
| Q9 | `windowed_date` text anchors: require `anchor_format: iso8601`, or keep the fixed ISO grammar with no declaration? | Keep the fixed grammar with no declaration (review round 1). A required field with one allowed value is ceremony. A later optional `anchor_format` with default `iso8601` is additive. |
| Q10 | Language keyword `as`, or a word that cannot clash with column names? | `as`. It reads well, matches SQL `CAST(x AS type)`, and the language already quotes columns named after keywords. |
