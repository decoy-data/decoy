# Scan and detection

Status: current

Part of the roadmap: [ROADMAP.md](../../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

Rows keep their number from the pre-split track. A row number or section number that is not in a group file is a closed row or old section in the [snapshot](../../archive/2026-11-18-roadmap-before-split.md).

## 1.0

Blocks the 1.0 release.

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| 16 | NAME-REMOVAL E1 (engine part of the NAME-REMOVAL), registry 1.7.0 | engine | NOT MERGED; no (an identifier kept in the pre-split snapshot) on origin | NAME-REMOVAL re-cut plan (an identifier kept in the pre-split snapshot) `dfe7cc6a` | SUB-STOP |
| 24zm | PROFILE-UNFLAGGED-VALUES (found 2026-11-16 while planning row 24f; owner 2026-11-16: V1, a fix to an existing feature): `profile_document`, the profile behind `decoy demo` and `decoy.scan()`, keeps real values for every column the profiler does not flag (exact numeric `min`/`max`, labels seen once, short free text), the same leak class as row 24f. Fix by applying row 24f's minimum-count rules to the profile document, then the CLI docs and tests. Leak class, blocks V1 | engine, CLI | NOT STARTED | none | row 24f E1 |
| PROFILE-SAMPLE-LABELS | Sample numbers shown as whole-file numbers (found 2026-11-18): the default scan profiles the first 10,000 rows but prints the sample null and distinct counts beside the exact whole-file row count, and `key_candidates` can call a column a key from the sample alone. The chunked mask run profiles only its first chunk yet marks columns `sampled=False`, so the plan's `profile_hash` depends on chunk size. Fix before the freeze, because each changes output: label every sampled field (`basis`, `scanned_rows`), claim a key only from exact counts, and make the first-chunk profile say it is a sample (or keep its distribution fields out of the plan hash). Exact whole-file numbers stay a 1.x opt-in. V1 fix | engine, CLI | NOT STARTED | none | none |
| 24zu | REPORT-INTEGRITY-DEMO (found in the report guide run, 2026-11-17): `decoy report integrity` fails the demo's own masked output. The redacted `customer_id` value matches the `mrn` detector and the command exits 4. The documented walk-through must end green. V1 fix | CLI, engine | NOT STARTED | report guide run 2026-11-17 | none |
| 27 | SCAN-MULTI S1c-cli: `decoy scan` over many tables (~690 lines) | CLI | IN PROGRESS. Plan passed 2026-11-06 (owner Q7-Q8 recommended). S1a and S1b are in engine 0.20.0, which the CLI pins since CLI #164. S1c.1 MERGED (CLI #166, `f32834bb`, 2026-11-10): `decoy scan` takes several files and writes one value-free scan-set core through the engine's `scan_sources`; saved scans load through one reader, `load_scan_set`; CSV scans need `--has-header` or `--no-header`. Next: S1c.2 (`--config`, `--table` on scan, `--column-names-file`, `--skip-integrity`, the integrity block), which waits on CONFIG-EXPLICIT E2 and C1 S1c.2 re-planned 2026-11-19 (`E:plan/scan-multi` rev 8.2, `714dc754f`; Dennis r1-r2, Codex fix GO): engine slice E-S1c (`DeclarationRequest.for_scan`, ~360 lines) first, then its release and repin, then S1c.2-cli (~720 lines). The legacy bare-file branch is dropped; main's refusal stays. | `plan/scan-multi` | E-S1c release and repin |
| 29 | SCAN-MULTI S3-cli: `--emit-config` and `--compare` (~720 lines including moved code) | CLI | Plan passed 2026-11-06 (owner Q7-Q8 recommended). Waits on LIB L2 and the S3-engine release and repin; SCAN-MULTI S1c.1 is in review as CLI PR #166 | `plan/scan-multi` | LIB L2 (in place of S1d); S3-engine release and repin; CLI-DIALECT |
| 32a | SCAN-ML: optional ML in scans, set per pipeline (owner 2026-11-06). Default is regex only. The lgbm column classifier ships in every install (off until enabled); spaCy and its NER model are opt-in, installed by the setup step or a model-install command that also takes a copied model file for offline hosts. Pipeline config picks the detectors for the pre-scan and the post-scan separately (regex, classifier, NER, or both models). The classifier only suggests a type per column; the user confirms. NER post-scan findings warn by default; fail is opt-in. Logs, the scan report and the run result always name what ran, what was scanned, and each model and version. Folds in NER-CLICK (the `ner` extra misses `click`, so spaCy cannot load; add it plus a CI leg that installs `ner` alone) | engine, CLI | PARTLY MERGED. M0 (NER-CLICK) MERGED (engine #396). M1 (config, model status, loading; NER on free-text columns only, `NER_MIN_RATE` 0.211, owner 2026-11-07) MERGED (engine #405, `38951412`, 2026-11-08). M5 (route guard on streaming routes) MERGED (engine #508, `0f505928`, 2026-11-12). M4 (model findings in the post-scan) MERGED (engine #512, `32ab8044`, 2026-11-16). The post-scan report is now `post-scan-integrity/v3` (owner ruling 2026-11-16); the verdict reader still accepts v2. M3a MERGED (engine #602, `2cce9c40`, 2026-11-16): the pre-scan model pass; classifier and NER hits go into the pre-scan record as value-free `ModelHit` entries (`scan_sources(pre_scan=...)`; default regex only). C1 MERGED (CLI #298, `d564f00f`, 2026-11-17): `decoy models list` and `decoy models install ner`, a `models` step in `decoy setup`, the model-availability preflight in the shared gate, three `decoy doctor` rows. C2a is open (CLI #301, the run post-scan report and the exit 4 block). Left: C2a, C2b, and M3b (`starter_config` and `ColumnSuggestion`), which waits on INIT-WIZARD E1. Plan: branch `plan/scan-ml` (Revision 6, Codex GO) | none | SCAN-MULTI S3; shares the setup step with RUN-STREAM (63a) |
| 32c | SCAN-ML-MD: make `en_core_web_md` the default NER model, with its own `NER_MIN_RATE` set by the owner's Q7 rule (measured 0.087 against the small model's 0.211; owner 2026-11-07). On the frozen corpus and the Synthea healthcare sample, md flags notes columns whose names appear in 1 cell in 4 or 1 in 5, which the small model misses, and drops the small model's 3 false flags on clinical description columns (drug and vaccine names, lab terms). Costs a larger pinned wheel (`NER_MODEL_WHEELS` hash) and more location hits on organization names. The slice re-measures on the frozen corpora plus a clinical-vocabulary negative set before setting the constant | engine | PARTLY MERGED. Plan `E:docs/plans/2026-11-17-scan-ml-md.md` on `plan/scan-ml-md`. M-1 MERGED (engine #616, `d57c41222`, 2026-11-17): a NER hit threshold per model (md 0.122, sm 0.211) and the md wheel pin. M-2a1 MERGED (engine #630, `612cdfd4b`, 2026-11-17): one model resolver for every NER surface. M-2a2 MERGED (engine #639, `e701c2826`, 2026-11-17): one not-installed message on every surface, and the resolved NER model in the resume fingerprint. Left: M-2a3, M-2b (md becomes the default) and M-3 (CLI install hints). Evidence in vault `handoffs/phase1/scanml-ner-model-comparison-2026-11-07.md` | none | SCAN-ML M1 merged |
| 56 | NAME-REMOVAL, CLI half: re-cut so CLI C0 vendors (an identifier kept in the pre-split snapshot), (an identifier kept in the pre-split snapshot), `slices-cli.json` and drops the platform S2c dependency; CLI V1 ships the new names | CLI | NOT STARTED; re-cut plan needed (owner OQ-2 = B1) | from (an identifier kept in the pre-split snapshot) `dfe7cc6a` | R-c repin |

## Later (1.x)

Additive. Not scheduled until a 1.x release picks it up.

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| 30 | SCAN-LIB: scan snapshot library (`scan-set/v1` under `.decoy/`); the YAML references a snapshot as its baseline and the run hashes it into evidence | engine, CLI | mostly delivered by S1a (`scan-set/v1`), LIB L2 (snapshots in the library) and S3 (`scan_baseline`); the run-evidence hash is the remainder; confirm at their plan GO | none | S1a, L2, S3-engine |
| 31 | DIST-INTEGRITY: opt-in pre-scan distribution capture plus a post-scan check within n%; a breach blocks in strict mode | engine, CLI | NOT STARTED | none | SCAN-LIB, POSTSCAN-STREAM |
| 32 | DRIFT: opt-in pre-scan drift check at run start against a SCAN-LIB baseline (`on_drift: warn` or `fail`) | engine, CLI | NOT STARTED | none | SCAN-LIB |
| 80 | F15: bound-baseline object, strict-drift publication block; scan-diff moves into an engine `scan-diff/v1` | engine, CLI | NOT STARTED | none | NAME-REMOVAL; SCAN-LIB |

### Candidates with no plan yet

Non-breaking ideas, so v1+ by rule. A candidate becomes a row in the table above when a release picks it up.

| Item | Source | Why it does not break |
|---|---|---|
| DETECT-PROFILES: Detection settings profiles: named sets of detection settings (detectors, overrides, thresholds, ML on or off) that a pipeline picks by name. | owner, 2026-11-05 | New optional config key; pipelines without it are unchanged. |
| Value-based FK discovery (SCAN-MULTI plan section 7; DuckDB #14 is the same idea) | Post-V1 on demand (old list) | New scan option; declared relationships keep priority. |
| X-09 Secrets detection | Expansion candidates X-01 to X-25 | New detector. |
| 14 Relationship (PK and FK) discovery (same idea as value-based FK discovery) | DuckDB opportunities (vault `v2/duckdb/`, platform `plan/v2-duckdb-plans`) | See above. |
| 18 Trend and drift analytics across scans and reports | DuckDB opportunities (vault `v2/duckdb/`, platform `plan/v2-duckdb-plans`) | New report. |
| DUP-DEFECTS A6: `fromisoformat` with `Z` on Python 3.10 | ROADMAP row 24zd, `E:plan/dup-defects` section 13 | A hand-made profile that is refused with exit 1 today is accepted. |
| Record the detector set version a scan ran with | compatibility contract read, 2026-11-18 | New field. It lets a better default detector arrive later as a named set a config selects. |

## Maintenance

No user-visible change. Merges at any time and never gates a release.

None.

## Notes carried from the track

SCAN-MULTI plan: `E:docs/plans/2026-11-05-scan-multi-fk-discovery.md` on engine branch
`plan/scan-multi` `9b7cd9ab`. Dennis GO-WITH-FIXES; in a fix round. No FK inference in V1 (users
declare relationships; value-based FK discovery is parked for 1.x, as a minor release; [post-1.0-plan.md](../post-1.0-plan.md)). Columns with no PII default to
`redact` in the starter YAML.
