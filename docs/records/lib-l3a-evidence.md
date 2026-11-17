# LIB L3a (evidence half): build evidence

Slice L3a of the LIB plan (`plan/local-record-library:docs/plans/2026-11-05-local-record-library.md`,
revision 7, section L3a-cli with the amendment of 2026-11-12, and sections 4.16 and 4.17). This
is the evidence half only. The run-result half waits on RESULT C1a and C1b (roadmap row 62, in
progress). Branch `claude/inspiring-hopper-bb38t6` from main `4e6d60b`.

## Environment

- OS: Linux 6.18.44 (x86_64), ext4, run as uid 0 in a container.
- `python -V`: Python 3.10.20 (`.venv`; `scripts/dev/bootstrap.sh` OK against `requirements-dev.lock`).
- Engine: `decoy-engine` 0.27.0 (commit `ddd014a`). Its `EvidencePayload` already has the
  amendment's `path_base` and `project_manifest` keys, so no engine slice was needed first.
- Code head: `b7c6d9f` (mutations). Full suite: `2124e17` (adds Markdown only). `e7e76d9` fixes a
  CODEMAP path (Markdown only); this record is the last commit (Markdown only).

## Commits

| Commit | What |
|---|---|
| `2174e83` | red first: `tests/e2e/library/test_run_evidence_records.py`; the `evidence` canary case; the `evidence` pending row removed from G-KIND-CANARY and its baseline; the one-caller sentry |
| `6cd486b` | `cli/library/_run_records.py` (`store_evidence`, `StoreOutcome`) on the facade; `cli/run/_evidence.py` builds the manifest once, writes `--evidence-out` and stores the record; `--no-library` (forwarded by `--all`); the `library` member in `--json` and the card's `Library` line; `json-shapes.json` regenerated (`/library` opaque); CLI reference regenerated |
| `b7c6d9f` | the label is computed run-side (G-LIB-FS); the tests that compare two runs' `--json` and list a run's files take the new record into account; sentry manifest entry |
| `2124e17` | `docs/library.md`, CHANGELOG, CODEMAP |
| `e7e76d9` | CODEMAP names the caller by its full path (`test_codemap_paths.py`) |

## Red first (`2174e83`)

`test_run_evidence_records.py`: 8 of 9 failed (no record, no `--no-library`, no `library` key).
The `--rows` preview case passes on main too: it guards that a preview stays out. The canary case,
the G-KIND-CANARY pending count and the one-caller sentry failed.

## What was built

- **One store function.** `decoy.cli.library.store_evidence(manifest, pipeline=, label=,
  invocation_id=, enabled=)`:
  - It resolves the root from the run's YAML (`resolve_root(pipeline=...)`).
  - It builds an `evidence` envelope from the manifest dict as built, and puts it.
  - It returns `StoreOutcome` (`stored` with root and id, `skipped`, or `failed` with a code).
  - It never raises.
- **One caller.** `cli/run/_evidence.py` is the only call site, which a sentry holds
  (amendment: `finish` takes the call over in the RESULT PR).
- **Built once.** The manifest is built once per successful run, whether or not `--evidence-out` is
  given. The same dict goes to the file and to the record.
- **Labels.** `pipeline` is the YAML's project-relative POSIX path (absolute outside a project);
  `tables` are the target names. No links: the run-result record will link to the evidence.
- **Off switches.** `--no-library` and `DECOY_LIBRARY=off` give `skipped`. A `--duckdb-source`
  run is skipped too: its input is a transient snapshot with no defined fingerprint, the reason
  `--evidence-out` already refuses it.
- **Failure (4.17).** The run warns once on stderr (`warning: <code>: ...`), `--json` has
  `library.status = "failed"` with the code, and the exit code is the run's own.

## Acceptance tests and mutations (on `b7c6d9f`)

`mutate_l3a.py`: each mutation applied once by exact string replace, its tests run, the file
restored; `src` clean after.

| Plan row | Test | Mutation | Result |
|---|---|---|---|
| L3-records (evidence part) | `test_a_run_stores_one_evidence_record_by_default` | ML3-label: label is the file name | red |
| L3-evidence-same | `test_the_record_payload_equals_the_evidence_out_file[project, no-marker]` | ML3-drift: build the manifest a second time for the store | red (both) |
| L3-baseline-link (root half) | same, no-marker case: the record lands in the YAML's library, not the current folder's | ML3-cwd-root: resolve the root without the YAML | red |
| L3-no-library | `test_no_library_or_env_off_stores_nothing[flag, env]` | ML3-ignore: `--no-library` ignored | red (flag) |
| L3-readonly | `test_a_library_that_cannot_be_written_warns_and_keeps_the_exit_code` | ML3-fail: exit 3; ML3-silent-fail: no warning | red, red |
| L3-failed-run (evidence part) | `test_a_run_that_fails_stores_no_evidence` | none: the failure path never reaches `write_evidence` | guard |
| L3-canary | `test_canary.py` with the new `evidence` case | M-PAYLOAD-LEAK not applied: the payload model refuses unknown fields, so there is no CLI-side spot to inject a value | positive and negative checks pass |
| one caller | `test_evidence_store_caller.py` | ML3-second-caller | red |

L3-readonly uses a file where the `.decoy` folder goes, not a 0555 folder: this container runs as
root, and root writes through a read-only mode.

Not built (run-result half, RESULT C1a/C1b): L3-records' run-result part, L3-payload-from-finish,
L3-failed-run's run-result part, L3-log-link, ML3-nolink, ML3-two-way. L3-report-id (`report
show`, `verify` and `diff` by id) is not built in this part either (see Deviations).

## Finding: some runs' manifests fail the engine's evidence model (owner decision needed)

When the freeze snapshot regenerated, its two-table FK mask run (hash and redact) stored nothing:
`record_invalid`. The run itself is fine. Its manifest carries an engine warning that
`EvidencePayload.warnings` refuses:

```
code: out_of_core_caller_managed_residency
provider: ""                                  # Name needs at least 1 character
detail: {"shapes": [..two strings..], "message": "..."}   # detail values must be scalars
```

The engine attaches that warning on the out-of-core route whenever the caller passes resident
tables, so CLI runs on that route warn `record_invalid` every time and store no evidence record.
Following 4.17, the exit code is unchanged.

Two places can fix it, and they are not mine to choose:
- (a) The engine `EvidenceWarning` accepts what the CLI writes: an empty or null `provider`, and
  lists of scalars in `detail`. This is an engine slice and release, then a repin.
- (b) The CLI manifest normalizes engine warnings before hashing: `""` becomes `null`, and a list
  detail becomes a count or a joined string. This changes the `cli-local-1` files `--evidence-out`
  writes.

## Checks

The slice changes a default (every successful run now writes under `.decoy/`) and a frozen
`--json` shape. Both are full-suite triggers, so the whole suite ran at the slice.

`scripts/dev/gates.sh --keep-going tests` on `2124e17`:

| Step | Result |
|---|---|
| env | PASS |
| ruff | PASS |
| sentry | 1431 passed, 2 failed |
| layers | 23 passed |
| tests (whole `tests/`) | 6556 passed, 25 skipped, 2 failed |

- **The two failing ids** are `tests/sentry/layout/test_codemap_paths.py::test_every_path_in_the_codemap_layout_section_exists`
  and `::test_a_missing_concrete_path_in_the_section_is_red`. My CODEMAP row named
  `cli/run/_evidence.py` without `src/decoy/`. `e7e76d9` fixes it, and that file then passes
  (6 passed).
- **Main baseline.** Main `4e6d60b` is green in CI. No main-side full suite ran (the rule is to
  diff against the stored baseline), so no other failing id is attributed to main.
- **An earlier full run** on a superseded head found 19 failures. One was my mistake: a
  `ruff format` over all of `src/` and `tests/` had reformatted unrelated files (`scan.py` then
  tripped the module-size census). The two commits were rebuilt with only this slice's files.
  The other 18 came from the new default and are fixed in `b7c6d9f`:
  - G-LIB-FS: the label's `Path.resolve` was in the library module.
  - The sentry manifest was missing the new sentry file.
  - `--all` forwarding had no `--no-library` sample.
  - Seven tests that compare two runs' `--json` now ignore the per-run record id.
  - Two layout guarantee tests now list the library files a run writes.
- **Format.** No format gate is in `ci.yml`. The files this slice touches pass `ruff format --check`.

## OS lanes

- Linux: run.
- macOS and Windows: not required (plan 5.1: L3a is Linux only).

## Not run

mypy (no gate in `ci.yml`). The run-result half and `report ... <id>`.

## Deviations

1. **`--library DIR` is not on `decoy run` yet.** The plan's file list for L3a names only
   `--no-library`, and 4.16's `--library` mention refers to the root rule. `DECOY_LIBRARY=<dir>`
   moves the records today.
2. **`report show/verify/diff <id>` (L3-report-id) is left to a second part.** `report.py` is
   2382 lines and must not grow. Routing it through one library call is a separate, reviewable
   change, and it does not block the default write.
3. **Paths are stored as the manifest has them.** That is project-relative inside a project and
   absolute outside one. The amendment's "built once and stored as built" replaces the earlier
   "relativized by the kind spec" text. Export strips the declared path fields.
4. **`/library` is an opaque object in the frozen `--json` shape.** Its members depend on the
   store outcome, so the snapshot holds the key's presence and type.

## V2-LOG

- The pipeline label rule here is a few lines in `cli/run/_evidence.py`. L4a (#215) adds
  `decoy.cli.io.project_relative_posix` for the same rule; once both are on main, the label should
  call it.
- `decoy library list` on a project after this lands shows evidence rows. `library show` of one
  prints raw warning text, which is #215's V2-LOG a.
