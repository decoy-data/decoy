Status: plan

# DECOY-LANG commands: `decoy` reads, formats, converts and writes `.decoy`

Date: 2026-11-19. Revision 2. Roadmap row: DECOY-LANG. Parent plan:
[2026-11-19-decoy-language-completion.md](2026-11-19-decoy-language-completion.md), milestones 7
(command), 8 and 9.

Rules consulted: `dev-rules/README.md`, `00-universal.md`, `risk-and-exceptions.md`,
`development-loop.md`, `feature-dev.md`, `architecture.md`, `proportionality.md`,
`cross-cutting-concerns.md`, `api-and-compatibility.md`, `testing.md`, `documentation.md`,
`catalogs/recurring-defects.md`.

Risk: R2 overall; each slice has its own level in the slice table. The plan changes frozen 1.0
surfaces: the pipeline file a command accepts, command names, help text, the project layout,
finding locations, and what a run record stores. Nothing in it is built.

## Change log

Revision 2 answers Dennis plan review round 1. Each finding, and where it is answered:

| Finding | Answer | Section |
|---|---|---|
| H1 validation runs twice, codes differ | The loader lowers only (new `lower_text`); the gate validates once with engine codes; Guarantee 1 restated | Guarantee, The language side, Gate |
| H2 the guard watches the wrong call | `parse_config_mapping` becomes private; exact caller allowlist for `read_config_text`; import rule for `decoy.lang`; seeded spellings; two named mutations | Choke points and guards |
| H3 position types sit above the loader | New bottom-tier `decoy._source_positions`; `ci/locations.py` deleted, not wrapped (see Disagreements); `decoy.lang` to the bottom tier; allowlist key renamed; `GateFinding.position`; one walker for both kinds; parity test | Layers and positions |
| H4 review-mark semantics | `PipelineFile.unreviewed`; a rule per command; `ConfigFileError.problems`; one finding per problem; S2 acceptance rewritten | The review mark, S2 |
| M1 layout resolver | `PIPELINE_FILES`, `member_file()`, `member_destination()` in a new sibling module; `layout.pipeline_file_ambiguous`; `.decoy` in `_PATH_SUFFIXES` in S1; the real inventory plus a walk guard | Project layout |
| M2 frozen surfaces | Frozen-surface rows, language versioning rule, one `lang.*` code registry with a guard, `validation_codes`, json-shapes, CHANGELOG, templates, CODEMAP, help text | Frozen contracts touched |
| M3 run record | Owner-only sidecar plus two additive `cli-local-1` fields under `manifest_hash`; `report verify` rehashes it; the card leaves `evidence.py` first | What a run stores |
| M4 init mechanism | `convert_config(..., review=)`; stale "INIT-WIZARD owners agree" acceptance dropped; journey tests named; init files listed; sizes | S6 mechanism |
| M5 import cost | `decoy.lang` imported inside the `.decoy` branch only; subprocess import test | One loader |
| M6 value-free conversion | Conversion cells for `__cause__` and `__context__`; S3 twin cells keep the marker assertion | S1, S3 |
| L1 caller list | Built from the 14 `pipeline_argument` / `pipeline_option` sites; `plan`, `scan` and `explain pipeline` removed (they take no pipeline file) | Commands |
| L2 compiled-YAML view | `decoy convert pipeline.decoy` prints the compiled YAML; no `show pipeline`, no `validate` flag | Commands |
| L3 text, empty file, suffix case | `lang.not_utf8`, `lang.empty`, kind-neutral texts; `.decoy` matched case-insensitively | One loader |
| L4 semantic fingerprint | V2-LOG | Non-goals |
| L5 sizes | Per slice | Slices |

### Disagreements with round 1

1. H3 asks for `ci.locations` as a thin wrapper. After S2 the CI adapter reads
   `GateFinding.position` and builds no index, so a wrapper would have no caller. S2 deletes
   `src/decoy/ci/locations.py` and moves its tests. Pre-GA rule: hard delete.
2. H4 lists `convert` among the commands that proceed on a `?` mark. `decoy convert
   pipeline.decoy` writes YAML, and YAML has no review mark, so proceeding would let `convert`
   then `run` skip the review. Converting `.decoy` to YAML refuses on a mark. `fmt` proceeds
   and keeps the marks. Converting YAML to `.decoy` cannot meet a mark.

## What exists

The compiler, converter and formatter are in `src/decoy/lang/` (`compile_text`,
`convert_config`, `format_text`, each tested). `python -m decoy.lang` is the interim entry. No
`decoy` command reads a `.decoy` file. `compile_text` runs the engine's `parse_pipeline_config`
itself and rewrites every engine problem to the code `lang.config`
(`src/decoy/lang/_validate.py:46-50`), while the gate's schema layer reports engine codes
(`src/decoy/cli/gate/_layers.py:119-129`). Of the 11 bundled templates, 10 have a `.decoy`
twin in `tests/unit/lang/twins/`; `pci` has none.

## Guarantee and non-goals

1. Every command that takes a pipeline file accepts a `.decoy` file wherever it accepts a YAML
   file. When the two files give the same config:
   - the exit code is the same;
   - every engine, schema, compile-layer and preflight finding has the same code, severity,
     message and dotted `location` as for the YAML file;
   - the `--json` result document is the same apart from the file name, its hash and
     `position` keys (rule 2).

   Problems found while reading the `.decoy` text (parse and lowering, before any engine
   validation) carry `lang.*` codes. They have no YAML equivalent.
2. Where `decoy ci check` gives a YAML finding a line and column, it gives the `.decoy` finding
   the line and column of the `.decoy` construct that produced it. A `lang.*` problem carries
   its line and column on every surface. Direct commands (`validate`, `run`) keep printing the
   dotted `location` for engine findings on both kinds, so rule 1 holds.
3. A `.decoy` file with a rule still marked `?` is refused by every command that reads data,
   before any source is read, with exit 1 and one finding per mark. `decoy validate` reports the
   marks beside every other config-layer problem.
4. No message quotes a value from the file. A converted `LangError` has no `__cause__` and no
   `__context__`.
5. YAML keeps working unchanged: same codes, texts, exit codes, locations and SARIF regions for
   every YAML pipeline, pinned by the existing snapshots.

Non-goals: a `.decoy` form of the CI manifest, `decoy.yaml` or a policy file; changing what the
engine receives; the `policy` block (milestone 12); stdin input (no pipeline command reads
stdin today).

V2-LOG: a semantic fingerprint (a hash of the compiled config, so reformatting a `.decoy` file
or converting YAML does not change `pipeline_fingerprint`); kind-neutral names for
`PipelineEntry.yaml` and `parse_pipeline_yaml`; line numbers in direct output for every
finding, done for both kinds at once.

## Established solutions

One loader that dispatches on the file's kind and returns the same value for every kind is how
Terraform reads `.tf` and `.tf.json`, and how dbt reads SQL and Python models. This repository
already has that choke point for YAML, `decoy._config_file`, guarded by
`tests/sentry/io_policy/test_config_load_choke_point.py`. Reporting a generated program's error
on the source line through a map built during lowering is how Elm and Rust do it, and how
`decoy.lang._validate.locate` works today. SARIF 2.1.0 section 3.30 is the region model.

## Design notes

- New structure: one bottom-tier position module, one sibling layout module, one command
  sub-package, one code registry. Principle: one place per fact. The change pain each removes:
  the YAML mark index sits in the `ci` tier, above the loader that now needs it (H3);
  `_layout.py` is at its 800-line cap (M1); the flat `cli/` folder is frozen at 30 modules;
  `lang.*` codes are literals spread over 15 modules (M2).
- Kind-neutral position: the loader returns a `locate` function, so no caller learns the kind.
- One walker for both kinds: the YAML index and the `.decoy` index share the path parser and
  the walker; only the node adapter differs. Parity holds by construction and a test pins it.
- No flag arguments: `Template` gains a `decoy_body` field instead of `get_template(kind=)`.

## Design

### One loader

`decoy._config_file` is the only place that decides how a pipeline file is read:

```python
@dataclass(frozen=True)
class ConfigProblem:
    code: str                   # yaml.* or lang.*
    message: str                # no value from the file
    position: Position | None   # from decoy._source_positions

class ConfigFileError(Exception):
    problems: tuple[ConfigProblem, ...]   # at least one, in source order, marks last
    code: str        # problems[0].code, so every existing caller keeps working
    message: str     # problems[0] rendered, plus "(N more; `decoy validate FILE` lists them)"

@dataclass(frozen=True)
class PipelineFile:
    config: dict[str, Any]
    locate: Callable[[str | None], Position | None]   # dotted config path -> place in the file
    unreviewed: tuple[ConfigProblem, ...]              # `?` marks (lang.unreviewed); () for YAML

def load_pipeline(path: Path, *, text: str | None = None) -> PipelineFile
def read_decoy_text(path: Path) -> str
def load_config_mapping(path: Path) -> dict[str, Any]
```

- Kind rule (L3): a path whose name ends in `.decoy`, compared case-insensitively, is a
  `.decoy` file, as `.yaml` and `.yml` are compared today in `looks_like_path` and the
  completer. Every other path is YAML. A member file name is exact (`pipeline.decoy`), as
  `pipeline.yaml` is today.
- YAML: today's steps and the four `yaml.*` codes, unchanged. `locate` is
  `YamlPositionIndex.from_text(text).locate`, built on first call.
- `.decoy`: `read_decoy_text` decodes the bytes once (strict UTF-8, BOM dropped). Non-UTF-8 is
  `lang.not_utf8`, "Pipeline file is not UTF-8 text."; text that is empty or only whitespace is
  `lang.empty`, "Pipeline file is empty." Then `decoy.lang.lower_text(text)`. A `LangError`
  becomes one `ConfigFileError` with one `ConfigProblem` per diagnostic, raised after the
  handler closes. `locate` is `DecoyPositionIndex(config, source_map).locate`.
- `decoy.lang` is imported inside the `.decoy` branch only (M5). Importing `decoy._config_file`
  loads neither `decoy_engine` nor `lark`; a subprocess test pins it.
- `load_config_mapping(path)` returns `load_pipeline(path).config`, and raises a
  `ConfigFileError` of the marks when `unreviewed` is not empty. So every caller that needs
  only the mapping refuses a marked file with no new code at the call site.
- `config_refusal` keeps exactly its two keys, `message` and `code` (`preflight.py:658`
  unpacks two values), and puts "line L, column C: " before a message that has a position.
- `parse_config_mapping` becomes the private `_parse_yaml_mapping` and leaves `__all__`.

### The language side (H1)

`decoy.lang` gains:

```python
@dataclass(frozen=True)
class Lowered:
    config: dict[str, Any]
    source_map: SourceMap
    unreviewed: tuple[Diagnostic, ...]   # lang.unreviewed, one per marked rule

def lower_text(text: str) -> Lowered    # parse and lower; no engine validation
```

- A parse failure raises the syntax problems. A lowering failure raises the lowering problems
  followed by the marks (the program parsed, so the marks are known). Success returns the marks
  as data.
- `compile_text` stays the package's one-call entry for library use (decision E7 keeps the
  package movable): `lower_text`, then `validate`, then the marks raised. It keeps
  `lang.config`. No CLI code calls it (import rule below).
- The gate runs the engine's `parse_pipeline_config` once, in its schema layer, for both kinds,
  so engine findings keep engine codes. `locate` maps their dotted location to the `.decoy`
  construct with the nearest-construct rule of `_validate.locate`.

### Layers and positions (H3)

- New module `src/decoy/_source_positions.py`, bottom tier:
  - `Position(line, column, end_line, end_column)`, every field optional; all `None` means
    "the file, no region" (today's file-level `SourceLocation`).
  - `segments(logical_path)`: the one path parser. It accepts the spellings the YAML index
    accepts today: numeric (`tables.0.columns.2.provider`), bracket (`tables[0]...`), semantic
    (`tables.customers.columns.email.provider`) and plain mapping keys. It refuses empty
    segments, `*` and `<pseudo>` segments.
  - One walker over a small node interface, with two adapters: PyYAML nodes
    (`YamlPositionIndex`, the code moved from `ci/locations.py`) and a config value plus a
    source map (`DecoyPositionIndex`). Both record a duplicate key or name as ambiguous, and
    both give a file-level `Position` for a proven parent whose leaf is absent.
  - It takes the source map as a mapping of path tuples to objects with `line` and `column`,
    so it does not import `decoy.lang`.
- `.importlinter`: the bottom tier becomes
  `_private_file | _version | _yaml_errors | _source_positions | lang`, and `lang` leaves the
  `ui | ... | templates | lang` tier. The layer snapshot in
  `tests/sentry/layout/test_import_layers.py` changes with it. The builder checks
  `tests/sentry/layout/test_package_fanout.py` for `src/decoy` (limit 25) before adding the
  module.
- `src/decoy/lang/__main__.py` is deleted: it imports `_config_file`, which is now above it.
  `tests/unit/lang/test_package_boundary.py` then has `ALLOWED = set()`.
- The baseline key `ci/locations.py::YamlSourceIndex.from_text::1` in
  `tests/sentry/baselines/config-load-allow.json` is renamed to
  `_source_positions.py::YamlPositionIndex.from_text::1`, same kind and reason. It is a move,
  not growth: the entry count stays 11.
- `GateFinding` gains a last field `position: Position | None = None`. The gate fills it from
  `PipelineFile.locate(logical_path or location)` for config, compile and preflight findings,
  and from the `ConfigProblem` for loader problems.
- `ci/adapters.py` stops reading the file and building an index. It calls the gate with the
  path and builds `SourceLocation(uri=rel, ...)` from `item.position`. Its `yaml.not_utf8`
  special case goes: the gate reports that code as a config finding, and the result (rule id
  `validate.yaml.not_utf8`, exit 1, no region) is the same, pinned by the SARIF snapshot.

### Gate (`cli/gate/_layers.py`)

- `parse_pipeline_yaml(path, source_text)` calls `load_pipeline` and returns
  `(PipelineFile | None, findings)`: one config-layer error finding per `ConfigProblem`.
- `run_config_gate` and `run_gate` stop when the pipeline is `None` (today: on any finding).
  With a pipeline, they run the config base as today, then append one config-layer error
  finding per mark after the other config-layer findings. The config layer has failed, so the
  gate stops before compile and preflight, as it does for any config error.
- `run/_prepare.py:_load_raw_config` refuses on any finding, marks included. That is the step
  where `run` refuses a YAML syntax error today, before the layout check and before any source
  is opened.
- `cli/gen/_scaffold.py:144` calls `load_pipeline(staged_path, text=config_text)` instead of
  `parse_config_mapping` (CLI-written YAML, suffix `.yaml`).

### The review mark (H4)

| Command | A file whose only problems are `?` marks |
|---|---|
| `validate`, `validate config`, `ci check` | Report every mark beside the other config-layer findings; exit 1 |
| `run`, `project run --all` (each member) | Refuse at the parse step, one finding per mark; exit 1; no source read |
| `validate compile`, `validate preflight`, `subset`, `tokenize`, `detokenize`, `unmask`, `report fidelity/integrity/vault --config`, Python `mask(config=path)` | Refuse through `load_config_mapping`; exit 1; the message names the first mark and the count |
| `convert pipeline.decoy` (to YAML) | Refuse; exit 1 (see Disagreements) |
| `fmt` | Proceed; the marks are kept |

A file with other compile problems as well raises them all, marks last, on every command.

### Project layout (M1)

- New module `src/decoy/cli/io/_member_file.py`:
  - `PIPELINE_FILES = ("pipeline.yaml", "pipeline.decoy")`.
  - `member_file(root, name) -> Path | None`: the one present file; `None` when neither is a
    regular file; `LayoutError` `layout.pipeline_file_ambiguous` when both are present.
  - `member_destination(root, name, kind) -> Path`: where `decoy init` writes; refuses with the
    same code when the other file is already present.
  - `member_has_link` and `_member` move here from `_pipelines.py` and check both names.
- `_layout_errors.py` registers `PIPELINE_FILE_AMBIGUOUS` (the message names the folder, never
  file content) among the gate descriptors, so `GATE_CODES` and `validation_codes` carry it.
- `_layout.py` stays at or under 800 lines: `PIPELINE_YAML` and `member_yaml` leave it, and
  lines 331 and 350 test `parts[2] in PIPELINE_FILES`. The cap is not raised.
- Inventory today:

| Site | Change |
|---|---|
| `cli/io/_layout.py:55-60` (`PIPELINE_YAML`, `member_yaml`) | Removed; replaced by `_member_file.py` |
| `cli/io/_layout.py:331` (`_taken`), `:350` (`pipeline_name_for`) | Either file name is a member |
| `cli/io/_pipelines.py:56` (`_PATH_SUFFIXES`), `:116` | Adds `.decoy` (S1) |
| `cli/io/_pipelines.py:182-205` (`member_has_link`, `_member`), `:310` | Use `member_file`; the error path names the file found |
| `cli/io/__init__.py:48, 216` | Exports `member_file`, `member_destination`, `PIPELINE_FILES` instead of `member_yaml` |
| `cli/project/_scaffold.py:36, 109-112` | Destination from `member_destination` |
| `cli/completers.py:130` | Offers `.decoy` files |
| `cli/project/_show.py:48` | Key `"yaml"` unchanged (frozen json shape); its value may name a `.decoy` file |
| `cli/project/_run_all.py:164` | Unchanged; `entry.yaml` is the member file |
| `cli/gen/_scaffold.py:147`, `cli/demo.py:153` | Unchanged; CLI-written YAML |
| `docs/project-layout.md` | Both file names; the both-present refusal |

- Guard (a walk, so the grep above is not trusted alone):
  `tests/sentry/io_policy/test_member_file_names.py` walks the syntax tree of `src/decoy/cli`
  for string constants equal to `pipeline.yaml` or `pipeline.decoy` outside docstrings. Allowed:
  `cli/io/_member_file.py`, and the two CLI-written sites `cli/gen/_scaffold.py` and
  `cli/demo.py`, by (file, function). Mutation M-S4: put `root / "pipelines" / name /
  "pipeline.yaml"` back in `cli/io/_pipelines.py`; the guard fails.

### What a run stores (M3)

For a `.decoy` pipeline run with `--evidence-out`:

- `pipeline_path` and `pipeline_fingerprint` name and hash the `.decoy` file, as written.
- The compiled YAML (`emit_yaml` of the exact dict the run hands the engine) is written to an
  owner-only sidecar beside the manifest, `<manifest stem>.compiled.yaml`, through
  `decoy._private_file` and `_atomic`. It holds the config, the same class of content as the
  user's own pipeline file, so it is owner-only and never inside the manifest.
- The manifest gains two additive `cli-local-1` fields, `compiled_pipeline_path` and
  `compiled_pipeline_fingerprint`, both optional in `_FIELDS` and both covered by
  `manifest_hash`. YAML runs and old manifests have neither and verify unchanged.
- `report verify` and `decoy ci check` rehash the sidecar through `_stored_files` as a
  pipeline-kind entry: a missing sidecar is `pipeline_missing`, a changed one
  `pipeline_fingerprint_changed`, each naming the sidecar path. No new issue code.
- The `no_raw_values` test gains a `.decoy` run whose config holds marker values: no marker in
  the manifest; the sidecar is mode 0600.
- Write order: the sidecar first, then the manifest, so a manifest never names a sidecar that
  was not written. If the manifest write fails, the sidecar is removed; a failed removal is
  named in the same error line. The exit stays `EXIT_RUNTIME`, as today
  (`src/decoy/cli/run/_evidence.py:52-56`).
- `evidence.py` is at 792 lines. S7 first moves `_render_manifest_card` (lines 700-781) to
  `src/decoy/ui/evidence_card.py`, a move with no behaviour change, then adds about 10 lines.
  The writer side goes in `cli/run/_evidence.py` (61 lines).

### Commands (L1, L2)

Caller list, from every `pipeline_argument` / `pipeline_option` site plus the routes that take
a pipeline path another way:

| Command | Site | Change |
|---|---|---|
| `run` | `cli/run/__init__.py:111` | Accepts `.decoy` |
| `validate`, `validate config` | `cli/validate.py:255`, `:115` | Accepts `.decoy` |
| `validate compile` | `cli/compile_explain.py:88` | Accepts `.decoy` |
| `validate preflight` | `cli/preflight.py:589` | Accepts `.decoy` |
| `subset` | `cli/subset.py:81` | Accepts `.decoy` |
| `tokenize`, `detokenize` | `cli/tokenize.py:125`, `:464` | Accepts `.decoy` |
| `unmask` | `cli/unmask.py:70` | Accepts `.decoy` |
| `report fidelity`, `integrity`, `vault` with `--config` | `cli/report.py:1629`, `:1911`, `:2162` | Accepts `.decoy` |
| `ci check` | the manifest's pipeline paths, `ci/adapters.py` | Accepts `.decoy` |
| `project run --all` | members, `cli/project/_run_all.py` | Runs `pipeline.decoy` members |
| Python API `mask(config=path)` | `api.py:105` | Accepts `.decoy` |
| `decoy fmt FILE` (new) | `cli/lang/_fmt.py` | Prints the canonical layout; `--write` replaces the file through `_atomic`; `--check` exits 1 when the file would change; a non-`.decoy` path is a usage error (exit 2) |
| `decoy convert FILE` (new) | `cli/lang/_convert.py` | YAML in: prints the `.decoy` program (`convert_config`). `.decoy` in: prints the compiled YAML after the engine's schema check, refusing any problem or mark. `-o PATH` writes through `_atomic`. A refusal is exit 1 with its code (`lang.not_convertible` for a `ConvertError`) |
| `decoy init` | `cli/init.py` | Writes `pipeline.decoy`, inferred rules marked `?`; `--yaml` writes today's output (S6) |
| `decoy show template NAME` | `cli/templates.py` | Prints the `.decoy` body; `--yaml` prints the YAML body (S6) |

`plan`, `scan` and `explain pipeline` take no pipeline file and are out of scope. The compiled
YAML view is `decoy convert pipeline.decoy`: one command converts both ways, chosen by the
input's kind, so no `show pipeline` kind and no `validate` flag is added.

`convert -o` into a pipeline folder that already holds the other file writes it and prints a
warning that the folder is refused until one file is removed. Writing is safe because every
reader refuses that folder.

`--json` for the new commands: `fmt` gives `{command, status, file, changed}`; `convert` gives
`{command, status, from, to, output}` and needs `-o` (without it, `--json` is a usage error,
exit 2), so no program text goes into a JSON string.

## Frozen contracts touched (M2)

Rows added to `docs/release/frozen-surfaces.md`:

| Surface | Owning code | Pinning test |
|---|---|---|
| The Decoy language: grammar, `lang.*` codes, `SUPPORTED_VERSIONS` | `src/decoy/lang/` | `tests/unit/lang/test_language_freeze.py` (grammar text, code set and versions against `tests/fixtures/release_freeze/lang-surface.json`), the twins, the round-trip tests |
| Pipeline file kinds and member file names | `src/decoy/_config_file.py`, `src/decoy/cli/io/_member_file.py` | loader and layout tests |
| Finding `position` in `--json`, SARIF regions for `.decoy` | `src/decoy/cli/gate/`, `src/decoy/ci/adapters.py` | S2 snapshots |
| Compiled-pipeline sidecar and its two manifest fields | `src/decoy/cli/run/_evidence.py`, `src/decoy/cli/evidence.py` | `tests/unit/test_evidence.py` |

The bundled template row gains the `.decoy` bodies; the command row gains `fmt` and `convert`.

Language versioning rule, written into the frozen-surfaces page:

- A program that compiles under `version 1` compiles to the same config in every 1.x release.
- A new keyword or construct may be added only where today's grammar gives a syntax error.
- A `lang.*` code is never renamed, removed or reused for another problem in 1.x. Message text
  may change.
- A change that breaks a valid program adds a new value to `SUPPORTED_VERSIONS` and keeps
  accepting `1`.

One code registry: `src/decoy/lang/_codes.py` holds `CODES`, every `lang.*` code with a
one-line meaning, including the new `lang.not_utf8`, `lang.empty` and `lang.not_convertible`.
`_codes.py` imports nothing. `tests/unit/lang/test_codes.py` walks `src/decoy/lang/`,
`src/decoy/_config_file.py` and `src/decoy/cli/lang/` for `lang.*` string literals: each is in
`CODES`, and each entry of `CODES` is used. Seeded: a literal not in the registry is reported.

`ci/rule_codes.py:validation_codes()` adds `CODES`, imported inside the function as the layout
codes are, so a `.decoy` finding never maps to the unknown rule id. It takes the whole
registry, so the two sets cannot drift.

Changed with the commands: the json-shapes snapshot
(`tests/fixtures/release_freeze/json-shapes.json`, `tests/e2e/release_freeze/write_shapes.py`)
for `fmt` and `convert`; `CHANGELOG.md`; `docs/cli-reference.md` regenerated; the help text at
all 14 `pipeline_argument` / `pipeline_option` sites says "pipeline file (.yaml or .decoy)"
(S1); the CODEMAP templates row (`<name>.yaml` and `<name>.decoy`), the lang row (no
`python -m decoy.lang`), and a row for `src/decoy/cli/lang/`.

## Choke points and guards (H2)

Rule 1: every read of a user's pipeline file goes through `decoy._config_file`.

By construction:
- `parse_config_mapping` is private (`_parse_yaml_mapping`), so the bypass
  `parse_config_mapping(read_config_text(p))` (today at `cli/gate/_layers.py:102`, with the
  read at `ci/adapters.py:86`) cannot be written outside the module.
- `read_config_text` has an exact caller allowlist by (file, function):
  `ci/manifest.py::load_manifest` only (the CI manifest, a different kind). Calls inside
  `_config_file.py` are not counted.
- Only `decoy._config_file` and `decoy.cli.lang` import `decoy.lang`. `decoy.cli.lang` may
  import only `format_text`, `convert_config`, `emit_yaml`, `ConvertError`, `LangError` and
  `render`, never `lower_text` or `compile_text`. Any config it needs comes from
  `load_pipeline`.

Guard: `tests/sentry/io_policy/test_config_load_choke_point.py` gains three tests over
`src/decoy`, with the AST walk in `_yaml_load_sites.py`:
1. the `read_config_text` call sites equal the allowlist;
2. no import of `_parse_yaml_mapping`, or of any `_` name of `decoy._config_file`, outside it;
3. the `decoy.lang` import rule, with the name allowlist for `decoy.cli.lang`.

Seeded spellings, each a self-test: `import decoy.lang as L` then `L.lower_text(t)`;
`from decoy.lang import compile_text`; the attribute call `decoy.lang.compile_text(t)` after
`import decoy`; `from decoy.lang._lower import lower`; `from decoy import lang`;
`importlib.import_module("decoy.lang")`; and the bypass
`from decoy._config_file import _parse_yaml_mapping, read_config_text` then
`_parse_yaml_mapping(read_config_text(p))`.

Mutations that must turn the guard red:
- M-H2a: in `cli/validate.py`, add `from decoy.lang import compile_text` and compile the
  path's text there. Test 3 fails.
- M-H2b: in `ci/adapters.py`, restore `text = read_config_text(path)` before the gate call.
  Test 1 fails.

Rule 2: a command that takes a pipeline file accepts both kinds and gives the same result.
Guard: the route-cell table in `tests/sentry/defects/test_config_error_routes.py` already walks
every command with a config parameter. Each cell runs twice: with the YAML marker config and
with its `.decoy` twin, made in the test by `convert_config` so no fixture can drift. Both runs
keep the existing assertion that no marker reaches stdout, stderr or `--json`, and the two runs
must give the same exit code and the same finding codes. A command added later gets both runs
or fails the walk. Mutation M-R2: make `cli/unmask.py` call `yaml.safe_load` on the path's text
itself; its `.decoy` run fails, and the existing YAML reader sentry fails too.

Rule 3: the review mark is refused by construction in `load_config_mapping` and in the gate's
`parse_pipeline_yaml`. Mutation M-R3: drop the marks check from `load_config_mapping`; the S2
cell "`tokenize` refuses a marked file" fails.

Rule 4: the member file names live in `_member_file.py` (guard and mutation M-S4 under Project
layout).

## Defect classes

From `catalogs/recurring-defects.md` and the plan contract's class list.

| # | Class | Closing structure | Proof | Mutation |
|---|---|---|---|---|
| 1 | Value-bearing output | `ConfigProblem` text comes only from value-free lang diagnostics and the four fixed YAML texts; `ConfigFileError` is raised after the handler closes | S3 route cells assert no marker on any surface for both kinds; S1 conversion cells check `__cause__`, `__context__`, `str` and `args` | Raise the `ConfigFileError` inside the `except LangError` block: the `__context__` cell fails |
| 2 | Cleanup on an exit path | Sidecar first, manifest second, sidecar removed when the manifest write fails; `fmt --write` and `convert -o` replace through `_atomic` | S7 exit-path cell: a failing manifest write leaves no sidecar and exits `EXIT_RUNTIME`; S5 cell: a failing `--write` leaves the original bytes | Drop the sidecar removal: the S7 cell fails |
| 3 | State and concurrency | N/A: the loader keeps no state between calls. `locate` builds its index once per `PipelineFile` and no index is shared across files or calls | | |
| 4 | Route parity and silent fallback | One loader for every route; no command falls back from `.decoy` to YAML; the kind rule is one function | S3 both-kinds route cells over every config-taking command (Click-tree walk) | M-R2 |
| 5 | Referential integrity | N/A: no row handling changes. Links (`<-`) lower to the same `foreign_keys` config, which the twins test already proves equal to the YAML templates | | |
| 6 | Untrusted producer | The `.decoy` text is user input: the compiler turns a `RecursionError` into `lang.nesting`; the position walker keeps its node cap (`_MAX_NODES`); `ci check` keeps its regular-file check before the gate | Hostile corpus in S1 loader tests: 10 000 nested parentheses, a 5 MB file, NUL bytes, a lone surrogate escape, CRLF, BOM, non-UTF-8 | Remove the `RecursionError` handler in `lower_text`: the nesting cell fails |
| 7 | Check then use on a path | The file is read once; `config`, `unreviewed` and `locate` all come from that one text | `read_config_text` caller allowlist and the existing read-and-decode sentry | M-H2b (the adapter reads the file a second time) |
| 8 | Weak tests and overclaimed evidence | Every new guard has seeded self-tests; the parity test asserts it saw all 11 pairs and at least 20 paths in each | The builder reports the seeded counts and reruns the YAML snapshots on the merge head | Empty the twin list: the parity test's own count check fails |
| 9 | Refactor drift | Two moves: `ci/locations.py` to `_source_positions.py`, the manifest card to `ui/evidence_card.py`. The old tests move unchanged first, then the code | Moved `test_ci_locations.py` cases and the SARIF snapshot; `report show` snapshot; the config-load sentry scans the renamed key | Drop the ambiguity mark in the moved walker: the duplicate-key case fails |
| 10 | Frozen contract drift | Every change is additive except the listed command and layout additions (see Frozen contracts touched) | json-shapes, SARIF, CLI surface, evidence and language freeze snapshots | Rename `lang.unreviewed`: the language freeze test fails |

## Enumerations

### Exit paths

Code that owns files on the way out:

- `decoy run --evidence-out` writes the manifest at `src/decoy/cli/run/_evidence.py:52`; S7
  adds the sidecar before it (class 2 row).
- `decoy fmt --write` and `decoy convert -o`: one `_atomic` replace each; a failure leaves the
  old file and exits 3, as other `write_local_target` failures do.
- `decoy init` writes the member file through `cli/project/_scaffold.py:170`; S6 changes only
  the name and the body.
- The gate and the loader own no files: refusal paths return findings
  (`src/decoy/cli/gate/_layers.py:480-494`).

### Routes

- Direct gate: `validate`, `validate config` (`src/decoy/cli/validate.py:156`, `:301`).
- Run: plain and `--chunked` (`GateRoute` at `src/decoy/cli/gate/_layers.py:33`), `--rows`
  preview, `--duckdb-source`, `project run --all` children (`src/decoy/cli/project/_run_all.py:164`).
- CI: `ci check` config mode and full mode (`src/decoy/ci/adapters.py:105`).
- Mapping-only readers: the 11 `load_config_mapping` call sites today (`src/decoy/api.py:105`, `cli/report.py` three, `cli/tokenize.py` two, `cli/compile_explain.py`, `cli/unmask.py`, `cli/subset.py`, `cli/preflight.py`, `cli/io/_placement.py:394`).
- All of them reach the file through `load_pipeline`; the S3 cells cover each command.

### FK shapes

N/A: the plan does not change foreign-key handling. A `.decoy` link lowers to the same
`foreign_keys` config as YAML, proven by the twins.

### Fields

- `PipelineFile`: `config`, `locate`, `unreviewed`.
- `ConfigProblem`: `code`, `message`, `position`. `ConfigFileError`: `problems`, `code`,
  `message`.
- `Lowered`: `config`, `source_map`, `unreviewed`.
- `Position`: `line`, `column`, `end_line`, `end_column`.
- `GateFinding` (`src/decoy/cli/gate/_layers.py:45`): adds `position`; `GateResult` unchanged.
- Evidence manifest: adds `compiled_pipeline_path`, `compiled_pipeline_fingerprint`
  (`src/decoy/cli/evidence.py:107-125`).
- `Template` (`src/decoy/templates/__init__.py:15`): adds `decoy_body`.

### Output surfaces

- stdout human text and `--json` success documents (new `position` key; `fmt` and `convert`
  shapes).
- stderr error lines and the `--json` error object (`config_refusal`, two keys, unchanged
  schema).
- SARIF and the CI JSON from `ci check` (regions on `.decoy` lines).
- Files: the evidence manifest and sidecar, `fmt --write`, `convert -o`, `init` output.
- Help text at the 14 parameter sites (`src/decoy/cli/io/_pipelines.py:148`, `:161`), the
  completer, and Typer's own parse errors for a missing path (unchanged text).
- Logs: the CI debug sink on a crashed check (unchanged; the loader adds no log line).

## Reuse inventory

- `decoy._config_file` and its sentry `test_config_load_choke_point.py`, with the shrink-only
  baseline `config-load-allow.json`.
- The YAML mark walker in `ci/locations.py`, moved, not rewritten.
- `decoy.lang`: `SourceMap`, `_validate.locate` (nearest construct, union-member rule), the
  printer's `Notes`, `convert_config`'s round-trip check, `format_text`.
- The gate's schema layer and `_schema_findings`, the one construction of engine findings.
- `layout.*` descriptors in `_layout_errors.py` and `GATE_CODES`.
- `_atomic.write_local_target`, `_private_file`, evidence `_stored_files` and `manifest_hash`.
- The route-cell table and its Click-tree walk in `test_config_error_routes.py`.
- The json-shapes snapshot, the CLI reference generator and `test_cli_surface.py`.

New machinery and its reason: `_source_positions.py` (the walker must sit below the loader),
`_member_file.py` (`_layout.py` is at its cap), `_codes.py` (codes are scattered literals),
`cli/lang/` (the flat `cli/` is frozen).

## Pre-mortem

- An engine location names a union member (`sources.x.file.path`) that the `.decoy` index
  does not hold. Closed by reusing the union rule of `_validate.locate`; the parity test runs
  every engine problem path the twins produce.
- A twin compiles to a config that the engine accepts but the YAML form does not quite match
  (key order, a default written out), so the two runs differ. Closed by the S3 cells comparing
  exit codes and codes, and the twins test comparing configs.
- The first `.decoy` load is slow because Lark builds the grammar. S1 measures `decoy validate`
  on a twin against its YAML template and reports the difference; more than 300 ms stops the
  slice for a cached grammar.
- Changing the help text at 14 sites breaks `docs/cli-reference.md`; S1 regenerates it.
- The init default change breaks the QA journey document; S6 updates
  `docs/qa/cli-v1-journey.md` with the journey tests.
- `src/decoy/lang/` is still being changed by another builder on
  `claude/sweet-einstein-u3104u`. S1 starts from main after that branch merges, never on top of
  it.

## Placement

| New file | Directory | CODEMAP "Where things go" line | Sits beside |
|---|---|---|---|
| `_source_positions.py` | `src/decoy/` | "Private shared filesystem or process primitives used by more than one package" (`src/decoy/_<noun>.py`); used by `_config_file`, the gate and `ci` | `_yaml_errors.py` |
| `_codes.py` | `src/decoy/lang/` | "Decoy language compiler" (`src/decoy/lang/_<stage>.py`) | `_errors.py` |
| `_member_file.py` | `src/decoy/cli/io/` | "Project layout services ... the `layout.*` descriptors" | `_layout.py` |
| `__init__.py`, `_fmt.py`, `_convert.py`, `_scaffold.py` | `src/decoy/cli/lang/` | "Command module ... new commands go in a named sub-package", and the lang row ("a `decoy` command for it goes in a sub-package below `src/decoy/cli/`") | `src/decoy/cli/setup/` |
| `evidence_card.py` | `src/decoy/ui/` | "Terminal output" (`src/decoy/ui/<concern>.py`) | `card.py` |
| `<name>.decoy` (11) | `src/decoy/templates/` | "Packaged templates"; the row changes to name both suffixes | `<name>.yaml` |
| `test_source_positions.py` | `tests/unit/` | moved from `tests/unit/test_ci_locations.py` | |
| `test_member_file_names.py` | `tests/sentry/io_policy/` | beside the other io-policy sentries | `test_config_load_choke_point.py` |

Deleted: `src/decoy/lang/__main__.py`, `tests/unit/lang/test_module_entry.py`,
`src/decoy/ci/locations.py`, `tests/unit/lang/twins/` (moved to `src/decoy/templates/`).

## Slices

S1 and S5 are a stacked pair (one full suite on the stack top, then merge in order): S1 deletes
`python -m decoy.lang`, and S5 adds the `decoy fmt` and `decoy convert` that the guide pages
switch to. Order: S1+S5, S2, S3, S4, S6, S7. S6 waits for S1 to S3 (owner O4).

| # | Slice | Risk | Frozen surface | Size |
|---|---|---|---|---|
| S1 | Loader (`PipelineFile`, `load_pipeline`, `ConfigProblem`, `read_decoy_text`), `lower_text`, `_codes.py`, layer move, `__main__` deleted, `_PATH_SUFFIXES`, help text, guards for rules 1 and 3, language freeze test | R2 | loader shape, help text, the language | ~150 src lines in `_config_file.py`, ~45 in `lang/`, ~70 in `_codes.py`, -86 for `__main__`; ~400 test lines; 6 public names added, 1 made private |
| S5 | `decoy fmt`, `decoy convert`; guide pages off `python -m decoy.lang` | R2 | command names, json shapes | ~250 src lines in `cli/lang/`; ~250 test lines; 2 commands |
| S2 | `_source_positions.py`, `GateFinding.position`, gate marks, adapter change, `ci/locations.py` deleted, `validation_codes` | R2 | finding positions, SARIF | ~200 src lines moved or new, ~-60 in `ci/`, ~40 in the gate; ~250 test lines |
| S3 | Both-kinds route cells | R1 | none | ~200 test lines |
| S4 | `_member_file.py`, `layout.pipeline_file_ambiguous`, layout sites, completion, `run --all`, name guard | R2 | project layout | ~90 src lines new, ~20 changed; ~180 test lines |
| S6 | `decoy init` and templates write `.decoy` | R2 | init output, template text | ~40 in `lang/_convert.py`, ~60 in `cli/lang/_scaffold.py`, ~25 in `init.py`, ~20 in templates; 11 `.decoy` bodies; ~200 test lines changed |
| S7 | Run record sidecar and fields | R2 | `cli-local-1` | card move (~80 lines, no change), ~40 in `run/_evidence.py`, ~10 in `evidence.py`; ~120 test lines |

### Acceptance tests

S1:
- Loader unit tests for both kinds and every code: the four `yaml.*` codes unchanged;
  `lang.not_utf8`; `lang.empty` (empty and whitespace-only); a syntax error; a lowering error;
  a lowering error plus two marks (marks last); a clean file with marks (`unreviewed` holds two,
  `config` is set); `P.DECOY` read as `.decoy`; `p.decoy.yaml` read as YAML.
- Conversion cells (M6): for a `ConfigFileError` made from a `LangError`, `__cause__` and
  `__context__` are `None`, and no marker value from the source is in `str(exc)`, `exc.args`
  or any `ConfigProblem`.
- `config_refusal` returns exactly two keys for a three-problem error, and its message names
  the count.
- Import test: in a fresh interpreter, `import decoy._config_file` leaves `decoy_engine` and
  `lark` out of `sys.modules`, and loading a YAML file does too.
- `decoy validate pipeline.decoy` on a twin: exit 0. On a file with a syntax error: exit 1 and
  a `lang.syntax` finding with its line.
- The layer contract, the layer snapshot and `test_package_boundary.py` (`ALLOWED = set()`)
  pass. The guard tests and their seeded spellings pass; M-H2a, M-H2b and M-R3 turn them red.
- `test_language_freeze.py` and `test_codes.py` pass; a seeded unregistered literal fails.
- `docs/cli-reference.md` regenerated; `tests/unit/test_cli_surface.py` passes.

S5:
- `fmt`: a twin is unchanged and `--check` exits 0. A reordered file is printed in the
  canonical layout, `--check` exits 1, `--write` replaces it, and a second `--check` exits 0.
  Comments and `?` marks are kept. A syntax error is exit 1 with its line. A `.yaml` path is
  exit 2.
- `convert`: every bundled YAML template converts, and the output compiles to the same config.
  Every twin converts to YAML equal to its template's config. A marked `.decoy` file is exit 1
  with one finding per mark. A schema-invalid `.decoy` file is exit 1 with the engine code. A
  config with a value the language cannot write is exit 1 `lang.not_convertible`. `--json`
  without `-o` is exit 2.
- json-shapes snapshot, CLI surface test, CHANGELOG entry; no guide page names
  `python -m decoy.lang`.

S2:
- A `.decoy` file with a link missing its namespace, an unknown strategy and one `?`:
  `validate --json` gives three config findings in source order (`lang.link_needs_namespace`,
  `lang.unknown_strategy`, `lang.unreviewed`), each with a `position` on the right line.
- A `.decoy` file that lowers cleanly, with an engine schema problem and two `?` marks: the
  schema finding has the same code, message and `location` as the YAML twin's, its `position`
  is the line of the construct, and two `lang.unreviewed` findings follow; exit 1.
- A file whose only problems are two marks: `validate` exits 1 with two findings. `run` exits 1
  with two findings and never opens its source (the source path does not exist, and the error
  is the mark, not the missing file). `tokenize` exits 1 naming the first mark and the count.
- `ci check` SARIF for the `.decoy` case puts each region on the `.decoy` line. The YAML SARIF
  and `--json` snapshots are unchanged, including the `yaml.not_utf8` case.
- Parity test (`tests/unit/test_source_positions.py`): for every template and its twin, every
  path the YAML index records gives a `Position` from the `.decoy` index; both accept and
  refuse the same spellings; a duplicated table name gives `None` from both.

S3:
- Every route cell passes for the YAML run and the `.decoy` run, with the marker assertion in
  both, and the two runs agree on exit code and finding codes. M-R2 turns the cell red.

S4:
- `pipelines/x/pipeline.decoy` alone is the member `x` for `run x`, `validate x`, completion and
  `project show`. Both files present is `layout.pipeline_file_ambiguous` (exit 1, names the
  folder) for lookup, `run --all` and `init`. A linked `pipeline.decoy` is not a member.
  `docs/project-layout.md` descriptor tests pass. `_layout.py` is at most 800 lines. The name
  guard passes and M-S4 turns it red.

S6:
- `decoy init data.csv` writes `pipelines/data/pipeline.decoy`. Every inferred rule ends with
  `?` under a `# REVIEW:` comment that holds the `Inference.review` text. `decoy validate` on
  it lists one `lang.unreviewed` per inferred rule; after the marks are removed it validates.
- `decoy init data.csv --yaml` writes output byte-identical to today's (snapshot).
- `decoy init --preset hipaa` and `decoy show template hipaa` give the `.decoy` body; `--yaml`
  gives the YAML body. `test_twins.py`, now reading `src/decoy/templates/`, proves each pair,
  including the new `pci.decoy`.
- Init-then-run tests updated. Journey tests (the `CJ` steps and
  `tests/e2e/first_user/journey/test_cli_journey.py`) follow the new default and clear the
  marks the way the docs tell users. Tests that only need a runnable pipeline pass `--yaml`:
  `tests/e2e/test_init_command.py`, `tests/e2e/first_user/test_items_generate_init.py`,
  `tests/e2e/project_layout/test_walkthrough.py`, `tests/e2e/project_layout/test_init_project.py`,
  `tests/e2e/project_layout/test_no_stray_files.py`, `tests/e2e/test_keyed_secret_guidance.py`,
  `tests/e2e/test_source_csv_dialect.py`, `tests/e2e/test_release_smoke.py`,
  `tests/e2e/test_unmask_command.py`, `tests/e2e/cli_fmt/test_target_format_readers.py`. The
  builder confirms the list by searching for tests that call `init` and then `run`.

S7:
- A `.decoy` run with `--evidence-out ev.json` writes `ev.compiled.yaml` (mode 0600), equal to
  `emit_yaml` of the run's config. The manifest has both new fields and verifies clean.
- Editing or deleting the sidecar gives `pipeline_fingerprint_changed` or `pipeline_missing`
  naming it, in `report verify` and `ci check`.
- A YAML run's manifest is unchanged (snapshot); an old manifest still verifies.
- `no_raw_values` passes with marker values in the `.decoy` config.
- `evidence.py` is at most 800 lines; `report show` output is unchanged after the card move.

### S6 mechanism (M4)

- `convert_config(config, *, review: Mapping[tuple[str, str], str] | None = None)`: for each
  `(table, column)` key, the printed rule ends with `?` and gets a `# REVIEW: <note>` comment,
  through the printer's existing `Notes`. The round-trip check ignores marks, so it still
  proves the program.
- `cli/lang/_scaffold.py:decoy_scaffold(yaml_text, review)`: parses the YAML the init wizard
  already builds (`_build_scaffold_yaml`, a CLI-written-text site on the allowlist today) and
  returns the `.decoy` text with a header that says to remove each `?` after checking the rule.
- Files that change: `src/decoy/cli/init.py` (`--yaml`, one call into `decoy_scaffold`, the
  destination kind; stays under 800 lines), `src/decoy/cli/project/_scaffold.py` (destination
  through `member_destination`), `src/decoy/templates/__init__.py` (`Template.decoy_body`),
  `src/decoy/cli/templates.py` and `src/decoy/cli/reference.py` (`show template --yaml`, the
  help example), `src/decoy/lang/_convert.py` (`review`). `_init_inference.py` does not
  change. The wizard's questions, inference and flow stay frozen (decisions.md, 2026-11-19).

## Owner questions

Owner answered all five on 2026-11-19: each recommendation below is the decision.

| # | Question | Decision (owner 2026-11-19) |
|---|---|---|
| O1 | Is `decoy fmt` named `fmt` or `format`? | `fmt`, as in `go fmt` and `terraform fmt` |
| O2 | Does a run record keep the compiled YAML beside the `.decoy` hash? | Yes: it is what the engine ran, and it makes a record readable without the compiler. Built as an owner-only sidecar that the manifest names and hashes, because the manifest holds no config values |
| O3 | With both `pipeline.yaml` and `pipeline.decoy` in a folder, refuse or prefer `.decoy`? | Refuse; two sources of truth is the failure to avoid |
| O4 | Does `decoy init` write `.decoy` by default at 1.0? | Yes, with `--yaml` for the old output, once S1 to S3 are in |
| O5 | The guard `tests/sentry/run/test_no_subset_edit.py` fails on the compiler's `subset` block (hand-off H1) | A narrow exemption for `lang/_subset.py`: stores and dict displays only |
