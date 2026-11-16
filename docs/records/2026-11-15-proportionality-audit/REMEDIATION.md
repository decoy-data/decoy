# Remediation report: over-built code, tests and docs (engine and CLI)

Status: record. Roadmap placement: rows 24zi to 24zl (V1); the rest is classified in `docs/roadmap/post-1.0-plan.md` (1.x patch, or before 1.0 freeze for the public-surface items).

Date: 2026-11-15. Read at engine `64e9349b` and CLI `e716f445`. Engine main has since moved to
`6367af59` and CLI main to `de4cdeea`, so re-check every line number at build time. No code was
changed.

This is the working list for removing code, tests and docs that are larger than the need they
serve. Each package below says what the problem is, where it occurs, why it is bad, and the
recommended fix. The rules that now forbid each form are in `dev-rules/proportionality.md`
(dev-rules `master`, `7cf31fa`).

Path shorthand: `E:` is `decoy-engine/src/decoy_engine/`, `ET:` is `decoy-engine/tests/`, `C:` is
`decoy/src/decoy/`, `CT:` is `decoy/tests/`.

## 1. How this was produced, and its limits

Five read-only audit agents each took one slice: engine `execution/`, the rest of the engine
source, the engine tests, the CLI source, and the CLI tests plus docs. Each grepped for
candidates and read the code around them: about 225 files read in whole or part, the rest
covered by grep and a few AST scripts.

- **It is a sample, not a census.** Counts are what the agents found, not totals.
- **The platform repo was not available.** "No caller" means no caller in the engine or the CLI.
  Anything on the engine's public surface must be checked against the platform before deletion.
- **Git history was shallow.** Both clones held 50 commits covering about three days, so churn
  figures are indicative only.
- **Nothing was run.** No test suite was executed and no failure was reproduced.
- **Five claims were re-read by hand** and held: `E:execution/_chunked_adapter_gate.py`, the
  unused operator Protocols, `MemoryMonitor`, the `C:_native_gate.py:482` signature probe against
  the `decoy-engine==0.26.0` pin, and the reviewer-name count in engine source.

Confidence in the tables: **H** means the agent verified it by grep or by citing the
guaranteeing line. **M** means likely and partly verified. **L** means a suspicion.

Not read: most of `E:execution/out_of_core/` internals, `E:execution/native/protocol/`, the
engine parity, property, security and privacy tests, `C:distribution/` beyond four files, most
of `C:cli/io/` internals, and docs content (docs were counted, not reviewed).

## 2. Size of the problem

| Measure | Engine | CLI |
|---|---|---|
| Source lines | 187,992 | 35,800 |
| Test lines | 440,261 (2.34x source) | 83,659 (2.3x source) |
| Guard-test lines | 26,757, plus 36 baseline JSON files | 20,039 (56% of source) |
| Docs lines | 108k (57% of source) | 23.1k, plus 12.2k of committed SVG |
| Lines added, last 49 commits (source : tests) | 1 : 3.2 | 1 : 2.5 |
| Prose per code line in `execution/` | 0.59 | - |

In the CLI, 27 of the last 49 commits carried no code: 14 regenerated diagrams and 13 were docs
bookkeeping.

## 3. Packages and suggested order

| Package | What | Items | Risk | Order |
|---|---|---|---|---|
| A | Quiet fallbacks (possible defects) | 9 | Behavior change | 1: verify, then fix what is real |
| B | Public-surface leftovers | 9 | Needs platform check | 2: before REL-GATE freezes the surface |
| C | Dead code with no production caller | 17 | Low | 3 |
| D | Shims, re-exports and old-engine probes | 13 | Low | 4 |
| E | Guard-test bookkeeping | 8 | Low, cuts per-change churn | 5 |
| F | Comment and docstring history | 2 sweeps | None to behavior | 6 |
| G | Defensive code for states that cannot occur | 9 | Low to medium | 7 |
| H | Mechanical size-cap splits | 5 | Low, wide diffs | 8 |
| I | Test reductions | 12 | Coverage must be shown unchanged | 9 |
| J | CLI thin-wrapper violations | 6 | Medium | V1+ unless a V1 row touches the file |
| K | Docs and process | 4 | None | Any time |

Each package still runs the dev loop. The PLAN re-checks lanes: this report did not check which
files a live roadmap row holds.

## 4. Package A: quiet fallbacks (possible defects)

**What it is.** A `try/except` or default that turns a failure into a different, quieter result.
The run continues and reports success.

**Why it is bad.** These can produce wrong output with no signal, which is worse than a crash
for a masking tool. They also hide bugs in the code they wrap: the native lane fallback means a
native bug never surfaces.

**Recommended solution.** Check reachability first, as the duplication census did for its
packages A and B. For each confirmed item, let the error propagate or catch only the named
error types. A confirmed item that can change output meets the V1 bar.

| Id | Where | What happens | Fix | Conf |
|---|---|---|---|---|
| A1 | `E:transforms/text_mask.py:414` | A Faker method failure is swallowed and `fake.name()` is substituted for any detector type | Let it raise | H |
| A2 | `E:transforms/geo_generalize.py:280` | A shipped reference table that fails to load becomes a warning plus `{}`; the state fallback is silently off | Raise | H |
| A3 | `E:plan/_seed_envelope.py:127` | An unknown provider is swallowed "so a bug in the check-runner doesn't crash the planner" | Let it raise | H |
| A4 | `E:plan/checks/_generate_columns.py:355` | A bad expression becomes an empty reference set | Raise a coded error | M |
| A5 | `E:execution/_unified_slice.py:359` | Any exception in the default-on native lane logs a class name and reruns on pandas | Catch the coded decline errors only | M |
| A6 | `E:execution/physical/_compiler.py:444` | `except Exception: return None` around `post_scan_resident_for` | Catch the named error | M |
| A7 | `C:cli/init.py:327-330` | `except Exception: return` around importing yaml and the engine skips scaffold validation | Import normally | H |
| A8 | `C:cli/run/_execute.py:318-320`, copy at `C:cli/demo.py:284-286` | A result with no `outputs` writes nothing and reports success | Read `result.outputs` directly | M |
| A9 | `C:cli/run/_render.py:53-61` | `_next_hint_for_run` reads a key the V2 schema does not have inside try/except-pass, so it always returns None | Delete | H |

Lower value, same form: `E:context.py:161-226` (five `emit_*` helpers each with
`except Exception: pass`), and `E:execution/_chunked_fk_dtype_safety.py:132,164,174,183` (broad
catches where three named errors would do).

## 5. Package B: public-surface leftovers

**What it is.** Names on the engine's public surface that nothing in the engine or CLI uses:
kept bindings, deprecated functions, parameters nobody passes.

**Why it is bad.** REL-GATE (roadmap row 93) freezes the public surface and makes the
compatibility contract binding. Every unused public name that survives the freeze becomes a
promise that needs a migration to remove. Today it is a changelog line.

**Recommended solution.** Check each name against the platform repo. Delete what has no
consumer there. For any the platform does use, record the consumer next to the name.

| Id | Where | What | Conf |
|---|---|---|---|
| B1 | `E:__init__.py:252-272,345` | `_F9_KEPT_BINDINGS`: 17 names "kept for backward-compatible attribute access" beside `identifiers.py` | H |
| B2 | `E:internal/crypto.py:18` | `deterministic_hash`: "kept for backwards compatibility", emits `DeprecationWarning`, no source caller | H |
| B3 | `E:context.py:248-330` | `ExecutionContext.resolve_connector`, `captured_outputs`, `pool_resolver`, `column_relationships`, `export()`: left from the deleted V1 graph runner | H (engine and CLI) |
| B4 | `E:context.py:230` | `TelemetryClient`: "Published for forward compatibility; unused today" | H |
| B5 | `E:context.py` | `emit_fidelity`, `emit_quarantine` exported and test-only; `emit_step(node_id=)` never passed | H |
| B6 | `E:execution/_events.py` | `ExecutionEvent` exported, never constructed | M |
| B7 | `run_pipeline` keywords | `progress_interval_s`, `secret_registry`, `secret_cache_policy` have no keyword call site; five kill switches (`chunked_dispatcher_enabled`, `multi_table_dispatch_enabled`, `stream_chunked_output`, `use_byte_estimate_routing`, `use_probe_routing`) are passed only by tests | M |
| B8 | `E:validation_result.py:367`, `E:_progress_events.py:598` | `FK_SELF_REFERENCE` "legacy" alias with no reader; `event_to_legacy_dict` test-only | H, M |
| B9 | `E:reasons/platform/_part1.py` and others | 68 of 69 platform codes, 12 of 28 verification codes, 9 runtime codes unreferenced in engine and CLI | M (likely the platform wire contract) |

## 6. Package C: dead code with no production caller

**What it is.** Modules, classes and functions whose only consumer is their own test, or
nothing at all. Much of it was built ahead of a caller that never arrived.

**Why it is bad.** It is read, maintained, size-capped and tested as if it were live. Tests of
unwired code are not evidence the product works. About 2,600 engine test lines exist only for
code no production path reaches.

**Recommended solution.** Delete the code and its tests together. Version control keeps it. For
planned work that will be wired soon, park it on its branch until the command that uses it lands.

| Id | Where | What | Lines | Conf |
|---|---|---|---|---|
| C1 | `E:internal/memory.py`, `ET:unit/internal/test_memory.py` | `MemoryMonitor`, no importer; test written because the module "was at 0% coverage" | ~100 + 269 | H |
| C2 | `E:internal/logging.py:176` | `ProgressLogger`, no callers and no tests | ~110 | H |
| C3 | `E:internal/base.py:8` | `ConfigValidator` ABC, zero subclasses | small | H |
| C4 | `E:execution/physical/_protocols.py:58-137` | Five operator Protocols, kept "so a later compiler has a named shape" | ~80 | H |
| C5 | `E:execution/physical/drivers/_chunked.py`, `_sequential.py` | Pass-through adapters instantiated only in tests | ~270 | H |
| C6 | `E:execution/native/_route_diagnostics.py`, `ET:native/test_c1_*.py` | "standalone, not wired into `_dispatch.py`" | 664 test | H |
| C7 | `E:detection/_ner_rate.py` and four test files | Imported nowhere in source | 403 test | H |
| C8 | `E:execution/native/_pool_quality.py`, `ET:native/test_pool_quality.py` | States it is "NOT wired" | 481 + 1,234 | M (platform caller claimed) |
| C9 | `E:transforms/date_shift.py:131` | `DateShiftStrategy`, V1 class never instantiated; only two helpers are used | 155 | H |
| C10 | `E:internal/base.py:42`, `E:transforms/base.py:14` | Two-level ABC stack with one live subclass, `FormulaStrategy` | ~265 to one function | H |
| C11 | `E:providers_v2/mimesis/_parity.py` | Evaluation harness in source, called only from tests | 202, move to tests | M |
| C12 | `E:execution/_chunked_text_mask.py:118` | `reject_unsafe_text_mask_source_dtype`, "kept for direct unit tests" | small | H |
| C13 | `C:cli/library/` | 9 files with no importer outside the package, 12 test files | 1,456 + tests | H (planned work, row LIB) |
| C14 | `C:ui/progress.py:57-88` | `progress_bar`, `_BarHandle`: no caller in source or tests | ~30 | H |
| C15 | `C:_env_flags.py:53`, `C:distribution/installer.py:677` | `env_int`, `prune_old_versions`: tests only | small | H |
| C16 | `C:cli/demo.py:292-515` | Hidden `--ref` and `--rows` flags that always print "deferred"; `_generate_ref_datasets` never called | ~80 | H |
| C17 | `C:cli/scan.py:300-382` | Pandas loaders used only by `api.scan` | ~80 | H |

Smaller items of the same form: five `composite_*` factories that only forward keyword
arguments (`E:generation/composite/_person.py:245` and siblings), `C:cli/setup/_sections.py:16-31`
(a Protocol and registry with one implementation), and the unused `NativeOp` slots at
`E:execution/_sequential_native_group_key.py:73-92`.

## 7. Package D: shims, re-exports and old-engine probes

**What it is.** Code that keeps an old import path, an old format or an old engine version
working. Three forms: re-exports left after a module was split, readers for formats written
before a rename, and runtime checks for engine features that the exact pin already guarantees.

**Why it is bad.** Both repos have a hard-delete rule before GA and this code breaks it. The CLI
pins `decoy-engine==0.26.0`, so every "older engine" branch is unreachable and untestable. The
re-exports mean one name has two import paths, and callers drift between them.

**Recommended solution.** Point importers at the real module and delete the re-export. Replace
each capability probe with a plain import or a plain keyword. Delete the old-format readers
unless a named consumer has such files.

| Id | Where | What | Conf |
|---|---|---|---|
| D1 | `C:_native_gate.py:482-507` | `inspect.signature(run_pipeline)` to see whether `unified_slice_enabled` exists | H |
| D2 | `C:cli/run/_prepare.py:403-415`, `C:cli/tokenize.py:296-308`, `C:api.py:135-138`, `C:cli/run/_errors.py:115-136`, `C:cli/exit_codes.py:270-281`, `C:_mask_secret.py:72-78` | `try/except ImportError` for `keyprovider` and `ExecutionError`, plus the `OLD_ENGINE_*` texts | H |
| D3 | `C:cli/preflight.py:397,552`, `C:_native_gate.py:139`, `C:cli/exit_codes.py:232-235` | `hasattr`/`getattr` for names that exist in 0.26.0 | H |
| D4 | `C:cli/report.py:889-894` | `ImportError` guard for pandas, a hard dependency | H |
| D5 | `C:cli/run/_execute.py:350-362` | Report keywords omitted "so the call shape stays valid on an older engine" | H |
| D6 | `C:cli/io/_scan_set.py:35-57,152-208`, `C:cli/io/_targets.py:193` | Readers for pre-`scan-set/v1` saved scans and pre-CLI-FMT manifests | M |
| D7 | `E:execution/out_of_core/_source.py` | Re-export shim with 10 importers; its docstring says no shim is owed | H |
| D8 | `E:execution/_mem_estimate.py:84-93`, `_planner_columns.py:3`, `_sequential_order.py:3`, `_chunked_fk.py:8`, `_pipeline_routing.py:22`, `native/_dispatch.py:51,81` | Old module re-exports names "so existing imports keep working" after a split | H |
| D9 | `E:quality/dp_budget.py:499-520` | Module `__getattr__` lazy re-export so an old import path survives a split | H |
| D10 | `E:execution/_fk_key_compat.py` | 23-line module for a one-line delegate | H |
| D11 | `E:execution/_chunked_adapter_gate.py:13` | Three-parameter predicate that returns `True` unconditionally, one caller | H |
| D12 | `E:context.py:143` | `TypeError` fallback for "older JobLogger implementations" | H |
| D13 | `E:providers_v2/_faker_adapter.py:84,251` | V2 custom-provider table kept "until S9 removes the V1 stack", one test caller | M |

## 8. Package E: guard-test bookkeeping

**What it is.** Guard tests whose facts are kept by hand in several places, or which pin a fact
that ordinary changes move.

**Why it is bad.** These make every change pay a tax that protects nothing. The list of guard
files changed in 14 of the last 50 engine commits; 14 of 18 CLI feature commits edited the guard
directory. A pin that people edit on every change stops being read. The pins also fail at their
job: `decoy/CODEMAP.md:48` says "frozen at 30 modules" while the allowlist says 29.

**Recommended solution.** Keep each pinned fact in one place and derive every list that can be
derived. Keep the guards that pin a real invariant (import direction, secret handling, value-free
errors). Remove the ones that pin an incidental fact.

| Id | Where | What | Fix | Conf |
|---|---|---|---|---|
| E1 | `ET:sentry/test_sentry_manifest.py:26`, `CT:sentry/test_sentry_manifest.py:26` | Hand lists of 106 and 72 guard paths | Glob the directory, plus the few outside paths | H |
| E2 | Both repos: in-code constant, `baselines/*.json`, `sentry_registry.toml` row, `_baseline_sources.SOURCES` | Every allowlist is kept four times; keys are `file::function::call::ordinal`, so a code move needs `moved_from` edits | Make the JSON the only source | H |
| E3 | `ET:sentry/test_physical_seam_disconnection.py:290` | "`execution/` byte-identical to origin/main" with ~720 lines of permitted-diff allowlist; every change to `execution/` must enrol | Keep the import-direction tests at lines 165-212, delete the diff gate | H |
| E4 | `CT:sentry/layout/test_codemap_paths.py:23` | `KINDS` pins every CODEMAP row title verbatim | Keep the path-exists test, drop `KINDS` | H |
| E5 | `CT:sentry/layout/test_module_size.py:22` | Exact line counts for four legacy files, edited for diffs such as 882 to 879 | Use a ceiling. This reverses the owner rule of 2026-11-10 for legacy files, so it needs an owner decision | H |
| E6 | Six CLI files, for example `CT:sentry/defects/test_exit_code_owner.py:58` | Per-guard baseline header pins repeat `test_baseline_registry.py:46` | Delete the six | H |
| E7 | `ET:sentry/test_perf_claim_provenance.py:20`, `test_wave_b_no_registry_version_literal.py` | A forward-looking guard with nothing to guard, and one tied to a finished migration | Delete both | M |
| E8 | `ET:sentry/ci_scan/`, `CT:sentry/tooling/` | ~2,100 lines of bespoke shell parser, vendored across both repos, to check that CI installs use lock files; it polices 503 lines of workflow YAML | Replace with a plain scan for an install with no lock | M |

## 9. Package F: comment and docstring history

**What it is.** Comments and docstrings that record task ids, review rounds, dates and reviewer
names, or that are several times longer than the function they describe.

**Why it is bad.** Both `CLAUDE.md` files already forbid it. A reader must get through review
history to find the invariant. The history is also stale: `E:providers_v2/_real_registry.py:1-18`
says "Default at S7 close: EMPTY" above a populated set. Version control already holds it.

**Where.**

- Engine `execution/`: 146 files carry task or review history, with 18.3k docstring lines and
  6.2k comment lines against 41.5k code lines.
- Rest of the engine source: 548 tagged lines in 178 files, and 32 lines that name people.
- Engine tests: 156 files name reviewers, and 258 test files are named after sprint or task ids.
- CLI source: 60 history markers. CLI tests: 114 of 354 files.

Worst cases: `E:execution/_chunked_fk.py:82` (121-line docstring, 16-line body),
`E:execution/out_of_core/_memory_estimate.py` (323 prose lines, 59 code lines),
`C:cli/validate.py:1-41` (a 40-line changelog as module docstring),
`ET:perf/test_governor_reroute_completion.py:1` (111-line docstring).

**Recommended solution.** Two steps, in this order.

1. Add a guard that fails on new history markers in comments (task ids, review rounds, dates,
   reviewer names), with a baseline of today's files. This stops growth while other rows keep
   adding code.
2. Sweep the baseline down package by package. Keep the sentence that states the invariant and
   delete the history. This changes no behavior, so it can go between other merges.

## 10. Package G: defensive code for states that cannot occur

**What it is.** Checks on values that the types or the caller already guarantee: `None` and
`isinstance` checks, `getattr` with a default on a declared field, branches the code itself
labels unreachable.

**Why it is bad.** Each one tells the reader a state is possible when it is not. The
`# pragma: no cover` marks (99 in `execution/`) hide them from coverage, so nobody notices they
never run. Some of them also swallow a real error if the "impossible" state ever does occur.

**Recommended solution.** Replace an unreachable guard with one `assert` where a type checker
needs narrowing, and delete the rest. Fix the test doubles that the `getattr` defaults exist for.

| Id | Where | What | Conf |
|---|---|---|---|
| G1 | `E:execution/physical/_shadow_operators.py:195-294` | ~100 lines of `if X is None: raise AssertionError`, self-labelled "C0 always binds this" | H |
| G2 | `E:execution/_strategies/_hash.py:64`, `_fpe.py:181`, `_faker.py:113`, `_categorical.py:266`, `_adapter.py:499,508`, about 30 sites | `getattr(ctx, field, default)` on `StrategyContext`, which declares every field; the reason given is test doubles | H |
| G3 | `E:execution/physical/_shadow_full_frame.py:183`, `_shadow_generation.py:147`, `_shadow_coordinator.py:260` | `last_invocation is None` checked right after a `run()` that sets it | H |
| G4 | `E:execution/_planner_columns.py:14-18` and others | 117 `isinstance(x, dict)` and 172 `.get(...) or []` on a config that `_pipeline.py:166` says is already validated | M |
| G5 | `E:execution/_pipeline.py:365-370` | Four `getattr(decision, ..., default)` on the `RouteDecision` returned one line earlier | M |
| G6 | `E:generation/pool/_pool_adapter.py:152` | Re-checks what `ProviderSpec._validate` already guarantees | H |
| G7 | `E:profiling/_k_anonymity.py:123`, `E:profiling/profiler.py:390` | Filters names against the columns they came from; accumulators for a "continue on error" mode that does not exist | H |
| G8 | `E:generation/_fidelity_gate.py:115`, `E:generation/statistical/_sample.py:270,544`, `E:plan/_serialize.py:477` | "unreachable through compile_plan; defensive only" branches that return empty | M |
| G9 | `C:cli/run/_prepare.py:74,309` | A `raw_cfg` parameter "accepted (and unused) for call-site symmetry"; an unused import kept "at its original point" | H |

## 11. Package H: mechanical size-cap splits

**What it is.** A module cut at a line count to pass the size guard, not along a reason to
change. 41 files in `execution/` say they exist for the cap.

**Where.** `E:execution/_chunked.py` has 20 `_chunked_*` siblings and `_pipeline.py` has 15.
`E:reasons/*/_part1.py`, `_part2.py`, `_part3.py` are one flat catalog cut by line count. Six
engine modules sit at exactly 600 lines. Small cases: `E:execution/native/_chunked_preflight_wiring.py`
(44 lines), `_pipeline_routing_samples.py` (56), `_chunked_oracle_rows.py` (13 lines, one caller).

**Why it is bad.** The flow of one concern is spread over many files, and each split leaves a
re-export shim (package D). The cap is met and the reader is worse off.

**Recommended solution.** Do not re-merge wholesale. Fold the one-function modules back into
their caller where the caller has room. Let the `reasons` catalogs be data files exempt from
the cap, or one module per namespace. For the rest, apply the new rule in
`dev-rules/architecture.md` going forward: split along a reason to change and leave no re-export.

## 12. Package I: test reductions

**What it is.** Tests that cannot fail for a reason a user would care about, the same case
tested at several layers, and same-shape tests that are not parametrized.

**Why it is bad.** Tests are 2.3 times the source and growing faster than it. Each extra test
costs suite time and breaks on refactors without catching defects. 533 engine test files import
private names, so internal moves break tests that guard no behavior.

**Recommended solution.** For each item, show coverage and mutation score for the unit are
unchanged after the cut, per `dev-rules/testing.md`.

| Id | Where | What | Fix | Conf |
|---|---|---|---|---|
| I1 | `ET:unit/test_lark_parser.py:26`, `ET:unit/test_checksums.py:38` | 45 and 38 same-shape tests | One parametrized table each | H |
| I2 | `ET:unit/execution/test_sequential_run_kills.py:1203,1230,1254` | Repeats `ET:integration/test_quarantine_commit_fate.py:414,464,641` | Keep one layer | H |
| I3 | 24 `*kills*` files, 11,235 lines | Keyed to mutant ids | Fold into base files, drop repeats | M |
| I4 | `ET:unit/profile/test_dataclass_shapes.py:23` | Asserts field-name sets and frozen-ness | Delete | H |
| I5 | `ET:unit/test_scan_eval_bands.py:51`, `ET:unit/execution/test_out_of_core_public_api.py:45` | A constant equals its literal | Keep the behavior tests only | H |
| I6 | `ET:native/test_operator_tables_snapshot.py` | 249-line literal copy of pre-refactor tables | Retire | M |
| I7 | `ET:physical/test_bench_compare_harness.py`, `test_bench_gen_pool_harness.py` | 2,090 lines testing offline benchmark scripts | Trim to a smoke test | M |
| I8 | CLI exit codes: 9 test files, 1,158 lines, for a 318-line module | Precedence asserted identically in three places | One doc-agreement test | H |
| I9 | `CT:e2e/test_s1_deletions.py:31`, `test_s4b_consolidation.py:20,34`, `test_stateless_cli.py:98` | "Removed command is No such command" | One parametrized test, or delete | H |
| I10 | `CT:e2e/test_theme.py:54`, `CT:unit/test_ci_docs.py:49` | A dict equals a copied literal; strings appear in a doc | Delete | H |
| I11 | 86 CLI test files | Each builds its own v2 pipeline dict (159 occurrences) | One shared builder in conftest | M |
| I12 | `CT:unit/scripts/test_gates_*.py` | ~1,770 lines for a dev-only runner script | Trim | M |

### How to tell which tests earn their place

There is no count that is "too many". A test earns its place when it can fail because behavior a
user depends on broke, and no other test at that layer already fails for the same break. Three
measurements answer that, in order of strength:

1. **Mutation testing.** Change the source (flip a comparison, drop a line) and see which tests
   fail. A test that kills no mutant that another test does not also kill is redundant for that
   unit. The engine already runs `mutmut`. To check a proposed cut: record the mutation score for
   the unit, remove the tests, run again. An unchanged score means the removed tests were not
   doing anything the rest did not do.
2. **Per-test coverage.** `coverage.py` with `dynamic_context = test_function` records which test
   ran each line. A test whose lines and branches are all covered by other tests is a candidate
   for removal; mutation testing then confirms it.
3. **Failure history.** From CI results, list tests that have only ever failed in a change that
   also edited the test. A test that breaks on refactors and never on defects has negative value.

Mutation testing does not judge contract, parity or end-to-end tests: the only test at a real
boundary stays even if a unit test kills the same mutants. Signs that the suite as a whole is
past the useful point: test lines grow faster than source lines, most changes edit tests without
changing behavior, and the suite time grows while the mutation score does not.

## 13. Package J: CLI thin-wrapper violations

**What it is.** The CLI is meant to be a thin wrapper, but some commands re-implement engine
behavior or pass through many internal layers.

**Why it is bad.** Two copies of engine logic drift. `C:api.py` says it uses "the same engine
path" as the CLI and does not. A successful `decoy run` crosses about 18 CLI files that share a
~70-field mutable `RunContext`.

| Id | Where | What | Fix | Conf |
|---|---|---|---|---|
| J1 | `C:cli/demo.py:199-289` | Hand-composes profile, compile, registry, graph and adapter run, with private copies of the load and write helpers | Call `run_pipeline` through the shared helpers | H |
| J2 | `C:api.py:101-166` | Three self-described "Port of run.py's ..." copies; `api.scan` calls `profile_columns` while the CLI calls `scan_sources` | Point `api.scan` at `scan_sources`, share the helpers | H |
| J3 | `C:_native_gate.py:212-303` | 90-line mirror of the engine's unified-slice admission rules | Ask the engine | M |
| J4 | `C:cli/report.py:835-1020` | Data-level diff statistics computed in the CLI | Move to the engine or call it | M |
| J5 | `C:ci/engine_logging.py:28-39` | Imports `decoy_engine.internal.logging` and resets a private global | Use a public hook | M |
| J6 | `C:cli/run/` | Chunked refusals split between `_prepare.py:303-460` and `_execute.py:152-230`; `exit_codes.usage_error_types` reaches into five private run modules | Plan with the next row that touches `run/` | M |

These sit in hot lanes (`_execute.py`, `_flow.py`, `_errors.py`, `_render.py`), so they are V1+
unless a V1 row already owns the file.

## 14. Package K: docs and process

| Id | Where | What | Fix |
|---|---|---|---|
| K1 | `decoy/docs/diagrams` | Three SVGs (12k lines) committed after every source push: 14 of 49 commits | Publish as a CI artifact |
| K2 | `decoy/docs/plans` | At least 10 of 21 plans are shipped work | Archive per `dev-rules/documentation.md` |
| K3 | `decoy-engine/docs/plans` | 304 plans, at least 125 with a terminal status; the archive holds 18 | Archive |
| K4 | Shipped state | Recorded in `ROADMAP.md`, `RECENTLY-SHIPPED.md`, `docs/roadmap/`, `docs/records/` and `docs/archive/shipped-*.md` | Owner decision: one place |

## 15. Guards to add so it does not grow back

The audit's main lesson is that two of the most widespread forms were already forbidden in
prose and were broken throughout. Each of these is a scanner with a baseline of today's sites:

1. **Comment history.** Task ids, review rounds, dates and reviewer names in comments and
   docstrings (package F, step 1).
2. **Re-export shims.** A private module that imports a name only to re-export it.
3. **No production caller.** A source module or public name referenced only from tests.

Build them from the existing guard helpers. Do not add a fourth copy of any allowlist
(package E2 should land first, or these should use the single-source form from the start).

## 16. Leave alone

These looked over-built and are justified.

- **Key scrubbing.** `except BaseException: del key; raise` in determinism, kernel and context
  keeps key material out of traceback frames.
- **Value-free errors.** Raising outside the handler in `C:cli/run/_vault.py:68-77`,
  `C:cli/io/_scan_set.py:130-136`, `E:execution/pipeline/_post_scan.py:178-212` and
  `_when_gate.py:169` keeps paths and cell values out of exception chains.
- **Compiled-companion loaders.** The broad catches in `E:execution/native/_crypto_ext.py`,
  `_index_ext.py`, `_fpe_ext.py` and `_group_key_ext.py` wrap an ABI check and a known-answer
  self-test.
- **Public re-export modules.** `E:providers.py`, `identifiers.py` and `generation/pinned.py` are
  the public face of the `internal/` boundary.
- **`E:fileaccess/`.** Seven Protocols, but with several real implementations at a security
  boundary.
- **Tiny leaf modules that break import cycles.** `E:_error_base.py`, `_execution_error.py`,
  `_field_names.py`, `E:execution/_stitch.py` (only its docstring is bloat).
- **Tests.** `ET:unit/generation/pool/test_canonicalize.py` (byte literals are the determinism
  envelope), `ET:unit/execution/test_r3_public_signature_freeze.py`,
  `ET:integration/test_quarantine_commit_fate.py`, the wire-version constant pins,
  `CT:e2e/test_vault_commit_order.py`, `CT:unit/test_cli_surface.py`, and the security and leak
  guards.
