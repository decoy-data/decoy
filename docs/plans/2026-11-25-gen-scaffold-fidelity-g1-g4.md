Status: plan

# GEN-SCAFFOLD-FIDELITY G1-G4: the generate scaffold keeps ids and dates, and fidelity stops scoring broken dates 1.000

Owner: Cam. Author: Opus plan agent. Date: 2026-11-25. Revision 2 (Dennis R1 folded: H1-H3, M1-M5, L1-L6). Source: `docs/roadmap/inbox.md` item "carried from CLI #321, outside review: broken today, a generated sequential id came out negative and a date column came out as lorem text; the fidelity report scored that column 1.000", and the second half of EXAMPLES-FIX ("`decoy init --preset generate` fails on the demo's own CSV"). Repos: decoy (CLI) and decoy-engine. Branch: docs/plans-inbox-triage-1125 (CLI). Read at CLI `origin/main` `fffca916` and engine `origin/main` `2b8a47fbe`.

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md` (PLAN, Proportion, Design notes, Placement), `bugfix.md`, `reuse-first.md`, `api-and-compatibility.md`, `testing.md` (Test depth), `catalogs/recurring-defects.md`.

Classification: 1.0 blocker. The documented generate flow (`decoy init source.csv --preset generate`, then `decoy run`) gives wrong output on a plain CSV, and the fidelity report calls one broken column perfect. On small CSVs with text columns (the demo's `customers.csv`) the scaffold fails outright. Both are function breaks under the V1 bar. Risk: R2. It changes snapshot values for one class of flagged column and quality-report scores for date columns.

## 1. Reproduction and root cause

Reproduced on the Mac node with `vm-run` (CLI `fffca916`, engine pin at that commit). Input: 200 rows, `id` 1 to 200, `signup_date` ISO dates, `amount` 5 to 500, `status` in a, b, c. Steps: `decoy init data.csv --preset generate -o gen/pipeline.yaml --yes`, add `allow_real_categories: true` to `status`, `decoy run gen/pipeline.yaml`, `decoy report fidelity data.csv <output> --generate`.

Observed: 61 of 200 generated `id` values were negative and 5 were duplicates. Every `signup_date` was 10 characters of lorem text. The report gave `id` similarity 0.000, `signup_date` 1.000 (method `length_mean_diff`), overall 0.724, grade C, and "no policy violations". On `decoy_demo/customers.csv` the scaffold exits 1: "statistical column 'customer_id': the snapshot withheld the real values ... no values to sample".

Root causes (each confirmed in code by Dennis R1):

- R1, ids. The scaffold turns every column into `type: statistical` (`src/decoy/cli/gen/_scaffold.py:102`). The profiler flags a unique column as value-sensitive, so the snapshot keeps one coarse bin for it. `_grid_edges` (`decoy_engine/profiling/_snapshot_values.py:91`) puts the lower edge one power-of-ten step below the smallest cell, so 1..200 becomes the bin [-1000, 2000]. Sampling from that bin gives negatives and repeats.
- R2, dates. The scaffold calls `fit_exact_snapshot(csv, row_limit=...)` with no date handling (`_scaffold.py:221`), so ISO date strings stay `object` dtype. With more than `CATEGORICAL_DISTINCT_CAP` distinct values, `_stats_for` (`decoy_engine/quality/snapshot.py:279`) calls the column `freetext`, and the generator writes lorem text of the right length.
- R3, the 1.000. `report fidelity` reads both CSVs with pandas defaults (`read_report_source`, `src/decoy/cli/_sources.py:434`), so source dates and output lorem are both `freetext`. `_freetext_similarity` (`decoy_engine/quality/fidelity.py:510`) compares mean length only. `kind_drift` (`decoy_engine/quality/diagnostic.py:170`) sees freetext on both sides and passes.
- R4, the demo failure. The demo CSV has 10 rows, below the release count K=10 rule (`decoy_engine/profiling/_value_redaction.py:78`), so every text column is withheld: `customer_id`, `first_name`, `last_name`, `email`, `ssn` and `gender`. The engine refuses a statistical column over withheld values (`STATISTICAL_SNAPSHOT_VALUES_REDACTED`, `_refuse_withheld_values`, `decoy_engine/generation/statistical/_spec.py:240`). `compile_plan` stops at the first failing statistical column (`decoy_engine/plan/_checks.py:378-391`), so a gate-retry loop sees one column per run and cannot fix the file.

## 2. Established solutions

Searched: how synthesizers pick a generator per column from a sample (SDV `Metadata.detect_from_dataframe` and its `sdtype` of `id` and `datetime`; Gretel and synthpop column typing), and how profilers spot date strings (pandas `to_datetime` with an explicit or ISO8601 format, `pandas.tseries.api.guess_datetime_format`, ydata-profiling type inference, and the engine's own `profiling/_date_sniff.py`). SDV marks a key as `id` from uniqueness plus a column-name signal and regenerates it as a key, never from a distribution. It marks a column as `datetime` when its strings parse with one format. This plan follows that rule: key-named unique integers become `sequence`; a date column is one whose sample agrees on one explicit format, and the full column is parsed vectorized with that format. For the coarse bin, Hundepool et al. (Statistical Disclosure Control, 2012, section 4.2, global recoding) allows a recoded interval to keep a public bound such as zero; the sign of a column is not a cell value.

## 3. Behavior

### G2, engine: one date-text rule and one value-access verdict

1. Date rule, in `decoy_engine/profiling/_date_sniff.py`, exported from `decoy_engine.profiling`:
   - `date_text_format(values) -> str | None`. Read the first 200 non-null values of a text column. Return `None` when every sampled value is digits only (zip codes, ids). Try `format="ISO8601"` with `utc=True`; if at least 95 percent of the sample parses and every parsed value has a date part (a leading `YYYY-MM-DD`), return `"ISO8601"`. Otherwise take `guess_datetime_format` on each sampled value. Keep a format only if it contains a year, a month and a day directive (so "10:30" and "1.2.3" never qualify) and parses at least 95 percent of the sample. If both a month-first and a day-first format parse the whole sample, the column is ambiguous and the result is `None` (no silent day and month swap). Otherwise return the one format.
   - `coerce_date_text(values, fmt) -> Series`: one vectorized `pd.to_datetime(values, format=fmt, errors="coerce", utc=True)`, then naive UTC through the shared tz step in `decoy_engine/internal/pandas_compat.py:84`. That function is split so its tz step (`utc_naive`) does not drop nulls; `utc_naive_datetimes` keeps its behavior by calling it and dropping nulls.
   - `align_date_text(source, output) -> tuple[DataFrame, DataFrame]`: returns copies, never mutates the callers' frames. A source column of text dtype with a format, or a source column already `datetime64`, is converted in both frames with that format (`ISO8601` for an already-datetime source). Output cells that do not parse become null.
   - The profiler's own `sniff_dates` and `_coerce` (0.7 rule, no format) do not change, so profile output (`date_min`, `date_max`, `invalid_count`) stays byte-identical.
2. Fidelity: `compute_quality_report` (`decoy_engine/quality/report.py:140`) calls `align_date_text` before it snapshots the two frames. A broken date column now has source kind `datetime` and output kind `empty` with a 100 percent null rate: `kind_drift` and `null_drift` fail and name the column, the column method is `kind_mismatch`, and the score is never 1.000. A mask run whose date column keeps date strings scores on dates, not lengths.
3. Value-access verdict, in `decoy_engine/generation/statistical/_spec.py`, exported from `decoy_engine.generation.statistical`: `statistical_value_access(snapshot, column) -> Literal["open", "opt_in", "withheld"]`. `withheld` is exactly the condition on which `_refuse_withheld_values` raises for a plain column (no `condition_on`, not DP verified, no restored numeric shape); `opt_in` is exactly the condition of the `STATISTICAL_REAL_CATEGORIES_NOT_ALLOWED` refusal (`_spec.py:470`). Both refusals call the shared decision, so the rule exists once. Messages and codes do not change.

### G3, engine snapshot (fixes R1 for flagged positive numerics that are not keys)

For a flagged numeric column (`Rule.COARSE_RANGE`), when every finite cell is greater than 0, the lower edge of the one coarse bin is `max(grid lower edge, 0)`. Zero is not a cell, so the edge reveals the sign only. When the smallest cell is 0 or negative, nothing changes. `_coarse_domain` (`_snapshot_values.py:107`) keeps its fallback.

### G1, CLI scaffold (fixes R1, R2, R4 for new scaffolds)

`decoy init <csv> --preset generate` picks each column's generator from snapshot facts and the engine verdicts. It never reads a cell value into the config.

1. Dates. `fit_exact_snapshot` gains a keyword-only `detect_dates: bool = False`. When true, after the CSV read it converts each column with a `date_text_format` through `coerce_date_text` (no `read_csv(parse_dates=...)`, which leaves a column with a few bad cells as `object`). `decoy fit --parse-dates` keeps its current path. The scaffold passes `detect_dates=True`. A date column stays `type: statistical`, fitted as `datetime`.
2. Keys. A column whose name is key-like and that is a unique integer becomes `type: sequence`, `start: 1`. Key-like: the lowercased name equals `id` or `key`, or ends in `_id`, `-id`, `_key`, or the name ends in `Id` or `ID` after a letter. Unique: kind `numeric`, an integer dtype, no nulls, `distinct_count == non_null_count == rows`. An all-distinct measure such as `salary` stays statistical.
3. Placeholders, decided before the gate. Each remaining column gets `statistical_value_access`. `withheld` becomes `type: sequence`, `start: 1`, `prefix: "<column>-"`. `opt_in` gets `allow_real_categories: true` with today's NOTICE. The YAML header gets one more NOTICE line naming the placeholder columns (names only) and saying they are placeholders to replace with a generator type.
4. The gate then runs once, as a validator. Any error is `ScaffoldInvalid` as today. The `_OptIn` retry in `_publish_pair` (`_scaffold.py:244`, raised at `_scaffold.py:314`) is removed, because the opt-in columns are known up front.
5. The `init` report line gains a count of columns per type (`sequence 2, statistical 5`).

### G4, CLI pin bump and end-to-end proof

Bump the engine pin to the release that holds G2 and G3, and add the e2e test that replays section 1.

Non-goals: the run card fidelity number and the report number come from different comparisons (snapshot versus CSV). The disagreement (0.66 and 0.788 in the review) is a 1.1 inbox item. Columns whose smallest cell is exactly 0 can still go negative after G3 (known issue). No new generator type. Ambiguous day and month columns stay text (F8).

## 4. Failure modes

- F1: a text column of digits (zip codes, `00123`). `date_text_format` returns `None` for all-digit samples.
- F2: a date column with a few bad cells. Above 95 percent it is a date column; `coerce_date_text` makes the bad cells null, which the snapshot counts as nulls.
- F3: a column name with characters that are not safe in a `prefix`. `safe_dump` quotes the string. Names are not data values.
- F4: an integer key that does not start at 1. The scaffold writes `start: 1`; the real start is a value the snapshot withholds. The user can edit `start`.
- F5: G2 changes report numbers for every date column read from CSV. This is the fix. CHANGELOG names it; quality-report/v1 keys do not change.
- F6: a gate error that the up-front verdicts did not predict. `ScaffoldInvalid`, exit 1, and staged files and new folders are removed as today.
- F7: G3 when the grid lower edge is already 0 or above. `max` leaves it unchanged.
- F8: `03/04/2024`-style columns where every value fits both orders. Ambiguous, so `None`: the column stays text. A day above 12 anywhere in the sample settles it.
- F9: mixed time-zone offsets. `utc=True` parses them to one UTC frame instead of leaving `object` dtype.
- F10: a 10M-row frame. The full-column parse is one vectorized call with an explicit format; only the 200-value sample uses per-value format guessing.
- F11: small files. Every categorical column on a file below K rows (the demo's `gender` included) is withheld and becomes a placeholder. OC-1 states this.

## 5. Defect classes

Project taxonomy (`development-loop.md`):

| # | Class | Applies | Structure that closes it | Proof and the mutation that turns it red |
|---|---|---|---|---|
| 1 | value | Yes: the scaffold and the report must not copy cell values into YAML, notices, logs or report text | G1 reads snapshot facts, verdicts and a format string only; G3 writes 0, never a cell | AT-3 and AT-11 marker tests; mutation: set `start` to the column's real minimum |
| 2 | cleanup | Yes: a failed gate must not leave staged files | one validation on the existing `_publish_pair` staging path | AT-4; mutation: publish before validation |
| 3 | state | N/A: no state machine or concurrency | none | none |
| 4 | route | Yes: `report fidelity`, `run --fidelity` and the CLI null-rate rendering all read date columns | `align_date_text` in `compute_quality_report`, and `null_rate_pairs` (`src/decoy/ui/summary.py:409`) calls the same export | AT-6, AT-12; mutation: align in the report only |
| 5 | referential | N/A: one table; `sequence` keys are not referenced by another table in a scaffold | none | none |
| 6 | untrusted | Yes: date parsing on user text | explicit-format vectorized parse with `errors="coerce"`; per-value guessing on 200 values only | AT-5 rows; mutation: drop the date-part requirement |
| 7 | toctou | N/A: no path checks added | none | none |
| 8 | weak | Yes: a test could check "not 1.000" only | AT-6 requires the output kind `empty`, a 100 percent output null rate and named drift | AT-6; mutation: convert only the source frame |
| 9 | refactor drift | Yes: `_refuse_withheld_values` and the opt-in refusal move onto a shared decision; `utc_naive_datetimes` is split | existing refusal tests and `tests/unit/internal/` pandas_compat tests run unchanged | AT-13; mutation: invert one branch of the shared decision |
| 10 | frozen contract | Yes: snapshot values (G3), quality-report scores (G2), engine pin (G4) | schemas and keys unchanged; CHANGELOG lines; one full engine suite on the G2+G3 stack top and a full CLI suite on G4 | AT-8, AT-9, AT-14 |

Recurring-defect catalog (`catalogs/recurring-defects.md`): #6 no private-module imports applies (the CLI imports only `decoy_engine.profiling` and `decoy_engine.generation.statistical` public names; AT-15); #9 mutations on the final head applies (mutations recorded on the merge head); #11 no raised pins applies to G4 (the pin moves forward to the new release only). Anchored regex (#1) applies to the key-name rule (`fullmatch`). The others (strict wire types, exception context, versioned read models, guard scanners, hidden CI failures, trust class, allowlisted helpers) are N/A: no wire type, read model, scanner or entry point is added, and new raises follow the existing outside-the-except pattern.

## 6. Acceptance tests

Write each test first and record it red at base where it is red.

| AT | Slice | Test | Mutation that turns it red |
|---|---|---|---|
| AT-1 | G1 | Scaffold on the section 1 CSV: `id` is `type: sequence`, `start: 1`; `signup_date` is `statistical` with snapshot kind `datetime`. | Skip `detect_dates` |
| AT-2 | G1 | Scaffold on `decoy demo`'s `customers.csv` exits 0; every withheld column is `sequence` with `prefix: "<column>-"`; `dob` is fitted as `datetime`; the NOTICE names the placeholders. Then `decoy run` on the published config exits 0. Two more CSVs: two withheld text columns; an opt-in column before a withheld column. Both scaffold and run with exit 0. | Restore the gate-retry approach |
| AT-3 | G1 | No cell value from the input appears in the YAML, the NOTICE, stdout, stderr, the `--json` document, captured warnings or log records. A marker in every text column and ids 7001..7200; `7001` appears nowhere. | Write the first id value as `start` |
| AT-4 | G1 | A patched gate that refuses the built config exits 1 with the gate message and leaves no config, snapshot or new folder. | Skip the cleanup |
| AT-5 | G2 | `date_text_format` table test, literal expectations: ISO dates, ISO datetimes with mixed offsets (parsed, naive UTC), `MM/DD/YYYY` with a day above 12, an all-ambiguous `03/04` column (`None`), `DD/MM` with a day above 12, time-only `10:30` (`None`), version strings `1.2.3` (`None`), zip codes as text (`None`), free text (`None`), 96 percent valid (format), 90 percent valid (`None`). | Use `format="mixed"` for the full column |
| AT-6 | G2 | `compute_quality_report` on source ISO dates and output lorem of the same length: output kind `empty`, output null rate 100, `kind_drift` and `null_drift` fail and name the column, method `kind_mismatch`. The input frames are unchanged after the call. Through the CLI, `report fidelity` and `run --fidelity` show the same column result. | Convert only the source frame |
| AT-7 | G2 | Source and output both `DD/MM/YYYY` dates with a day above 12: kind `datetime` on both sides, a datetime method, no drift. | Parse the output without the source's format |
| AT-8 | G3 | `tests/sentry/profiling/test_snapshot_value_registry.py` passes unchanged. New: flagged 1..200 writes `bin_edges[0] == 0`; a flagged column with a 0 cell keeps the old edge; one with a negative cell keeps it. | Clamp when the minimum is 0 |
| AT-9 | G3 | 10,000 rows generated from the G3 snapshot of a flagged positive column: none below 0. | Remove the clamp |
| AT-10 | G4 | E2E replay of section 1 on the bumped pin: `id` unique and positive, `signup_date` values parse as dates in the source's year range, no column of kind `freetext` at 1.000. | Revert the pin |
| AT-11 | G2 | Marker cells in both frames of `compute_quality_report`: no marker in the report JSON, warnings or log records. | Put the first unparsed cell in a warning |
| AT-12 | G1 | The rendered `report fidelity` null rates for the broken date column are 0 and 100, matching `null_drift`. | Leave `null_rate_pairs` on the raw frames |
| AT-13 | G2 | Profile output for a date column is byte-identical before and after G2 (golden from base); every existing `_spec.py` refusal test passes unchanged; `statistical_value_access` table test covers open, opt-in, withheld, DP verified and legacy snapshots. | Route `sniff_dates` through the new format rule |
| AT-14 | G3 | Moved pins listed in section 13 are the only changed expectations in the G3 diff. | Any other edited assertion fails the gate diff check |
| AT-15 | G1 | Sentry: the CLI scaffold modules hold no `to_datetime` call, no `0.95` literal and no `decoy_engine` import of a `_`-prefixed module. | Add a local `to_datetime` |

## 7. Placement

| New file | Directory | Map line | Sits beside |
|---|---|---|---|
| `src/decoy/cli/gen/_scaffold_types.py` (about 110 lines: per-column type choice and key-name rule) | `src/decoy/cli/gen/` | `CODEMAP.md:58` (generation CLI helpers, `src/decoy/cli/gen/_<noun>.py`) | `_scaffold.py`, `_fit.py` |

No new engine module. `profiling/` (29 entries) and `quality/` (25 direct modules) are at the size limit, so the date rule extends `profiling/_date_sniff.py` (50 lines, about +70) and the verdict extends `generation/statistical/_spec.py` (600 lines, about +25). `quality` (tier 3) importing `profiling` (tier 4) is a downward import that `.importlinter` allows; the earlier placement in `quality/` would have made `profiling` import upward. The builder checks engine `CODEMAP.md:53` and the "Where Things Go" table at line 251 and stops if either places these elsewhere.

## 8. Design notes

- One place per fact: the date rule (sample, threshold, digits skip, date-part rule, ambiguity rule) is in `_date_sniff.py` and is exported once. The value-access rule is the shared decision behind both refusals in `_spec.py`. The tz step is the one in `pandas_compat.py`. The CLI copies none of them (AT-15).
- Open/closed: the scaffold's per-column choice is an ordered list of rules in `_scaffold_types.py`. A new rule adds one entry. `build_config` takes a mapping of column name to column spec, with no flag argument.
- The gate validates and no longer drives the choice, so one compile error at a time no longer matters for the scaffold.
- No new structure in G3: one `max` in `_coarse_domain`.

## 9. Files allowed to change and size

- G2 (engine): `profiling/_date_sniff.py`, `profiling/__init__.py` export, `internal/pandas_compat.py` (split the tz step), `quality/report.py` (about +5 at line 140), `generation/statistical/_spec.py`, `generation/statistical/__init__.py` export, tests, `CHANGELOG.md`.
- G3 (engine): `profiling/_snapshot_values.py` (about +5 in `_coarse_domain`), snapshot tests with the moved pins in section 13, `CHANGELOG.md`.
- G1 (CLI): `src/decoy/cli/gen/_scaffold.py` (368 lines, about +10 net after the retry goes), `_fit.py` (208 lines, about +10), new `_scaffold_types.py`, `src/decoy/ui/summary.py` (`null_rate_pairs`, about +3), scaffold and report tests, `CHANGELOG.md`.
- G4 (CLI): the engine pin and every place the repin checklist names, the AT-10 e2e test. G1 calls G2's exports, so G1 and G4 are one CLI PR after the engine release.

## 10. Test selection

- G2: T0 date-sniff, report and `_spec` tests. T1: `tests/**/quality/`, `tests/**/profiling/`, the statistical generator tests, `tests/unit/internal/`, every test that calls `compute_quality_report`, sentries.
- G3: T0 snapshot tests. T1: `tests/sentry/profiling/`, `tests/**/profiling/`, the statistical generator tests.
- G2 and G3 are stacked; one full engine suite runs on the stack top merged into main (frozen snapshot values and report scores), against the saved main baseline. Then the parts merge in order.
- G1 + G4: T0 scaffold tests. T1: `tests/e2e/first_user/test_items_error_envelope.py`, every `scaffold`, `init` and `report` test, the demo e2e, `tests/sentry/`. Full CLI suite on the merge head against the saved baseline (version pin trigger).

## 11. Enumerations

### Exit paths

- `init --preset generate`: exits 0 where it exited 1 for withheld columns (R4); exits 1 as today on any gate error (`_scaffold.py:253`).
- `report fidelity`: exit codes unchanged under the default policy. The default policy fails on the diagnostic only when `thresholds.diagnostic.required` is set (`decoy_engine/quality/policy.py:262-279`), so a broken date column shows as failed drift but still prints "OK no policy violations". OC-5 asks whether that should change.

### Routes

- `decoy init <csv> --preset generate` (`_scaffold.py:221`).
- `decoy report fidelity` and `decoy run --fidelity`, both into `compute_quality_report` (`decoy_engine/quality/report.py:140`), and the CLI null-rate rendering (`src/decoy/ui/summary.py:409`).
- `decoy fit`: unchanged (`--parse-dates` path).

### FK shapes

N/A: the scaffold builds one table and writes no `reference` columns.

### Fields

- Scaffold YAML: `type: sequence`, `start`, `prefix` per chosen column; `allow_real_categories` as today; one new NOTICE header line.
- Snapshot: `stats.bin_edges[0]` and `stats.min` for flagged positive columns (G3).
- quality-report/v1: per-column `method`, `similarity`, the `kind_drift` and `null_drift` entries for date columns (G2). No new keys.

### Output surfaces

- `init` stdout and `--json` (type counts), the YAML header.
- `report fidelity` human, markdown, HTML and `--json` output, including rendered null rates.
- The snapshot file written by `fit` and `init`.

## 12. Reuse inventory

`fit_exact_snapshot` (`src/decoy/cli/gen/_fit.py:65`), `_publish_pair` staging, the `sequence` type and its options (`decoy_engine/config/_generate_options.py:284`), `profiling/_date_sniff.py` sampling, `utc_naive_datetimes` tz rule (`internal/pandas_compat.py:84`), `_refuse_withheld_values` and the opt-in refusal (`_spec.py:240`, `_spec.py:470`), `compute_quality_report`, `kind_drift` and `null_drift`, `null_rate_pairs`, the snapshot value registry sentry, `notice_for` for the header text style.

## 13. Frozen contracts

`quality-report/v1` schema (keys unchanged, values change for date columns), the snapshot schema (unchanged; values change for flagged positive columns), profile output (unchanged, AT-13), the `init` `--json` document (gains a type count member; the builder checks the release-freeze shape fixture and records any change in the PR), the engine pin (G4). CHANGELOG `Changed` lines in both repos.

Moved pins in G3 (the only expectation edits allowed): `test_a_float_rule_would_have_written_the_real_extremes` in `tests/unit/profiling/test_snapshot_values.py` ([-10, 20] to [0, 20]) and the constant-7 case in the same file. The builder lists any other moved pin in the PR and the gate checks each one.

## 14. Owner calls

- OC-1: the placeholder for a withheld column. Default: `sequence` with `prefix: "<column>-"` and a NOTICE. On a file below K rows, every categorical column (the demo's `gender` too) becomes a placeholder. Alternative: `faker` chosen from the column name, which the owner turned down for auto-classification on 2026-11-05 (disguises are presets).
- OC-2: a key-named unique integer becomes `sequence` starting at 1. Default: yes, with the key-name rule so measures stay statistical. Alternative: uniqueness alone, which turns small all-distinct measures into 1..N.
- OC-3: `kind_mismatch` columns stay out of the overall score and show only as drift. Default: keep. Alternative: count them as 0, which lowers many existing mask-report grades.
- OC-4: run card versus report fidelity disagreement goes to the 1.1 inbox. Default: yes.
- OC-5: should a failed `kind_drift` fail the default fidelity policy? Default: no change in this row (1.1 inbox). Alternative: make the diagnostic required by default, which can turn existing report runs into exit 4.

## 15. Slices

| Slice | Repo | Size | Depends on | Test depth |
|---|---|---|---|---|
| G2 | engine | about 110 source lines, 200 test lines | none | T1; full engine suite on the stack top |
| G3 | engine | about 5 source lines, 60 test lines | stacked on G2 | T1; shares the stack-top full suite |
| G1 + G4 | CLI, one PR | about 140 source lines, 260 test lines | engine release with G2 and G3 | T1, full CLI suite (pin) |

No open PR in either repo touches `_scaffold.py`, `_fit.py`, `quality/report.py`, `_date_sniff.py`, `_spec.py` or `_coarse_domain` (checked with `gh pr list` on 2026-11-25). Engine #799 routes profile source reads; it does not touch these files.

## 16. Pre-mortem

- The builder makes AT-6 pass by special-casing lorem text in `_freetext_similarity`. AT-5 and AT-7 need the date rule itself.
- The builder uses `format="mixed"` for the full column because it passes the happy path. AT-5 time-only, version and ambiguity rows and the AT-5 mutation catch it.
- The builder keeps `read_csv(parse_dates=...)`. AT-1 with a 96 percent valid column catches it.
- The builder clamps every coarse edge to 0. AT-8 keeps the negative case.
- The builder reads the first id from the CSV to set `start`. AT-3 uses ids 7001..7200.
- The builder edits the registry sentry or other pins. AT-8 and AT-14.
- The builder copies the withheld rule into the CLI. AT-15 and the shared engine export.
- G1 merges before the engine release. G1 and G4 are one PR.
