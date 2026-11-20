# 4. Generating data

Status: current

A `generate` block makes a table from nothing. Columns are defined with `=`.

```decoy
decoy 1

pipeline {
  seed 42

  generate customers rows 1000 to csv("customers.csv") {
    customer_id = sequence(10000, unique: true)
    first_name  = faker(first_name)
    email       = faker(email)
    tier        = categorical({None: 0.6, Silver: 0.3, Gold: 0.1})
    spend       = faker(random_int, faker_kwargs: {min: 1, max: 500})
    label       = concat(tier, '-', customer_id)
  }

  generate orders rows 3000 to csv("orders.csv") {
    order_id    = sequence(1)
    customer_id <- customers.customer_id
    placed_on   = faker(date_this_year)
    status      = categorical({New: 0.2, Paid: 0.5, Shipped: 0.3})
  }
}
```

| Written | Makes |
|---|---|
| `sequence(10000)` | 10000, 10001, ... |
| `faker(email)` | A fake value of that kind |
| `categorical({None: 0.6, Gold: 0.4})` | One of the values, with those shares |
| `constant("EU")` | The same value in every row |
| `name <- table.column` | A value drawn from another generated table, so the tables join |
| `name = expression` | A value computed from the columns above it |

`unique (a, b)` on its own line stops a pair of drawn columns from repeating.

A pipeline can hold both kinds of table. A masked table cannot hold a generator; the compiler
says so and points to a `generate` block.
