# CERT-PIN-CVES: repin four certified runtime packages past their advisories

Status: plan

Owner: Cam. Roadmap row 24zc (`docs/ROADMAP.md`, section 5; `docs/roadmap/groups/release.md`).
Source: automated QA scan 2026-11-11, finding F1. Owner decision 2026-11-11: a V1 release blocker.

Rules consulted: 00-universal, risk-and-exceptions, development-loop, local-operations,
workspace-and-vcs, reuse-first, exploration, scope-discipline, proportionality, verification,
bugfix, security, config-secrets-and-supply-chain, release-and-rollback, testing, architecture,
cross-cutting-concerns, api-and-compatibility, documentation, and catalogs/recurring-defects.

Risk: R2 (supply-chain pins on the release path, a frozen certified-row contract).

Base (revision 2, 2026-11-20): CLI main `7c0fe61d` (pins `decoy-engine==0.28.1`, 70 certified
pins, header fingerprint `b61dcfd6...`, `decoy-cli` 0.1.0), engine main `815d15442` (version
0.28.1; `b61dcfd6...` is the newest CLI-profile row in `_CERTIFIED_STACKS`). Revision 1 was
written against CLI `ac0cb686` and engine 0.22.0 (63 pins, `d5898d1f...`) and is replaced.

**Guarantee.** The certified DP runtime set (`requirements-certified.txt`) pins exactly certifi
2026.10.18, cryptography 50.0.0, pyasn1 0.6.5 and urllib3 2.8.0, and that set is a certified row in
the engine the CLI pins, so a real DP fit still completes on the certified platform. Across every
pin line, the complete before/after delta is exactly the four named old-to-new pairs. No fifth pin
is added, removed or changed, and no version goes above the four named.

**Non-goals:** moving any other certified pin; moving `requirements-dev.lock` third-party lines
(it holds certifi 2026.10.23, cryptography 50.0.2 and urllib3 2.8.0, which are dev-only and not
shipped); raising the `cryptography>=42` floor in `pyproject.toml`; a pip-audit CI step (see
"Follow-ups"); the platform image, under the owner-approved parked-platform exception below.

**Size.** Engine: no source change; release prep inputs, one test tuple, one comment line, one doc
count. CLI: about 20 existing files touched with version strings, one new fixture, one new test
module (`tests/unit/release/test_certified_pin_delta.py`, about 80 lines). No new public names.

## Why

`pip-audit` on `requirements-certified.txt` (QA scan 2026-11-11) found:

| Package | Pinned | Advisories | Fixed in |
|---|---|---|---|
| certifi | 2026.7.22 | PYSEC-2026-4320 | 2026.10.18 |
| cryptography | 49.0.0 | PYSEC-2026-3552 | 50.0.0 |
| pyasn1 | 0.6.4 | GHSA-2qm8-x737-gmw5, GHSA-fm9c-5rcf-2q5p, GHSA-mm57-4v3p-rchx, GHSA-9m75-vc3g-4x39 | 0.6.5 |
| urllib3 | 2.7.0 | PYSEC-2026-4175, -4176, -4177 | 2.8.0 |

The pinned versions are still the same on CLI main `7c0fe61d`. This file is what the release ships
for DP and what `scripts/release/sbom.sh` turns into the SBOM, so the SBOM would list open
advisories. The engine's own `uv.lock` already holds exactly certifi 2026.10.18, cryptography
50.0.0, pyasn1 0.6.5 and urllib3 2.8.0, and its dev/CI rows are certified with them.

## Pre-check: the four versions resolve with no other move (done 2026-11-20)

Run on the Mac (a throwaway uv venv in a scratch folder, deleted after), not the devbox.

- **They exist on PyPI.** `pip download --no-deps --only-binary=:all: --platform
  manylinux_2_28_x86_64 --python-version 3.10 --implementation cp` fetched
  `certifi-2026.10.18-py3-none-any.whl`, `cryptography-50.0.0-cp39-abi3-manylinux_2_28_x86_64.whl`,
  `pyasn1-0.6.5-py3-none-any.whl` and `urllib3-2.8.0-py3-none-any.whl`. cryptography installs a
  wheel on CPython 3.10.20, not a source build.
- **Their own floors.** From each wheel's `METADATA` (non-extra `Requires-Dist`): certifi, pyasn1
  and urllib3 have none (urllib3 needs Python 3.10 or later). cryptography 50.0.0 needs
  `cffi>=2.0.0` and, below 3.11, `typing-extensions>=4.13.2`. The set pins `cffi==2.1.0` and
  `typing-extensions==4.16.0`, so neither forces a move.
- **The whole candidate closes.** `uv pip compile` of the 70 candidate pins (the live file with only
  the four lines changed) for CPython 3.10.20 on `x86_64-unknown-linux-gnu` resolved to exactly the
  same 70 `name==version` lines. The dependents that constrain the four (requests and botocore on
  urllib3 and certifi, google-auth and joserfc on cryptography, pyasn1-modules on pyasn1) all
  accept the new versions.

Result: no fifth pin has to move for the four. No owner question from the dependency floors.

## Behavior

- **Pins.** In `requirements-certified.txt`: `certifi==2026.10.18`, `cryptography==50.0.0`,
  `pyasn1==0.6.5`, `urllib3==2.8.0`. The count stays 70. `pyasn1-modules==0.4.2` stays (it accepts
  pyasn1 0.6.x).
- **Exact delta.** Preserve the pre-repin file as the test fixture
  `tests/fixtures/sbom_runtime/requirements-certified-pre-24zc.txt` (a byte copy of CLI main's file
  at the C0 base). A test parses both that fixture and the live file with
  `scripts/release/sbom_checks.py::pins`, canonicalizes with its `canonical_name`, and compares every
  pin line. The only permitted delta is the four exact old-to-new pairs above. An addition,
  removal, marker change, requirement-text change on an unchanged pin, or fifth version move is a
  hard failure. Header comment lines are not pin lines and may change.
- **Fingerprint.** `compute_lock_fingerprint` hashes every installed distribution and version,
  including `decoy-engine` and `decoy-cli`. So the four moves change `b61dcfd6...` to a new value
  `F`, and `F` is only defined for one engine version `N` and one CLI version `V`. The engine must
  carry `F` as a CLI-profile row before the CLI can ship the four pins.
- **Old rows stay.** `b61dcfd6...` and every older CLI-profile row stay in `_CERTIFIED_STACKS`, so
  snapshots recorded on them still compile. `c479d1de...` (the 24zc candidate row stamped at 0.28.0
  from the 69-pin file without joserfc and rfc8785; no real install has that set) also stays.
- **Install and smoke.** The `requirements-certified.txt` header, `scripts/cert_smoke.py` and the
  certified-profile CI job name engine `N` and fingerprint `F`.

## Sequencing: how `F` gets into the engine

Release prep already writes the DP rows (engine #621, `80c381b5c`).
`scripts/release/stamp_release.py` computes the dev/CI row from `uv.lock` and one CLI-profile row
per `--cli-pins` file through `scripts/release/dp_rows.py::plan_rows`, and inserts them newest
first in `_CERTIFIED_STACKS` without removing a row. It does not read the CLI repo by itself: the
release operator passes the pin files as paths. `scripts/release/release_checks.sh N` does not
compute CLI rows. It only proves the dev/CI row through `check_fit_environment()`. So the engine
half of this row is no code change: it is the normal release prep of `N` with one more
`--cli-pins` file.

Steps, in order. Each step names its input and its output.

1. **C0, CLI, before the engine release.** On branch `chore/certified-pin-cves-c1` (from CLI
   main): copy `requirements-certified.txt` to the fixture path, then change the four pin lines
   only. Leave the header (engine 0.28.1, `b61dcfd6...`) as it is; step 5 fixes it. Push. Record
   the C0 commit SHA. Output: the candidate file at `C0:requirements-certified.txt`.
2. **E1, engine release prep of `N`.** In the engine release prep branch for `N`, export both pin
   files from the CLI clone into a scratch folder:
   `git -C <cli> show origin/main:requirements-certified.txt > base.txt` and
   `git -C <cli> show <C0 sha>:requirements-certified.txt > cand-24zc.txt`. Then run
   `python scripts/release/stamp_release.py --version N --cli-version V --cli-pins-base base.txt
   --cli-pins base.txt --cli-pins cand-24zc.txt`, where `V` is the `__version__` in CLI
   `src/decoy/_version.py` at C0 (0.1.0 on `7c0fe61d`). No `--allow-delta`: the names are the same.
   This writes three rows: the dev/CI row for `N`, the unchanged 70-pin CLI row for `N` (so the
   CLI can still repin to `N` without this row if C1 slips), and `F`. `dp_rows.base_closure` also
   refuses here if engine `N` added a base dependency that the candidate lacks (the 0.28.1 PyNaCl
   case); see "Failure modes".
3. **E1, by hand in the same release prep PR** (as #706 did): add `_VN_ROWS` (the three rows, with
   a comment naming which is `F` and the C0 SHA it came from) to
   `tests/unit/generation/test_dp_prior_release_rows.py` and append it to `_ALL_ROWS`; extend the
   CLI-profile comment in `dp_provenance.py` with one line ("N: F is the 70-pin profile with
   certifi, cryptography, pyasn1 and urllib3 moved, row 24zc"); correct the stale count in
   `docs/distribution-integrity/differential-privacy.md` ("63 third-party pins; 67 once ...") to 70.
4. **E1 proof before the tag.** On a Linux x86-64 glibc node (the Dell WSL node through
   `~/bin/vm-run`, or a GCP test VM), build the AT-5 venv by hand: CPython 3.10.20, the engine from
   the release prep commit with `--no-deps`, the CLI wheel built from C0 with `--no-deps`, then
   `-r cand-24zc.txt`, then call `check_fit_environment()` and print
   `compute_lock_fingerprint(installed_distribution_set())`. It must equal `F` and pass. (C0's
   header still names the old fingerprint, so `cert_smoke.py` is not run here.) Then
   `scripts/release/release_checks.sh N`, then `cut-release.sh` tags `vN`.
5. **C1, CLI, after `vN` exists.** On the same CLI branch: repin the engine to `N` (file list
   below), write `F` and `N` into the header and `cert_smoke.py`, add the tests, and merge only
   when the certified-profile CI job is green on the exact head.

If the CLI version changes between C0 and C1, `F` is wrong for C1 (the fingerprint hashes
`decoy-cli`). C1 then waits for the next engine release prep to stamp the row again with the new
`V`. C1 does not change `_version.py`.

## Where the pins and the fingerprint move

Checked on CLI `7c0fe61d` and engine `815d15442`. The CLI engine repin list follows CLI #327
(`c394ab99`, the 0.28.1 repin), less its feature changes.

**Engine (E1, the release prep for `N`):**

1. `src/decoy_engine/quality/dp_provenance.py:271-327` `_CERTIFIED_STACKS`: rows written by
   `stamp_release.py` (step 2); the CLI-profile comment at `:304-306` gains one line by hand. No
   row is removed.
2. `tests/unit/generation/test_dp_prior_release_rows.py:94-122`: `_VN_ROWS` beside
   `_V0_28_1_ROWS`, appended to `_ALL_ROWS`.
3. `docs/distribution-integrity/differential-privacy.md`, "Certified profiles" table: the CLI pin
   count reads 70.
4. `_CERTIFIED_ANNOTATIONS` (`dp_provenance.py:330`): unchanged; none of the four is
   proof-critical.
5. `uv.lock`: unchanged for this row (it already holds the four fixed versions).

**CLI (C0 then C1, branch `chore/certified-pin-cves-c1`):**

6. `requirements-certified.txt:56, 59, 93, 118`: the four pins (C0).
7. `tests/fixtures/sbom_runtime/requirements-certified-pre-24zc.txt`: byte copy of the pre-repin
   file (C0), used only as the before side of AT-1.
8. `requirements-certified.txt:4-14, 25`: engine `N`, fingerprint `F`, and the history line ("Was
   b61dcfd6... on engine 0.28.1 with the four pre-advisory pins") (C1).
9. `pyproject.toml:143-149`: `decoy-engine==N` and its comment.
10. `requirements-dev.lock`: the `decoy-engine` line and whatever engine `N`'s own requirements
    move, through `scripts/dev/lock.sh` (stale-lock rule: regenerate, do not hand-edit). The
    certifi, cryptography and urllib3 dev-lock lines stay where they are.
11. `.github/workflows/ci.yml:322` and `.github/workflows/release-smoke.yml:88`: the engine tag.
12. `scripts/cert_smoke.py:8-11`: the docstring names engine `N` and `F` (it says `dceac0cd...`
    today, which is already stale).
13. `scripts/dev/bootstrap.sh:32`, `scripts/dev/lock_version.sh:17`: the engine spec.
14. `docs/guides/shape-and-privacy/04-differential-privacy.md:88`,
    `docs/guides/shape-and-privacy/README.md:10-13`, `docs/release/fresh-install-smoke.md:47, 87,
    115`: the engine tag.
15. `LICENSING.md:6`, `README.md:218` and the two quoted strings in
    `tests/unit/test_pyproject_metadata.py:174, 189`: "including the N the CLI pins today".
16. `src/decoy/ci/rule_codes.py:214`: the engine version in the comment, after re-checking the
    literal codes against `N`.
17. `tests/unit/release/test_launch_pin_check.py:21` (`TAG`) and `packaging_tools/candidate.py:9`
    (usage example): `vN`.
18. `docs/release/sbom.md:21`: "67-package" is already stale on main; it becomes "70-package".
19. `CHANGELOG.md`: one entry (engine repin plus the four security pins, fingerprint `F`).
20. The new test module `tests/unit/release/test_certified_pin_delta.py` (AT-1 to AT-3).
21. SBOM: no committed SBOM file. `scripts/release/sbom.sh` reads the pin list at release time.
    `tests/unit/test_sbom_script.py:300-317` counts pins from the file itself (no literal count),
    so it stays green at 70.
22. `docs/RECENTLY-SHIPPED.md` and the 24zc row in `docs/ROADMAP.md` and
    `docs/roadmap/groups/release.md`: closed when C1 merges.

**Not moved:** `requirements-dev.lock` third-party lines other than what engine `N` itself
requires, `ci/ci-tools.lock`, `pyproject.toml:171` (`cryptography>=42`), the engine's `uv.lock`,
`src/decoy/_version.py`, the platform.

## Failure modes and reason codes

| Failure | Code or signal (fixed, value-free) | Where caught | Response |
|---|---|---|---|
| Installed set is not a certified row (stale `F`, wrong engine or CLI version in the hash) | `ProvenanceError` code `dp_stack_uncertified` | step 4 on the Linux node; `cert_smoke.py` in the certified-profile CI job; AT-3 | do not tag (step 4) or do not merge (C1) |
| Header fingerprint does not match the pins | `cert_smoke.py` failure "pinned file no longer produces the fingerprint it records" | CI; AT-2 | fix the header to the computed value |
| A pin left at an advisory version, raised above the named version, or a fifth pin line changed | AT-1 exact-delta failure naming the package and the before and after requirement | T1 | revert the extra move |
| Engine `N` adds a base dependency the candidate lacks (as PyNaCl did at 0.28.1) | `DpRowError` "--cli-pins #2: lacks the engine's base requirements: <names>" from `stamp_release.py` (exit 1, tree unchanged) | step 2 | stop. Adding that pin is a fifth line move. Owner question at that time: allow it as part of the engine repin, or stamp `F` on an earlier `N` |
| Candidate names differ from the base | `DpRowError` "package names differ from the base" | step 2 | the C0 file is wrong; fix C0, never pass `--allow-delta` for this row |
| Release prep for `N` is cut without the extra `--cli-pins` | `F` is not a row; AT-3 and the C1 CI job fail | C1 | C1 waits for the next release prep; nothing else is blocked, because the unchanged 70-pin row is stamped either way |
| CLI version changed between C0 and C1 | AT-2 and the CI `cert_smoke.py` fail on `dp_stack_uncertified` | C1 | wait for the next engine release prep with the new `V` |
| cryptography 50.0.0 needs a dependency the set does not hold | `uv pip install -r requirements-certified.txt` resolution error | C1 CI install step | stop and report; do not move a fifth pin (the pre-check says it does not happen today) |
| A snapshot recorded on `b61dcfd6...` or an older row no longer compiles | existing prior-release-rows test (AT-4) | E1 T1 | restore the row |
| A cryptography 50.0.0 API change breaks CLI Ed25519 signing | AT-6 failure | C1 | stop and report |

Refusal messages carry package names, versions and fingerprints only. No paths or secrets are
added. The synthetic success values printed by `cert_smoke.py` are the V2-LOG item recorded under
Output surfaces.

## Pre-mortem

| Risk | Guard |
|---|---|
| `F` computed for the wrong engine version | `F` comes from `stamp_release.py --version N` on the release prep branch; step 4 checks it on a real install of that exact commit before the tag; C1's certified-profile job installs the real tag |
| `F` computed for the wrong CLI version | `--cli-version` is read from C0's `_version.py`; C1 does not change it; a changed version fails AT-2 and CI |
| The repin raises a pin past the named fix (cryptography 50.0.2 copied from the dev lock) | AT-1 checks exact equality |
| A fifth pin moves and `F` is recomputed and registered to hide it | AT-1 compares all 70 parsed pin lines against the fixture, independently of `F` (M5) |
| Release prep stamps `F` from the wrong file (CLI main instead of C0) | the release prep PR names both rows and the C0 SHA; step 4 installs `cand-24zc.txt` and must reproduce `F` |
| E1 drops an old row | `dp_rows.plan_rows` refuses a lost or reordered row; AT-4 |
| The dev lock gets regenerated with a wider move | `lock.sh` is run with only the engine spec changed; the diff must touch only lines engine `N` requires |

## Acceptance tests (red first)

| # | Test | Red on |
|---|---|---|
| AT-1 | New `tests/unit/release/test_certified_pin_delta.py`. Load `scripts/release/sbom_checks.py` with the importlib pattern the other `tests/unit/release/` modules use; parse the fixture and the live file with `sbom_checks.pins()` and `canonical_name()`. Require 70 unique names on each side, identical name sets, identical requirement text (markers included) for every unchanged pin, and a complete version delta equal to exactly `{certifi: 2026.7.22 -> 2026.10.18, cryptography: 49.0.0 -> 50.0.0, pyasn1: 0.6.4 -> 0.6.5, urllib3: 2.7.0 -> 2.8.0}` | current main (no fixture, no delta); M1, M4, M5 |
| AT-2 | Same module: the header fingerprint equals public `compute_lock_fingerprint` over the 70 pins plus `decoy-engine` at the `pyproject.toml` pin and `decoy-cli` at `src/decoy/_version.py` | M2, M6 |
| AT-3 | Same module: construct public `Provenance(CERTIFIED_PLATFORM, "3.10.20.final", F)`, where `F` is read from the header, and call public `validate_recorded_provenance()`. Do not import or inspect `_CERTIFIED_STACKS` | M3; and C0 alone (engine still 0.28.1, `F` not a row) |
| AT-4 | Engine `test_dp_prior_release_rows.py`: `_VN_ROWS` includes `F` and the unchanged 70-pin row for `N`; every older row, `b61dcfd6...` included, still compiles | an E1 that drops a row |
| AT-5 | CI certified-profile job on the C1 head: fresh 3.10.20 venv, engine tag `vN` and the CLI wheel with `--no-deps`, then `-r requirements-certified.txt`, then `cert_smoke.py` (fingerprint, manifest row, real DP fit). Step 4 runs the same install against the release prep commit, without `cert_smoke.py` | M2, M3, M6 |
| AT-6 | Exact-50.0.0 CLI Ed25519 cell: a throwaway CPython 3.10.20 test environment constrained to `cryptography==50.0.0`; first assert `importlib.metadata.version("cryptography") == "50.0.0"`, then run the Ed25519 signing, verification, wrong-key and tamper cases in `tests/unit/test_distribution.py`, `tests/unit/test_distribution_acceptance.py` and `tests/unit/test_distribution_r7_security.py` | M4 (the version assert), or an API break in 50.0.0 |
| AT-7 | Engine release prep refusal: `stamp_release.py` with a candidate that lacks an engine base requirement exits 1 with the tree unchanged. The existing `tests/unit/scripts/test_dp_rows.py` and `tests/unit/scripts/test_stamp_release_compile.py` cover this; E1 runs them and adds nothing | a release prep that would stamp `F` for a set no install has |

**Named mutations** (on the C1 head unless stated; each must turn a test red):

- M1: leave `urllib3==2.7.0`.
- M2: keep the old header fingerprint `b61dcfd6...`.
- M3: install an engine build with `F` removed from `_CERTIFIED_STACKS`. AT-3 still calls only the
  public `validate_recorded_provenance()` boundary and must reject the record.
- M4: pin `cryptography==50.0.2`.
- M5: move a fifth pin, `numpy==2.2.6` to `numpy==2.2.7`, then recompute the header fingerprint
  and admit that row engine-side. AT-2, AT-3 and AT-5 may then pass; AT-1 must still fail on the
  unauthorized fifth delta.
- M6: set `src/decoy/_version.py` to a different version with the header unchanged. AT-2 fails.

## Enumerations (CLI `7c0fe61d`, engine `815d15442`)

### Routes

- Certified install: `.github/workflows/ci.yml:300-335` (`--no-deps` engine plus wheel, then the
  pin file, then `cert_smoke.py`).
- Release smoke: `.github/workflows/release-smoke.yml:88`.
- Row writer: `E:scripts/release/stamp_release.py:557` `main` through
  `E:scripts/release/dp_rows.py:262` `plan_rows`.
- Fit-time gate: `E:src/decoy_engine/quality/dp_provenance.py:347` `check_fit_environment`.
- Recorded-snapshot gate: `E:src/decoy_engine/quality/dp_provenance.py:382`
  `validate_recorded_provenance`.

### Exit paths

- `cert_smoke.py` exits non-zero on any mismatch (`scripts/cert_smoke.py:40` `_fail`).
- `stamp_release.py` exits 1 on a `DpRowError` (`E:scripts/release/stamp_release.py:500`), with
  the tree unchanged.
- A fit on an uncertified set raises `ProvenanceError` `dp_stack_uncertified`.
- A clean install exits 0 after a real fit.

### FK shapes

N/A: dependency pins only; no data path changes.

### Fields

N/A: no config key, result key or reason code is added; the change is version strings and one
fingerprint.

### Output surfaces

- The SBOM produced at release from `requirements-certified.txt` (`scripts/release/sbom.sh`).
- `cert_smoke.py` messages: package names, versions, fingerprints.
- `cert_smoke.py` also prints generated synthetic amounts and flags to server-admin-only CI
  output. This is recorded as V2-LOG and is not a V1 disclosure or part of this pin slice.
- `stamp_release.py` messages: file labels, line numbers, package names.
- `CHANGELOG.md` entries in both repos.

## Class table

| # | Class | Where it applies | Structure that closes it | Proof | Mutation that must turn it red |
|---|---|---|---|---|---|
| 1 | Value-bearing output | none; certifi and urllib3 carry data in transit, which is why the pins move | exact fixed versions in the shipped set | AT-1 | M1 |
| 2 | Cleanup missing on an exit path | `stamp_release.py` refusal | existing restore of owned paths on failure | AT-7 | n/a (existing tests) |
| 3 | State machine and concurrency | none | N/A: no runtime code changes | n/a | n/a |
| 4 | Route parity and silent fallback | certified install vs dev install | only the certified set is fingerprinted and certified; the dev lock is separate and not shipped | AT-5 | M3 |
| 5 | Referential integrity | none | N/A: dependency pins only, no keys or FK data paths change | n/a | n/a |
| 6 | Untrusted producer | package index content | `uv` installs wheels by exact pin; the engine gate checks the installed set by fingerprint | AT-5 | M2 |
| 7 | Check then use (TOCTOU) | the fingerprint is computed from the installed set at fit time, not from the file | unchanged engine gate | AT-5 | n/a |
| 8 | Weak tests | nothing in T1 limits the pin delta to the four approved moves | exact whole-file delta plus fingerprint and public admission in one release test module | AT-1, AT-2, AT-3 | M1, M2, M4, M5, M6 |
| 9 | Refactor drift | the engine repin file list | follow CLI #327's list; `test_pyproject_metadata.py` and `test_launch_pin_check.py` pin `N` | AT-5, existing metadata tests | leave `ci.yml` on `v0.28.1` (AT-5 red) |
| 10 | Frozen contract drift | the DP certified-row set and prior snapshots | release prep only inserts rows; `plan_rows` refuses a lost row | AT-4 | drop `b61dcfd6...` (AT-4 red) |

## Established solutions, reuse inventory, frozen contracts

- **Codebase search and reuse:** the engine row comes from the existing release-prep writer
  (`stamp_release.py` and `dp_rows.py`, engine #621); no engine code changes. CLI tests use
  `scripts/release/sbom_checks.py::pins` and `canonical_name` as the one requirements grammar and
  normalizer; no second regex parser. Reuse public engine `compute_lock_fingerprint`,
  `installed_distribution_set`, `Provenance`, `CERTIFIED_PLATFORM` and
  `validate_recorded_provenance`, plus `cert_smoke.py`, the certified-profile CI job,
  `scripts/dev/lock.sh`, and CLI #327's repin file list.
- **External evidence:** the official cryptography 50.0.0 changelog records PKCS7 failure-handling
  changes and FFDH deprecation, neither of which appears in the CLI call inventory. The CLI uses
  Ed25519 generation, serialization, signing and verification, so AT-6 runs those exact calls
  under exactly 50.0.0. Source: <https://cryptography.io/en/latest/changelog/#v50-0-0>. The
  dependency floors were read from the published wheels (see "Pre-check").
- **Prior engine evidence:** engine main already locks exactly cryptography 50.0.0 and its earlier
  compatibility run passed 1,866 targeted Fernet, AES-GCM, FF1, quarantine, vault and SFTP tests.
  C1 does not rely on that as CLI proof; AT-6 supplies the CLI-specific Ed25519 cell.
- **Frozen contracts:** the DP certified-row set grows by the rows release prep writes; no row is
  removed. The 70-package count and the proof-critical versions in `_CERTIFIED_ANNOTATIONS` do not
  change.

## Design notes

None: no new structure. One test module and one fixture are added; no source module,
abstraction or variant. The certified-row choke point is the existing release-prep writer
(`dp_rows.plan_rows`), which every row passes through, and the existing fit-time and
recorded-snapshot gates in `dp_provenance.py`.

## Placement

| Change | File | CODEMAP authority | Sits beside |
|---|---|---|---|
| Rows for `N`, including `F` | `E:src/decoy_engine/quality/dp_provenance.py` | existing DP provenance owner, written by release prep | the CLI-profile rows |
| `_VN_ROWS` | `E:tests/unit/generation/test_dp_prior_release_rows.py` | existing owning unit test | `_V0_28_1_ROWS` |
| Four pins, header | `requirements-certified.txt` | existing certified runtime manifest | the other 66 pins |
| Exact-delta, fingerprint and public-admission tests | new `tests/unit/release/test_certified_pin_delta.py` | CLI `CODEMAP.md:75`, Release scripts row: "new tests go in `tests/unit/release/`" | `test_launch_pin_check.py`, `test_version_agreement.py` |
| Pre-repin pin-line input | `tests/fixtures/sbom_runtime/requirements-certified-pre-24zc.txt` (new) | fixture beside the existing release pin fixture | `requirements-runtime.txt` |
| Engine repin | the CLI files listed above | existing repin surfaces | as in CLI #327 |

## Slices

| Slice | Repo | Branch | Size | Gate | Depends on |
|---|---|---|---|---|---|
| C0 | CLI | `chore/certified-pin-cves-c1` (first commit, pushed, not merged) | XS (four pin lines, one fixture) | none on its own; it is the input to E1 | none |
| E1 | engine | the release prep branch for `N` | XS (one extra `--cli-pins` flag, one test tuple, one comment line, one doc count) | T1: `tests/unit/generation/test_dp_prior_release_rows.py`, `tests/unit/scripts/test_dp_rows.py`, `tests/unit/scripts/test_stamp_release_compile.py`, `tests/sentry/test_dp_lock_row.py`; step 4 on a Linux x86-64 node; `scripts/release/release_checks.sh N` | C0 pushed; the daily engine release |
| C1 | CLI | `chore/certified-pin-cves-c1` | S (header, repin file list, one new test module) | T1: `tests/unit/release/test_certified_pin_delta.py`, `tests/unit/test_sbom_script.py`, `tests/unit/test_pyproject_metadata.py`, `tests/unit/release/test_launch_pin_check.py`, AT-6, and the CI certified-profile job green on the exact head; M1 to M6. Full suite per the testing.md dependency-lock, version-pin and frozen-contract triggers | E1 released as tag `vN` |

**When to build.** Feature group: fit, fidelity and differential privacy (engine QA checklist
section 13). Owner rule 2026-11-11: QA and its fixes run only on a V1-complete group, so C0, E1 and
C1 are built at that group's QA pass, and before the first release cut (row 93). C0 must be pushed
before the engine release prep that is meant to carry `F`.

`F` cannot be proven on the Mac: the DP certified row covers only Linux x86-64 CPython 3.10.20
glibc. Step 4 proves it on a Linux node before the tag, and C1's CI job proves it again on the
real tag.

## Parked platform exception

Owner Cam approved parking platform V1 on 2026-11-11. Policy domain:
`release-and-rollback/platform-engine-repin`; risk R2. Scope: this engine and CLI certified-pin
release only. The normal platform follow-on must move all seven engine-pin locations from the
engine-repin checklist (compat, fences, FROZEN, doc, `PIN_PREFIX`, Dockerfile ARG and catalog) in
one platform change and boot the platform before that change is done. Rationale: platform V1 is
parked and is not a release consumer for this row. Compensating control: platform stays on its old,
internally consistent released engine pin and is not partly repinned. Residual risk: platform does
not receive `N` or row `F` while parked. Owner: Cam. Expiry and follow-up trigger: the first
platform V1 resume or any request to consume engine `N`, whichever comes first. This exception does
not waive the seven-location repin or boot proof at that trigger.

## Engineering calls made

- One row per release: no released engine can change, so `F` goes into the next release prep.
  Release prep also stamps the unchanged 70-pin file for `N`, so a CLI repin to `N` never waits on
  this row.
- The engine half is a release-prep input, not an engine code slice: engine #621 already writes
  rows from `--cli-pins` files.
- The pin file for E1 comes from a pushed CLI commit (C0), not a local edit, so the release prep
  input can be reproduced from its SHA.
- The new tests go in `tests/unit/release/`, as the current CODEMAP row says. Revision 1 put them
  in `tests/unit/test_sbom_script.py`, which is now 761 lines; adding them would take it past the
  800-line size rule.
- AT-1 and its fixture prove this one change. The next legitimate re-certification that moves a
  pin (for example a new engine base dependency) deletes the fixture and the exact-delta test in
  the same change, as the file header's "re-derive" rule already expects. AT-2 and AT-3 stay: they
  hold for every future header.
- The dev lock third-party lines are left alone. Their versions are newer than the named fixes and
  the dev lock is not shipped; aligning it to the certified pins would lower them.

## Owner questions

None open. The pre-check found no dependency floor that forces a fifth move. One conditional
question is written into "Failure modes": if engine `N` adds a base dependency, stamping `F` needs
a fifth pin line, and that needs an owner call at the time.

## Follow-ups (not in this row)

- A `pip-audit` step on `requirements-certified.txt` in CI (V2-LOG candidate; needs a pinned tool
  and network access in CI).
- Platform image pins are governed by the parked-platform exception above, not dropped.
