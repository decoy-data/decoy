Status: plan

# DECOY-LANG commands: `decoy` reads, formats, converts and writes `.decoy`

Date: 2026-11-19. Revision 3. Roadmap row: DECOY-LANG. Parent plan:
[2026-11-19-decoy-language-completion.md](2026-11-19-decoy-language-completion.md), milestones 7
(command), 8 and 9.

Rules consulted: `dev-rules/README.md`, `00-universal.md`, `risk-and-exceptions.md`,
`development-loop.md`, `profiles/local-operations.md`, `workspace-and-vcs.md`, `reuse-first.md`,
`exploration.md`, `scope-discipline.md`, `proportionality.md`, `verification.md`, `feature-dev.md`,
`code-review.md`, `testing.md`, `architecture.md`, `cross-cutting-concerns.md`,
`api-and-compatibility.md`, `config-secrets-and-supply-chain.md`, `security.md`,
`documentation.md`, and `catalogs/recurring-defects.md`.

Risk: R2 overall; each slice has its own level in the slice table. The plan changes frozen 1.0
surfaces: the pipeline file a command accepts, command names, help text, the project layout,
finding locations, and what a run record stores. Nothing in it is built.

## Change log

Revision 3 answers Dennis plan review round 2.

| Finding | Answer | Section |
|---|---|---|
| F1 | S3 writes a valid `.decoy` program by hand, derives its YAML twin from `load_pipeline(p).config`, uses separate marker names by kind, compares every exit code, and compares codes only for JSON cells. It also has a lowering-error marker cell. M-R2 stays. | Choke points and guards; S3 acceptance |
| F2 | `CODES` is public. The language-import guard uses exact module and name pairs. S7 calls `decoy.cli.lang.compiled_yaml`. Every allowed pair has a seeded self-test. | Frozen contracts; Choke points and guards; S7 |
| F3 | S1 now owns the `Position`, `segments`, and `YamlPositionIndex` move, adapter import switch, deletion, SARIF pin, and baseline-key rename. S2 owns `.decoy` positions, `GateFinding.position`, removal of the adapter read, guard test 1, and M-H2b. | Layers and positions; Slices; acceptance |
| F4 | `_source_positions` alone owns path parsing, union-member removal, and nearest-construct lookup. YAML stays exact or file-level. `.decoy` uses nearest construct. The parity test rejects all-`None` positions and covers duplicate names. | Layers and positions; S2 acceptance |
| F5 | Direct JSON adds `position` only to loader findings that have a region. CI JSON and SARIF use positions for loader and engine findings. The JSON shape changes once. | Guarantee; Layers and positions; Frozen contracts |
| F6 | `parse_pipeline_yaml` returns a non-`None` `PipelineFile` with mark findings. The gates hold marks until schema findings and `_load_raw_config` refuses any non-empty finding list. | Gate; S2 acceptance |
| F7 | `report.py` computes `hash_ok` and passes it to the moved UI card. The move adds no import-linter ignore. | Run record; S7 acceptance |
| F8 | `decoy_scaffold` takes the parsed mapping. Keyed guidance comes from that mapping and is written into the `.decoy` header. The YAML-load allowlist stays at 11. | S6 mechanism; S6 acceptance |
| F9 | Init kind comes from `-o`; `-o -` follows `--yaml`; conflicting `--yaml` and `.decoy` is usage error 2. Pathed presets render YAML first and do not keep bundled comments. | Commands; S6 mechanism; S6 acceptance |
| F10 | `PIPELINE_SUFFIXES` and `is_decoy_path` live only in `_config_file`. Pipeline token parsing and completion import them. A sentry rejects another `.yml` literal under `src/decoy/cli`. | One loader; Project layout; S1 acceptance |
| F11 | A manifest with only one compiled-pipeline field is malformed. The sidecar path resolves through `resolve_manifest_path`, like `pipeline_path`. | Run record; S7 acceptance |
| F12 | `pci.decoy` is moved from the existing twins folder. It is not new. | What exists; Placement; S6 acceptance |
| F13 | The caller and help-text count is 12. | Commands; Frozen contracts; Routes |
| F14 | A config refusal keeps the exit each command gives today, including exit 3 for `report integrity --config`. | Review mark; S3 acceptance |
| F15 | `fmt --write` uses the local atomic path that preserves an existing file's mode. | Commands; S5 acceptance |
| F16 | The language-import guard seeds star import, dynamic package import, dynamic private import, and aliased private import spellings. | Choke points and guards |
| F17 | The preflight success message says `Pipeline syntax is valid.` | S1 acceptance |
| F18 | One private decoder serves `read_config_text` and `read_decoy_text`. | One loader; S1 acceptance |
| F19 | Ambiguous member folders are invalid in `list_pipelines`, completion, `project show`, and `project list`. | Project layout; S4 acceptance |
| F20 | Every named mutation is rerun on the final head of its slice. | Slices; acceptance |
| F21 | S6 checks that the built wheel contains `decoy/templates/*.decoy`. | S6 acceptance |

Revision 2 answered round 1. Revision 3 keeps those answers except where the table above
changes slice ownership or a shared mechanism.

## What exists

The compiler, converter and formatter are in `src/decoy/lang/` (`compile_text`,
`convert_config`, `format_text`, each tested). `python -m decoy.lang` is the interim entry. No
`decoy` command reads a `.decoy` file. `compile_text` runs the engine's `parse_pipeline_config`
itself and rewrites every engine problem to the code `lang.config`
(`src/decoy/lang/_validate.py:46-50`), while the gate's schema layer reports engine codes
(`src/decoy/cli/gate/_layers.py:119-129`). All 11 bundled templates already have a `.decoy`
twin in `tests/unit/lang/twins/`, including `pci.decoy`. S6 moves those twins into
`src/decoy/templates/`.

## Guarantee and non-goals

1. Every command that takes a pipeline file accepts a `.decoy` file wherever it accepts a YAML
   file. When the two files give the same config:
   - the exit code is the same;
   - every engine, schema, compile-layer and preflight finding has the same code, severity,
     message and dotted `location` as for the YAML file;
   - the `--json` result document is the same apart from the file name and its hash. Direct
     command JSON adds `position` only for a `yaml.*` or `lang.*` loader problem that has a
     region. CI JSON and SARIF add a region for both loader and engine findings when known.

   Problems found while reading the `.decoy` text (parse and lowering, before any engine
   validation) carry `lang.*` codes. They have no YAML equivalent.
2. Where YAML gives an exact region, `.decoy` gives a non-`None` line for the construct that
   produced the finding. A `lang.*` loader problem carries its line and column on direct JSON,
   CI JSON, and SARIF. Direct commands keep the dotted `location` for engine findings. CI JSON
   and SARIF also use `GateFinding.position` for engine findings of both file kinds.
3. A `.decoy` file with a rule still marked `?` is refused by every command that reads data,
   before any source is read, with exit 1 and one finding per mark. `decoy validate` reports the
   marks beside every other config-layer problem.
4. No message quotes a value from the file. A converted `LangError` has no `__cause__` and no
   `__context__`.
5. YAML keeps the same codes, texts, exit codes, dotted locations, and SARIF regions. Its direct
   JSON changes only when a loader problem already has a region, and that one additive shape
   update is pinned in `json-shapes.json`.

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
- One position owner: YAML and `.decoy` share `segments`, union-member removal, and lookup rules
  in `_source_positions`. YAML keeps exact-or-file-level lookup. `.decoy` uses nearest
  construct. The parity test pins the intended difference.
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
PIPELINE_SUFFIXES = (".yaml", ".yml", ".decoy")
def is_decoy_path(path: str | Path) -> bool
```

- Kind rule (L3): `PIPELINE_SUFFIXES` is the only pipeline suffix table and `is_decoy_path` is
  the only kind check. Both live in `decoy._config_file`. A `.decoy` suffix is compared
  case-insensitively. Every other path is YAML. `cli/io/_pipelines.py:56` uses
  `PIPELINE_SUFFIXES` in `looks_like_path`; `cli/completers.py:130` uses it for file completion.
  A member file name is exact (`pipeline.decoy`), as `pipeline.yaml` is today. A sentry asserts
  that no other string literal equal to `.yml` exists under `src/decoy/cli`.
- YAML: today's steps and the four `yaml.*` codes, unchanged. `locate` is
  `YamlPositionIndex.from_text(text).locate`, built on first call.
- One private decoder takes bytes plus the fixed not-UTF-8 code and text. Both
  `read_config_text` and `read_decoy_text` call it. The existing read-and-decode sentry still
  sees one owner. `read_decoy_text` drops a BOM and decodes strict UTF-8. Non-UTF-8 is
  `lang.not_utf8`, "Pipeline file is not UTF-8 text."; text that is empty or only whitespace is
  `lang.empty`, "Pipeline file is empty." Then the loader calls `decoy.lang.lower_text(text)`.
  A `LangError` becomes one `ConfigFileError` with one `ConfigProblem` per diagnostic, raised
  after the handler closes. `locate` is `DecoyPositionIndex(config, source_map).locate`.
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

- S1 creates `src/decoy/_source_positions.py` and moves the YAML location code from
  `ci/locations.py` into it without changing behavior. It owns:
  - `Position(line, column, end_line, end_column)`, with every field optional. All `None` means
    file-level only and never satisfies a region assertion.
  - `segments(logical_path)`, the only parser for numeric, bracket, semantic, and mapping-key
    paths. It rejects empty, `*`, and `<pseudo>` segments.
  - `YamlPositionIndex`, which stays exact-or-file-level. A missing leaf under a proven parent
    is file-level. Duplicate YAML keys or semantic names are ambiguous.
  - the union-member removal and nearest-construct lookup used for source maps.
- S1 deletes `src/decoy/ci/locations.py`. `ci/adapters.py` changes only its import to
  `decoy._source_positions.YamlPositionIndex`; it still reads the text and builds the same YAML
  index. The existing SARIF snapshot pins that no-behavior-change move.
- S2 adds `DecoyPositionIndex`. It calls `segments`, drops a source or target union member in
  the shared rule, and uses the shared nearest-construct lookup. `lang/_validate.py` calls the
  same functions; its `path_of` and `locate` copies are deleted. `.decoy` positions use nearest
  construct. YAML positions do not.
- `_source_positions` takes a source map as path tuples mapped to objects with `line` and
  `column`; it does not import `decoy.lang`.
- `.importlinter`: `lang` moves to the low tier, and `_source_positions` is alone on a new last
  layer below `lang`. The layer snapshot changes with it. The builder checks the root-package
  fan-out limit before adding the module.
- `src/decoy/lang/__main__.py` is deleted: it imports `_config_file`, which is now above it.
  `tests/unit/lang/test_package_boundary.py` then has `ALLOWED = set()`.
- In S1, the baseline key `ci/locations.py::YamlSourceIndex.from_text::1` in
  `tests/sentry/baselines/config-load-allow.json` is renamed to
  `_source_positions.py::YamlPositionIndex.from_text::1`, same kind and reason. It is a move,
  not growth: the entry count stays 11.
- In S2, `GateFinding` gains a last field `position: Position | None = None`. The gate fills it
  from `PipelineFile.locate(logical_path or location)` for schema, compile, and preflight
  findings, and from `ConfigProblem.position` for loader problems.
- In S2, `ci/adapters.py` stops its read and index build. It calls the gate with the path and
  builds `SourceLocation(uri=rel, ...)` from `item.position`. Its `yaml.not_utf8` special case
  goes. Guard test 1 and M-H2b land here, after the read is removed.
- Direct command JSON includes `position` only for `yaml.*` and `lang.*` loader findings with
  a non-`None` region. Engine findings keep dotted `location` only on direct JSON. CI JSON and
  SARIF use `position` for both loader and engine findings. The JSON-shapes snapshot changes
  once in S2.
- Position parity uses a synthetic config and source map, including a duplicate table name.
  Wherever YAML gives an exact region, `.decoy` must give a `Position` with a non-`None` line.
  An all-`None` `Position` is not a pass.

### Gate (`cli/gate/_layers.py`)

- `parse_pipeline_yaml(path, source_text)` calls `load_pipeline` and returns
  `(PipelineFile | None, findings)`. A read, parse, or lowering failure returns `None` and one
  finding per `ConfigProblem`. A successful load with marks returns the non-`None`
  `PipelineFile` and one `lang.unreviewed` finding per mark.
- `run_config_gate` and `run_gate` stop immediately only when the pipeline is `None`. They hold
  mark findings, run the schema layer, then append marks after every schema finding. If schema
  findings or marks exist, the config layer fails and compile and preflight do not run.
- `run/_prepare.py:_load_raw_config` refuses whenever the returned finding list is non-empty,
  including marks on a non-`None` pipeline. That is before layout and before any source opens.
  Acceptance counts exactly two mark findings from `validate` and exactly two from `run`.
- `cli/gen/_scaffold.py:144` calls `load_pipeline(staged_path, text=config_text)` instead of
  `parse_config_mapping` (CLI-written YAML, suffix `.yaml`).

### The review mark (H4)

| Command | A file whose only problems are `?` marks |
|---|---|
| `validate`, `validate config`, `ci check` | Report every mark beside the other config-layer findings; exit 1 |
| `run`, `project run --all` (each member) | Refuse at the parse step, one finding per mark; exit 1; no source read |
| `validate compile`, `validate preflight`, `subset`, `tokenize`, `detokenize`, `unmask`, `report fidelity/integrity/vault --config`, Python `mask(config=path)` | Refuse through `load_config_mapping`; keep the exit each command gives a config refusal today. In particular, `report integrity --config` exits 3. The message names the first mark and the count. |
| `convert pipeline.decoy` (to YAML) | Refuse with exit 1 because YAML cannot keep review marks |
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
- `list_pipelines` does not hide an ambiguous member. It raises
  `layout.pipeline_file_ambiguous`. Pipeline completion catches that refusal, omits project
  names, and still offers path completions. `project show` refuses with the code. `project
  list` records the project as invalid with the same warning code instead of reporting a lower
  pipeline count.
- `_layout_errors.py` registers `PIPELINE_FILE_AMBIGUOUS` (the message names the folder, never
  file content) among the gate descriptors, so `GATE_CODES` and `validation_codes` carry it.
- `_layout.py` stays at or under 800 lines: `PIPELINE_YAML` and `member_yaml` leave it, and
  lines 331 and 350 test `parts[2] in PIPELINE_FILES`. The cap is not raised.
- Inventory today:

| Site | Change |
|---|---|
| `cli/io/_layout.py:55-60` (`PIPELINE_YAML`, `member_yaml`) | Removed; replaced by `_member_file.py` |
| `cli/io/_layout.py:331` (`_taken`), `:350` (`pipeline_name_for`) | Either file name is a member |
| `cli/io/_pipelines.py:56`, `:116` | Deletes `_PATH_SUFFIXES`; imports `PIPELINE_SUFFIXES` from `_config_file` (S1) |
| `cli/io/_pipelines.py:182-205` (`member_has_link`, `_member`), `:310` | Use `member_file`; the error path names the file found |
| `cli/io/__init__.py:48, 216` | Exports `member_file`, `member_destination`, `PIPELINE_FILES` instead of `member_yaml` |
| `cli/project/_scaffold.py:36, 109-112` | Destination from `member_destination` |
| `cli/completers.py:130` | Uses `PIPELINE_SUFFIXES`; offers `.decoy` files; no local suffix tuple |
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
- The same sentry rejects any `.yml` string literal under `src/decoy/cli`; the only suffix
  registry is `decoy._config_file.PIPELINE_SUFFIXES`.

### What a run stores (M3)

For a `.decoy` pipeline run with `--evidence-out`:

- `pipeline_path` and `pipeline_fingerprint` name and hash the `.decoy` file, as written.
- The compiled YAML (`decoy.cli.lang.compiled_yaml` of the exact dict the run hands the engine)
  is written to an
  owner-only sidecar beside the manifest, `<manifest stem>.compiled.yaml`, through
  `decoy._private_file` and `_atomic`. It holds the config, the same class of content as the
  user's own pipeline file, so it is owner-only and never inside the manifest.
- The manifest gains two additive `cli-local-1` fields, `compiled_pipeline_path` and
  `compiled_pipeline_fingerprint`, both optional in `_FIELDS` and both covered by
  `manifest_hash`. `check_manifest` requires both or neither; a manifest with only one is
  malformed. YAML runs and old manifests have neither and verify unchanged.
- `report verify` and `decoy ci check` rehash the sidecar through `_stored_files` as a
  pipeline-kind entry: a missing sidecar is `pipeline_missing`, a changed one
  `pipeline_fingerprint_changed`, each naming the sidecar path. `_stored_files` passes the
  recorded sidecar through `resolve_manifest_path` with the manifest's path-base rule, exactly
  like `pipeline_path`. No new issue code.
- The `no_raw_values` test gains a `.decoy` run whose config holds marker values: no marker in
  the manifest; the sidecar is mode 0600.
- Write order: the sidecar first, then the manifest, so a manifest never names a sidecar that
  was not written. If the manifest write fails, the sidecar is removed; a failed removal is
  named in the same error line. The exit stays `EXIT_RUNTIME`, as today
  (`src/decoy/cli/run/_evidence.py:52-56`).
- `evidence.py` is at 792 lines. S7 first moves `_render_manifest_card` (lines 700-781) to
  `src/decoy/ui/evidence_card.py`. The UI function takes `hash_ok: bool`; it does not import or
  call `compute_manifest_hash`. `report.py:1130` computes the boolean and passes it with the
  existing arguments. The output stays unchanged. No `.importlinter` ignore is added. The
  writer side goes in `cli/run/_evidence.py` (61 lines) and gets YAML text only from
  `decoy.cli.lang.compiled_yaml`.

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
| `decoy fmt FILE` (new) | `cli/lang/_fmt.py` | Prints the canonical layout; `--write` replaces through `_atomic.staged_local_target` so an existing file keeps its mode; `--check` exits 1 when the file would change; a non-`.decoy` path is a usage error (exit 2) |
| `decoy convert FILE` (new) | `cli/lang/_convert.py` | YAML in: prints the `.decoy` program (`convert_config`). `.decoy` in: prints the compiled YAML after the engine's schema check, refusing any problem or mark. `-o PATH` writes through `_atomic`. A refusal is exit 1 with its code (`lang.not_convertible` for a `ConvertError`) |
| `decoy init` | `cli/init.py` | Writes Decoy by default, with inferred rules marked `?`. `-o .yaml` or `.yml` selects YAML, `-o .decoy` selects Decoy, another suffix is usage error 2, and `-o -` follows `--yaml`. `--yaml` with a `.decoy` destination is usage error 2. |
| `decoy show template NAME` | `cli/templates.py` | Prints the `.decoy` body; `--yaml` prints the YAML body (S6) |

`plan`, `scan` and `explain pipeline` take no pipeline file and are out of scope. The compiled
YAML view is `decoy convert pipeline.decoy`: one command converts both ways, chosen by the
input's kind, so no `show pipeline` kind and no `validate` flag is added.

`convert -o` into a pipeline folder that already holds the other file writes it and prints a
warning that the folder is refused until one file is removed. Writing is safe because every
reader refuses that folder.

For `init --preset` with source or target paths, the existing renderer first builds the
path-adjusted YAML mapping, then `decoy_scaffold(config, review={})` writes Decoy. Bundled YAML
comments are not kept on that path. The config and keyed guidance are kept.

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
`_codes.py` imports nothing. `decoy.lang` exports `CODES` and includes it in `__all__`.
`tests/unit/lang/test_codes.py` walks `src/decoy/lang/`,
`src/decoy/_config_file.py` and `src/decoy/cli/lang/` for `lang.*` string literals: each is in
`CODES`, and each entry of `CODES` is used. Seeded: a literal not in the registry is reported.

`ci/rule_codes.py:validation_codes()` adds `CODES`, imported inside the function as the layout
codes are, so a `.decoy` finding never maps to the unknown rule id. It takes the whole
registry, so the two sets cannot drift.

Changed with the commands and loader positions: the json-shapes snapshot changes once
(`tests/fixtures/release_freeze/json-shapes.json`, `tests/e2e/release_freeze/write_shapes.py`)
for `fmt` and `convert`; `CHANGELOG.md`; `docs/cli-reference.md` regenerated; the help text at
all 12 `resolve_pipeline` call sites says "pipeline file (.yaml or .decoy)"
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
- The import guard uses exact `(importer module, imported public name)` pairs:
  `decoy._config_file` may import `lower_text` and `LangError`; `decoy.cli.lang` may import
  `format_text`, `convert_config`, `emit_yaml`, `ConvertError`, `LangError`, and `render`;
  `decoy.ci.rule_codes` may import `CODES` only inside `validation_codes`. No importer may use a
  private `decoy.lang._*` module. Any CLI config comes from `load_pipeline`.
- `decoy.cli.lang.compiled_yaml(config)` is the command-layer helper that calls the allowed
  public `emit_yaml`. S7 calls this helper and does not import `decoy.lang` from
  `cli/run/_evidence.py`.

Guard: `tests/sentry/io_policy/test_config_load_choke_point.py` gains three tests over
`src/decoy`, with the AST walk in `_yaml_load_sites.py`:
1. the `read_config_text` call sites equal the allowlist;
2. no import of `_parse_yaml_mapping`, or of any `_` name of `decoy._config_file`, outside it;
3. the exact language import pairs above, including the function scope for
   `decoy.ci.rule_codes::validation_codes`.

Seeded spellings, each a self-test: `import decoy.lang as L` then `L.lower_text(t)`;
`from decoy.lang import compile_text`; the attribute call `decoy.lang.compile_text(t)` after
`import decoy`; `from decoy.lang._lower import lower`; `from decoy import lang`;
`from decoy.lang import *`; `__import__("decoy.lang")`;
`importlib.import_module("decoy.lang")`; `importlib.import_module("decoy.lang._lower")`;
`import decoy.lang._lower as x`; and the bypass
`from decoy._config_file import _parse_yaml_mapping, read_config_text` then
`_parse_yaml_mapping(read_config_text(p))`.
Each allowed pair also has a seeded positive self-test. Moving the `CODES` import to module
scope or adding one name to an allowed importer turns the guard red.

Mutations that must turn the guard red:
- M-H2a: in `cli/validate.py`, add `from decoy.lang import compile_text` and compile the
  path's text there. Test 3 fails.
- M-H2b: in `ci/adapters.py`, restore `text = read_config_text(path)` before the gate call.
  Test 1 fails.

Rule 2: a command that takes a pipeline file accepts both kinds and gives the same result.
Guard: the route-cell table in `tests/sentry/defects/test_config_error_routes.py` already walks
every command with a config parameter. The test writes the schema-invalid `.decoy` marker
program by hand. It must parse and lower cleanly, then fail engine schema because an extra key
was added through `options { }`. It does not call `convert_config` on an invalid config.
The test loads that program with `load_pipeline(p).config`, then writes the YAML twin with
`yaml.safe_dump`. `_FIRST_YAML`, `_EXTRA_YAML`, `_FIRST_DECOY`, and `_EXTRA_DECOY` are distinct,
so each run proves its own marker is absent. Every cell compares the YAML and `.decoy` exit
codes. Only cells that invoke `--json` compare finding-code lists, because human output has no
stable code document. Each run keeps the marker checks on stdout, stderr, JSON, notifications,
and output files that the existing cell covers. One extra `.decoy` cell puts markers inside a
lowering error, asserts no marker escapes, and expects exit 1. A command added later gets both
runs or fails the walk. Mutation M-R2 stays: make `cli/unmask.py` call `yaml.safe_load` on the
path text. Its `.decoy` run fails, and the existing YAML reader sentry fails too.

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
- `decoy fmt --write` uses `_atomic.staged_local_target` so it keeps an existing mode;
  `decoy convert -o` uses the normal local-target replace. A failure leaves the old file and
  exits 3.
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

- stdout human text and `--json` success documents (`position` only on positioned loader
  findings; new `fmt` and `convert` shapes).
- stderr error lines and the `--json` error object (`config_refusal`, two keys, unchanged
  schema).
- SARIF and the CI JSON from `ci check` (regions on `.decoy` lines).
- Files: the evidence manifest and sidecar, `fmt --write`, `convert -o`, `init` output.
- Help text at the 12 `resolve_pipeline` call sites (`src/decoy/cli/io/_pipelines.py:148`,
  `:161`), the
  completer, and Typer's own parse errors for a missing path (unchanged text).
- Logs: the CI debug sink on a crashed check (unchanged; the loader adds no log line).

## Reuse inventory

- `decoy._config_file` and its sentry `test_config_load_choke_point.py`, with the shrink-only
  baseline `config-load-allow.json`.
- The YAML mark walker in `ci/locations.py`, moved, not rewritten.
- `decoy.lang`: `SourceMap`, the existing `_validate.locate` behavior moved into
  `_source_positions`, the
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
- Changing the help text at 12 sites breaks `docs/cli-reference.md`; S1 regenerates it.
- The init default change breaks the QA journey document; S6 updates
  `docs/qa/cli-v1-journey.md` with the journey tests.
- `src/decoy/lang/` is still being changed by another builder on
  `claude/sweet-einstein-u3104u`. S1 starts from main after that branch merges, never on top of
  it.

## Placement

| New file | Directory | CODEMAP "Where things go" line | Sits beside |
|---|---|---|---|
| `_source_positions.py` | `src/decoy/` | Expand the private-shared-primitives CODEMAP row to include source-position primitives used by more than one package; used by `_config_file`, `lang`, the gate and `ci` | `_yaml_errors.py` |
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
| S1 | Loader (`PipelineFile`, `load_pipeline`, `ConfigProblem`, `read_decoy_text`), shared decoder and suffix registry, `lower_text`, `_codes.py`, `Position`, `segments`, moved `YamlPositionIndex`, adapter import switch, `ci/locations.py` deletion, baseline rename, layer move, `__main__` deletion, help text, import guards except the adapter-read guard, language freeze test | R2 | loader shape, help text, the language, unchanged YAML SARIF | ~150 src lines in `_config_file.py`, ~45 in `lang/`, ~70 in `_codes.py`, ~190 moved position lines, -86 for `__main__`; ~450 test lines; 9 public names added, 1 made private |
| S5 | `decoy fmt`, `decoy convert`; guide pages off `python -m decoy.lang` | R2 | command names, json shapes | ~250 src lines in `cli/lang/`; ~250 test lines; 2 commands |
| S2 | `DecoyPositionIndex`, shared nearest lookup, deletion of `lang/_validate.py` path copies, `GateFinding.position`, gate mark ordering, removal of the adapter read, guard test 1 and M-H2b, `validation_codes`, JSON and SARIF position output | R2 | finding positions, JSON, SARIF | ~70 source-position lines, ~40 in the gate, adapter deletion; ~250 test lines |
| S3 | Both-kinds route cells | R1 | none | ~200 test lines |
| S4 | `_member_file.py`, `layout.pipeline_file_ambiguous`, layout sites, completion, `run --all`, name guard | R2 | project layout | ~90 src lines new, ~20 changed; ~180 test lines |
| S6 | `decoy init` and templates write `.decoy` | R2 | init output, template text | ~40 in `lang/_convert.py`, ~60 in `cli/lang/_scaffold.py`, ~25 in `init.py`, ~20 in templates; 11 `.decoy` bodies; ~200 test lines changed |
| S7 | Run record sidecar and paired fields, `compiled_yaml` route, manifest path resolution | R2 | `cli-local-1` | card move (~80 lines, no output change), ~40 in `run/_evidence.py`, ~15 in `evidence.py`; ~140 test lines |

Every named mutation is rerun after the last change on the final head of its slice. The build
record names that head and each red test. A later edit voids the mutation evidence and reruns it.

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
- Decoder tests call the private decoder through both `read_config_text` and `read_decoy_text`:
  BOM, strict UTF-8 refusal, no exception context, and the kind-specific fixed code and text.
- `PIPELINE_SUFFIXES` drives `looks_like_path` and completion. `.YML`, `.YAML`, and `.DECOY`
  work. The sentry rejects a seeded `.yml` literal in a CLI module.
- `decoy validate pipeline.decoy` on a twin: exit 0. On a file with a syntax error: exit 1 and
  a `lang.syntax` finding with its line.
- The `YamlPositionIndex` move leaves its unit tests and the YAML SARIF snapshot unchanged. The
  config-load baseline has 11 entries under the renamed key. The adapter imports the new module
  but still performs its old read in this slice.
- The layer contract, the layer snapshot and `test_package_boundary.py` (`ALLOWED = set()`)
  pass. The import guard's positive and negative seeded spellings pass; M-H2a and M-R3 turn the
  final S1 head red.
- `test_language_freeze.py` and `test_codes.py` pass; a seeded unregistered literal fails.
- `validate preflight` reports the kind-neutral pass message `Pipeline syntax is valid.`
- `docs/cli-reference.md` regenerated; `tests/unit/test_cli_surface.py` passes.

S5:
- `fmt`: a twin is unchanged and `--check` exits 0. A reordered file is printed in the
  canonical layout, `--check` exits 1, `--write` replaces it, and a second `--check` exits 0.
  A file set to mode 0640 stays 0640 after `--write`. Comments and `?` marks are kept. A syntax
  error is exit 1 with its line. A `.yaml` path is exit 2.
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
  with exactly two findings and never opens its source. The source path does not exist, and the
  error is the mark, not the missing file. `tokenize` exits with its current config-refusal code,
  naming the first mark and the count.
- `ci check` SARIF for the `.decoy` case puts each region on the `.decoy` line. The YAML SARIF
  snapshot stays unchanged, including `yaml.not_utf8`. Direct JSON adds `position` only to a
  positioned loader problem. CI JSON and SARIF use positions for loader and engine findings.
  `json-shapes.json` is updated once.
- Parity test (`tests/unit/test_source_positions.py`): synthetic YAML, config, and source map
  cover numeric, bracket, semantic, union-member, missing-leaf, and duplicate-table-name paths.
  For every exact YAML region, `.decoy` returns a position with a non-`None` line. An all-`None`
  position fails. YAML missing leaves stay file-level; `.decoy` uses nearest construct.
- The adapter no longer reads or builds an index. Guard test 1 and M-H2b pass and turn red on
  the final S2 head.

S3:
- The schema-invalid `.decoy` program is handwritten with an unknown key in `options { }` and
  lowers cleanly. Its YAML twin is `yaml.safe_dump(load_pipeline(p).config)`. Separate
  `_FIRST_*` and `_EXTRA_*` markers prove each kind independently.
- Every route cell checks both kinds and compares exit codes. JSON cells also compare finding
  codes. All cells check their own markers on every covered surface. Config errors keep the
  exit each command gives today; `report integrity --config` is pinned at exit 3.
- One `.decoy` lowering-error cell contains markers, emits none, and exits 1. M-R2 turns the
  route cell red on the final S3 head.

S4:
- `pipelines/x/pipeline.decoy` alone is the member `x` for `run x`, `validate x`, completion and
  `project show`. Both files present is `layout.pipeline_file_ambiguous` (exit 1, names the
  folder) for lookup, `run --all`, and `init`. `list_pipelines` raises it, completion omits
  project names but still returns path candidates, `project show` refuses, and `project list`
  reports the project invalid with that code. A linked `pipeline.decoy` is not a member.
  `docs/project-layout.md` descriptor tests pass. `_layout.py` is at most 800 lines. The name
  guard passes and M-S4 turns it red.

S6:
- `decoy init data.csv` writes `pipelines/data/pipeline.decoy`. Every inferred rule ends with
  `?` under a `# REVIEW:` comment that holds the `Inference.review` text. `decoy validate` on
  it lists one `lang.unreviewed` per inferred rule; after the marks are removed it validates.
- One cell for each output-kind case: default member is `.decoy`; `-o p.yaml` and `-o p.yml`
  are YAML; `-o p.decoy` is Decoy; another suffix exits 2; `-o -` is Decoy unless `--yaml` is
  set; `--yaml -o p.decoy` exits 2.
- `decoy init data.csv --yaml` writes output byte-identical to today's snapshot. The default
  `.decoy` header includes the keyed-secret guidance when its mapping is keyed. The existing
  `test_keyed_secret_guidance` runs on the default `.decoy` path and has a `--yaml` twin.
- `decoy init --preset hipaa` and `decoy show template hipaa` give the `.decoy` body; `--yaml`
  gives the YAML body. A preset with adjusted paths compiles from the adjusted mapping and does
  not keep bundled comments. The `gdpr`, `hipaa`, and `pci` `.decoy` headers carry the same
  keyed-secret guidance as their YAML twins. `test_twins.py`, now reading
  `src/decoy/templates/`, proves each pair. `pci.decoy` is moved from
  `tests/unit/lang/twins`; it is not newly authored.
- Init-then-run tests updated. Journey tests (the `CJ` steps and
  `tests/e2e/first_user/journey/test_cli_journey.py`) follow the new default and clear the
  marks the way the docs tell users. Tests that only need a runnable pipeline pass `--yaml`:
  `tests/e2e/test_init_command.py`, `tests/e2e/first_user/test_items_generate_init.py`,
  `tests/e2e/project_layout/test_walkthrough.py`, `tests/e2e/project_layout/test_init_project.py`,
  `tests/e2e/project_layout/test_no_stray_files.py`, `tests/e2e/test_keyed_secret_guidance.py`,
  `tests/e2e/test_source_csv_dialect.py`, `tests/e2e/test_release_smoke.py`,
  `tests/e2e/test_unmask_command.py`, `tests/e2e/cli_fmt/test_target_format_readers.py`. The
  builder confirms the list by searching for tests that call `init` and then `run`.
- Build the wheel and inspect its file list. It contains all `decoy/templates/*.decoy` files.

S7:
- A `.decoy` run with `--evidence-out ev.json` writes `ev.compiled.yaml` (mode 0600), equal to
  `decoy.cli.lang.compiled_yaml` of the run's config. The manifest has both new fields and
  verifies clean.
- Removing either new field alone makes `check_manifest` return `malformed`. Removing both is
  accepted as an old manifest.
- Project-relative and old-rule sidecar paths resolve through `resolve_manifest_path`, with the
  same containment and path-base behavior as `pipeline_path`.
- Editing or deleting the sidecar gives `pipeline_fingerprint_changed` or `pipeline_missing`
  naming it, in `report verify` and `ci check`.
- A YAML run's manifest is unchanged (snapshot); an old manifest still verifies.
- `no_raw_values` passes with marker values in the `.decoy` config.
- `evidence.py` is at most 800 lines. `report.py` computes `hash_ok`; the UI card receives it.
  `report show` output is unchanged and the import-layer baseline gains no ignore.

### S6 mechanism (M4)

- `convert_config(config, *, review: Mapping[tuple[str, str], str] | None = None)`: for each
  `(table, column)` key, the printed rule ends with `?` and gets a `# REVIEW: <note>` comment,
  through the printer's existing `Notes`. The round-trip check ignores marks, so it still
  proves the program.
- `cli/lang/_scaffold.py:decoy_scaffold(config: Mapping[str, Any], review)`: takes the parsed
  mapping already held by init. It does not call `yaml.safe_load`. It derives whether the
  config is keyed from that mapping and returns `.decoy` text with a header that says to remove
  each `?` after checking the rule. A keyed config's header also carries the existing required
  mask-secret guidance. The existing `_print_keyed_hint` CLI-written-YAML reader remains for
  YAML output only, so its existing allowlist entry stays live. No new YAML load is added and
  the config-load allowlist stays at 11.
- Init decides kind once. A member defaults to `.decoy`. An explicit `.yaml` or `.yml` output
  is YAML, `.decoy` is Decoy, any other suffix is usage error 2, and stdout uses YAML only with
  `--yaml`. `--yaml` plus a `.decoy` output is usage error 2.
- Column inference keeps the mapping used to build YAML and passes it with review notes to
  `decoy_scaffold`. A preset with adjusted source or target paths renders YAML through the
  existing path renderer, loads that CLI-written YAML through the existing allowed site, then
  passes its mapping to `decoy_scaffold(config, review={})`. Bundled template comments are not
  kept in this path-adjusted Decoy output.
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
