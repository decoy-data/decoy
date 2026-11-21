Status: plan

# PRE-SCAN-RUN: run the declared pre-scan at the start of `decoy run`

Date: 2026-11-21. Repos: engine and CLI. Row: PRE-SCAN-RUN in `docs/roadmap/groups/scan.md` (1.0 table, added by open PR #368, branch `docs/roadmap-dataflow-gaps`).

Rules consulted: `~/dev-rules/README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md`, `profiles/local-operations.md`, `feature-dev.md`, `api-and-compatibility.md`, `cross-cutting-concerns.md`, `architecture.md`, `testing.md`, `workspace-and-vcs.md`; CLI `docs/roadmap/working-rules.md` (sections 3 and 4).

Read from: CLI origin/main (2026-11-21, near `697ce68a`), engine origin/main (2026-11-21, near `92916e6e`), engine branch `plan/scan-checks` (`docs/plans/2026-11-16-scan-checks.md`, section 5, row 32 DRIFT), CLI PRs #309 and #367 (LIB L3a), vault `30_Resources/Decoy-Language-to-Delivery.md`.

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

1. A pipeline that writes a `pre_scan` block (YAML) or a `scan before(...)` statement (`.decoy`) gets a pre-scan at the start of every `decoy run` that reads sources. A pipeline without one gets none, exactly as today.
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
- Partial coverage inside one column (a strategy with a `when` condition). A column with any non-passthrough rule counts as covered. Recorded as a known limit.
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
- Plan hash: `pre_scan` stays in `_UNHASHED_BLOCKS`. `pre_scan.on_findings` is hashed only when it is `fail`, because only `fail` can refuse a run (the `scan_baseline.on_drift` rule). Detectors, `ner_model` and `warn` stay out: they change no output. The two "hashed control" rules move out of `plan/_compile.py` (670 lines, ceiling 700) into a new `plan/_hashed_controls.py`.
- `ner_model` keeps its rule (needs `ner` in `detectors`). The existing checks do not change.

Why presence and not a new `enabled` key: the owner's baseline is "yes/no on prescan", and in both writers the user already says yes by writing the block or the statement. No new syntax, and `scan before` keeps the meaning its guide already gives it. The alternative is in section 13 Q1.

### 4.2 The coverage verdict (engine)

`decoy_engine.profiling.evaluate_pre_scan(config, core) -> PreScanVerdict`, a pure function in a new module `profiling/pre_scan_check.py`, beside `bound_baseline.py::evaluate_drift`. It is engine-owned so the platform runs the same rule (ROADMAP section 2, "Engine contracts stay platform-ready").

Inputs: the validated config dict and a `scan-set/v1` core dict (value-free).

Rule, per mask table in the config that the core holds:

- A field is **flagged** when `pii_candidate` is true, or it has a model hit with band `high` from a detector in `pre_scan.detectors`. Model hits with band `review` are counted, not flagged.
- A flagged field is **covered** when the column rule for it has a strategy other than `passthrough`. `from_parent` counts as covered.
- A flagged field is **uncovered** when it has no column rule (an unconfigured column) or its rule is `passthrough` (`keep` in `.decoy`).
- Generate tables have no source and are not scanned.

Output: `PreScanVerdict(status, findings, counts, code)`.

| status | When | Code | Blocking |
|---|---|---|---|
| `passed` | no uncovered field | none | no |
| `warned` | uncovered fields, `on_findings: warn` | `pre_scan.uncovered_pii` | no |
| `failed` | uncovered fields, `on_findings: fail` | `pre_scan.uncovered_pii_blocked` | yes |

`findings` is a sorted tuple of `(table, column, sources)`, where `sources` names the detectors that flagged the field. Names only. `counts` maps to the run result `CheckCounts`: `pass` = covered flagged fields, `warning` or `fail` = uncovered fields, `error` = 0. `to_check()` returns the run result `Check` with id `pre_scan`.

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

New module `src/decoy/cli/run/_pre_scan.py`, one public function `run_pre_scan(ctx) -> None`. One call in `_prepare.prepare`, placed:

- after `check_before_run` returns the validated `ctx.config_dict`, so a config error wins without a source read, and `--duckdb-source` tables are already staged to Parquet and are scanned as `decoy scan` would see them;
- before `_load_sources_from_config`, so `fail` stops before the full source load, and before the run folder opens, so `fail` writes nothing.

This is the position the scan-checks plan gives D-2 (its section 5.1). D-2 later adds its drift check to the same step and the same scan result. It must not add a second rescan.

What the step does:

1. `pre_scan_requested(ctx.config_dict)`; return when false. No scan, no check, no output change.
2. Build the descriptors from `resolved_source_config(ctx.config_dict, ctx.config.parent)["sources"]`, mask tables only.
3. Call `scan_descriptors(descriptors, rows=DEFAULT_SCAN_ROWS, strategy="head", pre_scan=<the PreScanConfig>)`. Model detectors load strictly before the first table; the gate (4.6) has already refused a model that cannot run.
4. `evaluate_pre_scan(ctx.config_dict, run.core)`; keep `verdict.to_check()` on `ctx._pre_checks`.
5. `warned`: one stderr line per finding, `warning: pre-scan: <table>.<column> looks like PII (<sources>) and is not masked`, then continue. `failed`: raise `PreScanBlockedError` (a CLI type) that carries the verdict.
6. Any exception from the scan: re-raise as `PreScanFailedError` with `pre_scan.profile_failed` and fixed text, `from None`. Never `str(exc)`: an engine read error can quote a cell (the rule `decoy scan` already follows in `_multi.py`).

Wiring in the existing modules:

- `_result.py`: `_build` passes `ctx._pre_checks` to `build_run_result(pre_checks=...)`. One line.
- `_errors.py`: `PreScanBlockedError` takes the `PostScanBlockedError` arm (category `None`, status `findings`, exit 4, no traceback hint, a fixed summary text). `PreScanFailedError` is a runtime failure (exit 3) with its code.
- `_render.py`: the `--json` envelope gains `pre_scan: {status, detectors, tables_scanned, findings: [{table, column, sources}]}` when the pre-scan ran, and no member otherwise. The card gains one `Pre-scan` line (`passed`, or `2 unmasked PII columns (warn)`).
- `RunContext` gains `_pre_checks` and `_pre_scan` (the verdict). Two fields.

### 4.6 Model preflight (CLI gate)

`src/decoy/cli/gate/_models.py` also checks the `pre_scan` models when `pre_scan_requested(config)` is true. Today it checks only `post_scan` models, and its docstring says "a `pre_scan` model is the scan's to refuse". That was true while only `decoy scan` read the block. Now `decoy validate`, `decoy ci check` and `decoy run` refuse an unavailable pre-scan model before any row is read, with exit 1 and the same install hint, at location `pre_scan.detectors`.

### 4.7 Run variants

| Variant | Pre-scan |
|---|---|
| plain `decoy run` | runs |
| `--chunked` | runs (head sample, bounded); the chunked branch reads sources itself afterwards |
| `--duckdb-source` | runs on the staged Parquet |
| `--all` | each child process runs its own pipeline's pre-scan |
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

- Pre-scan absent: the step returns at once (`src/decoy/cli/run/_prepare.py:380` is the `check_before_run` call it follows).
- `passed` or `warned`: the run continues to the source load (`src/decoy/cli/run/_prepare.py:535`) and ends through `_render.finish`.
- `failed`: `PreScanBlockedError` goes to the one error handler, the `PostScanBlockedError` arm (`src/decoy/cli/run/_errors.py:192`), exit 4.
- Scan error: `PreScanFailedError`, runtime arm, exit 3.
- Model cannot run: gate refusal before the run starts (`src/decoy/cli/gate/_models.py:20`), exit 1.

### Routes

- Plain branch: `run_pipeline` in `src/decoy/cli/run/_execute.py:359`; the step runs before it, in `prepare`.
- Chunked branch: `_run_chunked_mask` in `src/decoy/cli/run/_execute.py:75`; the step runs before it too.
- `--duckdb-source`: staging in `src/decoy/cli/run/_prepare.py:316`, before the gate; the step scans the staged Parquet.
- Preview (`--rows`): `prepare_preview` (`src/decoy/cli/run/_prepare.py:259`); no step.
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

## 6. Failure modes

| # | Failure | Behaviour and code | Exit | Test |
|---|---|---|---|---|
| F1 | Block parsed and ignored again (a refactor drops the call) | G-CONFIG-READER sentry fails; e2e B4 and B5 fail | n/a | C0-T3, C1-T4, C1-T11 |
| F2 | A default block dropped by the dump (the by-value rule comes back) | engine test fails; `scan before(regex)` gets no scan | n/a | E1-T1, C2-T1 |
| F3 | Scan error text leaks a cell value | `PreScanFailedError` carries `pre_scan.profile_failed` and fixed text only | 3 | C1-T6, C1-T7 (canary sweep) |
| F4 | A finding line echoes a sampled value | lines hold table, column and detector source names only | n/a | C1-T7, E2-T7 |
| F5 | `fail` stops after outputs are written | the step runs before the source load and before the run folder opens | 4 | C1-T5 (read spy, no folder) |
| F6 | A second scan implementation appears | G-ONE-SCAN-CALL (`scan-call-allow` must not grow) | n/a | existing sentry, C1-T3 |
| F7 | A missing model is found only mid-run | the gate preflight refuses first | 1 | C1b-T1 |
| F8 | `on_findings: fail` added without moving the hash | plan hash test fails | n/a | E1-T3 |
| F9 | Unknown `on_findings` value | engine literal-error code at the field location, no value echoed | 1 | E1-T4, C2-T3 |
| F10 | An older reader meets check id `pre_scan` | the tolerant read keeps it as a token | n/a | E1-T6 |
| F11 | Pre-scan on a very large source | head sample of 10,000 rows per table; model detectors cost more; stated in the docs | n/a | docs |
| F12 | `--duckdb-source` scanned before staging | the step is after `check_before_run`; the staged Parquet is scanned | as case | C1-T8 |
| F13 | A config producer writes a default `pre_scan` block everywhere and turns scans on for all | checked 2026-11-21: no shipped example, `decoy init` scaffold or CLI writer emits `pre_scan`; the platform is parked | n/a | C0 manifest review |

New exit code: none. All cases reuse 0, 1, 3 and 4. No owner call is needed for exit codes.

## 7. The sentry (G-CONFIG-READER)

Where: CLI `tests/sentry/config/test_config_field_readers.py`, with the manifest `tests/sentry/baselines/config-field-readers.json`. The CLI composes the run, so only the CLI can see whether a field the engine accepts is used on the run path. The drift case shows why an engine-side check is not enough: `evaluate_drift` exists in the engine and nothing calls it.

What it walks: the pinned engine's `PipelineConfig.model_fields`, every top-level field, plus the fields of the control blocks `pre_scan`, `post_scan`, `scan_baseline`, `delivery`, `quarantine` and `subset` (one level down, through `Optional`). The list comes from the live model, not from the manifest.

Each walked path must have exactly one manifest entry, of one kind:

- `{"engine": "decoy_engine.<module>:<name>"}`: consumed inside `run_pipeline` or `compile_plan`. The sentry imports the name and checks that its source (`inspect.getsource`, parsed with `ast`) holds the key as a string constant or an attribute name.
- `{"cli": "src/decoy/cli/<path>.py::<function>", "via": "<engine helper>"}`: read on the CLI run path. The sentry checks that the function exists, that its body references the key or calls the helper named in `via` (for `pre_scan`: `pre_scan_requested`), and that a module in `src/decoy/cli/run/` calls the function (one hop, by AST).
- `{"other_command": "<command>", "row": "<row id>"}`: read only by another command (for example `scan_baseline.path` by `decoy scan --compare`).
- `{"unread": "<row id>"}`: accepted and read by no run. A ratchet: the list may shrink and never grows without a reviewed change (`tests/sentry/_ratchet.py`, the X0a pattern). At C0 merge it holds `pre_scan` (PRE-SCAN-RUN) and `scan_baseline.on_drift` (row 32 DRIFT). C1 removes `pre_scan`.

A new engine field after a repin fails the sentry until it is classified. The vault `engine-repin-checklist` gains that line.

Mutations that must turn it red, each seen before merge (the cross-cutting rule "prove the walk sees a bypass"): delete the `run_pre_scan` call from `_prepare.prepare`; add a field with no entry to a fixture `PipelineConfig` subclass; add a row to `unread`.

## 8. Placement

| File | Repo | Change | Why here | Size after |
|---|---|---|---|---|
| `src/decoy_engine/config/_pre_scan.py` | engine | `on_findings` field; `pre_scan_requested` helper | owns `PreScanConfig` | 98 to ~125 |
| `src/decoy_engine/config/_pipeline.py` | engine | the dump keeps a written `pre_scan` (presence rule) | owns the dump | 539 to ~542 |
| `src/decoy_engine/plan/_hashed_controls.py` | engine | new: the `scan_baseline.on_drift` hash rule moved here, plus `pre_scan.on_findings: fail` | `_compile.py` is at 670 of 700; plan package | ~50 |
| `src/decoy_engine/plan/_compile.py` | engine | calls the helper; shrinks | | 670 to ~660 |
| `src/decoy_engine/profiling/pre_scan_check.py` | engine | new: `evaluate_pre_scan`, `PreScanVerdict` | engine CODEMAP row 73 (`bound_baseline.py`, `evaluate_drift -> DriftVerdict`); sits beside it | ~150 |
| `src/decoy_engine/profiling/__init__.py` | engine | export the two names | public profiling API | 178 to ~182 |
| `src/decoy_engine/reasons/pre_scan/_part1.py` | engine | two codes; registry minor | the `pre_scan` namespace | 108 to ~130 |
| `src/decoy_engine/run_result/_model.py`, `_build.py` | engine | `CheckId` gains `pre_scan`; `pre_checks` accepts it | the one run result constructor | 411 and 274, +~8 |
| `docs/compatibility-contract.md`, `CHANGELOG.md`, `CODEMAP.md` row 73 | engine | additive entries | | |
| `src/decoy/cli/run/_pre_scan.py` | CLI | new: `run_pre_scan`, `PreScanBlockedError`, `PreScanFailedError` | CLI CODEMAP row "`decoy run` internals", `run/_<noun>.py`; the package goes from 12 to 13 modules | ~140 |
| `src/decoy/cli/run/_prepare.py` | CLI | one call | owns the phase order | 546 to ~550 (run package cap 600, `test_run_package_shape.py`) |
| `src/decoy/cli/run/_errors.py`, `_result.py`, `_render.py`, `_context.py` | CLI | error arms, `pre_checks`, the `--json` member and card line, two fields | existing owners | each +3 to +25, all under 600 |
| `src/decoy/cli/gate/_models.py` | CLI | pre-scan models when requested | the gate's model preflight | 54 to ~70 |
| `tests/sentry/config/test_config_field_readers.py`, `tests/sentry/baselines/config-field-readers.json` | CLI | new sentry and manifest | sentries live in per-concern packages under `tests/sentry/` | ~180; manifest ~60 entries |
| `tests/e2e/pre_scan_run/` | CLI | new e2e package | CLI CODEMAP: new e2e tests go in a package, not the flat folder | ~350 |
| `tests/unit/lang/` (existing language tests) | CLI | round-trip cases | | ~40 |
| `tests/fixtures/release_freeze/json-shapes.json` | CLI | the `pre_scan` member in the run success shape | the frozen `--json` shapes snapshot | regenerated by `write_shapes.py` |

**Design notes.** No new abstraction beyond one module per repo. The verdict follows `evaluate_drift` (pure, value-free, engine-owned). The run step takes the scan-checks D-2 position. The sentry follows the X0a ratchet. One place per fact: the switch in `pre_scan_requested`, the coverage rule in `evaluate_pre_scan`, the scan call in `scan_descriptors`, the exit in `exit_code_for`. Owner question (working rules 4.3), "could it be rolled into a central location?": yes, the run-start step is the one place for every run-start scan check, and D-2 must join it.

## 9. Slices and acceptance tests (red first, with a hostile corpus)

The hostile corpus is the canary source of C1-T7 and E2-T7: cells that hold canary strings, an email-shaped value in a `keep` column, and a CSV row that the reader rejects. Each slice is independently mergeable. Acceptance tests are written first and seen red before the code, each under the named mutation.

### C0. Sentry G-CONFIG-READER (CLI, R1, ~300 lines)

After: none. Lands on the current engine pin with `pre_scan` and `scan_baseline.on_drift` in the `unread` ratchet.

| Test | Asserts | Mutation that turns it red |
|---|---|---|
| C0-T1 | every walked `PipelineConfig` path has exactly one manifest entry | remove one entry |
| C0-T2 | an `engine` entry's source references its key | point an entry at a function that does not |
| C0-T3 | a `cli` entry is called from `src/decoy/cli/run/` | move the call out of the run package |
| C0-T4 | `unread` can only shrink | add a row to `unread` |
| C0-T5 | a fixture subclass with one extra nested field fails the walk | make the walker skip nested blocks |

### E1. Engine config, codes and check id (engine, R2, ~380 lines)

After: none. Reason registry minor; rebase the bump if another registry slice merges first.

| Test | Asserts | Mutation |
|---|---|---|
| E1-T1 | a written default `pre_scan` survives `model_dump` and re-validation; an unwritten one is dropped; the dump of a config without it is byte-identical to the frozen corpus | restore the by-value drop |
| E1-T2 | `pre_scan_requested` is true for `pre_scan: {}` and false for no block | return `bool(config.get("pre_scan"))` (an empty dict is false) |
| E1-T3 | the plan hash moves for `on_findings: fail`, not for `warn`, `detectors` or `ner_model` | hash the whole block, or never hash it |
| E1-T4 | `on_findings: maybe` is refused at `pre_scan.on_findings` with the literal-error code and no value in the message | widen the literal |
| E1-T5 | `build_run_result(pre_checks=(pre_scan failed blocking,))` gives status `findings`, exit 4 | drop `pre_scan` from the accepted set |
| E1-T6 | `RunResultRead` reads a document with check `pre_scan`; an older-shape reader fixture keeps it as a token | make the read model strict on `CheckId` |
| E1-T7 | the two codes are registered with `since` and fixed text | remove one from `__all__` |

### E2. Coverage verdict (engine, R2, ~330 lines)

After: E1 (codes, check id). Mergeable alone: no caller yet.

| Test | Asserts | Mutation |
|---|---|---|
| E2-T1 | a regex `pii_candidate` on an unconfigured column is uncovered | treat unconfigured as covered |
| E2-T2 | `passthrough` is uncovered; `hash`, `redact`, `faker` and `from_parent` are covered | treat `passthrough` as covered |
| E2-T3 | a model hit with band `high` flags; band `review` does not | flag `review` |
| E2-T4 | a model hit from a detector not in `pre_scan.detectors` does not flag | ignore the detector list |
| E2-T5 | `warn` gives `warned`, not blocking; `fail` gives `failed`, blocking; nothing uncovered gives `passed` | swap the policy branch |
| E2-T6 | generate tables are skipped; a mask table missing from the core is skipped, not an error | raise on a missing table |
| E2-T7 | the verdict, its `Check` and its `repr` hold no value from a canary core (names only) | copy a field sample into the findings |
| E2-T8 | findings are sorted by table, then column | drop the sort |

### R. Engine release and CLI repin (R1)

After: E1 and E2. Daily engine release train (owner 2026-11-09). The CLI repin follows the vault `engine-repin-checklist`. C0's walker sees `on_findings`, so its manifest entry goes in the repin commit.

### C1. Run-start pre-scan (CLI, R2, ~650 lines with tests)

After: R. Touches the exit path and the frozen `--json` shapes, so the full suite runs (escalation trigger: frozen contract).

| Test | Asserts | Mutation |
|---|---|---|
| C1-T1 | B1: no `pre_scan`: `scan_descriptors` is never called (spy) and the `--json` envelope equals the frozen snapshot | always scan |
| C1-T2 | B2 and B3: exit 0, check `passed` | drop `pre_checks` from `_result._build` |
| C1-T3 | the run calls `scan_descriptors` and no other engine scan function; `scan-call-allow` unchanged | call `decoy_engine.scan_sources` directly |
| C1-T4 | B4: an unmasked email column under `warn`: exit 0, one stderr line naming `table.column`, check `warned`, output written | drop the stderr line, or block |
| C1-T5 | B5: the same under `fail`: exit 4, status `findings`, no run folder, no target file, no vault file, and `_load_sources_from_config` never runs (spy) | move the step after the source load or into `execute` |
| C1-T6 | B7: an unreadable source: exit 3, reason `pre_scan.profile_failed` | pass `str(exc)` through |
| C1-T7 | canary sweep: source cells hold canary strings; under warn, under fail and with a forced scan error, no canary reaches stdout, stderr, `--json`, `--result` or the run result | echo a sample value in the finding line |
| C1-T8 | variants: `--duckdb-source` scans the staged Parquet; `--chunked` scans; `--rows` does not | place the step before `check_before_run` |
| C1-T9 | B10: the same pipeline as YAML and as `.decoy` gives the same verdict, check and exit | a lowering that drops the block |
| C1-T10 | B11: pre-scan warn plus a post-scan block: both checks, `pre_scan` first, exit 4 | replace the checks instead of prepending |
| C1-T11 | G-CONFIG-READER: `pre_scan` leaves `unread`; entry `cli: run/_pre_scan.py::run_pre_scan`, via `pre_scan_requested` | keep the `unread` row |
| C1-T12 | with LIB L3a merged, the stored run-result record holds the `pre_scan` check (skipped with a reason while #367 is open) | strip checks before the store |

### C1b. Gate model preflight for pre-scan (CLI, R1, ~150 lines)

After: R. Independent of C1. Before C1b, a missing model is found by the scan itself (exit 1, `ModelUnavailableError`). C1b moves the refusal into the gate, so `decoy validate` reports it too.

| Test | Asserts | Mutation |
|---|---|---|
| C1b-T1 | `pre_scan: {detectors: [regex, ner]}` with the model absent: `decoy validate` and `decoy run` exit 1 with location `pre_scan.detectors` and the install hint, before any row is read | check models only when `post_scan` asks |
| C1b-T2 | no `pre_scan` block: no pre-scan model probe | probe whenever any block lists `ner` |

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
- Vault `30_Resources/Decoy-Language-to-Delivery.md` section 11 (gaps): mark the gap closed when C1 merges.
- Vault `engine-repin-checklist`: classify new config fields in `config-field-readers.json`.
- Engine `plan/scan-checks` (section 5.4): a note that D-2 reuses the step in `run/_pre_scan.py` and its scan result instead of a separate `_drift.py` rescan. A note on that branch, not a rewrite.

## 11. Freeze and frozen contracts

**This is a 1.0 freeze item.** By the ROADMAP section 3 tests it changes an output and an exit code for configs that were accepted and silently ignored: a pipeline that writes `pre_scan` now scans, can print warnings, and under `fail` exits 4. C1b also adds a gate refusal for a missing pre-scan model. Both must land before the freeze, because after 1.0, turning on a dormant block is a behaviour change to a released contract.

Additive, under the existing versions:

- Config: `pre_scan.on_findings` (new key, default dropped from the dump). A reader from before this change refuses the new key (the `on_drift` precedent).
- Dump: a written default `pre_scan` block now stays in the dump. `pipeline_config_hash` and the plan hash do not change for it (`pre_scan` is unhashed). Only `on_findings: fail` moves the hash.
- `decoy-run-result/v1`: check id `pre_scan`; tolerant readers keep it as a token.
- Registry: two codes, one minor.
- `--json` run envelope: a `pre_scan` member, present only when the pre-scan ran. C1 regenerates the frozen shapes snapshot.

Exposure check (2026-11-21): no shipped example, `decoy init` scaffold or CLI writer emits `pre_scan`. The `.decoy` guides show `scan before(regex)` in examples. Those examples now scan, which is what the guide says they do.

## 12. Risk tiers

| Slice | Tier | Why | Gate |
|---|---|---|---|
| C0 | R1 | test-only, CLI; a ratchet manifest | Codex |
| E1 | R2 | config schema, plan hash, run-result wire, registry | Codex and Dennis |
| E2 | R2 | value-free boundary for a new engine output | Codex and Dennis |
| R | R1 | release train and repin checklist | as the train |
| C1 | R2 | changes exits and outputs of `decoy run`; frozen `--json` shapes; value-free error path | Codex and Dennis; full suite (frozen contract trigger) |
| C1b | R1 | a gate model finding, an existing pattern | Codex |
| C2 | R1 | tests and docs | Codex |

Order: C0 and E1 in parallel; E2; R; then C1, C1b and C2 in parallel (C2 merges with or after C1).

## 12a. Class table

| # | Class | Where it applies | Structure that closes it | Proof | Mutation that must turn it red |
|---|---|---|---|---|---|
| 1 | Value-bearing output | finding lines, `--json` member, run result check, scan error text | the verdict holds names and detector sources only, built from the value-free `scan-set/v1` core; scan errors become `PreScanFailedError` with fixed text | E2-T7, C1-T6, C1-T7 | copy a sample into findings; pass `str(exc)` |
| 2 | Cleanup missing on an exit path | `fail` stop; scan error | the step runs before the run folder opens and before the source load, so nothing exists to clean | C1-T5, C1-T6 | move the step into `execute` |
| 3 | State and concurrency | `ctx._pre_checks` across `--all` children | each child is its own process with its own `RunContext`; no shared cache beyond the existing per-process model cache | C1-T8 (`--all` cell) | store the verdict in a module global |
| 4 | Route parity and silent fallback | plain, `--chunked`, `--duckdb-source`, `--rows`, YAML and `.decoy` | one step on every source-reading route, placed after `check_before_run`; one scan call; one switch helper | C1-T8, C1-T9, C1-T3 | skip the step on `--chunked`; scan before staging |
| 5 | Referential integrity | config tables against scanned tables; column names against field names | exact table and column name match; a table missing from the core is skipped and counted, not guessed | E2-T6 | raise or match by prefix |
| 6 | Untrusted producer | config values; source files | strict `Literal` for `on_findings`; sources read only through `scan_descriptors` and the engine's validated descriptors | E1-T4, C2-T3 | widen the literal |
| 7 | Check then use (TOCTOU) | the scan reads a head sample, then the run reads the source again | stated limit: a source that changes between the two reads is not detected (the same limit as `decoy scan` then `decoy run`); the coverage rule is about columns, which a mid-run edit to rows does not change | doc note, F11 | n/a (recorded known limit) |
| 8 | Weak tests | coverage and policy tests | every verdict test has a passing and a failing case; e2e tests assert exit, check status and the absence of output under `fail` | E2-T5, C1-T4, C1-T5 | swap the policy branch |
| 9 | Refactor drift | configs without `pre_scan`; the run path later refactored | byte-identical dump and envelope when absent; G-CONFIG-READER keeps a reader on the run path | E1-T1, C1-T1, C0-T3 | restore the by-value drop; delete the call |
| 10 | Frozen contract drift | config schema, plan hash, `decoy-run-result/v1`, registry, `--json` shapes | additive members recorded in `docs/compatibility-contract.md`; registry minor; shapes snapshot regenerated | E1-T3, E1-T6, C1-T1 | strict `CheckId` read |
| 11 | Parallel tables kept by hand | "passthrough" strategy names; config field list against the reader manifest | the verdict reads the strategy name from the engine catalog constant for passthrough; the sentry walks the live model, not a copied list | E2-T2, C0-T1, C0-T5 | hard-code a second passthrough list |

## 12b. Pre-mortem

It is three months after 1.0 and this row went wrong. The likely reasons, and the guard for each:

- **`fail` blocks every real pipeline.** Free-text columns and ID columns trip the regex detectors and users leave them as `keep`. Guard: `warn` is the default; the docs say how to read a finding; Q5 (dismissals) is the named next step if this shows up in QA.
- **The pre-scan is slow on wide tables with NER on.** Guard: the head sample is bounded; the docs state the cost; the card shows the pre-scan as its own line so the time is visible.
- **D-2 adds a second rescan anyway.** Guard: this plan and a note on the scan-checks plan name one step; G-ONE-SCAN-CALL keeps one call; review of D-2 checks it.
- **A producer turns pre-scans on for everyone.** Guard: F13 check; the presence rule is pinned by E1-T1 and documented in the compatibility contract.
- **The sentry is muted by a broad manifest entry.** Guard: each `engine` and `cli` entry must name a function whose AST references the key; `unread` is a ratchet.

## 13. Open questions (each with a recommended answer)

- **Q1. What turns the pre-scan on?** (a) The presence of the block or statement. (b) A new explicit key (`pre_scan.run: true`, or `on_findings` with no default where absent means off). Recommended: (a). It matches "yes/no on prescan", needs no language change, and makes `scan before` mean what its guide says. Cost: a dump rule by presence instead of by value, which E1-T1 pins. (b) would leave the existing `scan before(...)` statements silently off, which is the bug.
- **Q2. What counts as a finding?** Recommended: a flagged source column (regex `pii_candidate`, or a model hit with band `high`) whose effective strategy is `passthrough` or that has no rule. Not every PII candidate: a run that masks every flagged column must pass, or `fail` would block every real pipeline.
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
- Reason registry minor: E1 rebases its bump if another registry slice merges first (the parallel ledger rule).

## 15. Expected size

Engine: 2 new modules (`plan/_hashed_controls.py`, `profiling/pre_scan_check.py`), 6 changed. Public names added: `pre_scan_requested`, `evaluate_pre_scan`, `PreScanVerdict`, the codes `pre_scan.uncovered_pii` and `pre_scan.uncovered_pii_blocked`, the check id `pre_scan`, the config key `pre_scan.on_findings`. About 710 lines with tests over E1 and E2.

CLI: 2 new modules (`run/_pre_scan.py` and the sentry), one manifest, one e2e package, 7 changed. Public names added: the `--json` member `pre_scan`, the card line, the sentry id G-CONFIG-READER. About 1,350 lines with tests and docs over C0, C1, C1b and C2.
