Status: record

# Engine clean-architecture review (2026-11-21)

Report-only review of `decoy-engine` at origin/main `54db2e5f2` (#748). No file in any repo was changed. Method: the 7-row Quick Diagnostic from the `clean-architecture` skill, scored 0 to 10. Findings are tagged with the V1 bar: **V1** means function break, data loss or an accidental value leak. **QA** means structure, for the QA phase or V2-LOG.

Related: [[decoy-single-roadmap]], [[develop-correctly-registries-and-sizing]], [[best-practice-becomes-a-sentry]], [[v1-bar-blocking-criteria]].

## Score

**5 / 10, band 3-5** ("framework or persistence dictates structure").

3 of 7 diagnostic rows pass. That puts the engine at the top of the 3-5 band. The strong points: the policy leaves (`reasons`, `contracts`, `expressions`, `config`, `delivery`) are clean, cloud SDKs stay in `connectors`, and the engine never knows it is driven by a CLI. A working layer sentry keeps the debt from growing. The weak points are a dependency cycle through the middle of the engine, strategy policy that lives inside the execution layer, and a dataframe library inside the strategy rules.

No finding meets the V1 bar. All findings are QA.

## The 7 checks

| # | Diagnostic row | Result | Evidence | Fix |
|---|---|---|---|---|
| 1 | Can business rules be tested without DB, files or framework? | Pass | `reasons` imports only `_error_base`. 0 of 12 `tests/unit/reasons` files use tmp_path, Parquet or pandas. 8 of 32 in `tests/unit/plan`. `config` imports one pyarrow module (`config/_generate_type_checks.py:24`). Caveat: `plan/_compile.py:55`, `plan/_generation.py:180` and `plan/checks/_lookup_tables.py:24` read files through `fileaccess` during compile. | Optional: pass snapshot and lookup bytes into compile from the caller, so compile does no reads. |
| 2 | Do all source dependencies point inward? | Fail | 30 measured back edges are on the `.importlinter` ignore list. Policy reaching outward: `plan/_checks_top_code.py:32` and `plan/_checks_bucketize.py:28` import `_PRESETS` from `execution/_strategies`. `plan/_checks_correctness.py:67` imports `execution.out_of_core._mask.masked_output_type`. `plan/_seed_envelope.py:15` imports `execution._technique_class`. `profile/_declared_columns.py:77,156` imports `execution._transforms` and `execution._pipeline_context`. `config/_generate_unique.py` imports `generation.pool._capacity`. | Move strategy facts (presets, technique class, output type rule) down into `contracts/`, next to `strategy_requirements.py` and `distribution_behavior.py`. Then delete the matching ignore lines. |
| 3 | Can the database or store be swapped without touching business logic? | Pass | `connectors/` is imported by one engine module only (`profile/_cloud_readers.py:28`). boto3, GCS and paramiko imports appear only in `connectors/_clients.py` and `connectors/sftp.py`. Connectors depend on `sdk/` protocols. DuckDB goes through one factory, `connect_duckdb`. | Small: `profile/_cloud_readers.py` builds S3 and GCS clients itself (lines 209, 361). Put a ranged-read port in `sdk/` and inject it. |
| 4 | Are use cases independent of the delivery mechanism? | Pass | No click, typer, argparse or rich imports in `src/decoy_engine`. Exit codes are caller data: `run_result/_outcome.py:3` takes an injected `exit_map`. | None. |
| 5 | Is the framework confined to the outer circle? | Fail | pandas is the strategy framework. 10 of the `transforms/` modules that CODEMAP calls "core logic" take pandas objects (`date_shift`, `geo_generalize`, `joint_mask`, `formula`, `bucket_perturb` and 5 more). All 28 handlers in `execution/_strategies` import pandas. The Arrow `kernel/` covers only hash, redact, truncate and passthrough. The other strategies exist as pandas code plus separate Arrow or native copies. | Over time, move each strategy's rule to a pure function on Python values or Arrow arrays (the `kernel/` shape). Keep pandas as one adapter. This is long-term direction, not a QA task. |
| 6 | Is the component graph cycle-free? | Fail | AST scan of top-level packages. Module-level imports only: one strongly connected group of 11 packages (`execution, generation, generators, kernel, plan, profile, profiling, providers_v2, relationships, transforms, verification`). With function-level imports: one group of 27 packages. Examples: `plan <-> execution` (5 and 137 edges), `plan <-> generation` (17 and 19), `plan <-> transforms` (16 and 11), `generation <-> execution` (8 and 109), `fileaccess <-> execution` (1 and 50). | Most of these are siblings in the same tier, which the layer contract allows. Break the `plan <-> execution` and `plan <-> generation` loops first (see finding 1). Move shared error types such as `plan._errors.PlanCompileError` (imported by `transforms/joint_mask.py:62`, `relationships/_namespace.py:36`) to a leaf. |
| 7 | Does one composition root wire all dependencies? | Fail | `run_pipeline` with `build_run_context` (`execution/_pipeline_context.py`) is the main root, and `pipeline/_routing_facts.build_routing_facts` is the shared routing-facts owner. But `execution/capacity.py` and `execution/_job_estimate.py` each run `profile_source`, `compile_plan` and `decide_execution_route` again, with flags that differ from a real run (their docstrings say so). Public entries that wire their own graph: `run_pipeline`, `select_execution_adapter().run`, `generate_tables`, `run_mask_chunked`, `run_fk_out_of_core`, `run_subset`, `run_pipeline_isolated`. | Make `capacity` and `_job_estimate` call `build_routing_facts`, with an explicit "estimate" mode, instead of their own sequence. Mark which entries are the supported roots. |

Graphify note: `graphify query` on the cached engine graph (built 2026-11-21 16:49) returned doc and symbol nodes, not import edges. The edge counts above come from an AST scan of `src/decoy_engine`, with `TYPE_CHECKING` imports left out.

## The layer sentry (`tests/sentry/layout/test_import_layers.py`)

**Why our runs deselect it.** The test is not broken and the rule is not being avoided. It is built to run only in its own venv:

- The test needs `import-linter==2.15`, which is the separate `layers` extra in `pyproject.toml` (line 224). The certified `.venv` does not get it on purpose, so the certified profile stays exact.
- Without import-linter the test fails closed with "import-linter is not installed" instead of skipping (test docstring, `INSTALL` message). So any run in the normal venv shows about 10 failures from this file. The wiki notes T0942 and T0998 record exactly this.
- `scripts/dev/gates.sh --steps layers` syncs `.venv-layers` and runs only this file there. Every other gates.sh route ignores the path (gates.sh lines 68, 288). CI does the same: `ci.yml` lines 196 and 204 use `--ignore`.
- It was added in #480 (2026-11-11, LAYOUT E3).

**Where it does run.**

- `gate-selfhosted.yml`, gate shard 1: gates.sh with its default step list, which includes `layers`. This is the merge gate behind the `engine-gate/verdict` status, so a branch dispatch does check the contract.
- `ci.yml` job `layers-gate`: `if: github.event_name != 'pull_request'`, so only the nightly schedule and manual dispatch. It passed on the 2026-11-20 and 2026-11-21 nightly runs.
- It does not run in the fast tier on every push (that tier runs `env,ruff,format,mypy,sentry`, and the sentry step ignores this file), and not in PR CI.

**What it reports now.** Run once through `vm-run engine` (Dell node, tree `54db2e5f2`): `scripts/dev/gates.sh --steps layers` gives **PASS, 15 passed, 0 failed**. The contract is kept, the snapshot matches the config, and all meta-tests (seeded violations go red) pass. The ignore list has 30 lines. It was 32 at #480 and has been 30 since #650, so the ratchet works but the debt has not gone down in 10 days.

**Gap in what it checks.** The contract is a measured order of today's imports, not a policy direction. `connectors` is in tier 4 and `io` and `fileaccess` are in tier 5, below `plan` (tier 3). So a new `plan -> connectors` or `plan -> io` import would pass the sentry. Also, `kernel` (described as backend-neutral) sits in tier 2 next to `execution`.

**Recommended fix.**

1. Keep the isolated venv. It is a deliberate choice, not a bug.
2. Give our ad-hoc runners the same rule CI uses. Use `--ignore=tests/sentry/layout/test_import_layers.py` in vm-run and T1 command templates, and add `--steps layers` when a slice touches imports, so nobody reads the 10 "not installed" failures as real reds.
3. Add a second import-linter contract of type `forbidden`: the policy packages (`plan`, `config`, `reasons`, `contracts`, `expressions`, `relationships`, `delivery`, `determinism`) must not import `connectors`, `io`, `publication`, `vault`, `unmask` or `execution`. Seed it with today's edges as ignores, so it only ratchets.
4. Optional: run `--steps layers` in the hosted fast tier. It costs one small venv sync and catches a break at push time instead of at gate dispatch.

## Findings, ranked

1. **QA. Strategy policy lives in the execution layer.** Presets (`execution/_strategies/_top_code.py`, `_bucketize.py`), the GDPR technique class (`execution/_technique_class.py:73`, a pure table with no engine imports), the output-type rule (`execution/out_of_core/_mask.py`) and the public `strategy_catalog` (`execution/_strategies/__init__.py:124`) are all in tier 2. `plan` reads them through ignored back edges, and `validation/starter_review.py` has to sit in the execution tier only to read the catalog (CODEMAP line 77). Fix: move these facts to `contracts/`, which already holds `strategy_requirements.py` and `distribution_behavior.py`. This removes about 5 ignore lines and the `plan <-> execution` loop.
2. **QA. Per-strategy facts are spread over about 12 tables in 8 modules.** `SCALAR_HANDLERS` (`execution/_strategies/__init__.py:52`), `_SCALAR_STRATEGIES` (`execution/_column_access.py:293`), `_CHUNK_ADMITTED_STRATEGIES` (`execution/_chunked.py:204`), `_SUPPORTED_WORK_STRATEGIES` (`execution/out_of_core/_compat.py:61`), `_STATE_TABLE_BY_STRATEGY` (`execution/native/_requirements.py:44`), `OPERATOR_ID_BY_STRATEGY` (`execution/physical/_shadow_bindings.py:78`), `MASK_STRATEGY_TO_SITE` (`execution/native/_determinism_protocol.py:74`), `TECHNIQUE_CLASS_BY_STRATEGY`, `SEQUENTIAL_INPUT_TYPE_DRIFT_BY_STRATEGY` (`reasons/runtime/_tables.py:18`), plus the two `contracts/` tables and `quality/policy.py:112,138`. Some are pinned by snapshot tests in `tests/native/`, but there is no one registry that says "strategy X: these routes, this class, this output type". This is the same class as the transform-lineage copies. Fix: one strategy registry in `contracts/`, with each route's admission table derived from it, plus a sentry that fails when a strategy is missing from it. Watch item: a route that admits a strategy it does not fully implement could become V1, but every admission gate seen here fails closed.
3. **QA. Import cycle through the middle of the engine.** 11 packages form one cycle at module level and 27 with function-level imports (check 6). Most edges are allowed because the packages are siblings in tier 3 or 4. The cross-tier ones are the 30 ignores. Fix: findings 1 and 4 remove the largest loops. After that, split tier 3 into "policy" (`plan`, `relationships`) above "builders" (`generation`, `transforms`).
4. **QA. `execution/` is 78,000 lines, about 40 percent of the package.** It holds the use-case orchestrator (`run_pipeline`), at least 8 route deciders (`decide_route` in `_pipeline_context.py:496` and in `out_of_core/_route_policy.py:96`, `decide_execution_route`, `decide_chunk_route`, `decide_split`, `decide_stream_route`, `decide_multi_table_split`, `decide_output_mode`), the pandas handlers, the native bridge, out-of-core, physical plans and estimators. Different actors change it for different reasons (common-closure failure). Two functions share the name `run_mask_chunked` with different signatures (`execution/_pipeline_route_exec.py:565` and the public one at `execution/native/_chunked_entry.py:601`). Fix: give the run orchestration and routing their own package above the backends, and rename the private delegate. This is a structure task for after V1 ([[structure-cleanup-review-later]]).
5. **QA. Routing preparation is run three ways.** `build_routing_facts` is the shared owner, but `execution/capacity.py` (lines 79-101) and `execution/_job_estimate.py` each run their own profile, compile and route sequence, with byte-estimate and probe routing turned off. The estimate can disagree with the real route. Both are advisory and never gate a run, so it is not V1. Fix: call `build_routing_facts` with an explicit estimate mode.
6. **QA. The layer contract does not encode policy direction.** See the sentry section. `connectors`, `io` and `fileaccess` sit below `plan`, so new outward imports from policy to I/O would pass. Fix: the `forbidden` contract above.
7. **QA. pandas inside strategy rules.** See check 5. The pandas path is the parity oracle, so this is a deliberate choice. The cost is that each strategy exists in pandas plus one or more Arrow or native copies, kept equal by parity tests and not by construction.
8. **QA. Plan compile does file reads.** `plan/_compile.py:55`, `plan/_generation.py:176-182`, `plan/_serialize.py`, `plan/validate/_consolidator.py`. All go through the `fileaccess` choke point, so there is no leak risk, but compile is not pure. Fix: resolve snapshot and lookup files before compile and pass the bytes in.
9. **QA. Error types in a high layer.** `plan._errors.PlanCompileError` is imported by `transforms` (11 edges) and `relationships`, which creates `transforms -> plan` and `relationships -> plan` edges. Fix: move plan error classes to a leaf next to `_error_base`.
10. **QA. Profile builds cloud clients itself.** `profile/_cloud_readers.py` calls `connectors._clients.s3_client` and `gcs_client` directly (lines 209, 361). Fix: a ranged-read protocol in `sdk/`, injected by the caller.

## What is already good

- `reasons/` is a pure leaf. `contracts/`, `expressions/`, `delivery/` and `run_result/` depend only on lower leaves.
- Cloud SDKs and database drivers are only in `connectors/`, behind `sdk/` protocols, and nothing in the core imports `connectors`.
- The engine does not know about the CLI. Exit codes are injected.
- `fileaccess` and `connect_duckdb` are single choke points for file and DuckDB access.
- The layer sentry is exhaustive, fails closed, rejects facade ignores, and has meta-tests that prove it goes red on seeded violations.
