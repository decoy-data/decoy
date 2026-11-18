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
| FAKER-MIGRATE | Move the launch engine from Faker 40.23.0 to 40.31 before the freeze (owner 2026-11-18). Faker's name and data pools are not semver-stable, so the Faker release that ships in 1.0 fixes deterministic `faker` output for the life of 1.x; the provider fixes in 40.31 cannot ship later without a 2.0. Re-pin, regenerate the determinism goldens as one reviewed act, and re-certify the DP stack row. Snapshotting the pools so Faker can be upgraded freely is non-breaking and is a Later candidate | engine, CLI | NOT STARTED | `E:fix/faker-40-31-migration` (was planned as a replay after R1; see release gate D-4) | none; merges before row 93 |

Row 79 is split. 1.0 holds only the authenticated, versioned CLI token vault header, because the vault format freezes at 1.0. The domain-version object, rotation and remap are Later.

## Later (1.x)

Additive. Not scheduled until a 1.x release picks it up. The proposed order of the 1.x releases is in
[releases-1x.md](../releases-1x.md).

| # | Item | Repo | State | Branch, plan or handoff | After |
|---|---|---|---|---|---|
| 24zt | F16-PROHIBIT-DOC (found in engine #631 review): policy prohibitions see only the mask columns a table declares, not every column of the source. The behavior stays; document it in the CLI explain text and guide (slice C2 of row 81). V1 doc item | CLI | NOT STARTED | engine #631 | row 81 E3 |
| 81 | F16: selector grammar, prohibition predicates, 5-level precedence; disguises applied in the engine | engine, CLI | PARTLY MERGED. Plan `E:plan/f16-selectors` (revision 2). E2a MERGED (engine #631, `50cc74827`, 2026-11-17): the `policy` block models, selector grammar, 5-level precedence and `expand_policy`; nothing calls it until E3. E2b is open (engine #642, prohibitions and explanation). Left: E2b, E1, E3, the release, C1, C2 | `E:plan/f16-selectors` | Phase 1 rows |
| 83 | F13 external adapters (HashiCorp Vault, AWS and GCP Secret Manager, Azure Key Vault) | engine, CLI | NOT STARTED | none | F13 preflight (merged) |

### Candidates with no plan yet

Non-breaking ideas, so v1+ by rule. A candidate becomes a row in the table above when a release picks it up.

| Item | Source | Why it does not break |
|---|---|---|
| F17 portable disguise bundles | Council features | New export and import of the existing bundle model. Companion scope says V1: check. |
| F40 plugin SDK | Council features | New public extension contract. It creates a new frozen surface of its own, so the first release of it must be reviewed as one. |
| F47 healthcare packs | Council features | New packs and presets; existing presets keep their output. |
| F50 native masking-policy export | Council features | New export. |
| VAULT-STREAM: A reversible-masking vault (`decoy run --vault`) on runs that write output before they finish: `--chunked`, out-of-core FK runs and sink runs. Today the engine refuses these with `runtime/vault_requires_resident_output` and the CLI refuses `--chunked --vault` first, so a vault run must fit in memory. Needs a staged two-step publish: hold the output where no one can read it, save the vault durably, then release the output, with cleanup on every failure path. | owner | Turns a refusal into a success. The vault format does not change. |
| TOKENIZE-CHUNKED: `decoy tokenize` on the chunked and auto-chunk routes. Today a tokenize job is forced to the full-frame route and the bounded routes fail closed with `tokenize_requires_vault`, so a tokenize job must fit in memory. Needs the token vault wired through the chunked and auto-chunk lanes with per-chunk token reuse. | owner, 2026-11-13 | Turns a refusal into a success. |
| X-08 International identifiers, generators and region disguises | Expansion candidates X-01 to X-25 | New detectors and new dated disguise versions. A released disguise version is never edited. |
| X-10 Meaning-preserving masks | Expansion candidates X-01 to X-25 | New strategies. |
| X-13 Time-series and event masking | Expansion candidates X-01 to X-25 | New strategies. |
| X-19 File metadata scrubbing | Expansion candidates X-01 to X-25 | New option; the default stays as it is. |
| X-25 Plugin SDK as the home for heavy extras (same item as F40) | Expansion candidates X-01 to X-25 | See F40. |
| 1 Reversible tokenization vault, de-tokenize half (MG-5) | Platform V2 candidate plan (`P:docs/backlog/v2-candidate-plan.md`) | New feature on the existing vault; the vault format keeps its permanent readers. Blocked on an auth-model decision (who may de-tokenize); owner question. |
| 3 Cross-job joinable masking (`fpe_join_group` expansion) | Platform V2 candidate plan (`P:docs/backlog/v2-candidate-plan.md`) | New explicit join-group option. Changing how an existing config derives tokens would be 2.0 (see the contract's `fpe_join_group` note). |
| Secondary: temporal and decimal Faker sources | Platform V2 candidate plan (`P:docs/backlog/v2-candidate-plan.md`) | New sources; today "not planned". |
| Secondary: NDC therapeutic-chapter derivation via ATC mapping | Platform V2 candidate plan (`P:docs/backlog/v2-candidate-plan.md`) | New derivation. |
| Phase F deferral: `windowed_date` supported-range widening | Platform V2 candidate plan (`P:docs/backlog/v2-candidate-plan.md`) | Widens an accepted range; today's range stays valid. |
| 11 Conditional (`when:`) hashing of number columns | Platform V2 candidate plan (`P:docs/backlog/v2-candidate-plan.md`) | Turns a deferred decline into a success. |
| Snapshot the Faker pools so the Faker dependency can be upgraded in 1.x | owner 2026-11-18 | Output stays byte-identical if the snapshot is taken from the pinned release. |

## Maintenance

No user-visible change. Merges at any time and never gates a release.

None.
