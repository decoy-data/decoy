# Handoff: how to use the roadmap from 2026-11-18

Status: current. Written 2026-11-18. For the owner, the orchestrator and any builder or agent that
reads or edits the roadmap.

Rules consulted: 00-universal, documentation, scope-discipline, proportionality

## Why it changed

`docs/ROADMAP.md` had grown to 153 KB because one file did five jobs: strategy, process rules, a
merge list, a file-lock table and a status tracker for 157 rows. Three things followed.

- Nobody could read it in one sitting, and one in four CLI commits was a roadmap text edit.
- The rule "every track row ships in 1.0" met no intake step. Each audit, QA run and review note
  became a new row, so 1.0 grew every day (rows 24a to 24zx) and had no end.
- Ideas for after 1.0 sat in six places, sorted by version number and not by what to build next.

## What is where now

| You want | Go to |
|---|---|
| The goal, the scope of each release, the list of groups | [`../ROADMAP.md`](../ROADMAP.md) (about 120 lines) |
| A row: its state, plan, branch and dependencies | its group file in [`../roadmap/groups/`](../roadmap/groups/) |
| To record something new | [`../roadmap/inbox.md`](../roadmap/inbox.md) |
| The dev loop, choke-point rules, sequencing and single-writer rules | [`../roadmap/working-rules.md`](../roadmap/working-rules.md) |
| The parked platform rows | [`../roadmap/platform-parked.md`](../roadmap/platform-parked.md) |
| Whether a change is 1.x or 2.0 | [`../roadmap/post-1.0-plan.md`](../roadmap/post-1.0-plan.md) |
| What shipped | [`../RECENTLY-SHIPPED.md`](../RECENTLY-SHIPPED.md) |
| A closed row, the old merge list, any old section number | [`../archive/2026-11-18-roadmap-before-split.md`](../archive/2026-11-18-roadmap-before-split.md) |
| Why each row is in or out of 1.0 | [`../records/2026-11-18-1.0-scope-triage.md`](../records/2026-11-18-1.0-scope-triage.md) |

There are ten groups: scan, config, mask, generate, run, library, connect, trust, release, health.
A group is a capability a user would name, not a phase. Each group file has three tables: 1.0, Later
and Maintenance. Rows keep their old numbers so existing plans, records and the QA checklist still
resolve. New rows get a short slug (as SUB-RUN and RUN-STREAM have) and no number.

## The strategy

Four kinds of information change at four speeds, so each has its own place.

| Kind | Changes | Place |
|---|---|---|
| Direction: the goal and what each release is for | rarely | `ROADMAP.md` |
| Commitment: the rows, their state and dependencies | per slice | group files |
| Intake: what came up and is not yet decided | daily | inbox |
| History: what merged | per merge | shipped log and git |

The roadmap stays short because it holds only the first kind and an index of the second.

### Feature selection has one gate

Everything new goes to the inbox as one line. Triage is the only step that makes a row. Triage gives
each item one outcome:

1. **Blocks 1.0.** Only on one of three tests. Freeze: it changes a public name, default, output,
   exit code, reason or stored format, or adds a refusal of something that works today. Safety: a
   leak, a wrong result reported as success, a known advisory. Broken today: a shipped command fails
   or misleads on the documented path.
2. **Later.** It adds something next to existing behavior. This is most ideas.
3. **Maintenance.** No user-visible change. It merges whenever it is ready and never gates a release.
4. **Rejected.** Deleted.

"It would be good to have in 1.0" is not a test. One exception is on record: the init wizard is 1.0
although it is additive, because a first user cannot be asked to hand build complex YAML on a product
they do not yet trust. An exception like that is an owner decision and gets a line in
[`../roadmap/decisions.md`](../roadmap/decisions.md).

### After 1.0: themed minors

A 1.x release is planned in three steps.

1. Pick one headline group from Later (for example connect: cloud targets and a PostgreSQL source).
   Pick it on evidence: a user asked, it unblocks other rows, or it is cheap next to work in flight.
2. Set a time budget (two to three weeks is a reasonable size) and fill it with that group's Later
   rows first, then small rows from other groups. What does not fit stays in Later.
3. Check each row's bucket in the post-1.0 plan. A row that would break the contract cannot ship in
   a minor; it goes to the 2.0 holding list.

2.0 is not a feature release. It is the list of breaking changes waiting for a reason to break.

## Day to day

| When | Do |
|---|---|
| A review, QA run or audit finds something | Add one line to the inbox. Do not add a row. |
| Triage (at least weekly, and before planning a release) | Empty the inbox: each item to a group table or deleted. |
| You start a row | Read its group file row and its After column, then the working rules. |
| A slice merges | Update the row's State to what is left. Add the slice to the shipped log. |
| The last slice of a row merges | Add it to the shipped log and delete the row in the same change. |
| A row's scope changes | Edit the row. If it moves between 1.0 and Later, add a line to the decisions log. |
| A group table moves | Update the group's cells in the roadmap index (section 4) in the same change. |

State cells are short from now on: one state word (NOT STARTED, PLANNED, BUILDING, IN REVIEW, PARTLY
MERGED), then what is left. Pull request numbers, hashes and merge dates belong in the shipped log.
The rows carried over today still have their long State text; trim a row when you next touch it.

## Decisions applied today

- 1.0 is 47 rows. 29 rows are Later and 13 are Maintenance. Five rows were closed as not being
  features (named releases, work the owner had already deferred).
- INIT-WIZARD (row 32b) is 1.0.
- Two rows are split: GEN-REL (24n) and F09 (79). The 1.0 part is named under the 1.0 table of the
  group file.
- These moved to Later although an earlier owner decision said V1: CLI-CLOUD (64), CLI-DB-SRC (64b),
  F01 (86), GEN-PROVIDERS (24p), the remaining GEN-TYPES families (24q), GEN-INHERIT (24r), and
  Windows (6, 89). Moving one back is a one-row edit plus a decisions line.

## Known limits of this split

- It was a mechanical move. Row text is unchanged, so rows still cite old section numbers and closed
  rows. Those resolve in the snapshot.
- Buckets were set from each row's title and State text, not from its plan or code. Check a row's
  plan before relying on "nearly done".
- The retired product name may not appear in new files (the retired-name sentry). In the new files it
  reads NAME-REMOVAL, and branch or file names that contain it were replaced by a pointer to the
  snapshot.
- The 1.0 tables do not show an overall build order. Order comes from each After column and the
  sequencing rules. About half of the 1.0 rows are in flight at once; finishing rows before starting
  new ones would shorten the list faster than anything else.

## Not done yet

1. **Fold the other candidate lists into Later or the inbox**: the X-items in
   `roadmap/v2-v3-expansion-candidates.md`, the item tables in `roadmap/post-1.0-plan.md` (keep its
   rule, move its items), engine `docs/backlog/`, and the corrective backlog in the vault.
2. **Choose the 1.1 theme.**
3. **Plan lifecycle in the engine repo.** `docs/plans/` holds 219 files, most of them built or
   superseded. Archive them and fix the Status line to a short fixed set.
4. **Stale pointers.** `decoy-web/PLAN.md` names the platform repo as the roadmap home. The `PLAN.md`
   files in the CLI and engine say planning is private. `roadmap/feature-checklist.md` has statuses
   from the 2026-10-27 audit. `roadmap/row-detail.md` and the QA checklist row index still describe
   the old track.
5. **A guard.** A sentry that checks every row id appears in exactly one group table and in the
   roadmap index would keep the two from drifting. It is not built.
