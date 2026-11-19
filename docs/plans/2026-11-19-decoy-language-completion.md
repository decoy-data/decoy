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
| 5 | `src/decoy/lang/_convert.py`, `src/decoy/lang/_print.py` (built) | Config to syntax tree; syntax tree to text (shared with the formatter) |
| 7 | `src/decoy/lang/_format.py` | Comment-keeping formatter over `_print.py` |
| 8, 9 | `src/decoy/cli/lang/_<noun>.py` | The `decoy` command surface; `src/decoy/lang/__main__.py` is deleted then |

Expected size per milestone: 3 adds about 250 source lines and one module; 4 about 150 and one
module; 5 about 400 and two modules. `_parse.py` (about 366 lines) and `_grammar.py` grow with each
statement and stay under the 800-line cap; if `_parse.py` passes 600 it is split by statement
family (masking, generation, checks), not by line count.

## Test evidence, stated plainly

- 424 tests in `tests/unit/lang/`: enumerated cases plus two property tests.
- Line and branch coverage of `src/decoy/lang/`: 97% (1819 statements, 44 missed; 692 branches, 34
  partial), measured with `pytest --cov=decoy.lang --cov-branch`.
- No mutation score has been measured. The two guard mutations above are the only mutations run.
- One test runs a compiled foreign key through the engine and checks the join.
- Two Hypothesis property tests (`test_roundtrip.py`, 200 generated configs each, derandomized):
  a valid config converts and compiles back to the same engine model, compared type-strictly, and
  printing is a fixed point. The generator covers rules with options of every value type, option
  keys that are words of the language, conditions, shaping, one foreign key, a generated table,
  settings, a subset seed and three checks. It does not generate coherent groups, composite keys
  or a column with a link and a rule; those have enumerated cases. Mutation shown red: with the
  converter's own check off and `when` dropped, the first property test fails.
- Respacing an expression: one engine run with `when` and `where` written tight and spaced gave
  identical masked output (40 rows, `hash` and `faker` columns). One experiment, not a proof.
- `test_convert.py` converts every valid pipeline YAML in this repository (one listed refusal).
  Run by hand over both repositories: 20 of 22 convert.
  The two refusals are right: one declares a relationship with no namespace (a QA fixture for
  that failure), one uses strategy names the engine no longer has
  (`decoy-engine/examples/complex_healthcare_claims.yaml`, which is stale).
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
| Coverage test against the engine's config schema (`tests/unit/lang/test_coverage.py`); one block is `options`-only, on purpose (`protected_quarantine`) | Built |
| Subsetting: `subset { start ... follow ... budget(...) allow dangling }` | Built |
| Checks and safety: `scan before/after`, `expect`, `quarantine`, `baseline`, `delivery`, `namespace ... for` | Built |

## Milestones

Each milestone ends with tests that pass and this table updated. The order puts the proof (the
agent trial) before the expensive tooling, so the code-first decision rests on evidence early.

| # | Milestone | What it delivers | Done when | Touches frozen 1.0 code |
|---|---|---|---|---|
| 1 | **Coverage test** (built) | A test that reads the engine's config schema and lists every field the language cannot write with its own syntax. The list may only shrink. | The test is green and fails when the engine adds a field | No |
| 2 | **Nothing locked out** (built) | `settings { }` for every pipeline setting; `options { }` as the escape hatch for any config block without syntax yet | Every `PipelineConfig` field can be written, by syntax or by `options` | No |
| 3 | **Checks and safety** (built) | Syntax for scans (before and after), `expect` checks, quarantine, delivery mode, the scan baseline, the `namespaces` block | Those blocks leave the `options`-only list | No |
| 4 | **Subsetting** (built) | A `subset { }` block: start tables, what to follow, row budgets | `subset` leaves the `options`-only list | No |
| 5 | **Converter** (built) | Any pipeline YAML to `.decoy` text; round-trip test (config to `.decoy` to config gives the same config) over the templates and generated configs | The 11 twins are produced by the converter; the round-trip test is green | No |
| 6 | **Agent card and agent trial** (done; the trial did not show a validity gap) | One page holding the whole language, sized for a prompt. Twenty pipeline tasks attempted by an agent in YAML and in `.decoy`; the share that validate first time | The trial has a result; the syntax is revised where agents stumble | No |
| 7 | **Formatter** (library and interim entry built; the `decoy` command is hand-off H8) | One canonical layout, comments kept | Formatting twice changes nothing; no comment is lost | Adds a command |
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

## Milestone 5 plan: converter and printer

Behavior. `convert_config(config)` returns `.decoy` text for a pipeline config. `print_program`
writes a syntax tree as text in the one canonical layout; the converter builds a tree and prints
it, and the formatter (milestone 7) will print the tree it parsed, so there is one layout.

Guarantee. The text the converter returns compiles to the same pipeline: the engine's model of the
compiled config equals the engine's model of the input (`parse_pipeline_config(...).model_dump()`),
with expression strings compared after canonical spacing. The converter checks this itself before
returning and refuses with `ConvertError` otherwise. It never returns text that means something
else.

Failure modes, all refused with `ConvertError` naming the config path, never a value:

| Case | Why it cannot be written |
|---|---|
| The input does not validate | Nothing to preserve |
| A table with no target, or a source or target for a table that is not declared | `mask` and `generate` carry both |
| A `null` or non-finite number where a value is written | The language has no spelling for it |
| `coherent_with` that is not one symmetric group with one shared rule | `{a, b} : rule` states exactly that |
| A relationship whose order cannot be reproduced from the table order | Links are written in the child table |
| `quarantine` with `enabled: false`, a namespace with no columns | The statement form implies the other case |

Acceptance tests. (1) All 11 template twins are the converter's output, byte for byte. (2) Each
language construct round-trips from a config written by hand. (3) A Hypothesis property test:
generated valid configs convert and compile back to an equal model. (4) Every `ConvertError` case
above. (5) A corpus run over every pipeline YAML in both repositories reports how many convert.

Placement: `src/decoy/lang/_print.py` (tree to text), `src/decoy/lang/_convert.py` (config to
tree, and the faithfulness check); tests `tests/unit/lang/test_print.py`, `test_convert.py`,
`test_roundtrip.py`. Expected size: about 500 source lines in the two modules, two public names
(`convert_config`, `ConvertError`).

## Milestone 7 plan: formatter

Behavior. `format_text(text)` returns the program in the canonical layout with its comments.
A comment belongs to the statement it shares a line with, else to the next statement in the same
block, else it stays at the end of that block; comments before `decoy 1` and after the last `}`
stay there. One blank line between statements is kept where the source had one.

Guarantee. The result parses to the same program and holds every comment; `format_text` checks
both before returning and raises `lang.format` otherwise. Formatting a formatted file changes
nothing.

Known limits: sections are printed in a set order, so a comment between two sections travels with
the statement after it; a comment after a block's `}` on the same line moves to that block's
opening line; blank lines inside `settings { }` and `options { }` are not kept.

Acceptance tests (`test_format.py`): a worked example, exact; every twin unchanged; a property
test that puts comments at random places in a twin and checks that all are kept, the lowered
config is equal and a second pass changes nothing.

Placement: `src/decoy/lang/_format.py` (comment placement and the checks); `Notes` in `_print.py`.

## Choices made without asking

The owner asked (2026-11-19) for recommended choices to be taken and recorded here for review.

| # | Choice | Alternative | Why |
|---|---|---|---|
| C1 | Hypothesis is added to the dev dependencies and the lock regenerated (decision E6) | Enumerated round-trip cases only | The testing rules ask for property tests on round-trip claims |
| C2 | A child key column may have both a link and a rule (`id <- t.id ...` and `id : hash in ns`) | Refuse it, as before | Existing YAML declares the child's own rule beside the relationship (engine recipe (b)); without this it cannot be written |
| C3 | The converter refuses rather than approximates | Emit the nearest program with a warning | A converted pipeline that masks differently is a data-safety defect |
| C4 | The printer aligns `:` and `=` within a run of single-line rules | No alignment | It is how the hand-written twins read; one layout rule, applied by the tool |
| C6 | The formatter keeps a single blank line the author left between statements | One fixed layout with no blank lines inside a block | It is what gofmt and Black do, and it keeps a file's own grouping |
| C7 | The formatter orders pipeline-level sections (settings, `let`, subset, checks, tables, options) | Keep the author's order | One layout; order between sections has no meaning in the language |
| C5 | An independent review is run by a separate agent at milestone boundaries | Wait for the repository's named reviewers | They are not available in this session; findings and verdicts are recorded below |

## Reviews

| Date | Scope | Reviewer | Verdict | Outcome |
|---|---|---|---|---|
| 2026-11-19 | `src/decoy/lang/` and its tests at `20bdc9b` (before the converter) | A separate agent, given the code and the review rulebooks, not the author's conclusions | NO-GO, 12 findings | All fixed in the two commits after it, each with a test; see below |
| 2026-11-19 | The change `20bdc9b..0550214`: converter, printer, and the fixes above | A second separate agent | NO-GO for the converter (8 findings); GO for the earlier fixes, which it re-ran | All fixed, each with a test; see below. The fixes themselves are not yet re-reviewed |

Findings of the first review and what was done:

| # | Finding | Fix |
|---|---|---|
| 1 | Crash (`KeyError`) when a link points at a generated table | Links read generated columns too; a masked table can follow a generated key |
| 2 | Quoted text was decoded with Python's literal rules: bad escapes crashed, `"C:\temp"` became a tab | The language has its own rules: JSON escapes in double quotes, literal text in single quotes, an error with a hint otherwise |
| 3 | Deep nesting raised `RecursionError` | Reported as `lang.nesting` |
| 4 | A `let` naming another `let` compiled to the inner name as a strategy | A `let` is resolved when defined; an unknown name is an error on the `let` line |
| 5 | A misspelled generator became a computed column | A call close to a generator name, or a generator with computed arguments, is an error |
| 6 | Repeated connector options, `budget` and `follow` kept the last one silently | Each is an error; a connector's own format cannot be overridden |
| 7 | Syntax errors could show a bare word, a map key or the version number | Only words of the language and punctuation are shown |
| 8 | A chained composite link took the namespace of the wrong key column | It follows its own position in the key |
| 9 | Link problems were hidden when a table had another problem | Reported together |
| 10 | The parser produced engine shapes; shared helpers sat in unrelated modules; parallel tables | Syntax nodes for table shaping, `_tokens.py`, `plain` in `_ast.py`, `SourceMap` in `_errors.py`, one settings table, a coverage test for connectors |
| 11 | `decoy 1.0` accepted; no exponent numbers; reserved words missing from the docstring | Fixed. Not changed: inside a condition true and false are the engine's `True` and `False` (the hint says so); a quoted table name with a dot sends an engine error to the pipeline line |
| 12 | Twins compared with `==` only; missing tests | Type-strict comparison; tests for every finding above |

Still open from the first review: `Compiled.source_map` has no consumer until milestone 8, and
the coverage tests prove a field is passed through, not that the engine accepts a sample value
for it.

Findings of the second review (the converter and printer) and what was done:

| # | Finding | Fix |
|---|---|---|
| 1 | Adjacent columns were merged when their rules were equal to Python but not to the engine (`1`, `True`, `1.0`), and the faithfulness check could not see it | Rules and models are compared type-strictly |
| 2 | Option keys that are words of the language were printed in a form the grammar does not read, so a column with `unique: true` could not be converted | Keys are written bare where the grammar reads them bare and in single quotes otherwise; a test tries every word of the language in every place |
| 3 | Crashes on valid configs: a null block, a number written as text, a sort with the wrong number of directions | The converter works from the engine's own dump of what the config sets, so types are the engine's; the sort case is a refusal |
| 4 | A refusal could name a map key from the config | Paths stop at the option |
| 5 | The property test compared a few fields loosely and its generator was narrow | Full model, type-strict; wider generator; mutation shown red |
| 6 | Refusals with no reason; the engine's full dump of a config was refused | The compiler's reason is included; unset and null fields are dropped |
| 7 | Text rules differ inside expressions | Documented: an expression goes to the engine as written |
| 8 | An over-large number read as infinity; a surrogate pair gave two half characters; duplicated word pattern | A number must be finite; pairs are joined; the pattern is defined once |

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

## Agent trial result

Record: [../records/2026-11-19-decoy-language-agent-trial.md](../records/2026-11-19-decoy-language-agent-trial.md).
Twenty tasks, one agent per format, closed-book and first-attempt. Both formats: 20 of 20 files
valid. Doing what the task asked: 20 of 20 in `.decoy`, 19 of 20 in YAML. The `.decoy` files were
243 lines against 678, written from a one-page reference against 220 KB of YAML documentation.

The bar this milestone set, "more often valid in `.decoy`", is not met as worded: there is no
validity gap for a capable agent with the full documentation. What the trial supports is the same
correctness from a much smaller reference in about a third of the lines. One run, one model; the
record lists the limits and what a harder trial would change.

## Hand-off to the main orchestration

Items this branch cannot settle on its own. Each needs the owner or the orchestrating session.

| # | Item | State on the branch | What is needed |
|---|---|---|---|
| H1 | `tests/sentry/run/test_no_subset_edit.py` fails. The guard forbids any code under `src/decoy` from writing a config's `subset` key, so that the CLI never edits a user's config. `src/decoy/lang/_subset.py` writes that block because it builds a config from a `.decoy` program | **Red.** The guard was not changed and not sidestepped | A decision: a narrow exemption for the compiler (a store and a dict display in `lang/_subset.py` only; `pop`, `update` and `del` stay forbidden), or another design |
| H2 | Guard and registry files changed for the new package: `.importlinter` and its snapshot in `tests/sentry/layout/test_import_layers.py` (the `lang` layer), `tests/sentry/layout/test_codemap_paths.py` (one new layout kind) | Green | Confirm the placement |
| H3 | `pyproject.toml` declares `lark>=1.1` and, for tests, `hypothesis>=6.0`; `requirements-dev.lock` regenerated with `scripts/dev/lock.sh` | `lock.sh --check` passes | Confirm; owner approved `lark` on 2026-11-19, `hypothesis` is choice C1 |
| H4 | Roadmap row DECOY-LANG, the decisions log entry and the removed inbox line | Written | Confirm the row text and state |
| H5 | `tests/sentry/test_engine_reason_code_copies.py` flags `_resources.py` and `ci/rule_codes.py` against the local engine checkout (0.28.0; the CLI pins 0.27.0) | Red, in files this work does not touch; cause not investigated | Someone who owns those files |
| H6 | Engine follow-ups: a public list of validator names (so `expect` can check them); `examples/complex_healthcare_claims.yaml` uses strategy names the engine no longer has; the orphan-remap observation in the roadmap inbox | Recorded | Triage in the engine |
| H7 | Independent review of the fixes to the second review's findings | Not reviewed | A review before merge |
| H8 | Milestones 7 to 9 change `decoy` commands and frozen 1.0 surfaces | Not started; each gets its own plan | Plan review, then build |

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
- The engine has no public list of validator names, so `expect lunh(...)` compiles and is refused
  at run. A read-only accessor in the engine would let the compiler check the name and suggest
  the nearest one, as it does for strategies and generators.
- Mistakes inside `where` and `name = expression` are found by the engine only at plan compile,
  which the compiler does not run. Milestone 8 closes this, because the commands do run it.
