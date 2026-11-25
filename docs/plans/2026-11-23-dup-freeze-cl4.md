Status: plan

# 24zf DUP-FREEZE CL4: one exit-code owner and one error emitter on the run, demo, fit and scan hot lanes

Owner: Cam. Author: Opus plan agent. Date: 2026-11-23. Revision 4. Roadmap row: 24zf DUP-FREEZE (`docs/roadmap/groups/health.md:16`, "Not started: CL4"). Parent plan: engine `docs/plans/2026-11-13-dup-freeze.md` on `plan/dup-freeze`, slice row CL4 (line 1027) and AT-CL4-1 to AT-CL4-3. This file is the build copy for the CLI repo. Census items: `docs/records/2026-11-12-duplication-census/REMEDIATION.md:104-118` (C1, C2, C5, C7).

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md` (PLAN, Proportion), `cross-cutting-concerns.md`, `api-and-compatibility.md`, `proportionality.md`, `testing.md` (Test depth). CLI `docs/roadmap/working-rules.md:92-115` (hot lanes).

Read at CLI `origin/main` `6544b6ec` (after #400 merged as `87f87b59`).

Risk: R2. Exit codes change for `decoy demo` and for some `decoy run` failures, and `--json` error members and key order change for `run` and `scan`. All of these freeze at REL-GATE (row 93), so this must land before 1.0. Plan review: Dennis, then Codex. Tests: T0, T1, then a full CLI suite before merge (exit-code and frozen-contract trigger).

## Revision history

| Rev | Date | Change |
|---|---|---|
| 1 | 2026-11-23 | First draft |
| 2 | 2026-11-23 | Dennis R1 (GO-WITH-FIXES, 3 HIGH, 6 MEDIUM, 4 LOW). H1: G1 limited to the sites the owner sentry sees; the except-arm limit named; fit's `FitSourceError` arm goes to the owner, `--joint-max-cells` is a named override; other literal exits go to 24ze G-C1. H2: run exit changes listed, with an e2e AT. H3: AT-1 compares against a literal table recorded at base. M1: per-arm table (section 7.1). M2: `capacity:` only on the human line, no code there. M3: one capacity classification. M4: `_result.finish_error` with a new `hint` keyword, no new payload builder. M5: the pre-run `code` member goes to `code=`. M6: demo `PipelineValidationError` arm, explain and docstrings. L1 to L4: anchors after #400, "capped" wording, key-order and quiet ATs, `SmtpConfig.problem` order and the stderr detail |
| 3 | 2026-11-23 | Codex R2 (NO-GO, 3 V1, 2 V2-LOG). One code rule for `fail()` (section 5.2): every `code` leaves its members dict by `pop` and goes to `code=` after `is_reason_code`; this fixes the post-scan block (its `code` was passed in `context`) and the native refusal (its code had a hyphen) together. Native gate codes use `_` in place of `-` at the producer (section 7.3). Generic `run --quiet` prints the exception type, not `str(exc)`. `_host_only` drops URL userinfo. Section 7 now lists every demo exit change, the scan envelopes and the run wire changes. AT-1 table recorded in its own commit; AT-3 checks cleanup order; AT-10 compares full ordered envelopes. New AT-13 to AT-16 |
| 4 | 2026-11-23 | V1: one exception-text rule covers run errors, gate findings and notify warnings. DESIGN: run and tokenize share refusal context. V2-LOG: AT-3 checks an unpublished layout. AT-15 checks reachable refusals and top-level codes. AT-16 injects a canary at each exception boundary. |

## 1. Problem

Three commands still pick their own exit code for the main error path, and two modules still build their own error output. After REL-GATE, any of these that disagrees with the owner map is a 2.0 break.

1. `run/_errors.py` has its own category classifier. `demo.py` maps exceptions to 1 or 3 by hand. `fit.py` repeats the DP arms. The exit-code owner sentry allows these three sites through a baseline.
2. `run/_errors.py` and `scan.py` write the `--json` error dict and the stderr lines by hand instead of through `emit_error`.
3. `run/_prepare.py` has a dead `UnicodeDecodeError` arm.
4. `run/_notify.py` reads `DECOY_NOTIFY_SMTP_PORT` with a bare `int()`. A bad value puts the value in the message and drops every notify channel, the webhook included.

## 2. Dependencies

The parent row lists rows 62, 63a and 66. Status at `6544b6ec`:

- Rows 62 (RESULT) and 66 (F29 remainder) closed on 2026-11-20 (#352).
- Row 63a RUN-STREAM has C1a, C1b, C2 and M1 left. None of them touch `_errors.py`, `demo.py`, `fit.py`, `scan.py`, `_notify.py` or `_evidence.py`. C2 touches `run/_prepare.py` and `exit_codes.py`.
- PR #400 merged as `87f87b59` (scan.py lost 84 lines; `is_reason_code` added to `ui/output.py:209`). Anchors below are re-read after it.

So CL4 waits on no row. It shares files with two open items. Whichever merges second rebases.

| Open item | Shared file | Overlap |
|---|---|---|
| 63a C2 | `run/_prepare.py`, `exit_codes.py` | C2 removes obsolete refusals; CL4 changes one `except` line and adds one function |
| PR #399 (chunked `run_mask_chunked`) | `run/_errors.py:168`, `exit_codes.py` | #399 adds `is_out_of_memory`; CL4 calls it for the fixed out-of-memory text |

Order: #399 first, then CL4. If CL4 is built before #399 merges, the builder rebases on it and re-runs every AT mutation on the final head after the rebase. The `_errors.py` hot lane has no other writer.

## 3. Current code

| Site | What it does today |
|---|---|
| `src/decoy/cli/run/_errors.py:158-168` | Capacity check: `capacity_code` from `ExecutionError` or `DecoyError` codes, `out_of_memory` from `MemoryError` |
| `src/decoy/cli/run/_errors.py:179-204` | Category classifier (capacity, usage, runtime, findings), separate from `exit_code_for` |
| `src/decoy/cli/run/_errors.py:270-306` | `--json` payload dict literal: `config`, `mode`, published members, blocked members, `hint`, pre-run members, `error_kind`, `code`, `extra`, `reason`, `notify` |
| `src/decoy/cli/run/_errors.py:307-339` | Human `error:` and `capacity:` lines and hints, skipped in `--quiet` |
| `src/decoy/cli/run/_errors.py:342` | `_result.finish(ctx, document, payload)` |
| `src/decoy/cli/run/_result.py:382-414` | `report_error` and `finish_error`: run errors through `emit_error`, with `context` plus the RESULT members; no `hint` keyword |
| `src/decoy/cli/gate/_run.py:120-128` | `PreRunCheckError.json_members()` includes `code` |
| `src/decoy/cli/demo.py:353-369` | `PipelineValidationError` arm exits `EXIT_USAGE`; then `_exit_code = EXIT_USAGE` for three types, else `EXIT_RUNTIME` |
| `src/decoy/cli/fit.py:557-562` | `DistributionSnapshotError` from `--joint-max-cells` validation exits 1 (owner map says 3) |
| `src/decoy/cli/fit.py:645-654`, `:707-716` | DP arms: ProvenanceError 3, DpBudgetError 3 or 1, DpError and CarrierError 1 |
| `src/decoy/cli/fit.py:672-676` | `FitSourceError` (plain `Exception`, `src/decoy/cli/gen/_fit.py:28`) exits 1 (owner map says 3) |
| `src/decoy/cli/scan.py` `_emit_load_error` (`:188`, sites `:211`, `:221`), `_show` (`:482`, sites `:517`, `:529`), `_diff` (`:601`, sites `:631`, `:640`) | `emit_json` dict plus `err_console.print` pairs |
| `src/decoy/cli/run/_prepare.py:73` | `except (OSError, UnicodeDecodeError)`; the decode arm is dead since CL3 (`yaml.not_utf8` is a finding) |
| `src/decoy/cli/run/_notify.py:156` | `int(os.environ.get("DECOY_NOTIFY_SMTP_PORT") or 587)` inside the `except Exception` at `:175-180` |
| `src/decoy/cli/exit_codes.py:82-86`, `:196-198` | `EXIT_CAPACITY` docstring names only `run` and `validate preflight`; `exit_code_for` docstring says "Until CL4" |
| `src/decoy/cli/explain.py:465` | `explain exit-codes`: exit 5 names only `run` and `validate preflight` |
| `tests/sentry/defects/_exit_map_sites.py:9-14` | The owner scan sees `if`/`IfExp` and dict shapes that pick an `EXIT_*`; it does not see `except T: raise typer.Exit(code=EXIT_*)` |
| `tests/sentry/baselines/exit-code-owner.json` | Three allowed sites: `cli/demo.py::_demo`, `cli/fit.py::fit`, `cli/run/_errors.py::fail` |
| `tests/sentry/baselines/one-error-emitter.json` | Five `run/_errors.py::fail` keys, two `demo.py::_demo` keys, six `scan.py` keys |

## 4. Guarantee and non-goals

Guarantee:

- G1. Every exit site the exit-code owner sentry detects (an `if`, `IfExp` or dict that picks an `EXIT_*` from an exception) calls `exit_code_for` (`src/decoy/cli/exit_codes.py:179`). The owner baseline is empty. Limit, named in the sentry docstring: an `except T: raise typer.Exit(code=EXIT_*)` arm is not seen. About 79 such arms exist today (for example `tokenize.py:384`, `report.py:711`, `compile_explain.py:256`). They move under row 24ze G-C1 (the literal-exit sentry, shrink-only baseline of today's sites), which must merge before REL-GATE.
- G2. `decoy run`'s exit equals `exit_code_for(exc)` for every exception that reaches `fail()`.
- G3. `run` and `scan` errors go through `emit_error` (`src/decoy/ui/output.py:217`). Their keys leave the D7 baseline.
- G4. A bad `DECOY_NOTIFY_SMTP_PORT` fails only the email channel, with a value-free message, and does not change the run exit.
- G5a. A `code` reaches the run error output only through `emit_error`'s `code=`, never through `context`. Every code promoted to the top-level envelope passes `is_reason_code`.
- G5b. Run error lines in default and quiet mode, run JSON errors and notify warnings share the exception-text rule in section 5.2. Exception detail may contain only fixed text, codes and the exception type name. Notify targets show only the sanitized host.
- G5. The `run --json` error object validates against `docs/schemas/decoy-error-v1.schema.json` and keeps every member it has today except where section 7 names a change.

Non-goals: demo's D7 emission (stays in the baseline, V1+), moving `config_caused_generation_codes` (`_errors.py:42`; waits on the reason-code ratchet decision), `_evidence.py` (no D7 site left), any new exit code, the other literal-exit arms (24ze G-C1).

## 5. Design

One choke point per rule. Both exist already: `exit_code_for` for the exit, `emit_error` for the output. This slice removes the sites that bypass them.

### 5.1 Exit code

- `exit_codes.py` gains `run_category_for(exc) -> str | None`. It inverts the `("failed", category)` rows of `RUN_EXIT_MAP` (`exit_codes.py:135`) over `exit_code_for(exc)`. Exit 4 returns `None` (the caller sets `blocking_failed`). An exit with no row raises `RuntimeError`, so a new exit code cannot pass silently.
- `fail()` calls it after the existing ImportError and NER translations. The classifier at `_errors.py:179-204` and the unused `EXIT_CAPACITY` and `EXIT_USAGE` imports go.
- One capacity classification (M3): `is_capacity = category == "capacity"`. `capacity_code = getattr(exc, "code", None)` when it is in `capacity_codes()`, else `None`. `is_out_of_memory(exc)` (from #399) decides only whether the fixed out-of-memory text replaces the message. The checks at `_errors.py:158-168` go.
- `demo.py`: the `PipelineValidationError` arm exits `exit_code_for(exc)`, and the generic arm sets `_exit_code = exit_code_for(exc)`. Both `EXIT_*` imports go.
- `fit.py`: both DP arms become `exit_code_for(exc)`. `FitSourceError` joins `usage_error_types()` (it reports the caller's file, columns or flags: "could not read X as a CSV", a missing `--parse-dates` column, bad `--numeric-bins`), and its arm at `:672-676` exits `exit_code_for(source_error)`. No fit exit changes.
- `fit.py:557-562` (`--joint-max-cells`) stays 1 as a named override: it uses the engine's `DistributionSnapshotError` as a flag validator, and the owner map's 3 for that type is right for a snapshot that fails at run time. The arm gets a one-line comment, and 24ze G-C1 carries it with that reason.
- Docstrings: remove "Until CL4" from `exit_code_for` (`exit_codes.py:196-198`) and from the `tests/unit/test_exit_code_for.py` module docstring. Add `decoy demo` to the `EXIT_CAPACITY` docstring (`exit_codes.py:82-86`) and to `explain exit-codes` (`explain.py:465`).

### 5.2 Error output

- `_result.report_error` (`_result.py:382`) gains a `hint: str | None = None` keyword passed to both `emit_error` calls, and a `human_line: HumanLine | None = None` keyword. `HumanLine(text, code)` is a frozen dataclass in `_result.py`: the stderr text and code when they differ from the JSON `error` and `code`. No new payload builder; `_result.finish_error` is the one writer.
- `fail()` builds `context` from today's members: `config`, `mode`, `ctx.published_members()`, the blocked members, the pre-run members without `code`, `error_kind`, `extra`, `reason`, `notify`. It keeps `ctx.layout.abandon()` in JSON mode before the write, then calls `_result.finish_error(ctx, document, error_text, code=..., hint=..., context=..., human_line=...)`. The dict literal at `_errors.py:270-306` and the prints at `:307-339` go.
- Replace `PreRunCheckError.json_members()` at `cli/gate/_run.py:120` with `context_members()`. Return `error_kind`, optional `extra` and `messages`. The refusal already exposes its code as `.code`. Run (`cli/run/_errors.py:290`) and tokenize (`cli/tokenize.py:322`) both use this accessor. Remove tokenize's pop. Preserve its existing `code=findings[0].code` for layout errors.
- In `fail()`, take the pre-run code from `exc.code`. For post-scan only, pop the code from the dict returned by `blocked_run()`. The other sources are the capacity code and the native gate code. Pass the selected value via `code=` when it passes `is_reason_code`. Omit an invalid code. AT-15 checks the producer before this filter.
- Native gate codes (producer fix). `_native_gate.py:345` and `:383` build `native_require_{status.reason}` and `native_companion_{status.reason}`. The engine reasons `abi-mismatch`, `kat-corrupt` and `load-error` have hyphens, and `emit_error` refuses them. One helper, `_code_token(reason) -> str` in `_native_gate.py`, replaces `-` with `_`, and both f-strings use it. The message text keeps the engine's own reason (`(kat-corrupt)`), so `tests/e2e/test_run_native.py:299` and the other `reason in result.output` asserts stay as they are. `decoy preflight`'s `native_companion.code` is the engine reason, not a `NativeGateError` code, and does not change.
- For coded capacity exceptions, select fixed capacity text by code. Keep the memory hint and exit 5. Update the raw `GB of memory` assertion in `tests/e2e/test_run_capacity.py:77` to check the safe message.
- One hint per error (7.1). Where today two print, the specific hint wins over "rerun with --verbose".
- Form safe text where the exception enters the output path. In `fail()`, use `run failed (<ExceptionType>).` as the fallback for every mode. Keep a specific message only when its producer supplies fixed CLI or registry text or structured, value-free fields. An exception class or a length cap alone gives no such guarantee. Pass the same safe detail to `_result.finish_error` for human, quiet and JSON output. Keep the existing type-only notification summary.
- In `cli/gate/_layers.py:206,347`, build exception-derived findings from a fixed message and the type name. Keep the existing code and structured location. Apply the same rule to typed finding builders that accept free exception detail. The compile fallback reads `compile failed (<ExceptionType>).` This protects both the first-finding summary at `cli/gate/_run.py:106` and every nested JSON message.
- The notify writers are the warning logger in `notify.py` and the stderr printer in `cli/run/_notify.py`. Apply G5b before formatting either warning. Webhook, Slack, SMTP and per-channel dispatch catches pass only the type name as exception detail. The outer dispatch catch follows the same rule. Keep fixed delivery details, refusal codes and sanitized targets. Neither writer receives the exception object or its formatted text. AT-16 guards these writers through the CLI.
- `scan.py`: the three sites call `emit_error` with the human hint text as `hint=` and the context in section 7.4. `scan diff - -` has no `scan` member today and gets none. The JSON `suggestion` member stays.

### 5.3 Dead arm and SMTP port

- `_prepare.py:73` becomes `except OSError`.
- `_notify.py` reads the port with `env_int("DECOY_NOTIFY_SMTP_PORT", 587)` (`src/decoy/_env_flags.py:58`) in its own `try`. On `ValueError` it builds `SmtpConfig` with port 587 and a new field `problem: str | None` set to the value-free message. `send_email` checks `problem` first, before `configured` (`notify.py:376`), and returns `(False, smtp.problem)`: a user who set the port should see that error even if the host is also missing. `dispatch` (`notify.py:412`) wraps each channel, so the webhook still sends. The existing stderr warning prints `notify email to <host> did not deliver: DECOY_NOTIFY_SMTP_PORT must be a whole number.`
- Webhook host (G5b). Once the webhook keeps sending, its `target_host` reaches the run JSON `notify` member and the stderr warning. `_host_only()` (`notify.py:451`) returns `urlsplit(url).netloc`, which keeps `user:password@`. It becomes: `parts = urlsplit(url)`, then `parts.hostname` (brackets put back for an IPv6 literal) plus `:<port>` when `parts.port` is set. `parts.port` raises `ValueError` on a bad port; that falls into the existing `except` and returns `(unknown host)`. All callers (the warnings at `notify.py:282-350` and `dispatch` at `:430`) get the fix.

### 5.4 Guards

- The exit-code owner sentry (`tests/sentry/defects/test_exit_code_owner.py`) stays at equality with an empty baseline. Its docstring names the except-arm limit and points at 24ze G-C1.
- The D7 sentry is shrink-only, so the removed `run` and `scan` keys cannot come back.
- The env-reads baseline loses `cli/run/_notify.py::_dispatch_run_notifications::DECOY_NOTIFY_SMTP_PORT::1`.

Design notes: one new frozen dataclass, `HumanLine`, so the human form can differ from the JSON form without a flag argument. `run_category_for` is a view derived from `RUN_EXIT_MAP`, so the category fact keeps one home.

Established solutions: none needed. The slice reuses the repo's owner map, emitter, `report_error` and `env_int`.

## 6. Owner question: the `capacity:` label

Today `run` prints `capacity: <msg>` for a capacity failure and `error: <msg>` otherwise. `emit_error` prints `error: [code] <msg>`. `tests/e2e/test_run_capacity.py:76,87` assert `"capacity:"` in the output.

- (a) Prefix the human message only: `error: capacity: <msg>`, with no `[code]` on that line (through `HumanLine`). The JSON `error` uses the safe detail without the label; the JSON `code` stays. Exit 5 and `error_kind` stay the machine signal. **Recommended.**
- (b) Add a `label` keyword to `emit_error`. A flag argument used by one site.
- (c) Drop the word and update the two tests.

Default if no answer: (a). The label change is on the CHANGELOG Breaking line.

## 7. Behavior changes

### 7.1 Run error arms

Columns: today, then revision 4. "verbose" is "rerun with --verbose for the full traceback."

| Arm | Human line today | Human line rev 4 | Human hint today | Human hint rev 4 | JSON `code` | JSON `hint` today | JSON `hint` rev 2 |
|---|---|---|---|---|---|---|---|
| Pre-run usage | `error: <t>` | same | none | none | refusal code if valid | none | none |
| Pre-run capacity | `capacity: <t>` | `error: capacity: <t>` | none | none | refusal code if valid | none | none |
| Capacity (code or out of memory) | `capacity: <t>` | `error: capacity: <t>` | memory hint | memory hint | capacity code or none | none | memory hint |
| Native gate | `error: <t>` | `error: [<code>] <t>` | verbose | verbose | native code, `_` spelling (7.3) | none | verbose |
| Missing extra | `error: <t>` | same | verbose | verbose | none | none | verbose |
| Keyed secret refusal | `error: <t>` | same | none | none | none | none | none |
| Post-scan block | `error: <t>` | same | none | none | `post_scan.<code>` when the reason is known, else none (unchanged value, now a fixed member) | none | none |
| Raise rows | `error: <t>` | same | raise-rows, then verbose | raise-rows only | none | raise-rows | raise-rows |
| Vault commit | `error: <t>` | same | vault, then verbose | vault only | none | vault | vault |
| Generic | `error: <t>` | `error: run failed (<ExceptionType>).` | verbose | verbose | none | none | verbose |

In every arm the human lines now print in quiet mode. The new text column uses the safe detail from section 5.2 in all modes. The JSON error uses the same detail without the terminal label.

### 7.2 Other changes

- `decoy run` exits that change, because `exit_code_for` has arms the old classifier lacked: engine `EnvFlagError` (a `DecoyError` and `ValueError`, raised in the run phases and reaching `fail()` through `_flow.py:224-226`) 3 to 1; `ConfigFileError` 3 to 1; `DpError`, `CarrierError` and a `DpBudgetError` other than `dp_schedule_mismatch` 3 to 1. These match the documented contract (`explain.py:441-450`).
- `decoy demo` exits now match `run`. Demo's map (`demo.py:365-369`) gave 1 only to `PlanCompileError`, `PipelineValidationError` and `ConfigError`, and 3 to every other exception. Under `exit_code_for` (`exit_codes.py:179-270`):
  - capacity (a capacity-code `DecoyError`, `MemoryError`): 3 to 5;
  - `PostScanBlockedError`: 3 to 4;
  - 3 to 1: `ConfigFileError`; `EnvFlagError`; an `ImportError` for a known optional extra and `MissingExtraError`; a `GenerationError` with a code in `config_caused_generation_codes()`; `VaultError` with `vault_exists` or any code in `_vault_input_codes()` (wrong secret, not a vault, other format or protocol version); `DpError`, `CarrierError` and a `DpBudgetError` other than `dp_schedule_mismatch`; every other type in `usage_error_types()` (for example `ModelUnavailableError`, `PostScanRouteError`, `NerUnavailableError`, `MaskSecretError`, `ResourceError`);
  - unchanged at 3: `vault_tampered`, `ProvenanceError`, `dp_schedule_mismatch`, any other exception.
  All of these fit the documented usage contract (`explain.py:441-450`). Demo's stderr and JSON text do not change.
- `decoy fit` exits do not change (section 5.1).
- `run --json` and `scan --json` error key order is `command, status, error, code, hint`, then the context members, then (run) `result` and `result_status`. For a post-scan block, `code` moves from after `error_kind` to the fixed position; its value does not change.
- `run --json` gains a `hint` member on the capacity, native, missing-extra and generic arms (section 7.1).
- A bad SMTP port: the webhook still sends, and the email channel reports `DECOY_NOTIFY_SMTP_PORT must be a whole number.`
- Notify `target_host` (run JSON `notify[]`, stderr warnings, logs) drops URL userinfo: `https://u:p@hooks.example.com:8443/x` gives `hooks.example.com:8443`, not `u:p@hooks.example.com:8443`.

### 7.3 Native gate code spelling

`NativeGateError.code` uses `_` where the engine reason has `-`. This is the `run --json` `code` member and the attribute the Python API raises (`api.py:471`).

| Today | Rev 3 |
|---|---|
| `native_companion_abi-mismatch` | `native_companion_abi_mismatch` |
| `native_companion_kat-corrupt` | `native_companion_kat_corrupt` |
| `native_companion_load-error` | `native_companion_load_error` |
| `native_require_abi-mismatch`, `native_require_kat-corrupt`, `native_require_load-error` | same change, `native_require_` prefix |

Codes with no hyphen (`native_require_not_a_candidate`, `native_require_vault_active`, `native_require_no_evidence`, `native_flag_conflict`, `native_require_absent`) do not change. Without this change, a hyphen code makes `emit_error` raise before it writes, and the native refusal loses its envelope. `tests/e2e/test_run_native.py:287` and `tests/unit/test_native_gate.py:729` change their expected string to `native_companion_kat_corrupt` and keep the broken-companion setup (`_status("kat-corrupt", present=True, ok=False, ...)`).

### 7.4 Scan error envelopes

Exit 1 at every site, as today. No `code`: scan has no reason code for these. The `hint` member is the human hint as plain text.

| Site | Rev 3 `--json` members, in order | `hint` text |
|---|---|---|
| `_emit_load_error`, raw data | `command, status, error, hint, scan` | `scan it first: decoy scan <scan> --has-header --output scan.json` |
| `_emit_load_error`, other | `command, status, error, hint, scan` | `pass the JSON file produced by decoy scan --output scan.json` |
| `_show`, field not found | `command, status, error, hint, scan, field, suggestion` | `did you mean <suggestion>` or `list all fields with decoy scan fields <scan>` |
| `_diff`, both `-` | `command, status, error, hint` | `pipe one scan, pass the other as a path.` |

Today these objects have no `hint` member and put `scan` (and `field`) before `error`. The human lines are the same text as today and now print in `--quiet`.

CHANGELOG `## [Unreleased]`, Breaking:

> `decoy demo` now uses the same exit codes as `decoy run` (capacity 5, blocked findings 4, usage 1). `decoy run` now exits 1, not 3, for a bad `DECOY_*` environment flag, an unreadable config file and a differential-privacy request error. `run` and `scan` errors now go through the shared error emitter: they print in `--quiet` (a generic run error identifies the exception type in every mode), `--json` error members come in the standard order with a `hint` member where the terminal shows one, a capacity failure prints `error: capacity: <message>`, and an error with two hints shows only the specific one. Native refusal codes use `_` in place of `-` (`native_companion_kat_corrupt`). A notify target host no longer shows URL credentials.

## 8. Failure modes

| Failure | Handling |
|---|---|
| `exit_code_for` returns an exit with no `RUN_EXIT_MAP` row | `run_category_for` raises `RuntimeError`; AT-4 pins it |
| A pre-run context member uses the reserved key `code` | Both callers use `context_members()`. AT-8 checks the accessor and both envelopes. |
| A pre-run code that is not a valid reason code | Left out of `code=`, so `emit_error` does not raise; AT-8 seed |
| A post-scan block passes its `code` in `context` | `fail()` pops it from the `blocked` members; AT-13 expects exit 4 and the code |
| A producer emits a code that fails the rule (native hyphen) | Fixed at the producer; AT-14 runs the real broken-companion case; AT-15 checks codes promoted to the envelope |
| Free exception text reaches a run error or notify warning | G5b applies at the exception boundary. AT-16 exercises each source. |
| A webhook URL with credentials reaches `target_host` | `_host_only` keeps hostname and port only; AT-2 |
| The SMTP message echoes the env value | The `env_int` message is value-free; AT-2 asserts `abc` is absent |
| A rebase on #399 loses `is_out_of_memory` | AT-1 includes an `ArrowCapacityError` case once #399 is in; mutations re-run on the final head |
| An except-arm literal exit disagrees with the owner | Out of this slice's guard (G1 limit); 24ze G-C1 before REL-GATE |

## 8a. Defect classes

| # | Class | Applies | Structure that closes it | Proof and the mutation that turns it red |
|---|---|---|---|---|
| 1 | value | Exception detail and URL credentials can reach run output or notify warnings | G5b and the writers in section 5.2. Use `env_int` for the port and `_host_only` for the host. | AT-2 and AT-16 name the mutations. |
| 2 | cleanup | Yes, narrowly: `ctx.layout.abandon()` must run before the JSON is written | kept before `finish_error`; `_flow.py` `finally` unchanged | AT-3 records call order and asserts `abandon` comes before the write; mutation: drop the `abandon()` call in `fail()` (the `finally` call comes after the write, so the order check fails) |
| 3 | state | N/A: no state machine or concurrency touched | none | none |
| 4 | route | Yes: each command picking its own exit is a parity gap | `exit_code_for` as the one owner for the sites the sentry sees; owner baseline empty | AT-1, AT-5; mutation: re-add a baseline site |
| 5 | referential | N/A: no data rows handled | none | none |
| 6 | untrusted | N/A: no new producer; env input goes through the existing `env_int` | none | none |
| 7 | toctou | N/A: no path checks | none | none |
| 8 | weak | Yes: a parity test can compare a function with itself; a key check can test three keys of many | AT-1 compares with a literal table committed before the classifier goes; AT-10 compares full ordered key lists | AT-1, AT-10 |
| 9 | refactor drift | Yes: run and scan output, hints and quiet behavior change | section 7.1 table pinned by AT-6 and AT-9 | AT-6, AT-7, AT-9 |
| 10 | frozen contract | Yes: exit codes, the `--json` error shape and the native code spelling | `decoy-error-v1` schema validation, one code rule, member-set check, CHANGELOG Breaking line | AT-3 (mutation: drop a RESULT member), AT-13, AT-14 |

## 9. Acceptance tests

| AT | Test | Mutation that turns it red |
|---|---|---|
| AT-1 | Commit 1 of the branch, on main's code, before any source change: the builder runs the old classifier over every `_run_categories()` case (`tests/unit/test_exit_code_for.py`) and writes its literal output (`{case: (category, exit)}`) into the test file. The values are typed out, not computed from any function. Later commits change only the rows section 7.2 names, each with a comment naming the 7.2 line. After CL4: `exit_code_for(case)` and `run_category_for(case)` equal the table. A `run` and a `demo` capacity failure exit 5 (e2e). The PR body lists the table and each mutation's red result | Change the usage arm of `exit_code_for` to return 3 |
| AT-2 | `DECOY_NOTIFY_SMTP_PORT=abc` with a webhook target `https://hookuser:HOOKPASS@hooks.example.com:8443/x` and an email target, in default mode and in `--json`: the webhook is called; stderr has `notify email to ... did not deliver: DECOY_NOTIFY_SMTP_PORT must be a whole number.`; the JSON `notify` webhook entry has `target_host == "hooks.example.com:8443"`; `abc`, `hookuser` and `HOOKPASS` are not in stdout, stderr or captured logs; the run exit is the run's own. Unit cases for `_host_only`: userinfo with and without a port, an IPv6 literal, a bad port | Move the `env_int` call back inside the outer `try`; return `netloc` from `_host_only` |
| AT-3 | For generic, capacity, pre-run and post-scan JSON errors, validate the schema and compare the member set to base plus the listed additions. With an allocated run layout and no published file, assert the empty run folder is gone. Record `layout.abandon` and the envelope write in one event list. Abandon must come first when a layout exists. A published report survives and its path still resolves. | Drop `members(document)` from the context. Drop the pre-write `abandon()` call. |
| AT-4 | `run_category_for` on a stub that maps to exit 7 raises `RuntimeError` | Return `"runtime"` as a default |
| AT-5 | The exit-code owner baseline is empty and the sentry passes | Re-add `cli/fit.py::fit` to the baseline (the sentry fails on equality) |
| AT-6 | `scan show` with a bad field and `run` with a generic error, both in `--quiet`: stderr has `error:` and one `hint:` line. Added to `QUIET_CASES` in `tests/e2e/first_user/test_items_error_envelope.py:196` | Keep the `state.mode is not OutputMode.quiet` guard in `scan.py` |
| AT-7 | A `run` capacity failure prints `error: capacity: <t>` with no `[` before `capacity:`; its `--json` `error` has no `capacity:` prefix and keeps `code` | Pass the capacity code on the human line |
| AT-8 | Check the context accessor on a refusal with a code. Its keys are `error_kind`, `messages` and optional `extra`. Run emits the refusal code and exits 1 or 5. A seeded invalid top-level code is omitted. Tokenize emits the first layout finding code. Both envelopes keep all messages. | Include `code` in the accessor result. |
| AT-9 | Per-arm table (section 7.1): for each arm, the human hint lines and the JSON `hint` member equal the table | Print the verbose hint after the raise-rows hint |
| AT-10 | Key order: for each run arm in 7.1 and each scan site in 7.4, `list(obj)` equals the full ordered key list written as a literal in the test (`tests/unit/test_ui_emit_error.py` and the envelope e2e) | Build the run payload with `config` first; put `scan` before `hint` |
| AT-11 | `run` with an `EnvFlagError` patched into `run_pipeline` exits 1 (e2e) | Restore the classifier's `else: "runtime"` arm |
| AT-12 | `fit` with an unreadable CSV exits 1 through `exit_code_for`; `--joint-max-cells 0` exits 1 | Remove `FitSourceError` from `usage_error_types()` |
| AT-13 | The existing `tests/e2e/integrity/test_run_blocked.py:107` keeps passing unchanged: exit 4, `code == "post_scan.ner_blocked"`, schema-valid. Add: `list(doc)[:4] == ["command", "status", "error", "code"]` | Pass the `blocked` members into `context` without popping `code` (`emit_error` raises, the exit is not 4) |
| AT-14 | `tests/e2e/test_run_native.py:274` with the real broken companion (`_status("kat-corrupt", ...)`): exit 1, one schema-valid JSON object on stdout, `error_kind == "native"`, `code == "native_companion_kat_corrupt"`. The parametrized test at `:290` keeps `reason in result.output` for all three reasons | Remove the `_code_token` call from the `native_companion_` f-string |
| AT-15 | Call `pre_execution_gate` with an eligible config. Default refuses `abi-mismatch`, `kat-corrupt` and `load-error`. Require refuses those three plus `absent`. Check each actual exception for the exact prefixed code and `is_reason_code`. Healthy status in either mode and absent in default succeed. Exercise require with a noncandidate and an active vault, the CLI flag conflict and the post-run no-evidence gate through their real entry points. Assert the exact fixed code in each case. Apply `is_reason_code` to every promoted code from the native, capacity, post-scan and pre-run producers. Include source-file refusals. Leave nested finding codes such as `kat-corrupt` intact. | Skip normalization in the require branch. The require case for `kat-corrupt` must fail. |
| AT-16 | Run the canary cases below in default, quiet and JSON modes. Capture stdout and stderr separately. Route the notify logger to captured stderr at WARNING. Assert each injected call ran. Reject the canary in either stream and anywhere in the parsed JSON document. | Restore free exception text at each source in turn. Its own case must turn red on the final head. |

- Compile. Make `decoy_engine.plan.compile_plan` raise `ValueError("COMPILE-CANARY-42")` on a valid config. Expect exit 1. Check the safe compile message in the human summary and in both JSON `error` and `messages[]`. Mutate the compile finding back to `str(exc)`.
- Pipeline. Make `run_pipeline` raise `ValueError("ROWVALUE-CANARY-42")` after the gate passes. Expect exit 3. Check `run failed (ValueError).` and one hint on the human paths. Check the same error in JSON. Mutate the shared fallback to `str(exc)`.
- Transport. Set `--notify-on always` and configure a webhook. Make the webhook opener raise `ValueError("HOOKPASS-CANARY-42")`. Let real dispatch catch it. A successful run still exits 0. Check the failed delivery in JSON and the warning in default mode. Mutate the dispatch logger at `notify.py:439` to interpolate the exception. Also exercise a caught URL error, Slack and SMTP failure, and an exception from dispatch itself. Restore raw exception text in each affected warning to turn its case red.

The builder records each AT red at base where it is red, and re-runs every mutation on the final head after the rebase on #399.

## 10. Files allowed to change

`src/decoy/cli/exit_codes.py`, `src/decoy/_native_gate.py`, `src/decoy/cli/explain.py`, `src/decoy/cli/gate/_layers.py`, `src/decoy/cli/gate/_run.py`, `src/decoy/cli/tokenize.py`, `src/decoy/cli/run/_errors.py`, `src/decoy/cli/run/_result.py`, `src/decoy/cli/demo.py`, `src/decoy/cli/fit.py`, `src/decoy/cli/scan.py`, `src/decoy/cli/run/_prepare.py`, `src/decoy/cli/run/_notify.py`, `src/decoy/notify.py`, `tests/sentry/defects/test_exit_code_owner.py` (docstring only), `tests/sentry/baselines/exit-code-owner.json`, `tests/sentry/baselines/one-error-emitter.json`, the env-reads baseline, `tests/unit/test_exit_code_for.py`, `tests/unit/test_ui_emit_error.py`, `tests/e2e/first_user/test_items_error_envelope.py`, the gate, tokenize, notify, scan, demo, fit and run-error tests, `tests/unit/test_native_gate.py`, `tests/e2e/test_run_native.py`, `tests/e2e/integrity/test_run_blocked.py` (one added assert), the release-freeze JSON shape fixture if key order is pinned there, `tests/e2e/test_run_capacity.py`, `CHANGELOG.md`.

`src/decoy/ui/output.py` does not change.

## 11. Test selection

- T0: each touched file's own tests.
- T1: `tests/unit/test_native_gate.py`, `tests/e2e/test_run_native.py`, `tests/e2e/test_mask_api_native.py`, `tests/e2e/integrity/test_run_blocked.py`, `tests/unit/test_exit_code_for.py`, `tests/unit/test_ui_emit_error.py`, all of `tests/sentry/`, the notify tests, `tests/e2e/test_run_capacity.py`, `tests/e2e/test_preflight_capacity.py`, `tests/e2e/first_user/test_items_error_envelope.py`, the scan, demo and fit e2e tests, the explain tests, the release-freeze JSON shape test, plus import-impact selection.
- Before merge: full CLI suite on the merge head, diffed against the saved main baseline (exit-code and frozen-contract triggers).

## 12. Risks

- Demo and run exit changes are visible to users. They match the documented contract and land before REL-GATE.
- `--json` key order and new `hint` members: a JSON parser is not affected, a byte compare is. The release-freeze fixture may need a refresh in the same PR, named in the PR body.
- About 79 except-arm literal exits stay outside this guard until 24ze G-C1. That row must close before REL-GATE.
- Rebase churn with #399 and 63a C2. The order in section 2 limits it.

## 13. Size

About 150 source lines changed, net negative (the classifier, the second capacity check, two DP arms, demo's map, three scan pairs and the payload literal go). New names: `PreRunCheckError.context_members` replaces `json_members`, `run_category_for` in `exit_codes.py`, `_code_token` in `_native_gate.py`, `HumanLine` and the `hint` and `human_line` keywords in `_result.py`, the `SmtpConfig.problem` field. One slice, one PR.

## 14. Enumerations

Exit-map sites come from the exit-code owner scan (`tests/sentry/defects/_exit_map_sites.py`).

### Exit paths

- `cli/run/_errors.py::fail` (`_errors.py:179-204`): moves to `run_category_for` and `exit_code_for`.
- `cli/demo.py::_demo` (`demo.py:353-369`): both arms move to `exit_code_for`.
- `cli/fit.py::fit` (`fit.py:645-654`, `fit.py:707-716`, `fit.py:672-676`): move to `exit_code_for`.
- `fit.py:557-562`: named override, carried by 24ze G-C1.
- Notify (`_notify.py:156`): sets no exit; a bad port stays a channel failure.

### Routes

- `run`, in-memory and `--chunked`: both end in `fail()`.
- `demo`: `PipelineValidationError` arm and generic arm.
- `fit`: two DP arms and the source arm.
- `scan`: `_emit_load_error`, `_show`, `_diff`.

### FK shapes

N/A: no data rows handled.

### Fields

- New `SmtpConfig.problem: str | None` (`notify.py:107`).
- New `HumanLine.text` and `HumanLine.code` (`_result.py`).
- `NativeGateError.code`: hyphen reasons spelled with `_` (7.3).
- `NotifyResult.target_host`: hostname and port only.
- The `run --json` error document keeps every RESULT member (AT-3).
- `emit_error` fixed members: `command`, `status`, `error`, `code`, `hint`, then context.

### Output surfaces

- `run` stderr and `--json` document (`_errors.py:270-339`).
- `scan` stderr and `--json` (three sites above).
- Notify stderr warning line, email result string and `target_host` (`_notify.py:163-172`, `notify.py:376`, `notify.py:451`).
- Python API `NativeGateError.code` (`api.py:471`).
- Process exit codes for `run`, `demo`, `fit`.
- `explain exit-codes` text (`explain.py:465`).
- Demo stderr and `--json` text: unchanged.

## 15. Reuse inventory

`exit_code_for`, `usage_error_types` and `RUN_EXIT_MAP` (`exit_codes.py`), `is_out_of_memory` (from #399), `emit_error` and `is_reason_code` (`ui/output.py`), `_result.report_error` and `finish_error`, `env_int` (`_env_flags.py:58`), the exit-code owner sentry, the D7 one-error-emitter sentry, the env-reads sentry. The refusal owns its context fields. No new file is needed.

## 16. Frozen contracts

Exit codes (breaking for `demo` and some `run` failures), the `--json` error members and order for `run` and `scan` (breaking), the native refusal code spelling (breaking, 7.3), `docs/schemas/decoy-error-v1.schema.json` (unchanged, validated). All land before REL-GATE.

## 17. Slices

One slice, CLI repo, about 150 source lines. Merge after #399.

## 18. Pre-mortem

- The build keeps a private classifier "for the NER case". The empty owner baseline fails it, and AT-1 compares with the base table, not with itself.
- Key order changes break the release-freeze fixture and the builder edits the test to pass. The fixture change must be in the diff and named in the PR.
- `--quiet` now prints run errors and a script that greps stderr sees new lines. Covered by the CHANGELOG Breaking line.
- The builder puts a top-level code back in the refusal context or passes the `blocked` members straight into `context` and the refusal in `--json` becomes an internal error. AT-8, AT-13.
- The builder filters the hyphen native code out at `fail()` instead of fixing the producer, and the code silently leaves the envelope. AT-14 expects the code; AT-15 checks the producer.
- The builder writes the AT-1 table from `exit_code_for` after the change. Commit 1 holds the table before any source change; the reviewer checks it against main.
- The builder treats G1 as covering every literal exit. G1 names the limit, and 24ze G-C1 owns the rest.
