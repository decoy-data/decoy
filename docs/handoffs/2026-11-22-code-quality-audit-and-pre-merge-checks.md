# Handoff: the code-quality audit, when to run it, and standard pre-merge checks

Status: current. Written 2026-11-22. For the owner, the orchestrator and any builder. It collects
every planned code-quality remediation in one index, sets when the full quality audit runs in the
V1 timeline, and proposes the standard checks every PR runs before merge.

Path shorthand as in the roadmap: `E:` is `decoy-engine/src/decoy_engine/`, `ET:` is
`decoy-engine/tests/`, `C:` is `decoy/src/decoy/`, `CT:` is `decoy/tests/`.

Rules consulted: 00-universal, documentation, development-loop, proportionality, scope-discipline

## In one page

- Code-quality work is already planned in four places: the health group rows, the duplication
  census (2026-11-12), the proportionality audit (2026-11-15) and the clean-architecture review
  (2026-11-21). Section 2 indexes them; it does not replace them.
- The roadmap rule (owner 2026-11-21) stands: format, code-correctness and architecture findings are
  fixed in V1 or at the start of 1.x, before any new 1.x feature.
- **One full quality audit runs at V1 alpha, at the start of QA** (target about 2026-12-15 to
  2026-12-18), read-only and in parallel with QA. Its findings are triaged together with QA findings.
- **A narrow freeze-surface audit runs now**, before alpha, because a surface miss found after
  REL-GATE is a v2 break.
- **Every PR runs standard checks before the gate**: a lint-debt ratchet in `gates.sh`, `/simplify`
  and `/code-review` on the diff, and `/security-review` plus a Windows checklist when the diff
  touches the named areas. Section 5 has the proposal; it needs owner sign-off and an edit to
  `~/dev-rules/development-loop.md`.

## 1. Timeline

```
preV1 dev -> V1 alpha -> QA -> remediate + code quality -> V1 release -> v1+ dev
   |            |          |              |                     |            |
   |            |          |              |                     |            +-- guards hold the line;
   |            |          |              |                     |                no full audit until 2.0 prep
   |            |          |              |                     +-- delta pass on everything changed
   |            |          |              |                         since alpha, before REL-GATE
   |            |          |              +-- lint ratchets on first; /simplify and /code-review
   |            |          |                  on every remediation PR
   |            |          +-- one triage of audit + QA findings (V1 bar or 1.x row)
   |            +-- FULL AUDIT (read-only, runs beside QA)
   +-- narrow freeze-surface audit; close the open freeze rows; pre-merge checks on every PR
```

### Why the full audit runs at alpha

| When | Problem |
|---|---|
| During pre-V1 dev | Code moves at about 2 rows a day; findings and line references go stale before anyone fixes them. The 11-12 and 11-15 reports already show items absorbed or moved. |
| At alpha (chosen) | The code is feature-complete. Findings describe what will ship. The audit is read-only, so it adds no time to QA. |
| During remediation | Half the phase goes to finding work instead of doing it. The remediation phase needs the list on day one. |
| After release | Public names, reason codes, exit codes and `--json` shapes are frozen at REL-GATE. A fix there is a v2 break. |

### What runs in each phase

| Phase | Quality work |
|---|---|
| Pre-V1 dev (now) | Close the open freeze rows (24zf CL4, 24zi, 24zj, 24zk, FREEZE-SURFACE sign-off). Run the narrow freeze-surface audit (section 4). Start the pre-merge checks (section 5). |
| V1 alpha | Full audit, package by package, each finding verified (section 3). |
| QA | One triage of audit and QA findings by the same bar: blocks V1 (freeze, safety, broken today) or a 1.x row. Decide which ENGINE-ARCH and H-1 items are in the remediation phase. |
| Remediate + code quality | Turn on the lint-debt ratchets first so counts only go down. Run the work in section 2. `/simplify` and `/code-review` on every remediation PR. |
| Before V1 release | Delta pass: `/code-review` over the diff from the alpha tag to the release head. Not a second full audit. Remediation PRs are large and mechanical, which is where regressions hide. |
| v1+ dev | Sentries and lint ratchets prevent regrowth. Next full audit at 2.0 prep. |

## 2. Inventory of planned remediation

Each line points to its source. State lives in the group file or the record, not here.

Sources:
[health.md](../roadmap/groups/health.md),
[duplication census](../records/2026-11-12-duplication-census/REMEDIATION.md) (DC),
[proportionality audit](../records/2026-11-15-proportionality-audit/REMEDIATION.md) (PA),
[clean-architecture review](../records/2026-11-21-engine-clean-architecture-review.md) (AR).
Not readable from the public repos: the H-1 Wave B plan (`P:docs/plans/2026-11-01-h1-wave-b-code-organization.md`)
and the vault H-1 tracker.

### Open rows (as of 2026-11-22)

| Row | Bucket | Left |
|---|---|---|
| 24zf DUP-FREEZE | 1.0 | CL4 |
| 24zi PROP-FALLBACK | 1.0 | E-F1, E-F2, C-F1a, C-F1b, engine release and CLI repin |
| 24zj PROP-SURFACE | 1.0 | Not started (PA B1 to B9) |
| 24zk PROP-SHIMS | 1.0 | D2, D5, D6 manifest half, D7 to D13 |
| FREEZE-SURFACE | 1.0 | Sign-off: item 1 and item 7 |
| 24ze DUP-GUARDS | Maintenance | G-E1, G-E2, G-C1 |
| 24zl PROP-GUARDS | Maintenance | C-G2, E-G2a, E-G2b, E-G3 |
| ENGINE-ARCH | Maintenance, 1.x | AR findings 1 to 10; LAYERS-FORBID in progress |
| 46 to 54 H-1 | Maintenance | Handoffs not written; after CLI V1 (Q3) |
| SEAM-REASONS, SEAM-EXPLAIN | run group candidates | Delete the CLI admission copy (PA J3), shadow-only branches, PA C4 and C5 |

### By kind of work

**Module size and file splits.** H-1 rows 46 to 54 (CLI size census, split `C:distribution/installer.py`,
engine E-series, `E:execution/` subpackages as H-1 E8). PA package H: fold the 41 cap-only
`execution/` modules where the caller has room, and give `E:reasons/*/_partN.py` a data-file or
per-namespace shape. SIZE-CEIL (engine `docs/plans/size-ceil.md`): ceilings with headroom.
Oversize today: CLI `cli/report.py` 2270, `cli/scan.py` 930, `cli/preflight.py` 839, `cli/fit.py`
817; engine `detection/detectors.py` 920, `profiling/model_pack/trainer.py` 711, four files at 700.

**Directory structure and layering.** ENGINE-ARCH (AR): strategy policy from `execution` into
`contracts/`; break the 11-package import cycle (30 ignore lines); run orchestration and routing as
their own package; one route-preparation path for `capacity.py` and `_job_estimate.py`;
`PlanCompileError` to a leaf; a ranged-read port in `sdk/` for profile; pure plan compile;
LAYERS-FORBID contract.

**Imports and caller corrections.** PA D (shims and re-exports), PA B (unused public names), PA C
(dead modules), PA J (CLI copies of engine logic), DC EW-9 (one export point).

**One registry instead of many copies.** Per-strategy facts in about 12 tables across 8 modules
(AR finding 2, DC package H: EP-1, EP-2, EC-3, EC-23). Generate-type registry (EP-8). Config walk
and lookup helpers (DC I). RNG and canonical JSON owners (DC J). Data predicates (DC K). One
`topo_order`, one kernel loader, `PipelineRunContext` to executors (DC L). CLI error sites, JSON
artifact writer, `explain` topics from option definitions (DC N).

**Quiet fallbacks and impossible-state code.** PA A (row 24zi), PA G.

**Comments, tests, guards, docs.** PA F (history in comments; guard first, then sweep), PA I (test
reductions), PA E and section 15 (guard bookkeeping and new guards), PA K (diagrams, archive
shipped plans, one place for shipped state).

**Small extractions and possible-defect copies.** DC A, B, E, F. Several were absorbed by
DUP-FREEZE and FREEZE-SURFACE; re-check each against main before it is scheduled.

### Not covered by any audit yet

Rough marker counts on main, 2026-11-22. Plain text search, not triaged.

| Marker | Engine | CLI | Why it matters |
|---|---|---|---|
| `except Exception` or `BaseException` in source | 457 | 84 | PA package A names about 10 of them. The engine also ignores ruff `S110` and `S112` (try-except-pass and -continue) globally. |
| `# type: ignore` / `# noqa` in source | 115 / 186 | 21 / 7 | Silenced checks; each should carry a code and a reason |
| `pragma: no cover` in source | 113 | 3 | Code excluded from coverage |
| Skip and xfail markers in tests | 304 | 128 | Skips pile up instead of fixes |
| `mock.patch`, `MagicMock`, `monkeypatch.setattr` in tests | about 1,880 | about 725 | Tests that may assert the mock, not the behavior |
| `time.sleep` in tests | 35 | 21 | Flaky timing |
| Paths built with `"/"` in strings | 25 | 12 | Windows is in 1.0 |

Other AI-typical issues to look for at the alpha audit: weakened assertions (use the mutation
tooling, `scripts/tq_mutate.py`), dependencies declared and unused or used and undeclared
(`deptry`), docs and `--help` text that drifted from behavior, and the same constant defined in
several places.

## 3. The full audit at alpha

Read-only. Runs on the alpha tag of both repos.

- **Scope.** Package by package: engine `execution/` (split by subpackage), `plan`, `generation`,
  `profile` and `profiling`, `transforms`, the policy leaves; CLI `cli/run/`, `cli/` commands, `api.py`,
  `distribution/`. Tests in a separate pass.
- **Inputs.** The four reports in section 2, so known items are not re-reported. Each finding is
  matched to an existing id or marked new.
- **Lenses.** Correctness (`/code-review` at `high`), simplification and reuse (`/simplify` lens),
  security (`/security-review` lens on the areas in section 5), Windows portability (section 5
  checklist), test quality (skips, mock-only tests, weakened assertions), and the counts in section 2.
- **Verification.** Every finding is checked by a second pass that tries to disprove it before it
  reaches triage.
- **Output.** One record in `docs/records/` with each finding tagged V1 (freeze, safety, broken
  today) or 1.x, and the matching inbox lines.
- **How.** A multi-agent workflow (ask Claude to "use a workflow"), or `/code-review high <path>`
  per package by hand. `max` effort only for the release-blocking packages, and only on the owner's ask.

## 4. Narrow freeze-surface audit (now)

Only what REL-GATE freezes: public engine names and `__all__`, reason codes, CLI commands, flags and
defaults, exit codes, `--json` and result-document shapes, config keys, environment variables,
stored formats. For each: is it intended, is it named the way 1.x will keep it, does one owner
produce it. Findings go to the inbox; a confirmed one meets the freeze test and blocks 1.0. Rows
24zj PROP-SURFACE and FREEZE-SURFACE already cover part of this; the audit checks for anything they
miss.

## 5. Proposal: standard pre-merge checks

Hosted GitHub CI is off for billing, so checks run in `scripts/dev/gates.sh` locally and on the
self-hosted gate, and in the agent steps of the dev loop. Nothing here changes the V1 bar for a
merge: only a function break, data loss or a non-admin leak blocks. Other findings go to the inbox.

### Tier A: automatic, every PR (`gates.sh`)

1. **Lint-debt ratchet.** A new `lintdebt` step runs ruff with extra rules in report mode and
   compares per-file counts with a shrink-only baseline JSON, using the existing ratchet machinery
   (`ratchet_check.py`, single-source baseline per row 24zl). New code cannot add a hit; old hits
   are paid down as files are touched. Rules:

   | Rule | Catches |
   |---|---|
   | `BLE001` | `except Exception` |
   | `S110`, `S112` | try-except-pass and -continue (engine only; ignored globally today) |
   | `PGH003` | `# type: ignore` with no error code |
   | `ANN401` | `Any` in a signature |
   | `PTH` | string paths instead of `pathlib` |
   | `PLW1514` | `open()` without `encoding=` |
   | `ERA001` | commented-out code |
   | `C901`, `PLR0912`, `PLR0915` | functions too complex to review |
   | `T20` (CLI only, outside `ui/output.py`) | stray `print` |

2. **Existing sentries** (module size, layers, choke points) stay as they are.

### Tier B: agent checks, every PR, before the Codex and Dennis gates

The builder runs these on the PR diff and fixes or answers each finding before asking for a gate.

1. `/simplify`: reuse, simplification, efficiency. It applies its own fixes; the builder reviews them.
2. `/code-review medium` on the PR (`/code-review medium <PR number>`). A V1-bar finding is fixed
   in the PR. Anything else is fixed in the PR if small, or becomes an inbox line.

The gate record notes that both ran and what was done with each finding.

### Tier C: when the diff touches certain areas

| Diff touches | Also run |
|---|---|
| `E:vault*`, `E:secret_providers/`, `E:internal/crypto.py`, `E:determinism/`, `E:fileaccess/`, `E:connectors/`, `E:unmask*`, `E:publication*`, `C:_mask_secret.py`, `C:notify.py`, `C:cli/run/_notify.py`, `C:cli/upgrade.py`, `C:distribution/` | `/security-review` |
| File I/O, paths, subprocess, multiprocessing, signals, permissions | Windows checklist below |
| A public name, reason code, flag, exit code, `--json` shape or config key | The freeze questions in section 4 |
| A hot `cli/run/` lane file or `E:execution/` routing | `/code-review high` instead of `medium` |

**Windows checklist.** `pathlib` for every path; `encoding=` on every text `open`; `os.replace`, not
`os.rename`, over an existing file; no `fork` start method; no POSIX-only signals; no reliance on
`chmod` or POSIX modes; reserved device names (`CON`, `NUL` and the rest) go through the one table
(DC CE-2); filenames compared case-insensitively where the user supplies them.

### Not pre-merge

The full audit (alpha), mutation runs (scheduled, per package), `max`-effort review (owner's ask
only).

### What has to change to adopt this

| Change | Where |
|---|---|
| Add the tier B and C steps to the build and gate stages | `~/dev-rules/development-loop.md` (dev-rules repo) |
| Add the `lintdebt` step and its baselines | engine and CLI `scripts/dev/gates.sh`, `pyproject.toml`, baseline JSON |
| Mention the checks in the dev-loop section | [working-rules.md](../roadmap/working-rules.md) section 3 |
| The alpha audit and the delta pass as release steps | [release-gates.md](../roadmap/release-gates.md), R1 |

## 6. Open questions for the owner

1. Run the narrow freeze-surface audit now (recommended), or fold it into the alpha audit?
2. `/code-review` effort per PR: `medium` by default and `high` for hot lanes (recommended), or
   `high` everywhere at higher cost?
3. Tier B before the Codex and Dennis gates (recommended), or as a third gate?
4. Lint-debt ratchet in both repos at once, or the CLI first (smaller, 84 broad excepts) as a trial?
5. Remove the engine's global `S110` and `S112` ignores in favor of the ratchet?
