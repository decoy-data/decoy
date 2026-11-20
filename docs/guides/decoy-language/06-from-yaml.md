# 6. Coming from YAML

Status: current

A `.decoy` file compiles to exactly the YAML you would have written, and an existing YAML
pipeline converts the other way:

```
python -m decoy.lang --to-decoy pipeline.yaml > pipeline.decoy
```

The converter checks its own work. It compiles the program it wrote and compares the result with
your YAML as the engine sees it. If they differ it refuses, naming the block that would change,
rather than write something close.

## Side by side

```yaml
version: 2
global_settings:
  seed: 42
sources:
  transactions:
    type: file
    format: csv
    has_header: true
    path: ./transactions.csv
tables:
  - name: transactions
    columns:
      - name: card_number
        strategy: fpe
        namespace: pan_identity
        provider_config:
          charset: digits
          validate_luhn: true
      - name: cvv
        strategy: redact
      - name: email
        strategy: faker
        provider: person_email
targets:
  transactions:
    type: file
    format: csv
    path: ./transactions_masked.csv
```

```decoy
decoy 1

pipeline {
  seed 42

  mask transactions from csv("./transactions.csv", header: true) to csv("./transactions_masked.csv") {
    card_number : fpe(charset: digits, validate_luhn: true) in pan_identity
    cvv         : redact
    email       : faker(person_email)
  }
}
```

## Where each YAML block went

| YAML | `.decoy` |
|---|---|
| `version: 2` | `decoy 1` (the compiler writes the config version) |
| `name:` | `pipeline <name> { }` |
| `global_settings.seed` | `seed 42` |
| `global_settings.mask_secret_ref` | `secret ref("...")` |
| other `global_settings` | `settings { }` |
| `sources`, `targets` | `from ...` and `to ...` on the table |
| `tables[].columns[]` | `column : strategy(...)` |
| `strategy: passthrough` | `keep column` |
| `provider`, `provider_config` | The first value and the options of the call |
| `namespace`, `deterministic`, `vault`, `when` | `in`, `deterministic`, `vaulted`, `when` after the call |
| `coherent_with` | `{a, b} : rule` |
| `tables[].transforms[]` | `where`, `name = ...`, `sort by`, `limit`, `dedupe`, `drop` |
| `relationships` and `strategy: from_parent` | `child <- table.key orphans <policy>` |
| `tables[].generate_columns[]`, `row_count` | `generate <table> rows N { name = generator(...) }` |
| `type: reference` | `name <- table.column` |
| `pre_scan`, `post_scan` | `scan before(...)`, `scan after(...)` |
| `validators` | `expect <check>(...)` |
| `quarantine`, `scan_baseline`, `delivery` | `quarantine(...)`, `baseline(...)`, `delivery(...)` |
| `namespaces` | `namespace <name> for table.column` |
| `subset` | `subset { }` |
| anything else | `options { }` |

## What the converter will not write

| Your YAML has | Why it is refused |
|---|---|
| A relationship with no `namespace` | A link always carries one, so the pipeline would change |
| `quarantine` with `enabled: false` | Writing `quarantine(...)` turns it on; leave the block out instead |
| A `null` where a value is expected | The language has no spelling for it |
| An expression with `**`, `%`, `&` or attribute access | The language holds the engine's closed expression forms only |
