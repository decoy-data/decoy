Status: plan

# NATIVE-MISSING-WARN C1: the CLI prints the engine's native fallback notice

Owner: Cam. Author: Opus plan agent. Date: 2026-11-22. Roadmap row: NATIVE-MISSING-WARN (`docs/roadmap/groups/run.md:23`). Parent plan: engine `docs/plans/2026-11-21-native-missing-warn.md` on `plan/native-missing-warn` (`fc1f40b5e`, revision 3), section 3.2 and the AT-C tests in section 7. This file fills in that section. Where the two differ, the parent's guarantee (G1 to G5) wins, and each difference is named in section 7.

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md` (PLAN, Proportion), `cross-cutting-concerns.md`, `api-and-compatibility.md`, `proportionality.md`, `testing.md` (test depth), `security.md` (value-free output), `workspace-and-vcs.md` (commit messages), `catalogs/recurring-defects.md`. CLI `CLAUDE.md`, `CODEMAP.md` "Where Things Go" (rows "`decoy run` internals" and "Private shared ... primitives"), `tests/fixtures/release_freeze/json-shapes.json`.

Read at CLI `origin/main` `2dfc0233`. Engine API read at tag `v0.28.3`. C1 builds after the CLI re-pin to `decoy-engine==0.28.3` merges (separate PR). Until then `pyproject.toml:151` pins 0.28.2.

Risk: R1. One advisory stderr line and one removed pre-run hint. No output bytes, exit code, result document or `--json` member changes. Plan review: one round. Code gate: Codex. Tests: T0 and T1, then the T2 set. No full-suite trigger.

## 1. Engine API used (v0.28.3)

- `ExecutionResult.native_fallback_code: str | None`. `run_pipeline` sets it once, through `with_native_notice` (`execution/_pipeline.py:361`). The value is `native_companion_missing` or None. If the notice itself fails, the field stays None and the run does not fail.
- `decoy_engine.reasons.find("warning", code) -> ReasonSpec | None` (`reasons/_registry.py:119`). It returns None for an unknown or non-string code. `ReasonSpec.summary` for the code is "No compiled kernel ran: a native kernel this run needs is not available, so masking ran in Python."

## 2. Behavior

- G1. After a plain `decoy run` (not `--chunked`, not `--rows`) with the default native intent and not `--quiet`, when `result.native_fallback_code` is a registered `warning` code, stderr gets exactly one line:

  ``warning: No compiled kernel ran: a native kernel this run needs is not available, so masking ran in Python. Compiled kernels come with the signed bundle; run `decoy explain native` to see what is missing.``

- G2. `--json`: the notice is not in the stdout JSON. It is not added to `warnings`, `native_route` or `result`. The stderr line still prints in `--json` mode, the same as the gate's existing `warning:` line (`cli/run/_prepare.py:569-570`). Reason: the roadmap row and the parent's G2 keep the output contract unchanged, so the same config gives the same JSON on a bundle install and a pip install. The freeze does not force this: `/warnings` is an opaque array in `json-shapes.json`, so a new item would be additive. See open question Q1.
- G3. Nothing prints under `--no-native`, `--native`, `--chunked`, `--quiet`, a `--rows` preview, or an unknown code.
- G4. The line is the registry summary plus one CLI constant. It holds no table, column, path or value.
- G5. The pre-run `native:` hint for an absent companion is removed: `_native_gate.py:368-375` returns `PreGateResult(unified_slice_enabled=True)`.

Non-goals: `decoy.mask()` prints nothing (M4 rule; only the comment at `api.py:583-591` is reworded, as the parent says). Text-only configs (Q2, V2-LOG). `run_pipeline_isolated` (V2-LOG; the CLI never calls it). Removing the now-unset `PreGateResult.info_message` and its print (V2-LOG). The `decoy explain native` text.

## 3. Choke point and guard

- Choke point: one function in `src/decoy/_native_gate.py`, beside the hint constant that the parent puts there:

  ```python
  FALLBACK_HINT = "Compiled kernels come with the signed bundle; run `decoy explain native` to see what is missing."

  def fallback_notice(result: ExecutionResult, *, intent: NativeIntent) -> str | None:
      """The line to print after a run, or None. Only the default intent prints."""
  ```

  It returns None unless `intent == "default"` and `reasons.find("warning", result.native_fallback_code)` is not None. Then it returns `f"{spec.summary} {FALLBACK_HINT}"`. It is the only reader of `native_fallback_code` in `src/decoy/`.
- One call site: `cli/run/_execute.py`, in `execute`, right after `ctx._execution = result` (`:390`) and before `post_run_verify` and the writes:

  ```python
  notice = _native_gate.fallback_notice(result, intent=ctx.native_intent)
  if notice is not None and ctx.state.mode is not OutputMode.quiet:
      ctx.state.err_console.print(warn("warning:"), notice, markup=False, highlight=False, soft_wrap=True)
  ```

  `soft_wrap=True` keeps the line whole at any terminal width. There is no call in `execute_preview`: a preview sets no `native_intent` (parent revision 3). The notice does not go through `ctx.add_cli_warning`, because that list feeds the `--json` `warnings` array and the stdout summary, which G2 keeps unchanged.
- Guard: AT-C4 (the intent and quiet checks) and AT-C1 (JSON unchanged). No new sentry: the rule has one site and no realistic second one (`cross-cutting-concerns.md`: do not add a registry for a one-site rule). The engine side holds the cross-route choke point and its guard (parent AT-2).
- Mutations that must turn a named test red: drop the `intent == "default"` check (AT-C4, `--no-native` cell); drop the quiet check (AT-C4, `--quiet` cell); append the notice to `ctx._cli_warnings` instead of printing it (AT-C1, JSON equality); restore the `info_message` branch (AT-C2).

### 3.1 Class table

| # | Class | Where it applies | Structure that closes it | Proof | Mutation that must turn it red |
|---|---|---|---|---|---|
| 1 | Value-bearing output | the warning line | registry summary plus one CLI constant; no config text is formatted in | AT-C3 | add the table name to the line |
| 2 | Cleanup on exit path | none | N/A: nothing is opened; one print | n/a | n/a |
| 3 | State and concurrency | none | N/A: one pure function, no shared state | n/a | n/a |
| 4 | Route parity and silent fallback | every `run_pipeline` route | the engine sets the field once for all routes (parent AT-2); the CLI has one call site after the one `run_pipeline` call | AT-C1 | move the call into `execute_preview` only |
| 5 | Referential integrity | none | N/A: no key or FK value is read | n/a | n/a |
| 6 | Untrusted producer | the engine field | `reasons.find` admits registered codes only | AT-C6 | print the raw field value |
| 7 | Check then use (TOCTOU) | none | N/A: advisory text, drives no data path | n/a | n/a |
| 8 | Weak tests | a test that passes because the node has or lacks the companion | each test sets the field itself with `dataclasses.replace` | AT-C1, AT-C4 | let the real engine field decide |
| 9 | Refactor drift | the removed pre-run hint | AT-C2 asserts no `native:` line | AT-C2 | keep the old hint |
| 10 | Frozen contract drift | `--json` envelope | the notice stays out of stdout JSON | AT-C1, `test_json_shapes.py` | add the notice to `warnings` |

## 4. Failure modes

| Case | Behavior |
|---|---|
| Unknown or non-string code (a future engine) | `find` gives None. Nothing prints. No exception |
| The notice failed inside the engine | The field is None. Nothing prints |
| The run fails after the notice (verify, vault, write) | The warning line, then the usual error line. The warning is still true |
| `--native` and no kernel ran | `post_run_verify` refuses as today. No notice (require intent) |
| Companion present but broken | Refused before the run as today (`_native_gate.py:376-385`) |
| Healthy companion | The engine sets None. Nothing prints |

## 5. Acceptance tests, red first

New `tests/e2e/run_native/__init__.py` and `tests/e2e/run_native/test_missing_warn.py` (about 100 lines). Each test wraps the real `decoy_engine.run_pipeline` and returns `dataclasses.replace(result, native_fallback_code=X)`. X is `str(decoy_engine.reasons.warning.NATIVE_COMPANION_MISSING)` or None, so the host's companion never decides the result. The status probe is patched to absent with `monkeypatch.setattr("decoy_engine.native_companion_status", ...)`, as in `tests/e2e/test_run_native.py:93-94`. The config is that file's 10-row hash config. The code is never written as a string literal (sentry `tests/sentry/test_engine_reason_code_copies.py`).

- AT-C1: `decoy run CFG` with X set: stderr has exactly one line that contains `No compiled kernel ran`, and that line equals the G1 text. Then `decoy run CFG --json --no-library` with X set and with X None: parse both stdouts, drop the volatile fields the parent names (top-level `elapsed_s`; `result.invocation_id`; `result.timings` `started_at`, `finished_at` and `elapsed_s`; each `result.timings.phases[*].elapsed_s`; each `result.tables[*].elapsed_s`), and assert the two are equal. The `--json` run with X set has the G1 line on stderr.
- AT-C2: (red first with AT-C1 and the unit test; AT-C3 to AT-C6 are regression cells and pass without the feature) absent companion, X None: no stderr line starts with `native:`.
- AT-C3: the G1 line contains no table name, column name or source path from the fixture.
- AT-C4: X set, once each with `--no-native`, `--chunked` and `--quiet`: `No compiled kernel ran` is on neither stderr nor stdout, and the exit code equals that of the same run with X None.
- AT-C5: `decoy run GEN_CFG --rows 5` prints no notice.
- AT-C6: X = `"not_a_registered_code"` and X = `3`: exit 0 and no notice.

Changed test: `tests/unit/test_native_gate.py:651-662`. Rename it to `test_default_on_eligible_shape_with_absent_companion_is_silent` and assert `info_message is None`. Do not delete it. Add two unit cases for `fallback_notice` in the same file: default intent with the code gives the G1 text after `warning: `; `disable` and `require` give None.

Command (T1, through `~/bin/vm-run` or `~/bin/pytest-one`):

```
pytest tests/e2e/run_native tests/unit/test_native_gate.py tests/e2e/test_run_native.py tests/e2e/release_freeze/test_json_shapes.py -q
```

Expected: all pass after C1. On `origin/main` with the 0.28.3 pin, AT-C1 and AT-C2 and the renamed unit test fail (no notice, hint still set).

## 6. Placement and size

| File | Change | CODEMAP "Where Things Go" row | Beside |
|---|---|---|---|
| `src/decoy/_native_gate.py` (492 lines) | add `FALLBACK_HINT` and `fallback_notice`; remove the absent `info_message` branch (net about +12) | "Private shared ... primitives" names `src/decoy/_native_gate.py` | `classify_route` |
| `src/decoy/cli/run/_execute.py` (445 lines) | the 3-line call after `:390`, plus imports of `warn` and `OutputMode` | "`decoy run` internals" | existing |
| `src/decoy/api.py` | reword the comment at `:583-591` only | "Python API" | existing |
| `tests/e2e/run_native/` (new package) | AT-C1 to AT-C6 | "`decoy run` internals": tests in `tests/e2e/`, new ones in a package (the flat folder has 109 entries) | `tests/e2e/test_run_native.py` |
| `tests/unit/test_native_gate.py` | one test changed, two added | existing | existing |
| `CHANGELOG.md` | one `Changed` entry under Unreleased | repo convention | existing |

Size: about 130 lines with tests, about 20 of them source. Files touched: 6 (one new test package). New public names: none (`fallback_notice` and `FALLBACK_HINT` are in a private module). No module passes its size cap. No `--json` shape change, so no `json-shapes.json` or shape-changelog update. At close: roadmap row to MERGED, shipped log, Slack explainer.

### 6.1 Enumerations

#### Exit paths

- Normal return: the notice is checked after `ctx._execution = result` (`src/decoy/cli/run/_execute.py:390`).
- `post_run_verify` refusal under `--native` (`src/decoy/_native_gate.py:450-464`): require intent, so no notice.
- Vault or write failure after the notice (`src/decoy/cli/run/_execute.py:404-406`): the line was printed and is still true.

#### Routes

- Every non-chunked `run_pipeline` route (unified slice, auto-chunk, SEQ, OOC, mixed) returns to the one call site at `src/decoy/cli/run/_execute.py:390`.
- `--chunked` (`src/decoy/cli/run/_execute.py:333-347`) and `--rows` (`execute_preview`, `:423`) do not reach it, by design (G3).
- `run --all` inherits the notice from its child runs. `demo` uses a separate adapter and deliberately skips it.

#### FK shapes

- N/A. The CLI reads one result field, never keys.

#### Fields

- Read: `ExecutionResult.native_fallback_code` (engine v0.28.3, `execution/_pipeline.py:361`).
- Read: `RunContext.native_intent` (`src/decoy/cli/run/_prepare.py:556`) and `ctx.state.mode`. No field is written.

#### Output surfaces

- New: one stderr line.
- Removed: the pre-run `native:` hint (`src/decoy/cli/run/_prepare.py:564-568` no longer fires for this cause).
- Unchanged: stdout JSON (`src/decoy/cli/run/_render.py:117-153`), the summary card, the run result document and evidence.

### 6.2 Reuse inventory

| Need | Reused |
|---|---|
| The decision and the code | engine `with_native_notice` (v0.28.3) |
| The message text | engine `reasons.find("warning", code).summary` |
| The warning style | `warn("warning:")` on `ctx.state.err_console`, as `_prepare.py:569-570` |
| The test fake | the real-`run_pipeline` wrapper pattern of `tests/e2e/test_run_native.py:585-615` |

### 6.3 Frozen contracts touched

None. `json-shapes.json` is unchanged (AT-C1, `test_json_shapes.py`). Exit codes are unchanged (AT-C4). Stderr text is not a frozen surface.

### 6.4 Slices

One slice, C1, CLI, R1, Codex gate, after the 0.28.3 re-pin merges.

### 6.5 Pre-mortem

- Rich wraps the line at 80 columns in CliRunner and AT-C1 sees two lines: `soft_wrap=True`.
- A test passes because the node has no companion and the real engine set the field: every test sets the field itself.
- A builder hard-codes `"native_companion_missing"` in a test: the engine reason-code copy sentry fails; import the constant.

## 7. Differences from the parent C1 section

- The parent reads `getattr(result, "native_fallback_code", None)` so an older engine prints nothing. With the 0.28.3 pin the attribute always exists, and `proportionality.md` says not to probe for what the pin guarantees. C1 reads `result.native_fallback_code` directly, and the parent's AT-C5 cell "a result without the attribute" is dropped. The unknown-code cell (AT-C6) stays, because `find` returns None by contract.
- The parent puts the check inline at the call site. C1 puts the decision and text in `_native_gate.fallback_notice` so the unit tests can reach it without a run. The call site and its position are the parent's.

## 8. Open questions (recommended answer first)

- Q1. Should `--json` also carry the notice as an item in `warnings`? Recommended: no for V1. This keeps the parent's G2 and the row text, and the stderr line already shows in CI logs. If it is wanted later, the change is additive (`/warnings` is opaque) and goes through `ctx.add_cli_warning` and `CLI_WARNING_CODES`.
