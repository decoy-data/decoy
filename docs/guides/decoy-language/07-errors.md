# 7. Errors

Status: current

Every error has a code. `tests/unit/lang/test_docs.py` fails if the compiler can raise a code
that is not on this page.

## Reading the file

| Code | Means | Fix |
|---|---|---|
| `lang.syntax` | A word or symbol is not where the language expects one | The hint lists what would fit there |
| `lang.version` | The first line is not `decoy 1` | Write `decoy 1` |
| `lang.string_escape` | A backslash sequence in double quotes is not one the language reads | Use single quotes, or double the backslash |
| `lang.number` | A number is too large to hold | Write a smaller one |
| `lang.name_empty` | A quoted name is empty | Give it a name |
| `lang.nesting` | Lists, maps or brackets are nested too deeply | Flatten the value |

## The pipeline

| Code | Means | Fix |
|---|---|---|
| `lang.seed_missing` | The pipeline has no seed | Add `seed 42` |
| `lang.setting_repeated` | A setting is given twice | Keep one |
| `lang.table_repeated` | Two tables have the same name | Rename one |
| `lang.block_repeated` | A statement that may appear once appears twice | Keep one |
| `lang.block_arguments` | A statement was given more plain values than it takes | Write the others as `key: value` |
| `lang.reference_not_allowed` | A `table.column` was given where the statement takes none | Remove it |
| `lang.expect_argument` | A check was given a plain value | Columns are `table.column`; settings are `key: value` |
| `lang.option_not_allowed` | The option has its own syntax, or is set by the statement itself | Use the form in the hint |
| `lang.option_repeated` | An option or map key is given twice | Keep one |
| `lang.positional_after_option` | A plain value follows a `key: value` | Put plain values first |

## Tables and rules

| Code | Means | Fix |
|---|---|---|
| `lang.unknown_strategy` | The name after `:` is not a strategy or a `let` | The hint suggests the nearest |
| `lang.strategy_arguments` | A strategy was given more than one plain value | Only the provider is plain; the rest are `key: value` |
| `lang.column_repeated` | A column has two rules, or two links | Keep one |
| `lang.group_too_small` | `{...}` has one column | A group needs at least two |
| `lang.let_repeated` | A `let` name is defined twice | Rename one |
| `lang.let_shadows_strategy` | A `let` has a strategy's name | Choose another name |
| `lang.let_modified` | A `let` name was given options or words | Put them on the `let` line |
| `lang.unknown_connector` | The source or target is not one the language has | Use `csv`, `parquet`, `fixed_width`, `s3` or `gcs` |
| `lang.connector_arguments` | A source or target was given the wrong number of plain values | See the list in the hint |
| `lang.format_unknown` | The format of an `s3` or `gcs` object cannot be told from its name | Add `format: csv` or `format: parquet` |
| `lang.generator_in_masked_table` | A masked table defines a column with a generator | Move it to a `generate` block |

## Foreign keys

| Code | Means | Fix |
|---|---|---|
| `lang.link_unknown_table` | The parent table is not in the pipeline | The hint suggests the nearest |
| `lang.link_unknown_column` | The parent table has no rule for that key | Add one |
| `lang.link_arity` | The child and parent keys have different numbers of columns | Make them match |
| `lang.link_needs_namespace` | The parent key has no namespace | Add `in <namespace>` to its rule or to the link |
| `lang.orphans_missing` | The link does not say what happens to unmatched rows | Add `orphans preserve`, `remap`, `warn` or `fail` |

## Generated tables

| Code | Means | Fix |
|---|---|---|
| `lang.unknown_generator` | The call is not a generator | The hint suggests the nearest |
| `lang.generator_arguments` | A generator was given more plain values than it takes | Write the others as `key: value` |
| `lang.generator_argument` | A generator was given a computed value, or written without its call | Give plain values; compute in a separate column |

## Subsets

| Code | Means | Fix |
|---|---|---|
| `lang.sample_rows` | A row count is not a whole number | `sample 500 rows`, or `sample 2.5%` |
| `lang.subset_condition` | A test uses an operator a subset cannot filter on | Use `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `is null`, `is not null` |

## From the engine, the formatter and the converter

| Code | Means | Fix |
|---|---|---|
| `lang.config` | The engine refused the compiled pipeline; its own code is in brackets | Fix what the message names, on the line shown |
| `lang.expression` | An expression cannot be held by the language | Use the forms on [page 2](02-masking.md) |
| `lang.unreviewed` | A rule still ends with `?` | Check the rule, then remove the `?` |
| `lang.format` | Formatting would have changed the program; the file is left alone | Report it; this is a formatter bug |
| `lang.unprintable_name` | A name has a quote or a line break and cannot be written | Rename the column or table |
| `lang.unprintable_number` | A number is not finite and cannot be written | Use a finite number |
