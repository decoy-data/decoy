Status: plan

# VALIDATE-ENVELOPE V1: `decoy validate CONFIG --json` error documents meet `decoy-error/v1`

Owner: Cam. Author: Opus plan agent. Date: 2026-11-25. Revision 2 (Codex R1 folded: source-path credentials, explicit codes only, primary finding matches the exit code, one error emitter, GATE-11 evidence, R2 with a full suite). Source: `docs/roadmap/inbox.md` item "QA (found at CLI #381 CI, exempted in `test_items_error_envelope`)". Repo: decoy (CLI). Branch: docs/plans-inbox-triage-1125. Read at CLI `origin/main` `fffca916`.

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md` (PLAN, Proportion), `bugfix.md`, `api-and-compatibility.md`, `testing.md` (Test depth). CLI `docs/qa/cli-v1-checklist.md:230` (GATE-11).

Classification: 1.0 fix row. The missing member is not a function break. But the `--json` shape freezes at REL-GATE (FREEZE-SURFACE C-HIDDEN, CLI #381), QA GATE-11 expects one error object with `error` and `code`, and after 1.0 this fix would be a 2.0 change. Review also found that a source path with URL credentials is echoed in gate findings today (section 1). That echo goes to the user who wrote the credential, so it is not a leak to a non-admin under the V1 bar, but it reaches CI logs; this row fixes it (OC-1 asks whether it blocks). Risk: R2. A serialized output changes and the preflight messages change, so the full CLI suite runs (section 7).

## 1. Problem

1. The hidden default command `decoy validate CONFIG --json` renders through `_emit_gate` (`src/decoy/cli/validate.py:330`). On a failed gate it prints `{command, status: "error", config, messages}` with no top-level `error`, so it fails `docs/schemas/decoy-error-v1.schema.json` (required: `command`, `status`, `error`). The envelope test exempts `validate` (`tests/e2e/first_user/test_items_error_envelope.py:80`). Reproduced on the Mac node: `decoy validate examples/mask_example.yaml --json` printed `messages[0].code == "hash_requires_namespace"` and no `error`.
2. Three source-file findings in preflight interpolate the raw `path` (`src/decoy/cli/preflight.py:230` not found, `:238` not a regular file, `:253` not readable, which also appends `str(OSError)`), and the pass entry at `:260` does too. A path like `https://user:SECRET@host/input.csv` puts the credential in `messages[]`, in the human report, in `validate preflight --json` `checks[]` and in the `decoy run` refusal summary (`gate/_run.py:106`).
3. `messages[].code` holds `c.code or c.name` (`gate/_layers.py:137`). A check with no reason code reports its check name (`source.people.exists`), which passes `is_reason_code` but is not a reason code.
4. The engine's declared-column refusal keeps its `source_file.<code>: ` prefix in the message (`preflight.py:448`).
5. Findings are ordered config, compile, preflight, but a capacity refusal exits 5 and outranks a compile error (`gate/_layers.py:545`). The first error is not always the cause of the exit. `PreRunCheckError.from_result` (`gate/_run.py:84`) already picks the capacity finding for exit 5.

## 2. Behavior

On a gate result with at least one error finding, `_emit_gate` calls `emit_error` (`src/decoy/ui/output.py:217`), the one error builder:

`emit_error(state, "validate", <error>, code=<code>, hint=<hint>, context={"config": config_str, "messages": [...]})`

which writes `{command, status: "error", error, code?, hint?, config, messages}` (the emitter's order).

- Primary finding: a new `primary_error(result: GateResult) -> GateFinding` in `gate/_run.py`, beside `capacity_codes()` (`gate/_run.py:32`), which it needs; `gate/_run.py` already imports `gate/_layers.py`, so no cycle. On exit 5 it is the first error whose code is in `capacity_codes()`, else the first error. `PreRunCheckError.from_result` calls it instead of its own selection, so `run` and `validate` agree.
- `error`: the primary finding's message with a leading `<code>: ` removed. The rule moves out of `refusal_message` (`src/decoy/cli/_sources.py:92`) into `strip_code_prefix(text, code)` in the same module; `refusal_message` calls it. Capped with `cap_error_text` as `messages[]` already is.
- `code`: present only when the finding carries an explicit reason code. `GateFinding` gains `explicit_code: bool = True`. `_findings_from_checks` sets it to `c.code is not None`. Every other constructor of `GateFinding` already passes an engine or CLI reason code. The member is emitted only when `explicit_code` and `is_reason_code(code)` are both true; `emit_error` refuses a malformed code, so the guard stays.
- `hint`: the primary finding's `hint`, when it has one.
- `messages`: built by `_message` (`gate/_run.py:133`), the shape `run --json` already uses. Members unchanged (`message` now capped as in `run`).
- `status: "ok"` and `status: "warn"` documents keep their current shape and builder. A `warn` document is a result, not an error.
- Source-file findings name the table and config location, never the path or the `OSError` text: `Source 'people': file not found.`, `Source 'people': path is not a regular file.`, `Source 'people': file not readable (PermissionError).`, pass `Source 'people': file exists and is readable.` `location` stays `sources.<table>.path`, which tells the user what to fix. The same text reaches `validate preflight` and `run` because they share the accumulator.

Non-goals: `validate config` keeps its legacy builder (`validate.py:195`, on the one-error-emitter baseline); `validate compile` and the human report layout do not change; no exit code changes. Other preflight messages that name a path (output targets) are local file paths the user chose and stay; only the source-path findings carry a remote URL.

## 3. Failure modes

- F1: the primary finding has no explicit code (a preflight check without `code=`). `code` is left out; the document stays schema-valid.
- F2: the primary message is empty. Not reachable: every `add_fail` and `GateFinding` site passes a literal message. The schema requires `minLength: 1` for `error`, so AT-1 fails if one appears.
- F3: the gate fails before any layer runs (a YAML load error). One config finding; `primary_error` returns it. AT-2 pins it.
- F4: exit 5 with no capacity-coded finding (the flag set by a path that adds no coded finding). `primary_error` falls back to the first error, as `from_result` does today.
- F5: a remote source path with credentials. No finding text contains it (AT-3).

## 4. Defect classes

| # | Class | Applies | Structure that closes it | Proof and the mutation that turns it red |
|---|---|---|---|---|
| 1 | value | Yes: a source path can carry credentials, and a finding can echo a cell | source-file findings carry the table name and location only; `error` comes from the same finding text | AT-3; mutation: put `src_path_str` back in the not-found message |
| 2 | cleanup | N/A: no files or resources are touched | none | none |
| 3 | state | N/A: no state machine | none | none |
| 4 | route | Yes: `validate`, `validate preflight` and `run` print the same findings, and `run` and `validate` pick a primary finding | one `primary_error`, one accumulator, one `_message` | AT-4 compares `run --json` and `validate --json` top-level `code` on the exit 5 case; mutation: keep the old selection in `from_result` |
| 5 | referential | N/A: no data rows | none | none |
| 6 | untrusted | N/A: no new input parsing | none | none |
| 7 | toctou | N/A: no path checks added | none | none |
| 8 | weak | Yes: a test could check key presence only | AT-2 compares the full ordered key list and each value as literals | AT-2; mutation: emit the check name as `code` |
| 9 | refactor drift | Yes: `from_result` moves to `primary_error`; `refusal_message` moves to `strip_code_prefix` | existing `run` refusal tests and `_sources` tests pass unchanged | AT-5; mutation: invert the capacity branch |
| 10 | frozen contract | Yes: the `validate` `--json` shape is frozen by C-HIDDEN | success documents unchanged; release-freeze fixture unchanged; CHANGELOG `Changed` line; full CLI suite | AT-6 |

Recurring-defect catalog (`catalogs/recurring-defects.md`): #1 anchored patterns applies to `strip_code_prefix` (`removeprefix`, not a regex); #9 mutations on the final head applies. The others are N/A: no new read model, scanner, private import or pin.

## 5. Acceptance tests

Write each test first and record it red at base where it is red.

| AT | Test | Mutation that turns it red |
|---|---|---|
| AT-1 | `tests/e2e/first_user/test_items_error_envelope.py`: remove `"validate"` from `EXEMPT` (line 80) and add `"validate": ["validate", BAD_YAML]` to `BAD_INPUT`. `test_bad_input_gives_one_schema_valid_error_object` passes; the coverage test at line 95 still passes. | Delete the `error` argument |
| AT-2 | `tests/e2e/test_validate_gate.py`, three literal cases. (a) `examples/mask_example.yaml` without a namespace: `list(doc) == ["command", "status", "error", "code", "hint", "config", "messages"]` (or without `hint` if the finding has none, stated as the literal the builder records at base), `doc["code"] == "hash_requires_namespace"`, `doc["error"]` equals the finding's message. (b) A missing local source file: no `code` member, `messages[0].code == "source.<table>.exists"` unchanged. (c) A declared-column refusal: `doc["code"]` is the `source_file.` code and `doc["error"]` does not start with it. A YAML load failure gives one schema-valid line. | Emit the check name as `code`; skip `strip_code_prefix` |
| AT-3 | Credential sweep: a file source with `path: https://user:CANARY7731@example.invalid/in.csv`. `decoy validate --json`, `decoy validate` (human, stdout and stderr), `decoy validate preflight --json` and `decoy run --json`: each refuses with exit 1 and `CANARY7731` appears in no output. The GATE-11 pair, run as written in `cli-v1-checklist.md:230`: a `categorical` mapping keyed on a fixture marker, and a malformed secret ref; each in human and `--json` mode exits 1, the `--json` document is schema-valid with `error` and `code`, and the marker appears nowhere. | Put `src_path_str` back in the not-found message |
| AT-4 | Extend `test_gate_capacity_outranks_compile_fail` (`tests/e2e/test_validate_gate.py:384`) with `--json`: exit 5, `doc["code"]` is the capacity code, `doc["error"]` is the capacity message, `messages` holds both the compile and the capacity error. The same config through `decoy run --json` gives the same top-level `code`. | Use the first error as primary |
| AT-5 | Existing `run` refusal tests and `tests/**/test_sources*.py` pass unchanged. | Change `strip_code_prefix` to strip any `x: ` prefix |
| AT-6 | `tests/e2e/release_freeze/test_json_shapes.py` passes with `tests/fixtures/release_freeze/json-shapes.json` unchanged (empty fixture diff in the PR). An ok document and a `--fail-on-warning` warn document have no `error`, `code` or `hint` member. `tests/sentry/baselines/one-error-emitter.json` loses its two `_emit_gate` entries and gains none. | Add the members to every status |

## 6. Files allowed to change

`src/decoy/cli/validate.py` (`_emit_gate`, about 15 lines; the file is 430 lines), `src/decoy/cli/gate/_layers.py` (`GateFinding.explicit_code`, `_findings_from_checks`, about +5), `src/decoy/cli/gate/_run.py` (`primary_error`, and `from_result` calls it, about +5 net), `src/decoy/cli/_sources.py` (`strip_code_prefix`, about +5), `src/decoy/cli/preflight.py` (four source messages), `tests/e2e/first_user/test_items_error_envelope.py`, `tests/e2e/test_validate_gate.py`, any existing test that asserts the old source-file message text (the builder lists each in the PR), `tests/sentry/baselines/one-error-emitter.json` (two entries removed), `CHANGELOG.md`.

## 7. Test selection

- T0: `tests/e2e/test_validate_gate.py` and the envelope e2e.
- T1: the envelope e2e, `tests/e2e/release_freeze/test_json_shapes.py`, every test that invokes `validate`, `validate preflight` or asserts a `PreRunCheckError`, `tests/sentry/`, plus import-impact selection for `gate/_layers.py`, `gate/_run.py`, `_sources.py` and `preflight.py`.
- T2 gate: T1 on the exact head with the mutations above, head recorded.
- Full suite: yes, once on the final slice head against the saved main baseline. Trigger: serialized output and frozen contract (`validate --json` error documents and the shared preflight messages change).

## 8. Enumerations

### Exit paths

- `_gate` exits 5, 1, 3 or 0 by `gate_exit_code` (`gate/_layers.py:543`): unchanged. The top-level `code` now names the cause of exit 5.
- `run` refusals exit as today; `from_result` (`gate/_run.py:77`) picks the same finding.

### Routes

- `decoy validate CONFIG` (hidden default, `_gate` at `validate.py:267`, `_emit_gate` at `validate.py:330`): error documents change; source messages change.
- `decoy validate preflight`: source messages change.
- `decoy run` refusal (summary at `gate/_run.py:106`): source messages change; primary selection moves to the shared function.
- `decoy validate config` (`_emit_result`, `validate.py:175`): unchanged.

### FK shapes

N/A: no data rows or relations are handled.

### Fields

- Error documents of the hidden default gain `error` (string), `code` (explicit reason code, optional) and `hint` (optional); `config` moves after them.
- `messages[].message` is capped as in `run`.
- `GateFinding.explicit_code` (internal, `gate/_layers.py:45`).

### Output surfaces

- `--json` stdout of `decoy validate CONFIG`: gains members on error.
- Human output of `validate`, `validate preflight` and `run`: source-file messages lose the path.
- Quiet output: unchanged.

## 9. Reuse inventory

`emit_error` and `is_reason_code` (`ui/output.py:209-217`), `_message` (`gate/_run.py:133`), `capacity_codes()`, `cap_error_text`, the `refusal_message` rule (`_sources.py:92`), the envelope test's `SCHEMA` and `BAD_YAML`, the release-freeze shape test, the one-error-emitter sentry.

## 10. Frozen contracts

`decoy-error/v1` (unchanged, now met), the `validate` success shape in `json-shapes.json` (unchanged), exit codes (unchanged). CHANGELOG `Changed`: "`decoy validate CONFIG --json` error documents now carry `error`, `code` and `hint` (decoy-error/v1), and the top-level code names the cause of the exit. Source-file findings no longer print the source path."

## 11. Owner calls

- OC-1: does the source-path credential echo block 1.0 on its own? Default: no. It reaches only the user's own terminal and logs, and it is fixed in this row, which is a 1.0 fix row anyway. Alternative: mark the row a 1.0 blocker and build it first.
- OC-2: source-file messages drop the path entirely. Default: yes, the location `sources.<table>.path` is enough to fix it. Alternative: print the path with any `user:password@` part removed, which keeps local paths visible but adds a URL parser to the message path.

## 12. Slices

One slice, V1, CLI repo, R2, about 40 source lines and 120 test lines. No open PR touches `validate.py`, `gate/_layers.py`, `gate/_run.py`, `_sources.py` or the source checks in `preflight.py` (checked with `gh pr list` on 2026-11-25; the builder re-checks at start).

## 13. Pre-mortem

- The builder keeps a validate-specific dict builder. AT-6 sentry baseline must lose the `_emit_gate` entries.
- The builder regenerates the shape fixture to turn a red test green. AT-6 requires an empty fixture diff.
- The builder fills `code` from the check-name fallback. AT-2 (b).
- The builder fixes the credential in `validate` only. AT-3 runs `validate preflight` and `run` too.
- The builder picks the first error on exit 5. AT-4.
