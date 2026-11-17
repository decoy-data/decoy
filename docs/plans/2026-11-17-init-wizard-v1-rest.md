# Init wizard: the rest of V1 (row 32b after Phase 1a)

Status: plan

Revision: rev 1, 2026-11-17. Fixes Dennis round 1 on `98bfdc8d` (BLOCK, 0 critical, 8 high,
14 medium, 5 low). Section 17 maps each finding to the change. Owner answers recorded in
section 15.

Date: 2026-11-17. Author: Opus planner. Risk: R2 overall (privacy of scan output, persisted
answer and draft formats, edits to user-owned YAML, the frozen `decoy-ci/v1` contract). Each
slice carries its own tier in section 11.

Bases: CLI `origin/main` `c558e2fb` (#310), engine `origin/main` `11ceb73f5` (#635, version
0.27.0). The CLI pins `decoy-engine==0.27.0`.

Rules consulted: `/home/cam/dev-rules/00-universal.md`, `development-loop.md`,
`risk-and-exceptions.md`, `proportionality.md`, `catalogs/recurring-defects.md` (classes 1 to
11); the plan contract and defect catalog
(`obsidian-vault/30_Resources/Decoy-Plan-Contract-and-Defect-Catalog.md`); CODEMAP "Where Things
Go"; standing memory rules (V1 bar, pre-release no locking, one registry per concern, files about
800 lines, sentry over prose, no raised caps).

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
- V2: arrow keys and `prompt_toolkit` completion; before and after previews (owner, 2026-11-17).

This plan does not re-plan Phase 1a. Section 3 lists the changes the 1a builders must apply
because CLI main moved since the 1a plan was written.

## 1. Coverage

### 1.1 How the table was built

The table comes from a walk of `PipelineConfig.model_json_schema()` on engine `11ceb73f5`
(resolving `$ref`, `anyOf`, `oneOf`, `allOf`, `if` and `then`; list items as `[]`, map values as
`{}`). The walk gives 214 nodes, of which 184 are leaves. Three leaves are open maps
(`additionalProperties: true`), written `{*}`. A container node (for example `subset.budget`) is
covered when all its leaves are covered. V0 turns this table into a sentry (section 6, rule C1).

Every leaf maps to one of:

- **Step** (the step and the slice that configures it);
- **Hand** (left for a hand edit, with the reason; `decoy edit` and the checklist name it under
  "Set by hand", spec 7);
- **Row** (a V1 roadmap row that has not built the surface; it ships its own wizard entry).

### 1.2 Pipeline config leaves

| Leaves | Entry | Slice |
|---|---|---|
| `version`, `name` | Step: Start, through the project layout | 1a W1a.6a |
| `sources.{}.type`, `.path`, `.format`, `.delimiter`, `.has_header`, `.column_names`, `.column_names_file` | Step: Sources (local file) | 1a W1a.4a |
| `sources.{}.layout.exact_record_width`, `sources.{}.layout.columns[].name`, `.start`, `.width`, `.align`, `.pad`, `.type` | Step: Sources, fixed-width sub-flow | **B1** |
| `sources.{}.bucket`, `.key`, `.object`, `.region`, `.endpoint_url`, `.credentials_ref` | Step: Sources, S3 and GCS location kinds. `credentials_ref` takes a reference (`env:` or `file:`), never a value (`config/_sources.py:275-293`) | **B2** |
| `targets.{}.type`, `.path`, `.format` | Step: Output (local file) | 1a W1a.5a |
| `targets.{}.layout.exact_record_width`, `targets.{}.layout.columns[].name`, `.start`, `.width`, `.align`, `.pad`, `.type` | Step: Output, fixed width | **B1** |
| `targets.{}.bucket`, `.key`, `.object`, `.region`, `.endpoint_url`, `.credentials_ref` | Step: Output, S3 and GCS location kinds | **B2** |
| `delivery.mode` | Step: Output | **B2** |
| `tables[].name` | Step: Sources (table name) | 1a W1a.4a |
| `tables[].columns[].name`, `.strategy`, `.provider`, `.provider_config.{*}`, `.namespace`, `.deterministic` | Step: Fields, through E1 `column_entry` | 1a W1a.3b |
| `tables[].columns[].vault` | Step: Fields, Tokenize branch | **T1** |
| `tables[].columns[].when`, `.coherent_with`, `.cardinality_mode`, `.error_policy`, `.logical_type`, `.parse_format`, `.output_format`, `.backend_type`, `.pool_size`, `.allow_collisions`, `.dtype`, `.sentinel_to_null` | Hand: spec 7 column-key list. Each refines one column after it has a valid strategy; the job runs without them (owner question Q12) | none |
| `tables[].columns[].scale`, `.backend_version` | Hand: they qualify `dtype` and `backend_type`, which are on the spec 7 list (Q12) | none |
| `tables[].transforms[].op` (value `drop_column`), `tables[].transforms[].column` | Step: Fields, `d` key | 1a W1a.3b |
| `tables[].transforms[].columns`, `.by`, `.ascending`, `.n`, `.expression` | Hand: spec 7 (filter, sort, limit, dedupe, derive) | none |
| `tables[].row_count`, `tables[].unique_together` | Step: Generate (GEN-UNIQUE is V1) | **P1b** |
| `tables[].generate_columns[].name`, `.type`, `.null_probability`, `.determinism`, `.output_type`, `.pooled`, `.unique` | Step: Generate, options common to every type | **P1b** |
| `tables[].generate_columns[].` `allow_real_categories`, `anchor`, `bounds`, `categories`, `codeset`, `column`, `condition_on`, `distribution`, `expression`, `faker_kwargs`, `faker_type`, `family`, `file`, `formula`, `generator`, `group_by`, `high`, `high_cardinality`, `length`, `locale`, `low`, `max`, `max_days`, `max_per_parent`, `max_step`, `min`, `min_days`, `min_per_parent`, `null_propagation`, `op`, `order_by`, `other_mode`, `pad_length`, `prefix`, `reference_column`, `reference_table`, `references`, `snapshot_file`, `source_column`, `start`, `step`, `suffix`, `value`, `value_column`, `weight_column`, `weights`, and the open map `{*}` | Step: Generate, per-type options from the EG1 catalog (`config/_tables.py:254-271`, `allOf` `if`/`then`). P1b's claim is derived from the catalog, not typed | **P1b** (needs **EG1**) |
| `pre_scan.detectors`, `pre_scan.ner_model` | Step: Scan, detectors section | **W2** |
| `post_scan.detectors`, `post_scan.ner_model`, `post_scan.ner_findings` | Step: Checks, detectors section | **W2** |
| `post_scan.integrity` | Step: Checks | **B5** |
| `post_scan.dismissed[].table`, `.column`, `.detector_id`, `.source`, `.model_id`, `.model_version`, `.strategy` | Step: findings review | **W3.2** (needs **E2**) |
| `scan_baseline.path`, `scan_baseline.schema` | Step: Scan (`starter_config` already writes both, `profiling/_starter_config.py:140-141`) | **W2** |
| `scan_baseline.on_drift` | Row 32 DRIFT | Row 32 |
| `relationships[].parent.table`, `.parent.columns`, `.children[].table`, `.children[].columns`, `.orphan_policy`, `.namespace` | Step: Relationships | **P2** (needs **EG5**) |
| `namespaces.{}.declared_by` | Hand: spec 7; relationships bind one shared namespace through E1 | none |
| `subset.seeds[].table`, `.mode` (`filter`, `sample`), `.predicates[].column`, `.predicates[].op`, `.predicates[].value`, `.count`, `.fraction` | Step: Subset | **P3** |
| `subset.budget.max_total_rows`, `subset.budget.max_table_seed_multiple` | Step: Subset (defaults shown, Enter keeps them) | **P3** |
| `subset.seeds[].keys`, `.key_columns`, `subset.edge_directions`, `subset.allow_dangling` | Hand: spec 7 (`keys` mode, edge directions, dangling) | none |
| `validators[].name`, `.columns`, `.params.{*}` | Step: Checks, from the EG2 catalog | **B5** (needs **EG2**) |
| `quarantine.enabled`, `.output_path`, `.triggers` | Step: Checks | **B5** |
| `protected_quarantine.schema_version`, `.access_policy`, `.retention_seconds`, `.max_rows`, `.max_bytes`, `.required_protection` | Hand: spec 7 | none |
| `global_settings.seed`, `global_settings.mask_secret_ref` | Step: Secrets | 1a W1a.5a |
| `global_settings.post_validation`, `.fidelity_warn_threshold`, `.categorical_retention_warn_threshold` | Step: Quality | **B6** |
| `global_settings.freetext_advisory_min_avg_length`, `.freetext_advisory_min_distinctness` | Hand: tuning for the advisory that B4 and EG3 apply with the configured values; the defaults are documented | none |
| `global_settings.unconfigured_column_policy` | Hand: the wizard declares every column (CONFIG-EXPLICIT), so the policy never applies to a wizard-written pipeline | none |
| `global_settings.on_pool_exhaustion`, `global_settings.reference_date` | Hand: spec 7 | none |
| `global_settings.dp.epsilon`, `global_settings.dp.delta` | Hand: DP is gated behind a V2 certificate (decisions 2026-11-08) | none |
| `policy` (row 81 F16), quality contracts (row 69 F35), invariants (row 68 F36) | Row 81, 69, 68: not in `PipelineConfig` yet. When each lands, V0 makes it add an entry | Rows |
| Postgres source (64b), Postgres target (86), SFTP target (87) | Row: each adds a location kind (5.1) | Rows |

### 1.3 CI manifest leaves (`CiManifest`, `src/decoy/ci/contracts.py:615`)

| Leaves | Entry | Slice |
|---|---|---|
| `schema_version`, `pipelines[].id`, `pipelines[].path` | Step: Review, CI offer | **C1**, **C2** |
| `checks.validation.enabled`, `.mode`, `.pipelines`, `.fail_on_warning` | Step: Review, CI offer (8.3 rules) | **C2** |
| `checks.evidence[].id`, `.manifest` | Step: Review, CI offer, only when the run command has `--evidence-out` | **C2** |
| `checks.drift[].id`, `.baseline`, `.current`, `.blocking` | Hand: needs a "current" scan file that a CI job produces outside `decoy-ci`; documented in `docs/ci-contracts.md` | none |
| `checks.regression_suites[].id`, `.suite` | Hand: the loader refuses them until a public F12 runner exists (`contracts.py:538`) | none |
| `staged_scan.*` | Hand: the patterns are raw secret-like literals and must not pass through prompts | none |

### 1.4 `decoy run` flags (`src/decoy/cli/run/__init__.py`)

The printed next command comes from one builder (RC, 5.6). Each flag is either set by a step or
named as a per-run choice.

| Flag | Entry | Slice |
|---|---|---|
| `--mode` | Step: Goal (mask, generate or mixed) | **RC** |
| `--duckdb-source TABLE=DB_PATH` | Step: Sources, DuckDB sub-flow | **B3** |
| `--fidelity`, `--post-validate`, `--post-validate-enforce` | Step: Quality | **B6** |
| `--vault PATH` | Step: Secrets, Tokenize branch | **T1** |
| `--master-key`, `--key-label` | Step: Secrets, Generate branch (reference only, never a key value) | **P1b** |
| `--mask-secret` | Not printed: the Secrets step writes `global_settings.mask_secret_ref` instead | 1a |
| `--evidence-out PATH` | Step: Review, offered with the CI evidence check | **C2** |
| `--notify`, `--notify-on` | Hand: destinations are webhook URLs and addresses the wizard does not collect | none |
| `--chunked`, `--chunk-size`, `--native`, `--no-native`, `--threads`, `--max-memory`, `--otel-endpoint`, `--explain-plan`, `--rows`, `--out-dir`, `--all`, `--no-subset`, `--json`, `--quiet`, `--verbose` | Per-run: they change how one run executes, not what the job is | none |

### 1.5 Commands and flags of `decoy init` itself

| Surface | Slice |
|---|---|
| `--answers`, `--save-answers`, `--fail-on-warning` | **P4** |
| `--skip`, `--only`, `--no-validate`, `--diff` | **P5** |
| `decoy edit <section> <pipeline>` | **P7** (needs W3.1, W3.1b) |
| Drafts, `q` to save and quit, `--resume` | **B7** |
| Preset pre-fill of the steps | **B8** |

### 1.6 Gaps found

1. DuckDB tables have no wizard path. Slice **B3**.
2. `delivery.mode` and the S3 and GCS `region`, `endpoint_url`, `credentials_ref` keys. **B2**.
3. The generate catalog has names and required options but no wire types or examples. **EG1**.
4. No public validator list (`validators/_registry.py:63` `_REGISTRY` is private). **EG2**.
5. No per-column free-text or high-cardinality fact (spec 16.14). **EG3**.
6. Vault eligibility is a private predicate in `check_vault_columns`
   (`plan/_checks_correctness.py:154`). **EG4**.
7. No relationship candidates: `relationship_template` holds only table names
   (`profiling/_starter_config.py:148`). **EG5**.
8. No CI manifest writer. **C1**, **C2**.
9. The YAML editor has no owner for block, key, map-entry and list-append spans. **W3.1b**.
10. No single builder for the printed run command. **RC**.
11. Later V1 rows add config surface, and nothing makes them add a wizard entry. **V0**.

## 2. Guarantees and non-goals

### 2.1 Properties that must always hold

- G1. Every leaf of `PipelineConfig`, every leaf of `CiManifest` and every `decoy run` option has
  exactly one coverage entry. A Step entry is claimed by a production step object. Any schema
  keyword the walker does not handle fails the sentry. (V0)
- G2. No input data value, secret value, credential, bucket name, key, endpoint, DB path, DSN or
  exception text reaches any wizard surface (section 9.5) except the allow-list:
  - `validators[name=column_in_set].params.allowed_values` for a field the user confirmed (H2
    rule, spec 4.5);
  - subset predicate values the user typed (`subset.seeds[].predicates[].value`);
  - snapshot `top_values` of unflagged categorical columns written by the fit (P1a), under the
    same `value_policy` and `allow_real_categories` opt-in notice as `decoy fit`
    (`cli/fit.py:14-18`).
  Each allow-listed value may appear only in the pipeline, the snapshot file, the draft and the
  answers file (all owner-only except the pipeline), never in stdout summaries, `-v` logs,
  `--json` or error text.
- G3. Every file the wizard writes or edits has one owner object and one exit-path matrix. A
  failed write leaves the earlier file byte for byte unchanged.
- G4. A YAML file the wizard edits changes only inside the spans the user changed. Every other
  byte stays the same, comments included (G-ONE-EDITOR).
- G5. Every new pipeline YAML comes from the one emitter `cli/_scaffold_yaml.render`
  (G-ONE-EMITTER). The CI manifest has one writer, `src/decoy/ci/emit.py`, the one named
  exception (5.3).
- G6. Menus come from engine registries: strategies, generate types, validators, detectors,
  vault eligibility, review flags and relationship candidates. The CLI keeps no hand list of any
  of them.
- G7. Answers and drafts are versioned, strict and created owner-only. An unknown major, a
  missing tag or a lax-typed value is refused with a registered `init.*` code.
- G8. The wizard uses only the six public exit codes.
- G9. Every user-typed identifier the wizard checks (step ids for `--skip` and `--only`, CI
  pipeline ids, table names) is checked with `re.fullmatch` (recurring defect 1).

### 2.2 Non-goals

- Arrow keys, `prompt_toolkit`, before and after previews (V2, owner).
- New config kinds. DuckDB stays a run flag (Q5).
- Postgres and SFTP prompts. Their rows own them.
- Hostile in-process evasion of the sentries (V2-LOG, catalog class 5 scope rule).

## 3. Changes the Phase 1a builders must apply (rebase delta)

Dennis confirmed D1 to D7 against main.

| # | Fact on main now | 1a slice it changes | Amendment |
|---|---|---|---|
| D1 | `cli/init.py` is 742 lines (1a assumed about 690) and has PROJECT-LAYOUT: a `NAME` or `FILE` token, `--source`, default `pipelines/NAME/pipeline.yaml`, `-o` outside a project | W1a.0, W1a.6a, W1a.6b | AT-W1 characterization adds the NAME, `--source`, in-project and outside-project cases. The `init.py` size pin starts at its size on the W1a.0 base and only shrinks. The Start step takes the pipeline path from `decoy.cli.project` (`resolve_destination`) |
| D2 | Outputs default to a bare target `<stem>.masked.<ext>` placed in a run folder (`cli/io/_layout.py`) | W1a.5a | The Output default is the project scaffold's target, not `out/<table>.masked.<ext>`. AT-W25 changes its expected default |
| D3 | `--preset generate` with a FILE fits a snapshot through `decoy.cli.gen.scaffold_generate` | W1a.1 | The preset path keeps that behavior through the Prompter |
| D4 | P3, P4, P5 (CONFIG-EXPLICIT) merged; P6 `scan_sources` and P7 `starter_config` are on engine main; P9 `apply_review` is not; the CLI pins engine 0.27.0 | section 2 | Mark P3 to P7 and P10 met; P9 (E1) open. R-1a is the next engine release after E1 |
| D5 | The post-scan report is `post-scan-integrity/v3` | none in 1a | W3.2 reads v3 and v2 (7.6) |
| D6 | Owner-only file creation has one home, `src/decoy/_private_file.py` (`create_private_exclusive`) | none in 1a | B7 and P4 use it. The record plan's `mode` argument on `_atomic.write_local_target` is dropped |
| D7 | `src/decoy/cli/io/` holds the layout services and the cloud root check | W1a.6a | The path-role check calls `decoy.cli.io` for placement and the collision rule |

## 4. Reuse inventory

| Need | Reuse | Where |
|---|---|---|
| Step loop, state, stale marking, Prompter, tree, field review, write step | Phase 1a modules | `src/decoy/cli/wizard/` (after W1a.6b) |
| Reason codes | central registry from W1a.0 | `src/decoy/_reason_codes.py` |
| Owner-only files | `create_private_exclusive`, `open_private` | `src/decoy/_private_file.py:168,200` |
| Atomic replace | `_atomic.write_local_target` | `src/decoy/_atomic.py:199` |
| YAML marks | index in `ci/locations.py`, moved by Y0 | `src/decoy/_yaml_marks.py` (target) |
| `.gitignore` | `write_decoy_gitignore`, the one writer; B5 adds `append_gitignore_line` beside it | `src/decoy/cli/io/_project.py:236` |
| Run folders, quarantine placement, scratch | `RunLayout`; `.decoy/scratch/` is already ignored (`DECOY_DIR_GITIGNORE`, `_project.py:35`) | `src/decoy/cli/io/_layout.py:465` |
| Cloud root rules | `cloud_root_issues` | `src/decoy/cli/io/_cloud.py` |
| Snapshot fit for Generate | `fit_exact_snapshot` and the snapshot layout (not `scaffold_generate`, which owns its own publish and exits through `_fail`, `gen/_scaffold.py:196-260`) | `src/decoy/cli/gen/_fit.py:65` |
| DuckDB staging | `acquire_relation`, `describe_relation`; B3 adds a sample option | `src/decoy/cli/_duckdb_source.py:76,87` |
| Value-free scan record | `ScanSetCore` (the one value-free core) | engine `profiling/scan_set.py:11` |
| Relationship facts | `relationship_facts` | engine `profiling/_scan_integrity.py:176` |
| Join-safe key rule, column entries | E1 `column_entry`, `apply_review` | engine (1a plan 6.1) |
| Keyed fields | `keyed_columns_for_config` (E3, merged) | engine |
| Fixed-width overflow | the writer refuses overflow before anything is published | engine `profile/_fixed_width_writer.py:22,140` |
| NER model status | `decoy.cli.models._status` | `src/decoy/cli/models/` |
| CI manifest model and loader | `CiManifest`, `ci/manifest.py` | `src/decoy/ci/` |
| Gate before write | `write_blocking_findings` (1a W1a.6a) | `src/decoy/cli/gate/_layers.py` |
| Module size, fan-out, CODEMAP path sentries | existing | `tests/sentry/layout/` |

New machinery and the reason for each: the coverage sentry (no guard ties config fields to the
wizard), the location-kind table (four rows add kinds), the run-command builder (four steps add
flags), the CI writer (none exists), the editor spans (three slices need them).

## 5. Design notes

### 5.1 Location kinds (B2)

`cli/wizard/steps/_locations.py` holds one table: kind id, prompts, `to_block`, `config_paths`
and the roles it may fill (source, target or both). B2 refactors `steps/sources.py` and
`steps/output.py` from 1a to dispatch through the table, so local file moves into it too. Rows:
local file, S3, GCS, DuckDB (source only). Rows 64b, 86 and 87 each add one row. S3 and GCS take
bucket, key or object, region and endpoint, and a `credentials_ref` given as `env:NAME` or
`file:PATH` (checked with `re.fullmatch`). No credential value is asked.

### 5.2 The coverage sentry (V0)

Path claims are on the production step objects: every Step in `STEPS` and every location row
has `config_paths: frozenset[str]` (schema path patterns). P1b's claim is computed from the EG1
catalog. The sentry data module `tests/sentry/wizard/_config_coverage.py` holds only the Hand
entries (path, reason) and Row entries (path, row id). Step entries are not repeated there.

The walker covers three sources:

1. `PipelineConfig.model_json_schema()`;
2. `CiManifest.model_json_schema()`;
3. the Click parameters of the `decoy run` command (names of every option), checked against the
   run-flag table (`_run_command.FLAG_COVERAGE`, 5.6).

Walker rules (fail closed):

- it resolves `$ref`, `anyOf`, `oneOf`, `allOf`, `if`, `then`, `else`, `items`, `prefixItems`,
  `properties` and `additionalProperties` given as a schema;
- `additionalProperties: true` makes an open-map leaf `{*}` that needs its own entry;
- any other structural keyword (`patternProperties`, `not`, `dependentSchemas`,
  `unevaluatedProperties`, `contains`, `propertyNames`) is red unless a named entry covers that
  path.

Row entries:

- a surface that row 32b itself has not built yet is `Row("32b")`. Each slice turns its rows into
  Step claims as it lands. Row 32b cannot close while any `Row("32b")` remains;
- a Row entry names a row id that must exist in `docs/ROADMAP.md`. The sentry reads the row's
  state cell and compares it with an explicit token list: done tokens `MERGED`, `DONE`,
  `SHIPPED`; open tokens `NOT STARTED`, `PLANNED`, `PLAN`, `BUILDING`, `IN PROGRESS`, `BLOCKED`,
  `PARKED`. A done row with a Row entry is red. An unknown token or a missing row is red.

### 5.3 The CI manifest writer (C1, C2)

`src/decoy/ci/emit.py` (public module, like `ci/manifest.py`) has
`render_manifest(pipelines, checks) -> bytes`. It takes only `pipelines` and `checks`, so a
`staged_scan` block cannot be written by construction. It writes `schema_version: decoy-ci/v1`
and loads the bytes back through `ci/manifest.py` before it returns them.

G-ONE-EMITTER covers pipeline YAML. `ci/emit.py` is its one named exception: another document
type with its own strict loader that proves the round trip. The G-ONE-EMITTER sentry lists
`(src/decoy/ci/emit.py, render_manifest)` as the one allowed exception by exact identity, and a
seeded case (a second `yaml.safe_dump` caller in `src/decoy/ci/`) must be red.

C2 rules for an existing manifest are in 7.5.

### 5.4 DuckDB (B3)

B3 adds `sample_rows: int | None` to `acquire_relation`. With a value, the COPY selects
`USING SAMPLE <n> ROWS`; without one, behavior is unchanged for `decoy run`. The wizard stages the
sample to a private directory: `.decoy/scratch/init-duckdb-<pid>/` inside a project (already
ignored), or a 0700 directory from `_private_file` outside one. It scans and removes it on every
exit. On the next start the wizard sweeps stale `init-duckdb-*` directories whose pid is gone.

`DuckDBSourceError` messages carry the DB path and relation name. The wizard never shows them: it
catches `DuckDBSourceError` and raises the value-free `init.source_unreadable` (table name only)
after the `except` block closes (recurring defect 3). The YAML declares the table with no
`sources` entry, which is what `decoy run --duckdb-source` expects.

### 5.5 Tokenize (T1, EG4)

EG4 adds `vault_eligible: bool` to `StrategyInfo`, set on each handler, and rewrites
`check_vault_columns` to read it. T1 shows `tokenize` in the tree only when Tokenize is in the
goal (spec 5.4.3). It offers "also store originals in the vault" only on `vault_eligible`
strategies. Both set a namespace through E1 `column_entry`. Secrets then asks for the vault path.
The default is never inside the repository tree. A chosen path inside a git work tree that git
does not ignore gets a warning and the `.gitignore` offer.

### 5.6 The run command builder (RC)

`cli/wizard/_run_command.py` owns `RunFlag`, a closed enum of the flags a step may contribute
(the Step rows of 1.4), and `FLAG_COVERAGE`, which maps every `decoy run` option to a `RunFlag`
or a per-run or Hand reason. Steps return `RunFlag` facts; one function renders the command for
the Review screen, the checklist and `--json`. `--chunked` is not a `RunFlag`, so the wizard can
never print `--chunked` with `--vault`. Paths in the printed command are the user's own answers.

### 5.7 Project layout first (B5, B7)

Inside a project, quarantine `output_path` is a relative path that `RunLayout` places in the run
folder, and drafts go to `.decoy/scratch/` (already ignored). The `.gitignore` offer appears only
outside a project, or for a user-chosen path that git does not ignore.

## 6. Construction rules (sentries)

- C1 (V0). Config coverage, as 5.2.
- C2 (B2). Location kinds: every source and target `type` literal maps to one location row or to
  a Row entry.
- C3 (B5, P1b). No catalog-name literal in comparing positions in `src/decoy/cli/wizard/`.
  Covered spellings: a string literal equal to a validator name, generate type name or strategy
  name used as an operand of `==`, `!=`, `in`, `not in`, as a `match` case, as a dict key or set
  or tuple member in a module-level constant, or as a call argument to a `Prompter` menu. Prompt
  text and docstrings are not comparing positions. Extends the 1a no-strategy-literal sentry.
- C4 (B7, P4, B3). One write path for wizard files. An AST sentry over `src/decoy/cli/wizard/`
  and `src/decoy/ci/emit.py` flags `open(` with a mode containing `w`, `a`, `x` or `+`,
  `Path.write_text`, `Path.write_bytes`, `Path.open` with a write mode, `os.open` with
  `O_WRONLY`, `O_RDWR` or `O_CREAT`, `os.replace`, `os.rename`, `shutil.copy*`, `shutil.move`
  and `tempfile.NamedTemporaryFile` (covered spellings, including `from x import y` and aliases,
  through the G-ONE-GATE resolver). The allowed helpers, by exact `(path, name)`, are
  `_private_file.create_private_exclusive`, `_private_file.open_private`,
  `_atomic.write_local_target`, `cli/io/_project.append_gitignore_line` and the W3.1 editor's
  `apply_edits`. Callers of `apply_edits` are checked too (catalog class 10): only
  `cli/wizard/_edit.py`, `_ci_step.py` and `_findings.py` may call it.
- C5 (B5). One `.gitignore` writer home: `src/decoy/cli/io/_project.py`. The existing
  `.gitignore` sentry scope (or a new one in `tests/sentry/io_policy/`) fails on any other
  `.gitignore` write under `src/decoy/`.
- C6 (C1). One CI manifest writer, `src/decoy/ci/emit.py`; G-ONE-EMITTER lists it as the one
  exception (5.3).
- C7 (P4). Route parity: every entry in `STEPS` has an `answers_model`; a step with no model is
  red.

## 7. Slices: guarantees, failure modes, acceptance tests, mutations

Test IDs are `AT-<slice>.<n>`. Every AT is written red first. "Mutation" names the change that
must turn the test red; it runs on the final head (recurring defect 9). Every new step slice also
adds its surfaces and its Step claims, with a per-step AT: answers built from catalog examples
produce YAML whose leaves equal the step's `config_paths` (each claim is reached, nothing outside
is written).

### 7.1 Engine slices

**EG1. Generate type catalog: wire types and examples (spec 16.7).** R1, engine, ~350.

- Guarantee: `generate_option_catalog()` gives, for every option of every type, a wire type
  token (`str`, `int`, `float`, `bool`, `list[str]`, `mapping`, `column_ref`, `expression`) and
  one example that validates. It also lists the options common to all types.
- Failure modes: a type or option without a wire type; an example that does not validate; a
  free-string token.
- AT-EG1.1: for each type, a `GenerateColumnConfig` from the required options' examples
  validates. Mutation: change one example to a wrong type, red.
- AT-EG1.2: catalog types equal the `GenerateColumnConfig.type` literals; catalog options per
  type equal the schema's `if`/`then` properties for that type. Mutation: drop one option, red.
- AT-EG1.3: the wire type is a closed enum; a string outside it is refused (recurring 4).
- Starts now.

**EG2. Public validator catalog (spec 16.8).** R1, engine, ~350.

- Guarantee: `validator_catalog()` exported from `decoy_engine` lists every registered validator
  with name, `columns` arity, params (name, wire type, required, example) and a one-line
  description. It is derived from `_REGISTRY`, which stays private.
- Failure modes: a validator registered without catalog metadata; a catalog entry with no
  function; a params example that fails the validator's own check.
- AT-EG2.1: catalog names equal `_REGISTRY` keys. Mutation: register a validator without
  metadata, red.
- AT-EG2.2: every example builds a `ValidatorEntry` that passes config validation.
- AT-EG2.3: export snapshot updated (additive).
- Starts now.

**EG3. Per-column review flags (spec 16.14).** R1, engine, ~350.

- Guarantee: `column_review_flags(stats, config) -> frozenset[ReviewFlag]` takes one column's
  scan stats and the config. `ReviewFlag.FREE_TEXT` uses the same scorer and the configured
  thresholds as `score_unmasked_freetext`. `ReviewFlag.HIGH_CARDINALITY` reads the engine's own
  `high_cardinality` stat (`profiling/_snapshot_values.py:354,455`). The CLI copies neither rule.
- Failure modes: a second threshold reader; the per-column answer differs from the run-time
  advisory; a value in the result.
- AT-EG3.1 (parity): over a corpus, with default thresholds and with non-default
  `freetext_advisory_min_avg_length` and `freetext_advisory_min_distinctness` cells, the
  per-column flag equals the run-time advisory's set. Mutation: hard-code the default threshold,
  red (the non-default cells catch it).
- AT-EG3.2: `HIGH_CARDINALITY` equals the stat for each corpus column. Mutation: recompute the
  share locally, red on the boundary cell.
- AT-EG3.3: the result holds flags only, no values.
- Starts now.

**EG4. Vault eligibility in the strategy catalog.** R2, engine, ~300.

- Guarantee: `StrategyInfo.vault_eligible` exists for every strategy, and `check_vault_columns`
  reads it. `fpe` and `passthrough` are not eligible, as today.
- AT-EG4.1: for every strategy, `check_vault_columns` on a one-column config with `vault: true`
  passes exactly when `vault_eligible` is true. Mutation: flip `fpe` to eligible, red.
- AT-EG4.2: a handler without the attribute fails G-CATALOG.
- Depends on E1 (same catalog files).

**EG5. Value-free relationship candidates.** R2, engine, ~500.

- Guarantee: `relationship_candidates(sources, scan_set) -> tuple[RelationshipCandidate, ...]`.
  Each candidate has parent (table, columns), child (table, columns) and evidence:
  `name_match: bool`, `parent_unique: bool`, `overlap: Literal["high", "partial", "none",
  "skipped_cloud"]`. The engine computes key-name matches and value overlap in protected scratch
  (the `relationship_facts` route) and returns no value.
- Failure modes: a cell value or exception text in a candidate or error; cloud ends read; unbounded
  memory on a large child.
- AT-EG5.1: a seeded corpus with single, composite and self-referencing keys gives the expected
  candidates. Mutation: drop the overlap check (name match only), red on the decoy column.
- AT-EG5.2: canary values in key columns never appear in candidates, errors or logs.
- AT-EG5.3: a cloud end gives `skipped_cloud` and reads nothing.
- Starts now. Released with R-1b. Owner question Q11 (taken as recommended).

**E2.** As in the record plan (4.6, AT-E5, ~420, R2), reading report v3 fields. Starts now.

**E1.** As in the 1a plan (6.1). Starts now.

### 7.2 Independent CLI slices (can start before S3a.1)

**Y0. Move the YAML mark index to `src/decoy/_yaml_marks.py`.** R1, CLI, ~250.

- Guarantee: `ci/locations.py` imports the index from the new module and keeps its public names.
  No re-export shim is left beyond the names `ci/locations.py` already exports.
- AT-Y0.1: existing `ci` location tests, unchanged. Mutation: off-by-one on a line mark, red.
- AT-Y0.2: CODEMAP row "Shared YAML document structure and source-mark indexing" added; the
  CODEMAP path sentry passes.

**C1. CI manifest renderer.** R1, CLI, ~300.

- Guarantee: 5.3.
- Failure modes: output the loader refuses; key order not stable; an id that only passes a
  `$`-anchored check.
- AT-C1.1 (round trip): property test over generated `pipelines` and `checks` values. Mutation:
  drop `fail_on_warning` from the output, red.
- AT-C1.2: G-ONE-EMITTER exception by exact identity; a second dumper caller in `src/decoy/ci/`
  is red.
- AT-C1.3 (golden): one two-pipeline manifest, byte golden, with `schema_version`.
- AT-C1.4: an id `"ok\n"` is refused before rendering (fullmatch).
- Consumer: C2 (proportionality exception; C2 lands before row 32b closes).

### 7.3 Phase 1b slices

All depend on W1a.6b unless stated. Each extends the privacy test (spec 15) with its surfaces.

**V0. Coverage sentry.** R1, CLI, ~500.

- Guarantee: G1, 5.2.
- Failure modes: the walker misses `if`/`then`, `allOf`, open maps or list items; a stale Hand
  entry; a Row entry for a done row; an unknown roadmap state token.
- AT-V0.1 (walker cells): a fixture schema with nested models, a discriminated union, `allOf`
  with `if`/`then` per-type options, an open map, a list of models and a map of models; each leaf
  is found. Non-vacuity: 184 leaves on the real `PipelineConfig` at the V0 base, compared with a
  count computed in the test, not pinned.
- AT-V0.2: a field added to a fixture copy, red. Mutation: delete one Hand entry, red.
- AT-V0.3: an unhandled keyword (`patternProperties`) in a fixture, red.
- AT-V0.4: a Step claim naming a path not in the schema, red; a Hand entry for a missing path,
  red.
- AT-V0.5: a Row entry for a row whose state is `MERGED`, red; an unknown state token, red; a
  missing row id, red.
- AT-V0.6: a `decoy run` option missing from `FLAG_COVERAGE`, red; a `CiManifest` leaf with no
  entry, red.

**RC. Run command builder.** R1, CLI, ~250.

- Guarantee: 5.6.
- AT-RC.1: Goal facts give `--mode` for mask, generate and mixed.
- AT-RC.2: no step can contribute a flag outside `RunFlag`; `--chunked` never appears, including
  with `--vault`. Mutation: add `CHUNKED` to the enum, red.
- AT-RC.3: the Review screen, the checklist and `--json` show the same command.

**B1. Fixed-width sources and targets.** R1, CLI, ~450.

- Guarantee: Sources offers fixed width with a column ruler (spec 5.2); the user types widths or
  start positions; the engine validates `layout` before Scan. Output offers `fixed_width` and
  copies the layout. Overflow: the wizard warns at Review when a chosen strategy is not
  passthrough on a fixed-width target column, and names the layer that catches overflow: the
  engine writer refuses a value wider than its column before anything is published
  (`profile/_fixed_width_writer.py:22,140`).
- Failure modes: overlapping fields accepted; real values in the ruler with `--no-samples`;
  partial output after overflow.
- AT-B1.1: scripted three-field layout; YAML validates and round-trips.
- AT-B1.2: overlapping widths refused with the engine reason; no write.
- AT-B1.3: `--no-samples` ruler shows shapes only. Mutation: pass raw rows to the ruler, red.
- AT-B1.4: a wizard-built fixed-width target with a widening strategy fails at run with the
  writer's overflow reason and no target file exists after the run.
- AT-B1.5: changing the layout marks Scan and Fields stale.

**B2. Location kinds, S3 and GCS, delivery mode.** R2, CLI, ~500.

- Guarantee: 5.1. `steps/sources.py` and `steps/output.py` dispatch through `_locations.py`.
  `delivery.mode` is asked when any target is cloud (default `strict`). The gate's
  `cloud_root_issues` runs before write.
- Failure modes: bucket, key, endpoint or credentials ref text in an error, log or `--json`; a
  split delivery root accepted; a credential value accepted (`credentials_ref` not a reference).
- AT-B2.1: scripted S3 source and GCS target session with region and endpoint; YAML validates.
- AT-B2.2: a split root is refused with a `layout.*` reason through `write_blocking_findings`.
- AT-B2.3: bucket, key and endpoint canaries never appear in `-v` logs, `--json` or error text.
  Mutation: include the key in the summary line, red.
- AT-B2.4: `credentials_ref` values `AKIA...`, `env:`, `env:A\n` are refused; `env:AWS_PROFILE`
  and `file:creds.json` pass (fullmatch).
- AT-B2.5 (C2): every kind literal maps to a location row or a Row entry. Mutation: remove the
  GCS row, red.
- AT-B2.6 (characterization): the 1a local-file sessions produce the same YAML after the
  dispatch refactor.

**B3. DuckDB tables.** R1, CLI, ~400.

- Guarantee: 5.4.
- Failure modes: staged files left; the whole relation copied for a sample; the DB path or
  relation in output; a `sources` entry written.
- AT-B3.1 (exit-path matrix): success, cancel at each later step, scan error, gate refusal, write
  error, interrupt; the staging directory is gone after each. Mutation: skip cleanup on cancel,
  red.
- AT-B3.2: with `sample_rows`, the staged file has at most that many rows; `decoy run` without it
  is unchanged (existing duckdb tests green).
- AT-B3.3: a stale `init-duckdb-*` directory with a dead pid is removed on the next start; one with
  a live pid is kept.
- AT-B3.4: a missing DB file and a bad relation give `init.source_unreadable` with the table name
  only; the path canary is absent; `__context__` is None.
- AT-B3.5: the YAML has no `sources` entry for the table, and the printed command (RC) includes
  `--duckdb-source TABLE=DB_PATH`; `decoy run` with it validates the pipeline.

**B4. Flagged-only field review.** R2, CLI, ~400.

- Guarantee: spec 5.4.1. A field is flagged when the scan found it, was unsure, or EG3 returns
  `FREE_TEXT` or `HIGH_CARDINALITY`. Unflagged fields take one bulk strategy. Review shows the
  count kept unchanged without review and needs an explicit confirm.
- AT-B4.1: a short identifier no detector matches but EG3 flags is reviewed one at a time.
  Mutation: drop the EG3 term, red.
- AT-B4.2: Review refuses to write until the confirm when any bulk `passthrough` field exists,
  in terminal, answers and resume routes.
- AT-B4.3: no unique-share constant in `cli/wizard/` (the flag comes from EG3).
- Depends on EG3 repinned.

**B5. Checks step.** R2, CLI, ~500.

- Guarantee: Checks writes `post_scan.integrity`, `validators` from EG2, and `quarantine`. The H1
  rule warns that quarantine holds unmasked rows; inside a project the path is placed in the run
  folder (5.7); outside a project it offers a `.gitignore` line through
  `decoy.cli.io.append_gitignore_line`. The H2 rule shows `column_in_set` allowed values only on a
  confirmed field.
- Failure modes: validator names typed in the CLI; the `.gitignore` rewritten; allowed values in
  logs.
- AT-B5.1: every catalog validator can be added from its example; the YAML validates.
- AT-B5.2 (C3): a validator name in a comparing position in `cli/wizard/`, red, one seeded case
  per covered spelling.
- AT-B5.3: `append_gitignore_line` on a file with comments and no trailing newline adds one line;
  other bytes equal; a second call adds nothing; a symlinked `.gitignore` is refused. Mutation:
  rewrite joined lines, red.
- AT-B5.4 (C5): a `.gitignore` write outside `cli/io/_project.py`, red.
- AT-B5.5: allowed-values canaries never in `-v` logs, `--json` or the summary.
- AT-B5.6: inside a project the quarantine path is relative and placed by `RunLayout`; no
  `.gitignore` offer.

**B6. Quality step.** R1, CLI, ~300.

- Guarantee: writes `post_validation`, `fidelity_warn_threshold`,
  `categorical_retention_warn_threshold`; contributes `--fidelity`, `--post-validate` or
  `--post-validate-enforce` to RC when chosen.
- AT-B6.1: scripted session; YAML validates. AT-B6.2: a value outside the engine's range is
  refused with the engine reason. Mutation: skip validation before write, red.

**B7. Drafts and resume.** R2, CLI, ~500.

- Guarantee: spec 10. `q` saves the draft (`decoy-init-draft/v1`) owner-only. Inside a project it
  goes to `.decoy/scratch/`; outside, beside the pipeline with a `.gitignore` offer. The draft
  stores scan results only as the engine's `ScanSetCore` (value-free) plus the answers.
  `--resume` loads it strictly. The draft is removed after a successful write.
- Source fingerprint: per source, SHA-256 over (kind, normalized location, declared column names,
  and for a local file its size and `mtime_ns`; for DuckDB the DB file's size and `mtime_ns` and
  the relation's column names from `describe_relation`; for S3 and GCS the column names from a
  header read). A mismatch refuses the resume with `init.draft_stale` and offers a fresh scan.
- Failure modes: lax types read; unknown major accepted; sample values in the draft; the draft
  left after success; a draft for a changed source accepted.
- AT-B7.1: round trip equals the state. AT-B7.2: next major, missing tag, `true` for an int,
  `"5"` for an int each refused with `init.draft_invalid`; `__cause__` and `__context__` None.
- AT-B7.3: canaries planted in `top_values`, `min_value`, `max_value` never in the draft.
  Mutation: store the detailed profile instead of `ScanSetCore`, red.
- AT-B7.4 (exit matrix): success removes the draft; cancel keeps the last draft; failed write
  keeps the old draft unchanged.
- AT-B7.5: touching the source file (new `mtime_ns`) or renaming a column gives
  `init.draft_stale`. Mutation: drop `mtime_ns` from the fingerprint, red.
- AT-B7.6 (C4): one seeded case per covered write spelling in `cli/wizard/`, red; the allowed
  helpers pass; a call to `apply_edits` from another module, red.

**B8. Preset pre-fill.** R1, CLI, ~250.

- Guarantee: a preset at Start pre-fills Goal, Checks and Quality with origin `preset`; the
  written YAML for an unchanged preset session equals today's preset output.
- AT-B8.1: per template, the unchanged session output equals the template output (golden).
  Mutation: drop one pre-filled answer, red.

### 7.4 Phase 2 slices

**P1a. Goal multi-select and generate from a snapshot.** R2, CLI, ~400.

- Guarantee: Goal offers Mask, Generate, Subset, Tokenize (Tokenize enabled by T1). Per table the
  user picks mask or generate. A generated table fitted from a snapshot calls
  `fit_exact_snapshot`, writes the snapshot in the same layout as `decoy init --preset generate`
  through `_atomic`, and renders the config through the shared renderer. It shows the same
  withheld-values policy and `allow_real_categories` opt-in notice as `decoy fit`.
- Failure modes: a copied fit; real categories written without the notice; the snapshot written
  and the pipeline write failing (orphan snapshot).
- AT-P1a.1: off then on restores answers.
- AT-P1a.2: `fit_exact_snapshot` is the only fit call in `cli/wizard/` (import sentry). Mutation:
  call a copied fit, red.
- AT-P1a.3: the snapshot equals the preset route's snapshot for the same file; flagged columns
  are withheld; unflagged `top_values` canaries never appear in stdout, `-v` or `--json`.
- AT-P1a.4: pipeline write fails, snapshot removed (one publish order, both or neither).

**P1b. Generate column editor.** R1, CLI, ~500.

- Guarantee: per column the user picks a type from EG1 and fills required options by wire type;
  common options (`null_probability`, `determinism`, `output_type`, `pooled`, `unique`) are
  offered; `row_count` and `unique_together` per table; the Secrets step's Generate branch asks
  `--master-key` as a reference and `--key-label` (RC).
- AT-P1b.1: every catalog type can be configured from catalog examples (per-step AT).
- AT-P1b.2 (C3): a generate type name in a comparing position, red.
- AT-P1b.3: `required_when` and `one_of` enforced from the catalog. Mutation: ignore
  `required_when`, red.
- AT-P1b.4: `unique_together` naming a missing column is refused with the engine reason.
- Depends on EG1 repinned.

**P2. Relationships step.** R2, CLI, ~500.

- Guarantee: spec 5.5. Candidates come from EG5 only; the CLI does no matching. The user
  confirms, edits or adds. Composite keys keep column order. Key fields end with one shared
  namespace and a `join_safe` strategy through E1 `apply_review`. `orphan_policy` asked.
  `relationship_facts` runs on local sources before write.
- FK shapes: section 9.3.
- AT-P2.1a: one scripted case per accepted shape; each validates.
- AT-P2.1b: a key-node cycle is refused with the engine's `FK_CYCLE` reason
  (`relationships/_graph.py:300-310`).
- AT-P2.1c: a cross-table cycle (not a key-node cycle) is accepted and written; the Review screen
  states the run takes the full-frame route (`CROSS_TABLE_CYCLE`,
  `execution/_pipeline_routing.py:484,507`). Mutation: refuse all cycles, red.
- AT-P2.2: `redact` on a key is refused until a join-safe strategy is chosen. Mutation: skip
  `apply_review`, red.
- AT-P2.3: confirming a relationship marks Fields stale.
- AT-P2.4: a cloud end reports `skipped_cloud`, not "no orphans".
- Depends on EG5 repinned.

**P3. Subset step.** R2, CLI, ~450.

- Guarantee: seeds of mode `filter` (ops from the engine literal) and `sample` (`count` or
  `fraction`), and `budget`. Parquet sources are checked before the step (engine reason
  `subset_requires_parquet`). Predicate values are allow-listed data (G2).
- AT-P3.1: filter and sample sessions validate; `decoy subset --dry-run` accepts the result.
- AT-P3.2: a CSV source with Subset in the goal is told before the step. Mutation: skip the
  check, red.
- AT-P3.3: a seed naming a removed table is marked stale.
- AT-P3.4: a predicate value canary appears in the pipeline, draft and answers only, never in
  `-v` logs, `--json`, the summary or error text.
- Depends on P2, P1a.

**P4. Answers files.** R2, CLI, ~500.

- Guarantee: record plan 4.4. `decoy-init-answers/v1` strict model built from each step's
  `answers_model` (C7). `--answers FILE` runs with no prompts. `--save-answers FILE` creates the
  file owner-only through `create_private_exclusive`. `unlisted: skip|confirm`; a stale confirm
  raises `pre_scan.review_stale`; `--fail-on-warning` maps warnings to exit 2.
- The schema is not frozen at P4. Later slices add their step models. The snapshot is taken and
  frozen when row 32b closes (M3).
- AT-P4.1: every step's answers round-trip; an answers run equals the terminal run.
- AT-P4.2: strict-type and version cells as AT-B7.2, with `init.answers_invalid`.
- AT-P4.3: an existing file is not overwritten. Mutation: replace mode, red.
- AT-P4.4 (C7): a step without `answers_model`, red.
- Depends on Y0.

**P5. Step selection and dry flags.** R1, CLI, ~300.

- Guarantee: `--skip` and `--only` take step ids from `STEPS`, matched with `re.fullmatch`;
  `--no-validate` skips only the final engine validation and says so; `--diff` prints the YAML
  diff and writes nothing (exit 0).
- AT-P5.1: an unknown id and `"fields\n"` are usage errors (exit 1).
- AT-P5.2: `--diff` leaves the tree byte for byte unchanged. Mutation: write before diff, red.

**W3.1.** As in the record plan (4.7, ~540, R2), with D6 (no `mode` argument; owner-only files
through `_private_file`). AT-W13, AT-W14, AT-W21, G-ONE-EDITOR. The editor's write function is
`apply_edits`. Depends on Y0.

**W3.1b. Editor spans for sections and manifests.** R2, CLI, ~450.

- Guarantee: `_yaml_edit.py` gains these span kinds, each with the record plan's refusal rules
  (`init.yaml_edit_unsupported` for flow style, anchors or aliases in the span, tabs, multiple
  documents) and the hash check (`init.yaml_changed`):
  - top-level block span; comment lines directly above a key, with no blank line between, belong
    to that key;
  - key-level edit inside `global_settings` (one key replaced, added or removed);
  - map-entry span for one entry of `sources` or `targets`;
  - insertion of an absent top-level block, after the last block, separated by one blank line;
  - list-item append under `pipelines:` and under `checks.validation.pipelines:`, keeping the
    list's indent style.
- When the editor refuses, it writes `<file>.new` with the full new text through
  `create_private_exclusive` (`CREATE_ONCE`) and tells the user to compare and move it. The
  original is unchanged.
- AT-W3.1b.1 (hostile corpus, AT-W13 style) per span kind: comments, blank lines, reordered
  blocks, end of file without newline, CRLF, a comment inside the span, a key that is a prefix of
  another key. Every byte outside the span is unchanged.
- AT-W3.1b.2: each refusal case writes `<file>.new` once; a second run with `.new` present
  refuses without overwriting it.
- AT-W3.1b.3: a comment directly above `subset:` moves with the block; a comment after a blank
  line stays. Mutation: drop the comment-above rule, red.
- Depends on W3.1.

**P7. `decoy edit <section> <pipeline>`.** R2, CLI, ~450.

- Guarantee: runs one step over an existing pipeline and writes its span through W3.1b; the
  `edit` verb is registered from `cli/wizard/_edit.py`.
- AT-P7.1 (round-trip property): full flow with answers A equals the same sections run one at a
  time through `decoy edit`.
- AT-P7.2: every byte outside the edited span is unchanged, for each section.
- AT-P7.3: a file changed between read and write gives `init.yaml_changed`. Mutation: drop the
  hash check, red.
- Depends on W3.1b, P4.

**W2.** As in the record plan (~460, R1), plus `scan_baseline.path` and `schema` in the Scan
step. Depends on SCAN-ML M3b released (which waits on E1).

**W3.2.** As in the record plan (~590, R2), reading report v3 and v2 (7.6). Depends on W3.1, E2
repinned, SCAN-ML C2a merged (CLI #301).

### 7.5 Phase 3 slices kept in V1

**T1. Tokenize goal.** R2, CLI, ~400.

- Guarantee: 5.5.
- AT-T1.1: tree sync (spec 15) with and without the Tokenize goal.
- AT-T1.2: the vault offer set equals the `vault_eligible` set. Mutation: offer on all, red.
- AT-T1.3: YAML from a Tokenize session passes `check_vault_columns`.
- AT-T1.4: RC prints `--vault PATH` and never `--chunked`.
- AT-T1.5: a vault path inside the work tree that git does not ignore gets the warning and offer;
  the default path is outside the tree.
- Depends on EG4 repinned, P1a, RC.

**C2. CI manifest step.** R2, CLI, ~400.

- Guarantee: Review offers "run this pipeline in CI".
  - No manifest: write one through C1 with `CREATE_ONCE`.
  - Existing manifest: append one `pipelines` entry through W3.1b.
  - When `checks.validation.pipelines` is an explicit list (`contracts.py:509-516`), the wizard
    asks to add the id to it too (default yes). If the user says no, the manifest loads but the
    pipeline is not validated, and the checklist says so.
  - When `checks.validation.enabled` is false, it warns that CI will not validate the pipeline.
  - At `MAX_PIPELINES` (32, `contracts.py:447`) it refuses with `init.ci_manifest_full`.
  - The id is checked with `re.fullmatch` against the manifest's id rule and must be unique.
  - A DuckDB pipeline is not offered (CI has no `--duckdb-source`); the checklist says why.
  - With `--evidence-out` in the run command, it offers an `evidence` check.
- Order: the pipeline is written first; the manifest after. If the manifest write fails, the
  pipeline stays, and the error names the manifest step and the `<file>.new` fallback.
- AT-C2.1: append to a manifest with comments; other bytes equal; the result loads.
- AT-C2.2: duplicate id refused; `"ci\n"` refused.
- AT-C2.3: with an explicit `validation.pipelines`, the id is appended there and the manifest
  loads; with "no", the checklist line appears. Mutation: skip the list append, red (the loader
  still accepts, so the AT asserts the list).
- AT-C2.4: `validation.enabled: false` gives the warning.
- AT-C2.5: a 32-pipeline manifest gives `init.ci_manifest_full`, file unchanged.
- AT-C2.6: pipeline write fails, manifest unchanged. Mutation: write the manifest first, red.
- AT-C2.7: pipeline written, manifest write fails; pipeline kept, `<file>.new` written, exit 3.
- Depends on C1, W3.1b, RC.

### 7.6 Report versions for W3.2

W3.2 reads `post-scan-integrity/v3`. It also reads v2 and treats a v2 report without
`tables_checked` as covering no table (every finding shown, none auto-dismissed). Unknown major
and missing tag are refused with `init.report_schema`.

## 8. Class table

### 8.1 Plan-contract classes

| # | Class | Applies to | Structure | Proof | Mutation |
|---|---|---|---|---|---|
| 1 | Value-bearing output | B1 ruler, B2 locations, B3 paths, B5 allowed values, P1a snapshot values, P3 predicates, B7 drafts, P4 answers | value-free `init.*` errors; `ScanSetCore` only in drafts; G2 allow-list | canary corpus over every surface per step | pass a raw value into a summary line |
| 2 | Cleanup on exit paths | B3 staging, B7 draft, P1a snapshot pair, C2 order, W3.1b `.new` | one owner per resource | AT-B3.1, AT-B7.4, AT-P1a.4, AT-C2.6, AT-C2.7 | skip one cleanup |
| 3 | State machine | stale marking across new steps | 1a `_nav` rules plus each new `stale()` | navigation cases per step | drop one `depends_on` |
| 4 | Route parity | terminal, answers, resume, `decoy edit` | one step object per route; C7 | AT-P4.1, AT-P4.4, AT-P7.1 | a step without an answers model |
| 5 | Referential integrity | P2, P3 | FK shape list; engine refusals only | AT-P2.1a/b/c, AT-P3.3 | refuse cross-table cycles |
| 6 | Untrusted producer | answers, drafts, reports, existing manifest, DuckDB errors | strict versioned models; errors rebuilt from codes | AT-B7.2, AT-P4.2, AT-B3.4 | lax int field |
| 7 | TOCTOU on paths | editor writes, manifest append | hash check at write | AT-P7.3, AT-C2.1 | drop the hash check |
| 8 | Weak tests | all | evidence rules (12) | reviewer reruns on the exact head | n/a |
| 9 | Refactor drift | Y0, B2 dispatch refactor | characterization first | AT-Y0.1, AT-B2.6 | n/a |
| 10 | Frozen contract drift | `decoy-ci/v1`, engine exports | additive only; answers frozen at 32b close | AT-C1.1, export snapshots | add a manifest key |

### 8.2 Recurring-defect catalog classes (`dev-rules/catalogs/recurring-defects.md`)

| # | Class | Where it applies | Guard |
|---|---|---|---|
| 1 | Anchored validation | step ids, CI ids, `credentials_ref`, table names | AT-P5.1, AT-C1.4, AT-C2.2, AT-B2.4 (value plus `"\n"`) |
| 2 | Strict wire types | answers, drafts, catalog wire types | AT-B7.2, AT-P4.2, AT-EG1.3 |
| 3 | No exception context | `init.source_unreadable`, draft and answers errors | AT-B3.4, AT-B7.2 assert `__context__` None |
| 4 | Versioned read models | draft, answers, report v2/v3 | AT-B7.2, AT-P4.2, 7.6 cells |
| 5 | Normalized guard scanners | C3, C4 | covered spellings listed in section 6; one seeded case each |
| 6 | No private imports | wizard to engine; wizard to `cli/io` | public `decoy_engine` names and the `decoy.cli.io` facade only; EG1 to EG5 export what the wizard needs |
| 7 | No hidden CI failures | new sentries | registered in `SENTRIES`; no skip markers |
| 8 | One input, one trust class | `.gitignore` lines (program-chosen) vs user paths | `append_gitignore_line` takes program lines; user paths go through `write_local_target` |
| 9 | Mutations on the final head | every slice | section 12 |
| 10 | Allowlisted helpers still checked | C4 `apply_edits`, C6 `render_manifest` | exact `(path, name)`; caller list checked (AT-B7.6, AT-C1.2) |
| 11 | No raised caps | module size, fan-out, init.py pin | section 10 |

## 9. Enumerations

### 9.1 New exit paths that own files or state

| Owner | Exits |
|---|---|
| DuckDB staging (B3) | success, cancel at each step, scan error, gate refusal, write error, interrupt, stale sweep |
| Draft (B7) | `q`, cancel, interrupt, success (removed), failed write (kept), bad draft, stale draft |
| Snapshot pair (P1a) | both written, snapshot written then pipeline fails (snapshot removed), fit fails |
| Answers save (P4) | success, file exists, parent missing, write error |
| `.gitignore` (B5, B7, T1) | added, already present, missing (created), symlink refused, write error |
| Editor writes (W3.1, W3.1b, P7, C2) | success, hash changed, unsupported span (`.new` written), `.new` exists, symlink, write error |
| Manifest (C1, C2) | new file, append, duplicate id, full, invalid existing manifest, pipeline write failed first, pipeline written then manifest failed |

### 9.2 Routes

- Terminal session (`decoy init`, `decoy init FILE`).
- Answers file (`--answers`, P4).
- Draft resume (`--resume`, B7).
- Section edit (`decoy edit <section>`, P7).
- Findings review (`--review-findings`, W3.2).
- One-shot flags (`--json`, `-q`, `--no-input`), unchanged from 1a.

### 9.3 FK shapes

The Relationships step (P2) handles each shape `RelationshipConfig` (engine
`config/_relationships.py:41`) can hold:

- single-column key;
- composite key (column order kept);
- self-referencing table;
- one parent with several children;
- a chain (A to B to C);
- a child whose source is cloud: facts and candidates report `skipped_cloud`
  (`profiling/_scan_integrity.py:176`);
- a cross-table cycle: accepted; the run takes the full-frame route (`CROSS_TABLE_CYCLE`);
- a key-node cycle: refused by the engine (`FK_CYCLE`, `relationships/_graph.py:300-310`).

### 9.4 Fields

The models whose fields the wizard writes, each walked in full by V0 (5.2):

- `PipelineConfig` (engine `config/_pipeline.py:87`), with `DeliveryConfig`
  (`config/_delivery.py:19`), `RelationshipConfig` (`config/_relationships.py:41`),
  `SubsetConfig` (`config/_subset.py:87`) and the generate per-type options
  (`config/_tables.py:254-271`);
- `CiManifest` (CLI `src/decoy/ci/contracts.py:615`), `PipelineRef` (`contracts.py:500`),
  `ValidationCheck` (`contracts.py:509`);
- the `decoy run` options (`src/decoy/cli/run/__init__.py`), through `FLAG_COVERAGE`;
- the engine results the wizard reads: `ScanSetCore` (`profiling/scan_set.py:11`),
  `GenerateTypeOptions` (`config/_generate_option_catalog.py:32`), and the new EG2, EG3 and EG5
  results;
- the DuckDB staging pair (`src/decoy/cli/_duckdb_source.py:76,87`).

### 9.5 Output surfaces

- stdout prompts, summaries, the Review screen and the printed run command;
- stderr errors;
- `--json` output;
- `-v` logs;
- the pipeline YAML;
- the snapshot file (P1a);
- the draft file;
- the answers file;
- `.gitignore`;
- `.decoy-ci.yaml` and its `.new` fallback;
- the end-of-run checklist;
- help text and parse errors.

Each new slice adds its surfaces to the privacy test.

## 10. Placement

| New file | Directory | CODEMAP row | Sits beside |
|---|---|---|---|
| `steps/_locations.py`, `_fixed_width.py`, `_duckdb.py`, `checks.py`, `quality.py`, `generate.py`, `relationships.py`, `subset.py`, `detectors.py`, `tokenize.py` | `src/decoy/cli/wizard/steps/` | "Interactive review wizard" (added by W1a.0) | 1a step modules |
| `_draft.py`, `_answers.py`, `_run_command.py`, `_yaml_edit.py`, `_edit.py`, `_findings.py`, `_ci_step.py` | `src/decoy/cli/wizard/` | same | `_flow.py` |
| `_yaml_marks.py` (target) | `src/decoy/` | "Shared YAML document structure and source-mark indexing" (added by Y0) | `_atomic.py` |
| `emit.py` (target) | `src/decoy/ci/` | "CI integration" (`src/decoy/ci/<concern>.py`) | `manifest.py` |
| `append_gitignore_line` (function, no new file) | `src/decoy/cli/io/_project.py` (251 lines now) | "Project layout services" | `write_decoy_gitignore` |
| `sample_rows` option (no new file) | `src/decoy/cli/_duckdb_source.py` | existing flat module, edited in place | |
| `_config_coverage.py`, `test_config_coverage.py`, `test_wizard_writes.py` | `tests/sentry/wizard/` | wizard sentry row (1a) | 1a wizard sentries |
| unit and e2e tests | `tests/unit/wizard/`, `tests/e2e/wizard/` | wizard row | 1a tests |
| engine `_generate_option_catalog.py` (edit) | `decoy_engine/config/` | engine config | |
| engine `validators/_catalog.py` (target) | `decoy_engine/validators/` | engine validators | `_registry.py` |
| engine `quality/_freetext_advisory.py` (edit), `column_review_flags` | `decoy_engine/quality/` | engine quality | |
| engine `profiling/_relationship_candidates.py` (target) | `decoy_engine/profiling/` | engine profiling | `_scan_integrity.py` |

The draft does not add `_safe_profile.py`: it stores `ScanSetCore`. No new file in flat
`src/decoy/cli/`. Fan-out: `cli/wizard/` about 15 modules, `cli/wizard/steps/` about 19, both
under the 25 cap. Each module stays under 800 lines; `steps/sources.py` shrinks in B2 because
location kinds, fixed width and DuckDB are separate modules. No ceiling, pin or baseline is
raised.

Consumer pairs (proportionality exception): C1 to C2; Y0 to P4 and W3.1 (and `ci/locations.py`
now); EG1 to P1b; EG2 to B5; EG3 to B4; EG4 to T1; EG5 to P2; E2 to W3.2; W3.1b to P7 and C2.

## 11. Slices, order and tiers

| Slice | Repo | Lines | Tier | Depends on | Before S3a.1 |
|---|---|---|---|---|---|
| E1 (1a plan) | engine | ~700 | R2 | merged S3-engine.2, M1 | yes |
| E2 (record plan) | engine | ~420 | R2 | E1 (types), M1, M4 | yes |
| EG1 | engine | ~350 | R1 | none | yes |
| EG2 | engine | ~350 | R1 | none | yes |
| EG3 | engine | ~350 | R1 | none | yes |
| EG4 | engine | ~300 | R2 | E1 | yes, after E1 |
| EG5 | engine | ~500 | R2 | none | yes |
| R-1b | engine | n/a | R2 | EG1 to EG5 (E2 may ride R-1a) | yes |
| Y0 | CLI | ~250 | R1 | none | yes |
| C1 | CLI | ~300 | R1 | none | yes |
| V0 | CLI | ~500 | R1 | W1a.6b | no |
| RC | CLI | ~250 | R1 | W1a.6b | no |
| B1 | CLI | ~450 | R1 | B2 | no |
| B2 | CLI | ~500 | R2 | W1a.6b | no |
| B3 | CLI | ~400 | R1 | B2, RC | no |
| B4 | CLI | ~400 | R2 | W1a.6b; EG3 repinned | no |
| B5 | CLI | ~500 | R2 | W1a.6b; EG2 repinned | no |
| B6 | CLI | ~300 | R1 | B5, RC | no |
| B7 | CLI | ~500 | R2 | W1a.6b | no |
| B8 | CLI | ~250 | R1 | B5, B6 | no |
| P1a | CLI | ~400 | R2 | RC | no |
| P1b | CLI | ~500 | R1 | P1a; EG1 repinned | no |
| P2 | CLI | ~500 | R2 | W1a.6b; EG5 repinned | no |
| P3 | CLI | ~450 | R2 | P2, P1a | no |
| P4 | CLI | ~500 | R2 | Y0, W1a.6b | no |
| P5 | CLI | ~300 | R1 | P4 | no |
| W3.1 (record plan) | CLI | ~540 | R2 | Y0, W1a.6b | no |
| W3.1b | CLI | ~450 | R2 | W3.1 | no |
| P7 | CLI | ~450 | R2 | W3.1b, P4 | no |
| W2 (record plan) | CLI | ~460 | R1 | W1a.6b; SCAN-ML M3b released | no |
| W3.2 (record plan) | CLI | ~590 | R2 | W3.1; E2 repinned; C2a merged | no |
| T1 | CLI | ~400 | R2 | P1a, RC; EG4 repinned | no |
| C2 | CLI | ~400 | R2 | C1, W3.1b, RC | no |

Totals: 25 CLI slices, about 10,540 lines (of which W2, W3.1 and W3.2, about 1,590, were sized
in the record plan). 5 new engine slices, about 1,850 lines. E1 and E2 were sized in earlier
plans.

Before S3a.1 unblocks 1a: E1, E2, EG1, EG2, EG3, EG5 (then EG4), Y0 and C1. About 2,400 new lines
plus E1 and E2, none of which needs the renderer.

Order after W1a.6b: V0 and RC first, then lanes with one writer per file:

- lane L (locations): B2, then B1 and B3;
- lane K (checks): B5, B6, B8;
- lane F (fields): B4;
- lane D (drafts): B7;
- lane G (generate): P1a, P1b;
- lane R (relationships): P2, P3;
- lane A (answers): P4, P5;
- lane E (editor): W3.1, W3.1b, then P7 and C2;
- lane S (scan): W2;
- lane W (findings): W3.2;
- lane T (tokenize): T1.

Shared files (keep both sides on merge, one writer at a time per file): `steps/__init__.py`
(`STEPS`), `tests/sentry/wizard/_config_coverage.py`, `_run_command.py` (`RunFlag`,
`FLAG_COVERAGE`), `steps/review.py` (C2, B4 confirm, P1a fit notice), `steps/secrets.py` (T1,
P1b), `_checklist.py` (B3, B5, P3, C2), `steps/sources.py` and `steps/output.py` (B2 refactor
first; B1 and B3 after), and the central reason-code registry.

One engine release (R-1b) after EG1 to EG5, then one CLI repin. One release and one repin open
at a time.

## 12. Worker evidence rules

- Name the class of every finding and fix the class.
- Write the ATs first and record them red.
- Run the named mutations on the final head and record the head.
- Tests run on the Mac or through `vm-run`, never on the devbox.
- T0 per edit, T1 per commit. Full suite only on a trigger: the R-1b repin (lock), the answers
  and draft formats (serialization), Y0 (moved code), C1 and C2 (`decoy-ci/v1`), and B3 (shared
  `acquire_relation` used by `decoy run`).
- Never raise a size cap, ratchet or allowlist. Never weaken a test to pass.

## 13. Frozen contracts touched

| Contract | Change |
|---|---|
| `decoy-ci/v1` | none to the schema; `ci/emit.py` writes only what the loader reads |
| `decoy-init-answers/v1` | new; grows per step; snapshot frozen when row 32b closes |
| `decoy-init-draft/v1` | new; private, versioned, not a public contract |
| `post-scan-integrity/v3` | read only (v2 still read) |
| Engine public exports | additive: `validator_catalog`, `column_review_flags`, `ReviewFlag`, `relationship_candidates`, `RelationshipCandidate`, `StrategyInfo.vault_eligible`, catalog fields |
| `acquire_relation` | additive keyword `sample_rows`; default behavior unchanged |
| Exit codes | none |
| `init.*` reason codes | additive in the central registry: `init.draft_invalid`, `init.draft_stale`, `init.answers_invalid`, `init.yaml_changed`, `init.yaml_edit_unsupported`, `init.yaml_symlink`, `init.report_missing`, `init.report_schema`, `init.report_stale`, `init.source_unreadable`, `init.ci_manifest_full` |

## 14. Roadmap row 32b text (for the roadmap owner; this plan does not edit ROADMAP.md)

> **32b INIT-WIZARD (V1, owner 2026-11-17: "a working wizard to configure a job is v1").**
> `decoy init` configures any V1 job: local, fixed-width, S3, GCS and DuckDB sources; local,
> fixed-width, S3 and GCS targets with delivery mode; mask, generate, subset and tokenize goals;
> pre-scan and post-scan detectors and the scan baseline; per-field strategies in every-field or
> flagged-only review; generated columns and table uniqueness; relationships from engine
> candidates; subset filter and sample seeds with budget; post-scan integrity, validators and
> quarantine; quality settings; secrets and the vault; the printed run command; and the CI
> manifest. Answers files, drafts and resume, `decoy edit`, and post-scan findings review
> included. Plans: Phase 1a `docs/plans/2026-11-08-init-wizard-phase-1a.md`; the rest
> `docs/plans/2026-11-17-init-wizard-v1-rest.md`. A coverage sentry fails CI for any config
> field, CI manifest field or run flag with no wizard entry. Rows 64b, 86, 87, 81, 68, 69 and 32
> add their own wizard entries. V2: arrow keys and completion, before and after previews. After:
> SCAN-MULTI S3a.1 (1a), engine R-1a and R-1b, SCAN-ML M3b (W2), C2a (W3.2).

## 15. Owner questions and answers

| # | Question | Answer |
|---|---|---|
| Q1 | Tokenize goal offers both the `tokenize` strategy and `vault: true` on eligible strategies? | Both (taken as recommended, 2026-11-17) |
| Q2 | Validator list from an engine catalog (EG2)? | Engine catalog (taken as recommended) |
| Q3 | Keep `decoy init --review-findings PIPELINE --report FILE`? | Keep (taken as recommended) |
| Q4 | Rows 64b, 86, 87, 81, 68, 69 and 32 each ship their wizard entry, enforced by V0? | Yes (taken as recommended) |
| Q5 | DuckDB stays a run flag in V1? | Yes; a config kind is V2 (taken as recommended) |
| Q6 | Before and after previews? | V2 (owner, 2026-11-17) |
| Q7 | Preset pre-fill (B8) in V1? | Yes (taken as recommended) |
| Q8 | No new dependency? | None (taken as recommended) |
| Q9 | Append to an existing `.decoy-ci.yaml` through the editor? | Yes, with the hash check and a diff first; `.new` fallback (taken as recommended) |
| Q10 | `scan_baseline.on_drift` belongs to row 32 DRIFT? | Yes (taken as recommended); `path` and `schema` are in the Scan step |
| Q11 | Relationship candidates come from a new engine slice EG5? | EG5 (Dennis round 1, taken under go-with-recommended) |
| Q12 | The spec 7 column keys (`when`, `coherent_with`, `cardinality_mode`, `error_policy`, `logical_type`, `parse_format`, `output_format`, `backend_type`, `backend_version`, `scale`, `pool_size`, `allow_collisions`, `dtype`, `sentinel_to_null`) stay hand-set in V1, named under "Set by hand"? | Recommended: yes. Every V1 job runs without them; they refine one column. OPEN |

## 16. Pre-mortem

- 1a slips on S3a.1 and this plan waits. About 2,400 new lines plus E1 and E2 start now.
- Many lanes touch the shared files in 11 at once. V0 and RC land first; the shared files are
  keep-both ledgers with one writer at a time.
- The editor is the riskiest piece and four slices wait on it (W3.1b, P7, C2, W3.2). Start W3.1
  the day W1a.6b merges.
- The privacy test grows with each step. One shared canary fixture, one parametrized test per
  surface.
- Engine slices slip the release train. Each is independent; B4, B5, P1b, P2 and T1 wait only on
  their own engine slice.
- A later row adds a source kind or field before V0 lands. V0 maps every kind present at its
  base; the sentry then holds.
- The roadmap state tokens change wording. V0 fails closed on an unknown token, and the fix is to
  add the token to the list, not to remove the check.

## 17. Review resolutions

### Dennis round 1 on `98bfdc8d` (BLOCK, 0/8/14/5)

| Finding | Resolution |
|---|---|
| H1 coverage incomplete | Section 1 rebuilt from the schema walk (214 nodes, 184 leaves); every leaf has Step, Hand with a reason, or Row; CI manifest table (1.3); run-flag table (1.4); real thresholds named; `unique_together` moved to P1b |
| H2 V0 not fail-closed | 5.2: full keyword walk, unknown keyword red, open maps need entries, claims on step objects with per-step AT, `Row("32b")`, explicit state tokens, `CiManifest` and run flags in scope; AT-V0.1 to V0.6 |
| H3 editor spans | New slice W3.1b with five span kinds, the `.new` fallback and a hostile corpus per kind |
| H4 second `.gitignore` writer | `append_gitignore_line` beside `write_decoy_gitignore` in `cli/io/_project.py`; C5 points there; `_gitignore.py` dropped |
| H5 `_safe_profile` | Dropped; drafts store `ScanSetCore`; AT-B7.3 kept |
| H6 P1a reuse | Reuses `fit_exact_snapshot` and the snapshot layout; renders through the shared renderer; snapshot values in G2 and 9.5; AT-P1a.2 to P1a.4 |
| H7 relationship candidates | New engine slice EG5; Q11; P2 uses EG5 only |
| H8 C2 and `validation.pipelines` | C2 appends to the explicit list (asks), warns on `enabled: false`, refuses at 32; AT-C2.3 to C2.5 |
| M1 cycles | AT-P2.1 split into a/b/c; cross-table cycles accepted |
| M2 DuckDB staging | `sample_rows`, private staging dir, stale sweep, value-free `init.source_unreadable` |
| M3 answers freeze | Per-step `answers_model` (C7); frozen at 32b close |
| M4 subset values | Added to G2 allow-list and class row 1; AT-P3.4 |
| M5 draft fingerprint | Defined in B7; AT-B7.5; `init.draft_stale` |
| M6 EG3 thresholds | Non-default threshold cells in AT-EG3.1 |
| M7 run command | New slice RC; `--chunked` not a `RunFlag`; AT-T1.4 |
| M8 high cardinality | Folded into EG3 (`HIGH_CARDINALITY` from the engine stat); AT-B4.3 |
| M9 fixed-width overflow | Writer layer named; Review warning; AT-B1.4 |
| M10 `scan_baseline` | `path` and `schema` to the Scan step (W2); `on_drift` to row 32 |
| M11 class table, C3, C4 | 8.2 recurring-defect rows by name; covered spellings listed; C4 is an AST sentry with exact helpers and a caller check |
| M12 second emitter | `ci/emit.py` is the one named, tested exception (5.3, AT-C1.2) |
| M13 project layout | 5.7: `RunLayout` and `.decoy/scratch/` first; `.gitignore` only outside a project |
| M14 shared files | All shared lane files named in 11; B2's dispatch refactor named, with AT-B2.6 |
| L1 totals | Recounted in 11 |
| L2 `ci/emit.py` | Public module name; writes `schema_version` |
| L3 1a statuses | D4 updated (P6, P7 met; P9 open) |
| L4 manifest after pipeline | Exit row in 9.1 and AT-C2.7 |
| L5 C3 scope | Comparing positions and spellings listed; fullmatch on ids (G9) |
