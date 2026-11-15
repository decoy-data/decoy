# Release smoke log (append-only)

Two tables. The canonical table at the end is the release record: one row per green
candidate-mode smoke (`packaging_tools/smoke_install.py --from-dist`) of a signed 1.0.0 bundle
set on one supported platform. Rows are appended only by `scripts/release/record_smoke.py`,
which refuses a red run, a summary that does not match `candidate.json`, and any edit to a row
already committed. Release gate R1 counts only canonical rows.

The wheel-smoke table records past green runs of `.github/workflows/release-smoke.yml`. That
workflow builds the CLI wheel and installs it with pip, so it smokes a wheel, not the release
bundle; its rows do not count toward R1. It stays as the weekly regression lane and is not
appended to after this backfill.

No row holds a host name beyond a label, a user name, a home path or a secret.

## Wheel smoke (not the release artifact)

Backfilled once from the green `release-smoke` runs (Python 3.10, 3.11 and 3.12 each). Runs
before 2026-07-20 failed and are not listed.

| Date | SHA | Branch | Event | Python | Run |
|------|-----|--------|-------|--------|-----|
| 2026-07-20 | ab16941241ae | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/29728499791 |
| 2026-07-27 | 079bd1428f44 | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/30253997852 |
| 2026-08-03 | 079bd1428f44 | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/30799545625 |
| 2026-08-10 | 079bd1428f44 | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/31364569169 |
| 2026-08-17 | 079bd1428f44 | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/32002021842 |
| 2026-08-24 | 079bd1428f44 | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/32697864584 |
| 2026-08-31 | 079bd1428f44 | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/33389923445 |
| 2026-09-07 | 079bd1428f44 | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/34114162914 |
| 2026-09-14 | 4d16363f4158 | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/34836851424 |
| 2026-09-21 | 4d16363f4158 | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/35593603543 |
| 2026-09-28 | b8274b019474 | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/36420806688 |
| 2026-10-05 | d766d50234db | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/37313038857 |
| 2026-10-12 | 70869ea4b4bb | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/38258305653 |
| 2026-10-19 | 70869ea4b4bb | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/39244936135 |
| 2026-10-26 | f05b50135618 | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/40317780423 |
| 2026-11-02 | b4f19bade389 | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/41458730272 |
| 2026-11-06 | 0503fb465d74 | fix/ci-l1-cli-ci | workflow_dispatch | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/42239072431 |
| 2026-11-09 | 9f752825d140 | main | schedule | 3.10, 3.11, 3.12 | https://github.com/louiskeep/decoy/actions/runs/42636594411 |

## Release candidate smoke

Columns: date (UTC), CLI commit, engine tag, platform tag, the first 16 hex of the SHA-256 of
`SHA256SUMS`, the CI run URL or a host label, and a one-line note.

| Date | CLI SHA | Engine tag | Platform | SHA256SUMS | Run | Note |
|------|---------|------------|----------|------------|-----|------|
