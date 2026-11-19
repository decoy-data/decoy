Status: draft

# DECOY-LANG commands: `decoy` reads, formats, converts and writes `.decoy`

Date: 2026-11-19. Roadmap row: DECOY-LANG. Parent plan:
[2026-11-19-decoy-language-completion.md](2026-11-19-decoy-language-completion.md), milestones 7
(command), 8 and 9.

Rules consulted: `dev-rules/README.md`, `00-universal.md`, `risk-and-exceptions.md`,
`development-loop.md`, `feature-dev.md`, `architecture.md`, `proportionality.md`,
`cross-cutting-concerns.md`, `api-and-compatibility.md`, `testing.md`, `documentation.md`,
`catalogs/recurring-defects.md`.

Risk: R2. This plan changes frozen 1.0 surfaces: the pipeline file a command accepts, command
names, help text, the project layout and what a run record stores about its pipeline file. It is
written for the main orchestration to review and build. Nothing in it is built.

## What exists

The compiler, converter and formatter are in `src/decoy/lang/` (`compile_text`, `convert_config`,
`format_text`, each tested). `python -m decoy.lang` is the interim way to reach them. No `decoy`
command reads a `.decoy` file.

## Guarantee and non-goals

1. Every command that takes a pipeline file accepts a `.decoy` file wherever it accepts a YAML
   file, and behaves the same for the two files when they compile to the same config: same
   output, same exit code, same result document apart from the file name and its hash.
2. A finding or error about the config points at a line of the `.decoy` file, in the place a YAML
   finding points at a YAML line.
3. A `.decoy` file with a rule still marked `?` is refused by `decoy run` before any source is
   read, with exit 1 and one finding per marked line. `decoy validate` reports the same findings.
4. No message quotes a value from the file. This is already true of the compiler's diagnostics.
5. YAML keeps working unchanged. No YAML pipeline behaves differently after this change.

Non-goals: a `.decoy` form of the CI manifest, `decoy.yaml` or a policy file; changing what the
engine receives; the `policy` block (milestone 12).

## Established solutions

One loader that dispatches on the file's kind and returns the same value for every kind is how
Terraform reads `.tf` and `.tf.json`, and how dbt reads SQL and Python models: the rest of the
tool never learns which was written. This repository already has that choke point for YAML,
`decoy._config_file`, guarded by `tests/sentry/io_policy/test_config_load_choke_point.py`. The
design extends it rather than adding a second one.

## Design

### One loader

`decoy._config_file` gains the only place that decides how a pipeline file is read:

```python
@dataclass(frozen=True)
class PipelineFile:
    config: dict[str, Any]          # the mapping every command already works with
    locate: Callable[[str], SourceLocation | None]   # config path -> line in the file as written
    unreviewed: tuple[SourceLocation, ...]           # always empty for YAML

def load_pipeline(path: Path, *, text: str | None = None) -> PipelineFile
```

- A path ending in `.decoy` is compiled with `decoy.lang.compile_text`. A `LangError` becomes a
  `ConfigFileError` per diagnostic, with the diagnostic's code (`lang.*`), message and position.
- Any other path is read as today (`yaml.safe_load`, the four `yaml.*` codes).
- `locate` wraps the YAML mark index (`decoy.ci.locations.YamlSourceIndex`) for YAML and the
  compiler's source map for `.decoy`. The mark index moves below `_config_file` or is passed in,
  whichever the layer contract allows; the plan review decides.
- `load_config_mapping(path)` stays, as `load_pipeline(path).config`, so the ten callers that need
  only the mapping change nothing.

### Layers

`decoy.lang` moves to the bottom tier of `.importlinter` (beside `_yaml_errors`), since
`_config_file` now imports it. It imports nothing from the rest of `decoy` once
`src/decoy/lang/__main__.py` is deleted, which this plan does; `test_package_boundary.py` then
allows no import at all.

### Call sites

Sixteen sites read a pipeline file today. By what they need:

| Need | Sites | Change |
|---|---|---|
| The mapping only | `api.py:105`, `cli/report.py` (3), `cli/tokenize.py` (2), `cli/compile_explain.py`, `cli/unmask.py`, `cli/subset.py`, `cli/preflight.py`, `cli/io/_placement.py:394` | None: `load_config_mapping` dispatches |
| The mapping and line numbers | `cli/gate/_layers.py:102` (the gate behind `validate`, `ci check`, `run`), `ci/adapters.py:86` | Take a `PipelineFile`; findings use `locate` |
| YAML text the CLI wrote itself | `cli/gen/_scaffold.py:144` | None; it is not a user file |
| Not a pipeline | `ci/manifest.py:166` | None |

### The review mark

The gate's config layer adds one error finding per entry of `PipelineFile.unreviewed`, code
`lang.unreviewed`. `run` already refuses on a gate error, so no second check is written.

### Project layout

A pipeline folder may hold `pipeline.decoy` instead of `pipeline.yaml`. Both present is an error
that names the folder. The places that spell the file name are found by a walk, not a grep, at
build time; known ones: `cli/project/_scaffold.py` (destination), `cli/io/_placement.py` (claims
and names), `cli/project/_run_all.py:164`, `cli/completers.py:130` (completion offers `.decoy`).
`docs/project-layout.md` and its descriptors change with them.

### What a run stores

`pipeline_fingerprint` and the evidence record hash the pipeline file's bytes. For a `.decoy`
file they hash the `.decoy` bytes, and the record names the file as written. The compiled config
is what the engine hashes for seeds and signed evidence, and that does not change. Whether the
record should also store the compiled YAML is an owner question (O2).

### Commands

| Command | Change |
|---|---|
| `decoy validate`, `run`, `plan`, `scan`, `subset`, `tokenize`, `detokenize`, `unmask`, `report *` with `--config`, `ci check`, `explain pipeline` | Accept `.decoy`; nothing else changes |
| `decoy fmt <file>` (new) | Prints the canonical layout; `--write` rewrites the file through `_atomic`; `--check` exits 1 when the file would change |
| `decoy convert <pipeline.yaml>` (new) | Prints the `.decoy` program; `-o` writes it; refuses with exit 1 and the `ConvertError` reason |
| `decoy show pipeline <file> --yaml` (or a flag on `validate`) | Prints the compiled YAML of a `.decoy` file |
| `decoy init` | Writes `pipeline.decoy`, inferred lines marked `?`; `--yaml` keeps today's output |
| `decoy show template <name>` and `decoy init --preset` | The `.decoy` twin; `--yaml` for the YAML body |

New commands go in `src/decoy/cli/lang/_<noun>.py`, per the layout map. The twins move from
`tests/unit/lang/twins/` to `src/decoy/templates/<name>.decoy`, where `decoy.templates` serves
them; `test_twins.py` keeps proving each equals its YAML.

## Choke point and guard

The rule: every read of a user's pipeline file goes through `load_pipeline`. The existing sentry
`tests/sentry/io_policy/test_config_load_choke_point.py` already fails on a second YAML reader; it
is extended to fail on any call of `decoy.lang.compile_text` outside `_config_file`. Mutation that
must turn it red: a command that calls `compile_text` on a path itself.

The second rule: a command that takes a pipeline file accepts both kinds. Guard: the route-cell
table in `tests/sentry/defects/test_config_error_routes.py` already walks every command with a
config parameter; each cell runs once with the YAML file and once with its `.decoy` twin and
compares exit code and findings. A command added later gets both cells or fails the walk.

## Slices

| # | Slice | Frozen surface | Acceptance |
|---|---|---|---|
| S1 | `PipelineFile`, `load_pipeline`, the layer move, deletion of `lang/__main__.py` | The loader's public shape | Loader unit tests for both kinds and every error code; layer contract green |
| S2 | Gate and CI findings through `locate`; the review mark as a gate finding | Finding locations in `--json`, SARIF | A `.decoy` file with a missing namespace, an unknown strategy and a `?` gives findings on the right lines; YAML locations unchanged, by snapshot |
| S3 | Both-kinds route cells; `.decoy` twins of the e2e pipelines | None | Each pipeline command gives the same exit code and result for the twin |
| S4 | Project layout: `pipeline.decoy` in a pipeline folder, completion, `run --all` | Project layout, stored names | Layout descriptor tests; both-present refusal |
| S5 | `decoy fmt`, `decoy convert`, the compiled-YAML view | New command names | CLI surface test and regenerated `docs/cli-reference.md` |
| S6 | `decoy init` and templates write `.decoy` | Wizard output, template text | Init tests for both outputs; INIT-WIZARD owners agree the mark |
| S7 | Run record names and hashes the `.decoy` file | Stored formats | Record schema tests; an old record still reads |

S1 to S3 are the minimum for "the commands read `.decoy`". S4 to S7 can follow in any order.

## Expected size

S1: about 120 source lines in `_config_file.py`, three public names. S2: about 80 lines across
the gate and `ci/adapters.py`. S5: about 250 lines in a new `cli/lang/` package, two commands.
S6 depends on the wizard's state at the time.

## Owner questions

| # | Question | Recommendation |
|---|---|---|
| O1 | Is `decoy fmt` named `fmt` or `format`? | `fmt`, as in `go fmt` and `terraform fmt` |
| O2 | Does a run record keep the compiled YAML beside the `.decoy` hash? | Yes: it is what the engine ran, and it makes a record readable without the compiler |
| O3 | With both `pipeline.yaml` and `pipeline.decoy` in a folder, refuse or prefer `.decoy`? | Refuse; two sources of truth is the failure to avoid |
| O4 | Does `decoy init` write `.decoy` by default at 1.0? | Yes, with `--yaml` for the old output, once S1 to S3 are in |
| O5 | The guard `tests/sentry/run/test_no_subset_edit.py` fails on the compiler's `subset` block (hand-off H1) | A narrow exemption for `lang/_subset.py`: stores and dict displays only |
