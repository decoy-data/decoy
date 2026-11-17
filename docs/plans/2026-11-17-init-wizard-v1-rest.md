# Init wizard: the rest of V1 (row 32b after Phase 1a)

Status: plan

Date: 2026-11-17. Author: Opus planner. Risk: R2 overall (privacy of scan output, persisted
answer and draft formats, edits to user-owned YAML, the frozen `decoy-ci/v1` contract). Each
slice carries its own tier in section 11.

Bases: CLI `origin/main` `c558e2fb` (#310), engine `origin/main` `11ceb73f5` (#635, version
0.27.0). The CLI pins `decoy-engine==0.27.0`.

Rules consulted: `/home/cam/dev-rules/00-universal.md`, `development-loop.md`,
`risk-and-exceptions.md`, `proportionality.md`, `catalogs/recurring-defects.md` (classes 1 to
11); the plan contract and defect catalog
(`obsidian-vault/30_Resources/Decoy-Plan-Contract-and-Defect-Catalog.md`); CODEMAP "Where Things
Go"; standing memory rules (V1 bar, pre-release no locking, develop correctly with one registry
per concern, files about 800 lines, sentry over prose, no raised caps).

Inputs: the Phase 1a plan `docs/plans/2026-11-08-init-wizard-phase-1a.md` (sections 1.2 and
1.3), the record plan `docs/plans/2026-11-07-init-wizard.md` (sections 4.4 to 4.7, W2, W3, E2),
the spec `docs/plans/2026-10-30-init-wizard-spec.md`, and roadmap section 5.

## 0. Why this plan exists

Owner decision 2026-11-17: "a working wizard to configure a job is v1." `decoy init` must be able
to configure any V1 job. That covers every V1 source and target kind, subset, pre-scan with
detectors, mask or generate per table, relationships, post-scan checks, delivery, the vault and
Tokenize goal, and the CI manifest.

V1 scope of row 32b is now:

- Phase 1a (planned, 11 slices, blocked on SCAN-MULTI S3a.1).
- Phase 1b, Phase 2, W2, E2, W3.1 and W3.2 (this plan).
- From Phase 3, only the Tokenize goal and the CI manifest (this plan).
- V2: arrow keys and `prompt_toolkit` completion, before and after previews (owner question Q6).

This plan does not re-plan Phase 1a. Section 3 lists the changes the 1a builders must apply
because CLI main moved since the 1a plan was written.

## 1. Coverage table

Every V1 config surface, read from `PipelineConfig` on engine `11ceb73f5` and from the CLI run
flags, mapped to the step and slice that configures it. "Hand" means the wizard leaves it for a
hand edit, with the reason. "Row" means a V1 roadmap row that has not built the surface yet and
must ship its own wizard entry (section 6, rule C1).

### 1.1 Sources and targets

| Surface | Where it is defined | Configured by | Slice |
|---|---|---|---|
| File source, CSV or delimited, header row or header file or typed names | `FileSource` (`format`, `delimiter`, `has_header`, `column_names`, `column_names_file`) | Sources step | 1a W1a.4a |
| File source, Parquet | `FileSource` | Sources step | 1a W1a.4a |
| File source, fixed width (`layout`, ruler) | `FileSource.layout` | Sources step, fixed-width sub-flow | **B1** |
| S3 source, GCS source | `S3Source`, `GCSSource` | Sources step, location kinds | **B2** |
| DuckDB table (`decoy run --duckdb-source TABLE=DB_PATH`) | CLI run flag, `src/decoy/cli/_duckdb_source.py`; not a config kind | Sources step, DuckDB sub-flow; the flag goes into the printed run command | **B3** (gap) |
| Postgres source | row 64b CLI-DB-SRC, not started | Row 64b adds a location kind | Row 64b |
| File target, CSV or Parquet | `FileTarget` | Output step | 1a W1a.5a |
| File target, fixed width | `FileTarget` | Output step | **B1** |
| S3 target, GCS target | `S3Target`, `GCSTarget`; offline root check `cli/io/_cloud.py` | Output step, location kinds | **B2** |
| Postgres target | row 86 F01, not started | Row 86 adds a location kind | Row 86 |
| SFTP target | row 87 F02, plan written | Row 87 adds a location kind | Row 87 |
| `delivery.mode` (`strict`, `best_effort`) | `DeliveryConfig` | Output step | **B2** (gap) |

### 1.2 Goal and per-table work

| Surface | Configured by | Slice |
|---|---|---|
| Goal Mask | Goal step | 1a W1a.4a |
| Goal Generate, Subset, Tokenize (multi-select) | Goal step | **P1a** (Tokenize leaf turned on by **T1**) |
| `tables.<t>.columns` (strategy, options, namespace) | Fields step, every-field mode | 1a W1a.3b |
| Flagged-only review mode with the leak guard | Fields step | **B4** (needs **EG3**) |
| `transforms: drop_column` | Fields step `d` key | 1a W1a.3b |
| Other transforms (filter, sort, limit, dedupe, derive) | Hand: spec 7 list | none |
| `tables.<t>.generate_columns` (14 types) | Generate step | **P1b** (needs **EG1**) |
| Generated table fitted from a snapshot | Generate step, reuses `decoy.cli.gen.scaffold_generate` | **P1a** |
| `tables.<t>.row_count` | Generate step | **P1b** |
| `tables.<t>.unique_together` | Hand: generation constraint, not in spec 5.4.4 | none |
| Column `vault: true` | Tokenize branch of the Fields step | **T1** (needs **EG4**) |
| `tokenize` strategy | Strategy tree, shown only when Tokenize is in the goal | **T1** |

### 1.3 Scan, relationships, subset, checks

| Surface | Configured by | Slice |
|---|---|---|
| `pre_scan.detectors`, `pre_scan.ner_model` | Detectors section of Scan | **W2** |
| `post_scan.detectors`, `post_scan.ner_model`, `post_scan.ner_findings` | Detectors section of Checks | **W2** |
| `post_scan.integrity` | Checks step | **B5** |
| `post_scan.dismissed` | Findings review (`--review-findings`) | **W3.2** (needs **E2**) |
| `relationships[]` (parent, children, composite keys, `orphan_policy`, `namespace`) | Relationships step | **P2** |
| top-level `namespaces` block | Hand: spec 7 list; relationships bind one shared namespace through E1 | none |
| `subset.seeds` mode `filter` and `sample` | Subset step | **P3** |
| `subset.seeds` mode `keys`, `budget`, `edge_directions`, `allow_dangling` | Hand: spec 5.6 offers filter and sample only | none |
| `validators[]` | Checks step, list from an engine catalog | **B5** (needs **EG2**) |
| `quarantine` (with the H1 warning and the `.gitignore` offer) | Checks step | **B5** |
| `protected_quarantine` | Hand: spec 7 list | none |
| `scan_baseline` (`path`, `on_drift`) | Row 32 DRIFT, not started | Row 32 (owner question Q10) |

### 1.4 Global settings, secrets, CI

| Surface | Configured by | Slice |
|---|---|---|
| `version`, `name` | Start step and project layout | 1a W1a.6a |
| `global_settings.seed`, `global_settings.mask_secret_ref` | Secrets step | 1a W1a.5a |
| `global_settings.post_validation`, `global_settings.thresholds` | Quality step | **B6** |
| `--fidelity` run flag | Quality step adds it to the printed run command | **B6** |
| `on_pool_exhaustion`, `reference_date`, `unconfigured_column_policy`, freetext thresholds | Hand: spec 7 list | none |
| `global_settings.dp` | Hand: DP is gated behind a V2 certificate (decisions 2026-11-08) | none |
| Vault path for a Tokenize run (`--vault PATH`) and the cryptography extra | Secrets step, Tokenize branch | **T1** |
| `policy` block | Row 81 F16 (models merged, not in `PipelineConfig` yet) | Row 81 |
| Quality contracts, invariants | Rows 69 F35, 68 F36 (plan GO, not built) | Rows 69, 68 |
| CI manifest `.decoy-ci.yaml` (`decoy-ci/v1`): new file | Review step, CI offer | **C1**, **C2** |
| CI manifest: add a pipeline to an existing file | Review step, CI offer, through the editor | **C2** (needs W3.1) |
| CI manifest `staged_scan` patterns | Hand: the literals are raw secret-like data and must not pass through prompts | none |

### 1.5 Commands and flags

| Surface | Slice |
|---|---|
| `--answers`, `--save-answers`, `--fail-on-warning` | **P4** |
| `--skip`, `--only`, `--no-validate`, `--diff` | **P5** |
| `decoy edit <section> <pipeline>` | **P7** (needs W3.1) |
| Drafts, `q` to save and quit, `--resume` | **B7** |
| Preset pre-fill of the steps | **B8** |

### 1.6 Gaps found

Each gap became a slice or a rule:

1. DuckDB tables have no wizard path. Slice **B3**.
2. `delivery.mode` has no step. Folded into **B2**.
3. The generate catalog has names and required options but no wire types or examples. Engine
   slice **EG1**.
4. No public validator list (spec 16.8; `_REGISTRY` in `validators/_registry.py:63` is private).
   Engine slice **EG2**.
5. No per-column free-text check (spec 16.14; only config-level readers in
   `quality/_freetext_advisory.py:99,113`). Engine slice **EG3**.
6. No catalog fact says which strategies may carry `vault: true`. The rule is a private predicate
   in `check_vault_columns` (`plan/_checks_correctness.py:154`). Engine slice **EG4**.
7. No CI manifest writer exists (only the loader `ci/manifest.py`). Slices **C1** and **C2**.
8. Rows 64b, 86, 87, 81, 68, 69 and 32 will add config surface after the wizard ships. Nothing
   today makes them add a wizard entry. Slice **V0** (the coverage sentry) closes this by
   construction.

## 2. Guarantees and non-goals

### 2.1 Properties that must always hold

- G1. Every field path and every kind literal in `PipelineConfig` has exactly one entry in the
  coverage registry: a step id that exists in `STEPS`, a hand-edit reason, or an owning roadmap
  row. (V0)
- G2. No input data value, secret value, credential, bucket name, DSN or exception text reaches
  any wizard surface except the allow-listed ones (spec 15 privacy test, extended to every new
  step and file).
- G3. Every file the wizard writes or edits has one owner object and one exit-path matrix. A
  failed write leaves the earlier file byte for byte unchanged.
- G4. A YAML file the wizard edits changes only inside the blocks the user changed. Every other
  byte stays the same, comments included (G-ONE-EDITOR).
- G5. Every new YAML file the wizard writes comes from the one emitter `cli/_scaffold_yaml.render`
  (G-ONE-EMITTER). The CI manifest is written by C1's renderer and read back through
  `ci/manifest.py` before it is written.
- G6. Menus come from engine registries: strategies, generate types, validators, detectors and
  vault eligibility. The CLI keeps no hand list of any of them.
- G7. Answers and drafts are versioned, strict and created owner-only. Reading an unknown major,
  a missing tag or a lax-typed value is refused with a registered `init.*` code.
- G8. The wizard uses only the six public exit codes.

### 2.2 Non-goals

- Arrow keys, `prompt_toolkit`, before and after previews (V2).
- New config kinds. DuckDB stays a run flag (owner question Q5).
- Postgres and SFTP prompts. Their rows own them (rule C1).
- Hostile in-process evasion of the sentries (V2-LOG, threat model 2026-11).

## 3. Changes the Phase 1a builders must apply (rebase delta)

The 1a plan was written on CLI `08124b5` and engine 0.19.0. These facts changed. They are
amendments to the 1a slices, not new slices.

| # | Fact on main now | 1a slice it changes | Amendment |
|---|---|---|---|
| D1 | `cli/init.py` is 742 lines (1a assumed about 690) and has PROJECT-LAYOUT: a `NAME` or `FILE` token, `--source`, default `pipelines/NAME/pipeline.yaml`, `-o` outside a project | W1a.0, W1a.6a, W1a.6b | AT-W1 characterization adds the NAME, `--source`, in-project and outside-project cases. The module-size pin for `init.py` starts at its size on the W1a.0 base and only shrinks. The Start step takes the pipeline path from `decoy.cli.project` (`resolve_destination`), never builds it |
| D2 | Outputs default to a bare target `<stem>.masked.<ext>` placed in a run folder (`cli/io/_layout.py`) | W1a.5a | The Output default is the project scaffold's target (`decoy.cli.project`), not `out/<table>.masked.<ext>`. AT-W25 changes its expected default |
| D3 | `--preset generate` with a FILE fits a snapshot through `decoy.cli.gen.scaffold_generate` | W1a.1 | The preset path keeps that behavior through the Prompter. P1a reuses the same function for the Generate goal |
| D4 | P3, P4, P5 (CONFIG-EXPLICIT) are merged; the CLI pins engine 0.27.0 | section 2 | Mark P3 to P5 met. R-1a is the next engine release after E1 |
| D5 | The post-scan report is `post-scan-integrity/v3` (`tables_checked`, `config_sha256`, `promoted`, dismissals applied) | none in 1a | W3.2 reads v3 and still reads v2 (section 7.6) |
| D6 | Private owner-only file creation has one home, `src/decoy/_private_file.py` | none in 1a | B7 and P4 create drafts and answers through it. The record plan's `mode` argument on `_atomic.write_local_target` is dropped |
| D7 | `src/decoy/cli/io/` holds the layout services and the cloud root check | W1a.6a | The path-role check calls `decoy.cli.io` for placement and the one collision rule |

## 4. Reuse inventory

| Need | Reuse | Where |
|---|---|---|
| Step loop, state, stale marking, Prompter, tree, field review, write step | Phase 1a modules | `src/decoy/cli/wizard/` (after W1a.6b) |
| Reason codes | central registry from W1a.0 | `src/decoy/_reason_codes.py` |
| Owner-only files | `_private_file` | `src/decoy/_private_file.py` |
| Atomic replace | `_atomic.write_local_target` | `src/decoy/_atomic.py:199` |
| YAML marks | index in `ci/locations.py`, moved by Y0 | `src/decoy/_yaml_marks.py` (target) |
| Cloud root rules | `cloud_root_issues` | `src/decoy/cli/io/_cloud.py` |
| Snapshot fit for Generate | `scaffold_generate`, `fit_exact_snapshot` | `src/decoy/cli/gen/` |
| DuckDB staging | `acquire_relation`, `describe_relation` | `src/decoy/cli/_duckdb_source.py` |
| Starter suggestions and relationship template | `starter_config` (`suggestions`, `relationship_template`) | engine `profiling/_starter_config.py` |
| Relationship facts (orphans, key widths) | `relationship_facts` | engine `profiling/_scan_integrity.py:176` |
| Join-safe key rule, column entries | E1 `column_entry`, `apply_review` | engine (E1, 1a plan 6.1) |
| Keyed fields | `keyed_columns_for_config` (E3, merged) | engine |
| NER model status and install command | `decoy.cli.models._status` | `src/decoy/cli/models/` |
| CI manifest model and loader | `CiManifest`, `ci/manifest.py` | `src/decoy/ci/` |
| Gate before write | `write_blocking_findings` (1a W1a.6a) | `src/decoy/cli/gate/_layers.py` |
| Module size, fan-out, CODEMAP path sentries | existing | `tests/sentry/layout/` |

New machinery and the reason for each: the coverage registry (no existing guard ties config
fields to the wizard), the location-kind table (four rows add kinds, so one table beats four
branches), the CI renderer (no writer exists).

## 5. Design notes

### 5.1 Location kinds (B2)

`cli/wizard/steps/_locations.py` holds one table: kind id, the prompts, `to_block`, and the
roles it may fill (source, target or both). Local file, S3 and GCS are the V1 rows. DuckDB is a
source row whose `to_block` writes no `sources` entry and returns a run-flag fact instead. Rows
64b, 86 and 87 each add one row. Credentials are never asked. S3 and GCS take a bucket and key
prefix and print where the credentials come from (environment or profile), as `decoy run` reads
them today.

### 5.2 The coverage registry (V0)

A sentry data module `tests/sentry/wizard/_config_coverage.py` maps each path to one of
`Step("<step id>")`, `Hand("<reason>")` or `Row("<row id>")`. The sentry walks
`PipelineConfig.model_json_schema()` (resolving `$defs`, list items as `[]`, map values as `{}`),
plus the discriminator literals of sources, targets and `GenerateColumnConfig.type`. The registry
sits in the test tree because only the sentry reads it; the step ids it names come from the
production `STEPS` tuple.

### 5.3 The CI manifest writer (C1, C2)

C1 renders a new `decoy-ci/v1` document from a `CiManifest` value and proves it by loading the
bytes back through `ci/manifest.py` before returning them. C2 offers the CI step at Review. For a
new manifest it writes through C1 with `CREATE_ONCE`. For an existing manifest it appends one
`pipelines` entry through the W3.1 editor (span rule, hash check, `init.yaml_changed`). It never
writes `staged_scan`.

### 5.4 DuckDB (B3)

The wizard stages the relation to a protected temporary Parquet file with `acquire_relation`, scans
it, and removes it on every exit. The YAML declares the table with no `sources` entry, which is
what `decoy run --duckdb-source` expects. The printed next command and the checklist name the flag.
The answers file and the draft record the DB path and relation as answers, not as YAML.

### 5.5 Tokenize (T1, EG4)

EG4 adds `vault_eligible: bool` to `StrategyInfo`, set on each handler, and rewrites
`check_vault_columns` to read it. The rule then has one home. T1 shows `tokenize` in the tree only
when Tokenize is in the goal (spec 5.4.3), and offers "also store originals in the vault" only on
fields whose strategy is `vault_eligible`. Both set a namespace through E1 `column_entry`. Secrets
then asks for the vault path and checks the cryptography extra through the engine's own check.

## 6. Construction rules (sentries)

- C1 (V0). Config coverage: a new `PipelineConfig` field or kind literal fails CI until it has a
  coverage entry. A `Row` entry needs a row id that the roadmap lists as not done. When the row
  closes, its entry must turn into `Step` or `Hand`.
- C2 (B2). Location kinds: every source and target kind literal maps to one location row or to a
  `Row` coverage entry.
- C3 (EG2, B5). No validator name literal in `src/decoy/cli/wizard/`. Extends the 1a
  no-strategy-literal sentry with validator names and generate type names.
- C4 (B7, P4). Every wizard file write goes through `_private_file`, `_atomic` or the W3.1 editor.
  Extends `tests/sentry/test_atomic_writer.py` scope to `cli/wizard/`.
- C5 (B5). One `.gitignore` writer, `cli/wizard/_gitignore.py` (spec 12).
- C6 (C2). One CI manifest writer, `src/decoy/ci/_emit.py`.

## 7. Slices: guarantees, failure modes, acceptance tests, mutations

Test IDs are `AT-<slice>.<n>`. Every AT is written red first. "Mutation" names the change that
must turn the test red; it runs on the final head (recurring defect 9).

### 7.1 Engine slices

**EG1. Generate type catalog: wire types and examples (spec 16.7).** R1, engine, ~350.

- Guarantee: `generate_option_catalog()` gives, for every option of every type, a wire type token
  (`str`, `int`, `float`, `bool`, `list[str]`, `mapping`, `column_ref`, `expression`) and one
  example that validates.
- Failure modes: a new type or option ships without a wire type; an example that does not
  validate; a free-string token.
- AT-EG1.1: for each type, build a `GenerateColumnConfig` from required options' examples; it
  validates. Mutation: change one example to a wrong type, red.
- AT-EG1.2: the catalog's type set equals the `GenerateColumnConfig.type` literal set. Mutation:
  drop one type, red.
- AT-EG1.3: wire type is a closed enum; a string outside it is refused (recurring defect 4).
- Starts now.

**EG2. Public validator catalog (spec 16.8).** R1, engine, ~350.

- Guarantee: `validator_catalog()` exported from `decoy_engine` lists every registered validator
  with name, `columns` arity, params (name, wire type, required, example) and a one-line
  description. `_REGISTRY` stays private and the catalog is derived from it.
- Failure modes: a validator registered without catalog metadata; a catalog entry with no
  registered function; a params example that fails the validator's own param check.
- AT-EG2.1: catalog names equal `_REGISTRY` keys. Mutation: register a validator without
  metadata, red.
- AT-EG2.2: every example builds a `ValidatorEntry` that passes config validation.
- AT-EG2.3: export snapshot updated (additive).
- Starts now.

**EG3. Per-column free-text flag (spec 16.14).** R1, engine, ~300.

- Guarantee: a public function takes one column's scan `FieldStats` and the config, and returns
  whether the advisory would flag it, using the same thresholds and the same scorer as
  `score_unmasked_freetext`.
- Failure modes: a second threshold reader; the per-column answer differs from the run-time
  advisory for the same data.
- AT-EG3.1 (parity): over a corpus of columns, the per-column flag equals the run-time advisory's
  set. Mutation: hard-code a threshold in the new function, red.
- AT-EG3.2: no value appears in the result (returns a bool and a reason id only).
- Starts now.

**EG4. Vault eligibility in the strategy catalog.** R2 (security rule moves home), engine, ~300.

- Guarantee: `StrategyInfo.vault_eligible` exists for every strategy, and `check_vault_columns`
  reads it. `fpe` and `passthrough` are not eligible, as today.
- Failure modes: two copies of the rule; a strategy added without the attribute.
- AT-EG4.1: for every strategy, `check_vault_columns` on a one-column config with `vault: true`
  passes exactly when `vault_eligible` is true. Mutation: flip `fpe` to eligible, red.
- AT-EG4.2: a handler without the attribute fails G-CATALOG.
- Depends on E1 (same files in the catalog). Released with R-1b.

**E2.** As in the record plan (4.6, AT-E5, ~420, R2). Unchanged except that it reads report v3
fields. Starts now: M1 and M4 are merged.

**E1.** As in the 1a plan (6.1). Listed for order only. Starts now.

### 7.2 Independent CLI slices (can start before S3a.1)

**Y0. Move the YAML mark index to `src/decoy/_yaml_marks.py`.** R1, CLI, ~250.

- Guarantee: `ci/locations.py` keeps its public names and imports the index from the new module.
  All existing `ci` tests pass unchanged.
- Failure modes: a behavior change in mark positions; a re-export kept with no consumer.
- AT-Y0.1: existing `tests/unit/test_ci_*` location tests, unchanged. Mutation: off-by-one on a
  line mark, red.
- AT-Y0.2: CODEMAP row "Shared YAML document structure and source-mark indexing" added; the
  CODEMAP path sentry passes.
- Consumer now: `ci/locations.py`. Later: W3.1, P4.

**C1. CI manifest renderer.** R1, CLI, ~300.

- Guarantee: `render_manifest(manifest: CiManifest) -> bytes` gives a document that
  `ci/manifest.py` loads back to an equal model. Only `pipelines` and `checks` are written.
- Failure modes: output the loader refuses; a `staged_scan` block written; key order not stable.
- AT-C1.1 (round trip): a property test over generated `CiManifest` values without
  `staged_scan`. Mutation: drop the `fail_on_warning` key from the output, red.
- AT-C1.2: a manifest with `staged_scan` is refused by the renderer with a registered code.
- AT-C1.3 (golden): one two-pipeline manifest, byte golden.
- Consumer: C2 (named under the proportionality exception; C2 lands before row 32b closes).

### 7.3 Phase 1b slices

All 1b slices depend on W1a.6b unless they say otherwise. Each extends the privacy test
(spec 15) with its new surfaces and fields.

**V0. Config coverage registry and sentry.** R1, CLI, ~350.

- Guarantee: G1 and construction rule C1.
- Failure modes: the walker misses nested models, unions or list items; a stale entry for a field
  that no longer exists; a `Row` entry for a closed row.
- AT-V0.1: the walker yields every path of a seeded fixture schema with nested models, a
  discriminated union, a list of models and a map of models. Non-vacuity: at least 120 paths on
  the real schema.
- AT-V0.2: add a field to a fixture copy of the schema; the sentry is red. Mutation: delete one
  registry entry, red.
- AT-V0.3: an entry naming a step id not in `STEPS`, red.
- AT-V0.4: an entry for a path not in the schema, red.
- AT-V0.5: a `Row` entry whose row is marked done in `docs/ROADMAP.md`, red.

**B1. Fixed-width sources and targets.** R1, CLI, ~450.

- Guarantee: Sources offers fixed width with a column ruler over the first records (spec 5.2);
  the user types widths or start positions; `layout` is validated by the engine before Scan.
  Output offers `fixed_width` for a fixed-width source and copies the layout.
- Failure modes: overlapping or gap fields accepted; the ruler shows real values with
  `--no-samples`; the layout is re-asked after Back with answers lost.
- AT-B1.1: scripted session builds a three-field layout; YAML validates and round-trips.
- AT-B1.2: overlapping widths are refused with the engine's reason; no write.
- AT-B1.3: `--no-samples` ruler shows shapes only (canary test). Mutation: pass raw rows to the
  ruler, red.
- AT-B1.4: changing the layout marks Scan and Fields stale.
- Module: `steps/_fixed_width.py`.

**B2. S3 and GCS locations, delivery mode.** R2, CLI, ~450.

- Guarantee: one location table (5.1); S3 and GCS for sources and targets; no credential prompt;
  `delivery.mode` asked in Output when any target is cloud (default `strict`); the gate's cloud
  root check (`cloud_root_issues`) runs before write.
- Failure modes: bucket or key text in an error, log or `--json` output; a split delivery root
  accepted; a credential value accepted into YAML.
- AT-B2.1: scripted S3 source and GCS target session; YAML validates; `delivery.mode` written.
- AT-B2.2: a split root is refused with `layout.*` reason through `write_blocking_findings`.
- AT-B2.3: seeded bucket and key canaries never appear in `-v` logs, `--json` or error text.
  Mutation: include the key in the location summary line, red.
- AT-B2.4 (C2 sentry): every source and target kind literal maps to a location row or a `Row`
  entry. Mutation: remove the GCS row, red.
- Module: `steps/_locations.py`.

**B3. DuckDB tables.** R1, CLI, ~350.

- Guarantee: 5.4. The staged Parquet file is removed on every exit.
- Failure modes: staged file left after cancel, error or crash; a `sources` entry written for the
  table; the next command lacks the flag; the DB path in logs.
- AT-B3.1 (exit-path matrix): success, cancel at each later step, scan error, write refusal,
  KeyboardInterrupt; the staging directory is empty after each. Mutation: skip cleanup on cancel,
  red.
- AT-B3.2: the YAML has no `sources` entry for the table and `decoy run --duckdb-source` with the
  printed command validates it (`duckdb_probe_raw`).
- AT-B3.3: the printed command and the checklist name `--duckdb-source TABLE=DB_PATH`.
- Module: `steps/_duckdb.py`.

**B4. Flagged-only field review.** R2, CLI, ~400.

- Guarantee: spec 5.4.1. A field is flagged when the scan found it, was unsure, it has a high
  unique share, or EG3 flags it. Unflagged fields take one bulk strategy. Review shows the count
  of fields kept unchanged without review and needs an explicit confirm.
- Failure modes: an EG3-flagged field bulk-passed through; the Review confirm skipped on a resumed
  draft or answers file.
- AT-B4.1: a fixture with a short identifier no detector matches but EG3 flags is reviewed one at
  a time. Mutation: drop the EG3 term from the flag rule, red.
- AT-B4.2: Review refuses to write until the confirm when any bulk `passthrough` field exists,
  in terminal and answers routes.
- AT-B4.3: the unique-share threshold is one constant, used in one place.
- Depends on EG3 released and repinned.

**B5. Checks step.** R2, CLI, ~500.

- Guarantee: Checks writes `post_scan.integrity`, `validators` from EG2's catalog, and
  `quarantine`. The H1 rule warns that quarantine holds unmasked rows and offers a `.gitignore`
  entry through `_gitignore.py`. The H2 rule shows `column_in_set` allowed values only on a field
  the user confirmed, and they are the only allow-listed values in files (spec 15).
- Failure modes: validator names typed in the CLI; a quarantine path inside the repo with no
  warning; the `.gitignore` rewritten (other lines changed); allowed values leaking to logs.
- AT-B5.1: every catalog validator can be added in a scripted session and the YAML validates.
- AT-B5.2 (C3): a validator name literal in `cli/wizard/`, red.
- AT-B5.3: `.gitignore` with comments and no trailing newline gains one line; other bytes equal;
  a second run adds nothing. Mutation: write with `REPLACE` of joined lines, red.
- AT-B5.4 (C5): a second `.gitignore` writer under `src/decoy/`, red.
- AT-B5.5: allowed values never appear in `-v` logs or `--json`.
- Modules: `steps/checks.py`, `_gitignore.py`. Depends on EG2 released.

**B6. Quality step.** R1, CLI, ~300.

- Guarantee: writes `post_validation` and `thresholds`; adds `--fidelity` to the printed run
  command when chosen.
- AT-B6.1: scripted session; YAML validates. AT-B6.2: a threshold outside the engine's range is
  refused with the engine reason. Mutation: skip validation before write, red.
- Module: `steps/quality.py`.

**B7. Drafts and resume.** R2, CLI, ~500.

- Guarantee: spec 10. `q` saves `.<name>.init-draft.json` (`decoy-init-draft/v1`) owner-only
  through `_private_file`; `--resume` loads it strictly; the draft holds only `_safe_profile`
  records, never sample values; the draft is removed after a successful write; a `.gitignore`
  entry is offered once.
- Failure modes: lax types read (recurring 2); unknown major accepted (4); sample values in the
  draft; the draft left after success; a draft for a different source accepted.
- AT-B7.1: draft round trip equals the state. AT-B7.2: next major, missing tag, `true` for an int,
  `"5"` for an int each refused with `init.draft_invalid`; error has no `__context__`
  (recurring 3).
- AT-B7.3: canary values from `top_values`, `min_value`, `max_value` never in the draft.
  Mutation: store the raw profile, red.
- AT-B7.4 (exit matrix): success removes the draft; cancel keeps the last draft; failed write
  keeps the old draft unchanged.
- AT-B7.5 (C4): a wizard file write not through `_private_file`, `_atomic` or the editor, red.
- Modules: `_draft.py`; `src/decoy/_safe_profile.py` promoted from `cli/scan.py` (scan imports it).

**B8. Preset pre-fill.** R1, CLI, ~250.

- Guarantee: choosing a preset at Start pre-fills Goal, Checks and Quality answers from the
  template with origin `preset`; the user can change each; the written YAML for an unchanged
  preset session equals today's preset output for the same answers.
- AT-B8.1: for each template, the unchanged session output equals the template output (golden).
  Mutation: drop one pre-filled answer, red.

### 7.4 Phase 2 slices

**P1a. Goal multi-select and generate-from-snapshot.** R1, CLI, ~350.

- Guarantee: Goal offers Mask, Generate, Subset, Tokenize (Tokenize leaf enabled by T1). Per
  table the user picks mask or generate. A generated table fitted from a snapshot reuses
  `scaffold_generate`; no fit code is copied.
- Failure modes: turning a goal off loses its answers; seeds naming a removed table not marked.
- AT-P1a.1: off then on restores answers (spec 15 navigation case).
- AT-P1a.2: a generate table from a snapshot equals `decoy init --preset generate FILE` output for
  that table. Mutation: call a copied fit, red (import sentry: `scaffold_generate` is the only fit
  caller in `cli/wizard/`).

**P1b. Generate column editor.** R1, CLI, ~500.

- Guarantee: per column the user picks a type from EG1's catalog and fills required options by
  wire type; `row_count` asked per generated table; the YAML validates per column before the next.
- Failure modes: a type list typed in the CLI; `required_when` options skipped; `column_ref`
  options naming a missing column.
- AT-P1b.1: every catalog type can be configured in a scripted session from catalog examples.
- AT-P1b.2: generate type name literal in `cli/wizard/` fails C3.
- AT-P1b.3: `required_when` and `one_of` rules enforced from the catalog. Mutation: ignore
  `required_when`, red.
- Module: `steps/generate.py`. Depends on EG1 released.

**P2. Relationships step.** R2, CLI, ~500.

- Guarantee: spec 5.5. Candidates come from `starter_config`'s relationship template; the user
  confirms, edits or adds; composite keys keep column order; key fields end with one shared
  namespace and a `join_safe` strategy chosen through E1 `apply_review`; `orphan_policy` asked;
  `relationship_facts` runs on local sources and reports orphans before write.
- FK shapes (enumeration): single column; composite; self-referencing; one parent with several
  children; a chain (A to B to C); a child in another source format; a cross-table cycle (refused:
  V1 keeps the full-frame fallback, cross-table cycles are V2, decision 2026-11).
- Failure modes: a non-join-safe key confirmed; key widths differ; a cloud end silently checked
  as if local.
- AT-P2.1: one scripted case per FK shape above; the cycle case is refused with the engine
  reason. AT-P2.2: `redact` on a key is refused until a join-safe strategy is chosen. Mutation:
  skip the `apply_review` call, red.
- AT-P2.3: confirming a relationship marks Fields stale (spec 15).
- AT-P2.4: a cloud end reports "skipped_cloud" as the engine does, not "no orphans".
- Module: `steps/relationships.py`.

**P3. Subset step.** R1, CLI, ~400.

- Guarantee: seeds of mode `filter` (predicate ops from the engine literal) and `sample`; Parquet
  required for subset is checked before the step (engine reason `subset_requires_parquet`); the
  checklist names the hand-edit keys (`keys`, `budget`, `edge_directions`, `allow_dangling`).
- AT-P3.1: filter and sample sessions validate; `subset --dry-run` accepts the result.
- AT-P3.2: a CSV source with Subset in the goal is told before the step, with a registered reason.
  Mutation: skip the check, red.
- AT-P3.3: a seed naming a removed table is marked stale.
- Module: `steps/subset.py`. Depends on P2.

**P4. Answers files.** R2, CLI, ~500.

- Guarantee: record plan 4.4. `decoy-init-answers/v1` strict model; `--answers FILE` runs with no
  prompts; `--save-answers FILE` writes owner-only through `_private_file` with `CREATE_ONCE`;
  `unlisted: skip|confirm`; a stale confirm raises `pre_scan.review_stale`; marks come from
  `_yaml_marks`; `--fail-on-warning` maps warnings to exit 2.
- Failure modes as B7, plus: an answers file that sets a field the scan no longer has.
- AT-P4.1: every step's answers round-trip; a full answers run equals the terminal run with the
  same answers. AT-P4.2: strict-type cells and version cells (as AT-B7.2) with
  `init.answers_invalid`. AT-P4.3: existing file not overwritten. Mutation: use `REPLACE`, red.
- AT-P4.4: schema snapshot of `decoy-init-answers/v1` (frozen from here).
- Module: `_answers.py`. Depends on Y0.

**P5. Step selection and dry flags.** R1, CLI, ~300.

- Guarantee: `--skip`, `--only` take step ids from `STEPS` only; `--no-validate` skips only the
  final engine validation and says so in the checklist; `--diff` prints the YAML diff and writes
  nothing (exit 0).
- AT-P5.1: an unknown step id is a usage error (exit 1). AT-P5.2: `--diff` leaves the tree byte
  for byte unchanged. Mutation: write before diff, red.

**W3.1. Comment-preserving editor.** As in the record plan (4.7, ~540, R2), with D6: owner-only
writes use `_private_file`; no `mode` argument is added. AT-W13, AT-W14, AT-W21, G-ONE-EDITOR.
Depends on Y0 and W1a.6b.

**P7. `decoy edit <section> <pipeline>`.** R2, CLI, ~450.

- Guarantee: runs one step over an existing pipeline and splices its block through W3.1; the
  `edit` verb is registered from `cli/wizard/_edit.py`, not a flat module.
- AT-P7.1 (round-trip property, spec 15): full flow with answers A equals the same sections run
  one at a time through `decoy edit`.
- AT-P7.2: every byte outside the edited block is unchanged, for each section.
- AT-P7.3: a file changed between read and write refuses with `init.yaml_changed`. Mutation: drop
  the hash check, red.

**W2.** As in the record plan (~460, R1). Depends on SCAN-ML M3b (classifier suggestions) released,
which waits on E1.

**W3.2.** As in the record plan (~590, R2), reading report v3 and v2 (D5). Depends on W3.1, E2
released, SCAN-ML C2a merged (CLI #301).

### 7.5 Phase 3 slices kept in V1

**T1. Tokenize goal.** R2, CLI, ~400.

- Guarantee: 5.5. `tokenize` shown only with the Tokenize goal; "store originals in the vault"
  offered only on `vault_eligible` strategies; namespaces set through E1; Secrets asks for the
  vault path and states that the vault file is a secret; the `.gitignore` offer covers it.
- Failure modes: `vault: true` on `fpe`; a tokenize field with no namespace; the vault path inside
  the repo with no warning; the cryptography extra missing and not reported.
- AT-T1.1: tree sync (spec 15) with and without the Tokenize goal. AT-T1.2: the vault offer set
  equals the `vault_eligible` set. Mutation: offer on all strategies, red.
- AT-T1.3: YAML from a Tokenize session passes `check_vault_columns`.
- Module: `steps/tokenize.py`. Depends on EG4 released, P1a.

**C2. CI manifest step.** R2, CLI, ~350.

- Guarantee: 5.3. Review offers "run this pipeline in CI". New manifest through C1; existing
  manifest gets one `pipelines` entry through W3.1. A DuckDB pipeline is not offered (the CI
  runner has no `--duckdb-source`); the checklist says why.
- Failure modes: an existing manifest's other bytes changed; a duplicate pipeline id; a
  `staged_scan` block touched; the manifest written when the pipeline write failed.
- AT-C2.1: append to a manifest with comments; other bytes equal; the result loads.
- AT-C2.2: duplicate id refused. AT-C2.3: pipeline write fails, manifest unchanged (order: the
  pipeline is written first). Mutation: write the manifest first, red.
- AT-C2.4 (C6): a second manifest writer, red.
- Depends on C1, W3.1.

### 7.6 Report versions for W3.2

W3.2 reads `post-scan-integrity/v3`. It also reads v2 and treats a v2 report without
`tables_checked` as covering no table (so every finding is shown, none auto-dismissed). Unknown
major and missing tag are refused with `init.report_schema` (recurring 4).

## 8. Class table

| # | Class | Applies to | Structure | Proof | Mutation |
|---|---|---|---|---|---|
| 1 | Value-bearing output | B1 ruler, B2 locations, B5 allowed values, B7 drafts, P4 answers, B3 paths | value-free errors from registered codes; `_safe_profile` only in drafts | canary corpus over every surface (spec 15) per new step | pass a raw value into a summary line |
| 2 | Cleanup on exit paths | B3 staging, B7 draft, C2 order | one owner per resource; draft removed only after a write | exit-path matrices AT-B3.1, AT-B7.4, AT-C2.3 | skip one cleanup |
| 3 | State machine | stale marking across new steps | 1a `_nav` transition rules, each new `stale()` | navigation cases per new step | drop one `depends_on` |
| 4 | Route parity | terminal, answers, draft resume, `decoy edit` | one step object per route | AT-P4.1, AT-P7.1 | answers route skipping a step's validation |
| 5 | Referential integrity | P2, P3 | FK shape list; engine refusals | AT-P2.1, AT-P3.3 | skip `apply_review` on a key |
| 6 | Untrusted producer | answers, drafts, reports, existing manifest | strict versioned models, bounded reads | AT-B7.2, AT-P4.2, W3.2 report cells | lax int field |
| 7 | TOCTOU on paths | editor writes, manifest append | hash check at write | AT-P7.3, AT-C2.1 | drop the hash check |
| 8 | Weak tests | all | evidence rules section 12 | reviewer reruns on the exact head | n/a |
| 9 | Refactor drift | Y0, `_safe_profile` move | existing tests unchanged | AT-Y0.1 | n/a |
| 10 | Frozen contract drift | `decoy-ci/v1`, answers v1, engine exports | additive only, snapshots | AT-C1.1, AT-P4.4, export snapshots | add a manifest key |

## 9. Enumerations

### 9.1 New exit paths that own files or state

| Owner | Exits |
|---|---|
| DuckDB staging (B3) | success, cancel at each step, scan error, gate refusal, write error, interrupt |
| Draft (B7) | `q`, cancel, interrupt, success (removed), failed write (kept), bad draft on resume |
| Answers save (P4) | success, file exists, parent missing, write error |
| `.gitignore` (B5, B7, T1) | added, already present, file missing (created), write error |
| Editor writes (W3.1, P7, C2) | success, hash changed, unsupported span, symlink, write error |
| Manifest (C1, C2) | new file, append, duplicate id, invalid existing manifest, pipeline write failed first |

### 9.2 Routes

- Terminal session (`decoy init`, `decoy init FILE`).
- Answers file (`--answers`, P4).
- Draft resume (`--resume`, B7).
- Section edit (`decoy edit <section>`, P7).
- Findings review (`--review-findings`, W3.2).
- One-shot flags (`--json`, `-q`, `--no-input`), unchanged from 1a.

### 9.3 FK shapes

The Relationships step (P2) handles each shape that `RelationshipConfig`
(engine `config/_relationships.py:41`) can hold:

- single-column key;
- composite key (column order kept);
- self-referencing table;
- one parent with several children;
- a chain (A to B to C);
- a child whose source is cloud: facts report `skipped_cloud`
  (engine `profiling/_scan_integrity.py:176`);
- a cross-table cycle: refused (V1 keeps the full-frame fallback; first-class cycles are V2).

### 9.4 Fields

The config models whose fields the wizard writes, each walked in full by V0:

- `PipelineConfig` (engine `config/_pipeline.py:87`);
- `DeliveryConfig` (engine `config/_delivery.py:19`);
- `RelationshipConfig` (engine `config/_relationships.py:41`);
- `SubsetConfig` (engine `config/_subset.py:87`);
- `GenerateTypeOptions` (engine `config/_generate_option_catalog.py:32`), extended by EG1;
- `CiManifest` (CLI `src/decoy/ci/contracts.py:615`) and `PipelineRef` (`contracts.py:500`),
  written by C1;
- the DuckDB staging pair `describe_relation` and `acquire_relation`
  (CLI `src/decoy/cli/_duckdb_source.py:76,87`), called by B3.

### 9.5 Output surfaces

- stdout prompts, summaries and the printed next command;
- stderr errors;
- `--json` output;
- `-v` logs;
- the pipeline YAML;
- the draft file;
- the answers file;
- `.gitignore`;
- `.decoy-ci.yaml`;
- the end-of-run checklist;
- help text and parse errors.

Each new slice adds its surfaces to the privacy test.

## 10. Placement

| New file | Directory | CODEMAP row | Sits beside |
|---|---|---|---|
| `steps/_locations.py`, `_fixed_width.py`, `_duckdb.py`, `checks.py`, `quality.py`, `generate.py`, `relationships.py`, `subset.py`, `detectors.py`, `tokenize.py` | `src/decoy/cli/wizard/steps/` | "Interactive review wizard" (added by W1a.0) | 1a step modules |
| `_draft.py`, `_answers.py`, `_gitignore.py`, `_yaml_edit.py`, `_edit.py`, `_findings.py`, `_ci_step.py` | `src/decoy/cli/wizard/` | same | `_flow.py` |
| `_yaml_marks.py` (target) | `src/decoy/` | "Shared YAML document structure and source-mark indexing" (added by Y0) | `_atomic.py` |
| `_safe_profile.py` (target) | `src/decoy/` | "Private shared filesystem or process primitives" | `_private_file.py` |
| `_emit.py` (target) | `src/decoy/ci/` | "CI integration" (`src/decoy/ci/<concern>.py`) | `manifest.py` |
| `_config_coverage.py`, `test_config_coverage.py` | `tests/sentry/wizard/` | wizard sentry row (1a) | 1a wizard sentries |
| unit and e2e tests | `tests/unit/wizard/`, `tests/e2e/wizard/` | wizard row | 1a tests |
| engine `_generate_option_catalog.py` (edit) | `decoy_engine/config/` | engine config | |
| engine `validators/_catalog.py` (target) | `decoy_engine/validators/` | engine validators | `_registry.py` |
| engine `quality/_freetext_advisory.py` (edit) | `decoy_engine/quality/` | engine quality | |

No new file in flat `src/decoy/cli/`. Fan-out: `cli/wizard/` reaches about 16 modules and
`cli/wizard/steps/` about 19, both under the 25 cap. Module size: each step module stays under
800 lines; `steps/sources.py` does not grow past its 1a size because location kinds, fixed width
and DuckDB are separate modules. No ceiling, pin or baseline is raised.

Consumer pairs (proportionality exception): C1 to C2; Y0 to P4 and W3.1 (also `ci/locations.py`
now); EG1 to P1b; EG2 to B5; EG3 to B4; EG4 to T1; E2 to W3.2.

## 11. Slices, order and tiers

| Slice | Repo | Lines | Tier | Depends on | Can start before S3a.1 |
|---|---|---|---|---|---|
| E1 (1a plan) | engine | ~700 | R2 | merged S3-engine.2, M1 | yes |
| E2 | engine | ~420 | R2 | E1 (types), M1, M4 | yes |
| EG1 | engine | ~350 | R1 | none | yes |
| EG2 | engine | ~350 | R1 | none | yes |
| EG3 | engine | ~300 | R1 | none | yes |
| EG4 | engine | ~300 | R2 | E1 | yes (after E1) |
| R-1b | engine | n/a | R2 | EG1 to EG4, E2 (or split across trains) | yes |
| Y0 | CLI | ~250 | R1 | none | yes |
| C1 | CLI | ~300 | R1 | none | yes |
| V0 | CLI | ~350 | R1 | W1a.6b | no |
| B1 | CLI | ~450 | R1 | W1a.6b | no |
| B2 | CLI | ~450 | R2 | W1a.6b | no |
| B3 | CLI | ~350 | R1 | B2 | no |
| B4 | CLI | ~400 | R2 | W1a.6b; EG3 repinned | no |
| B5 | CLI | ~500 | R2 | W1a.6b; EG2 repinned | no |
| B6 | CLI | ~300 | R1 | B5 | no |
| B7 | CLI | ~500 | R2 | W1a.6b | no |
| B8 | CLI | ~250 | R1 | B5, B6 | no |
| P1a | CLI | ~350 | R1 | W1a.6b | no |
| P1b | CLI | ~500 | R1 | P1a; EG1 repinned | no |
| P2 | CLI | ~500 | R2 | W1a.6b | no |
| P3 | CLI | ~400 | R1 | P2, P1a | no |
| P4 | CLI | ~500 | R2 | Y0, W1a.6b | no |
| P5 | CLI | ~300 | R1 | P4 | no |
| W3.1 | CLI | ~540 | R2 | Y0, W1a.6b | no |
| P7 | CLI | ~450 | R2 | W3.1, P4 | no |
| W2 | CLI | ~460 | R1 | W1a.6b; SCAN-ML M3b released | no |
| W3.2 | CLI | ~590 | R2 | W3.1; E2 repinned; C2a merged | no |
| T1 | CLI | ~400 | R2 | P1a; EG4 repinned | no |
| C2 | CLI | ~350 | R2 | C1, W3.1 | no |

New CLI lines in this plan: about 9,800 across 21 CLI slices; engine: about 1,300 across EG1 to
EG4 (E1 and E2 were sized in earlier plans).

Order after W1a.6b: V0 first (so every later step adds its coverage entry), then in parallel
lanes with one writer per file: (B1, B2, B3), (B5, B6, B8), (B4), (B7), (P1a, P1b), (P2, P3),
(Y0 done, P4, P5), (W3.1, P7, C2), (W2), (W3.2), (T1). `steps/__init__.py` (`STEPS`) and the
coverage registry are shared ledger files: keep both sides on merge.

One engine release (R-1b) after E1 and EG1 to EG4, with one CLI repin; E2 can ride R-1a if it is
ready. One release and one repin open at a time.

Before S3a.1 unblocks 1a: E1, E2, EG1, EG2, EG3 (then EG4), Y0, C1. That is about 3,000 lines of
work with no dependency on the renderer.

## 12. Worker evidence rules

- Name the class of every finding and fix the class.
- Write the ATs first and record them red.
- Run the named mutations on the final head and record the head.
- Tests run on the Mac or through `vm-run`, never on the devbox.
- T0 per edit, T1 per commit. The full suite runs only on a trigger: the R-1b repin (lock),
  answers and draft formats (serialization), Y0 (moved code with moved tests) and C1, C2
  (`decoy-ci/v1`, a frozen contract).
- Never raise a size cap, ratchet or allowlist. Never weaken a test to pass.

## 13. Frozen contracts touched

| Contract | Change |
|---|---|
| `decoy-ci/v1` | none to the schema; C1 writes only what the loader already reads |
| `decoy-init-answers/v1` | new; frozen at P4 with a snapshot |
| `decoy-init-draft/v1` | new; private, versioned, not a public contract |
| `post-scan-integrity/v3` | read only |
| Engine public exports | additive: `validator_catalog`, the per-column free-text function, `StrategyInfo.vault_eligible`, catalog fields |
| Exit codes | none |
| `init.*` reason codes | additive in the central registry: `init.draft_invalid`, `init.answers_invalid`, `init.yaml_changed`, `init.yaml_edit_unsupported`, `init.yaml_symlink`, `init.report_missing`, `init.report_schema`, `init.report_stale` (as planned in 1a section 12) |

## 14. Roadmap row 32b text (for the roadmap owner to apply; this plan does not edit ROADMAP.md)

> **32b INIT-WIZARD (V1, owner 2026-11-17: "a working wizard to configure a job is v1").**
> `decoy init` configures any V1 job: local, fixed-width, S3, GCS and DuckDB sources; local,
> fixed-width, S3 and GCS targets with delivery mode; mask, generate, subset and tokenize goals;
> pre-scan and post-scan detectors; per-field strategies in every-field or flagged-only review;
> generated columns; relationships; subset filter and sample seeds; post-scan integrity,
> validators and quarantine; quality settings; secrets and the vault; and the CI manifest.
> Answers files, drafts and resume, `decoy edit`, and post-scan findings review included. Plans:
> Phase 1a `docs/plans/2026-11-08-init-wizard-phase-1a.md`; the rest
> `docs/plans/2026-11-17-init-wizard-v1-rest.md`. A coverage sentry fails CI for any new config
> field with no wizard entry. Rows 64b, 86, 87, 81, 68, 69 and 32 add their own wizard entries.
> V2: arrow keys and completion, before and after previews. After: SCAN-MULTI S3a.1 (1a), engine
> R-1a and R-1b, SCAN-ML M3b (W2), C2a (W3.2).

## 15. Owner questions (each with a recommended answer)

| # | Question | Recommended |
|---|---|---|
| Q1 | Tokenize goal: offer both the `tokenize` strategy and `vault: true` on eligible strategies? (1a open decision 14.2) | Both, as separate choices |
| Q2 | Validator list from a new engine catalog (EG2) or a temporary CLI table with a sync test (spec 12)? | Engine catalog |
| Q3 | Findings review command home: keep `decoy init --review-findings PIPELINE --report FILE`? (1a 14.1) | Keep it |
| Q4 | Rows 64b, 86, 87, 81, 68, 69 and 32 each ship their wizard entry, enforced by the coverage sentry? | Yes |
| Q5 | DuckDB stays a run flag in V1 (no config kind); the wizard prints the flag? | Yes; a config kind is V2 |
| Q6 | Before and after previews (engine gap 16.1) move to V2? Shapes and samples from 1a stay | Yes, V2 |
| Q7 | Preset pre-fill (B8) in V1? | Yes, it is small and presets already exist |
| Q8 | No new dependency for any slice here (no `ruamel.yaml`, no `prompt_toolkit`)? | Confirm: none |
| Q9 | The wizard may append to an existing user-owned `.decoy-ci.yaml` through the editor? | Yes, with the hash check and a diff shown first; otherwise print the entry to paste |
| Q10 | `scan_baseline` (drift) belongs to row 32 DRIFT, not to this plan? | Yes |

## 16. Pre-mortem

- 1a slips on S3a.1 and this plan waits. Mitigation: about 3,000 lines start now (section 11).
- Many lanes touch `steps/__init__.py` and the coverage registry at once. Mitigation: V0 lands
  first; both files are keep-both ledgers.
- The editor (W3.1) is the riskiest piece and three slices wait on it (P7, C2, W3.2). Mitigation:
  start W3.1 the day W1a.6b merges; its record-plan ATs and hostile corpus are ready.
- The privacy test grows with each step and slows. Mitigation: one shared canary fixture, one
  parametrized test per surface.
- Engine catalog additions (EG1 to EG4) slip the release train. Mitigation: each is independent;
  B4, B5, P1b and T1 wait only on their own engine slice.
- A later row adds a source kind before V0 lands. Mitigation: V0 maps every kind present at its
  base; the sentry then holds.
