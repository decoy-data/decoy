Status: current

# DECOY-LANG: plan to completion

Rules consulted: `dev-rules/README.md`, `00-universal.md`, `risk-and-exceptions.md`,
`development-loop.md`, `feature-dev.md`, `architecture.md`, `proportionality.md`,
`cross-cutting-concerns.md`, `api-and-compatibility.md`, `testing.md`, `reuse-first.md`,
`documentation.md`, `config-secrets-and-supply-chain.md`, `catalogs/recurring-defects.md`.

Risk: R2 (a new component with a compatibility surface). Gates not yet met: this plan has had no
independent plan review, and the code no independent review. Both are required before any merge
to the main branch. All work is on the branch `claude/sweet-einstein-u3104u`.

Date: 2026-11-19. Design and syntax: [2026-11-19-decoy-language.md](2026-11-19-decoy-language.md).
This page is the one place that tracks what is built and what is left.

## Where this is going

Owner decision, 2026-11-19: the Decoy language is a 1.0 focus. A `.decoy` file is the native way
to define a pipeline. A project writes and commits it, the `decoy` commands read it directly, and
`decoy init` writes it. YAML stays supported, as an input and as the compiled form the engine reads.

That makes the syntax part of what 1.0 promises, so the freeze (milestone 11) is 1.0 work too, and
the agent trial has to come before it. Roadmap row: DECOY-LANG in
[roadmap/groups/config.md](../roadmap/groups/config.md).

## Guarantee and non-goals

The change promises exactly this:

1. `compile_text(text)` returns the pipeline config for a `.decoy` program, or raises `LangError`
   with every problem found, each with a code and a source position.
2. The config has passed the engine's own validation (`parse_pipeline_config`). The compiler
   validates nothing the engine validates.
3. The same text always gives the same config, key for key and in the same key order.
4. No message quotes a value from the program: it names words of the language, strategies,
   generators, tables and columns only.
5. Each bundled template has a `.decoy` twin that compiles to the config its YAML loads to.

Non-goals: running a pipeline; checks the engine makes only at plan compile (expressions in
`where` and `name = expression`, provider names, namespace rules); any change to a `decoy`
command; any change to engine behavior; loops, functions or file access in the language.

## Design notes

| Principle | The change pain it answers | How |
|---|---|---|
| Deep module | Callers should not learn compile stages | One entry, `compile_text`; stages are private modules |
| Open/closed | The engine keeps adding strategies, generators, options and settings | Names are read from `strategy_catalog()`, `generate_option_catalog()` and the config JSON schema; the grammar has no strategy or generator names |
| One place per fact | Syntax tables drifting from tests and docs | `COLUMN_SYNTAX`, `SETTING_SYNTAX`, `BLOCK_SYNTAX` in `_lower.py` are the one list of what has syntax; the coverage test imports them |
| Single responsibility | A parser file edited for every new statement and every expression rule | Expression handling is `_expressions.py`; each statement family lowers in its own module |

Established pattern and source: a readable front-end over an existing data model with the
compiled form always available (PRQL, HCL); a language that always terminates (CUE, Dhall,
Starlark); errors mapped to the source through a source map (Elm, Rust). Section 3 of the design
page has the survey. Parsing uses Lark, which the engine already uses.

## Choke points and guards

| Rule | Enforced by construction | Guard test | Mutation shown red (head `0ba97d8` plus this change) |
|---|---|---|---|
| A compiled config is always validated by the engine, on the value-free route | `compile_text` is the only public way to a config and calls `validate` | `tests/sentry/defects/test_config_error_routes.py` (existing) flags any raw validation in `src/decoy` | Not rerun here; it flagged the first version of `_validate.py` |
| Every config field can be written | `settings { }` and `options { }` pass any field through | `tests/unit/lang/test_coverage.py` | Removing `relationships` from `BLOCK_SYNTAX` fails `test_the_options_only_list_has_not_grown` |
| The package stays self-contained | `.importlinter` places `lang` below `cli`, `ci`, `api` | `tests/unit/lang/test_package_boundary.py` | Adding `from decoy.ui import theme` to `_links.py` fails it |

## Placement

One row of the CODEMAP layout map covers the package ("Decoy language compiler").

| File | Directory | Sits beside | Present consumer |
|---|---|---|---|
| `_grammar.py`, `_parse.py`, `_expressions.py`, `_ast.py`, `_errors.py` | `src/decoy/lang/` | each other | `compile_text` |
| `_lower.py`, `_connectors.py`, `_links.py`, `_generate.py` | `src/decoy/lang/` | each other | `compile_text` |
| `_validate.py` | `src/decoy/lang/` | `_lower.py` | `compile_text` |
| `__main__.py` | `src/decoy/lang/` | `__init__.py` | `python -m decoy.lang`, the interim compile step until milestone 8 |
| `Compiled.source_map` | `src/decoy/lang/__init__.py` | | Milestone 8: commands map findings to `.decoy` lines |
| Tests | `tests/unit/lang/test_<area>.py` | | |
| Twins | `tests/unit/lang/twins/<template>.decoy` | | `test_twins.py`; they move to `src/decoy/templates/` at milestone 9, when the wizard needs them as template bodies |

Files the later milestones add, placed now so nothing moves later:

| Milestone | File | Holds |
|---|---|---|
| 3 | `src/decoy/lang/_safety.py` | Lowering of scans, `expect`, quarantine, delivery, baseline, namespaces |
| 4 | `src/decoy/lang/_subset.py` | Lowering of `subset { }` |
| 5 | `src/decoy/lang/_convert.py`, `src/decoy/lang/_print.py` | Config to syntax tree; syntax tree to text (shared with the formatter) |
| 7 | `src/decoy/lang/_format.py` | Comment-keeping formatter over `_print.py` |
| 8, 9 | `src/decoy/cli/lang/_<noun>.py` | The `decoy` command surface; `src/decoy/lang/__main__.py` is deleted then |

Expected size per milestone: 3 adds about 250 source lines and one module; 4 about 150 and one
module; 5 about 400 and two modules. `_parse.py` (about 366 lines) and `_grammar.py` grow with each
statement and stay under the 800-line cap; if `_parse.py` passes 600 it is split by statement
family (masking, generation, checks), not by line count.

## Test evidence, stated plainly

- 167 tests in `tests/unit/lang/`, all enumerated cases. None is a property test yet.
- Line and branch coverage of `src/decoy/lang/`: 98% (923 statements, 14 missed; 324 branches, 17
  partial), measured with `pytest --cov=decoy.lang --cov-branch`.
- No mutation score has been measured. The two guard mutations above are the only mutations run.
- One test runs a compiled foreign key through the engine and checks the join.
- The round-trip property test arrives with milestone 5 and needs Hypothesis, which is not in the
  dev lock (decision E6).
- The full repository suite has not been run on this head. The last full `tests/sentry` run was
  before the cleanup in this change; since then only the language tests and the layout, config
  route, engine boundary, source hygiene and config-load guards were rerun.

## Built

| Area | State |
|---|---|
| Pipeline: `decoy 1`, `pipeline`, `seed`, `secret ref`, `unconfigured columns`, `let` | Built |
| Sources and targets: `csv`, `parquet`, `fixed_width`, `s3`, `gcs` | Built |
| Masking: `column : strategy(...)`, `in`, `deterministic`, `vaulted`, `when`, `keep` | Built |
| Table shaping: `where`, `name = expression`, `sort by`, `limit`, `dedupe`, `drop` | Built |
| Joins: `<-` foreign keys, composite keys, `orphans`, `{a, b} : rule` groups | Built |
| Generation: `generate` blocks, generator calls, expressions, `<-`, `unique` | Built |
| Errors on source lines, never quoting a config value | Built |
| All 11 bundled templates have a `.decoy` twin that compiles to the same config | Built |
| `python -m decoy.lang file.decoy` prints the pipeline YAML | Built; interim until the commands read `.decoy` |
| `settings { }` for any pipeline setting; `options { }` escape hatch for any config block | Built |
| Coverage test against the engine's config schema (`tests/unit/lang/test_coverage.py`); nine blocks are `options`-only | Built |

## Milestones

Each milestone ends with tests that pass and this table updated. The order puts the proof (the
agent trial) before the expensive tooling, so the code-first decision rests on evidence early.

| # | Milestone | What it delivers | Done when | Touches frozen 1.0 code |
|---|---|---|---|---|
| 1 | **Coverage test** (built) | A test that reads the engine's config schema and lists every field the language cannot write with its own syntax. The list may only shrink. | The test is green and fails when the engine adds a field | No |
| 2 | **Nothing locked out** (built) | `settings { }` for every pipeline setting; `options { }` as the escape hatch for any config block without syntax yet | Every `PipelineConfig` field can be written, by syntax or by `options` | No |
| 3 | **Checks and safety** | Syntax for scans (before and after), `expect` checks, quarantine, delivery mode, the scan baseline, the `namespaces` block | Those blocks leave the `options`-only list | No |
| 4 | **Subsetting** | A `subset { }` block: start tables, what to follow, row budgets | `subset` leaves the `options`-only list | No |
| 5 | **Converter** | Any pipeline YAML to `.decoy` text; round-trip test (config to `.decoy` to config gives the same config) over the templates and generated configs | The 11 twins are produced by the converter; the round-trip test is green | No |
| 6 | **Agent card and agent trial** | One page holding the whole language, sized for a prompt. Twenty pipeline tasks attempted by an agent in YAML and in `.decoy`; the share that validate first time | The trial has a result; the syntax is revised where agents stumble | No |
| 7 | **Formatter** | One canonical layout, comments kept | Formatting twice changes nothing; no comment is lost | Adds a command |
| 8 | **Commands read `.decoy`** | `decoy validate`, `decoy run` and the other pipeline commands take a `.decoy` file; findings point at `.decoy` lines | The command tests pass for `.decoy` input on every pipeline command | Yes |
| 9 | **Wizard writes `.decoy`** | `decoy init` output in the language, with the review marker | Init tests pass for both outputs | Yes |
| 10 | **Docs** | Quickstart, tour, reference generated from the engine catalogs, cookbook, YAML side by side, error index | Published with the docs site | Docs only |
| 11 | **Freeze** | Syntax review, reserved-word list final, compatibility rule for `decoy 1`, editor highlighting | The language joins the compatibility contract | Contract |
| 12 | **Policy and disguises** | `use <disguise>`, `match ... =>`, `forbid` | Compiles to the engine's `policy` block | Waits on the CLI |

Notes on the order:

- **2 before 3 and 4.** The escape hatch makes the language complete at once. Dedicated syntax
  then replaces `options` one block at a time, and the coverage test counts down.
- **5 before 6.** The converter produces the YAML and `.decoy` task pairs the trial needs, and it
  is how existing users move.
- **12 is last because it is blocked.** The engine has the `policy` block, but the CLI does not
  read it yet (it is not a `PipelineConfig` field; it is expanded before validation). Language
  syntax follows the CLI roadmap rows that add it (F16).

## Order for 1.0

| Step | Milestones | Why here |
|---|---|---|
| 1 | 3, 4 | Finish the syntax inside the package; no command changes |
| 2 | 5 | The converter gives existing pipelines a way in and supplies the trial's task pairs |
| 3 | 6 | Evidence on the syntax before anything public depends on it |
| 4 | 8 | The commands read `.decoy`. This changes frozen 1.0 code, so it gets its own plan and review before building |
| 5 | 7, 9 | The formatter and the wizard output build on the commands |
| 6 | 10, 11 | Docs, then the freeze |
| After 1.0 | 12 | Needs the CLI to read the `policy` block first |

## Working rules

1. No change to engine behavior. If the compiler needs an engine fact that is private, that is a
   small read-only accessor in the engine, as its own change.
2. A change to a `decoy` command, its output, exit codes or stored formats (milestones 7 to 9)
   starts from its own reviewed plan.
3. The compiler holds no list of strategies, generators, options or config fields. It reads the
   engine's catalogs and schema.
4. Every construct has a test that compiles it and, where the engine can run it cheaply, a test
   that runs it.
5. Errors carry positions and never the source line or a config value.
6. A syntax change updates the twins, the tests, this page and the design page in one commit.

## Owner decisions

| # | Decision | Needed for | Recommendation |
|---|---|---|---|
| E1 | Is the language experimental in 1.0 | | **Decided 2026-11-19:** no. It is a 1.0 focus and the native pipeline definition |
| E2 | How an experimental command is offered | | Not needed after E1 |
| E3 | Do `decoy validate` and `decoy run` read `.decoy` in 1.0 | Milestone 8 | **Decided 2026-11-19:** yes |
| E4 | Review marker: an inferred line ends with `?` and `decoy run` refuses until it is cleared | Milestone 9 | **Decided 2026-11-19:** yes |
| E5 | The `lark` dependency and the lock | Any merge | **Approved 2026-11-19 and done:** `scripts/dev/lock.sh` rewrote `requirements-dev.lock` (the only change is that `lark` is now also listed as required by the CLI) and `lock.sh --check` passes |
| E6 | Add Hypothesis to the dev dependencies for the round-trip property test | Milestone 5 | Yes; the testing rules ask for property tests on round-trip claims |
| E7 | Where the compiler lives long term. It is self-contained in the CLI package today. If the platform or another tool must read `.decoy`, it should not depend on the CLI | Before milestone 8 | Keep it in the CLI for 1.0; the boundary test keeps a later move to its own package a file move |

## Open items

- The reason-code scan also flags `_resources.py` and `ci/rule_codes.py` when run against the local
  engine checkout (0.28.0). Those files are not part of this work; cause not investigated.
- Mistakes inside `where` and `name = expression` are found by the engine only at plan compile,
  which the compiler does not run. Milestone 8 closes this, because the commands do run it.
