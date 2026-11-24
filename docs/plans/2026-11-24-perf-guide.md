Status: plan

# PERF-GUIDE: one scripted benchmark of the whole flow, published on /how-it-works

Owner: Cam. Author: Opus plan agent. Date: 2026-11-24. Revision 1. Roadmap row: PERF-GUIDE (`docs/roadmap/groups/release.md:27`, owner 2026-11-23, V1 release effort). Ordering from the row: after the final engine performance work, before row 94 (CLI-REL).

Rules consulted: dev-rules `README.md`, `00-universal.md`, `development-loop.md` (PLAN, Proportion), `risk-and-exceptions.md`, `performance.md`, `testing.md` (Rules, Test depth), `reuse-first.md`, `proportionality.md`, `architecture.md` (Layout), `cross-cutting-concerns.md`, `release-and-rollback.md`, `documentation.md`.

Risk: R2 for build slices S1 to S4. They add new tooling, a public page that states numbers, and a data file shape on the site. S5 is R3: it spends money on one GCP VM and it publishes a consequential public claim. So S5 needs owner approval right before the cloud run and again before the page goes live. Plan review: one Codex review of this plan. Code gate per slice: Codex for S1 and S3; Codex then Dennis for S2 and S4. Tests: T0 per edit, T1 per commit. No slice changes shipped product code, so no full-suite trigger applies.

Repos: CLI (`decoy-data/decoy`) for the harness, the records and the publisher. Web (`decoy-data/decoy-web`, local `/home/cam/vscode/decoy-site`) for the page. The engine gets no change.

## 1. Problem

The Performance section of `/how-it-works` (`decoy-site/src/how-it-works.njk`, section `id="performance"`) renders from `src/_data/performance.json`. Today that file has `status: pending_benchmarks`, every cell is null, and the 100M cells carry `projected: true`. The caption says "100M is a linear projection from the measured sizes". So the page has no numbers. The one rule it states (projection) also conflicts with the owner's intent that the numbers come from real runs of the release build.

A user who asks "how long will 10M rows take, and what box do I need" has no answer. No harness times the whole flow (source read to delivered output) of the shipped CLI, and no record of such runs exists.

## 2. Pinned guarantee

Every number in the Performance section comes from a recorded run of the release build of `decoy run`. The run used a stated machine class and the default route, and it passed the correctness guard. No number is projected, extrapolated or copied from a dev build. A cell with no such run says "Not measured". A cell whose run failed on that class says "Needs a bigger box".

## 3. Non-goals

- No engine or CLI product change. A slow result is a finding for the engine roadmap, not work in this row.
- No per-strategy or per-format micro benchmarks. The engine bench tools (`scripts/native-baseline/`, `scripts/fk-scale/`) keep that job.
- No change to `/proof` or to the engine `docs/proof-manifest.json`. A later row may link them to the perf records.
- No benchmark of the platform, of DP fit, or of `decoy scan` alone. The prior site plan listed Scan and DP fit rows. The owner row asks for mask and generate, with and without subset and pre-scan, so the page has those and nothing else. The current five-operation data shape goes away.
- No CI job runs the benchmark. A person runs it by hand on chosen hosts. CI runs only the unit tests and the site data check.
- No census, baseline or allowlist raise in any slice.

## 4. Established solutions

Search run: hyperfine and pyperf documentation (benchmark method), TPC-H and TPC-DS specifications (whole-flow benchmark with a data generator and scale factors), Linux cgroup v2 documentation and `systemd.resource-control` (`MemoryMax`, `AllowedCPUs`), psutil documentation (process tree memory), and in-codebase search of both repos and decoy-site for bench, perf, proof and how-it-works work.

| Source | What we take |
|---|---|
| hyperfine, pyperf (warmup, repeated runs, median and spread, recorded environment) | One warmup run that does not count, then N measured runs. Report the median and the min to max range. Record host, OS, CPU model, versions and commands with every run. |
| dev-rules `performance.md` | Define workload, correctness guard, baseline, warmup, variance and resource budget. Report throughput with the resources used and the correctness result. |
| TPC-H / TPC-DS (fixed data generator, fixed scale factors, timed run from load to result) | A deterministic generator with a seed and fixed scale points (1M, 10M, 100M rows). The timed unit is the whole user command, not an inner function. |
| cgroup v2 through `systemd-run --scope -p MemoryMax= -p AllowedCPUs=` | A machine class is enforced by a cap, not assumed. The engine already reads its cgroup quota and CPU affinity (`decoy_engine/execution/pipeline/_host.py`, `detect_usable_cpus`), and the CLI's `auto` threads and memory come from it (`src/decoy/_resources.py`). So a capped run shows what a user with that box gets. A run that finishes under a 16 GB cap shows that the flow fits in 16 GB. |
| psutil process tree sampling; `getrusage` max RSS (as in GNU `time -v`) | Peak memory is the sampled sum of RSS over the `decoy` process tree. The engine can start an isolated child process, so one process's max RSS undercounts. The child's `ru_maxrss` is kept as a cross check. psutil is already in `requirements-dev.lock`. |
| Prior plan: decoy-site `docs-src/docs/plans/2026-10-24-how-it-works-performance-matrix.md` (Codex draft, not reviewed) | Its honesty rules: no extrapolation, "Not measured", date, hardware, version and route on every cell, a link to the record. Also 5 repetitions at 1M and 10M and 3 at 100M, one site data file with a provenance check, and owner approval before cloud runs. We drop its Scan and DP fit rows. We also move its record folder from the engine to the CLI repo, because the release build is the CLI. |

Reuse in this repo:

- `tests/e2e/run_stream/_perf_driver.py`: one `decoy run` per child process, with `{exit, seconds, peak_rss}` output.
- `scripts/release/record_smoke.py` with `packaging_tools/candidate.py` (`read_candidate`): an append-only record tied to a release candidate. The bench record checks the installed CLI version against the candidate the same way.
- `scripts/qa/corpus/shapes.py`: the column mix of `single` and `parent_child` is the model for the fixture schema. The QA generator itself is not reused. It builds Python lists in memory and renders whole files, which does not scale to 100M rows.
- `decoy run --result PATH`: the run result document gives `Timings.phases`, `Route` (execution mode, native state, chunked) and `ProducerInfo` (CLI, engine and registry versions). The harness reads these and adds no phase timer of its own.

Custom code that remains: the fixture writer (no maintained generator produces this schema in row-group chunks with a fixed seed), the guard, the record writer and the publisher. Each is small and specific to this row.

## 5. Behavior

### 5.1 Workload

Fixture data. It is deterministic: seed `20261124`, and the same seed and size give the same bytes.

- `customers`: N rows, 12 columns. `customer_id` (int64, unique), `first_name`, `last_name`, `email`, `phone`, `ssn` (string), `street`, `city`, `postcode` (string), `birth_date` (date32), `balance` (float64), `status` (string, 5 values). Values come from fixed word lists and the seeded NumPy generator. About 5% nulls in `phone` and `street`.
- `orders`: N rows, 6 columns. `order_id` (int64, unique), `customer_id` (int64, a foreign key to `customers`; every value is present in the parent), `order_date` (date32), `amount` (float64), `channel` (string), `note` (short free text; about 1% of rows contain an email, so the pre-scan finds something).
- Formats: Parquet (Snappy, row groups of 1M rows), and plain CSV for the CSV scenario. The writer emits one row group at a time, so its memory does not grow with N.

Scenarios. Each is one `.decoy` pipeline that passes `decoy validate`.

| Id | Flow | Sizes | Notes |
|---|---|---|---|
| MASK | `customers` Parquet in, Parquet out, the default mask for each column (name, email, phone, ssn, address parts, date shift on `birth_date`, numeric noise on `balance`) | 1M, 10M, 100M | The headline row |
| MASK-SCAN | MASK plus a regex pre-scan before the run (`pre_scan` / `scan before(regex)`) | 1M, 10M, 100M | Needs PRE-SCAN-RUN (CLI run-start step) merged. Until then the cells are "Not measured" |
| SUBSET-MASK | `customers` and `orders`; sample 10% of `customers` by `customer_id`; follow `orders.customer_id -> customers.customer_id` downward; mask both; Parquet out | 1M, 10M, 100M (N per table) | Output is about 10% of input. The table shows input rows and output rows |
| MASK-CSV | MASK with CSV in and CSV out | 1M, 10M | The common second format. 100M CSV needs about 3 times the disk of Parquet and adds little |
| GENERATE | Generate N rows of the `customers` schema from column specs, Parquet out | 1M, 10M, 100M | Subset and pre-scan do not apply, because there is no source data |

N is the row count of each source table, or of the generated table. Rows per second is input rows (sum over source tables) divided by wall time. For GENERATE it is output rows.

### 5.2 Machine classes

| Class | Cores | RAM | How it is applied |
|---|---|---|---|
| Small | 4 | 16 GB | A cap on a bigger Linux host, or a host of that size |
| Medium | 8 | 32 GB | A cap on a bigger Linux host, or a host of that size |
| Large | 16 | 64 GB | One GCP VM (for example n2-standard-16 with pd-ssd), no cap |
| Laptop | 10 (M4) | 16 GB | The Mac mini as it is, no cap (macOS has no cgroup). Shown as its own column |

A class run is valid only when one of these holds. `host.json` records which.

1. The host's real cores and RAM equal the class.
2. A cgroup cap was applied (`systemd-run --scope -p AllowedCPUs=... -p MemoryMax=...`, as root or with user delegation), and the harness read the cap back inside the scope before the run started.

If neither holds, the harness refuses the class (exit 2) and writes nothing. The harness passes no `--threads` or `--max-memory` flag, and it clears `DECOY_THREADS` and `DECOY_MAX_MEMORY` and uses an empty `DECOY_HOME`. So each run uses `auto`, as a user with that box would.

The harness records the disk (device type, filesystem). Source and output are on the same local disk. The harness does not drop the page cache (that needs root, and users rarely run cold). The warmup run reads the same files, so every measured run has a warm cache. The page says so.

### 5.3 The harness

`python scripts/bench/run.py --class medium --scenario MASK --rows 10M --reps 5 --out <records dir>`:

1. Checks the CLI under test. It runs `decoy --version` from `--decoy` (default: `decoy` on `PATH`). A version with `+` or `.dev`, or an editable install, is a dev build. A dev build runs only with `--provisional`, and every record it writes has `"provisional": true`.
2. With `--candidate <dir>`, checks that the version equals the candidate's version through `packaging_tools/candidate.py` (`read_candidate`). A record that is not provisional requires `--candidate`.
3. Generates the fixture at the given size if it is missing (`scripts/bench/fixtures.py`), and checks its manifest (row counts, seed, generator version, sha256 of each file).
4. Writes the scenario pipeline into a new run folder and runs `decoy validate` once. Then it does one warmup run and `--reps` measured runs. Each run uses a new empty output folder and runs `decoy run <pipeline> --result <file>`. The harness times the child process with `time.monotonic_ns()`. A psutil sampler sums RSS over the process tree every 100 ms.
5. After each run, applies the correctness guard (5.4). If the guard fails, the run is failed and the cell gets no number.
6. Deletes the run's output folder after the guard, to keep disk use bounded at 100M.
7. Writes the session record (5.5).

### 5.4 Correctness guard (each measured run)

- Exit code 0, and the result document says the run succeeded.
- Output row count per table equals the expected count: N for MASK, MASK-SCAN, MASK-CSV and GENERATE. For SUBSET-MASK, the output counts equal the counts in the result document, and every `orders.customer_id` in the output is present in the output `customers` (checked by streaming the output files with PyArrow).
- Output column names and order equal the expected schema.
- Masking happened. For MASK, MASK-SCAN and MASK-CSV: on a fixed 10k-row sample of `email`, `ssn` and `last_name`, no output value equals the source value in the same row. For SUBSET-MASK, row order changes, so the check is that the source `email` values of the sample do not appear in the output `email` column.
- The result document's `Route` goes into the record. A route other than the default is not a failure (the page shows what users get), but the record and the page details line show it.

### 5.5 Records

One folder per session in the CLI repo: `docs/records/perf-guide/<YYYY-MM-DD>-<class>-<host-label>/`.

- `host.json`: the class and how it was applied (real size, or cap with the values read back), CPU model, cores, RAM, OS, kernel, disk, Python, CLI, engine and registry versions (from `ProducerInfo`), and the candidate id or `provisional`.
- `results.json`: one entry per cell. It has scenario, rows and reps; for each run: wall seconds, sampled peak tree RSS, child `ru_maxrss`, phases from the result document, route and guard result. Then the cell summary: median, min and max wall seconds, median rows per second, and the highest peak memory.
- `fixture.json`: the fixture manifest (seed, generator version, sizes, sha256 per file).
- `commands.txt`: every command run, with the pipeline text.
- `record.md`: a short summary rendered from the JSON by `scripts/bench/record.py`, with `Status: record`.

Records are append-only: the writer refuses a folder that exists. Fixture data and outputs are never committed.

### 5.6 Site data

`python scripts/bench/publish.py <record folders...> --out performance.json` builds the site file from records only. The file shape (schema version 1):

- `schema_version`, `generated_by` (`decoy scripts/bench/publish.py`), `release_version`, `measured_on` (date range), `status` (`pending` or `published`).
- `classes`: id, label, cores, RAM, how applied, host summary.
- `scenarios`: id, label, description. These come from `scripts/bench/scenarios.py`, the one list of scenarios.
- `cells`: scenario, rows and class, then one of: `{median_s, min_s, max_s, rows_per_s, peak_mem_bytes, route, record}`, `{did_not_complete: true, reason, record}`, or `{not_measured: true}`.
- `record` is the CLI repo path of the record folder and the commit that added it.

`publish.py` refuses (exit 1) when: a record is provisional and `--allow-provisional` is not given; records name two CLI versions; a cell has a failed guard; a cell has fewer reps than the rule (5 at 1M and 10M, 3 at 100M). With `--allow-provisional` the output has `status: pending`.

### 5.7 The page

S4 replaces the Performance section in `decoy-site/src/how-it-works.njk` and the shape of `src/_data/performance.json`:

- A short intro: what was measured (the whole `decoy run`, source read to written output, warm cache, default settings), the release version, the dates, and a link to the records.
- "Pick a box": for each scenario and size, the smallest class that completed, and its median time. This is the box-size answer the row asks for.
- One table per scenario: rows (1M, 10M, 100M) by class. Each cell shows median time and rows per second, with peak memory and route in a details line.
- "Not measured" for a cell with no run, and "Needs a bigger box" for a run that did not complete on that class. No projected values, no `projected` field, and no "linear projection" caption.
- With `status: pending`, a notice says the numbers are preview data from a dev build, not release numbers.
- It uses the site's existing table styles. Cam reviews the section live before merge.

The site gets a perf data check, `scripts/check-performance.mjs`, called from `check:site`:

- The data file matches schema version 1 and has `generated_by`.
- No key named `projected`, `extrapolated` or `estimate` anywhere in the file.
- Every measured or did-not-complete cell has a `record` with a path and a commit, and `release_version` is set.
- `status: pending` fails a production build (the switch the existing docs gate uses) and passes a preview build.
- The built HTML of the section contains no "projection" or "projected".

## 6. Failure modes

| Failure | Handling |
|---|---|
| Class cap cannot be applied or read back | Refuse the class, exit 2, write no record |
| Dev build used for a release record | Refused unless `--provisional`. The publisher refuses provisional records unless `--allow-provisional`. The site refuses `pending` in production |
| Candidate version differs from the installed CLI | Refuse, exit 2 |
| A run exits non-zero, or the cap kills it (OOM) | Record the run as failed with its exit status or signal. The cell for that class is "did not complete", which is useful box-size data. The page shows "Needs a bigger box" |
| A run takes more than 2 hours | The harness stops it and records "did not complete in 2 h" |
| Guard fails (wrong rows, unmasked value, broken FK) | Run failed, the cell gets no number, and the harness prints the guard name. This is a product bug: open a QA finding and do not publish that cell |
| Disk too small at 100M | Before each scenario the harness checks free space against 3 times the fixture size, and refuses with a clear message |
| High variance (max over min above 1.5 in a cell) | Recorded and flagged in `record.md`. S5 reruns flagged cells once before publish |
| Fixture bytes differ from the manifest | Refuse. Regenerate with `--force` |
| PRE-SCAN-RUN not merged by S5 | MASK-SCAN cells are "Not measured", and the intro says pre-scan numbers come in a point release. The row is not blocked on it. The plan does not time `decoy scan` plus `decoy run` as a stand-in, because that is a different flow |
| Engine performance work lands after S5 | The numbers are stale. S5 runs on the release candidate that row 94 ships. A later engine change means a rerun of S5, one command per class |
| Mac has no cgroup | The Laptop class is the real machine with no cap, and the record says so |

## 7. Acceptance tests

Unit tests in `tests/unit/bench/` (T0 and T1, no large data):

- AT-1 Fixture determinism: the same seed and N (10k) give the same sha256 for every file, twice. A different seed gives different bytes. With a 1k row group size and 3 row groups, the writer never holds more than one row group (checked through an injected writer that records batch sizes).
- AT-2 Fixture shape: schema and types as in 5.1; every `orders.customer_id` is in `customers`; null rates within 1 point of 5%; about 1% of notes contain an email.
- AT-3 Scenario pipelines: each pipeline passes `decoy validate` on a 10k fixture (e2e through the dev CLI). MASK-SCAN is skipped with a stated reason until PRE-SCAN-RUN merges.
- AT-4 Dev build check: a fake `decoy --version` that returns `1.0.0+local` or `1.0.0.dev3` is refused without `--provisional` and accepted with it, and the record says provisional.
- AT-5 Candidate check: a candidate dir with version 1.0.0rc1 and a CLI that reports 1.0.0rc2 is refused.
- AT-6 Class cap: with a fake `/proc/self/cgroup` and cgroup tree (as the engine's `_host.py` tests use), no cap on a host bigger than the class is refused; the cap present is accepted and its values recorded.
- AT-7 Timing, memory and child control: a fake child (a Python script that sleeps 0.3 s and starts a grandchild that holds 50 MB) gives a wall time of at least 0.3 s, a sampled tree peak of at least 50 MB, and a recorded child `ru_maxrss`. With `DECOY_THREADS=1` set in the harness environment, the child does not see it. On timeout, the grandchild is gone after the kill.
- AT-8 Guard: a fake output with one row missing, one unmasked email, or one orphan `orders.customer_id` each fails the guard by name. A correct output passes.
- AT-9 Record writer: writes the five files, refuses an existing folder, and renders `record.md` from the JSON with `Status: record`. No fixture value (a sample of 100 `email` and `ssn` values) appears in any record file, including after a failed guard.
- AT-10 Publisher refusals: a provisional record without the flag, two CLI versions, a failed guard, and too few reps each exit 1 with a named reason. Seeded mutation: remove the reps check and AT-10 fails.
- AT-11 Publisher output: from two fixed record folders, the output equals a golden `performance.json`. Cells with no record are `not_measured`. An OOM run gives `did_not_complete`.

Site tests (S4, in decoy-site, through `npm run check`):

- AT-12 The data check passes the S4 sample data (`status: pending`) in a preview build and fails it in a production build.
- AT-13 A data file with a `projected` key, a file without `generated_by`, or a measured cell without `record` each fails the check (fixture files in the site's existing `scripts/run-fixtures.mjs` setup). Seeded mutation: remove the `record` check and AT-13 fails.
- AT-14 The built section has no "projection" text, shows "Not measured" for empty cells, and its table headers have `scope` set.

S5 evidence (R3), in `docs/records/<date>-perf-guide-release.md`:

- AT-15 Records exist for every scenario, size and class in 5.1 and 5.2, each one measured, did-not-complete or not-measured with its reason. All are on one candidate version, and all measured runs passed the guard.
- AT-16 Rerunning one 1M cell on the same host gives a median within 10% of the recorded one (a repeatability check, once per host).

## 7a. Defect classes

| # | Class | Applies | Structure | Proof (mutation) |
|---|---|---|---|---|
| 1 | value | Yes: a record or the site file must not carry source values. Fixtures are synthetic, and records hold counts, times and versions only. The guard compares values in memory and records only the guard name and pass or fail | record schema has no value field; guard output is a name | AT-8, AT-9 (mutation: write the failing value into the record, AT-9 asserts no fixture value in any record file) |
| 2 | cleanup | Yes: 100M outputs fill the disk; a killed run leaves a child process | output folder removed after each guard; the child is started in its own process group and the group is killed on timeout or Ctrl-C | AT-7 (mutation: kill only the child, the grandchild stays and the test fails) |
| 3 | state | Yes: environment and settings leak into a run (`DECOY_THREADS`, `DECOY_MAX_MEMORY`, `settings.json`) | the harness builds the child environment from an allowlist and an empty `DECOY_HOME` | AT-7 (mutation: pass `os.environ` through; the test sets `DECOY_THREADS=1` and asserts the child does not see it) |
| 4 | route | Yes: a cell measured on a non-default route would mislead | route recorded per run, never forced; shown on the page | AT-11 (route carried into the site file) |
| 5 | referential | Yes: SUBSET-MASK output must keep every order's customer | FK check in the guard | AT-8 orphan case |
| 6 | untrusted | N/A: the harness runs only the `decoy` the operator names, on synthetic data, on hosts we own. Records are written by our own tool | none | none |
| 7 | toctou | Low: the fixture could change between manifest check and run. Fixtures are written once by the harness on our own disk | manifest checked before each scenario | AT-1 |
| 8 | weak | Yes: a publisher or site check that accepts a bad file would publish a false claim | seeded mutations on the reps check and the `record` check | AT-10, AT-13 |

## 8. Design notes

- Choke point: `publish.py` is the one producer of the site file, and `check-performance.mjs` is the one gate on it. The page never reads records directly, and nobody edits `performance.json` by hand. Guard: the check refuses a file without `generated_by` or a cell without `record` (AT-13). Mutation that must turn it red: drop the `record` check.
- One place per fact: the scenario list and its expected rows and schema live in `scripts/bench/scenarios.py`. The harness, the guard and the publisher read it. The site reads scenario labels from the published file, not from a second copy.
- The harness drives the CLI as a user does: a subprocess on an installed `decoy`. So the numbers include process start, imports, validation and the write. That is the flow the row asks for.
- Wall time comes from the harness; phases come from the result document. The page shows wall time only. Phases stay in the record for engine work.
- The memory a user needs is the class (the cap the run fit in). The sampled peak is a guide.
- Route: the V1 default is the fast path (owner 2026-11-22). The harness never forces a route. If the default for a scenario is not native, the record and the details line say so.
- Run count: 4 scenarios at 3 sizes and MASK-CSV at 2 sizes is 14 cells per class. With the warmup, that is 6 runs per cell at 1M and 10M and 4 at 100M. The Large class runs all 14 cells. Small, Medium and Laptop run every cell; a 100M cell that does not fit is a did-not-complete result, which the page needs.
- Design principles: none beyond the above. The modules are direct scripts with no new abstraction.

## 9. Placement

New CODEMAP row (S1): "Benchmark tooling (not shipped)": `scripts/bench/`, one module per concern, tests in `tests/unit/bench/`, imports no private product module (the same rule as the "QA tooling (not shipped)" row and `scripts/qa/`). Records go in `docs/records/perf-guide/`, under the existing "Roadmap, plans, records" row.

| File | Directory and map line | Beside | Lines (est.) | Slice | Consumer |
|---|---|---|---|---|---|
| `scripts/bench/__init__.py` | new row "Benchmark tooling" | `scripts/qa/` | 1 | S1 | package |
| `scripts/bench/fixtures.py` (schema, chunked writer, manifest, entry point) | same | `scripts/qa/corpus/generate.py` | 300 | S1 | `run.py` (S2) |
| `scripts/bench/scenarios.py` (pipeline texts, expected rows and schema) | same | | 200 | S1 | `run.py`, `_guard.py` (S2), `publish.py` (S3) |
| `scripts/bench/_measure.py` (child run, timer, sampler, class caps) | same | `tests/e2e/run_stream/_perf_driver.py` | 260 | S2 | `run.py` |
| `scripts/bench/_guard.py` | same | | 180 | S2 | `run.py` |
| `scripts/bench/record.py` (record schema, writer, `record.md`) | same | `scripts/release/record_smoke.py` | 220 | S2 | `run.py`, `publish.py` |
| `scripts/bench/run.py` (entry point, version and candidate checks, loop) | same | | 200 | S2 | person running S5 |
| `scripts/bench/publish.py` | same | | 250 | S3 | site file (S4, S5) |
| `tests/unit/bench/test_*.py` | "Benchmark tooling" tests | `tests/unit/qa/` | 600 total | S1 to S3 | |
| `docs/records/perf-guide/<session>/` | "Roadmap, plans, records" | `docs/records/` | data | S2, S5 | `publish.py` |
| decoy-site `src/how-it-works.njk` (section only), `src/_data/performance.json`, `scripts/check-performance.mjs`, `package.json` (`check:site`) | site layout | `scripts/check-claims.mjs` | 120 + data + 150 | S4 | the page |

Every module stays under 600 lines. New public names: none in the product. The scripts expose only their command lines.

## 10. Slices

| Slice | Content | Repo | Risk | Size | Depends on |
|---|---|---|---|---|---|
| S1 | Fixture generator, five scenario pipelines, CODEMAP row; AT-1, AT-2, AT-3 | CLI | R1 | 1 day | none |
| S2 | Harness: version and candidate checks, class caps, timer and sampler, guard, record writer; AT-4 to AT-9; one provisional 1M session on the Dell or Mac committed as a sample record | CLI | R2 | 1 day | S1 |
| S3 | Publisher with refusals and golden output; AT-10, AT-11; a provisional `performance.json` from the S2 sample | CLI | R2 | 0.5 day | S2 |
| S4 | Page section, new data shape (the S3 provisional file, `status: pending`), site data check; AT-12 to AT-14; live review by Cam | web | R2 | 1 day | S3 output format |
| S5 | Release run: Small and Medium on the Dell (or a capped GCP VM), Laptop on the Mac, Large on one GCP VM; records committed; publish; set `status: published`; AT-15, AT-16 | CLI, web | R3 | about 1 day of runs | release candidate for row 94, final engine perf work, S1 to S4; PRE-SCAN-RUN for MASK-SCAN cells |

S1 to S4 can build now. S5 waits for the release candidate. S4 is web work during the web pause. It is allowed because PERF-GUIDE is an owner row in the V1 release effort.

Recovery for S5: the page change is one data file and one template section. If a published number is wrong, revert the decoy-site commit (the page goes back to `pending`) and rerun the cell.

## 11. Owner gates

- Before the GCP run in S5: a Slack ping with VM type, disk, expected hours and a cost estimate, and owner approval (cloud spend; one VM at a time).
- Before the page goes live: the owner reviews the S5 numbers and the page (consequential public claim).
- Open choice, default applies if no answer: class sizes. Default: Small 4 cores and 16 GB, Medium 8 and 32 GB, Large 16 and 64 GB, Laptop the Mac M4 with 16 GB.
