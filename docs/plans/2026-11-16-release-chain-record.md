# Release chain supporting record

Status: record

Date: 2026-11-16. Companion to
[`2026-11-16-release-chain.md`](2026-11-16-release-chain.md). This file holds supporting audits
and inherited-plan deltas only. The executable acceptance tests, slices, dependencies, placement,
invariants and frozen-contract work remain in the plan.

Rules consulted: `dev-rules/00-universal.md`, `dev-rules/risk-and-exceptions.md`,
`dev-rules/development-loop.md`, `dev-rules/release-and-rollback.md`,
`dev-rules/catalogs/recurring-defects.md`, `dev-rules/testing.md`,
`dev-rules/workspace-and-vcs.md`, `dev-rules/architecture.md`,
`dev-rules/cross-cutting-concerns.md`, `dev-rules/api-and-compatibility.md`,
`dev-rules/security.md`, `dev-rules/documentation.md`.

## 1. MAC-ED25519 delta audit

The MAC-ED25519 plan (`plan/mac-ed25519` `97dbcfb0`) stands. MAC-V1b merged as #281. MAC-V1a is
PR #282 on `feat/mac-v1a`. Its executable action remains in the plan: finish Dennis and Codex
gates on the exact head and merge. It adds no new slice.

After MAC-V1a, the remaining items are owner tasks or row 94 S0:

- Create the release key pair. Put the private half only in Environment `native-release`.
- Create that Environment with a required approver.
- Protect `native-v*` and CLI release tags.
- Pin the qemu action by SHA. Engine `native-companion-release.yml:119` currently uses
  `docker/setup-qemu-action@v3`.
- Build row 94 S0 `.github/workflows/release.yml`, including the five PRE-S0 MAC items.

Windows audit: `targets.py` owns the target list. 88-O refuses a foreign bundle through
`targets.detect_target()`, so row 89 can add Windows without changing this release-chain design.

## 2. REL-IMAGE delta audit

The plan on `plan/rel-image` `d4716855` stands. These facts changed since its CLI base
`5bb93e66`:

1. Roadmap row 90a says "NOT STARTED; needs a plan". Reconcile it to the gated plan and IMG-1
   buildable state.
2. The launcher shim moved from `installer.py:655` to `installer.py:660`. After 47-B it remains in
   `installer.py`.
3. IMG-1 edits `_root` at `src/decoy/__main__.py:218`. The runtime guard is at lines 251 to 255.
   The image check follows the runtime guard and precedes the update notice.
4. The write-scope ratchet is at `tests/sentry/test_ci_lock_installs.py:313`, not line 314. Its
   increase from one to three has no durable owner-exception citation that names who approved it,
   when, and where it was recorded. IMG-4 remains owner-gated and outside the buildable slices
   until that exact exception is recorded.
5. The container-guide host is `trydecoy.com`, not `decoy.dev`. Derive it from
   `version_document.DEFAULT_URL`, the same constant used by the version endpoint.
6. Recorded answers cover OQ-1 option (a), OQ-2 GHCR under an organization, OQ-3 keyless and OQ-4
   slim only. OQ-5 is not treated as approval without the exact exception citation. The GHCR
   organization also does not exist yet.
7. IMG-2 needs one published engine native companion release. No `native-v*` tag exists yet. The
   release needs `DECOY_RELEASE_KEY_PEM` in the owner-managed Environment.
8. When IMG-2 merges, the Dockerfile `ARG` engine pin joins the RD-n pin list and AT-76-1.

The executable order and risks remain in plan section 9. IMG-1 can build now. IMG-4 cannot.

## 3. REL-WEB delta audit

The plan on `plan/rel-web` `53e0e77c` revision 3 stands. It had two Dennis rounds and a cross-model
review, but no Codex pass. The executable plan therefore requires one Codex pass on sections 5.1
to 5.4 before RW-H.

- RW-C2b is unblocked. Its audit scope is `docs/install.md`, `packaging_tools/README.md`,
  `docs/distribution/version-endpoint-contract.md`, the host-agreement sentry and AT-C7. It is R1,
  at most five files and 200 lines, and precedes 88-O because both edit `docs/install.md`.
- RW-H covers hosting layout, `check-dist.mjs`, deploy guards and the freshness workflow. Its
  acceptance cells are AT-H1 to AT-H6. It is R2 because it publishes signed files.
- RW-D covers the download page, AT-D1 to AT-D4, R1, after RW-H.
- RW-P covers `/proof`, AT-P1 to AT-P5, R1, after RW-H.

The domain, DNS and hosting account remain owner items.

## 4. Defect-class audit

Classes are from `docs/handoffs/DEFECT-CATALOG.md`, section 3.

| # | Class | Closing structure | Sentry or test | Mutation that turns it red |
|---|---|---|---|---|
| 1 | Value-bearing output | `_refuse` prints fixed text, a code and the exception type; env reports carry labels, never host names | AT-78-E4, AT-78-C4, AT-88-S4 | Print `str(exc)`; read `socket.gethostname()` |
| 2 | Cleanup missing | Staging stays under the install lock and `_sweep_stale_staging`; verified in-memory bytes extract into `.incoming.*` | AT-88-O2, O3, O5 and O7 assert no residual `.incoming*` after refusal | Skip the staging sweep on offline refusal |
| 3 | State machine and concurrency | The single-flight lock covers offline install and preflight | Hold the lock and run `decoy upgrade --bundle`; it refuses at once | Call the local entry outside `_exclusive(home)` |
| 4 | Route parity and silent fallback | Network and offline upgrade share one verify, stage and flip core | AT-88-O4 and AT-88-P4 | Skip local signature verification |
| 5 | Referential integrity | No slice reads or writes table data or foreign keys | N/A | N/A |
| 6 | Untrusted producer | Strict versioned readers bound the report to 64 KiB and never echo producer text | AT-78-E6, AT-78-C8, AT-88-P5 | Echo staged stderr; make a reader coerce a numeric string or accept an unknown `probe_status` |
| 7 | Check then use on a path | 88-O reads the bundle once, verifies those in-memory bytes, and extracts those same bytes | AT-88-O6 | Reopen `PATH` after verification and extract the replacement |
| 8 | Weak tests | Every acceptance test states its fail-before; RD-0 seeds an old tag | AT-76-1; AT-47-3 | Remove the seeded assertion |
| 9 | Refactor drift | 47-B is a pure move with a characterization golden and re-homed sentry keys | AT-47-1, AT-47-2, AT-47-4 | Rename staging before self-check |
| 10 | Frozen contract drift | New commands, flags, schema and JSON fields are additive and mapped | Frozen-surface, CLI-surface and release-freeze tests | Add `decoy env` without map and reference rows |

## 5. Enumerations

### Exit paths

Current `decoy upgrade` exit paths at the plan base:

- `upgrade.py:81` and `:87`: usage refusals, exit 1. 88-O adds incompatible `--bundle` combinations.
- `upgrade.py:101`: local activation failed through `_refuse`, exit 3.
- `upgrade.py:103`: local activation completed, exit 0.
- `upgrade.py:110`, `:122` and `:127`: endpoint unavailable, rejected or stale, exit 3. Offline
  upgrade skips them.
- `upgrade.py:118`: placeholder key or signature refusal, exit 3.
- `upgrade.py:142` and `:145`: check result or already current, exit 0.
- `upgrade.py:174`: install failed with runtime unchanged, exit 3. New 88-O and 88-P refusals end
  here.
- `upgrade.py:177`: installed, exit 0.
- The 35 `InstallError` sites in `installer.py` all reach `upgrade.py:174`.

### Routes

- Network upgrade calls `install_version` at `installer.py:464`.
- Local activation calls `activate_local_version` at `installer.py:398`.
- 88-O adds `install_local_bundle` on the same install core as `install_version`.
- First install remains in `install.sh` and `first_install.py`.

### FK shapes

N/A: no slice touches table data or relationships.

### Fields

- `InstallOutcome` keeps `version`, `target`, `version_dir`, `previous_version`, `rolled_back` and
  `rollback_version`. Preflight belongs to upgrade JSON, not this type.
- `RuntimeLock` adds the `runtime_identity()` keys, `compat_phase`, `faker`, `providers_digest`,
  `data_digest`, `dependencies`, `key_version` and `probe`.
- `decoy-env-report/v1` adds `cli_version`, `target`, `native_selfcheck` with only `present`, `ok`
  and `reason`, `probe_status` and `label`.
- Upgrade JSON adds optional `preflight` and offline-only `checks_skipped`.

### Output surfaces

- User output: env report, compare and upgrade stdout; fixed refusal, offline-skip, preflight and
  probe-mismatch stderr; report and upgrade JSON.
- Durable and help output: report files, bundle license, notice and SBOM files, and env and upgrade
  help. No log site is added.

## 6. Reuse inventory

- Signature and manifest checks: `distribution/signing.py`, `manifest.py`, `release_key.py` and
  `verify_extracted.py`.
- Staging, flip, rollback and single-flight locking: `installer.py`, `lock.py` and `layout.py`.
- Refusal and exits: `_refuse` in `upgrade.py` and `cli/exit_codes.py`.
- Environment reads: `decoy._env_flags`, guarded by `test_environment_reads.py`.
- Atomic writes: the CLI atomic writer, guarded by `test_atomic_writer.py`.
- Engine inputs: `runtime_identity()`, `_canonical`, the reason catalog and provider registry.
- Size and layout guards: `test_module_size.py` and `test_package_fanout.py`.
- Engine pin source: `scripts/dev/lock_version.sh --engine-spec`.
- Release tools: `build_bundle.py`, `sbom.sh`, `sbom_checks.py` and `launch_pin_check.py`.

The only new machinery remains the ported pure-move checker, the row-required lock and probe, and
the row-required env command.

## 7. Hostile corpus / acceptance tests red first

The executable hostile and malformed-input matrices remain in plan section 7 and section 8.
AT-78-E6 and AT-78-C8 cover strict writer and reader types. AT-88-O2 through O10 cover offline
bundle failures. Each cell states its fail-before reason and named mutation in the plan.

## 8. Frozen contracts

The executable frozen-contract edits remain in plan section 19. This record only notes that the
command surface, JSON shapes, `decoy-env-report/v1`, `lock/v1`, public label checker and existing
exit-code assignments are additive.

## 9. Slices

No slice is defined in this record. The complete executable slice table remains in plan section
14. The inherited-plan execution summary remains in plan section 9.

## 10. Pre-mortem

The executable pre-mortem remains in plan section 21. Record-specific risks are stale inherited
line citations and accidentally treating the uncited IMG-4 write-scope decision as approval. The
plan counters them with current-head checks and an explicit owner gate.
