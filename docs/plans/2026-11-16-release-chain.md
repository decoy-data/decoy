# Release chain: rows 47, 76, 78, 88, 90, 90a and 91

Status: plan

Date: 2026-11-16. Author: Opus planner. Bases: CLI `origin/main` `60cac678`, engine `origin/main`
`13c95c7d` (#607). Line numbers below are from those heads.

Rules consulted: `dev-rules/00-universal.md`, `dev-rules/risk-and-exceptions.md`,
`dev-rules/development-loop.md`, `dev-rules/release-and-rollback.md`,
`dev-rules/catalogs/recurring-defects.md`, `dev-rules/testing.md` (Test depth),
`dev-rules/workspace-and-vcs.md` (Commit messages); memories plan-defines-acceptance-tests,
v1-bar-blocking-criteria, develop-correctly-registries-and-sizing.

This plan covers the release-chain rows that have not started, and the parts of the partly done
rows that have not started. V1 is CLI 1.0.0, with an optional 1.0.0rc.1 first. The Windows chain
(rows 6 and 89) is out of scope; where a slice must leave a hook for it, the slice says so.

It adds no feature beyond the row text. Where a row already has a gated plan, this plan does not
repeat it: it says whether that plan still stands on main and lists what changed.

## 1. Verdicts

| Row | Name | Verdict |
|---|---|---|
| 47 | H-1 C1 installer split | Needs this plan. The H-1 Wave B C1 design stands, with new line numbers and two fixes: the row's path is wrong, and five sentry keys must be re-homed. Build before row 88's code. |
| 46 | H-1 C0 census and checker | Census done by FILE-SIZE (row 7, slice C2, CLI #196). Only the pure-move checker is left, and it moves into row 47 as slice 47-A. Recommend: mark row 46 folded. |
| 76 | R-d engine release and repin | Needs this plan: a release train, not one release. Engine releases are pre-authorized. The last train stop is the D-4 launch tag at REL-GATE G1. |
| 78 | F10 runtime lock and environment report | Needs this plan. The source plan the row cites (`P:docs/plans/2026-10-24-upgrade-determinism-gate.md`) is a platform golden-sample gate and is parked with the platform. This plan replaces it for the engine and CLI halves. |
| 88 | F44 CLI half | SBOM generators merged. Left: upgrade preflight, offline signature path for upgrade, a rollback compatibility statement, and an SBOM built at release time and shipped in the bundle. "Signed bundles" is row 94 S0 and owner-gated. |
| 90 | REL-PKG | Only MAC-V1a is left (PR #282, plan `plan/mac-ed25519` `97dbcfb0`). Plan stands. The rest is owner tasks and row 94 S0. |
| 90a | REL-IMAGE | Plan exists and passed its gate (`plan/rel-image` `d4716855`). The roadmap text "NOT STARTED; needs a plan" is stale. Plan stands with the deltas in section 9. IMG-1 can build now. |
| 91 | REL-WEB | Plan exists (`plan/rel-web` `53e0e77c`, rev 3). RW-C2b is no longer blocked: owner Q1 and Q2 were answered 2026-11-15. Web slices RW-H, RW-D and RW-P are planned and not started. |

## 2. Order across rows

Start now, in parallel (no dependency between them):

1. 47-A, the pure-move checker (CLI).
2. RD-0, the pin-location sentry, and the daily RD-n release and repin (engine, CLI).
3. 78-E1, the lock envelope (engine).
4. 88-S, the SBOM, LICENSE and NOTICE in the bundle (CLI).
5. 88-R, the rollback compatibility statement (CLI docs and one sentry).
6. 90 MAC-V1a: finish the gate on PR #282.
7. 90a IMG-1, the image gate (CLI).
8. 91 RW-C2b (CLI docs); a Codex pass on the REL-WEB plan, then RW-H (web).

Then:

9. 78-E2, the probe, after 78-E1.
10. 47-B, the installer split, after 47-A.
11. 91 RW-D and RW-P (web), after RW-H.
12. 88-O, the offline upgrade path, after 47-B (it lands in the new `_bundle.py`).
13. 78-C1, the CLI environment report, after 78-E1 and 78-E2 are in an engine release the CLI
    pins (an RD-n stop).
14. 88-P, the upgrade preflight, after 78-C1 and 88-O.

Owner-gated, then:

15. Row 94 S0 (`release.yml`) after the release key and the `native-release` Environment exist.
16. 90a IMG-2 after one published native companion release; IMG-3 after IMG-2; IMG-4 after S0
    and the GHCR organization; IMG-5 after row 32a.
17. The last RD-n stop is the D-4 tag (REL-GATE G1); the repin to it, version 1.0.0 and the key
    commit are G2.

Build-complete is 2026-12-04 (G0). Items 1 to 14 fit before G0. Items 15 to 17 depend on owner
actions; section 12 lists them with the dates they are needed by.

## 3. Rules that apply to every slice

- At most 10 production files and 800 lines per slice. Tests, fixtures and docs do not count to
  the file cap. The one exception is RD-n (section 5), recorded there.
- Risk tiers follow `dev-rules/risk-and-exceptions.md`. R1: Codex review only. R2: Dennis then
  Codex, exact-head gate. No slice in this plan is R3. Owner actions (key creation, tag push,
  spend) are R3 and stay with the owner.
- Tests run on the Mac or a VM through `~/bin/vm-run`, never on the devbox. T0 per edit, T1 per
  commit, T2 at the gate. A full suite runs only on an escalation trigger: 47-B moves tests and
  sentry keys, and 88-O and 88-P touch the signature path, so those three get a full suite on the
  merge head against the saved baseline.
- Each acceptance test below is written first and must fail on the base head for the reason
  given ("fails before"). A builder may add tests but must not weaken these.
- Recurring defect classes apply by name: 1 (anchored validation) to the `key_version` label and
  every new option value; 3 (no exception context) to every new refusal; 4 (versioned read models)
  to `lock/v1` and `decoy-env-report/v1`; 11 (no raised caps) to every ratchet this plan touches.
- Commit rules: Conventional Commits subject, no body unless it says why, final line `cam`.
- No logging of data values, user project paths, host names or key material.
- File size cap 800 lines. `src/decoy/cli` is frozen at 29 direct modules; a new command goes in a
  named sub-package (sub-packages do not count toward the parent).

## 4. Established solutions

Searches run for this plan (web and codebase):

- Offline install with signature checks. Rust's standalone installers ship a detached signature
  per archive for offline hosts; rustup itself fetches on demand and is not meant for offline use
  (forge.rust-lang.org, "Other installation methods"). Mirror tools (Panamax, romt) carry archives
  and signatures across the gap and verify on import. Decoy already follows this model in
  `install.sh` (`DECOY_LOCAL_BUNDLE` plus `.sha256` and `.sig` sidecars). 88-O reuses the same
  sidecars and the same pinned key; no new trust format.
- Reproducible SBOM. `cyclonedx-py` honors `SOURCE_DATE_EPOCH` for the timestamp and has an
  `--output-reproducible` mode (cyclonedx-bom-tool docs and changelog, v7.4.0). The serial number
  is a random UUID by design; reproducible output drops it. 88-S uses `cyclonedx-py environment`
  against the bundle's own interpreter, with `SOURCE_DATE_EPOCH` set to the bundle's fixed mtime
  and `--output-reproducible`. The builder confirms at build time that the pinned tool version
  omits the serial in that mode; if it does not, the slice stops and reports.
- Runtime lock and environment report. Established patterns: lock files that record the exact
  resolved inputs (`uv.lock`, Nix `flake.lock`) and environment reports that are diffed rather than
  enforced (`conda env export`, `pip freeze`). The engine already has `runtime_identity()`
  (`generation/_pinned_plan.py:163`) and one canonical JSON writer (`_canonical`). 78-E1 builds on
  both; no new hashing or serialization code.
- Pure-move check. The engine has `scripts/check_pure_move.py` (H-1 Wave A). 47-A ports it.
- Pin agreement. The CLI already has one source for the engine spec (`lock_version.sh
  --engine-spec`) and tests that read it. RD-0 extends that pattern to the remaining locations.

Custom code that remains: the field list of the lock, the probe inputs, and the CLI command
wiring. Each is small and specific to Decoy.

## 5. Row 47: H-1 C1, split `installer.py`

### Scope

Split `src/decoy/distribution/installer.py` (731 lines) into private modules by concern, as a
pure move. The row names `src/decoy/cli/distribution/installer.py`; that path does not exist. The
real file is `src/decoy/distribution/installer.py`. Fix the row text when this slice merges.

No sentry forces the split today (731 is under 800). It is done now because row 88 adds an
offline bundle source and an upgrade preflight to this file, which would put it over the cap.

Guarantee: no behavior change. Non-goals: renaming public names, changing error text, changing
the B-2 staging order.

### V1 behavior

No behavior change. Every public name that callers import from `decoy.distribution.installer`
still imports from there.

### Target layout

From the H-1 Wave B plan (`P:plan/h1-wave-b`, `docs/plans/2026-11-01-h1-wave-b-code-organization.md`,
section C1), checked against main:

| New module | Moves (current lines) | Size |
|---|---|---|
| `src/decoy/distribution/_slots.py` | `_fresh_same_version_slot` 126, `_promote_staged` 139, `_reclaim_superseded` 161, `_sweep_stale_staging` 175, `_retained_other` 443, `prune_old_versions` 695 (re-exported) | about 170 lines |
| `src/decoy/distribution/_trust.py` | `_read_trust_state` 185, `_trust_state_text` 207, `check_document_freshness` 215 (re-exported) | about 70 lines |
| `src/decoy/distribution/_bundle.py` | `_urllib_download` 247, `_no_bytecode_env` 254, `_selfcheck` 265, `_resolve_in_archive` 286, `_extract_bundle` 314, `_try_download_sha` 369, `_bundle_declared_version` 379, `_bundle_declared_target` 451 | about 220 lines |
| `src/decoy/distribution/installer.py` (stays) | `install_version` 464, `activate_local_version` 398, `local_version_present` 392, `_write_launcher_shim` 660, `resolve_bundle_base`, `DEFAULT_BUNDLE_BASE`, the error and outcome types | about 300 lines |

`_write_launcher_shim` stays in `installer.py` so the private-files key
`installer.py::_write_launcher_shim::os.chmod::1` does not move. `check_document_freshness` moves,
so its key `installer.py::check_document_freshness::write_atomic::1` is re-homed to `_trust.py`.

The error and outcome types stay in `installer.py`; the new modules must not import
`installer` (no cycle). If a moved function raises `InstallError`, the type moves to `_trust.py`
or a small `_errors.py` and `installer.py` re-exports it. The builder picks one and records it.

### Design notes

No new structure beyond the split. Principle: single responsibility, applied because row 88 is
about to add two concerns (local source, preflight) to a file that already holds four. Pattern:
the H-1 Wave A splits in the engine (pure move, re-export, characterization golden first).

### Failure modes

- A test patches a private name on `decoy.distribution.installer` (for example
  `monkeypatch.setattr(installer, "_urllib_download", ...)`) and the moved code no longer reads it
  from there, so the patch silently does nothing. A false green.
- A sentry allowlist keyed on `installer.py::<function>` no longer matches, and the entry is
  dropped instead of re-homed, which loosens the ratchet.
- An import cycle between `installer.py` and a new module.
- The B-2 rule (never change a version folder in place) breaks if staging steps change order.

### Acceptance tests (write first)

| Id | Test | Fails before |
|---|---|---|
| AT-47-1 | `scripts/dev/check_pure_move.py --base origin/main --head HEAD src/decoy/distribution` reports every removed function body present byte-for-byte in one new module, and no other source change except imports and re-exports | The script does not exist in the CLI (47-A adds it) |
| AT-47-2 | `tests/unit/test_installer_characterization.py::test_install_version_layout_golden` (from H-1 Wave B) passes unchanged before and after the split. Mutation: rename the staged folder before the self-check; the test must fail | The golden test does not exist on main |
| AT-47-3 | A test lists every `monkeypatch.setattr(installer, "<name>")` and `mock.patch("decoy.distribution.installer.<name>")` in `tests/`, and asserts each name is still looked up through `installer` at run time, or the patch target names the new module | No such test; after a move the patch would be a no-op |
| AT-47-4 | Re-homed sentry keys: `tests/sentry/test_atomic_writer.py` (lines 108, 278), `tests/sentry/io_policy/test_canonical_json.py:56`, `tests/sentry/io_policy/test_private_files.py:101,133`. For each moved key the count is unchanged, and a test proves the old key no longer matches (owner re-home rule, 2026-11-15) | The old keys point at code that moves |
| AT-47-5 | `import decoy.distribution.installer as i` then `i.install_version`, `i.check_document_freshness`, `i.prune_old_versions`, `i.activate_local_version` in a clean venv | Guard: green before, must stay green |
| AT-47-6 | QA INST-17: INST-01 to INST-06 and INST-14 give the same result on the split build | Run at QA |

### Slices

| Slice | Files (production) | Lines | Tests | Risk |
|---|---|---|---|---|
| 47-A | `scripts/dev/check_pure_move.py` (ported from engine `scripts/check_pure_move.py`, adapted to CLI paths) | 1 file, about 250 | self-test with a fixture move (passes) and a fixture move plus one edited line (refused) | R1 |
| 47-B | `installer.py`, `_slots.py`, `_trust.py`, `_bundle.py`, the sentry allowlist data for the re-homed keys; test patch targets updated in `test_distribution.py`, `test_distribution_r7_security.py`, `test_distribution_acceptance.py`, `tests/unit/distribution/test_bundle_base.py`, `test_atomic_callers.py`, `test_release_smoke_workflow.py`, `tests/e2e/test_upgrade_error_text.py` | 4 production files, about 750 moved lines | AT-47-1 to AT-47-5; full suite on the merge head | R2 |

The characterization golden (AT-47-2) lands as 47-B's first commit, before any move, so the gate
sees it pass on the unsplit file.

### Placement

| Item | Goes in | Map line and neighbor |
|---|---|---|
| `_slots.py`, `_trust.py`, `_bundle.py` | `src/decoy/distribution/` | Private modules beside their owner, as `layout_point.py` and `verify_extracted.py` sit today. 13 direct modules now, 16 after, under the 25 cap |
| `check_pure_move.py` | `scripts/dev/` | Dev tooling, beside `ratchet_check.py`; 5 Python modules there |
| Characterization test | `tests/unit/test_installer_characterization.py` | Name fixed by H-1 Wave B |

## 6. Row 76: R-d, engine release train and CLI repin

### Scope

R-d carries the engine halves of SUB-RUN, F25, F22, POSTSCAN-STREAM, CONFIG-EXPLICIT, DELIV,
RESULT, SAMPLE, and the engine parts of SCAN-LIB, DIST-INTEGRITY and DRIFT. Under the daily
release train (owner D4, 2026-11-09) this is a series of releases. The CLI pins 0.27.0 today
(CLI #290). Each stop is one engine release plus one CLI repin.

SUB-RUN, F25, POSTSCAN-STREAM and CONFIG-EXPLICIT are merged in the engine. F22, DELIV, RESULT
and SAMPLE are partly merged. SCAN-LIB is mostly delivered by other rows. DIST-INTEGRITY (row 31)
has not started. Row 76 closes when the last engine half on its list is in a release the CLI pins.
If row 31 is not built by G0, it leaves the R-d list by owner call (OQ-6) and row 76 closes
without it.

Guarantee: at every stop, all pin locations name the same engine tag. Non-goal: deciding what each
release contains (that follows what merged).

### Release unit and recovery (release-and-rollback rulebook)

- Unit: one engine tag `vX.Y.Z` cut from engine main (3-file stamp on a `release/` branch, not
  merged to main), then one CLI repin PR.
- Preconditions: engine main CI green on the tagged commit; the CLI repin PR green including the
  release freeze shape test.
- Health check: CLI main CI and the nightly after the repin merges.
- Rollback: revert the CLI repin PR (the previous tag still exists). A tag is never moved or
  deleted; a bad release is followed by a new patch release.

### Pin locations (from the 0.27.0 repin, CLI #290)

`pyproject.toml`, `scripts/dev/lock_version.sh` (`ENGINE_SPEC`, the one source the tests read),
`requirements-certified.txt`, `requirements-dev.lock`, `.github/workflows/ci.yml`,
`.github/workflows/release-smoke.yml`, `scripts/cert_smoke.py`, `scripts/dev/bootstrap.sh`,
`packaging_tools/candidate.py`, `src/decoy/ci/rule_codes.py`, `CHANGELOG.md`, `LICENSING.md`,
`README.md`, `docs/release/fresh-install-smoke.md`, the guides that quote a version, and
`tests/fixtures/release_freeze/json-shapes.json` (new report shapes). The REL-IMAGE Dockerfile
`ARG` joins this list when IMG-2 merges.

### Failure modes

- A partial repin: one location still names the old tag. `test_ci_lock_installs.py`
  (`test_lock_profile_lives_in_lock_version_and_the_policy`) and `test_pyproject_metadata.py`
  catch the engine URLs and the pyproject pin; the docs and `candidate.py` are not checked today.
- A release changes a JSON shape and the shape is not recorded in `json-shapes.json`.
- Two repins in flight at once on different branches.

### Acceptance tests

| Id | Test | Fails before |
|---|---|---|
| AT-76-1 | A sentry reads `lock_version.sh --engine-spec` and asserts every literal engine version in the listed pin locations (docs included, `CHANGELOG.md` history excluded) equals it. The list is one tuple in the test, a reason per entry | Plant an old tag in `docs/release/fresh-install-smoke.md`: the new test fails, the current suite passes |
| AT-76-2 | Per stop: `scripts/release/launch_pin_check.py` passes, and the release freeze shape test passes with the new shapes recorded | Fails on a stop until the shapes are recorded |
| AT-76-3 | QA BLD-05 and INST-11 at RC | Run at REL-GATE |

Choke point: `lock_version.sh --engine-spec` is the one place the tag is written by intent; AT-76-1
is the guard; the mutation is an old tag in one doc.

### Slices

| Slice | Content | Files | Lines | Risk |
|---|---|---|---|---|
| RD-0 | AT-76-1 | 0 production, 1 test | about 120 | R1 |
| RD-n (one per stop) | Engine: cut the tag (pre-authorized). CLI: one repin PR moving every location | about 15 small edits, of which 2 are code (`rule_codes.py`, `candidate.py`) | under 60 | R1 |
| RD-last | The D-4 launch tag; the repin happens at REL-GATE G2 with version 1.0.0 and the key commit | as RD-n | under 60 | R2 (it is the release head) |

Exception record for RD-n: policy domain "slice size", scope RD-n only, risk R1, rationale: the
repin is a mechanical string change across pin files and each file is one or two lines;
compensating control: AT-76-1; residual risk: none beyond a missed location, which AT-76-1
catches; approver: the orchestrator (an R1 process default, per risk-and-exceptions); follow-up:
none.

### Placement

| Item | Goes in | Map line and neighbor |
|---|---|---|
| Pin-location sentry | `tests/sentry/release/test_engine_pin_locations.py` | Release sentries, beside the release freeze tests |

## 7. Row 78: F10, runtime lock and environment report

### Scope

From the row and MASTER F10:

- Engine: one portable lock envelope, `lock/v1`, that records what masked or generated bytes
  depend on: engine version and compatibility phase, seed protocol, canonical form version, Faker
  version, provider registry digest, pool digests, generator logic version, the pinned dependency
  versions, and the F09 `key_version` label. A synthetic probe that runs fixed inputs and digests
  the result.
- CLI: an environment report that prints the envelope for this host, and a comparison of two or
  more reports that names each difference (the fleet comparison, in file form).

Non-goals for V1: the platform fleet view (platform parked); a run-time refusal when the host
differs from a saved lock (OQ-2); any network fetch of reports.

Locks hold no secrets and no source mappings (MASTER F10). They carry the `key_version` label
only, never the F09 key check value: the check value is derived from the key, and a lock file is
meant to be copied between hosts.

### V1 behavior

- `decoy env report` prints the report for this host. `--json` prints `decoy-env-report/v1`.
  `--out FILE` writes it through the CLI's atomic writer. `--label NAME` sets the host label in
  the file (default `host`). Exit 0.
- `decoy env compare A.json B.json [C.json ...]` reads two or more reports and prints one line per
  differing field, naming the field and the label of each side. Exit 0 when all match, exit 4
  (`EXIT_FINDINGS`) when any field differs, exit 1 on a file that is not a valid report.
- The probe runs inside `decoy env report`; its digest is a report field. If it differs from the
  golden digest the engine ships for its seed protocol, the report says `probe: MISMATCH` and the
  command exits 3.
- `--key-version LABEL` (optional) records the label the project uses. It must full-match the F09
  rule `[A-Za-z0-9._-]{1,64}`; anything else exits 1.

### Engine design

- `decoy_engine.contracts.runtime_lock`:
  - `build_runtime_lock(*, key_version: str | None = None) -> RuntimeLock`
  - `RuntimeLock.to_json()` through the engine's `_canonical` package
  - `compare_runtime_locks(locks: Sequence[RuntimeLock]) -> tuple[LockDifference, ...]`
  - `RuntimeLock` reads `runtime_identity()` for engine, numpy, pandas, pyarrow, python, seed
    protocol and tz, so those keys have one source. Fields added beside it: `compat_phase`
    (`release.py`), `canon`, `faker`, `providers_digest` (over `providers_v2/_registry.py`),
    `pools_digest`, `generator_logic`, `dependencies` (the G12 floor set, read from installed
    metadata), `key_version`, `probe`.
  - The row detail FRAME note says `runtime_identity` should include Faker and the provider and
    pool digests. This plan does not change `runtime_identity`, because that changes the
    fingerprint of every saved pinned plan. The lock carries those keys beside it (OQ-3).
  - One writer model; the reader is derived from it, refuses an unknown major and a missing
    version tag, and treats unknown minor fields as differences (defect class 4).
- `decoy_engine.determinism._probe`: `run_probe() -> str`. A fixed synthetic table (no real data),
  a fixed seed and a fixed test key, run through the deterministic hash path and one pinned
  generator per provider family; returns a SHA-256 hex digest. The golden digest per
  `SEED_PROTOCOL_VERSION` is a constant beside it.

### CLI design

- New sub-package `src/decoy/cli/env/` with `__init__.py` (the Typer group), `_report.py` and
  `_compare.py`. The report adds CLI fields to the engine lock: CLI version, bundle target (from
  `decoy.distribution.targets`) and the native companion self-check result.
- Registered in `src/decoy/__main__.py` beside `doctor` (one line). `doctor` does not change.
- Windows hook: the target field takes whatever `targets.detect_target()` returns; the env package
  has no platform list of its own.

### Design notes

New structure: one engine contract module, one engine probe module, one CLI command group.
Principles: one place per fact (the runtime keys come from `runtime_identity`, digests from
`_canonical`); open/closed is not needed (the field list is fixed by `lock/v1`, a new field is a
minor version). Pattern: lock file plus diffable environment report (section 4).

### Failure modes

- A digest built from an unordered source (dict order, file listing order) differs between two
  identical hosts. Every digest goes through canonical JSON.
- A report carries a path, host name or user name. Hosts are named only by `--label`.
- The probe is slow or does I/O. It must finish in under 2 seconds and touch no file or network.
- A report from a newer CLI has fields an older CLI does not know: compare lists them as
  differences, it does not crash.
- A value derived from key material leaks into the lock.

### Acceptance tests (write first)

| Id | Test | Fails before |
|---|---|---|
| AT-78-E1 | `build_runtime_lock()` in two processes with different `PYTHONHASHSEED` gives equal canonical bytes | Function does not exist |
| AT-78-E2 | Changing the Faker version (patched metadata), the provider registry (one added provider), or `SEED_PROTOCOL_VERSION` each changes exactly the named field in `compare_runtime_locks` | Function does not exist |
| AT-78-E3 | `run_probe()` equals the shipped golden; a mutation in the hash path (one HKDF label byte) changes it | Probe does not exist |
| AT-78-E4 | The lock JSON contains no key, no KCV, no path under `tmp_path` and not `socket.gethostname()` | Lock does not exist |
| AT-78-E5 | `key_version` values `"v1\n"`, `""`, 65 characters, and `"a/b"` raise the engine's typed error with a catalog reason code; `__cause__` and `__context__` are None | Lock does not exist |
| AT-78-E6 | Reader cells: next major refused, missing version tag refused, an extra minor field read as a difference | Lock does not exist |
| AT-78-C1 | `decoy env report --json` validates against `decoy-env-report/v1` and contains the engine lock fields | Command does not exist |
| AT-78-C2 | Two reports that differ in `faker`: `decoy env compare` prints one line naming `faker` and exits 4; identical reports exit 0; a truncated file exits 1 | Command does not exist |
| AT-78-C3 | Probe golden patched to a wrong value: `decoy env report` prints `probe: MISMATCH` and exits 3 | Command does not exist |
| AT-78-C4 | Report and compare output contain no host name and no absolute path | Command does not exist |
| AT-78-C5 | QA INST-18 on two hosts (a Linux VM and the Mac) | Run at QA |

### Slices

| Slice | Repo | Files (production) | Count | Lines | Depends on | Risk |
|---|---|---|---|---|---|---|
| 78-E1 | engine | `contracts/runtime_lock.py`, `contracts/__init__.py`, root `__init__.py` export, the reason catalog entry, a `changelog.d/` fragment | 4 | about 380 | none | R2 (new versioned contract) |
| 78-E2 | engine | `determinism/_probe.py`, `determinism/__init__.py`, `contracts/runtime_lock.py` (wire `probe`) | 3 | about 260 | 78-E1 | R2 |
| 78-C1 | CLI | `cli/env/__init__.py`, `cli/env/_report.py`, `cli/env/_compare.py`, `__main__.py` (one line), the report schema file where the CLI keeps its other JSON schemas | 5 | about 450 | an engine release with E1 and E2 | R2 |

### Placement

| Item | Goes in | Map line and neighbor |
|---|---|---|
| Lock envelope | engine `src/decoy_engine/contracts/runtime_lock.py` | CODEMAP "Versioned contracts"; beside `strategy_requirements.py`; 5 modules there. The engine root is at its fan-out cap |
| Probe | engine `src/decoy_engine/determinism/_probe.py` | Beside `_derive.py`, which holds the seed protocol it guards; 3 modules there |
| Env command | CLI `src/decoy/cli/env/` | `src/decoy/cli` frozen at 29; new command goes in a named sub-package, like `project/` and `setup/` |
| Engine tests | `tests/unit/contracts/`, `tests/unit/determinism/` | Unit tests mirror `src/` |
| CLI tests | `tests/unit/cli/env/`, one e2e in `tests/e2e/` | Mirror `src/` |

## 8. Row 88: F44 CLI half, the remainder

Done: the CycloneDX generators (engine #355, CLI #75, #359), signature checks on install and
upgrade, local rollback before any network call. "Signed bundles" in the row is the release
workflow (row 94 S0); it is owner-gated and not planned here.

Left, in four slices.

### 88-S: SBOM, LICENSE and NOTICE in the bundle

Scope: the SBOM must describe what the bundle ships, and the bundle must carry the license files
(QA INST-13). Today `scripts/release/sbom.sh` reads `requirements-certified.txt`, and
`packaging_tools/build_bundle.py` copies no `LICENSE.md`, `NOTICE` or SBOM into the bundle.

V1 behavior:

- `build_bundle.py` writes `LICENSE.md`, `NOTICE` and `sbom.cdx.json` into the bundle root before
  the manifest is computed, so the signed manifest covers them.
- The SBOM is generated from the bundle's own interpreter (`cyclonedx-py environment` against the
  staged `python/bin/python3`), so it lists what is installed, including `decoy-engine`,
  `decoy-engine-native` and `decoy-cli`. `SOURCE_DATE_EPOCH` is the bundle's fixed mtime, and
  reproducible output is on (section 4).
- Row detail follow-ups, in this slice: `sbom.sh` line 96 `cd` stderr must not name the caller's
  path; the completeness check also checks the root component `version`.

Failure modes: the SBOM tool needs the network on a cold cache (CI has it; an offline build with a
cold cache fails with a clear message, never a partial SBOM). Non-reproducible SBOM fields break
byte-identical bundles.

| Id | Test | Fails before |
|---|---|---|
| AT-88-S1 | A fixture bundle: `LICENSE.md`, `NOTICE`, `sbom.cdx.json` at the root and listed in the manifest | Not copied today |
| AT-88-S2 | The SBOM lists `decoy-cli` at the bundle's version and every distribution in the bundle's site-packages | SBOM reads the requirements file |
| AT-88-S3 | Two builds of the same inputs give identical archive bytes | Green today; must stay green with the SBOM added |
| AT-88-S4 | `sbom.sh` run from a directory whose path holds a marker string: stderr does not contain it | Line 96 prints it |
| AT-88-S5 | A fixture SBOM with a wrong root `version`: the completeness check refuses it | Not checked today |

Files: `packaging_tools/build_bundle.py`, `scripts/release/sbom.sh`, `scripts/release/sbom_checks.py`,
and `docs/release/sbom.md`. 3 production files, about 220 lines. Risk R2 (release artifact
contents). OQ-5 covers the lock-mode refusal text.

### 88-R: rollback compatibility statement

Scope (MASTER F44; platform audit gap "rollback compatibility matrix"): one page that says, for
each thing Decoy writes and keeps, what happens when a user rolls back with
`decoy upgrade --version <older>`.

V1 behavior: `docs/distribution/rollback-compatibility.md`, one row per persisted artifact:
project config, settings, the vault, run checkpoints and resume state, the record library, run
result documents, scan snapshots, and env reports. Each row names the schema id and version
field, what an older runtime does with a newer file (reads it, or refuses with a named reason),
and whether rollback is safe. An upgrade never rewrites project files, so rollback needs no
migration; the page says so and names the test that proves it.

| Id | Test | Fails before |
|---|---|---|
| AT-88-R1 | A doc-truth sentry reads the table and asserts every schema id it names exists in `src/` | Page does not exist |
| AT-88-R2 | `decoy upgrade` to a fixture version and back leaves every file under a fixture project byte-identical (mtimes ignored) | No such test |

Files: the page and one sentry. 0 production files, about 200 lines. Risk R1.

### 88-O: offline signature path for upgrade

Scope: `install.sh` has an offline path (`DECOY_LOCAL_BUNDLE`, lines 251 to 255); `decoy upgrade`
has none. An air-gapped host must be able to upgrade from a bundle file it was handed.

V1 behavior:

- `decoy upgrade --bundle PATH` installs from a local bundle. It needs `PATH.sha256` and
  `PATH.sig` beside it, the same sidecars `install.sh` needs. It copies the bundle into staging,
  then checks the SHA-256 and the Ed25519 signature of the copy with the pinned release key, then
  the bundle's signed manifest, then self-checks and flips `current` exactly like a network
  upgrade. No network call.
- No version document is read, so yank, floor and freshness are not checked. Stderr says:
  `offline bundle: yank and floor checks skipped (no version document)`.
- A bundle older than the current version is refused unless `--version` names that same version
  (explicit rollback). A bundle for another target is refused before extract.
- `--bundle` with `--url` or `--check` exits 1.
- Errors go through the existing `_refuse` path: fixed text, a code, exit 3.

Failure modes: a sidecar missing or for another file; the bundle changing on disk between check
and extract (checked and extracted from the staged copy only); `PATH` a symlink into
`DECOY_HOME`.

| Id | Test | Fails before |
|---|---|---|
| AT-88-O1 | A fixture bundle signed by a test key, key pinned: `decoy upgrade --bundle` installs and `current` flips; a socket guard proves no network call | Option does not exist |
| AT-88-O2 | One flipped byte in the bundle: refused before extract; `versions/` unchanged (INST-03 for upgrade) | Option does not exist |
| AT-88-O3 | Missing `.sig`, then missing `.sha256`: each refused (INST-04 for upgrade) | Option does not exist |
| AT-88-O4 | Signature by a second key: refused with the signature code | Option does not exist |
| AT-88-O5 | Older bundle without `--version`: refused; with `--version <that>`: installs | Option does not exist |
| AT-88-O6 | Original file replaced after the copy (test hook): the staged copy is what installs | Option does not exist |

Files: `src/decoy/distribution/_bundle.py` (local source beside the downloader),
`src/decoy/distribution/installer.py` (an `install_local_bundle` entry on the same core as
`install_version`), `src/decoy/cli/upgrade.py` (the option and the stderr line), `docs/install.md`
(offline section). 3 production files, about 300 lines. Risk R2 (signature path); full suite on
the merge head. Depends on 47-B.

Choke point: both entries share one verify-stage-flip core in `installer.py`; a test asserts
`install_local_bundle` and `install_version` reach the same verify function (mutation: skip the
signature check in the local entry; AT-88-O4 turns red).

### 88-P: upgrade preflight

Scope (MASTER F44: "upgrade preflight consumes the F10 compatibility reports"). Before
`decoy upgrade` flips `current`, compare the staged runtime's environment report with the current
one and tell the user which determinism fields change.

V1 behavior:

- After the staged runtime passes its self-check and before the flip, the upgrade runs the staged
  runtime's report (subprocess of the staged interpreter, `-I -B`) and the current runtime's report
  (in-process), and compares them with the engine compare function.
- If `seed_protocol`, `canon`, `providers_digest`, `pools_digest` or `generator_logic` differ, it
  prints one line per field on stderr: `upgrade changes <field>: outputs for the same seed and key
  will differ from runs made with <old version>`. With `--json`, the list goes in a `preflight`
  field of the result.
- It does not block (OQ-4). Rollback is local and offline.
- `--check` does not run the preflight (it would need the new runtime installed). The help text
  says so.
- If the staged report fails to run, the upgrade refuses before the flip with the existing
  post-swap error code.
- Upgrading from a version with no `decoy env` command (anything before 78-C1): the current-side
  report is built in-process from the running code, so this case does not arise for the running
  CLI; a staged runtime without the command is treated as "report unavailable" and noted on
  stderr, not refused.

| Id | Test | Fails before |
|---|---|---|
| AT-88-P1 | A fixture staged runtime whose report differs in `seed_protocol`: stderr names the field; the flip happens; `--json` has `preflight` with one entry | No preflight |
| AT-88-P2 | Identical reports: no preflight line | No preflight |
| AT-88-P3 | Staged report exits non-zero: refused before the flip; `current` unchanged | No preflight |
| AT-88-P4 | The same through `--bundle` | No preflight |

Files: `src/decoy/distribution/installer.py` (a preflight hook beside `post_swap_validate`),
`src/decoy/cli/upgrade.py`, `src/decoy/cli/env/_report.py` (a function the upgrade can call
in-process). 3 production files, about 220 lines. Risk R2. Depends on 78-C1 and 88-O.

`upgrade.py` is 204 lines; after 88-O and 88-P it should stay under 400. If it would pass 500,
the 88-P builder moves the preflight text into `src/decoy/distribution/_preflight.py`.

### Placement for row 88

| Item | Goes in | Map line and neighbor |
|---|---|---|
| Local bundle source | `src/decoy/distribution/_bundle.py` | Created by 47-B, beside the downloader |
| Preflight hook | `src/decoy/distribution/installer.py` | Beside `post_swap_validate` |
| Upgrade options | `src/decoy/cli/upgrade.py` | Existing command module |
| Rollback page | `docs/distribution/rollback-compatibility.md` | Beside `version-endpoint-contract.md` |
| SBOM in bundle | `packaging_tools/build_bundle.py` | Existing bundle builder |
| Tests | `tests/unit/distribution/`, `tests/e2e/test_upgrade_*.py`, `tests/unit/release/` | Existing test homes |

## 9. Row 90: REL-PKG remainder

Verdict: the MAC-ED25519 plan (`plan/mac-ed25519` `97dbcfb0`) stands. MAC-V1b merged (#281).
MAC-V1a is PR #282 on `feat/mac-v1a`. Action: finish its gate (Codex on the exact head; Dennis
too, since it touches signature code) and merge. No new slice.

Left after MAC-V1a, all owner tasks or row 94:

- The release key pair (owner creates it; the private half goes only into the Environment
  `native-release`).
- The Environment, with a required approver.
- Tag protection for `native-v*` and for the CLI release tags.
- A SHA pin for the qemu action. Engine `native-companion-release.yml` line 119 uses
  `docker/setup-qemu-action@v3`, a tag, not a SHA.
- Row 94 S0 `.github/workflows/release.yml`, including the five PRE-S0 items in the MAC plan.

Windows hook: `targets.py` holds the target list in one place; 88-O refuses a foreign bundle
through `targets.detect_target()`, so a Windows target added by row 89 needs no change here.

## 10. Row 90a: REL-IMAGE, deltas against main

The plan on `plan/rel-image` `d4716855` stands. Changes since its base (CLI `5bb93e66`):

1. Roadmap row 90a says "NOT STARTED; needs a plan". Update to "plan GO (Codex); IMG-1
   buildable".
2. `installer.py:655` (the launcher shim) is now `installer.py:660`. After 47-B it stays in
   `installer.py`.
3. The root callback IMG-1 edits is now `src/decoy/__main__.py:218` (`_root`), with the runtime
   guard at lines 251 to 255. IMG-1 puts its check after the runtime guard and before the update
   notice, as the plan says.
4. The write-scope ratchet assertion is at `tests/sentry/test_ci_lock_installs.py:313`, not 314.
   OQ-5 (raise to 3) was answered yes on 2026-11-15, so IMG-4 may raise it, as a recorded owner
   exception (defect class 11).
5. The guide hint `https://decoy.dev/docs/container` (plan line 352) must use the REL-WEB Q1 host,
   `trydecoy.com`. Derive it from the same constant the version endpoint uses
   (`version_document.DEFAULT_URL`) so one change moves both.
6. Owner answers are in: OQ-1 (a), OQ-2 GHCR under an organization, OQ-3 keyless, OQ-4 slim only,
   OQ-5 yes. The GHCR organization is not created yet; IMG-4 waits on it.
7. IMG-2 needs one published engine native companion release. The workflow exists
   (`native-companion-release.yml`, tags `native-v*`); no `native-v*` tag exists yet. It needs the
   `DECOY_RELEASE_KEY_PEM` secret in the Environment (owner).
8. The engine pin in the Dockerfile `ARG` joins the RD-n pin list (and AT-76-1) when IMG-2
   merges.

Slices unchanged: IMG-1 R2 (now), IMG-2 R2, IMG-3 R1, IMG-4 R2, IMG-5 R2.

## 11. Row 91: REL-WEB remainder

The plan on `plan/rel-web` `53e0e77c` (rev 3) stands. The roadmap calls it "not yet gated": it had
two Dennis rounds and a cross-model review, but no Codex pass. Recommend one Codex pass on its
sections 5.1 to 5.4 before RW-H builds (plan only, R1).

- RW-C2b (CLI): unblocked. `docs/install.md`, `packaging_tools/README.md` and
  `docs/distribution/version-endpoint-contract.md` still name decoy.dev; plus the host-agreement
  sentry. AT-C7. At most 5 files and 200 lines. R1. Build now. 88-O also edits `docs/install.md`;
  RW-C2b goes first.
- RW-H (web): hosting layout, `check-dist.mjs`, deploy guards, freshness workflow. AT-H1 to AT-H6.
  R2 (it publishes signed files).
- RW-D (web): download page. AT-D1 to AT-D4. Under Q1 (a) it needs no extra field. R1. After RW-H.
- RW-P (web): `/proof` page. AT-P1 to AT-P5. R1. After RW-H.

The trydecoy.com domain, DNS and hosting account are owner items (section 12).

## 12. Owner-gated items

None of these blocks a slice in sections 5 to 11 except where the slice says so.

| Item | Blocks | Needed by |
|---|---|---|
| Create the Ed25519 release key; private half into Environment `native-release`; public half for `release_key.pub.pem` | Row 94 S0, IMG-2 (a native release), REL-GATE G2 | 2026-12-01, so S0 runs before G5 |
| Create the Environment `native-release` with a required approver | Same | 2026-12-01 |
| Tag protection for `native-v*` and the CLI release tags | S0 | 2026-12-01 |
| Approve the qemu action SHA pin | S0 | 2026-12-01 |
| Push the first `native-v*` tag (a release, R3) | IMG-2 | after the key |
| Create the GHCR organization | IMG-4 | before G5 |
| trydecoy.com domain, DNS and hosting account (spend) | RW-H deploy, the live version endpoint | before G5 |
| Licensor name and CLA (counsel; REL-GATE Q1, Q2) | INST-13 license check at RC | G7 |
| GA flip (REL-GATE Q3) | G8 | G8 |
| Tart on the Mac mini (MAC plan Q3) | Mac release smoke only | G6 |

## 13. Owner questions, with recommended answers

| Id | Question | Recommended |
|---|---|---|
| OQ-1 | Mark row 46 (H-1 C0) folded into FILE-SIZE C2, with the pure-move checker moved to row 47 slice 47-A? | Yes. |
| OQ-2 | F10 in V1: should `decoy run` refuse when the host differs from a project's saved lock? | No for V1. V1 ships the report and the compare. The CLI has no project lock file today, and adding one is a new feature. |
| OQ-3 | Should engine `runtime_identity()` grow Faker, provider and pool digests before 1.0 (row detail FRAME note)? | No. It would change the fingerprint of every saved pinned plan. The lock carries those keys beside it. Revisit after 1.0. |
| OQ-4 | Should an upgrade that changes seed protocol or generator logic block until the user confirms? | No. Print the change and go on; rollback is local and offline. A block needs a new flag the row does not ask for. |
| OQ-5 | The SBOM lock-mode refusal prints lock package names (row 88 follow-up). Keep? | Keep. Package names are public build metadata, not user data. |
| OQ-6 | DIST-INTEGRITY (row 31) has not started. If it is not built by G0, does it leave the R-d list? | Yes. R-d closes with what merged; row 31 keeps its own row. |
| OQ-7 | `decoy upgrade --bundle` skips yank and floor checks (no version document offline). Accept? | Yes, with the stderr line. Reading a signed version document from beside the bundle can come later if users ask. |
| OQ-8 | QA INST-11 open point: should `decoy --version` also print the engine version? | Yes, one extra line. It is a REL-GATE item, not planned here. |

## 14. Slice summary

| Order | Slice | Row | Repo | Depends on | Risk |
|---|---|---|---|---|---|
| 1 | 47-A pure-move checker | 47 | CLI | none | R1 |
| 1 | RD-0 pin-location sentry | 76 | CLI | none | R1 |
| 1 | RD-n release and repin (daily) | 76 | engine, CLI | merged engine work | R1 |
| 1 | 78-E1 lock envelope | 78 | engine | none | R2 |
| 1 | 88-S SBOM, LICENSE, NOTICE in bundle | 88 | CLI | none | R2 |
| 1 | 88-R rollback statement | 88 | CLI | none | R1 |
| 1 | MAC-V1a finish (#282) | 90 | CLI | none | R2 |
| 1 | IMG-1 image gate | 90a | CLI | none | R2 |
| 1 | RW-C2b docs and host sentry | 91 | CLI | none | R1 |
| 1 | RW-H hosting | 91 | web | Codex pass on the REL-WEB plan | R2 |
| 2 | 78-E2 probe | 78 | engine | 78-E1 | R2 |
| 2 | 47-B installer split | 47 | CLI | 47-A | R2 |
| 2 | RW-D, RW-P | 91 | web | RW-H | R1 |
| 3 | 88-O offline upgrade | 88 | CLI | 47-B, RW-C2b | R2 |
| 3 | 78-C1 env report and compare | 78 | CLI | 78-E1, 78-E2 in a pinned release | R2 |
| 4 | 88-P upgrade preflight | 88 | CLI | 78-C1, 88-O | R2 |
| owner | S0 (row 94), IMG-2 to IMG-5, RD-last | 94, 90a, 76 | both | section 12 | R2 |

## 15. Invariants

- No bundle reaches `versions/` unless its SHA-256 and its Ed25519 signature verify against the
  pinned key, on the network path and the offline path alike.
- `current` changes only by one atomic flip after the staged runtime passes its self-check. A
  refusal at any step leaves `current` and every existing `versions/<v>` folder unchanged.
- No runtime lock, environment report, preflight line or error carries a data value, a key, a key
  check value, a host name or a user path.
- At every repin stop, every engine pin location names the same tag.
- The installer split changes no behavior and no sentry count.

## 16. Class table

Classes from the defect catalog (`docs/handoffs/DEFECT-CATALOG.md`, section 3).

| # | Class | Closing structure | Sentry or test | Mutation that turns it red |
|---|---|---|---|---|
| 1 | Value-bearing output | `_refuse` in `upgrade.py` prints fixed text, a code and the exception type only; env reports carry labels, never host names | AT-78-E4, AT-78-C4, AT-88-S4; a seeded marker in the bundle path and the label must not reach stdout, stderr or `--json` | Make `_refuse` print `str(exc)`; make the report read `socket.gethostname()` |
| 2 | Cleanup missing on an exit path | Staging stays under the install lock and `_sweep_stale_staging`; 88-O copies into the same staging folder | AT-88-O2, AT-88-O3 and AT-88-P3 assert no new folder under `versions/` after each refusal | Skip the staging sweep on the offline refusal path |
| 3 | State machine and concurrency | The single-flight lock in `distribution/lock.py` covers the offline path and the preflight, since both run inside the install critical section | A test that holds the lock and runs `decoy upgrade --bundle`: refused at once | Call the local entry outside `_exclusive(home)` |
| 4 | Route parity and silent fallback | Network and offline upgrade share one verify, stage and flip core | AT-88-O4 and AT-88-P4 run the same checks through `--bundle` | Skip the signature check in `install_local_bundle` |
| 5 | Referential integrity | N/A: no slice reads or writes table data or foreign keys | N/A: no table data in this plan | N/A: no table data in this plan |
| 6 | Untrusted producer | The staged runtime's report is parsed by the strict versioned reader (unknown major refused, size bounded at 64 KiB) and its text is never echoed | AT-78-E6; a staged report of 1 MiB, or with a wrong major, is "report unavailable" | Echo the staged runtime's stderr in the preflight line |
| 7 | Check then use on a path (TOCTOU) | 88-O copies the bundle into staging first, then checks and extracts the copy only | AT-88-O6 | Extract from the original `PATH` after checking the copy |
| 8 | Weak tests and overclaimed evidence | Every acceptance test states its fail-before; RD-0 seeds an old tag | AT-76-1 seeded doc; AT-47-3 lists patch targets | Remove the seeded-case assertion in AT-76-1 |
| 9 | Behavior-preserving refactor drift | 47-B is a pure move with the characterization golden first and re-homed sentry keys | AT-47-1, AT-47-2, AT-47-4 | Rename the staged folder before the self-check (AT-47-2) |
| 10 | Frozen contract drift | New command, flag, schema and `--json` fields are additive and recorded in the frozen-surface map | `tests/sentry/release/test_frozen_surface_map.py`, `tests/unit/test_cli_surface.py`, the release freeze shape test | Add `decoy env` without its `docs/cli-reference.md` and map rows |

## 17. Enumerations

### Exit paths of `decoy upgrade` (the code that owns installed state)

- `src/decoy/cli/upgrade.py:81` and `src/decoy/cli/upgrade.py:87`: usage refusals, exit 1. 88-O
  adds `--bundle` with `--url` or `--check` here.
- `src/decoy/cli/upgrade.py:101`: local activation failed, `_refuse`, exit 3.
- `src/decoy/cli/upgrade.py:103`: local activation done, exit 0.
- `src/decoy/cli/upgrade.py:110`, `:122`, `:127`: endpoint unreachable, document rejected,
  document stale; exit 3. The offline path skips all three.
- `src/decoy/cli/upgrade.py:118`: placeholder key or signature refusal, exit 3.
- `src/decoy/cli/upgrade.py:142` and `:145`: `--check` result and already current, exit 0.
- `src/decoy/cli/upgrade.py:174`: install failed, runtime unchanged, exit 3. The 88-O and 88-P
  refusals end here.
- `src/decoy/cli/upgrade.py:177`: installed, exit 0.
- `src/decoy/distribution/installer.py` raises `InstallError` at 35 sites; all reach
  `src/decoy/cli/upgrade.py:174`.

### Routes

- Network upgrade: `upgrade.py` to `install_version` (`src/decoy/distribution/installer.py:464`).
- Local activation: `activate_local_version` (`src/decoy/distribution/installer.py:398`).
- Offline upgrade (new, 88-O): `install_local_bundle`, on the same core as `install_version`.
- First install: `install.sh` and `src/decoy/distribution/first_install.py`; unchanged here.

### FK shapes

N/A: no slice in this plan touches table data or relationships.

### Fields

- `InstallOutcome` (`src/decoy/distribution/installer.py:115`): `version`, `target`,
  `version_dir`, `previous_version`, `rolled_back`, `rollback_version`. Unchanged; the preflight
  list goes in the upgrade `--json` result, not in this type.
- `RuntimeLock` (new, 78-E1): the `runtime_identity()` keys plus `compat_phase`, `canon`, `faker`,
  `providers_digest`, `pools_digest`, `generator_logic`, `dependencies`, `key_version`, `probe`.
- `decoy-env-report/v1` (new, 78-C1): the lock plus `cli_version`, `target`, `native_selfcheck`,
  `label`.

### Output surfaces

- stdout: `decoy env report`, `decoy env compare`, the `decoy upgrade` result.
- stderr: refusals through `_refuse` (`src/decoy/cli/upgrade.py:180`), the offline skip line, the
  preflight lines, `probe: MISMATCH`.
- `--json`: `decoy-env-report/v1`; the upgrade result's new `preflight` field.
- Files: the report written by `--out`; `LICENSE.md`, `NOTICE` and `sbom.cdx.json` in the bundle.
- Logs: none added. Errors: typed engine errors with catalog reason codes (78-E1).
- Help: `decoy env --help`, `decoy upgrade --help` (the `--bundle` text and the `--check` note).
- Root callback: unchanged by this plan (IMG-1 owns its own edit, section 10).

## 18. Reuse inventory

- Pinned release key, signature and manifest checks: `src/decoy/distribution/signing.py`,
  `manifest.py`, `release_key.py`, `verify_extracted.py`.
- Staging, flip, rollback and the single-flight lock: `installer.py`, `lock.py`, `layout.py`.
- Refusal path: `_refuse` in `upgrade.py`; exit codes in `src/decoy/cli/exit_codes.py`.
- Environment reads: `decoy._env_flags` only (sentry `tests/sentry/io_policy/test_environment_reads.py`).
- Atomic writes: the CLI atomic writer (sentry `tests/sentry/test_atomic_writer.py`).
- Engine: `runtime_identity()`, `_canonical`, the reason catalog, `providers_v2/_registry.py`.
- Size and layout sentries: `tests/sentry/layout/test_module_size.py`, `test_package_fanout.py`.
- Engine pin source: `scripts/dev/lock_version.sh --engine-spec`.
- Release tools: `packaging_tools/build_bundle.py`, `scripts/release/sbom.sh`, `sbom_checks.py`,
  `launch_pin_check.py`.

New machinery and why: the pure-move checker (ported, not new); the lock envelope and the probe
(the row asks for them); the env command (the row asks for it).

## 19. Frozen contracts touched

All additive. Each is recorded in `docs/release/frozen-surfaces.md` before 1.0.0.

- Command and flag set: new `decoy env report`, `decoy env compare`, `decoy upgrade --bundle`.
  Updates `docs/cli-reference.md` and `tests/unit/test_cli_surface.py`.
- `--json` success shapes: `env report`, `env compare`, and the upgrade `preflight` field. Upgrade
  is on the snapshot's exemption list; the env commands get snapshot rows.
- `docs/schemas/`: new `decoy-env-report-v1.schema.json`, which needs its own map row.
- Version document and installer contract: unchanged; the offline path reads no version document.
- Engine: the new `lock/v1` contract, added to the engine's frozen-surface map in 78-E1.
- Exit codes: no new code. `env compare` uses 0, 1 and 4; `env report` uses 0, 1 and 3.

## 20. Pre-mortem

Assume it is 2026-12-04 and the release chain slipped. Likely reasons, with the guard for each:

- The owner key and Environment came late, so S0 and IMG-2 could not run. Guard: the dates in
  section 12 and an early ping. No slice before item 15 needs the key.
- 47-B grew past a pure move (a "while here" fix), review took three rounds, and 88-O waited.
  Guard: AT-47-1 refuses any change that is not a move.
- 78-C1 waited for a release that carried E1 and E2. Guard: RD-n is daily; cut a release the day
  E2 merges.
- The SBOM tool kept a random serial in reproducible mode and broke byte-identical bundles. Guard:
  section 4 tells the 88-S builder to stop and report.
- 88-P's subprocess call to the staged runtime was slow or flaky on the Mac. Guard: a 30-second
  timeout; on timeout the preflight is "report unavailable", never a refusal of a good runtime.
