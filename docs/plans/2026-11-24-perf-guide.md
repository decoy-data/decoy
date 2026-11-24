Status: plan

# PERF-GUIDE: one scripted benchmark of the whole flow, published on /how-it-works

Owner: Cam. Author: Opus plan agent. Date: 2026-11-24. Revision 4. Roadmap row: PERF-GUIDE (`docs/roadmap/groups/release.md:27`, owner 2026-11-23, V1 release effort). Ordering from the row: after the final engine performance work, before row 94 (CLI-REL).

Rules consulted: dev-rules `README.md`, `00-universal.md`, `development-loop.md` (PLAN, Proportion, REMEDIATE), `risk-and-exceptions.md`, `performance.md`, `testing.md` (Rules, Test depth), `reuse-first.md`, `proportionality.md`, `architecture.md` (Layout), `cross-cutting-concerns.md`, `release-and-rollback.md`, `documentation.md`.

Risk: S1 is R1 (synthetic fixtures and pipeline texts, no measurement or publication). S2a, S2b, S3 and S4 are R2: they decide what counts as a measurement and what the public page may show. S5 is R3: it spends money on one GCP VM and publishes a consequential public claim, so it needs owner approval before the cloud run and again before the page goes live. Plan review: Codex R1, R2 and R3 NO-GO. R3 hit the 3-round cap, so rev 4 is the plan fix under the dev-loop rule (section "Changes in revision 4"). Code gate per slice: Codex for S1; Codex then Dennis for S2a, S2b, S3 and S4. Tests: T0 per edit, T1 per commit. S2b touches release tooling (`packaging_tools/smoke_install.py`, `packaging_tools/candidate.py`, `scripts/release/record_smoke.py`), so its T1 set includes the existing release-smoke and record-smoke tests. No slice changes shipped product code, so no full-suite trigger applies.

Repos: CLI (`decoy-data/decoy`) for the harness, the records and the publisher. Web (`decoy-data/decoy-web`, local `/home/cam/vscode/decoy-site`) for the page. The engine gets no change.

Threat model: V1 covers accidental errors only (owner, V1 threat model). The checks in this plan stop a wrong number that a bug, a wrong build or a careless edit would produce. They do not stop a person who edits the site data on purpose; site changes go through reviewed PRs.

## Revision history

| Rev | Date | Change |
|---|---|---|
| 1 | 2026-11-24 | First plan (head `c721ee6b`) |
| 2 | 2026-11-24 | Codex R1 NO-GO, 19 findings, all taken (head `3d33c418`) |
| 3 | 2026-11-24 | Codex R2 NO-GO, 12 findings. Orchestrator decisions applied: less machinery (head `d3d30004`) |
| 4 | 2026-11-24 | Codex R3 NO-GO at the review cap, 10 findings. Plan fix: two shared contracts replace per-scenario prose. See "Changes in revision 4" |

## Changes in revision 4

Cause of the repeated findings. Across R1 to R3 the findings fall in two classes.

1. Unbound external facts. The plan stated engine and CLI facts from memory (a candidate field name, a provider catalog, an output type, a JSON error shape, a detector rule, a class size). Each round found the next wrong one. Rev 4 adds section 9d, "External contract bindings": every fact the harness depends on has one row with its source on `origin/main` and the test that runs it against the real installed code. Section 5 cites the binding id instead of restating the fact. A builder who finds a binding false stops and returns to the plan; the builder does not work around it.
2. Evidence qualification written per scenario. Guards, qualification, the displayed coordinate and the reduction of 5 runs to one figure were each described in their own paragraph, so some rules were too strict (they rejected correct masking) and some were missing (a guard could be absent, a scale could be relabeled). Rev 4 adds one shared contract, section 5.4, "Evidence-qualification contract". It defines the check ids each scenario requires, one predicate per column strategy with its legal exceptions, one qualification rule, one displayed-coordinate rule and one reduction rule. The guard runner, the publisher and the site check all use it.

Each finding of Codex R3, and its change:

- R3-1 (candidate has `engine_tag`, not `engine_version`): `verified_install` yields the validated candidate record (`cli_version`, `engine_tag`, `sha256sums_sha256`) and the launcher. The comparison is factored out of `record_smoke.check_match` into `packaging_tools/candidate.py` `identity_matches(cli_version, engine_version, record)`: `cli_version == record["cli_version"]` and `f"v{engine_version}" == record["engine_tag"]`. `check_match` and the bench both call it (5.3, B1, B2). AT-4 adds an engine-only mismatch.
- R3-2 (wrong provider catalog for MASK): MASK providers are checked with `providers_v2.get_default_registry().get_capabilities(name)` and frozen as `address_city` and `address_zip`. GENERATE providers are checked with `list_generate_faker_providers()`. The per-attempt key is passed as 64 hex characters (5.1, B4 to B6, AT-3).
- R3-3 (`bucketize` does not give int64): the float64 workload stays and the bucket label is frozen as a string column holding the integer lower bound as text. AT-3 checks the delivered Parquet type and the label values (5.1, B7).
- R3-4 (equality guard rejects correct masking): per-row inequality is gone. Each strategy has its own predicate (5.4 column table): the marker scan covers Faker and redact columns, whose source values all carry a marker, so source and output are disjoint by construction; `date_shift` requires a shift within [-30, 30] days (zero allowed) and at least 90% of sampled rows changed; `bucketize` requires the exact label; nulls stay null. AT-8 adds passing cases with a zero-day shift and a bucket-boundary input, and failing cases with an unmasked date and an unmasked amount.
- R3-5 (subset join uses the wrong key population): for each delivered table the guard samples `min(10_000, delivered_rows)` distinct primary keys and joins customers by `customer_id` and orders by `order_id`, one source match each. The complete expected and delivered order and customer pairs are compared on their own (5.4). AT-8 adds a passing case with two orders for one retained customer.
- R3-6 (uncapped check rejects the Medium fallback): the uncapped check uses the selected class's CPU count and nominal bytes. The Laptop row pins the real `hw.memsize` byte count apart from the "16 GB" label (5.2, B10). AT-6 adds an uncapped Medium positive case.
- R3-7 (exit 5 without a top-level code): the harness runs `decoy validate <pipeline> --json` and takes the error code that is in `capacity_codes()` from `messages[]`. For `run` it reads the top-level `code`, then `reason.code`. With neither, the state is `refused` with "capacity refusal; code unavailable" (5.3, B11, B12). AT-10 covers both envelope shapes, a validate payload with a capacity code and another error, and a run refusal with no code.
- R3-8a (missing guard evidence): `scenarios.py` freezes the required check ids per scenario. An invocation counts only when every required id is present and passed (5.4). AT-11 deletes one check from an otherwise good record and expects `not_measured`. The bench does not use `i4_rows.check_subset` (it only rejects growth, B14).
- R3-8b (GENERATE scale mismatch): the displayed-coordinate rule (5.4) requires the record path's scenario, size and class to equal the cell's, and the delivered rows to equal the scenario's expected count (`customers == rows_per_table` for GENERATE). Publisher and site check both apply it. AT-13 changes only the GENERATE scale and expects a failure.
- R3-9 (R2-6, pre-scan positive control): every `email` value is a valid whole-field address `pgmark<id>@scan.invalid`. The street email marker is gone. S1 freezes a positive `pre_scan` pass count; AT-3 checks it is above zero and that a variant with `email` uncovered gives `warned`. The parsed model field is `check.counts.passed` (wire `counts.pass`) (5.4, B9).
- R3-10 (R2-11, reduction of 5 runs to one figure): the reduction rule in 5.4 is fixed: memory shown is the highest of the 5 timed peaks; delivered bytes per table come from the median-wall-time invocation (third in order of wall time, ties to the lower invocation number); delivered rows must be equal over the 5 runs; warmup never enters. The site file carries the 5 raw values so the site check recomputes both. AT-12 uses unequal inputs.

Fixed owner decisions R2-1, R2-2, R2-3 and R2-10 are unchanged. Codex R3 found R2-8 and R2-12 resolved; they are unchanged.

## Changes in revision 3

Each line names the Codex R2 finding. Items R2-4, R2-5, R2-6, R2-7, R2-9 and R2-11 are corrected again in revision 4; where this list and section 5 differ, section 5 holds.

- R2-1 (tamper-proof numbers): out of scope under the V1 threat model. The site check stays a consistency recompute (median, range and rows/s match the raw repetitions). 5.7 now says plainly that it does not detect a deliberate edit. Codex's design (the Pages build verifies the bytes against a pinned CLI evidence commit) is in section 13.
- R2-2 (variance rerun): the rerun is gone. Every cell has exactly one attempt with 5 timed runs at every size. A cell with max/min above 1.5 is published with a "high variance" flag. One attempt per cell key, enforced by an exclusive start marker. The repeatability check is its own cell key (`MASK-REPEAT/1M`), so no key repeats.
- R2-3 (unmeasured cells block the campaign): repetition, route and identity rules apply only when a cell qualifies as measured. A refused, failed, interrupted or mixed-route cell is published as "Not measured" (or its refusal state) with its reason. It never blocks the campaign while the headline cells (5.8) are measured. Capacity refusals keep their specific engine reason code and are labelled "Refused at this size", not "Needs more memory", because some codes (for example `pool_exceeds_cache_budget`) are not cured by a larger host. Validate runs under the same class limits as the timed runs.
- R2-4 (install deleted before the run): a shared `verified_install()` context in `packaging_tools/smoke_install.py` runs the candidate verify and install steps, yields the absolute launcher and the verified identity, and removes the install root on exit. `candidate_main` and the benchmark both use it, and the whole campaign cell runs inside it.
- R2-5 (numeric strategy, providers, key): `balance` and `amount` use `bucketize` instead of `bucket_perturb`, which takes dates. The missing-key case runs through `decoy run`, not `validate`. The key is made per attempt.
- R2-6 (MASK-SCAN check): the guard checks what the engine emits: the `pre_scan` check with status `passed` and the frozen pass count. The pipeline uses the default `warn` policy. An ordinary MASK result in a MASK-SCAN slot fails.
- R2-7 (guard holes): subset requires unique parent rows and exact `(order_id, customer_id)` pairs. A streaming scan rejects any reserved marker anywhere in delivered output. `orders.note` carries a marker.
- R2-8 (inode freshness): each invocation gets its own new directory; the result path must be absent before spawn. The inode test is gone.
- R2-9 (resources envelope): checks use the real fields (`threads`, `threads_source`, `max_memory_bytes`, `max_memory_source`). `max_memory_bytes` is the auto out-of-core budget (25% of the memory ceiling), so the harness reads the ceiling itself and compares. Separate cases for capped Linux, uncapped Linux and macOS.
- R2-10 (cgroup peak): no cgroup memory reads at all. The memory figure is the sampled peak RSS of the process tree at 100 ms, labelled as such. Capacity is exit 5 only. A bare SIGKILL is "Not measured: killed by signal 9 (cause not confirmed)". Scopes remain only to apply the CPU and memory caps.
- R2-11 (delivered bytes): per-table delivered bytes go through the publisher and onto the page. GENERATE shows zero source bytes, N delivered rows, output rows/s and output bytes.
- R2-12 (disk check order): the fixture writer checks free space before it writes, summing every path on the same device, and writes into a staging directory that becomes the fixture only after every file verifies.
- R1 V2-LOG items taken because they are small: `commands.txt` is written first and `attempt.json` last, so `attempt.json` is the completion marker (R1-F15). End-to-end assertions move to the slice where their surfaces exist (R1-F18).

## 1. Problem

The Performance section of `/how-it-works` (`decoy-site/src/how-it-works.njk`, section `id="performance"`) renders from `src/_data/performance.json`. Today that file has `status: pending_benchmarks`, every cell is null, and the 100M cells carry `projected: true`. The caption says "100M is a linear projection from the measured sizes". `/cli#performance` (`src/cli.njk:249-293`) renders a second table from the same file, with the same caption and a statement that there is no macOS or ARM64 evidence. So neither page has numbers, and the one rule they state (projection) conflicts with the owner's intent that the numbers come from real runs of the release build.

A user who asks "how long will 10M rows take, and what box do I need" has no answer. No harness times the whole flow (source read to delivered output) of the shipped CLI, and no record of such runs exists.

## 2. Pinned guarantee

Every number in the Performance section comes from one recorded attempt of 5 successful invocations of the verified release-candidate install of `decoy run`, on a named host under stated limits that the timed process itself reported, where each invocation passed every check the evidence-qualification contract (5.4) requires for its scenario. The site check recomputes every shown number from the raw repetitions in its data file before deploy; this catches accidental errors, not deliberate edits. No number is projected, extrapolated, selected from a subset of runs, or taken from a dev build. A cell without such an attempt shows its state and reason: "Refused at this size" with the engine reason code, "Did not finish in 2 h", or "Not measured" with the named reason.

## 3. Non-goals

- No engine or CLI product change. A slow result is a finding for the engine roadmap, not work in this row.
- No per-strategy or per-format micro benchmarks. The engine bench tools (`scripts/native-baseline/`, `scripts/fk-scale/`) keep that job.
- No change to `/proof` or to the engine `docs/proof-manifest.json`.
- No benchmark of the platform, of DP fit, or of `decoy scan` alone. The owner row asks for mask and generate, with and without subset and pre-scan. The current five-operation data shape goes away.
- No CI job runs the benchmark. A person runs it by hand on chosen hosts. CI runs the unit tests and the site data check.
- No 100M CSV cell. It is outside the scenario matrix and the page says so.
- No protection against deliberate edits of the site data (section 13).
- No cgroup memory accounting and no out-of-memory diagnosis.
- No census, baseline or allowlist raise in any slice.

## 4. Established solutions

Search run: hyperfine and pyperf documentation (benchmark method), TPC-H and TPC-DS specifications (whole-flow benchmark with a data generator and scale factors), `systemd.resource-control` (`AllowedCPUs`, `MemoryMax`, `MemorySwapMax`), Linux `getrusage(2)`, psutil documentation, and in-codebase search of the CLI, the engine and decoy-site for bench, perf, proof, QA and how-it-works work.

| Source | What we take |
|---|---|
| hyperfine, pyperf | One untimed warmup, then N timed invocations. Report the median and the min to max range. Keep every run. Record host, OS, CPU, versions and commands. Flag high variance instead of hiding it |
| dev-rules `performance.md` | Define workload, correctness guard, warmup, variance and resource budget. Report throughput with the resources used and the correctness result |
| TPC-H / TPC-DS | A deterministic generator with a seed and fixed scale points (1M, 10M, 100M rows per table). The timed unit is the whole user command. The benchmark definition is frozen before any number exists |
| `systemd-run --scope` with `AllowedCPUs`, `MemoryMax`, `MemorySwapMax=0` | The standard way to run one command under CPU and memory caps on a larger Linux host. Used only to apply limits; nothing is read from the scope after exit |
| `getrusage(2)`, psutil | `ru_maxrss` of children is the largest single child, not the tree, and its unit differs by OS. The portable figure is "highest sampled sum of RSS over the process tree, 100 ms interval", with its method, units and missed samples recorded |
| Engine `scripts/fk-scale/_supervisor.py` | An external supervisor that starts the measured process in its own process group and records how it ended, with memory observations per invocation. Reference design only; not imported (private sibling-repo code) |
| Engine `scripts/fk-scale/build_fk_chain.py` | Seeded FK Parquet generation one chunk at a time. The model for the fixture writer |
| Engine `validators/_leak_check.py`, CLI `scripts/qa/invariants/i1_leaks.py` | Leak checks that accept a zero date shift, a bucket boundary and a chance equal value, and exempt `bucketize` from per-row inequality. The model for the per-strategy predicates in 5.4 |
| Prior plan: decoy-site `docs-src/docs/plans/2026-10-24-how-it-works-performance-matrix.md` | Honesty rules: no extrapolation, "Not measured", date, hardware, version and route on every cell, a link from each number to its exact record, 100M runs only on an approved cloud budget. We drop its Scan and DP fit rows and put the records in the CLI repo, because the release build is the CLI |

Reuse in this repo (detail in 9b): `packaging_tools/candidate.py` `read_candidate` and the verify and install steps of `packaging_tools/smoke_install.py`, the identity comparison in `scripts/release/record_smoke.py`, `scripts/qa/invariants/` (`i1_leaks` marker approach, `i4_rows.check_mask` and `check_generate`, `i5_schema`), `scripts/qa/io.py` (`staged_private`, `publish_private_once`), `scripts/qa/repro.py` (process-group timeout pattern), `src/decoy/cli/gate/_run.py` `capacity_codes()`, the engine public `RunResultRead`, `list_generate_faker_providers` and `providers_v2.get_default_registry`, and the `decoy run --json` `resources` envelope.

Custom code that remains: the chunked fixture writer, the bounded large-scale subset check, the supervisor and the publisher. Each is specific to this row.

## 5. Behavior

Every fact about the engine or CLI that this section relies on is a binding in section 9d, cited as (B<n>).

### 5.1 Workload

Fixture data. Deterministic: seed `20261124`. The generator, PyArrow version, compression (Snappy), row-group size (1M rows, 1k in tests), dictionary and statistics settings are pinned in `fixture.json`. The same seed, size and pins give the same bytes, and the harness checks the sha256 of every file on every host.

- `customers`: N rows. `customer_id` (int64, unique, 0..N-1 then a fixed permutation), `first_name`, `last_name`, `email`, `phone`, `ssn`, `street`, `city`, `postcode` (string), `birth_date` (date32), `balance` (float64, non-negative), `status` (string, 5 values). About 5% nulls in `phone` and `street`.
- `orders`: N rows. `order_id` (int64, unique), `customer_id` (int64, every value present in `customers`, a fixed skew so some customers have many orders and some none), `order_date` (date32), `amount` (float64, non-negative), `channel` (string), `note` (short free text).
- Markers. Every non-null value of every column a Faker or redact strategy treats (`first_name`, `last_name`, `email`, `phone`, `ssn`, `street`, `city`, `postcode`, `note`) carries a reserved marker token, `pgmark` plus the row id, that no Faker provider or redaction output can produce. So a masked output value never equals its source value, by construction. Passthrough and key columns carry no marker.
- Pre-scan positive control (R3-9). Every `email` value is a valid whole-field address `pgmark<id>@scan.invalid`, so the regex email detector, which matches whole values over a rate threshold (B9), flags the column. No other column is built to trigger a detector.
- Writer: one row group at a time from the seeded generator. No list or array covers the whole table. Only the files a scenario uses are generated.
- Disk check first: before it writes, the writer sums the fixture budget (from `scenarios.py`) and every other path the run will use on the same device (grouped by `st_dev`), and refuses with the device and the shortfall. It writes into `<fixtures>/.staging-<random>/`, checks the sha256 of every file against the pins, writes `fixture.json`, then renames the staging directory to the final fixture name in one step. An interrupted or failed write leaves only a staging directory, which the next run removes; a finished fixture and all evidence are untouched.

Scenarios. Frozen in `scripts/bench/scenarios.py`, the one list. Each is one `.decoy` pipeline that sets `seed 20261124` and `secret ref("env:DECOY_BENCH_MASK_KEY")`.

Key: the harness makes a 32-byte random key at the start of each attempt, holds it only in memory, and passes it to the child through that one variable as 64 hex characters (B6). It is never written to a record (only the reference text is). Outputs are not compared across attempts, so attempts on different hosts need no shared key.

Column treatment, the same in every mask scenario:

| Column | Strategy | Parameters | Delivered type |
|---|---|---|---|
| `customer_id`, `order_id`, `orders.customer_id` | passthrough (key columns) | none | int64 |
| `first_name`, `last_name` | `faker` | `person_first_name`, `person_last_name` | string |
| `email`, `phone` | `faker` | `person_email`, `person_phone` | string |
| `city`, `postcode` | `faker` | `address_city`, `address_zip` | string |
| `ssn`, `street`, `note` | `redact` | default text | string |
| `birth_date`, `order_date` | `date_shift` | `min_days: -30, max_days: 30` | date32 |
| `balance`, `amount` | `bucketize` | `width: 100` (an integer), `format: lower` | string: the integer lower bound as text, for example `1200` (B7) |
| `status`, `channel` | passthrough | none | string |

MASK provider names are checked with `providers_v2.get_default_registry().get_capabilities(name)` (B4). GENERATE uses the Faker method names from `list_generate_faker_providers()` (B5), and S1 freezes one name per generated column. S1 freezes the provider names, the `bucketize` parameters, the label rendering, the null rule per strategy and the expected output schema in `scenarios.py`, each from the 1k run. AT-3 checks that every strategy is in the installed `strategy_catalog()`, each MASK provider passes `get_capabilities`, each GENERATE provider is in `list_generate_faker_providers()`, and that the delivered Parquet types and the bucket labels match the frozen values. The page lists each strategy by name.

| Id | Flow | Sizes (rows per table) | Denominator |
|---|---|---|---|
| MASK | `customers` Parquet in, Parquet out | 1M, 10M, 100M | input rows: N |
| MASK-SCAN | MASK plus `scan before(regex)`, default `warn` policy | 1M, 10M, 100M | input rows: N |
| SUBSET-MASK | `customers` and `orders`; sample 10% of `customers` by `customer_id`; follow `orders.customer_id -> customers.customer_id`; mask both; Parquet out | 1M, 10M, 100M | input rows: 2N (both tables). Delivered rows and retention shown too |
| MASK-CSV | MASK with CSV in and CSV out (explicit types on read) | 1M, 10M | input rows: N |
| GENERATE | Generate N rows of the `customers` schema, Parquet out | 1M, 10M, 100M | output rows: N |
| MASK-REPEAT | The MASK pipeline at 1M, run as its own cell after the host's other cells. Not shown as a table cell; used for the repeatability rule in 5.5 | 1M | input rows: N |

### 5.2 Machine classes

Frozen in `scenarios.py` with exact byte counts.

| Class | Logical CPUs | Nominal memory (bytes) | Label | Host |
|---|---|---|---|---|
| Small | 4 | 17179869184 (16 GiB) | 16 GiB | Capped on a larger Linux host, or a GCP VM with that shape |
| Medium | 8 | 34359738368 (32 GiB) | 32 GiB | Capped on a larger Linux host, or a GCP VM with that shape |
| Large | 16 | 68719476736 (64 GiB) | 64 GiB | One GCP VM (n2-standard-16, pd-ssd), no cap |
| Laptop | 10 (M4, 4P+6E) | the Mac's `hw.memsize`, read once in S2a and pinned | 16 GB | The Mac mini as it is. Its own column |

Units: CPUs are logical CPUs (vCPU on GCP, hardware threads elsewhere). Linux limits are GiB. The Mac shows installed RAM by its label and is checked by its pinned byte count. On a capped run the scope sets `MemorySwapMax=0`; the host's swap state is recorded. GCP VMs are described by machine type.

Applying limits. On a capped run each invocation (validate, warmup, timed) runs as `systemd-run --scope -p AllowedCPUs=<set> -p MemoryMax=<limit> -p MemorySwapMax=0 <launcher> ...`. The scope only applies the caps. Nothing is read from it after the process exits.

Class check (R3-6). The harness reads the memory ceiling itself and the child reports what it used. The check always compares with the selected class's CPU count and nominal bytes. Three cases:

| Case | Ceiling read by the harness | Valid when |
|---|---|---|
| Capped Linux | while the child runs: the tightest `memory.max`, `cpu.max` and `cpuset.cpus.effective` up the child's cgroup ancestor chain | tightest memory equals the class nominal bytes, usable CPUs equal the class CPUs |
| Uncapped Linux (Large, or a Small or Medium GCP VM) | `MemTotal` from `/proc/meminfo`, `nproc`, and no finite `memory.max` or `cpu.max` in the chain | CPUs equal the class CPUs, `MemTotal` at most the class nominal bytes and at least 95% of them |
| macOS (Laptop) | `sysctl hw.memsize`, `hw.logicalcpu` | `hw.memsize` equals the pinned byte count, CPUs equal 10 |

In every case the child's `decoy run --json` `resources` envelope must show `threads_source` and `max_memory_source` both `auto`, `threads` equal to the class CPUs, and `max_memory_bytes` equal to the auto budget for the ceiling the harness read: 25% of that ceiling (B10), within 1% for rounding. S2a confirms this formula on each measurement host against the engine's own resolver and records it. The attempt records the class, its nominal bytes, the observed ceiling in bytes and the child's budget. A run that fails a check is refused before timing. If the child exits without the envelope (a failure), the class check from the harness side is still recorded.

The child environment is built from an allowlist (`PATH`, `HOME` set to a fresh directory, `LANG`, `TMPDIR` set to the attempt's scratch, `DECOY_BENCH_MASK_KEY`). `DECOY_THREADS`, `DECOY_MAX_MEMORY` and `DECOY_HOME` are not passed, and the fresh home has no `settings.json`.

Cache: the page says "one untimed warmup, OS caches left enabled". GENERATE has no input files, so its warmup only loads the program.

### 5.3 The harness

Commands. Release and provisional modes are separate entry points so a dev build cannot take the release path.

- `python scripts/bench/run.py --campaign <manifest> --cell MASK/10M --class medium` (S2b, release). Reads the campaign manifest (5.5), which names the candidate directory.
- `python scripts/bench/run.py --provisional --decoy <path> --cell MASK/1M --class medium` (S2a). Every attempt it writes is `provisional: true`. The publisher refuses these in release mode and the site check refuses them in every build.

Release identity (R3-1). S2b extracts a context manager `verified_install(candidate, dist, pubkey, target)` from `packaging_tools/smoke_install.py`. It runs the existing smoke steps `candidate`, `version_document`, `installer_key` and `install` into a fresh temp root, yields the absolute launcher path and the validated candidate record as `read_candidate` returns it (`cli_version`, `cli_sha`, `engine_tag`, `engine_commit`, `sha256sums_sha256`, B1) plus the target, and removes the root in its `finally`. `candidate_main` is changed to use the same context, with no change to its steps, summary or exit codes. S2b adds `identity_matches(cli_version, engine_version, record) -> bool` to `packaging_tools/candidate.py`: true when `cli_version == record["cli_version"]` and `f"v{engine_version}" == record["engine_tag"]` (B2). `scripts/release/record_smoke.check_match` calls it and keeps its own `sha256sums_sha256` comparison, so both callers use one rule. In release mode the whole attempt (version, validate, warmup, timed runs, guards) runs inside one `verified_install` lifetime, every invocation uses the yielded launcher, and after each run the harness calls `identity_matches` with the result's `ProducerInfo` CLI and engine versions. The campaign manifest pins one candidate by its sums digest; a replacement candidate makes a new campaign.

One attempt (a cell key: campaign, scenario, size, class, host):

1. Start marker: the harness creates `<campaign>/<scenario>/<size>/<class>/<host>/` with an exclusive create and writes `started.json` (time, harness commit). If the directory exists, the harness refuses: one attempt per cell key. A retry needs a new campaign.
2. Preflight: fixture sha256 check; free space on each device the attempt uses (fixture, output, spill in `TMPDIR`, guard scratch), summed per device, against the per-device budget in `scenarios.py`. Refuse with the device and the shortfall.
3. `decoy validate <pipeline> --json` once with the launcher, under the same class limits as the runs. Exit 5 ends the attempt as `refused` with the code taken by the rule below. Any other failure ends it as `failed` with the reason.
4. One untimed warmup, then 5 timed invocations at every size. Each invocation gets its own new directory `inv-<n>/` (project, output, result). The result path must not exist before spawn. The supervisor starts `decoy run <pipeline> --json --result <path>` in its own process group (inside the scope on a capped run) and times spawn to exit with `time.monotonic_ns()` outside the child. A sampler sums RSS over the process tree (the child and all its descendants, psutil) every 100 ms and keeps the highest sum and the count of missed samples. `ru_maxrss` of children is recorded as a labelled side figure.
5. After each invocation, outside the timer: read the result through `RunResultRead`, then run every check the scenario requires (5.4) and record each by id with `passed` or `failed`. Record delivered rows and bytes per table. Delete that invocation's output. An invocation that is not a success ends the attempt; the rest are not run.
6. Write the evidence: `commands.txt` first, then `attempt.json` last with `publish_private_once` (staged, then one create-once rename). `attempt.json` is the completion marker. An attempt with `started.json` and no `attempt.json` is `interrupted`. Scratch is removed on success, guard failure, timeout and interrupt; fixture and evidence roots are outside the cleanup path.

Capacity code (R3-7). For validate (B11): the code is the first `messages[]` entry with severity `error` whose `code` is in `capacity_codes()`; a validate exit 5 payload can hold other errors too, and those are recorded but not used. For run (B12): the top-level `code`, else `reason.code`. If no code is found in either shape, the state is still `refused` with the reason "capacity refusal; code unavailable".

Exit classification of one invocation, from the CLI's exit codes only:

| Outcome | Evidence | Cell state |
|---|---|---|
| success | exit 0, a result document at the new path that `RunResultRead` accepts, every required check passed | counts toward the set |
| refused | exit 5 from validate or run | `refused`: "Refused at this size" with the capacity code, or "capacity refusal; code unavailable" |
| timeout | the 2 h limit hit; the supervisor kills the process group | `timeout`: "Did not finish in 2 h" |
| runtime | exit 3 | `not_measured`: "runtime error", and a QA finding |
| guard | exit 0, a required check fails | `not_measured`: "guard failed: <check id>", and a QA finding |
| result | exit 0 with a missing, unsupported-major or partial-delivery result | `not_measured`: "result unusable" |
| signal | killed by a signal the harness did not send, including SIGKILL | `not_measured`: "killed by signal <n> (cause not confirmed)" |
| other | any other exit code, disk full, launch failure, cancel | `not_measured` with the named reason |

### 5.4 Evidence-qualification contract (all scenarios)

This is the one contract for what makes a timed invocation count, what makes a cell measured, and how 5 runs become the figures on the page. `scripts/bench/scenarios.py` holds its frozen tables. `_guard.py` produces the check results, `publish.py` qualifies cells and reduces them, and `check-performance.mjs` recomputes the displayed-coordinate and reduction rules from the site file. No other place defines these rules.

#### Required checks per scenario

Frozen as `REQUIRED_CHECKS` in `scenarios.py`. Every timed invocation records each id with `passed` or `failed`.

| Check id | Predicate | Scenarios |
|---|---|---|
| `result_doc` | result at the invocation's own path, parses through `RunResultRead` with a supported major, success status, a delivery entry for every expected table, the expected config digest, an invocation id distinct from every earlier invocation in the attempt, and `identity_matches` on its `ProducerInfo` (release mode) | all |
| `rows` | delivered rows, counted by the harness from the files, equal the expected count (see the displayed-coordinate rule): `i4_rows.check_mask` for mask, `i4_rows.check_generate` for GENERATE | all except SUBSET-MASK |
| `subset_rows` | delivered `customers` rows equal `max(1, floor(0.1 * N))`, with unique `customer_id`, each present in the source | SUBSET-MASK |
| `schema` | names, order, physical and logical types and nullability equal the frozen schema (`i5_schema`); CSV is read with explicit types | all |
| `marker_scan` | a streaming pass over every string column of every delivered file, one row group (or CSV block) at a time, finds no value containing `pgmark` | all mask scenarios |
| `key_join` | for each delivered table, a sample of `min(10_000, delivered_rows)` distinct primary keys from the delivered table (fixed sample seed); `customers` rows join the source by `customer_id`, `orders` rows by `order_id`; each sampled key matches exactly one source row and appears once in the delivered table | all mask scenarios |
| `column_predicates` | on the joined sample, every column satisfies its strategy predicate (table below) | all mask scenarios |
| `pair_set` | the guard computes the source `(order_id, customer_id)` pairs whose `customer_id` is in the delivered `customers` set, and the delivered `orders` pairs equal that set exactly, with no duplicate rows. At 10M and 100M a bounded, disk-backed sort and merge in scratch, outside the timer | SUBSET-MASK |
| `pre_scan` | the result has a check with id `pre_scan`, status `passed`, and `check.counts.passed` (wire `counts.pass`) equal to the frozen positive count (B9) | MASK-SCAN |
| `generate_domains` | `customer_id` unique; each column within its declared domain (non-null rate, string length range, date range, the 5 `status` values); no all-null column | GENERATE |

The subset row check does not use `i4_rows.check_subset`, which only rejects growth (B14).

#### Column predicates (mask scenarios)

One predicate per strategy, with the exceptions the strategy allows. These replace any per-row inequality rule.

| Strategy | Predicate on each joined sample row | Allowed |
|---|---|---|
| passthrough | output equals source, nulls included | |
| `faker`, `redact` | source null gives output null, per the null rule S1 froze; a non-null output carries no marker (`marker_scan`). Because every source value carries a marker, output and source are disjoint by construction | a Faker value equal to some other row's source value |
| `date_shift` | output minus source is between -30 and 30 days inclusive; null stays null. Over the sample, at least 90% of non-null rows changed. Offsets are keyed per row (B8), so a zero shift has probability 1 in 61 per row and the expected changed share is about 98% | a zero-day shift on any single row |
| `bucketize` | output is a string equal to the frozen rendering of `floor(source / 100) * 100`; null stays null | a source value on a bucket boundary, whose label equals its own value |

An unmasked column fails: a Faker or redact column by `marker_scan`, a date column by the 90% rule, a numeric column by `schema` (float64 instead of string) and by its label.

#### Qualification

A timed invocation counts only when its outcome is success and every id in `REQUIRED_CHECKS[scenario]` is present in its record with `passed`. A missing id is a failure of that invocation, recorded as "required check <id> missing".

A cell key is:

- `not_measured`: "not run" when it has no `started.json`; "attempt interrupted" when it has `started.json` and no `attempt.json`.
- its terminal state from 5.3 when the attempt ended early.
- `measured` only when the attempt is complete and all of these hold: 5 timed invocations that count, each with a finite positive wall time; one observed route over the 5 (route fields recorded as observed, null ones included); delivered rows per table equal over the 5; fixture, pipeline digest and candidate identity that match the manifest; and the displayed-coordinate rule. Otherwise it is `not_measured` with the failing rule named: "route changed between runs", "delivered rows changed between runs", "required check <id> missing", and so on.

These outcomes never stop the publisher.

#### Displayed-coordinate rule

A cell shows `(scenario, rows_per_table, class)`. It is consistent only when:

- its evidence record path is `docs/records/perf-guide/<campaign>/<scenario>/<size>/<class>/<host>/`, and `<scenario>`, `<size>` (the 1M, 10M, 100M label of `rows_per_table`) and `<class>` equal the cell's own fields;
- `input_rows` has each of the scenario's input tables at `rows_per_table` (none for GENERATE);
- `delivered_rows` equals the scenario's expected count: `customers == rows_per_table` for MASK, MASK-SCAN, MASK-CSV, MASK-REPEAT and GENERATE; `customers == max(1, floor(0.1 * rows_per_table))` and `orders <= rows_per_table` for SUBSET-MASK.

The publisher applies it when it qualifies a cell. The site check applies it to every measured cell, so a cell moved to another scale fails even when its times and throughput are recomputed correctly.

#### Reduction of 5 runs to the shown figures

Warmup never enters any figure. From the 5 timed invocations, in invocation order:

- Times: `timed_ns` holds all 5 raw wall times. `median_s`, `min_s`, `max_s` come from them. Rows per second is the denominator (5.1) divided by `median_s`.
- Memory: the shown figure is the highest of the 5 sampled peaks, labelled "highest sampled RSS of the process tree, 100 ms, highest of 5 timed runs". `timed_memory` holds all 5.
- Delivered bytes per table: taken from the median invocation, which is the third when the 5 are sorted by wall time, ties going to the lower invocation number. Labelled "from the median run". `timed_delivered_bytes` holds all 5 per table.
- Delivered rows per table: equal over the 5 by the qualification rule, so one value.
- `high_variance`: max/min wall time above 1.5.

### 5.5 Campaign and records

Campaign manifest, frozen and committed before any timed run: candidate directory and sums digest, fixture pins, the scenario matrix and its frozen pipelines (by digest), `REQUIRED_CHECKS`, the class table, the cell keys (scenario, size, class, host), 5 timed runs, timeout, the variance flag rule, the repeatability rule and the stop conditions (5.8). The harness refuses a cell key not in the manifest.

Records in the CLI repo: `docs/records/perf-guide/<campaign-id>/<scenario>/<size>/<class>/<host>/` with `started.json`, `commands.txt` and `attempt.json` (the one canonical structured record). `attempt.json` holds:

- host and class facts (CPU model, logical CPUs, class nominal bytes, observed ceiling bytes, swap, OS, kernel, disk device and filesystem, machine type)
- the class check and the child's `resources` envelope
- release identity, fixture pins, per-table input rows and on-disk bytes
- the terminal state and reason, with the capacity code when there is one
- for each invocation: kind (`warmup` or `timed`), invocation id, wall ns, the sampled memory figure with label and units, missed samples, `ru_maxrss` with label and unit, outcome, route as observed, delivered rows and bytes per table, and each check id with its result

A campaign `summary.md` (`Status: record`) is rendered from the JSON by `scripts/bench/record.py`; nobody edits it. Records are append-only.

Variance flag: a measured cell with max/min wall time above 1.5 is published with `high_variance: true` and the page shows "high variance". No rerun, no selection.

Repeatability: the publisher compares each host's `MASK-REPEAT/1M` median with its `MASK/1M` median. If both are measured and differ by more than 10%, every cell from that host is published as `not_measured`: "host failed repeatability". If either is not measured, the host's cells carry the note "repeatability not shown".

### 5.6 Site data

`python scripts/bench/publish.py --campaign <manifest> --out performance.json` reads every cell key in the manifest and is the sole owner of qualification and reduction, both by the contract in 5.4. `publish.py --check performance.json --campaign <manifest>` regenerates and requires byte equality. Schema version 1:

- `schema_version`, `generated_by`, `release_version`, `evidence`: CLI repository, the 40-hex commit that holds the records, and the campaign id. `status` (`placeholder` or `published`) is derived: `published` only when every measured cell comes from a non-provisional attempt and the headline rule (5.8) holds.
- `classes`: id, label, logical CPUs, nominal bytes, label unit, observed ceiling bytes, host and machine type, how applied.
- `scenarios`: id, label, description, strategies by name, denominator kind.
- `cells`: scenario, `rows_per_table`, class, `state` (`measured`, `refused`, `timeout`, `not_measured`) and `reason`. A measured cell holds `timed_ns` (5 raw wall times, in order), `timed_memory` (5 sampled peaks, in order), `timed_delivered_bytes` (5 per table, in order), `input_rows`, `input_bytes`, `delivered_rows` per table, `route`, `high_variance`, and `evidence` (record path and the 40-hex commit). The reduced `median_s`, `min_s`, `max_s`, `rows_per_s`, `memory` (value, label, unit) and `delivered_bytes` per table (with the "from the median run" label) are written too, so the page reads them directly.

Publisher refusals (exit 1, named reason), only for campaign-level faults: a provisional attempt in release mode; attempts on a candidate other than the manifest's; an attempt directory whose key is not in the manifest; `published` asked for when the headline rule (5.8) does not hold.

### 5.7 The pages

S4 (decoy-site):

- `/how-it-works/#performance`: intro (whole `decoy run`, source read to delivered output, one untimed warmup with OS caches left enabled, default settings, the strategies by name, release version, dates, link to the evidence commit). "Pick a box": for each scenario and size, the smallest tested Linux class with a measured cell and its median; lower classes are shown with their state; the Mac is shown on its own. One table per scenario: rows per table by class. A measured cell shows median time and input rows per second (output rows per second for GENERATE). The details line has range, input and delivered rows and bytes per table with the "from the median run" label (retention for SUBSET-MASK; zero source bytes for GENERATE), memory with its full label, route, host, date, the "high variance" flag when set, and a link to the attempt record. Other states show their label and reason. No projected values and no projection caption.
- `/cli#performance`: the table is replaced with one sentence and a link to `/how-it-works/#performance`. The anchor stays. The Linux-only and projection text go.
- `src/_data/performance.json` in S4 is a placeholder: schema 1, `status: placeholder`, every cell `not_measured` with reason "release benchmark not run yet", zero numbers. Provisional numeric data exists only in fixture tests and local preview input, never in `src/_data/`.

`scripts/check-performance.mjs`, run by `check:site`, which `npm run check` runs and the Pages workflow runs before upload. It is a consistency recompute. It catches an accidental error (a stale median, a cell moved to another scale, a copy mistake). It does not detect a deliberate edit that changes the raw values and the derived values together, and it does not resolve the evidence commit. Protection against deliberate edits is section 13.

- Schema 1, `generated_by` present, no key named `projected`, `extrapolated` or `estimate`.
- `status: placeholder` passes only if no cell is measured. `status: published` passes only if every measured cell has a 40-hex evidence commit. Any other status, and any provisional flag, fails in every build.
- For each measured cell: the displayed-coordinate rule (5.4), including the record path segments and the delivered-row count; `timed_ns` and `timed_memory` have exactly 5 finite positive entries and `timed_delivered_bytes` has 5 per table; `median_s`, `min_s`, `max_s`, `rows_per_s`, `high_variance`, `memory` and `delivered_bytes` equal the values recomputed by the reduction rule (5.4).
- Built HTML of both pages has no "projection" or "projected", and the `/cli` link resolves to the `/how-it-works` anchor.

The S5 PR runs `publish.py --check` against the committed records, and the S5 record lists its output. The reviewer of a later site data PR is expected to rerun it.

### 5.8 Row close and cost

Headline rule: the row closes only when the published file has measured cells for MASK and GENERATE at 1M and 10M on Large, Medium and Laptop. Any other cell may be in any state. A file where a headline cell is not measured cannot be `published`.

S5 elapsed time: the full matrix is 15 cells per class (14 plus `MASK-REPEAT`), 90 timed and warmup invocations per class, about 360 over four classes, plus validation and fixtures. Before the owner approval ping, a pilot runs MASK and GENERATE at 1M and 10M on the Dell or Mac and estimates the campaign's machine hours, disk and GCP cost (for budgeting only, never published). Stop conditions in the manifest: a GCP spend cap, a wall-clock cap per class, and stop on the first guard failure. VM and disk teardown is a checklist step in the S5 record.

## 6. Failure modes

| Failure | Handling |
|---|---|
| Dev or foreign build in release mode | Release mode runs only the launcher yielded by `verified_install`, and `identity_matches` checks every result. Provisional mode marks every attempt provisional, and both the publisher and the site check refuse provisional data |
| Candidate install removed mid-campaign | The attempt runs inside one `verified_install` lifetime; cleanup happens after the last guard (AT-4) |
| Candidate replaced after measurement | New campaign; old attempts cannot publish under it |
| Limits not applied or not seen by the child | Refuse the attempt before timing (5.2) |
| Missing mask key | `decoy run` fails at key admission (AT-3) |
| Validate or run exit 5 | `refused` with the capacity code, or "code unavailable" when the envelope has none |
| Process killed by SIGKILL or another signal | `not_measured`: "killed by signal <n> (cause not confirmed)" |
| Exit 3, disk full, launch failure | `not_measured` with the named reason |
| Timeout 2 h | Process group killed, `timeout` |
| Result missing or partial with exit 0 | `not_measured`: "result unusable" |
| A required check fails | `not_measured`: "guard failed: <check id>" and a QA finding |
| A required check is missing from a record | `not_measured`: "required check <id> missing" |
| Correct masking with a zero date shift, a bucket-boundary value or two orders for one customer | Passes (5.4 allowed column) |
| A cell moved to another scale or class in the site file | Site check fails (displayed-coordinate rule) |
| Interrupt mid-attempt | `started.json` without `attempt.json`: `not_measured`: "attempt interrupted"; scratch removed; other attempts untouched |
| Second attempt for the same key | Refused at the start marker |
| High variance | Published with the flag |
| Host not repeatable | Host cells `not_measured` (5.5) |
| Fixture bytes differ across hosts | Refuse; the pins in `fixture.json` name the difference |
| Disk too small for fixture | Writer refuses before writing; nothing published |
| Interrupt during fixture creation | Only a staging directory is left; next run removes it |
| MASK-SCAN not supported by the candidate | No `pre_scan` check: `not_measured`: "pre-scan not in this release" |
| A non-headline cell refused, failed or mixed-route | Published with its state; the campaign still publishes |
| A binding in 9d is false on the candidate | The slice stops and the plan is revised; no workaround in the harness |
| Deliberate edit of site data | Out of scope (V1 threat model); reviewed PRs; section 13 |
| Engine performance work lands after S5 | New candidate, new campaign |

## 7. Acceptance tests

Unit tests in `tests/unit/bench/` (T0 and T1, small data). Fixture tests for decoy-site in `scripts/fixtures/performance/*.test.mjs` (the shape `scripts/run-fixtures.mjs` finds). Tests that prove a binding (9d) run the real installed code, not a mock.

- AT-1 Fixture determinism, bounds and disk: same seed, N and pins give the same sha256 twice; another seed differs. With 1k row groups, peak live rows stay at one row group as N goes 3k to 30k. Seeded mutation: build the whole table first; the test fails. With a fake `statvfs` below the summed per-device need, the writer refuses before any file is written. An interrupt during writing leaves only a staging directory; a retry produces the fixture and an existing fixture and evidence directory are unchanged.
- AT-2 Fixture shape: types; every `orders.customer_id` in `customers`; null rates within 1 point; every non-null value of each Faker or redact column carries a unique marker; passthrough columns carry none; every `email` is a whole-field address `pgmark<id>@scan.invalid`; `balance` and `amount` are non-negative.
- AT-3 Scenario pipelines (installed dev CLI on a 1k fixture; proves B4 to B7 and B9): every strategy is in `strategy_catalog()`; every MASK provider passes `get_default_registry().get_capabilities`; every GENERATE provider is in `list_generate_faker_providers()`; a GENERATE name such as `postcode` used as a MASK provider is rejected by the check. Every scenario runs through delivered output, and the delivered schema equals the frozen one, with `balance` and `amount` delivered as strings whose values equal the frozen rendering of `floor(v / 100) * 100`. MASK-SCAN gives `pre_scan` `passed` with `check.counts.passed` equal to the frozen count, and that count is above zero; a variant with `email` as passthrough gives `pre_scan` `warned` (skipped with its reason if pre-scan is not supported). The key is passed as 64 hex characters; with `DECOY_BENCH_MASK_KEY` removed, `decoy run` fails with the key admission reason.
- AT-4 Release identity (proves B1 to B3): `verified_install` on a valid candidate yields a launcher that runs `decoy --version` after verification and the record with `engine_tag`, and the root is gone after the context exits, also when the body raises. `candidate_main` gives the same summary and exit codes as before (existing smoke tests), and the existing `record_smoke` tests pass with `check_match` calling `identity_matches`. `identity_matches` is false for a CLI-only mismatch and for an engine-only mismatch (`engine_version` `1.2.3` against `engine_tag` `v1.2.4`), and true for a match. A launcher outside the context is refused in release mode; two candidates with different sums give two campaigns that cannot mix.
- AT-5 Provisional path: provisional attempts carry the flag; the publisher in release mode refuses them; the site check refuses them in a preview and a production build.
- AT-6 Class check (proves B10): capped Linux with matching tightest limits passes; a tighter ancestor `cpu.max` or `memory.max` fails. Uncapped Linux Large with 16 CPUs and `MemTotal` 62.8 GiB passes; 32 GiB fails. Uncapped Linux Medium with 8 CPUs and `MemTotal` 31.3 GiB passes; with 16 CPUs it fails. macOS with `hw.memsize` equal to the pinned bytes and 10 CPUs passes; a different byte count fails. In each case a `resources` envelope with a source other than `auto`, a wrong `threads`, or a `max_memory_bytes` not 25% of the ceiling fails. An inherited `DECOY_THREADS` or `settings.json` is not seen by the child. A capped 32 GiB host whose envelope reports 8 GiB passes (the budget, not the limit).
- AT-7 Supervisor: a fake child that sleeps 0.3 s and starts a grandchild holding 50 MB gives a wall time of at least 0.3 s and a sampled sum of at least 50 MB. Seeded mutation: sample only the direct child; the test fails. A large fake run followed by a small one: the second run's figure is not raised by the first. On timeout the grandchild is gone.
- AT-8 Guards (5.4): a correct output passes every required check of its scenario. Passing cases that must stay passing: a row with a zero-day shift; a source amount on a bucket boundary (`1200.0` gives `1200`); a null `phone` that stays null; a SUBSET-MASK output where one retained customer has two orders; a SUBSET-MASK output at 1k where fewer than 10k keys exist. Each of these fails by check id, also with a result document that agrees with the wrong output: a permuted unmasked output; markers rotated between customer rows; a sampled key that appears twice; an unmasked date column (every shift zero); an unmasked amount column (float64 kept); a generated column of nulls; a type changed with names and counts kept; a full-copy subset; a duplicated parent row; an order reassigned to another retained customer; an empty child table; a missing child; a duplicated child; an orphan. MASK-SCAN: `warned`, a wrong count, and an ordinary MASK result each fail.
- AT-9 Result and records (S2a): exit 0 with a missing, unsupported-major or partial-delivery result is "result unusable". Two valid invocations in a row whose result files reuse an inode number both pass. A second start for the same cell key is refused. An interrupt after `commands.txt` and before `attempt.json` leaves an attempt the reader marks interrupted. A seeded failing marker and the benchmark key are run through the error paths; neither appears in terminal output or any record file.
- AT-10 Exit classification (proves B11, B12): validate exit 5 with a `messages[]` payload that holds a capacity code and a second, non-capacity error keeps the capacity code; run exit 5 with a top-level `code` keeps it; run exit 5 with only `reason.code` keeps that; run exit 5 with neither (the bare `MemoryError` shape) gives `refused` with "capacity refusal; code unavailable". Exit 3, SIGKILL, timeout, and a mixed success and failure set each give the state in 5.3.
- AT-11 Publisher qualification and refusals (S3): one campaign with measured headline cells, a validate refusal, a mixed-route cell, an interrupted attempt and a cell never run publishes, with each non-measured cell in its state and reason. A record that is good except that one timed invocation lacks the `pair_set` id gives `not_measured`: "required check pair_set missing". A cell whose delivered rows differ between two timed runs gives `not_measured`: "delivered rows changed between runs". A GENERATE record whose path says `10M` while its delivered rows are 1M gives `not_measured` by the displayed-coordinate rule. Refusals: provisional in release mode, a foreign candidate, an unlisted key, `published` with a headline cell not measured. Seeded mutations: count a warmup as timed; drop the required-check test; each makes a test fail. The key and marker do not appear in the site file.
- AT-12 Publisher output (S3): from fixed attempts the output equals a golden file. The fixed attempts have 5 unequal wall times whose median is invocation 4, 5 unequal memory peaks whose highest is invocation 2, and 5 unequal delivered byte counts; the output shows the peak of invocation 2 and the bytes of invocation 4, and a warmup with a higher peak than any timed run does not change the memory figure. SUBSET-MASK has the 2N input denominator and delivered rows and bytes; GENERATE has zero input bytes, N delivered rows, output rows/s and output bytes; a cell with max/min 1.6 has `high_variance: true`; a host whose repeat median is 12% off has its cells `not_measured`; `--check` fails after any byte change.
- AT-13 Site check (S4): the placeholder passes in a production build; a provisional file fails in every build. Each of these fails: an edited median; an edited `high_variance`; an edited `memory` or `delivered_bytes` that no longer matches its 5 raw values; a GENERATE cell whose `rows_per_table` alone changes from 1M to 10M, with times and throughput recomputed to match; a cell whose record path names another size or class; a malformed evidence commit or path; a flipped status; a `projected` key. Seeded mutations: remove the recompute, then remove the displayed-coordinate check; the edited-median and GENERATE-scale tests fail.
- AT-14 Pages (S4): the built `/how-it-works` section has no projection text, shows each state label and the "high variance" flag, shows delivered bytes with "from the median run" and memory with its full label, and table headers have `scope`; the GENERATE fixture page shows zero source bytes, N delivered rows, output rows/s and output bytes; `/cli#performance` links to the canonical section; neither page has the Linux-only claim.

S5 evidence (R3), in `docs/records/2026-<mm>-<dd>-perf-guide-release.md`:

- AT-15 Every manifest cell key has a state and reason; all attempts are on one candidate; the headline rule holds; `publish.py --check` passes on the committed site file; the memory label, the bytes label and the "does not detect deliberate edits" statement are on the page.
- AT-16 Every host has a `MASK-REPEAT/1M` result and the repeatability outcome is shown.

## 7a. Defect classes

| # | Class | Applies | Structure | Proof (mutation) |
|---|---|---|---|---|
| 1 | value | Yes: records, terminal and site file must not carry source values or the key | records hold counts, times, versions and check ids only; the key is per attempt, in memory, passed by one env var | AT-9, AT-11 (mutation: write the failing value or the key into a record) |
| 2 | cleanup | Yes: scratch at 100M, orphaned processes, the install root | per-attempt scratch removed on every exit path; process group killed; `verified_install` removes its root in `finally` | AT-4, AT-7 (mutation: kill only the child) |
| 3 | state | Yes: env, settings, earlier runs, earlier results leak in | env allowlist, fresh home, own directory per invocation, result path absent before spawn | AT-6, AT-7, AT-9 |
| 4 | route | Yes: mixed routes under one label | route per invocation; mixed set is `not_measured` | AT-11 |
| 5 | referential | Yes: subset output | exact pair comparison, unique parents, key join on each table's own key | AT-8 |
| 6 | untrusted | Low: records are ours; deliberate edits are out of scope under the V1 threat model | site check recomputes for accidental errors; section 13 for more | AT-13 |
| 7 | toctou | Low: fixture changed between check and run; disk filled between check and write | sha256 per attempt; disk check before writing; staged fixture | AT-1 |
| 8 | weak | Yes: a lax guard, a missing check, a relabeled cell or a different reduction publishes a false claim | one evidence-qualification contract (5.4) used by guard, publisher and site check; seeded mutations on guards, required checks, warmup counting, the recompute and the coordinate check | AT-8, AT-11, AT-12, AT-13 |
| 9 | over-strict | Yes: a guard rejects correct output and stops the campaign | per-strategy predicates with their allowed cases (5.4); passing cases in AT-8 | AT-8 |
| 10 | contract drift | Yes: the harness assumes a field, catalog, type or envelope that the code does not have | section 9d bindings, each proved by a test on the real installed code | AT-3, AT-4, AT-6, AT-10 |
| 11 | refactor drift | Yes: `candidate_main` moves onto `verified_install`; `check_match` moves onto `identity_matches`; `/cli` table removed | existing smoke and record-smoke tests unchanged; both pages built | AT-4, AT-14 |
| 12 | frozen contract | Low: the site data schema changes for both readers in one slice; the run result is read through the public versioned reader | `schema_version`; `RunResultRead` major check | AT-9, AT-13 |

## 8. Design notes

- Choke points: `scenarios.py` holds every frozen rule; `publish.py` is the one producer of the site file and the one owner of qualification and reduction; `check-performance.mjs` only recomputes the 5.4 coordinate and reduction rules and checks shape. It decides nothing new.
- One contract for evidence (5.4): a new scenario adds a row to `REQUIRED_CHECKS` and, if it uses a new strategy, a row to the column predicate table. It does not add a new qualification paragraph.
- One place per fact: scenarios, strategies, providers, schema, scan count, class bytes, required checks, denominators and disk budgets in `scenarios.py`; one canonical `attempt.json` per attempt; `summary.md`, commands and the site file derive from it. External facts are in 9d.
- One attempt per cell key. No rerun or selection rule exists, so there is nothing to agree on between the publisher and the site.
- The supervisor drives the installed CLI as a user does, so numbers include process start, imports and the write.
- Memory a user needs is the class limit the run fit in. The memory figure is a labelled guide, not an accounting figure.

## 9. Placement

CODEMAP (S1): new row "Benchmark tooling (not shipped)": `scripts/bench/`, tests in `tests/unit/bench/`, imports no private product module (same rule as "QA tooling (not shipped)"). The "Roadmap, plans, records" row gains one line: `docs/records/perf-guide/<campaign>/<scenario>/<size>/<class>/<host>/` holds JSON attempt records, not dated Markdown.

| File | Lines (est.) | Slice |
|---|---|---|
| `scripts/bench/fixtures.py` (pins, chunked writer, markers, disk check, staging) | 340 | S1 |
| `scripts/bench/scenarios.py` (pipelines, strategies, providers, schema, label rendering, null rules, scan count, class table, `REQUIRED_CHECKS`, denominators, disk budgets) | 300 | S1 |
| `scripts/bench/_supervise.py` (scope, spawn, timer, sampler, env, exit classification, capacity code) | 320 | S2a |
| `scripts/bench/_limits.py` (class check, three cases) | 180 | S2a |
| `scripts/bench/_attempt.py` (start marker, invocation dirs, write order, result read) | 220 | S2a |
| `scripts/bench/run.py` (both entry points) | 200 | S2a, S2b |
| `packaging_tools/smoke_install.py` (`verified_install` extracted; net change about +40) | existing | S2b |
| `packaging_tools/candidate.py` (`identity_matches`, about +10) and `scripts/release/record_smoke.py` (`check_match` calls it) | existing | S2b |
| `scripts/bench/_release.py` (identity check, campaign manifest) | 160 | S2b |
| `scripts/bench/_guard.py` (required checks, marker scan, key join, column predicates, scan check; uses `scripts/qa/invariants`) | 360 | S2b |
| `scripts/bench/_subset_check.py` (bounded sort and merge of pairs) | 200 | S2b |
| `scripts/bench/record.py` (`summary.md`) | 150 | S2b |
| `scripts/bench/publish.py` (qualification, displayed-coordinate rule, reduction, refusals, `--check`) | 420 | S3 |
| `tests/unit/bench/test_*.py` | about 1100 over 9 files | S1 to S3 |
| decoy-site `src/how-it-works.njk` (section), `src/cli.njk` (section to link), `src/_data/performance.json` (placeholder), `scripts/check-performance.mjs` (240), `scripts/fixtures/performance/*.test.mjs`, `package.json` (`check:site`) | | S4 |
| CLI `docs/records/perf-guide/<campaign>/...`, `docs/records/2026-<mm>-<dd>-perf-guide-release.md`; decoy-site `src/_data/performance.json` (published) | data | S5 |

Every handwritten module stays under 600 lines. `smoke_install.py` must stay under 700 after the extraction; if it would not, `verified_install` goes in a new `packaging_tools/_verified_install.py`. No new public product names.

## 9a. Enumerations

### Exit paths of one invocation

- success: exit 0, usable result at its own path, every required check passed.
- refused: exit 5 from run (`src/decoy/cli/exit_codes.py:82`) or from validate (B11), with the capacity code or "code unavailable".
- timeout: 2 h, process group killed.
- runtime: exit 3 (`src/decoy/cli/exit_codes.py:66`).
- guard: exit 0, a required check fails.
- result: exit 0 with an unusable result document.
- signal: killed by a signal the harness did not send.
- other: unknown exit, disk full, launch failure, cancel; a harness interrupt leaves `started.json` without `attempt.json`.

Cell states: `measured`, `refused`, `timeout`, `not_measured` (with reason).

### Routes

- None forced; every observed `Route` field is recorded, including null ones (engine `src/decoy_engine/run_result/_model.py:276`).
- Two observed routes in one timed set: the cell is `not_measured` ("route changed between runs"), and the campaign still publishes.

### FK shapes

- `orders.customer_id -> customers.customer_id`, single column, downward follow, in SUBSET-MASK (B13).
- No other FK shape: MASK, MASK-SCAN, MASK-CSV, MASK-REPEAT and GENERATE use one table.

### Fields

- Fixture fields as in 5.1.
- Result fields read: producer, config digest, invocation id, status, per-table delivery, route, and the `pre_scan` check status and counts (B9).
- Child `resources` fields (B10).
- Candidate record fields (B1).

### Output surfaces

- Record files: `started.json`, `commands.txt`, `attempt.json`, `summary.md`.
- Terminal output of the harness and publisher.
- The site file and both pages (`decoy-site/src/how-it-works.njk:240`, `src/cli.njk:259`).

None carries a source value or the key.

## 9b. Reuse inventory

- `packaging_tools/candidate.py` `read_candidate`; the smoke steps `candidate`, `version_document`, `installer_key`, `install` of `packaging_tools/smoke_install.py` (`:451` to `:546`), extracted into `verified_install` and shared with `candidate_main` (`:647`); the identity rule of `scripts/release/record_smoke.py` `check_match` (`:97`), factored into `identity_matches`.
- `scripts/qa/invariants/i1_leaks.py` (marker approach, `bucketize` exemption), `i4_rows.py` (`check_mask`, `check_generate`), `i5_schema.py`.
- `scripts/qa/io.py` `staged_private`, `publish_private_once`; `scripts/qa/repro.py` process-group timeout pattern.
- `src/decoy/cli/gate/_run.py` `capacity_codes()`.
- Engine public `RunResultRead`, `list_generate_faker_providers` and `providers_v2.get_default_registry`; `decoy run --json` `resources`; `decoy validate --json`.
- Reference only, not imported: engine `scripts/fk-scale/_supervisor.py`, `build_fk_chain.py` and `validators/_leak_check.py`.
- psutil and PyArrow from `requirements-dev.lock`. decoy-site `scripts/run-fixtures.mjs` and `check:site`.

New: the chunked fixture writer, the supervisor and class check, the bounded subset check, the publisher and `check-performance.mjs`.

## 9c. Frozen contracts

None changed. The run result is read through the engine's public, versioned reader. `candidate_main` keeps its steps, summary schema and exit codes; `check_match` keeps its behavior. The site data file moves to schema 1, and both its readers (`how-it-works.njk`, `cli.njk`) change in the same slice.

## 9d. External contract bindings

Every fact about code outside `scripts/bench/` that the harness depends on. Sources are on `origin/main` (CLI `488d98b3`, engine `9f7bb1f4a`, site `c5a43f9`, as reviewed in R3). At the start of each slice the builder rechecks the rows that slice uses against `origin/main`. If a row is false, the builder stops and the plan is revised; the harness never works around a false binding. The test column names the test that runs the real installed code.

| Id | Fact | Source | Test |
|---|---|---|---|
| B1 | The candidate record has exactly `cli_version`, `cli_sha`, `engine_tag` (`v<semver>`), `engine_commit`, `sha256sums_sha256`; the strict reader rejects other fields. It has no `engine_version` | CLI `packaging_tools/candidate.py:43`, `:90` | AT-4 |
| B2 | The installed engine's version matches the candidate when `f"v{engine_version}" == engine_tag`; the CLI version matches by equality | CLI `scripts/release/record_smoke.py:97` | AT-4 |
| B3 | The smoke steps `candidate`, `version_document`, `installer_key`, `install` come before `bundle_key`, which reads the installed engine version | CLI `packaging_tools/smoke_install.py:451`, `:546`, `:554`, `:647` | AT-4 |
| B4 | MASK provider names are `person_*` and `address_*` (`address_city`, `address_zip`), checked by `providers_v2.get_default_registry().get_capabilities(name)` | engine `providers_v2/_faker_adapter.py:54`, `providers_v2/_registry.py:67`, `:146`; CLI `docs/guides/decoy-language/cheat-sheet.md:121` | AT-3 |
| B5 | GENERATE provider names are Faker method names (`first_name`, `email`, `city`, `postcode`) from the public `list_generate_faker_providers()` | engine `internal/faker_setup.py:608`; CLI cheat sheet `:173` | AT-3 |
| B6 | A 32-byte key given as 64 hex characters is read as 32 bytes | engine `secret_providers/_requirements.py:151` | AT-3 |
| B7 | `bucketize` with an integer width and `format: lower` on float input renders the integer lower bound as text; integer output needs `declared_integer_output`, which a float column does not set | engine `execution/_strategies/_bucketize.py:93`, `:103`, `:114`; `plan/_seed_envelope.py:229` | AT-3 |
| B8 | `date_shift` derives a keyed offset per row from the row's own value, uniform over `[min_days, max_days]` | engine `execution/_strategies/_date_shift.py:292` | AT-3, AT-8 |
| B9 | The result's pre-scan check has id `pre_scan`, a status, and counts whose parsed field is `counts.passed` (wire `pass`); the email detector matches whole values over a rate threshold | engine `profiling/pre_scan/_check.py:85`, `:96`; `run_result/_model.py:310`; `detection/detectors.py:284`; `detection/_scoring.py:38`, `:220` | AT-3 |
| B10 | `decoy run --json` `resources` has `threads`, `threads_source`, `max_memory_bytes`, `max_memory_source`; the auto memory budget is 25% of the ceiling | CLI `src/decoy/_resources.py:44`, `:48`, `:105`; `src/decoy/cli/run/_render.py:128`; engine `execution/out_of_core/_budget.py:332`, `:376`, `:391` | AT-6, S2a host check |
| B11 | `decoy validate --json` puts findings in `messages[]` with `code` and `severity`; a capacity refusal exits 5 and can coexist with other errors; the capacity code set is `capacity_codes()` | CLI `src/decoy/cli/validate.py:294`, `:301`, `:358`; `src/decoy/cli/gate/_run.py:32`, `:85` | AT-10 |
| B12 | `decoy run` exit 5 carries a top-level `code` only when it is a valid reason code, or a `reason` payload; a bare `MemoryError` can give neither | CLI `src/decoy/cli/run/_errors.py:298`, `:329`; `tests/e2e/test_run_capacity_widening.py:60`; engine `reason_adapter.py:135` | AT-10 |
| B13 | Subset keeps a sampled parent set and follows children by FK, so most source parents are absent and a parent can have many children | engine `subset/_seed.py:267`, `:277`; `subset/_closure.py:15` | AT-8 |
| B14 | `i4_rows.check_subset` only rejects growth; `check_generate` checks the exact count | CLI `scripts/qa/invariants/i4_rows.py:28`, `:32` | AT-8 |
| B15 | The scale label and the timing become a public claim at these template lines | site `src/how-it-works.njk:245`, `:257` | AT-14 |

## 10. Slices

| Slice | Content | Repo | Risk | Size | Depends on |
|---|---|---|---|---|---|
| S1 | Fixture writer with pins, markers, disk check and staging; frozen scenarios, strategies, providers, schema, label rendering, null rules, scan count, class table and `REQUIRED_CHECKS`; CODEMAP rows; AT-1 to AT-3 with a 1k installed dev CLI run per scenario | CLI | R1 | 1 day | none |
| S2a | Provisional measurement: supervisor, sampler, class check (three cases), env, exit classification and capacity code, start marker, invocation dirs, write order, result read; AT-6, AT-7, AT-9, AT-10; a real capped-scope check on the Dell, an uncapped check on the Mac, and the Mac's `hw.memsize` pinned | CLI | R2 | 1 day | S1 |
| S2b | Release qualification and correctness: `verified_install` extraction, `identity_matches`, campaign manifest, required checks and guards, bounded subset check, `summary.md`; AT-4, AT-5 (CLI half), AT-8 | CLI | R2 | 1 day | S2a |
| S3 | Publisher (qualification, displayed-coordinate rule, reduction, variance flag, repeatability, refusals) and `--check`; AT-11, AT-12 | CLI | R2 | 1 day | S2a (attempt schema) |
| S4 | Both pages, placeholder data, site check and fixture tests; AT-5 (site half), AT-13, AT-14; live review by Cam | web | R2 | 1 day | S3 site schema |
| S5 | Pilot and cost ping, campaign, records, publish, page live; AT-15, AT-16 | CLI, web | R3 | builder about 1 day; machine time from the pilot | row 94 candidate, final engine perf work, S1 to S4; PRE-SCAN-RUN for measured MASK-SCAN |

S1 to S4 can build now. S4 merges before S5. S4 is web work during the web pause, allowed because PERF-GUIDE is an owner row in the V1 release effort.

Recovery: the page data is one file. If a published number is wrong, revert the site data commit to the placeholder (which passes the production check) and measure the cell again in a new campaign.

## 11. Owner gates

- Before the GCP run in S5: a Slack ping with VM type, disk, the pilot's hour and cost estimate, stop conditions, and owner approval (one VM at a time).
- Before the page goes live: the owner reviews the S5 numbers and both pages.
- Open choice, default applies if no answer: class sizes as in 5.2.

## 12. Risks and pre-mortem

- Numbers look worse than competitors'. That is engine work, not a reason to tune the benchmark. The manifest freezes the workload first.
- A builder passes `--threads` or settings to go faster. AT-6 fails, and the child's `resources` envelope shows it.
- A builder drops a guard at 100M. The record then lacks a required check id, and the publisher marks the cell `not_measured` (AT-11).
- A builder loosens a guard to get a cell through. The column predicates and their allowed cases are frozen in `scenarios.py`, and the seeded mutations in AT-8 and AT-11 fail.
- A guard rejects correct output and stops the campaign. The allowed cases in 5.4 and the passing cases in AT-8 cover the known ones (zero shift, bucket boundary, many children per parent). A new one found in the pilot is a plan revision, not a builder fix.
- Someone edits `performance.json` by mistake. The site recompute and coordinate check (AT-13) catch a mismatch, and `publish.py --check` in review catches the rest. A deliberate consistent edit is not caught (section 13).
- A real out-of-memory kill shows as "killed by signal 9 (cause not confirmed)" instead of a memory verdict. Accepted: the page does not claim a cause it did not observe.
- One attempt per cell key means a transient fault (a VM hiccup) costs a new campaign for that cell. Accepted for simplicity; the manifest can list only the cells to redo.
- The cap tool is not available on the Dell (WSL) or the devbox (LXC). Small and Medium then run on GCP VMs of that shape (n2-standard-4, n2-standard-8), one at a time, in the S5 cost ping. Such a VM is checked as uncapped Linux against its own class's CPUs and nominal bytes (5.2).
- The pilot shows 100M on Small or Medium costs too much. The manifest leaves those cells out, they publish as "not run", and the headline rule still holds.

## 13. V2-LOG

- Deliberate-edit protection for published numbers (Codex R2-1): the Pages build verifies the exact published bytes against an independently pinned CLI evidence commit, by running the canonical publisher or verifying its signed output, and resolves every record path. Tests: a coordinated timing edit, a memory-only edit, an unresolved record, and a placeholder relabelled `published`.
- Variance reruns with identified attempt slots (Codex R2-2): rerun a high-variance cell in a recorded slot, require all slots, and define which times enter the statistic.
- cgroup memory accounting and out-of-memory evidence (Codex R2-10): a fresh delegated leaf whose lifetime the supervisor controls through the final reads of `memory.peak` and `memory.events`, to report a cgroup peak and to classify OOM kills.
- Retry within a campaign for a cell lost to a transient host fault, with the earlier attempt kept and shown.
