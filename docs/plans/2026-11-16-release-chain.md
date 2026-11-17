# Release chain: rows 47, 76, 78, 88, 90, 90a and 91

Status: plan

Date: 2026-11-16. Author: Opus planner. Bases: CLI `origin/main` `ba7b613e` (re-checked against `e4c7f387`), engine `origin/main`
`13c95c7de` (#607). Line numbers below are from those heads.

Rules consulted: `dev-rules/00-universal.md`, `dev-rules/risk-and-exceptions.md`,
`dev-rules/development-loop.md`, `dev-rules/release-and-rollback.md`,
`dev-rules/catalogs/recurring-defects.md`, `dev-rules/testing.md` (Test depth),
`dev-rules/workspace-and-vcs.md` (Commit messages), `dev-rules/architecture.md`,
`dev-rules/cross-cutting-concerns.md`, `dev-rules/api-and-compatibility.md`,
`dev-rules/security.md`, `dev-rules/documentation.md`; memories
plan-defines-acceptance-tests, v1-bar-blocking-criteria,
develop-correctly-registries-and-sizing.

This plan covers the release-chain rows that have not started, and the parts of the partly done
rows that have not started. V1 is CLI 1.0.0, with an optional 1.0.0rc.1 first. The Windows chain
(rows 6 and 89) is out of scope; where a slice must leave a hook for it, the slice says so.

It adds no feature beyond the row text. Where a row already has a gated plan, this plan does not
repeat it: it says whether that plan still stands on main and lists what changed.

## 1. Verdicts

| Row | Name | Verdict |
|---|---|---|
| 47 | H-1 C1 installer split | Needs this plan. The H-1 Wave B C1 design stands, with new line numbers and two fixes: the row's path is wrong, and four sentry keys must be re-homed while `_promote_staged` stays put. Build before row 88's code. |
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
2. RD-0, the pin-location rows and check, and the daily RD-n release and repin (engine, CLI).
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
  every new option value; 2 (strict wire and stored types) and 4 (versioned read models) to
  `lock/v1` and `decoy-env-report/v1`; 3 (no exception context) to every new refusal; 11 (no
  raised caps) to every ratchet this plan touches.
- Commit rules: Conventional Commits subject, no body unless it says why, final line `cam`.
- No logging of data values, user project paths, host names or key material.
- File size cap 800 lines. `src/decoy/cli` is frozen at 30 direct modules (CODEMAP on current main); a new command goes in a
  named sub-package (sub-packages do not count toward the parent).

### Plan-record placement

| New file | Directory | Placement basis | Neighbor |
|---|---|---|---|
| `2026-11-16-release-chain-record.md` | `docs/plans/` | Owner-directed companion record beside this executable plan; it has `Status: record` and contains no executable work | `2026-11-16-release-chain.md` |

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
- Pure-move check. The engine has `scripts/check_pure_move.py` and its scope analyzer,
  `scripts/check_pure_move_scope.py` (H-1 Wave A). 47-A ports both and records both as adapted
  `[[mirror]]` entries in `ci/vendored.toml`.
- Pin agreement. The CLI already has one source for the engine spec (`lock_version.sh
  --engine-spec`) and tests that read it. RD-0 extends that registry and test to the remaining locations.

Custom code that remains: the field list of the lock, the probe inputs, and the CLI command
wiring. Each is small and specific to Decoy.

## 5. Row 47: H-1 C1, split `installer.py`

### Scope

Split `src/decoy/distribution/installer.py` (731 lines) into private modules by concern, as a
pure move. The row names `src/decoy/cli/distribution/installer.py`; that path does not exist. The
real file is `src/decoy/distribution/installer.py`. Fix the row text when this slice merges.

No sentry forces the split today (731 is under 800). It is done now because row 88 adds an
offline bundle source and an upgrade preflight to this file, which can put it over the cap.

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
| `src/decoy/distribution/_slots.py` | `_fresh_same_version_slot` 126, `_reclaim_superseded` 161, `_sweep_stale_staging` 175, `_retained_other` 443, `prune_old_versions` 695 (re-exported) | about 150 lines |
| `src/decoy/distribution/_trust.py` | `_read_trust_state` 185, `_trust_state_text` 207, `check_document_freshness` 215 (re-exported) | about 70 lines |
| `src/decoy/distribution/_bundle.py` | `_urllib_download` 247, `_no_bytecode_env` 254, `_run_staged` and `_selfcheck` 265, `_resolve_in_archive` 286, `_extract_bundle` 314, `_try_download_sha` 369, `_bundle_declared_version` 379, `_bundle_declared_target` 451 | about 240 lines |
| `src/decoy/distribution/_errors.py` | `InstallError` 98 (re-exported from `installer.py`) | about 20 lines |
| `src/decoy/distribution/installer.py` (stays) | `install_version` 464, `activate_local_version` 398, `local_version_present` 392, `_promote_staged` 139, `_write_launcher_shim` 660, `_exclusive` 104, `_bundle_url` 94, `_explicit_bundle_base` 89, `resolve_bundle_base`, `DEFAULT_BUNDLE_BASE`, `InstallOutcome` 115 | about 320 lines |

`_promote_staged` (its `os.replace` at `installer.py:152`) and `_write_launcher_shim` (its
`os.replace` at `installer.py:688`) stay in `installer.py`. Moving either adds a second file
to the atomic-writer allowlist, which `tests/sentry/test_atomic_writer.py:218` pins at two files
(defect class 11). With both kept, the atomic-writer entry stays `distribution/installer.py`, 3
sites, unchanged.

`InstallError` moves to `src/decoy/distribution/_errors.py` and `installer.py` re-exports it, so
`installer.InstallError` still works and no new module imports `installer` (no cycle).
`InstallOutcome`, `_exclusive`, `_bundle_url` and `_explicit_bundle_base` stay in `installer.py`.

The moved `_selfcheck` and the later 88-P preflight use one
`_run_staged(python_bin, argv, timeout, max_bytes)` helper in `_bundle.py`. The helper always adds
`-I -B`, uses `_no_bytecode_env()`, applies the timeout and bounds captured output. This is the
one subprocess policy for code that runs from a staged runtime.

Every sentry key on `installer.py`, and what happens to it. The invariant: the total site count per
sentry is unchanged.

| Sentry | Key today | After 47-B |
|---|---|---|
| Atomic writer, `tests/sentry/test_atomic_writer.py:108` and data `tests/sentry/baselines/atomic-writer-allow.json:9` | `distribution/installer.py`, 3 sites | Unchanged (`_promote_staged` and the shim stay) |
| Atomic writer seeded test, `tests/sentry/test_atomic_writer.py:278` | seeds into `distribution/installer.py` | Unchanged |
| Canonical JSON, `tests/sentry/io_policy/test_canonical_json.py:56` and data `tests/sentry/baselines/canonical-json-allow.json:13` | `distribution/installer.py`, 1 site (`_trust_state_text`, `installer.py:212`) | Re-homed to `distribution/_trust.py`, 1 site |
| Private files, `tests/sentry/io_policy/test_private_files.py:101` | `installer.py::_write_launcher_shim::os.chmod::1` | Unchanged |
| Private files, `tests/sentry/io_policy/test_private_files.py:133` | `distribution/installer.py::check_document_freshness::write_atomic::1` | Re-homed to `distribution/_trust.py::check_document_freshness::write_atomic::1` |
| Exception context, `tests/sentry/baselines/exception-context.json:104` | `decoy/distribution/installer.py::check_document_freshness::0` | Re-homed to `decoy/distribution/_trust.py::check_document_freshness::0` |
| File sinks, `tests/sentry/io_policy/file_sinks.toml:250` | `distribution/installer.py`, `_extract_bundle`, `extractall`, ordinal 1 | Re-homed to `distribution/_bundle.py` |

The 47-B builder greps every sentry baseline and allowlist for `installer` before the move and
adds any key this table missed to it, with the same rule.

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
| AT-47-1 | `python scripts/dev/check_pure_move.py --manifest ci/pure-moves/installer-split.json --base origin/main --head HEAD` reports `PURE`. The manifest lists the retained file, each new module, moved-name owners and importers. The checker refuses an edited statement, an unlisted importer and a changed definition scope | The checker, scope analyzer and manifest do not exist in the CLI |
| AT-47-2 | `tests/unit/test_installer_characterization.py::test_install_version_layout_golden` (from H-1 Wave B) passes unchanged before and after the split. Mutation: rename the staged folder before the self-check; the test must fail | The golden test does not exist on main |
| AT-47-3 | A test lists every `monkeypatch.setattr(installer, "<name>")` and `mock.patch("decoy.distribution.installer.<name>")` in `tests/`, and asserts each name is still looked up through `installer` at run time, or the patch target names the new module | No such test; after a move the patch is a no-op |
| AT-47-4 | For every row of the sentry key table above: the total sites per sentry are unchanged, each re-homed key matches its new path, and a test proves the old key no longer matches (owner re-home rule, 2026-11-15). `test_atomic_writer.py:218` still asserts two files | The four re-homed keys point at code that moves; without the re-home each sentry goes red on the split |
| AT-47-5 | `import decoy.distribution.installer as i` then `i.install_version`, `i.check_document_freshness`, `i.prune_old_versions`, `i.activate_local_version` in a clean venv | Guard: green before, must stay green |
| AT-47-6 | QA INST-17: INST-01 to INST-06 and INST-14 give the same result on the split build | Run at QA |

### Slices

| Slice | Files (production) | Lines | Tests | Risk |
|---|---|---|---|---|
| 47-A | `scripts/dev/check_pure_move.py` and `scripts/dev/check_pure_move_scope.py` (ported from engine at 249 and 214 lines, adapted to CLI paths), plus one `[[mirror]]` row for each in `ci/vendored.toml` | 2 files, about 460 | ported unit tests and fixtures cover a pure move, one edited line, an unlisted importer and scope drift | R1 |
| 47-B | `installer.py`, `_slots.py`, `_trust.py`, `_bundle.py`, `_errors.py`, `ci/pure-moves/installer-split.json`, the sentry data for the four re-homed keys; test patch targets updated in `test_distribution.py`, `test_distribution_r7_security.py`, `test_distribution_acceptance.py`, `tests/unit/distribution/test_bundle_base.py`, `test_atomic_callers.py`, `test_release_smoke_workflow.py`, `tests/e2e/test_upgrade_error_text.py` | 5 production files, about 750 moved lines | Author the move manifest, then run AT-47-1 to AT-47-5; full suite on the merge head | R2 |

The characterization golden (AT-47-2) lands as 47-B's first commit, before any move, so the gate
sees it pass on the unsplit file.

### Placement

| Item | Goes in | Map line and neighbor |
|---|---|---|
| `_slots.py`, `_trust.py`, `_bundle.py`, `_errors.py` | `src/decoy/distribution/` | Private modules beside their owner, as `layout_point.py` and `verify_extracted.py` sit today. 13 direct modules now, 17 after, under the 25 cap |
| `check_pure_move.py`, `check_pure_move_scope.py` | `scripts/dev/` | Dev tooling, beside `ratchet_check.py`; 5 Python modules there before this slice |
| Installer move manifest | `ci/pure-moves/installer-split.json` | Add a CODEMAP row for pure-move manifests under `ci/`, beside the existing CI registries |
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
| AT-76-1 | The existing sentry `tests/sentry/test_ci_lock_installs.py:277` (`test_lock_profile_lives_in_lock_version_and_the_policy`, which `scripts/release/launch_pin_check.py` already runs) also reads new `[[engine_pin]]` rows in `ci/install-policy.toml`. It asserts that every pattern matches exactly once and that its captured version equals the `--engine-spec` tag. The `policy_findings()` reason loop in `tests/sentry/_ci_lock_scan.py:329` includes `engine_pin`. A seeded missing reason, zero-match pattern, two-match pattern and old tag each fail | Plant an old tag in the current-pin sentence of `docs/release/fresh-install-smoke.md`: the extended test fails, today's suite passes |
| AT-76-2 | Per stop: `scripts/release/launch_pin_check.py` passes, and the release freeze shape test passes with the new shapes recorded | Fails on a stop until the shapes are recorded |
| AT-76-3 | QA BLD-05 and INST-11 at RC | Run at REL-GATE |

Registry: no second pin list. `ci/install-policy.toml` is already the one registry for engine
spec sites (`[[engine_site]]`, lines 33 to 46). Those rows name workflow steps, so the doc and code
pins go in a sibling `[[engine_pin]]` table in the same file, one row per location: `file`, an
exact `pattern` with one capture group for the version, and a `reason`. Patterns match the
current-pin phrase only, so history literals stay out: `LICENSING.md:6`, `README.md:210` and
`docs/guides/shape-and-privacy/README.md:10` name 0.22.0, 0.23.0 and 0.19.0 as history, and only
their "pins today" phrase is a row. `CHANGELOG.md` has no row. The lock file's hash pins stay with
`scripts/dev/lock.sh --check`, not this sentry.

Choke point: `lock_version.sh --engine-spec` is the one place the tag is written by intent; AT-76-1
is the guard; the mutation is an old tag in one doc.

### Slices

| Slice | Content | Files | Lines | Risk |
|---|---|---|---|---|
| RD-0 | AT-76-1: `[[engine_pin]]` rows in `ci/install-policy.toml` and the extended test | 1 registry file, 1 test | about 120 | R1 |
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
| Pin rows | `ci/install-policy.toml`, `[[engine_pin]]` beside `[[engine_site]]` | CODEMAP: CI registries in `ci/`; the existing engine-spec registry |
| Pin check | `tests/sentry/test_ci_lock_installs.py`, extending the test at line 277 | The sentry that already owns the engine spec |

## 7. Row 78: F10, runtime lock and environment report

78-E1 merged (engine #618). The executable plan for 78-E2 and 78-C1 is now the engine plan
`E:plan/f10-lock-envelope` (`docs/plans/2026-11-17-f10-lock-envelope.md`, revision 3), which
replaces the rest of this section where they differ.

### Scope

From the row and MASTER F10:

- Engine: one portable lock envelope, `lock/v1`, that records what masked or generated bytes
  depend on, and a synthetic probe that runs fixed inputs and digests the result.
- CLI: an environment report that prints the envelope for this host, and a comparison of two or
  more reports that names each difference (the fleet comparison, in file form).

Non-goals for V1: the platform fleet view (platform parked); a run-time refusal when the host
differs from a saved lock (OQ-2); any network fetch of reports.

Locks hold no secrets and no source mappings (MASTER F10). They carry the `key_version` label
only, never the F09 key check value: the check value is derived from the key, and a lock file is
meant to be copied between hosts.

### Lock fields and the source of each

Each field has one engine source. A field with no source in the engine today is left out rather
than invented.

| Field | Source |
|---|---|
| `engine`, `numpy`, `pandas`, `pyarrow`, `python`, `seed_protocol`, `tz` | `runtime_identity()`, `generation/_pinned_plan.py:163` (seed protocol from `determinism/_derive.py:135`) |
| `compat_phase` | `RELEASE_PHASE` in `src/decoy_engine/release.py` |
| `faker` | installed `faker` distribution metadata |
| `providers_digest` | SHA-256 of the canonical JSON of the default provider registry's content (`providers_v2/_registry.py:146`, `get_default_registry()`): each provider's name, kind and backing library version, sorted. Not file bytes |
| `data_digest` | SHA-256 over canonical JSON of sorted `(relative path, sha256)` pairs for shipped data under `codesets/*.parquet`, `reference_tables/data/*.parquet` and `generation/composite/data/us_localities.csv`. Paths use package-relative POSIX spelling; the digest covers file bytes |
| `dependencies` | installed versions of the G12 floor set, read from distribution metadata |
| `key_version` | optional label from the caller |
| `probe` | `run_probe()` digest (78-E2) |

The engine ships pool and reference data. The `data_digest` covers the four files under
`codesets/`, every parquet file under `reference_tables/data/`, and
`generation/composite/data/us_localities.csv`. Resource discovery supplies the file set, so the
implementation has no second hand-written data-file list.

OQ-9 is decided: V1 drops `canon` and `generator_logic`. The engine has no canonical-form or
generator-logic version constant today. The version-invariant probe covers both executable paths,
and `engine` records the release.

Drift guard: AT-78-E2 changes each source and asserts exactly the named field changes, so a source
that stops feeding its field turns the test red.

### V1 behavior

- `decoy env report` prints the report for this host. `--json` prints `decoy-env-report/v1`.
  `--out FILE` writes it through the CLI's atomic writer. `--label NAME` sets the host label
  (default `host`); it must full-match `[A-Za-z0-9][A-Za-z0-9._-]{0,31}` (defect class 1), else
  exit 1. Exit 0 when the probe matches.
- `decoy env compare A.json B.json [C.json ...]` reads two or more reports and prints one line per
  differing field, naming the field and the label of each side. Exit 0 when all match, exit 4
  (`EXIT_FINDINGS`) when any field differs, exit 1 on a file that is not a valid report.
- The probe runs inside `decoy env report`; its digest and `probe_status` are report fields.
  `probe_status` is `ok` or `mismatch`. `--json` always prints the complete report. A mismatch
  prints `probe: MISMATCH` in human mode and exits 3 after writing the report in either mode.
- `--key-version LABEL` (optional) records the label the project uses. It is checked by the
  engine's one exported key-version label rule (below); anything else exits 1.
- `native_selfcheck` in the report carries only the companion's `present`, `ok` and `reason`
  code, taken from the CLI's existing safe reader `_companion_report()` (`src/decoy/cli/info.py:72`).
  It never carries `SelfCheckResult.detail` (`src/decoy/distribution/selfcheck.py:32`), which holds
  exception text and can name a path under the home directory.

### Key-version label rule

The engine already has one label pattern: `_LABEL_PATTERN` at
`src/decoy_engine/delivery/resume/_records.py:102`, `[A-Za-z0-9][A-Za-z0-9._:+!-]{0,63}`, used with
`fullmatch`. 78-E1 moves the private pattern and `is_key_version_label()` to
`src/decoy_engine/keyprovider.py` (import tier 3), the owner of `KeyProvider.key_version`.
`delivery/resume/_records.py` and the runtime lock import the function from there. The engine root
exports only `is_key_version_label` through `decoy_engine.__all__`; the CLI imports that public
name and holds no copy of the pattern. `docs/frozen-surfaces.md` adds it to one Public names row,
and `tests/sentry/release/test_frozen_surface_map.py` proves that the name appears exactly once.

### Engine design

- `src/decoy_engine/support/_runtime_lock.py`: `build_runtime_lock(*, key_version=None)`,
  `RuntimeLock` with `to_json()` through `_canonical`, and
  `compare_runtime_locks(locks) -> tuple[LockDifference, ...]`. One writer model; the reader is
  derived from it. The `lock/v1` reader refuses an unknown major or missing tag and ignores added
  fields, matching the existing `RunResultRead` rule for additive fields (defect class 4).
- `src/decoy_engine/support/_probe.py`: `run_probe() -> str`. Its module contract says the golden
  uses version-invariant code only: the HKDF/HMAC hash path, FF1 and seeded draws from the pinned
  Faker. It does not use NumPy or pandas distribution draws. Fixed inputs, a fixed seed and a fixed
  test key produce one SHA-256 digest. The golden per `SEED_PROTOCOL_VERSION` is a constant beside
  it.
- Both are exported from `decoy_engine.support` and the root `__init__.py`.
- 78-E1 adds `lock/v1` to the compatibility-contract 3.1 tag block and the Format tags table in
  `docs/frozen-surfaces.md`. `test_every_contract_tag_has_a_row` enforces the pair. It also adds a
  hand-written `tests/integration/compat_corpus/runtime-lock/lock-v1.json` sample and a corpus
  reader cell. The written compatibility rule permits additive fields and requires older readers
  to ignore them.
- The row detail FRAME note proposes that `runtime_identity` include Faker and the provider and
  pool digests. This plan does not change `runtime_identity`, because that changes the
  fingerprint of every saved pinned plan (OQ-3, decided). The lock carries those keys beside it.

Why `support/`: the engine import layers (`.importlinter`, exhaustive) put `contracts` and
`determinism` in tier 4, below `generation`, `providers_v2` (tier 3) and `execution` (tier 2). The
lock reads `generation` and `providers_v2`; the probe runs generators and the masking hash path in
`execution`. Both must sit in tier 1, the top tier. `support` is a tier 1 package, its job is
support bundles that describe a run's environment with no values (F32), and it has 2 modules.
Both modules import the label rule from `keyprovider` in tier 3. No new top-level package (the
engine root is at its fan-out cap) and no new ignore line.

### CLI design

- New sub-package `src/decoy/cli/env/` with `__init__.py` (the Typer group), `_report.py` and
  `_compare.py`. The report adds CLI fields to the engine lock: CLI version, bundle target (from
  `decoy.distribution.targets`) and the companion fields above.
- Registered in `src/decoy/__main__.py` beside `doctor` (one line). `doctor` does not change.
- 78-C1 adds a CLI CODEMAP "Where Things Go" row for `src/decoy/cli/env/`, so
  `tests/sentry/layout/test_package_fanout.py` does not list it as an unmapped sub-package.
- 78-C1 updates QA INST-18 (`docs/qa/cli-v1-checklist.md:168`) to require `data_digest`, the
  other lock fields and `probe_status`, plus a two-host comparison that names each differing
  field. It no longer refers to a generic pool digest.
- Windows hook: the target field takes whatever `targets.detect_target()` returns; the env package
  has no platform list of its own.

### Design notes

New structure: two engine modules in an existing package, one CLI command group. Principles: one
place per fact (runtime keys from `runtime_identity`, digests from `_canonical`, the label rule
from `keyprovider`). Pattern: lock file plus diffable environment report (section 4).

### Failure modes

- A digest built from an unordered source (dict order, file listing order) differs between two
  identical hosts. Every digest goes through canonical JSON.
- A report carries a path, host name or user name. Hosts are named only by `--label`; the companion
  fields carry a reason code, never detail text.
- The probe is slow or does I/O. It must finish in under 2 seconds and touch no file or network.
- A lock from a newer engine has added fields an older reader does not know: the reader ignores
  them under `lock/v1`, matching the compatibility contract.
- A value derived from key material leaks into the lock.

### Acceptance tests (write first)

| Id | Test | Fails before |
|---|---|---|
| AT-78-E1 | `build_runtime_lock()` in two processes with different `PYTHONHASHSEED` gives equal canonical bytes | Function does not exist |
| AT-78-E2 | Changing the Faker version (patched metadata), the provider registry (one added provider), `SEED_PROTOCOL_VERSION`, `RELEASE_PHASE`, and one byte from a stubbed shipped-data resource changes exactly the named field in `compare_runtime_locks`. These field-isolation cells stub `run_probe()` to a constant; a separate integration cell expects both `seed_protocol` and `probe` when the real probe changes with the protocol | Function does not exist |
| AT-78-E3 | `run_probe()` equals the shipped golden; mutations in one HKDF/HMAC label byte, the FF1 path and one seeded Faker draw each change it. The focused golden assertion runs in every `fingerprint-matrix` cell in `.github/workflows/dps-dependency-matrix.yml`, with no NumPy or pandas distribution draw | Probe does not exist |
| AT-78-E4 | With a configured key seeded for the test: the lock JSON does not contain that key, `build_fingerprint(...).key_check` (`delivery/resume/_fingerprint.py:96-103`), any path under `tmp_path`, or `socket.gethostname()` | Lock does not exist |
| AT-78-E5 | `key_version` values `"v1\n"`, `""`, 65 characters, and `"a/b"` raise the engine's typed error with a catalog reason code; `__cause__` and `__context__` are None; `_records.py` and the lock use the same public check (mutating the private pattern in `keyprovider.py` turns both red) | Lock does not exist; the pattern is private in `_records.py` |
| AT-78-E6 | Writer and reader strict-type matrix for `lock/v1`: every integer field refuses `True`, a numeric string and a non-integer scalar; every scalar field refuses a list or object; `dependencies` refuses a scalar, list, non-string key, non-string version and nested value. Run each mutation through model construction/write and JSON read. Reader compatibility cells also refuse the next major and a missing version tag, ignore an added field under `lock/v1`, and read the hand-written corpus sample. Named mutations: coerce `str` to `int`, accept `True` as `1`, stringify dependency values and accept a list in place of the dependency object | Lock does not exist |
| AT-78-E7 | The import-layer sentry (`tests/sentry/layout/test_import_layers.py`) passes with no new ignore line | Guard: green before, must stay green |
| AT-78-C1 | `decoy env report --json` validates against `decoy-env-report/v1` and contains the engine lock fields | Command does not exist |
| AT-78-C2 | Two reports that differ in `faker`: `decoy env compare` prints one line naming `faker` and exits 4; identical reports exit 0; a truncated file exits 1 | Command does not exist |
| AT-78-C3 | Probe golden patched to a wrong value: human mode prints `probe: MISMATCH`; `--json` prints the complete report with `probe_status: "mismatch"`; both exit 3 | Command does not exist |
| AT-78-C4 | Report and compare output contain no host name and no absolute path | Command does not exist |
| AT-78-C5 | A patched `native_companion_status()` returns a seeded path marker in both `cause` and `abi_actual`: the report shows `ok: false` and a reason code, omits both unsafe fields, and the marker is absent from stdout, stderr and `--json` | Command does not exist |
| AT-78-C6 | `--label` values `"a\n"`, `""`, 33 characters and `"a b"` exit 1 | Command does not exist |
| AT-78-C7 | QA INST-18 on two hosts (a Linux VM and the Mac) | Run at QA |
| AT-78-C8 | Writer and CLI report-reader strict-type matrix for `decoy-env-report/v1`: apply the AT-78-E6 primitive and `dependencies` mutations on write and read; also refuse wrong scalar or container types for `cli_version`, `target`, `native_selfcheck`, `label` and `probe_status`, booleans or numeric strings in integer fields, malformed `native_selfcheck` members (`present` and `ok` each refuse `0`, `1`, `"true"`, `null` and a list on write and on read), and every `probe_status` token except `ok` and `mismatch`. Named mutations: coerce a numeric string, accept `True` as `1`, stringify a dependency value, accept a list for an object, coerce an integer to a boolean in `native_selfcheck.present` or `native_selfcheck.ok`, and treat unknown `probe_status` as free text | Command and strict report reader do not exist |

### Slices

| Slice | Repo | Files (production) | Count | Lines | Depends on | Risk |
|---|---|---|---|---|---|---|
| 78-E1 | engine | `support/_runtime_lock.py`, `support/__init__.py`, root `__init__.py` export, `keyprovider.py`, `delivery/resume/_records.py`, the reason catalog entry, a `changelog.d/` fragment | 6 | about 450 | none | R2 (new versioned contract) |
| 78-E2 | engine | `support/_probe.py`, `support/__init__.py`, `support/_runtime_lock.py` (wire `probe`), dependency-matrix workflow | 3 | about 300 | 78-E1 | R2 |
| 78-C1 | CLI | `cli/env/__init__.py`, `cli/env/_report.py`, `cli/env/_compare.py`, `__main__.py` (one line), `docs/schemas/decoy-env-report-v1.schema.json` with its row in `docs/release/frozen-surfaces.md`, the CODEMAP row, and QA INST-18 | 5 | about 450 | an engine release with E1 and E2 | R2 |

### Placement

| Item | Goes in | Map line and neighbor |
|---|---|---|
| Lock envelope | engine `src/decoy_engine/support/_runtime_lock.py` | CODEMAP "Support bundles" (`src/decoy_engine/support/_<concern>.py`); import tier 1, beside `_shape.py`; 2 modules there, 4 after |
| Probe | engine `src/decoy_engine/support/_probe.py` | Same row; tier 1 because it runs tier 2 and tier 3 code |
| Label rule | engine `src/decoy_engine/keyprovider.py` | Existing owner of `KeyProvider.key_version`; import tier 3, read by `delivery.resume` and `support` |
| Lock corpus sample | engine `tests/integration/compat_corpus/runtime-lock/lock-v1.json` | Existing compatibility corpus; hand-written sample read by its harness |
| Env command | CLI `src/decoy/cli/env/` | `src/decoy/cli` frozen at 30; new command goes in a named sub-package, like `project/` and `setup/`; new CODEMAP row |
| Engine tests | `tests/unit/support/` | CODEMAP "Support bundles" tests |
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

- The SBOM is generated from the bundle's own interpreter (`cyclonedx-py environment` against the
  staged `python/bin/python3`), so it lists what is installed, including `decoy-engine`,
  `decoy-engine-native` and `decoy-cli`. `SOURCE_DATE_EPOCH` is the bundle's fixed mtime, and
  reproducible output is on (section 4).
- Step order in `build_bundle.py` (today lines 208 to 216): `_install_wheels`,
  `_normalize_bin_shebangs`, then the new SBOM step, then `_strip_pycache`, `_write_launcher`, the
  new copy of `LICENSE.md` and `NOTICE`, `_write_bundle_info`, and last `compute_manifest`. The SBOM
  step runs the staged interpreter, which may write bytecode, so it runs with
  `PYTHONDONTWRITEBYTECODE=1` and before `_strip_pycache`, which removes anything left. All three
  new files exist before the manifest is computed, so the signed manifest covers them.
- Row detail follow-ups, in this slice: a `cd` in `sbom.sh` must not print the caller's path on
  stderr. The row detail cited line 96; on main the `cd` calls are at `scripts/release/sbom.sh:52`
  and `:53` (stdout to `/dev/null`, stderr not). The builder confirms which `cd` the follow-up
  meant and fixes every `cd` that can print a path. The completeness check also checks the root
  component `version`.

Failure modes: the SBOM tool needs the network on a cold cache (CI has it; an offline build with a
cold cache fails with a clear message, never a partial SBOM). Non-reproducible SBOM fields break
byte-identical bundles. A bytecode cache written by the SBOM run lands in the bundle unsigned.

| Id | Test | Fails before |
|---|---|---|
| AT-88-S1 | A fixture bundle: `LICENSE.md`, `NOTICE`, `sbom.cdx.json` at the root and listed in the manifest | Not copied today |
| AT-88-S2 | The SBOM lists `decoy-cli` at the bundle's version and every distribution in the bundle's site-packages | SBOM reads the requirements file |
| AT-88-S3 | Two builds of the same inputs give identical archive bytes | Green today; must stay green with the SBOM added |
| AT-88-S4 | `sbom.sh` run from a directory whose path holds a marker string, with that directory made unreadable for the `cd`: stderr does not contain the marker | The `cd` error names the path |
| AT-88-S5 | A fixture SBOM with a wrong root `version`: the completeness check refuses it | Not checked today |
| AT-88-S6 | The built bundle holds no `__pycache__` folder and no `.pyc` file | Guard: green before; turns red if the SBOM step moves after `_strip_pycache` |

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
| AT-88-R2 | `decoy upgrade` to a fixture version and back leaves every file under a fixture project byte-identical (mtimes ignored) | No fail-before: this is a guard that pins the claim the page makes. Non-vacuity: a seeded write to the project during the fixture upgrade turns it red |

Files: the page and one sentry. 0 production files, about 200 lines. Risk R1.

### 88-O: offline signature path for upgrade

Scope: `install.sh` has an offline path (`DECOY_LOCAL_BUNDLE`,
`packaging_tools/install/install.sh:251-255`); `decoy upgrade` has none. An air-gapped host must
be able to upgrade from a bundle file it was handed.

V1 behavior:

- `decoy upgrade --bundle PATH` installs from a local bundle. It needs `PATH.sha256` and
  `PATH.sig` beside it, the same sidecars `install.sh` needs. It reads the bundle into memory once,
  then verifies the SHA-256 and Ed25519 signature of those bytes with the pinned release key. It
  quarantine-extracts the verified bytes into a random-token `.incoming.*` folder and verifies the
  signed manifest with the existing extractor and verifier. It then reads the declared version and
  target from the extracted `BUNDLE_INFO`, before `_selfcheck` and before `_promote_staged`. This
  matches the network order at `installer.py:545-575` and adds no second tar-member parser. No
  network call occurs.
- Where the branch sits in `upgrade.py`: after the pinned-key check (`src/decoy/cli/upgrade.py:83`
  to `:87`) and before the local-activation branch (`:98`). So `--bundle` always installs from the
  file; local activation never runs for it, even when `--version` names a retained version.
- With `--bundle`, `--version` has one meaning: it confirms a downgrade. A bundle whose declared
  version is lower than the current one is refused unless `--version` equals that declared
  version. A `--version` that differs from the declared version is refused. Both refusals come
  after quarantine extract and manifest verification, before self-check, through `_refuse`
  (exit 3).
- A bundle whose declared target differs from this host is refused after quarantine extract and
  manifest verification, before self-check.
- A bundle that declares the current version is verified and then reports no action unless
  `--force` is present. With `--force`, it reinstalls from the local bytes. A retained non-current
  version still installs from the bundle; it never takes the local-activation shortcut.
- No version document is read, so yank, floor and freshness are not checked. Stderr says:
  `offline bundle: yank and floor checks skipped (no version document)`. With `--json`, the result
  carries `checks_skipped: ["yank", "floor"]` (OQ-7).
- `--bundle` with `--url` or `--check` exits 1.

Shared core: the declared-version and declared-target checks, staging, self-check and flip move
into one core that both `install_version` and the new `install_local_bundle` call. That is a
refactor of `install_version` steps 3 to 7 (`src/decoy/distribution/installer.py:464-658`), so the
network path changes shape. The characterization golden from 47-B (AT-47-2) must pass unchanged
on the network path before and after. The core passes the verified declared version to the CLI
`_post_swap` validator; it does not close over `target_version`, which is `None` on `--bundle`.

Failure modes: a sidecar missing or for another file; the bundle changing on disk after its one
bounded read (the in-memory bytes are verified and extracted); `PATH` a symlink into `DECOY_HOME`;
a renamed file that claims a newer version than it holds.

The local reader adds no file sink and no atomic-writer site. It supplies bytes to the existing
extractor, while `_promote_staged` remains the only runtime promotion site.

The refusal tests compare retained version folders before and after. They exclude `.incoming*`
from that comparison because the staging folder has a random token, then separately assert that
cleanup leaves no `.incoming*` folder.

| Id | Test | Fails before |
|---|---|---|
| AT-88-O1 | A fixture bundle signed by a test key, key pinned: `decoy upgrade --bundle` installs and `current` flips; a socket guard proves no network call; `--json` has `checks_skipped` | Option does not exist |
| AT-88-O2 | One flipped byte in the bundle: refused before extract; existing version folders are unchanged and no `.incoming.*` folder remains (INST-03 for upgrade) | Option does not exist |
| AT-88-O3 | Missing `.sig`, then missing `.sha256`: each refused, with no residual `.incoming*` staging directory (INST-04 for upgrade) | Option does not exist |
| AT-88-O4 | Signature by a second key: refused with the signature code | Option does not exist |
| AT-88-O5 | Older bundle without `--version`: refused; with `--version <its declared version>`: installs; with a different `--version`: refused. Each refusal leaves existing version folders unchanged and no `.incoming.*` folder remains | Option does not exist |
| AT-88-O6 | Original file replaced after the one bounded in-memory read (test hook): the already verified in-memory bytes are what install; there is no staged file copy to substitute | Option does not exist |
| AT-88-O7 | A validly signed older bundle renamed to a newer version's file name, sidecars renamed with it: refused as a downgrade without `--version`, with no residual `.incoming*` staging directory | Option does not exist |
| AT-88-O8 | `--bundle` with `--version` naming a version that is retained on disk: the bundle installs; `activate_local_version` is not called | Option does not exist |
| AT-88-O9 | AT-47-2 golden passes on the network path after the shared-core refactor | Guard from 47-B |
| AT-88-O10 | A bundle with the current declared version reports no action without `--force`; with `--force` it reinstalls. The post-swap validator receives that declared version and accepts the launched version | Option does not exist |

Files: `src/decoy/distribution/_bundle.py` (local source beside the downloader),
`src/decoy/distribution/installer.py` (the shared core and `install_local_bundle`),
`src/decoy/cli/upgrade.py` (the option, the branch, the stderr line, `checks_skipped`),
`docs/install.md` (offline section). 3 production files, about 350 lines. Risk R2 (signature path
and a refactor of the network path); full suite on the merge head. Depends on 47-B and RW-C2b.

Choke point: both entries share one verify, stage and flip core in `installer.py`; a test asserts
both reach the same verify function. The offline source only supplies already-read bytes and
sidecars. Mutation: skip the signature check in the local entry; AT-88-O4 turns red.

V2-LOG: read a signed version document placed beside the bundle, so offline upgrades can check
yank and floor too.

### 88-P: upgrade preflight

Scope (MASTER F44: "upgrade preflight consumes the F10 compatibility reports"). Before
`decoy upgrade` flips `current`, compare the staged runtime's environment report with the current
one and tell the user which determinism fields change. The preflight informs; it never refuses.
The existing self-check already gates whether the staged runtime is healthy.

V1 behavior:

- After the staged runtime passes its self-check and before the flip, the upgrade runs the staged
  runtime's report as a subprocess (`python -I -B -m decoy --no-update-check env report --json`,
  30-second timeout, output read up to 64 KiB) through
  `_run_staged(python_bin, argv, timeout, max_bytes)`. `_selfcheck` uses the same helper, including
  `-I -B` and `_no_bytecode_env()`. The preflight builds the current report in-process, then
  compares both reports with the engine compare function.
- Fields compared: every lock field except `key_version` (not set during an upgrade). That is
  `engine`, `numpy`, `pandas`, `pyarrow`, `python`, `seed_protocol`, `tz`, `compat_phase`, `faker`,
  `providers_digest`, `data_digest`, `dependencies` and `probe`. For each that differs it prints
  one value-free line on stderr: `upgrade changes <field>: outputs for the same seed and key may
  differ`. With `--json`, the list goes in a `preflight` field of the result.
- Exit 0 and exit 3 are accepted when stdout is a valid report. Exit 3 with
  `probe_status: "mismatch"` prints `upgrade changes probe: outputs for the same seed and key may
  differ` and the upgrade continues.
- Any other non-zero exit, timeout, more than 64 KiB, unparsable report, unknown major version, or
  staged runtime with no `env` command gives one stderr line,
  `upgrade preflight: report unavailable`, and `preflight: null` in `--json`. The upgrade goes on
  and flips. The staged runtime's own output is never echoed.
- It never blocks (OQ-4). Rollback is local and offline.
- `--check` does not run the preflight (it needs the new runtime installed). The help text
  says so.

V2-LOG: local-activation rollback (`activate_local_version`, `src/decoy/distribution/installer.py:398`)
gets no preflight.

| Id | Test | Fails before |
|---|---|---|
| AT-88-P1 | A fixture staged runtime whose report differs in `seed_protocol` and `faker`: stderr names both fields; the flip happens; `--json` has `preflight` with two entries | No preflight |
| AT-88-P2 | Identical reports: no preflight line | No preflight |
| AT-88-P3 | A staged runtime with no `env` command: the upgrade flips; stderr has `upgrade preflight: report unavailable`; `--json` has `preflight: null` | No preflight |
| AT-88-P4 | The same as P1 through `--bundle` | No preflight |
| AT-88-P5 | A staged report of 1 MiB, one with an unknown major, and one that sleeps past the timeout: each is "report unavailable" and the flip happens; a seeded marker in the staged runtime's stderr does not reach the user | No preflight |
| AT-88-P6 | `_selfcheck` and the preflight both call `_run_staged`; each subprocess argument list contains `-I -B`, the preflight list contains `--no-update-check`, and both receive `_no_bytecode_env()` | No shared staged-runtime helper |
| AT-88-P7 | The staged report writes valid JSON with `probe_status: "mismatch"` and exits 3: stderr says `upgrade changes probe ...`, the flip happens, and `--json` records `probe` in `preflight` | No preflight |

Files: `src/decoy/distribution/installer.py` (a preflight hook beside `post_swap_validate`),
`src/decoy/cli/upgrade.py`, `src/decoy/cli/env/_report.py` (a function the upgrade can call
in-process). 3 production files, about 240 lines. Risk R2. Depends on 78-C1 and 88-O.

`upgrade.py` is 204 lines; its estimated finished size after 88-O and 88-P is under 400 lines, and
the finished file must stay under the 800-line cap.

### Placement for row 88

| Item | Goes in | Map line and neighbor |
|---|---|---|
| Local bundle source | `src/decoy/distribution/_bundle.py` | Created by 47-B, beside the downloader |
| Shared install core, preflight hook | `src/decoy/distribution/installer.py` | Beside `install_version` and `post_swap_validate` |
| Upgrade options | `src/decoy/cli/upgrade.py` | Existing command module |
| Rollback page | `docs/distribution/rollback-compatibility.md` | Beside `version-endpoint-contract.md` |
| SBOM in bundle | `packaging_tools/build_bundle.py` | Existing bundle builder |
| Tests | `tests/unit/distribution/`, `tests/e2e/test_upgrade_*.py`, `tests/unit/release/` | Existing test homes |

## 9. Inherited plans: executable summary

The supporting delta audits for MAC-ED25519, REL-IMAGE and REL-WEB are in the linked
[release-chain record](2026-11-16-release-chain-record.md). Their executable decisions remain
here:

- MAC-V1a: finish Dennis and Codex gates on PR #282 and merge. All remaining REL-PKG work is an
  owner task or row 94 S0. No new slice is added here.
- REL-IMAGE: IMG-1 is buildable now. IMG-2 follows one published native companion release; IMG-3
  follows IMG-2. IMG-4 is not buildable: its increase of the CI write-scope allowlist from one to
  three remains owner-gated until an exception records who approved it, when, and where. IMG-5
  follows IMG-4 and row 32a. Risks remain IMG-1 R2, IMG-2 R2, IMG-3 R1, IMG-4 R2 and IMG-5 R2.
- REL-WEB: run one Codex pass on `plan/rel-web` `53e0e77c` sections 5.1 to 5.4 before RW-H. RW-C2b
  is buildable now and precedes 88-O. RW-H is R2; RW-D and RW-P are R1 and follow RW-H.

The owner-gated setup and release actions are in section 12.

## 12. Owner-gated items

None of these blocks a slice in sections 5 to 9 except where the slice says so.

| Item | Blocks | Needed by |
|---|---|---|
| Create the Ed25519 release key; private half into Environment `native-release`; public half for `release_key.pub.pem` | Row 94 S0, IMG-2 (a native release), REL-GATE G2 | 2026-12-01, so S0 runs before G5 |
| Create the Environment `native-release` with a required approver | Same | 2026-12-01 |
| Tag protection for `native-v*` and the CLI release tags | S0 | 2026-12-01 |
| Approve the qemu action SHA pin | S0 | 2026-12-01 |
| Push the first `native-v*` tag (a release, R3) | IMG-2 | after the key |
| Create the GHCR organization | IMG-4 | before G5 |
| Record the CI write-scope allowlist exception with approver, date and durable location | IMG-4 | before IMG-4 enters a buildable slice |
| trydecoy.com domain, DNS and hosting account (spend) | RW-H deploy, the live version endpoint | before G5 |
| Licensor name and CLA (counsel; REL-GATE Q1, Q2) | INST-13 license check at RC | G7 |
| GA flip (REL-GATE Q3) | G8 | G8 |
| Tart on the Mac mini (MAC plan Q3) | Mac release smoke only | G6 |

## 13. Owner decisions and recommended answers

| Id | Question | Recommended |
|---|---|---|
| OQ-1 | Mark row 46 (H-1 C0) folded into FILE-SIZE C2, with the pure-move checker moved to row 47 slice 47-A? | Yes. |
| OQ-2 | Does F10 in V1 make `decoy run` refuse when the host differs from a project's saved lock? | No for V1. V1 ships the report and the compare. The CLI has no project lock file today, and adding one is a new feature. |
| OQ-3 | Does engine `runtime_identity()` grow Faker, provider and pool digests before 1.0 (row detail FRAME note)? | No. That changes the fingerprint of every saved pinned plan. The lock carries those keys beside it. Revisit after 1.0. |
| OQ-4 | Does an upgrade that changes seed protocol or generator logic block until the user confirms? | No. Print the change and go on; rollback is local and offline. A block needs a new flag the row does not ask for. |
| OQ-5 | The SBOM lock-mode refusal prints lock package names (row 88 follow-up). Keep? | Keep. Package names are public build metadata, not user data. |
| OQ-6 | DIST-INTEGRITY (row 31) has not started. If it is not built by G0, does it leave the R-d list? | Yes. R-d closes with what merged; row 31 keeps its own row. |
| OQ-7 | `decoy upgrade --bundle` skips yank and floor checks (no version document offline). Accept? | Yes, with the stderr line. Reading a signed version document from beside the bundle can come later if users ask. |
| OQ-8 | QA INST-11 open point: does `decoy --version` also print the engine version? | Yes, one extra line. It is a REL-GATE item, not planned here. |
| OQ-9 | Keep separate `canon` and `generator_logic` fields in `lock/v1` when the engine has no version constants for them? | No. Drop both for V1. The version-invariant probe covers both executable paths, and `engine` records the release. |

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

The full supporting audit is in the linked
[release-chain record](2026-11-16-release-chain-record.md). This compact index keeps the plan-lint
contract and points to the executable acceptance cells.

| # | Class | Closing structure | Sentry or property test | Mutation |
|---|---|---|---|---|
| 1 | Value-bearing output | Fixed refusal text and bounded report fields | AT-78-E4, AT-78-C4, AT-88-S4 | Print `str(exc)` |
| 2 | Cleanup missing on an exit path | One staging sweep under the install lock | AT-88-O2, O3, O5, O7 | Skip the sweep |
| 3 | State machine and concurrency | One exclusive install section | Offline lock-contention test | Call outside `_exclusive` |
| 4 | Route parity and silent fallback | Shared verify, stage and flip core | AT-88-O4, AT-88-P4 | Skip local signature verification |
| 5 | Referential integrity | N/A: no table data | N/A | N/A |
| 6 | Untrusted producer | Strict versioned readers and 64 KiB bound | AT-78-E6, AT-78-C8, AT-88-P5 | Coerce a numeric string |
| 7 | Check then use on a path (TOCTOU) | Verify and extract the same in-memory bytes | AT-88-O6 | Reopen `PATH` after verification |
| 8 | Weak tests and overclaimed evidence | Red-first acceptance cells | AT-76-1, AT-47-3 | Remove a seeded assertion |
| 9 | Behavior-preserving refactor drift | Pure-move manifest and characterization golden | AT-47-1, AT-47-2, AT-47-4 | Rename staging before self-check |
| 10 | Frozen contract drift | One frozen-surface map | Frozen-surface, CLI-surface and release-freeze tests | Omit the map row |

## 17. Enumerations

The full enumeration audit is in the linked
[release-chain record](2026-11-16-release-chain-record.md). No executable requirement is moved.

### Exit paths

- Usage and early refusal exits begin at `src/decoy/cli/upgrade.py:81`.
- Install failures converge on the refusal at `src/decoy/cli/upgrade.py:174`.

### Routes

- Network upgrade enters through `install_version` at `src/decoy/distribution/installer.py:464`.
- Offline upgrade enters through `install_local_bundle` and shares the verify, stage and flip core.

### FK shapes

N/A: no slice touches table data or relationships.

### Fields

- Stored fields: `InstallOutcome`, `RuntimeLock` and `decoy-env-report/v1`.
- Wire additions: upgrade `preflight` and `checks_skipped`.

### Output surfaces

- User surfaces: stdout, stderr, JSON, report and bundle files, and help.
- Server log surfaces: none added.

## 18. Reuse inventory

The detailed reuse inventory is in the linked
[release-chain record](2026-11-16-release-chain-record.md). The executable plan continues to name
each reused choke point where its slice uses it.

## 19. Frozen contracts touched

All additive. Each is recorded in `docs/release/frozen-surfaces.md` before 1.0.0.

- Command and flag set: new `decoy env report`, `decoy env compare`, `decoy upgrade --bundle`.
  Updates `docs/cli-reference.md` and `tests/unit/test_cli_surface.py`.
- `--json` success shapes: `env report`, `env compare`, and the upgrade `preflight` and
  `checks_skipped` fields. Upgrade
  is on the snapshot's exemption list; the env commands get snapshot rows.
- `docs/schemas/`: new `decoy-env-report-v1.schema.json`, which needs its own map row.
- Version document and installer contract: unchanged; the offline path reads no version document.
- Engine: `lock/v1` is added to the compatibility-contract 3.1 tag block and the Format tags map.
  Its hand-written corpus sample pins the reader rule that added fields are ignored. The public
  `is_key_version_label` name from `decoy_engine.keyprovider` appears in exactly one Public names
  row. The private label pattern itself does not change.
- Exit codes: no new code. `env compare` uses 0, 1 and 4; `env report` uses 0, 1 and 3.

## 20. V2-LOG items this plan records

- Offline upgrade reads a signed version document placed beside the bundle, to check yank and
  floor (88-O, OQ-7).
- Local-activation rollback gets the upgrade preflight (88-P).
- Engine `support/_shape.py:252` can derive `Versions` from `build_runtime_lock` after V1, instead
  of keeping a parallel environment-version shape.

## 21. Pre-mortem

Assume it is 2026-12-04 and the release chain slipped. Likely reasons, with the guard for each:

- The owner key and Environment came late, so S0 and IMG-2 did not run. Guard: the dates in
  section 12 and an early ping. No slice before item 15 needs the key.
- 47-B grew past a pure move (a "while here" fix), review took three rounds, and 88-O waited.
  Guard: AT-47-1 refuses any change that is not a move.
- 78-C1 waited for a release that carried E1 and E2. Guard: RD-n is daily; cut a release the day
  E2 merges.
- The SBOM tool kept a random serial in reproducible mode and broke byte-identical bundles. Guard:
  section 4 tells the 88-S builder to stop and report.
- 88-P's subprocess call to the staged runtime was slow or flaky on the Mac. Guard: a 30-second
  timeout; on timeout the preflight is "report unavailable", never a refusal of a good runtime.
