# 1.x release schedule

Status: plan

Part of the roadmap: [ROADMAP.md](../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

This page proposes the order of the v1+ releases (1.1, 1.2 and so on) and says what every 1.x release
must keep so that `decoy upgrade` stays safe. Written 2026-11-18, after the scope split. The buckets
are the owner's: v1 blocks 1.0, v1+ is anything that does not break the contract, v2 is anything that
breaks it ([roadmap handoff](../handoffs/2026-11-18-roadmap-strategy.md), "The three buckets").

What this page does not hold:

- The rows and candidates. Each one is in the Later table, the "Candidates with no plan yet" table or
  the Maintenance table of its [group file](groups/). This page names them only.
- The bucket rule and the tests that decide it: [post-1.0-plan.md](post-1.0-plan.md).
- What waits for v2 and what is fixed for the life of 1.x: [2.0-holding.md](2.0-holding.md).
- Dates. The handoff plans a minor as two to three weeks of work. The schedule is an order, not a
  calendar.

## How to read the schedule

- The handoff's planning steps apply: a minor has one headline group from Later, a time budget, and
  fill from that group's candidates first, then small rows from other groups. Fill that does not fit
  stays in the pool. It never delays the release.
- Size is in slices. A slice is one reviewed pull request of about 800 hand-written lines or fewer
  ([working-rules.md](working-rules.md), 4.2). The numbers are rough and come from each row's plan
  where one exists.
- "Engine release" says whether the minor needs engine code that is not yet in a release. If it does,
  the CLI half waits for the engine release and the repin, as working rules 5.2 items 3 and 4 say.
- Before a minor is planned, check each item against [2.0-holding.md](2.0-holding.md). Some are v1+
  only if built a named way.
- The order is a recommendation by user value and dependency. Step 1 of the handoff says to pick each
  headline on evidence, so a user request can move a theme earlier. Moving one is an edit here plus a
  line in [decisions.md](decisions.md). The handoff's first open item, "choose the 1.1 theme", is an
  owner call; this page proposes one.

## Summary

| Release | Theme | Headline rows | Size (slices) | Engine release |
|---|---|---|---|---|
| 1.0.x | Fixes | Maintenance rows and candidates, patch entries of the corrective backlog | 1 to 4 each | only if a fix is in the engine |
| 1.1 | Run in production pipelines: cloud targets and resume | 64, 85, 84, 41 | about 18 | yes |
| 1.2 | Generate completeness | 24p, 24q, 24r, 24s, the Later part of 24n | about 14 | yes |
| 1.3 | More ways to install: the container image and PyPI | 90a, 38, 42; candidates PYPI, PY-VERSIONS | about 9 | no new engine code |
| 1.4 | More sources: PostgreSQL in, SFTP and cloud scan | 64b, 87 | about 15 | yes |
| 1.5 | Policy, secrets and key rotation | 81, 24zt, 83, the Later part of 79 | about 13 | yes |
| 1.6 | Scan baselines and drift | 30, 31, 32, 80 | about 12 | yes |
| 1.7 | Quality contracts | 69, 68 | about 9 | yes |
| 1.8 | Evidence you can hand to an auditor | 72, 78, 70 | about 11 | yes |
| 1.9 | Nested data and application-ready databases | 82, 86 | about 15 | yes |
| 1.10 onward | Chosen from the pool on evidence | see [The pool](#the-pool-after-19) | | |
| 2.0 | Only contract breaks | see [v2](#v2) | | |

1.1 to 1.9 carry all 27 planned v1+ rows and the Later parts of the two split rows (24n and 79).
Windows (rows 6 and 89) is v1, so it is not on this page.

## 1.0.x patch releases

A patch release carries fixes and internal cleanup. For a config or run that is valid today it never
changes a name, a default, an output byte, an exit code, a reason string, a schema field or a report
tag. Cut one when a fix is ready; there is no fixed cadence.

Candidates, in the order to take them:

1. A fix that a user reports and that breaks a function or loses data, in its own patch.
2. Broken-today items from the inbox that miss 1.0 (EXAMPLES-FIX, README-FIX), and row 24zr
   SETUP-NER-JSON ([release](groups/release.md)).
3. The Maintenance rows and the maintenance candidates in [health](groups/health.md). They merge to
   main whenever they are ready and ride the next release of either kind.
4. The patch entries of the corrective backlog (about 400), by theme, when a builder is free. See
   [Corrective backlog](#corrective-backlog-by-bucket-and-theme).

## 1.1: run in production pipelines

Theme: the owner's 1.0 goal is "use in production pipelines". Most pipelines read and write cloud
storage and need a failed run to restart without redoing finished tables. Three of these rows are
already partly built, and working rule 5.2 item 10 says to close partly merged rows first.

| Row | Group | What is left | Slices |
|---|---|---|---|
| 64 CLI-CLOUD | [connect](groups/connect.md) | EC2b to EC5, REL-C, CC1 to CC5 (12 in the plan, 3 merged) | about 9 |
| 85 F23 resume, CLI half | [run](groups/run.md) | engine release, then C0, C1, C2a, C2b, C3 | 5 |
| 84 F24 engine half | [run](groups/run.md) | merge 84-E1 (engine #635), then 84-E2 | 2 |
| 41 L5a-cli progress | [library](groups/library.md) | one slice, plan passed | 1 |

Fill: the run candidate for job-outcome notifications ([run](groups/run.md)); the corrective-backlog
minors on chunked progress events and the subset signal in `decoy.mask()` and `decoy tokenize`.

Depends on: 1.0 rows 61 (CLI delivery) and 59 (F22). Engine release: yes (CLI-CLOUD EC slices; F23 E1
and E2 are merged but not yet in a release the CLI pins).

## 1.2: generate completeness

Theme: synthetic data that looks like the business. All five items have a passed plan or merged
slices, so this is cheap next to work in flight. An earlier owner decision put 24p, 24q and 24r in V1;
the split moved them to v1+ and the owner has not objected.

| Row | Group | What is left | Slices |
|---|---|---|---|
| 24p GEN-PROVIDERS | [generate](groups/generate.md) | plan in a final fix pass; build | about 4 |
| 24q GEN-TYPES | [generate](groups/generate.md) | E1b, more distribution families, after a portable-sampling design | 2 |
| 24r GEN-INHERIT | [generate](groups/generate.md) | plan passed; build | about 3 |
| 24s GEN-CATALOG | [generate](groups/generate.md) | GC3-E (engine #643), then GC3 after the release | 2 |
| 24n GEN-REL, Later part | [generate](groups/generate.md) | parent-anchored date windows, per-parent aggregates, self-reference as a hierarchy | about 3 |

Fill: the generate candidates for per-provider options and `unique`, and HC5-FIT-CLI
([generate](groups/generate.md)); the corrective-backlog minors on `condition_on` with a renamed
parent, number-type inference for computed columns, and `unique_together` on a subset of a composite
key.

Depends on: the 1.0 part of row 24n. Engine release: yes.

## 1.3: more ways to install

Theme: reach. The container image and a PyPI package are the two ways a pipeline gets Decoy other
than the signed download. L3b and L5b ride here because their plans ask for three OS lanes, which
exist once the 1.0 Windows runner (row 6) is in place.

| Row or candidate | Group | What is left | Slices |
|---|---|---|---|
| 90a REL-IMAGE | [release](groups/release.md) | needs a plan; image build, signing, smoke run | about 3 |
| PYPI, PY-VERSIONS (candidates) | [release](groups/release.md) | publish the engine and the CLI on PyPI; add Python 3.13 | about 3 |
| 38 L3b-cli, 42 L5b-cli | [library](groups/library.md) | plans passed | 2 |

L3b and L5b depend on how the release gate settles the `decoy library` commands (row
EXPERIMENTAL-TIER). If they are frozen, L3b and L5b add record kinds and flags only. If they are
labelled experimental, a 1.x minor may also reshape them.

Depends on: 1.0 rows 90 (REL-PKG), 32a (SCAN-ML model install, for the `-ner` image tag) and 6
(WIN-RUNNER); L3b on 1.0 row 63 (SAMPLE). Engine release: no new engine code. PYPI publishes the
engine release the CLI already pins.

## 1.4: more sources

Theme: the data most users start from. A PostgreSQL source and SFTP and cloud scan complete the "read
from where the data is" story that 1.1 starts for targets.

| Row | Group | What is left | Slices |
|---|---|---|---|
| 64b CLI-DB-SRC | [connect](groups/connect.md) | not started; includes a Postgres CI lane | about 5 |
| 87 F02 | [connect](groups/connect.md) | plan written (E1 to E6, release, C1 to C4) | about 10 |

Fill: the connect candidates for SQL filters on sources and SFTP host-key pinning, and the run
candidate for subset from non-Parquet sources; the corrective-backlog minor on one engine retry choke
point for transient cloud errors (F02's retry executor is the same work; build it once).

Depends on: 1.1 (CLI-CLOUD, for F02). Engine release: yes.

## 1.5: policy, secrets and key rotation

Theme: governance. A security team can state rules once (selectors, prohibitions, precedence), keep
secrets in their own vault, and rotate token domains without breaking old outputs.

| Row | Group | What is left | Slices |
|---|---|---|---|
| 81 F16, with 24zt | [mask](groups/mask.md) | E2b (engine #642), E1, E3, release, C1, C2 (C2 carries 24zt) | 5 |
| 83 F13 external adapters | [mask](groups/mask.md) | HashiCorp Vault, AWS and GCP Secret Manager, Azure Key Vault | about 4 |
| 79 F09, Later part | [mask](groups/mask.md) | domain-version object, rotation, remap (plan gated 2026-11-15) | about 4 |

Fill: the mask candidate F17 portable disguise bundles.

Depends on: the 1.0 part of row 79 (the vault header). Engine release: yes. The vault format is fixed
for the life of 1.x ([2.0-holding.md](2.0-holding.md)), so rotation adds a version object and keeps
every existing reader.

## 1.6: scan baselines and drift

Theme: catch a source that changed before it reaches a test environment. All four rows build on the
scan library that 1.0 ships (LIB L2, SCAN-MULTI S3).

| Row | Group | What is left | Slices |
|---|---|---|---|
| 30 SCAN-LIB | [scan](groups/scan.md) | the run-evidence hash | 1 |
| 32 DRIFT | [scan](groups/scan.md) | not started | about 3 |
| 31 DIST-INTEGRITY | [scan](groups/scan.md) | not started | about 4 |
| 80 F15 | [scan](groups/scan.md) | not started | about 4 |

Fill: the scan candidates DETECT-PROFILES, X-09, trend and drift analytics, and the detector set
version field ([scan](groups/scan.md)).

Depends on: 1.0 rows 29 and 36. Engine release: yes.

## 1.7: quality contracts

Theme: say what "good output" means and have the run check it.

| Row | Group | What is left | Slices |
|---|---|---|---|
| 69 F35 | [trust](groups/trust.md) | E1a onward, plan rev 4 GO | about 4 |
| 68 F36 | [trust](groups/trust.md) | finish, entry slices, slice 4 registry; plan rev 8 GO | about 5 |

F35 goes first, and before F32 in 1.8 (owner Q5, 2026-11-08: F35 E1a before F32 E1b).

Fill: the trust candidates F12 and F37, and the generate candidate F46.

Engine release: yes.

## 1.8: evidence you can hand to an auditor

Theme: proof. A signed result that a third party can verify, the environment it ran in, and one
support bundle.

| Row | Group | What is left | Slices |
|---|---|---|---|
| 72 F33 | [trust](groups/trust.md) | plan in review (rev 9): E1a, E1b, C1a, C1b | 4 |
| 78 F10 | [trust](groups/trust.md) | release and repin, then 78-C1 | 1 |
| 70 F32 remainder | [trust](groups/trust.md) | E1b to E3, C0, C1, C1b | 6 |

Fill: the trust candidates for a Parquet support bundle and F39 OpenLineage export.

Depends on: 1.0 row 62 (RESULT); F32 E1b on F35 E1a (1.7). Engine release: yes.

## 1.9: nested data and application-ready databases

Theme: JSON columns and a database target an application can use straight away.

| Row | Group | What is left | Slices |
|---|---|---|---|
| 82 F07 | [connect](groups/connect.md) | 82-E1, E2a, E2b, E3a, E3b, E4a, E4b, E5 | 8 |
| 86 F01 | [connect](groups/connect.md) | not started | about 7 |

Fill: the connect candidate X-02 if F07 lands early.

Depends on: 1.4 (64b, the Postgres CI lane). Engine release: yes.

## The pool (after 1.9)

Every other candidate waits here. Pick the next minor's theme on evidence: a user asked, it unblocks
other rows, or it is cheap next to work in flight. Suggested themes, not ordered. Each one names the
group files whose candidate tables hold the items.

| Theme | Candidates | Groups |
|---|---|---|
| Larger-than-memory runs | the reversible vault on runs that write output, tokenize on the chunked routes, route-coverage phase 2, chunk-level resume, multi-hop FK chains, FK cycles, bounded reorder, nested relationships out of core, the mixed-job deferrals, F05, F42 | [mask](groups/mask.md), [run](groups/run.md), [connect](groups/connect.md) |
| File formats | X-01 to X-05, F03 | [connect](groups/connect.md) |
| More databases and streams | X-06, X-07, writing masked output back into a database | [connect](groups/connect.md), [run](groups/run.md) |
| Masks and detectors | X-08, X-10, X-13, F47, F50, cross-job joinable masking, `when:` hashing of number columns, the secondary Faker sources, `windowed_date` range, the Faker pool snapshot; value-based FK discovery | [mask](groups/mask.md), [scan](groups/scan.md) |
| Synthesis | F48, X-14 to X-18, the certified DP stack, dirty output on the mixed route | [generate](groups/generate.md) |
| Privacy measurement | F37, X-12, source-versus-output compare | [trust](groups/trust.md) |
| Authoring tools | F18, F19, F41; sample preview and dry run | [config](groups/config.md), [run](groups/run.md) |
| Integrations and extension | F39, F49, F40 and X-25 (the plugin SDK) | [trust](groups/trust.md), [connect](groups/connect.md), [mask](groups/mask.md) |
| Documents and media | X-19 to X-24 | [mask](groups/mask.md), [connect](groups/connect.md) |
| Local library | the user-level store, the local catalog | [library](groups/library.md) |

The plugin SDK (F40, X-25) builds on custom providers and the connector SDK, which 1.0 labels
experimental (row EXPERIMENTAL-TIER). A 1.x minor may reshape that surface, so the SDK can change it
without a v2. Output from a custom provider stays under the determinism rule.

## v2

v2 is not a feature release. The [handoff](../handoffs/2026-11-18-roadmap-strategy.md), "Doing the
breaking work in v1", lists the 1.0 rows that settle every known break before the freeze (24zi,
24zj, 24zk, FREEZE-SURFACE, FREEZE-OUTPUT, FAKER-MIGRATE, EXPERIMENTAL-TIER). This page does not
repeat them.

Three things go elsewhere:

- The items that are v1+ only if built a named way, and the surfaces fixed for the life of 1.x, are
  in [2.0-holding.md](2.0-holding.md). This schedule added HC1-CORPORA and WIDE-SIGNATURES there.
- Three freeze questions this schedule found that have no row yet (C9, the update channel, dropping
  Python 3.10) are in the [inbox](inbox.md), "Freeze candidates".
- Surfaces labelled experimental (the Python API, custom providers and the connector SDK) may change in
  a 1.x minor. A change to them is v1+, not v2.

## The upgrade path

`decoy upgrade` swaps the whole managed runtime (CLI and its pinned engine) to a newer signed bundle,
keeps the old one on disk, and can go back with `decoy upgrade --version`. Users move between any two
1.x releases this way, in either direction. Every 1.x release must keep the following. The rules are
stated in the linked pages; this list only says which ones the upgrade depends on.

| Keep | Rule | Where it is stated |
|---|---|---|
| Config schema additive only | A config valid in 1.x loads and gives the same result in every later 1.x. New keys are optional. | [post-1.0-plan.md](post-1.0-plan.md), "The rule"; `E:docs/compatibility-contract.md` sections 3.4 and 4.1 |
| Exit codes and reason strings stable | An exit code keeps its meaning. The reason registry is append-only; a reason that stops firing keeps its entry. | [post-1.0-plan.md](post-1.0-plan.md), "The rule"; [2.0-holding.md](2.0-holding.md), "Fixed for the life of 1.x" |
| Report tags versioned | A new report shape is a new tag (`name/vN+1`). A reader for every tag that 1.0 writes stays. | [post-1.0-plan.md](post-1.0-plan.md), "The rule"; `E:docs/compatibility-contract.md` sections 3.1 and 4.2 |
| The engine compatibility contract | Artifact formats, the vault, determinism and Faker data within a major, the public API, disguises. | `E:docs/compatibility-contract.md` sections 3 and 4, and section 8 for a real break; [2.0-holding.md](2.0-holding.md) |

The engine contract is at
[decoy-engine `docs/compatibility-contract.md`](https://github.com/decoy-data/decoy-engine/blob/main/docs/compatibility-contract.md).

Four points that these rules do not cover yet, found while checking them against the code
(2026-11-18):

1. **The update channel is part of the contract.** `decoy upgrade` checks the version document against
   one release key pinned in the build, and accepts only the exact schema `cli-version-document/v1`
   (`C:src/decoy/distribution/version_document.py`). A new key or a `v2` document would leave every
   older install unable to upgrade. This is a freeze candidate in the [inbox](inbox.md).
2. **Going back must be safe.** A newer minor may write a new artifact version (a library record, a
   resume store, a scan set). Write the new version only when the new feature is used, and make an
   older 1.x refuse an unknown version with a coded reason, never misread it. Then `decoy upgrade
   --version <older>` stays safe.
3. **Later engine code already on main ships in 1.0.** The engine releases daily, so engine slices of
   v1+ rows that merge before the freeze (F16 E2a, F23 E1 and E2, F10 E1 and E2) are in the engine
   that 1.0 pins. Each must stay unreachable from the frozen surface, or be added to the frozen
   surface map on purpose at REL-GATE (row 93). Otherwise its first 1.x change can be a break.
4. **The local record library is a stored format.** 1.0 freezes the record layout under `.decoy/` (row
   37), whatever the release gate decides for the `decoy library` commands. Later minors (L3b, L5b,
   the user-level store, the local catalog) add record kinds and never change an existing one.

## Corrective backlog by bucket and theme

The vault file `handoffs/V2-CORRECTIVE-BACKLOG.md` holds about 480 entries; the handoff counts 528
lines. Bringing it into the repo through the inbox is open item 2 of the handoff. A recount on
2026-11-18 found 385 patch tags, 17 minor, 32 to 38 "either", 16 V1, 10 check and 2 before the freeze
(some lines carry more than one item). This page does not copy the entries. It says where each theme
goes when it is triaged.

| Bucket | Themes | Goes to |
|---|---|---|
| v1+ minor (17) | generate options (renamed parent with `condition_on`, number-type inference, `unique_together`) | 1.2 fill |
| | run and observability (chunked progress events, `RouteSummary` and cap contract exports, a public subset guard, the subset signal in `decoy.mask()` and `tokenize`) | 1.1 fill |
| | connectors (one retry choke point for transient errors, a readable-sink protocol for wrapper sinks) | 1.4 fill |
| | scan and post-scan (multi-table drift baseline, all-null key columns, gate memory pressure read as out of memory) | 1.6 fill |
| | library and layout (writer sentry edge cases, fsck repair of special files, hard-link-aware layout identity) | 1.3 fill (L3b, L5b) |
| | web client `default_by` | [platform-parked.md](platform-parked.md) |
| either (32 to 38) | new refusals and changed reason strings | v1+ if they only warn or add a reason beside the old one, in the minor that touches the code; listed as a class in [2.0-holding.md](2.0-holding.md) |
| patch (about 385 to 436) | review notes from POSTSCAN, DUP-FREEZE, F21, F22, H-1, CLI-CLOUD, SUB-RUN, LIB, the Rust companion design audit, distribution-model QA, CI and tooling | 1.0.x patches, by theme, when a builder is free |
| V1 (16) | entries that say they stay V1 | check each against the three v1 tests; a live one becomes a 1.0 row, else it is v1+ |
| check (10) | owner questions and missing facts | inbox at the next triage |
| before 1.0 freeze (2) | one is the `large_string` type, now in 1.0 row FREEZE-OUTPUT | confirm the other against the 1.0 freeze rows at the next triage |

## Where each source landed

| Source | Landed in |
|---|---|
| Expansion candidates X-01 to X-25 | candidate tables of connect, mask, scan, generate and trust (done by the split); ordered in [The pool](#the-pool-after-19) |
| [post-1.0-plan.md](post-1.0-plan.md) item tables | group files, [2.0-holding.md](2.0-holding.md) and [platform-parked.md](platform-parked.md) (done by the split) |
| Outside review, 2026-11-18 (docs PR #319) | candidates PYPI and PY-VERSIONS ([release](groups/release.md)); two maintenance candidates in [health](groups/health.md); WIDE-SIGNATURES in [2.0-holding.md](2.0-holding.md); EXAMPLES-FIX, README-FIX, the generate bugs and dropping Python 3.10 in the [inbox](inbox.md) |
| Engine `docs/backlog/` | candidate HC5-FIT-CLI ([generate](groups/generate.md)); HC1-CORPORA in [2.0-holding.md](2.0-holding.md); the chunked-route tails in [health](groups/health.md) maintenance candidates. Already done, not candidates: the three S2 FK guides, `top-code-float64-numeric-domain.md` (resolved), `tx-freetext-ner-implementation.md` (`text_mask` NER is built) and the DPS plan (the accountant is built; the certified DP stack is a generate candidate) |
| Code check of `decoy upgrade` | C9 and the update channel in the [inbox](inbox.md); [The upgrade path](#the-upgrade-path) |
| Vault corrective backlog | [Corrective backlog by bucket and theme](#corrective-backlog-by-bucket-and-theme) |
