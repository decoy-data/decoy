Status: plan

# GEN-SCAFFOLD-FIDELITY G1-G4: the generate scaffold keeps ids and dates, and fidelity stops scoring broken dates 1.000

Owner: Cam. Author: Opus plan agent. Date: 2026-11-25. Revision 1. Source: `docs/roadmap/inbox.md` item "carried from CLI #321, outside review: broken today, a generated sequential id came out negative and a date column came out as lorem text; the fidelity report scored that column 1.000", and the second half of EXAMPLES-FIX ("`decoy init --preset generate` fails on the demo's own CSV"). Repos: decoy (CLI) and decoy-engine. Branch: docs/plans-inbox-triage-1125 (CLI). Read at CLI `origin/main` `fffca916` and engine `origin/main` `2b8a47fbe`.

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md` (PLAN, Proportion, Design notes, Placement), `bugfix.md`, `reuse-first.md`, `api-and-compatibility.md`, `testing.md` (Test depth), `catalogs/recurring-defects.md`.

Classification: 1.0 blocker. The documented generate flow (`decoy init source.csv --preset generate`, then `decoy run`) gives wrong output on a plain CSV, and the fidelity report calls one broken column perfect. On CSVs with a unique text column (the demo's `customer_id`) the scaffold fails outright. Both are function breaks under the V1 bar. Risk: R2. It changes snapshot values for one class of flagged column and changes quality-report scores for date columns.

## 1. Reproduction and root cause

Reproduced on the Mac node with `vm-run` (CLI `fffca916`, engine pin at that commit). Input: 200 rows, `id` 1 to 200, `signup_date` ISO dates, `amount` 5 to 500, `status` in a, b, c. Steps: `decoy init data.csv --preset generate -o gen/pipeline.yaml --yes`, add `allow_real_categories: true` to `status`, `decoy run gen/pipeline.yaml`, `decoy report fidelity data.csv <output> --generate`.

Observed: 61 of 200 generated `id` values were negative and 5 were duplicates. Every `signup_date` was 10 characters of lorem text. The report gave `id` similarity 0.000, `signup_date` 1.000 (method `length_mean_diff`), overall 0.724, grade C, and "no policy violations". On `decoy_demo/customers.csv` the scaffold exits 1: "statistical column 'customer_id': the snapshot withheld the real values ... no values to sample".

Root causes:

- R1, ids. The scaffold turns every column into `type: statistical` (`src/decoy/cli/gen/_scaffold.py:102`). The profiler flags a unique column as value-sensitive, so the snapshot keeps one coarse bin for it. `_grid_edges` (`decoy_engine/profiling/_snapshot_values.py:91`) puts the lower edge one power-of-ten step below the smallest cell, so 1..200 becomes the bin [-1000, 2000]. Sampling uniformly from that bin gives negatives and repeats. A statistical column cannot promise unique values in any case.
- R2, dates. The scaffold calls `fit_exact_snapshot(csv, row_limit=...)` with no `parse_dates` (`_scaffold.py:221`), so ISO date strings stay `object` dtype. With more than `CATEGORICAL_DISTINCT_CAP` distinct values, `_stats_for` (`decoy_engine/quality/snapshot.py:279`) calls the column `freetext`, and the generator writes lorem text of the right length.
- R3, the 1.000. `report fidelity` reads both CSVs with pandas defaults (`read_report_source`, `src/decoy/cli/_sources.py:434`), so source dates and output lorem are both `freetext`. `_freetext_similarity` (`decoy_engine/quality/fidelity.py:510`) compares mean length only, so equal lengths score 1.000. `kind_drift` (`decoy_engine/quality/diagnostic.py:170`) sees freetext on both sides and passes.
- R4, the demo failure. A unique text column is withheld in the snapshot, and the engine refuses a statistical column over withheld text values (`STATISTICAL_SNAPSHOT_VALUES_REDACTED`, `decoy_engine/generation/statistical/_spec.py:294`). The scaffold treats that as a hard failure.

## 2. Established solutions

Searched: how synthesizers pick a generator per column from a sample (SDV `Metadata.detect_from_dataframe` and its `sdtype` of `id` and `datetime`; Gretel and synthpop column typing), and how profilers spot date strings (pandas `to_datetime` with `format="ISO8601"`, ydata-profiling type inference, and the engine's own `profiling/_date_sniff.py`). SDV marks a unique integer or text key as `id` and regenerates it as a key, never from a distribution. It marks a column as `datetime` when its strings parse with one format. This plan follows SDV's rule: unique keys become `sequence`, parseable date columns are fitted as dates. Date detection reuses the engine's sniff threshold and pandas parsing; nothing is hand-written beyond the per-column rule. For the coarse bin, Hundepool et al. (Statistical Disclosure Control, 2012, section 4.2, global recoding) allows a recoded interval to keep a public bound such as zero; the sign of a column is not a cell value.

## 3. Behavior

### G1, CLI scaffold (fixes R1, R2, R4 for new scaffolds)

`decoy init <csv> --preset generate` picks each column's generator from the fitted snapshot's column facts (kind, dtype, counts). It never reads a cell value into the config.

1. Date columns. Before fitting, the scaffold reads the first 200 non-null values of each text column (the same sample size and 0.7 rule as `profiling/_date_sniff.py`, raised to 0.95 for the scaffold) and parses them with `pd.to_datetime(format="ISO8601", errors="coerce")`, then with `format="mixed"`. A column that is not all-numeric text and parses at 95 percent or more is passed in `parse_dates`. It stays `type: statistical`, fitted as `datetime`.
2. Unique integer keys. A column with kind `numeric`, an integer dtype, no nulls and `distinct_count == non_null_count == rows` becomes `type: sequence`, `start: 1`.
3. Unique or withheld text columns. If the gate refuses a column with `STATISTICAL_SNAPSHOT_VALUES_REDACTED`, the scaffold replaces it with `type: sequence`, `start: 1`, `prefix: "<column>-"` and publishes. This uses the same retry as the real-categories opt-in in `_validate_pair` (`_scaffold.py:131`). The YAML header gets one NOTICE line that names these columns (names only) and says they are placeholders to replace with a generator type.
4. Every other column stays `type: statistical`. The real-categories opt-in is unchanged.
5. The `init` report line gains a count of columns per type (`sequence 2, statistical 5`).

### G2, engine fidelity (fixes R3)

`compute_quality_report` finds date columns in the source frame before it snapshots. A source column of text dtype that is not all-numeric text and parses at 95 percent or more (the same rule as G1, in one engine helper) is converted to `datetime64` in the source frame and in the output frame (`errors="coerce"`). Output that does not parse becomes null. The result for a broken date column: source kind `datetime`, output kind `empty` or `datetime` with a null jump. `kind_drift` or `null_drift` fails, the column's method is `kind_mismatch` or a datetime metric, and the score is never 1.000 for lorem text. A mask run whose date column keeps date strings now scores on dates, not lengths.

### G3, engine snapshot (fixes R1 for flagged non-negative numerics that are not keys)

For a flagged numeric column (`Rule.COARSE_RANGE`), when every finite cell is greater than 0, the lower edge of the one coarse bin is `max(grid lower edge, 0)`. Zero is not a cell, so the edge reveals the sign only. When the smallest cell is 0 or negative, nothing changes. `_coarse_domain` (`_snapshot_values.py:107`) keeps its fallback.

### G4, CLI pin bump and end-to-end proof

Bump the engine pin to the release that holds G2 and G3, and add the e2e test that replays the reproduction in section 1.

Non-goals: the run card fidelity number and the report number come from different comparisons (the run card scores against the snapshot, the report against the CSV). The disagreement (0.66 and 0.788 in the review) is a 1.1 inbox item, not this row. Columns whose smallest cell is exactly 0 can still go negative after G3 (known issue). No new generator type. `decoy fit` without the scaffold keeps its explicit `--parse-dates` flag.

## 4. Failure modes

- F1: a text column of numbers (zip codes, `00123`) parses as dates under `format="mixed"`. G1 and G2 skip columns whose values are all digits.
- F2: a date column with a few bad cells. Above 95 percent it is still a date column; the bad cells become null in the fit, which the snapshot already counts.
- F3: a column name with characters that are not safe in a `prefix`. The prefix is a YAML string; `safe_dump` quotes it. Names are not data values.
- F4: an integer key that does not start at 1 (ids 1001..1200). The scaffold writes `start: 1`. The real start is a value the snapshot withholds. The NOTICE does not mention it; the user can edit `start`.
- F5: G2 changes report numbers for every date column read from CSV. This is the fix. The CHANGELOG names it, and quality-report/v1 keys do not change.
- F6: the retry in G1 loops. One retry only: after the replacement, any remaining error is `ScaffoldInvalid` as today.
- F7: G3 when every cell is positive but the grid lower edge is already above 0 (cells 5000..9000 give a lower edge of 0 anyway, or higher). `max` leaves it unchanged.

## 5. Defect classes

| # | Class | Applies | Structure that closes it | Proof and the mutation that turns it red |
|---|---|---|---|---|
| 1 | value | Yes: the scaffold and the report must not copy cell values into YAML, notices or report text | G1 reads snapshot facts and a parse rate only; G3 writes 0, never a cell | AT-3 checks no source cell in the YAML or stdout; AT-8 runs the snapshot registry sentry; mutation: set `start` to the column's real minimum |
| 2 | cleanup | Yes: the G1 retry must not leave staged files | the retry reuses the `_publish_pair` staging path of the opt-in retry | AT-4 checks the folder after a failed retry; mutation: publish before the second validation |
| 3 | state | N/A: no state machine or concurrency | none | none |
| 4 | route | Yes: `report fidelity` and `run --fidelity` both reach `compute_quality_report` | the date rule sits in `compute_quality_report`, the one engine entry | AT-6 checks both routes; mutation: apply the rule in the CLI reader only |
| 5 | referential | N/A: one table; `sequence` keys are not referenced by another table in a scaffold | none | none |
| 6 | untrusted | Yes: date parsing on user text | pandas parsing with `errors="coerce"` on a 200-value sample, then the full column only when the sample passes | AT-5 includes free text, digits and mixed cells; mutation: drop the all-digits skip |
| 7 | toctou | N/A: no path checks added | none | none |
| 8 | weak | Yes: a test could check "not 1.000" only | AT-6 requires `kind_drift` failed and names the method | AT-6; mutation: keep source dates as text |
| 9 | refactor drift | N/A: no refactor; `build_config` gains a per-column choice | none | none |
| 10 | frozen contract | Yes: snapshot values (G3) and quality-report scores (G2) change; the engine pin moves (G4) | schemas and keys unchanged; CHANGELOG lines in both repos; full suites on G3 and G4 | AT-8, AT-9; mutation: clamp edges for unflagged columns too |

## 6. Acceptance tests

Write each test first and record it red at base where it is red.

| AT | Slice | Test | Mutation that turns it red |
|---|---|---|---|
| AT-1 | G1 | Scaffold on the section 1 CSV: `id` is `type: sequence`, `start: 1`; `signup_date` is `statistical`; the snapshot column `signup_date` has kind `datetime`. | Skip the `parse_dates` argument |
| AT-2 | G1 | Scaffold on `decoy demo`'s `customers.csv` exits 0. `customer_id` is `sequence` with `prefix: "customer_id-"`; `dob` is fitted as `datetime`; the header NOTICE names the placeholder columns. | Remove the retry |
| AT-3 | G1 | No cell value from the input CSV appears in the YAML, the NOTICE, stdout or the `--json` document. Use a marker in every text column. | Write the first id value as `start` |
| AT-4 | G1 | A CSV where the replacement still fails (a patched gate that refuses the sequence too) exits 1 with the old error and leaves no config, snapshot or new folder. | Skip the cleanup on the second failure |
| AT-5 | G1, G2 | The date rule as a table test: ISO dates, `MM/DD/YYYY`, datetimes with time zones, zip codes as text, digits-only ids, free text, 96 percent and 90 percent valid columns. Expected verdicts are literals in the test. G1 and G2 call the same engine helper. | Lower the threshold to 0.7 |
| AT-6 | G2 | `compute_quality_report` on source ISO dates and output lorem text of the same length: column method is not `length_mean_diff`, similarity is not 1.0, `kind_drift` or `null_drift` has `passed: false` and names the column. Through the CLI, `report fidelity` and `run --fidelity` show the same column result. | Convert only the source frame and leave the output as text |
| AT-7 | G2 | Source and output both ISO dates (a mask with `date_shift`): kind `datetime` on both sides, a datetime method, no drift. | Convert the output with the source format string only |
| AT-8 | G3 | `tests/sentry/profiling/test_snapshot_value_registry.py` keeps passing unchanged (no written number equals a raw cell). New case: a flagged column 1..200 writes `bin_edges[0] == 0`; a flagged column with a 0 cell keeps the old edge; a flagged column with a negative cell keeps the old edge. | Clamp when the minimum is 0 |
| AT-9 | G3 | Generating 10,000 rows from the G3 snapshot of a flagged positive column gives no value below 0. | Remove the clamp |
| AT-10 | G4 | E2E replay of section 1 on the bumped pin: `id` unique and positive, `signup_date` values parse as dates within the source's year range, report exit 0 with no column of kind `freetext` at 1.000. | Revert the pin |

## 7. Placement

| New file | Directory | Map line | Sits beside |
|---|---|---|---|
| `src/decoy/cli/gen/_scaffold_types.py` (about 110 lines: per-column type choice and the date sample read) | `src/decoy/cli/gen/` | `CODEMAP.md:58` (generation CLI helpers, `src/decoy/cli/gen/_<noun>.py`) | `_scaffold.py`, `_fit.py` |
| `src/decoy_engine/quality/_date_text.py` (about 60 lines: the date rule, used by G2 and exported for G1) | `src/decoy_engine/quality/` | engine `CODEMAP.md:53` (`quality/report.py`, the fidelity report) and the "Where Things Go" table at line 251 | `snapshot.py`, `report.py` |

`profiling/_date_sniff.py` keeps its own 0.7 profiler rule; it imports the parse call from `_date_text.py` so there is one parse function. The builder checks both CODEMAP lines and stops if either map places these elsewhere.

## 8. Design notes

- One place per fact: the date rule (sample size, threshold, the digits skip) lives in engine `quality/_date_text.py` and is exported once (`decoy_engine.quality.date_text_columns`). The CLI calls it; it does not copy the threshold.
- Open/closed: the scaffold's per-column choice is a small ordered list of rules in `_scaffold_types.py`. A new rule adds one entry. No flag argument on `build_config`; it takes a mapping of column name to column spec.
- No new structure in G3: one `max` in `_coarse_domain`.

## 9. Files allowed to change and size

- G1 (CLI): `src/decoy/cli/gen/_scaffold.py` (368 lines, about +30), new `_scaffold_types.py`, scaffold tests, `CHANGELOG.md`. G1 calls the G2 engine helper, so G1 and the G4 pin bump are one CLI PR, after the engine release that holds G2 and G3.
- G2 (engine): new `quality/_date_text.py`, `quality/report.py` (about +10 at line 140), `quality/__init__.py` export, `profiling/_date_sniff.py` (import only), quality tests, `CHANGELOG.md`.
- G3 (engine): `profiling/_snapshot_values.py` (about +5 in `_coarse_domain`), snapshot tests, `CHANGELOG.md`.
- G4 (CLI): the engine pin and every place the repin checklist names, the AT-10 e2e test.

## 10. Test selection

- G1: T0 scaffold tests. T1: `tests/e2e/first_user/test_items_error_envelope.py`, every test that matches `scaffold` or `init`, the demo e2e, `tests/sentry/`, import-impact selection. No full-suite trigger on its own; it rides G4's full suite.
- G2: T0 quality tests. T1: `tests/**/quality/`, every test that calls `compute_quality_report`, CLI-facing engine API tests, sentries. Full engine suite before merge: report scores change for date columns (serialization of a public report).
- G3: T0 snapshot tests. T1: `tests/sentry/profiling/`, `tests/**/profiling/`, the statistical generator tests. Full engine suite before merge: snapshot values change (frozen snapshot surface).
- G4: full CLI suite on the merge head against the saved main baseline (version pin trigger).

## 11. Enumerations

### Exit paths

- `init --preset generate`: exits 0 where it exited 1 for withheld text columns (R4); exits 1 as today when the replacement still fails (`_scaffold.py:131`).
- `report fidelity`: exit codes unchanged; a date column that broke now shows drift, which can turn a `--mode fail` verdict into exit 4.

### Routes

- `decoy init <csv> --preset generate` (`_scaffold.py:221`).
- `decoy report fidelity` and `decoy run --fidelity`, both into `compute_quality_report` (`decoy_engine/quality/report.py:140`).
- `decoy fit`: unchanged.

### FK shapes

N/A: the scaffold builds one table and writes no `reference` columns.

### Fields

- Scaffold YAML: `type: sequence`, `start`, `prefix` per chosen column; new NOTICE header line.
- Snapshot: `stats.bin_edges[0]` and `stats.min` for flagged positive columns (G3).
- quality-report/v1: per-column `method`, `similarity`, and the `kind_drift` and `null_drift` entries for date columns (G2). No new keys.

### Output surfaces

- `init` stdout and `--json` (type counts), the YAML header.
- `report fidelity` human, markdown, HTML and `--json` output.
- The snapshot file written by `fit` and `init`.

## 12. Reuse inventory

`fit_exact_snapshot(parse_dates=...)` (`src/decoy/cli/gen/_fit.py:65`), the opt-in retry in `_validate_pair`, the `sequence` type and its options (`decoy_engine/config/_generate_options.py:284`), `profiling/_date_sniff.py`, `compute_quality_report`, `kind_drift` and `null_drift` checks, the snapshot value registry sentry, `notice_for` for the header text style.

## 13. Frozen contracts

`quality-report/v1` schema (keys unchanged, values change for date columns), the snapshot schema (unchanged; values change for flagged positive columns), the `init` `--json` document (gains a type count member; the builder checks the release-freeze shape fixture and records any change in the PR), the engine pin (G4). CHANGELOG `Changed` lines in both repos.

## 14. Owner calls

- OC-1: the placeholder for a withheld text column. Default: `sequence` with `prefix: "<column>-"` and a NOTICE. Alternative: `faker` chosen from the column name, which the owner turned down for auto-classification on 2026-11-05 (disguises are presets).
- OC-2: a unique integer key starts at 1. Default: yes. Alternative: keep the coarse range and accept repeats.
- OC-3: `kind_mismatch` columns stay out of the overall score (current rule) and show only as drift. Default: keep. Alternative: count them as 0, which lowers many existing mask-report grades.
- OC-4: run card versus report fidelity disagreement goes to the 1.1 inbox. Default: yes.

## 15. Slices

| Slice | Repo | Size | Depends on | Test depth |
|---|---|---|---|---|
| G2 | engine | about 80 source lines, 120 test lines | none | T1, full engine suite |
| G3 | engine | about 5 source lines, 60 test lines | none (parallel with G2) | T1, full engine suite |
| G1 + G4 | CLI, one PR | about 150 source lines, 200 test lines | engine release with G2 and G3 | T1, full CLI suite (pin) |

G2 and G3 can merge in either order and go into one engine release. No open PR in either repo touches `_scaffold.py`, `quality/report.py` or `_coarse_domain` (checked with `gh pr list` on 2026-11-25). Engine #799 routes profile source reads; it does not touch the quality report reader.

## 16. Pre-mortem

- The builder makes the AT-6 test pass by special-casing lorem text in `_freetext_similarity`. AT-7 and AT-5 need the date rule itself.
- The builder clamps every coarse edge to 0, and a flagged column with negative values loses its range. AT-8 keeps the negative case.
- The builder reads the first id from the CSV to set `start`. AT-3 puts a marker in the id column.
- The builder edits the registry sentry to allow 0. AT-8 requires the sentry unchanged.
- G1 merges before the engine release, and the CLI calls a helper the pinned engine lacks. G1 and G4 are one PR.
