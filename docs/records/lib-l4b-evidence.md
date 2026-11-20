# LIB L4b (prune, export, clean): build evidence

Slice L4b of the LIB plan (`plan/local-record-library:docs/plans/2026-11-05-local-record-library.md`,
revision 7: slice L4b-cli, sections 4.7, 4.8, 4.11, 4.3a and 4.15). Branch `feat/lib-l4b-prune`
from `origin/feat/lib-l4a-read` at `f15bf45`.

`prune` and `clean` were built first (code head `16ba70d`). `export` stopped twice on an owner
decision, and both decisions were taken on 2026-11-12:

1. **Accept the engine 0.22.0 export codec's behavior** (option (a) below). The three plan rows
   it contradicts are rewritten. The CLI is a thin call over `records.export_lines`.
2. **The file flag is `--output`/`-o`, not plan 4.15's `--out`.** The slice B1 sentry
   `test_no_standalone_out_flag_in_source` (on main) allows only `--output`/`-o`. The sentry is
   unchanged.

The final code head is `b11aed3`. This record is the only later commit (Markdown only).

## Environment

- OS: Linux 6.18.44 (x86_64), ext4, run as uid 0 in a container.
- `python -V`: Python 3.10.20 (`.venv`, matches `requirements-dev.lock`).
- Engine: `decoy-engine` 0.22.0.
- Code heads the checks ran on: `16ba70d` (prune, clean), then `b11aed3` (export, final).

## The export codec gap (exact; resolved by owner decision 1)

`decoy_engine.records.export_lines(records, *, producer, exported_at, refs, keep_paths, logs)` in
0.22.0, without `keep_paths` (the default export):

- **Withholds a record of a kind this version has no model for** (`kind_spec(kind)` is None):
  it is left out, and its id goes into the header's `withheld_records`.
- **Withholds a record whose payload carries a field this version does not know** (a newer CLI,
  same payload tag). `_strip` validates the payload with the strict write model, the extra field
  fails it, and the record is left out and listed under `withheld_records`.
- Uses `unstripped` only for records that had a remote locator removed.

Measured on this node (a known record, a newer-CLI record and an opaque record linking to the
known one): the default export holds 1 record and `withheld_records` 2; `keep_paths=True` holds
all 3, byte for byte.

The plan's rows expect the opposite in a default export:

| Plan row | Expects | Codec (default) |
|---|---|---|
| L4b-export-newer | the newer record keeps its bytes and id, listed under `unstripped` | left out, listed under `withheld_records` |
| L4b-export-unknown | the opaque record is exported with payload and id unchanged | left out, listed under `withheld_records` |
| L4b-export-closure | opaque and newer payloads byte for byte; every link resolves inside the export; `external_links` 0 | both left out |

Plan 4.3a ("`export` copies it byte for byte ... lists its id under `unstripped`") and 4.11
("Raw payloads ... keeps its payload byte for byte ... listed in the header under `unstripped`")
describe the plan's design. The engine chose to withhold, because this version cannot prove such
a record carries no path. The codec is the engine's, and the CLI may not reimplement stripping or
remapping, so the CLI cannot meet those rows.

Options for the owner:

- (a) Accept the engine semantics. Rewrite the three rows as "a default export withholds them and
  lists them in `withheld_records`; `--keep-paths` exports them byte for byte". `export` is then
  a thin CLI call over the codec (link-order input, refs, the user-path atomic write). No engine
  change.
- (b) Change the engine codec to export opaque and newer records unchanged in a default export
  and list them under `unstripped`. This is an engine slice plus a repin, and a change to the
  `decoy-library-export/v1` semantics.

**Owner decision 1: (a).** The other plan rows (L4b-export-import, -remap and -scratch) hold
with the codec as the plan states them. Remap holds because the CLI hands records over in link
order.

## Commits

| Commit | What |
|---|---|
| `15cd1b2` | red-first `tests/unit/library/test_prune.py`, `tests/e2e/library/test_library_destructive.py` |
| `16ba70d` | `_prune.py`, `_destructive.py` (`prune`, `clean`), `_scratch.clean_all` and single-file `delete_tree`, `_index.delete_row`, `Library.object_path` and `index_row`; `docs/cli-reference.md` regenerated; docs, CHANGELOG, CODEMAP |
| `b5ab2dc` | the first version of this record (the export stop) |
| `655a2e3` | red-first `tests/e2e/library/test_library_export.py`; shared builders moved to `tests/e2e/library/_records.py`; private-file case key renamed |
| `fda6092` | `_export.py` (`export`), `_fs.write_user_file`; docs, CHANGELOG, CODEMAP, `docs/cli-reference.md` |
| `b11aed3` | the flag is `--output`/`-o` (owner decision 2); docs and reference regenerated |

## Red first: prune and clean (`15cd1b2`)

`pytest tests/unit/library/test_prune.py tests/e2e/library/test_library_destructive.py --continue-on-collection-errors`:
**9 failed, 3 passed, 1 skipped, 1 error.**

- 1 collection error: `test_prune.py`, because `decoy.cli.library._prune` did not exist.
- 9 e2e failures: there were no `prune` or `clean` commands.
- 3 passes: the bad-argument cases, which assert only a non-zero exit, and Click's "no such
  command" already gave one. They pass for the intended reason after `16ba70d`.
- 1 skip: the Windows-only case.

## Red first: export (`655a2e3`)

`pytest tests/e2e/library/test_library_export.py` on `655a2e3`: **12 failed** (all 12 cases).
There was no `export` command, so every invocation exited with Click's usage error. Each test also
carries a non-vacuity assertion (data seeded and present before the export is checked).

## What was built

- **`_prune.py`: `prune_preview` and `prune_apply`** are separate functions with no behavior
  flag.
  - Both refuse a degraded library (`library_lock_unavailable`). Both take the library lock,
    catch the index up, and resolve the targets from the index under it.
  - Rules: per kind, keep the newest N, and/or delete only records older than D; with both, a
    record must meet both.
  - Never deleted:
    - records reachable from a ref, or from any kept record, through links (transitively);
    - records younger than one hour (`GRACE`);
    - unknown-kind and newer-payload rows (`known = 0`), which also count as roots, so their link
      targets are kept.
  - Apply unlinks each object file. A failure (`PermissionError`, held open) is reported in
    `left`, and the file and its index row stay. The index row is deleted only after the file is
    gone.
  - `policy_rules(root)` turns `.decoy/library.yaml` `keep_last` rules into prune rules; the
    default keeps all.
- **`decoy library prune [--kind K] [--keep-last N] [--older-than D] [--yes] [--library DIR]`**
  - Without `--yes` it prints `would delete <id>` for each exact id, plus counts (to delete, kept
    by a ref or link, younger than an hour), and deletes nothing.
  - With `--yes` it prints each deleted id and each one left behind; exit 4 if any is left.
  - With no options it applies the policy (or says the policy keeps all).
  - A bad `--keep-last` or `--older-than` exits 1; degraded mode exits 3.
- **`decoy library clean [--yes] [--library DIR]`**
  - Previews each `scratch/` entry, then with `--yes` removes them through
    `Library.delete_scratch` under the library lock.
  - Each file left behind is listed; exit 4. Degraded mode exits 3.
  - Only `.decoy/scratch/` is touched.
- **`_export.py`: `decoy library export --output/-o FILE [--kind K] [--since D] [--ref R]
  [--include-logs] [--keep-paths] [--library DIR]`.**
  - `select` picks the records: all of them, or `--ref R` plus everything reachable from it
    through links, then `--kind` and `--since` filters.
  - `link_order` puts every link target before the record that links to it (Kahn's order,
    ties by `(created_at, id)`). The codec builds its id map in input order.
  - It hands over raw verified envelopes (`Library.get(id).raw`, never a typed view) and the refs
    to `records.export_lines`. The CLI does no stripping, remapping or id recomputation.
  - The lines are written through `_fs.write_user_file`: the atomic writer, replace mode, 0600.
  - A default export withholds unknown-kind and newer-payload records, as the codec decides.
    One stderr notice gives the count and the ids, and points to `--keep-paths`.
  - `--keep-paths` exports every record byte for byte.
  - Scratch is never read.
  - **`--include-logs` exports no logs until L5b** (job logs do not exist yet). It prints a
    stderr notice saying so, and `docs/library.md` documents it.

## Rewritten export rows (owner decision 1)

| Row | Plan said | Now asserts |
|---|---|---|
| L4b-export-newer | newer record exported with bytes and id kept, listed under `unstripped` | default: withheld, listed in `withheld_records` and the stderr notice, library file untouched; `--keep-paths`: exported byte for byte, newer field present, no `source_id` |
| L4b-export-unknown | opaque record exported with payload and id unchanged | default: withheld, listed and named on stderr; `--keep-paths`: exported as an `OpaqueRecord`, byte for byte |
| L4b-export-closure | opaque and newer payloads byte for byte; every link resolves; `external_links` 0 | for both modes: `external_links` 0 and every link resolves inside the export; default withholds both, `--keep-paths` withholds none; every envelope verifies and `source_id` stays outside it |

L4b-export-import, -remap and -scratch are tested as the plan states them.

## Mutations (`mutate_l4b.py` and `mutate_export.py`; each applied once and restored; `src` clean)

| Mutation | Change | Test | Result |
|---|---|---|---|
| ML4-apply | preview unlinks the planned files | `test_preview_lists_exact_ids_and_deletes_nothing`, `test_prune_previews_exact_ids_then_deletes_with_yes` | red, both |
| ML4-noreach | reachable = kept records only (refs and links ignored) | `test_records_reachable_from_a_ref_or_a_kept_record_survive` | red |
| ML4-nograce | no grace period | `test_a_record_younger_than_an_hour_survives` | red |
| ML4-nograce | same | `test_prune_while_another_process_puts` | green: the prune finished before the child (about a second of engine import) wrote anything. The grace rule is held by the unit test above |
| ML4-unlocked | apply uses a plain SQLite connection, no `BEGIN IMMEDIATE` | `test_prune_waits_for_the_lock_and_deletes_nothing_while_it_is_held` (a child holds the lock; prune must fail `library_busy` and delete nothing) | red |
| ML4-prune-unknown | kind rules applied to opaque rows | `test_an_opaque_record_and_what_it_links_to_are_never_pruned` (both parametrized cases) | red |
| ML4-wide | clean removes the whole library root | `test_clean_previews_then_removes_only_scratch` | red |
| ML4-clean-raise | the first `PermissionError` escapes | `test_clean_lists_a_held_file_and_exits_4` | red |
| ML4-paths | export passes `keep_paths=True` always | `test_export_then_read_gives_the_same_ids_and_strips_only_path_fields` | red |
| ML4-scratch | every file under `scratch/` handed to the codec as log lines | `test_no_option_exports_scratch` | red on the 2 `--keep-paths` cases (the codec writes logs only with `--keep-paths`) |
| ML4-export-view | payload taken from the typed view, not the raw envelope | `test_a_newer_record_is_withheld_by_default_and_kept_byte_for_byte_with_keep_paths` | red |
| ML4-skip-unknown (rewritten) | unknown kinds left out of selection | `test_an_opaque_record_is_withheld_by_default_and_kept_with_keep_paths` | red |
| ML4-skip-unknown (rewritten) | withheld ids not reported on stderr | the opaque and newer tests | red, both |
| ML4-no-remap | records handed over out of link order (the CLI-boundary form: the codec's id map then misses link targets) | `test_links_and_refs_point_at_the_new_ids_after_stripping` | red |
| ML4-strip-all | | | engine-owned, not applied (stripping is in the codec; no faithful CLI-boundary form) |
| ML4-verbatim-links | | | engine-owned, not applied (link rewriting is in the codec; no faithful CLI-boundary form) |

The export mutations ran on `b11aed3`. No survivors.

## Checks on `16ba70d` (prune, clean)

| Command | Result |
|---|---|
| `.venv/bin/pytest tests/unit/library tests/e2e/library tests/sentry -q -p no:cacheprovider` | 1291 passed, 7 skipped (Windows/macOS-only cases) |
| `.venv/bin/ruff check src tests` | pass |
| `ruff format --check` on the `.py` files changed since the base | 8 files already formatted |
| `uvx mypy --python-executable .venv/bin/python src/decoy`, compared with base `f15bf45` | no new error (161 on both) |
| `bash scripts/dev/gates.sh --steps layers` | PASS 22/22 |
| impact selection (`tests/unit/library tests/e2e/library tests/unit/test_cli_surface.py tests/unit/test_surface_docs_consistency.py tests/unit/test_no_dead_command_strings.py tests/sentry/cli_text tests/e2e/test_stateless_cli.py tests/unit/private_file`) | branch 346 passed, 7 skipped; base (`PYTHONPATH=<worktree>/src`) 323 passed, 6 skipped |
| real run: `prune --keep-last 1`, then with `--yes`, then `clean`, `clean --yes`, `list` | as expected: exact ids previewed, deleted with `--yes`, scratch removed, one record left |

Failure sets: branch none; base none. `decoy --help` still imports no engine code.

## Checks on `b11aed3` (final code head)

| Command | Result |
|---|---|
| `.venv/bin/pytest tests/unit/library tests/e2e/library tests/sentry tests/unit/test_surface_docs_consistency.py tests/unit/test_cli_surface.py -q -p no:cacheprovider` | 1315 passed, 7 skipped |
| `.venv/bin/ruff check src tests` (repo root) | last line: `All checks passed!` |
| `ruff format --check` on the 7 `.py` files the export commits touched | 7 files already formatted |
| `uvx mypy --python-executable .venv/bin/python src/decoy`, compared with base `b5ab2dc` (line numbers stripped) | no new error (161 on both) |
| `bash scripts/dev/gates.sh --steps layers` | PASS 22/22 |
| impact selection (the list above plus `tests/sentry/io_policy/test_private_files.py`) | branch 392 passed, 7 skipped; base `b5ab2dc` (`PYTHONPATH=<worktree>/src:<worktree>`) 380 passed, 7 skipped |

Failure sets: branch none; base none. Before `b11aed3` the branch set was
`test_no_standalone_out_flag_in_source` (the `--out` flag), which owner decision 2 resolved.
No `--out` spelling remains in `src/decoy/cli/library`, its tests, `docs/library.md`,
`docs/cli-reference.md` or CHANGELOG.

## Sentry registrations

None. The private-file census is unchanged at 61/23 (deletes are not watched sinks). Export
writes through the existing `_fs._write_local` site, whose `PRIVATE_CASES` key was renamed to
`cli/library/_fs.py::_write_local::write_local_target::1`, with no new site. No baseline or
allowlist changed. The flat `src/decoy/cli/` is unchanged.

## OS lanes

- Linux: run.
- macOS: NOT RUN (no runner).
- Windows: NOT RUN (no runner). `test_clean_with_a_file_held_open_on_windows` (L4b-clean-open) is
  written and skip-marked; the Linux case forces the `PermissionError` path.

## Not run

The full suite, the macOS and Windows lanes, and mypy from `.venv`. The `--include-logs`
export of real logs waits on L5b.

## Deviations

1. **Export follows the engine codec** (owner decision 1): three plan rows rewritten.
   **The flag is `--output`/`-o`** (owner decision 2), not plan 4.15's `--out`.
2. **`--keep-last` and `--older-than` together** delete only records that meet both rules.
3. **Prune's preview takes the library lock too** (read-only), so preview and apply resolve
   against the same caught-up index, and a degraded library refuses both.
4. **A newer-payload record** (indexed with `known = 0`) is protected like an opaque record.

## V2-LOG (noticed, not built)

- A `--json` form for `prune`, `clean` and `export` (4.15 has none).
- `--include-logs` should export the run logs once L5b writes them.
- Plan 4.3a and 4.11 still describe `unstripped` for opaque and newer records, and 4.15 still
  says `--out`; the plan should be revised to match both owner decisions.
- Prune could also sweep empty fan-out folders under `objects/`.
- The concurrent test could hold the child until the prune starts (a barrier) to also exercise
  the grace rule under concurrency.

## Re-check on the main-merged head after review round 2 (2026-11-17)

`b393840` merges the updated #215 (`123831d`: main at `4e6d60b`, the `diff_scan_sets` move,
the `library path` wrap fix). The merge was clean. The checks above ran on older heads, so the
round-2 fixes and every mutation were rerun here.

- OS: Linux 6.18.44 (x86_64), ext4, uid 0 in a container.
- `python -V`: Python 3.10.20 (`.venv`, `scripts/dev/bootstrap.sh` OK against `requirements-dev.lock`).
- Engine: `decoy-engine` 0.27.0 (commit `ddd014a`).
- Main: `4e6d60b`. Code head the checks ran on: `b393840`. This record is the only later commit
  (Markdown only).

**Round 2 (Codex, head `31d8ce1`).** Fixed in `399ebfd` after the red cells in `81a3dfb`:

| Item | Fix | Red at `81a3dfb` (worktree, `PYTHONPATH` to its `src`) | Green at `b393840` |
|---|---|---|---|
| V1-A | `_inventory` counts a ref or a link that names a missing record as unexplained; `export` refuses before writing; `--ref` checks its closure is all indexed | `test_an_export_whose_record_links_to_a_missing_record_refuses` (exit 0, 1 record written), `test_an_export_with_a_dangling_ref_refuses[named-ref]` and `[whole-library]` (exit 0) | yes |
| DESIGN-B | `_fs.write_export` is the one checked write, built on `_atomic.destination_entry`; `_exporting.py` has no path inspection; G-LIB-FS seeds `os.path.realpath` and `os.path.islink` | `test_export_writes_through_one_checked_entry_point` | yes |
| DESIGN-C | one parser, `_index.parse_instant`, exposed through the facade and used by `_read`, `_prune` and `_exporting` | `test_one_timestamp_parser` | yes |

**T1** (`scripts/dev/gates.sh --keep-going --baseline` with paths `tests/e2e/library tests/unit/library
tests/e2e/first_user/test_items_error_envelope.py tests/e2e/release_freeze tests/unit/test_cli_surface.py
tests/unit/test_report.py tests/e2e/test_report_diff_command.py tests/e2e/test_stateless_cli.py`;
the sentry step runs all of `tests/sentry`):

| Step | Branch `b393840` | Main `4e6d60b` |
|---|---|---|
| env | PASS | (same venv) |
| ruff | PASS | PASS |
| sentry | 1432 passed | 1432 passed |
| layers | 23 passed | 23 passed |
| tests | 475 passed, 7 skipped | 375 passed, 6 skipped |

Failure sets: branch none; main none; branch-only none. The extra skip is the Windows-only
`test_clean_with_a_file_held_open_on_windows`.

**Mutations on `b393840`** (`mutate_l4b.py`, rewritten for the post-review code; each applied
once by exact string replace, its tests run, the file restored; `src` clean after):

| Mutation | Change | Tests | Result |
|---|---|---|---|
| ML4-apply | preview removes the planned files | `test_preview_lists_exact_ids_and_deletes_nothing`, `test_prune_previews_exact_ids_then_deletes_with_yes` | red (2 failed) |
| ML4-noreach | `reachable = set(kept)` (refs and links ignored) | `test_records_reachable_from_a_ref_or_a_kept_record_survive` | red |
| ML4-nograce | `young = set()` | `test_a_record_younger_than_an_hour_survives`, `test_prune_while_another_process_puts` | red (the unit test; the concurrent test stays green, as before) |
| ML4-unlocked | apply on a plain autocommit SQLite connection, no lock | `test_prune_waits_for_the_lock_and_deletes_nothing_while_it_is_held` | red |
| ML4-prune-unknown | kind rules applied to opaque rows | `test_an_opaque_record_and_what_it_links_to_are_never_pruned` | red (both cases) |
| ML4-wide | `clean_all` also removes the whole root | `test_clean_previews_then_removes_only_scratch` | red |
| ML4-clean-raise | `clear_tree` re-raises the `PermissionError` | `test_clean_lists_a_held_file_and_exits_4` | red |
| ML4-paths | export always `keep_paths=True` | `test_export_then_read_gives_the_same_ids_and_strips_only_path_fields` | red |
| ML4-scratch | scratch files handed to the codec as logs | `test_no_option_exports_scratch` | red (4 cases) |
| ML4-skip-unknown | only `DecodedRecord`s handed to the codec | `test_an_opaque_record_is_withheld_by_default_and_kept_with_keep_paths` | red |
| ML4-skip-unknown (notice) | withheld ids not reported | the opaque and newer export tests | red, both |
| ML4-no-remap | records handed over in reverse link order | `test_links_and_refs_point_at_the_new_ids_after_stripping` | red |
| ML4b-closure (V1-A) | `_inventory` stops counting dangling refs and links | the missing-link and dangling-ref cells | red (missing link and `whole-library`; `named-ref` is also held by the `--ref` closure check, so it stays green) |
| ML4b-unexplained | `require_explained` never raises | the unreadable-ref, unreadable-kept-record and cannot-verify cells | red (3 failed) |
| ML4b-destination (DESIGN-B) | `write_export` ignores `unsafe` | `test_export_into_the_library_is_refused`, `test_export_through_a_final_symlink_is_refused` | red (2 failed) |

ML4-export-view, ML4-strip-all and ML4-verbatim-links stay engine-owned, as recorded above.

**OS lanes on this head.** Linux: run. macOS: NOT RUN (no Mac runner reachable from this
session). Windows: NOT RUN (no Windows node). The plan requires both for L4b; they are open.

Not run on this head: the full suite, mypy, macOS and Windows lanes. CI: see the PR checks on the
pushed head.

## Review round 3 (Codex, head `e334e2c`): export closure

**Finding (V1).** Export could exit 0 with a set that is not closed, in two ways:
- `--kind` and `--since` filtered records without adding what they link to.
- The codec could withhold an opaque or newer dependency while keeping a known record that links
  to it.

Both gave `external_links > 0` against the closure contract above.

**Rule (also written into the plan's L4b section, `plan/local-record-library` `b08b091`).**
- Filters (`--kind`, `--since`, `--ref`) choose the starting records only. Export then adds every
  record they link to, transitively, whatever its kind or date (`_exporting.closure`, over
  `_index.reachable`, the walk prune uses).
- If the codec withholds a record, every record that links to it, directly or not, is withheld
  too. It is listed in the header's `withheld_records` and named in its own stderr notice, and a
  ref to any withheld record is left out of the header.
- As a last check, export refuses with `export_not_closed` before writing if the codec reports
  `external_links > 0`.

**How.**
- `export_lines` runs the codec once and reads which records it withheld.
- In link order, it marks every record that links to a withheld one.
- It reruns the codec without those records, with the refs to any withheld record removed.
- It adds the marked ids to the header's `withheld_records`, keeping the header in the codec's
  canonical form. The header is not revalidated in the CLI (G-config-error-routes forbids a
  CLI-side engine model validation); `records.read_export` validates it on import, and every test
  reads exports through it.
- The codec still decides what it can strip: the CLI does not repeat that rule.

| Commit | What |
|---|---|
| `76e2609` | red cells (on `e334e2c`): `test_a_filter_pulls_in_every_record_a_kept_record_links_to[--kind, --since]`, `test_a_record_that_links_to_a_withheld_record_is_withheld_too`, `test_export_refuses_before_writing_a_set_that_would_not_be_closed`; 4 failed, for the stated reasons (linked records missing; dependents exported; no refusal) |
| `ff0b77b` | the fix: `closure`, withheld dependents, `export_not_closed`, `ExportLines`, the two stderr notices, `--kind`/`--since` help |
| `f0b5074` | merge of #215 at `9609f8d` (main `c558e2f`); `docs/cli-reference.md` regenerated |
| `d51c5ac` | `docs/library.md`, CHANGELOG |
| `cfbe3f0` | the header is extended without a CLI-side `ExportHeader.model_validate` (T1 on `d51c5ac` caught it: `tests/sentry/defects/test_config_error_routes.py`) |

**Environment.** Linux 6.18.44 (x86_64), ext4, uid 0 in a container; Python 3.10.20; engine
0.27.0 (`ddd014a`); main `c558e2f`.

**T1 on `cfbe3f0`** (`scripts/dev/gates.sh --keep-going --baseline`, same paths as above):

| Step | Branch `cfbe3f0` | Main `c558e2f` |
|---|---|---|
| env | PASS | (same venv) |
| ruff | PASS | PASS |
| sentry | 1433 passed | 1433 passed |
| layers | 23 passed | 23 passed |
| tests | 482 passed, 7 skipped | 378 passed, 6 skipped |

Failure sets: branch none; main none; branch-only none. The one branch-only id on `d51c5ac`
(`test_config_error_routes.py::test_no_raw_validation_error_route_in_src`) is fixed in `cfbe3f0`.

**Mutations on `cfbe3f0`** (all applied once by exact string replace, tests run, file restored; `src` clean after):

| Mutation | Change | Result |
|---|---|---|
| ML4-apply, -noreach, -nograce, -unlocked, -prune-unknown, -wide, -clean-raise | as in the round-2 table | red, each (ML4-nograce: the unit test; the concurrent test stays green, as before) |
| ML4-paths, -scratch, -skip-unknown (both forms), -no-remap | as in the round-2 table | red, each |
| ML4b-closure (V1-A) | `_inventory` stops counting dangling refs and links | red (the missing-link cell). Both dangling-ref cases are now also refused by the closure check (`chosen <= rows`), so they stay green under this mutation |
| ML4b-unexplained, ML4b-destination | as in the round-2 table | red, each |
| ML4-no-closure | `chosen = set(start)` | red (both filter cells) |
| ML4-keep-dependents | records linking to a withheld one are never marked | red |
| ML4-no-last-check | the `external_links` refusal removed | red (the last-check cell) |

ML4-no-last-check is red only through the cell that breaks the closure step on purpose: with the
closure and withholding correct, the check cannot fire, by construction.

**Not run on this head.** macOS lane: no runner reachable from this session. Windows lane: no
node. CI: none, because the base is the #215 branch. The full suite.
