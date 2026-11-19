# Decoy language

Status: current

A `.decoy` file defines a pipeline: what to read, how to mask or generate each table, and where
to write it. It compiles to the pipeline YAML the engine reads, so anything a YAML pipeline does,
a `.decoy` file does too.

```decoy
decoy 1

pipeline {
  seed 42

  mask people from csv("people.csv", header: true) to csv("people_masked.csv") {
    email : faker(person_email)
    ssn   : redact
    keep id
  }
}
```

For now a `.decoy` file is compiled in one step and then run as usual:

```
python -m decoy.lang pipeline.decoy > pipeline.yaml
decoy run pipeline.yaml
```

| Page | For |
|---|---|
| [1. A first pipeline](01-first-pipeline.md) | The shape of a file, and the three commands |
| [2. Masking](02-masking.md) | Rules, conditions, shaping a table before it is masked |
| [3. Joins and groups](03-joins-and-groups.md) | Foreign keys that survive masking; columns that stay consistent |
| [4. Generating data](04-generating.md) | Tables made from nothing |
| [5. Checks, safety and subsets](05-checks-and-subsets.md) | Scans, `expect`, quarantine, a referentially intact slice |
| [6. Coming from YAML](06-from-yaml.md) | The two forms side by side, and the converter |
| [7. Errors](07-errors.md) | Every compiler error and its fix |
| [Cheat sheet](cheat-sheet.md) | Syntax at a glance |
| [The language on one page](agent-card.md) | A complete reference sized for a prompt |

Every complete program on these pages is compiled by `tests/unit/lang/test_docs.py`.

Design and status: [docs/plans/2026-11-19-decoy-language.md](../../plans/2026-11-19-decoy-language.md),
[docs/plans/2026-11-19-decoy-language-completion.md](../../plans/2026-11-19-decoy-language-completion.md).
