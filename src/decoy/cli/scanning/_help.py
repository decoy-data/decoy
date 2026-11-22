"""Help text of `decoy scan`, kept apart so `scan.py` stays under its size ceiling."""

SCAN_EPILOG = """\
Options of `decoy scan SOURCES...` (the default command; the subcommands below
have their own):

  --has-header / --no-header   Does row 1 of a CSV hold the column names? Required for every CSV.
  --column-names TEXT          Names for one headerless CSV (needs --no-header).
  --rows INTEGER               Scan the first N rows; 0 scans every row. Default: 10000.
  --strategy [head|random]     Sampling strategy when --rows bounds the scan.
  --format TEXT                Input format: delimited, parquet or fixed-width.
  --layout PATH                Column layout (YAML or JSON) for fixed-width input.
  --detectors TEXT             Which detectors to run.
  --ner-model TEXT             NER model for the name detector.
  --show-fields                Show per-field detail.
  -o, --output PATH            Save the value-free scan JSON; - writes to stdout.
  --json                       Emit a JSON result on stdout.
  -q, --quiet / -v, --verbose  Less or more output.

Examples:

  decoy scan data.csv --has-header
    Profile a CSV: row/field counts, PII candidates (as suggestions), reid risk.
    A CSV always needs --has-header or --no-header: scan never guesses.
    Reads the first 10 000 rows by default and labels the counts a sample, with
    no key candidates (--rows 0 reads every row and gives whole-file numbers).

  decoy scan customers.csv orders.csv --has-header
    Scan several files in one run: one table each, named from the file stem.

  decoy scan raw.csv --no-header --column-names id,name,email
    A headerless CSV: row 1 is data, the names come from you.

  decoy scan data.csv --has-header --show-fields
    Per-field detail: dtype, null_rate, distinct_count, PII candidate flag.

  decoy scan data.csv --has-header --rows 50000 --strategy random
    Sample 50K random rows instead of the first 10 000.

  decoy scan data.csv --has-header --output scan.json
    Save the value-free scan to scan.json, then: decoy scan fields scan.json

  decoy scan data.csv --has-header --output -
    Stream the scan JSON to stdout for downstream tooling.

  decoy scan records.fwf --layout layout.yaml
    Scan a fixed-width file using an explicit column layout.
    Layout YAML: columns: [{name: id, start: 0, width: 5}, ...]

HONESTY: PII candidates are SUGGESTIONS based on pattern matching. They
are NOT authoritative classifications. You review each flagged field and decide
what masking to apply. Decoy never auto-classifies PII.

No raw cell values appear in the inline output or in --output. Field stats
include dtype, null_rate, distinct_count only.

See also: decoy scan fields, decoy scan show, decoy scan diff,
  decoy explain scan, decoy validate.
"""
