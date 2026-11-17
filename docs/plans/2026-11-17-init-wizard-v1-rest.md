# Init wizard: the rest of V1 (row 32b after Phase 1a)

Status: plan

Revision: rev 2, 2026-11-17. Fixes Dennis rounds 1 and 2. Round 2 was BLOCK, 0 critical,
4 high, 11 medium, 6 low. Section 17 maps every finding to its root fix. Owner answers are in
section 15.

Date: 2026-11-17. Author: Opus planner. Risk: R2 overall (privacy of scan output, persisted
answer and draft formats, edits to user-owned YAML, the frozen `decoy-ci/v1` contract). Each
slice carries its own tier in section 11.

Bases: CLI `origin/main` `c558e2fb` (#310), engine `origin/main` `11ceb73f5` (#635, version
0.27.0). The CLI pins `decoy-engine==0.27.0`. Rev 2 was reconciled against the plan branch
`origin/plan/init-wizard-v1-rest` at `7385dc16` by read-only `git show`.

Rules consulted: `/home/cam/dev-rules/00-universal.md`, `development-loop.md`,
`risk-and-exceptions.md`, `reuse-first.md`, `exploration.md`, `scope-discipline.md`,
`proportionality.md`, `verification.md`, `feature-dev.md`, `bugfix.md`, `code-review.md`,
`testing.md`, `architecture.md`, `cross-cutting-concerns.md`, `api-and-compatibility.md`,
`config-secrets-and-supply-chain.md`, `security.md`, `documentation.md`,
`profiles/local-operations.md`, and `catalogs/recurring-defects.md` (classes 1 to 11); the plan contract and defect catalog
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
| `sources.{}.bucket`, `.key`, `.object`, `.region`, `.endpoint_url` | `Row("64")` until its CLI source slices make the kind executable and export it from `decoy.cli.io`; B2 then turns the row into a Step claim | Row 64, then **B2** |
| `sources.{}.credentials_ref` | Hand until row 64 defines and implements a CLI resolver; today it is opaque and the SDK uses its default chain | none |
| `targets.{}.type`, `.path`, `.format` | Step: Output (local file) | 1a W1a.5a |
| `targets.{}.layout.exact_record_width`, `targets.{}.layout.columns[].name`, `.start`, `.width`, `.align`, `.pad`, `.type` | Step: Output, fixed width | **B1** |
| `targets.{}.bucket`, `.key`, `.object`, `.region`, `.endpoint_url`, `.credentials_ref` | `Row("64")` until its CLI target slices make each kind and field executable and export it from `decoy.cli.io`; B2 then turns the row into a Step claim | Row 64, then **B2** |
| `delivery.mode` | `Row("64")` until cloud delivery is executable; B2 then turns it into a Step claim | Row 64, then **B2** |
| `tables[].name` | Step: Sources (table name) | 1a W1a.4a |
| `tables[].columns[].name`, `.strategy`, `.provider`, `.provider_config.{*}`, `.namespace`, `.deterministic` | Step: Fields, through E1 `column_entry` | 1a W1a.3b |
| `tables[].columns[].vault` | Step: Fields, Tokenize branch | **T1** |
| `tables[].columns[].when`, `.coherent_with`, `.cardinality_mode`, `.error_policy`, `.logical_type`, `.parse_format`, `.output_format`, `.backend_type`, `.pool_size`, `.allow_collisions`, `.dtype`, `.sentinel_to_null` | Hand: spec 7 column-key list. V1 writes the engine default by omission; Set by hand and validation errors name each key (owner Q12) | none |
| `tables[].columns[].scale`, `.backend_version` | Hand: they qualify `dtype` and `backend_type`. V1 writes the engine default by omission; Set by hand and errors name them (Q12) | none |
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
| `checks.evidence[].id`, `.manifest` | Hand: the evidence manifest is produced by a separate run outside `decoy-ci`; the checklist names the repository-relative manifest path rule | none |
| `checks.drift[].id`, `.baseline`, `.current`, `.blocking` | Hand: needs a "current" scan file that a CI job produces outside `decoy-ci`; documented in `docs/ci-contracts.md` | none |
| `checks.regression_suites[].id`, `.suite` | Hand: the loader refuses them until a public F12 runner exists (`contracts.py:538`) | none |
| `staged_scan.*` | Hand: the patterns are raw secret-like literals and must not pass through prompts | none |

### 1.4 `decoy run` flags (`src/decoy/cli/run/__init__.py`)

The printed next command comes from one builder (RC, 5.6). Each flag is either set by a step or
named as a per-run choice.

| Flag | Entry | Slice |
|---|---|---|
| `--mode` | Hand/per-run: the YAML decides table behavior and RC does not print this flag | none |
| `--duckdb-source TABLE=DB_PATH` | Step: Sources, DuckDB sub-flow | **B3** |
| `--fidelity`, `--post-validate`, `--post-validate-enforce` | Step: Quality | **B6** |
| `--vault PATH` | Step: Secrets, Tokenize branch | **T1** |
| `--master-key` | Hand/per-run: a raw 64-hex key or `DECOY_MASTER_KEY`; the wizard never collects or prints it | none |
| `--key-label` | Step: Secrets, Generate branch; the same branch names `DECOY_MASTER_KEY` without reading its value | **P1b** |
| `--mask-secret` | Not printed: the Secrets step writes `global_settings.mask_secret_ref` instead | 1a |
| `--evidence-out PATH` | Hand/per-run: it produces an evidence manifest outside `decoy-ci`; C2's checklist explains how to reference that file by a later hand edit | none |
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
2. Cloud execution is row 64. After its CLI slices merge, B2 exposes only the source/target
   kinds and fields that the row 64 gate says are executable. `sources.credentials_ref` stays
   Hand unless row 64 implements a resolver.
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
- G2a. No input data value, secret value, credential or exception text reaches any wizard
  surface (section 9.5) except this data-value allow-list:
  - `validators[name=column_in_set].params.allowed_values` for a field the user confirmed (H2
    rule, spec 4.5);
  - subset predicate values the user typed (`subset.seeds[].predicates[].value`);
  - snapshot `top_values` of unflagged categorical columns written by the fit (P1a), under the
    same `value_policy` and `allow_real_categories` opt-in notice as `decoy fit`
    (`cli/fit.py:14-18`).
  Each allow-listed value may appear only in the pipeline, snapshot, draft and answers file
  (all owner-only except the pipeline), never in stdout summaries, `-v` logs, `--json`, error
  text or notifications.
- G2b. A location that the user typed, including a bucket, object key, endpoint, DB path or DSN,
  is structure for this workflow. It may appear only in the pipeline YAML, draft, answers file
  and the run command where that command needs it, including the run-command field of `--json`.
  It is absent from errors, `-v` logs, summaries, every other `--json` field, notifications,
  `.decoy-ci.yaml` and output data files. Section 9.5 is the
  per-surface matrix and every location slice adds its canaries to it. URL userinfo is a
  credential, not a location: the wizard refuses endpoints or DSNs containing it without
  echoing the value.
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
| D6 | `create_private_exclusive` creates only an empty 0600 file; atomic bytes belong to `_atomic.write_local_target` | none in 1a | B7 drafts, P4 answers and W3.1b `.new` files write bytes with `CREATE_ONCE`; replacements use `REPLACE`. The record plan's `mode` argument is a `WriteMode`, not a `_private_file` operation |
| D7 | `src/decoy/cli/io/` holds the layout services and the cloud root check | W1a.6a | The path-role check calls `decoy.cli.io` for placement and the collision rule |

## 4. Reuse inventory

| Need | Reuse | Where |
|---|---|---|
| Step loop, state, stale marking, Prompter, tree, field review, write step | Phase 1a modules | `src/decoy/cli/wizard/` (after W1a.6b) |
| Reason codes | central registry from W1a.0 | `src/decoy/_reason_codes.py` |
| Empty owner-only reservation | `create_private_exclusive`, `open_private` | `src/decoy/_private_file.py:168,200` |
| Atomic owner-only bytes, create or replace | `_atomic.write_local_target(..., CREATE_ONCE|REPLACE)` and paired publish | `src/decoy/_atomic.py:199,363`; `_atomic.publish_local_targets` |
| YAML marks | index in `ci/locations.py`, moved by Y0 | `src/decoy/_yaml_marks.py` (target) |
| `.gitignore` | `prepare_out`/`RunLayout` already create the run-tree ignore; B5 adds `append_gitignore_line` to the `decoy.cli.io` package as the one exact-path append choke point | `src/decoy/cli/io/_layout.py:241-262,468`; `src/decoy/cli/io/` |
| Run folders, quarantine placement, scratch | `RunLayout`; `.decoy/scratch/` is already ignored (`DECOY_DIR_GITIGNORE`, `_project.py:35`) | `src/decoy/cli/io/_layout.py:465` |
| Cloud root rules | `cloud_root_issues` | `src/decoy/cli/io/_cloud.py` |
| Generate scaffold | P1a first exports one non-exiting seam from `decoy.cli.gen` that owns fit, layout, validation, opt-in columns and paired publish; both `scaffold_generate` and the wizard call it | current private pieces in `gen/_scaffold.py:1-260`, CSV fit in `gen/_fit.py:65-160` |
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

`decoy.cli.io` exports one immutable capability fact derived from the cloud gate's own tables:
the currently executable source kinds, target kinds and allowed fields for each role. The gate
and capability fact have one root descriptor, so they cannot disagree. B2's
`cli/wizard/steps/_locations.py` adds prompt/render functions around that public fact and around
the existing local-file and DuckDB kinds. It never copies a cloud kind or field literal.

Until row 64's CLI source and target slices merge, the public fact contains no cloud kind because
`decoy run` refuses every S3/GCS source and target. After those slices merge, B2 depends on them
and offers exactly what the fact exposes. GCS targets, target `credentials_ref` and
`endpoint_url`, and quarantine with a cloud target stay absent while the gate refuses them.
`sources.credentials_ref` is Hand because the CLI does not resolve it; row 64 may replace that
with its own implemented form. Rows 64b, 86 and 87 extend the same root descriptor when their
execution paths exist.

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
- a Row entry names a row id that must exist in `docs/ROADMAP.md`. The sentry reads only the
  leading state token, case-insensitively, using longest-token-first matching. Done tokens are
  `MERGED`, `DONE`, `SHIPPED`. Open tokens include `NOT STARTED`, `PARTLY MERGED`, `IN PROGRESS`,
  `BUILDING`, `BLOCKED`, `PARKED`, `PLANNED`, `PLAN`, and `plan rev N GO`. A done row with a Row
  entry is red. An unknown token, a missing row, or a substring match is red. The fixture pins
  the current state cells of every row referenced by the coverage table, including 32, 32b, 64,
  64b, 68, 69, 81, 86 and 87.

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
the Review screen, checklist and `--json`. RC never prints `--mode`, `--master-key` or
`--chunked`. The Generate secrets branch names `DECOY_MASTER_KEY` and may contribute only
`--key-label`. A path in the printed command is a user answer allowed by G2b.

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
- C4 (B7, P4, B3, P1a). One write path for wizard files. An AST sentry over `src/decoy/cli/wizard/`
  and `src/decoy/ci/emit.py` flags `open(` with a mode containing `w`, `a`, `x` or `+`,
  `Path.write_text`, `Path.write_bytes`, `Path.open` with a write mode, `os.open` with
  `O_WRONLY`, `O_RDWR` or `O_CREAT`, `os.replace`, `os.rename`, `shutil.copy*`, `shutil.move`
  and `tempfile.NamedTemporaryFile` (covered spellings, including `from x import y` and aliases,
  through the G-ONE-GATE resolver). The allowed helpers, by exact `(path, name)`, are
  `_atomic.write_local_target`, `_atomic.publish_local_targets`,
  `cli/io.append_gitignore_line` and the W3.1 editor's `apply_edits`. Callers of every allowed
  forwarding helper are checked too (catalog class 10): only
  `cli/wizard/_edit.py`, `_ci_step.py` and `_findings.py` may call it.
- C5 (B5). One `.gitignore` policy home: the `decoy.cli.io` package. Its sentry uses an exact
  `(path, name)` allowlist for `(_layout.py, prepare_out)`, `(_layout.py, RunLayout.open)` and
  `(_project.py, append_gitignore_line)`; any other `.gitignore` write under `src/decoy/` is red. The append
  API escapes Git pattern metacharacters (`#`, `!`, `*`, `?`, `[`, `\\`) and trailing spaces,
  and refuses a newline, before an atomic append-equivalent replacement.
- C6 (C1). One CI manifest writer, `src/decoy/ci/emit.py`. C1 owns a self-contained AST sentry
  over `src/decoy/ci/` that permits only exact `(src/decoy/ci/emit.py, render_manifest)` to dump
  YAML. S3a.1 later folds the same identity into G-ONE-EMITTER; C1 does not depend on it.
- C7 (F0). Route parity: every entry in `STEPS` has an `answers_model`; a step with no model is
  red. F0 owns the protocol before V0 and RC land. P4 consumes it and adds the one answers
  serializer; drafts embed that same typed answer object and do not serialize answers again.

## 7. Slices: guarantees, failure modes, acceptance tests, mutations

Test IDs are `AT-<slice>.<n>`. Every AT is written red first. "Mutation" names the change that
must turn the test red; it runs on the final head (recurring defect 9). Every new step slice also
adds its surfaces and its Step claims, with a per-step AT: answers built from catalog examples
produce YAML whose leaves, unioned over all scripted sessions for that step, equal the step's
`config_paths` (each claim is reached in at least one session, and no session writes a path
outside the claim). A single session need not exercise mutually exclusive branches.

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

- Guarantee: add value-free `avg_length` and `value_set_size_class` fields to `FieldCore`, with
  compatible defaults on the read model, and populate them from `FieldStats`. Then
  `column_review_flags(field_core, config) -> frozenset[ReviewFlag]` uses the same scorer and
  configured thresholds as `score_unmasked_freetext`. `ReviewFlag.HIGH_CARDINALITY` is true
  exactly when `FieldStats.value_set_size_class` is `unique` or `high`. It never reads the
  snapshot-fit `high_cardinality` opt-in, which is not a scan statistic. The CLI copies neither
  rule and drafts keep the flags through the value-free core.
- Failure modes: a second threshold reader; the per-column answer differs from the run-time
  advisory; a value in the result.
- AT-EG3.1 (parity): over a corpus, with default thresholds and with non-default
  `freetext_advisory_min_avg_length` and `freetext_advisory_min_distinctness` cells, the
  per-column flag equals the run-time advisory's set. Mutation: hard-code the default threshold,
  red (the non-default cells catch it).
- AT-EG3.2: `HIGH_CARDINALITY` is set for `unique` and `high`, and absent for `medium`, `low`,
  `binary`, `constant` and `None`. A boundary corpus on either side of the profiler's class
  threshold is included. Mutation: read snapshot `high_cardinality` or recompute unique share,
  red on the boundary cell.
- AT-EG3.3: the new `FieldCore` fields and result hold labels/count-derived values only; planted
  cell canaries are absent. Old `scan-set/v1` records without the additive fields still read.
- Starts now.

**EG4. Vault eligibility in the strategy catalog.** R2, engine, ~300.

- Guarantee: `StrategyInfo.vault_eligible` exists for every strategy, and `check_vault_columns`
  reads it. `fpe` and `passthrough` are not eligible, as today.
- AT-EG4.1: in the vault extra test environment with `cryptography` installed, for every strategy,
  `check_vault_columns` on a one-column config with `vault: true` and an explicit namespace
  passes exactly when `vault_eligible` is true. Mutation: flip `fpe` to eligible, red.
- AT-EG4.2: a handler without the attribute fails G-CATALOG.
- Depends on E1 (same catalog files).

**EG5. Value-free relationship candidates.** R2, engine, ~500.

- Guarantee: `relationship_candidates(sources, scan_set) -> tuple[RelationshipCandidate, ...]`.
  Each candidate has parent (table, columns), child (table, columns) and evidence:
  `name_match: bool`, `parent_unique: bool`, `status: Literal["complete", "sampled",
  "skipped_cloud"]`, and an overlap classification only when the evidence is complete. The
  engine computes key-name matches and value overlap in protected scratch (the
  `relationship_facts` route) and returns no value. Both relationship facts and candidates say
  `sampled` when either end was sampled; sampled evidence never becomes a false `none`,
  `partial`, orphan count or clean-orphan claim.
- Failure modes: a cell value or exception text in a candidate or error; cloud ends read; unbounded
  memory on a large child.
- AT-EG5.1: a seeded corpus with single, composite and self-referencing keys gives the expected
  candidates. Mutation: drop the overlap check (name match only), red on the decoy column.
- AT-EG5.2: canary values in key columns never appear in candidates, errors or logs.
- AT-EG5.3: a cloud end gives `skipped_cloud` and reads nothing. A sampled end gives `sampled`,
  no orphan verdict and no `partial`/`none` overlap. Mutation: treat sampled rows as complete,
  red.
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
- AT-C1.2: C1's own sentry permits only exact `(src/decoy/ci/emit.py, render_manifest)`; a second
  dumper caller in `src/decoy/ci/` is red. When S3a.1 lands, the same mutation is also red under
  G-ONE-EMITTER.
- AT-C1.3 (golden): one two-pipeline manifest, byte golden, with `schema_version`.
- AT-C1.4: an id `"ok\n"` is refused before rendering (fullmatch).
- Consumer: C2 (proportionality exception; C2 lands before row 32b closes).

### 7.3 Phase 1b slices

All depend on W1a.6b unless stated. Each extends the privacy test (spec 15) with its surfaces.

**F0. Wizard base protocols.** R1, CLI, ~180.

- Guarantee: defines the per-step `answers_model` protocol, its C7 registry guard, and the typed
  answer object shared by terminal, answers-file and draft routes. It does not write a file and
  does not add a second serializer.
- AT-F0.1: every base `STEPS` entry exposes one model; adding a step without one is red.
- AT-F0.2: the typed object used by a scripted terminal session is the object embedded in a draft
  and later serialized by P4. Mutation: convert it through an untyped dict in either route, red.
- V0 and RC depend on F0; later step slices add their models as they register.

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
  missing row id, red. Fixture cells cover every currently referenced roadmap row and prove
  case-insensitive, longest-first leading-token handling for `PARTLY MERGED`, `IN PROGRESS` and
  `plan rev N GO`; a later occurrence of `MERGED` in descriptive text does not close a row.
- AT-V0.6: a `decoy run` option missing from `FLAG_COVERAGE`, red; a `CiManifest` leaf with no
  entry, red.

**RC. Run command builder.** R1, CLI, ~250.

- Guarantee: 5.6.
- AT-RC.1: mask-only, generate-only and a YAML containing both table kinds never print
  `--mode`; there is no `mixed` token in wizard state or output.
- AT-RC.2: no step can contribute a flag outside `RunFlag`; `--chunked` never appears, including
  with `--vault`; `--master-key` is not a `RunFlag`. Mutation: add `CHUNKED` or `MASTER_KEY` to
  the enum, red.
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

- Guarantee: 5.1. `steps/sources.py` and `steps/output.py` dispatch through `_locations.py`, which
  consumes the public `decoy.cli.io` capability fact. Before row 64's CLI execution slices this
  means local kinds only. After them, B2 offers only the cloud kinds and fields exposed from the
  gate's root descriptor; `delivery.mode` appears only when an executable cloud target exists.
  B5 consumes the same fact for quarantine compatibility. The gate runs before write.
- Failure modes: bucket, key or endpoint text in an error, log or `--json`; a split delivery root
  accepted; a gate-refused kind or field exposed; a raw credential accepted by any prompt.
- AT-B2.1: at the row 64 dependency head, one scripted session for every exported executable
  cloud source and target kind/field produces YAML that validates and reaches a CLI run path;
  no refused kind or field appears in a menu.
- AT-B2.2: a split root is refused with a `layout.*` reason through `write_blocking_findings`.
- AT-B2.3: bucket, key and endpoint canaries never appear in `-v` logs, `--json` or error text.
  Mutation: include the key in the summary line, red.
- AT-B2.3a: an endpoint containing URL userinfo is refused value-free before write; the credential canary
  is absent from every section 9.5 surface.
- AT-B2.4: `sources.credentials_ref` is absent and named under Set by hand unless row 64 exports
  an implemented resolver form; raw credential canaries are never accepted by a prompt.
- AT-B2.5 (C2): every schema kind literal maps to the public executable fact or a Row/Hand entry.
  Mutation: expose a gate-refused kind or copy a cloud kind into `_locations.py`, red.
- AT-B2.6 (characterization): the 1a local-file sessions produce the same YAML after the
  dispatch refactor.
- Depends on the row 64 CLI source and target execution slices, in addition to W1a.6b.

**B3. DuckDB tables.** R1, CLI, ~400.

- Guarantee: 5.4.
- Failure modes: staged files left; the whole relation copied for a sample; the DB path or
  relation in output; a `sources` entry written.
- AT-B3.1 (exit-path matrix): success, cancel at each later step, scan error, gate refusal, write
  error, interrupt; the staging directory is gone after each. Mutation: skip cleanup on cancel,
  red. The project-local staging directory and every parent created for it are mode 0700.
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
  confirmed field. For cloud targets it reads the same `decoy.cli.io` capability fact as B2 and
  does not offer quarantine while the gate marks that combination unsupported.
- Failure modes: validator names typed in the CLI; the `.gitignore` rewritten; allowed values in
  logs.
- AT-B5.1: every catalog validator can be added from its example; the YAML validates.
- AT-B5.2 (C3): a validator name in a comparing position in `cli/wizard/`, red, one seeded case
  per covered spelling.
- AT-B5.3: `append_gitignore_line` on a file with comments and no trailing newline adds one line;
  other bytes equal; a second call adds nothing; a symlinked `.gitignore` is refused. Mutation:
  rewrite joined lines, red.
- AT-B5.4 (C5): a `.gitignore` writer outside the exact `decoy.cli.io` `(path, name)` allowlist is
  red. `git check-ignore` proves literal user paths containing `#`, `!`, `*`, `?`, `[`, `\\` and
  trailing space are ignored as that exact path; a newline is refused.
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
  `--resume` loads it strictly. Draft bytes are published with
  `_atomic.write_local_target(..., CREATE_ONCE|REPLACE)`, mode 0600. The draft is removed after a
  successful write.
- Source fingerprint: per source, SHA-256 over (kind, normalized location, declared column names,
  and for a local file its size and `mtime_ns`; for DuckDB the DB file's size and `mtime_ns` and
  the relation's column names from `describe_relation`; for any row-64 cloud kind the safe
  identity facts that its public capability descriptor supplies). A mismatch refuses the resume
  with `init.draft_stale` and offers a fresh scan.
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
  user picks mask or generate. Generate-from-snapshot is offered only for a CSV source because
  `fit_exact_snapshot` is CSV-only; other formats continue to P1b's schema-only column editor.
  P1a first exports one non-exiting public seam from `decoy.cli.gen` that owns fit, layout,
  validation, opt-in column discovery, staging and `_atomic.publish_local_targets`. Both
  `scaffold_generate` and the wizard call it; command-specific code alone maps its typed errors
  to output and exits. When the seam reports real-category columns, the wizard names those
  columns and asks an explicit, default-no prompt before writing `allow_real_categories: true`.
  Refusal keeps them withheld. The renderer remains the shared pipeline renderer.
- Failure modes: a copied fit; real categories written without the notice; the snapshot written
  and the pipeline write failing (orphan snapshot).
- AT-P1a.1: off then on restores answers.
- AT-P1a.2: the exported seam is the only generate-scaffold call in `cli/wizard/`, and both the
  preset command and wizard route reach it. Mutation: call `fit_exact_snapshot`, validation or
  `publish_local_targets` directly from the wizard, red.
- AT-P1a.3: the snapshot and layout equal the preset route for the same CSV. A real-category
  column is withheld after a no answer and gains `allow_real_categories: true` only after an
  explicit yes; canaries never appear in stdout, `-v`, `--json` or errors.
- AT-P1a.4: inject a failure on each member of `publish_local_targets`; the old pair is restored
  or neither new file exists. This is the existing paired-publish contract, not manual cleanup.
- AT-P1a.5: CSV offers fit; Parquet, fixed-width, DuckDB and cloud sources do not call the fit and
  enter P1b schema-only editing.

**P1b. Generate column editor.** R1, CLI, ~500.

- Guarantee: per column the user picks a type from EG1 and fills required options by wire type;
  common options (`null_probability`, `determinism`, `output_type`, `pooled`, `unique`) are
  offered; `row_count` and `unique_together` per table. The Secrets Generate branch names the
  environment variable `DECOY_MASTER_KEY` without reading its value and may add `--key-label` to
  RC. It never asks for, stores or prints the raw 64-hex `--master-key` value.
- AT-P1b.1: every catalog type can be configured from catalog examples (per-step AT).
- AT-P1b.2 (C3): a generate type name in a comparing position, red.
- AT-P1b.3: `required_when` and `one_of` enforced from the catalog. Mutation: ignore
  `required_when`, red.
- AT-P1b.4: `unique_together` naming a missing column is refused with the engine reason.
- AT-P1b.5: a 64-hex canary in `DECOY_MASTER_KEY` never appears in RC output, answers, drafts,
  `--json`, logs or errors; only the name `DECOY_MASTER_KEY` and chosen key label may appear.
- AT-P1b.6: the Set by hand checklist names every Q12 advanced key. Omitting them uses engine
  defaults; an invalid hand-added option is reported by key name without echoing its value.
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
- AT-P2.5: when either end is sampled, relationship facts and the Review screen say `sampled` and
  show no orphan or complete-overlap verdict.
- Depends on EG5 repinned.

**P3. Subset step.** R2, CLI, ~450.

- Guarantee: seeds of mode `filter` (ops from the engine literal) and `sample` (`count` or
  `fraction`), and `budget`. Parquet sources are checked before the step (engine reason
  `subset_requires_parquet`). Predicate values are allow-listed data (G2a).
- AT-P3.1: filter and sample sessions validate; `decoy subset --dry-run` accepts the result.
- AT-P3.2: a CSV source with Subset in the goal is told before the step. Mutation: skip the
  check, red.
- AT-P3.3: a seed naming a removed table is marked stale.
- AT-P3.4: a predicate value canary appears in the pipeline, draft and answers only, never in
  `-v` logs, `--json`, the summary or error text.
- Depends on P2, P1a.

**P4. Answers files.** R2, CLI, ~500.

- Guarantee: record plan 4.4. `decoy-init-answers/v1` strict model built from each step's
  F0 `answers_model` (C7). `--answers FILE` runs with no prompts. `--save-answers FILE` writes
  owner-only bytes atomically through `_atomic.write_local_target(..., CREATE_ONCE)`; it does not
  use `create_private_exclusive` as a writer. `unlisted: skip|confirm`; a stale confirm raises
  `pre_scan.review_stale`; `--fail-on-warning` maps warnings to exit 2. P4 is the only answer
  serializer and drafts embed its typed object.
- The schema is not frozen at P4. Later slices add their step models. The snapshot is taken and
  frozen when row 32b closes (M3).
- AT-P4.1: every step's answers round-trip; an answers run equals the terminal run.
- AT-P4.2: strict-type and version cells as AT-B7.2, with `init.answers_invalid`.
- AT-P4.3: an existing file is not overwritten. Mutation: replace mode, red.
- AT-P4.4 (C7): a step without `answers_model`, red.
- Depends on F0 and Y0.

**P5. Step selection and dry flags.** R1, CLI, ~300.

- Guarantee: `--skip` and `--only` take step ids from `STEPS`, matched with `re.fullmatch`;
  `--no-validate` skips only the final full engine validation and says so; it never skips
  `write_blocking_findings` or any pre-write safety gate. `--diff` prints the YAML diff and
  writes nothing (exit 0).
- AT-P5.1: an unknown id and `"fields\n"` are usage errors (exit 1).
- AT-P5.2: `--diff` leaves the tree byte for byte unchanged. Mutation: write before diff, red.
- AT-P5.3: with `--no-validate`, a blocking gate finding still refuses before any file write.
  Mutation: guard `write_blocking_findings` behind final validation, red.

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
  `_atomic.write_local_target(..., CREATE_ONCE)` and tells the user to compare and move it. The
  original is unchanged. If the span that would be replaced contains a comment, refusal does not
  write `.new`; the comment must be preserved through a supported span or the user edits by hand.
- AT-W3.1b.1 (hostile corpus, AT-W13 style) per span kind: comments, blank lines, reordered
  blocks, end of file without newline, CRLF, a comment inside the span, a key that is a prefix of
  another key. Every byte outside the span is unchanged.
- AT-W3.1b.2: non-comment refusal cases write `<file>.new` once with mode 0600; a second run with
  `.new` present refuses without overwriting it. A replaced span containing any comment leaves
  both original and `.new` unchanged.
- AT-W3.1b.3: a comment directly above `subset:` moves with the block; a comment after a blank
  line stays. Mutation: drop the comment-above rule, red.
- Depends on W3.1.

**P7. `decoy edit <section> <pipeline>`.** R2, CLI, ~450.

- Guarantee: runs one step over an existing pipeline and writes its span through W3.1b; the
  `edit` verb is registered from `cli/wizard/_edit.py`. It always shows the exact diff and asks
  for confirmation before the write; answers mode requires an explicit `confirm_write: true`.
- AT-P7.1 (round-trip property): full flow with answers A equals the same sections run one at a
  time through `decoy edit`.
- AT-P7.2: every byte outside the edited span is unchanged, for each section.
- AT-P7.3: a file changed between read and write gives `init.yaml_changed`. Mutation: drop the
  hash check, red.
- AT-P7.4: every route shows the diff before its write. A no answer, or missing
  `confirm_write: true` in answers mode, leaves the file unchanged. A span with a comment is
  preserved or refused without `.new`.
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
  - Evidence remains Hand. C2 locates or creates `.decoy-ci.yaml` at the wizard project's Git
    top-level, or at the project root when it is not a Git work tree. The checklist explains that
    `decoy run --evidence-out` produces the evidence manifest outside `decoy-ci`, and that
    `checks.evidence[].manifest` is a safe path relative to the directory containing
    `.decoy-ci.yaml`. `load_manifest` contains the resolved file in the Git top-level, falling
    back to the manifest directory outside Git. Absolute paths and `..` are refused by `RepoPath`.
  - A pipeline outside that repository cannot be added. It is refused before either file changes
    with `init.ci_pipeline_outside_repo`.
- Order: the pipeline is written first; the manifest after. If the manifest write fails, the
  pipeline stays, and the error names the manifest step and either the safe `<file>.new`
  fallback or the required manual edit when a comment prevents that fallback.
- AT-C2.1: append to a manifest with comments; other bytes equal; the result loads.
- AT-C2.2: duplicate id refused; `"ci\n"` refused.
- AT-C2.3: with an explicit `validation.pipelines`, the id is appended there and the manifest
  loads; with "no", the checklist line appears. Mutation: skip the list append, red (the loader
  still accepts, so the AT asserts the list).
- AT-C2.4: `validation.enabled: false` gives the warning.
- AT-C2.5: a 32-pipeline manifest gives `init.ci_manifest_full`, file unchanged.
- AT-C2.6: pipeline write fails, manifest unchanged. Mutation: write the manifest first, red.
- AT-C2.7: pipeline written, manifest write fails; pipeline kept, a non-comment fallback may be
  written as `<file>.new`, and the command exits `EXIT_PARTIAL` (6). This is a partial two-file
  operation, not a runtime failure: the usable pipeline committed but CI registration did not.
- AT-C2.8: an evidence manifest path is entered only by a hand edit; absolute and `..` forms are
  refused by the contract. A pipeline outside the manifest repository gives
  `init.ci_pipeline_outside_repo`, exit 1, with neither file changed.
- AT-C2.9: a hand-authored, contained evidence path that is missing loads as a valid CI manifest
  and `decoy ci` reports the existing value-free reason `ci.input_missing`.
- Depends on C1, W3.1b, RC.

### 7.6 Report versions for W3.2

W3.2 reads `post-scan-integrity/v3`. It also reads v2 and treats a v2 report without
`tables_checked` as covering no table (every finding shown, none auto-dismissed). Unknown major
and missing tag are refused with `init.report_schema`.

## 8. Class table

### 8.1 Plan-contract classes

| # | Class | Applies to | Structure | Proof | Mutation |
|---|---|---|---|---|---|
| 1 | Value-bearing output | B1 ruler, B2 locations, B3 paths, B5 allowed values, P1a snapshot values, P3 predicates, B7 drafts, P4 answers | value-free `init.*` errors; `ScanSetCore` only in drafts; G2a allow-list and G2b matrix | canary corpus over every surface per step | pass a raw value into a summary line |
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
| 1 | Anchored validation | step ids, CI ids, table names | AT-P5.1, AT-C1.4, AT-C2.2 (value plus `"\n"`) |
| 2 | Strict wire types | answers, drafts, catalog wire types | AT-B7.2, AT-P4.2, AT-EG1.3 |
| 3 | No exception context | `init.source_unreadable`, draft and answers errors | AT-B3.4, AT-B7.2 assert `__context__` None |
| 4 | Versioned read models | draft, answers, report v2/v3 | AT-B7.2, AT-P4.2, 7.6 cells |
| 5 | Normalized guard scanners | C3, C4 | covered spellings listed in section 6; one seeded case each |
| 6 | No private imports | wizard to engine; wizard to `cli/io` | public `decoy_engine` names and the `decoy.cli.io` facade only; EG1 to EG5 export what the wizard needs |
| 7 | No hidden CI failures | new sentries | registered in `SENTRIES`; no skip markers |
| 8 | One input, one trust class | `.gitignore` program patterns vs user-chosen paths | separate named entry points share one escape/write core; user forms are proved by `git check-ignore` |
| 9 | Mutations on the final head | every slice | section 12 |
| 10 | Allowlisted helpers still checked | C4 `apply_edits`, C6 `render_manifest` | exact `(path, name)`; caller list checked (AT-B7.6, AT-C1.2) |
| 11 | No raised caps | module size, fan-out, init.py pin | section 10 |

## 9. Enumerations

### 9.1 New exit paths that own files or state

| Owner | Exits |
|---|---|
| DuckDB staging (B3) | success, cancel at each step, scan error, gate refusal, write error, interrupt, stale sweep |
| Draft (B7) | `q`, cancel, interrupt, success (removed), failed write (kept), bad draft, stale draft |
| Snapshot pair (P1a) | both published; failure staging, validating or publishing either member restores the old pair or leaves neither new member; fit fails before staging |
| Answers save (P4) | success, file exists, parent missing, write error |
| `.gitignore` (B5, B7, T1) | added, already present, missing (created), symlink refused, write error |
| Editor writes (W3.1, W3.1b, P7, C2) | success, hash changed, unsupported span (`.new` written), `.new` exists, symlink, write error |
| Manifest (C1, C2) | new file, append, duplicate id, full, invalid existing manifest, pipeline write failed first, pipeline written then manifest failed |
| CI repository containment (C2) | manifest found from repository root, pipeline inside, pipeline outside, absolute path, `..` path, missing hand-authored evidence manifest (`ci.input_missing` at CI run time) |

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
- one child with two different parents;
- two child columns referencing one parent in one namespace, such as `created_by` and
  `updated_by`;
- a column that is both a parent key and a child key;
- a chain (A to B to C);
- a child whose source is cloud: facts and candidates report `skipped_cloud`
  (`profiling/_scan_integrity.py:176`);
- either end sampled: facts and candidates report `sampled`, without an orphan or complete
  overlap verdict;
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

### 9.5 Output-surface matrix

`No` means planted canaries must be absent. `Allow-list` means only G2a's confirmed data classes
may appear. `Location` means only the user-typed location fields covered by G2b may appear.
Names and config structure are not values under the standing rule.

| Surface | Input data values | Secrets and credentials | User-typed locations | Exception text |
|---|---|---|---|---|
| prompts, summaries, Review, checklist | No | No | No | No |
| printed run command | No | No | Location, only flags that require it | No |
| stderr errors and parse errors | No | No | No | No |
| `--json` | No | No | Location only inside its run-command field | No |
| `-v` and other logs | No | No | No | No |
| notifications | No | No | No | No |
| pipeline YAML | Allow-list | secret references only, never values | Location | No |
| snapshot | P1a confirmed fit policy only | No | No | No |
| draft and answers | Allow-list | references and the name `DECOY_MASTER_KEY`, never values | Location | No |
| `.gitignore` | No | No | escaped literal path only | No |
| `.decoy-ci.yaml` and `.new` | No | No | repository-relative pipeline paths only | No |
| generated output and quarantine | engine-owned job behavior, not wizard diagnostics | No | No | No |
| help text | No | names such as `DECOY_MASTER_KEY` only | No | No |

Each new slice adds every surface it reaches to the shared canary test. The test plants distinct
canaries in raw cells, each allow-listed data class, secret/key material, bucket, object key,
endpoint, DB path, DSN and exception text so a permissive assertion cannot confuse classes.

## 10. Placement

| New file | Directory | CODEMAP row | Sits beside |
|---|---|---|---|
| `steps/_locations.py`, `_fixed_width.py`, `_duckdb.py`, `checks.py`, `quality.py`, `generate.py`, `relationships.py`, `subset.py`, `detectors.py`, `tokenize.py` | `src/decoy/cli/wizard/steps/` | "Interactive review wizard" (added by W1a.0) | 1a step modules |
| `_draft.py`, `_answers.py`, `_run_command.py`, `_yaml_edit.py`, `_edit.py`, `_findings.py`, `_ci_step.py` | `src/decoy/cli/wizard/` | same | `_flow.py` |
| `_yaml_marks.py` (target) | `src/decoy/` | "Shared YAML document structure and source-mark indexing" (added by Y0) | `_atomic.py` |
| `emit.py` (target) | `src/decoy/ci/` | "CI integration" (`src/decoy/ci/<concern>.py`) | `manifest.py` |
| cloud capability fact (edit, no new file) | `src/decoy/cli/io/_cloud.py`, exported by `io/__init__.py` | "Project layout services" | the gate tables it derives from |
| `append_gitignore_line` (function, no new file) | `src/decoy/cli/io/_project.py` (251 lines now), exported by `io/__init__.py` | "Project layout services" | `write_decoy_gitignore`; C5 also names existing `_layout.py` writers |
| public generate scaffold seam (edit, no new file) | `src/decoy/cli/gen/_scaffold.py`, exported by `gen/__init__.py` | existing generation package | `scaffold_generate` |
| `sample_rows` option (no new file) | `src/decoy/cli/_duckdb_source.py` | existing flat module, edited in place | |
| `_config_coverage.py`, `test_config_coverage.py`, `test_wizard_writes.py` | `tests/sentry/wizard/` | wizard sentry row (1a) | 1a wizard sentries |
| unit and e2e tests | `tests/unit/wizard/`, `tests/e2e/wizard/` | wizard row | 1a tests |
| engine `_generate_option_catalog.py` (edit) | `decoy_engine/config/` | engine config | |
| engine `validators/_catalog.py` (target) | `decoy_engine/validators/` | engine validators | `_registry.py` |
| engine `quality/_freetext_advisory.py` (edit), `column_review_flags` | `decoy_engine/quality/` | engine quality | |
| engine `FieldCore` additive fields (edit) | `decoy_engine/profiling/scan_set.py` | engine profiling | `_field_core` |
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
| F0 | CLI | ~180 | R1 | W1a.6b | no |
| RC | CLI | ~250 | R1 | F0 | no |
| V0 | CLI | ~500 | R1 | F0, RC | no |
| B1 | CLI | ~450 | R1 | B2 | no |
| B2 | CLI | ~500 | R2 | W1a.6b; row 64 CLI source and target slices | no |
| B3 | CLI | ~400 | R1 | B2, RC | no |
| B4 | CLI | ~400 | R2 | W1a.6b; EG3 repinned | no |
| B5 | CLI | ~500 | R2 | B2; EG2 repinned | no |
| B6 | CLI | ~300 | R1 | B5, RC | no |
| B7 | CLI | ~500 | R2 | F0 | no |
| B8 | CLI | ~250 | R1 | B5, B6 | no |
| P1a | CLI | ~400 | R2 | RC | no |
| P1b | CLI | ~500 | R1 | P1a; EG1 repinned | no |
| P2 | CLI | ~500 | R2 | W1a.6b; EG5 repinned | no |
| P3 | CLI | ~450 | R2 | P2, P1a | no |
| P4 | CLI | ~500 | R2 | F0, Y0 | no |
| P5 | CLI | ~300 | R1 | P4 | no |
| W3.1 (record plan) | CLI | ~540 | R2 | Y0, W1a.6b | no |
| W3.1b | CLI | ~450 | R2 | W3.1 | no |
| P7 | CLI | ~450 | R2 | W3.1b, P4 | no |
| W2 (record plan) | CLI | ~460 | R1 | W1a.6b; SCAN-ML M3b released | no |
| W3.2 (record plan) | CLI | ~590 | R2 | W3.1; E2 repinned; C2a merged | no |
| T1 | CLI | ~400 | R2 | P1a, RC; EG4 repinned | no |
| C2 | CLI | ~400 | R2 | C1, W3.1b, RC | no |

Totals: 26 CLI slices, about 10,720 lines (of which W2, W3.1 and W3.2, about 1,590, were sized
in the record plan). 5 new engine slices, about 1,850 lines. E1 and E2 were sized in earlier
plans.

Before S3a.1 unblocks 1a: E1, E2, EG1, EG2, EG3, EG5 (then EG4), Y0 and C1. About 2,400 new lines
plus E1 and E2, none of which needs the renderer.

Order after W1a.6b: F0, then RC, then V0, then lanes with one writer per file. RC precedes V0
because V0 walks `FLAG_COVERAGE`:

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
| Engine public exports | additive: `validator_catalog`, `column_review_flags`, `ReviewFlag`, `relationship_candidates`, `RelationshipCandidate`, `StrategyInfo.vault_eligible`, catalog fields; additive value-free `FieldCore.avg_length` and `.value_set_size_class` |
| `acquire_relation` | additive keyword `sample_rows`; default behavior unchanged |
| Exit codes | none |
| `init.*` reason codes | additive in the central registry: `init.draft_invalid`, `init.draft_stale`, `init.answers_invalid`, `init.yaml_changed`, `init.yaml_edit_unsupported`, `init.yaml_symlink`, `init.report_missing`, `init.report_schema`, `init.report_stale`, `init.source_unreadable`, `init.ci_manifest_full`, `init.ci_pipeline_outside_repo` |

## 14. Roadmap row 32b text (for the roadmap owner; this plan does not edit ROADMAP.md)

> **32b INIT-WIZARD (V1, owner 2026-11-17: "a working wizard to configure a job is v1").**
> `decoy init` configures any V1 job whose execution path is present. It configures local,
> fixed-width and DuckDB sources and local/fixed-width targets; after row 64's CLI execution
> slices merge, it derives and offers the executable S3/GCS source and target kinds and fields
> from `decoy.cli.io`, with delivery mode. It also configures mask, generate, subset and tokenize goals;
> pre-scan and post-scan detectors and the scan baseline; per-field strategies in every-field or
> flagged-only review; generated columns and table uniqueness; relationships from engine
> candidates; subset filter and sample seeds with budget; post-scan integrity, validators and
> quarantine; quality settings; secrets and the vault; the printed run command; and the CI
> manifest. Answers files, drafts and resume, `decoy edit`, and post-scan findings review
> included. Plans: Phase 1a `docs/plans/2026-11-08-init-wizard-phase-1a.md`; the rest
> `docs/plans/2026-11-17-init-wizard-v1-rest.md`. A coverage sentry fails CI for any config
> field, CI manifest field or run flag with no wizard entry. Rows 64, 64b, 86, 87, 81, 68, 69 and 32
> add their own wizard entries. V2: arrow keys and completion, before and after previews. After:
> SCAN-MULTI S3a.1 (1a), row 64 CLI source and target execution slices (B2), engine R-1a and
> R-1b, SCAN-ML M3b (W2), C2a (W3.2).

## 15. Owner questions and answers

| # | Question | Answer |
|---|---|---|
| Q1 | Tokenize goal offers both the `tokenize` strategy and `vault: true` on eligible strategies? | Both (taken as recommended, 2026-11-17) |
| Q2 | Validator list from an engine catalog (EG2)? | Engine catalog (taken as recommended) |
| Q3 | Keep `decoy init --review-findings PIPELINE --report FILE`? | Keep (taken as recommended) |
| Q4 | Rows 64, 64b, 86, 87, 81, 68, 69 and 32 each ship their wizard entry, enforced by V0? | Yes (taken as recommended) |
| Q5 | DuckDB stays a run flag in V1? | Yes; a config kind is V2 (taken as recommended) |
| Q6 | Before and after previews? | V2 (owner, 2026-11-17) |
| Q7 | Preset pre-fill (B8) in V1? | Yes (taken as recommended) |
| Q8 | No new dependency? | None (taken as recommended) |
| Q9 | Append to an existing `.decoy-ci.yaml` through the editor? | Yes, with the hash check and a diff first; `.new` fallback (taken as recommended) |
| Q10 | `scan_baseline.on_drift` belongs to row 32 DRIFT? | Yes (taken as recommended); `path` and `schema` are in the Scan step |
| Q11 | Relationship candidates come from a new engine slice EG5? | EG5 (Dennis round 1, taken under go-with-recommended) |
| Q12 | The spec 7 column keys (`when`, `coherent_with`, `cardinality_mode`, `error_policy`, `logical_type`, `parse_format`, `output_format`, `backend_type`, `backend_version`, `scale`, `pool_size`, `allow_collisions`, `dtype`, `sentinel_to_null`) stay hand-set in V1, named under "Set by hand"? | Yes. Owner decided 2026-11-17: V1 writes defaults and errors name the keys; editing them stays manual |

### 15.1 Follow-ups outside V1

| Follow-up | Classification | Scope | Why not V1 |
|---|---|---|---|
| Opt-in Advanced column options step | V2-LOG | V1+ | Exposes the spec 7 per-column keys from Q12 after the working V1 wizard; V1 writes defaults and names each hand-edited key |
| Replace `build_config`'s direct `yaml.safe_dump` | DESIGN, pre-existing | Cleanup | `gen/_scaffold.py:126` predates this plan; P1a centralizes scaffold behavior but does not broaden into an emitter rewrite |

## 16. Pre-mortem

- 1a slips on S3a.1 and this plan waits. About 2,400 new lines plus E1 and E2 start now.
- Many lanes touch the shared files in 11 at once. F0, RC and V0 land first in that order; the shared files are
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
| H4 second `.gitignore` writer | `append_gitignore_line` stays in `decoy.cli.io`; rev 2's C5 uses an exact allowlist that also names the pre-existing `_layout.py` writers; `_gitignore.py` remains dropped |
| H5 `_safe_profile` | Dropped; drafts store `ScanSetCore`; AT-B7.3 kept |
| H6 P1a reuse | Rev 2 strengthens this to one public non-exiting `decoy.cli.gen` scaffold seam used by both routes; snapshot values are governed by G2a and 9.5; AT-P1a.2 to P1a.5 |
| H7 relationship candidates | New engine slice EG5; Q11; P2 uses EG5 only |
| H8 C2 and `validation.pipelines` | C2 appends to the explicit list (asks), warns on `enabled: false`, refuses at 32; AT-C2.3 to C2.5 |
| M1 cycles | AT-P2.1 split into a/b/c; cross-table cycles accepted |
| M2 DuckDB staging | `sample_rows`, private staging dir, stale sweep, value-free `init.source_unreadable` |
| M3 answers freeze | Per-step `answers_model` (C7); frozen at 32b close |
| M4 subset values | Added to G2a allow-list and class row 1; AT-P3.4 |
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

### Dennis round 2 on rev 1 (BLOCK, 0/4/11/6)

| Finding | Root fix in rev 2 |
|---|---|
| H1 cloud cannot execute | Cloud leaves are `Row("64")` until row 64's CLI slices merge; B2 depends on them and consumes one public `decoy.cli.io` fact derived from the gate tables; `sources.credentials_ref` is Hand; B5 uses the same fact; sections 1, 5.1, 7.3, 11 and 14 |
| H2 EG3 reads fit opt-in | EG3 adds value-free `FieldCore.avg_length` and `.value_set_size_class`; `HIGH_CARDINALITY` is exactly `unique|high`, with boundary and compatibility cells; sections 7.1 and 10 |
| H3 P1a duplicates private scaffold | P1a exports one non-exiting `decoy.cli.gen` seam used by the preset and wizard, keeps CSV-only fit, uses paired publish, and requires an explicit real-category opt-in; `build_config` emitter debt is logged in 15.1 |
| H4 `--master-key` is raw | `--master-key` is Hand/per-run and never a `RunFlag`; Secrets names `DECOY_MASTER_KEY` and contributes only `--key-label`; hex-canary AT-P1b.5 and the 9.5 matrix cover all surfaces |
| M1 G2 conflates value classes | Split into G2a data/secrets and G2b user-typed locations; section 9.5 gives a per-surface matrix |
| M2 `.gitignore` baseline and escaping | C5 lives in `decoy.cli.io`, names the existing `_layout.py` writers and new append function by exact identity, escapes every Git metacharacter and trailing space, refuses newline, and proves behavior with `git check-ignore` |
| M3 empty private-file helper | D6, reuse, B7, P4 and W3.1b now use `_atomic.write_local_target` with `CREATE_ONCE` or `REPLACE`; `create_private_exclusive` is described only as an empty reservation |
| M4 roadmap state parsing | V0 matches the case-insensitive leading token, longest first, recognizes `PARTLY MERGED` and `plan rev N GO` as open, and fixtures every referenced row's current cell |
| M5 C1 depends on a later sentry | C1 owns its own exact-identity dumper sentry over `src/decoy/ci/`; S3a.1 later folds the identity into G-ONE-EMITTER |
| M6 answers protocol lands too late | New base slice F0 owns `answers_model`, C7 and the shared typed object before RC and V0; P4 is the only serializer |
| M7 evidence provenance and containment | Evidence is Hand, its repository-relative location rule and runtime `ci.input_missing` are explicit, and C2 refuses an outside-repository pipeline with `init.ci_pipeline_outside_repo`; sections 1.3, 7.5 and 9.1 |
| M8 missing FK shapes | Section 9.3 and P2 now cover a child with two parents, two child columns to one parent namespace, and a column that is both parent and child key |
| M9 sampled relationship evidence | EG5 and P2 use explicit `sampled` status and suppress false overlap/orphan verdicts |
| M10 nonexistent mixed mode | RC never prints `--mode`; `mixed` is removed from the state and AT-RC.1 |
| M11 comment-bearing fallback and preview | W3.1b refuses without `.new` when the replaced span contains a comment; P7 always shows a diff and requires confirmation before write |
| L1 ordering | Section 11 orders F0, RC, then V0 because V0 consumes `FLAG_COVERAGE` |
| L2 paired writer sentry | `_atomic.publish_local_targets` is in C4's exact helper list and its callers are checked |
| L3 partial exit | AT-C2.7 uses existing `EXIT_PARTIAL` 6 because one member of the user-requested pipeline/CI registration pair committed |
| L4 `--no-validate` | P5 states and proves that it never skips `write_blocking_findings` |
| L5 per-step path coverage | Section 7 defines `config_paths` equality over the union of the step's scripted sessions |
| L6 private DuckDB staging and vault test | AT-B3.1 requires project-local mode 0700; AT-EG4.1 installs `cryptography` and sets a namespace |
