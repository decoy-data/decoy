Status: plan

# PRE-SCAN-RUN: run the declared pre-scan at the start of `decoy run`

Date: 2026-11-21. Repos: engine and CLI. Row: PRE-SCAN-RUN in `docs/roadmap/groups/scan.md` (1.0 table, added by open PR #368, branch `docs/roadmap-dataflow-gaps`).

Rules consulted: `~/dev-rules/README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md`, `profiles/local-operations.md`, `feature-dev.md`, `api-and-compatibility.md`, `cross-cutting-concerns.md`, `architecture.md`, `testing.md`, `workspace-and-vcs.md`; CLI `docs/roadmap/working-rules.md` (sections 3 and 4).

Read from: CLI origin/main `1eb0289c`, engine origin/main `e96d9b48` (engine 0.28.2 released), both 2026-11-21, engine branch `plan/scan-checks` (`docs/plans/2026-11-16-scan-checks.md`, section 5, row 32 DRIFT), CLI PRs #309 and #367 (LIB L3a), vault `30_Resources/Decoy-Language-to-Delivery.md`.

## 1. Frame

**Problem (confirmed 2026-11-21).** A pipeline config accepts a `pre_scan` block (engine `src/decoy_engine/config/_pipeline.py:130`, `pre_scan: PreScanConfig`). `decoy run` never runs it. The CLI run path (`src/decoy/cli/run/_prepare.py`, and `_execute.py`, which calls `run_pipeline` near line 359) does not read `pre_scan`, and the engine run path does not either. Only `decoy scan` uses a `PreScanConfig`, built from its own `--detectors` and `--ner-model` options (`src/decoy/cli/scanning/_detectors.py::resolve_pre_scan`, called from `_multi.py:576`). So a pipeline that asks for a pre-scan runs without one and reports success. That is a wrong result reported as success, which is the safety test for a 1.0 row.

Two more facts make it worse:

1. The config cannot say "yes, pre-scan" today. `PreScanConfig` holds only `detectors` and `ner_model`. The pipeline dump drops `pre_scan` by value when it equals the default (`_pipeline.py:179-181`), so `pre_scan: {detectors: [regex]}` and no block at all give the same validated config. The `.decoy` statement `scan before(regex)` lowers to exactly that block (`src/decoy/lang/_safety.py`, `SHAPES["scan before"]`), so it is lost too. The language guide says the statement "Looks for sensitive data before masking" (`docs/guides/decoy-language/05-checks-and-subsets.md`). It does not.
2. The same class exists next door. `scan_baseline.on_drift` is parsed, hashed and documented as "rescans the sources at run start" (engine `reasons/pre_scan/_part1.py`), but no CLI code calls `evaluate_drift`. That is row 32 DRIFT (Later, 1.x), slice D-2 of the scan-checks plan. This plan does not build D-2. It builds the run-start scan step that D-2 will reuse, and its sentry lists `scan_baseline.on_drift` as a known unread field so it cannot be forgotten.

**Owner decisions.**

- Owner 2026-11-05 (pipeline baseline, vault `10_Projects/decoy/v1-pipeline-baseline.md`): "both platform and CLI need to be able to build a pipeline configuration that has the source, the subset used, yes/no on prescan, the actual mask/gen process for each table, the post scan confirmation, and then delivery of the dataset."
- Owner 2026-11-21, on this row: "go with recommended". The recommended shape: at run start, run the declared pre-scan through the same scan entry `decoy scan` uses (one scan path, no second implementation), record its report in the run record and result, and apply its declared policy, reusing the post-scan gate policy and exit codes.
- Owner 2026-11-21: the `.decoy` language is the primary pipeline writer; YAML stays fully supported. Language sugar compiles to explicit YAML fields the engine checks.

## 2. Guarantee and non-goals

**Guarantee.** After this row:

1. A pipeline that writes a `pre_scan` block (YAML) or a `scan before(...)` statement (`.decoy`) gets a pre-scan at the start of every `decoy run` that reads sources, and of every `decoy.mask(config=...)` call (the Python API that promises to mirror `decoy run`, `src/decoy/api.py:411`). A pipeline without one gets none, exactly as today.
2. The pre-scan runs through `decoy.cli.scanning.scan_descriptors`, the one CLI caller of the engine scan (`tests/sentry/scan/test_one_scan_call.py`). There is no second scan implementation.
3. The pre-scan result decides one thing: whether a source column that the detectors flag as PII leaves the run unmasked. The policy is `pre_scan.on_findings: warn | fail` (default `warn`). `warn` reports and continues. `fail` stops the run before the full source load and before any write, with exit 4, the code a blocked post-scan gives.
4. The result is recorded in the run result document as check `pre_scan` (codes and counts), on stderr as one line per finding (table and column names, never a value), and in the `--json` envelope as a `pre_scan` member.
5. A config field that no reader consumes fails a sentry, so a block cannot be parsed and ignored again without an explicit, ratcheted allowlist entry.

**Non-goals.**

- Drift against a baseline (row 32 DRIFT, D-2). This plan only makes the run-start scan step reusable for it.
- Dismissals for pre-scan findings (a `pre_scan.dismissed` list like `post_scan.dismissed`). Later candidate, section 13 Q5.
- Pre-scan sampling options in the config (`rows`, `strategy`). The run uses the `decoy scan` defaults: head, `DEFAULT_SCAN_ROWS` = 10,000 rows per table. Section 13 Q4.
- A pre-scan side file on disk (`<stem>.pre-scan.json`). Section 13 Q3.
- A separate library record for the run-start scan (a LIB L2 `scan` record). Section 13 Q6.
- Scanning the subset output. The pre-scan reads the declared sources. Findings are about columns; a subset changes rows, not columns.
- Proving that a `when:` condition selects every row. A rule with `when:` set is treated as partial coverage, so the column is a finding (4.2). A finer check that reads the condition is later.
- Platform pre-scans (`release_gates.py`, parked).

## 3. Established solutions

Search run 2026-11-21 (web and in-codebase): "unused configuration" detection in config-driven tools; inspect-then-de-identify flows in data-protection products; CI exit-code splits.

- **Unused config detection.** dbt warns "Configuration paths exist in your dbt_project.yml file which do not apply to any resources" and lets CI make that warning an error with `--warn-error-options` ([dbt FAQ](https://docs.getdbt.com/faqs/Troubleshooting/unused-model-configurations.md), [dbt discourse](https://discourse.getdbt.com/t/use-warn-error-options-in-ci-to-catch-all-warnings-except-the-unhelpful-ones/10548)). The sentry in slice C0 uses the same idea at build time instead of run time: every accepted key must map to a consumer. Pydantic `extra="forbid"` (already on every engine model) covers unknown keys. It does not cover known keys that nothing reads, which is this bug.
- **Inspect, then de-identify.** Google Sensitive Data Protection profiles and inspects tables at column level, then a de-identify step masks the findings ([scan BigQuery data](https://docs.cloud.google.com/bigquery/docs/scan-with-dlp), [Sensitive Data Protection with BigQuery](https://docs.cloud.google.com/sensitive-data-protection/docs/dlp-bigquery)). Decoy's pre-scan is the inspect step. The useful run-time question is the one this plan asks: which flagged columns does the de-identify config leave alone.
- **Exit codes.** The CLI already follows semgrep's split (0 pass, a findings code, an error code) in `src/decoy/cli/exit_codes.py`. Pre-scan `fail` reuses `EXIT_FINDINGS` = 4. No new code.
- **In-codebase precedents followed.** SCAN-CHECKS D-1 (`scan_baseline.on_drift: warn | fail`, absent means no check, hashed when it can refuse a run, a `scan_drift` check id, `build_run_result(pre_checks=...)`); `post_scan.ner_findings: warn | fail`; `quarantine(...)` in `.decoy` (writing the statement turns the feature on); `evaluate_drift` returning a value-free `DriftVerdict` from engine `profiling/bound_baseline.py`.

Custom code left: the coverage rule (flagged column against effective strategy) and the run-start step. Both are small and have no library equivalent, because they read Decoy's own config and scan core.

## 4. Design

### 4.1 Config (engine)

```yaml
pre_scan:                 # writing the block turns the pre-scan on
  detectors: [regex, ner] # as today; regex always
  ner_model: en_core_web_md
  on_findings: warn       # warn (default) | fail
```

- **The switch is presence.** `PipelineConfig` keeps `pre_scan` in its dump when the input wrote it (`"pre_scan" in self.model_fields_set`), even when every field is the default. It drops the block only when it was not written. The dump of a config that never wrote `pre_scan` is byte-identical to today.
- One engine helper, `pre_scan_requested(config: Mapping) -> bool`, in `config/_pre_scan.py` (the pattern of `post_scan_integrity_requested`). It is the only reader of the switch, so the CLI and later the platform agree.
- `on_findings: Literal["warn", "fail"] = "warn"`. Dropped from the dump while `warn`, like `ner_findings`.
- Plan hash: `pre_scan` stays in `_UNHASHED_BLOCKS`. When `on_findings` is `fail`, the hash takes `{on_findings, detectors, ner_model}` with their effective values (detectors sorted and with the `regex` default filled in, `ner_model` only when `ner` is listed), because under `fail` those three decide whether the run blocks. This is the same reason `post_scan` stays hashed (engine `plan/_compile.py:640-646`) and the `scan_baseline.on_drift` rule (`:654-662`). Under `warn` nothing from `pre_scan` is hashed: it changes no output. The rule stays in `_hash_config` in `plan/_compile.py` (670 lines, about 682 after, ceiling 700). No new `plan/` module: `plan/` is frozen at 30 direct modules (engine `tests/sentry/layout/test_package_fanout.py:38`) and the pin is not raised.
- `ner_model` keeps its rule (needs `ner` in `detectors`). The existing checks do not change.

Why presence and not a new `enabled` key: the owner's baseline is "yes/no on prescan", and in both writers the user already says yes by writing the block or the statement. No new syntax, and `scan before` keeps the meaning its guide already gives it. The alternative is in section 13 Q1.

### 4.2 The coverage verdict (engine)

`decoy_engine.profiling.evaluate_pre_scan(config, core) -> PreScanVerdict`, a pure function in a new module `profiling/pre_scan_check.py`, beside `bound_baseline.py::evaluate_drift`. It is engine-owned so the platform runs the same rule (ROADMAP section 2, "Engine contracts stay platform-ready").

Inputs: the validated config dict and a `scan-set/v1` core dict (value-free).

Rule, per mask table in the config that the core holds:

- A field is **flagged** when `pii_candidate` is true, or it has a model hit with band `high` from a detector in `pre_scan.detectors`. Model hits with band `review` are counted, not flagged.
- A flagged field is **covered** when the column rule for it has a strategy other than `passthrough` and no `when:` (engine `config/_tables.py:140`, `ColumnConfig.when`). `from_parent` counts as covered.
- A flagged field is **uncovered** when it has no column rule (an unconfigured column), its rule is `passthrough` (`keep` in `.decoy`), or its rule has a `when:` condition. Rows where `when` is false pass through unchanged (engine `execution/_when_gate.py:1-6`), so a conditional rule is partial coverage. The finding carries `partial: true` and the line says `is masked only where its when: condition holds`.
- A mask table in the config that is absent from the core is a finding too (`not_scanned`, fail closed), not a skip.
- Generate tables have no source and are not scanned.

Output: `PreScanVerdict(status, findings, counts, code, detectors, tables_scanned)`. `detectors` is the effective detector tuple (sorted, `regex` default filled in) and `tables_scanned` the sorted names of the mask tables the core holds. Both are set on every verdict, including `passed` with no findings and a pure generate pipeline (`tables_scanned` empty), so `pre_scan_member` never rebuilds them from findings.

| status | When | Code | Blocking |
|---|---|---|---|
| `passed` | no uncovered field | none | no |
| `warned` | uncovered fields, `on_findings: warn` | `pre_scan.uncovered_pii` | no |
| `failed` | uncovered fields, `on_findings: fail` | `pre_scan.uncovered_pii_blocked` | yes |

`findings` is a sorted tuple of `(table, column, sources, partial)`, where `sources` names the detectors that flagged the field (or `not_scanned` for a table absent from the core). Names only. `counts` maps to the run result `CheckCounts`: `pass` = covered flagged fields, `warning` or `fail` = uncovered fields, `error` = 0. `to_check()` returns the run result `Check` with id `pre_scan`.

The two run errors also live in the engine, in `profiling/pre_scan_check.py`: `PreScanBlockedError(verdict)` (code `pre_scan.uncovered_pii_blocked`) and `PreScanFailedError` (code `pre_scan.profile_failed`). Both are registered in the engine reason adapter's coded families with namespace `pre_scan` (`reason_adapter.py`, the list where `BaselineBindingError` sits at `:118` and `PostScanBlockedError` at `:104`). That is the only way the code reaches the run result: the adapter trusts a `.code` only on a registered family (`reason_adapter.py:8-15`, `_classify` at `:291-307`), and a CLI class would become `decoy.unexpected_error`. `PreScanWarning(UserWarning)` sits beside them.

### 4.3 Run result (engine)

- `CheckId` gains `pre_scan`. A tolerant `RunResultRead` reads an unknown id as a plain token (the compatibility contract precedent for `scan_drift`), so the change is additive under `decoy-run-result/v1`.
- `build_run_result(pre_checks=...)` accepts `pre_scan` and `scan_drift`, at most one of each, in that order. A blocking failed pre-check makes the status `findings` and exit 4 through the existing map. That path already exists for `scan_drift`.

### 4.4 Reason codes (engine registry, `pre_scan` namespace, one minor)

| Code | Kind, severity, outcome | Text (fixed) |
|---|---|---|
| `pre_scan.uncovered_pii` | warning, warning, findings | "The pre-scan flagged source columns that the pipeline leaves unmasked; the run continues under on_findings: warn." |
| `pre_scan.uncovered_pii_blocked` | finding, error, findings | "The pre-scan flagged source columns that the pipeline leaves unmasked, so the run stopped under on_findings: fail." |

Reused, not new: `pre_scan.profile_failed` ("The Pre-scan profile did not complete.") for a scan that raises; the model reasons the gate already uses for a model that cannot load; the engine's literal-error code for a bad `on_findings` value (as for `post_scan.ner_findings`).

### 4.5 The run-start step (CLI)

New module `src/decoy/cli/run/_pre_scan.py` with two public functions:

- `check_pre_scan(config_dict, base_dir) -> PreScanVerdict | PreScanModelRefused | None`: the shared core. It holds no `RunContext`, prints nothing, raises no route error and takes no mode flag, so `decoy run` and `decoy.mask` (4.5a) both call it. `None` means the config asks for no pre-scan. `PreScanModelRefused(status)` is a neutral value (a frozen dataclass in `_pre_scan.py` holding the `ModelStatus` that `load_detector_set` returned) for a model that cannot run.
- Two route adapters, one per route, each mapping the core's result to that route's contract:
  - `run_pre_scan(ctx) -> None` (CLI, `_pre_scan.py`): `PreScanModelRefused` becomes `PreRunCheckError.from_findings([model_finding(status, block="pre_scan")])` (exit 1, reason code, install hint), as `preflight_detectors` does for post-scan (`src/decoy/cli/io/_integrity_report.py:95-106`); a verdict is stored, printed, and raised as `PreScanBlockedError` on `failed`.
  - `_mask_pre_scan(config_dict, base_dir) -> None` (API, `src/decoy/api.py`, private): `PreScanModelRefused` becomes `ConfigValidationError` (`api.py:79`) with the same finding text (names only); `warned` becomes one `PreScanWarning`; `failed` raises `PreScanBlockedError`.

**Rule: every refusal that reads no rows comes before the scan, on every route.** Today some config-only checks run late, inside the source loader or the chunked check. C1 moves them, without changing what they check, into one function that both routes call first:

- New `check_before_read(config_dict, base_dir, *, chunked)` in `src/decoy/cli/run/_execute.py` (it owns these checks today). It holds, in today's order: `_require_local_io_endpoints` (`_execute.py:242`); for chunked, `_check_chunked_tables` (`:203`: integrity `:210`, quarantine `:211-215`, target formats `:216`, per-table strategy compatibility `:221-223`); for plain, `check_target_formats(chunked=False)` (`:280`) and `prepared_sources` (`:281`, the declared-source checks; it reads each source's header or footer, never a data row, `src/decoy/cli/_sources.py:116-156`). For plain it returns the `PreparedDeclaredSources` capability that `prepared_sources` built; for chunked it returns `None`.
- Probe once: `_load_sources_from_config` gains a keyword `prepared=None`. `prepare` and `api.mask` pass the capability that `check_before_read` returned, and the loader skips its own probe. When `prepared` is `None` (any other caller), the loader calls `check_before_read` itself, so a caller that skips it still refuses (the existing "each helper calls this itself" rule, `:253-254`). So each source header is read once per run on both routes; C1-T14 pins it with a call-count spy on `prepare_declared_sources`.

Placement in `_prepare.prepare` (`src/decoy/cli/run/_prepare.py`):

- after `check_before_run` (`:380`), so a gate error wins without a source read, and `--duckdb-source` tables are already staged to Parquet;
- after every usage refusal in `prepare` (`:398` to `:530`: mask secret flag, chunked combinations, `--vault` checks, the native gate, local endpoints, resources);
- after `check_before_read` (new, at `:531`, replacing the bare `_check_chunked_tables` call there for chunked);
- before the row read (`_load_sources_from_config`, `:535`), so `fail` reads only the head sample and opens no run folder;
- before key admission (`:538`). Admission is not a config-only check: it reads the secret. Today it already runs after the source read (`:535` then `:538`; in `api.mask`, `:600` then `:618`), so a missing source beats a missing secret today. The scan keeps that relative order, and `fail` never reads the secret.

In `api.mask` (4.5a) the same order: native gate (`api.py:575`) and output collisions (`:594`), then `check_before_read`, then `check_pre_scan`, then `_load_sources_from_config` (`:600`), then admission (`:618`).

This is also where D-2 must add its drift check (the scan-checks plan places D-2 right after `check_before_run`; that plan should move to this point). D-2 reuses the same step and the same scan result. It must not add a second rescan.

What the core does:

1. `pre_scan_requested(config_dict)`; return `None` when false. No scan, no check, no output change.
2. Build the descriptors from `resolved_source_config(config_dict, base_dir)["sources"]`, mask tables only.
3. Load the model detectors first with `load_detector_set(pre_scan.detectors, pre_scan.ner_model)` (`src/decoy/cli/io/_integrity_report.py:75`). It does not raise: it returns `(detector_set, None)` or `(None, refused_status)`. On a refusal the core returns `PreScanModelRefused(refused_status)` and does not scan; the route adapter above turns it into that route's error. The gate (4.6) normally refuses earlier on `decoy run`; this is the second line.
4. Call `scan_descriptors(descriptors, rows=DEFAULT_SCAN_ROWS, strategy="head", pre_scan=<the PreScanConfig>)`.
5. Return `evaluate_pre_scan(config_dict, run.core)`.

Errors in step 4 (only `scan_descriptors` raises): `ModelUnavailableError` (a model that loaded in step 3 but fails inside the scan), `MemoryError` and the engine capacity refusals (`ExecutionError` with a capacity code) pass through unchanged, so they keep their own exits (1 and 5). Every other exception from the scan becomes the engine's `PreScanFailedError` (`pre_scan.profile_failed`, fixed text). The `except` block only records that the scan failed; the new error is raised after the block ends, with `from None`, so neither `__cause__` nor `__context__` holds the original (an engine read error can quote a cell; the rule `decoy scan` follows in `_multi.py`). Never `str(exc)`. The pass-through set is one tuple in `_pre_scan.py`, tested.

What the `decoy run` wrapper adds: it keeps `verdict.to_check()` on `ctx._pre_checks`; on `warned` it prints one stderr line per finding, `warning: pre-scan: <table>.<column> looks like PII (<sources>) and is not masked`; on `failed` it raises `PreScanBlockedError`, which carries the verdict.

Wiring in the existing modules:

- `_result.py`: `_build` passes `ctx._pre_checks` to `build_run_result(pre_checks=...)`. One line.
- `exit_codes.py`: one predicate, `is_blocking_verdict(exc)`, at the exit-code choke point, true for `PostScanBlockedError` and `PreScanBlockedError`. It replaces the check in `exit_code_for` (`src/decoy/cli/exit_codes.py:224-226`), so `exit_code_for(PreScanBlockedError(...))` is 4.
- `_errors.py`: the same predicate replaces the three `isinstance(exc, PostScanBlockedError)` tests that mean "a verdict about the data": the category arm (`:192`), `blocking_failed=` (`:211`) and the no-traceback test (`:335`). So pre-scan `fail` gets category `None`, status `findings`, exit 4 and no traceback hint. The arm at `:226` writes the post-scan report and stays post-scan only; the pre-scan blocked text is its own fixed summary. `PreScanFailedError` is a runtime failure (exit 3). Because both errors are engine-registered, `_failure_reason` (`:86`) gets the trusted `pre_scan` reason from `reason_adapter.reason_from_exception` with no CLI special case.
- One serializer for the `--json` member: `pre_scan_member(verdict) -> dict` in `run/_pre_scan.py`. It reads only verdict fields (`status`, `detectors`, `tables_scanned`, `findings`), giving `{status, detectors, tables_scanned, findings: [{table, column, sources, partial}]}`. Both envelope builders call it when `ctx._pre_scan` is set: the success envelope in `_render.finish` (`_render.py:96`, json branch `:107`) and the error envelope in `_errors.fail` (`_errors.py:265-305`, next to `payload.update(blocked)`). No member when the pre-scan did not run. C1-T5 asserts the top-level member on the exit 4 envelope.
- `_render.py`: the card gains one `Pre-scan` line (`passed`, or `2 unmasked PII columns (warn)`).
- `RunContext` gains `_pre_checks` and `_pre_scan` (the verdict). Two fields.

### 4.5a The Python API route (`decoy.mask`)

`decoy.mask(config=...)` (`src/decoy/api.py:411`) says it "Mirrors `decoy run`'s semantics exactly" and calls `run_pipeline` itself (`api.py:620`). Without a change it would skip a declared pre-scan, which is the same bug. So `mask` calls `check_before_read` and then its adapter `_mask_pre_scan`, which calls the same core, `check_pre_scan(config_dict, base_dir)`, after its native gate and output-collision checks and before `_load_sources_from_config` (`api.py:600`). When `data` is a DataFrame, Arrow table or path, `mask` has already staged it to a temporary file named by `sources:`, so the scan reads what the run will read.

- `passed`: nothing.
- `warned`: one `warnings.warn` per call, category `decoy.PreScanWarning` (a new public `UserWarning` subclass), text naming the tables and columns, never a value.
- `failed`: raise `decoy.PreScanBlockedError` (the engine class the CLI also raises), with the findings as a names-only attribute. Nothing is masked or returned.

Public names: `PreScanWarning`, `PreScanBlockedError` and `PreScanFailedError` are imported into `src/decoy/api.py` from the engine, added to `api.__all__` (`api.py:62`) and to `_LAZY_API` in `src/decoy/__init__.py:20-28`, so `decoy.PreScanBlockedError` resolves through the root `__getattr__` without importing the engine at `import decoy`. The compatibility inventory of public `decoy` names gains the three. Tested by C1-T19.
- scan failure: `PreScanFailedError` with `pre_scan.profile_failed`; model and capacity errors pass through as in 4.5.

`decoy.scan()` is a scan, not a run, so it is unchanged.

### 4.6 Model preflight (CLI gate)

`src/decoy/cli/gate/_models.py` also checks the `pre_scan` models when `pre_scan_requested(config)` is true. Today it checks only `post_scan` models, and its docstring says "a `pre_scan` model is the scan's to refuse". That was true while only `decoy scan` read the block. Now `decoy validate`, `decoy ci check` and `decoy run` refuse an unavailable pre-scan model before any row is read, with exit 1 and the same install hint, at location `pre_scan.detectors`.

`model_finding` (`_models.py:35`) and `_LOCATION` are hard-coded to `post_scan` today (the message starts "post_scan asks for the ..."). C1b gives `model_finding` a `block` parameter (`"pre_scan"` or `"post_scan"`) that sets both the message start and the location, so each finding names the block that asked for the model. `decoy validate` and `decoy ci check` only probe the models (`classifier_status`, `ner_status`); they never scan.

### 4.6a `scan_baseline.on_drift` until DRIFT lands

`scan_baseline.on_drift` is accepted, hashed and described as a run-start check, but no run reads it (row 32 DRIFT, 1.x). This row does not build the check. It stops the silence: the gate adds a warning finding when `scan_baseline.on_drift` is set, `scan_baseline.on_drift is not checked by decoy run yet; the run continues without a drift check`, code `warning.drift_not_checked` (new, engine registry, the `warning` namespace), location `scan_baseline.on_drift`. How the text reaches the user: `decoy validate` and `decoy ci check` list gate findings verbatim. `decoy run` does not: `check_before_run` prints only a warning count and a `decoy validate` hint (`src/decoy/cli/gate/_run.py:161-168`). So `run_pre_scan`'s neighbour in `prepare` also calls `ctx.add_cli_warning("drift_not_checked", <the same text>)` (`run/_context.py:208`, the route used for `chunked_key_check_not_run`), which puts the sentence on the card and in the `--json` `warnings` list. The text is one constant in `gate/`, used by both. `--fail-on-warning` turns it into exit 2 on `validate` as for any warning. The engine comment in `reasons/pre_scan/_part1.py` ("rescans the sources at run start") and the matching compatibility-contract text are corrected to say the run-start check is planned (DRIFT), not shipped. Registered reason descriptions stay as they are if the registry treats description text as frozen; the slice checks the registry rule first. When D-2 lands it removes the warning and the sentry's `unread` row together.

### 4.7 Run variants

| Variant | Pre-scan |
|---|---|
| plain `decoy run` | runs |
| `--chunked` | runs (head sample, bounded); the chunked branch reads sources itself afterwards |
| `--duckdb-source` | runs on the staged Parquet |
| `--all` | each child process runs its own pipeline's pre-scan; a child blocked by `fail` exits 4 and the parent aggregates child exits as it does today (`src/decoy/cli/project/_run_all.py`, highest-precedence code wins: capacity, runtime, usage, partial, findings, warnings, ok) |
| `decoy.mask(config=...)` | runs, through the same core (4.5a) |
| `decoy validate`, `decoy ci check` | no scan; the pre-scan model probe only (4.6) |
| `--rows N` preview | does not run (generate only, no sources, nothing written) |
| `--no-subset` | runs (the pre-scan reads sources, not the subset) |
| `--no-library` (LIB L3a, PR #309) | runs; the check is in the run result either way; only the library store is skipped |
| pure generate pipeline with a `pre_scan` block | no mask table: the step records `passed` with zero tables and prints nothing |

### 4.8 `.decoy` language

How pre-scan is written:

```decoy
scan before(regex)                          // on, warn
scan before(regex, ner, on_findings: fail)  // on, stop on unmasked PII
scan before                                 // on, regex only, warn
```

Lowering does not change. `scan before(...)` already writes `pre_scan` with `detectors` from the plain values, and every `key: value` option is passed through under the same key (`_safety.py::_options`), so `on_findings: fail` needs no new code. With the engine change in 4.1 the block now survives validation, so the statement takes effect.

Language change needed: none in the grammar, the lowering or the codes. Needed: tests that pin the round trip (`scan before` with no arguments lowers to `pre_scan: {}`, the engine keeps it, `convert_config` prints it back as `scan before`; `on_findings: fail` round-trips), and the guide text (section 10). `convert_config` already reads `SHAPES`, so a YAML `pre_scan` block converts to `scan before(...)` with its options.

YAML stays fully supported and is the same contract: a `.decoy` file compiles to the YAML shape in 4.1.

## 4a. Enumerations

### Exit paths

- Pre-scan absent: the step returns at once (it sits at `src/decoy/cli/run/_prepare.py:531`, after `check_before_run` at `:380` and the usage refusals up to `:529`).
- A usage refusal in `prepare`: raised before the step, so no scan runs (exit 1).
- `passed` or `warned`: the run continues to the source load (`src/decoy/cli/run/_prepare.py:535`) and ends through `_render.finish`.
- `failed`: `PreScanBlockedError` goes to the one error handler, the `PostScanBlockedError` arm (`src/decoy/cli/run/_errors.py:192`), exit 4.
- Scan error: `PreScanFailedError`, runtime arm, exit 3. Model, `MemoryError` and capacity errors pass through to their own arms (exit 1 or 5).
- `decoy.mask`: `PreScanBlockedError` or `PreScanFailedError` raised to the caller; `PreScanWarning` on warn (`src/decoy/api.py:600` is the source load it precedes).
- Model cannot run: gate refusal before the run starts (`src/decoy/cli/gate/_models.py:20`), exit 1.

### Routes

- Plain branch: `run_pipeline` in `src/decoy/cli/run/_execute.py:359`; the step runs before it, in `prepare`.
- Chunked branch: `_run_chunked_mask` in `src/decoy/cli/run/_execute.py:75`; the step runs before it too.
- `--duckdb-source`: staging in `src/decoy/cli/run/_prepare.py:316`, before the gate; the step scans the staged Parquet.
- Preview (`--rows`): `prepare_preview` (`src/decoy/cli/run/_prepare.py:259`); no step.
- Python API: `decoy.mask` calls `run_pipeline` at `src/decoy/api.py:620`; the core runs before its source load.
- `--all`: child processes (`src/decoy/cli/project/_run_all.py`); each runs the step for its own pipeline.

### FK shapes

- N/A for the verdict: coverage is per column, and an FK child column with `from_parent` counts as covered (4.2). No join is read.
- The scan runs with no `relationships` argument, so `scan_sources` reads no key spill (`src/decoy_engine/profiling/scan_set.py:151` default is empty).

### Fields

- `pre_scan.detectors`, `pre_scan.ner_model` (`src/decoy_engine/config/_pre_scan.py:64`): read by the scan.
- `pre_scan.on_findings` (new): read by `evaluate_pre_scan`.
- The block's presence (`src/decoy_engine/config/_pipeline.py:130`): read by `pre_scan_requested`.
- Scan core fields read by the verdict: `pii_candidate`, `model_hits[].band`, `model_hits[].source` (`src/decoy_engine/profiling/_scan_core.py:82`).

### Output surfaces

- stderr finding lines and the blocked summary.
- `--json` envelope `pre_scan` member, and the error envelope on `fail`.
- Run result document check `pre_scan` (`src/decoy_engine/run_result/_model.py:182`), also written by `--result` and stored by LIB L3a when merged.
- The run card `Pre-scan` line.
- Not touched: evidence manifest (`--evidence-out`), post-scan report, notifications (they carry the exception type name only, `src/decoy/cli/run/_errors.py:241`).

## 4b. Reuse inventory

| Need | Reused | Where |
|---|---|---|
| Run a scan | `scan_descriptors`, the one CLI scan call | `src/decoy/cli/scanning/_engine_call.py` |
| Default sample | `DEFAULT_SCAN_ROWS`, `head` | same module |
| Verdict shape | `evaluate_drift` and `DriftVerdict` pattern | engine `profiling/bound_baseline.py` |
| Run-start checks in the run result | `build_run_result(pre_checks=...)` | engine `run_result/_build.py` |
| Findings exit | `EXIT_FINDINGS` and the `PostScanBlockedError` arm | `src/decoy/cli/exit_codes.py`, `src/decoy/cli/run/_errors.py` |
| Model preflight | `model_finding` and the engine status probes | `src/decoy/cli/gate/_models.py` |
| Scan failure code | `pre_scan.profile_failed` | engine `reasons/pre_scan/_part1.py` |
| Source paths | `resolved_source_config` | `src/decoy/cli/io` |
| Ratchet allowlist | `load_allowlist` | `tests/sentry/_ratchet.py` |
| `.decoy` statement | `scan before(...)` and its options | `src/decoy/lang/_safety.py` |

Nothing new is built where one of these fits.

## 5. Behaviour table

| Case | Config | Run behaviour | Exit | Run result check | stderr | `--json` |
|---|---|---|---|---|---|---|
| B1 pre-scan absent | no `pre_scan`, no `scan before` | no scan; byte-identical to today | as today | no `pre_scan` check | nothing new | no `pre_scan` member |
| B2 on, nothing flagged | `pre_scan: {}` | scan, then run | 0 | `pre_scan` `passed`, not blocking | nothing | `pre_scan.status: passed` |
| B3 on, flagged and all covered | `pre_scan: {}`, flagged columns all masked | scan, then run | 0 | `passed`, `pass` = n | nothing | `passed` |
| B4 uncovered, warn | `on_findings` unset or `warn` | scan, warn, run, write | 0 | `warned`, code `pre_scan.uncovered_pii`, not blocking | one line per finding | `warned`, findings listed |
| B5 uncovered, fail | `on_findings: fail` | scan, stop before the full source load; no run folder, no output, no vault | 4 | `failed`, blocking, code `pre_scan.uncovered_pii_blocked`; status `findings` | one line per finding, then the fixed blocked summary | error envelope with the `pre_scan` member |
| B6 model cannot run | `detectors: [regex, ner]`, spaCy model missing | refused by the gate before any row is read | 1 | none (refused before the run starts) | gate finding and install hint | gate error |
| B7 scan raises (unreadable source, bad CSV) | any `pre_scan` | stopped; no output | 3 | run `failed`, reason `pre_scan.profile_failed` | fixed text, no cell value | error envelope |
| B8 `--no-library` | any `pre_scan` | as B2 to B5 | same | same | same | same, `library: skipped` |
| B9 `--rows` preview | any `pre_scan` | no scan | as today | none | nothing | none |
| B10 YAML and `.decoy` parity | the same pipeline in both forms | same verdict, check and exit | same | same | same | same |
| B11 pre-scan warn, then a post-scan block | warn plus a post-scan blocking finding | both checks recorded, `pre_scan` first | 4 | `pre_scan` warned, `post_scan_integrity` failed | both | both |
| B12 usage refusal and a pre-scan | `pre_scan: {}` plus a usage error (`--chunked` with a vault, `--native` on an ineligible shape) | usage refusal first; no scan, no source read | 1 | none | the usage message only | usage error envelope |
| B13 `decoy.mask(config=...)` | any `pre_scan` | same core as `decoy run`: warn gives `PreScanWarning` and masks; fail raises `PreScanBlockedError`, nothing masked or returned; scan error raises `PreScanFailedError` | n/a (Python) | n/a | none | n/a |
| B14 `decoy validate` with a pre-scan | `pre_scan` with a model detector | model probe only, no scan; missing model is a gate error | 1 if the model cannot run, else as today | n/a | gate finding at `pre_scan.detectors` | gate JSON |
| B15 `decoy ci check` with a pre-scan | same | same as B14 | same as B14 | n/a | same | same |
| B16 `decoy run --all`, one child blocked | one pipeline `on_findings: fail` with unmasked PII, others clean | blocked child exits 4, others run | aggregate by the existing precedence (4 when no child is worse) | per child | per child | per child |
| B17 model cannot run, gate skipped (second line) | model missing at scan time | the model error passes through, not wrapped | 1 | none | model hint | error envelope |
| B18 capacity during the scan | `MemoryError` or engine capacity refusal | passes through, not wrapped | 5 | run `failed`, capacity reason | capacity text | capacity envelope |
| B19 `scan_baseline.on_drift` set | `scan_baseline: {path, on_drift: fail}` | gate warning `warning.drift_not_checked`; run continues with no drift check | 0 (`validate --fail-on-warning`: 2) | none new | the warning | gate warning |

## 6. Failure modes

| # | Failure | Behaviour and code | Exit | Test |
|---|---|---|---|---|
| F1 | Block parsed and ignored again (a refactor drops the call) | G-CONFIG-READER sentry fails; e2e B4 and B5 fail | n/a | C0-T3, C1-T4, C1-T11 |
| F2 | A default block dropped by the dump (the by-value rule comes back) | engine test fails; `scan before(regex)` gets no scan | n/a | E1-T1, C2-T1 |
| F3 | Scan error text leaks a cell value | `PreScanFailedError` carries `pre_scan.profile_failed` and fixed text only | 3 | C1-T6, C1-T7 (canary sweep) |
| F4 | A finding line echoes a sampled value | lines hold table, column and detector source names only | n/a | C1-T7, E2-T7 |
| F5 | `fail` stops after outputs are written | the step runs before the source load (`_prepare.py:535`), key admission (`:538`) and the run folder | 4 | C1-T5 (read spy, no folder) |
| F5b | The scan runs before a usage refusal and reads sources for a run that is refused anyway | the step sits after every usage refusal (`:398` to `:529`) | 1 | C1-T14 |
| F5c | Model or capacity error swallowed as a scan failure (wrong exit) | pass-through tuple; only other errors become `PreScanFailedError` | 1 or 5 | C1-T15, C1-T16 |
| F5d | `decoy.mask` skips a declared pre-scan | `mask` calls the same core; sentry sees the route | n/a | C1-T13, C0-T3 |
| F5e | `on_drift` set and silently ignored | gate warning until DRIFT lands | 0 or 2 | C1b-T5 |
| F6 | A second scan implementation appears | G-ONE-SCAN-CALL (`scan-call-allow` must not grow) | n/a | existing sentry, C1-T3 |
| F7 | A missing model is found only mid-run | the gate preflight refuses first | 1 | C1b-T1 |
| F8 | Under `fail`, a changed detector set or model does not move the hash, so two runs that block differently look equal | plan hash test fails | n/a | E1-T3 |
| F8b | A conditional rule (`when:`) hides PII on the rows it skips | the rule counts as partial coverage, a finding | 0 or 4 | E2-T2b |
| F8c | A mask table the scan did not cover passes silently | `not_scanned` finding, fail closed | 0 or 4 | E2-T6 |
| F8d | The scan failure becomes `decoy.unexpected_error` in the run result | both errors are engine-registered families | 3 | E2-T9, C1-T6 |
| F9 | Unknown `on_findings` value | engine literal-error code at the field location, no value echoed | 1 | E1-T4, C2-T3 |
| F10 | An older reader meets check id `pre_scan` | the tolerant read keeps it as a token | n/a | E1-T6 |
| F11 | Pre-scan on a very large source | head sample of 10,000 rows per table; model detectors cost more; stated in the docs | n/a | docs |
| F12 | `--duckdb-source` scanned before staging | the step is after `check_before_run` and the usage refusals; the staged Parquet is scanned | as case | C1-T8 |
| F13 | A config producer writes a default `pre_scan` block everywhere and turns scans on for all | checked 2026-11-21: no shipped example, `decoy init` scaffold or CLI writer emits `pre_scan`; the platform is parked | n/a | C0 manifest review |

New exit code: none. All cases reuse 0, 1, 2, 3, 4 and 5. No owner call is needed for exit codes.

## 7. The sentry (G-CONFIG-READER)

Where: CLI `tests/sentry/config/test_config_field_readers.py`, with the manifest `tests/sentry/baselines/config-field-readers.json`. The CLI composes the run, so only the CLI can see whether a field the engine accepts is used on the run path. The drift case shows why an engine-side check is not enough: `evaluate_drift` exists in the engine and nothing calls it.

What it walks: the pinned engine's `PipelineConfig.model_fields`, every top-level field, plus the fields of every top-level field whose annotation is a pydantic model (through `Optional` and unions), found from the live schema, not from a hand-kept block list. One level down. The list comes from the live model, not from the manifest. It does not walk `tables`, `columns` or per-column strategy fields: those are list items read by the compiler and covered by the engine's own plan tests, and walking them would turn the manifest into a copy of the schema. Stated in the sentry docstring so nobody assumes it.

Each walked path must have exactly one manifest entry, of one kind:

- `{"engine": "decoy_engine.<module>:<name>"}`: consumed inside `run_pipeline` or `compile_plan`. The name must be a public engine symbol: no `_`-prefixed module part or name, and listed in that module's `__all__`. So a private refactor in the engine cannot break the CLI sentry, and the entry points at a stable surface. The sentry imports the name and checks that its source (`inspect.getsource`, parsed with `ast`) holds the key as a string constant or an attribute name.
- `{"cli": "src/decoy/cli/<path>.py::<function>", "via": "<engine helper>"}`: read on the CLI run path. The sentry checks that the function exists, that its body references the key or calls the helper named in `via` (for `pre_scan`: `pre_scan_requested`), and that every route chain in the entry holds. A `cli` entry for a run-path field lists its chains as exact function paths, each link a direct call found by AST in that function's own body:
  - `run`: `src/decoy/cli/run/_prepare.py::prepare -> src/decoy/cli/run/_pre_scan.py::run_pre_scan -> src/decoy/cli/run/_pre_scan.py::check_pre_scan`;
  - `api.mask`: `src/decoy/api.py::mask -> src/decoy/api.py::_mask_pre_scan -> src/decoy/cli/run/_pre_scan.py::check_pre_scan`.
  "Some module in `run/` calls it" is not enough: `run_pre_scan` itself calls `check_pre_scan`, so deleting the call in `prepare` would stay green. With exact chains, deleting `prepare -> run_pre_scan` breaks the first link and the sentry fails. That is also the check that would have caught the `decoy.mask` gap.
- Matching rule for all kinds: a key shorter than 6 characters (`path`, `rows`, `mode`) or on a short common-word list (`enabled`, `output`, `format`, `detectors`, `strategy`) proves nothing by appearing in a source, so its entry must name a `via` helper and the sentry checks the call to that helper instead. The list lives in the sentry module.
- `{"other_command": "<command>", "row": "<row id>"}`: read only by another command (for example `scan_baseline.path` by `decoy scan --compare`).
- `{"unread": "<row id>"}`: accepted and read by no run. A ratchet: the list may shrink and never grows without a reviewed change (`tests/sentry/_ratchet.py`, the X0a pattern). At C0 merge it holds `pre_scan` (PRE-SCAN-RUN) and `scan_baseline.on_drift` (row 32 DRIFT). C1 removes `pre_scan`.

A new engine field after a repin fails the sentry until it is classified. The vault `engine-repin-checklist` gains that line.

Mutations that must turn it red, each seen before merge (the cross-cutting rule "prove the walk sees a bypass"): delete the `run_pre_scan` call from `_prepare.prepare`; delete the `_mask_pre_scan` call from `api.mask`; point an `engine` entry at a private name; drop the `via` from a short key; add a field with no entry to a fixture `PipelineConfig` subclass; add a row to `unread`.

## 8. Placement

| File | Repo | Change | Why here | Size after |
|---|---|---|---|---|
| `src/decoy_engine/config/_pre_scan.py` | engine | `on_findings` field; `pre_scan_requested` helper | owns `PreScanConfig` | 98 to ~125 |
| `src/decoy_engine/config/__init__.py` | engine | import and export `pre_scan_requested`, beside `post_scan_integrity_requested` (import `:95`, `__all__` `:223`) | the public config facade | +2 |
| `src/decoy_engine/config/_pipeline.py` | engine | the dump keeps a written `pre_scan` (presence rule) | owns the dump | 539 to ~542 |
| `src/decoy_engine/plan/_compile.py` | engine | `_hash_config` hashes `{on_findings, detectors, ner_model}` (effective values) when `on_findings: fail` | owns the hash; no new `plan/` module (frozen at 30, `test_package_fanout.py:38`) | 670 to ~682 (cap 700) |
| `src/decoy_engine/reason_adapter.py` | engine | register `PreScanBlockedError` and `PreScanFailedError` as coded families, namespace `pre_scan` | the one adapter that decides which codes are trusted | +2 rows |
| `src/decoy_engine/profiling/pre_scan_check.py` | engine | new: `evaluate_pre_scan`, `PreScanVerdict`, `PreScanBlockedError`, `PreScanFailedError`, `PreScanWarning` | engine CODEMAP row 73 (`bound_baseline.py`, `evaluate_drift -> DriftVerdict`); sits beside it | ~150 |
| `src/decoy_engine/profiling/__init__.py` | engine | export the five names | public profiling API; `profiling/` gets its 25th direct module, at the limit of 25 | 178 to ~185 |
| `src/decoy_engine/reasons/pre_scan/_part1.py` | engine | two codes, `since=UNRELEASED` | the `pre_scan` namespace | 108 to ~130 |
| `src/decoy_engine/run_result/_model.py`, `_build.py` | engine | `CheckId` gains `pre_scan`; `pre_checks` accepts it | the one run result constructor | 411 and 274, +~8 |
| `docs/compatibility-contract.md`, `CHANGELOG.md`, `CODEMAP.md` row 73 | engine | additive entries | | |
| `src/decoy/cli/run/_pre_scan.py` | CLI | new: `check_pre_scan` (the shared core), `PreScanModelRefused`, `run_pre_scan` (the CLI adapter), `pre_scan_member` (the one `--json` serializer), the pass-through tuple | CLI CODEMAP row "`decoy run` internals", `run/_<noun>.py`; the package goes from 12 to 13 modules | ~140 |
| `tests/sentry/layout/test_run_package_shape.py` | CLI | add `_pre_scan` to `ORDER` (`:35`) after `_execute` and before `_prepare` (it imports `_execute`'s `check_before_read`; `_prepare` imports it) | the run package DAG guard | +1 |
| `src/decoy/cli/run/_execute.py` | CLI | new `check_before_read`; `_load_sources_from_config` calls it | owns the no-row I/O checks today | 433 to ~450 |
| `src/decoy/cli/exit_codes.py` | CLI | `is_blocking_verdict`; `exit_code_for` uses it | the exit-code choke point | +~8 |
| `src/decoy/__init__.py` | CLI | three names in `_LAZY_API` | the root lazy exports | +3 |
| `src/decoy/cli/run/__init__.py` | CLI | import `check_before_read` (from `_execute`) and `check_pre_scan` (from `_pre_scan`) and add both to `__all__` (`:30-40`) | `api.py:49-52` imports run helpers only through this facade | +4 |
| `src/decoy/cli/run/_prepare.py` | CLI | `check_before_read` call replacing the bare `_check_chunked_tables` call (`:531-532`), then `run_pre_scan`, then the drift warning | owns the phase order | 546 to ~550 (run package cap 600, `test_run_package_shape.py`) |
| `src/decoy/cli/run/_errors.py`, `_result.py`, `_render.py`, `_context.py` | CLI | error arms, `pre_checks`, the `--json` member and card line, two fields | existing owners | each +3 to +25, all under 600 |
| `src/decoy/cli/gate/_models.py` | CLI | pre-scan models when requested; `model_finding` and the location take a `block` parameter | the gate's model preflight | 54 to ~75 |
| `src/decoy/cli/gate/` drift warning (in the existing gate module that reads `scan_baseline`, or `_models.py` if none) | CLI | the `warning.drift_not_checked` finding | the gate owns run-start warnings | +~20 |
| `src/decoy/api.py` | CLI | `mask` calls `check_before_read` and the private adapter `_mask_pre_scan` (which calls `check_pre_scan`); the three engine names imported and added to `__all__` (`:62`) | the API route that mirrors `decoy run` | +~25 (file is large; no new logic in it, the core stays in `run/_pre_scan.py`) |
| `src/decoy_engine/reasons/warning/` | engine | `warning.drift_not_checked` | the `warning` namespace | +~10 |
| `tests/sentry/config/test_config_field_readers.py`, `tests/sentry/baselines/config-field-readers.json` | CLI | new sentry and manifest | sentries live in per-concern packages under `tests/sentry/` | ~180; manifest ~60 entries |
| `tests/e2e/pre_scan_run/` | CLI | new e2e package | CLI CODEMAP: new e2e tests go in a package, not the flat folder | ~350 |
| `tests/unit/lang/` (existing language tests) | CLI | round-trip cases | | ~40 |
| `tests/fixtures/release_freeze/json-shapes.json` | CLI | the `pre_scan` member in the run success shape | the frozen `--json` shapes snapshot | regenerated by `write_shapes.py` |

**Design notes.** No new abstraction beyond one module per repo. The verdict follows `evaluate_drift` (pure, value-free, engine-owned). The run step sits after the usage refusals, and D-2 joins it there. The sentry follows the X0a ratchet. One place per fact: the switch in `pre_scan_requested`, the coverage rule in `evaluate_pre_scan`, the scan call in `scan_descriptors`, the exit in `exit_code_for`. Owner question (working rules 4.3), "could it be rolled into a central location?": yes, the run-start step is the one place for every run-start scan check, and D-2 must join it.

## 9. Slices and acceptance tests (red first, with a hostile corpus)

The hostile corpus is the canary source of C1-T7 and E2-T7: cells that hold canary strings, an email-shaped value in a `keep` column, and a CSV row that the reader rejects. Each slice is mergeable on its own once its After slices are on main. Acceptance tests are written first and seen red before the code, each under the named mutation. Mutations are rerun on the final head of each slice before merge, and the gate ledger records, per mutation, the head SHA it ran on and the red test id. A mutation result from an earlier head does not count.

### C0. Sentry G-CONFIG-READER (CLI, R1, ~300 lines)

After: R. Lands on the repinned engine with `pre_scan` and `scan_baseline.on_drift` in the `unread` ratchet.

| Test | Asserts | Mutation that turns it red |
|---|---|---|
| C0-T1 | every walked `PipelineConfig` path has exactly one manifest entry | remove one entry |
| C0-T2 | an `engine` entry's source references its key | point an entry at a function that does not |
| C0-T3 | every link of every route chain in a `cli` entry is a direct call in that function's body (`prepare -> run_pre_scan -> check_pre_scan`; `api.mask -> _mask_pre_scan -> check_pre_scan`) | delete the `prepare -> run_pre_scan` call (it must go red even though `run_pre_scan` still calls `check_pre_scan`); drop the call from `mask` |
| C0-T4 | `unread` can only shrink | add a row to `unread` |
| C0-T5 | a fixture subclass with one extra nested field, in a new nested model field the walker was never told about, fails the walk | make the walker skip nested blocks, or walk a hand-kept block list |
| C0-T6 | an `engine` entry naming a private symbol (a `_`-prefixed module part or name, or a name not in the module's `__all__`) fails | accept any importable name |
| C0-T7 | a key shorter than 6 characters or on the common-word list, with no `via`, fails | match the bare key in the source |

### E1. Engine config, codes, check id and the drift warning code (engine, R2, ~400 lines)

After: none. New codes carry `since=UNRELEASED`; REGISTRY_VERSION is never edited by hand (CONTRIBUTING.md), the release stamp sets it.

| Test | Asserts | Mutation |
|---|---|---|
| E1-T1 | a written default `pre_scan` survives `model_dump` and re-validation; an unwritten one is dropped; the dump of a config without it is byte-identical to the frozen corpus | restore the by-value drop |
| E1-T2 | `pre_scan_requested` is true for `pre_scan: {}` and false for no block | return `bool(config.get("pre_scan"))` (an empty dict is false) |
| E1-T3 | under `on_findings: fail` the plan hash moves when `on_findings`, `detectors` or `ner_model` changes; `{on_findings: fail}` and `{detectors: [regex], on_findings: fail}` hash the same (effective values); under `warn` (or unset) no `pre_scan` change moves the hash | hash only `on_findings`; hash raw rather than effective values; hash under `warn` |
| E1-T4 | `on_findings: maybe` is refused at `pre_scan.on_findings` with the literal-error code and no value in the message | widen the literal |
| E1-T5 | `build_run_result(pre_checks=(pre_scan failed blocking,))` gives status `findings`, exit 4 | drop `pre_scan` from the accepted set |
| E1-T6 | `RunResultRead` reads a document with check `pre_scan`; an older-shape reader fixture keeps it as a token | make the read model strict on `CheckId` |
| E1-T7 | the two codes are registered with `since` and fixed text | remove one from `__all__` |
| E1-T10 | `from decoy_engine.config import pre_scan_requested` works and the name is in `decoy_engine.config.__all__` | leave the facade export out |
| E1-T8 | `warning.drift_not_checked` is registered; the `reasons/pre_scan` DRIFT comment and the compatibility-contract text say the run-start drift check is planned, not shipped | keep the old "rescans the sources at run start" text (doc test greps for it) |

### E2. Coverage verdict (engine, R2, ~330 lines)

After: E1 (codes, check id). Mergeable alone: no caller yet. E2 also adds the two error classes and their reason-adapter rows.

| Test | Asserts | Mutation |
|---|---|---|
| E2-T1 | a regex `pii_candidate` on an unconfigured column is uncovered | treat unconfigured as covered |
| E2-T2 | `passthrough` is uncovered; `hash`, `redact`, `faker` and `from_parent` are covered | treat `passthrough` as covered |
| E2-T2b | `hash` with `when: "country == 'US'"` on a flagged column is uncovered with `partial: true`; under `fail` it blocks; a blank `when` counts as no gate (covered) | treat any non-passthrough strategy as covered, ignoring `when` |
| E2-T3 | a model hit with band `high` flags; band `review` does not | flag `review` |
| E2-T4 | a model hit from a detector not in `pre_scan.detectors` does not flag | ignore the detector list |
| E2-T5 | `warn` gives `warned`, not blocking; `fail` gives `failed`, blocking; nothing uncovered gives `passed` | swap the policy branch |
| E2-T6 | generate tables are skipped; a mask table missing from the core is a `not_scanned` finding (fail closed): `warned` under warn, `failed` under fail | skip the missing table |
| E2-T7 | the verdict, its `Check` and its `repr` hold no value from a canary core (names only) | copy a field sample into the findings |
| E2-T8 | findings are sorted by table, then column | drop the sort |
| E2-T10 | a `passed` verdict with no findings still carries `detectors` (effective, sorted) and `tables_scanned`; a pure generate config gives `passed`, `tables_scanned == ()` | derive `tables_scanned` from findings |
| E2-T9 | `reason_from_exception(PreScanBlockedError(...))` and `reason_from_exception(PreScanFailedError())` give records with namespace `pre_scan` and codes `uncovered_pii_blocked` and `profile_failed`, not `decoy.unexpected_error` | drop the adapter rows |

### R. Engine release and CLI repin (R1)

After: E1 and E2. Daily engine release train (owner 2026-11-09). The CLI repin follows the vault `engine-repin-checklist`. C0 comes after R, so the `on_findings` entry is written in C0.

### C1. Run-start pre-scan (CLI, R2, ~850 lines with tests)

After: R. Touches the exit path and the frozen `--json` shapes, so the full suite runs (escalation trigger: frozen contract).

| Test | Asserts | Mutation |
|---|---|---|
| C1-T1 | B1: no `pre_scan`: `scan_descriptors` is never called (spy) and the `--json` envelope equals the frozen snapshot | always scan |
| C1-T2 | B2 and B3: exit 0, check `passed` | drop `pre_checks` from `_result._build` |
| C1-T3 | the run calls `scan_descriptors` and no other engine scan function; `scan-call-allow` unchanged | call `decoy_engine.scan_sources` directly |
| C1-T4 | B4: an unmasked email column under `warn`: exit 0, one stderr line naming `table.column`, check `warned`, output written | drop the stderr line, or block |
| C1-T5 | B5: the same under `fail`: exit 4, status `findings`, no run folder, no target file, no vault file, `_load_sources_from_config` and `admitted_key_provider` never run (spy), and the `--json` error envelope has a top-level `pre_scan` member equal to `pre_scan_member(verdict)` | move the step after the source load; build the member only in `_render.finish` |
| C1-T6 | B7: an unreadable source: exit 3; the run result failure reason payload (from `reason_adapter`) is `{namespace: pre_scan, code: profile_failed}`, not `decoy.unexpected_error`; the raised error has `__cause__` and `__context__` both `None` | pass `str(exc)` through; define the error in the CLI; raise inside the `except` block |
| C1-T7 | canary sweep: source cells hold canary strings; under warn, under fail and with a forced scan error, no canary reaches stdout, stderr, `--json`, `--result` or the run result | echo a sample value in the finding line |
| C1-T8 | variants: `--duckdb-source` scans the staged Parquet; `--chunked` scans; `--rows` does not | place the step before `check_before_run` |
| C1-T9 | B10: the same pipeline as YAML and as `.decoy` gives the same verdict, check and exit | a lowering that drops the block |
| C1-T10 | B11: pre-scan warn plus a post-scan block: both checks, `pre_scan` first, exit 4 | replace the checks instead of prepending |
| C1-T11 | G-CONFIG-READER: `pre_scan` leaves `unread`; entry `cli: run/_pre_scan.py::check_pre_scan`, via `pre_scan_requested`, routes `run` and `api.mask` | keep the `unread` row |
| C1-T12 | with LIB L3a merged, the stored run-result record holds the `pre_scan` check. Checked 2026-11-21: PR #367 is still open (commit `c280004c` is only on `origin/feat/lib-l3a-run-result`, not an ancestor of CLI main `1eb0289c`). So the rule is: if #367 is on main when C1 is built, the test starts unmarked; if not, it is `xfail(strict=True, reason="needs #367 (LIB L3a run-result half)")`, which turns red as an unexpected pass the day #367 lands | strip checks before the store |
| C1-T13 | B13: `decoy.mask(config=...)` with an unmasked email column: `warn` gives one `PreScanWarning` and the masked frame; `fail` raises `PreScanBlockedError` and `run_pipeline` is never called (spy); a scan error raises `PreScanFailedError` with no cell text; no `pre_scan` gives no scan (spy); a `ner` detector with the model absent raises `ConfigValidationError` naming `pre_scan.detectors` and the install hint, not `PreRunCheckError` and not `PreScanFailedError`, and `scan_descriptors` is never called (spy) | remove the adapter call from `mask`; let the CLI error reach the API |
| C1-T14 | B12: each no-row refusal plus `pre_scan: {}` and an unreadable source exits 1 with its usage message and `scan_descriptors` is never called (spy). One case per refusal, on `decoy run` and (where it applies) `decoy.mask`: mask secret flag; chunked with generate, report flags, vault, fixed_width; `--vault` usage; native gate; cloud endpoint; resources; chunked integrity, quarantine, target format and strategy compatibility (`_execute.py:210-223`); plain target format (`:280`); declared-source check (`:281`). Probe once: on a passing plain run, on both `decoy run` and `decoy.mask`, `prepare_declared_sources` is called exactly once (call-count spy), because the loader receives `prepared=`; a direct `_load_sources_from_config` call without `prepared=` still runs the checks itself (one call) | place the step before `check_before_read`, or right after `check_before_run`; drop `prepared=` so the loader probes again |
| C1-T15 | B17: with the gate stubbed out (C1b not merged yet, or bypassed) and the model absent, `decoy run` exits 1 with a `PreRunCheckError` finding at `pre_scan.detectors` and the install hint, not `pre_scan.profile_failed`; `decoy.mask` with the same config raises `ConfigValidationError` with the same finding text; `check_pre_scan` itself returns `PreScanModelRefused` and raises nothing (unit) | wrap every exception; raise a route error inside the core |
| C1-T16 | B18: a `MemoryError` and an engine capacity refusal raised inside the scan give exit 5 and the capacity kind | wrap every exception |
| C1-T17 | `is_blocking_verdict` is the one predicate: `exit_code_for(PreScanBlockedError(...))` is 4; in the run handler pre-scan `fail` has category `None`, `blocking_failed` true, no traceback hint; the post-scan report writer (`_errors.py:226`) is not called for a pre-scan block; a grep test finds no other `isinstance(..., PostScanBlockedError)` in `exit_codes.py` or `run/_errors.py` outside `:226` | keep the `PostScanBlockedError` check in `exit_code_for` or at one `_errors.py` site |
| C1-T18 | B16: `decoy run --all` with one child blocked by `fail` and one clean: the child exits 4 and the parent exit follows the existing precedence | exit 0 when one child is clean |
| C1-T19 | `import decoy` does not import the engine; `decoy.PreScanWarning`, `decoy.PreScanBlockedError`, `decoy.PreScanFailedError` resolve and are the engine classes; they are in `dir(decoy)`, `decoy.api.__all__` and the compatibility inventory | leave a name out of `_LAZY_API` |
| C1-T21 | `--json` for B2 (`passed`, flagged columns all covered) and for a pure generate pipeline with `pre_scan: {}` (zero tables, zero findings) holds `pre_scan: {status: passed, detectors: [...], tables_scanned: [...], findings: []}`, the same member in both envelopes' shape | build the member from findings only |
| C1-T22 | import contract: `decoy.cli.run.__all__` holds `check_before_read` and `check_pre_scan`; `api.py` imports them from `decoy.cli.run`, not from `decoy.cli.run._execute` or `._pre_scan` (AST check) | import the private modules from `api.py` |
| C1-T20 | the drift warning text appears on the `decoy run` card and in `--json` `warnings` when `on_drift` is set | rely on the gate count line |

### C1b. Gate model preflight for pre-scan, and the drift warning (CLI, R1, ~200 lines)

After: C1. Not before it: on a head without C1, no run executes the pre-scan, so a gate refusal of a missing pre-scan model would fail a job that today succeeds. With C1 merged first, a missing model is caught by C1's `load_detector_set` step (exit 1, unwrapped, C1-T15); C1b then moves the refusal earlier, into the gate, so `decoy validate` and `decoy ci check` report it too. C1b also adds the `scan_baseline.on_drift` gate finding (4.6a), which needs `warning.drift_not_checked` from R; the run-card warning (C1-T20) is in C1.

| Test | Asserts | Mutation |
|---|---|---|
| C1b-T1 | `pre_scan: {detectors: [regex, ner]}` with the model absent: `decoy validate` and `decoy run` exit 1 with location `pre_scan.detectors` and the install hint, before any row is read | check models only when `post_scan` asks |
| C1b-T2 | no `pre_scan` block: no pre-scan model probe | probe whenever any block lists `ner` |
| C1b-T3 | `model_finding(status, block="pre_scan")` text starts "pre_scan asks for the" and its location is `pre_scan.detectors`; the `post_scan` form is unchanged byte for byte | keep the hard-coded `post_scan` text or `_LOCATION` |
| C1b-T4 | B14 and B15: `decoy validate` and `decoy ci check` with a pre-scan block never call `scan_descriptors` (spy); they only probe | scan in the gate |
| C1b-T5 | B19: `scan_baseline.on_drift: fail` gives the `warning.drift_not_checked` finding at `scan_baseline.on_drift` in `validate`, `ci check` and `run`; `validate --fail-on-warning` exits 2; no `on_drift` gives no warning | drop the finding |

### C2. Language tests and docs (CLI, R1, ~250 lines, mostly docs)

After: R (it needs the presence rule). Merge with or after C1, because the doc text describes what C1 does.

| Test | Asserts | Mutation |
|---|---|---|
| C2-T1 | `scan before` with no arguments compiles to a config whose validated dump keeps `pre_scan: {detectors: [regex]}` | the by-value drop (engine), or a lowering that skips an empty block |
| C2-T2 | `scan before(regex, on_findings: fail)` round-trips through `convert_config` | drop options in `_convert._blocks` |
| C2-T3 | `scan before(regex, on_findings: sometimes)` gives `lang.config` on that line with the engine code in brackets | lose the source span |

## 10. Docs to update

- CLI `docs/guides/decoy-language/05-checks-and-subsets.md`: what `scan before` does at run start, `on_findings`, and the cost note (head 10,000 rows per table).
- CLI `docs/guides/decoy-language/cheat-sheet.md`, `agent-card.md`, `06-from-yaml.md` (the `pre_scan` row gains `on_findings`).
- CLI run docs: the README exit-code section and the `decoy explain exit-codes` text for 4 ("a blocked pre-scan or post-scan"); one line in the `decoy run` help epilog (`_RUN_EPILOG`).
- CLI `CODEMAP.md`: `_pre_scan.py` in the "`decoy run` internals" row; G-CONFIG-READER in the sentries.
- CLI `CHANGELOG.md`, `docs/RECENTLY-SHIPPED.md`, and the PRE-SCAN-RUN row state in `docs/roadmap/groups/scan.md`.
- Engine `docs/compatibility-contract.md`: the presence rule, `on_findings`, the hash rule, the check id and the codes. Engine `CODEMAP.md` row 73 (`pre_scan_check.py`) and `CHANGELOG.md`.
- Engine `config/_pre_scan.py` docstring: "Pre-scan only suggests" becomes "Pre-scan suggests in `decoy scan` and checks coverage at run start".
- CLI `gate/_models.py` docstring (the plan 4.1 matrix line).
- CLI `src/decoy/api.py` `mask` docstring and the Python API guide: `mask` runs a declared pre-scan; `PreScanWarning`, `PreScanBlockedError`, `PreScanFailedError`.
- Engine `reasons/pre_scan/_part1.py` DRIFT comment and the `on_drift` text in the compatibility contract: the run-start drift check is planned (row 32), not shipped; the run warns with `warning.drift_not_checked` until it lands.
- Vault `30_Resources/Decoy-Language-to-Delivery.md` section 11 (gaps): mark the gap closed when C1 merges.
- Vault `engine-repin-checklist`: classify new config fields in `config-field-readers.json`.
- Engine `plan/scan-checks` (section 5.4): a note that D-2 reuses the step in `run/_pre_scan.py` and its scan result instead of a separate `_drift.py` rescan. A note on that branch, not a rewrite.

## 11. Freeze and frozen contracts

**This is a 1.0 freeze item.** By the ROADMAP section 3 tests it changes an output and an exit code for configs that were accepted and silently ignored: a pipeline that writes `pre_scan` now scans, can print warnings, and under `fail` exits 4. C1b also adds a gate refusal for a missing pre-scan model. Both must land before the freeze, because after 1.0, turning on a dormant block is a behaviour change to a released contract.

Additive, under the existing versions:

- Config: `pre_scan.on_findings` (new key, default dropped from the dump). A reader from before this change refuses the new key (the `on_drift` precedent).
- Dump: a written default `pre_scan` block now stays in the dump. `pipeline_config_hash` and the plan hash do not change for it (`pre_scan` is unhashed). Under `on_findings: fail`, the effective `on_findings`, `detectors` and `ner_model` are hashed.
- Reason adapter: two new coded families (`PreScanBlockedError`, `PreScanFailedError`, namespace `pre_scan`).
- Exit-code map: `exit_code_for` returns 4 for `PreScanBlockedError`, through the one predicate.
- Check order: config-only refusals that today run inside the source loader now run, unchanged, before the pre-scan. For a config without `pre_scan` the order and the outcome are the same as today.
- `decoy-run-result/v1`: check id `pre_scan`; tolerant readers keep it as a token.
- Registry: three codes (`pre_scan.uncovered_pii`, `pre_scan.uncovered_pii_blocked`, `warning.drift_not_checked`), one minor.
- `--json` run envelope: a `pre_scan` member, present only when the pre-scan ran. C1 regenerates the frozen shapes snapshot.
- Python API (`decoy` public names): `PreScanWarning`, `PreScanBlockedError`, `PreScanFailedError`; `decoy.mask` raises or warns for a config with a `pre_scan` block. A config without one is unchanged.
- Gate: a new warning finding for a set `scan_baseline.on_drift`. Under `validate --fail-on-warning` this changes exit 0 to 2 for such a config; no shipped example sets `on_drift`.

Exposure check (2026-11-21): no shipped example, `decoy init` scaffold or CLI writer emits `pre_scan`. The `.decoy` guides show `scan before(regex)` in examples. Those examples now scan, which is what the guide says they do.

## 12. Risk tiers

| Slice | Tier | Why | Gate |
|---|---|---|---|
| C0 | R1 | test-only, CLI; a ratchet manifest | Codex |
| E1 | R2 | config schema, plan hash, run-result wire, registry | Codex and Dennis |
| E2 | R2 | value-free boundary for a new engine output | Codex and Dennis |
| R | R1 | release train and repin checklist | as the train |
| C1 | R2 | changes exits and outputs of `decoy run` and `decoy.mask`; frozen `--json` shapes and public API names; value-free error path | Codex and Dennis; full suite (frozen contract trigger) |
| C1b | R1 | a gate model finding and one gate warning, existing patterns | Codex |
| C2 | R1 | tests and docs | Codex |

Order, strict: E1, E2, R (engine release and CLI repin), C0, C1, C1b, C2. C0 lands on the repinned engine so its walk sees `on_findings` from the start. C1b and C2 each need C1 on main.

## 12a. Class table

| # | Class | Where it applies | Structure that closes it | Proof | Mutation that must turn it red |
|---|---|---|---|---|---|
| 1 | Value-bearing output | finding lines, `--json` member, run result check, scan error text | the verdict holds names and detector sources only, built from the value-free `scan-set/v1` core; scan errors become `PreScanFailedError` with fixed text | E2-T7, C1-T6, C1-T7 | copy a sample into findings; pass `str(exc)` |
| 2 | Cleanup missing on an exit path | `fail` stop; scan error | the step runs before the run folder opens, before the source load and before key admission, so nothing exists to clean | C1-T5, C1-T6 | move the step into `execute` |
| 3 | State and concurrency | `ctx._pre_checks` across `--all` children | each child is its own process with its own `RunContext`; no shared cache beyond the existing per-process model cache | C1-T18 | store the verdict in a module global |
| 4 | Route parity and silent fallback | plain, `--chunked`, `--duckdb-source`, `--rows`, `decoy.mask`, YAML and `.decoy` | one core (`check_pre_scan`) on every source-reading route, placed after the usage refusals; one scan call; one switch helper; the sentry checks both routes | C1-T8, C1-T9, C1-T3, C1-T13, C0-T3 | skip the step on `--chunked`; drop it from `mask` |
| 5 | Referential integrity | config tables against scanned tables; column names against field names | exact table and column name match; a table missing from the core is a `not_scanned` finding (fail closed), not guessed | E2-T6 | skip it, or match by prefix |
| 6 | Untrusted producer | config values; source files | strict `Literal` for `on_findings`; sources read only through `scan_descriptors` and the engine's validated descriptors | E1-T4, C2-T3 | widen the literal |
| 7 | Check then use (TOCTOU) | the scan reads a head sample, then the run reads the source again | stated limit: a source that changes between the two reads is not detected (the same limit as `decoy scan` then `decoy run`); the coverage rule is about columns, which a mid-run edit to rows does not change | doc note, F11 | n/a (recorded known limit) |
| 8 | Weak tests | coverage and policy tests | every verdict test has a passing and a failing case; e2e tests assert exit, check status and the absence of output under `fail` | E2-T5, C1-T4, C1-T5 | swap the policy branch |
| 9 | Refactor drift | configs without `pre_scan`; the run path later refactored | byte-identical dump and envelope when absent; G-CONFIG-READER keeps a reader on the run path | E1-T1, C1-T1, C0-T3 | restore the by-value drop; delete the call |
| 10 | Frozen contract drift | config schema, plan hash, `decoy-run-result/v1`, registry, `--json` shapes | additive members recorded in `docs/compatibility-contract.md`; new reason codes `since=UNRELEASED`; shapes snapshot regenerated | E1-T3, E1-T6, C1-T1 | strict `CheckId` read |
| 11 | Parallel tables kept by hand | "passthrough" strategy names; config field list against the reader manifest | the verdict reads the strategy name from the engine catalog constant for passthrough; the sentry walks the live model, not a copied list | E2-T2, C0-T1, C0-T5 | hard-code a second passthrough list |

## 12b. Pre-mortem

It is three months after 1.0 and this row went wrong. The likely reasons, and the guard for each:

- **`fail` blocks every real pipeline.** Free-text columns and ID columns trip the regex detectors and users leave them as `keep`. Guard: `warn` is the default; the docs say how to read a finding; Q5 (dismissals) is the named next step if this shows up in QA.
- **The pre-scan is slow on wide tables with NER on.** Guard: the head sample is bounded; the docs state the cost; the card shows the pre-scan as its own line so the time is visible.
- **D-2 adds a second rescan anyway.** Guard: this plan and a note on the scan-checks plan name one step; G-ONE-SCAN-CALL keeps one call; review of D-2 checks it.
- **A producer turns pre-scans on for everyone.** Guard: F13 check; the presence rule is pinned by E1-T1 and documented in the compatibility contract.
- **The sentry is muted by a broad manifest entry.** Guard: each `engine` entry names a public function whose AST references the key; each `cli` entry gives exact call chains per route, checked link by link; `unread` is a ratchet.

## 13. Open questions (each with a recommended answer)

- **Q1. What turns the pre-scan on?** (a) The presence of the block or statement. (b) A new explicit key (`pre_scan.run: true`, or `on_findings` with no default where absent means off). Recommended: (a). It matches "yes/no on prescan", needs no language change, and makes `scan before` mean what its guide says. Cost: a dump rule by presence instead of by value, which E1-T1 pins. (b) would leave the existing `scan before(...)` statements silently off, which is the bug.
- **Q2. What counts as a finding?** Recommended: a flagged source column (regex `pii_candidate`, or a model hit with band `high`) whose effective strategy is `passthrough`, that has no rule, or whose rule has a `when:` condition (partial coverage, `partial: true`); plus every mask table absent from the scan core (`not_scanned`, fail closed). Not every PII candidate: a run that masks every flagged column must pass, or `fail` would block every real pipeline.
- **Q3. A pre-scan file on disk?** Recommended: no for 1.0. The report is the run result check, the `--json` member and stderr. A `fail` run opens no run folder, so a side file would exist only for warn runs, which is inconsistent. The full scan is one command away (`decoy scan`). Later candidate.
- **Q4. Sampling settings in the config?** Recommended: no for 1.0. Fixed head of 10,000 rows, the `decoy scan` default, stated in the docs. Later candidate: `pre_scan.rows`.
- **Q5. Dismissals?** Recommended: not in this row. Under `fail`, the user masks the column or uses `warn`. Later candidate: `pre_scan.dismissed` with the `post_scan.dismissed` shape.
- **Q6. A library record for the run-start scan?** Recommended: no. The run-result record (LIB L3a, PR #367) carries the check once it merges. A stored `scan` record is LIB L2's job.
- **Q7. Run the pre-scan under `--chunked`?** Recommended: yes. The head sample is bounded, and a chunked run that skips a declared pre-scan is the same silent gap.
- **Q8. Where does the sentry live?** Recommended: the CLI, because only the composer of the run can see whether a field is used. Engine field additions surface at repin.

## 14. Dependencies

- LIB L3a (CLI PR #309, evidence half; PR #367, run-result half): not a blocker. The check rides the run result document, which `_result.py` already builds on main. When #367 merges, the stored record carries the check with no change here (C1-T12).
- Row 32 DRIFT D-2 (Later): reuses the step from C1. Recorded on the scan-checks plan.
- PR #368 (the roadmap row text): the row exists only on that branch. This plan does not depend on it, but the row state update in C1 does.
- Reason codes: new codes carry `since=UNRELEASED`; the release stamp versions them, so no slice bumps the registry.

## 15. Expected size

Engine: 1 new module (`profiling/pre_scan_check.py`), 8 changed (with `reason_adapter.py`). Public names added: `pre_scan_requested`, `evaluate_pre_scan`, `PreScanVerdict`, `PreScanBlockedError`, `PreScanFailedError`, `PreScanWarning`, the codes `pre_scan.uncovered_pii`, `pre_scan.uncovered_pii_blocked` and `warning.drift_not_checked`, the check id `pre_scan`, the config key `pre_scan.on_findings`. About 760 lines with tests over E1 and E2.

CLI: 2 new modules (`run/_pre_scan.py` and the sentry), one manifest, one e2e package, 9 changed (with `api.py` and the gate). Public names added: the `--json` member `pre_scan`, the card line, `decoy.PreScanWarning`, `decoy.PreScanBlockedError`, `decoy.PreScanFailedError`, the sentry id G-CONFIG-READER. About 1,550 lines with tests and docs over C0, C1, C1b and C2.
