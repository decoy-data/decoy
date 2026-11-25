# 24zk PROP-SHIMS D6 manifest half: `report diff` refuses an evidence manifest entry with no `format`

Status: plan
Revision: 3
Repo: decoy (CLI), branch `docs/plans-prop-shims-d6-manifest`, planned against CLI `origin/main`
`fffca916`.
Parent: engine `docs/plans/2026-11-16-prop-batch.md` (revision 7, branch
`docs/plans-prop-reanchor-1125`), item D6 and AT-D6. The saved-scan half of D6 merged as CLI #313
(`41832f22`). This plan is the remaining manifest half, so row 24zk can close.
Rules consulted: README, 00-universal, risk-and-exceptions, development-loop,
api-and-compatibility, testing, security, proportionality.
Risk: R1 (bounded, reversible, one reader path; no writer change). The change removes a
compatibility reader of the frozen `cli-local-1` payload, which is a full-suite escalation
trigger, so T3 runs on the merge head. Reviews: plan Dennis then Codex; code gate Codex only.

Revision 2 folds Dennis R1 (8 should-fix, 7 low): deviations from the parent stated (section
2a), frozen-shape claim corrected, the second fallback test named, AT-4 rebuilt, both sides
checked before any read, M-5 defined once, `entry_format` loses its unused `path`, stale legacy
text listed, AT-6 replaced by existing tests, no new export.

Revision 3 folds Codex R1 (2 V1, 1 DESIGN, 5 low): a one-sided table entry is checked too; each
side is checked on its own so the codes do not depend on argument order; the hint lives only in
the exception message and one block records refused or unreadable paths; AT-4 covers human and
JSON modes; M-1 and M-3 made executable; full run before the code gate; anchors corrected.

## 1. Problem

`entry_format` (`src/decoy/cli/io/_targets.py:302`) reads an evidence-manifest output entry back
for `decoy report diff`. An entry with no `format` key falls back to `_legacy_format_for_path`
(`_targets.py:240-245`): `.parquet` is Parquet, everything else CSV. The parent plan (D6) removes
this shim before 1.0 and refuses such an entry with a coded, value-free error.

CLI #313 deferred this half because `report.py` was over the size cap. The CLI split moved it to
the `src/decoy/cli/report/` package (`_compare.py` 312 lines, `_diff.py` 361 lines), so the size
reason is gone.

Every current writer records `format` for a file target (`src/decoy/cli/evidence.py:313-317`
with `_format_keys` at `evidence.py:179-196`), and no non-file target can carry `path` (the
engine's `S3Target` and `GCSTarget` forbid extra fields). Only manifests written by main builds
between the evidence writer (`7de0d22f`) and format recording lack it; CLI 0.1.0 predates the
evidence writer. No CLI release since 0.1.0 has shipped, and format recording is in the CHANGELOG `[Unreleased]` block as a pre-1.0 breaking
change.

## 2. Guarantee and non-goals

Guarantee: `decoy report diff` never reads a manifest output entry that has no `format` key, and
reads neither side of that table when one side lacks it. It reports the code
`target_format_unrecorded` after `refused:` in its error, note and JSON `data_note`, followed by
a fixed hint. Neither holds a cell value. With `--require-data` it exits 1 (`EXIT_USAGE`, the
existing exit for unreadable outputs). Without it, the data level is `skipped`, as for any
unreadable output today.

Non-goals:
- No change to the manifest writer, `cli-local-1`, `manifest_hash` or `report verify`. An old
  manifest still verifies (`tests/unit/cli_fmt/test_evidence_target_format.py:60-78` stays green).
- No new exit code and no new JSON key in `report diff`.
- No migration tool for old manifests. Re-running the pipeline writes a current one.
- The raw manifest path strings that `report diff` already prints for a missing or unreadable
  output stay as they are (they are the user's own paths, not cell values).
- `_compare.py:231` stops at the first missing or refused table (existing behaviour), so
  `refusals` lists refusals found up to that table. Logged, not changed.
- The parent plan's other D items, and every 24zi and 24zj slice.

## 2a. Deviations from parent D6

- Code name: the parent (section 4 D6 row, `prop-batch.md:589`) names `io.manifest_format_missing`.
  This plan uses `target_format_unrecorded`, because the code is raised by `_targets.py` beside
  its siblings `target_format_unreadable` and `target_format_unknown` (`_targets.py:53-58`); one
  family per module.
- Exit: parent AT-D6 says "exits 1 with its code". Here exit 1 holds under `--require-data`;
  without it `report diff` keeps its documented degrade contract (exit 0, data level skipped,
  code in the note), the same as for a corrupt or missing output.
- Both are technical choices, not owner calls. The slice amends the parent's D6 row and AT-D6
  text to match (Done when).

## 3. Established solutions

Search run: the CLI tree for existing refusal patterns of a retired on-disk shape, and the
parent plan's D-item rules. Found: CLI #313 refused an untagged saved scan with one coded
`ScanSetFormatError` and a fixed message (`src/decoy/cli/io/_scan_set.py`,
`SAVED_SCAN_SCHEMA_UNSUPPORTED`). The `TargetFormatError(code, message)` class at
`_targets.py:78` already carries codes for the same reader (`UNREADABLE` at `_targets.py:56`).
This plan follows those two patterns. No external research applies: the change deletes a branch
and adds one coded refusal through an existing error type.

## 4. Design

4.1 `_targets.py`: add `UNRECORDED = "target_format_unrecorded"` beside the other codes
(`_targets.py:53-58`). Not exported from `decoy.cli.io`: its siblings are not either, and tests
import them from `decoy.cli.io._targets`. `entry_format` drops its `path` parameter (it is used
only by the fallback) and becomes `entry_format(recorded)`. With no `format` it raises
`TargetFormatError(UNRECORDED, "the evidence manifest entry records no format (written before
format recording); re-run the pipeline to write a new manifest")`. Delete
`_legacy_format_for_path` and the legacy sentence of the docstring (`_targets.py:307-308`).

4.2 `src/decoy/cli/report/_compare.py` `compare_data` (`_compare.py:158`):
- One local helper, `_entry_refusal(entry) -> TargetFormatError | None`, calls
  `entry_format({k: entry[k] for k in ("format", "layout") if k in entry})` and returns the
  error instead of raising. Each side is checked on its own, so a pair with one `format: xml`
  side and one side with no `format` yields both codes in either argument order.
- One-sided table (`_compare.py:201-216`): before recording the "only exists in one run" delta,
  the present entry is checked. A refusal records the refusal and its raw path and skips the
  delta; a current entry keeps the existing delta. Covers added and removed tables.
- Two-sided table: after the path check (`_compare.py:225-232`), both sides are checked. Any
  refusal records every refusal and both raw paths, then `continue`; only when both pass are the
  two `read_file` calls made, under the existing `except (OSError, ValueError, DecoyError)` arm.
- One block records a skipped side: a local `_skip(raws, refusals=())` appends the raw paths to
  `missing_files` (deduplicated, as today at `_compare.py:242-244`) and adds each
  `(err.code, str(err))` pair to a `refusals` set. Both the refusal path and the generic read arm
  call it.
- The result dict gains `"refusals": sorted(refusals)` (pairs of fixed code and fixed message).
  It is needed because the generic arm drops the code, and the code is the only thing that tells
  a user why the file was not compared.
- Update the docstring (`_compare.py:170-172`) and the comment at `_compare.py:234`, which still
  describe the legacy suffix rule.

4.3 `src/decoy/cli/report/_diff.py`: one function `_refusal_text(refusals)` builds
`"refused: " + "; ".join(f"{code}: {message}" ...)`. The remediation hint is only in the
exception message (4.1), so every mode prints the same text. Append it with `"; "` to the
`--require-data` message (`_diff.py:130-135`); set the existing skipped-branch `data_note` key
(`_diff.py:162-167`) to it when there is no dependency error; in the human note
(`_diff.py:221-229`) say "output files missing or refused (...)" and append it. Codes and
messages are fixed text, never data.

4.4 Docs: `src/decoy/cli/evidence.py` module docstring (`evidence.py:21-29`) states that an entry
without `format` is refused by `report diff` with `target_format_unrecorded`. The `_format_keys`
docstring (`evidence.py:180-185`) says such an entry has no format and `report diff` refuses it,
and that the branch cannot fire after the gate. CHANGELOG `[Unreleased]`: one line under the
existing `### Breaking` subsection (`CHANGELOG.md:12`), and the parenthetical at the end of the
format-recording entry (`CHANGELOG.md:242`, "older manifests are read by suffix as before")
changes to say they are refused.

## 4a. Enumerations

### Exit paths

- `report diff --require-data`, old entry on either side: exit 1 (`EXIT_USAGE`) at
  `_diff.py:146`; the message names the raw manifest path strings (as today) plus the refusal
  text.
- `report diff` without `--require-data`, old entry: exit 0, `data_level: skipped`, note and
  `data_note` carry the refusal text.
- `report diff`, both entries carry `format`: unchanged (exit 0, `data_level: compared`).
- `report verify`, old manifest: unchanged, exit 0 when fingerprints match (no read by format).

### Routes

- `report diff` data level: `_diff.py:113` calls `compare_data`, which calls `entry_format` at
  `_compare.py:237-238`. The only production caller of `entry_format`.
- `report verify` and `run --evidence-out`: do not call `entry_format`; untouched.

### FK shapes

N/A: the change reads no tables relationally and touches no key handling; it refuses a manifest
entry before either side's file is read.

### Fields

- `output_fingerprints.<table>.format`: absent now means refusal (was the legacy suffix rule).
- `output_fingerprints.<table>.layout`: unchanged; read only when `format` is `fixed_width`.
- `report diff` JSON `data_note`: existing optional string on the skipped branch, now also set for
  a refusal.
- `compare_data` result `refusals`: new internal key, never emitted as its own JSON key.

### Output surfaces

- `report diff` JSON payload (`_diff.py:149-168`): no new key; `data_note` value only.
- `report diff` stderr error and human note (`_diff.py:136-143`, `_diff.py:221-229`).
- No log lines are added.

## 4b. Reuse inventory

- `TargetFormatError` and its `code` attribute (`_targets.py:78`): reused, no new error class.
- The `missing_files` degrade path and `--require-data` exit (`_diff.py:124-146`): reused.
- The existing `data_note` JSON key (`_diff.py:166`): reused instead of a new key. The frozen
  `report diff` shape in `tests/fixtures/release_freeze/json-shapes.json:216-244` records only the
  compared branch (from `tests/e2e/release_freeze/write_shapes.py:384`); the skipped branch and
  `data_note` are not frozen, so AT-2 pins the skipped key set instead.

## 5. Behaviour

| # | Input | Result |
|---|---|---|
| B1 | Both entries have `format` | Data level compared, as today |
| B2 | Either entry lacks `format`, no `--require-data` | Exit 0, `data_level: skipped`, both paths in `missing_files`, `data_note` holds the refusal text; no file of that table is read |
| B3 | Same, with `--require-data` | Exit 1, message holds the refusal text |
| B4 | Old entry whose file is missing | Missing as today (path check runs first, `_compare.py:225-232`); no code |
| B4a | Table in one manifest only, its entry has no `format` | Refused as B2/B3 (added or removed table); with `format`, the existing "only exists in one run" delta |
| B5 | Entry with `format: xml` | `target_format_unreadable` named the same way (gains the code in the note) |
| B6 | Corrupt file with a valid `format` | Unchanged: generic arm, no code |
| B7 | `report verify` on an old manifest | Unchanged |

## 6. Failure modes

- F1: the value-isolation sentry (`tests/sentry/test_report_raw_value_isolation.py:64-67`)
  builds entries without `format`. After the change its CSV and Parquet leak cells (`:212`,
  `:266`) would read nothing and pass vacuously. AT-5 moves them to recorded formats and asserts
  the data level ran.
- F2: arm order or scope wrong: the generic arm catches the refusal and the code is lost (M-2).
- F3: one side is read before the other side's format is checked (today's order at
  `_compare.py:237-238`). AT-3 runs both orders with `read_file` raising (M-6).
- F4: the refusal text carries data. The message is a constant and the code list joins fixed
  codes; AT-4 pins the exact text and the cell sentinel's absence.
- F5: two e2e tests rely on the fallback: `test_report_diff_old_manifest_falls_back`
  (`tests/e2e/cli_fmt/test_target_format_readers.py:413`) and
  `test_report_diff_old_manifest_pq_holds_csv` (`:429`). The first becomes AT-2. The second
  becomes the `.pq`-holds-CSV refusal cell of AT-2 (old manifest, `.pq` path, CSV bytes: refused,
  not compared). Neither is deleted or weakened to pass.
- F6: a future writer path drops `format` for a file target, so `report diff` refuses its own
  manifest. Caught by existing real-run tests (M-5).
- F7: an outside consumer of `entry_format`. None: `git grep` finds only `_compare.py`, the unit
  tests and seeded strings in `tests/sentry/io_policy/test_manifest_path_resolution.py:404,432`,
  which never run and need no change.

## 7. Defect classes

| # | Class | Status | Closing structure | Sentry/property test | Mutation |
|---|---|---|---|---|---|
| 1 | Value-bearing output | Applies | Constant message, codes only in notes | AT-4, AT-5 (value-isolation sentry runs at data level) | M-3 and M-4 |
| 2 | Cleanup on failure | N/A: no file is opened or written on the refusal path | | | |
| 3 | Partial state | N/A: read-only command, no state written | | | |
| 4 | Route parity | Applies | One reader, `entry_format`, for the only route | AT-1, AT-2 | M-1: restore the fallback |
| 5 | Referential integrity | N/A: no keys or relations involved | | | |
| 6 | Untrusted input | Applies | The manifest is untrusted; a missing key is refused at one point before any read, one-sided entries included | AT-1, AT-3 | M-1, M-6, M-8 |
| 7 | TOCTOU / check-then-use | N/A: the format is read from the same parsed manifest used for the path | | | |
| 8 | Weak test | Applies | Sentry asserts the data level ran | AT-5 | M-4 |
| 9 | Refactor drift | Applies | Helper deleted, not kept as dead code | AT-1 | M-1 |
| 10 | Frozen contract | Applies | No JSON key added; `cli-local-1` writer untouched | AT-2 (skipped key set), `tests/e2e/release_freeze/test_json_shapes.py` (compared set) | M-7 |

## 8. Slices

One slice, C-S2m (CLI), R1.

| Files | Budget |
|---|---|
| `src/decoy/cli/io/_targets.py` (793 lines) | about -12 / +6; stays under 800 |
| `src/decoy/cli/report/_compare.py` (312) | about +12 |
| `src/decoy/cli/report/_diff.py` (361) | about +14 |
| `src/decoy/cli/evidence.py` (792) | docstrings only, net 0 to +2; stays under 800 |
| `CHANGELOG.md` | +1, one parenthetical edited |
| Parent plan (engine branch) D6 row and AT-D6 text | 2 lines |
| Tests: `tests/unit/cli_fmt/test_targets_format.py`, `tests/e2e/cli_fmt/test_target_format_readers.py`, `tests/sentry/test_report_raw_value_isolation.py` | about +70 / -30 |

New public names: `UNRECORDED` in `decoy.cli.io._targets` (not re-exported). Changed signature:
`entry_format(recorded)` (one production caller). No new files, so no Placement table.
Dependencies: none open. The parent plan's C-S2 row now points here for the remaining D6 work.

### Acceptance tests

Written red first against `fffca916`:

- AT-1 (unit, `test_targets_format.py:176-209`): the four legacy rows (no `format`) move to a
  refusal case: `entry_format({})` raises `TargetFormatError` with `code == UNRECORDED` and no
  `__cause__`, and the message equals the constant. The existing parametrized cases drop the
  `path` argument.
- AT-2 (e2e, `test_target_format_readers.py:413` and `:429`): `..._old_manifest_falls_back`
  becomes `..._old_manifest_refused`, and `..._pq_holds_csv` becomes its `.pq`-holds-CSV cell.
  With `--require-data`: exit 1, output names `target_format_unrecorded`. Without it: exit 0,
  JSON `data_level == "skipped"`, `data_note` starts with `refused: target_format_unrecorded`,
  the payload key set equals the current skipped set (manifest keys plus `data_level`,
  `any_data_change`, `table_deltas`, `missing_files`, `data_note`), `"refusals"` is not a key, and
  `missing_files` holds exactly the two distinct raw paths.
- AT-3 (unit, calls `compare_data` directly) with `decoy.cli.report._compare.read_file` (the
  name `compare_data` calls) monkeypatched to raise (the `boom` pattern at
  `test_targets_format.py:164`). Cells: old entry on side A; old entry on side B; `format: xml`
  on A and no `format` on B, in both argument orders (same sorted `refusals`, both codes); an old
  entry for a table only in A, and only in B (refused, no "only exists in one run" delta); a
  current entry for a one-sided table (delta kept). `read_file` is never called in any refusal
  cell.
- AT-4 (e2e, `test_unreadable_entries_are_value_free` at `:450`): add the old-shape entry to its
  cases and give each case an expected code or an explicit no-code expectation (parser failures
  keep no code, B6; the existing generic read-error cases stay). Run each in human mode and in
  `--json` mode (the helper at `:324` passes `--json` only, so a human-mode call is added). The
  refusal text equals the fixed `code: message` text, and the cell sentinel `_CELL` is absent
  from stdout, stderr and JSON (the existing check at `:489`).
- AT-5 (sentry, `test_report_raw_value_isolation.py`): `_outputs(path, fmt)` records `format`;
  the CSV and Parquet cells assert `table_deltas` is non-empty before checking the sentinel is
  absent.
- Existing real-run cover for F6, kept green: `test_manifest_records_format_and_layout`
  (`test_target_format_readers.py:299`), `test_report_diff_parquet_at_pq_dat_and_no_suffix`
  (`:347`), `test_report_diff_fixed_width_both_sides`, and the json-shapes `report diff`
  scenario. No new test is added for it.

### Mutations

- M-1: in `entry_format`, return `("csv", None)` when `format` is absent. AT-1 and the CSV cell of
  AT-2 red.
- M-2: catch `TargetFormatError` in the generic arm only (drop the new arm). AT-2, AT-4 red.
- M-3: interpolate `recorded.get("layout")` into the refusal message. AT-1 gains a cell that
  passes a seeded layout with no `format` and asserts the message equals the constant: red.
- M-4: revert AT-5's `_outputs` to no format. AT-5 red (empty `table_deltas`).
- M-5: drop `format` from `_format_keys`. The real-run tests above go red.
- M-6: restore read-then-check order (`read_file` for A before B is checked), or stop at the
  first side's refusal. AT-3 red.
- M-8: drop the one-sided check. AT-3 one-sided cells red.
- M-7: emit `refusals` as a JSON key on the skipped branch. AT-2 red.

## 9. Frozen contracts

- `cli-local-1` evidence payload (`docs/release/frozen-surfaces.md:26`): writer unchanged; the
  reader drops a pre-1.0 compatibility rule. Breaking for pre-format manifests only, recorded in
  CHANGELOG `### Breaking`. The parent plan (D6) approved removal before 1.0.
- `report diff` `--json` shape: the frozen compared-branch shape
  (`tests/fixtures/release_freeze/json-shapes.json:216-244`) does not move. The skipped branch is
  not frozen; `data_note` is an existing, unfrozen optional key; AT-2 pins its key set.
- Exit codes: unchanged (1 for `--require-data`).

## 10. Test depth

T1: the three changed test files, `tests/unit/cli_fmt/`, `tests/e2e/cli_fmt/`,
`tests/sentry/test_report_raw_value_isolation.py`, `tests/sentry/io_policy/`,
`tests/e2e/release_freeze/test_json_shapes.py`, `tests/unit/test_evidence.py`,
`tests/e2e/test_report_diff_command.py`, `tests/e2e/project_layout/test_evidence_paths.py`,
every test file that imports `decoy.cli.report` or names `entry_format`, plus the repo guard
tests. Full suite (serialization and frozen-contract trigger) at the slice head before the code
gate, diffed against the saved main baseline; reused at merge if the merge head is the same
tree, else re-run on the merge head. The Codex gate runs T2 on the head it records, and mutation
evidence (M-1 to M-8) is from the final head.

## 11. Pre-mortem

- The sentry change (AT-5) is skipped and the leak cells go vacuous. Mitigated by the non-empty
  `table_deltas` assertion and M-4.
- A builder keeps `_legacy_format_for_path` or the `path` parameter "for tests". Proportionality
  forbids it; M-1 and review check both are gone.
- A builder deletes the `.pq`-holds-CSV test instead of converting it. F5 and AT-2 name its new
  form.
- A user with a manifest from a pre-format main build loses data-level diff. Accepted: pre-1.0, named in the
  CHANGELOG, and the refusal text tells them to re-run.

## 12. Owner calls

None. The removal was decided in the parent plan (D6); the two deviations in section 2a are
technical.

## 13. Done when

- [ ] AT-1 to AT-5 green and the named real-run tests still green; M-1 to M-8 each turn a named
  test red.
- [ ] `_legacy_format_for_path` and the `entry_format` `path` parameter gone; no caller of the
  fallback left; docstrings, comment and CHANGELOG no longer describe the suffix rule.
- [ ] Source and test files stay under 800 lines.
- [ ] T3 shows no new failing id against the main baseline.
- [ ] The parent plan's D6 row, AT-D6 text, exit summary (`prop-batch.md:792`) and registry
  summary (`prop-batch.md:896`) name `target_format_unrecorded` and exit 1 under
  `--require-data`; row 24zk D6-manifest marked done in its post-1.0 rows.
