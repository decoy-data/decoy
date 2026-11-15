# CLI QA run: <group name> (template)

Status: record

<!-- Copy this file to docs/records/YYYY-MM-DD-cli-qa-<group>.md, one record per group pass, and
delete these comments. Never paste a cell value or a secret into this record. Name tables, columns,
files, counts and reason codes only. -->

Checklist: [docs/qa/cli-v1-checklist.md](../qa/cli-v1-checklist.md), group <N>, at commit `<sha>`.

## Run

| Field | Value |
|---|---|
| Date (UTC) | YYYY-MM-DD |
| Tester | |
| CLI version (`decoy --version`) | |
| Engine version (`decoy info --json`) | |
| Bundle and `SHA256SUMS` digest | |
| Platforms | linux-x86_64 / linux-aarch64 / macos-arm64 / windows-x86_64 |
| Native companion | present / absent |
| Fixture project commit or archive digest | |

## Group readiness

Every row the group waits on, with its State in `docs/ROADMAP.md` on the day of the run. Do not
start unless every State begins with `MERGED` or `DONE`.

| Row | State on the run date |
|---|---|
| | |

## Results

Copy the group's table from the checklist, one line per check per platform. Result is `pass`,
`fail` or `blocked`.

| Id | Platform | Result | Notes (value-free) |
|---|---|---|---|
| | | | |

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
- Value-free sweep (`grep -r qamark` over captured output): clean / findings listed above.
