Status: record

# DECOY-LANG step 0: syntax trial for groups A, B and D

Date: 2026-11-19. Part of [2026-11-19-decoy-language.md](2026-11-19-decoy-language.md) (step 0,
decision D1).

Four pipelines, each written in two candidate styles. Three are bundled templates
(`minimal`, `hipaa`, `pci`), so the YAML to compare against is in `src/decoy/templates/`. The fourth
is made up to show the per-column settings the templates do not use; it has not been run against
the engine.

Only groups A (pipeline and settings), B (sources and targets) and D (masking) are in play. Nothing
here is built.

## The two styles

| | Style 1: symbols | Style 2: verbs |
|---|---|---|
| Mask a column | `ssn : fpe(charset: digits)` | `mask ssn with fpe(charset: digits)` |
| Several columns | `dob, admitted : shift` | `mask dob, admitted with shift` |
| Leave unchanged | `status : passthrough` | `keep status` |
| Namespace | `… in ssn_identity` | `… in ssn_identity` |

Everything else is the same in both: `decoy 1`, `pipeline { }`, `seed`, `let`, `table … from … to`,
call syntax with `key: value` options, `//` comments.

Shared rules used below:

- A strategy with no options is written bare: `redact`, not `redact()`.
- `faker(person_email)`: the first plain argument of `faker` is the provider.
- `let` names a strategy with its options and namespace so it can be reused.
- A comma list on the left applies one strategy to several columns.

## 1. `minimal` (30 lines of YAML)

Style 1:

```
decoy 1

pipeline {
  seed 42

  table people from csv("input.csv") to csv("output.csv") {
    first_name     : faker(person_first_name)
    last_name      : faker(person_last_name)
    email          : faker(person_email)
    ssn            : redact
    account_status : passthrough
  }
}
```

Style 2:

```
decoy 1

pipeline {
  seed 42

  table people from csv("input.csv") to csv("output.csv") {
    mask first_name with faker(person_first_name)
    mask last_name  with faker(person_last_name)
    mask email      with faker(person_email)
    mask ssn        with redact
    keep account_status
  }
}
```

## 2. `hipaa` (94 lines of YAML)

Style 1:

```
decoy 1

pipeline {
  seed 42

  let shift = date_shift(min_days: -30, max_days: 30) in patient_dates

  table patients from csv("patients.csv") to csv("patients_masked.csv") {
    first_name : faker(person_first_name)
    last_name  : faker(person_last_name)
    street     : faker(address_street)
    city       : faker(address_city)
    zip        : geo_generalize(type: zip, cascade: [zip5, zip3, state, suppress], k_threshold: 20000)

    dob, admission_date, discharge_date : shift

    phone, fax : faker(person_phone)
    email      : faker(person_email)

    ssn            : fpe(charset: digits)   in ssn_identity
    mrn            : fpe(charset: ALPHANUM) in mrn_identity
    account_number : fpe(charset: ALPHANUM) in account_identity
    vehicle_id     : fpe(charset: ALPHANUM) in vehicle_identity

    health_plan_id, license_number, device_id, url, ip_address, biometric_id : redact
  }
}
```

Style 2:

```
decoy 1

pipeline {
  seed 42

  let shift = date_shift(min_days: -30, max_days: 30) in patient_dates

  table patients from csv("patients.csv") to csv("patients_masked.csv") {
    mask first_name with faker(person_first_name)
    mask last_name  with faker(person_last_name)
    mask street     with faker(address_street)
    mask city       with faker(address_city)
    mask zip        with geo_generalize(type: zip, cascade: [zip5, zip3, state, suppress], k_threshold: 20000)

    mask dob, admission_date, discharge_date with shift

    mask phone, fax with faker(person_phone)
    mask email      with faker(person_email)

    mask ssn            with fpe(charset: digits)   in ssn_identity
    mask mrn            with fpe(charset: ALPHANUM) in mrn_identity
    mask account_number with fpe(charset: ALPHANUM) in account_identity
    mask vehicle_id     with fpe(charset: ALPHANUM) in vehicle_identity

    mask health_plan_id, license_number, device_id, url, ip_address, biometric_id with redact
  }
}
```

## 3. `pci` (46 lines of YAML)

Style 1:

```
decoy 1

pipeline {
  seed 42

  table transactions from csv("transactions.csv") to csv("transactions_masked.csv") {
    cardholder_name  : faker(person_name)
    card_number      : fpe(charset: digits, validate_luhn: true) in pan_identity
    card_expiry, cvv : redact
    billing_zip      : truncate(length: 3)
    email            : faker(person_email)
    transaction_id   : hash in transaction_identity
    transaction_date : date_shift(min_days: -30, max_days: 30) in transaction_dates
  }
}
```

Style 2:

```
decoy 1

pipeline {
  seed 42

  table transactions from csv("transactions.csv") to csv("transactions_masked.csv") {
    mask cardholder_name  with faker(person_name)
    mask card_number      with fpe(charset: digits, validate_luhn: true) in pan_identity
    mask card_expiry, cvv with redact
    mask billing_zip      with truncate(length: 3)
    mask email            with faker(person_email)
    mask transaction_id   with hash in transaction_identity
    mask transaction_date with date_shift(min_days: -30, max_days: 30) in transaction_dates
  }
}
```

## 4. Settings and a cloud source (made up, not run)

Shows group A settings, an S3 source with a pipe-delimited file, and the per-column settings:
`deterministic`, `vaulted`, `when`.

Style 1:

```
decoy 1

pipeline member_export {
  seed env("DECOY_SEED")
  secret ref("mask-key")
  unconfigured columns error

  table members
    from s3("acme-landing", "members/2026-06.csv", credentials: "phi-readonly", delimiter: "|")
    to   parquet("out/members.parquet")
  {
    member_id : fpe(charset: digits) in member_identity deterministic
    account   : faker(synthetic_account_number) in account_vault vaulted
    ssn       : fpe(charset: digits) in ssn_identity when country == 'US'
    notes     : text_redact
    tier      : passthrough
  }
}
```

Style 2:

```
decoy 1

pipeline member_export {
  seed env("DECOY_SEED")
  secret ref("mask-key")
  unconfigured columns error

  table members
    from s3("acme-landing", "members/2026-06.csv", credentials: "phi-readonly", delimiter: "|")
    to   parquet("out/members.parquet")
  {
    mask member_id with fpe(charset: digits) in member_identity deterministic
    mask account   with faker(synthetic_account_number) in account_vault vaulted
    mask ssn       with fpe(charset: digits) in ssn_identity when country == 'US'
    mask notes     with text_redact
    keep tier
  }
}
```

## How they compare

| | Style 1: symbols | Style 2: verbs |
|---|---|---|
| Length | Shortest. `hipaa` is 25 lines against 94 of YAML. | Same line count, about 10 characters more per line |
| Scanning a wide table | Column names line up on the left edge, like a schema | Every line starts with `mask`, so names start further in |
| First read with no docs | Needs one sentence: "`:` means mask with" | Reads as English |
| Looks like | A typed field list (TypeScript, Python annotations) | SQL or a shell script |
| Generation (group F) | Needs the second symbol: `id = sequence(...)` | Needs a second verb: `make id from sequence(...)` |
| Risk of confusion | `:` against `=`; also looks a little like YAML | Low |
| Searching a repo | `grep "ssn *:"` | `grep "mask ssn"` |
| Typing by hand | Less | More |

Recommendation: **Style 1**, with one borrowing from Style 2: `keep` as a statement for unchanged
columns (`keep tier, status`). A pipeline is mostly a long list of columns, and Style 1 keeps the
column names where the eye lands. The one thing to learn (`:` masks, `=` defines) is small, and the
`table` and `generate` block names already say which is which.

## Smaller questions this trial raised

| # | Question | Suggestion |
|---|---|---|
| Q1 | `passthrough` or `keep`? | `keep a, b` as a statement. It is the one renamed engine word, so it needs a yes. |
| Q2 | Is `pipeline` named? | Name optional, as in YAML. `pipeline { }` and `pipeline claims { }` both valid. |
| Q3 | CSV header default | `csv("x.csv")` means a header row; `csv("x.csv", header: false)` otherwise. The compiled YAML always states `has_header`. |
| Q4 | Provider shorthand: allow `email : person_email` for `faker(person_email)`? | No. One way to say each thing; a bare name is always a strategy. |
| Q5 | Options: `charset: digits` or `charset = digits`? | `key: value`, matching Swift, Kotlin and YAML habits. |
| Q6 | Bare words as option values (`digits`, `zip5`) or quoted strings? | Bare words where the engine has a fixed list of choices; quotes for free text such as paths. |
| Q7 | Where do `in`, `deterministic`, `vaulted`, `when` go? | After the call, in that order. The formatter enforces the order. |
| Q8 | Relative paths: `"input.csv"` or `"./input.csv"`? | Both accepted; compiled YAML keeps what was written. |

## Outcome (2026-11-19)

| Question | Decision |
|---|---|
| Style | **Style 1, symbols**: `<columns> : <strategy>`, with `keep <columns>` from Style 2. Style 2 was built first and then reverted |
| Q1 | `keep a, b`; it compiles to `passthrough` |
| Q2 | Pipeline name is optional |
| Q3 | A CSV source has a header row unless `header: false` |
| Q4 | No provider shorthand; a bare name is a strategy or a `let` name |
| Q5 | Options are `key: value` |
| Q6 | Bare words and quoted strings both give a string; quotes are needed for anything that is not a plain word |
| Q7 | After the call: `in <namespace>`, then `deterministic`, then `vaulted` |
| Q8 | Paths are kept as written |
| Comments | `#`, not `//`: `//` is integer division in the engine's expression grammar |
| New column in a masked table | `name = expression`; a generator there is a compile error |
| Layout | Spaces and line breaks only separate words. Inside a table `keep`, `in`, `deterministic` and `vaulted` are reserved; such a column name goes in single quotes |

The Style 2 examples above are kept as the record of what was compared. The built form is in
`src/decoy/lang/` and the `.decoy` twins of the templates in `tests/unit/lang/twins/`.
