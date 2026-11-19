Status: current

# DECOY-LANG: plan to completion

Date: 2026-11-19. Design and syntax: [2026-11-19-decoy-language.md](2026-11-19-decoy-language.md).
This page is the one place that tracks what is built and what is left.

## Where this is going

After 1.0, pipelines are code first: a project writes and commits a `.decoy` file, and `decoy init`
is the quick route for simple pipelines. YAML stays as the compiled form the engine reads and as a
supported input.

The aim for the 1.0 launch is to have as much of that finished as possible **without changing
anything 1.0 has frozen**. Everything up to milestone 6 lives inside `src/decoy/lang/` and its
tests, so it can be built now and ship in the 1.0 wheel as an experimental feature. Milestone 7
onward changes `decoy` commands, and waits for the owner decisions at the end of this page.

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
| `python -m decoy.lang file.decoy` prints the pipeline YAML | Built, experimental |

## Milestones

Each milestone ends with tests that pass and this table updated. The order puts the proof (the
agent trial) before the expensive tooling, so the code-first decision rests on evidence early.

| # | Milestone | What it delivers | Done when | Touches frozen 1.0 code |
|---|---|---|---|---|
| 1 | **Coverage test** | A test that reads the engine's config schema and lists every field the language cannot write with its own syntax. The list may only shrink. | The test is green and fails when the engine adds a field | No |
| 2 | **Nothing locked out** | `settings { }` for every pipeline setting; `options { }` as the escape hatch for any config block without syntax yet | Every `PipelineConfig` field can be written, by syntax or by `options` | No |
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

## What can be finished by the 1.0 launch

| Group | Milestones | Needs |
|---|---|---|
| Can be complete at launch, shipped experimental | 1 to 6, and 10 as draft pages | Decision E1 |
| Can be built before launch, but changes a command | 7, 8, 9 | Decisions E2 and E3 |
| After launch | 11 (needs the trial result and real use), 12 (needs CLI policy support) | |

## Working rules

1. No change to engine behavior. If the compiler needs an engine fact that is private, that is a
   small read-only accessor in the engine, as its own change.
2. No change to a `decoy` command, its output, exit codes or stored formats until the decision
   that covers it is made.
3. The compiler holds no list of strategies, generators, options or config fields. It reads the
   engine's catalogs and schema.
4. Every construct has a test that compiles it and, where the engine can run it cheaply, a test
   that runs it.
5. Errors carry positions and never the source line or a config value.
6. A syntax change updates the twins, the tests, this page and the design page in one commit.

## Owner decisions

| # | Decision | Needed for | Recommendation |
|---|---|---|---|
| E1 | List the Decoy language in the experimental tier for 1.0 (roadmap row EXPERIMENTAL-TIER): it ships and works, and its syntax may change in a 1.x minor | Shipping milestones 1 to 6 in the 1.0 wheel | Yes |
| E2 | How an experimental command is offered: a normal command with an "experimental" label, or behind an environment switch | Milestones 7 and 8 before launch | Label, no switch: one fewer thing to explain |
| E3 | Whether `decoy validate` and `decoy run` accept `.decoy` in 1.0, or the separate compile step is the 1.0 form | Milestone 8 before launch | Compile step for 1.0; direct reading in the first 1.x minor |
| E4 | Review marker: an inferred line ends with `?` and `decoy run` refuses until it is cleared | Milestone 9 | Yes |
| E5 | Whether the `lark` dependency, now declared directly, needs the lock files regenerated before release | Any release that includes `decoy.lang` | Regenerate with the next lock update |

## Open items

- `tests/sentry/allowlist-before.json` and the engine-reason-code allowlist each gained one entry
  for the config key `row_count` in `lang/_generate.py`. The allowlist is meant to shrink; a
  maintainer should confirm the entry or ask for the key to be avoided.
- The reason-code scan also flags `_resources.py` and `ci/rule_codes.py` when run against the local
  engine checkout (0.28.0). Those files are not part of this work; cause not investigated.
- Mistakes inside `where` and `name = expression` are found by the engine only at plan compile,
  which the compiler does not run. Milestone 8 closes this, because the commands do run it.
