# 5. Checks, safety and subsets

Status: current

These statements sit at the pipeline level, beside the tables.

```decoy
decoy 1

pipeline {
  seed 42

  settings {
    post_validation: true
    on_pool_exhaustion: fail
  }

  subset {
    start customers sample 2% by customer_id
    follow customers.customer_id -> orders.customer_id downward
    budget(max_total_rows: 2_000_000)
  }

  scan before(regex)
  scan after(regex, integrity: true)
  expect leak_check(customers.email, min_rows: 50)
  expect fk_intact
  quarantine("out/quarantine.jsonl", triggers: [validation_fail])
  delivery(strict)

  mask customers from csv("customers.csv", header: true) to csv("out/customers.csv") {
    customer_id : hash in customer_identity
    email       : faker(person_email)
  }

  mask orders from csv("orders.csv", header: true) to csv("out/orders.csv") {
    customer_id <- customers.customer_id orphans preserve
    keep total
  }
}
```

| Statement | Does |
|---|---|
| `settings { }` | Any pipeline setting, by the engine's name for it |
| `scan before(...)`, `scan after(...)` | Looks for sensitive data before masking, and for leftovers after |
| `expect <check>(table.column, ...)` | A check the output must pass |
| `quarantine("path", triggers: [...])` | Sends failing rows to a file instead of the output |
| `baseline("path", on_drift: warn)` | Compares the source with an earlier scan |
| `delivery(strict)` | All tables are written, or none |
| `namespace <name> for table.column, ...` | Declares a namespace for columns outright |

## A smaller, intact slice

`subset { }` keeps part of the data and everything that belongs to it.

| Line | Means |
|---|---|
| `start customers sample 2% by customer_id` | Begin with 2% of customers |
| `start customers sample 500 rows by customer_id` | Or a fixed number |
| `start orders where total > 1000, status == open` | Or the rows that pass every test |
| `start customers keys customer_id in [101, 102]` | Or these exact keys |
| `follow parent.key -> child.key downward` | How far to follow one foreign key: `both`, `downward`, `upward`, `none` |
| `budget(max_total_rows: 2_000_000)` | Stop, rather than grow past this |

A subset follows every foreign key both ways unless a `follow` line says otherwise.

## Anything without a statement

`options { }` takes any top-level block of the pipeline config, written as plain values, so a
setting the language has no statement for is never out of reach.
