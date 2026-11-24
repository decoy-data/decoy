Status: plan

# PERF-GUIDE: one scripted benchmark of the whole flow, published on /how-it-works

Owner: Cam. Author: Opus plan agent. Date: 2026-11-24. Revision 2. Roadmap row: PERF-GUIDE (`docs/roadmap/groups/release.md:27`, owner 2026-11-23, V1 release effort). Ordering from the row: after the final engine performance work, before row 94 (CLI-REL).

Rules consulted: dev-rules `README.md`, `00-universal.md`, `development-loop.md` (PLAN, Proportion), `risk-and-exceptions.md`, `performance.md`, `testing.md` (Rules, Test depth), `reuse-first.md`, `proportionality.md`, `architecture.md` (Layout), `cross-cutting-concerns.md`, `release-and-rollback.md`, `documentation.md`.

Risk: S1 is R1 (synthetic fixtures and pipeline texts, no measurement or publication). S2a, S2b, S3 and S4 are R2: they decide what counts as a measurement and what the public page may show. S5 is R3: it spends money on one GCP VM and publishes a consequential public claim, so it needs owner approval before the cloud run and again before the page goes live. Plan review: one Codex review (rev 1 NO-GO, this is rev 2). Code gate per slice: Codex for S1; Codex then Dennis for S2a, S2b, S3 and S4. Tests: T0 per edit, T1 per commit. No slice changes shipped product code, so no full-suite trigger applies.

Repos: CLI (`decoy-data/decoy`) for the harness, the records and the publisher. Web (`decoy-data/decoy-web`, local `/home/cam/vscode/decoy-site`) for the page. The engine gets no change.

## Revision history

| Rev | Date | Change |
|---|---|---|
| 1 | 2026-11-24 | First plan (head `c721ee6b`) |
| 2 | 2026-11-24 | Codex R1 NO-GO, 15 BLOCK, 3 FIX, 1 V2-LOG. All taken. Release identity now comes from the verified candidate install, not a version string (F1). Site cells carry their raw repetitions and the site check recomputes them (F2). `/cli` loses its copy of the table (F3). S4 ships an empty placeholder, and provisional numbers never reach the deploy input (F4). Scenarios are frozen with exact strategies and a benchmark key (F5). MASK-SCAN needs proof that the scan ran (F6). Subset, mask and generate guards are exact (F7, F8). The result is read through `RunResultRead` from a fresh path (F9). Effective resources come from the child's own `resources` output (F10). Failures use the CLI exit codes and cgroup OOM evidence (F11). Memory labels say what the tool measured (F12). Per-table denominators and bytes are published (F13). A frozen campaign manifest and a no-selection variance rule (F14). Unique attempt ids with create-once publication (F15). Bounded fixture generation and per-device disk preflight (F16). Reuse of `scripts/qa` checks and writers (F17). S2 split into S2a and S2b, placement completed (F18). S5 elapsed time comes from a pilot (F19) |

## 1. Problem

The Performance section of `/how-it-works` (`decoy-site/src/how-it-works.njk`, section `id="performance"`) renders from `src/_data/performance.json`. Today that file has `status: pending_benchmarks`, every cell is null, and the 100M cells carry `projected: true`. The caption says "100M is a linear projection from the measured sizes". `/cli#performance` (`src/cli.njk:249-293`) renders a second table from the same file, with the same caption and a statement that there is no macOS or ARM64 evidence. So neither page has numbers, and the one rule they state (projection) conflicts with the owner's intent that the numbers come from real runs of the release build.

A user who asks "how long will 10M rows take, and what box do I need" has no answer. No harness times the whole flow (source read to delivered output) of the shipped CLI, and no record of such runs exists.

## 2. Pinned guarantee

Every number in the Performance section comes from a complete set of recorded, successful, guarded invocations of the verified release-candidate install of `decoy run`, on a named host under stated limits that the timed process itself reported. The site recomputes every shown number from the raw repetitions in its data file before deploy. No number is projected, extrapolated, selected from a subset of attempts, or taken from a dev build. A cell with no such set says "Not measured" with a reason. A cell whose run was refused for capacity, or killed by a confirmed out-of-memory event, says "Needs more memory" with that evidence. A timeout says "Did not finish in 2 h". Any other failure is "Not measured" with its reason.

## 3. Non-goals

- No engine or CLI product change. A slow result is a finding for the engine roadmap, not work in this row.
- No per-strategy or per-format micro benchmarks. The engine bench tools (`scripts/native-baseline/`, `scripts/fk-scale/`) keep that job.
- No change to `/proof` or to the engine `docs/proof-manifest.json`.
- No benchmark of the platform, of DP fit, or of `decoy scan` alone. The owner row asks for mask and generate, with and without subset and pre-scan. The current five-operation data shape goes away.
- No CI job runs the benchmark. A person runs it by hand on chosen hosts. CI runs the unit tests and the site data check.
- No 100M CSV cell. It is outside the scenario matrix and the page says so.
- No census, baseline or allowlist raise in any slice.

## 4. Established solutions

Search run: hyperfine and pyperf documentation (benchmark method), TPC-H and TPC-DS specifications (whole-flow benchmark with a data generator and scale factors), Linux cgroup v2 documentation (`memory.peak`, `memory.events`, `cpu.max`, `cpuset`) and `systemd.resource-control`, Linux `getrusage(2)`, psutil documentation, and in-codebase search of the CLI, the engine and decoy-site for bench, perf, proof, QA and how-it-works work.

| Source | What we take |
|---|---|
| hyperfine, pyperf | One untimed warmup, then N timed invocations. Report the median and the min to max range. Keep every attempt. Record host, OS, CPU, versions and commands |
| dev-rules `performance.md` | Define workload, correctness guard, warmup, variance and resource budget. Report throughput with the resources used and the correctness result |
| TPC-H / TPC-DS | A deterministic generator with a seed and fixed scale points (1M, 10M, 100M rows per table). The timed unit is the whole user command. The benchmark definition is frozen before any number exists |
| cgroup v2 (`memory.peak`, `memory.events` `oom_kill`), `systemd-run --scope` | A capped run is a run on a named host under stated limits. `memory.peak` of a fresh per-invocation scope is the Linux memory figure, labelled "cgroup memory, includes page cache charged to the run". An `oom_kill` counter delta is the evidence for an out-of-memory kill |
| `getrusage(2)`, psutil | `ru_maxrss` of children is the largest single child, not the tree, and its unit differs by OS. So it is recorded only as a labelled side figure. The portable figure is "highest sampled sum of process RSS, 100 ms interval", with its method, units and missed samples recorded |
| Engine `scripts/fk-scale/_supervisor.py` | An external supervisor that starts the measured process in its own process group and records how it ended. Used as the reference design. It is not imported (private sibling-repo code) |
| Engine `scripts/fk-scale/build_fk_chain.py` | Seeded FK Parquet generation one chunk at a time. The model for the fixture writer |
| Prior plan: decoy-site `docs-src/docs/plans/2026-10-24-how-it-works-performance-matrix.md` | Honesty rules: no extrapolation, "Not measured", date, hardware, version and route on every cell, a link from each number to its exact record field, 5 reps at 1M and 10M and 3 at 100M, 100M runs only on an approved cloud budget. We drop its Scan and DP fit rows and put the records in the CLI repo, because the release build is the CLI |

Reuse in this repo (detail in 9b): `packaging_tools/candidate.py` and `packaging_tools/smoke_install.py` (candidate verify and install), `scripts/release/record_smoke.py` (`check_match`), `scripts/qa/invariants/` (`i1_leaks`, `i2_foreign_keys`, `i4_rows`, `i5_schema`), `scripts/qa/io.py` (`staged_private`, `publish_private_once`, `publish_or_same`), `scripts/qa/repro.py` (process-group timeout pattern), the engine public `RunResultRead`, and the `decoy run --json` `resources` envelope.

Custom code that remains: the chunked fixture writer, the bounded large-scale FK and subset check, the installed-process supervisor and the publisher. Each is specific to this row.

## 5. Behavior

### 5.1 Workload

Fixture data. Deterministic: seed `20261124`. The generator, PyArrow version, compression (Snappy), row-group size (1M rows, 1k in tests), dictionary and statistics settings are pinned in `fixture.json`. The same seed, size and pins give the same bytes, and the harness checks the sha256 of every file on every host.

- `customers`: N rows. `customer_id` (int64, unique, 0..N-1 then a fixed permutation), `first_name`, `last_name`, `email`, `phone`, `ssn`, `street`, `city`, `postcode` (string), `birth_date` (date32), `balance` (float64), `status` (string, 5 values). About 5% nulls in `phone` and `street`. Every `email`, `ssn` and `last_name` value carries a synthetic marker token (`pgmark` plus the row id) that no Faker provider or redaction output can produce. So "source value appears in output" is an exact test, with no false hit from a real surname.
- `orders`: N rows. `order_id` (int64, unique), `customer_id` (int64, every value present in `customers`, a fixed skew so some customers have many orders and some none), `order_date` (date32), `amount` (float64), `channel` (string), `note` (short free text).
- The pre-scan marker for MASK-SCAN goes in `customers.street`: about 1% of rows hold a marker email address (`pgmark<id>@scan.invalid`) inside the street text. MASK-SCAN reads this table and masks `street`, so the scan has a known finding in data it reads (F6).
- The writer produces one row group at a time from the seeded generator. No list or array covers the whole table. Only the files a scenario uses are generated.

Scenarios. Frozen in `scripts/bench/scenarios.py`, the one list. Each is one `.decoy` pipeline. Every pipeline sets `seed 20261124` and `secret ref("env:DECOY_BENCH_MASK_KEY")`. The key is a 32-byte random value made once per campaign, held only in the harness process and passed to the child through that one variable. It is never written to a record (only the reference text is).

Column treatment, the same in every mask scenario:

| Column | Strategy | Parameters |
|---|---|---|
| `customer_id`, `order_id`, `customers` key in `orders` | passthrough (key columns) | none |
| `first_name`, `last_name` | `faker` | `person_first_name`, `person_last_name` |
| `email`, `phone` | `faker` | `person_email`, `person_phone` |
| `ssn` | `redact` | default text |
| `street` | `redact` | default text |
| `city`, `postcode` | `faker` | the address-city and postcode providers named in S1 from `strategy_catalog()` |
| `birth_date`, `order_date` | `date_shift` | `min_days: -30, max_days: 30` |
| `balance`, `amount` | `bucket_perturb` | fixed buckets and noise named in S1 |
| `status`, `channel` | passthrough | none |
| `note` | `redact` | default text |

S1 freezes the two provider names and the `bucket_perturb` parameters in `scenarios.py`, and AT-3 checks every named strategy and provider is in the installed `strategy_catalog()`. The page lists each strategy by name.

| Id | Flow | Sizes (rows per table) | Denominator |
|---|---|---|---|
| MASK | `customers` Parquet in, Parquet out | 1M, 10M, 100M | input rows: N |
| MASK-SCAN | MASK plus `scan before(regex)` with `continue` policy | 1M, 10M, 100M | input rows: N |
| SUBSET-MASK | `customers` and `orders`; sample 10% of `customers` by `customer_id`; follow `orders.customer_id -> customers.customer_id`; mask both; Parquet out | 1M, 10M, 100M | input rows: 2N (both tables). Delivered rows and retention shown too |
| MASK-CSV | MASK with CSV in and CSV out (explicit types on read) | 1M, 10M | input rows: N |
| GENERATE | Generate N rows of the `customers` schema, Parquet out | 1M, 10M, 100M | output rows: N |

### 5.2 Machine classes

| Class | Logical CPUs | Memory limit | Host |
|---|---|---|---|
| Small | 4 | 16 GiB | Capped on a larger Linux host, or a GCP VM with that shape |
| Medium | 8 | 32 GiB | Capped on a larger Linux host, or a GCP VM with that shape |
| Large | 16 | 64 GiB | One GCP VM (n2-standard-16, pd-ssd), no cap |
| Laptop | 10 (M4, 4P+6E) | 16 GB installed | The Mac mini as it is (macOS has no cgroup). Its own column |

Units: CPUs are logical CPUs (vCPU on GCP, hardware threads elsewhere). Memory limits are GiB (cgroup `memory.max`). The Mac shows installed RAM. Swap: the scope sets `MemorySwapMax=0`; the host's swap state is recorded. GCP VMs are described by machine type.

A capped run is "a measurement on host H under these limits". It is valid only when all of these hold (F10):

1. The supervisor runs outside the measured scope. Each invocation gets its own new scope (`systemd-run --scope -p AllowedCPUs= -p MemoryMax= -p MemorySwapMax=0`) or, on a host of the class size, its own cgroup leaf.
2. The measured child runs `decoy run --json` and its `resources` envelope reports `threads` and `memory` with source `auto`, the logical CPU count equal to the class, and the memory ceiling equal to the class limit (with the derived out-of-core budget recorded).
3. The harness also reads, from inside the child's cgroup, the effective `cpuset`, `cpu.max` and `memory.max` up the whole ancestor chain, and the tightest values match the class.

A run where any check fails is refused (no timing). The same checks apply to physical hosts: a host of the class size still has its `resources` output checked. S2a includes one real delegated-scope check on each measurement host.

The child environment is built from an allowlist (`PATH`, `HOME` set to a fresh directory, `LANG`, `TMPDIR` set to the attempt's scratch, `DECOY_BENCH_MASK_KEY`). `DECOY_THREADS`, `DECOY_MAX_MEMORY` and `DECOY_HOME` are not passed, and the fresh home has no `settings.json`.

Cache: the page says "one untimed warmup, OS caches left enabled". GENERATE has no input files, so its warmup only loads the program.

### 5.3 The harness

Commands. Release and provisional modes are separate entry points so a dev build cannot take the release path.

- `python scripts/bench/run.py --campaign <manifest> --cell MASK/10M --class medium` (S2b, release). Reads the campaign manifest (5.5), which names the candidate directory.
- `python scripts/bench/run.py --provisional --decoy <path> --cell MASK/1M --class medium` (S2a). Every attempt it writes is `provisional: true`. The publisher refuses these in release mode and the site check refuses them in every build.

Release identity (F1). Release mode reads `<dist>/candidate.json` through `read_candidate`, then verifies and installs the signed artifact for this host's target through the existing release-smoke candidate path (`packaging_tools/smoke_install.py` `candidate_main`) into a fresh prefix. Every invocation (version, validate, warmup, timed runs) uses that install's absolute launcher. The attempt records the CLI and engine commits, the candidate sums digest, the target and the artifact digest. The result document's `ProducerInfo` CLI and engine versions must match the candidate (`record_smoke.check_match`). The campaign manifest pins one candidate. A replacement candidate makes a new campaign; earlier attempts stay but cannot publish under it.

One attempt (a cell on a class):

1. Preflight: fixture sha256 check; free space on each actual device (fixture, output, spill in `TMPDIR`, guard scratch) against the scenario's per-device budget in `scenarios.py`; for GENERATE the budget is from output size only. Refuse with the device and the shortfall.
2. Fresh attempt directory with a unique attempt id (`<campaign>/<cell>/<class>/<utc>-<random>`), its own project, output and scratch folders. The result path for each invocation is fresh and outside `out/`.
3. `decoy validate` once with the installed launcher. A capacity refusal here (exit 5) ends the attempt as capacity-refused. Any other failure ends it as config-failed.
4. One untimed warmup, then the timed invocations (5 at 1M and 10M, 3 at 100M). Each timed invocation: new scope, the supervisor starts `decoy run <pipeline> --json --result <fresh path>` in its own process group, timing from spawn to exit with `time.monotonic_ns()` outside the child. A sampler sums RSS over the scope's processes every 100 ms. After exit: `memory.peak` and the `memory.events` `oom_kill` delta of that fresh scope (Linux), `ru_maxrss` labelled as largest child.
5. After each invocation, outside the timer: read the result through `RunResultRead`, then the guard (5.4). Then delete that invocation's output.
6. Stage the attempt's evidence (one canonical `attempt.json` plus `commands.txt`) and publish it once with `publish_private_once`. An attempt with no completion file is incomplete and ignored by the publisher. Scratch is removed on success, guard failure, timeout and interrupt; fixture and evidence roots are outside the cleanup path.

Exit classification of one invocation (F11), from the CLI's exit codes and the cgroup:

| Outcome | Evidence | Cell effect |
|---|---|---|
| success | exit 0, a new result document that `RunResultRead` accepts, guard pass | counts toward the set |
| capacity | exit 5 (engine capacity reason code), or `oom_kill` delta > 0 in the run's own scope | "Needs more memory" with the code or the OOM evidence |
| timeout | the 2 h limit hit; the supervisor kills the process group | "Did not finish in 2 h" |
| runtime | exit 3 | "Not measured: runtime error" and a QA finding |
| guard | exit 0, guard fails | "Not measured: guard failed" and a QA finding |
| result | exit 0 with a missing, stale, unsupported-major or partial-delivery result | "Not measured: result unusable" |
| other | any other exit code, a bare signal with no `oom_kill` delta, disk full, launch failure, cancel | "Not measured" with the named reason |

A cell has a measured value only when every timed invocation in its set is a success. A mix of success and failure never gives a median of the successes.

### 5.4 Correctness guard (each timed invocation)

Result checks (F9): the result file is new (created after spawn, inode not seen before), parses through `RunResultRead` with a supported major, has the expected producer and config digest, a distinct invocation id from every earlier invocation in the campaign, success status, and a delivery entry for every expected table. The harness counts delivered rows and files itself and does not trust the document's counts. Route fields are recorded as observed, including null or inapplicable ones. Invocations with different observed routes are never combined under one label; a cell whose timed set has two routes is "Not measured: route changed between runs".

MASK, MASK-SCAN, MASK-CSV (F8): delivered row count is N (`i4_rows.check_mask`). Schema: names, order, physical and logical types and nullability match `scenarios.py` (`i5_schema`), with CSV read using explicit types. Leak check: a fixed sample of 10k `customer_id` values; join output to source by `customer_id`; for each sampled row no marker token from the source `email`, `ssn`, `last_name` or `street` appears in any output column. A permuted but unmasked output fails because the join uses the key, not row position.

MASK-SCAN (F6): the result's run-start `pre_scan` check is present, its state is `ran`, and it reports at least the expected number of marker findings in `street` under the `continue` policy. A missing or `not_run` check, or a result without the scan, is not a success.

SUBSET-MASK (F7): exactly `max(1, floor(0.1 * N))` distinct `customer_id` values in the output, each present in the source. The guard independently computes the set of source `order_id` values whose `customer_id` is in that output set, and checks that the output `orders` holds every one of them exactly once and nothing else. The leak check runs on retained rows of both tables. At 10M and 100M the check uses a bounded, disk-backed join (sorted runs in scratch) outside the timer, not an in-memory set.

GENERATE (F8): row count N (`i4_rows.check_generate`); exact types and nullability; `customer_id` unique; each column within its declared domain (non-null rate, string length range, date range, the 5 `status` values). An all-null column fails.

### 5.5 Campaign and records

Campaign manifest (F14), frozen and committed before any timed run: candidate directory and sums digest, fixture pins, the scenario matrix and its frozen pipelines (by digest), the classes and hosts, repetition counts, timeout, the variance rule, and stop conditions (5.8). The harness refuses a cell, class or host not in the manifest.

Records in the CLI repo: `docs/records/perf-guide/<campaign-id>/<cell>/<class>/<attempt-id>/` with `attempt.json` (the one canonical structured record) and `commands.txt`. `attempt.json` holds: host and class facts (CPU model, logical CPUs, memory, swap, OS, kernel, disk device and filesystem, machine type), the limit checks and the child's `resources` output, release identity (1 above), fixture pins and per-table input rows and on-disk bytes, and for each invocation: kind (`warmup` or `timed`), invocation id, wall ns, memory figures with their labels and units, missed samples, outcome class, route as observed, delivered rows and bytes per table, and guard result by name. A campaign `summary.md` (`Status: record`) is rendered from the JSON by `scripts/bench/record.py`; nobody edits it.

Records are append-only. A completed attempt is never overwritten. Two cells on one host on one day get distinct attempt ids. The CODEMAP row describes this layout.

Variance rule (F14), fixed before measurement. If a measured cell's max/min wall time is above 1.5, the cell is rerun once as a new attempt. The published figures are the median and range over all timed invocations of both attempts, marked "high variance, rerun". No attempt is dropped. If the rerun is incomplete, the cell is "Not measured: unstable".

Repeatability (AT-16): once per host, the first 1M MASK cell is run again as a new attempt. If the medians differ by more than 10%, every cell from that host is "Not measured: host failed repeatability" until the owner decides.

### 5.6 Site data

`python scripts/bench/publish.py --campaign <manifest> --out performance.json` (release mode) reads every completed attempt under the campaign, owns all eligibility and statistics, and writes the site file. `publish.py --check performance.json --campaign <manifest>` regenerates and requires byte equality. Schema version 1:

- `schema_version`, `generated_by`, `release_version`, `evidence`: CLI repository, the 40-hex commit that holds the records, and the campaign id. `status` (`placeholder` or `published`) is derived by the publisher: `published` only when every measured cell comes from a non-provisional attempt and the row-close rule (5.8) holds.
- `classes`: id, label, logical CPUs, memory limit with unit, host and machine type, how applied.
- `scenarios`: id, label, description, strategies by name, denominator kind.
- `cells`: scenario, `rows_per_table`, class, and `state` (`measured`, `capacity`, `timeout`, `not_measured`) with `reason`. A measured cell holds `timed_ns` (the raw wall times of every timed invocation, in order), `input_rows` and `delivered_rows` per table, `input_bytes` per table, `route`, `memory` (value, label, unit), `variance_rerun`, and `evidence` (the record path, the attempt ids and the 40-hex commit). The derived `median_s`, `min_s`, `max_s` and `rows_per_s` are written too, so the page reads them directly.

Publisher refusals (exit 1, named reason): a provisional attempt in release mode; attempts on two candidates; a duplicate cell key or invocation id; a non-finite or non-positive wall time; a timed count other than 5 or 3 (warmups never count); inconsistent fixture, pipeline or host identity inside a cell; mixed routes; any cell not in the manifest; a missing headline cell (5.8) when `published` is asked for.

### 5.7 The pages

S4 (decoy-site):

- `/how-it-works/#performance`: intro (whole `decoy run`, source read to delivered output, one untimed warmup with OS caches left enabled, default settings, the strategies by name, release version, dates, link to the evidence commit). "Pick a box": for each scenario and size, the smallest tested Linux class with a measured cell and its median; lower classes that were not tested or did not complete are shown with their state; the Mac is shown on its own. One table per scenario: rows per table by class. A measured cell shows median time and input rows per second (output rows per second for GENERATE). The details line has range, total input and delivered rows (and retention for SUBSET-MASK), input bytes, memory with its label, route, host, date and a link to the exact attempt record. Other states show their label and reason. No projected values and no projection caption.
- `/cli#performance`: the table is replaced with one sentence and a link to `/how-it-works/#performance`. The anchor stays (F3). The Linux-only and projection text go.
- `src/_data/performance.json` in S4 is a placeholder: schema 1, `status: placeholder`, every cell `not_measured` with reason "release benchmark not run yet", zero numbers (F4). Provisional numeric data exists only in fixture tests and local preview input, never in `src/_data/`.

`scripts/check-performance.mjs`, run by `check:site`, which `npm run check` runs and the Pages workflow runs before upload:

- Schema 1, `generated_by` present, no key named `projected`, `extrapolated` or `estimate`.
- `status: placeholder` passes only if no cell is measured. `status: published` passes only if every measured cell has a 40-hex evidence commit, a record path matching `docs/records/perf-guide/<campaign>/<cell>/<class>/<attempt>/`, and attempt ids. Any other status, and any provisional flag, fails in every build.
- For each measured cell: `timed_ns` has exactly 5 entries (1M, 10M) or 3 (100M), all finite and positive; `median_s`, `min_s`, `max_s` and `rows_per_s` equal the values recomputed from `timed_ns` and the per-table rows; `input_rows` equals `rows_per_table` times the scenario's table count. So an edited median, a cell moved to another scale, or a flipped status fails (F2).
- Built HTML of both pages has no "projection" or "projected", and the `/cli` link resolves to the `/how-it-works` anchor.

Byte equality between the site file and the committed CLI records is checked by `publish.py --check` in S5, and the S5 evidence record lists its output. The site check cannot read the CLI repo at deploy time, which is why the raw repetitions travel in the site file.

### 5.8 Row close and cost

The row closes only when the published file has measured cells for MASK and GENERATE at 1M and 10M on at least Large, Medium and Laptop. A file where every cell is not measured cannot be `published` (F14).

S5 elapsed time (F19): the full matrix is 14 cells per class, 76 timed and warmup invocations per class, about 304 over four classes, plus validation, fixtures, reruns and AT-16. Before the owner approval ping, a pilot runs MASK and GENERATE at 1M and 10M on the Dell or Mac and extrapolates the campaign's machine hours, disk and GCP cost (an estimate for budgeting only, never published). Stop conditions in the manifest: a GCP spend cap, a wall-clock cap per class, and stop on the first guard failure. VM and disk teardown is a checklist step in the S5 record.

## 6. Failure modes

| Failure | Handling |
|---|---|
| Dev or foreign build in release mode | Release mode uses only the verified candidate install. A version match alone is not accepted. Provisional mode marks every attempt provisional, and both the publisher and the site check refuse provisional data |
| Candidate replaced after measurement | New campaign; old attempts cannot publish under it |
| Limits not applied or not seen by the child | Refuse the attempt (5.2) |
| Missing mask key | `decoy validate` fails with the key reason before any timing (AT-3) |
| Validate refuses for capacity | Attempt is "capacity" with the code, no timing |
| Run exit 5 or OOM kill in scope | "Needs more memory" with the evidence |
| Exit 3, unknown signal, disk full, launch failure | "Not measured" with the named reason |
| Timeout 2 h | Process group killed, "Did not finish in 2 h" |
| Result missing, stale or partial with exit 0 | "Not measured: result unusable" |
| Guard fails | "Not measured: guard failed" and a QA finding. The cell is not published |
| Interrupt or disk full mid-attempt | No completion file, so the publisher ignores it; scratch removed; earlier attempts untouched |
| High variance | 5.5 rule, no selection |
| Fixture bytes differ across hosts | Refuse; the pins in `fixture.json` name the difference |
| MASK-SCAN not supported by the candidate | `pre_scan` not `ran`, so "Not measured: pre-scan not in this release" |
| Engine performance work lands after S5 | New candidate, new campaign |
| Mac has no cgroup | Laptop column is the real machine, checked through `resources`; no cgroup memory figure, only sampled RSS |

## 7. Acceptance tests

Unit tests in `tests/unit/bench/` (T0 and T1, small data). Fixture tests for decoy-site in `scripts/fixtures/performance/*.test.mjs` (the shape `scripts/run-fixtures.mjs` finds).

- AT-1 Fixture determinism and bounds: same seed, N and pins give the same sha256 twice; another seed differs. With 1k row groups, peak live rows stay at one row group as N goes 3k to 30k. Seeded mutation: build the whole table first, then hand it out in batches; the test fails.
- AT-2 Fixture shape: types; every `orders.customer_id` in `customers`; null rates within 1 point; marker tokens unique per row; about 1% street markers.
- AT-3 Scenario pipelines: every named strategy and provider is in `strategy_catalog()`. Every scenario runs through delivered output on a 1k fixture with the installed dev CLI (MASK-SCAN skipped with its reason if pre-scan is not supported). With `DECOY_BENCH_MASK_KEY` removed, `decoy validate` fails with the key reason.
- AT-4 Release identity: valid candidate and matching install pass; `1.0.0` candidate with a CLI reporting `1.0.1` fails with the version-mismatch reason; a same-version executable that is not the candidate install fails on artifact digest; two same-version candidates with different sums give two campaigns that cannot mix.
- AT-5 Provisional path: provisional attempts carry the flag; the publisher in release mode refuses them; the site check refuses them in a preview and a production build.
- AT-6 Limits: the child's `resources` with source `auto` and class values passes. Fails for: a tighter ancestor `cpu.max` or `memory.max`, a child started outside the scope, an inherited `DECOY_THREADS` or `settings.json`, a `resources` source other than `auto`.
- AT-7 Supervisor: a fake child that sleeps 0.3 s and starts a grandchild holding 50 MB gives a wall time of at least 0.3 s and a sampled sum of at least 50 MB. Seeded mutation: sample only the direct child; the test fails. A large fake run followed by a small one: the second run's memory figure is not raised by the first. On timeout the grandchild is gone. `DECOY_THREADS=1` in the harness is not seen by the child.
- AT-8 Guards: for each, a correct output passes and these fail by name: a permuted unmasked output; a generated column of nulls; a type changed with names and counts kept; full-copy subset output; empty child table; a missing valid child; a duplicated child; an orphan; each case also with a result document that agrees with the wrong output. MASK-SCAN with `pre_scan` missing or `not_run` fails.
- AT-9 Result and records: exit 0 with a missing, stale, unsupported-major or partial-delivery result is "result unusable". Two cells on one host on one day, a variance rerun and a retry after an interrupt during writing all keep every completed attempt. A seeded failing marker and the benchmark key are run through the error paths; neither appears in terminal output, any record file or the site file (file names, config keys and column names are allowed).
- AT-10 Exit classification: validate exit 5, run exit 5, exit 3, OOM delta, bare SIGKILL with no OOM delta, timeout, and a mixed success and failure set each give the state in 5.3.
- AT-11 Publisher refusals: provisional in release mode, two candidates, duplicate cell or invocation id, a non-positive or NaN time, a counted warmup, a short set, mixed routes, an all-empty campaign asked to publish. Seeded mutation: remove the repetition-count check; the test fails.
- AT-12 Publisher output: from fixed attempts the output equals a golden file; SUBSET-MASK has the 2N input denominator and delivered rows; GENERATE uses output rows; omitting the slow attempt of a variance pair is refused because the manifest expects it; `--check` fails after any byte change.
- AT-13 Site check: the S4 placeholder passes in a production build; a provisional file fails in every build; an edited median, a cell relabeled to another scale, a bad evidence commit or path, and a flipped status each fail; a `projected` key fails. Seeded mutation: remove the recompute; the edited-median test fails.
- AT-14 Pages: the built `/how-it-works` section has no projection text, shows each state label, and table headers have `scope`; `/cli#performance` links to the canonical section; neither page has the Linux-only claim.

S5 evidence (R3), in `docs/records/2026-<mm>-<dd>-perf-guide-release.md`:

- AT-15 The campaign covers the manifest; every cell has a state and reason; all attempts are on one candidate; the row-close rule in 5.8 holds; `publish.py --check` passes on the committed site file.
- AT-16 Per-host repeatability as in 5.5.

## 7a. Defect classes

| # | Class | Applies | Structure | Proof (mutation) |
|---|---|---|---|---|
| 1 | value | Yes: records, terminal and site file must not carry source values or the key | records hold counts, times, versions and guard names only; the key is held in memory and passed by one env var | AT-9 (mutation: write the failing value or the key into a record) |
| 2 | cleanup | Yes: scratch at 100M, orphaned processes | per-attempt scratch removed on every exit path; process group killed | AT-7, AT-9 (mutation: kill only the child) |
| 3 | state | Yes: env, settings and earlier runs leak in | env allowlist, fresh home, fresh scope per invocation, fresh result path | AT-6, AT-7, AT-9 |
| 4 | route | Yes: mixed routes under one label | route per invocation, mixed routes refused | AT-11 |
| 5 | referential | Yes: subset output | exact independent subset check | AT-8 |
| 6 | untrusted | Low: records are our own; the site file is checked by recompute | site check recomputes | AT-13 |
| 7 | toctou | Low: fixture changed between check and run | sha256 checked in each attempt's preflight | AT-1 |
| 8 | weak | Yes: a lax publisher or site check publishes a false claim | seeded mutations on the repetition check and the recompute | AT-11, AT-13 |
| 9 | refactor drift | Low: `/cli` table removed, renderer becomes one | both pages built in AT-14 | AT-14 |
| 10 | frozen contract | Low: the site data schema changes for both readers in one slice; the run result is read through the public versioned reader | `schema_version`; `RunResultRead` major check | AT-9, AT-13 |

## 8. Design notes

- Choke point: `publish.py` is the one producer of the site file and the one owner of eligibility and statistics. `check-performance.mjs` verifies and recomputes; it decides nothing new. Mutation that must turn it red: drop the recompute (AT-13).
- One place per fact: scenarios, strategies, denominators and disk budgets in `scenarios.py`; one canonical `attempt.json` per attempt; `summary.md`, commands and the site file are derived from it.
- The supervisor drives the installed CLI as a user does, so numbers include process start, imports and the write.
- Memory a user needs is the class limit the run fit in. The memory figure is a labelled guide.

## 9. Placement

CODEMAP (S1): new row "Benchmark tooling (not shipped)": `scripts/bench/`, tests in `tests/unit/bench/`, imports no private product module (same rule as "QA tooling (not shipped)"). The "Roadmap, plans, records" row gains one line: `docs/records/perf-guide/<campaign>/<cell>/<class>/<attempt>/` holds JSON attempt records, not dated Markdown.

| File | Lines (est.) | Slice |
|---|---|---|
| `scripts/bench/fixtures.py` (pins, chunked writer, manifest) | 300 | S1 |
| `scripts/bench/scenarios.py` (pipelines, strategies, schema, denominators, disk budgets) | 260 | S1 |
| `scripts/bench/_supervise.py` (scope, spawn, timer, sampler, cgroup reads, limits check, env, exit classification) | 380 | S2a |
| `scripts/bench/_attempt.py` (attempt ids, staging, `publish_private_once`, result read) | 220 | S2a |
| `scripts/bench/run.py` (both entry points) | 200 | S2a, S2b |
| `scripts/bench/_release.py` (candidate verify and install, identity match, campaign manifest) | 250 | S2b |
| `scripts/bench/_guard.py` (uses `scripts/qa/invariants`) | 300 | S2b |
| `scripts/bench/_subset_check.py` (bounded disk-backed join) | 200 | S2b |
| `scripts/bench/record.py` (`summary.md`) | 150 | S2b |
| `scripts/bench/publish.py` | 350 | S3 |
| `tests/unit/bench/test_*.py` | about 900 over 8 files | S1 to S3 |
| decoy-site `src/how-it-works.njk` (section), `src/cli.njk` (section to link), `src/_data/performance.json` (placeholder), `scripts/check-performance.mjs` (250), `scripts/fixtures/performance/*.test.mjs`, `package.json` (`check:site`) | | S4 |
| CLI `docs/records/perf-guide/<campaign>/...`, `docs/records/2026-<mm>-<dd>-perf-guide-release.md`; decoy-site `src/_data/performance.json` (published) | data | S5 |

Every handwritten module stays under 600 lines. No new public product names.

## 9a. Enumerations

### Exit paths of one invocation

- success: exit 0, usable result, guard pass.
- capacity: exit 5 (`src/decoy/cli/exit_codes.py:82`), validate refusal (`src/decoy/cli/validate.py:294`), or an `oom_kill` delta.
- timeout: 2 h, process group killed.
- runtime: exit 3 (`src/decoy/cli/exit_codes.py:66`).
- guard: exit 0, guard fails.
- result: exit 0 with an unusable result document.
- other: unknown exit or signal, disk full, launch failure, cancel; a harness interrupt leaves no completion file.

Cell states: `measured`, `capacity`, `timeout`, `not_measured` (with reason).

### Routes

- None forced; every observed `Route` field is recorded, including null ones (engine `src/decoy_engine/run_result/_model.py:276`).
- Two observed routes in one timed set: the cell is refused ("route changed between runs").

### FK shapes

- `orders.customer_id -> customers.customer_id`, single column, downward follow, in SUBSET-MASK. Parent cardinality for unique non-null keys follows engine `src/decoy_engine/subset/_seed.py:267`.
- No other FK shape: MASK, MASK-SCAN, MASK-CSV and GENERATE use one table.

### Fields

- Fixture fields as in 5.1.
- Result fields read: producer, config digest, invocation id, status, per-table delivery, route, `pre_scan` check (engine `src/decoy_engine/run_result/_model.py:182`, `:297`).
- Child `resources` fields: threads and memory with their sources (`src/decoy/cli/run/_render.py:128`, `src/decoy/_resources.py:105`).

### Output surfaces

- Record files: `attempt.json`, `commands.txt`, `summary.md`.
- Terminal output of the harness and publisher.
- The site file and both pages (`decoy-site/src/how-it-works.njk:240`, `src/cli.njk:259`).

None carries a source value or the key.

## 9b. Reuse inventory

- `packaging_tools/candidate.py` `read_candidate`; `packaging_tools/smoke_install.py` `candidate_main` (verify and install); `scripts/release/record_smoke.py` `check_match`.
- `scripts/qa/invariants/i1_leaks.py` (marker approach), `i2_foreign_keys.py` (small-scale FK), `i4_rows.py` (`check_mask`, `check_subset`, `check_generate`), `i5_schema.py`.
- `scripts/qa/io.py` `staged_private`, `publish_private_once`, `publish_or_same`; `scripts/qa/repro.py` process-group timeout pattern.
- Engine public `RunResultRead`; `decoy run --json` `resources`; `decoy validate`.
- Reference only, not imported: engine `scripts/fk-scale/_supervisor.py` and `build_fk_chain.py`.
- psutil and PyArrow from `requirements-dev.lock`. decoy-site `scripts/run-fixtures.mjs` and `check:site`.

New: the chunked fixture writer, the supervisor, the bounded subset check, the publisher and `check-performance.mjs`.

## 9c. Frozen contracts

None changed. The run result is read through the engine's public, versioned reader. The site data file moves to schema 1, and both its readers (`how-it-works.njk`, `cli.njk`) change in the same slice.

## 10. Slices

| Slice | Content | Repo | Risk | Size | Depends on |
|---|---|---|---|---|---|
| S1 | Fixture writer with pins, frozen scenarios and strategies, CODEMAP rows; AT-1 to AT-3 including a 1k installed-CLI run per scenario | CLI | R1 | 1 day | none |
| S2a | Provisional measurement: supervisor, limits check, env, exit classification, attempt staging, result read; AT-6, AT-7, AT-9, AT-10; the real delegated-scope check on the Dell and the Mac | CLI | R2 | 1 day | S1 |
| S2b | Release qualification and correctness: candidate install and identity, campaign manifest, guards, bounded subset check, `summary.md`; AT-4, AT-5 (CLI half), AT-8 | CLI | R2 | 1 day | S2a |
| S3 | Publisher and `--check`; AT-11, AT-12 | CLI | R2 | 1 day | S2a (attempt schema) |
| S4 | Both pages, placeholder data, site check and fixture tests; AT-5 (site half), AT-13, AT-14; live review by Cam | web | R2 | 1 day | S3 site schema |
| S5 | Pilot and cost ping, campaign, records, publish, page live; AT-15, AT-16 | CLI, web | R3 | builder about 1 day; machine time from the pilot | row 94 candidate, final engine perf work, S1 to S4; PRE-SCAN-RUN for measured MASK-SCAN |

S1 to S4 can build now. S4 merges before S5. S4 is web work during the web pause, allowed because PERF-GUIDE is an owner row in the V1 release effort.

Recovery: the page data is one file. If a published number is wrong, revert the site data commit to the placeholder (which passes the production check) and rerun the cell in a new attempt.

## 11. Owner gates

- Before the GCP run in S5: a Slack ping with VM type, disk, the pilot's hour and cost estimate, stop conditions, and owner approval (one VM at a time).
- Before the page goes live: the owner reviews the S5 numbers and both pages.
- Open choice, default applies if no answer: class sizes as in 5.2.

## 12. Risks and pre-mortem

- Numbers look worse than competitors'. That is engine work, not a reason to tune the benchmark. The manifest freezes the workload first.
- A builder passes `--threads` or settings to go faster. AT-6 and AT-7 fail, and the child's `resources` output shows it.
- A builder drops a guard at 100M. AT-8 and the publisher's eligibility rules stop the cell.
- Someone edits `performance.json` by hand. The site recompute (AT-13) and `publish.py --check` catch it.
- The cap tool is not available on the Dell (WSL) or the devbox (LXC). Small and Medium then run on GCP VMs of that shape, one at a time, in the S5 cost ping.
- The pilot shows 100M on Small or Medium costs too much. The manifest marks those cells "Not measured: outside approved budget", and the row-close rule still holds without them.
