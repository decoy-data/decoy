# Release readiness: decoy-cli 1.0.0

Status: current

This is the template. Copy it to `docs/records/YYYY-MM-DD-release-readiness-1.0.0.md` for the release
candidate and fill it in; do not edit the copy's row text. `scripts/release/readiness_check.py` checks the
structure and the identity of the copy, not whether a criterion was met: that comes from running the command
in each row. The gates G0 to G8 are in `docs/plans/2026-11-15-rel-gate.md` section 4.

Result values: `pass`, `fail`, `accepted-known-limit`. A `pass` row cites evidence: an https run URL, a
repo-relative record path or a commit SHA. An `accepted-known-limit` row lists the V2-LOG ids of its cells,
separated by `;`. Rows 12 and 14 are manual: their evidence names the reviewer, the commit read (7 or more
hex digits) and the date (YYYY-MM-DD).

## Rows

| id | gate | command | criterion | result | evidence | owner |
|---|---|---|---|---|---|---|
| 1 | G0 | Read the roadmap State column | Every row above 93 is closed or moved to V2-LOG by Cam. Evidence: roadmap commit | | | orchestrator |
| 2 | G1 | `release_checks.sh` in the engine repo at the D-4 tag | Exit 0, log linked. Evidence: run URL | | | orchestrator |
| 3 | G3 | `scripts/release/launch_pin_check.py` at the CLI SHA | Exit 0. Evidence: run URL | | | worker |
| 4 | G3 | Both frozen-surface map sentries and all snapshot tests at the exact heads | Green. Every accepted-known-limit map cell in both maps is listed with its V2-LOG id (`readiness_check.py --engine-repo` enumerates them). Evidence: run URL | | | worker |
| 5 | G3 | CLI and engine T2 gate sets at the exact heads, with the saved main baselines named | No new failure. Evidence: run URL | | | orchestrator |
| 6 | G3 | Pre-release audit (`dev-rules/pre-release-audit.md`): static, dependency and secret scans on both repos | No unwaived HIGH; the certified-pin CVE repin (owner F1, 2026-11-11) is closed. Evidence: record path | | | orchestrator |
| 7 | G4 | QA records for every V1 feature group (row 92a and the engine checklist), each citing the checklist's merged SHA | No open V1 finding, EXIT-01 passed at G4, every CLI check marked RC except BLD-07 run on the candidate at G6 or G7 with a pass. BLD-07 reads this instance and runs at G8. Evidence: record path | | | orchestrator |
| 8 | G5 | Build-and-sign workflow from CLI-REL S0, then `packaging_tools/candidate.py` | Bundles signed; `SHA256SUMS`, version document and `candidate.json` produced. Evidence: run URL | | | Cam |
| 9 | G6 | Canonical smoke rows in `docs/release/smoke-log.md` for every supported platform | Rows match the candidate record; the shipped release key is the owner's key and equals the key that signed the set. Evidence: record path | | | orchestrator |
| 10 | G5 | `scripts/release/sbom.sh` | SBOM produced and its digest recorded. Evidence: run URL | | | worker |
| 11 | G7 | `readiness_check.py --release` licensor checks | Green (5.6). Evidence: run URL | | | orchestrator |
| 12 | G7 | Claims checkpoint (B-3): `CLAIMS-AUDIT.md` complete and `/proof` synced to the catalog | Manual: reviewer, decoy-web commit read, date | | | decoy-web |
| 13 | G7 | Docs honesty: CHANGELOG 1.0.0 section, release notes draft, security contact | All present. Evidence: commit SHA | | | worker |
| 14 | G7 | Local gates and the worker-bootstrap gates (R1-d) | Manual: gates run, host, head SHA and date | | | orchestrator |
| 15 | G7 | GA flip (Q3) | Done, or explicitly deferred by Cam. Evidence: record path | | | Cam |
| 16 | G7 | CLA status (Q2) | The owner's answer is recorded. Evidence: record path | | | Cam |
| 17 | G7 | Legal-file markers: every `TODO` in the license file list (plan 5.6) | Each is classified in the Legal markers list below by the owner | | | Cam |
| 18 | G8 | Owner sign-off | The sign-off block below is filled. Evidence: record path | | | Cam |

## Identity

Record the G3 fields at G3, the G5 digest at G5, and all four again at G7. If a field changed after G3 or G5,
the gates were rerun against the new value: record it under Reruns, or the check refuses the drift.

- g3.cli_sha:
- g3.engine_tag:
- g3.engine_commit:
- g5.sha256sums_sha256:
- g7.cli_sha:
- g7.engine_tag:
- g7.engine_commit:
- g7.sha256sums_sha256:

## Reruns

- rerun.cli_sha:
- rerun.engine_tag:
- rerun.engine_commit:
- rerun.sha256sums_sha256:

## Licensor

The final legal name from counsel's answer (Q1), filled at G7. Every copyright and licensor line in the
license files must equal it.

- licensor:

## Legal markers

One line per `TODO` marker left in the license files, as `- cli:FILE TOKEN => CLASS` or
`- engine:FILE TOKEN => CLASS`, where CLASS is `release-blocking` or `carry-forward`. A release-blocking
marker that remains in its file fails `--release`.

## Sign-off

- signoff.owner:
- signoff.date:
- signoff.decision:
