# CLI QA run: <group name> (template)

Status: current

<!-- Copy this file to docs/records/YYYY-MM-DD-cli-qa-<group>.md, one record per group pass, set the
copy's Status line to record, and delete these comments. Never paste a cell value or a secret into
this record. Name tables, columns, files, counts and reason codes only. -->

Checklist: [docs/qa/cli-v1-checklist.md](../qa/cli-v1-checklist.md), group <N>, at commit `<sha>`.

## Run

| Field | Value |
|---|---|
| Date (UTC) | YYYY-MM-DD |
| Tester | |
| CLI version (`decoy --version`) | |
| Engine version (the runtime's `decoy_engine.__version__`) | |
| Bundle and `SHA256SUMS` digest | |
| Platforms | linux-x86_64 / linux-aarch64 / macos-arm64 / windows-x86_64 |
| Native companion | present / absent |
| Fixture project commit or archive digest | |

## Group readiness

Every row in the group's "Waits on rows" line, with its State in `docs/ROADMAP.md` on the day of the
run. Do not start unless every State begins with `MERGED` or `DONE`. Rows 6, 77, 89, 93 and 94 never
hold a group (checklist, "When a group is ready for QA"): record RC checks and Windows cells as
blocked until their rows allow them.

| Row | State on the run date |
|---|---|
| | |

## Results

Copy the group's table from the checklist, one line per check per platform. Exit observed is the
code the command gave, or `none` when the check runs no command. Result is `pass`, `fail` or
`blocked`.

| Id | Platform | Exit observed | Result | Notes (value-free) |
|---|---|---|---|---|
| | | | | |

## Failures

One block per failed check.

### <Id>: <one-line summary>

- Command, exactly as run:
- Config: pipeline name and the keys involved (no data values):
- Expected (from the checklist):
- Observed: exit code and the output with values removed:
- Roadmap row filed: <row id, or "to file">

## Blocked checks

For each blocked check: the id, why it could not run as written, and the checklist correction made
in the same change.

## Summary

- Checks run: N. Passed: N. Failed: N. Blocked: N.
- Group verdict: pass (every check passed) or fail (rows filed above).
- Marker sweep (`python -m scripts.qa.sweep --needles data/markers.txt <captured files>` over captured output; exit 1 is clean): clean / findings listed above.
