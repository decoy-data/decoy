Status: plan

# GEN-CATALOG: finish the generation catalog (CLI roadmap row 24s)

Owner: Cam. Author: Opus plan agent. Date: 2026-11-17. Revision 1.
Scope: one engine slice (GC3-E) and one CLI slice (GC3). Most of the row is already merged; this
plan closes what is left and updates the row.

Rules consulted: `dev-rules/README.md` (routing), `00-universal.md`, `risk-and-exceptions.md`
(R1 tier), `development-loop.md` (PLAN and Proportion: guarantee, size, design notes, choke
point, Placement), `profiles/local-operations.md` (review tiers, docs-current), 
`cross-cutting-concerns.md` (one kinds table), `api-and-compatibility.md` (an additive public
engine name, an additive CLI list kind and JSON key), `catalogs/recurring-defects.md`. Also CLI
`CODEMAP.md` "Where Things Go" (lines 48, 56, 65), engine `CODEMAP.md` "Where Things Go" (Public
API and Transforms rows), engine `docs/frozen-surfaces.md` (Execution row), CLI
`docs/cli-reference.md` and `tests/unit/test_cli_surface.py` (the surface pin), and the V1 bar
(only a function break, data loss, a non-admin value leak or cascading design blocks V1).

Bases: CLI `origin/main` `4e6d60ba` (#307), engine `origin/main` `b2f37cd3`, CLI pin
`decoy-engine==0.27.0`. Line numbers below are from those heads.

## 1. Source and what is already done

Source, in this order:

1. Roadmap row 24s (CLI `docs/ROADMAP.md:288`): "a CLI command that lists every generate type and
   option, and every provider, from the engine's registries (no hand-kept list); one generate
   starter template per industry (healthcare, banking, insurance, retail, telecom, HR)". The row
   still says "NOT STARTED; plan needed". That is stale.
2. The completeness audit `docs/records/2026-11-08-generation-completeness-audit.md`. The row
   cites section C, but the matching items are gap F4 (a column-type catalog command), gap F5
   (industry starter templates) and section 4 (the user cannot learn the type list from the
   product; domain providers and Faker names are two registries and the wrong one fails
   silently).
3. The earlier plan section B1.3 on engine branch `plan/f1-bucket-perturb-and-unplanned`
   (`docs/plans/2026-11-16-f1-bucket-perturb-and-unplanned.md:357`). It split the row into GC1
   and GC2 and passed review. Both slices are merged.

What is built (do not rebuild):

| Piece | Where | Merged |
|---|---|---|
| `decoy list generate-types [--json]`: every type with required and optional options and the common options, read from `generate_option_catalog()` | reader `src/decoy/cli/cockpit.py:254`; projection `type_entries()` in `src/decoy/cli/gen/_topic.py:58`, shared with `decoy explain generation` | GC1, CLI #299 (`55cd4a05`, 2026-11-16) |
| `decoy list faker-types [--json]`: every `faker_type` value, from `decoy_engine.list_generate_faker_providers()` | `src/decoy/cli/cockpit.py:295` | GC1, CLI #299 |
| `decoy list providers [--json]`, `decoy show provider NAME`: every provider in `providers_v2.get_default_registry()` with its capabilities | `src/decoy/cli/cockpit.py:181`, `:330` | before this row |
| Six templates `generate-healthcare`, `-banking`, `-insurance`, `-retail`, `-telecom`, `-hr`: three tables each, foreign keys through `reference` columns, with faker, categorical, sequence and `constant` values | `src/decoy/templates/generate-*.yaml`, `_REGISTRY` in `src/decoy/templates/__init__.py:23` | GC2, CLI #302 (`419572a2`, 2026-11-16) |
| Registry-driven template tests: `validate config` exit 0, `run` exit 0, row counts, FK links, at least one FK per industry template, every `type`, option and `faker_type` in the live engine catalogs, no snapshot or disguise marker, key columns are references | `tests/e2e/test_bundled_templates_e2e.py:202` to `:290`; expected names `tests/generate_industry_templates.py` | GC2, CLI #302 |

The gaps this plan closes, each checked in code:

- G1. `lookup` has a `one_of` rule (exactly one of `file`, `codeset`; the `"lookup"` entry of
  engine `config/_generate_options.py`). The CLI projection drops it: `type_entries()` copies
  `required`, `optional` and `required_when` only (`src/decoy/cli/gen/_topic.py:58` to `:76`).
  `decoy list generate-types` and `decoy explain generation` therefore show `lookup` with no
  required option and both keys optional, which reads as "neither is needed".
- G2. The value list for `lookup` `codeset` (and for the mask `code_set` strategy's `code_set`
  option) is not listable. Names and descriptions sit in the engine's private
  `transforms/_codeset_provenance.py` `CODESET_REGISTRY`. The public surface has only the names,
  in a module outside `decoy_engine.__all__` (`transforms/code_set.py:559` `SHIPPED_CODE_SETS`).
  A user writing `type: lookup` cannot learn that `icd10`, `hcpcs`, `ndc` and `mcc` exist.
- G3. `decoy list providers` says it lists "every registered generation provider" (docstring,
  `src/decoy/cli/cockpit.py:194`) and the `list` epilog says "Every generation provider as JSON"
  (`src/decoy/cli/reference.py:130`). These are the masking domain providers. A generate column
  cannot use any of them until row 24p (GEN-PROVIDERS) ships `type: provider`. The wording is the
  "two registries, wrong one fails silently" trap from audit section 4.
- G4. The list of kinds is written three times by hand: the argument help
  (`src/decoy/cli/reference.py:152`), the epilog "Kinds:" line (`:141`) and the `list_`
  docstring (`:166`), beside the real table `_LIST_READERS` (`:110`). A new kind that misses one
  of them fails nowhere.
- G5. The six templates use `faker random_int` for money. The earlier plan said they should use
  the GEN-TYPES types where they fit. `lookup` with a shipped code set, `distribution` and
  `output_type` are all in the pinned engine `0.27.0` (GEN-TYPES E1, E2 and E3 are in `v0.23.0`
  and later).
- G6. The template test runs `decoy validate config` only
  (`tests/e2e/test_bundled_templates_e2e.py:234`), which is the schema and config layer. The
  plan-compile checks (for example the shipped code-set name check in engine
  `plan/checks/_lookup_tables.py:174`) and preflight are not run. The gate a user runs is
  `decoy validate CONFIG` (config, compile and preflight).
- G7. Docs are stale: roadmap row 24s and QA checklist row GEN-14
  (`docs/qa/cli-v1-checklist.md:377`) both say not built.

## 2. Guarantee and non-goals

### The guarantee (pinned)

After GC3, from the installed CLI, with no hand-kept list:

- `decoy list generate-types` shows, for every type in `generate_option_catalog()`, its required
  options, its optional options, its exactly-one-of group when it has one, its conditional
  requirements, and the common options. `--json` carries the same, with a `one_of` list on every
  entry.
- `decoy list faker-types` shows every `faker_type` value (unchanged).
- `decoy list codesets` shows every shipped code set with its one-line description, read from a
  new public engine function `code_set_catalog()`.
- `decoy list providers` shows every registered domain provider (unchanged data) and says that
  they are masking providers.
- Every bundled generate template passes the whole `decoy validate` gate (exit 0) and a small
  `decoy run`, its foreign keys link, and every `type`, option, `one_of` group, `faker_type` and
  `codeset` it uses is in the live engine catalogs.
- The industry templates use `lookup` code sets where a shipped set fits and `distribution` with
  `output_type: decimal(2)` for money columns.

### Non-goals

- Which providers a generate column can use. None can today; row 24p adds `type: provider`. The
  generate-usable marker on `list providers` belongs to 24p (OQ-1).
- Allowed values of enumerated options other than code sets (for example
  `reference.distribution`, `derived_aggregate.op`, `grouped_series.generator`,
  `windowed_date.distribution`). The `distribution.family` values already show through
  `required_when`. The rest are checked in several engine modules at config or plan time and
  have no single registry to read (OQ-2, follow-up F-1).
- A `show codeset NAME` detail view, code counts, or provenance fields beyond the description.
- New templates, new industries, more tables per template, or templates that read a file.
- Changes to the mask templates, to `decoy init`, or to `explain` topics other than `generation`.

## 3. Established solutions

R1 change; the development loop requires the external search for R2 and R3 only. The
in-codebase reuse search was run: grep of both repos for `generate_option_catalog`,
`list_generate_faker_providers`, `SHIPPED_CODE_SETS`, `CODESET_REGISTRY`, `strategy_catalog`,
`_LIST_READERS` and `list templates`, and `git log` for row 24s (which found GC1 and GC2).

| Need | Existing pattern | Followed here |
|---|---|---|
| A public read-only view of a private engine registry | `generate_option_catalog()` (`config/_generate_option_catalog.py:103`) and the root export `strategy_catalog` | `code_set_catalog()` reads `CODESET_REGISTRY`, returns names and descriptions only |
| A CLI list kind over a live registry | `_faker_types_list` (`cockpit.py:295`): one engine call, JSON envelope `command`, `status`, `count`, list | `_codesets_list`, same shape |
| One projection behind `list` and `explain` | `type_entries()` in `gen/_topic.py` | extended with `one_of`; no second projection |
| Registry-driven template tests | `_generate_names()` (`test_bundled_templates_e2e.py:209`) | kept; the whole gate replaces `validate config` |

No new dependency.

### Reuse inventory

| Need | Reused | Where |
|---|---|---|
| Code set names and descriptions | `CODESET_REGISTRY` | engine `src/decoy_engine/transforms/_codeset_provenance.py:254` |
| Generate types, options and `one_of` | `generate_option_catalog()` | engine `src/decoy_engine/config/_generate_option_catalog.py:103` |
| Faker type names | `list_generate_faker_providers()` | engine `src/decoy_engine/internal/faker_setup.py:608` (root export) |
| List JSON envelope and output modes | `setup_output`, `emit_json`, `make_table` | `src/decoy/cli/cockpit.py:31` to `:32` imports |
| Template registry | `list_templates`, `get_template` | `src/decoy/templates/__init__.py:42` |

## 4. Behavior

### 4.1 GC3-E (engine): public code set catalog

- New function in `src/decoy_engine/transforms/code_set.py`, beside `SHIPPED_CODE_SETS`:
  `code_set_catalog() -> dict[str, str]`, shipped code set name to its `description`, in name
  order, built from `CODESET_REGISTRY` on each call. It returns a new dict and reads no corpus
  file.
- Exported from `decoy_engine.__all__` beside `strategy_catalog`.
- `SHIPPED_CODE_SETS` is unchanged. Both come from `CODESET_REGISTRY`.
- Docs: the Execution row of `docs/frozen-surfaces.md` gains the name; one "Pre-GA additive name"
  entry in `docs/compatibility-contract.md`; one `changelog.d/` fragment.

### 4.2 GC3 (CLI)

GC3 starts on a CLI `main` that pins an engine release holding GC3-E. The daily engine release
train and the usual repin carry it; the repin is not part of this slice.

1. **`one_of` in the projection (G1).** `type_entries()` adds `"one_of": list(spec.one_of)` to
   each record. `type_lines()` prints `      exactly one of: file, codeset` for a type with a
   group. The `list generate-types` table shows `one of: file, codeset` in the Required cell,
   after any required keys. JSON carries the key on every entry (an empty list when there is no
   group).
2. **`decoy list codesets` (G2).** `_codesets_list(json_, quiet, verbose)` in `cockpit.py`, beside
   `_faker_types_list`, calls `decoy_engine.code_set_catalog()`. Human output: a heading with the
   count, a two-column table (Name, Description), then a tip naming `type: lookup` with
   `codeset:` and the mask `code_set` strategy. JSON:
   `{"command": "list codesets", "status": "ok", "count": N, "codesets": [{"name": ..., "description": ...}]}`.
   Registered in `_LIST_READERS`; `"codeset": "codesets"` joins `_SINGULAR_TO_PLURAL` so
   `decoy list codeset` cross-suggests the plural.
3. **Kinds from one table (G4).** The argument help, the epilog "Kinds:" line and the docstring
   sentence that names kinds are built from `_LIST_KINDS` (the keys of `_LIST_READERS`). The
   epilog examples stay prose and gain one `decoy list codesets` example.
4. **Provider wording (G3).** The `_providers_list` docstring and the epilog line say "domain
   providers used by masking (`provider:` on a mask column)". The tip adds: "Generate columns use
   `decoy list faker-types` values." No data or column changes.
5. **`explain generation` tail.** One line after the common options: "Value lists:
   `decoy list faker-types` (faker_type) and `decoy list codesets` (lookup codeset)."
6. **Templates (G5).** YAML edits only:
   - healthcare `claims`: add `diagnosis_code` (`type: lookup`, `codeset: icd10`) and
     `procedure_code` (`type: lookup`, `codeset: hcpcs`); `amount_billed` becomes
     `type: distribution`, `family: uniform`, `low: 50`, `high: 5000`, `output_type: decimal(2)`.
   - banking `transactions`: add `merchant_category` (`type: lookup`, `codeset: mcc`); `amount`
     becomes `distribution` uniform 1 to 4000, `decimal(2)`.
   - insurance: `annual_premium` (150 to 4000) and `claim_amount` (100 to 25000) become
     `distribution` uniform, `decimal(2)`.
   - retail `order_lines`: `unit_price` (3 to 400) becomes `distribution` uniform, `decimal(2)`;
     `quantity` stays an integer.
   - hr: payroll `gross_pay` (`faker random_int` 1500 to 12000, `generate-hr.yaml:75`)
     becomes `distribution` uniform, `decimal(2)`.
   - telecom: unchanged (its numeric column is a call duration in seconds, an integer).
   - The header comment of each edited file names the types it now shows, in one sentence.
7. **Whole gate in the template test (G6).** `test_generate_template_validates_runs_and_links_keys`
   runs `decoy validate <config>` (the whole gate) instead of `decoy validate config <config>` and
   expects exit 0. The run and link checks stay.
8. **Catalog guard (G5, G6).** `test_generate_template_uses_only_catalog_types` adds two checks:
   for a type with a `one_of` group, exactly one key of the group is given; every `codeset` value
   is a key of `code_set_catalog()`.
9. **Docs (G7).** `docs/cli-reference.md` regenerated (the surface pin); `CHANGELOG.md` entry;
   roadmap row 24s status lists the merged slices (GC1 #299, GC2 #302, GC3-E, GC3) and DONE;
   QA checklist row GEN-14 text changes from "Not built" to the commands that check it
   (`decoy list generate-types`, `faker-types`, `codesets`, `providers`, `decoy list templates`).

## 5. Failure modes

| # | Failure | Handling |
|---|---|---|
| FM-1 | The whole `decoy validate` gate does not exit 0 on a generate-only config for a reason unrelated to the template (a preflight rule on `sources: {}`) | The builder stops and reports with the gate output. The template is not bent to pass and the test does not go back to `validate config`. A gate bug is a separate row (section 13) |
| FM-2 | The pinned engine refuses a template column (`lookup` codeset, `distribution`, `output_type`) | AT-5 fails at the builder's T1. Fix the template from the engine catalog; never widen the test |
| FM-3 | `code_set_catalog` is missing from the pinned engine | The CLI import-surface sentry (`tests/sentry/test_engine_import_surface.py`) fails. GC3 waits for the repin; no `getattr` fallback |
| FM-4 | A later engine release renames a code set, a type or an option | AT-6 fails in the CLI suite at that repin, not at a user's run |
| FM-5 | A new list kind is added without help text | AT-3 fails |
| FM-6 | The `icd10` corpus slows the template test | `row_count` is 30 per table; the lookup list is pinned once per column. If one parametrized case takes more than 10 s on the Mac, the builder stops and reports |
| FM-7 | `decimal(2)` reaches a fixed_width target, which refuses it | All six templates write CSV; AT-5 runs them |

Value-free: the listings print registry names, option names and the engine's fixed description
strings. Templates hold no real data; every value is generated. No log line is added.

## 6. Design notes and choke points

- No new structure: one public function in an existing engine module, one reader function in an
  existing CLI module, one key in an existing projection. No new file in either repo except the
  engine changelog fragment.
- One place per fact:
  - Code set names and descriptions: engine `CODESET_REGISTRY`; `SHIPPED_CODE_SETS` and
    `code_set_catalog()` both derive from it.
  - Generate types and options, including `one_of`: engine `GENERATE_OPTIONS` through
    `generate_option_catalog()`. The CLI's only projection is `type_entries()`.
  - List kinds: `_LIST_READERS`. Help, the epilog line and the docstring sentence derive from it.
  - Industry template names: `_REGISTRY` in `src/decoy/templates/__init__.py`. Tests read it
    through `_generate_names()`; `tests/generate_industry_templates.py` is the expected-set pin.
- Choke point for "every listing reads the engine": each list reader calls one engine function
  and holds no names. Guard: AT-1 and AT-4 compare CLI output with the engine function's result.
  Mutation: return a fixed tuple from the reader.
- `cockpit.py` grows from 694 to about 735 lines, under the 800-line cap
  (`tests/sentry/layout/test_module_size.py`). No baseline or allowlist moves.
- House style: the reader takes the same three concrete bools as its siblings; no flag argument.

## 7. Acceptance tests (red first)

Engine, `tests/unit/transforms/test_code_set.py` and `tests/unit/test_public_api.py` (existing):

- **AT-E1** `code_set_catalog()` keys equal `SHIPPED_CODE_SETS`, in the same order, and every value
  is a non-empty string. Catches: a hand list, or a catalog that drifts from the registry the
  compile check uses. Fails today: no such name.
- **AT-E2** `code_set_catalog` is in `decoy_engine.__all__` and on the frozen-surface map
  (`test_public_api.py` expected set; `tests/sentry/release/test_frozen_surface_map.py`).
  Catches: an export missing from the frozen map.
- **AT-E3** Two calls return equal but separate dicts; changing one does not change the next.
  Catches: the module registry handed out to callers.

CLI, `tests/e2e/test_reference_command.py` (existing):

- **AT-1** `decoy list codesets --json` exit 0; the `codesets` names equal `code_set_catalog()`
  keys in name order and each description equals the catalog's. Catches: a hand-kept list, a
  missing kind. Fails today: unknown kind, exit 1.
- **AT-2** `decoy list codesets` (human) exit 0 and names `icd10`. Catches: a reader that prints
  only in JSON mode.
- **AT-3** `decoy list --help` names every key of `_LIST_READERS`, and `decoy list nope` lists
  every key (extends `test_list_unknown_kind_lists_the_new_kinds_too`). Catches: a kind added
  without help (G4). Fails today for `codesets`.
- **AT-4** `decoy list generate-types --json`: on every entry `one_of` equals the engine catalog's
  `one_of` (so `lookup` has `["file", "codeset"]` and the rest `[]`); the human table shows
  `one of: file, codeset` on the `lookup` row; `decoy explain generation` prints
  `exactly one of: file, codeset`. Catches: the projection dropping the group (G1). Fails today.
- **AT-7** Neither `decoy list --help` nor the `decoy list providers` output contains
  "generation provider". Catches: the misleading wording coming back (G3). Fails today.

CLI, `tests/e2e/test_bundled_templates_e2e.py` (existing):

- **AT-5** For every generate template in the registry: the whole gate `decoy validate <config>`
  exits 0, `decoy run` exits 0, each table has 30 rows, every `reference` column links. Catches:
  a template the compile or preflight layer refuses (G6). Red-first proof, recorded once in the
  PR and not kept as a test: a copy of the healthcare template with `codeset: icd11` passes
  `validate config` and fails the whole gate.
- **AT-6** Catalog guard: every `type`, option and `faker_type` is in the live catalogs
  (existing), exactly one key of each `one_of` group is given, and every `codeset` is a key of
  `code_set_catalog()`. Catches: an engine rename reaching users (FM-4).
- **AT-8** Value shapes, each checked with `re.fullmatch` (recurring-defect class 1): healthcare
  `claims.diagnosis_code` values are non-null and match `[A-Z][0-9][0-9A-Z].*`; banking
  `transactions.merchant_category` values match `[0-9]{4}`; every money column's values match
  `-?[0-9]+\.[0-9]{2}` and fall within its `low` and `high`. Catches: a lookup or an output type
  silently not applied.
- **AT-9** `test_registry_has_the_expected_set` and the release-smoke expected set are unchanged.
  Catches: a template added or removed in this slice.

Surface pin: `tests/unit/test_cli_surface.py` passes after `docs/cli-reference.md` is
regenerated.

## 8. Mutations (the gate reruns each on the final head)

| Mutation | Must turn red |
|---|---|
| Engine: `code_set_catalog` returns a literal dict without `ndc` | AT-E1 |
| Engine: return the module-level registry view itself | AT-E3 |
| CLI: `_codesets_list` prints a fixed tuple of names | AT-1 |
| CLI: drop `one_of` from `type_entries()` | AT-4 |
| CLI: restore the literal "Kinds:" epilog without `codesets` | AT-3 |
| CLI: healthcare `codeset: icd10` becomes `codeset: icd11` | AT-5 and AT-6 |
| CLI: remove `output_type: decimal(2)` from banking `amount` | AT-8 |

## 9. Placement

Engine (engine `CODEMAP.md` "Where Things Go"):

| Item | Goes in | Map row and neighbor |
|---|---|---|
| `code_set_catalog()` | `src/decoy_engine/transforms/code_set.py` (existing, 559 lines) | "Transforms"; beside `SHIPPED_CODE_SETS` (`:559`) |
| Root export | `src/decoy_engine/__init__.py` (existing) | "Public API"; beside `strategy_catalog` |
| Tests | `tests/unit/transforms/test_code_set.py`, `tests/unit/test_public_api.py` (existing) | transform tests; public API pin |
| Docs | `docs/frozen-surfaces.md` Execution row, `docs/compatibility-contract.md`, `changelog.d/gen-catalog-codesets.md` (new fragment) | "Feature and contract docs"; fragment rules |

CLI (CLI `CODEMAP.md` "Where Things Go"):

| Item | Goes in | Map line and neighbor |
|---|---|---|
| `_codesets_list`, provider wording | `src/decoy/cli/cockpit.py` (existing; no new file in the frozen flat folder) | line 48 "Command module"; beside `_faker_types_list` |
| Derived kind help, `codeset` plural | `src/decoy/cli/reference.py` (existing) | line 48; beside `_LIST_READERS` |
| `one_of` in the projection, explain tail | `src/decoy/cli/gen/_topic.py` (existing, 140 lines) | line 56 "Generation CLI helpers"; `type_entries()` |
| Template edits | `src/decoy/templates/generate-{healthcare,banking,insurance,retail,hr}.yaml` (existing) | line 65 "Packaged templates" |
| Tests | `tests/e2e/test_reference_command.py`, `tests/e2e/test_bundled_templates_e2e.py` (existing) | test columns of lines 48 and 65 |
| Docs | `docs/cli-reference.md` (regenerated), `CHANGELOG.md`, `docs/ROADMAP.md` row 24s, `docs/qa/cli-v1-checklist.md` row GEN-14 | existing |

No new CLI module, so the flat `src/decoy/cli/` freeze and the package fan-out cap are untouched.

## 10. Frozen contracts touched

All additive.

- Engine: one new name in `decoy_engine.__all__` (`code_set_catalog`), on the Execution row of
  `docs/frozen-surfaces.md`, recorded as "Pre-GA additive" in `docs/compatibility-contract.md`.
  No reason code, schema, config key or exit code.
- CLI: one new `list` kind (`codesets`) and one new JSON key (`one_of`) on each
  `list generate-types` entry. `docs/cli-reference.md` changes (surface pin). No exit code
  changes; an unknown kind is still exit 1 (DOC-08). Consumers of the `list` JSON: none outside
  the CLI tests (the platform is parked and does not call `decoy list`).
- Templates: the edited templates write different columns and value formats. A copied template
  keeps its old body; `decoy show template` prints the new one. Pre-GA; named in `CHANGELOG.md`.

## 11. Class table

| # | Class | Closing structure | Sentry or property test | Mutation |
|---|---|---|---|---|
| 1 | Value-bearing output | Listings print registry names, option names and the engine's fixed descriptions only; templates hold generated values only; no log line added | AT-1, AT-2, existing `test_generate_templates_carry_no_real_looking_seeds` | print a corpus code in the codesets tip line |
| 2 | Cleanup missing on an exit path | N/A: no file, handle or temp folder is opened by the new code; `code_set_catalog()` reads a dict and no corpus file | N/A, the reason is in the closing-structure cell | N/A |
| 3 | State and concurrency | `code_set_catalog()` builds a new dict per call from the frozen registry; the CLI reader holds no module state | AT-E3 | return the module-level registry view itself |
| 4 | Route parity and silent fallback | N/A: no execution route is touched; templates run on whatever route the engine picks, and AT-5 checks the result, not the route | N/A, listings and template content only | N/A |
| 5 | Referential integrity | Every template FK is a `reference` column; the test checks child values are in the parent column | AT-5, existing `test_industry_template_key_columns_are_all_references` | point a `reference_column` at a non-key column |
| 6 | Untrusted producer | N/A: no user input is read by the new code; `list codesets` takes no argument, and the unknown-kind path is unchanged (DOC-08) | N/A, existing `test_list_unknown_kind_names_valid_kinds` still covers the one input | N/A |
| 7 | Check then use on a path (TOCTOU) | N/A: no path is checked or opened by the new code; the template test writes only to `tmp_path` | N/A, no path handling added | N/A |
| 8 | Weak tests and overclaimed evidence | Each AT names its mutation (section 8); AT-5 carries a red-first proof that `validate config` alone misses a bad code set; AT-8 uses `re.fullmatch` (recurring-defect class 1) | AT-1 to AT-9, AT-E1 to AT-E3 | test calls `validate config` with the `icd11` template and stays green |
| 9 | Behavior-preserving refactor drift | The kinds help moves from three literals to one derived string; the rendered help keeps every existing kind | AT-3, `tests/unit/test_cli_surface.py` | drop `faker-types` from the derived string |
| 10 | Frozen contract drift | Additive engine name on the frozen-surface map; additive CLI kind and JSON key; reference regenerated | AT-E2, `tests/sentry/release/test_frozen_surface_map.py`, `tests/unit/test_cli_surface.py` | rename `code_set_catalog` without the map row |

Other catalog classes: strict wire types, `one_of` is always a list (AT-4); no exception context,
no new error path; normalized guard scanners, AT-3 compares kind sets; no private-module reach,
the CLI reads only `decoy_engine.code_set_catalog` and the CLI internal-boundary allowlist
(`tests/sentry/baselines/engine-internal-allow.json`) gains no entry; mutations on the final
head, section 8; no raised caps, nothing moves.

## 11a. Enumerations

### Exit paths

- `decoy list codesets`: exit 0 in human, `--json` and `--quiet` modes, like `_faker_types_list`
  (`src/decoy/cli/cockpit.py:295`).
- `decoy list <unknown>`: exit 1 through `_reject_kind`, listing every kind
  (`src/decoy/cli/reference.py:327`).
- `decoy list codeset` (singular): exit 1 with the plural suggestion
  (`src/decoy/cli/reference.py:346`).
- `decoy validate <template>`: exit 0 expected for every generate template (AT-5); any other code
  is FM-1.

### Routes

- N/A: no execution route is added or changed. The template runs in AT-5 use whatever route the
  engine picks for a 30-row generate job.

### FK shapes

- Parent to child, one level (each template's second table references the first).
- Chain, two levels (each template's third table references the second), as in
  `src/decoy/templates/generate-healthcare.yaml:74`.

### Fields

- `list generate-types` JSON entry: `type`, `required`, `optional`, `required_when`, and the new
  `one_of` (always a list).
- `list codesets` JSON: `command`, `status`, `count`, `codesets[].name`, `codesets[].description`.

### Output surfaces

- stdout of `decoy list` (table or JSON) and `decoy explain generation` text.
- The bundled template bodies printed by `decoy show template` and written by `decoy init`.
- No log line, no file written by the listing code.

## 12. Slices, risk and OS lanes

| Slice | Repo | Production files | Size | Depends on | Risk |
|---|---|---|---|---|---|
| GC3-E | engine | `transforms/code_set.py`, `__init__.py`; tests; frozen-surface row, compatibility entry, changelog fragment | about 15 production lines, 40 test lines; one public name | none | R1 (additive public name, no behavior change) |
| GC3 | CLI | `cli/cockpit.py`, `cli/reference.py`, `cli/gen/_topic.py`, five template YAML files; tests; reference, changelog, roadmap, QA checklist | about 90 Python and 40 YAML production lines, 90 test lines; one list kind, one JSON key | an engine release with GC3-E pinned on CLI `main` | R1 (read-only listings, template content, a stronger test) |

Two slices because they are in two repos and the CLI needs the engine release. Docs fold into
each slice.

Gates: R1 gets Codex only, on the exact head (local operations profile). Tests: T0 per edit, T1
per commit and slice head, T2 at the gate; on the Mac or a test VM through `~/bin/vm-run`, never
the devbox. Full-suite trigger: none expected (no shared fixtures, schema, lock, frozen format or
moved tests). The CLI JSON gains a key; the gate judges it against the serialization trigger and,
if it applies, runs one full suite on the merge head against the saved main baseline.

OS lanes:

- Linux: required for both slices (CI on the gate runners, T1 on a VM).
- macOS: the T2 run for GC3 on the Mac mini (Mac first for test runs). GC3-E needs no Mac lane;
  it reads a Python dict.
- Windows: not required. Neither slice adds a path, file write or OS-specific call; the template
  test writes to `tmp_path` through the existing config-relative path code. Windows coverage
  comes with WIN-RUNNER (roadmap row 6), as for every CLI row.

Commit rules for builders: Conventional Commits subject at most 72 characters, no body unless it
says why, final line `cam`, no other trailers.

## 13. Dependencies and release

1. GC3-E builds now on engine `main`.
2. The next daily engine release carries it; the CLI repin follows the engine repin checklist.
3. GC3 builds on CLI `main` after that repin. Row 24s closes when GC3 merges.
4. If the engine release is held, GC3 may split into GC3a (items 1 and 3 to 9 without the
   `codeset` half of AT-6) and GC3b (item 2 and that half). This is the only planned split.
5. If FM-1 fires, the orchestrator opens a gate bug row; GC3 then lands with AT-5 on
   `validate config` plus `validate compile`, recorded as an approved change to AT-5.
6. Rows 24p and 24r change nothing here. When 24p merges, `decoy list generate-types` shows
   `provider` with no CLI change, because the projection reads the catalog.

## 14. Owner questions (taken on the recommended answer under standing approval unless the owner says otherwise)

- **OQ-1. Where does the "usable in generate" marker on `decoy list providers` go?**
  Recommended: in row 24p. Its compile check (`plan/checks/_generate_providers.py` in that plan)
  owns the rule; 24p E1 should export one predicate that both the check and the CLI read, and the
  CLI marker ships with 24p's CLI follow-up. Row 24s closes without it, because no provider is
  usable in generate today.
- **OQ-2. List the allowed values of every enumerated option (`op`, `generator`, `distribution` on
  `reference` and `windowed_date`, `null_propagation`, `other_mode`)?** Recommended: not in this
  row. They are checked in several engine modules, some at plan time, with no single registry to
  read; listing them now needs a hand list. Follow-up F-1.
- **OQ-3. Change the templates to use `lookup`, `distribution` and `output_type`?** Recommended:
  yes (G5). New users start from templates, and AT-5 and AT-6 keep them valid at every repin.

## 14a. Pre-mortem

Assume it is 2026-12-01 and row 24s is still open. Likely reasons, with the guard for each:

- The whole gate refused a generate-only config (FM-1) and the slice stalled. Guard: the builder
  stops at the first T1 and reports; section 13 item 5 gives the fallback.
- The engine release with GC3-E slipped. Guard: section 13 item 4 splits GC3.
- A review asked for option-value lists or the provider marker. Guard: both are non-goals with
  owner questions (OQ-1, OQ-2); findings outside the guarantee become follow-ups.

## 15. Follow-ups (recorded, not in this row)

- F-1. An engine registry of closed option values, so `list generate-types` can show each
  option's choices (OQ-2). V2-LOG.
- F-2. The generate-usable provider marker (OQ-1), in row 24p.
- F-3. `decoy list strategies` reads the private `SCALAR_HANDLERS` while the engine exports
  `strategy_catalog`; moving to it would shrink the internal-boundary allowlist. Not this row.

## 16. Review record

(filled by plan review rounds)
