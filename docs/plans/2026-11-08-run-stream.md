Status: plan

# RUN-STREAM: one fast run path for `decoy run` (roadmap row 63a)

Owner: Cam. Author: claudeworkerbee (Opus). Date: 2026-11-08. Scope: engine and CLI, V1. Revision 6.3 (owner call 2026-11-15 on E5's lazy-input pre-check, after the Codex plan gate on revision 6.1; dispositions in section 0).

Rules consulted: `dev-rules/README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md`
(PLAN: choke point, Placement, Design notes, Established solutions), `feature-dev.md`, `architecture.md`
(layout), `reuse-first.md`, `api-and-compatibility.md`, `cross-cutting-concerns.md`, `testing.md`,
`performance.md`, `security.md`; the plan contract (`30_Resources/Decoy-Plan-Contract-and-Defect-Catalog.md`),
`LOCAL-BUILDER-BRIEF.md`, the V1 bar (a second copy of a central mechanism always blocks); the engine
`CLAUDE.md` (600/700-line module rule, established methodology, pre-GA hard delete); the CLI CODEMAP
"Where Things Go" (`CODEMAP.md:42-78`, the flat `cli/` is frozen); the code at each anchor on engine `main`
`5a7f14dc` and CLI `main` `73dd8cef` for revisions 1 to 4. Revision 5 rechecked every CLI anchor in
sections 1 to 16 on CLI `origin/main` `3007a0a` (pins `decoy-engine==0.26.0`; RUN-SPLIT #179 turned
`src/decoy/cli/run.py` into the `src/decoy/cli/run/` package) and every engine anchor it adds on engine
`origin/main` `c7433ede` (SE3b #595 merged, not yet released), against DELIV `E:plan/deliv` `0a8e8c72`
(revision 3.5) and POSTSCAN-STREAM `E:plan/postscan-stream` `9b48f31e`. Codex review also consulted
`code-review.md`, `verification.md`, `documentation.md`, and `catalogs/recurring-defects.md`.

Roadmap row 63a (`docs/ROADMAP.md:384`): plain `decoy run` streams large sources from disk by itself when
the config can be processed in pieces; relationship jobs larger than memory use the out-of-core (DuckDB)
route; `--chunked` becomes a strict switch on the same code path; Decoy settings hold max memory and max
threads, set in the setup step, with per-run flag and config overrides; defaults use the machine; the
run summary says which route ran and why. Step 1 of the row is a measurement; section 1 holds it.

## 0. Review dispositions

Revision 6.3 (owner call 2026-11-15, "redesign the pre-check"; option D, recommended):

| Finding | Disposition | Sections |
|---|---|---|
| OWNER 2026-11-15: the E5 pre-check `lazy_input_tables(config, ...)` added an entry to the post-scan route sentry's EXEMPT list, and an early `refuse_unchecked_route` call was rejected. No honest compiled-input form exists: the run's Profile needs the execution-only declared prep (`execution/_guards.py:235`), so any public builder is a new config-taking execution entry | Option D, recommended: the run decides. `lazy_input_tables` and its public export are removed. `run_pipeline` gains the keyword `resident_fallback: bool = False`; when true, a private pre-pass in `execution/pipeline/_lazy_input.py` asks the existing owners which caller `LazySource` inputs the run cannot keep lazy and reads each of them whole through `_pipeline_sources.materialize_source` before `build_run_context`. The CLI passes every candidate lazy with the keyword set. No EXEMPT entry, no guard call, no copied rule; the platform's isolated worker keeps the default and does not run the new pre-pass. E5 separately makes a no-sink lazy auto-chunk lane return resident output through the existing collector | 4, 5.1, 6.2, 6.4, 7, 8, 11-16 |
| Dennis r1 on 734aa3b8, 1 V1: the pre-pass would read sources before `stream`'s `streaming_unavailable` refusal | The pre-pass runs only for plain `auto` (not `stream`, not an explicit route); AT-E5 stream cell, M-E5k | 5.1, 8 |
| Dennis r1, DESIGN 2-4: compatibility contract, physical-seam sentry and pre-pass position unstated | E5 lists `docs/compatibility-contract.md` (new paragraph after the SUB-RUN E2 entry at `:78-80`) and `tests/sentry/test_physical_seam_disconnection.py` (changed-module record, not an exemption); the pre-pass sits after `resolve_subset` and the token-vault mode rewrite, inside the `resolve` phase | 5.1, 12-14 |
| Dennis r1, V2-LOG 5-6: refusal order on two-fault runs; CLI sentry names; preview keyword; M-E5j wording | Pre-mortem V2-LOG line; AT-C1k forbids the pre-pass names; `execute_preview` does not pass the keyword; M-E5j asserts a `LazySource` reaches `build_run_context` | 8, 14, 15 |

Revision 6.2 (Codex plan gate on revision 6.1, remediated in place):

| Finding | Disposition | Sections |
|---|---|---|
| HIGH 1 - V1: a lazy source with no sink reaches `run_auto_chunk` and asserts (`_pipeline_auto_chunk.py:433-434`), so C1l's no-sink lane cells could not work | E5 reuses the engine's existing callable sink adapter as an internal resident collector. It runs the same bounded lazy input loop, returns the collected table in `ExecutionResult.outputs`, reports resident output, and never publishes. AT-E5 and AT-C1l cover the no-sink lane before C1a | 4, 5.1, 6.2, 8, 12-14 |
| HIGH 2 - V1/DESIGN: the stated `lazy_input_tables(config, ...)` inputs do not carry source schemas, a compiled plan or a relationship graph, so the predicate could not call the exact out-of-core compatibility and dtype-hazard owners it promises without copying or guessing | E4 builds row-free lazy candidates first. E5 accepts that candidate map and uses the engine's existing bounded profiler, compiler, graph builder and routing predicates. The CLI makes no route decision. A guard rejects copied eligibility logic | 4, 5.1, 8, 11-14 |
| HIGH 3 - V1: `native_executed` could treat an `arrow_python` planned backend as compiled merely because planned and executed strings match, allowing `--native` to pass without a compiled kernel | The field now requires both an engine-registry compiled backend and equality with executed backend. AT-E5 and AT-C1n include a planned-Python equality cell and an idle compiled-kernel cell | 5.2, 6.4, 8, 13-14 |
| HIGH 4 - V1: design note 4 still told `seal_result` to reject a configured target with no output, contradicting 5.2 and today's skip | Removed the stale rejection. `seal_result` writes only returned outputs, while DELIV's declared-table file-target set remains the decision universe | 4, 5.2, 8 |
| HIGH 5 - V1: DELIV's missing-report rule withholds any applicable post-scan run, while C2 says relationship-only `--chunked` must keep today's warning-and-deliver behavior; no slice owned the exception | C2 changes the one DELIV missing-report decision to require the registered engine deferred reason, the output-unreadable warning and the closed `chunked_key_check_not_run` record together. AT-C2a covers the eventual DELIV C5 state and removes each member | 5.6, 7, 8, 14 |
| HIGH 6 - V1: `committed_table_path` returned an invented file path for a targetless table, so the engine quarantine alias guard could falsely reject a valid quarantine destination | For a targetless table it returns the stage directory itself, which no file placement may equal; targeted tables still return their exact staged path. AT-C1g covers targetless quarantine names around the sentinel | 5.2, 8 |
| HIGH 7 - V1: E5 said it calls `compile_plan`, but its API omitted the engine version, config base directory and instance locale needed to compile the same plan as the real run | The E5 API now takes the run's `engine_version`, `base_dir` and `instance_default_locale`; C1l resolves them from the same public package, config parent and config expression used by `run_pipeline`. AT-C1k records equality | 5.1, 6.4, 8, 13-14 |
| HIGH 8 - V1: a declared-cast lazy table with the internal collector would reach the auto-chunk sink refusal, and the acceptance text incorrectly required the reused `_CallableSinkAdapter` itself to carry no publication evidence | E5 excludes tables in the engine-owned declared-casting contract. The collected table and output metrics are normalized to resident, while adapter-local evidence is not exposed as run publication evidence. AT-C1l and AT-E5 cover both | 4, 5.1, 8, 14 |
| HIGH 9 - V1: if the no-sink resident collector were installed as the run-context sink, the post-scan gate would classify it as a foreign sink and turn a relationship block into an unreadable-output warning | The adapter is created only inside `run_auto_chunk`; `PipelineRunContext.sink` and its publish boundary remain `None`, and the gate receives the restored resident output. AT-E5 mutates the adapter into the context and requires the relationship verdict to change red | 4, 5.1, 8, 14 |
| DESIGN 1: E5 added a root export to `decoy_engine/__init__.py`, already exactly 600 lines, creating avoidable facade growth and a size-census edit | `lazy_input_tables` is public from `decoy_engine.execution.pipeline`, beside `route_summary`; the CLI imports that public package. The root facade is untouched | 5.1, 6.4, 12-14 |
| V2-LOG 1: current sections retained stale line anchors and slice rows named test directories rather than an auditable file set | Current anchors now point at CLI `3007a0a` and engine `c7433ede`; open slices list exact files and remain at most 10 files and 800 changed lines | 4-6, 12, 14 |

Revision 6.1 (Dennis plan gate round 2 on revision 6 at `fb0cc66`, GO-WITH-FIXES, 2 HIGH, 6
MEDIUM, 7 LOW; the last Dennis round, Codex follows):

| Finding | Disposition | Sections |
|---|---|---|
| HIGH 1 - V1: a lazy table gives the size estimator no sample (`_pipeline_routing_samples.py:37-56`, `_mem_estimate_schema.py:104`, probe skipped `_pipeline_routing_signals.py:433`), so a relationship job that is not bounded-eligible (`--fidelity`, post-validation, validators, a model post-scan ask, a vault, a generate table, an FK cycle) raises `fk_full_frame_oom_risk_rejected` (`_pipeline_routing.py:346-425`, `:407`) where the resident run fits and runs full frame | New engine slice E5 exports one predicate, `lazy_input_tables`, that names the tables that may take lazy input; a relationship job that is not bounded-eligible gets none. The CLI calls it once and copies no routing rule | 5.1, 8 (AT-C1l, AT-E5), 14 |
| HIGH 2 - V1: a lazy mask table that declares transforms defers the post-scan gate to report-only (`_post_scan.py:460-473`, `:150-155`, `:248-266`; on Windows always, `tee_supported()` `:453-457`), so `post_scan.integrity: true` and relationship runs would deliver what base blocks | `lazy_input_tables` never names a mask table that declares transforms when `post_scan_gate_applies(config)` | 5.1, 8 (AT-C1l, AT-E5) |
| MEDIUM 1 - V1: the lane records `execution_mode: "full_frame"` (`_pipeline_route_exec.py:104-112`), so a change keyed on "non-full-frame" never reaches it, and it fires in C1l with no sink | `classify_route` keys on `route_summary(...).route == "auto_chunk"` when `unified_slice_activation` is absent; moved to C1l with AT-C1n's no-sink cell | 5.2, 8, 14 |
| MEDIUM 2: `native_admitted` is fixed at preflight and is not proof a compiled kernel ran (`_chunked_evidence.py:117-124`, `:150-176`) | E5 adds `route_summary(...).native_executed`, true only when a lane column's executed backend equals its compiled planned backend; `classify_route` reads that; AT-C1n gets an idle-kernel cell | 5.2, 8, 13 |
| MEDIUM 3: C1l's safety tests sat in C1a; the switch had no vault branch | new AT-C1l in C1l holds every lazy-input safety cell; the vault rule is inside `lazy_input_tables` | 5.1, 8, 14 |
| MEDIUM 4: replacing `_prepare.py:539` drops the endpoint and target-format refusals | `_load_sources_from_config` (`_execute.py:272-299`) stays the call; C1l swaps only its per-table read loop | 5.1, 8 (M-C1c2), 14 |
| MEDIUM 5: Q8 (a)'s cost overstated; line "every question takes its recommended option" contradicted Q8; C1a did not wait on Q8 | (a) restated: lower peak, not "larger than memory" for FK jobs, and an OS kill rather than exit 5 is the likely end on Linux; owner-answer line scoped to Q1 to Q7; C1a waits on the Q8 answer | 10, 14 |
| MEDIUM 6: AT-C1b in no slice; C1a without a file list | AT-C1b goes to C1a (VM cell); C1a, C1l, E4 and E5 each list their files | 14 |
| LOW 1: 6.2 stale | 6.2 rewritten at `c7433ede` | 6.2 |
| LOW 2: the vault effect understated | 5.1 states the rejection and folds the rule into E5 | 5.1 |
| LOW 3: AT-C1k shapes | listed | 8 |
| LOW 4: DELIV's own member list lacks the seam | section 13 asks the DELIV owner to add it to DELIV's text; the result says so | 13 |
| LOW 5: no `SINK_UNUSED_CODES` literal guard | AT-C1j adds it | 8 |
| LOW 6: engine repin unowned | the repin is the orchestrator's chore PR, as for 0.26.0 (#267), outside every slice here | 14 |
| LOW 7: AT-C1c's threshold cells take one route | AT-C1c compares the recorded route with base per cell | 8 |

Revision 6 (Dennis plan gate round 1 on revision 5, NO-GO, 3 HIGH, 11 MEDIUM, 7 LOW):

| Finding | Disposition | Sections |
|---|---|---|
| H1 - V1/DESIGN: lazy input was tied to the sink, so relationship jobs (kept off the sink) still read every source whole and row 63a's out-of-core promise was not met; Q8 (a) claimed memory was bounded by the output | Lazy input no longer depends on the sink: every plain `decoy run` takes lazy input where E4 gives a backend; the engine already serves that shape to the platform and the post-scan gate reads lazy sources (`_pipeline_sources.py:1-30`, `pipeline/_post_scan.py:350-372`). Q8 (a) now states the true cost: output held in memory, input and join bounded. Q8 has no owner answer yet (the 2026-11-09 answer covers Q1 to Q7) | 5.1, 5.6, 10 Q8, AT-C1c, AT-C1j |
| H2 - DESIGN: the lazy switch sat in `execute`, after `prepare` already read every source | a new slice C1l, before C1a, replaces `src/decoy/cli/run/_prepare.py:539` (550 of 600 lines) and lands lazy input alone | 5.1, 12, 14 |
| H3 - DESIGN: `DeliverySink` has no stage-directory or non-recording staged-path member | C1a adds `stage_dir()` and `staged_path(table)` to `io/_delivery.py` as a named DELIV seam | 5.2, 10 Q7, 13 |
| M1: the spill folder is `_decoy_hold_<hex>`, not `_hold` | text, AT-C1d, AT-C1i and M-C1i2 use the real prefix | 5.2, 7, 8 |
| M2, M3, M4: fixed-width blank floats, overflow parity and identity coverage were overstated | 5.1 states the engine's actual behavior; parity is on exit and value-free text | 5.1, 7, 8 (AT-C1f, AT-C1w) |
| M5: `_table_records` read `result.outputs` | moved to `rows_written()` with the evidence and notify counts | 5.2, AT-C1g |
| M6: `seal_result` refused a target with no output table | removed; DELIV's file-target set and today's skip apply | 5.2, AT-C1e |
| M7: empty streamed tables, the `schema` keyword, batches versus tables | stated in 5.2; AT-C1m | 5.2, 8 |
| M8: 5.6 contradicted itself on `--chunked`; DELIV step 4 would withhold `--chunked` relationship runs | 5.6 states the `--chunked` rule and the DELIV CR exception | 5.6, AT-C2a |
| M9: E4 copied `_build_file_source`'s format branches | E4 moves them into one format table both builders read; AT-E4 | 5.1, 8 |
| M10: `sink_applies` codes not registered | three codes in `SINK_UNUSED_CODES` beside `CLI_WARNING_CODES` | 5.6, 6.4 |
| M11 - V1: `classify_route` marks every non-full-frame route not applicable, so `--native` would refuse every streamed run | C1a reads the lane's native evidence through E3's `route_summary(...).native`; AT-C1n | 5.2, 8, 12 |
| L1 to L7 | anchors fixed; class row 6 and section 13 stale text fixed; the abort path stated once (no CLI `except` arm); `field_key` difference stated; slice files counted with tests, CODEMAP and registries; AT-C1k gets its own sentry; steps 4 to 7 named as one shared path | 0.1, 2, 5, 7, 8, 13, 14, 16 |

Revision 5 (task T0930, 2026-11-15: make C1a build-ready; the first four items are the task, R5-5 to
R5-8 were found while checking the anchors):

| Finding | Disposition | Where |
|---|---|---|
| R5-1: CLI anchors were stale after RUN-SPLIT (#179) | Every CLI anchor in sections 1 to 16 points at CLI `3007a0a`. Rows of revisions 1 to 4 below keep the anchors of their own bases; 0.1 maps each of them to its current place | all, 0.1 |
| R5-2: section 14 did not name the DELIV slice C1a waits on | C1a waits on DELIV C2a (`DeliverySink` with the kind R `DeliveryStage` and `PreVisible`, DELIV 4.6 and 10). DELIV keeps kind A (`--out-dir`, absolute targets) on today's writers until its C2b, so a kind A run takes no sink until C1b, which waits on DELIV C2b | 5.2, 5.6, 14 |
| R5-3: `fixed_width` sources had no streaming consumer for engine SE3b (`FixedWidthLazySource`, #595 `c7433ede`) | 5.1 adds the fixed-width arm. It needs no slice of its own: C1a already needs an engine release after `c7433ede` (R5-6), and that release carries #595. C2 removes `_ChunkedFixedWidthError` | 5.1, 6.2, 8 (AT-C1w), 14 |
| R5-4: slices built since revision 4 were still planned as open | E2 (#437), E1a (#439), E1b (#442) and E3 (#459) are merged and released in 0.20.0 and 0.21.0, which is R; C3 is merged (CLI #165). Section 14 gains a Status column and these are not re-planned. C3 shipped `$DECOY_HOME/settings.json` (`src/decoy/_resources.py:31`) where 5.4 said `settings.toml`; 5.4 now states the built file | 5.4, 14 |
| R5-5 - V1: revision 4's vault journal no longer matches the code. B-6 (engine #559) makes a vault create-only, the engine refuses a `sink=` together with a `vault_writer` (B0, `execution/_pipeline_context.py:163-166`), and DELIV 3.5 keeps every published vault, including a not-delivered orphan | `TargetSink` prepares, journals and restores no vault and publishes nothing itself. A run with `--vault` takes no sink and stays resident, as today (V2 row VAULT-STREAM, `docs/roadmap/out-of-scope.md:20`). DELIV's `deliver(decision, before_visible)` is the one publication. Sink states shrink to `OPEN`, `ENGINE_COMMITTED`, `SEALED`, `ABORTED`. Class rows 2 and 3 and AT-C1d, AT-C1e and AT-C1h are rewritten | 5.2, 5.6, 7, 8, 13 |
| R5-6 - V1: the CLI cannot build a lazy CSV source. `CsvLazySource` has no public export (only `profile/_lazy_csv.py` and tests name it), and the CLI boundary sentry refuses engine private imports (`tests/sentry/test_engine_internal_boundary.py`) | New engine slice E4: one public `decoy_engine.profile.build_lazy_source(table, descriptor)` that returns the lazy backend for a format that has one and `None` otherwise. The CLI never dispatches on format to pick a reader class. C1a needs the first release carrying E4 | 5.1, 11, 12, 14 |
| R5-7 - V1: the engine post-scan gate reads back only the engine's own staged sink (`config/_post_scan.py:162-181`). Any other sink is foreign: declared relationships defer the gate to a warning, and `post_scan.integrity: true` is refused (`post_scan_sink_refusal`, `:196-210`; POSTSCAN-STREAM section 12, "Foreign sinks"). A `TargetSink` on a relationship run would drop the orphan block plain `decoy run` has today | C1a passes a sink only when `post_scan_gate_applies(config)` is false. Other jobs keep today's no-sink path: the gate runs and blocks, the output is held in memory, and the out-of-core route still spills its own work. Q8 asks the owner; the engine follow-up is in 16 | 5.6, 8 (AT-C1j), 10 Q8, 16 |
| R5-8: the `run.py` size follow-up is closed. RUN-SPLIT holds each `run/` module to 600 lines (`tests/sentry/layout/test_run_package_shape.py`) | Follow-up removed; 12 checks every touched `run/` and `io/` module against its cap | 12, 16 |

### 0.1 Anchor map (revision 4 base `73dd8cef` to CLI `3007a0a`)

| Revision 4 anchor | What it is | Now |
|---|---|---|
| `run.py:613-620`, `:616` | `--duckdb-source` snapshot to a temp Parquet file | `src/decoy/cli/run/_prepare.py:330-380` |
| `run.py:841-857` | the `--chunked` fork | `src/decoy/cli/run/_execute.py:331-345` |
| `run.py:868-878` | the plain `run_pipeline` call, no `sink` | `src/decoy/cli/run/_execute.py:364-380` |
| `run.py:884-892`, `:885-890` | native check, vault commit, then target writes | `src/decoy/cli/run/_execute.py:390-395`; `_commit_vault` at `src/decoy/cli/run/_vault.py:59-78` |
| `run.py:892` | `_write_mask_outputs` call | `src/decoy/cli/run/_execute.py:395`; body `:302-321` |
| `run.py:901`, `:904` | evidence and notify row counts from `result.outputs` | `src/decoy/cli/run/_execute.py:407`, `:410` |
| `run.py:905-908` | the `except Exception` arm | `src/decoy/cli/run/_flow.py:152-154`; the `finally` that calls `layout.abandon()` is `:155-158` |
| `run.py:1237`, `:1238` | summary `Route` row; enforce exit 4 | `src/decoy/cli/run/_render.py:158-159`; `:196` |
| `run.py:1449`, `:1462-1466` | `_run_chunked_mask` and its per-table write | `src/decoy/cli/run/_execute.py:69-143`, write at `:132-142` |
| `run.py:1512-1521`, `:1520` | per-table `check_chunked_compatibility` | `src/decoy/cli/run/_execute.py:210-230` |
| `run.py:1-4`, `:841-878`, `:1449-1509` | `run.py` size | closed by RUN-SPLIT (R5-8) |
| `src/decoy/cli/_sources.py:127-139` | whole-file and chunk readers | `read_source` `src/decoy/cli/_sources.py:169-191`; `iter_source_chunks` `:194-223` |
| `cli/io/_targets.py:163` | `check_target_formats` | `src/decoy/cli/io/_targets.py:170` |
| `cli/io/_targets.py:401-422` | targetless outputs skipped | `write_targets` `src/decoy/cli/io/_targets.py:461-497` |
| `cli/io/_targets.py:425-467`, `:445-450`, `:453-457` | `write_chunked_output`, its empty-source rule, its staged write | `src/decoy/cli/io/_targets.py:498-553`, `:528-533`, `:535` |
| `_native_gate.py:474-478` | "no output was written" | `src/decoy/_native_gate.py:465-479` |
| `cli/tokenize.py:347`, `api.py:529` | the other `run_pipeline` callers | `src/decoy/cli/tokenize.py:353`, `src/decoy/api.py:560` |
| `CODEMAP.md:42-59`, `:50` | Where Things Go; the reader and writer row | `CODEMAP.md:42-78`; `run/` row `:50`, source readers and target writers row `:53` |
| `docs/ROADMAP.md:339-341`, `:340`, `:344` | F22, CLI delivery, RUN-STREAM rows | `docs/ROADMAP.md:378` (59, F22), `:380` (61, DELIV), `:384` (63a) |
| `layout.py:29-31` | `decoy_home()` | `src/decoy/distribution/layout.py:32` |

Revision 4 (Codex round 2 on revision 3 at `37e247e`: NO-GO, 1 BLOCKER, 3 HIGH, 2 LOW):

| Finding | Disposition | Where |
|---|---|---|
| BLOCKER - V1: Q3 and the CLI `auto` mapping used the stale claim that `resolve_ooc_memory_limit(None)` returns 25% of RAM; current main returns the effective ceiling less a 20%/2 GiB reserve, so two automatic runs can overcommit a shared host | Current behavior is stated accurately. E1b exposes one engine-owned `resolve_conservative_ooc_budget_bytes()` policy that delegates to `_budget.py`'s existing `resolve_budget(None)` 25% calculation; CLI `auto` resolves it once and passes the explicit result. Other engine callers that pass `None` keep the current generous OOC default. AT-E1e runs two automatic CLI resolutions against one host and pins 25% each | 2 G4, 4, 5.4, 7, 8 (AT-E1e, AT-C3a), 10 Q3, 11-16 |
| HIGH - V1: REL-PKG was selected for V1 but was not a release prerequisite, and companion absence was accepted as a terminal C2 cell | REL-PKG's installed companion wheel is now a prerequisite for C2 and the V1 release. Companion absence remains reportable only for development installs. AT-C2d installs the release wheel and proves `--threads` reaches native execution | 2 G7, 8 (AT-C2b, AT-C2d), 10 Q1, 14 |
| HIGH - V1: the class-table state machine reversed the publication protocol | The state machine now states the exact order `SEALED -> vault journal/preparation -> vault commit -> target install -> directory fsyncs -> PUBLISHED`, with rollback armed throughout. AT-C1h asserts every transition and the crash cell between vault commit and first target install | 5.2, 7, 8 (AT-C1h) |
| HIGH - V1 / DESIGN: C3 did not name the CLI's existing atomic writer for `settings.toml` | Design notes and reuse inventory name `decoy._atomic.write_atomic(..., WriteMode.REPLACE)` as the one settings writer and `tests/sentry/test_atomic_writer.py` as its guard. AT-C3b mutates C3 to an inline temp/replace writer and requires the sentry to turn red | 4, 7, 8 (AT-C3b), 11 |
| LOW - V2-LOG: current main has ten relevant internal `execution_mode` comparison sites and `read_csv_source` moved | The comparison count and anchors now match engine `5a7f14dc`; `read_csv_source` is cited at `_csv_reader.py:462-540` | 5.1, 5.3 |
| LOW - V2-LOG: the owner-approved Mac measurement remained deferred | M1 and AT-M1 put the macOS arm64 sweep in V1 scope and make its evidence a release prerequisite; the stale follow-up is removed | 1.3, 8 (AT-M1), 10 Q5, 14 |

Revision 3 (first Codex review of revision 2 at `6b4831e`):

| Finding | Disposition | Where |
|---|---|---|
| V1-1: `commit()` sealed the sink and the state machine forbade later `write`, but `publish()` then tried to write resident `result.outputs`; full-frame does not call the sink's commit at all (`_pipeline_full_frame.py:269-305`) | `commit()` now closes only engine-owned streamed writes and records engine success. The CLI-only `seal_result(outputs)` is the one second-stage entry point: it stages resident outputs, rejects overlap or a missing target, seals everything, and returns before the native check and vault commit. `publish()` only renames sealed files | 4, 5.2, 7, 8 (AT-C1e, AT-C1g) |
| V1-2: the CLI's `except Exception` does not catch `KeyboardInterrupt`, so a signal after engine commit could leave staged files (`run.py:905-908`) | `TargetSink` is a context manager around the run, native check, vault commit and publish. Every exit before `PUBLISHED`, including `BaseException`, calls non-raising `abort()` | 5.2, 7, 8 (AT-C1d, AT-C1h) |
| V1-3: the FK split named only `gate_fk_child_edges`, but base `--chunked` uses all of `check_chunked_compatibility`, including both-orientation `code_set` and `bucket_perturb` FK checks (`_chunked.py:255-374`) | Strict preflight calls the existing compatibility gate once per mask table. The split extends B7 only when every table passes that gate; its FK component remains `gate_fk_child_edges` | 5.3, 7, 8 (AT-E1a, AT-C2a) |
| V1-4: E2's full CSV counting pass could read source rows before a strict refusal | Strict preflight runs from config plus source schema before any data-row iterator is opened. Only an admitted job may perform the bounded facts pass through the shared reader; the stream threshold remains bypassed | 5.3, 8 (AT-E1a, AT-E2a) |
| V1-5: the platform API accepts `fs_root` and `affinity`, while the frozen engine function was zero-argument; the port also used Linux-only `os.sched_getaffinity` (`api/cgroup_cpu.py:231-244`) | The engine public function preserves the injectable keyword signature, the platform delegates through the engine facade, and hosts without affinity support use `os.cpu_count() or 1`; cgroup files remain optional when absent | 4, 5.4, 8 (AT-E1d), 13 |
| V1-6: `out_of_core_threads` was not connected to the six nested `connect_duckdb` callers, so some DuckDB work would ignore the cap (`_duckdb.py:32-64`) | `run_fk_out_of_core` binds the validated cap once in a run-scoped context; every connection reads it at the single `connect_duckdb` choke point and clamps it with memory and detected CPUs | 4, 5.4, 7, 8 (AT-E1c) |
| V1-7: the new stored settings model did not reject TOML booleans and had no versioned read contract | `settings.toml` has required string `schema_version = "1.0"`; readers use strict primitives and `fullmatch`, refuse missing or unknown majors, and tolerate unknown minors and keys | 5.4, 7, 8 (AT-C3a, AT-C3b), 13 |
| V1-8: config-order target renames could leave a multi-table relationship output split across old and new generations; because `_commit_vault` runs first, the same failure could also replace the old vault while restoring old outputs (`run.py:884-892`) | `TargetSink` adapts CLI delivery's central publication session: it journals the old vault and targets, installs no target before the new vault, and restores the old generation on any caught failure (`docs/ROADMAP.md:339-341`) | 5.2, 7, 8 (AT-C1d, AT-C1h), 9 |
| DESIGN-1: putting the target/vault rollback journal in RUN-STREAM would create a second publication mechanism beside F22 and CLI delivery, whose roadmap contract already owns atomic publication and the one sink (`docs/ROADMAP.md:339-341`) | CLI delivery is now a C1 prerequisite. `TargetSink` is only the engine-protocol adapter over that central publication session; all staging, journaling, rollback, permissions and rename order stay in the delivery choke point and its guard tests | 4, 5.2, 11, 12, 14 |
| V1-9: the engine sends every output table to a supplied sink, but CLI targets are optional and today's writer skips outputs with no declared target (`_targets.py:401-422`); the planned sink would either fail that valid run or lack a `spill_parent` when there were no targets | `TargetSink` consumes and row-counts targetless tables without serializing them. Its run-wide spill parent comes from CLI delivery's protected publication scratch, not from a target path, so zero-target and distinct-target runs remain valid | 5.2, 8 (AT-C1d, AT-C1g) |
| V1-10: routing recognizes lazy inputs through concrete `isinstance(source, LazySource)` checks, so an unrelated CSV lazy class would remain resident or fail (`_chunked_input.py:115-145`, `_pipeline_auto_chunk.py:378-395`) | `CsvLazySource` is a substitutable subclass of the existing public Parquet `LazySource` and overrides its read/facts methods through the one CSV reader. Existing type choke points admit it without parallel CSV routing checks; a guard pins the subclass relationship | 4, 5.1, 7, 8 (AT-E2a), 12 |
| V1-11: the engine streamed sink regroups output at 1,048,576 rows or 256 MiB, while base `--chunked` writes each configured chunk as a Parquet row group (`_chunked_output_sink.py:69-73`, `_targets.py:453-457`), so values would match but bytes would not | Only under `stream_required`, output grouping preserves the base path's row-group boundaries from `chunk_size_rows` and PyArrow's 1,048,576-row writer cap; the 256 MiB early cut remains an `auto` policy only. CSV still uses the shared writer core | 5.3, 7, 8 (AT-E1a, AT-C2a) |
| V1-12: the summary called configured thread and memory caps resources "used" even when the route never opened DuckDB or a native kernel (`_duckdb.py:59-64`, `_pipeline.py:139-145`) | The frozen route view separates configured caps from route-applied values. An unused resource says `not_used`; native or DuckDB settings are shown as applied only from execution evidence, never inferred from the cap | 2 G5, 5.5, 6.4, 8 (AT-E3a, AT-C2b), 13 |

Revision 2 (Dennis round 2 on `337672a`: GO-WITH-FIXES, 3 HIGH, 3 MEDIUM, 2 LOW):

| Finding | Disposition | Where |
|---|---|---|
| V1-1: `TargetSink` had no `spill_parent`, so a streamed table that holds back past one row group raises `HOLD_BACK_SPILL_UNAVAILABLE` (`_chunked_output_sink.py:466-475`) where the resident run works | Superseded by revision 3: `TargetSink.spill_parent` returns CLI delivery's protected run scratch, including when there is no target; AT-C1i | 5.2, 8 |
| V1-2: the lane takes no FK config (`_planner.py:16-18`; `_pipeline_chunk_route.py:84` captures no lazy facts with edges); `gate_fk_child_edges` lives only in the pandas oracle (`_chunked.py:305`); the out-of-core force ignores the FK dtype hazard (`_pipeline_routing_fk_dtype.py:48-75`), so a chain could fail after parents were written | Superseded by revision 3: under `stream` only, every mask table must pass the complete existing `check_chunked_compatibility` gate before the B7 split; other FK configs use out-of-core only when compatible and hazard-free. `auto` is unchanged | 5.3, 6.3, 8 (AT-E1a, AT-C2a), 14 |
| V1-3: `detect_usable_cpus` would be a second copy of the platform's `effective_cores` (`decoy-platform:api/cgroup_cpu.py:231`) | E1b ports `api/cgroup_cpu.py` into the engine (citing it and its sources, automaxprocs and HotSpot); slice P1 makes the platform's `api/cgroup_cpu.py` call the engine's function; `_duckdb.py:84` uses it too | 4, 12, 14, 16 |
| MEDIUM: G4a untrue for the quarantine file; the engine never calls `abort()` after `commit()`; the eight `execution_mode` comparisons; streamed generation | G4a states the quarantine exception; `TargetSink.committed_table_path` preserves the aliasing guard; revision 3 uses a context manager for every post-commit exit; E1a translates `stream` once; generation stays resident without `bounded_write_batches` | 2, 5.2, 5.3, 6.2, 8 |
| LOW: section 9 says "during `commit`"; `detect_usable_cpus` placement | "during `publish`"; placement: `execution/pipeline/_host.py`, because `execution/out_of_core/` is frozen at 44 and the package root has 60 entries; the row names it a host probe, not spine | 9, 12 |
| Threshold "0" | `stream` bypasses the threshold check; it does not pass 0, which `require_positive_int` refuses (`physical/_snapshot.py:118`) | 5.3 |

Revision 1:

| Finding (Dennis r1) | Disposition | Where |
|---|---|---|
| B1: full frame and the mixed route never touch the sink (`_pipeline_full_frame.py:305` commit is inert unless the run streamed; `_isolated_worker.py:157-162` handles two shapes); dropping `_write_mask_outputs` (`run.py:892`) would write nothing on the most common path | Superseded by revision 3: `seal_result` is the one CLI-only resident entry point; it rejects overlap and missing targets before sealing the complete output set | 4, 5.2, 6.2, AT-C1g |
| B2: with a sink inside `run_pipeline`, `commit()` would publish before `post_run_verify` and the vault commit (`run.py:885-890`), so masked output could outlive a lost vault and `--native` would print a false "no output was written" (`_native_gate.py:476-478`) | Superseded by revision 3: engine `commit()` closes streamed writes, `seal_result` closes resident writes, and the rollback journal publishes only after the native check and vault commit | 5.2, 6.1, AT-C1h |
| H1: evidence and notify row counts read `result.outputs` (`run.py:901`, `:904`), empty on streamed runs | The sink counts rows per table; the CLI reads counts from the sink | 5.2, 6.5, AT-C1g |
| H2: under `stream`, small tables (lane threshold 100,000 rows), FK configs `--chunked` admits today (`_chunked.py:299-307`) and CSV before E2 would be refused | `stream` drops the lane's row threshold, and an FK config the lane does not take is forced to the out-of-core route (the existing `execution_mode="out_of_core"` force) instead of refused; C2 waits for E2 in a release; the C2 gate lists every config base `--chunked` accepts that the new path refuses, and a non-empty list blocks C2 | 5.3, 6.3, 14, AT-C2a |
| H3: `RunResources` was a second way to set `native_threads` and `out_of_core_budget_bytes` (`_pipeline.py:139`), and the CLI's "0.6 x ceiling - 1 GiB" a second default memory policy beside `_HOST_RAM_FRACTION` (`_budget.py:137`) | Superseded by revision 4: `RunResources` stays dropped; CLI `auto` calls the engine's public conservative policy and passes explicit bytes, while explicit flags/settings use the same pipeline keyword | 2 G4, 4, 5.4, 6.4, 10 Q3, 14 |
| Medium and low items | taken: speed claims marked single-run (1.4); E2 states how a lazy CSV gets its routing facts; the `run_pipeline` call-site sentry scoped to `cli/run.py` (`cli/tokenize.py:347`, `api.py:529` named); E1 split into E1a and E1b; `detect_usable_cpus` out of `_budget.py` (609 lines); 1.3 thread count is 8; DuckDB sources go lazy (they are Parquet snapshots, `run.py:616`); `.csv.gz` and empty-source rules stated; hostile item 2 answered | 1, 5.1, 5.2, 8, 9, 12, 14 |

## 1. Measurement (step 1 of the row)

Harness: `docs/plans/run-stream-evidence/` (`gen.py` writes a four-column string table, `t.parquet` in
1,048,576-row groups and the same rows as `t.csv`; `drive.py` runs `decoy run` end to end in a fresh
process per cell under `/usr/bin/time -v`; `engine_cell.py` calls `run_pipeline` directly). Workload per
row: `hash` on `email`, `redact` on `secret`, `truncate` on `zip`, `passthrough` on `ref`, Parquet target.
Hosts: GCP `decoy-test-6` (CLI, 8 vCPU, 32 GB) and `decoy-test-5` (engine, 8 vCPU, 32 GB), CLI
`994bc7a`, engine `7a61be3c`. Neither venv has `decoy-engine-native`; the CLI prints "native acceleration
is not installed ... Running on the Python fallback", so every cell below is the Python (pandas) path.

### 1.1 `decoy run` today (CLI)

| Rows | Source | Mode | Wall s | Peak RSS MB | Route label printed |
|---|---|---|---|---|---|
| 1M | Parquet 38 MB | plain | 13.5 | 620 | pandas (legacy adapter) |
| 1M | Parquet | `--chunked` | 13.0 | 511 | pandas chunked stream |
| 1M | CSV 76 MB | plain | 13.4 | 630 | pandas (legacy adapter) |
| 1M | CSV | `--chunked` | 13.6 | 469 | pandas chunked stream |
| 4M | Parquet 151 MB | plain | 44.1 | 1,563 | pandas (legacy adapter) |
| 4M | Parquet | `--chunked` | 42.4 | 651 | pandas chunked stream |
| 4M | CSV 304 MB | plain | 48.6 | 1,875 | pandas (legacy adapter) |
| 4M | CSV | `--chunked` | 47.3 | 480 | pandas chunked stream |
| 16M | Parquet 606 MB | plain | 240.2 | 5,056 | pandas (legacy adapter) |
| 16M | Parquet | `--chunked` | 219.2 | 1,130 | pandas chunked stream |
| 16M | CSV 1,216 MB | plain | 278.7 | 6,809 | pandas (legacy adapter) |
| 16M | CSV | `--chunked` | 261.5 | 484 | pandas chunked stream |

Threads (Arrow's CPU pool, `OMP_NUM_THREADS`, plain Parquet run): 1M rows 11.9 s at 1 and 12.0 s at 8;
4M rows 42.9 s at 1 and 47.6 s at 8; 16M rows 274.7 s at 1 and 253.5 s at 8, with the default run
at 240.2 s, so the spread between single runs (about 15%) is larger than any thread effect. No
reliable speedup: the Python path masks on one core and Arrow's pool only decodes Parquet.

What this shows:

- Plain `decoy run` never streams. `_sources.read_source` loads every Parquet source whole
  (`src/decoy/cli/_sources.py:179-182`) and CSV through pandas then `from_pandas` (`:183-185`);
  `run/_execute.py` calls `run_pipeline` with no `sink` (`src/decoy/cli/run/_execute.py:364-380`; at
  the measurement base it also passed default resources, before C3). Peak
  memory grows with the file: 8 to 16 times the Parquet file size, 5 to 8 times the CSV size.
  At 16M rows a plain CSV run peaks at 6.8 GB.
- `--chunked` is bounded (470 to 1,130 MB at every size) but is a second engine path:
  `run_mask_pipeline_chunked` (`execution/_chunked.py:378`, the pandas oracle) fed by the CLI's own
  chunk reader (`_sources.iter_source_chunks`, `src/decoy/cli/_sources.py:194-223`) and writer
  (`src/decoy/cli/io/_targets.py:498`).
- Throughput is about 85,000 rows per second for three masked string columns up to 4M rows on
  every path. At 16M rows the resident runs slow to about 67,000 (Parquet) and 57,000 (CSV) rows per
  second, and `--chunked` is 6 to 9% faster than plain. Streaming is mainly a memory fix on the
  Python path; the time gain only shows on large inputs.

### 1.2 The engine's own streaming lane (engine, `run_pipeline` direct)

`engine_cell.py`, same data shape (`bench_worker_lazy.py prepare --workload native`, 1,048,576-row
groups), `mask_secret_ref` set:

| Rows | Cell | Wall s | RSS increment MB | Process peak MB | Input mode | Output mode |
|---|---|---|---|---|---|---|
| 4M | `pq.read_table`, no sink (today's CLI) | 48.1 | 1,263 | 1,470 | resident | resident (`no_sink`) |
| 4M | `pq.read_table` + `ParquetTransactionalSink` | 48.3 | 799 | 995 | resident | streamed |
| 4M | `LazySource` + `ParquetTransactionalSink` | 47.9 | 514 | 704 | lazy | streamed |
| 16M | `pq.read_table`, no sink (today's CLI) | 242.9 | 4,651 | 4,824 | resident | resident (`no_sink`) |
| 16M | `pq.read_table` + `ParquetTransactionalSink` | 248.4 | 2,125 | 2,298 | resident | streamed |
| 16M | `LazySource` + `ParquetTransactionalSink` | 191.0 | 528 | 701 | lazy | streamed |

The auto-chunk lane already routes this config (`auto_chunk.mode == "chunked"`, reason "single mask
table with only chunk-safe scalar strategies ... at or above the auto-chunk threshold (100000)"); what
the CLI misses is a `LazySource` input and a sink. `native_admitted` is `False` on every cell (no
companion). With lazy input and a sink the RSS increment stays flat (514 MB at 4M rows, 528 MB at 16M;
605 MB file), and the 16M run is 21 percent faster than today's resident call (191 s against 243 s),
because nothing pays for whole-table Arrow and pandas copies. The engine lane alone gives more than
`--chunked` gives today, on the default path.

### 1.3 Threads where they exist

- Native companion (not installed here): the recorded 100M-row W2 run on `n2-standard-8` took the hash
  kernel from 299.7 s at 1 thread to 94.8 s at 8 (3.2 times), whole job 429.9 s at 8 threads, peak
  447 MB; `redact` and `truncate` stayed single-threaded at about 128 to 178 s
  (engine `docs/records/audit-2026-09-30/stage-2c-summary.md:213-262`; also
  `docs/plans/2026-09-21-phase5-native-operator-expansion.md:35-41`). That run called
  `run_native_or_oracle_chunked` directly, not a product path. The native thread knee is 4 by default
  (`decoy-engine-native/src/threads.rs:47`, `DECOY_NATIVE_MASK_THREAD_KNEE`), so "all cores" means at
  most 4 kernel threads per call unless the knee is raised.
- DuckDB out-of-core FK route: 3M rows per table, 3 tables, `scripts/fk_memory_probe.py --mode out_of_core` on the engine VM.
  At `--mem-cap-mb 4000` DuckDB got `memory_limit` 3200MB and so 1 thread; mask 500.7 s, peak RSS
  905 MB. At 24000 it got 19200MB and so 8 threads (9 by memory, capped at the VM's 8 CPUs, `_duckdb.py:84`); mask 310.4 s
  (38% less), peak RSS 1287 MB. Spill peak about 1 GB and parity ok in both. The thread count comes
  only from the memory limit at 2 GiB per thread (engine
  `src/decoy_engine/execution/out_of_core/_duckdb.py:29`, `:67`), so a small memory budget also
  takes away this route's cores. This route already uses many threads when it has the memory; the
  plan does not change it.
- Mac (macOS arm64): the owner approved the recommended measurement in Q5. M1 repeats the Linux sweep
  in a temporary venv at `~/decoy/acct2-cli-mac`, records the same wall-time, peak-RSS, route and thread
  cells in this evidence section, and removes the venv afterward. The measurement is in V1 scope and
  must land before the V1 release gate; it does not block the engine implementation slices.

### 1.4 What follows for the plan

1. The biggest speed lever is the native companion, and the CLI install does not ship it
   (REL-PKG, row 90: "native companion wheels (engine #353 workflow, never run)"). RUN-STREAM threads
   the resources through so the companion uses them the day it ships; it cannot make the Python path
   multithreaded. This is stated in the run summary (4.5) and is owner question Q1.
2. Streaming is a memory fix on the Python path and already exists in the engine. The CLI change is
   to call it: a `LazySource` per Parquet source and a sink per target. It is faster too once the
   data is large: at 16M rows the engine's lazy-plus-sink cell took 191.0 s against 242.9 s resident
   with no sink (21% less), and the CLI's `--chunked` run took 219.2 s against 240.2 s (1.2), at a
   quarter of the memory or less. Small inputs show no difference either way. These times are single
   runs, and runs of one cell spread by about 15% (1.3), so the time gains are indicative; the memory
   gains are the finding.
3. CSV had no lazy input in the engine lane (`LazySource` was Parquet only,
   `profile/_readers.py:214` at `5a7f14dc`), so CSV needed one engine slice (E2, since merged).
4. The DuckDB out-of-core FK route already runs on many threads when its memory budget allows
   (1.3). RUN-STREAM keeps its 2 GiB-per-thread rule and only adds the user's thread cap on top
   (the new `out_of_core_threads` keyword, AT-E1c), so a large memory budget no longer means every core
   when the user asked for fewer.

## 2. FRAME

### Problem

Users run `decoy run` and get one of two behaviours: a plain run that holds every source in memory,
or `--chunked`, a separate pandas path with its own reader, writer, refusals and route label. The
engine has a third: the auto-chunk lane with lazy input, streamed output and an out-of-core FK route,
none of which the CLI reaches. Resources are fixed: `native_threads=1` (`execution/_pipeline.py:139`)
and no CLI memory setting. On current engine main, an out-of-core caller that passes no explicit budget
receives the effective memory ceiling minus `max(20%, 2 GiB)`, not 25%
(`out_of_core/_budget.py:398-472`). The separate routing budget remains 25% (`_budget.py:356-395`).

### Guarantee (what V1 promises)

- G1. A plain `decoy run` passes every local mask-table source that has a lazy backend (Parquet,
  CSV, fixed-width, and each DuckDB snapshot, which is Parquet) as a `LazySource` built by the
  engine's one builder, and the run reads whole, before routing, each one its own rules cannot
  keep lazy (5.1). A run that takes a sink (5.6) also passes every target through one
  CLI `TransactionalSink` over DELIV's `DeliverySink`; the engine picks the route. Every route's output reaches the targets: streamed tables
  through the sink during the run, resident tables through the same sink after it (5.2). A config the
  auto-chunk lane admits streams input and output (peak memory bounded by chunk size, not file size).
  Large FK jobs take the existing out-of-core route by the existing decision
  (`_pipeline_routing.py:195`) and read their sources in batches; in V1 they take no sink (5.6,
  Q8), so their output tables are held in memory until delivery.
- G2. CSV sources stream through the engine's one CSV reader (E2, merged) and fixed-width sources
  through its one fixed-width parser (SE3b, engine #595); the CLI reaches both through E4.
- G3. `--chunked` means "must stream": the same call with `execution_mode="stream"`; one strict
  preflight uses the existing compatibility and route gates before any source data-row iterator is
  opened, and refuses with a reason code and the blocking fact when no streaming route applies
  (`_chunked.py:255-374`, `_pipeline_chunk_route.py:43-103`).
  Every config base `--chunked` runs keeps running (5.3, AT-C2a). The CLI pandas chunked path
  (`_run_chunked_mask`, `src/decoy/cli/run/_execute.py:69-143`) is deleted (pre-GA).
- G4. Resources come from one resolved record: flag over environment over settings file over `auto`.
  `auto` threads = the engine's `detect_usable_cpus()` (affinity and cgroup quota, or `os.cpu_count()`
  where affinity is unavailable, following the platform calculation at `api/cgroup_cpu.py:231-244`);
  CLI `auto` memory = `resolve_conservative_ooc_budget_bytes()`, the engine-owned 25% policy over the
  effective memory ceiling. The CLI passes that explicit byte value to `run_pipeline`; `--max-memory`
  and `settings.json` may raise it. In V1 the value bounds the out-of-core route (its budget and so its
  DuckDB threads); the auto-chunk lane is bounded by chunk size, not by this value. The engine's existing
  `resolve_ooc_memory_limit(None)` behavior remains unchanged for platform and library callers.
- G4a. No target becomes visible before the native evidence check and DELIV's delivery decision: the
  sink stages streamed output into DELIV's stage during the run and resident `result.outputs` right
  after it, then the CLI runs `post_run_verify`, and only DELIV's `deliver(decision, before_visible)`
  makes the run visible (DELIV 4.2 steps 3 to 7). A failure before that point aborts the stage and
  leaves `LATEST` and every earlier output unchanged. A run with `--vault` takes no sink (B0 and
  VAULT-STREAM), so the vault rules are DELIV's and B-6's, unchanged by this plan.
  The quarantine file goes through DELIV's `sink.place_quarantine(config)`, as on the resident path.
- G5. The run summary prints the route, its reason code, input and output modes, configured resource
  caps, and route-specific applied values when execution evidence has them. An inapplicable resource says
  `not_used`; nothing is inferred from a cap. All fields come from `ExecutionResult.quality_metrics`,
  never from a CLI guess (`_duckdb.py:59-64`, `_pipeline.py:139-145`).
- G6. Output semantics are unchanged: a plain streamed run writes the same CSV bytes and Parquet
  values and schema as its resident run. The strict `--chunked` path additionally preserves base
  `--chunked` CSV and Parquet bytes by keeping its chunk-boundary writer grouping
  (`src/decoy/cli/run/_execute.py:132-142`, `src/decoy/cli/io/_targets.py:535-551`). For `.csv.gz` targets the decompressed bytes are equal;
  the file itself may be multi-member gzip, as the shared writer core already makes it under
  `--chunked`. Empty sources follow the plain run's rule on both paths; where base `--chunked`
  differed, the CHANGELOG says so.
- G7. V1 release artifacts include the native companion wheel from REL-PKG. The installed CLI wheel's
  primary non-FK path sends `--threads` to native execution. A source/development install may lack the
  companion and reports that state, but companion absence is not an acceptable V1 release state.

### Non-goals (V1)

- Multithreading the Python path. Speed beyond today needs the native companion (REL-PKG).
- Cloud sources and targets (`s3`, `gcs`): still refused by `_require_local_io_endpoints`
  (`src/decoy/cli/run/_execute.py:249-269`); CLI-CLOUD (row 64) owns them.
- Streaming `fixed_width` or archive CSV targets (still resident; the refusal text moves to the engine
  reason under `--chunked`). Archive CSV sources stay resident too: E4 returns no lazy backend for them.
- A sink on a job the post-scan gate applies to, or on a `--vault` run (5.6, Q8, VAULT-STREAM).
- A resources field in the pipeline YAML (owner question Q2; recommendation: no).
- The platform's own budget code (`api/jobs/native_budget.py`): unchanged; V2-LOG item.

### Failure modes

| Failure | Behaviour |
|---|---|
| Lazy source changes between facts and a lane batch read | Parquet: engine `facts_match` refusal (`_chunked_input.py:26-29`); CSV and fixed-width: `runtime.lazy_source_changed`; exit 3, nothing visible (DELIV abort) |
| A run fails after the sink took some tables | the engine calls `TargetSink.abort()`, which forwards to `DeliverySink.abort()` and never raises; for `KeyboardInterrupt` and anything else that skips that call, `_flow.py`'s `finally` calls `layout.abandon()`, which runs the abort callback DELIV registers (DELIV 4.2 step 8; `src/decoy/cli/run/_flow.py:155-158`). The stage is removed and `LATEST` and old outputs are untouched |
| `post_run_verify` fails after the run | the refusal raises; `layout.abandon()` in `_flow.py`'s `finally` runs DELIV's abort callback, so nothing becomes visible (G4a) |
| Delivery fails | DELIV's own failure rows (DELIV 6.1, 6.2); RUN-STREAM adds none |
| An exception after the engine called `commit()` (the engine never aborts after it, `_sequential.py:639-650`, `out_of_core/_runner.py:302-313`) | the same `abandon()` callback runs for `Exception` and `BaseException`, so the stage is removed and nothing becomes visible |
| `--chunked` on a config no streaming route takes | engine `runtime.streaming_unavailable` before a data-row iterator opens; exit 1 (usage) with the blocking fact |
| Settings file unreadable or invalid | exit 1 naming the file and key; never a silent default |
| `--max-memory` below the engine floor | exit 1 (`resources.memory_below_floor`) |
| Memory or CPU detection fails | the engine's coded `OUT_OF_CORE_MEMORY_DETECTION_FAILED` (`_budget.py:222`) surfaces with the flag to pass |
| Out of disk while staging a target | sink aborts, `OSError` errno class kept, exit 3 |

## 3. Established solutions

Search run 2026-11-09 against primary docs plus current code: `Spark executor memory configuration`,
`DuckDB SET memory_limit threads`, `Polars collect streaming fallback`, `JVM MaxRAMPercentage`, and
`git config precedence`; code search covered `resolve_budget`, `resolve_ooc_memory_limit`,
`decide_execution_route`, `decide_chunk_route`, `TransactionalSink`, and the CLI atomic writer. The
selected pattern is planner-owned routing plus explicit host resource controls, using the existing
engine and CLI choke points rather than a new scheduler, writer or budget calculator.

- Spark and DuckDB: the planner chooses the physical route from facts (sizes, operators) and the user
  sets resources (`spark.executor.memory`, `SET memory_limit`, `SET threads`), not routes. Here the
  engine's `decide_execution_route` and `decide_chunk_route` already choose; the CLI only supplies
  inputs and resources ([Spark configuration](https://spark.apache.org/docs/latest/configuration),
  [DuckDB configuration](https://duckdb.org/docs/stable/configuration/overview)).
- Polars streaming: `collect(engine="streaming")` falls back silently when a node cannot stream; the
  engine's B6b lane chose the opposite and records why (`_chunked_input.py:18-20`). `--chunked` keeps
  that choice and deliberately turns an unsupported node into a hard refusal rather than Polars'
  documented fallback
  ([Polars LazyFrame](https://docs.pola.rs/api/python/stable/reference/lazyframe/)).
- Resource defaults: the JVM sizes its heap as a fraction of the cgroup limit
  (`-XX:MaxRAMPercentage`); Ray and the platform's `native_budget.py` set threads from CPU affinity and
  the cgroup CPU quota and export `OMP_NUM_THREADS`. Precedence flag over env over file over default is
  the pip and git configuration model
  ([Java command](https://docs.oracle.com/en/java/javase/18/docs/specs/man/java.html),
  [Git config](https://git-scm.com/docs/git-config)).
- Settings file: one versioned file under the app home, as `uv` (`uv.toml`) and `pip` (`pip.conf`)
  do; C3 built it as JSON (`$DECOY_HOME/settings.json`, `src/decoy/_resources.py:31`) with
  `decoy_home()` (`src/decoy/distribution/layout.py:32`, `DECOY_HOME` override).
- Atomic output: write to a temp beside the target, rename on commit (the CLI's
  `staged_local_target`, used by `write_chunked_output`, `src/decoy/cli/io/_targets.py:535`); DELIV
  moves the run-level version of this into its stage.

## 4. Design notes

- One run call. The CLI builds `sources` and `sink` and calls `run_pipeline` once; the `if chunked:`
  fork at `src/decoy/cli/run/_execute.py:331-345` goes (C2). `--chunked` only sets
  `execution_mode="stream"`.
- Two output shapes, one writer (Dennis B1). Streamed routes hand the sink bounded batches during the
  run; full frame and the unstreamed mixed route return `result.outputs` and never touch the sink
  (`_pipeline_full_frame.py:248-332`, `_isolated_worker.py:138-165`). After `run_pipeline` returns, the
  CLI calls the same sink's CLI-only `seal_result(result.outputs)`. It rejects any table present in
  both shapes, writes only outputs the engine returned, then seals the complete set. A target key
  with no returned output keeps today's skip; DELIV's declared-table file-target set remains the
  decision universe. DELIV C2a
  turns `_write_mask_outputs` (`src/decoy/cli/run/_execute.py:302-321`, called at `:395`) into the
  deliver step's `sink.write_table` loop; on a sink run `seal_result` is that loop, so there is still
  one writer.
- Stage in the run, deliver after the checks (Dennis B2). `TargetSink` adapts DELIV's `DeliverySink`
  (row 61, `docs/ROADMAP.md:380`), which owns stage-then-deliver for every CLI run route and depends on
  F22 (`:378`). A streamed route calls `sink.commit()` inside the run; for `TargetSink` that checks the
  stage holds no spill litter and records engine success, but delivers nothing. A resident route does
  not call it unless an internal lane streamed (`_pipeline_full_frame.py:323-332`). In both cases the CLI next calls `seal_result`, then
  `post_run_verify`, then DELIV's post-scan, `plan_delivery` and `deliver` steps (DELIV 4.2 steps 4
  to 7). Pattern: two-stage prepare, then DELIV's single visibility point.
- The sink reuses the one CLI writer and the one delivery sink. `write_chunked_output` already writes
  CSV with `to_csv(header=first)` and Parquet with `ParquetWriter`; DELIV C2a calls it with stage
  paths through `sink.write_chunked` (DELIV 4.1). `TargetSink` calls `sink.write_chunked` and
  `sink.write_table`, never a writer directly, so DELIV's G-ONE-DELIVERY-SINK sentry (DELIV 6.3) holds.
  No second writer, stage or journal is added.
- Resources use the engine's existing keywords (Dennis H3): `native_threads` (`_pipeline.py:139`,
  clamped by the native knee, clamp recorded) and `out_of_core_budget_bytes`, plus one new keyword,
  `out_of_core_threads: int | None`. `run_fk_out_of_core` binds that cap for the run, and the one
  `connect_duckdb` function applies it to every nested connection (`_runner.py:105-127`,
  `_duckdb.py:32-64`). The result stays at most `memory_limit / 2 GiB` (`_duckdb.py:29`) because that
  keeps per-thread buffers inside the budget. There is no new resources object. The CLI resolves flag, env, settings file and `auto` in one
  function (`src/decoy/_resources.py`), used by `run`, `setup` and `doctor`; detection and policy are
  engine-owned. The new public `resolve_conservative_ooc_budget_bytes()` is a thin facade over
  `_budget.py`'s existing `resolve_budget(None).budget_bytes`, so 25%, effective-ceiling detection and
  the floor remain one implementation rather than a second CLI copy. `detect_usable_cpus` is ported
  from the platform. The CLI grows no cgroup reader and no memory-policy arithmetic of its own.
- Settings writes use the CLI's existing atomic-write choke point:
  `decoy._atomic.write_atomic(decoy_home(), "settings.json", data, WriteMode.REPLACE)`. C3 adds no temp,
  rename, permission or directory-fsync implementation. The existing AST guard
  `tests/sentry/test_atomic_writer.py` walks `src/decoy/`, has a shrink-only exact-site allowlist, and
  turns red if `_resources.py` or setup adds an inline atomic writer.
- The route summary is an engine record. `quality_metrics` already carries `execution` and
  `auto_chunk` blocks; E3 adds one frozen `route` view so the CLI renders fields, not dict paths.
- Lazy input keeps one capability boundary. Existing routing uses the concrete `LazySource` identity
  at its choke points (`_chunked_input.py:115-145`, `_pipeline_sources.py:56-64`). E2 adds
  `CsvLazySource(LazySource)` and overrides `footer_facts`, `open_batches`, `iter_batches`, `schema`,
  `num_rows`, `column_null_counts` and `to_table` through `read_csv_source(chunksize=)`. The public
  `LazySource(path)` constructor remains the Parquet implementation (`profile/_readers.py:227` at `c7433ede`).
  This is a substitutable second backend, not a second route test or reader. SE3b adds
  `FixedWidthLazySource(LazyFileIdentity, LazySource)` the same way (`profile/_lazy_fixed_width.py:110-223`
  at `c7433ede`).
- One public lazy builder (E4). `CsvLazySource` is private and `FixedWidthLazySource` is public; a CLI
  `if format ==` choosing between them would be a second format dispatch beside the engine's
  `_build_file_source` (`profile/_readers.py:536`). E4 adds `build_lazy_source(table, descriptor,
  *, file_access=None) -> LazySource | None` beside `build_declared_source` (`:482-491`), reading under
  the same config position `sources.<table>.path`; it returns `None` for a format with no lazy backend.
  The CLI calls it once per mask-table descriptor to build row-free candidates and keeps the resident
  read only for `None`; the run itself reads whole any candidate it cannot keep lazy (E5, 5.1).
- Lazy input without a publication sink reuses an engine adapter, not a second route. Current
  `run_auto_chunk` asserts when `sink is None and source` is a `LazySource`
  (`_pipeline_auto_chunk.py:433-434`). E5 drives `_run_streamed` through the existing
  `_CallableSinkAdapter`, whose `write_batches` already materializes one complete table for a callable
  consumer (`_transactional_sink.py:108-154`). The adapter writes into a route-local result mapping,
  not a file or user sink; on success the table is returned in `ExecutionResult.outputs`, the output
  evidence says `resident`, and on failure the local mapping is discarded. The input still opens and
  closes through the one lazy batch path (`_pipeline_auto_chunk.py:319-382`). This is the resident
  result arm of the existing lane, not a new writer, stage or publication mechanism.

## 5. Behavior

### 5.1 Sources (CLI part C1l, engine part E4)

Lazy input and the sink are separate choices (revision 6, Dennis r1 H1). Every plain (not
`--chunked`) `decoy run` passes lazy input for each mask table that has a lazy backend, with
`run_pipeline(..., resident_fallback=True)` (E5), whether or not it also takes a sink. The run keeps
a source lazy only where its own rules allow and reads the rest whole before routing. The sink is the 5.6 choice. This is the shape the engine already serves
for the platform: the isolated worker hands `run_pipeline` every input as a `LazySource`
(`execution/_pipeline_sources.py:1-30`), each route resolves a source where it uses it, the
out-of-core route reads it in batches, and the post-scan gate reads a lazy source batch by batch
(`execution/pipeline/_post_scan.py:350-372`, deferred case `:460-473`). A run with no sink gets
its output tables resident, as today.

- The switch is at the one place the CLI reads sources today: `prepare` calls
  `_load_sources_from_config` (`src/decoy/cli/run/_prepare.py:539`), which first refuses cloud
  endpoints and contradicting target formats (`_execute.py:286-287`) and then reads each source
  (`:293-298`). That call and those two refusals stay. C1l swaps only the read loop: it asks
  `lazy_sources(config_dict, base_dir)` in `cli/io/_lazy.py` for the lazy tables and reads the rest
  as today. For each mask-table descriptor that `source_is_materialized` accepts, `lazy_sources`
  calls `build_lazy_source(table, descriptor)` (E4) once. This is row-free; it may read declared
  schema, footer or framing facts through the owning reader. Every non-`None` candidate goes to
  `run_pipeline` lazy, and the `execute` call (`src/decoy/cli/run/_execute.py:364`) passes
  `resident_fallback=True`. `execute_preview` (`:420`) does not: it passes `{}` sources, so the
  keyword would be a no-op there. The CLI makes no admission decision and calls no
  eligibility owner. A `None` candidate and a source `source_is_materialized` skips keep exactly
  today's read (`read_source`, `src/decoy/cli/_sources.py:169-191`;
  `src/decoy/_native_gate.py:198-203`). `run_pipeline` already accepts that mix
  (`_pipeline_sources.py:56-64`).
- The run decides (E5, engine). With `resident_fallback=True` and a plain `auto` run,
  `run_pipeline` runs one private pre-pass, `resident_fallback_tables` in
  `execution/pipeline/_lazy_input.py`. Its position is fixed: after `resolve_subset`
  (`execution/_pipeline.py:289`, so it reads the resolved config) and after the token-vault mode
  rewrite (`:297-299`), inside the `resolve` progress phase (`:306`), immediately before
  `build_run_context` (`:307`). Under `execution_mode="stream"` (`stream_required`), under any
  explicit route, and for a tokenize job that the rewrite moved to `full_frame`, the pre-pass is a
  no-op. This keeps `pipeline/_stream.py`'s promise that `streaming_unavailable` is raised before
  any source is read. The pre-pass gets the run's own `config`,
  sources, `engine_version`, `base_dir`, `instance_default_locale`, `file_access`, `vault_writer`,
  `fidelity_report` and `post_validation`, so it compiles exactly what the run compiles; nothing
  crosses a caller boundary to be kept equal. It returns the caller `LazySource` names the run
  cannot keep lazy. `run_pipeline` reads each of those whole through the existing
  `_pipeline_sources.materialize_source` (`_pipeline_sources.py:56`) and builds the run context
  from that mixed map, so the route, plan and post-scan verdict are those of a run that was handed
  those tables resident. The pre-pass is not public and not an `@entry_point`; it is a step inside
  `run_pipeline`, which is already EXEMPT because it runs the post-scan on its resident routes. The
  default `False` disables only this new resident-fallback pre-pass for every other caller, the
  platform's isolated worker included. E5's separate no-sink lazy collector still applies when
  routing selects that lane. Every rule is its existing owner answering: `classify_table_kinds`,
  `compile_declared_casting_contract`, `post_scan_gate_applies`, `transform_bearing_mask_tables`,
  and for relationship jobs the bounded `profile_source` under `prepare_declared_execution_sources`,
  `compile_plan`, the relationship-graph builder, `_sequential_eligible`,
  `_has_cross_table_fk_cycle`, `out_of_core_admission`, `decline_out_of_core` and
  `fk_out_of_core_dtype_hazard`. It implements no second strategy, cycle, type or eligibility
  table. The bounded profile may make the owning reader's bounded facts pass, including CSV or
  fixed-width rows, but never materializes a whole source; that relationship-job profile runs once
  more inside `build_run_context`, the cost of keeping the pre-pass out of the 600-line
  `_pipeline_context.py`. A `LazySource` the run reads whole:
  - every table named by the engine-owned `compile_declared_casting_contract(config)`. The
    auto-chunk streamed arm refuses a declared table when any sink is present
    (`_pipeline_auto_chunk.py:435-439`), including the internal resident collector. The pre-pass
    calls that contract owner and does not inspect declared-casting structure itself.
  - every table when a vault writer is present. The chunked lane refuses a vault before reading a
    chunk (`execution/native/_chunked_entry.py:649-652`, `_chunked.py:444`), and routing lifts the
    vault only onto out-of-core under `vault_ooc_safe` with a fit estimate
    (`_pipeline_routing.py:236-260`, `:353-361`), which a lazy table cannot give: a lazy vault
    relationship job is rejected outright. Streaming a vault run is V2 VAULT-STREAM
    (`docs/roadmap/out-of-scope.md:20`).
  - when relationships are declared, every table unless the job is bounded-eligible: the terms of
    `_sequential_eligible` (`_pipeline_routing.py:88-147`: no `--fidelity`, post-validation,
    validators, model post-scan ask or generate table), no FK cycle (`_has_cross_table_fk_cycle`),
    out-of-core compatible and no FK dtype hazard. A lazy table gives the size estimator no sample
    (`_pipeline_routing_samples.py:37-56`, `_mem_estimate_schema.py:104`; the probe skips it,
    `_pipeline_routing_signals.py:433`), so an ineligible relationship job with no fit estimate
    raises `fk_full_frame_oom_risk_rejected` (`_pipeline_routing.py:346-425`, `:407`) where the
    resident run fits and runs full frame.
  - when `post_scan_gate_applies(config)`, every mask table that declares transforms. A lazy
    transform-bearing mask table defers the gate to report-only (`_post_scan.py:460-473`,
    `:150-155`, `:248-266`) unless the route is sequential and `tee_supported()`, which is false on
    Windows (`:453-457`); a report-only report passes DELIV step 4, so base's block would be lost.
- A no-sink auto-chunk lane is valid after E5: its lazy input runs through the existing callable
  sink adapter and the resident table comes back in `ExecutionResult.outputs` (4, 6.2). This is
  required for C1l to land before C1a and for post-scan or fixed-folder runs that correctly take no
  publication sink. The adapter's internal publication classification is not copied into the run's
  result or failure evidence; E5 returns the collected table and normalizes the route's output
  evidence to resident. The adapter is local to `run_auto_chunk`: it is never assigned to
  `PipelineRunContext.sink` or its publish boundary, so the post-scan gate sees the restored resident
  output exactly as it does on today's no-sink route. The counterfactual acceptance matrix compares
  the resident and lazy calls for
  route, exit, exact CLI output bytes and post-scan verdict; any unlisted difference is a C1l stop,
  not a new local exception (AT-C1l).
- `tokenize`, `api.mask()` and `--chunked` keep their own reads until DELIV C4 and C2.
- Local `format: parquet`: E4 returns `LazySource(path)`. DuckDB sources are snapshotted to a
  temp Parquet file before validation (`src/decoy/cli/run/_prepare.py:330-380`), so each snapshot
  is a Parquet source here.
- Local `format: csv` (not archive): E4 returns the engine's `CsvLazySource`, dialect resolved once
  through `resolve_csv_dialect`, every data pass through `read_csv_source(chunksize=)`
  (`profile/_csv_reader.py:462-540`). Archive CSV: `None`, resident.
- Local `format: fixed_width`: E4 returns `FixedWidthLazySource.from_descriptor(descriptor,
  table=table, field_key="sources.<table>.path")` (`profile/_lazy_fixed_width.py:119-131`). Behavior
  the CLI relies on, all engine-side:
  - Schema comes from the layout (`str` to string, `int` to int64, `float` to float64) and equals
    the resident `read_fixed_width` frame converted to Arrow, which engine AT-18b asserts.
  - Routing facts come from one counting pass that holds one record in memory, so a lazy
    fixed-width source is read twice (facts, then data). AT-C1w records the wall time against the
    resident read; this plan claims no speed gain for fixed-width, only bounded memory.
  - A blank `int` or `float` field is a `FixedWidthParseError` on both the lazy and the resident
    read; only the text `nan` in a float field reads as null.
  - Identity (device, inode, size, mtime) is checked by `open_batches` around each batch pass, the
    read the auto-chunk lane uses. `to_table` (a full-frame read) and `iter_batches` do not check:
    each is one read of whatever file is there, so the output is that file's content, never a mix
    of two files. `footer_facts` re-measures if the file changed between routing calls
    (`profile/_lazy_identity.py`). The guarantee is therefore: a file changed between the facts
    pass and a lane batch pass raises `runtime.lazy_source_changed`.
  - A bad record raises value-free `FixedWidthParseError` (record numbers and field name, never
    the bytes). An `int` beyond 64 bits raises `FixedWidthParseError` on the lazy read and
    `OverflowError` from `pa.Table.from_pandas` on the resident read.
- Failure parity is on the exit code and on the text being value-free, not on identical wording.
  For each fixed-width and CSV failure above, the lazy run exits 3, as the resident read of the
  same file does, its message carries no cell value, and nothing is visible (G4a). AT-C1w pins
  the fixed-width cases; AT-C1a the CSV ones.
- Empty fixed-width file: the lazy source reports the layout schema with zero rows. If the
  resident read of the same file gives a different schema, the layout schema wins and the
  CHANGELOG says so (AT-C1w).
- Generate-only tables: no source, unchanged.
- C2 deletes `_ChunkedFixedWidthError` (class `src/decoy/cli/run/_execute.py:37-38`, raised at
  `src/decoy/cli/run/_prepare.py:462-475`, mapped in `src/decoy/cli/exit_codes.py:238`, `:266`) and
  the `iter_source_chunks` fixed-width refusal (`src/decoy/cli/_sources.py:194-223`): under
  `--chunked` a fixed-width source then streams like any other. Fixed-width targets stay resident
  (non-goals).
- The resident fixed-width read names no config position in its errors today (it calls
  `read_fixed_width(path, layout)` directly). The lazy read names `sources.<table>.path`, so a lazy
  error says more than the resident one did; AT-C1w checks the lazy text, not equality.

E4 (engine). `build_lazy_source(table, descriptor, *, file_access=None) -> LazySource | None`,
exported from `decoy_engine.profile`, in a new `profile/_lazy_build.py`: `_readers.py` is 585
lines against the 600-line goal of `tests/sentry/test_module_size.py`. It is the lazy counterpart
of `build_declared_source` (`profile/_readers.py:482-491`). To keep one format dispatch (Dennis r1
M9), E4 moves `_build_file_source`'s format branches (`:534-567`) into one table in the same new
module, one entry per format holding its resident builder and its lazy builder or `None`.
`_build_file_source` and `build_lazy_source` both look formats up in that table, so a format added
later lands in one place and the lazy column is an explicit choice. `_readers.py` shrinks by
about 30 lines. The CLI holds no format dispatch.
It reads only under config position `sources.<table>.path`, as `build_declared_source` does. A read it
triggers (a `column_names_file` through `resolve_csv_dialect`) is listed in the declaration-gate
sentry `tests/sentry/source_config/test_declaration_gate.py`. It opens no data rows: the
facts pass runs when routing asks for facts, not at build time. Cloud descriptors and a compressed
CSV (a suffix `read_csv_source` decompresses) return `None`; CLI-CLOUD owns cloud sources. E4 is
decided by the engine, never by a CLI format check.

### 5.2 Targets (CLI parts C1a and C1b)

`cli/io/_sink.py`: `TargetSink` implements the engine `TransactionalSink` protocol (`write`,
`write_batches`, `commit`, `abort`; `execution/_transactional_sink.py:67-105`) over DELIV's
`DeliverySink` (`io/_delivery.py`, DELIV C2a). It adds three CLI-only members: `seal_result()`,
`rows_written() -> dict[str, int]`, and the `spill_parent` and `committed_table_path` the engine
reads. It stages, it never delivers, and it holds no vault.

- `write_batches(table, batches, *, schema)` hands the batches to `DeliverySink.write_chunked` for
  a table with a file target, each `pa.RecordBatch` wrapped as a one-batch `pa.Table`, because
  the one chunked writer, `write_chunked_output` (`src/decoy/cli/io/_targets.py:498-553`), takes
  tables. It passes `empty_schema=lambda: schema`. Zero batches keep the plain run's rule (G6):
  for a CSV target `TargetSink` writes `schema.empty_table()` through `write_table`, as a plain
  run writes an empty table, because `write_chunked_output` writes nothing for an empty CSV
  (`:528-533`); for Parquet the empty-schema path writes the zero-row file. `write(table, frame)`
  is `write_table` for the same table. A table without a target is consumed and counted, never
  serialized, matching today's skip in `write_targets` (`:461-497`). A second entry for one table
  raises.
- `commit()` is the engine boundary. It records that the engine finished, checks the stage holds
  no engine hold-back spill directory (`_decoy_hold_<hex>`, created under `spill_parent` by
  `fileaccess/_output.py:47`, `:140-145`, and removed in `close()`,
  `_chunked_output_sink.py:474-495`), and delivers nothing. Engine `write` and `write_batches` are
  refused after it.
- `seal_result(outputs)` is the one post-engine entry point. It writes each resident target
  through `DeliverySink.write_table`, counts targetless outputs, refuses a table the engine already
  wrote, and moves to `SEALED`. A target key that names no output table expects nothing, as in
  today's `write_targets` (`:487-489`) and DELIV's file-target set; an engine-streamed empty
  table counts as written. It accepts a
  resident result with no `commit()`, because the full-frame route leaves the sink unused
  (`_pipeline_full_frame.py:323-332`); if the engine wrote any table, `commit()` must have run. On
  a sink run it replaces DELIV C2a's `write_table` loop over `result.outputs`, so each table still
  has one writer.
- After `seal_result`: `post_run_verify` (`src/decoy/_native_gate.py:465-479`), then DELIV 4.2
  steps 4 to 7 unchanged: the post-scan check, `plan_delivery`, and either `DeliverySink.abort()`
  or `DeliverySink.deliver(decision, before_visible)`. Delivery is DELIV's only visibility point.
  `TargetSink` calls none of these. Steps 4 to 7 are one code path shared by sink and no-sink runs;
  the sink branch differs only in how tables reach the stage (engine writes plus `seal_result`,
  against DELIV's `write_table` loop).
- Row counts. `ctx._table_records` (`src/decoy/cli/run/_execute.py:396-398`), which feeds the
  summary's Rows and Files facts and per-table lines (`src/decoy/cli/run/_render.py:150-152`), and
  the evidence and notify counts (`:407`, `:410`) read `rows_written()` on a sink run, because
  `result.outputs` is empty for a streamed table.
- Native evidence (C1l). A lazy source the lane takes stays lazy, with or without a sink
  (`_chunked_input.py:446-466`, `_pipeline_full_frame.py:156-171`), and the unified-slice native
  coordinator declines it (`_unified_slice_admission.py:292-295`). The lane runs its own native
  chunked core but records `execution_mode: "full_frame"` (`_pipeline_route_exec.py:104-112`);
  `route_summary` names it `auto_chunk` from the `auto_chunk.lane` block (`_route_summary.py:157-160`).
  `classify_route` today finds no `unified_slice_activation` and returns `pandas`
  (`src/decoy/_native_gate.py:445-448`), so `post_run_verify` would refuse every lane-streamed
  `--native` run. C1l makes `classify_route`, when `unified_slice_activation` is absent and
  `route_summary(...).route == "auto_chunk"`, take the state from E5's
  `route_summary(...).native_executed`: true only when some lane column's executed backend equals
  its planned backend and that planned backend is one the engine operator registry marks compiled
  (`_chunked_evidence.py:53-60`, `:117-124`, `:178-200`). Equality for a planned
  `arrow_python` or `pandas_oracle` backend is false. `native_admitted` is
  fixed at preflight and an admitted column can still run `arrow_python`, so it is not evidence. A
  `--native` run with no compiled-kernel evidence still refuses with "no output was written"; on a
  sink run DELIV's abort callback removes the stage (AT-C1n).
- `abort()` forwards to `DeliverySink.abort()`, which is idempotent and never raises (protocol
  rule, `_transactional_sink.py:67-105`). The CLI has no `except` arm of its own: a refusal after
  the run (a native-check failure, a post-scan block) raises, and on any exit the engine does not
  see, including
  `KeyboardInterrupt` after the engine's `commit()` (the engine never aborts after it,
  `_sequential.py:639-650`, `out_of_core/_runner.py:302-313`), `_flow.py`'s `finally` calls
  `layout.abandon()` (`src/decoy/cli/run/_flow.py:155-158`), which runs the abort callback DELIV
  registers. RUN-STREAM adds no context manager or `except` arm of its own.
- Two read-only members DELIV does not define yet (Dennis r1 H3). `SinkStage` exposes only
  `abort` and `deliver`, and `DeliveryStage.stage_path(table, relpath)` records a staged file each
  time it is called, so it cannot serve as a lookup. C1a adds to `io/_delivery.py`:
  `DeliverySink.stage_dir() -> Path` and `DeliverySink.staged_path(table) -> Path | None`, which
  compute without recording. This is a DELIV seam: section 13 lists it, and the C1a brief asks
  DELIV's owner to take it into C2a if C2a has not merged.
- `spill_parent` is read run-wide, without a table (`_chunked_output_sink.py:474-488`). On kind R
  it is `stage_dir()` (0700, DELIV AT-14), so the engine's `_decoy_hold_<hex>` spill sits inside a
  private folder that `abort()` removes, and it exists when the run has no targets. Kind A takes
  no sink until C1b (5.6); there it is the fixed folder, and the engine creates
  `_decoy_hold_<hex>` as a 0700 private directory (`fileaccess/_output.py:140-145`), which AT-C1i
  asserts.
- `committed_table_path(table)` returns `staged_path(table)` for a targeted table, the namespace
  `DeliverySink.place_quarantine(config)` uses, so the engine's quarantine aliasing guard compares
  like with like (`_transactional_sink.py:344-356`). For a targetless table it returns
  `stage_dir()` itself. File placement never returns the stage directory as a file destination, so
  this sentinel cannot alias a valid quarantine file and invents no user-selectable reserved name.
- `rows_written()` gives per-table counts for both shapes. Evidence and notify counts
  (`src/decoy/cli/run/_execute.py:407`, `:410`) read it on a sink run, because `result.outputs` is
  empty on a streamed route.
- Targets the shared writer cannot stream (`fixed_width`, archive CSV) are written whole at `write`
  time through `write_table`; under `--chunked` the existing `check_target_formats(chunked=True)`
  still refuses them up front (`src/decoy/cli/io/_targets.py:170`).

### 5.3 The strict switch (engine part E1a, CLI part C2)

`run_pipeline(execution_mode="stream")`. E1a translates `"stream"` once at `run_pipeline` entry into
the existing internal `execution_mode="auto"` plus one immutable `stream_required` field on the run
  context. The ten relevant internal comparison sites therefore keep seeing a valid existing mode and
  do not grow their own interpretation (`_pipeline.py:284`; `_pipeline_context.py:281`, `:525`;
  `_transforms_admission.py:84`, `:344`, `:380`; `physical/_snapshot.py:126`;
  `_pipeline_routing.py:297`, `:302`, `:324`). Only the routing choke point reads `stream_required`; `auto` routing
is unchanged.

Before any source data-row iterator opens, that choke point performs strict preflight from the
validated config and source schemas. It calls the existing `check_chunked_compatibility` once for
each mask table and records its coded result, checks that every source has a lazy reader and every
target supports streaming, and computes out-of-core compatibility plus
`fk_out_of_core_dtype_hazard` for an FK fallback
(`_chunked.py:255-374`, `_pipeline_routing_fk_dtype.py:48-131`). Parquet schema comes from footer
metadata without column data (`profile/_readers.py:213-223`). CSV schema uses the declared dialect
and all-text contract before a batch iterator is opened; an admitted CSV job may then make E2's
bounded facts pass through the same reader (`profile/_readers_csv.py:1-7`). A complete chunked pass
selects the lane; an FK chunked refusal may select compatible, hazard-free out-of-core; only a job
with neither streaming result raises `runtime.streaming_unavailable`.

- The auto-chunk lane's row threshold check is bypassed (not set to 0, which
  `require_positive_int` refuses, `physical/_snapshot.py:118`): a chunk-safe table of any size takes
  the lane, as base `--chunked` does today.
- Under `stream_required` only, `_chunked_output_sink` preserves base `--chunked` output grouping:
  Parquet row groups follow `min(chunk_size_rows, 1_048_576)` and do not take the lane's 256 MiB
  early cut (`_chunked_output_sink.py:69-73`, `src/decoy/cli/io/_targets.py:535-540`). Plain `auto` keeps its current
  row and byte caps. This preserves Parquet bytes for the same chunk size and PyArrow version.
- A mask table the lane takes must have `input.mode == "lazy"` and `output.mode == "streamed"`.
- FK configs. The lane takes no job with FK edges today (`_planner.py:16-18`), and base `--chunked`
  masks each table on its own only after `check_chunked_compatibility` passes for that table
  (`src/decoy/cli/run/_execute.py:210-230`). Its FK component, `gate_fk_child_edges`, admits only child edges that self-mask
  by a value-keyed strategy under the shared namespace, while the same gate also checks parent-side
  `code_set` and `bucket_perturb` keys (`_chunked.py:300-326`). Under `stream`, E1a extends B7's
  independence rule from no FK edges (`_pipeline_multi_table.py:121-148`) to every mask table passing
  that complete existing compatibility gate. Each table then runs as one per-table unit with the FK
  graph removed only from that already-admitted unit's lane classification, exactly as base
  `--chunked` runs it. Lazy facts are captured after preflight instead of being suppressed merely
  because the job has edges (`_pipeline_chunk_route.py:68-103`).
- An FK config with an edge that gate rejects goes to the out-of-core route only when
  `decide_execution_route`'s out-of-core compatibility holds and `fk_ooc_dtype_hazard` is clear
  (`_pipeline_routing_fk_dtype.py:48-75`), both decided from facts before any source row is read.
  Base `--chunked` refuses these configs, so this only adds configs that run.
- Anything else raises `ExecutionError(code=reasons.runtime.STREAMING_UNAVAILABLE)` before a source
  data-row iterator opens, with the blocking fact from the existing reasons (`auto_chunk.input.reason`,
  `auto_chunk.output.reason`, `decide_chunk_route`'s reason, `gate_fk_child_edges`'s code,
  `out_of_core_reject_code`, the dtype hazard).

The CLI maps the refusal to exit 1 and prints the fact. `--chunk-size` maps to `chunk_size_rows`.
Parity rule for C2: the gate runs base `--chunked` and the new path over the CLI's chunked fixture set
and the FK shapes of 6.3, and lists every config base `--chunked` runs that the new path refuses; a
non-empty list blocks C2 (AT-C2a).

### 5.4 Resources (engine part E1b, CLI part C3; both merged)

E1b and C3 are built (section 14). This section records the contract as shipped; C1a only reads
it. C3 stored the file as JSON (`$DECOY_HOME/settings.json`, `src/decoy/_resources.py:3`, `:31`)
rather than the TOML that revision 4 described; the keys, precedence and strictness are the same,
and a JSON boolean is refused where an integer is expected.

```text
decoy run CONFIG [--max-memory 8GiB] [--threads 6]
DECOY_MAX_MEMORY=8GiB DECOY_THREADS=6 decoy run CONFIG
decoy setup            # resources section: shows detected values, writes settings.json
decoy doctor           # one row per resolved value and where it came from
```

`$DECOY_HOME/settings.json` (default `~/.decoy/settings.json`, `src/decoy/distribution/layout.py:32`):

```json
{"schema_version": "1.0", "resources": {"max_memory": "8GiB", "threads": 6}}
```

Either value may be `"auto"`.

Resolution (`_resources.resolve`), first hit wins per key: flag, env, settings file, `auto`. The
stored reader requires a string `schema_version` matched in full as `<major>.<minor>`, refuses a
missing or unknown major, accepts unknown minors and keys, and checks primitives strictly: JSON
booleans never count as integers, `threads` is a positive integer or the literal `"auto"`, and
`max_memory` is a size string or `"auto"`. The CLI does not import `_MIN_BUDGET_BYTES`; it passes parsed positive bytes and the
engine's existing budget resolver owns the floor (`out_of_core/_budget.py:135-147`). For `auto`, the
CLI calls the public engine `resolve_conservative_ooc_budget_bytes()` once and records that byte value;
the function delegates to `resolve_budget(None)` rather than duplicating effective-ceiling, 25% or floor
logic. The
values go to `run_pipeline` as `native_threads=threads`, `out_of_core_threads=threads` and
`out_of_core_budget_bytes=memory` (an explicit value even for CLI `auto`). `auto`
threads is `detect_usable_cpus()`. A memory value below the engine floor is refused by the engine.
The resolved record and each value's source go to the run summary and the `--json` envelope.

`out_of_core_threads` is validated with the other `run_pipeline` knobs, then bound once around
`run_fk_out_of_core`. The binding is run-scoped, not a process global. Every nested caller continues
to use `connect_duckdb(temp_dir=..., memory_limit=...)`; that function reads the bound cap and computes
`max(1, min(user cap or detected usable CPUs, memory_limit // 2 GiB))`
(`_duckdb.py:32-84`). `None` means no user cap, but the detected affinity and cgroup ceiling still
replaces the current raw `os.cpu_count()` host ceiling. The same run-scoped binding records the
distinct applied `(memory_limit_bytes, threads)` pairs from every connection and returns them in the
out-of-core route's resources metrics; no logger or CLI reconstructs them.
The setup section is one entry in the `cli/setup/` section list that SCAN-ML C1 creates
(`2026-11-07-scan-ml.md` 4.6, AT-C1f: "RUN-STREAM can append"); if C1 has not merged when C3 starts,
C3 creates the list with one section and C1 appends.

### 5.5 Run summary (engine part E3, CLI part C2)

```text
Route       auto-chunk lane (lazy input, streamed output)
Why         single mask table with chunk-safe strategies, 16,000,000 rows >= 100,000
Resources   thread cap 8 (auto), native threads not used (companion not installed), out-of-core memory not used
```

From `route_summary(result.quality_metrics)` (E3): `route`, `reason_code`, `reason_text`,
`input_mode`, `output_mode`, `thread_cap`, `thread_cap_source`, `native_threads_applied`,
`duckdb_threads_applied`, `out_of_core_memory_cap_bytes`, `out_of_core_memory_limits_applied_bytes`, and
`native` (`admitted`, `not_installed`, `declined: <code>`). Applied-value fields are nullable and
render `not_used`; they are populated only by the route that owns them. `_native_gate.classify_route`
(`src/decoy/_native_gate.py:417`) keeps its native-intent check and takes the label from this record.


### 5.6 When the CLI passes a sink (C1a, C1b)

Lazy input does not depend on this section (5.1). On a plain `decoy run`, the CLI passes
`TargetSink` only when all four hold. Otherwise the run passes no `sink`; the engine then returns
every output table resident, and DELIV's `write_table` loop stages them.

| Condition | Code when it fails | Why | Lifted by |
|---|---|---|---|
| no `--vault` | `run.sink_unused.vault` | the engine refuses a sink with a `vault_writer` (B0, `execution/_pipeline_context.py:163-166`) | V2 row VAULT-STREAM (`docs/roadmap/out-of-scope.md:20`) |
| `post_scan_gate_applies(config)` is false | `run.sink_unused.post_scan` | the post-scan gate cannot read a foreign sink, so declared relationships would drop to a warning and `post_scan.integrity: true` would be refused (`config/_post_scan.py:162-210`) | Q8; engine follow-up in 16 |
| delivery root kind R | `run.sink_unused.fixed_folder` | kind A is DELIV's pass-through to today's writers until C2b | C1b, after DELIV C2b |
| the caller is `decoy run` | (no code; other callers never reach `sink_applies`) | `tokenize` and `api.mask()` move onto the sink in DELIV C4 | a later slice after C4 |

The choice is one predicate, `sink_applies(ctx) -> str | None`, in `cli/io/_sink.py`. It returns
`None` or one of the three codes. The codes join `CLI_WARNING_CODES`' module
(`src/decoy/cli/run/_context.py:28`) as a sibling frozenset `SINK_UNUSED_CODES`, the CLI's one
registry for run-level codes (RESULT OQ-4); the run summary and `--json` `route.sink` print
`used` or the code (G5). It never refuses a run, and it is not a warning. A run it keeps off the
sink still takes lazy input for the tables the run keeps lazy (5.1), so a large
bounded-eligible FK job reaches the out-of-core route and reads its sources in batches; only its
output tables are held in memory until delivery.

Under `--chunked` (C2) the strict stream needs streamed output, so the rule differs:
- `--vault`: refused as today (`_ChunkedVaultError`, `src/decoy/cli/run/_prepare.py:459-460`).
- quarantine: refused as today (`src/decoy/cli/run/_execute.py:218-222`).
- `post_scan.integrity: true`: refused as today (DELIV CR).
- relationships declared without integrity: the sink is passed. The engine's gate cannot read it,
  so it defers to `warning.post_scan_output_unreadable`, and the CLI keeps DELIV CR's interim
  `chunked_key_check_not_run` warning and record. This is today's base `--chunked` behavior,
  which runs each table on its own with no key check. DELIV 4.2 step 4 withholds a run whose gate
  applies and returns no report. C2 changes that one central missing-report decision, not
  `sink_applies`: only a strict-stream run with both
  `quality_metrics["post_scan_gate_deferred"]` carrying the registered deferred reason and the
  `warning.post_scan_output_unreadable` warning, together with DELIV CR's closed
  `chunked_key_check_not_run` record, is the documented relationship-only
  exception and may proceed to `plan_delivery`. Missing either half still withholds. Integrity is
  refused before this point. The same rule remains after DELIV C5 replaces its applicability read
  with `post_scan_gate_applies`; no later DELIV slice may reintroduce the blanket withhold. This is
  today's base `--chunked` behavior until POSTSCAN-STREAM runs the key check. AT-C2a keeps those
  configs running and mutates each half of the conjunction.

## 6. Enumerations (from the code at the bases)

### 6.1 Exit paths

- `decoy run`: 0 OK; 1 config invalid, bad resource flag or settings value, `--chunked` refused
  (`runtime.streaming_unavailable`), gate refusal; 3 runtime failure (including
  `runtime.lazy_source_changed`, a lazy fixed-width parse error, out of disk); 4 enforce findings and
  post-scan blocks (unchanged, `src/decoy/cli/run/_render.py:196`; DELIV C5); 5 capacity
  (unchanged); 6 partial delivery once RESULT C-EXIT and DELIV C3 land (DELIV's, not this plan's).
  A `--native` evidence failure keeps today's exit code; the refusal raises and DELIV's abort
  callback removes the stage, so its "no output was written" stays true
  (`src/decoy/_native_gate.py:465-479`).
  A lazy source's failure exits as the resident read of the same file does (5.1).
- `decoy setup`: 0; 1 invalid input off a TTY without `--yes`.
- `decoy doctor`: unchanged codes; a resource row is informational.

### 6.2 Routes

Every route `run_pipeline` can take, and what this plan changes on it:

- auto-chunk lane, resident input (`run_auto_chunk`, `execution/_pipeline_auto_chunk.py:385-484`):
  unchanged; reached by archive CSV and every table the run reads whole under `resident_fallback` (5.1).
- auto-chunk lane, lazy input (`execution/_pipeline_auto_chunk.py:319-382`): the new default for
  Parquet, CSV and fixed-width tables the run keeps lazy; output streams on a sink run and
  is materialized through the existing callable sink adapter for the result on a run with no sink
  (E5, AT-C1a, AT-C1l, AT-C1w).
- full frame (`execution/_pipeline_full_frame.py:145-332`): `LazySource` resolved whole per route
  (`:156-163`); the route never touches the sink (its `commit` at `:332` is inert unless the run
  streamed), so its tables reach the targets through `TargetSink.seal_result(result.outputs)`
  (5.2, AT-C1g).
- sequential (`execution/_sequential.py:219`): sink `write` per table, FK-topological order (protocol docstring).
- out-of-core FK (`execution/out_of_core/_runner.py:106`): budget from `out_of_core_budget_bytes`,
  DuckDB threads capped by `out_of_core_threads` (AT-E1c). Declared relationships make the post-scan
  gate apply, so in V1 this route takes no sink (5.6) and returns resident outputs; under Q8 (b) it
  would use sink `write_batches`.
- mixed generate and mask (`execution/_pipeline_mixed_route.py`): unchanged; lazy keys read by
  `_read_key_column` (`:128`); streamed or not per `outputs_streamed` (`:257`), so either shape
  (AT-C1g). A generate table makes a relationship job not bounded-eligible, so such a job takes no
  lazy input (5.1).
- streamed generation (`generation/_streamed.py:94`): runs only when the sink sets
  `bounded_write_batches`; `TargetSink` does not, so generation stays resident and its tables reach
  the stage through `seal_result` (AT-C1g).
- multi-table dispatch (`execution/_pipeline_multi_table.py:290`): per-table streaming as today, now
  with a sink; under `stream` it also splits FK jobs whose every mask table passes the complete
  chunked compatibility gate (5.3, `_chunked.py:255-374`).
- CLI `--chunked` pandas path: deleted (C2).

### 6.3 FK shapes

The plan changes no FK masking logic. In V1 every shape declares relationships, so it takes lazy
input and no sink (5.1, 5.6); its output must equal the base CLI's plain run, with the post-scan
gate still blocking an introduced orphan (AT-C1c, AT-C1j). Under `--chunked`, an FK config for which every mask table
passes the complete `check_chunked_compatibility` gate is split per table onto the lane, as base
`--chunked` runs it; a gate-rejected job runs on out-of-core only when that route is compatible and
has no dtype hazard; otherwise it is refused before a data-row iterator opens (5.3, AT-E1a;
`_chunked.py:255-374`).

- one parent and one child;
- a three-level chain (the `fk_memory_probe.py` chain);
- one parent with two children;
- a composite key.

### 6.4 Fields

- Engine: `run_pipeline(execution_mode="stream")`, `run_pipeline(out_of_core_threads=int | None)`;
  existing `native_threads` and `out_of_core_budget_bytes` unchanged;
  `resolve_conservative_ooc_budget_bytes() -> int`, the public CLI-auto policy backed by
  `resolve_budget(None)` without changing the default for callers that omit a pipeline budget;
  `detect_usable_cpus(*, fs_root: Path | None = None, affinity: int | None = None) -> int`, preserving
  the platform's injectable test seam (`api/cgroup_cpu.py:231-244`);
  `route_summary(quality_metrics) -> RouteSummary` (frozen: `route`, `reason_code`, `reason_text`,
  `input_mode`, `output_mode`, `thread_cap`, `thread_cap_source`, `native_threads_applied`,
  `duckdb_threads_applied` (sorted distinct tuple), `out_of_core_memory_cap_bytes`,
  `out_of_core_memory_cap_source`, `out_of_core_memory_limits_applied_bytes` (sorted distinct tuple),
  `native`).
- Engine (E4): `decoy_engine.profile.build_lazy_source(table: str, descriptor: Mapping[str, Any], *,
  file_access=None) -> LazySource | None`.
- Engine (E5): `run_pipeline(..., resident_fallback: bool = False)`, one additive keyword;
  `RouteSummary.native_executed: bool | None`,
  where `True` requires an actually executed registry-owned compiled backend, `False` means lane
  evidence exists without one, and `None` means no lane evidence.
- CLI: `--max-memory`, `--threads`; env `DECOY_MAX_MEMORY`, `DECOY_THREADS`; `settings.json`
  `resources.max_memory`, `resources.threads` (all shipped by C3); `--json` `resources` and `route`
  objects; `--json` `route.sink` (`used` or a `SINK_UNUSED_CODES` member: `run.sink_unused.vault`,
  `run.sink_unused.post_scan`, `run.sink_unused.fixed_folder`, 5.6).
- CLI DELIV seam (C1a, 5.2): `DeliverySink.stage_dir() -> Path`,
  `DeliverySink.staged_path(table: str) -> Path | None`.

### 6.5 Output surfaces

No surface prints a cell value or a path outside the config's own paths.

- run summary card (`src/decoy/cli/run/_render.py:158-159`, the `Route` row);
- `--json` envelope (`route` and `resources` objects);
- `doctor` rows and `setup` prompts;
- error lines (reason code plus fact);
- evidence manifest (`--evidence-out`: route and resources added; row counts from `rows_written()`,
  5.2).

## 7. Class table

| # | Class | Applies here | Structure that closes it | Sentry or property test | Mutation that turns it red |
|---|---|---|---|---|---|
| 1 | Value-bearing output | refusal text under `--chunked`, route reason text, settings errors | Reasons carry codes, counts and column names only (existing reason registry); settings errors name the file and key, never the raw value beyond the key's own text | AT-E1a asserts the refusal for a canary-bearing source has no cell value; existing raw-value sentries run on the new surfaces | M-E1a: put the first lazy batch's first value in the refusal |
| 2 | Cleanup missing on an exit path | the stage and the engine `_decoy_hold_<hex>` spill on failure, Ctrl-C, out of disk, a native-check failure | `TargetSink.abort()` forwards to DELIV's idempotent, non-raising `DeliverySink.abort()`; every exit the engine does not see reaches it through `layout.abandon()` in `_flow.py`'s `finally` (`src/decoy/cli/run/_flow.py:155-158`); `TargetSink` owns no file of its own | AT-C1d injects `Exception` and `KeyboardInterrupt` before engine `commit()`, after it, after `seal_result` and after `post_run_verify`: `LATEST` and old outputs byte-equal, no stage or `_decoy_hold_` directory left | M-C1d: drop the `abort()` forward; M-C1d2: unregister DELIV's abandon callback for sink runs |
| 3 | State machine and concurrency | sink states `OPEN`, `ENGINE_COMMITTED`, `SEALED`, `ABORTED`; resources resolved once | `TargetSink` refuses engine writes after `commit()`, overlap, a second `seal_result`, and every call after `abort()`; delivery order is DELIV's (4.2) and `TargetSink` has no deliver member | AT-C1e state test; AT-C1h order through DELIV | M-C1e: let `seal_result` run twice; M-C1h: deliver from `commit()` |
| 4 | Route parity and silent fallback | plain lazy input with and without a sink; `--chunked` on a non-streamable config; CSV before E2; native absent | `run_pipeline(resident_fallback=True)` owns the plain-run admission through its existing owners and the no-sink lane reuses the existing callable sink adapter as a resident collector; one strict-stream preflight calls `check_chunked_compatibility`; `CsvLazySource` inherits the existing lazy identity; `stream` refuses instead of falling back | AT-E5 and AT-C1l compare resident and lazy route, exit, bytes and post-scan verdict; AT-E1a strict refusals; AT-E2a lazy choke points; AT-C2b summary | M-E5c: keep the no-sink assertion; M-E1a2: return resident under `stream`; M-E2d: remove `CsvLazySource` inheritance |
| 5 | Referential integrity | FK jobs with lazy sources and no sink | No FK code changes; the shapes in 6.3 compared with the base resident run; the gate still blocks | AT-C1c, AT-C1j | M-C1c: pass the sink for an FK job |
| 6 | Untrusted producer | settings file, env values, flag values | one size parser with `fullmatch`; strict stored primitives; required string `"schema_version": "1.0"` with full-value version parsing; JSON via `json` with duplicate keys and `NaN` refused and a 64 KiB cap; engine-owned budget floor (all shipped in C3) | AT-C3a corpus (`-1`, `0`, `true`, `"6"` for threads, `8gb `, `8GiB\n`, `auto2`, 2 TB, missing/numeric/trailing-newline/unknown-major versions, accepted unknown minor, non-object `resources`) | M-C3a: accept `bool` as `int`; M-C3d: version regex uses `$` |
| 7 | Check then use on a path (TOCTOU) | lazy source read more than once (facts, then batches); target staging | Engine `facts_match` compares footer facts with the handle it reads (`_chunked_input.py:26-29`); `LazyFileIdentity` checks a CSV or fixed-width file around each lane batch pass (`open_batches`); a full-frame `to_table` is one read of one file (5.1); staging is DELIV's | AT-C1f: on a lane-admitted Parquet and fixed-width source, the file is replaced after the facts pass and before the first batch: exit 3, nothing visible | M-C1f: drop the facts comparison in the CLI path by passing a resident table |
| 8 | Weak tests and overclaimed evidence | memory claims | Memory acceptance uses a real process and `VmHWM`, on a VM, with the file at least 8 times the bound; the measurement harness is committed | AT-C1b peak-RSS bound | removing the bound check from AT-C1b is a gate finding |
| 9 | Behavior-preserving refactor drift | output bytes; strict Parquet row-group boundaries; route labels; which jobs take a sink | G6 checks resident output; `stream_required` preserves base chunk grouping instead of the auto lane's 1,048,576-row/256 MiB grouping (`_chunked_output_sink.py:69-73`) | AT-C1a, AT-C2a | M-C1a: use `pyarrow.csv`; M-C2a4: keep the auto byte cap under strict stream |
| 10 | Frozen contract drift | `run_pipeline` signature, `ExecutionResult.quality_metrics` keys, CLI flags and exit codes, `--json` envelope, reason registry, `decoy_engine.profile` and `decoy_engine.execution.pipeline` exports | Additive only: new `execution_mode` literal, new keywords (E5 `resident_fallback`), new record, the E4 profile export; the 600-line engine root does not grow; `--chunked` keeps its flag and exit code 1 for refusals; registry adds one identity through REG-RENUMBER | compatibility snapshot test; reason registry sentry; engine public-API snapshot and size sentry | M-E1d: rename an existing `execution_mode` literal; M-E5g: default `resident_fallback` to `True` (the isolated worker's behavior changes) |
| 11 | Silent loss of a safety check | a sink on a job the post-scan gate applies to (R5-7), on a `--vault` run (B0), or the narrow relationship-only `--chunked` exception | one predicate, `sink_applies`, decides the plain route; it calls `post_scan_gate_applies(config)` and reads the vault flag. The one DELIV missing-report choke point owns the strict-stream exception and requires the closed engine metric, engine warning and CLI record conjunction | AT-C1j: a relationship job with an introduced orphan still blocks with exit 4, an integrity job still runs its gate, and a `--vault` job runs resident; AT-C2a removes each evidence member after DELIV C5 | M-C1j: pass the sink when relationships are declared; M-C1j2: inspect relationships locally; M-C2a4: accept a deferred gate without the full conjunction |

## 8. Acceptance tests (red first)

| ID | Part | Test | Mutation |
|---|---|---|---|
| AT-E1a | E1a | `execution_mode="stream"`: empty, 10-row, default-chunk and over-1,048,576-chunk tables bypass the route threshold and preserve base Parquet row-group bytes; compatible FK tables run as lane units equal to base `--chunked`; parent-side `code_set` and `bucket_perturb` failures come from the same gate and take guarded OOC only if compatible and hazard-free; every final refusal precedes Parquet batches or CSV data; existing mode sites see `"auto"`; `auto` routing and its 256 MiB cap are unchanged | M-E1a, M-E1a2; M-E1a3: keep route threshold; M-E1a4: split FK under `auto`; M-E1a5: call only `gate_fk_child_edges`; M-E1a6: keep auto output grouping under strict stream |
| AT-E1b | E1b | `native_threads=6` reaches the native call (clamped to the knee, clamp recorded) and the auto-chunk lane; `out_of_core_budget_bytes` unchanged in behaviour | M-E1b: drop the clamp record |
| AT-E1c | E1b | OOC: every nested DuckDB connection sees `threads = max(1, min(out_of_core_threads or detect_usable_cpus(), memory_limit // 2 GiB))`; its distinct applied pairs reach resources metrics; two concurrent run contexts with different caps and recorders do not bleed; `None` keeps no user cap but honors detected CPUs | M-E1c: make one nested caller bypass `connect_duckdb`; M-E1c2: use a process global; M-E1c3: infer metrics from the cap |
| AT-E1d | E1b | `detect_usable_cpus()` passes the platform's `api/cgroup_cpu.py` fixtures: injected affinity, cgroup v2 `cpu.max` (`200000 100000` gives 2), v1 quota files, ancestor walk, fake `/proc` and cgroup tree; an unreadable present limit file gives a coded error; a host without `sched_getaffinity` uses `os.cpu_count() or 1`; the platform wrapper preserves `fs_root`, `affinity` and `CpuLimitUnreadable`; `_duckdb.py` uses the detector | M-E1d2: ignore quota; M-E1d3: leaf only; M-E1d4: call `os.sched_getaffinity` unconditionally |
| AT-E1e | E1b/C3 | a barrier starts two automatic CLI runs on one injected 32 GiB host; the OOC route spy observes each run receive an explicit 8 GiB budget, and neither observes the other's run state. A direct library run with `out_of_core_budget_bytes=None` still receives current main's ceiling-minus-reserve policy | M-E1e: pass `None` for CLI auto; M-E1e2: compute 25% in CLI; M-E1e3: change the engine default for every caller |
| AT-E2a | E2 | `issubclass(CsvLazySource, LazySource)` is pinned; lazy CSV passes the existing facts, planner, input, materialization and out-of-core type choke points without CSV-only branches; strict preflight rejects before the shared reader yields a data row; admitted batches use the one CSV reader and all-text dtype, equal the resident CSV fixture corpus (quotes, embedded newlines, BOM, CRLF, headerless names), and refuse a file changed between facts and batches | M-E2a: use `pyarrow.csv`; M-E2b: skip identity check; M-E2c: start facts before preflight; M-E2d: remove inheritance |
| AT-E3a | E3 | `route_summary` on each route gives expected configured caps and applied values: flat Python and generate routes mark native and OOC resources `not_used`; native evidence reports its applied clamp; OOC reports applied DuckDB threads and memory limit; unknown keys are ignored and missing blocks give `route="unknown"` | M-E3a: render a cap as applied without evidence |
| AT-C1a | C1l, C1a | Plain run, with and without a sink (5.6): Parquet, CSV and DuckDB sources, Parquet, CSV and `.csv.gz` targets, an empty source: output equal (CSV bytes, decompressed `.csv.gz` bytes, Parquet values and schema) to the base CLI's plain run on the fixture set; each CSV failure of 5.1 exits 3 with value-free text | M-C1a |
| AT-C1b | C1a (VM cell) | VM, 16M-row Parquet source (605 MB): plain `decoy run` peak RSS under 1 GB and route "auto-chunk lane (lazy input, streamed output)" | removing the bound |
| AT-C1c | C1l | the four FK shapes of 6.3 through the CLI take lazy input and no sink (`route.sink` is `run.sink_unused.post_scan`) and equal the base CLI's plain run; each cell records the same `route_summary(...).route` as base (an eligible pure-mask FK job takes out-of-core under byte-estimate routing whatever `out_of_core_threshold_rows` says, `_pipeline_routing.py:392`); a VM run of the three-level chain at 8 times the bound records peak RSS below the base run's | M-C1c: omit `resident_fallback=True` (the run rejects or changes route instead of reading whole); M-C1c2: keep the resident read loop in `_load_sources_from_config` |
| AT-C1d | C1a | cleanup matrix of class row 2: `Exception` and `KeyboardInterrupt` before engine `commit()`, after it, after `seal_result`, after `post_run_verify`; zero targets with a hold-back spill; a source that is also a target: `LATEST` and earlier outputs byte-equal, no stage or `_decoy_hold_` directory remains | M-C1d, M-C1d2 |
| AT-C1e | C1a | sink state machine: resident no-commit, streamed commit then resident-distinct additions, overlap, a target key naming no output table (skipped, not refused), second `seal_result`, calls after `abort()`, `abort()` twice without raising | M-C1e |
| AT-C1f | C1l | on a lane-admitted Parquet and fixed-width source, the file is replaced after the facts pass and before the first batch read: exit 3, nothing visible | M-C1f |
| AT-C1g | C1a, C1b | one run per route shape (auto-chunk streamed, full frame, sequential, mixed streamed and unstreamed, multi-table, generate-only) on kind R and, after C1b, kind A, plus a targetless table with and without quarantine: `seal_result` sees each output table once, every target is delivered, and bytes equal base. Targeted tables return their exact stage path to the alias guard; a targetless table returns the stage directory sentinel, and quarantine names equal to the table name, the former invented sentinel name and a nested name do not falsely alias. The summary's Rows and Files facts and per-table lines, evidence counts and notify count equal base and include targetless tables | M-C1g: omit `seal_result` (full frame writes nothing); M-C1g2: count rows from `result.outputs`; M-C1g3: return an invented file path for a targetless table |
| AT-C1h | C1a | a call recorder on a stub `DeliverySink` sees, in order: engine writes, `commit()` (streamed only), `seal_result` writes, then `post_run_verify`, then DELIV's `deliver` once; `TargetSink` makes no `deliver` call; a `--native` run with no compiled-kernel evidence prints "no output was written" and the abandon callback removes the stage | M-C1h: deliver from `commit()`; M-C1h2: unregister the abandon callback on a native refusal |
| AT-C1i | C1a, C1b | a Parquet source of 1.2M rows whose first column is null for its first 1,100,000 rows: plain `decoy run` streams, the hold-back spills under the stage (kind R) or the fixed folder (kind A, C1b) in a `_decoy_hold_<hex>` directory of mode 0700, `commit()` finds none left, output equal to the resident run. If the hold-back does not fire on this file, the builder reports it and the test seeds the engine's hold-back threshold lower | M-C1i: drop `spill_parent` (raises `HOLD_BACK_SPILL_UNAVAILABLE`); M-C1i2: return a `spill_parent` outside the stage |
| AT-C1j | C1a | `sink_applies` matrix: relationships declared (no sink, gate blocks an introduced orphan, exit 4); `post_scan.integrity: true` (no sink, gate runs); `--vault` (no sink, vault committed by DELIV, output equal base); kind A before C1b; the plain Parquet job (sink used). Each code is a `SINK_UNUSED_CODES` member, and a guard fails on any `run.sink_unused.` literal in `src` that is not one; the predicate calls `post_scan_gate_applies` | M-C1j, M-C1j2 |
| AT-C1l | C1l | counterfactual resident-versus-lazy matrix, with no publication sink, asserts identical exit, `route_summary(...).route`, post-scan block and exact CLI target bytes: lane-admitted Parquet, CSV and fixed-width tables below and above the threshold, missing Parquet null statistics, all-null and empty tables, transforms, declared casting, subset, mixed generate/mask, every report flag, quarantine and targetless output. Relationship cells add an introduced orphan, integrity failure, forced `tee_supported() == False`, every `_sequential_eligible` disqualifier, an FK cycle, out-of-core incompatibility and FK dtype hazard. Vault cells remain resident. The no-sink lane must return resident outputs and never hit `_pipeline_auto_chunk.py:433-434`; any unlisted differential stops C1l. The CLI builds no admission set: every candidate reaches `run_pipeline` lazy with `resident_fallback=True` | M-C1l: pass `resident_fallback=False`; M-C1l2: read vault runs resident in the CLI (a copied rule; the engine's vault cell must be what keeps them resident); M-C1l3: keep the no-sink assertion; M-C1l4: report streamed output for the internal collector |
| AT-C1k | C1l | `lazy_sources` calls `build_lazy_source` once per materialized mask descriptor and hands exactly the non-`None` candidates to `run_pipeline` lazy; the `execute` call passes `resident_fallback=True` and `execute_preview` does not; a `None` candidate, a non-mask sourced table and a source without `path` keep today's resident read. The CLI imports no engine eligibility owner (`classify_table_kinds`, `post_scan_gate_applies`, `compile_declared_casting_contract`, `resident_fallback_tables`, the module `decoy_engine.execution.pipeline._lazy_input`, any routing name) in `src/decoy/cli/io/_lazy.py` or `src/decoy/cli/run/`, checked by the sentry below. Candidate construction opens no data row. A mixed lazy and resident run equals base; cloud-endpoint and target-format refusals still fire before candidate work. A new sentry `tests/sentry/io_policy/test_lazy_source_choke_point.py` fails, in `src/decoy/cli/io/_lazy.py` and `src/decoy/cli/run/`, on any engine reader class name (`LazySource`, `FixedWidthLazySource`, `CsvLazySource`, also through an import alias or `decoy_engine.profile.<name>` attribute access) and on any format dispatch (`==` either way, `in (...)`, `match`/`case`, a dict keyed by format, `.get("format")`), with a seeded red case for each | M-C1k: build `FixedWidthLazySource` directly in the CLI; M-C1k2: filter formats before calling the engine builder; M-C1k3: drop a candidate in the CLI by table kind or vault (a copied rule) |
| AT-C1w | C1l, C1a | fixed-width sources on a plain run, with and without a sink: values and schema equal the base CLI's resident run for str, int and float fields and a `nan` float, an empty file (layout schema; CHANGELOG line if base differed); a blank int or float field and an int beyond 64 bits exit 3 with value-free text, as the base run does; the lazy text names `sources.<table>.path`; a file changed between the facts pass and a lane batch gives `runtime.lazy_source_changed`; VM run records wall time and peak RSS against resident for a 4M-record file | M-C1w: build the lazy source with `field_key="source.path"` |
| AT-C1m | C1a | a streamed table with zero rows on a sink run: a CSV target holds the same bytes as the base plain run's empty-table output, a Parquet target is a zero-row file with the engine's `schema`; batches reach `write_chunked_output` as tables | M-C1m: pass zero batches to `write_chunked_output` for CSV (no file) |
| AT-C1n | C1l, C1a | `--native` on a lane-streamed single-table Parquet run with the companion installed: `route_summary(...).native_executed` is true and the run passes, with no sink (C1l) and with a sink (C1a). A companion decline, an admitted compiled-planned column whose kernel runs `arrow_python`, and a column planned for `arrow_python` whose executed backend equals that plan each set `native_executed` false and refuse with `native_require_no_evidence` and "no output was written", nothing visible. The base full-frame `--native` cell is unchanged | M-C1n: key the change on "not full frame" (never reaches the lane); M-C1n2: read `native_admitted`; M-C1n3: treat any planned/executed equality as compiled |
| AT-C2a | C2 | `--chunked` on base `--chunked`'s fixture set, chunk sizes on both sides of 1,048,576, a wide table that triggers the auto 256 MiB cut, and the 6.3 FK shapes: every config base runs also runs with byte-identical outputs and an empty newly-refused list; configs base refuses keep exit 1; CSV needs E2 in the pinned release. Run the relationship-only cells against the final DELIV C5 missing-report predicate: the registered `post_scan_gate_deferred` reason, `warning.post_scan_output_unreadable` and `chunked_key_check_not_run` together warn and deliver; removing any one withholds; `post_scan.integrity: true` still refuses before work | M-C2a: map refusal to exit 3; M-C2a2: refuse below threshold; M-C2a3: apply the auto byte cap; M-C2a4: accept an incomplete evidence conjunction; M-C2a5: restore DELIV's blanket missing-report withhold |
| AT-C2b | C2 | run summary card and `--json` route/resources objects per route, including `not_used` and OOC actuals; a development install without the companion reports `not_installed` without failing, but this cell is not release acceptance; no cap is labeled as use without route evidence | M-C2b: print the CLI's old label; M-C2b2: render cap as used |
| AT-C2d | C2/REL-PKG | install the actual V1 CLI wheel and its REL-PKG companion wheel into a clean environment; run the normal non-FK 16M-row path with `--threads 8`; compiled-kernel evidence proves native execution received the resolved thread cap (subject to the recorded native knee), and the test fails if the companion is absent or Python fallback runs | M-C2d: omit the companion wheel; M-C2d2: drop `native_threads` forwarding |
| AT-C2c | C2 | `_run_chunked_mask`, `iter_source_chunks`, `_ChunkedFixedWidthError` and the CLI import of `run_mask_pipeline_chunked` are gone; `--chunked` on a fixed-width source streams; a sentry fails on a second `run_pipeline` call site in `src/decoy/cli/run/` (the `tokenize` command, `src/decoy/cli/tokenize.py:353`, and the library `src/decoy/api.py:560` are separate callers and unchanged) | M-C2c: re-add a `run_mask_pipeline_chunked` import |
| AT-E5 | E5 | With `resident_fallback=True`, `run_pipeline` hands `build_run_context` a `pa.Table`, read through `materialize_source`, for every caller `LazySource` under a vault writer, in `compile_declared_casting_contract`, of a relationship job under each disqualifier of `_sequential_eligible`, an FK cycle, an out-of-core incompatible job or an FK dtype hazard, and for a transform-bearing mask table when `post_scan_gate_applies`; it keeps every otherwise-safe lazy source lazy. Each such run's route, exit, outputs and post-scan verdict equal the same call with those tables passed resident. With the default `False`, no cell runs the new pre-pass and the lazy vault relationship job still raises its reject-before-read; the separately specified no-sink collector behavior is unchanged by the keyword value. Under `execution_mode="stream"` with a declared-cast lazy table and `resident_fallback=True`, the run raises `streaming_unavailable` and no source is read (a read spy on the `LazySource` records zero calls); an explicit route also skips the pre-pass. The pre-pass is private and not an `@entry_point`; `decoy_engine.execution.pipeline.__all__` gains no name; the post-scan route sentry's GUARDED and EXEMPT tables and `tests/sentry/baselines/post-scan-route-exempt.json` are unchanged; the `run_pipeline` signature freeze gains exactly the one keyword row. The pre-pass uses the bounded profiler and the exact compiler, graph, compatibility and hazard owners, and a guard rejects a copied eligibility check. A lazy auto-chunk table with no external sink runs through a `_CallableSinkAdapter` local to `run_auto_chunk`, while `PipelineRunContext.sink` stays `None`; it returns one resident output equal to the resident-input lane, reports resident output, does not expose the adapter's local evidence as run publication evidence, and a relationship post-scan verdict equals the resident call. `route_summary(...).native_executed` is true only for an executed registry-owned compiled plan, false for an idle compiled kernel and for planned/executed `arrow_python` equality, `None` off the lane | M-E5: drop the transform rule; M-E5b: read `native_admitted`; M-E5c: keep the no-sink assertion; M-E5d: use equality without checking the compiled-backend registry; M-E5e: route a rejected declared-cast candidate lazily; M-E5f: install the collector as the context sink; M-E5g: default `resident_fallback` to `True`; M-E5h: skip the vault rule; M-E5i: publish the pre-pass with a `config` parameter (the EXEMPT test goes red); M-E5j: read a whole table the rules keep lazy (the lazy-kept cell asserts a `LazySource` reaches `build_run_context` and goes red); M-E5k: run the pre-pass under `stream` |
| AT-E4 | E4 | `build_lazy_source` returns `LazySource` for Parquet, a `CsvLazySource` for CSV, `FixedWidthLazySource` for fixed-width, `None` for compressed CSV, cloud and an unknown format; it opens no data row; a `column_names_file` read is on the declaration-gate sentry's list; a reason it raises names `sources.<table>.path`; `_build_file_source` and `build_lazy_source` read the one format table and a guard fails if either branches on format outside it | M-E4: add a format branch outside the table; M-E4b: open the facts pass at build time |
| AT-C3a | C3 | resolution precedence matrix (flag, env, file, auto, per key), strict stored types and version cells from class row 6, value-free public errors with `__cause__ is None` and `__context__ is None`, the keyword mapping of 5.4 (CLI `auto` calls the public engine conservative policy and passes explicit bytes), and proof that no CLI code imports `_MIN_BUDGET_BYTES` or implements the 25% arithmetic | M-C3a: pass `None` for auto; M-C3b: env over flag |
| AT-C3b | C3 | `decoy setup --yes --json` writes versioned `settings.json` through `write_atomic(decoy_home(), "settings.json", data, WriteMode.REPLACE)` with detected values; off a TTY without `--yes` exits 1; section order fixed; `tests/sentry/test_atomic_writer.py` sees the real tree and a seeded inline temp/replace copy in `_resources.py` turns it red | M-C3c: write in place; M-C3d: add an inline `os.replace` writer |
| AT-M1 | M1 | on macOS arm64, repeat the section 1 harness for 1M, 4M and 16M Parquet/CSV plain and strict-stream runs plus 1-vs-8-thread cells; record wall time, peak RSS, route, companion state and variance in section 1.3, and remove the temporary venv; a missing 16M cell or unrecorded companion state blocks the V1 release gate | M-M1: omit the 16M or thread cell |

### 8.1 Worker evidence rules

- Write the generated/property tests before implementation and record their fail-before result. For
  every acceptance row, run the named mutation and show it turns that row red; rerun all mutations on
  the final slice head because a later edit invalidates earlier mutation evidence.
- Run baselines and slice tests from the repo's locked environment. Record the exact head, commands,
  results, failures, skips and anything not run in a `Test scope` block; do not widen a threshold,
  allowlist, size pin or test budget to make the slice pass. Record line and branch coverage on the
  changed units plus the mutation score for correctness-critical units, against measured baselines.
- Every builder checks all recurring-defect classes: `fullmatch` and trailing-newline refusals; strict
  stored/wire primitives; value-free exceptions with no `__cause__` or `__context__`; versioned read
  models; normalized sentry spellings; public cross-package imports; no swallowed CI failures; one
  trust class per entry point; checked allowlisted helpers; mutations on the final head; no raised pins.
- If a defect from an already-covered class appears during implementation, stop and report the class
  instead of applying a third local patch. Each slice runs its listed T0/T1 checks; reviewers run T1,
  assigned risk cells and their own mutations, not the full suite.

## 9. Hostile corpus (ways a gate reviewer breaks it)

- A Parquet file with one 16M-row row group: the lazy lane reads row groups with an 8 MiB buffer
  (`_chunked_input.py:15-17`); AT-C1b adds this file and records peak RSS (expected higher, still
  bounded by the row group, not the file).
- A source that is also a target of the same run: on kind R a target lands in the run folder, so it
  cannot be a source path; on kind A (C1b) the stage is beside the fixed folder and delivery happens
  after the run, when every read is done, so the run reads the old bytes and the target gets the new
  ones (on POSIX the open reader keeps the old inode). AT-C1d adds the case.
- `--threads 0`, `--threads 100000`, `--max-memory 1KiB`: refused (class row 6).
- `DECOY_HOME` pointing at a symlinked or world-writable directory: the settings file is read with
  `json` only (64 KiB cap, duplicate keys and `NaN` refused, `src/decoy/_resources.py:169-180`),
  never executed; a world-writable file is warned in `doctor`.
- A cgroup v1 host with unlimited quota: `detect_usable_cpus` returns affinity (the ported platform
  test fixtures cover v1, v2, nested limits and an unreadable limit file).
- A macOS host without `os.sched_getaffinity`: `detect_usable_cpus` returns `os.cpu_count() or 1` and
  does not treat absent `/proc` or cgroup files as an error (`api/cgroup_cpu.py:203-244`).
- Ctrl-C after the engine's `commit()` and before delivery: `layout.abandon()` in `_flow.py`'s
  `finally` reaches DELIV's abort callback, so the stage and the `_decoy_hold_<hex>` spill go and nothing becomes visible
  (AT-C1d). Ctrl-C during delivery is DELIV's case (DELIV 4.7 rule 2, AT-16).
- A relationship job whose masking introduces an orphan: `sink_applies` keeps it off the sink, the
  gate reads the resident output, and the run blocks with exit 4 (AT-C1j). Passing the sink here
  would turn that block into a warning (R5-7).
- A fixed-width file edited between the count pass and the batch pass, keeping its size:
  `LazyFileIdentity` also compares mtime and inode, so the run refuses with
  `runtime.lazy_source_changed` (AT-C1f).

## 10. Owner questions (each answerable alone; recommended answer first)

Owner answers (Cam, 2026-11-09): "go with recommended". Q1 to Q7 take their recommended option; Q8 was added in revision 5 and has no owner answer.

- Q1. Accepted: ship the companion under REL-PKG before V1. C2 and the V1 release gate require the
  installed companion wheel and AT-C2d; "native companion not installed" is a non-terminal report only
  for source/development installs. Alternative rejected: build it into the CLI wheel now.
- Q2. "Config overrides" for resources: recommend settings file plus flags plus env only, no pipeline
  YAML field, because YAML travels to other hosts and resources are per host; a YAML field would also
  change the config hash. Alternative: an optional `run.resources` block outside the hash.
- Q3. Current main's OOC default for callers that pass `None` is the effective ceiling minus
  `max(20%, 2 GiB)` (`_budget.py:398-472`); 25% belongs to `resolve_budget`, not that OOC default.
  Accepted: keep a conservative 25% CLI `auto` in V1 through the engine-owned
  `resolve_conservative_ooc_budget_bytes()` policy, and let `--max-memory` or the settings file raise
  it. Do not change the engine default for platform or library callers in V1. Two automatic CLI runs
  on one host therefore each receive 25% instead of both claiming most of the box (AT-E1e).
- Q4. `--chunked` refusals: recommend exit 1 (usage) as today. Alternative: exit 5 (capacity).
- Q5. Accepted: M1 creates a temporary venv in `~/decoy/acct2-cli-mac`, runs the same macOS arm64
  sweep, records it in section 1.3, and removes the venv. AT-M1 is a V1 release prerequisite.
- Q7. Order against CLI delivery (row 61, `docs/ROADMAP.md:380`). Accepted 2026-11-09 and kept in
  revision 5. DELIV owns staging and delivery for every CLI write, so C1a adapts DELIV's
  `DeliverySink` and waits for DELIV C2a, which builds it (kind R); C1b waits for DELIV C2b (kind A).
  The engine half (E1a to E3) shipped in 0.20.0 and 0.21.0. Revision 5 changes the entry points
  RUN-STREAM needs from DELIV: `write_table`, `write_chunked`, `place_quarantine`, `abort` and the
  stage directory as `spill_parent`, all in DELIV 4.2 and 4.6. `prepare_vault` is gone (R5-5).
- Q6. Delete `run_mask_pipeline_chunked` from the engine too? Recommend not in V1: the platform still
  names it (`api/config.py:423`); the CLI stops calling it and a V2-LOG item tracks the engine delete.

Revision 5 adds one question. It has no owner answer yet.

- Q8. Streaming output for jobs the post-scan gate applies to (no owner answer yet). Today the
  gate reads back only the engine's own staged sink; on any other sink it gives a warning for
  declared relationships and refuses `post_scan.integrity: true` (R5-7). Row 63a says
  "relationship jobs larger than memory use the out-of-core (DuckDB) route".
  - (a) Recommended: in V1 keep those jobs off the sink (5.6). A bounded-eligible relationship job
    takes lazy input (5.1), so the out-of-core route reads its sources in batches and spills its
    join to DuckDB: peak memory drops (no input and output held together). Its output tables are
    held in memory as Arrow until delivery, and masked output is about as large as its input, so a
    relationship job truly larger than memory still fails. That failure is exit 5 only when Python
    raises `MemoryError` (`exit_codes.py:190-191`); on Linux the likely end is an OS kill, with no
    exit 5 and no `finally`. A job that is not bounded-eligible keeps resident input. The gate
    keeps blocking introduced orphans exactly as today. Row 63a's "relationship jobs larger than
    memory" is not met in V1; the roadmap row records that gap. Log a V2 engine
    item: let the gate measure the batches it hands a foreign sink, then lift the 5.6 condition.
  - (b) An engine slice before C1a that makes the gate read `TargetSink`'s stage through a
    protocol member, so relationship jobs stream their output too. Cost: new R2 engine work on the
    post-scan gate, and C1a waits for another engine release, which leaves less time before the
    12/4 build-complete target.

## 11. Reuse inventory

| Need | Reused | Where |
|---|---|---|
| Lazy Parquet input | `LazySource`, B6b lazy lane | `profile/_readers.py:227`, `execution/_chunked_input.py` |
| Lazy input on every route, resolved where used | TB-1 source resolution, the platform's shape | `execution/_pipeline_sources.py:1-30` |
| Lane native evidence | E3 `route_summary(...).native` plus E5's compiled-executed field, derived from the operator registry and per-column evidence | `execution/pipeline/_route_summary.py:109-137`; `execution/native/_chunked_evidence.py:53-60`, `:178-200` |
| Lazy CSV and fixed-width input | `CsvLazySource` (E2), `FixedWidthLazySource` (SE3b) through E4's builder | `profile/_lazy_csv.py`, `profile/_lazy_fixed_width.py:110-223` |
| Which jobs the post-scan gate covers | `post_scan_gate_applies(config)` | engine `config/_post_scan.py`; DELIV C5 uses the same predicate |
| Route choice | `decide_execution_route`, `decide_chunk_route` | `execution/_pipeline_routing.py:194`, `_pipeline_chunk_route.py:43-142` |
| Engine sink boundary | `TransactionalSink` protocol | `execution/_transactional_sink.py:67-105` |
| Staging, delivery, vault and evidence publication, abort on every exit | DELIV `DeliverySink` and its `SinkStage` (C2a, C2b) over F22; `TargetSink` adapts it, never copies it | DELIV 4.1, 4.2, 4.6; `docs/ROADMAP.md:378`, `:380` |
| Per-format serialization | `write_table`, `write_chunked_output`, called by DELIV with stage paths | `src/decoy/cli/io/_targets.py:461-553` |
| Memory ceiling and default | `detect_effective_memory_bytes`, `_MIN_BUDGET_BYTES`, `_HOST_RAM_FRACTION` | `execution/out_of_core/_budget.py:339`, `:137-142` |
| Conservative CLI automatic OOC budget | public `resolve_conservative_ooc_budget_bytes()` delegates to the existing `resolve_budget(None).budget_bytes`; no CLI arithmetic and no change to `resolve_ooc_memory_limit(None)` | `execution/out_of_core/_budget.py:356-395`, exported through `decoy_engine.__init__` |
| Usable CPUs | the platform's `effective_cores` and `cpu_quota_cores`, ported (moved, not copied: P1 points the platform at the engine public facade) | `decoy-platform:api/cgroup_cpu.py:203-249` |
| FK admission for per-table masking | the complete `check_chunked_compatibility`, including its `gate_fk_child_edges` component | `execution/_chunked.py:255-374` |
| Per-table split | B7 multi-table dispatch | `execution/_pipeline_multi_table.py:290` |
| Thread and budget inputs | `native_threads`, `out_of_core_budget_bytes` keywords | `execution/_pipeline.py:139`, `:145` |
| OOC sizing | `resolve_ooc_memory_limit`, `_threads_for_memory_limit`, and the single `connect_duckdb` connection choke point | `_budget.py:398`, `out_of_core/_duckdb.py:32-84` |
| CSV dialect and reader | `resolve_csv_dialect`, `read_csv_source`, `CsvFileSource` | `profile/_csv_reader.py`, `profile/_readers_csv.py:34` |
| App home | `decoy_home()` | `src/decoy/distribution/layout.py:32` |
| Atomic settings write | `write_atomic(..., WriteMode.REPLACE)`; guarded by the existing one-writer AST sentry and seeded-copy tests | `src/decoy/_atomic.py:1-151`, `tests/sentry/test_atomic_writer.py:1-210` |
| Setup sections | SCAN-ML C1 `cli/setup/_sections.py` | SCAN-ML plan 4.6 |
| Native gate | `pre_execution_gate`, `post_run_verify` | `src/decoy/_native_gate.py:306`, `:465` |
| Resources (shipped) | `_resources.resolve`, `run_pipeline_kwargs` | `src/decoy/_resources.py:303`, `:114-120` |

New mechanisms still to build: `build_lazy_source` (E4), the private `resident_fallback_tables`
pre-pass behind `run_pipeline(resident_fallback=True)` and `RouteSummary.native_executed` (E5), `TargetSink` and `sink_applies` (C1a),
`lazy_sources` (C1l). E5 reuses `_CallableSinkAdapter` for the no-external-sink resident result;
it adds no sink class or writer. Already built: `out_of_core_threads`, `detect_usable_cpus`, the conservative
CLI auto-budget policy, `route_summary`, lazy CSV input, `_resources.resolve`. Each is the only one
of its kind; C2 deletes the CLI's `iter_source_chunks`, `_run_chunked_mask` and
`_ChunkedFixedWidthError`, so the chunk reader count goes down by one.

## 12. Placement

Engine (open-slice placement checked against `CODEMAP.md:232-272` at `c7433ede`; earlier merged
rows retain their own recorded base):

| New code | Goes in | Map row | Nearest neighbour |
|---|---|---|---|
| `route_summary` (`_route_summary.py`) | `src/decoy_engine/execution/pipeline/` (target sub-package; this creates it) | "Pipeline spine and routes" (`CODEMAP.md:224`, fan-out freeze at 104) | `_pipeline_finalize.py` |
| `detect_usable_cpus` (`_host.py`, about 250 lines ported) | `src/decoy_engine/execution/pipeline/`, exported from `decoy_engine.__init__` for the platform | "Pipeline spine and routes" (`CODEMAP.md:224`, fan-out freeze at 104); consumers cross the package through the public API (`:220`) | `out_of_core/_budget.py` (the memory probe) |
| `out_of_core_threads` | the existing `run_pipeline` signature, `out_of_core/_runner.py` run-scoped binding, and `out_of_core/_duckdb.py` connection choke point | "Out-of-core FK" (`CODEMAP.md:227`) | `_threads_for_memory_limit` |
| conservative CLI auto-budget policy (`resolve_conservative_ooc_budget_bytes()`; no new file) | `src/decoy_engine/execution/out_of_core/_budget.py`, exported through the public root facade | "Out-of-core FK" (`CODEMAP.md:227`) and "Public API" (`:220`) | `resolve_budget`, `resolve_ooc_memory_limit` |
| lazy CSV input (`_lazy_csv.py`, `CsvLazySource(LazySource)`) | `src/decoy_engine/profile/` beside `_readers_csv.py`; E2 adds the missing CODEMAP row for source profile readers | map change in E2, because current `CODEMAP.md:213-237` has no `profile/` row | `LazySource`, `CsvFileSource` |
| tests | `tests/unit/execution/run_stream/` (new sub-package; `tests/unit/execution/` is over 25) | "Unit tests" (`:243`) | `tests/unit/execution/derived_visibility/` |
| `build_lazy_source` (E4, new `_lazy_build.py`, about 70 lines) | `src/decoy_engine/profile/`, exported from `decoy_engine.profile` | "Source readers, profile types" (`CODEMAP.md:258`): lazy backends sit beside `_readers.py`; E4 adds the module to the `profile/` directory map | `_readers.py` (`build_declared_source`), `_lazy_fixed_width.py` |
| E4 tests | `tests/unit/profile/` | same row | `tests/unit/profile/` lazy CSV tests |
| `resident_fallback_tables` (E5, new private `_lazy_input.py`, about 150 lines; not exported, not an `@entry_point`) | `src/decoy_engine/execution/pipeline/`, beside the other `run_pipeline` steps; `pipeline/__init__.py` unchanged | "Pipeline spine and routes" (`CODEMAP.md:249`); the target `pipeline/` sub-package has 8 direct modules at `c7433ede` | `_stream.py`, `_post_scan.py` |
| `resident_fallback` keyword and its call (E5, about 15 lines) | existing `src/decoy_engine/execution/_pipeline.py` (371 lines), after `resolve_subset` and the token-vault rewrite, inside the `resolve` phase, before `build_run_context`; `_pipeline_context.py` calls the shared `build_routing_facts` instead of its own copy | same row (`CODEMAP.md:249`) | `materialize_source` |
| `build_routing_facts` (E5, new private `_routing_facts.py`, about 110 lines; not exported) | `src/decoy_engine/execution/pipeline/`, beside `_lazy_input.py` | same row (`CODEMAP.md:249`) | `_lazy_input.py`, `_pipeline_context.py` |
| no-sink lazy-lane resident collection (E5) | existing `src/decoy_engine/execution/_pipeline_auto_chunk.py` | same pipeline-spine row (`CODEMAP.md:249`); no new module | `_run_streamed`, `_CallableSinkAdapter` |
| `RouteSummary.native_executed` (E5) | `src/decoy_engine/execution/pipeline/_route_summary.py` | same row (`CODEMAP.md:249`) | `_native_status` |

The rows above E4 are revision 4's placement at engine `5a7f14dc` and are built.

CLI (`CODEMAP.md:42-78` at `3007a0a`):

| New code | Goes in | Map row | Nearest neighbour |
|---|---|---|---|
| `TargetSink` engine adapter and `sink_applies` (`_sink.py`, about 220 lines) | `src/decoy/cli/io/`, over DELIV's `_delivery.py` | source readers and target writers (`CODEMAP.md:53`); DELIV owns the one delivery sink (`docs/ROADMAP.md:380`) | `_delivery.py`, `_targets.py` |
| lazy source building (`_lazy.py`, about 60 lines) | `src/decoy/cli/io/` | same row | `src/decoy/cli/_sources.py` |
| the lazy switch (C1l, the read loop) | `_load_sources_from_config`, `src/decoy/cli/run/_execute.py:291-299`; its call at `src/decoy/cli/run/_prepare.py:539` stays | `run/` package (`CODEMAP.md:50`) | `read_source` |
| `SINK_UNUSED_CODES` | `src/decoy/cli/run/_context.py` beside `CLI_WARNING_CODES` (`:28`) | `run/` package | `CLI_WARNING_CODES` |
| lane native evidence in `classify_route` (C1l) | `src/decoy/_native_gate.py:417-462` (existing function) | private shared primitives (`CODEMAP.md:66`) | `post_run_verify` |
| DELIV seam `stage_dir()`, `staged_path(table)` | `src/decoy/cli/io/_delivery.py` (DELIV's module; in C2a if C2a is still open) | source readers and target writers (`CODEMAP.md:53`) | `DeliveryStage.stage_path` |
| lazy-source choke-point sentry | `tests/sentry/io_policy/test_lazy_source_choke_point.py` | sentry tests | `tests/sentry/io_policy/` |
| the one `run_pipeline` call site with `sources` and `sink` | `src/decoy/cli/run/_execute.py` (`:364-380`) | `run/` package (`CODEMAP.md:50`); every `run/` module is held at 600 lines by `tests/sentry/layout/test_run_package_shape.py` | `_execute.py` |
| `_resources.py` | top-level `src/decoy/` | "Private shared ... primitives used by more than one package" (run, setup, doctor) | `_native_gate.py` |
| setup section `_resources.py` | `src/decoy/cli/setup/` (SCAN-ML C1) | C1's row | `_models.py` |
| tests | `tests/unit/run_stream/`, `tests/e2e/run_stream/` (new folders, like `cli_fmt/`) | map change row added in C1l | `tests/e2e/cli_fmt/` |

`src/decoy/cli/run/_execute.py` takes the `_execute.py` lane after DELIV C2a (DELIV's lane order:
P4, CR, SAMPLE SC0, L5a, RESULT C-DOC1, SUB-RUN C1, C2a, C3, C4, C5). C1a adds the sink branch to
`execute` (about 30 lines) and the call to `lazy_sources`; C2 removes `_run_chunked_mask` and the
`--chunked` fork (`:69-143`, `:331-345`, about 90 lines). The builder checks `_execute.py`,
`_prepare.py`, `io/_delivery.py` and the new `io/` modules against their caps before opening a PR.

## 13. Frozen contracts touched

- `run_pipeline` keyword set: adds `out_of_core_threads`; `execution_mode` gains `"stream"`. Additive,
  shipped in 0.20.0; the CLI passes both through `_resources.run_pipeline_kwargs`
  (`src/decoy/_resources.py:114-120`).
- `ExecutionResult.quality_metrics`: adds `route` and `resources` blocks; existing keys unchanged.
- `TransactionalSink` protocol: unchanged. `TargetSink` adds `seal_result` and `rows_written` as
  CLI-side methods (the engine never calls them) and implements the two optional members the
  engine's own sink has, `spill_parent` and `committed_table_path`
  (`_transactional_sink.py:338-344`).
- Engine `decoy_engine.profile`: adds `build_lazy_source` (E4). Additive.
- Engine `run_pipeline`: E5 adds the keyword `resident_fallback: bool = False` (one row in
  `tests/unit/execution/test_r3_public_signature_freeze.py`). `docs/compatibility-contract.md` gets
  one new paragraph after the SUB-RUN E2 entry (`:78-80`), in the same style as the entries at
  `:57`, `:64` and `:78`: the keyword is keyword-only and additive, `run_pipeline` then has 47
  frozen parameters (46 at `:79`; the count at `:49` is history and stays), and `False` disables
  the resident-fallback pre-pass. E5's separately documented no-sink lazy collector applies with
  either keyword value. The same paragraph records `RouteSummary.native_executed: bool | None`
  as an additive field (no earlier paragraph names `RouteSummary`, so none is edited); the engine root and
  `decoy_engine.execution.pipeline` exports stay exactly as they are. E5 also adds
  `RouteSummary.native_executed: bool | None`. Additive.
- DELIV `DeliverySink`: RUN-STREAM calls `write_table`, `write_chunked`, `place_quarantine` and
  `abort` (DELIV 4.2, 4.6) and adds two read-only members, `stage_dir()` and `staged_path(table)`,
  that compute without recording a staged file (5.2). If DELIV C2a has not merged when C1a starts,
  they go into C2a; otherwise C1a adds them with a DELIV-owner review. DELIV's own member list
  (DELIV 4.6) does not name them yet; the orchestrator asks the DELIV owner to add them there.
- `_native_gate.classify_route`: a lane run (no `unified_slice_activation`, `route_summary(...).route
  == "auto_chunk"`) reports native evidence from `route_summary(...).native_executed` (5.2, C1l);
  the full-frame logic is unchanged.
- DELIV missing-report decision: a strict-stream relationship run may proceed without a post-scan
  report only when both the engine deferred-gate evidence and the registered
  `chunked_key_check_not_run` record are present. This is one exception at DELIV's existing choke
  point, preserved when DELIV C5 switches to `post_scan_gate_applies`; integrity never reaches it.
- Engine public API: exports
  `detect_usable_cpus(*, fs_root: Path | None = None, affinity: int | None = None) -> int` and
  `resolve_conservative_ooc_budget_bytes() -> int`.
  Platform `api/cgroup_cpu.effective_cores` keeps that same injectable signature and its
  `CpuLimitUnreadable` error, and delegates through the engine facade (`api/cgroup_cpu.py:30-36`,
  `:231-249`).
- Settings file (shipped by C3, `settings.json`): required string `"schema_version": "1.0"`; strict
  `resources.max_memory` and `resources.threads`; unknown minor versions and keys tolerated, missing
  or unknown major refused.
- Reason registry: one identity `runtime.streaming_unavailable`, one `resources.cpu_detection_failed`;
  version through REG-RENUMBER at merge.
- CLI: `--chunked` keeps its name and refusal exit code; `--chunk-size` kept; new flags additive;
  `--json` envelope gains `route` (with `route.sink`) and `resources`; the printed route label text
  changes (pre-GA; CHANGELOG).
- `decoy-run-result/v1` (RESULT): `route` and `resources` are added only if RESULT's schema allows
  extension; else a RESULT follow-up (section 15).

## 14. Slices

Bound: at most 10 files and 800 lines per slice. Status is at CLI `3007a0a` and engine `c7433ede`;
a merged slice is not re-planned.

| Slice | Repo | Status | Contents | Files max | Lines max | Gate |
|---|---|---|---|---:|---:|---|
| E1a | engine | merged (#439), released 0.20.0 | `execution_mode="stream"` translated once to `auto` plus immutable `stream_required`; strict preflight; no route threshold; base chunk-boundary output grouping; complete-gate FK split; guarded out-of-core force; reason identity; AT-E1a; CHANGELOG | 10 | 760 | Dennis, then Codex |
| E1b | engine | merged (#442), released 0.20.0 | public `detect_usable_cpus`; public conservative CLI auto-budget policy; `out_of_core_threads` run-scoped binding; native clamp record; AT-E1b to AT-E1e | 10 | 780 | Codex |
| E2 | engine | merged (#437), released 0.20.0 | `CsvLazySource(LazySource)`; strict preflight; file identity; CODEMAP `profile/` row; AT-E2a | 8 | 550 | Codex |
| E3 | engine | merged (#459), released 0.21.0 | `route_summary` and the `route`/`resources` blocks; AT-E3a | 5 | 250 | Codex |
| R | engine | done (0.20.0, 0.21.0) | release carrying E1a to E3 | 3 | 100 | orchestrator |
| C3 | CLI | merged (#165) | `_resources.py`, flags, env, `settings.json` through `_atomic.write_atomic`, setup section, doctor rows; AT-C3a, AT-C3b | 10 | 650 | Codex |
| E4 | engine | open | Exact files: `src/decoy_engine/profile/_lazy_build.py` (new one format descriptor and `build_lazy_source`), `src/decoy_engine/profile/_readers.py`, `src/decoy_engine/profile/__init__.py`, `tests/sentry/source_config/test_declaration_gate.py`, `tests/sentry/defects/test_lazy_builder_registry.py`, `tests/unit/profile/test_lazy_build.py`, `CODEMAP.md`, one `changelog.d/` fragment. AT-E4 | 8 | 400 | Codex |
| E5 | engine | open | Exact files: `src/decoy_engine/execution/pipeline/_lazy_input.py` (new private pre-pass `resident_fallback_tables` over the existing owners; no export), `src/decoy_engine/execution/_pipeline.py` (`resident_fallback` keyword, pre-pass call and `materialize_source` before `build_run_context`), `src/decoy_engine/execution/pipeline/_route_summary.py` (`native_executed`), `src/decoy_engine/execution/_pipeline_auto_chunk.py` (no-sink resident collector through `_CallableSinkAdapter`), `tests/unit/execution/test_r3_public_signature_freeze.py` (one keyword row), `tests/sentry/test_physical_seam_disconnection.py` (the new `execution/pipeline/_lazy_input.py` is added to `GUARDED_MODULES` and to the changed-module record of `test_production_execution_modules_are_byte_identical_to_origin_main`; a changed-module record, not a new exemption), `docs/compatibility-contract.md` (one paragraph, 13), `tests/unit/execution/run_stream/test_lazy_input.py`, `tests/unit/execution/run_stream/test_route_summary_native.py`, `CODEMAP.md`, one `changelog.d/` fragment. New public names: the `resident_fallback` keyword and `RouteSummary.native_executed`, nothing else; `fileaccess.ENTRY_POINTS` gains no row. `src/decoy_engine/execution/pipeline/_routing_facts.py` (the one routing-facts builder, declaration, guards, bounded profile, compile and graph over the full source map and the resolved registry; `build_run_context` and the pre-pass both call it; added to `GUARDED_MODULES` and the new-module record as a registration), `src/decoy_engine/execution/_pipeline_context.py` (its fact building moves into `build_routing_facts`), `tests/sentry/source_config/test_declaration_gate.py` (`ROUTES` points at `build_routing_facts`). `pipeline/__init__.py`, the 600-line root facade and the post-scan route sentry and its baseline are untouched. One file over the 10-file bound, accepted: the signature-freeze and physical-seam edits are record rows the slice must carry to be green, so splitting them off cannot land alone. AT-E5 | 11 | 700 | Dennis, then Codex |
| C1l | CLI | open | Exact files: `src/decoy/cli/io/_lazy.py` (new), `src/decoy/cli/run/_execute.py` (`_load_sources_from_config`'s read loop and `resident_fallback=True` on the `execute` `run_pipeline` call only), `src/decoy/_native_gate.py` (`classify_route` lane case), `tests/sentry/io_policy/test_lazy_source_choke_point.py`, `tests/unit/run_stream/test_lazy_sources.py`, `tests/e2e/run_stream/test_lazy_parity.py`, `CODEMAP.md`, one `changelog.d/` fragment. AT-C1a (no-sink cells), AT-C1c, AT-C1f, AT-C1k, AT-C1l, AT-C1n (no-sink cell), AT-C1w (no-sink cells) | 8 | 750 | Dennis, then Codex |
| C1a | CLI | open | Exact files: `src/decoy/cli/io/_sink.py` (new `TargetSink`, `sink_applies`), `src/decoy/cli/io/_delivery.py` (read-only stage seam), `src/decoy/cli/run/_execute.py` (sink branch and row counts), `src/decoy/cli/run/_context.py` (`SINK_UNUSED_CODES`), `src/decoy/cli/run/_render.py` (`route.sink`), `tests/unit/run_stream/test_target_sink.py`, `tests/e2e/run_stream/test_sink_delivery.py`, `tests/sentry/run/test_sink_unused_codes.py`, one `changelog.d/` fragment. AT-C1a (sink cells), AT-C1b (VM), AT-C1d, AT-C1e, AT-C1g (kind R), AT-C1h, AT-C1i (kind R), AT-C1j, AT-C1m, AT-C1n (sink cell), AT-C1w (sink cells) | 9 | 800 | Dennis, then Codex |
| C1b | CLI | open | Exact files: `src/decoy/cli/io/_sink.py`, `tests/unit/run_stream/test_target_sink.py`, `tests/e2e/run_stream/test_sink_delivery.py`, one `changelog.d/` fragment. `sink_applies` admits kind A; `spill_parent` is the fixed folder; AT-C1g and AT-C1i kind-A cells | 4 | 300 | Codex |
| C2 | CLI | open | Exact files: `src/decoy/cli/run/_execute.py` (`--chunked` maps to `execution_mode="stream"`; old fork and class removed), `src/decoy/cli/run/_prepare.py` (obsolete fixed-width/report-path refusals removed; vault and integrity refusals remain), `src/decoy/cli/_sources.py` (`iter_source_chunks` removed), `src/decoy/cli/exit_codes.py` (obsolete exception rows removed), `src/decoy/cli/io/_delivery.py` (the one closed-evidence relationship-only missing-report exception, preserved through DELIV C5), `src/decoy/cli/run/_render.py` (summary and `--json`), `tests/e2e/run_stream/test_chunked_unified.py`, `tests/sentry/run/test_one_run_pipeline.py`, one `changelog.d/` fragment. REL-PKG installed-wheel prerequisite; AT-C2a to AT-C2d | 9 | 650 | Codex |
| P1 | platform | open (PARKED with Platform V1) | `api/cgroup_cpu.py` calls the public engine `detect_usable_cpus` with `fs_root` and `affinity`; lands with the platform's repin | 4 | 150 | Codex |
| M1 | CLI evidence (macOS arm64) | open | temporary venv, the section 1 Parquet/CSV and thread sweep through 16M rows, record evidence, remove venv; AT-M1 | 2 | 120 | Codex |

Order and what each open slice waits on:

- E4 needs nothing new; it can build now on engine main. It ships in the next engine release, which
  also carries SE3b (#595, `FixedWidthLazySource`), because SE3b is already on engine main
  (`c7433ede`) and 0.26.0 does not have it.
- E5 can build now on engine main, beside E4; both ship in the next engine release. The CLI repin
  to that release (`pyproject`, `uv.lock`, the repin checklist) is the orchestrator's chore PR, as
  for 0.26.0 (#267), outside every slice here.
- C1l waits only on that repin. It takes no sink and edits the read loop of
  `_load_sources_from_config` in `_execute.py` plus one keyword on the `execute` `run_pipeline`
  call, a one-line touch at a call site the `_execute.py` lane orders; it rebases onto whichever lane
  slice lands first. E5's resident
  collector makes its no-sink auto-chunk cells valid. It lands before C1a so a difference lazy
  input makes shows up without the publication sink in the way.
- C1a waits on C1l, on the owner's Q8 answer (option (b) changes `sink_applies` and adds an engine
  slice), and on two more things: the CLI repin to the engine release carrying E4 (roadmap rule 5.2.10
  starts the CLI half the moment that pin lands), and DELIV C2a merged on CLI main. DELIV C2a builds
  `DeliverySink`, its kind R stage, `place_quarantine`, the abort callback on `layout.abandon()` and
  the `SinkStage` protocol that `TargetSink` sits on; without it there is nothing to stage into.
  C1a then takes the `_execute.py` lane directly after DELIV C2a (DELIV 14 lane order; roadmap rule
  5.2.2), ahead of DELIV C3. If DELIV C3 is ready first, C1a rebases after it; the two touch
  different branches of `execute`.
- C1b waits on C1a and DELIV C2b (kind A's batch stage).
- C2 waits on C1b, the REL-PKG installed companion wheel (AT-C2d), the E4/E5 pin and DELIV C5.
  Waiting for C5 makes the relationship-only exception an edit to the final
  `post_scan_gate_applies` missing-report choke point, not a rule a later DELIV slice can overwrite.
  Base `--chunked` streams CSV and refuses fixed-width today; after C2 both stream.
- P1 waits on Platform V1 (PARKED). M1 can run once C2's candidate exists; AT-M1 and AT-C2d both
  block the V1 release gate.
- Q8 (b), if the owner picks it, adds one engine slice before C1a and the release that carries it.

## 15. Pre-mortem

- The sink changes output bytes for a corner (empty source, all-null column, a Parquet schema with
  dictionary encoding). Guard: AT-C1a runs the existing CLI format fixture set and the empty-source
  rule from `write_chunked_output` (`src/decoy/cli/io/_targets.py:528-533`).
- Defaults overcommit memory on a shared box. Guard: CLI `auto` calls the engine-owned conservative
  policy and passes an explicit 25% budget; AT-E1e resolves two concurrent automatic runs on one host;
  the summary prints the resolved value and its source; `settings.json` and `--max-memory` may raise it.
- A route the plan did not list returns tables in `result.outputs` while also streaming some. Guard:
  `seal_result` rejects overlap, writes every output table that has a configured target exactly
  once, and performs all remaining serialization before checks; delivery only moves staged files (DELIV). AT-C1g covers every route shape the
  engine has today (`_isolated_worker.py:138-165` documents the two current shapes).
- The native knee hides the thread setting (6 threads asked, 4 used). Guard: the clamp is recorded and
  printed.
- CSV streaming diverges from the resident CSV read on a dialect edge. Guard: AT-E2a uses the CSV
  framing corpus F06 already has.
- SUB-RUN (row 57) and DELIV C3 edit the same call site. Guard: the `_execute.py` lane order puts
  SUB-RUN C1 and DELIV C2a before C1a; one `run_pipeline` call site sentry (AT-C2c) keeps every
  change on one path.
- A future change makes a relationship job take the sink, and the post-scan gate quietly turns
  into a warning. Guard: `sink_applies` is the only place the decision is made and it calls
  `post_scan_gate_applies`; AT-C1j and M-C1j2 fail if the predicate is copied or dropped.
- A fixed-width source streams with a different schema or failure than the resident read. Guard:
  engine AT-18b pins schema and values; AT-C1w pins exits and reasons through the CLI.
- Lazy input on every plain run (revision 6) changes a route or a failure for a job that takes no
  sink: a CSV dialect, a fixed-width blank field, a route the engine picks for a lazy source but
  not for a resident one, or a gate that turns report-only. Guard: under
  `resident_fallback=True` the run (E5) reads whole, before routing, the lazy sources of vault runs,
  relationship jobs that are not bounded-eligible, declared-cast tables and transform-bearing tables
  under the gate (5.1); C1l lands alone before the
  sink; AT-C1a, AT-C1c, AT-C1l and AT-C1w compare with the base resident run on the CLI fixture set,
  the 6.3 FK shapes, the gate shapes and the fixed-width corpus; a reason that differs from base is
  a C1l stop, reported, not adapted around.
- V2-LOG: under `resident_fallback=True` some refusals that `build_run_context` raises (F13 secret
  admission, duplicate-table and loader-table refusals) now come after the pre-pass's bounded
  profile and its reads of rejected tables. A run with two faults can report a different refusal
  code first than base. A single-fault run is unchanged; recorded, not fixed in V1.
- DELIV C2a changes a member `TargetSink` calls before C1a starts. Guard: C1a's builder brief
  re-reads DELIV's merged `io/_delivery.py` first and reports a mismatch instead of adapting
  around it.

## 16. Follow-ups (recorded, not in V1)

- V2-LOG: delete `run_mask_pipeline_chunked` once the platform stops naming the public entry
  (`src/decoy_engine/execution/_chunked.py:377-391`; Q6).
- V2-LOG: `_fpe.py` uses `os.cpu_count()` outside RUN-STREAM's resource path; move it to
  `detect_usable_cpus` in the V2 cleanup (`src/decoy_engine/execution/_strategies/_fpe.py:353`).
- V2-LOG (Q8 (a)): the post-scan gate reads back only the engine's own sink. Let it measure the
  batches it hands any sink, then remove the post-scan condition from `sink_applies` so
  relationship jobs stream their output (`config/_post_scan.py:162-210`).
- V2 (VAULT-STREAM, `docs/roadmap/out-of-scope.md:20`): a vault on a sink run; until then a
  `--vault` run takes no sink (B0).
- V2-LOG: `TargetSink` has no `publication_evidence`, so engine-side failure observation cannot
  describe its cleanup precisely (`src/decoy_engine/execution/_transactional_sink.py:40-43`).
- V2-LOG: section 1.4's parenthetical `1.2` after the 219.2 s against 240.2 s comparison is an
  unexplained single-run annotation; the surrounding sentence already gives the supported numbers
  (section 1.4).
- V2-LOG: evaluate whether platform and library callers should later receive an explicit conservative
  policy or keep current `resolve_ooc_memory_limit(None)` behavior; V1 deliberately changes only CLI
  `auto`, so those callers retain the effective-ceiling-minus-reserve default.
- V2-LOG: the platform's separate native-job budget policy is unchanged by RUN-STREAM
  (section 1.3).
- V2-LOG: section 6.5 overstates its path rule because CPU-limit diagnostics can name `/proc` or
  cgroup paths; paths are user-written structure under the owner bar, so this is not a value leak
  (section 6.5; `api/cgroup_cpu.py:125-131`, `:138-172`).
- Stream `fixed_width` and archive CSV targets (fixed-width sources stream from C1l).
- Cloud sources as lazy sources (E4 returns `None` for them; CLI-CLOUD owns cloud I/O).
- V2-LOG: the post-scan route sentry misses `estimate_job_capacity` (`execution/capacity.py:235`), an `@entry_point` whose config parameter is named `config_dump`; record only, not fixed here.
- RESULT schema fields for route and resources if RESULT v1 is closed.
