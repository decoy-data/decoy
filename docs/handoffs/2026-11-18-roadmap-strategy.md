# Handoff: the roadmap after 2026-11-18

Status: current. Written 2026-11-18. For the owner, the orchestrator and any builder or agent that
reads or edits the roadmap. It explains what changed on 2026-11-18, what was decided, and how to use
the roadmap from here.

Rules consulted: 00-universal, documentation, scope-discipline, proportionality

## In one page

- The roadmap is now a short index. Rows live in ten feature-group files.
- There are three release buckets. **v1** is what blocks 1.0. **v1+** is anything that does not break
  the contract, shipped in 1.x releases. **v2** is anything that breaks it.
- 1.0 scope is cut: 53 rows block 1.0. It was "every row on the track", which had no end.
- New work enters through one inbox and becomes a row only at triage.
- Work that would be a breaking change after 1.0 is done in v1. Four new rows carry it.
- Two surfaces ship in 1.0 labelled experimental, so changing them later is not a v2.

## Why it changed

`docs/ROADMAP.md` had grown to 153 KB because one file did five jobs: strategy, process rules, a
merge list, a file-lock table and a status tracker for 157 rows. Three things followed.

- Nobody could read it in one sitting, and one in four CLI commits was a roadmap text edit.
- The rule "every track row ships in 1.0" met no intake step. Each audit, QA run and review note
  became a new row, so 1.0 grew every day (rows 24a to 24zx).
- Ideas for after 1.0 sat in six places, sorted by version number and not by what to build next.

## What is where

| You want | Go to |
|---|---|
| The goal, the scope of each release, the list of groups | [`../ROADMAP.md`](../ROADMAP.md) (about 125 lines) |
| A row: its state, plan, branch and dependencies | its group file in [`../roadmap/groups/`](../roadmap/groups/) |
| To record something new | [`../roadmap/inbox.md`](../roadmap/inbox.md) |
| Whether a change breaks the contract | [`../roadmap/post-1.0-plan.md`](../roadmap/post-1.0-plan.md) (the rule only) |
| What waits for v2, and what cannot change in 1.x | [`../roadmap/2.0-holding.md`](../roadmap/2.0-holding.md) |
| The dev loop, choke-point rules, sequencing and single-writer rules | [`../roadmap/working-rules.md`](../roadmap/working-rules.md) |
| The parked platform rows and platform-only candidates | [`../roadmap/platform-parked.md`](../roadmap/platform-parked.md) |
| Dated owner decisions | [`../roadmap/decisions.md`](../roadmap/decisions.md) |
| What shipped | [`../RECENTLY-SHIPPED.md`](../RECENTLY-SHIPPED.md) |
| A closed row, the old merge list, any old section number | [`../archive/2026-11-18-roadmap-before-split.md`](../archive/2026-11-18-roadmap-before-split.md) |
| Why each row is in or out of 1.0 | [`../records/2026-11-18-1.0-scope-triage.md`](../records/2026-11-18-1.0-scope-triage.md) |

The ten groups are scan, config, mask, generate, run, library, connect, trust, release and health. A
group is a capability a user would name, not a phase. Every group file has the same shape:

| Section | Holds | Bucket |
|---|---|---|
| 1.0 | rows that block the release | v1 |
| Later (1.x) | planned rows that do not break the contract | v1+ |
| Candidates with no plan yet | non-breaking ideas from the old lists | v1+ |
| Maintenance | rows with no user-visible change | any time |

Rows carried from the old track keep their number (so plans, records and the QA checklist still
resolve). New rows have a short slug and no number.

## The three buckets

The owner's rule (2026-11-18): anything that does not break is v1+; anything that breaks is v2.

"Break" means the contract changes for a config or run that is valid today: a public name, a
default, an output byte, an exit code, a reason string, a schema field, a report tag, or a new
refusal of something that works. The full tests are in the post-1.0 plan; the contract itself is the
engine's `docs/compatibility-contract.md`.

| Bucket | Count on 2026-11-18 | Where |
|---|---|---|
| v1 | 53 rows | the 1.0 tables |
| v1+ | 27 planned rows and 88 candidates | Later in the group files; 7 platform-only candidates in the parked page |
| Maintenance | 13 rows and 32 candidates | Maintenance tables; the candidates are in `groups/health.md` |
| v2 | nothing scheduled | the 2.0 holding list |

### What gets into v1

A row blocks 1.0 only on one of three tests.

1. **Freeze.** It would be a breaking change after 1.0, so it is cheap now and a v2 later.
2. **Safety.** A leak, a wrong result reported as success, or a known advisory.
3. **Broken today.** A shipped command fails or misleads on the documented path.

"It would be good to have in 1.0" is not a test. An exception is an owner decision and gets a line in
the decisions log. Two are on record:

- **The init wizard (row 32b)** is additive but stays in v1: a first user cannot be asked to hand
  build complex YAML on a product they do not yet trust.
- **Windows (rows 89 and 6)** is in v1: the owner must be able to download the CLI and demo it on a
  Windows machine.

### Doing the breaking work in v1

After 1.0 a breaking change costs a major version, a migration tool and a deprecation window. The
same change before 1.0 costs a normal pull request. So everything known to be of that kind is a v1
row:

| Row | Group | What it settles |
|---|---|---|
| PROP-SURFACE (24zj) | health | unused public engine names. Unreferenced platform reason codes are kept as the platform wire contract, with the consumer recorded beside each. |
| PROP-FALLBACK (24zi) | health | failures that today report success |
| PROP-SHIMS (24zk) | health | readers for old formats and leftover re-exports |
| FREEZE-SURFACE | health | the strategy base class, hidden `decoy demo` flags, one profile call behind `api.scan`, a reason rename, `when:` reserved names, URL schemes, the written list of public renames |
| FREEZE-OUTPUT | run | three fixes that change output bytes or types |
| FAKER-MIGRATE | mask | Faker 40.31 before the freeze. Faker's data pools change between releases, so the Faker that ships in 1.0 fixes deterministic output for all of 1.x. |
| EXPERIMENTAL-TIER | release | see below |

The 2.0 holding list also names what is fixed for the life of 1.x (determinism, Faker data, the
vault, stored formats, `when:` reserved names, the reason registry). Read it before planning a v1+
feature.

### The experimental tier

The contract had no middle ground: anything in 1.0 was frozen. 1.0 now labels two surfaces
experimental, meaning they ship and work but their names and shape may change in a 1.x minor.

- The Python API (`decoy.mask`, `decoy.scan`).
- Custom providers and the connector SDK.

The `decoy library` commands are decided at the release gate: labelled if they land late with little
use, frozen otherwise. The stored records under `.decoy/` are frozen either way, and output from a
custom provider stays under the determinism rule. The engine contract is not edited yet; that is the
row's work.

### v1+: themed minors

A 1.x release is planned in three steps.

1. Pick one headline group from Later (for example connect: cloud targets and a PostgreSQL source).
   Pick it on evidence: a user asked, it unblocks other rows, or it is cheap next to work in flight.
2. Set a time budget (two to three weeks is a reasonable size) and fill it with that group's Later
   rows and candidates first, then small rows from other groups. What does not fit stays.
3. Check each item against the 2.0 holding list. Ten items there are v1+ only if built a named way
   (usually as an opt-in). Built the other way they are v2.

### v2

v2 is not a feature release. It is the list of breaking changes waiting for a reason to break.
Nothing is on it today. An item lands there when the owner decides not to do a freeze item in v1.

## Day to day

| When | Do |
|---|---|
| A review, QA run or audit finds something | Add one line to the inbox. Do not add a row. |
| Triage (at least weekly, and before planning a release) | Empty the inbox: each item to a group table or deleted. |
| You start a row | Read its group file row and its After column, then the working rules. |
| A slice merges | Update the row's State to what is left. Add the slice to the shipped log. |
| The last slice of a row merges | Add it to the shipped log and delete the row in the same change. |
| A row moves between v1 and v1+ | Edit the group file, and add a line to the decisions log. |
| A group table changes | Update that group's cells and the counts in the roadmap index (section 4). |
| A change would break the contract | Stop. Do it before the freeze as a v1 row, or put it on the 2.0 holding list. |

State cells are short from now on: one state word (NOT STARTED, PLANNED, BUILDING, IN REVIEW, PARTLY
MERGED), then what is left. Pull request numbers, hashes and merge dates belong in the shipped log.
Rows carried over still have their long State text; trim a row when you next touch it.

## Decisions on 2026-11-18

All are in the decisions log.

1. 1.0 is the 1.0 tables, not the whole track.
2. v1+ is anything non-breaking; v2 is anything breaking.
3. INIT-WIZARD is v1.
4. Windows is v1.
5. Faker moves to 40.31 before the freeze.
6. Unreferenced platform reason codes stay, with their consumer recorded.
7. The Python API and custom providers are experimental in 1.0; the library commands are decided at
   the release gate.
8. Options that could be on by default (output ordering and byte reproducibility F11, dataset
   metadata F38, free-text identity binding F08) stay opt-in, so they are v1+. This one was applied
   without an explicit owner answer; flipping any of them to default-on must happen before 1.0.

These rows moved to v1+ although an earlier owner decision said V1, and the owner has not objected:
CLI-CLOUD (64), CLI-DB-SRC (64b), F01 (86), GEN-PROVIDERS (24p), the remaining GEN-TYPES families
(24q), GEN-INHERIT (24r). GEN-REL (24n) and F09 (79) are split; the v1 part is named under the 1.0
table of their group file. Moving a row back is a one-row edit plus a decisions line.

## Known limits

- The split was mechanical. Row text is unchanged, so rows still cite old section numbers and closed
  rows. Those resolve in the snapshot.
- Buckets were set from each row's title and State text, not from its plan or code. Check a row's
  plan before relying on "nearly done".
- The retired product name may not appear in new files (the retired-name sentry). In the new files it
  reads NAME-REMOVAL, and branch or file names that contain it point to the snapshot.
- The 1.0 tables do not show one overall build order. Order comes from each After column and the
  sequencing rules. About half of the 1.0 rows are in flight at once; finishing rows before starting
  new ones would shorten the list fastest.
- Candidates were placed in a group by their title. A few sit between two groups.
- The Windows bar stated by the owner is download, install and demo. WIN-FEAS still has to say
  whether every 1.0 feature holds on Windows or only that path.
- The corrective backlog in the vault (528 entries, 38 of them "v1+ or v2 depending on design") was
  not read. It is outside the repos.
- Only the retired-name, codemap-path, QA-checklist and journey sentries and the ratchet check were
  run. The full suite needs `typer`, `decoy_engine` and the import linter, which the build container
  did not have.

## Not done yet

1. **Choose the 1.1 theme.**
2. **Bring the vault's corrective backlog into the repo**, through the inbox.
3. **Fold the expansion page.** `roadmap/v2-v3-expansion-candidates.md` still holds the long text of
   X-01 to X-25; the group files list them as candidates. Its name also contradicts the bucket rule.
4. **Plan lifecycle in the engine repo.** `docs/plans/` holds 219 files, most of them built or
   superseded. Archive them and fix the Status line to a short fixed set.
5. **Stale pointers.** `decoy-web/PLAN.md` names the platform repo as the roadmap home. The `PLAN.md`
   files in the CLI and engine say planning is private. `roadmap/feature-checklist.md` has statuses
   from the 2026-10-27 audit. `roadmap/row-detail.md` and the QA checklist row index still describe
   the old track.
6. **A guard.** A sentry that checks every row appears in exactly one group table and in the roadmap
   index, with matching counts. Until it exists the index is kept in step by hand.
