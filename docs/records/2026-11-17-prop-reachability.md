# Reachability pass: proportionality packages A, B, D, E and K1 (rows 24zi to 24zl)

Status: record

Date: 2026-11-17. Engine main `dda1b61f`, CLI main `4e6d60b`, platform main `fbaee2a`. The CLI pins
`decoy-engine==0.27.0` (`pyproject.toml:141`; the audit read 0.26.0). The platform pins
`decoy-engine==0.18.0`. Input: [REMEDIATION.md](2026-11-15-proportionality-audit/REMEDIATION.md)
sections 4, 5, 7, 8, 14 and 15. No code was changed.

Method: read the code at the SHAs above, with grep and small AST scripts across all three repos
(every `decoy_engine` import and attribute use in engine, CLI and platform was indexed). Probed
engine names were checked with `git show v0.27.0:...`. **No test suite or command ran**: neither
clone had a venv with the engine's dependencies. Each verdict below is READ, not RUN. Line numbers
are current at the SHAs above and many differ from REMEDIATION.md.

Path shorthand as in REMEDIATION.md: `E:` is `decoy-engine/src/decoy_engine/`, `ET:` is
`decoy-engine/tests/`, `C:` is `decoy/src/decoy/`, `CT:` is `decoy/tests/`, `P:` is
`decoy-platform/`.

Marks:

- **CONFIRMED**: present on main as described, and (for package A) a realistic failure reaches the
  handler from a production entrypoint. The call path is given.
- **DEAD**: the handler sits on a production path, but no realistic failure reaches it (an earlier
  check refuses first, the input is a constant, or the type guarantees it). The fix is a deletion
  with no behavior change. Under `dev-rules/proportionality.md` ("a branch you would mark
  unreachable is an assertion or a deletion") these are still in scope, but none meets the V1 bar.
- **NOT CONFIRMED**: not as the audit described; the reason is given.
- Package B adds **DELETE** (no consumer outside tests in engine, CLI or platform) and
  **KEEP-PLATFORM** (a platform consumer, named).

## Counts

| Package | CONFIRMED / DELETE | DEAD | NOT CONFIRMED / KEEP | Owner decision | Items |
|---|---|---|---|---|---|
| A | 4 (A2, A5, A9, A10) | 6 (A1, A3, A4, A6, A7, A8) | 1 (A11) | A10 policy | 11 |
| B | 10 of 12 sub-items | - | B7b KEEP-PLATFORM; B9 runtime KEEP | B8a reason identity, B9 platform and verification codes | 9 (12 sub-items) |
| D | 12 (D1 to D12, D6 manifests half) | - | D6 saved-scan half, D13 | D6 saved scans, D13 | 13 |
| E | 6 (E1, E2, E3, E4, E6, E8) + E5 present | - | E7 (both halves differ from the audit) | E7 | 8 |
| K1 | 1 | - | - | - | 1 |

Main findings:

1. **Only one package A item changes masked output: A2.** A missing or corrupt shipped ZIP5 table
   silently turns off the state cascade level, so rows fall to `suppress` and the run succeeds. It
   meets the V1 bar.
2. **A5 is live and hides lane bugs,** but data stays identical under the parity contract; the
   activation evidence and route label change. RUN-STREAM E5a (engine #604) did not touch the file,
   so A5 is unblocked.
3. **Six package A items are dead defensive code,** not quiet fallbacks a user can hit.
4. **B7 is partly wrong:** the platform passes `chunked_dispatcher_enabled` and
   `multi_table_dispatch_enabled` in production (`P:api/jobs/v2_runner.py:263-264`). **B9 runtime
   is wrong:** all 325 runtime codes are reached.
5. **D6 is half wrong:** `decoy demo` still writes the pre-`scan-set/v1` scan shape, so the legacy
   saved-scan reader has a live writer.
6. **E2's four copies are not equal.** Some JSON baselines are the only source; others mirror an
   in-code constant whose values carry the real reasons; and nine CLI guards assert JSON equals
   constant a second time. Section 5 maps every allowlist.
7. **E7 differs from the audit on both files.** The perf-claim guard is live (32 docs carry
   claims), and the Wave B migration it pins is not finished.

## Package A: quiet fallbacks (row 24zi)

Common engine path, shortened to **P**: `run_pipeline` (`E:execution/_pipeline.py:115`) →
`_dispatch.execute_route` (:359) → `_pipeline_route_dispatch.py:94 run_full_frame_route` →
`_pipeline_full_frame.py:145 _run_full_frame`, then either `:171 maybe_run_unified_slice` or
`_pipeline_generate_mask.py:331 adapter.run` → `_pandas_adapter.py:299 _dispatch_mask_node` →
`:427 run_with_when_gate(handler.run)`. `decoy run` reaches `run_pipeline` through
`C:cli/run/_flow.py:152` → `_execute.py:314 execute` → `:353`.

| Id | Site on main | Mark | Changes output | V1 bar |
|---|---|---|---|---|
| A1 | `E:transforms/text_mask.py:412-417` | DEAD | no realistic path | no |
| A2 | `E:transforms/geo_generalize.py:278-281` | CONFIRMED | **yes, masked values** | **yes** |
| A3 | `E:plan/_seed_envelope.py:124-132` | DEAD | no | no |
| A4 | `E:plan/checks/_generate_columns.py:350-356` | DEAD | no | no |
| A5 | `E:execution/_unified_slice.py:359-361` | CONFIRMED | evidence and route label only | no (data identical) |
| A6 | `E:execution/physical/_compiler.py:437-445` | DEAD | no | no |
| A7 | `C:cli/init.py:326-331` | DEAD | no | no |
| A8 | `C:cli/run/_execute.py:308-310`, `C:cli/demo.py:300-302` | DEAD | no | no |
| A9 | `C:cli/run/_render.py:53-61` | CONFIRMED | success-card hint line only | no |
| A10 | `E:context.py:161,163,181,194,212,225` | CONFIRMED (platform only) | telemetry only | no |
| A11 | `E:execution/_chunked_fk_dtype_safety.py:132,164,174,183` | NOT CONFIRMED | no (fails closed) | no |

### A1 Faker method fallback: DEAD

- Handler: `try: return str(method()) except Exception: pass`, then `return str(fake.name())`.
- Path: P → `E:execution/_strategies/_text_mask.py:170 mask_cell` → `text_mask.py:637` → `:550
  _mask_span` → `:500 _mask_faker`.
- Why dead: the method name comes only from the constant `_FAKER_METHOD` (`text_mask.py:228`:
  name, first_name, last_name, address, city), never from config. `shared_faker()` is a
  default-locale `Faker()` (`_faker_span.py:32`), so the attribute always resolves.
- Tests pinning the quiet behavior (they flip on a fix): `ET:unit/transforms/test_text_mask_faker_reuse.py`
  `test_fallback_parity_method_raises_mid_draw`, `test_fallback_parity_attr_non_callable` and
  `test_fallback_parity_attr_unavailable`, plus its `_fresh_reference` helper (:80-95).
- Fix: call `getattr(fake, method_name)()` directly.

### A2 ZIP5 state map: CONFIRMED, V1

- Handler: `except Exception: _LOG.warning(...); return {}`.
- Path: P → `E:execution/_strategies/_geo_generalize.py:95 cascade_zip_column` →
  `geo_generalize.py:345 _build_state_map` → `:279 load_table("us_zip5_city_state")`.
- Failure that reaches it: `FileNotFoundError`, `OSError`, `ValueError` or a pyarrow error from
  `reference_tables/_loader.py:71-74` when the shipped parquet is missing or corrupt (a packaging
  regression).
- Output effect: every row's `state` becomes `""`, so the `state` cascade level never matches and
  rows fall to `suppress`. The run succeeds. This over-suppresses rather than leaks.
- The sibling `_load_restricted_zip3` (`:104-111`) lets the same failure raise.
- No test covers the fallback.
- Fix: delete the try, matching zip3.

### A3 seed envelope unknown provider: DEAD

- Handler: `except _ProviderError: reg_caps = None` (already a named catch).
- Why dead: `check_unknown_provider(config)` (`E:plan/_compile.py:190`) uses the same default
  registry and config and runs before `_build_seed_envelope` (`:439`, its only caller).
  `get_capabilities` raises only for an unknown name (`providers_v2/_registry.py:72-89`).
- No test covers it.
- Fix: drop the try.

### A4 `_expression_refs`: DEAD

- Handler: `except Exception: return frozenset()` at `:355`.
- Path: `compile_plan` → `_compile.py:218 check_generate_columns` → `_generate_columns.py:143
  _check_column` → `:165` → `:347` → `:355`.
- Why dead: `_check_column` runs `_check_parse_rules` first (`:164`). That calls
  `DerivedConfig.from_dict`, which runs the same `compile_expr` (`E:transforms/derived.py:138`), so
  a bad expression is refused with `GENERATE_OPTION_INVALID` before `:355`.
- Adjacent, not in the audit: `E:plan/_checks.py:638` (`except Exception: continue`, "skip
  double-report"). The plan should check it.

### A5 unified-slice reroute: CONFIRMED, unblocked

- Handler: `except Exception as exc: _logger.warning(_REROUTE_LOG, type(exc).__name__, ...);
  return None`.
- RUN-STREAM E5a (engine #604, `2929aace`) and #605 do not touch the file; its last change is
  #588 (`187a14e6`). The row's wait on E5a is met.
- Path: P → `_pipeline_full_frame.py:171` → `_unified_slice.py:369 maybe_run_unified_slice`
  (default on) → `:123 _execute_admitted`, whose try spans `:188-359`.
- Failures that reach it: `PlanCompileError`, `ExecutionError` and `ConfigError` from plan build
  or compile, `ArrowInvalid`/`ArrowTypeError`, native `RuntimeError`, `ValueError`, `KeyError` and
  `TypeError` from lane bugs, and `MemoryError`. A pyo3 `PanicException` is a `BaseException` and
  propagates (pinned by `test_base_exceptions_propagate_uncaught`).
- Output effect: the pandas oracle reruns, so data is identical under parity. The
  `unified_slice_activation` evidence disappears and the route label in `quality_metrics`
  changes. `decoy run --native` already turns a decline into `NativeGateError`
  (`C:_native_gate.py:466-480`); the default intent stays silent.
- Test pinning the quiet behavior: `ET:physical/test_unified_slice_exception_boundary.py::test_unexpected_exception_reroutes_to_legacy`.
- Fix: catch only the coded lane-decline set and let everything else raise.

### A6 `_post_scan_resident`: DEAD

- Handler: `try: return post_scan_resident_for(thaw_config(inputs.config)) except Exception:
  return None`.
- Path: P → `_unified_slice.py:214 compile_physical_plan` → `_compiler.py:408 select_driver` →
  `:252 layer1_route` → `:95` (also `:178`).
- Why dead: the body (`E:config/_post_scan.py:133-206`) is `Mapping.get` and comparisons over a
  validated config. The runtime already calls the same function unguarded earlier, at
  `_pipeline_routing.py:211` and other sites.
- Fix: delete the try.

### A7 `_validate_scaffold`: DEAD

- Handler: `try: import yaml; from decoy_engine.config import parse_pipeline_config except
  Exception: return`.
- Path: `decoy init <file>` → `init.py:509 _scaffold_from_file` → `:402` → `:315`.
- Why dead: `yaml` is imported at module top (`init.py:26`), the engine is a hard dependency, and
  `parse_pipeline_config` is exported in 0.27.0 (`decoy_engine/config/__init__.py:65,175`).
- `C:cli/init.py` is **not** a `cli/run/` hot file, so A7 can build in this row. The audit grouped
  it with A8 and A9.
- Fix: plain imports. Also update the comment at `CT:e2e/test_init_command.py:127`.

### A8 `outputs` not a dict: DEAD

- Handler: `if not isinstance(outputs, dict): return {}` (in `demo.py`, `return`).
- Paths: `decoy run` → `_execute.py:386 _write_mask_outputs` → `:309`; `decoy demo` →
  `demo.py:591` → `:172 _run_v2_mask` → `:277` → `:301`.
- Why dead: `ExecutionResult.outputs` is `dict[str, pa.Table]` (`E:execution/_adapter.py:63`),
  and every constructor reachable from `run_pipeline` passes a dict. `outputs=None` is produced
  only by `IsolatedRunResult`, which the CLI does not use. In `_execute.py`, line `:388` would
  raise `AttributeError` first anyway.
- **Adjacent quiet skip, not traced to the end:** `C:cli/io/_targets.py:487-489`, `if table is
  None: continue`. A declared target with no matching output writes nothing. Whether config
  validation refuses such a target key is unverified; the plan must settle it.
- Hot file: `C:cli/run/_execute.py`. Its deletion goes with the row that holds `_execute.py`
  (SUB-RUN CLI half, CLI delivery, SAMPLE, LIB L5a, F23 resume; ROADMAP section 4 rule 2). The
  `demo.py` copy can build here.

### A9 `_next_hint_for_run`: CONFIRMED, hint only

- Handler: `raw_cfg.get("output", {}).get("path")` inside try/except-pass.
- Path: `decoy run` → `_flow.py:201 _render.finish` → `_render.py:168`.
- Why it always returns `None`: `PipelineConfig` is `extra="forbid"` with no top-level `output`
  (`E:config/_pipeline.py:99-125`), and validation runs before rendering. The success card
  therefore never shows the hint. No data, file or exit-code effect.
- No test covers it.
- Hot file: `C:cli/run/_render.py` belongs to RESULT (row 62) inside F29 C1 (row 66). Plan it
  here; build it with F29 C1.

### A10 `emit_*` helpers: CONFIRMED, platform only

- Handlers: `except Exception: pass` at `E:context.py:161,163,181,194,212,225`.
- Reach: only when a logger is supplied, through the public `emit_*` exports, `StructuredEventsSink`
  (`E:progress.py:85-123`) or `profile_columns(ctx=...)` (`E:profiling/profiler.py:297,333`). The
  CLI never supplies a logger. The platform does: `ExecutionContext(logger=...)` at
  `P:api/storm/router.py:44,1297`.
- Failures that reach it: whatever `JobLogger` raises (DB or I/O errors), and `TypeError` from a
  signature mismatch.
- Output effect: telemetry only.
- Tests pinning the quiet behavior: `ET:unit/test_structured_events.py`, the five
  `Test{EmitStep,EmitLineage,EmitFidelity,EmitQuarantine,EmitThroughputSample}::test_noop_when_method_raises`.
- B5 deletes two of the five helpers and D12 changes `emit_step`.
- Owner question: best-effort telemetry may be intended. Either narrow the catch and log the
  class, or keep it and record why.

### A11 dtype-safety predicates: NOT CONFIRMED

- Handlers: the catches at `:132` (`ZoneInfo`), `:164` (`pa.timestamp`) and `:174`/`:183`
  (`pa.decimalNN`) return `False`.
- Paths: the chunked route → `_chunked_fk_edge_checks.py:526,536` (a compile-time decline), and
  `_chunked_fk_dtype.py:121`, where `False` raises `CHUNKED_FK_KEY_DTYPE_NOT_CROSS_ADAPTER_SAFE`.
- Why not confirmed: `False` fails closed. The route declines, or the run raises loudly. Nothing
  becomes quieter.
- Narrowing the catches to the named errors is cosmetic: `:132` to `(ZoneInfoNotFoundError,
  ValueError)`, the rest to `(ValueError, TypeError, OverflowError)`. Tests rely on these:
  `ET:unit/execution/test_chunked_fk_dtype_safety.py::test_real_type_unsafe_rejected` and
  `::test_declared_unsafe`.

## Package B: public-surface leftovers (row 24zj)

The platform imports no B1 to B8 name from any path, old or new. Its only engine uses touching
this package are `run_pipeline` (B7b), `ExecutionContext(logger=)` and
`composite_city_state_zip` via `decoy_engine.generation.composite`. All of those paths exist on
engine main.

| Id | Name | Public how | Consumers outside tests | Verdict |
|---|---|---|---|---|
| B1 | 21 `_F9_KEPT_BINDINGS` (`E:__init__.py:252-275`, tuple `:342-364`) | top-level attribute, not in `__all__` | none. The platform takes `composite_city_state_zip` from `generation.composite` (`P:api/composites/preview.py:14-16`) | DELETE the bindings; keep the `identifiers` and `generation.composite` homes |
| B2 | `deterministic_hash` (`E:internal/crypto.py:18`) | `internal/` | none (archived platform docs only) | DELETE |
| B3 | `ExecutionContext.resolve_connector`, `captured_outputs`, `pool_resolver`, `column_relationships`, `export()`, `_exports`, `_current_node_id` (`E:context.py:248-331`) | members of an `__all__` class | none; the only construction is `ExecutionContext(logger=...)`. Platform `ctx.export(...)` mentions are stale comments (`P:api/evidence/assembly.py:1664,1780`, `P:api/evidence/schema.py:413,440,471`, `P:api/models.py:1341`, `P:api/jobs/schemas.py:376`) | DELETE |
| B4 | `TelemetryClient` and the `telemetry` slot (`E:context.py:230`) | `__all__` | none | DELETE |
| B5a | `emit_fidelity` (`E:context.py:185`) | `__all__` | none | DELETE |
| B5b | `emit_quarantine` (`E:context.py:198`) | `__all__` | none | DELETE |
| B5c | `emit_step(node_id=)` (`E:context.py:108`) | keyword | no caller passes it (6 engine callers checked) | DELETE the keyword; `emit_step` stays |
| B6 | `ExecutionEvent` (`E:execution/_events.py:15`) | `__all__` of `decoy_engine` and `decoy_engine.execution` | never constructed | DELETE the file |
| B7a | `run_pipeline(progress_interval_s, secret_registry, secret_cache_policy)` (`E:execution/_pipeline.py:154,156,157`) | keywords | none, not even tests | DELETE with their plumbing (`_pipeline.py:301,348-349`, `_pipeline_context.py:212-213,317-318`, `_chunked_oracle.py:105-106`) |
| B7b | `chunked_dispatcher_enabled`, `multi_table_dispatch_enabled` (`_pipeline.py:141,143`) | keywords | **platform**, `P:api/jobs/v2_runner.py:263-264` (`=settings.native_dispatcher_enabled`, its rollback lever, `P:api/config.py:425`); present in 0.18.0 | **KEEP-PLATFORM**; record the consumer beside the keyword |
| B7c | `stream_chunked_output`, `use_byte_estimate_routing`, `use_probe_routing` (`_pipeline.py:142,148,149`) | keywords | tests (about 3, 38 and 21 files) and engine benchmark scripts | DELETE the `run_pipeline` keywords. The internal routing parameters that `capacity.py:384-385,443-445` passes stay |
| B8a | `VALIDATION_CODES.FK_SELF_REFERENCE` alias (`E:validation_result.py:367`) | attribute of an `__all__` object | none, and nothing produces `fk.self_reference` | DELETE the alias. Keeping the reason identity `config.fk.self_reference` is an owner question (see the notes) |
| B8b | `event_to_legacy_dict` (`E:_progress_events.py:598`) | `__all__` of `decoy_engine` and `decoy_engine.progress` | none | DELETE |
| B9 | platform, verification and runtime reason codes | `decoy_engine.reasons.*` | see the notes | PARTIAL |

Freeze pins that each deletion must edit in the same slice:

- `ET:unit/test_public_api.py:27-342` (the whole `__all__` set: B4, B5a, B5b, B6, B8b; also
  `:94`, `:119`, `:213-215`, `:416-419`).
- `E:../docs/frozen-surfaces.md:75,77,80`, read by `ET:sentry/release/test_frozen_surface_map.py`.
- `ET:unit/execution/test_r3_public_signature_freeze.py` (`FROZEN_PARAMETERS` and the `== 47`
  count, for B7a and B7c).
- `E:../docs/compatibility-contract.md:42-50` and `:806-822` (B7).
- `ET:sentry/test_deprecation_expiry.py:38-45`, which marks B2 `PERMANENT`.
- B8a: `ET:fixtures/f29/reason-baseline.json:25`, `ET:fixtures/f29/producer-inventory.json:1369` and
  `ET:sentry/baselines/f29-producer-inventory.json:3410`.

Tests deleted with their names:

- B1: `ET:unit/test_identifiers_subimport.py:41-47`.
- B2: `ET:unit/internal/test_crypto.py:15-51`.
- B3: `ET:unit/test_context_exports.py` (whole file).
- B5: `ET:unit/test_structured_events.py` `TestEmitFidelity` and `TestEmitQuarantine`.
- B8b: the uses in `ET:unit/progress/test_consumer_contract.py:102`,
  `ET:unit/progress/test_versioned_contract.py:103`, `ET:unit/safe_output/test_value_domains.py:71,281`
  and `ET:security/test_f29_remediation.py:27,139,148`.
- B5 also orphans the protocol methods `StructuredEvents.fidelity` and `quarantine`
  (`E:context.py:83-84`), and the platform's `Logger.fidelity` and `quarantine`
  (`P:api/persistence/logger.py:337,346`). The platform side is harmless; it needs only a note.

### B9 reason codes

- **Platform namespace: 69 codes** (66 live, 3 tombstones in `reasons/platform/_retired.py`).
  - No engine or CLI source references any of them, and no platform module imports
    `decoy_engine.reasons`. The module did not exist in 0.18.0.
  - 21 of the codes appear as the same string literal in platform code, which still hard-codes
    its own copies (for example `P:api/pipelines/v2_validation.py`, `P:api/jobs/v2_config.py`).
  - The namespace docstring says these are the platform's future wire identities. Verdict:
    **KEEP by intent**, as the roadmap row expects. Owner to confirm.
- **Verification: 28 codes.** 15 are referenced by symbol. The other 13 match only as bare
  check-name strings (`E:validation/post/_checks/__init__.py:33ff`,
  `E:quality/diagnostic.py:102-108`). No `ReasonRef("verification", ...)` lookup was found. They
  are probably unreferenced as reasons, which is close to the audit's 12, but this is
  **unverified**.
- **Runtime: 325 codes, 0 unreferenced. The audit was wrong.**
  - 10 are reached through the alias `_R.X` (`declared_casting/_numeric.py:78,126`, `_cobol.py`,
    `_quarantine_local.py`).
  - The audit's 9 are the `sequential_*_input_type_drift` table (`E:reasons/runtime/_tables.py:17-27`,
    used at `E:execution/_sequential_native.py:621`).
- Any reason deletion runs into the append-only pins:
  - `ET:fixtures/f29/reason-manifest-v1.json` (checked by `ET:unit/test_reason_registry.py:34`)
  - `ET:fixtures/f29/reason-registry-release.json` (checked by `ET:unit/test_reason_release_pin.py`)
  - `ET:sentry/baselines/f29-reason-baseline.json`
  - `E:../docs/reasons.md:27` ("deprecated, never deleted"; one pre-GA precedent)

Not checked: `ExecutionContext.derive_key` and `pipeline_derive_key`. The platform's
`P:api/keys/derive.py:59` builds a closure for `ExecutionContext.derive_key`, and they are not in
B3.

## Package D: shims, re-exports and old-engine probes (row 24zk)

Every probed name exists in the pinned `v0.27.0` (and in `v0.26.0`). The platform pins 0.18.0
and imports none of the engine paths below. Its only hit is a docstring at
`P:api/jobs/admission_fk.py:15`.

| Id | Mark | Sites on main | Tests that change | Guards that pin it |
|---|---|---|---|---|
| D1 | CONFIRMED | `C:_native_gate.py:503-522` `run_pipeline_accepts`, second caller `C:cli/run/_progress.py:58` | `CT:unit/run_progress/test_capability.py`; `CT:e2e/test_run_native.py:371`; `CT:e2e/test_mask_api_native.py:192,346` | none |
| D2 | CONFIRMED, plus 2 unlisted sites | `C:cli/run/_prepare.py:426-429`, `C:cli/tokenize.py:299-308` (keep the import; it binds `MaskSecretError`), `C:api.py:149-152`, `C:cli/run/_errors.py:134-151`, `C:cli/exit_codes.py:270-281`, `C:_mask_secret.py:72-78`; unlisted: `C:_mask_secret_guidance.py:138-141` and the `OLD_ENGINE_*` texts at `:49-77` | `CT:e2e/test_run_mask_secret.py::TestPreDE02EngineGuard` (:668); `CT:e2e/first_user/test_items_text.py` `old_engine` fixture and tests at :260 and :281 | none |
| D3 | CONFIRMED, plus 1 unlisted site | `C:cli/preflight.py:386,546`, `C:_native_gate.py:139-142` (with the too-old branch at `:352-358` and arms at `:379`, `:393`), `C:cli/exit_codes.py:230-235`; unlisted: `C:cli/info.py:84` | `CT:e2e/test_preflight_capacity.py:270`, `CT:e2e/test_preflight_native.py:164`, `CT:unit/test_native_gate.py:137,593`, `CT:e2e/test_info_native.py:140,149`, the skip at `CT:unit/test_exit_code_for.py:112-114` | none |
| D4 | CONFIRMED | `C:cli/report.py:894-899` (pandas is a hard dependency through the engine; `C:api.py:31` imports it at top) | none | none |
| D5 | CONFIRMED, tied to D1 | `C:cli/run/_execute.py:341-353` | D1's fake old engine at `CT:e2e/test_run_native.py:395-415` | none |
| D6a | CONFIRMED | manifests: `C:cli/io/_targets.py:193-198,263-264`; the only writer (`C:cli/evidence.py:180-196`) always writes `format` | `CT:unit/cli_fmt/test_targets_format.py:178-181` | docstring `C:cli/evidence.py:22-28` |
| D6b | **NOT CONFIRMED** | saved scans: `C:cli/io/_scan_set.py:35-57,152-208` | - | `CT:sentry/test_scan_reader.py` |
| D7 | CONFIRMED | `E:execution/out_of_core/_source.py`; **23 importers**: 8 in source, 14 in tests, 1 in scripts | `ET:unit/execution/test_out_of_core_source.py::test_lazy_source_is_public_export` | engine CODEMAP row 107; docstring `E:profile/_readers.py:27` |
| D8 | CONFIRMED, partly dual paths | `_mem_estimate.py:81-94`, `_chunked_fk.py:22-34`, `_pipeline_routing.py:19-30`, `native/_dispatch.py:51-54,81-83`; `_planner_columns` and `_sequential_order` are dual paths, not pure re-exports | about 15 test files | module-size census for `_dispatch.py` (688 ceiling, 677 actual); CODEMAP rows 42 and 111 |
| D9 | CONFIRMED | `E:quality/dp_budget.py:499-520`; 1 source importer (`E:quality/dp.py:77-79`) and 6 test files | `ET:unit/quality/test_opendp_dependency.py:186` | none |
| D10 | CONFIRMED | `E:execution/_fk_key_compat.py`; one caller `_pandas_adapter.py:51` | `ET:unit/execution/test_pandas_adapter_helper_kills.py::TestFkKeyValueWrapper` | `ET:sentry/test_physical_seam_disconnection.py:952-956`; comment in `test_module_size.py:121`; `_pandas_adapter.py` has an exact census of 700 (694 actual) |
| D11 | CONFIRMED | `E:execution/_chunked_adapter_gate.py:13-27` returns `True`; one caller `_chunked_oracle.py:343-347` | `ET:unit/execution/test_de10_chunked_fk_passthrough.py::test_chunked_adapter_touches_pandas_ingestion_is_unconditional` | `ET:sentry/test_physical_seam_disconnection.py:519` |
| D12 | CONFIRMED | `E:context.py:143-161` (`except TypeError` retry); the platform's `JobLogger.step` (`P:api/persistence/logger.py:182-192`) accepts the new keywords | the fake `CapturingStructured.step` at `ET:unit/test_structured_events.py:40` needs a wider signature | none |
| D13 | **NOT CONFIRMED** | `E:providers_v2/_faker_adapter.py:80-84,251-279` | - | - |

### D6b and D13

**D6b saved-scan reader: NOT CONFIRMED.** A live writer of the old shape remains.

- `C:cli/demo.py:167` writes `profile_document(profile)`. In 0.27.0 that is
  `redact_profile_dict(profile.to_dict())` (`profiling/_value_redaction.py:473-475`), with no
  `scan_schema`.
- `C:api.py:686-688` tells `decoy.scan()` users to save scans the same way.
- So `decoy scan fields|show|diff` on the `scan.json` that `decoy demo` writes relies on
  `_from_legacy`.
- Fixtures feed the old shape: `CT:fixtures/scan/legacy_profile.json`,
  `CT:e2e/cli_fmt/test_scan_saved.py`, `CT:e2e/test_scan_fields_show.py` and
  `CT:e2e/test_scan_diff_move.py:67-68`.
- Removing the reader needs `demo` and `api.scan` switched to the v1 core first, then an owner
  decision on scan files users already saved.

**D13 V2 custom-provider table: NOT CONFIRMED as a shim.** It backs a public function.

- `register_faker_provider_v2` is public:
  - exported at `E:__init__.py:250,577` and `E:providers_v2/__init__.py:54,69`
  - frozen in `docs/frozen-surfaces.md:84`, and pinned by `ET:unit/test_public_api.py:202`
  - named in the error text at `E:plan/_checks.py:93`
- The V1 table it was meant to outlive (`E:internal/faker_setup.py:41`) is still live.
- Its only user is `ET:unit/providers_v2/test_registry.py` (3 tests); there is no CLI or platform
  use.
- Removing it is a public-surface removal (package B form) and an owner decision.

### Hot-file notes for the plan

D1 (`cli/run/_progress.py`), D2 (`cli/run/_prepare.py`, `cli/run/_errors.py`) and D5
(`cli/run/_execute.py`) touch `cli/run/` modules that ROADMAP section 4 rule 2 assigns to other
rows. Their order matters: D1 and D5 have to land together.

### Importer lists

- **D7** (all should import `decoy_engine.profile._readers.LazySource`):
  - Source, all under `out_of_core/`: `_runner.py:81`, `_stream_driver.py:90`,
    `_preflight.py:23`, `__init__.py:26`, `_stage.py:27`, `_rewrite_pass.py:43`,
    `_relation.py:24`, `_route_policy.py:42`.
  - Tests, under `ET:`:
    - `perf_fixtures/fk_relational.py:34`
    - `parity/`: `_d1a_hash_data.py:29`, `_dcomp_ooc_shapes.py:30`, `_ooc_temporal_fk.py:26`,
      `test_out_of_core_route_seam_parity.py:40`
    - `unit/execution/`: `test_pipeline_route_exec_ooc_memory_preflight.py:20`,
      `test_stream_driver_lifecycle.py:25`, `test_route_policy_wide_key_fallback.py:40`,
      `test_out_of_core_source.py:20`, `_stream_driver_harness.py:28`
    - `fileaccess/`: `test_x4_scratch_and_names.py:19`, `scratch/test_scratch_plain_host.py:24`
    - `perf/`: `test_out_of_core_reorder_wide_raw_memory.py:79`,
      `test_out_of_core_reorder_multi_edge_memory.py:127`
  - Scripts: `scripts/build_floor_probe.py:55`.
- **D8**:
  - `_mem_estimate.py` → `_mem_estimate_dtypes`. `is_fixed_width_dtype` is in `__all__` at
    `:595`. Importers: `_mem_estimate_schema.py:25` and `out_of_core/_spill_estimate.py:160` in
    source, plus 4 test files.
  - `_chunked_fk.py` → `_chunked_fk_runtime` / `_chunked_fk_vocab`. Importers:
    `_chunked_oracle.py:34-38`, `_chunked.py:186-187` and `_chunked_fk_dtype.py:40` in source,
    plus 7 test files.
  - `_pipeline_routing.py` → `_pipeline_chunk_route` / `_pipeline_routing_signals`. 6 of its 9
    names have no user. Attribute users: `pipeline/_stream.py:133`, `_pipeline_finalize.py:143`
    and `_pipeline_context.py:499,524`, plus a monkeypatch at
    `ET:unit/execution/run_stream/test_e1a_stream.py:348`.
  - `native/_dispatch.py`:
    - `_mask_chunk_native` has 0 users.
    - `_resolve_faker_pools` and `_resolve_truncate_keep` are used by 3 test files.
    - `NativeChunkSchemaDriftError` is used by 4 test files.
  - `_planner_columns` and `_sequential_order` are dual paths. 5 importers use the old path,
    for example `_mixed_static.py:312` and `_pipeline_route_exec.py:330`.

## Package E: guard bookkeeping (row 24zl)

### E2 allowlists: CONFIRMED, but the copies are not equal

Shared machinery, the same shape in both repos:

- `tests/sentry/_ratchet.py`: the shrink-only check. Engine `REHOME_BY_BINDING`/`moved_from` is
  per entry and used only by `secret-material-census` (`_ratchet.py:30-37`). The CLI uses a
  top-level `moved_from` map (`_ratchet.py:13-19`), used today in `csv-read-allow.json` and
  `private-file-sinks.json`.
- `scripts/dev/ratchet_check.py`: runs `_ratchet.check` against the merge base, from
  `scripts/dev/gates.sh` (engine `:465-468`, CLI `:261-263`).
- `tests/sentry/_baseline_sources.py` (engine 424 lines, CLI 468): `SOURCES` holds extractors,
  not data (a constant name and a key lambda, or a file reader). It is read by
  `test_baseline_registry.py` and the one-off `--write-initial`.
- `scripts/dev/sentry_registry.toml` (engine 37 rows, CLI 26): each row has only `id` and
  `baseline`. `test_baseline_registry.py` asserts the path is always
  `tests/sentry/baselines/<id>.json` (engine `:39`, CLI `:44`), so **the row holds no fact of
  its own**; it repeats the file name. Readers: `_ratchet.parse_registry`,
  `test_baseline_registry`, and the CLI per-guard pins (E6).
- `test_baseline_registry.py`: checks the live `SOURCES` keys against the JSON keys both ways,
  plus `max`; checks registry ids against `SOURCES` ids; and AST-scans for unregistered
  `ALLOW|EXEMPT|...` constants (engine `:59-110`, CLI `:71-147`).

**Engine: 37 allowlists.**

| Group | Count | Where the fact lives | What the JSON adds |
|---|---|---|---|
| (a) constant + JSON mirror | 17 | the in-code constant; the guard reads it. `UNCHECKED_HELPERS` (`ET:sentry/test_reason_registry.py:202-210`) is also read from JSON at `:838-848`, a 3-way copy | the key set only; `reason` is the filler "initial X0a inventory of ...". `max` only for package-fanout and table-kind. The module-size ceiling lives in code only, so the ratchet cannot see a ceiling raise |
| (b) JSON only | 14 | the JSON; the guard reads it (`gcs-call-kwargs`, `serial-resources`, `exception-context`, `validation-name-messages`, `strategy-docs-agree`, 9 `post-scan-*`, 7 of them empty) | already the single source; `SOURCES` re-reads the same file, so the registry check compares the file with itself |
| (c) mirror of another data file | 4 | `ET:fixtures/f29/*.json` and `ET:sentry/secret_material_census.json` | a duplicate |
| (d) `private-file-sinks` | 1 | `file_access_registry.toml` rows with `disposition=private` | derived keys |
| (e) `import-layers` | 1 | the `.importlinter` ignore lines | a duplicate |

Group (a) files: `test_module_size.py:91-156`, `layout/test_package_fanout.py:30-43`,
`test_table_kind_classifier.py:26-54`, `test_public_import_boundary.py:57-70`,
`test_exception_hierarchy.py:63-73`, `test_reason_policy_single_source.py:39-65`,
`test_file_access_entry_points.py:34-41`, `test_post_scan_route_guard.py:48-61`,
`test_locator_hygiene.py:127-134`, `test_log_interpolation.py:71-81`, `test_source_hygiene.py:32-45`,
`test_phase_containment.py:17-30`, `test_validate_no_mutation.py:79` (empty),
`test_physical_seam_disconnection.py:152-157`, `test_engine_string_targets.py:33-41`,
`test_wave_b_no_registry_version_literal.py:22-29`, and `test_reason_registry.py:202-210`.

**CLI: 26 allowlists.**

| Group | Count | Where the fact lives | Notes |
|---|---|---|---|
| (a) constant + JSON | 18 | the constant | 9 guards also re-read their JSON and assert it equals the constant, **reason text included**. The reason text is therefore kept twice and checked twice |
| (b) `FromScan` | 3 | the JSON (`one-error-emitter`, `env-reads`, `json-stdout-writes`); a scanner produces the keys | single source |
| (c) JSON as source | 3 | `exception-context` (`BASELINE_KEYS` is built from the JSON, a circular check), `retired-name-pending` (`FromFile`), `import-layers` (`.importlinter`) | |
| (d) `private-file-sinks` | 1 | `io_policy/file_sinks.toml` → `BASELINE_ROWS` (`test_private_files.py:185`) → JSON | 3 copies |

Group (a) files:

- `test_engine_internal_boundary.py:70-87`, a dataclass with count, reason and removal note.
- `test_engine_reason_code_copies.py:58-86`, with count.
- `test_atomic_writer.py:106-119`.
- `io_policy/` files:
  - `test_canonical_json.py:42-73`
  - `test_library_writer.py:56-69`
  - `test_target_writes.py:66-74`
  - `test_manifest_path_resolution.py:61-68`
  - `test_output_placement.py:54-79` and `:82`
  - `test_config_load_choke_point.py:45-87`
- `defects/` files:
  - `test_kind_canary.py:37-42`
  - `test_config_error_routes.py:56-81`
  - `test_exit_code_owner.py:29-45`
- `test_csv_read_choke_point.py:52-77`.
- `test_gate_single_entry.py:61-83`.
- `CT:unit/test_surface_docs_consistency.py:43-56,61-76`.
- `layout/test_module_size.py:22-27`.
- `layout/test_package_fanout.py:24-27`.

Facts that live in code only today, and which a JSON-only design must carry as fields:

- `count` and the removal note in engine-internal-boundary.
- The exact `count` in engine-reason-code-copies. The ratchet cannot see a count raise
  (`_baseline_sources.py:11-14`).
- The real reasons in the engine group (a) constants.
- The engine module-size ceilings.

What a JSON-only change breaks and must replace:

- `_baseline_sources.write_initial`.
- All of `test_baseline_registry`.
- The seeded cases in `test_ratchet_check.py`.
- `_ratchet.parse_registry`.
- The CLI `test_baseline_registry`'s use of `SENTRIES` (E1).
- Engine `test_reason_registry.py:842`.

### Other E items and K1

| Id | Mark | Where on main | Notes and fix |
|---|---|---|---|
| E1 | CONFIRMED | `ET:sentry/test_sentry_manifest.py:25-129` (102 paths; 100 match the files on disk, plus 2 outside: `ET:secret_providers/test_leak_sentry.py`, `test_classifier_equivalence.py`); `CT:sentry/test_sentry_manifest.py:26-107` (79 paths; 76 plus 3 under `CT:unit/`) | The CLI `test_baseline_registry.py:33,121-134` reads `SENTRIES` to choose its scan set and asserts exactly 3 `tests/unit` entries. Fix: glob `tests/sentry/**/test_*.py` plus the named outside paths |
| E3 | CONFIRMED | `ET:sentry/test_physical_seam_disconnection.py` (1,055 lines): import direction `:57-221`; diff gate `:223-1021` (helpers `:229-252`, `F29_REGISTRY_MIGRATION` `:260-288`, test `:291-1021`, `permitted_non_physical` about `:326-990`); dynamic import probe `:1023-1055` | The import tests stand alone. Three `ET:unit/execution/test_*_bookkeeping.py` files import `GUARDED_MODULES` and `_imports_physical`, both in the part that stays. The gate diffs merge-base to HEAD and skips without origin/main, so it is vacuous on main. Fix: delete `:223-1021` and the `RETIRED_NAME` import at `:55` |
| E4 | CONFIRMED | `CT:sentry/layout/test_codemap_paths.py:23-60` (33 verbatim titles); used only by the test at `:81-85` | Fix: delete `KINDS` and that test; keep the header and path-exists tests |
| E5 | present, out of scope | `CT:sentry/layout/test_module_size.py:22-27` (report.py 2305, scan.py 1037, preflight.py 859, fit.py 818; all match `wc -l`), mirrored in `baselines/module-size.json` | Owner 2026-11-15: unchanged until V1. E2 must keep these pins exact |
| E6 | CONFIRMED | `CT:sentry/cli_text/test_one_error_emitter.py:33-39`, `cli_text/test_stdout_writes.py:45-51`, `defects/test_exit_code_owner.py:58-69`, `io_policy/test_config_load_choke_point.py:104-111`, `io_policy/test_environment_reads.py:32-38`, `io_policy/test_private_files.py:610-618` | Each pins `sentry_id`, `created_in` and (in five) the registry row, repeating `test_baseline_registry.py:42-45,63-64`. `test_exit_code_owner` also hand-lists the 3 keys a third time. The three `FromScan` guards also repeat the registry's scanner case. Fix: delete the six pins; keep the `exit` check from `test_private_files.py:615` |
| E7a | NOT CONFIRMED as described | `ET:sentry/test_perf_claim_provenance.py` | Its docstring (`:20-21`) says no doc has perf claims; 32 of 541 docs do. They pass because "provenance" is any of the words benchmark, calibration or measured anywhere in the file (`:49`). Live but weak. Owner: delete, or narrow it to published docs and fix the docstring |
| E7b | NOT CONFIRMED as described | `ET:sentry/test_wave_b_no_registry_version_literal.py` | Scans 8 files (6 in `E0_TEST_FILES` plus the `tests` lists of two Wave B manifests); 0 pins today. Wave B is not finished: E1.x, E2, E4, E6, E7 and E0r are "handoff not written" (`docs/ROADMAP.md:361-372`). Owner: keep until Wave B closes, or drop `E0_TEST_FILES` and its baseline now |
| E8 | CONFIRMED, V1+ | `ci_scan/` in both repos (`_shell_tokens.py` is 363 lines, byte-identical); engine `tooling/` 1,072 lines; CLI `tooling/` 882 | Out of row scope (the roadmap row places E8 in V1+) |
| K1 | CONFIRMED | `docs/diagrams/{classes_decoy,deps,packages_decoy}.svg` (215, 578 and 398 KB); generator `scripts/build_docs.py`; `.github/workflows/regen-diagrams.yml` commits as github-actions[bot] and pushes to main on `src/**` pushes (`:57-67`) | 12 of the 50 commits in the shallow history touch them (11 bot commits, 2026-11-15 to 2026-11-17). No freshness test, and no README, CODEMAP or docs index links to them. References to edit: `scripts/dev/gates.sh:18,63-65,318`, `CT:unit/scripts/test_gates_baseline_file.py:706-739`, `ci/install-policy.toml:6,22,48`, `ci/unlaned.toml:8`, `CT:sentry/tooling/test_ci_lanes.py:159-168`, `CT:sentry/test_ci_lock_installs.py:74,248`, `CONTRIBUTING.md:44` |

### Comment-history guard (REMEDIATION.md section 15 item 1)

None exists in either repo.

- **The CLI states the opposite policy.** `CT:sentry/cli_text/_banned_text.py:8-12`: "Comments
  and docstrings keep their ids because no user reads them." That sentence changes with the guard.
- Building blocks:
  - `CT:sentry/release/test_retired_name_residual.py`: tracked-file walk, `HISTORY` exclusions,
    and a per-path count in the `FromFile` JSON `retired-name-pending.json` with `max`. That is
    already the single-source shape E2 wants.
  - Its engine twin, `ET:sentry/test_no_residual_removed_surface.py`.
  - The ticket-id patterns in `BANNED_USER_TEXT`.
  - The docstring reader in `ET:sentry/test_methodology_citations.py`.
  - No existing scanner tokenizes comments, so the guard needs stdlib `tokenize`.

## Routing for the plan

- **Builds in these rows:** A2 (V1), A5 (unblocked; E5a merged), A1, A3, A4, A6 and A7 (dead
  code, R1), the `demo.py` copy of A8, A10 after the owner answer, B1 to B8 except B7b, D1 to
  D12 except D6b, E1, E2, E3, E4, E6, the comment-history guard, and K1.
- **Planned here, built by the row that holds the file:**
  - A8 `_execute.py` copy: `_execute.py` lane (SUB-RUN CLI half, CLI delivery, SAMPLE, LIB L5a,
    F23).
  - A9: `_render.py`, held by RESULT (row 62) in F29 C1 (row 66).
  - D1, D2 and D5: their `cli/run/` hunks (`_progress.py`, `_prepare.py`, `_errors.py`,
    `_execute.py`) go with their lanes, unless the plan shows those lanes are idle and takes the
    module.
- **Owner questions:**
  - A10: keep best-effort telemetry, or narrow the catch?
  - B8a: tombstone the reason identity, or delete it pre-GA?
  - B9: keep the platform and verification codes?
  - D6b: retire the old saved-scan shape once `demo` writes v1?
  - D13: remove `register_faker_provider_v2` from the public surface?
  - E7a and E7b: narrow, delete or keep?
- **Out of scope:** E5 (owner 2026-11-15), E8 (V1+), A11 (fails closed; narrowing is cosmetic,
  optional), and the adjacent `E:plan/_checks.py:638` catch (to check in the plan).
- **Overlap with 24zd and 24zf:** none of these items is a duplication-census item. The plan
  should still check `C:cli/exit_codes.py` (D2, D3), which 24zf CL3 rewrote as the
  exception-to-exit-code map.

## Not verified

- Nothing ran. Every mark is READ.
- Dynamic or string-built access to B1 names in the platform, beyond grep.
- Whether the 13 string-only verification codes resolve by name anywhere.
- Whether config validation refuses a target key with no output (`C:cli/io/_targets.py:487`).
- Whether moving D7 and D8 importers shifts the engine import-layer or package-fanout baselines.
- History before each shallow clone's 50-commit window.
- `[[RULES-REMOTE-2026-11-17]]`, named in the task brief, was not found in any of the four repos.
