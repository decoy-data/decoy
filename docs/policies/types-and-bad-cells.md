# Policy: column types and bad cells

Status: current

Owner decision 2026-11-21 (COLUMN-SHAPE-RULE), confirmed 2026-11-28 after an outside review. This is a product rule, not a plan. Customer-facing docs (the website, guides, the language reference) must state it. See "For customer docs" at the end.

## The rule

Text stays text until someone declares what it is. Decoy detects a type only while a pipeline is being set up (`decoy scan`, `decoy init`, `decoy fit`). It writes what it found into the pipeline, where a person confirms it. At run time Decoy only follows the declaration or refuses. It never guesses at run time.

## When a declaration is needed

- **Typed sources** (Parquet, DuckDB, a database, Arrow) with a plain date or number column: the type comes from the source. No declaration.
- **Strategies that do not read the value** (`hash`, `redact`, `tokenize`, faker replacement, `shuffle`, `categorical`): no declaration.
- **Text columns that a strategy reads as a date or a number** (`date_shift`, `bucket_perturb`, `bucketize`, `top_code`, `fpe` where it depends on shape): the type and its format are required. A missing one is a coded refusal at plan compile, before any data row is read.
- **A declaration on a typed column** is an override. A declaration that does not match the source type is refused.

`decoy init` and `decoy scan` write the declarations they detect with the `?` review mark. `decoy run` refuses until the person clears it. No flag clears it automatically. If detection is ambiguous (for example `01/02/2024`), Decoy writes no format and asks.

Declarations are rare and machine-written, so most `.decoy` files gain no lines.

## Bad cells

A cell that does not match its declared type or format is a row error. The error names the table, the column and the reason. It never contains the cell value.

| Action | What happens | Status |
|---|---|---|
| `fail` | The run stops. This is the default. | 1.0 |
| `quarantine` | The row is written to the quarantine file and counted, and the run finishes. | 1.0, when quarantine covers `format_error` |
| `null` | The output cell is emptied and counted. | 1.x candidate (row TYPES-DECLARED) |

These actions must never exist for masking, because each one can put a real value in the output or lose rows without notice:

- keeping the source value unchanged ("warn and continue");
- best-effort conversion, or trying a second format;
- dropping bad rows silently;
- copying the raw record into the output.

The quarantine file holds raw source data. Treat it as source data: admin-only, and named in the run report.

## Unusual encodings

Some typed sources store dates in forms that read differently on different execution routes (dictionary-encoded dates, dates whose timezone comes back only from pandas metadata, date64 values that are not whole days). For a column that a date strategy reads, Decoy refuses these with one coded error that names the fix (cast to a plain date or timestamp column). A column of that kind that is only kept, hashed, redacted or tokenized keeps working.

## Known limit in 1.0

`decoy fit` still lets pandas infer CSV column types. In 1.0 it keeps a column as text when every value is whole digits (optional sign) and at least one has a leading zero, so ZIPs and codes like `007` stay intact (row FIT-CODES-TEXT). A code column with no leading zero in the fitted rows is still read as a number. Row TYPES-DECLARED (1.x) moves `fit` to the same rule as masking: read CSV as text and apply declared types.

## What to refuse as the language grows

Keep `.decoy` simple. Do not add per-column bad-cell settings, sentinel patterns (only exact listed values), or "try these formats in order".

## For customer docs

State these points in plain words wherever types, CSV input, `decoy init`, `decoy fit` or quarantine are documented:

1. Decoy does not guess types when it runs. It asks you to confirm what it detected (the `?` mark).
2. You only declare a type when a strategy needs to read a date or number from text. `decoy init` fills it in.
3. A bad cell stops the run by default, or goes to quarantine if you turn that on. Decoy never passes a bad cell through unmasked.
4. Error messages never show your data.
5. The 1.0 limit on `decoy fit` above.

Background: established tools ended up in the same place. readr, Polars and DuckDB guess from the first rows and advise explicit types for production; Spark's CSV reader has type inference off by default; Frictionless Table Schema declares a type and format per field; dbt contracts fail the build on a type mismatch.
