Status: plan

# After 1.0: what ships in 1.x and what waits for 2.0

Part of the roadmap: [ROADMAP.md](../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.
This page replaces `out-of-scope.md`. Owner direction, 2026-11-16.

Since 2026-11-18 the items below are rows in the Later and Maintenance tables of the [group files](groups/), and
the order they ship in is in [releases-1x.md](releases-1x.md). The tables here stay as the record of each item's bucket
and the reason for it.

## The rule

After the CLI ships 1.0.0, any change that keeps the contract the same is a 1.x release, whatever the
roadmap called it before. "V2" now means 2.0.0 only, and 2.0.0 means a change that breaks the contract.

The contract is the REL-GATE versioning freeze (roadmap row 93 and [release-gates.md](release-gates.md)):
CLI commands and flags, exit codes (including 6), the result schema, the YAML config schema, the reason
registry, versioned report tags (`name/vN`, for example `post-scan-integrity/v3`), install and signature
verification, and the engine compatibility contract (engine `docs/compatibility-contract.md`: artifact
formats, the vault, determinism, the public API, disguises).

Every item has one bucket:

| Bucket | Meaning |
|---|---|
| Before 1.0 freeze | Would be 2.0 if it shipped after 1.0, but can be done now. Flagged here, not built. |
| 1.x minor | Adds a command, flag, option, format or feature, or turns a refusal into a success. Every existing valid config and run still gives the same result. |
| 1.x patch | A fix or an internal cleanup with no user-visible change. |
| 2.0 | Removes or renames a public name, changes a default output or the determinism of an existing config, changes the meaning of an exit code or reason, or drops an old config key or report tag. |

Four tests decide, in this order. (1) Does a name, default, output byte, exit code, reason string, schema
field or report tag change for a config or run that is valid today? Then it is 2.0, or before 1.0 freeze if
it can be done now. (2) Can it be done by adding something next to the old behavior? Then 1.x minor.
(3) Does nothing user-visible change? Then 1.x patch. (4) Could the design go either way? Then write
"1.x if <design>, else 2.0" and name the design that keeps it 1.x. A new refusal of something that works
today is a contract change. A new warning on stderr is not.

Where the source says "V2", "V2-LOG", "post-V1" or "V1+", read the bucket on this page instead.

## Before 1.0 freeze

These are public names, defaults or readers that cost a 2.0 to remove once 1.0 ships. They are flagged here and not
built by this page. Each needs an owner or orchestrator decision on whether to cut it before the freeze (row 93).

| Item | Source | Why it is before the freeze | Contract surface |
|---|---|---|---|
| B1 `_F9_KEPT_BINDINGS`: 17 engine names "kept for backward-compatible attribute access" | proportionality audit B1 | Nothing in the engine or CLI uses them. After 1.0 each one is a promise. Check the platform first. | public API |
| B2 `deterministic_hash`, deprecated and warning, no caller | audit B2 | Same. | public API |
| B3 `ExecutionContext.resolve_connector`, `captured_outputs`, `pool_resolver`, `column_relationships`, `export()` | audit B3 | Left from the deleted V1 graph runner. | public API |
| B4 `TelemetryClient` ("published for forward compatibility; unused today") | audit B4 | Same. | public API |
| B5 `emit_fidelity`, `emit_quarantine`, and the `node_id` keyword of `emit_step` | audit B5 | Exported and test-only, or never passed. | public API |
| B6 `ExecutionEvent`, exported and never built | audit B6 | Same. | public API |
| B7 `run_pipeline` keywords `progress_interval_s`, `secret_registry`, `secret_cache_policy` and five kill switches only tests pass | audit B7 | Keyword names are part of the API. | public API |
| B8 `FK_SELF_REFERENCE` "legacy" alias, `event_to_legacy_dict` | audit B8 | An alias with no reader. | reason registry, public API |
| B9 68 of 69 platform reason codes, 12 of 28 verification codes and 9 runtime codes unreferenced in the engine and CLI | audit B9 | The reason registry is frozen. Likely the platform wire contract, so the choice is to record the consumer or remove the code. Owner question. | reason registry |
| C9 `DateShiftStrategy`, a V1 class never built (two helpers are used) | audit C9 | Check whether it is exported. If it is, remove it before the freeze. | public API |
| C10 two-level strategy base classes with one live subclass | audit C10 | Check whether custom providers subclass them. If so, decide the base class now. | public API |
| C16 hidden `--ref` and `--rows` flags of `decoy demo` that only print "deferred" | audit C16 | A hidden flag is still a flag name. | CLI flags |
| D6 readers for pre-`scan-set/v1` saved scans and pre-CLI-FMT manifests | audit D6 | Dropping a reader for an old report tag after 1.0 is 2.0. No 1.0 user holds such files today. | report tags |
| D9 `dp_budget` module `__getattr__` re-export that keeps an old import path | audit D9 | An old import path of a public module. | public API |
| J2 `api.scan` points at `scan_sources` where the CLI uses a different profile call | audit J2 | The scan result of the public `api.scan` may change. 1.x patch only if results stay identical. | public API, result schema |
| STORM taxonomy split: pending public renames | owner direction 2026-11-16 | Renames after 1.0 are 2.0. The names are not listed in this repo's docs; the orchestrator lists them. | CLI flags, YAML config schema |
| F22 publication names | owner direction 2026-11-16 | Same. Roadmap rows 59 and 61 own the work. | public API, report tags |
| A1, A3, A4, A8 quiet fallbacks that hide a wrong result: a Faker failure replaced by `fake.name()` (A1), a swallowed provider check (A3), a bad expression becoming an empty reference set (A4), a result with no outputs reported as success (A8) | audit package A | Fixing each turns a run that "works" today into an error, and A8 changes an exit code. That is a contract change after 1.0. Owner question 2. | exit codes, reason registry |
| Partition-stable `when:` on number-with-blanks columns (platform plan 12) | platform V2 plan | Fixing the precision loss changes the output of existing configs on integers of 2**53 or more. | determinism |
| Atomic output: the `.gz` header can store the staging basename | ROADMAP row 21b, `docs/records/2026-11-07-atomic-output-build.md` | Fixing it changes the bytes of compressed outputs from existing configs. | determinism |
| `run_mask_chunked` writes a pass-through `large_string` column as `large_string` where the other routes write `string` | corrective backlog, DUP E3 #565 review (2026-11-13) | Same values, different output Arrow type. Unify now; after 1.0 it is 2.0. | artifact format |
| CLI reason registry: move `layout.report_source_ambiguous` out of the `layout.` namespace | corrective backlog | A reason code rename. | reason registry |

## 1.x minor

Each of these adds something next to the old behavior. A valid config or run today gives the same result after it ships.
Items that only stay 1.x with a particular design are in "2.0 only if built the other way" below, not here.

### Council features

The Council scope called these "V2, built when a customer pulls". Detail:
`P:docs/backlog/v2-candidate-plan.md` covers the platform's own V2 list; the Council text is in the vault under
`Market Expansion Specs/` (`COMPANION - Decoy V1 and V2 Feature Scope.md`). The old list said 21 features and named 22
(F03, F05, F08, F11, F12, F17, F18, F19, F20, F27, F28, F37, F38, F39, F40, F41, F42, F46, F47, F48, F49, F50). The
companion scope marks F17 and F27 as V1, so check them against roadmap rows before treating them as post-1.0.

| Item | Why 1.x minor | Contract surface |
|---|---|---|
| F03 file unions (several files as one logical table) | New optional source key; single-file configs unchanged. | YAML config schema (additive) |
| F05 fixed-width streaming | Turns a refusal on large fixed-width files into a success. | none |
| F12 customer regression suites | New command and artifact. | CLI commands (additive) |
| F17 portable disguise bundles | New export and import of the existing bundle model. Companion scope says V1: check. | disguises (additive) |
| F18 config composition (includes, inheritance) | New optional keys; complete inline configs unchanged. | YAML config schema (additive) |
| F19 semantic diff and repair | New command; no change to how a reviewed pipeline runs. | CLI commands (additive) |
| F27 governed schedules | Platform trigger path for a pinned pipeline. Companion scope says V1: check. | none for the CLI |
| F28 local execution node | New daemon beside the CLI and platform workers. | none |
| F37 post-mask privacy risk | New report under a new tag; k-anonymity and QI in `decoy scan` stay as they are. | report tags (additive) |
| F39 OpenLineage export | New export. | none |
| F40 plugin SDK | New public extension contract. It creates a new frozen surface of its own, so the first release of it must be reviewed as one. | public API (additive) |
| F41 expression evaluator preview | New command. | CLI commands (additive) |
| F42 Unix streams | New input and output form. | CLI flags (additive) |
| F46 reusable QA scenarios | New scenario compiler and case library. | YAML config schema (additive) |
| F47 healthcare packs | New packs and presets; existing presets keep their output. | disguises (additive) |
| F48 statistical synthesis | New opt-in backend and evaluation; existing generation unchanged. | determinism (opt-in only) |
| F49 clone-system handoff | New handoff after a valid published output. | none |
| F50 native masking-policy export | New export. | none |

### V2 rows carried from the old out-of-scope list

| Item | Source | What | Why 1.x minor | Contract surface |
|---|---|---|---|---|
| DETECT-PROFILES | owner, 2026-11-05 | Detection settings profiles: named sets of detection settings (detectors, overrides, thresholds, ML on or off) that a pipeline picks by name. | New optional config key; pipelines without it are unchanged. | YAML config schema (additive) |
| EXPAND | owner, 2026-11-06 | Core expansion candidates: see [v2-v3-expansion-candidates.md](v2-v3-expansion-candidates.md) and the X-items below. | Per item. | per item |
| VAULT-STREAM | owner | A reversible-masking vault (`decoy run --vault`) on runs that write output before they finish: `--chunked`, out-of-core FK runs and sink runs. Today the engine refuses these with `runtime/vault_requires_resident_output` and the CLI refuses `--chunked --vault` first, so a vault run must fit in memory. Needs a staged two-step publish: hold the output where no one can read it, save the vault durably, then release the output, with cleanup on every failure path. | Turns a refusal into a success. The vault format does not change. | reason registry (a reason stops firing), vault (no format change) |
| TOKENIZE-CHUNKED | owner, 2026-11-13 | `decoy tokenize` on the chunked and auto-chunk routes. Today a tokenize job is forced to the full-frame route and the bounded routes fail closed with `tokenize_requires_vault`, so a tokenize job must fit in memory. Needs the token vault wired through the chunked and auto-chunk lanes with per-chunk token reuse. | Turns a refusal into a success. | reason registry (a reason stops firing) |

A reason that stops firing is allowed: the registry keeps the entry for old results.

### Post-V1 on demand (old list)

| Item | Why 1.x minor | Contract surface |
|---|---|---|
| Route-coverage phase 2: out-of-core address faker | Turns a refusal into a success. | none |
| Route-coverage phase 2: FPE foreign-key key on the out-of-core route | Same. | none |
| Route-coverage phase 2: resident escape hatch | New option. | CLI flags (additive) |
| Route-coverage phase 2: out-of-core quarantine | Same refusal-to-success shape. | none |
| Value-based FK discovery (SCAN-MULTI plan section 7; DuckDB #14 is the same idea) | New scan option; declared relationships keep priority. | CLI flags (additive) |
| Chunk-level resume (the table-level `--resume` is row 85, V1) | New option. | CLI flags (additive) |
| User-level library store (LIB Q7) | New location for the library; the project library is unchanged. | none |

The CLI init wizard (spec CLI #73) was on this list. It is V1 now (roadmap row 32b, owner 2026-11-06), so it is not here.

### Expansion candidates X-01 to X-25

All X-items add input or output formats, detectors, masks, generators or extras. The expansion page's own tags
(V1+, V2, V3) are placement and size, not release buckets; read this table for the bucket. X-11 is in the
"other way" table below.

| Item | Why 1.x minor | Contract surface |
|---|---|---|
| X-01 Avro and ORC files | New formats. | none |
| X-02 JSON and JSONL with nested path masking | New format and path syntax. | YAML config schema (additive) |
| X-03 Excel workbooks | New format. | none |
| X-04 XML with path masking | New format. | YAML config schema (additive) |
| X-05 Delta Lake and Apache Iceberg tables | New formats. | none |
| X-06 More databases (MySQL, SQL Server, Snowflake, BigQuery; MongoDB later) | New connectors. | none |
| X-07 Streaming and change-data-capture masking | New run mode. Model-free; keeps the current determinism claim. | CLI commands (additive) |
| X-08 International identifiers, generators and region disguises | New detectors and new dated disguise versions. A released disguise version is never edited. | disguises (additive) |
| X-09 Secrets detection | New detector. | none |
| X-10 Meaning-preserving masks | New strategies. | none |
| X-12 Formal anonymity enforcement | New opt-in gate. | YAML config schema (additive) |
| X-13 Time-series and event masking | New strategies. | none |
| X-14 Joint-distribution synthesis (Gaussian copula) | New generation method; existing configs unchanged. | none |
| X-15 Multi-table synthesis | New generation method. | none |
| X-16 Generate from a schema | New source of generation specs. | none |
| X-17 Edge-case test data | New generators. | none |
| X-18 Sequential and event data synthesis | New generation method. | none |
| X-19 File metadata scrubbing | New option; the default stays as it is. | none |
| X-20 Document redaction (PDF, DOCX, email) | New formats and extras. | none |
| X-21 DICOM medical imaging de-identification | New format and extra. | none |
| X-22 Text in images and scans (OCR redaction) | New extra. Model based, so it states a weaker guarantee of its own. | none |
| X-23 Faces and licence plates in images and video | Same. | none |
| X-24 Audio redaction | Same. | none |
| X-25 Plugin SDK as the home for heavy extras (same item as F40) | See F40. | public API (additive) |

### DuckDB opportunities (vault `v2/duckdb/`, platform `plan/v2-duckdb-plans`)

The master note has 22 rows. Rows 1 to 4 and 22 say "keep" or "do not use DuckDB" and are not future work. Rows 5 to 7 are
cleanups (see 1.x patch). Row 9 is in the "other way" table.

| Item | Why 1.x minor | Contract surface |
|---|---|---|
| 8 Source-versus-output compare and leak check | New command or report. | CLI commands (additive) |
| 10 Deterministic sample preview and dry run | New option. | CLI flags (additive) |
| 11 New input formats and databases (same as X-01, X-06) | See those. | none |
| 12 Writing masked output back into a database | New write target. | none |
| 13 SQL filters on sources | New optional source key. | YAML config schema (additive) |
| 14 Relationship (PK and FK) discovery (same idea as value-based FK discovery) | See above. | CLI flags (additive) |
| 15 Local catalog of scans, runs and evidence | New local store. | none |
| 16 `decoy-admin` log query | New admin command. | none for the CLI |
| 17 Archive old logs and audit rows to Parquet | New admin feature. | none for the CLI |
| 18 Trend and drift analytics across scans and reports | New report. | report tags (additive) |
| 19 Subset from non-Parquet sources | Turns a refusal into a success. | none |
| 20 Support bundle as Parquet | New format. Stays 1.x only while the old bundle format stays readable and the default. | none |
| 21 DuckDB-Wasm in-browser preview | New web feature. | none |

### Items named in ROADMAP rows and plans

| Item | Source | Why 1.x minor | Contract surface |
|---|---|---|---|
| A certified DP stack for normal users (a DP fit on a default install works) | ROADMAP row 24g | Turns the `dp_stack_uncertified` message into a success. Exit code 3 stays for the cases still refused. | none |
| GEN-PROVIDERS per-provider options and `unique` | ROADMAP row 24p | New optional keys on `type: provider`. | YAML config schema (additive) |
| DUP-DEFECTS A6: `fromisoformat` with `Z` on Python 3.10 | ROADMAP row 24zd, `E:plan/dup-defects` section 13 | A hand-made profile that is refused with exit 1 today is accepted. | none |

### After-V1 items from the findings register and decisions

| Item | Source | Why 1.x minor | Contract surface |
|---|---|---|---|
| Login rate limit, lockout and password policy (F45) | findings-register, after V1 | New platform feature. | none for the CLI |
| SFTP host-key fingerprint pinning | findings-register, after V1 | New option. Pinning by default would refuse connections that work today. | YAML config schema (additive) |
| Multi-process API support | findings-register, after V1 | New platform capability. | none for the CLI |

### Platform V2 candidate plan (`P:docs/backlog/v2-candidate-plan.md`)

Its ranked features 2 (distribution-integrity) and the "reassigned to V1" items (ML advisory classification, native
generation throughput, job-time estimator) are V1 now and are not classified here. Feature 12 is in the "other way" table.

| Item | Why 1.x minor | Contract surface |
|---|---|---|
| 1 Reversible tokenization vault, de-tokenize half (MG-5) | New feature on the existing vault; the vault format keeps its permanent readers. Blocked on an auth-model decision (who may de-tokenize); owner question. | vault (additive) |
| 3 Cross-job joinable masking (`fpe_join_group` expansion) | New explicit join-group option. Changing how an existing config derives tokens would be 2.0 (see the contract's `fpe_join_group` note). | determinism (opt-in only) |
| 4 MCP server in the platform (`/mcp`) | New endpoint. | none for the CLI |
| 6 Composite multi-hop FK chains | Turns a coded decline into a success. | none |
| 7 Job-outcome notifications (success and both) and CLI `--notify` | New condition and new flag. | CLI flags (additive) |
| 8 Cross-table FK cycles on the bounded sequential route | Turns a decline into a success; needs one job-wide memory-eligibility rule first. | none |
| 9 Bounded reorder for large parents (partitioned or blocked join) | Turns a demotion past the parent-size ceiling into a bounded run. | none |
| 11 Conditional (`when:`) hashing of number columns | Turns a deferred decline into a success. | YAML config schema (no change) |
| Secondary: temporal and decimal Faker sources | New sources; today "not planned". | none |
| Secondary: NDC therapeutic-chapter derivation via ATC mapping | New derivation. | none |
| Secondary: nested and arbitrary-N relationships on the out-of-core route (deferred at OOC-B) | Turns a decline into a success. | none |
| Phase F deferral: mixed-job composite FK keys | Turns a typed decline into a success. | none |
| Phase F deferral: mixed-job out-of-core mask driver | Same. | none |
| Phase F deferral: `windowed_date` supported-range widening | Widens an accepted range; today's range stays valid. | none |
| F2 follow-up: dirty generated output (nullable, NaN, nested) on the mixed route | Lifts a decline. | none |

## 1.x patch

A fix or an internal cleanup with no user-visible change. This covers most V2-LOG and corrective-backlog items. The
audit rows below are from `docs/records/2026-11-15-proportionality-audit/REMEDIATION.md` (CLI roadmap rows 24zi to 24zl
carry the V1 part). Each cut shows the unit's coverage and mutation score unchanged.

### Proportionality audit (2026-11-15)

| Items | What | Why 1.x patch |
|---|---|---|
| A2, A5, A6, A7, A9 (package A) | Quiet fallbacks: a reference table that fails to load becoming `{}` (A2), a native-lane exception rerun on pandas (A5), `except Exception: return None` (A6, A7), a hint that always returns None (A9) | Each is a defect on a broken install or an internal bug; a working config sees no change. (A1, A3, A4 and A8 are in "Before 1.0 freeze".) |
| C1 to C8 | Internal modules with no production caller: `MemoryMonitor`, `ProgressLogger`, `ConfigValidator`, five operator Protocols, pass-through adapters, `_route_diagnostics.py`, `_ner_rate.py` (check against row 32c), `_pool_quality.py` (check the platform caller) | Private paths, no public name. |
| C11, C12, C14, C15, C17 | `mimesis/_parity.py` moves to tests; `reject_unsafe_text_mask_source_dtype`; `progress_bar`; `env_int` and `prune_old_versions`; pandas loaders used only by `api.scan` | Private or test-only. |
| C13 | `cli/library/`, nine files with no importer outside the package | Not a cleanup: planned work for row LIB. Stays. |
| D1 to D5 | Old-engine capability probes and `hasattr` checks for names that exist in the pinned engine; the `pandas` import guard; report keywords omitted for an older engine | Dead branches under the exact engine pin. |
| D7, D8, D10, D11, D12, D13 | Re-export shims, a 23-line delegate module, an always-true predicate, a `TypeError` fallback for old loggers, a V2 custom-provider table kept until the V1 stack goes | Private paths. |
| E1 to E8 (package E) | Guard-test bookkeeping: hand lists of guard paths, allowlists kept four times, a 720-line permitted-diff allowlist, exact line counts instead of ceilings, bespoke CI shell parser | Test and process machinery. |
| Package F | Comment and docstring history sweeps | Comments only. |
| G1 to G9 (package G) | Defensive code for states that cannot occur | No reachable behavior. |
| Package H | Mechanical size-cap splits | Same code, new files. |
| I1 to I12 (package I) | Test reductions | Tests only. |
| J1, J3 to J6 | CLI thin-wrapper violations: `demo` composing its own run, a 90-line mirror of the engine's admission rules, diff statistics in the CLI, a private-global reset, chunked refusals split across modules | Same results from fewer copies. (J2 is in "Before 1.0 freeze".) |
| K1 to K4 (package K) | Docs and process: committed diagrams, archive shipped plans, one place for shipped state (K4, owner 2026-11-15) | Docs. |
| Section 15 guards | Re-export and no-production-caller guards | Test machinery. |

### Findings register, decisions and DuckDB cleanups

| Item | Source | Why 1.x patch |
|---|---|---|
| CLI `scan` parses fixed width with `pd.read_fwf`; divergence from the engine reader is untested (G5) | findings-register | A test. |
| Native-kernel fallback telemetry beyond a warning | findings-register | Telemetry only. |
| GCS and S3 conditional writes | findings-register | Safer writes; the output is the same. |
| The `data_discovery` keyword denylist | findings-register | Internal. |
| Secret retention in `KeyboardInterrupt(secret)` args | decisions 2026-10-30 | Hardening, no output change. |
| "V2 audit after V1 from the V2 log; phases 1 to 3 are hardening" | decisions 2026-11-03 | This page and the vault backlog are that audit. |
| Flaky tests on platform main | ROADMAP, V2 backlog | Tests. |
| DuckDB 5 Data viewer SQL tab; 6 memory-fraction constant duplicated across repos; 7 `--duckdb-source` audit | DuckDB master note | "Needs change" items that keep results and names the same. |

### Items named in ROADMAP rows and records

| Item | Source | Why 1.x patch |
|---|---|---|
| The CI lane sentry imports `_shell_tokens` by a private name; add a small public facade shared by both repos | ROADMAP row 5 (CI-L1) | Test machinery. |
| The `decoy run` error text cap of 500 characters | ROADMAP row 65 (F31) | Text length in an error message. |
| Atomic output: ACLs and xattrs of an old output are not copied; `_atomic.py` is over 400 lines; a second temp-create path; a `KeyboardInterrupt` during the temp chmod can leave an empty hidden temp; ENOSPC inside the writer block is not mapped to `atomic_write_failed` | ROADMAP row 21b, `docs/records/2026-11-07-atomic-output-build.md` | Defects and cleanup; the output for a working run is the same. (The `.gz` header item is in "Before 1.0 freeze".) |
| VALUE-FREE-ERRORS B3, FU-5 and FU-6 | ROADMAP row 24a | In the vault backlog, tagged there. |

### Platform V2 candidate plan: cleanups and validation

| Item | Source | Why 1.x patch |
|---|---|---|
| 5 FPE checksum-mode native acceleration (luhn, npi, iban, vin, isbn13, ean13, gtin) | platform V2 plan | Same output, KAT-locked to python-stdnum; removes a speed cliff. |
| 10 Width-aware reorder ceiling | platform V2 plan | Guard counts bytes, not keys; same results. |
| D5 certification coverage; flaky cgroup-launcher tests that hang | platform V2 plan | Tests. |
| Secondary: Joinable-CDR telco demo config; `text_redact` full-Unicode Rust path | platform V2 plan | Demo and speedup with the same output. |
| Phase F: 200M generation and masking scale proofs (one pre-release run); GAP9 thread-count-versus-memory policy | platform V2 plan | Validation and a speed policy. |
| F2 follow-up: cross-chunk warning aggregation; kernel-ABI backend-witness harness | platform V2 plan | Makes the chunked warning match the oracle's single warning; a test harness. |

## 2.0

No item on the old V2 lists is 2.0 as designed. Two things can make one 2.0:

- Leaving an item in "Before 1.0 freeze" until after 1.0.
- Building one of the items below the other way. Each of these can stay 1.x with the design named in the table.

### 2.0 only if built the other way

| Item | Source | 1.x if | Else |
|---|---|---|---|
| F08 coherent free-text identity binding | Council scope | it is an opt-in option on the text strategy | 2.0: changes the default output of existing text-mask configs |
| F11 output ordering and byte reproducibility | Council scope | it is an opt-in option | 2.0: it becomes the default and changes the bytes of existing outputs |
| F20 config migration | Council scope | it adds a new schema version, `migrate` writes it, and old configs still load | 2.0: old config keys stop loading |
| F38 dataset metadata preserve and redact | Council scope | preserving metadata is opt-in | 2.0: default metadata handling changes |
| X-11 better free-text detection | expansion page | it ships as a new opt-in detector or profile | 2.0: it changes the findings of the existing default detector |
| DuckDB 9 whole-file profiling aggregates | DuckDB master note | the aggregates are an option or new fields | 2.0: default profile numbers change for configs valid today |
| Hostile in-process hardening | decisions 2026-10-30 | it hardens internals and custom providers keep working | 2.0: it restricts what custom providers may do |
| Phase F: re-baselined generation oracle (accelerated or streamed generation, F1 and F3) | platform V2 plan | new routes match today's output byte for byte | 2.0: generation re-freezes to a new deterministic output |
| F2 follow-up: a sibling column that reads the FK key through `when:` | platform V2 plan | the sibling keeps seeing the source key, as today | 2.0: it would see the resolved key |
| DUP-DEFECTS B11: no scheme check on notify and `--url` | ROADMAP row 24zd, `E:plan/dup-defects` section 13 | the check only warns, or the allowed schemes keep every scheme that works today (the census says `file://` is accepted) | 2.0: a new refusal of a URL that works today |

The corrective backlog has 38 more entries of this kind. Most are a new refusal or a changed reason string that stays 1.x
if it only warns or adds a reason beside the old one. In the vault file they read `[either: 1.x if ..., else 2.0]`.

## Corrective backlog (vault)

The vault holds the corrective backlog in one file, `handoffs/V2-CORRECTIVE-BACKLOG.md`, merged on 2026-11-16 from two
overlapping copies (nothing was dropped: every line of both is in the merged file). Each of its 528 entries carries a
bucket tag. The tags are a first pass. These are the counts:

| Bucket | Entries |
|---|---|
| 1.x patch | 436 |
| 1.x minor | 17 |
| either (1.x if a named design, else 2.0) | 38 |
| before 1.0 freeze | 2 (in the table above) |
| 2.0 | 0 |
| V1 (entry says it stays V1 or was kept V1) | 16 |
| check (needs an owner answer or a fact) | 10 |
| n/a (index rows and notes) | 9 |

## Owner questions

1. Reason codes (audit B9): 68 of 69 platform codes and others are unreferenced in the engine and CLI. Record the platform
   consumer, or remove the code before the freeze?
2. Package A: A1, A3, A4 and A8 are listed under "Before 1.0 freeze" because each turns a run that works today into an
   error, and A8 changes the exit code of a run with no outputs from success to failure. A2, A5, A6 and A7 turn a
   fallback into an error only on a broken install or an internal bug and are kept as 1.x patch. Confirm the split.
3. F17 and F27: the companion scope marks them V1 and the old list kept them as V2. Which is right? This page treats them
   as 1.x minor.
4. Which public renames belong in "Before 1.0 freeze" for the STORM taxonomy split and the F22 names?
5. Does the platform API count as contract? The rule above lists the CLI and the engine. The backlog's platform entries are
   tagged for that reading (patch unless named otherwise).
6. The ten `check` entries in the vault file (`grep '\[check:'`) each name the owner question or the missing fact.
7. Platform V2 plan feature 1 (reversible tokenization vault, de-tokenize half) waits on an auth-model decision: who may
   de-tokenize, under what policy, with what key custody.

## Where each source landed

| Source | Section |
|---|---|
| `out-of-scope.md` (replaced by this page): Council features, DETECT-PROFILES, EXPAND, VAULT-STREAM, TOKENIZE-CHUNKED, post-V1 on demand, proportionality work | 1.x minor, 1.x patch, Before 1.0 freeze |
| `v2-v3-expansion-candidates.md`, X-01 to X-25 | 1.x minor, 2.0 only if built the other way (X-11) |
| `findings-register.md` after-V1 items, `decisions.md` V2 notes, ROADMAP V2 mentions (rows 5, 12, 21b, 24a, 24g, 24p, 24zd, 65) and `docs/records/2026-11-07-atomic-output-build.md` | 1.x minor, 1.x patch, 2.0 only if built the other way |
| `REMEDIATION.md` (proportionality audit), packages A to K | Before 1.0 freeze (B, C9, C10, C16, D6, D9, J2), 1.x patch (the rest) |
| Vault `handoffs/V2-CORRECTIVE-BACKLOG.md` | Corrective backlog (vault) |
| Vault `v2/duckdb/` | 1.x minor, 1.x patch, 2.0 only if built the other way (9) |
| `P:docs/backlog/v2-candidate-plan.md` | 1.x minor, 1.x patch, 2.0 only if built the other way |
| Engine `docs/compatibility-contract.md` | The rule, sections 3 to 5 and 8 |
