Status: plan

# VALIDATE-ENVELOPE V1: `decoy validate CONFIG --json` error documents meet `decoy-error/v1`

Owner: Cam. Author: Opus plan agent. Date: 2026-11-25. Revision 1. Source: `docs/roadmap/inbox.md` item "QA (found at CLI #381 CI, exempted in `test_items_error_envelope`)". Repo: decoy (CLI). Branch: docs/plans-inbox-triage-1125. Read at CLI `origin/main` `fffca916`.

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md` (PLAN, Proportion), `bugfix.md`, `api-and-compatibility.md`, `testing.md` (Test depth). CLI `docs/qa/cli-v1-checklist.md:230` (GATE-11).

Classification: 1.0 fix row. It is not a function break. But the `--json` shape freezes at REL-GATE (FREEZE-SURFACE C-HIDDEN, CLI #381), and QA GATE-11 expects one error object with `error` and `code`. After 1.0 this fix would be a 2.0 change. Risk: R1. Error documents gain members; nothing else changes.

## 1. Problem

The hidden default command `decoy validate CONFIG --json` runs the full gate and renders through `_emit_gate` (`src/decoy/cli/validate.py:330`). On a failed gate it prints `{command, status: "error", config, messages}`. There is no top-level `error` member, so the document fails `docs/schemas/decoy-error-v1.schema.json` (required: `command`, `status`, `error`). `decoy validate config --json` (`validate.py:175`) already adds `error` from the first error finding. The envelope test exempts `validate` (`tests/e2e/first_user/test_items_error_envelope.py:80`).

Reproduced on the Mac node (`vm-run`): `decoy validate examples/mask_example.yaml --json` printed `{"command": "validate", "status": "error", "config": ..., "messages": [{"layer": "config", "severity": "error", "code": "hash_requires_namespace", ...}]}` with no `error`.

## 2. Behavior

On a gate result with at least one error finding, the `--json` document becomes:

`{command: "validate", status: "error", config, error, code?, hint?, messages}`

- `error`: the first error finding's `message`, the text the human report already prints. Gate messages are value-free under 24a.
- `code`: the first error finding's `code`, only when `is_reason_code(code)` (`src/decoy/ui/output.py:209`) is true. Otherwise the member is left out.
- `hint`: the first error finding's `hint`, when it has one.
- Key order: `command`, `status`, `config`, `error`, `code`, `hint`, `messages`. `config` stays third.
- `messages` does not change.
- `status: "ok"` and `status: "warn"` documents do not change. A `warn` document is a result, not an error.

Non-goals: `validate config`, `validate compile`, `validate preflight` and the human report do not change. No exit code changes.

## 3. Failure modes

- F1: the first error finding has a code that is not a reason code (a hyphen or upper case). `code` is left out and the document stays schema-valid. A raw bad code would fail the schema pattern.
- F2: an error finding with an empty message. Not reachable today. `error` would be an empty string, which the schema allows. No special case.
- F3: the gate fails before any layer runs (a YAML load error). This already comes out as one finding through `_emit_gate`. AT-2 pins it.

## 4. Defect classes

| # | Class | Applies | Structure that closes it | Proof and the mutation that turns it red |
|---|---|---|---|---|
| 1 | value | Yes, narrowly: `error` copies a gate message into a new member | the message is the one already in `messages[]` and on the human line; no new text source | AT-3 sweeps the GATE-11 marker over stdout; mutation: build `error` from the finding's `location` plus message |
| 2 | cleanup | N/A: no files or resources are touched | none | none |
| 3 | state | N/A: no state machine | none | none |
| 4 | route | Yes: two validate routes print two error shapes | both error routes pass the shared envelope test | AT-1; mutation: put `validate` back in `EXEMPT` |
| 5 | referential | N/A: no data rows | none | none |
| 6 | untrusted | N/A: no new input | none | none |
| 7 | toctou | N/A: no path checks | none | none |
| 8 | weak | Yes: a test could check key presence only | AT-2 compares the full ordered key list as a literal | AT-2; mutation: put `error` after `messages` |
| 9 | refactor drift | N/A: no refactor; one function gains members | none | none |
| 10 | frozen contract | Yes: the `validate` `--json` shape is frozen by C-HIDDEN | success documents unchanged; the release-freeze shape fixture is not regenerated; CHANGELOG `Changed` line | AT-4; mutation: add `error: null` to ok documents |

## 5. Acceptance tests

Write each test first and record it red at base where it is red.

| AT | Test | Mutation that turns it red |
|---|---|---|
| AT-1 | `tests/e2e/first_user/test_items_error_envelope.py`: remove `"validate"` from `EXEMPT` (line 80) and add `"validate": ["validate", BAD_YAML]` to `BAD_INPUT`. `test_bad_input_gives_one_schema_valid_error_object` passes for it; the coverage test at line 95 still passes. | Delete the `error` member |
| AT-2 | New unit test beside the validate tests: a config whose gate fails with a reason-coded finding that has a hint. `list(doc) == ["command", "status", "config", "error", "code", "hint", "messages"]`, `doc["error"]` equals the first error entry's `message` in `messages`, `doc["code"]` equals that finding's code. A second case with a warning first and an error second takes the error's members. A YAML load failure gives one schema-valid line. | Take the first finding instead of the first error finding |
| AT-3 | A patched finding list whose first error has code `Bad-Code` gives a schema-valid document with no `code` member. The GATE-11 categorical-marker config: the marker is not in stdout. | Drop the `is_reason_code` guard |
| AT-4 | `tests/e2e/release_freeze/test_json_shapes.py` passes with `tests/fixtures/release_freeze/json-shapes.json` unchanged (the PR diff has no change to the fixture). An ok document and a `--fail-on-warning` warn document have no `error`, `code` or `hint` member. | Add the members to every status |

## 6. Files allowed to change

`src/decoy/cli/validate.py` (about 15 lines in `_emit_gate`; the file is 430 lines), `tests/e2e/first_user/test_items_error_envelope.py`, one validate unit test file, `CHANGELOG.md`.

## 7. Test selection

- T0: the validate unit tests and the envelope e2e.
- T1: `tests/e2e/first_user/test_items_error_envelope.py`, `tests/e2e/release_freeze/test_json_shapes.py`, every test file under `tests/` that invokes `validate`, plus import-impact selection.
- T2 gate: T1 on the exact head with the mutations above.
- Full suite: not triggered. Only error documents gain members. The frozen success shapes do not change, and AT-4 proves the fixture is unchanged. If the fixture must change, the frozen-contract trigger applies and the full CLI suite runs before merge.

## 8. Enumerations

### Exit paths

- `_gate` exits 1 on an error (`validate.py:267`): unchanged.
- `_gate` exits 0, or the warning exit with `--fail-on-warning`: unchanged.

### Routes

- `decoy validate CONFIG` (hidden default, `_emit_gate`, `validate.py:330`): changes.
- `decoy validate config` (`_emit_result`, `validate.py:175`): already schema-valid, unchanged.

### FK shapes

N/A: no data rows or relations are handled.

### Fields

- New `error` (string), `code` (reason code, optional) and `hint` (optional) on error documents of the hidden default.
- `messages[]` members unchanged.

### Output surfaces

- `--json` stdout of `decoy validate CONFIG`: gains members on error.
- Human and quiet output: unchanged.

## 9. Reuse inventory

`is_reason_code` (`ui/output.py:209`), `emit_json`, the envelope test's `SCHEMA` and `BAD_YAML` fixtures, the release-freeze shape test. No new file.

## 10. Frozen contracts

`decoy-error/v1` (unchanged, now met), the `validate` success shape in `json-shapes.json` (unchanged), exit codes (unchanged).

## 11. Slices

One slice, V1, CLI repo, about 15 source lines and 60 test lines. No dependency on open PRs. CHANGELOG `Changed`: "`decoy validate CONFIG --json` error documents now carry `error`, `code` and `hint` (decoy-error/v1)."

## 12. Pre-mortem

- The builder emits through `emit_error` and loses `config` and `messages`. AT-2 pins the full key list.
- The builder regenerates the shape fixture to turn a red test green. AT-4 requires an empty fixture diff.
- The builder fills `code` from a finding with a bad code, and the schema test fails only on that path. AT-3 covers it.
