# Policy: column types and bad cells

Status: current

Owner decision 2026-11-21 (COLUMN-SHAPE-RULE), confirmed 2026-11-28 after an outside review. The rule below is the product direction. Customer-facing docs (the website, guides, the language reference) must state it, and must describe only what has shipped. The section "Where 1.0 stands" says which parts are built, and "For customer docs" lists what to say.

## The rule

1. **Do not guess at run time.** Decoy detects a type or format only while a pipeline is set up (`decoy scan`, `decoy init`, `decoy fit`). It writes what it found into the pipeline, where a person confirms it. At run time it follows the declaration or refuses.
2. **Declare only where a strategy needs it.** A declaration is needed only when a strategy reads a date or a number out of text. A supported source type (a typed Parquet, DuckDB, database or Arrow column) needs no declaration.
3. **A bad cell never passes through.** A cell that does not match what the strategy needs is a row error. The run fails, or the row is quarantined when quarantine covers it. Decoy never writes the source value to the output in its place.
4. **Errors never show the cell value.**

## When a declaration is needed (text sources)

| Strategy | What it needs on a text column |
|---|---|
| `date_shift` | a strategy `date_format`, or a supported declared date type (not both: both is refused) |
| `bucket_perturb` | a strategy `date_format` |
| `bucketize`, `top_code` | a supported numeric cast |
| `windowed_date` | nothing: its anchors use one fixed ISO grammar |
| `fpe` | nothing: it accepts text or integers |
| `hash`, `redact`, `tokenize`, faker replacement, `shuffle`, `categorical` | no type declaration (some of them still use the source value, for example as hash input) |

A missing declaration is a coded refusal before masking starts. On a typed column, a redundant date format can give an unused-format warning, and a declared cast expects text or bytes.

## Bad cells

What ships in 1.0:

- **Strategy row errors** (`format_error`). The run fails unless quarantine is turned on, covers that trigger, and the route supports it (`--chunked` refuses quarantine). Covered rows are counted and removed from the main output. The quarantine file is written from the masked output tables, so it is not a copy of the input, but it can still hold sensitive values: treat it as admin-only.
- **Declared casts** (F06) have their own per-column policy: `fail`, `null` or `quarantine`. Their quarantine needs a protected runtime sink. It stores the raw framed rows and reports a receipt.

Under the rule, these must never be added for masking, because each one can put a real value in the output or lose rows without notice:

- keeping the source value unchanged ("warn and continue");
- best-effort conversion, or trying a second format;
- dropping bad rows silently;
- copying the raw record into the output.

## Where 1.0 stands

- **Review mark.** `decoy run` refuses a `.decoy` rule while its `?` mark remains, and no flag clears it. YAML has no review mark. Writing detected declarations with the mark (the `as <shape>` syntax and marked starter output) is planned in COLUMN-SHAPE-RULE. Asking the user when a detected date format is ambiguous (for example `01/02/2024`) is also planned.
- **`decoy fit`.** Exact `decoy fit` still lets pandas infer CSV types, so it can turn `007` into `7`. Row FIT-CODES-TEXT (1.0, not merged) keeps a column as text when every value is whole digits (optional sign) and at least one has a leading zero. A code column with no leading zero in the fitted rows is still read as a number. The DP fit path already reads text.
- **Unusual date encodings.** Some typed sources store dates in forms that can read differently on different execution routes (dictionary-encoded dates, a timezone or unit that only pandas metadata restores, `date64` values with a time of day). Until row DATE-RANGE-SENTINEL S5 lands, support depends on the encoding and the route. S5 checks date inputs on every route, including carried columns. Its scope for these encodings is owner question Q9.

## Planned for 1.x

Row TYPES-DECLARED:

- `decoy fit` reads CSV as text and applies declared types, and the FIT-CODES-TEXT zero-padding rule goes away.
- One closed bad-cell setting per table in `.decoy`, built on the existing declared-cast policy, not a second mechanism.

## What to refuse as the language grows

Keep `.decoy` simple. Do not add sentinel patterns (only exact listed values) or "try these formats in order". Prefer one table-level bad-cell setting over a setting on every column.

## For customer docs

Wherever types, CSV input, `decoy init`, `decoy fit` or quarantine are documented, say:

1. Decoy does not guess types when it runs. A `.decoy` rule marked `?` must be confirmed before `decoy run` accepts it.
2. You declare a type only when a strategy reads a date or number from text. Give the table above.
3. A bad cell stops the run by default. With quarantine on and covering the error, the row is removed and counted instead. A bad cell is never passed through unmasked.
4. Bad-cell diagnostics omit the cell value. Strategy row errors name the table, the column and the trigger.
5. The known limits under "Where 1.0 stands" that apply to the page.

Only describe a planned item once it has shipped.

Background: established tools take the same approach. readr, Polars and DuckDB infer CSV types from a sample and advise explicit types for production. Spark's CSV reader has type inference off by default. Frictionless Table Schema declares a type and a format per field. dbt contracts fail the build on a type mismatch.
