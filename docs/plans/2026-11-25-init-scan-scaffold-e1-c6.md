Status: plan

# INIT-SCAN-SCAFFOLD: `decoy init SOURCES...` scans and writes a reviewable scaffold

Owner: Cam. Author: Opus plan agent. Date: 2026-11-25 (first written 2026-11-23). Revision: 4 (re-anchor on current main after Dennis R1 and R2 and the owner input of 2026-11-23; see "Rev changes"). Copied from `origin/plan/init-scan-scaffold` revision 3. Roadmap row: INIT-SCAN-SCAFFOLD (new V1 row, owner direction 2026-11-23). Related rows: SCAN-MULTI row 27 (S1c.2a merged as CLI #400; S1c.2b not started and not on the 1.0 list), SCAN-MULTI row 29 S3-cli (moved to 1.1 on 2026-11-22), DECOY-LANG S4, S6 and S8 (`docs/plans/2026-11-19-decoy-language-commands.md`, revision 3), INIT-WIZARD row 32b (stopped 2026-11-19), PRE-SCAN-RUN, COLUMN-SHAPE-RULE.

Anchors: `C:` is the CLI repo at `origin/main` `fffca916` (2026-11-25). `E:` is the engine at `origin/main` `2b8a47fbe` (2026-11-24). The CLI pins `decoy-engine` 0.28.3; CLI PR #408 (open) moves the pin to 0.28.4, which is tagged. Row 27 S1c.2a is merged (CLI #400). PRE-SCAN-RUN's verdict is merged (engine #764), so its second copy of the regex rule is now on engine main.

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md` (PLAN, Proportion), `api-and-compatibility.md`, `cross-cutting-concerns.md`, `proportionality.md`, `security.md`, `testing.md` (Test depth), `workspace-and-vcs.md` (Commit messages), `catalogs/recurring-defects.md` (classes 1 to 11). CLI `CODEMAP.md` "Where Things Go", `tests/fixtures/release_freeze/json-shapes.json`, `tests/sentry/release/test_default_command_flags.py` (#381). Engine row 27 plan revision 8.3 (S1c, S3-engine, S3a.1). The stopped wizard plans `C:docs/plans/2026-11-08-init-wizard-phase-1a.md` and `C:origin/plan/init-wizard-v1-rest:docs/plans/2026-11-17-init-wizard-v1-rest.md`.

Risk: R2 overall. E1 turns a frozen refusal into a normalization. C3 deletes a CLI module and changes the scaffold bytes of `decoy init FILE`. Plan review: Dennis, then Codex. Code gate: Codex plus Dennis on E1, E2, C3 and C5a; Codex only on the rest. Tests: T0 per edit, T1 per commit, the T2 set on each merge head. Full-suite triggers: E1 (frozen refusal), C1 (version pin), C3 (moved and deleted tests).

## Rev changes

Rev 2 fixed Dennis R1 (H, M, L rows below). Rev 3 fixes Dennis R2 (R2- rows).

| Finding | Fix | Sections |
|---|---|---|
| H1 header-suspect names leak cell values | C3 refuses with exit 1 and fixed text (`init.header_suspect`, hint `--no-header`) before rendering; G6 restated | 4.1 G6, 4.8, 9.2 row 1, 10.1, AT-C3l, M-C3l |
| H2 source paths become absolute | C3 rewrites each file source with `source_text(path, destination)`; named; pinned in the golden | 4.8, 8, AT-C3m, AT-C3n |
| H3 init would need a header flag | init defaults to a header row when no header flag is given; H1's refusal is the safety net; AT-C3k relabeled green | 4.6, 8, AT-C3k, M-C3k |
| H4 E1/C1 sequencing and labels | re-pin and C1 in one CLI PR; AT-C1a red on the pre-re-pin base; AT-C1c is now a text pin; M-C1a keeps the old text | 2, 5, 6, 7 |
| H5 NER rule on a bucket that does not exist | NER hits add evidence only, never change an entry; labels use the real buckets (`<10%`, `10-50%`, `>=50%`) | 4.4, 4.7, AT-E2d, M-E2d |
| H6 AT-C3c shapes and existing literals | adds the `strategy=` keyword and dict-value shapes with seeded cases; shrink-only baseline for `completers.py::TRANSFORM_IDS` and `explain.py::_STRATEGY_NOTES` | 4.10, AT-C3c, M-C3c |
| M1 label versus detector id | rule 3 uses `detector_entry(hit.detector_id, ...)` | 4.4, AT-E2a |
| M2 `live` meaning | E2 redefines `live` in its docstring and pins it with a test | 4.4, AT-E2g |
| M3 second copy of the regex rule | PRE-SCAN-RUN `_effective_detectors` reads the parsed detectors after E1; E1 adds a guard | 4.3, 13, AT-E1e |
| M4 no golden | golden for the three-source scaffold, YAML in C3 and `.decoy` in C5a | 6 (AT-C3n, AT-C5f), 8 |
| M5 `_columns.py` helpers, hand-quoting | keep `_columns.py` and its preset helpers; delete only `emit_column_yaml`; render each block with `yaml.safe_dump`, comments between blocks; G-ONE-EMITTER shapes and exemptions listed | 4.8, 4.10, 4.11, AT-C3d |
| M6 prompt scope | the preset path keeps its prompts and `_confirm_overwrite`; only the scan path loses them | 4.2, 4.6, AT-C3f |
| M7 FK candidate cannot validate | the candidate comment carries both key entries (`hash` plus one shared namespace) and the relationship; self-reference claim removed | 4.5, 10.5, AT-C6a |
| M8 `pre_scan` turns on run-start scans | the scaffold writes no `pre_scan` or `scan before`; `--detectors` applies to the init scan only | 4.2, 4.6, 8, AT-C3i |
| L1 engine QA doc | E1 updates `E:docs/qa/03-pre-scan-profiling-detection.md:37` (SCAN-07) | 5, 8 |
| L2 scan-call allowlist | C3 deletes `cli/init.py::_scaffold_from_file` from `tests/sentry/baselines/scan-call-allow.json` | 4.8, 9.1 |
| L3 "AT-F2f" | named by file: `C:tests/unit/release/test_check_shape_changelog.py` | 8 |
| L4 S8 `decoy convert` half | stays open in DECOY-LANG | 2, 13 |
| L5 C2 and S1c.2a both edit `_multi.py` | C2 rebases on S1c.2a if S1c.2a merges first | 2 |
| L6 late output-exists check | early check before the scan; `CREATE_ONCE` stays the authority | 4.6, AT-C3f, AT-C3o |
| L7 fixed-width targets | a fixed-width source gets a CSV target | 4.8, 10.4 |
| A1 (addendum) 1.x scan-diff input | three points added | 13 |
| Addendum (a) init writes only the scaffold | AT-C3a asserts the folder holds only the scaffold | 6 |
| Owner 11-23 | init writes only the scaffold; `decoy scan` alone writes the artifact, whose shape must stay stable for 1.x scan-to-scan diffs | 4.1 G8, 4.7, 8 |
| `_DATE_REDACT` wording (Dennis check list) | named as a wording change | 8 |
| R2-H1 AT-C3c red at C3 head | C3 deletes `_NAMESPACE_REQUIRED_STRATEGIES` with `emit_column_yaml`; `cli/demo.py` exempt by path; the hit list on the C3 base is recorded | 4.8, 4.10 |
| R2-H2 target paths changed without saying so | targets keep `target_text(source, format)` unchanged (bare name, `run` places it in the run folder); AT-C3m expects `people.masked.csv`; TSV and fixed width get a CSV target, as today | 4.8, 10.4, AT-C3m, AT-C3p |
| R2-M1 `source_text` input | `source_text` gets the path as typed (the `shown` map from `resolve_sources`); `-o -` cell added | 4.8, AT-C3m |
| R2-M2 `--no-header` needs `--column-names` | refusal text names both flags and says they work for one file; C4 adds the `--config` sentence; AT-C3l's success half passes `--column-names` | 4.8, 5, 12, AT-C3l, AT-C4b |
| R2-M3 header check in the CLI, not at the root | E2 makes `starter_config` raise a coded, value-free refusal; the CLI maps it to `init.header_suspect` | 4.4, 4.8, AT-E2h, AT-C3l |
| R2-M4 AT-E1e false hit on `Literal[...]` | subscript slices excluded; `.add("regex")` shape dropped; hits on the E1 base recorded | 4.3, AT-E1e |
| R2-M5 one FK comment block cannot validate | commented relationship under `relationships:` plus one comment beside each existing key entry; AT-C6a restated | 4.5, 10.5, AT-C6a |
| R2-M6 comment-line injection | one comment helper renders names with `json.dumps` and refuses control characters; newline cells | 4.8, 4.10, AT-C3q |
| R2-L1 AT-C2d byte compare | normalizes `scanned_at` and `engine_version` | AT-C2d |
| R2-L2 G-ONE-EMITTER string shape | skips docstrings | 4.10 |
| R2-L3 baseline counts | the sentry enforces the per-site count ceiling itself (`ratchet_check` compares keys only) | 4.10 |
| R2-L4 AT-C3l side effects | asserts no project member folder is created; `prepare` runs only at write time | 4.8, AT-C3l |
| R2-L5 release waits on E3 | release 1 = E1 + E2; E3 ships later in release 2 with C6 | 2, 5 |
| Rev 4 A1 anchors stale | anchors moved to CLI `fffca916` and engine `2b8a47fbe`; line numbers re-read | header, 1.2, 4.4 |
| Rev 4 A2 S1c.2a merged (#400) | C3 no longer waits on row 27; C3 waits on C1 only | 2, 5, 12 |
| Rev 4 A3 PRE-SCAN-RUN merged (#764) | E1 removes the copy at `E:profiling/pre_scan/_check.py:147-148` itself; it calls `canonical_detectors`, so an absent `pre_scan` block still counts regex; AT-E1f, M-E1f | 2, 4.3, 6, 7, 12, 13 |
| Rev 4 A4 S1c.2b has no row and no PR | C4 becomes an OWNER CALL (O1, default: C4 moves to 1.1 with S1c.2b) | 2, 5, 12, 14 |
| Rev 4 A5 pin PR #408 open | C1 rebases on #408 if it merges first, else C1 carries the 0.28.4 checklist items too | 2, 5 |
| Rev 4 A6 stale CLI PR #68 edits `init.py` and `_init_inference.py` | named as a conflict; C3 deletes `_init_inference.py`, so #68 must rebase or drop its hunk there | 2, 12 |

## 1. Frame

### 1.1 What the owner asked for (2026-11-23)

1. `decoy init <sources...>` scans many sources and writes a `.decoy` scaffold. Every suggestion carries a review mark. The user reviews the file. No prompts.
2. Regex always runs and never needs naming. `--detectors ner` means regex plus NER. `regex` stays accepted. One place owns this rule.
3. Model hits (classifier, NER) show in the scan card, in `--json` and in the saved artifact, next to the regex evidence, with no cell values.
4. `decoy scan` runs the same scan and only reports or saves an artifact. Same detector rule.
5. Basic foreign-key suggestions if they are cheap.
6. Build on row 27. Init uses the one scan call. Settle how this row relates to DECOY-LANG S6.
7. Intent is explicit: types, keys and relationships compile to explicit YAML fields (owner, 2026-11-21).
8. (Owner, later on 2026-11-23.) Init writes only the scaffold: no scan artifact, nothing in the library. `decoy scan` alone writes the artifact, and its saved shape must stay stable enough for 1.x scan-to-scan diffs (flags and notifications).

### 1.2 What exists today (probed)

- `decoy init FILE` reads one file through `_load_dataframe` (`C:src/decoy/cli/init.py:328`, `read_csv_frame(..., nrows=10_000)`), runs `profile_columns`, then the CLI's own `_infer_strategy_for_column` (`C:src/decoy/cli/_init_inference.py`, 360 lines). It hand-writes YAML with one table named `data` and `# REVIEW:` comments (column text from `C:src/decoy/cli/project/_columns.py:60`). This is a second scan path beside G-ONE-SCAN-CALL (`C:tests/sentry/scan/test_one_scan_call.py`), allowed by the entry `cli/init.py::_scaffold_from_file` in `C:tests/sentry/baselines/scan-call-allow.json`.
- `decoy init people.csv` works with no header flag and treats the first row as a header. A source is written relative to the output file (Dennis probe P1: `-o sub/p.yaml` writes `'../people.csv'`; `C:docs/project-layout.md:61`).
- The CLI rule table has drifted from the engine's. Probe on the Dell node (`vm-run cli`, CLI main): `decoy init people.csv -o -` writes `date_shift(min_days: -365, max_days: 365, date_format: "%Y-%m-%d")`. The engine starter dropped the fixed `min_days` and `max_days` on 2026-11-20 (DATE-SHIFT-FORMAT, `E:docs/compatibility-contract.md:268-276`).
- The scan path of `decoy init` asks an overwrite question (`_confirm_overwrite`) unless `-y`, and writes with `Path.write_text`.
- The engine has a multi-table starter, merged with row 27 S3-engine, #653 and #728: `decoy_engine.profiling.starter_config(scan: ScanSet, *, relationships=(), ...) -> StarterConfig(config, notes, suggestions, relationship_template)`. It never reads model hits. `ColumnSuggestion` already has `source`, `model`, `band` and `live` fields, and its `__post_init__` already refuses a live non-regex suggestion (`E:src/decoy_engine/profiling/_starter_config.py:85-121`; the module is 457 lines), and `TableScan.model_hits` already carries the hits (`E:src/decoy_engine/profiling/scan_set.py:126`).
- `starter_config` names columns from the in-memory profile, not from the value-free core. When a scan flags `warning.scan_header_suspect`, the core renames the columns `c0..cN` (`scan_set.py:_core_names`), but the starter still uses the first data row as names. Dennis probe P3: a headerless PII CSV scanned with a header gives column names that are cell values. `resolve_sources` also writes absolute paths into the descriptors (`p.resolve()`, `C:src/decoy/cli/scanning/_multi.py:281`) and returns the paths as typed in a second map, `shown` (`_multi.py:266-274`). Today init writes the target as the bare name from `target_text` (`C:src/decoy/cli/project/_scaffold.py:205-208`), which `run` places in the pipeline's run folder.
- `--detectors` without regex is refused by the engine only (`canonical_detectors`, `E:src/decoy_engine/config/_pre_scan.py:37-46`, code `detectors_invalid`). The CLI passes the list through (`C:src/decoy/cli/scanning/_detectors.py:66-86`) and maps the refusal to its fixed text `_BAD_LIST` (line 40). The engine function also parses `post_scan.detectors` (`E:src/decoy_engine/config/_post_scan.py:102`). PRE-SCAN-RUN (merged, engine #764) holds a second copy of the rule: `_effective_detectors` (`E:src/decoy_engine/profiling/pre_scan/_check.py:147-148`) returns `sorted({*(policy.get("detectors") or ()), "regex"})`, and `evaluate_pre_scan` reads `config["pre_scan"]` as a raw mapping that may be absent (line 179).
- `decoy scan` drops model hits from the card and `--json`: `safe_field_record` (`C:src/decoy/cli/scanning/_multi.py:78-92`) keeps `detector_hits` only. The saved core (`--output`) and `scan show --json` already carry `model_hits`.
- NER hits exist only when `NerRate.hit` is true, a calibrated per-model rate threshold, and NER scores only free-text columns (`E:src/decoy_engine/profiling/_model_pass.py:96-101`, `E:src/decoy_engine/detection/_ner_rate.py`). The rate buckets are `<10%`, `10-50%` and `>=50%`.
- Cheap-path probe (Dell node, CLI main): today's init YAML, with `pre_scan.detectors: [regex, ner]` added, converts through the merged `decoy.lang.convert_config` to a valid program in one call. It loses every `# REVIEW:` note and has no `?` marks, because the converter has no review input. That input is DECOY-LANG S6's `convert_config(config, *, review=...)`.

### 1.3 Impact

A user with three CSV files cannot get one starter pipeline today. The single-file scaffold names the table `data`, ignores model hits, uses a stale copy of the engine's rules, and can stop on a prompt.

## 2. Overlap and sequencing

| Item | State | Relation to this row | Decision |
|---|---|---|---|
| Row 27 S1c.2a: one gated scan call, `scan_descriptors` (`C:src/decoy/cli/scanning/_engine_call.py:55`), `scan_prepared_sources` (`C:src/decoy/cli/_sources.py:210`) | merged (CLI #400) | Init calls the same `scan_descriptors`. | No longer blocks. This row does not edit the scan call. |
| Row 27 S1c.2b: `--config` sources file for scan | not started; no 1.0 row, no PR, no `--config` on `decoy scan` at `fffca916` | Per-source header and dialect for init would come from the same sources file. | C3 builds positional sources. C4 waits on S1c.2b; whether either is V1 is owner call O1 (default: both 1.1). |
| Row 27 S3-engine (`starter_config`) | merged | The suggestion engine for this row. | Reuse. E2 extends it with model hits. |
| Row 29 S3a.1 (init rewrite, G-ONE-EMITTER) | 1.1, waits on LIB L2 | This row pulls the init half back into V1 without LIB, `scan_baseline`, `--emit-config` or `--compare`. | C3 takes the S3a.1 design minus those. Row 29 later reuses C3's `render_scaffold`. |
| DECOY-LANG S6 (`decoy init` writes `.decoy`) | not started | Same output step. | Folded in as C5a (scan scaffolds) and C5b (presets). S6 closes with C5b. |
| DECOY-LANG S8 (classifier guesses become suggested rules when `decoy init` or `decoy convert` writes `.decoy`) | not started | The init half is E2 plus C5a. | Folded for init only. The `decoy convert` half stays open in DECOY-LANG (L4). |
| DECOY-LANG S2, S3 | not started | Owner call O4: init writes `.decoy` by default "once S1 to S3 are in". | The `.decoy` default (C5a) waits for S2 and S3 by owner call. |
| DECOY-LANG S4 (project member `pipelines/x/pipeline.decoy`) | not started | The member default needs it. | C5a depends on S4. |
| Wizard row 32b | stopped | Left engine pieces with no CLI caller. | Section 11 says which are reused. |
| PRE-SCAN-RUN verdict | merged (engine #764) | Holds a second copy of "add regex" in `_effective_detectors`. | E1 replaces it with a call to `canonical_detectors`; AT-E1e and AT-E1f guard it (M3). |
| CLI pin 0.28.4 (#408) | open | C1 re-pins the same files. | Whichever merges second rebases; if #408 is closed, C1 carries its checklist items. |
| CLI #68 (F26 local-cleanup, open since 2026-11-18) | stale | Edits `cli/init.py` and `cli/_init_inference.py`. | C3 deletes `_init_inference.py`; #68 rebases and drops that hunk. Not a blocker for C3. |

Order:

1. E1 and E2 in parallel (engine), then engine release 1 (E1 + E2 only, so C1 and C3 do not wait on foreign-key work).
2. C1 = the CLI re-pin to release 1 plus the detectors text, in one CLI PR (H4). The re-pin alone would turn the old refusal cells red.
3. C2 can start now (S1c.2a is merged; nothing open edits `_multi.py`).
4. C3 after C1 merges.
5. C4 after S1c.2b and C3, if owner call O1 keeps it in V1.
6. C5a after C3 and DECOY-LANG S2, S3, S4. C5b after C5a.
7. E3 (owner said yes to Q2, level A) after E2, then engine release 2 and C6 (re-pin plus link comments) after C3.

## 3. Established solutions

Search run: scaffold generators (`rails generate`, `dbt init` and dbt-codegen `generate_source`/`generate_base_model`, Terraform config generation with `import` blocks), profiler-driven config (Great Expectations `UserConfigurableProfiler`, SDV `Metadata.detect_from_dataframes`), and the codebase (`starter_config`, `walks/inference.py`, the stopped wizard plans).

- Scaffold, then review by editing: dbt-codegen and Terraform's generated config both write a file the user edits and commits; neither asks questions. We follow this.
- Inferred keys are suggestions: SDV's metadata detection guesses keys from names and asks the user to validate before use; Great Expectations marks profiler output for review. We follow the conservative name rule already in `E:src/decoy_engine/walks/inference.py:1-25` and keep candidates as comments.
- A required member the user need not name: pydantic `field_validator` normalization at the model boundary. We follow it for regex.
- YAML text: `yaml.safe_dump` per block (already used at `C:src/decoy/cli/demo.py:125` and `C:src/decoy/cli/gen/_scaffold.py:127`) instead of hand quoting. Comments go between blocks because PyYAML does not keep comments.

Custom code left: the review-note text and the model-hit rule in E2. No library covers Decoy's detector descriptors.

## 4. Design

### 4.1 Guarantee

- G1. `decoy init SRC [SRC...]` makes one engine scan call through `scan_descriptors` and writes one pipeline with one table per source, named by `table_name_from_path`. Every column gets the entry `starter_config` chose. No second profiler, no CLI rule table.
- G2. Every column entry the scaffold writes carries a review mark: `?` plus a note comment in `.decoy`, a `# REVIEW:` comment in YAML. A `.decoy` scaffold does not run until the marks are removed (`load_config_mapping` refuses `?`, DECOY-LANG S1, merged).
- G3. Regex always runs. `--detectors` lists the extra sources. `regex` is accepted and changes nothing. The rule is in one place: the engine's `canonical_detectors`.
- G4. A classifier or NER hit appears next to the regex evidence in the scan card (`--show-fields`), `--json`, the saved scan, and the scaffold note: source, detector id, model id and version, band or rate bucket. Never a cell value.
- G5. The scan path of init asks no question. An existing output is refused unless `--yes`, first by an early check, then by `CREATE_ONCE` at write time. The write is atomic and owner-only.
- G6. Nothing the row writes or logs holds a cell value: scaffold, notes, card, `--json`, logs, errors. The starter names columns from the in-memory profile, so this needs one more rule, owned by the engine: when any scanned table carries `scan_header_suspect`, `starter_config` refuses with a coded, value-free error (E2), and init maps it to `init.header_suspect` and prints no column name.
- G7. Shapes are explicit. A text date column gets `date_format` only when every hit parses with it (engine #728), else `redact`. The starter suggests no strategy that needs a declared shape (bucketize, top_code), so no F06 declaration is written.
- G8. Init writes only the scaffold file: no saved scan, no library record, no `scan_baseline` block. Source paths in the scaffold are relative to the scaffold file; target paths keep today's bare names.

### 4.2 Non-goals

- No prompts and no interactive review in the scan path, and no caller of `apply_review` or `finding_edits` (section 11). The preset path keeps its preset and path prompts and `_confirm_overwrite` unchanged (M6).
- No `pre_scan` block or `scan before(...)` in the scaffold. `--detectors` chooses what the init scan runs, not what later runs do. A run-start pre-scan loads models and scans on every run, and the owner leans to no run-start pre-scan unless the user gates or flags (M8).
- No value-based foreign-key discovery (owner parked it 2026-11-05; stays 1.x).
- No active (uncommented) inferred relationship.
- No `--emit-config`, `--compare`, library ref or `scan_baseline` (row 29, 1.1).
- No Markdown report for `decoy scan` in V1 (Q3).
- `--preset` templates keep their content. C5b changes only their output format.
- No change to the scan call, its sampling or its default rows.

### 4.3 E1: regex is always on (the engine owns it)

`canonical_detectors(value)` returns `("regex", *rest)` in canonical order when regex is missing, instead of raising. An empty list becomes `("regex",)`. A repeat and an unknown source still raise `detectors_invalid`. `ner_model` without ner still raises `pre_scan_ner_inactive`.

Why the engine and not the CLI:

- The rule must hold for `--detectors`, `pre_scan:` and `post_scan:` in YAML, `scan before(ner)` in `.decoy`, the Python API and PRE-SCAN-RUN. Only the engine model sees all of them.
- The CLI already passes the list through, so the CLI needs no rule of its own.
- Cost: one engine release and a CLI re-pin, which E2 needs anyway.

Effect: a config written with `[ner]` dumps as `[regex, ner]`, and two configs that differ only by naming regex parse to the same model (AT-E1d).

Second copy (M3): PRE-SCAN-RUN's `_effective_detectors` (merged, engine #764) adds regex itself. It reads a raw config mapping, and `pre_scan` may be absent there, so reading the field directly would drop regex for a config with no `pre_scan` block. E1 changes its body to `return tuple(sorted(canonical_detectors(tuple(policy.get("detectors") or ()))))`: the one rule, which turns an empty list into `("regex",)`. The sort stays because `PreScanVerdict.detectors` is documented as sorted (`_check.py:60`) and reaches the verdict output (line 219), so its bytes do not change. AT-E1f pins both. E1 adds AT-E1e, a guard that no engine module outside `config/_pre_scan.py` builds a detector set by adding the literal `"regex"`. Shapes: a set, tuple or list literal holding `"regex"` and at least one other element (a starred element counts, so `("regex", *x)` and `{*x, "regex"}` match), and `| {"regex"}`. Excluded: every node inside a subscript slice, so `Literal["regex", "classifier", "ner"]` (`E:src/decoy_engine/detection/types.py:20`) and `get_args(...)` uses do not match. A one-element default such as `("regex",)` (`E:src/decoy_engine/config/_post_scan.py:93`) does not match. `.add("regex")` is not a shape: in PRE-SCAN-RUN it records a flag source (`_check.py:166`), not a detector set. Hits on the E1 base, engine `origin/main` `2b8a47fbe` (the builder re-runs the AST script, no pytest): one, `profiling/pre_scan/_check.py:148` (`{*(policy.get("detectors") or ()), "regex"}`), the copy this guard exists to remove. E1 removes it in the same PR, so the guard is red on the base and green at the E1 head.

E1 also updates the engine QA doc `E:docs/qa/03-pre-scan-profiling-detection.md:37` (SCAN-07 pins the refusal). Size: about 10 source lines in `_pre_scan.py`, about 40 for the guard, no new public name.

### 4.4 E2: model hits become suggestions (engine; folds the init half of DECOY-LANG S8)

`starter_config` reads `TableScan.model_hits[column]` for each column. Rules, in order:

1. A declared relationship key: unchanged (`hash` plus the shared namespace).
2. A confident regex decision (`infer_starter_strategy`, unchanged): the regex entry wins. A model hit on the same column adds evidence to the note only. When the hit's detector id differs, the note says so: "classifier says person_name, regex says email; regex kept".
3. No confident regex decision and a classifier hit with band `high`: the entry is `detector_entry(hit.detector_id, column, date_format=...)` when that returns an entry (`ModelHit.detector_id` is already the mapped id, `E:profiling/_model_pass.py:126`). The suggestion is `ColumnSuggestion(source="classifier", model=..., band="high", live=False)`. A band `review` hit changes no entry: the fallback stays and the note names the hit.
4. An NER hit adds evidence only and never changes an entry. NER scores free-text columns, and a whole-cell `faker` rule on a `notes` column would be wrong. Such a column usually falls back to `redact` already.
5. Otherwise: unchanged (integer-unique hash rule, then `redact`).

Notes gain one evidence line per hit, for example `classifier lgbm-v1 0.1.0: email (band high)` or `ner en_core_web_sm 3.8.0: person_name (rate >=50%)`. Only detector ids, model ids, versions, bands and buckets.

`live` (M2): today's docstring says "written into the config". Every starter entry is written, so that reading no longer separates anything. E2 redefines it: `live` is true when the entry was decided by a deterministic rule (regex, declared key, integer-unique hash, fallback) and false when a model chose it. The docstring changes and AT-E2g pins it. The #653 rule (only regex suggestions may be live) still holds.

Header refusal (R2-M3): before building any entry, `starter_config` checks every `TableScan.warnings` for `reasons.warning.SCAN_HEADER_SUSPECT`. If any table has it, it raises `PipelineConfigError.from_problems([ConfigProblem(<new config reason starter_header_suspect>, "tables[<index>]", "A scanned table looks like it has no header row; its column names may be data.")])`. The message names no table, column or path. The new reason goes in the engine reason registry with its manifest row. Every caller gets the rule, including row 29 later.

No new public name besides the reason code; `starter_config` and `StarterConfig` keep their signatures. Dennis measured `_starter_config.py` landing at about 637 lines; if the build passes 650, the model rules go in a new `_starter_models.py`.

### 4.5 E3: name-only foreign-key candidates (owner: yes, level A)

`starter_config(..., link_candidates=True)` builds a `SchemaSnapshot` from the scanned table and column names and runs the existing `walks.inference.infer_edges`. That rule fires only for a column named `<table>_id` (singular or plural table name) whose target table has a column `id`. It returns `StarterConfig.link_candidates: tuple[LinkCandidate, ...]`, where `LinkCandidate(parent_table, parent_column, child_table, child_column, namespace)`. The namespace is `link-<parent_table>-<parent_column>`. Names only: no value read, no containment test, no effect on any written entry. New public names: `LinkCandidate`, one keyword, one field.

How C6 prints a candidate (R2-M5). A key entry belongs under `tables[].columns`, and both columns already have an entry there (`orders.customer_id` usually `redact`, `customers.id` `hash`). A relationship belongs under top-level `relationships:`. So one block cannot hold both. C6 prints:

- under `relationships:` a commented relationship: parent `customers.id`, child `orders.customer_id`, `namespace: link-customers-id`, and an `orphan_policy` line for the user to choose;
- beside each of the two existing column entries, one comment: `to keep the link customers.id -> orders.customer_id: strategy hash, namespace link-customers-id`.

The user uncomments the relationship and edits the two entries as the comments say. In `.decoy` the same: a commented `link` line, and a note above each of the two mask lines.

Complexity:

| Level | What | Cost | Risk |
|---|---|---|---|
| A (V1) | the name rule, written as a commented relationship plus a comment beside each key entry | E3 about 120 + 150 test lines, C6 about 100 + 140 | Low: a wrong guess is a comment the user deletes. |
| B | A plus a containment check on each candidate | an engine change so the scan computes facts for undeclared pairs, about 400 lines, and a `scan-set/v1` minor | Medium. 1.x. |
| C | value-overlap discovery over all column pairs | large | High; owner parked it. 1.x. |

### 4.6 CLI surface

`decoy init` (C3, C4, C5a):

```
decoy init SOURCE [SOURCE ...]
           [--has-header | --no-header] [--column-names A,B,...] [--format csv|tsv|parquet|fixed]
           [--layout FILE] [--config SOURCES.yaml]                    (--config arrives in C4)
           [--rows N] [--detectors classifier,ner] [--ner-model NAME]
           [-o PATH | -o -] [--yaml] [--yes] [--json] [--quiet] [--verbose]
```

- Source flags mean what they mean on `decoy scan` (the same `resolve_sources`), with one difference (H3): on `init`, a CSV with neither header flag is read as having a header row, as `decoy init FILE` does today. `decoy scan` still requires the flag. If the scan then flags `scan_header_suspect`, init refuses (H1). This keeps `README.md:88`, `docs/cli-reference.md:519`, `docs/project-layout.md:41,61`, QA PROJ-05 and the e2e tests that call `decoy init FILE.csv` working.
- Mixed dialects use `--config` (C4), the S1c.2b sources file. `--column-names` is for one headerless CSV, as on scan.
- `--rows`: default 10,000 (`DEFAULT_SCAN_ROWS`, the same as scan and as today's init). `--rows 0` reads every row.
- `--detectors`, `--ner-model`: the shared `DETECTORS_OPTION` and `resolve_pre_scan`. They choose the detectors of the init scan only. The scaffold gets no `pre_scan` block (M8). The detectors that ran are named in the scaffold header comment and in `--json`.
- Output kind (C5a, DECOY-LANG S6 rules, unchanged): member default `.decoy`; `-o x.yaml` or `.yml` writes YAML; `-o x.decoy` writes Decoy; any other suffix exits 2; `-o -` writes Decoy unless `--yaml`; `--yaml -o x.decoy` exits 2. Until C5a merges, init writes YAML everywhere.
- Positional tokens: one bare token with no data suffix that is not an existing file is a pipeline NAME (preset path, unchanged). A NAME mixed with data files exits 2. `--source` (today's one-file option beside NAME) still names one source.
- `--yes`: overwrite an existing output. Without it, init checks for an existing output right after placement, before any source is read or model loaded, and exits 1 with `init.output_exists` (fixed text naming `--yes`). The write itself uses `CREATE_ONCE`, so a file created during the scan is still refused (L6). Placement only resolves paths; `prepare` (which makes a project member folder) runs at write time, so every refusal before the write leaves no folder behind. No question is asked on this path. The preset path keeps `_confirm_overwrite` (M6).
- `--json` (scaffold mode, C3): `{command: "init", status, out, mode: "scaffold-from-sources", sources: [str], table_count, column_count, suggestion_counts: {regex, classifier, fallback}, review_count, link_candidate_count, detectors: [{source, model_id, model_version}], **placed_members}`. `sources` replaces `source`; `mode` was `scaffold-from-file` (section 8).

`decoy scan` (C1, C2): no new flag. `--detectors` help and refusal text change (C1). Model hits appear (C2).

### 4.7 The `decoy scan` artifact (C2)

Recommendation, kept by the owner's "go with recommended": per-field evidence lines in the three existing surfaces, no new file format in V1.

- Card with `--show-fields`: one evidence line per hit under the field's row, regex first: `regex: email`, then `classifier lgbm-v1 0.1.0: email (band high)`, `ner en_core_web_sm 3.8.0: person_name (rate >=50%)`. Without `--show-fields`, the card adds one summary line `Model hits  3 fields (classifier 2, ner 1)` when a model ran.
- `--json`: `safe_field_record` keeps `model_hits` (the `ModelHitCore` dicts, already value-free) wherever field records are emitted. The top level gains `model_hit_count` (fields with at least one model hit). The `scan` snapshot entry has no `/fields` paths, so the per-field change moves no snapshot path; `model_hit_count` adds one.
- Saved scan (`--output`): unchanged. The core already holds `model_hits`, and `scan show` already prints them.

Stability constraint (owner 11-23): the saved scan is the artifact 1.x scan-to-scan diffs will read for flags and notifications. C2 changes nothing in the saved core. Any later change to `scan-set/v1` follows its versioned read model (catalog class 4): additive minors only, no renamed or retyped member. Section 13 lists what the 1.x diff row needs.

### 4.8 C3: the init rewrite (from row 29 S3a.1, trimmed)

Flow: `resolve_destination` (placement, unchanged) -> early output-exists check -> `resolve_sources` (CSV header default on) -> `scan_prepared_sources` -> `preflight` (models) -> `scan_descriptors(prepared, rows=..., strategy=..., pre_scan=...)` -> `starter_config(scan_set, targets=..., link_candidates=True)` (refuses a header-suspect table, E2) -> source path rewrite -> render -> `parse_pipeline_config` round trip -> one atomic `CREATE_ONCE` or `REPLACE` write.

- Header refusal (H1, R2-M2, R2-M3): the engine refuses (E2). Init maps the `starter_header_suspect` code to exit 1, code `init.header_suspect`, and fixed text: "A file looks like it has no header row. For one file, run again with --no-header and --column-names A,B,... (one name per column)." C4 adds a second sentence: "With several files, give each file's header rule in a sources file and pass --config." The text names no table, column or path. Until C4, a multi-file run with one headerless CSV has no route, because `--column-names` applies to one file only (section 12).
- Source paths (H2, R2-M1): every file source `path` in `StarterConfig.config` is replaced by `source_text(Path(shown[name]), destination)` (`C:src/decoy/cli/project/_scaffold.py:186`), where `shown` is the second value `resolve_sources` returns: the path as the user typed it. The resolved path in the descriptor is never passed, so `-o -` (which returns `source.as_posix()`) prints the path as typed. Cloud URIs are left as given.
- Targets (R2-H2, L7): one target per source, path `target_text(Path(shown[name]), format)` unchanged (`_scaffold.py:205-208`): the bare name `<stem>.masked.csv`, or `<stem>.masked.parquet` for Parquet. `run` places it in the pipeline's run folder, as today. TSV and fixed-width sources get a CSV target, as today.
- Comment lines (R2-M6): every comment the scaffold writes (header, `# REVIEW:` notes, keyed-column list, detector line, link comments) goes through one helper, `comment_text(template, **names)` in `_columns.py`. It renders each name with `json.dumps` and refuses any control character in a name or in a note from the engine, with exit 1, code `init.unsafe_name` and fixed text that names nothing. The `.decoy` path (C5a) passes its notes through the same helper. YAML values still go through `yaml.safe_dump`.
- Renderer (M5): `render_scaffold(config, notes, *, header) -> str` in `C:src/decoy/cli/project/_columns.py` (CODEMAP line 56: "the column YAML text of that scaffold"). It renders each block (top level, each source, each target, each table's columns one by one) with `yaml.safe_dump(..., sort_keys=False)`, and writes the `# REVIEW:` lines and header comments between blocks. No hand quoting. `_columns.py` keeps `yaml_quote`, `yaml_scalar` and `wrap_review_comment` for the preset path (`init.py:157,246-247,272`) and its exports in `project/__init__.py`; only `emit_column_yaml`, its export, the `Inference` import and `_NAMESPACE_REQUIRED_STRATEGIES` (`_columns.py:55-56`, used only by `emit_column_yaml` at `_columns.py:92`) go.
- Deleted: `C:src/decoy/cli/_init_inference.py`, `_NAMESPACE_REQUIRED_STRATEGIES`, `_load_dataframe`, `_scaffold_from_file`, `_build_scaffold_yaml`, `emit_column_yaml`, `C:tests/unit/test_init_inference.py`, and the `cli/init.py::_scaffold_from_file` entry in `C:tests/sentry/baselines/scan-call-allow.json` (L2). Before deleting the unit test, C3 checks each cell against the engine starter tests; a missing case (hostile names, header, date format) is added in E2.
- Keyed guidance: the scaffold header names the keyed columns from `keyed_columns_for_config(config)` (frozen, #407).
- Errors: scan-gate refusals pass through as raised (coded and value-free since S1c.2a). A starter refusal (`PipelineConfigError`) goes through the VALUE-FREE-ERRORS converter.

### 4.9 C5a and C5b: `.decoy` output (folds DECOY-LANG S6)

C5 builds the S6 mechanism as the S6 plan states it (`C:docs/plans/2026-11-19-decoy-language-commands.md`, "S6 mechanism"), with one change: the `review` input is `StarterConfig.notes`, not `_init_inference` notes.

- C5a: `convert_config(config, *, review: Mapping[tuple[str, str], str] | None = None) -> str`. A `(table, column)` in `review` prints with a trailing `?` and a `# REVIEW: <note>` line above it, through the printer's `Notes`. A `(table, "")` note prints above the table. `C:src/decoy/cli/lang/_scaffold.py:decoy_scaffold(config, review) -> str` is the one init entry to the converter (S6 placement; CODEMAP line 67). Output-kind rules from 4.6. The relationship template and link candidates print as comment lines: `link` has no review mark in the grammar (`C:src/decoy/lang/_grammar.py:92`), and an uncommented link would change masking.
- C5b: presets write `.decoy` through `decoy_scaffold(config, review={})`, `Template.decoy_body`, `show template --yaml`, as S6 lists.

### 4.10 Choke points

| Rule | One place | Guard test | Mutation |
|---|---|---|---|
| Regex required | engine `canonical_detectors` | AT-E1a to E1d; AT-E1e (no second "add regex" in the engine) | M-E1a, M-E1e |
| Scan call | `scan_descriptors` | G-ONE-SCAN-CALL, with the `init.py` allowlist entry removed (AT-C3b) | M-C3b |
| Per-column decision | engine `infer_starter_strategy` via `starter_config` | AT-C3c (no strategy-name table under `cli/`) | M-C3c |
| Init YAML scaffold text | `project/_columns.render_scaffold` | G-ONE-EMITTER (AT-C3d) | M-C3d |
| Scaffold comment lines | `project/_columns.comment_text` | AT-C3q | M-C3q |
| Header-suspect rule | engine `starter_config` | AT-E2h, AT-C3l | M-E2h, M-C3l |
| `.decoy` scaffold text | `decoy_scaffold` -> `convert_config` | AT-C5d | M-C5d |
| Field record for card and `--json` | `safe_field_record` | existing H5 test, extended (AT-C2a) | M-C2a |
| Atomic write and overwrite rule | `_atomic.write_local_target(..., CREATE_ONCE or REPLACE)` | AT-C3f, AT-C3g, AT-C3o | M-C3f, M-C3g, M-C3o |

AT-C3c shapes (H6). The sentry walks every module under `src/decoy/cli/` with `ast`. For each container literal (dict, tuple, list, set, `frozenset(...)` call) it collects catalog strategy names (`strategy_catalog()`) found as:

1. a string constant that is a dict key;
2. a string constant that is a dict value or a container item;
3. the constant of a `strategy=` keyword in any call inside the container (the `Inference(strategy="faker")` shape of `_INFERENCE_TABLE`);
4. the constant of a `strategy` key in a nested dict literal.

A container with two or more distinct names fails. A site is reported once, at its outermost matching container. Each shape has a seeded case that must fail. `cli/demo.py` is out of scope by path (the demo config is a fixed sample, as for G-ONE-EMITTER). The two remaining existing sites, `cli/completers.py::TRANSFORM_IDS` and `cli/explain.py::_STRATEGY_NOTES`, go in a shrink-only baseline `tests/sentry/baselines/strategy-literal-allow.json` (registered in `scripts/dev/sentry_registry.toml`, kind `json`), with their current name counts as ceilings. `ratchet_check` compares keys only, so the sentry itself fails when a baselined site holds more names than its ceiling (M-C3c2).

Hits counted on CLI `95362d16` and line numbers re-read on `fffca916` (AST script over `src/decoy/cli`, no pytest; nested containers collapsed to one site). The C3 builder recounts on its base and records the ceilings it writes:

| Site | Names | At C3 head |
|---|---|---|
| `_init_inference.py:76` | 6 | deleted |
| `completers.py:29` `TRANSFORM_IDS` | 13 | baseline, ceiling 13 |
| `explain.py:597` `_STRATEGY_NOTES` | 8 | baseline, ceiling 8 |
| `demo.py:96-105` demo column dicts | 3 | out of scope by path |
| `project/_columns.py:55-56` `_NAMESPACE_REQUIRED_STRATEGIES` | 7 | deleted |

C3 head must give no hit outside the baseline.

G-ONE-EMITTER shapes (M5). Scope: `src/decoy/cli/init.py` and `src/decoy/cli/project/`. Outside `project/_columns.py`, these fail: a call to `yaml.safe_dump`, `yaml.dump` or `decoy.lang.emit_yaml` (direct, aliased import, module-qualified, `from yaml import safe_dump as d`), and a string constant that holds `version: 2` or a line starting `tables:` (docstrings, the first statement of a module, class or function, are skipped). Named exemptions, out of scope by path: `cli/gen/_scaffold.py` (`init --preset generate` writes a generate config) and `cli/demo.py` (the demo config). Seeded cases per shape.

### 4.11 Placement

| File | Directory | CODEMAP line | Beside | Lines (est.) |
|---|---|---|---|---|
| E1 change and guard | `E:src/decoy_engine/config/_pre_scan.py`, `E:tests/sentry/` | engine config | `_post_scan.py` | +10 -6, guard +40 |
| E2 change, maybe new `_starter_models.py`; one reason code | `E:src/decoy_engine/profiling/`, `E:src/decoy_engine/reasons/` | engine profiling | `_starter_config.py` | +200 |
| E3 new `_starter_links.py` | `E:src/decoy_engine/profiling/` | engine profiling | `_starter_config.py` | +120 |
| C1 change, pin | `C:src/decoy/cli/scanning/_detectors.py`, `C:pyproject.toml` | line 53 | | +5 -8 |
| C2 change | `C:src/decoy/cli/scanning/_multi.py` and the card renderer | line 53 | | +90 |
| C3 change (no new module) | `C:src/decoy/cli/project/_columns.py`, `C:src/decoy/cli/init.py` (shrinks) | line 56 | `_scaffold.py` | +300 -520 |
| C3 new baseline | `C:tests/sentry/baselines/strategy-literal-allow.json` | line 73 | `scan-call-allow.json` | small |
| C4 change | `C:src/decoy/cli/init.py` | line 50 | | +60 |
| C5a new `_scaffold.py` | `C:src/decoy/cli/lang/` (created by DECOY-LANG S5 if it lands first, else by C5a) | line 67 | | +160 |
| C5a change | `C:src/decoy/lang/_convert.py` | line 67 | `_print.py` | +40 |
| C5b changes | `C:src/decoy/templates/__init__.py`, `C:src/decoy/cli/templates.py`, `C:src/decoy/cli/reference.py` | S6 list | | +120 |
| C6 change | `_columns.py`, `_convert.py` comment path | as above | | +100 |

No new module in the flat `src/decoy/cli/` folder (frozen at 30). `init.py` only shrinks (739 lines today).

### 4.12 Design notes

- Principles: one place per fact (one rule table, one regex rule, one renderer per format). No new abstraction: E2 extends an existing function, C3 removes a module and reuses `yaml.safe_dump`.
- The scaffold does not use `apply_review`. With no prompts, review is the user editing the file. The `?` mark and the gate's `lang.unreviewed` report hold the "not reviewed" state.
- A YAML scaffold runs without review (comments do not block); a `.decoy` scaffold does not. `.decoy` is the default (Q4).

## 5. Slices

| Slice | Repo | Content | Depends on | Risk | Size (src + tests) | Test depth |
|---|---|---|---|---|---|---|
| E1 | engine | regex normalization in `canonical_detectors`; `_effective_detectors` calls it; flip the hostile cells; AT-E1e guard; contract note, QA doc SCAN-07, CHANGELOG | none | R2 | ~55 + 140 | T1, T2 set, full suite (frozen refusal) |
| E2 | engine | model hits in `starter_config`; evidence notes; `live` redefined; header-suspect refusal and its reason code; cells ported from the CLI test | none (parallel with E1) | R2 | ~200 + 300 | T1, T2 set |
| E3 | engine | name-only `link_candidates` | E2 (same area) | R1 | ~120 + 150 | T1 |
| rel1 | engine | engine release 1 | E1, E2 | R1 | small | release set |
| rel2 | engine | engine release 2 | E3 | R1 | small | release set |
| C1 | CLI | re-pin to release 1 plus the detectors text in one PR: `_BAD_LIST` and help; e2e cells flip; `docs/cli-reference.md`; the re-pin checklist | rel1; rebase on #408 if open | R1 | ~15 + 60 plus pin files | T1, full suite (version pin) |
| C2 | CLI | model hits in card, `--show-fields`, `--json`; shape snapshot and CHANGELOG | none | R1 | ~90 + 160 | T1, shape test |
| C3 | CLI | init over `scan_descriptors` and `starter_config`; header default and the mapped header refusal; relative source paths, unchanged targets; `render_scaffold` and `comment_text`; deletions; early and atomic overwrite rule; `--json`; golden | C1 | R2 | ~300 + 320 (deletes ~520) | T1, T2 set, full suite (moved and deleted tests) |
| C4 | CLI | `--config` sources file on init; second sentence of the header refusal (owner call O1: default 1.1) | row 27 S1c.2b (not started); C3 | R1 | ~60 + 140 | T1 |
| C5a | CLI | `.decoy` output for scan scaffolds: `convert_config(review=)`, `decoy_scaffold`, output-kind rules, member default; `.decoy` golden | C3; DECOY-LANG S2, S3, S4 | R2 | ~200 + 260 | T1, T2 set |
| C5b | CLI | presets and templates write `.decoy` (rest of S6) | C5a | R1 | ~120 + 150 | T1 |
| C6 | CLI | re-pin to release 2; link candidates as a commented relationship plus key-entry comments, both formats | C3; rel2; C5a for the `.decoy` half | R1 | ~100 + 140 | T1 |

Every slice is under 600 changed lines. If C3 passes 600 while building, it splits into C3a (scan and starter wiring, header rules, renderer, deletion) and C3b (overwrite rule, atomic write, `--json`, golden).

## 6. Acceptance tests

Fixtures: `people.csv` (id, email, dob ISO, notes free text; 200 rows), `orders.csv` (order_id, customer_id, amount), `customers.parquet` (id, full_name, phone), a headerless PII CSV `raw.csv` (email, SSN-shaped and date values, no header), a CSV with hostile column names (`a: b # c`, `-x`, `"q"`), a marker CSV whose every cell is `MARKER-7f3a`, and a fixed-width file with a layout. Model e2e cells use the existing fake classifier and NER loaders (`C:tests/e2e/scan_models/`). E2 unit cells build `TableScan.model_hits` directly.

"Red on base" says whether the test fails on the slice's base. A "green" cell is a control or characterization cell; its named mutation must turn it red.

| Id | Slice | Test | Red on base | Mutation |
|---|---|---|---|---|
| AT-E1a | E1 | `PreScanConfig(detectors=["ner"]).detectors == ("regex", "ner")`; `["classifier"]` -> `("regex", "classifier")`; `[]` -> `("regex",)`; `["ner", "regex"]` -> `("regex", "ner")` | red | M-E1a |
| AT-E1b | E1 | `post_scan: {integrity: true, detectors: [ner]}` parses to `("regex", "ner")` | red | M-E1b |
| AT-E1c | E1 | repeats, an unknown source and `"regex\n"` still raise `detectors_invalid`; `ner_model` without ner still raises `pre_scan_ner_inactive` | green | M-E1c |
| AT-E1d | E1 | configs with `[ner]` and `[regex, ner]` dump the same `pre_scan` and give the same run-config hash | red | M-E1d |
| AT-E1e | E1 | guard: no engine module outside `config/_pre_scan.py` adds `"regex"` to a detector set (shapes and exclusions in 4.3, a seeded case each, plus a seeded `Literal["regex", "ner"]` that must not match); no hit on the E1 base | red (guard absent) | M-E1e |
| AT-E1f | E1 | `evaluate_pre_scan` with no `pre_scan` block, with `pre_scan: {detectors: []}` and with `[classifier]`: a field with `pii_candidate` true is flagged with source `regex` in each case; `verdict.detectors` equals today's sorted tuple for each input; `_effective_detectors` holds no `"regex"` literal | green for the first two cells, red for the literal check | M-E1f |
| AT-E2a | E2 | no regex hit, classifier hit `detector_id="email"`, band `high`: the entry equals `detector_entry("email", column)`; the suggestion has `source="classifier"`, `band="high"`, `live=False` | red | M-E2a |
| AT-E2b | E2 | classifier `review` band: the entry stays the fallback; the note names the hit | red | M-E2b |
| AT-E2c | E2 | confident regex `email` plus classifier `person_name`: regex entry kept; the note names both and says regex kept | red | M-E2c |
| AT-E2d | E2 | an NER hit (`NerRate.hit` true, bucket `>=50%`) on a free-text column with no confident regex decision: the entry stays the fallback; the note reads `ner <model> <version>: person_name (rate >=50%)` | red | M-E2d |
| AT-E2e | E2 | a classifier hit for a date detector without a complete format writes `redact`, not `date_shift` | red | M-E2e |
| AT-E2f | E2 | marker scan: no `MARKER-7f3a` in `config`, `notes` or any suggestion; `check_starter_config` passes | green | M-E2f |
| AT-E2h | E2 | a `ScanSet` whose table carries `scan_header_suspect` and whose profile names are marker values: `starter_config` raises `PipelineConfigError` with the `starter_header_suspect` code; no marker in the message, `str(exc)` or any problem field | red | M-E2h |
| AT-E2g | E2 | `live` is true for regex, key, integer-hash and fallback entries and false for a classifier-chosen entry; every suggestion's entry is in `config` | red | M-E2g |
| AT-E3a | E3 | `orders.customer_id` with `customers.id` gives one candidate with namespace `link-customers-id`; `customer.id` (singular) likewise; with no `id` column, none; `parent_id` inside `t` gives none; order stable | red | M-E3a |
| AT-C1a | C1 | `decoy scan people.csv --has-header --detectors classifier` exits 0 and the card says `Detectors regex; classifier lgbm-v1 0.1.0`; `--detectors ner` likewise | red on the pre-re-pin base (exit 1 today) | the re-pin itself |
| AT-C1b | C1 | repeat, unknown, empty name, model without ner and bad model name still exit 1 before any read | green | M-C1b |
| AT-C1c | C1 | the refusal prints the new `_BAD_LIST` text, and `decoy scan --help` shows the new `--detectors` help without "must include regex" | red | M-C1a |
| AT-C2a | C2 | `--show-fields --json` field records hold `model_hits` equal to the saved core's; the card shows one evidence line per hit with the real bucket label | red | M-C2a |
| AT-C2b | C2 | `--json` without `--show-fields` has `model_hit_count`; the card has the summary line only when a model ran | red | M-C2b |
| AT-C2c | C2 | marker CSV with classifier and NER: no marker in card, `--json`, `-v` stderr or saved core | green | M-C2c |
| AT-C2d | C2 | shape snapshot regenerated; `C:tests/unit/release/test_check_shape_changelog.py` passes with the CHANGELOG line; the saved core bytes for a fixed scan are unchanged after `scanned_at` and `engine_version` are normalized | red | snapshot test |
| AT-C3a | C3 | `decoy init people.csv orders.csv customers.parquet -o p.yaml` writes one pipeline with tables `people`, `orders`, `customers` and every column; `parse_pipeline_config` and `compile_plan` pass; afterwards the folder holds the inputs plus `p.yaml` only (no scan-core JSON, no `.decoy/` library record) | red | M-C3a, M-C3a2 |
| AT-C3b | C3 | G-ONE-SCAN-CALL with the `init.py` entry gone: a seeded `profile_columns` import or call in `init.py` fails it (direct, alias, module-qualified) | red | M-C3b |
| AT-C3c | C3 | the strategy-literal sentry (shapes 1 to 4 in 4.10, a seeded case each) passes at C3 head with only the two baseline sites; `_init_inference.py` is gone | red | M-C3c, M-C3c2 |
| AT-C3d | C3 | G-ONE-EMITTER (shapes and exemptions in 4.10) passes; seeded cases fail | red | M-C3d |
| AT-C3e | C3 | ISO `dob` gets `date_shift` with `date_format: "%Y-%m-%d"` and no `min_days` or `max_days`; a mixed-format date column gets `redact` | red (today writes min and max days) | M-C3e |
| AT-C3f | C3 | existing output, no `--yes`: exit 1, `init.output_exists`, bytes unchanged, stdin closed and never read, and no scan call made (spy on `scan_descriptors`) | red (today prompts) | M-C3f |
| AT-C3g | C3 | a write failure (read-only folder) leaves no temp file and no partial output; the written file is owner-only | red | M-C3g |
| AT-C3h | C3 | marker CSV: no marker in the scaffold, `--json`, `-v` stderr or any error text; relayed errors have `__cause__` and `__context__` None; hostile names round-trip through `parse_pipeline_config` | green | M-C3h |
| AT-C3i | C3 | `--detectors ner,classifier`: notes carry the model evidence, the header comment names the detectors, and the scaffold has no `pre_scan` key | red | M-C3i |
| AT-C3j | C3 | `--json` keys and types as in 4.6; `sources` lists the inputs in order | red | M-C3j |
| AT-C3k | C3 | `decoy init people.csv` with no header flag exits 0 and reads the first row as the header, as today | green | M-C3k |
| AT-C3l | C3 | `decoy init raw.csv` (headerless PII, no flag): exit 1, `init.header_suspect`, the fixed text, no file written, no project member folder created (also with a member destination), and no cell value in stdout, stderr, `--json` or `-o -`; `decoy init raw.csv --no-header --column-names email,ssn,dob` succeeds with those names | red (today writes cell values as names) | M-C3l |
| AT-C3m | C3 | `-o sub/p.yaml` writes source `../people.csv` and target `people.masked.csv`; `-o -` run from the data folder with `people.csv` typed writes source `people.csv`; neither holds an absolute path | green today; red under M-C3m | M-C3m, M-C3m2 |
| AT-C3n | C3 | golden: the three-source YAML scaffold equals `C:tests/fixtures/init_scaffold/three-sources.yaml` (paths relative, fake model loaders) | red | any byte change |
| AT-C3o | C3 | the output file is created after the early check and during the scan (hook on `scan_descriptors`): the write is refused by `CREATE_ONCE`, exit 1, the other file unchanged | red | M-C3o |
| AT-C3p | C3 | a fixed-width source and a TSV source each get the target `<stem>.masked.csv`; a Parquet source gets `<stem>.masked.parquet` (`target_text` unchanged) | green (today's rule) | M-C3p |
| AT-C3q | C3 | a CSV whose header holds a column name with a newline, and a file named with a newline: exit 1, `init.unsafe_name`, no file written, no name in any output; a hostile but printable name (`a: b # c`) appears in comments only as a JSON-quoted string and the scaffold parses | red | M-C3q |
| AT-C4a | C4 | `--config sources.yaml` with one TSV and one headerless CSV scaffolds both with their own dialects | red | M-C4a |
| AT-C4b | C4 | a two-file run with one headerless CSV and no `--config`: the refusal text has the `--config` sentence | red | M-C4b |
| AT-C5a | C5a | `decoy init a.csv b.csv -o p.decoy`: every mask line ends with `?` and has its note above it; `decoy validate p.decoy` reports `lang.unreviewed` per line; with every `?` removed it validates and runs | red | M-C5a |
| AT-C5b | C5a | the output-kind matrix of 4.6 (eight cells, exit 0 or 2) | red | M-C5b |
| AT-C5c | C5a | the member default writes `pipelines/<name>/pipeline.decoy`; `--yaml` writes `pipeline.yaml` | red | M-C5c |
| AT-C5d | C5a | the `.decoy` text equals `convert_config(config, review=notes)` of the same scan's config | red | M-C5d |
| AT-C5e | C5b | the S6 preset cells as written in the S6 plan ("S6 acceptance") | red | S6 mutations |
| AT-C5f | C5a | golden: the three-source `.decoy` scaffold equals `C:tests/fixtures/init_scaffold/three-sources.decoy`; it has no `scan before` | red | any byte change |
| AT-C6a | C6 | the `orders.customer_id` candidate prints, in YAML and `.decoy`, as a commented relationship under `relationships:` (`namespace: link-customers-id`, orphan policy left for the user) and one comment beside each of the `customers.id` and `orders.customer_id` entries; uncommenting the relationship, choosing an orphan policy and editing the two entries as the comments say gives a config that validates and compiles; with no candidate nothing prints | red | M-C6a, M-C6b |

## 7. Named mutations

| Id | Slice | Mutation | Must turn red |
|---|---|---|---|
| M-E1a | E1 | keep the refusal for a list without regex | AT-E1a |
| M-E1b | E1 | normalize in `PreScanConfig` only, not in the shared function `_post_scan.py` calls | AT-E1b |
| M-E1c | E1 | drop the repeat check while normalizing | AT-E1c |
| M-E1d | E1 | prepend regex without canonical ordering | AT-E1d |
| M-E1e | E1 | add `{*detectors, "regex"}` in `profiling/pre_scan/_check.py` | AT-E1e |
| M-E1f | E1 | make `_effective_detectors` return `tuple(policy.get("detectors") or ())` (read the field directly) | AT-E1f |
| M-E2a | E2 | ignore `model_hits`, or map `hit.detector_id` through `classifier_detector_id` again | AT-E2a |
| M-E2b | E2 | treat band `review` like `high` | AT-E2b |
| M-E2c | E2 | let a model hit replace a confident regex decision | AT-E2c |
| M-E2d | E2 | let an NER hit write `detector_entry` | AT-E2d |
| M-E2e | E2 | build a bare `date_shift` when `detector_entry` returns None | AT-E2e |
| M-E2f | E2 | put the hit's sample text in the note | AT-E2f |
| M-E2g | E2 | set `live=True` for a classifier entry | AT-E2g |
| M-E2h | E2 | skip the header-suspect check in `starter_config`, or put the table name in the message | AT-E2h |
| M-E3a | E3 | drop the "target has `id`" condition | AT-E3a |
| M-C1a | C1 | keep the old `_BAD_LIST` and help text | AT-C1c |
| M-C1b | C1 | map a parse refusal to exit 0 | AT-C1b |
| M-C2a | C2 | drop `model_hits` in `safe_field_record` (today's code) | AT-C2a |
| M-C2b | C2 | count hits, not fields, in `model_hit_count` | AT-C2b |
| M-C2c | C2 | render NER entity text in the evidence line | AT-C2c |
| M-C3a | C3 | keep the table name `data` | AT-C3a |
| M-C3a2 | C3 | also save the scan core next to the scaffold | AT-C3a |
| M-C3b | C3 | call `profile_columns` from `init.py` | AT-C3b |
| M-C3c | C3 | restore a dict whose values are `Inference(strategy="...")` calls in `init.py` | AT-C3c |
| M-C3c2 | C3 | add one strategy name to `TRANSFORM_IDS` (baseline ceiling) | AT-C3c |
| M-C3d | C3 | call `yaml.safe_dump` on the pipeline in `init.py` | AT-C3d |
| M-C3e | C3 | keep the `_init_inference` date rule | AT-C3e |
| M-C3f | C3 | call `_confirm_overwrite` from the scan scaffold path, or drop the early check | AT-C3f |
| M-C3g | C3 | write with `Path.write_text` | AT-C3g |
| M-C3h | C3 | include the exception text in the relayed error | AT-C3h |
| M-C3i | C3 | write `pre_scan.detectors` into the scaffold | AT-C3i |
| M-C3j | C3 | keep `source` (singular) in the envelope | AT-C3j |
| M-C3k | C3 | require a header flag on init | AT-C3k |
| M-C3l | C3 | map the engine's `starter_header_suspect` to the generic starter error | AT-C3l |
| M-C3m | C3 | skip the `source_text` rewrite | AT-C3m |
| M-C3m2 | C3 | pass the resolved descriptor path to `source_text`, or rewrite targets with `source_text` | AT-C3m |
| M-C3o | C3 | write with `REPLACE` when `--yes` is absent | AT-C3o |
| M-C3p | C3 | give a fixed-width or TSV source a target in its own format | AT-C3p |
| M-C3q | C3 | write a name into a comment without the helper | AT-C3q |
| M-C4a | C4 | apply the first source's dialect to all | AT-C4a |
| M-C4b | C4 | keep the C3 refusal text | AT-C4b |
| M-C5a | C5a | ignore `review` in `convert_config` | AT-C5a |
| M-C5b | C5a | accept `--yaml -o p.decoy` | AT-C5b |
| M-C5c | C5a | member default `.yaml` | AT-C5c |
| M-C5d | C5a | build `.decoy` text from the scan directly, not from config plus notes | AT-C5d |
| M-C6a | C6 | print the candidate uncommented | AT-C6a |
| M-C6b | C6 | leave out the comment beside a key entry, or print the key entries as a second `columns` block | AT-C6a |

## 8. Frozen contracts and byte changes

- E2: new config reason `starter_header_suspect`, registered with its manifest row; `starter_config` now refuses a header-suspect scan.
- E1: the engine refusal "detectors must include regex." goes away; lists without regex are accepted and normalized. A frozen refusal changes, so it gets a `compatibility-contract.md` note, a CHANGELOG line and the QA doc update (SCAN-07). `E:tests/unit/config/test_scan_ml_config_hostile.py:54` cells `["classifier"]`, `["ner"]` and `[]` move into AT-E1a.
- C1: the re-pin plus `_BAD_LIST` "--detectors takes classifier and ner, each once; regex always runs." and help without "must include regex". Cells `classifier_alone` and `ner_alone` (`C:tests/e2e/scan_models/test_scan_detectors.py:108-109`) move into AT-C1a. `docs/cli-reference.md` updated. The #381 flag test checks flag names only, so no freeze fixture moves.
- C2: `scan --json` gains `/model_hit_count` (integer). Field records gain `model_hits` where fields are emitted. `json-shapes.json` regenerated; CHANGELOG line, checked by `C:tests/unit/release/test_check_shape_changelog.py`. The saved scan core does not change (owner stability constraint, 4.7).
- C3, scaffold bytes of `decoy init FILE`:
  - the table is named after the file (was `data`);
  - entries come from the engine starter (no `min_days`/`max_days` on `date_shift`);
  - note wording is the engine's; in particular the CLI-only `_DATE_REDACT` note ("date format not detected") becomes the engine's generic redact note;
  - source paths stay relative to the scaffold file, built from the path as typed, and targets stay the bare `target_text` name (named so the switch to `resolve_sources`, which resolves to absolute paths, cannot change them);
  - comment lines render names as JSON strings, and a name with a control character is refused (`init.unsafe_name`);
  - YAML text comes from `yaml.safe_dump`, so quoting and key order may differ from the hand-written text;
  - no `pre_scan` block is written, with or without `--detectors` (M8). Today's init writes none either; this pins it.
  - Pinned by the golden `C:tests/fixtures/init_scaffold/three-sources.yaml`.
- C3, behavior: `decoy init FILE.csv` with no header flag still works (H3). A file that looks headerless now exits 1 (`init.header_suspect`) where today it writes a scaffold whose column names are cell values. The scan path asks no overwrite question (exit 1 without `--yes`); the preset path is unchanged. Scaffold-mode `--json` changes `mode` and replaces `source` with `sources`. The frozen `init` snapshot entry is the `--preset` document and does not change. Cells in `C:tests/e2e/test_init_command.py` and `C:tests/e2e/test_init_scaffold_roundtrip.py` that pin `data` or the CLI notes are updated as named characterization changes; the other e2e tests that call init on a CSV keep passing because the header default is kept.
- C5a: the member default becomes `pipeline.decoy` (owner call O4). Pinned by `C:tests/fixtures/init_scaffold/three-sources.decoy`.
- Experimental tier: this row calls no experimental-tier name and promotes nothing. `starter_config`, `ColumnSuggestion` and `detector_entry` are public names of `decoy_engine.profiling` (`E:docs/compatibility-contract.md:272`); E2 changes the documented meaning of `ColumnSuggestion.live` and says so in the contract note. `strategy_catalog` and `keyed_columns_for_config` are frozen top-level names (`E:docs/frozen-surfaces.md:103,107`). `column_entry`, `apply_review` and `finding_edits` are not used.

## 9. Class tables

### 9.1 Recurring-defect catalog

| # | Class | Where it applies | How the plan closes it |
|---|---|---|---|
| 1 | Anchored validation | `--detectors` names, output suffix | parsing stays in the engine model and the existing suffix table; AT-E1c has a `"regex\n"` cell |
| 2 | Strict types | `--json` envelope, `model_hit_count` | integers from `len()`; no stored data is read back |
| 3 | No exception context | relayed starter and write errors | raise after the `except` closes; AT-C3h checks `__cause__` and `__context__` |
| 4 | Versioned read models | `scan-set/v1` read by `starter_config` and later by 1.x diffs | reader unchanged; E2 reads existing fields; E3 level A adds no core field; C2 leaves the core bytes unchanged (AT-C2d) |
| 5 | Normalized guard scanners | AT-E1e, C3b, C3c, C3d | the shared call scanner `C:tests/sentry/io_policy/_calls.py`; shapes listed in 4.3 and 4.10; a seeded case per shape |
| 6 | No private imports | `decoy.lang` from `cli/lang/_scaffold.py`; engine names | `convert_config` is in `decoy.lang.__all__`; engine names from public packages |
| 7 | No hidden CI failures | none new | n/a |
| 8 | One trust class per entry | file names become table names | `table_name_from_path` unchanged; a collision is refused |
| 9 | Mutations on the final head | all slices | the builder records the head per mutation |
| 10 | Allowlisted helpers checked | G-ONE-SCAN-CALL | C3 removes the `cli/init.py::_scaffold_from_file` allowlist entry; `init.py` is then checked like any caller |
| 11 | No raised caps | `init.py` shrinks; `_starter_config.py` grows; the new strategy-literal baseline | E2 splits at 650 lines; the new baseline starts at today's counts and may only shrink; the scan-call allowlist shrinks |

### 9.2 Plan contract catalog (vault `Decoy-Plan-Contract-and-Defect-Catalog.md`, 10 classes)

| # | Class | Closing structure | Sentry or property test | Mutation |
|---|---|---|---|---|
| 1 | Value-bearing output | the starter names columns from the in-memory profile, so `starter_config` itself refuses a `scan_header_suspect` table with a value-free coded error (E2); everything else comes from the value-free core, detector descriptors and fixed text; relayed errors go through VALUE-FREE-ERRORS | AT-E2h, AT-C3l, AT-E2f, AT-C2c, AT-C3h, AT-C3q with seeded markers | M-E2h, M-C3l, M-E2f, M-C2c, M-C3h, M-C3q |
| 2 | Cleanup missing on an exit path | nothing is written before one atomic write; `_atomic` removes its temp file on failure; every exit in 10.1 writes nothing else | AT-C3f, AT-C3g, AT-C3l | M-C3f, M-C3g |
| 3 | State machine and concurrency | N/A: one linear flow, no shared state, no prompt loop in the scan path | AT-C3f (no stdin read) | N/A: no state added |
| 4 | Route parity and silent fallback | one scan call for all four routes (10.2); one detector resolver for scan and init; a model that cannot load refuses before any read, never falls back to regex only | AT-C1a, AT-C3b; the existing `preflight` cells | M-C3b |
| 5 | Referential integrity | declared relationship keys keep the shared-namespace rule (unchanged); a candidate is a commented relationship plus a comment beside each key entry, all naming one namespace | AT-C6a, AT-E3a | M-C6a, M-C6b |
| 6 | Untrusted producer | N/A: no child process or extension added; models load through `load_detector_set` | existing `preflight` cells | N/A |
| 7 | Check then use on a path (TOCTOU) | the early output check is UX only; `write_local_target(..., CREATE_ONCE)` is the authority | AT-C3o | M-C3o |
| 8 | Weak tests and overclaimed evidence | each AT records red on its named base; green cells name the mutation that turns them red; AT-E2d uses an input production makes (`NerRate.hit` true) | builder report with base SHA and red output | each mutation names its AT |
| 9 | Behavior-preserving refactor drift | the init rewrite is not behavior-preserving; every byte change is named in section 8 and pinned by the goldens; the header default and relative paths are kept on purpose | AT-C3k, AT-C3m, AT-C3n | M-C3k, M-C3m |
| 10 | Frozen contract drift | section 8 names each change: E1 refusal, C1 text, C2 `/model_hit_count`, C3 envelope, C5a default, `live` meaning | `json-shapes.json`, `test_check_shape_changelog.py`, #381 flag test, AT-E1a, AT-C1c, AT-E2g | M-E1a, M-C1a, M-C2b, M-E2g |

## 10. Enumerations

### 10.1 Exit paths (init, scan path)

| Path | Exit | Writes |
|---|---|---|
| success to a file | 0 | one atomic file |
| success to stdout | 0 | nothing on disk |
| bad flags, NAME mixed with files, output-kind mismatch | 2 | nothing |
| output exists without `--yes` (early check) | 1 | nothing; no source read |
| scan-gate refusal (missing file, bad dialect, name collision) | 1 | nothing |
| a model cannot load (`preflight`) | 1 | nothing |
| header suspect (engine refusal, mapped) | 1 | nothing; no column name printed; no member folder |
| control character in a name | 1 | nothing; no name printed |
| starter refusal | 1 | nothing |
| output created during the scan (`CREATE_ONCE`) | 1 | nothing; the other file unchanged |
| write failure | 1 | temp file removed |

### 10.2 Routes into the scan

All routes call `scan_descriptors` (`C:src/decoy/cli/_sources.py:176` prepares the sources):

- `decoy scan` (through S1c.2a);
- `decoy demo` (through S1c.2a);
- `decoy.scan()` in Python (through S1c.2a);
- `decoy init SOURCES...` (through C3; today it calls `profile_columns` from `C:src/decoy/cli/init.py:328`).

### 10.3 Detector inputs

Absent, `regex`, `classifier`, `ner`, `regex,ner`, `ner,classifier`, `classifier,ner,regex`, `ner,ner`, `bogus`, an empty name; `--ner-model` with and without ner. AT-E1a to E1c and AT-C1a, C1b cover them.

### 10.4 Source kinds and their targets

| Source | Header rule on init | Target |
|---|---|---|
| CSV, no flag | header row (H3); refused if suspect (H1) | CSV `<stem>.masked.csv` |
| CSV `--has-header`, or `--no-header` with `--column-names` (one file only) | as given | CSV `<stem>.masked.csv` |
| TSV | as CSV | CSV `<stem>.masked.csv` (`target_text`, as today) |
| Parquet | n/a | Parquet `<stem>.masked.parquet` |
| fixed width with `--layout` | n/a | CSV `<stem>.masked.csv` (`target_text`, as today) |
| mixed through `--config` (C4) | per source | per source as above |
| cloud URI | as `resolve_sources` | bare `target_text` name, same rules; the starter's cloud note applies |

### 10.5 FK shapes (E3 and C6)

The rule (`E:src/decoy_engine/walks/inference.py:33`) matches only a column named `<table>_id` where `<table>` (singular or plural) is a scanned table with an `id` column. Shapes:

- plural target: `customer_id` -> `customers.id` (one candidate);
- singular target: `customer_id` -> `customer.id` (one candidate);
- target with no `id` column: none;
- `parent_id` with no `parent` table: none (self references are not matched);
- composite keys: none at level A.

AT-E3a covers the first four shapes; E3's unit tests cover composite keys. AT-C6a covers how a candidate prints.

### 10.7 Fields

Fields the row adds or changes, all value-free:

- `ColumnSuggestion.live`: meaning redefined (E2; `E:src/decoy_engine/profiling/_starter_config.py:89-118`);
- `StarterConfig.link_candidates` and `LinkCandidate` (E3; new);
- scan `--json` `/model_hit_count` and per-field `model_hits` (C2; `C:src/decoy/cli/scanning/_multi.py:78-92`);
- init `--json` `mode`, `sources`, `suggestion_counts`, `review_count`, `link_candidate_count`, `detectors` (C3; `source` removed);
- `starter_header_suspect` config reason (E2; new);
- saved scan core: no change (`E:src/decoy_engine/profiling/scan_set.py:126` already holds `model_hits`).

### 10.6 Output surfaces

| Surface | Model hits | Values |
|---|---|---|
| scan card | summary line; evidence lines with `--show-fields` | none |
| scan `--json` | `model_hit_count`; `model_hits` per field record | none |
| saved scan | unchanged (already present) | none |
| init YAML | `# REVIEW:` evidence lines; detectors in the header comment | none |
| init `.decoy` | note comment and `?` | none |
| init `--json` | `suggestion_counts`, `detectors` | none |
| `-v` stderr | the existing `pre_scan.detectors` record | none |

## 11. Reuse inventory

| Need | Reuse | Where |
|---|---|---|
| Scan call | `scan_descriptors`, `scan_prepared_sources` (row 27 S1c.2a) | `C:src/decoy/cli/scanning/_engine_call.py`, `C:src/decoy/cli/_sources.py:176` |
| Sources and dialects | `resolve_sources`, `table_name_from_path`; S1c.2b `--config` | `C:src/decoy/cli/scanning/_multi.py` |
| Detectors | `DETECTORS_OPTION`, `resolve_pre_scan`, `preflight`, `detectors_line` | `C:src/decoy/cli/scanning/_detectors.py` |
| Per-column suggestion | `starter_config`, `infer_starter_strategy`, `detector_entry`, `check_starter_config` | engine `profiling` |
| Detected date format (#728) | `format_pattern_complete` through the starter | engine |
| Strategy names for the AT-C3c sentry (#400) | `strategy_catalog()` | engine top level, frozen |
| Keyed columns (#407) | `keyed_columns_for_config` | engine top level, frozen |
| Relative paths | `source_text(source, destination)` | `C:src/decoy/cli/project/_scaffold.py:186` |
| YAML text | `yaml.safe_dump` per block | as `C:src/decoy/cli/gen/_scaffold.py:127` |
| Converter and review mark | `convert_config` (+ `review`, C5a), `REVIEW_MARK`, `lang.unreviewed` | `C:src/decoy/lang/` |
| Atomic write | `_atomic.write_local_target` | `C:src/decoy/_atomic.py` |
| Placement | `resolve_destination`, `prepare` | `C:src/decoy/cli/project/` |
| FK name rule (E3) | `walks.inference.infer_edges` | `E:src/decoy_engine/walks/inference.py:33` |

The wizard's merged engine pieces:

- #400 `strategy_catalog`: reused, as the name set for the AT-C3c sentry.
- #407 `keyed_columns_for_config`: reused, for the keyed-column list in the scaffold header.
- #653 `column_entry`, `apply_review`, `ReviewVerdict`, `SuggestionRef`: not used. They apply prompt answers, and a non-interactive scaffold has none. They are not in `decoy_engine.validation.__all__` (only `validate_config`), not top-level, and not in `EXPERIMENTAL_OBJECTS`. This row does not promote them. `build_entry` and `detector_entry`, also from #653, are used through `starter_config` and E2.
- #654 `finding_edits`: not used. Init has no findings step.
- #728 detected date format: reused through `starter_config` (AT-C3e).

Kept from the stopped wizard plans: the value-free relay through VALUE-FREE-ERRORS; the no-strategy-literal sentry idea (Phase 1a AT-W6), extended with the keyword and dict-value shapes; "a classifier suggestion is never live" (Phase 1a AT-E2); "`init.py` may only shrink" (Phase 1a AT-W28). Dropped: everything about prompts, the Prompter, steps, stale marking and review keys.

## 12. Pre-mortem

- E1 changes what `evaluate_pre_scan` sees for a config with no `pre_scan` block. AT-E1f pins that regex still counts there. E1 runs the full suite.
- CLI #408 and C1 both move the engine pin. Whichever merges second rebases; C1 runs the full suite (version pin).
- Stale CLI #68 edits `_init_inference.py`, which C3 deletes. #68 rebases after C3; C3 does not wait for it.
- The fake model loaders give no `high` band for the email fixture (Dennis did not check). E2 builds `model_hits` directly in unit tests. C2 and C3 e2e cells check the loader output first; if the email fixture is not `high`, the cell uses the fixture the loaders do flag.
- The header-suspect heuristic refuses a real file with a numeric-looking header. `--has-header` does not override it; the user passes `--no-header --column-names ...` or fixes the file. Rare, and the refusal is safe.
- Between C3 and C4 (and for all of V1 if O1 keeps the default), a multi-file run with one headerless CSV has no route: `--column-names` applies to one file only. The user inits that file on its own. C4 closes this with `--config`. `decoy scan` on the files shows which one carries the warning.
- Users run a `.decoy` scaffold and hit `lang.unreviewed`. The scaffold header says "remove each `?` after you check the line", and the gate message names the line.
- `_starter_config.py` passes 800 lines. E2 starts in `_starter_models.py` if the build passes 650.

## 13. Follow-ups

- Row 29 (1.1) reuses `render_scaffold`.
- DECOY-LANG S6 closes with C5b. DECOY-LANG S8 keeps its `decoy convert` half open (the roadmap row text changes when C5a merges).
- Level B foreign-key candidates (containment checked) as a 1.x row.
- A `decoy scan --format md` report as a 1.x row.
- Input for the 1.x scan-diff notifications row (addendum A1):
  - `scan_diff` does not read `model_hits` today, so model-hit diffs need a `scan-diff/v1` minor;
  - key model hits on `(source, detector_id)` and report a model version change as its own change kind;
  - a header-flag change renames every field (to `c0..`), so a diff shows every field removed and re-added; the diff should detect a full rename and say so.

## 14. Owner questions

The owner's "go with recommended" rule applies to Q1, Q3, Q4 and Q5. The coordinator applied the owner's answers on 2026-11-23.

- Q1. Regex-always-on is owned by the engine (`canonical_detectors`). Decided.
- Q2. Foreign-key suggestions in V1: level A, name-only candidates as comments carrying the full relationship and key entries (E3 plus C6). Decided.
- Q3. The `decoy scan` artifact: per-field evidence in the card, `--json` and the saved scan; no Markdown report in V1. Decided.
- Q4. A YAML scaffold does not block until reviewed; `.decoy` does. Decided.
- Q5. A classifier `high` hit changes the entry when regex has no confident decision; NER hits add evidence only (H5). Decided.

One open owner call, new in revision 4:

- O1 (OWNER CALL). `decoy init --config SOURCES.yaml` (C4) needs the scan sources file from row 27 S1c.2b, which has no 1.0 row and no PR. Default: C4 and S1c.2b go to 1.1. In V1, init takes positional sources with the header default, `--has-header`, or `--no-header --column-names` for one file; a mixed run with one headerless CSV is refused with a fixed hint, and the user scaffolds that file alone. The alternative is to add S1c.2b and C4 to 1.0 (about 600 lines over two slices).
