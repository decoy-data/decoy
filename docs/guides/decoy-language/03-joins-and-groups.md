# 3. Joins and groups

Status: current

## Foreign keys

When two tables share a key, the child's key has to be masked to the same value as the parent's,
or the join breaks. One line says so.

```decoy
decoy 1

pipeline {
  seed 7

  mask customers from csv("customers.csv", header: true) to csv("out/customers.csv") {
    customer_id : hash in customer_identity
    keep region
  }

  mask orders from csv("orders.csv", header: true) to csv("out/orders.csv") {
    order_id    : hash in order_identity
    customer_id <- customers.customer_id orphans preserve
    keep total
  }

  mask order_lines from csv("lines.csv", header: true) to csv("out/lines.csv") {
    order_id, customer_id <- orders.(order_id, customer_id) in order_keys orphans fail
    keep sku
  }
}
```

`customer_id <- customers.customer_id` reads "takes its value from". The parent table is masked
first and the child key gets the value its parent got.

`orphans` says what happens to a child row with no matching parent. It has no default, because
the right answer depends on your data:

| Policy | A child row with no parent |
|---|---|
| `preserve` | Keeps its original key |
| `remap` | Is masked the way the parent key is |
| `warn` | Keeps its key, and the run reports how many there were |
| `fail` | Stops the run |

The parent key needs a namespace (`in customer_identity`). A key of several columns is written
with brackets on the parent side, and can name its own namespace with `in`.

## Columns that must agree

Some columns only make sense together: a first name, a last name and an email built from them.

```decoy
decoy 1

pipeline {
  seed 7

  mask contacts from csv("contacts.csv", header: true) to csv("out/contacts.csv") {
    {first_name, last_name, email} : faker(composite_name_email)
    keep id
  }
}
```

The braces make one group: each row gets a name and an email that belong together.
