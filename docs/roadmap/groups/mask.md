# Masking, policy, vault and secrets

Status: current

Part of the roadmap: [ROADMAP.md](../../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

Rows keep their number from the pre-split track. A row number or section number that is not in a group file is a closed row or old section in the [snapshot](../../archive/2026-11-18-roadmap-before-split.md).

## 1.0

Blocks the 1.0 release.

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| 24z | FAKER-POOL-DISTINCT (engine QA checklist fact-check 2026-11-11 (Codex, engine branch `claude/sharp-cori-um7k6i`)): deterministic `faker` picks a pool slot by reducing a 64-bit derived value modulo `pool_size` (`E:src/decoy_engine/determinism/_derive.py:319`), so two distinct source values can get the same output, while the docs promise distinct in, distinct out. A masked key column can merge two people. The plan either makes the mapping collision-free or corrects the promise and reports a collision count per column. V1 | engine, CLI | PARTLY MERGED. Plan `E:plan/factcheck-pins-guards`. Z-E1 MERGED (engine #620, `9df5582b2`, 2026-11-17): the faker collision rule: `--post-validate` reports `cardinality_collisions` for each deterministic `faker` column that is not `unique` (names and counts only), and the docs now say distinct sources can map to one output. Left: Z-C1 (CLI collision line in the post-validation text), which waits on the next engine release and a CLI repin | none | none |
| 24zb | DATE-SHIFT-UNKEYED (automated QA scan 2026-11-11, finding F2; owner 2026-11-11 option (a)): unkeyed `date_shift` is refused in V1 in the engine and the CLI. A proof on the Mac (2026-11-11, engine 0.22.0) showed the legacy `MD5(value)` shift in `E:src/decoy_engine/transforms/date_shift.py` is reversible by search (one to four candidate dates for each row over a 365-day window, the source date always among them), and that `decoy run`, `decoy run --chunked`, `decoy.mask()` and engine `run_pipeline` already refuse an unkeyed `date_shift` with `keyed_strategy_requires_secret` before reading a source. The legacy class has no live caller. Plan: pin the refusal on every surface, hard-delete the MD5 path, add a sentry that no unkeyed shift exists. Plan on engine branch `plan/date-shift-unkeyed`. Feature group: date and number strategies (engine QA checklist section 07); build at that group's QA pass (owner rule 2026-11-11: QA and its fixes run only on a V1-complete group). V1, blocks V1 | engine, CLI | NOT STARTED | none | none |
| 79 | F09: domain-version object, rotation and remap (engine); authenticated, versioned CLI token vault header (G9, 11.8) | engine, CLI | NOT STARTED. Its dependency is met: the B-6 core merged (engine #559, `c86ca58d`, 2026-11-13) and ships in engine 0.24.0. Plan gated 2026-11-15 (`E:plan/f09-domain-version`, `b5d59d96`; Dennis r1-r2, Codex GREEN); owner questions Q1-Q7 open | none | none (B-6 core merged) |

Row 79 is split. 1.0 holds only the authenticated, versioned CLI token vault header, because the vault format freezes at 1.0. The domain-version object, rotation and remap are Later, in row 79-later.

## Later (1.x)

Additive. Not scheduled until a 1.x release picks it up. The release each row is planned for is in [releases-1x.md](../releases-1x.md).

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| 24zt | F16-PROHIBIT-DOC (found in engine #631 review): policy prohibitions see only the mask columns a table declares, not every column of the source. The behavior stays; document it in the CLI explain text and guide (slice C2 of row 81). V1 doc item | CLI | NOT STARTED | engine #631 | row 81 E3 |
| 81 | F16: selector grammar, prohibition predicates, 5-level precedence; disguises applied in the engine | engine, CLI | PARTLY MERGED. Plan `E:plan/f16-selectors` (revision 2). E2a MERGED (engine #631, `50cc74827`, 2026-11-17): the `policy` block models, selector grammar, 5-level precedence and `expand_policy`; nothing calls it until E3. E2b is open (engine #642, prohibitions and explanation). Left: E2b, E1, E3, the release, C1, C2 | `E:plan/f16-selectors` | Phase 1 rows |
| 83 | F13 external adapters (HashiCorp Vault, AWS and GCP Secret Manager, Azure Key Vault) | engine, CLI | NOT STARTED | none | F13 preflight (merged) |
| 79-later | F09 Later part: domain-version object, rotation and remap. The 1.0 part (the vault header) stays in row 79 | engine, CLI | NOT STARTED. 1.x minor. Plan gated 2026-11-15 | `E:plan/f09-domain-version` | row 79 |
| F17 | Portable disguise bundles: export and import of the existing bundle model. Owner question 3: the companion scope says V1 | engine, CLI | NOT STARTED. 1.x minor | [post-1.0-plan](../post-1.0-plan.md) (Council scope) | owner question 3 |
| F47 | Healthcare packs and presets; existing presets keep their output | engine | NOT STARTED. 1.x minor | [post-1.0-plan](../post-1.0-plan.md) (Council scope) | none |
| F08 | Coherent free-text identity binding | engine | NOT STARTED. 1.x if it is an opt-in option on the text strategy, else 2.0 | [post-1.0-plan](../post-1.0-plan.md) (Council scope) | none |
| F40 | Plugin SDK, also the home for heavy extras (X-25 is the same item). It creates a new frozen surface; review its first release as one | engine | NOT STARTED. 1.x minor | [post-1.0-plan](../post-1.0-plan.md); [expansion page](../v2-v3-expansion-candidates.md) | none |
| X-08 | International identifiers, generators and region disguises, as new dated disguise versions | engine | NOT STARTED. 1.x minor | [expansion page](../v2-v3-expansion-candidates.md) | F47; DETECT-PROFILES |
| X-10 | Meaning-preserving masks | engine | NOT STARTED. 1.x minor | [expansion page](../v2-v3-expansion-candidates.md) | none |
| X-13 | Time-series and event masking | engine | NOT STARTED. 1.x minor | [expansion page](../v2-v3-expansion-candidates.md) | none |
| X-20 | Document redaction (PDF, DOCX, email) | engine | NOT STARTED. 1.x minor | [expansion page](../v2-v3-expansion-candidates.md) | X-11 |
| X-21 | DICOM medical imaging de-identification | engine | NOT STARTED. 1.x minor | [expansion page](../v2-v3-expansion-candidates.md) | F47 |
| MEDIA | X-22 text in images and scans (OCR), X-23 faces and licence plates, X-24 audio redaction. Model based, so each states its own weaker guarantee | engine | NOT STARTED. 1.x minor | [expansion page](../v2-v3-expansion-candidates.md) | X-20, X-21 |
| VAULT-STREAM | Reversible-masking vault on runs that write output before they finish (`--chunked`, out-of-core FK runs, sink runs); a staged two-step publish. Turns `runtime/vault_requires_resident_output` into a success | engine, CLI | NOT STARTED. 1.x minor | [post-1.0-plan](../post-1.0-plan.md) (owner) | row 59 |
| TOKENIZE-CHUNKED | `decoy tokenize` on the chunked and auto-chunk routes, with per-chunk token reuse | engine, CLI | NOT STARTED. 1.x minor | [post-1.0-plan](../post-1.0-plan.md) (owner 2026-11-13) | VAULT-STREAM |
| JOIN-GROUP | Cross-job joinable masking: an explicit `fpe_join_group` option. Opt-in only; see the contract's `fpe_join_group` note | engine | NOT STARTED. 1.x minor | [post-1.0-plan](../post-1.0-plan.md) (platform V2 plan 3) | none |
| WHEN-HASH-NUM | Conditional (`when:`) hashing of number columns | engine | NOT STARTED. 1.x minor | [post-1.0-plan](../post-1.0-plan.md) (platform V2 plan 11) | none |
| MASK-SOURCES | Temporal and decimal Faker sources; NDC therapeutic-chapter derivation through ATC | engine | NOT STARTED. 1.x minor | [post-1.0-plan](../post-1.0-plan.md) (platform V2 plan, secondary) | none |
| WINDOWED-DATE-RANGE | Widen the accepted `windowed_date` range; today's range stays valid | engine | NOT STARTED. 1.x minor | [post-1.0-plan](../post-1.0-plan.md) (Phase F deferral) | none |
| HC1-CORPORA | Full public code-set corpora (ICD-10-CM, HCPCS, NDC, MCC) with a release-dated update path, and per-value selection that does not scan the corpus | engine | NOT STARTED. 1.x if full corpora ship as new corpus versions a config chooses and the seed corpora stay the default, else 2.0 | `E:docs/backlog/hc-1-codeset-slice2-and-hardening-tail.md` | owner: corpus sourcing |
| FK-WHEN-SIBLING | A sibling column that reads the FK key through `when:` on the mixed route | engine | NOT STARTED. 1.x if the sibling keeps seeing the source key, as today, else 2.0 | [post-1.0-plan](../post-1.0-plan.md) (F2 follow-up) | none |

## Maintenance

No user-visible change. Merges at any time and never gates a release.

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| MASK-PATCH | FPE checksum-mode native acceleration (KAT-locked, same output); `text_redact` full-Unicode Rust path; the joinable-CDR telco demo config; HC-1 out-of-core all-null `code_set` evidence parity | engine | NOT STARTED. 1.x patch | [post-1.0-plan](../post-1.0-plan.md); `E:docs/backlog/hc-1-codeset-slice2-and-hardening-tail.md` section 2 | none |
