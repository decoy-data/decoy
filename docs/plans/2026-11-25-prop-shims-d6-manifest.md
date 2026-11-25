# 24zk PROP-SHIMS D6 manifest half: `report diff` refuses an evidence manifest entry with no `format`

Status: plan
Revision: 1
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

## 1. Problem

`entry_format` (`src/decoy/cli/io/_targets.py:302`) reads an evidence-manifest output entry back
for `decoy report diff`. An entry with no `format` key falls back to `_legacy_format_for_path`
(`_targets.py:240-245`): `.parquet` is Parquet, everything else CSV. The parent plan (D6) removes
this shim before 1.0 and refuses such an entry with a coded, value-free error.

CLI #313 deferred this half because `report.py` was over the size cap. The CLI split moved it to
the `src/decoy/cli/report/` package (`_compare.py` 312 lines, `_diff.py` 361 lines), so the size
reason is gone.

Every current writer records `format` for a file target (`src/decoy/cli/evidence.py:313-316`
with `_format_keys` at `evidence.py:179-196`). Only manifests written before format recording
(CLI 0.1.0 and pre-CLI-FMT main builds) lack it. No CLI release since 0.1.0 has shipped, and the
format-recording change is in the CHANGELOG `[Unreleased]` section as a pre-1.0 breaking change.

## 2. Guarantee and non-goals

Guarantee: `decoy report diff` never reads a manifest output entry that has no `format` key. For
such an entry it reports the code `target_format_unrecorded`, with a fixed message that holds no
path text from the entry and no cell value. With `--require-data` it exits 1 (`EXIT_USAGE`, the
existing exit for unreadable outputs). Without it, the data level is `skipped` and the code is
named in the note, as for any unreadable output today.

Non-goals:
- No change to the manifest writer, `cli-local-1`, `manifest_hash` or `report verify`. An old
  manifest still verifies (`tests/unit/cli_fmt/test_evidence_target_format.py:60-78` stays green).
- No new exit code and no new JSON key in `report diff`.
- No migration tool for old manifests. Re-running the pipeline writes a current one.
- The parent plan's other D items, and every 24zi and 24zj slice.

## 3. Established solutions

Search run: the CLI tree for existing refusal patterns of a retired on-disk shape, and the
parent plan's D-item rules. Found: CLI #313 refused an untagged saved scan with one coded
`ScanSetFormatError` and a fixed message (`src/decoy/cli/io/_scan_set.py`,
`SAVED_SCAN_SCHEMA_UNSUPPORTED`). The `TargetFormatError(code, message)` class at
`_targets.py:78` already carries codes for the same reader (`UNREADABLE` at `_targets.py:56`).
This plan follows those two patterns. No external research applies: the change deletes a branch
and adds one coded refusal through an existing error type. No custom machinery is added.

## 4. Design

4.1 `_targets.py`: add `UNRECORDED = "target_format_unrecorded"` beside the other codes
(`_targets.py:53-58`) and export it from `src/decoy/cli/io/__init__.py` beside `entry_format`
(`__init__.py:164`, `:238`). `entry_format` raises
`TargetFormatError(UNRECORDED, "the evidence manifest entry records no format (written before
format recording); re-run the pipeline to write a new manifest")` when `format` is absent.
Delete `_legacy_format_for_path` and the legacy sentence of the `entry_format` docstring
(`_targets.py:307-308`).

4.2 `src/decoy/cli/report/_compare.py` `compare_data` (`_compare.py:158`): the read loop at
`_compare.py:233-245` gets an `except TargetFormatError as err` arm before the generic
`except (OSError, ValueError, DecoyError)` arm. It adds both raw paths to `missing_files`
(same as today) and adds `err.code` to a `refused_codes` set. The result dict gains
`"refused_codes": sorted(refused_codes)`. The arm is needed because the generic arm drops the
code, and the code is the only thing that tells a user why the file was not compared.
`TargetFormatError` is a `ValueError`, so arm order matters (M-2).

4.3 `src/decoy/cli/report/_diff.py`: when `refused_codes` is non-empty, append
`"; refused: " + ", ".join(codes)` to the `--require-data` message (`_diff.py:129-135`), set the
existing `data_note` key in the skipped JSON payload (`_diff.py:160-165`) to
`"refused: <codes>"` when there is no dependency error, and append the same text to the human
note (`_diff.py:217-230`). Codes are fixed identifiers, never data.

4.4 Docs: `src/decoy/cli/evidence.py` module docstring (`evidence.py:21-29`) states that an entry
without `format` is refused by `report diff` with `target_format_unrecorded`. The `_format_keys`
docstring (`evidence.py:180-185`) drops "stays in the legacy shape" in favor of "has no format,
and `report diff` refuses it". CHANGELOG `[Unreleased]` gets one `### Removed` line.

## 4a. Enumerations

### Exit paths

- `report diff --require-data`, old entry: exit 1 (`EXIT_USAGE`) at `_diff.py:145`, message names
  the raw manifest path strings (as today) plus `refused: target_format_unrecorded`.
- `report diff` without `--require-data`, old entry: exit 0, `data_level: skipped`, note names
  the code.
- `report diff`, both entries carry `format`: unchanged (exit 0, `data_level: compared`).
- `report verify`, old manifest: unchanged, exit 0 when fingerprints match (no read by format).

### Routes

- `report diff` data level: `_diff.py:111` calls `compare_data`, which calls `entry_format` at
  `_compare.py:237-238`. The only production caller of `entry_format`.
- `report verify` and `run --evidence-out`: do not call `entry_format`; untouched.

### FK shapes

N/A: the change reads no tables relationally and touches no key handling; it refuses a manifest
entry before any file is read.

### Fields

- `output_fingerprints.<table>.format`: absent now means refusal (was the legacy suffix rule).
- `output_fingerprints.<table>.layout`: unchanged; read only when `format` is `fixed_width`.
- `report diff` JSON `data_note`: existing optional string, now also set for a refusal.
- `compare_data` result `refused_codes`: new internal key, not emitted as its own JSON key.

### Output surfaces

- `report diff` JSON payload (`_diff.py:147-166`): no new key; `data_note` value only.
- `report diff` stderr error and human note (`_diff.py:136-143`, `_diff.py:224-230`).
- No log lines are added.

## 4b. Reuse inventory

- `TargetFormatError` and its `code` attribute (`_targets.py:78`): reused, no new error class.
- The `missing_files` degrade path and `--require-data` exit (`_diff.py:124-145`): reused.
- The existing `data_note` JSON key (`_diff.py:165`): reused instead of a new key, so the
  frozen `report diff` shape in `tests/fixtures/release_freeze/json-shapes.json` does not move.

## 5. Behaviour

| # | Input | Result |
|---|---|---|
| B1 | Both entries have `format` | Data level compared, as today |
| B2 | One entry lacks `format`, no `--require-data` | Exit 0, `data_level: skipped`, both paths in `missing_files`, `data_note` names `target_format_unrecorded` |
| B3 | Same, with `--require-data` | Exit 1, message names the code |
| B4 | Old entry whose file is missing | Missing as today (path check runs first, `_compare.py:225-232`); no code |
| B5 | Entry with `format: xml` | `target_format_unreadable` named the same way (gains the code in the note) |
| B6 | Corrupt file with a valid `format` | Unchanged: generic arm, no code |
| B7 | `report verify` on an old manifest | Unchanged |

## 6. Failure modes

- F1: the value-isolation sentry (`tests/sentry/test_report_raw_value_isolation.py:64-67`)
  builds entries without `format`. After the change its CSV and Parquet leak cells (`:212`,
  `:266`) would read nothing and pass vacuously. AT-5 moves them to recorded formats and asserts
  the data level ran.
- F2: arm order reversed: the generic arm catches the refusal and the code is lost (M-2).
- F3: the message or note echoes entry text. The message is a constant; the note joins codes
  only. AT-4 checks a sentinel path segment is absent from the code-bearing text.
- F4: a future writer path drops `format` for a file target. Then `report diff` refuses its own
  manifest. `_format_keys` returns `{}` only for non-file targets and for a target the gate
  already refused; AT-6 pins that a fresh `run --evidence-out` manifest diffs at data level.
- F5: e2e tests that relied on the fallback (`tests/e2e/cli_fmt/test_target_format_readers.py:413`)
  flip. They are rewritten to the refusal, not deleted.
- F6: a consumer outside the CLI reads `entry_format`'s legacy result. None: `git grep` finds only
  `_compare.py` and tests.

## 7. Defect classes

| # | Class | Status | Closing structure | Sentry/property test | Mutation |
|---|---|---|---|---|---|
| 1 | Value-bearing output | Applies | Constant message, codes only in notes | AT-4, AT-5 (value-isolation sentry runs at data level) | M-3: put the raw path in the message |
| 2 | Cleanup on failure | N/A: no file is opened or written on the refusal path | | | |
| 3 | Partial state | N/A: read-only command, no state written | | | |
| 4 | Route parity | Applies | One reader, `entry_format`, for the only route | AT-1, AT-2 | M-1: restore the fallback |
| 5 | Referential integrity | N/A: no keys or relations involved | | | |
| 6 | Untrusted input | Applies | The manifest is untrusted; missing key refused at one point | AT-1 | M-1 |
| 7 | TOCTOU / check-then-use | N/A: the format is read from the same parsed manifest used for the path | | | |
| 8 | Weak test | Applies | Sentry asserts data level ran | AT-5 | M-4: leave `_outputs` without format |
| 9 | Refactor drift | Applies | Helper deleted, not kept as dead code | AT-1 | M-5: keep `_legacy_format_for_path` called |
| 10 | Frozen contract | Applies | No JSON key added; `cli-local-1` writer untouched | `tests/e2e/release_freeze/test_json_shapes.py` | M-6: emit `refused_codes` as a JSON key |

## 8. Slices

One slice, C-S2m (CLI), R1.

| Files | Budget |
|---|---|
| `src/decoy/cli/io/_targets.py` (793 lines) | about -10 / +6; stays under 800 |
| `src/decoy/cli/io/__init__.py` | +2 |
| `src/decoy/cli/report/_compare.py` (312) | +10 |
| `src/decoy/cli/report/_diff.py` (361) | +12 |
| `src/decoy/cli/evidence.py` (792) | docstrings only, net 0 to +2; stays under 800 |
| `CHANGELOG.md` | +1 |
| Tests: `tests/unit/cli_fmt/test_targets_format.py`, `tests/e2e/cli_fmt/test_target_format_readers.py`, `tests/sentry/test_report_raw_value_isolation.py` | about +60 / -25 |

New public names: `UNRECORDED` (exported from `decoy.cli.io`). No new files, so no Placement
table. Dependencies: none open. The parent plan's C-S2 row lists D6 in one slice with D6b; D6b
and the saved-scan half merged in #313, so this slice is the rest of C-S2's D6 work.

### Acceptance tests

Written red first against `fffca916`:

- AT-1 (unit, `test_targets_format.py:176-190`): the four legacy rows (`o.parquet`, `o.PARQUET`,
  `o.pq`, `o.dat` with no `format`) move to a refusal case: `entry_format` raises
  `TargetFormatError` with `code == UNRECORDED`, no `__cause__`, and the message holds no path.
- AT-2 (e2e, `test_target_format_readers.py:413`): `test_report_diff_old_manifest_falls_back`
  becomes `..._old_manifest_refused`. With `--require-data`: exit 1, stderr names
  `target_format_unrecorded`. Without it: exit 0, JSON `data_level == "skipped"` and `data_note`
  contains the code.
- AT-3 (e2e, same file): one entry with `format` and one without: refused the same way (the
  refusal is per side).
- AT-4 (e2e, `test_unreadable_entries_are_value_free` at `:450`): add the old-shape entry to
  its cases; a sentinel path segment and a sentinel cell value are absent from stdout, stderr and
  JSON except the raw path in `missing_files`, which is unchanged behaviour.
- AT-5 (sentry, `test_report_raw_value_isolation.py`): `_outputs(path, fmt)` records `format`;
  the CSV and Parquet cells assert `table_deltas` is non-empty before checking the sentinel is
  absent.
- AT-6 (e2e): a fresh `decoy run --evidence-out` twice on a small file-target pipeline (an existing `tests/e2e/cli_fmt` fixture), then
  `report diff --require-data`: exit 0, `data_level == "compared"`.

### Mutations

- M-1: restore the legacy fallback in `entry_format`. AT-1, AT-2 red.
- M-2: swap the two `except` arms in `compare_data`. AT-2 red (code absent).
- M-3: format the raw path into the refusal message. AT-1, AT-4 red.
- M-4: revert AT-5's `_outputs` to no format. AT-5 red (empty `table_deltas`).
- M-5: drop `format` from `_format_keys`. AT-6 red.
- M-6: add `refused_codes` to the JSON payload. `test_json_shapes.py` red.

## 9. Frozen contracts

- `cli-local-1` evidence payload (`docs/release/frozen-surfaces.md:26`): writer unchanged; the
  reader drops a pre-1.0 compatibility rule. Breaking for pre-format manifests only, recorded in
  CHANGELOG `### Removed`. The parent plan (D6) approved removal before 1.0.
- `report diff` `--json` shape (`tests/fixtures/release_freeze/json-shapes.json:216`): unchanged;
  `data_note` already exists as an optional string.
- Exit codes: unchanged (1 for `--require-data`).

## 10. Test depth

T1: the three changed test files, `tests/unit/cli_fmt/`, `tests/e2e/cli_fmt/`,
`tests/sentry/test_report_raw_value_isolation.py`, `tests/sentry/io_policy/`,
`tests/e2e/release_freeze/test_json_shapes.py`, `tests/unit/test_evidence.py`, every test file
that imports `decoy.cli.report` or names `entry_format`, plus the repo guard tests. T3: full
suite on the merge head (serialization and frozen-contract trigger), diffed against the saved
main baseline.

## 11. Pre-mortem

- The sentry change (AT-5) is skipped and the leak cells go vacuous. Mitigated by the non-empty
  `table_deltas` assertion and M-4.
- A builder keeps `_legacy_format_for_path` "for tests". Proportionality forbids it; M-5 and the
  review check it is gone.
- A user with a CLI 0.1.0 manifest loses data-level diff. Accepted: pre-1.0, named in the
  CHANGELOG, and the refusal tells them to re-run.

## 12. Owner calls

None. The removal itself was decided in the parent plan (D6).

## 13. Done when

- [ ] AT-1 to AT-6 green, M-1 to M-6 each turn a named test red.
- [ ] `_legacy_format_for_path` gone; no caller of the fallback left.
- [ ] Files stay under 800 lines.
- [ ] T3 shows no new failing id against the main baseline.
- [ ] Row 24zk D6-manifest marked done in the parent plan's post-1.0 rows.
