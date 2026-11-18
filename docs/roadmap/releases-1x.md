# 1.x release schedule

Status: plan

Part of the roadmap: [ROADMAP.md](../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

This page says which Later rows ship in which 1.x release, and what every 1.x release must keep so that
`decoy upgrade` stays safe. Written 2026-11-18 from the scope split (owner intent: cut 1.0 so it ships,
plan 1.x now, anything that breaks the engine contract is 2.0).

What this page does not hold:

- The rows. Each row lives in the Later or Maintenance table of its [group file](groups/). This page
  names rows by id only.
- The bucket rule (1.x minor, 1.x patch, before 1.0 freeze, 2.0) and the reason for each item's
  bucket. Those are in [post-1.0-plan.md](post-1.0-plan.md).
- Dates. Each minor is planned as two to three weeks of work, as the
  [roadmap handoff](../handoffs/2026-11-18-roadmap-strategy.md) says. The schedule is an order, not a
  calendar.

## How to read the schedule

- A minor has one theme. It carries the Later rows of that theme first, then small rows from other
  groups ("fill") if the time budget allows. Fill that does not fit moves to the next minor or back to
  the pool. It never delays the release.
- Size is in slices. A slice is one reviewed pull request of about 800 hand-written lines or fewer
  ([working-rules.md](working-rules.md), 4.2). The numbers are rough and come from each row's plan
  where one exists.
- "Engine release" says whether the minor needs engine code that is not yet in a release. If it does,
  the CLI half waits for the engine release and the repin, as working rules 5.2 items 3 and 4 say.
- Corrective backlog entries (vault) are not rows. When a minor is planned, triage pulls the entries
  of its theme from the backlog into the inbox, and from there into the minor. The theme map is in
  [Corrective backlog](#corrective-backlog-by-bucket-and-theme) below.
- The order of the minors is a recommendation by user value and dependency. A user request can move
  a theme earlier. Moving one is an edit here plus a line in [decisions.md](decisions.md).

## Summary

| Release | Theme | Headline rows | Size (slices) | Engine release |
|---|---|---|---|---|
| 1.0.x | Fixes | EXAMPLES-FIX, README-FIX, 24zr, Maintenance rows | 1 to 4 each | only if a fix is in the engine |
| 1.1 | Run in production pipelines: cloud targets and resume | 64, 85, 84, 41 | about 18 | yes |
| 1.2 | Generate completeness | 24p, 24q, 24r, 24s, 24n-later | about 14 | yes |
| 1.3 | Install anywhere: Windows, the container image, PyPI | 6, 89, 90a, PYPI, PY-VERSIONS, 38, 42 | about 16 | yes (Windows paths) |
| 1.4 | More sources: PostgreSQL in, SFTP and cloud scan | 64b, 87 | about 15 | yes |
| 1.5 | Policy, secrets and key rotation | 81, 24zt, 83, 79-later | about 13 | yes |
| 1.6 | Scan baselines and drift | 30, 31, 32, 80 | about 12 | yes |
| 1.7 | Quality contracts | 69, 68 | about 9 | yes |
| 1.8 | Evidence you can hand to an auditor | 72, 78, 70 | about 11 | yes |
| 1.9 | Nested data and application-ready databases | 82, 86 | about 15 | yes |
| 1.10 onward | Chosen from the pool on evidence | see [The pool](#the-pool-after-19) | | |
| 2.0 | Only contract breaks | see [2.0](#20) | | |

1.1 to 1.9 carry all 29 Later rows of the scope split and the Later parts of the two split rows (24n
and 79).

## 1.0.x patch releases

A patch release carries fixes and internal cleanup. For a config or run that is valid today it never
changes a name, a default, an output byte, an exit code, a reason string, a schema field or a report tag.
Cut one when a fix is ready; there is no
fixed cadence.

Candidates, in the order to take them:

1. User-visible fixes found before or at 1.0 that missed the release: EXAMPLES-FIX
   ([config](groups/config.md)), README-FIX ([release](groups/release.md)), 24zr SETUP-NER-JSON
   ([release](groups/release.md)).
2. The Maintenance rows of every group: H-1 splits (rows 46 to 54), 24ze, 24zl, 24zq, PROP-CLEANUP,
   FINDINGS-PATCH, OUTSIDE-REVIEW-CI ([health](groups/health.md)); RUN-PATCH ([run](groups/run.md));
   MASK-PATCH ([mask](groups/mask.md)); CLOUD-COND-WRITES ([connect](groups/connect.md));
   INSTALL-METADATA ([release](groups/release.md)). These merge to main whenever they are ready and
   ride the next release of either kind.
3. The 1.x patch entries of the corrective backlog (about 400), by theme, when a builder is free.

A fix that a user reports and that breaks a function or loses data goes first, in its own patch.

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

Fill: NOTIFY-OUTCOME ([run](groups/run.md)); the corrective-backlog minors on chunked progress events
and the subset signal in `decoy.mask()` and `decoy tokenize`.

Depends on: 1.0 rows 61 (CLI delivery) and 59 (F22). Engine release: yes (CLI-CLOUD EC slices; F23 E1
and E2 are merged but not yet in a release the CLI pins).

## 1.2: generate completeness

Theme: synthetic data that looks like the business. All five rows have a passed plan or merged slices,
so this is cheap next to work in flight. The owner put all of them in V1 before the split.

| Row | Group | What is left | Slices |
|---|---|---|---|
| 24p GEN-PROVIDERS | [generate](groups/generate.md) | plan in a final fix pass; build | about 4 |
| 24q GEN-TYPES | [generate](groups/generate.md) | E1b, more distribution families, after a portable-sampling design | 2 |
| 24r GEN-INHERIT | [generate](groups/generate.md) | plan passed; build | about 3 |
| 24s GEN-CATALOG | [generate](groups/generate.md) | GC3-E (engine #643), then GC3 after the release | 2 |
| 24n-later GEN-REL capabilities | [generate](groups/generate.md) | parent-anchored date windows, per-parent aggregates, self-reference as a hierarchy | about 3 |

Fill: GEN-PROVIDER-OPTS, HC5-FIT-CLI ([generate](groups/generate.md)); the corrective-backlog minors
on `condition_on` with a renamed parent, number-type inference for computed columns, and
`unique_together` on a subset of a composite key.

Depends on: 1.0 row 24n (its 1.0 part). Engine release: yes.

## 1.3: install anywhere

Theme: reach. Windows was in the 1.0 goal "if possible" and moved out at the split. The container
image and a PyPI package are the other two ways a pipeline gets Decoy. L3b and L5b ride here because
their plans ask for three OS lanes, which need the Windows runner.

| Row | Group | What is left | Slices |
|---|---|---|---|
| 6 WIN-RUNNER | [release](groups/release.md) | provision the runner | 1 |
| 89 WIN-FEAS | [release](groups/release.md) | feasibility first, then fixes (file ACLs, atomic replace, paths, installer, signing) | about 6 |
| 90a REL-IMAGE | [release](groups/release.md) | needs a plan; image build, signing, smoke run | about 3 |
| PYPI, PY-VERSIONS | [release](groups/release.md) | publish engine and CLI on PyPI; support Python 3.11 to 3.13 | about 3 |
| 38 L3b-cli, 42 L5b-cli | [library](groups/library.md) | plans passed | 2 |

Also carries the Windows arm of F22 (W1), which is still listed as left in 1.0 row 59. Move W1 out of
row 59 into WIN-FEAS when row 59 is next touched.

Start the WIN-FEAS feasibility study during 1.1, so that a blocker reaches the owner before 1.3 is
planned. If Windows is not feasible, 1.3 ships the image and PyPI and Windows goes back to Later.

Depends on: 1.0 rows 90 (REL-PKG) and 32a (SCAN-ML model install, for the `-ner` image tag); L3b on
1.0 row 63 (SAMPLE). Engine release: yes, for the Windows file paths.

## 1.4: more sources

Theme: the data most users start from. A PostgreSQL source and SFTP and cloud scan complete the "read
from where the data is" story that 1.1 starts for targets.

| Row | Group | What is left | Slices |
|---|---|---|---|
| 64b CLI-DB-SRC | [connect](groups/connect.md) | not started; includes a Postgres CI lane | about 5 |
| 87 F02 | [connect](groups/connect.md) | plan written (E1 to E6, release, C1 to C4) | about 10 |

Fill: SQL-FILTER, SFTP-HOSTKEY, SUBSET-ANY-SOURCE ([connect](groups/connect.md)); the corrective-backlog
minor on one engine retry choke point for transient cloud errors (F02's retry executor is the same
work; build it once).

Depends on: 1.1 (CLI-CLOUD, for F02). Engine release: yes.

## 1.5: policy, secrets and key rotation

Theme: governance. A security team can state rules once (selectors, prohibitions, precedence), keep
secrets in their own vault, and rotate token domains without breaking old outputs.

| Row | Group | What is left | Slices |
|---|---|---|---|
| 81 F16, with 24zt | [mask](groups/mask.md) | E2b (engine #642), E1, E3, release, C1, C2 (C2 carries 24zt) | 5 |
| 83 F13 external adapters | [mask](groups/mask.md) | HashiCorp Vault, AWS and GCP Secret Manager, Azure Key Vault | about 4 |
| 79-later F09 | [mask](groups/mask.md) | domain-version object, rotation, remap (plan gated 2026-11-15) | about 4 |

Fill: F17 ([mask](groups/mask.md)), after owner question 3 in [post-1.0-plan.md](post-1.0-plan.md).

Depends on: 1.0 row 79 (the vault header). Engine release: yes.

## 1.6: scan baselines and drift

Theme: catch a source that changed before it reaches a test environment. All four rows build on the
scan library that 1.0 ships (LIB L2, SCAN-MULTI S3).

| Row | Group | What is left | Slices |
|---|---|---|---|
| 30 SCAN-LIB | [scan](groups/scan.md) | the run-evidence hash | 1 |
| 32 DRIFT | [scan](groups/scan.md) | not started | about 3 |
| 31 DIST-INTEGRITY | [scan](groups/scan.md) | not started | about 4 |
| 80 F15 | [scan](groups/scan.md) | not started | about 4 |

Fill: DETECT-PROFILES, X-09, SCAN-TRENDS ([scan](groups/scan.md)).

Depends on: 1.0 rows 29 and 36. Engine release: yes.

## 1.7: quality contracts

Theme: say what "good output" means and have the run check it.

| Row | Group | What is left | Slices |
|---|---|---|---|
| 69 F35 | [trust](groups/trust.md) | E1a onward, plan rev 4 GO | about 4 |
| 68 F36 | [trust](groups/trust.md) | finish, entry slices, slice 4 registry; plan rev 8 GO | about 5 |

F35 goes first, and before F32 in 1.8 (owner Q5, 2026-11-08: F35 E1a before F32 E1b).

Fill: F12, F46, F37 ([trust](groups/trust.md)).

Engine release: yes.

## 1.8: evidence you can hand to an auditor

Theme: proof. A signed result that a third party can verify, the environment it ran in, and one
support bundle.

| Row | Group | What is left | Slices |
|---|---|---|---|
| 72 F33 | [trust](groups/trust.md) | plan in review (rev 9): E1a, E1b, C1a, C1b | 4 |
| 78 F10 | [trust](groups/trust.md) | release and repin, then 78-C1 | 1 |
| 70 F32 remainder | [trust](groups/trust.md) | E1b to E3, C0, C1, C1b | 6 |

Fill: BUNDLE-PARQUET, F39 ([trust](groups/trust.md)).

Depends on: 1.0 row 62 (RESULT); F32 E1b on F35 E1a (1.7). Engine release: yes.

## 1.9: nested data and application-ready databases

Theme: JSON columns and a database target an application can use straight away.

| Row | Group | What is left | Slices |
|---|---|---|---|
| 82 F07 | [connect](groups/connect.md) | 82-E1, E2a, E2b, E3a, E3b, E4a, E4b, E5 | 8 |
| 86 F01 | [connect](groups/connect.md) | not started | about 7 |

Fill: X-02 ([connect](groups/connect.md)) if F07 lands early.

Depends on: 1.4 (64b, the Postgres CI lane). Engine release: yes.

## The pool (after 1.9)

Every other Later row waits here. Pick the next minor's theme on evidence: a user asked, it unblocks
other rows, or it is cheap next to work in flight. Suggested themes, not ordered:

| Theme | Rows |
|---|---|
| Larger-than-memory runs | VAULT-STREAM, TOKENIZE-CHUNKED ([mask](groups/mask.md)); ROUTE-COV2, CHUNK-RESUME, FK-MULTIHOP, FK-CYCLES, FK-REORDER, OOC-NESTED-REL, MIXED-ROUTE, F05, F42 ([run](groups/run.md), [connect](groups/connect.md)) |
| File formats | X-01, X-02, X-03, X-04, X-05, F03 ([connect](groups/connect.md)) |
| More databases and streams | X-06, X-07 ([connect](groups/connect.md)) |
| Masks and detectors | X-08, X-10, X-13, F47, HC1-CORPORA, F08, MASK-SOURCES, WINDOWED-DATE-RANGE, JOIN-GROUP, WHEN-HASH-NUM, FK-WHEN-SIBLING ([mask](groups/mask.md)); X-11, FK-DISCOVER, SCAN-PROFILE-AGG ([scan](groups/scan.md)) |
| Synthesis | F48, X-14, X-15, X-16, X-17, X-18, DP-CERT, GEN-ORACLE, GEN-MIXED-DIRTY ([generate](groups/generate.md)) |
| Privacy measurement | F37, X-12, LEAK-COMPARE ([trust](groups/trust.md)) |
| Authoring tools | F18, F19, F20, F41 ([config](groups/config.md)); DRY-RUN ([run](groups/run.md)) |
| Integrations and extension | F39, F49, F50 ([trust](groups/trust.md)); F40 ([mask](groups/mask.md)); NOTIFY-SCHEME, F11 ([run](groups/run.md)) |
| Documents and media | X-19, F38 ([connect](groups/connect.md)); X-20, X-21, MEDIA ([mask](groups/mask.md)) |
| Local library | USER-LIBRARY, LOCAL-CATALOG ([library](groups/library.md)) |
| Hardening | HARDEN-INPROC, WIDE-SIGNATURES ([health](groups/health.md)) |

The expansion page tags (V1+, V2, V3) in [v2-v3-expansion-candidates.md](v2-v3-expansion-candidates.md)
are size and placement hints. They are not releases.

## 2.0

2.0 is a holding list of contract breaks. It is cut only when the list is worth a break, and it is not
a feature release. Today no planned item has to be 2.0.

### Breaks if not done before the 1.0 freeze

These change a name, a default, an output or a stored format. Done before row 93 (REL-GATE), they cost
nothing. Left until after 1.0, each one is 2.0. Each has a line in the [inbox](inbox.md) or a 1.0 row.

| Item | Where it is decided |
|---|---|
| Unused public names B1 to B9 | 1.0 row 24zj PROP-SURFACE |
| Quiet fallbacks A1 to A9 | 1.0 row 24zi PROP-FALLBACK |
| Old readers and shims D1 to D13 (D6 and D9 freeze) | 1.0 row 24zk PROP-SHIMS |
| F22 publication names | 1.0 row 59 |
| Taxonomy split renames (the retired product name; NAME-REMOVAL) | inbox (owner question 4 in [post-1.0-plan.md](post-1.0-plan.md)) |
| C9, C10, C16, J2 from the proportionality audit | inbox |
| Partition-stable `when:` on number-with-blanks columns | inbox |
| The `.gz` header storing the staging basename | inbox |
| `run_mask_chunked` writing `large_string` | inbox |
| The `layout.report_source_ambiguous` reason rename | inbox |
| Generate: negative sequential id, lorem text in a date column, fidelity scores that disagree (outside review) | inbox (V1 QA decides) |
| Dropping Python 3.10 | inbox |
| The update channel: one pinned release key with no rotation path, and an exact match on `cli-version-document/v1` | inbox (see [The upgrade path](#the-upgrade-path)) |

### Kept 1.x by design

Each of these is a Later row whose bucket is "1.x if <design>, else 2.0". Build it the 1.x way. Building
it the other way moves it here.

| Row | 1.x if | Group |
|---|---|---|
| F08 | the free-text identity binding is an opt-in option | [mask](groups/mask.md) |
| F11 | output ordering is opt-in | [run](groups/run.md) |
| F20 | `migrate` writes a new schema version and old configs still load | [config](groups/config.md) |
| F38 | metadata preserving is opt-in | [connect](groups/connect.md) |
| X-11 | it is a new opt-in detector or profile | [scan](groups/scan.md) |
| SCAN-PROFILE-AGG | the aggregates are an option or new fields | [scan](groups/scan.md) |
| HARDEN-INPROC | custom providers keep working | [health](groups/health.md) |
| GEN-ORACLE | new routes match today's output byte for byte | [generate](groups/generate.md) |
| FK-WHEN-SIBLING | the sibling keeps seeing the source key | [mask](groups/mask.md) |
| NOTIFY-SCHEME | the check only warns, or keeps every scheme that works today | [run](groups/run.md) |
| WIDE-SIGNATURES | the old `run_pipeline` keywords keep working | [health](groups/health.md) |
| HC1-CORPORA | full corpora ship as new corpus versions a config chooses; the seed corpora stay the default | [mask](groups/mask.md) |
| BUNDLE-PARQUET | the old support bundle format stays readable and the default | [trust](groups/trust.md) |

The corrective backlog has 32 to 38 more entries of this kind (`[either: ...]`). Most are a new refusal
or a changed reason string that stays 1.x if it only warns, or adds a new reason beside the old one.

## The upgrade path

`decoy upgrade` swaps the whole managed runtime (CLI and its pinned engine) to a newer signed bundle,
keeps the old one on disk, and can go back with `decoy upgrade --version`. Users move between any two
1.x releases this way, in either direction. Every 1.x release must keep the following. The rules are
stated in the linked pages; this list only says which ones the upgrade depends on.

| Keep | Rule | Where it is stated |
|---|---|---|
| Config schema additive only | A config valid in 1.x loads and gives the same result in every later 1.x. New keys are optional. | [post-1.0-plan.md](post-1.0-plan.md), "The rule", tests 1 and 2; `E:docs/compatibility-contract.md` sections 3.4 and 4.1 |
| Exit codes and reason strings stable | An exit code keeps its meaning. The reason registry is append-only; a reason that stops firing keeps its entry. | [post-1.0-plan.md](post-1.0-plan.md), "The rule" and VAULT-STREAM note; [working-rules.md](working-rules.md) 4.1 (reason registry choke point) |
| Report tags versioned | A new report shape is a new tag (`name/vN+1`). A reader for every tag that 1.0 writes stays. | [post-1.0-plan.md](post-1.0-plan.md), "The rule"; `E:docs/compatibility-contract.md` sections 3.1 and 4.2 |
| The engine compatibility contract | Artifact formats, the vault (forever), determinism within a major, the public API, disguises. | `E:docs/compatibility-contract.md` sections 3 and 4, and section 8 for a real break |

The engine contract is at
[decoy-engine `docs/compatibility-contract.md`](https://github.com/decoy-data/decoy-engine/blob/main/docs/compatibility-contract.md).

Four points that these rules do not cover yet, found while checking them against the code
(2026-11-18):

1. **The update channel is part of the contract.** `decoy upgrade` checks the version document against
   one release key pinned in the build, and accepts only the exact schema `cli-version-document/v1`
   (`C:src/decoy/distribution/version_document.py`). A new key or a `v2` document would leave every
   older install unable to upgrade. The download host must publish a `v1` document for as long as any
   1.x install exists. Key rotation needs a path that a 1.0 build can verify, and it has to ship in
   1.0 to help 1.0 installs. This is an inbox item before the freeze.
2. **Going back must be safe.** A newer minor may write a new artifact version (a library record, a
   resume store, a scan set). Write the new version only when the new feature is used, and make an
   older 1.x refuse an unknown version with a coded reason, never misread it. Then `decoy upgrade
   --version <older>` stays safe.
3. **Later engine code already on main ships in 1.0.** The engine releases daily, so engine slices of
   Later rows that merge before the freeze (F16 E2a, F23 E1 and E2, F10 E1 and E2) are in the engine
   that 1.0 pins. Each must stay unreachable from the public surface, or be added to the frozen surface
   map on purpose at REL-GATE (row 93). Otherwise its first 1.x change can be a break.
4. **The local record library is a stored format.** 1.0 freezes the record layout under `.decoy/` (row
   37). Later minors (L3b, L5b, USER-LIBRARY, LOCAL-CATALOG) add record kinds and never change an
   existing one.

## Corrective backlog by bucket and theme

The vault file `handoffs/V2-CORRECTIVE-BACKLOG.md` holds about 480 entries. Its bucket counts are in
[post-1.0-plan.md](post-1.0-plan.md), "Corrective backlog (vault)" (a recount on 2026-11-18 found 385
patch tags, 17 minor, 32 either, 16 V1, 10 check, 2 before the freeze; some lines carry more than one
item). This page does not copy the entries. It says where each theme goes.

| Bucket | Themes | Goes to |
|---|---|---|
| 1.x minor (17) | generate options (renamed parent with `condition_on`, number-type inference, `unique_together`) | 1.2 fill |
| | run and observability (chunked progress events, `RouteSummary` and cap contract exports, a public subset guard, the subset signal in `decoy.mask()` and `tokenize`) | 1.1 fill |
| | connectors (one retry choke point for transient errors, a readable-sink protocol for wrapper sinks) | 1.4 fill |
| | scan and post-scan (multi-table drift baseline, all-null key columns, gate memory pressure read as out of memory) | 1.6 fill |
| | library and layout (writer sentry edge cases, fsck repair of special files, hard-link-aware layout identity) | 1.3 fill (L3b, L5b) |
| | web client `default_by` | platform |
| either (32 to 38) | new refusals and changed reason strings | 1.x if they only warn or add a reason beside the old one; the theme minor that touches the code |
| 1.x patch (about 385 to 436) | review notes from POSTSCAN, DUP-FREEZE, F21, F22, H-1, CLI-CLOUD, SUB-RUN, LIB, the Rust companion design audit, distribution-model QA, CI and tooling | 1.0.x patches, by theme, when a builder is free |
| V1 (16) | entries that say they stay V1 | check each against the 1.0 tables; a live one becomes a 1.0 row or is closed |
| check (10) | owner questions and missing facts | inbox at the next triage |
| before 1.0 freeze (2) | already in [post-1.0-plan.md](post-1.0-plan.md) | inbox |

## Platform items

These came from the same candidate lists but belong to the paid platform, which is parked until CLI V1
ships. They are listed in [platform-parked.md](platform-parked.md), section 6.4, and are not in the CLI
1.x schedule: F27 governed schedules, F28 local execution node, F45 login limits and password policy,
multi-process API support, the MCP server, the de-tokenize half of the vault (MG-5), DuckDB 5, 16, 17
and 21, the web client `default_by`, and the flaky platform tests (including D5 certification coverage
and the cgroup launcher).

## Where each source landed

| Source | Landed in |
|---|---|
| Expansion candidates X-01 to X-25 | Later rows in connect, mask, scan, generate, trust (X-25 is F40) |
| [post-1.0-plan.md](post-1.0-plan.md), 1.x minor tables | Later rows; the platform items in [platform-parked.md](platform-parked.md) |
| [post-1.0-plan.md](post-1.0-plan.md), 1.x patch tables | Maintenance rows PROP-CLEANUP, FINDINGS-PATCH, RUN-PATCH, MASK-PATCH, CLOUD-COND-WRITES; the rest were already in 1.0 rows 24zi to 24zl |
| [post-1.0-plan.md](post-1.0-plan.md), before 1.0 freeze | 1.0 rows 24zi, 24zj, 24zk, 59, or the inbox |
| [post-1.0-plan.md](post-1.0-plan.md), 2.0 only if built the other way | Later rows; listed under [Kept 1.x by design](#kept-1x-by-design) |
| Outside review, 2026-11-18 (docs PR #319) | EXAMPLES-FIX, README-FIX, PYPI, PY-VERSIONS, WIDE-SIGNATURES (Later); INSTALL-METADATA, OUTSIDE-REVIEW-CI (Maintenance); three items to the inbox |
| Engine `docs/backlog/` | HC5-FIT-CLI, HC1-CORPORA, DP-CERT (Later); RUN-PATCH, MASK-PATCH (Maintenance). Already done, not candidates: the three S2 FK guides, `top-code-float64-numeric-domain.md` (resolved), `tx-freetext-ner-implementation.md` (`text_mask` NER is built), and the DPS plan (the accountant is built; DP-CERT is what is left) |
| Vault corrective backlog | [Corrective backlog by bucket and theme](#corrective-backlog-by-bucket-and-theme) |

The item tables in [post-1.0-plan.md](post-1.0-plan.md) stay as the record of each item's bucket and
reason. The rows now live in the group files.
