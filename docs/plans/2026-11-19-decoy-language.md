Status: draft

# DECOY-LANG: a small language for writing Decoy pipelines

Date: 2026-11-19. Scope: CLI repo only. No engine behavior changes. Not a 1.0 blocker.

This is the broad plan. It says what the language covers, how it should read, how the compiler
works, and the order to build it in. Each group in section 4 gets its own short design pass before
it is built. Groups A, B and D are decided and built (section 12 and the
[syntax trial](2026-11-19-decoy-language-syntax-trial.md)); syntax shown for the other groups is the
leading candidate until that group's design pass.

Working name: Decoy language. Working file extension: `.decoy`.

## 1. Goal

A pipeline file that is easier to write, read and review than hand-edited YAML, for people and for
coding agents.

- `decoy init` stays the main way in. It scaffolds the common case.
- The language is for everything the wizard cannot sensibly prompt for: relationships, coherent
  groups, generation, policy rules, subsetting, checks.
- YAML keeps working forever. A `.decoy` file compiles to exactly the config the engine already
  accepts.

Three promises:

1. **Anything YAML can say, the language can say.** Nothing is locked out.
2. **A `.decoy` file never means something the YAML cannot.** The compiled YAML is always
   available to read, diff and audit.
3. **A person who knows any mainstream language can read a pipeline on first sight** and write one
   after a ten-minute tour.

Not goals:

- Not a general-purpose language. No loops, no user-defined functions, no file or network access.
  Every program finishes and gives the same result every time.
- Not a replacement for CLI commands. `scan`, `fit`, `run`, `unmask`, `tokenize`, `report` stay
  commands. The language describes a pipeline; commands act on it.
- Not a second engine. No masking, generation or validation logic lives in the compiler.

## 2. How it fits

```
decoy init (wizard)  ──writes──▶  pipeline.decoy  ◀──hand edits── people and agents
                                        │
                                  decoy compiler (CLI repo)
                                        │
                                        ▼
                          config dict, same shape as pipeline.yaml
                                        │
                     PipelineConfig.model_validate → compile_plan → run_pipeline
                                  (engine, unchanged)
```

The config dict is the hand-off point. The engine never learns the language exists, which keeps
the rule that library code does not know its callers.

## 3. Prior art

Per the "use established methodology" rule, the design borrows from tools that solved the same
problem, and the implementing modules will cite them.

| Tool | What we take from it |
|---|---|
| HCL (Terraform) | Named blocks with braces; a config language that compiles to a plain data model |
| PRQL | A readable front-end that compiles to an existing back-end language (SQL) and can always show the output |
| CUE, Dhall, Starlark | Deliberately not Turing-complete: programs always finish and are deterministic |
| dbt | `ref`-style links between tables; project files reviewed in pull requests |
| gofmt, Black | One canonical layout, applied by a formatter |
| Rust and Elm compilers | Error messages that point at the source line and suggest the fix |
| Lark | The parser library; the engine already uses it for expressions (`expressions/grammar.lark`) |

## 4. What the engine does, by group

Every engine capability is reached through one validated object, `PipelineConfig`. The groups
below cover all of it. Each group lists what the engine does today, where it lives in YAML, and how
the language would say it. Counts come from the engine's generated capability matrix
(`decoy-engine/docs/capability-matrix.md`).

### Group A: Pipeline and settings

**Engine:** `version`, `name`, and `global_settings`: the seed, the mask secret reference, the
pool-exhaustion policy, the unconfigured-column policy, warning thresholds, differential-privacy
settings for generation, a reference date.

**Language:** one `pipeline` block. Settings are plain statements inside it.

```
decoy 1

pipeline claims_demo {
  seed 42
  secret ref("mask-key")
  unconfigured columns error
}
```

`decoy 1` on the first line is the language version, so the syntax can change later without
guessing which version a file uses.

### Group B: Sources and targets

**Engine:** per-table sources and targets. Files (csv, parquet, fixed-width), S3 and GCS, with CSV
dialect options, fixed-width layouts and an opaque `credentials_ref`. The CLI adds DuckDB sources.

**Language:** `from` and `to` on the table itself, written as calls. This removes the two separate
`sources:` and `targets:` blocks keyed by table name.

```
table patients
  from csv("in/patients.csv", delimiter: "|")
  to   parquet("out/patients.parquet")
{ ... }

table claims from s3("acme-landing", "claims/2026-06.parquet", credentials: "phi-readonly") { ... }
```

### Group C: Table shaping

**Engine:** six transforms that run before masking: `filter`, `sort`, `limit`, `dedupe`, `derive`,
`drop_column` (at most 32 per table).

**Language:** SQL-flavored statements, run in the order written.

```
where  status != 'TEST' and age >= 18
full_name = first_name + ' ' + last_name
sort by signup_date desc
limit 5_000_000
dedupe on (member_id)
drop internal_notes
```

### Group D: Masking

**Engine:** 24 mask strategies (`faker`, `fpe`, `hash`, `tokenize`, `redact`, `date_shift`,
`bucketize`, `bucket_perturb`, `top_code`, `truncate`, `shuffle`, `categorical`, `geo_generalize`,
`code_set`, `text_mask`, `text_redact`, `joint_mask`, `formula`, `derived`, `derived_aggregate`,
`group_key`, `grouped_series`, `windowed_date`, `passthrough`), 34 synthetic providers, and
per-column settings: `namespace`, `deterministic`, `vault`, `when`, `cardinality_mode`,
`allow_collisions`, declared casting.

**Language:** one line per rule: the column names, a colon, then the strategy as a call. Settings
that today sit beside the strategy become short trailing words. `keep` leaves columns unchanged.

```
email     : faker(person_email)
ssn       : fpe(charset: digits) in ssn_space
zip       : geo_generalize(type: zip, k_threshold: 20000)
dob, admitted : date_shift(min_days: -30, max_days: 30) in patient_dates
account   : faker(synthetic_account_number) vaulted
diagnosis : code_set(icd10, chapter_preserve: true) when region == 'US'
keep visit_count, status
```

Strategy names are not keywords. The compiler checks each name and its options against the engine's
live catalog (`strategy_catalog()`), so a new engine strategy works with no grammar change.

### Group E: Identity and joins

**Engine:** namespaces (two columns in one namespace mask to the same value), relationships
(parent, children, composite keys, orphan policy: preserve, remap, warn, fail), `from_parent`
columns, coherent groups (`coherent_with`), the token vault.

This is where YAML is hardest to write, because one idea is spread across three blocks.

**Language:** the idea is written once, where it applies.

```
link member_id to members.member_id                 # foreign key: child takes the parent's masked value
link (member_id, plan_id) to enrollments.(member_id, plan_id) orphans fail
mask {first_name, last_name, email} with faker(composite_name_email)   # stays consistent within a row
```

- `link` creates the relationship entry and the `from_parent` column together.
- Braces mark a coherent group; the compiler writes `coherent_with` on each member.
- A namespace exists once any column says `in <name>`. No separate declaration block.

### Group F: Generation

**Engine:** generate-kind tables with `row_count`, `unique_together` and 14 column types
(`sequence`, `faker`, `categorical`, `reference`, `formula`, `derived`, `derived_aggregate`,
`grouped_series`, `windowed_date`, `group_key`, `constant`, `distribution`, `lookup`,
`statistical`). Options are checked per type by the engine's registry.

**Language:** a `generate` block. Columns are defined with `name = generator(...)`.

```
generate customers rows 1000 to csv("out/customers.csv") {
  customer_id  = sequence(start: 10000)
  first_name   = faker(first_name)
  loyalty_tier = categorical { "None": 0.6, "Silver": 0.3, "Gold": 0.1 }
}

generate orders rows 3000 {
  order_id    = sequence(start: 1)
  customer_id = ref customers.customer_id
  label       = concat(status, ':', order_id)      # an expression, not a quoted string
  unique (customer_id, ordered_on)
}
```

The rule to remember: **`:` masks a column that exists, `=` defines a new one.** In a masked
table, `name = expression` adds a column from an expression (the `derive` transform), so there is
no separate `derive` word. A generator inside a masked
table is a compile error, because the engine keeps mask tables and generate tables separate; if
the engine later allows mixed tables, the same syntax starts working.

### Group G: Expressions

**Engine:** a closed expression grammar used by `filter`, `derive`, `when`, `formula`, `derived`:
arithmetic, comparisons, `and`/`or`/`not`, `concat`, `slice`, `days_between`, `if`, `case_when`. It
is a security boundary: nothing outside the list parses.

**Language:** the same expressions, written inline without quotes. The compiler reuses the engine
grammar rather than defining a second one, so the security boundary stays in one place.

### Group H: Policy and disguises

**Engine:** 10 disguises (HIPAA, GDPR, PCI, CCPA and others) that can be pinned by id and date;
policy rules that pick columns by table, column, classification, tag, logical type or role;
prohibitions (`forbid`, `require`); a default decision.

**Language:** rules read as rules.

```
use hipaa@2026-06-28

policy {
  match classification email  => faker(person_email)      because "contact data"
  match tag free_text         => text_redact()
  forbid passthrough on classification ssn
  default redact
}
```

### Group I: Subsetting

**Engine:** seed tables (sample, filter or explicit keys), row budgets, per-relationship edge
directions, a dangling-reference switch.

**Language:**

```
subset {
  start members sample 5%
  start claims where paid_amount > 10000
  follow claims -> members upward
  budget 2_000_000 rows
}
```

### Group J: Checks and safety

**Engine:** pre-scan and post-scan (regex and NER detectors, dismissals, distribution checks),
validators (leak check, FK checks), quarantine, protected quarantine, delivery mode (strict or
best effort), scan baseline.

**Language:** `expect` statements for checks, small blocks for the rest.

```
scan before with regex, ner
expect no_leaks(exempt: [state])
expect joins claims.member_id -> members.member_id
quarantine to "out/quarantine/" on [parse_error]
delivery strict
```

### Outside the language

- Run-time switches (`substrate`, chunking, worker counts) stay CLI flags. They change how a run
  executes, not what the pipeline means.
- `fit` snapshots, the vault, reports and evidence stay CLI commands.

### The escape hatch

Any block accepts `options { key: value }` for settings without dedicated syntax yet, and
`raw yaml { ... }` can carry a whole config block. A gap in the language slows nobody down; it only
reads less nicely until syntax is added.

## 5. How it should read

The words come from languages people already know.

| Idea | Word in the language | Where people know it from |
|---|---|---|
| Name a reusable value | `let` | JavaScript, Rust, Swift |
| Read and write data | `from`, `to` | SQL, plain English |
| Filter rows | `where` | SQL |
| Sort, limit | `sort by`, `limit` | SQL |
| Call something with options | `name(arg, key: value)` | Python, Swift, Kotlin |
| Link to another table | `table.column` | SQL |
| Bring in a rule pack | `use` | Rust, PHP |
| Condition | `when`, `if` | SQL, Ruby |
| Rule matching | `match … =>` | Rust, Scala |
| Assertion | `expect` | Jest, RSpec |
| Comment | `# …` | Python, shell, YAML |
| Lists and maps | `[a, b]`, `{k: v}` | JSON, Python |
| Big numbers | `5_000_000` | Python, Rust |

Writing rules:

1. **One way to say each thing.** No aliases, no optional punctuation.
2. **Braces, not indentation.** Spaces and line breaks only separate words, as in JSON or C, so
   nothing depends on layout; one rule per line is the convention the formatter applies.
   Indentation mistakes are the most common YAML failure for people and agents alike. Inside a
   table four words are reserved (`keep`, `in`, `deterministic`, `vaulted`); a column with one of
   those names, or with a space in it, is written in backticks.
3. **Things live where they apply.** A table's source sits on the table. A foreign key sits on the
   child column.
4. **Defaults are silent, overrides are visible.** A minimal pipeline is a few lines.
5. **Reads aloud.** "ssn: fpe with charset digits, in ssn_space."
6. **Every error names the line, says what is wrong and suggests the fix.**
7. **Order in the file does not matter** between blocks. Inside a table, transforms and generated
   columns run in the order written, as they do today.

The smallest complete program (recipe (a) in the engine docs, about twice as long in YAML):

```
decoy 1

pipeline people {
  seed 42

  table people from csv("people.csv") to csv("people_masked.csv") {
    email : faker(person_email)
    ssn   : redact
  }
}
```

## 6. How the compiler works

```
.decoy text
  1. parse        Lark grammar → syntax tree; every node keeps its line and column
  2. build        syntax tree → typed AST (frozen dataclasses)
  3. resolve      let names, `use` imports, table and column references
  4. desugar      groups → coherent_with; `link` → relationships; `in x` → namespaces;
                  from/to → sources/targets; expect → validators and post_scan
  5. lower        AST → plain dict in the PipelineConfig shape, plus a source map
                  (dict path → source span)
  6. validate     PipelineConfig.model_validate (engine)
  7. report       engine errors translated to source lines through the source map
```

Design rules:

- **The dict is the intermediate form.** `--emit yaml` prints it at any time.
- **Lowering is canonical.** The same program always gives the same dict, byte for byte. The seed
  fingerprint and signed evidence hash the config, so the language stays out of the trust chain.
- **Names come from the engine, not the grammar.** Strategies, providers, generator types and
  their options are checked against `strategy_catalog()`, `generate_option_catalog()` and the
  config JSON schema. The compiler holds no second list.
- **One expression grammar.** The engine's.
- **No engine edits.** If a registry the compiler needs is private, the fix is a small public
  read-only accessor in the engine, as its own change.
- **Where it lives:** `src/decoy/lang/` in the CLI repo, one module per stage, within the module
  size limits.

Commands (shape to be settled against the CLI redesign plans):

| Command | What it does |
|---|---|
| `decoy run pipeline.decoy` | Compile, then run as today |
| `decoy validate pipeline.decoy` | Compile and validate, errors on source lines |
| `decoy validate pipeline.decoy --emit yaml` | Print the compiled YAML |
| `decoy fmt pipeline.decoy` | Rewrite in the one canonical layout |
| `decoy init --lang` | Wizard writes `.decoy` instead of YAML |
| YAML to `.decoy` converter | Migrate existing pipelines; also powers the round-trip test |

## 7. Documentation

Someone should be able to read for ten minutes and start writing.

| Doc | Content |
|---|---|
| Quickstart (one page) | Install, the smallest program from section 5, run it |
| Tour | One short page per group A to J: a problem, the code, the YAML it becomes |
| Reference | Every strategy, provider and generator with its options, **generated from the engine registries** so it cannot drift |
| Cookbook | The five engine recipes and the eleven bundled templates, rewritten in the language |
| YAML side by side | For people who know the YAML: each block and its language form |
| Error index | Each compiler error with an example and the fix |
| Agent card | One page holding the whole grammar and rules, sized to paste into a prompt |

## 8. Build order

Each step ends with something runnable. Each group gets a short design pass first: write the
programs, agree the syntax, then build.

| Step | Content | Ends with |
|---|---|---|
| 0 | Syntax trial. Hand-translate five real configs into two candidate styles (section 12, D1). Pick one. Write the agent card. | Agreed syntax for groups A to F |
| 1 | Compiler skeleton: parse, AST, lower, validate, source-mapped errors. Groups A, B and the simple part of D. **Built** in `src/decoy/lang/`: the four mask templates compile to identical config. Not wired to a command; `when` waits for group G. | Recipe (a) compiles |
| 2 | Group D in full: all strategies through the catalog, trailing settings, `when`. Group G expressions. | `hipaa`, `gdpr`, `pci` templates compile to identical YAML |
| 3 | Group C transforms. Group E: `link`, composite keys, coherent groups, namespaces, vault. | A multi-table foreign-key pipeline compiles |
| 4 | Group F generation. | All seven `generate-*` templates compile to identical YAML |
| 5 | `let`, escape hatch, `--emit yaml`, `decoy run` and `decoy validate` wiring. | **v0.1: usable for real pipelines** |
| 6 | Group J checks. Group H policy and `use`. Group I subset. | Full coverage of `PipelineConfig` |
| 7 | Formatter, YAML converter, round-trip test, coverage test. | Safe to hand to others |
| 8 | Wizard writes `.decoy`; review marker (section 11). Docs set. | Ready to ship |
| 9 | Editor support: syntax highlighting, then hover and completion. | Optional |

Rough size: steps 0 to 5 are three to five weeks of focused work; steps 6 to 8 add four to six.

## 9. Testing

- **Golden files.** Each bundled template and engine recipe has a `.decoy` twin. The test is
  `compile(twin) == load(yaml)`. Only configs that validate on the current engine go in the corpus;
  `decoy-engine/examples/complex_healthcare_claims.yaml` needs that check first.
- **Round trip.** Valid config → converter → compiler → same config. Run as a property test over
  generated configs.
- **Coverage.** A test walks the `PipelineConfig` JSON schema and fails if a field has neither
  dedicated syntax nor a deliberate escape-hatch entry. An engine change that adds a field shows up
  as one failing line.
- **Errors.** Snapshot tests for every compiler error message.
- **Agent trial.** Twenty pipeline tasks given to a model with only the agent card, once in YAML
  and once in the language. Measure the share that compile and validate first time. The language
  should win clearly, or the syntax needs another pass.

## 10. Keeping up with the engine

| Engine change | Language work |
|---|---|
| New strategy, provider, generator type or option | None. Read from the catalogs. |
| New disguise | None. `use` loads it. |
| New column or table setting | Works through `options {}` at once; a trailing word is added when wanted |
| New top-level config block | Works through `raw yaml {}` at once; a block is designed later |
| Renamed or removed field | Engine validation flags it; one lowering change |

YAML is always the first place a capability appears. The language can trail it, and the coverage
test says by how much. It can never be ahead of it or disagree with it.

## 11. Working with the wizard

- The wizard asks its questions and writes a `.decoy` file. It does not need to grow a prompt for
  every feature; the rest is a few lines added by hand or by an agent.
- **Review marker.** Today the wizard writes `# REVIEW:` comments above inferred entries. In the
  language an inferred line ends with `?`:

  ```
  email : faker(person_email) ?
  ```

  `decoy run` refuses while any `?` remains. Review becomes something the tool enforces. This needs
  agreement with the init-wizard plans before it is built.

## 12. Decisions needed

| # | Decision | Recommendation |
|---|---|---|
| D1 | Column style | **Decided: symbols.** `ssn : fpe(...)` masks, `id = sequence(...)` defines, `keep status` leaves unchanged. Verbs were built first, then reverted |
| D2 | Name and file extension | `.decoy` |
| D7 | Comments | **Decided: `#`.** `//` is integer division in the engine's expression grammar |
| D8 | CSV header | **Decided:** a CSV source has a header row unless `header: false` |
| D9 | Generators in a masked table | **Decided:** compile error until the engine supports mixed tables |
| D3 | Which file is committed to a project | The `.decoy` file; compiled YAML goes with run outputs |
| D4 | Release bucket | After 1.0 (it adds, breaks nothing); can ship earlier behind an experimental flag |
| D5 | Review marker `?` | Yes, timed with the wizard work |
| D6 | Does `decoy init` default to `.decoy` | Not until step 8 is done and the agent trial passes |

## 13. Risks

| Risk | Answer |
|---|---|
| Two formats to maintain | The compiler holds no capability lists; the coverage test reports drift |
| Syntax churn annoys early users | `decoy 1` version line; formatter can rewrite old files |
| The language grows into a programming language | Section 1 non-goals; any loop or function proposal needs its own decision record |
| Error messages worse than YAML's | Source map is in step 1, not an afterthought |
| Distracts from 1.0 | Not on the 1.0 path; goes through the roadmap inbox like any other idea |
