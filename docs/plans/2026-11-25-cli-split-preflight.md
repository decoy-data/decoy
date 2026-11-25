# CLI-SPLIT S2: split `cli/preflight.py` into a package

Status: plan

Row: CLI-SPLIT (`docs/roadmap/groups/health.md`, PR #410), slice S2 of 3. S1 is `cli/report.py` (PR #411), S3 is `cli/fit.py` (`docs/plans/2026-11-25-cli-split-fit.md`).

Base: `origin/main` at `d6b9e4c7`. `src/decoy/cli/preflight.py` is 839 lines there. All line numbers below are from that commit.
Risk: R1 (a move of private code with the public import path kept; no tool change). One Codex review. The test tier is still a full suite, because moved code and shared baselines are escalation triggers (see Test tier).
Rules consulted: `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md` (PLAN), `refactoring.md`, `architecture.md` (layout), `proportionality.md`, `testing.md` (Test depth), `workspace-and-vcs.md` (commit messages).

Pattern: S1 (PR #411, plan `docs/plans/2026-11-25-cli-split-report.md` on branch `plan/cli-split-report`) and the `cli/run/` split (PR #179). S2 uses the `split_from` ratchet map that S1 adds. It adds no tool code of its own.

## Guarantee

The change moves code and nothing else. After it:

- `decoy validate preflight` prints the same bytes to stdout and stderr and exits with the same code as before, for every input and flag (`--local`, `--json`, `--quiet`, `--verbose`, `--fail-on-warning`).
- The gate's preflight layer (`decoy validate`, and `decoy run` through `run_gate`) gives the same findings, in the same order, with the same exit codes.
- `decoy validate --help` and `decoy validate preflight --help` are byte-identical.
- `from decoy.cli.preflight import preflight, PREFLIGHT_EPILOG, CAPACITY_CHECK, PLAN_UNCOMPILABLE_CHECK` keeps working. These four public names form the new `__all__`. The old module had no `__all__`, so a wildcard import also pulled in names such as `ConfigFileError`. The compatibility claim covers the four names and every name the repo imports by name (checked against base); wildcard imports are compared to base by the import-compat test, and any name that drops out is either kept or listed in the PR body.
- No sentry count or ceiling goes up. Two go down: module-size loses its `preflight.py` entry, and package-fanout for `src/decoy/cli` goes from 28 (after S1) to 27.

Non-goals (recorded follow-ups, not blockers):

- No function body changes. No lint-debt fixes, no renames, no dedupe. The `validate preflight` command keeps its own copy of steps 1-3 (the `gate-single-entry-allow` reason says CONFIG-EXPLICIT C2 folds it onto the gate). That item stays open, re-anchored to the new module.
- The gate keeps using the private check functions, through one supported module (`preflight.readiness`, below). A public check API is a separate design change.
- The `capacity_source_unprofilable` string copy stays. Its engine-reason-code entry moves unchanged.

## Module map

`src/decoy/cli/preflight.py` becomes `src/decoy/cli/preflight/`. Each function, class and constant moves verbatim (Fowler: Move Module, then Move Function and Move Field). Each module imports only the names it uses. Sizes include about 20 lines of docstring and imports.

| Module | Holds (line ranges at `d6b9e4c7`) | Reason to change | Est. lines |
|---|---|---|---|
| `__init__.py` | Module docstring (L1-48), re-exports, `__all__` | the public surface | ~60 |
| `_result.py` | `CAPACITY_CHECK`, `PLAN_UNCOMPILABLE_CHECK` with their comments, `_CheckResult`, `_PreflightAccumulator` (L111-181) | the fields of one check result | ~90 |
| `_checks.py` | `_check_source_files` (L188-262), `_check_target_overwrite` (L265-298), `_check_native` (L521-580) | how a source, a target or the native companion is judged ready | ~200 |
| `_capacity.py` | `_file_sources_missing_on_disk`, `_check_capacity` (L306-513) | the out-of-core FK capacity verdict | ~230 |
| `readiness.py` | The one supported import path for the readiness checks: binds `_check_source_files`, `_check_target_overwrite`, `_check_native`, `_check_capacity` and `_PreflightAccumulator` from their owning modules. No logic. | which checks the gate and the command share | ~25 |
| `_render.py` | `_emit_preflight_result` (L734-836) | how the result is printed (card, `--json`, exit code) | ~120 |
| `_command.py` | `_PREFLIGHT_EPILOG` (L68-108), `preflight` (L588-731), `PREFLIGHT_EPILOG = _PREFLIGHT_EPILOG` (L839) | the step order of `validate preflight` | ~215 |

All modules are well under the 800-line cap. The package has 7 modules, under the 25-module fan-out cap. `_capacity.py` holds one large check and its one helper. It is the only module that asks the engine to price a job, so it is kept apart from the three small checks.

Imports run one way: `_result` is a leaf; `_checks`, `_capacity` and `_render` import from `_result`; `readiness` imports from `_result`, `_checks` and `_capacity`; `_command` imports `_result`, `_render` and `readiness`; `__init__` imports from `_result` and `_command`. No module imports `__init__`. The engine imports (`decoy_engine.execution`, `decoy_engine`, `decoy._native_gate`, `parse_pipeline_config`, `run_config_only_checks`) and the `decoy.cli.io` layout imports stay lazy inside function bodies, as today, so `--help` does not load the engine.

`readiness` is the single place the checks are looked up. `_command.py` calls them as `readiness._check_x(...)`, and `gate/_layers.py` imports `readiness` and calls them the same way, so both callers resolve each check on the same module at call time. A test spy patches the check on `readiness` and sees both routes.

`__init__.py` stays thin: no function definitions. It re-exports only the four public names, each with a named consumer (see Importers). Private names (`_PreflightAccumulator`, `_check_*`, `_emit_preflight_result`) are not re-exported. A re-exported private name invites a test to patch the package attribute, which the moved code no longer reads, so the patch would do nothing without failing. `not hasattr(package, "_check_capacity")` is asserted in the import-compat test.

Do the move as `git mv src/decoy/cli/preflight.py src/decoy/cli/preflight/__init__.py` first, then cut the modules out of it, so `git log --follow` and `git blame -C` keep the history.

## Placement

| New file | Directory | CODEMAP "Where Things Go" line | Sits beside |
|---|---|---|---|
| `__init__.py` and the 6 modules above | `src/decoy/cli/preflight/` | "Command-private helpers" (S1 adds `src/decoy/cli/report/` there). S2 adds `src/decoy/cli/preflight/` (the `decoy validate preflight` command package) to the same line. | `src/decoy/cli/report/`, `src/decoy/cli/run/` |
| `test_cli_split_imports.py` | `tests/unit/` | "Command-private helpers", tests column (`tests/unit/`) | `tests/unit/test_report_fidelity.py` |

## Importers

Keep the package path (no edit). These are the named consumers of the `__init__` re-exports:

- `src/decoy/cli/validate.py:422-423` (`PREFLIGHT_EPILOG`, `preflight as _preflight_command`).
- `src/decoy/cli/gate/_layers.py:393` (`CAPACITY_CHECK`, `PLAN_UNCOMPILABLE_CHECK`; see the table for its private names).

Import-path edits only (no assertion changes). Each one reaches a private name, or patches or parses a name where the moved code now is:

| Site | Today | After |
|---|---|---|
| `src/decoy/cli/gate/_layers.py:243` (lazy) | `from decoy.cli.preflight import _check_target_overwrite, _PreflightAccumulator` | `from decoy.cli.preflight import readiness`; calls `readiness._check_target_overwrite` and `readiness._PreflightAccumulator` |
| `src/decoy/cli/gate/_layers.py:393` (lazy) | `from decoy.cli.preflight import CAPACITY_CHECK, PLAN_UNCOMPILABLE_CHECK, _check_capacity, _check_native, _check_source_files, _PreflightAccumulator` | the two constants from `decoy.cli.preflight`; `readiness` for the four private names, called as `readiness._check_x` |
| `tests/e2e/project_layout/test_layout_gate.py:80` (`install_read_spy`, shared with `test_shared_destination_parity.py`) | `import decoy.cli.preflight as preflight`; patches `_check_source_files` and `_check_capacity` on it | patch both on `decoy.cli.preflight.readiness` |
| `tests/unit/project_layout/test_layout.py:92,114-115` | `from decoy.cli import preflight`; `preflight._PreflightAccumulator()`, `preflight._check_target_overwrite(...)` | `from decoy.cli.preflight import readiness` and the same calls on it |
| `tests/unit/test_ci_rule_codes.py:31,171` | `import decoy.cli.preflight as cli_preflight`; walks the AST of `cli_preflight.__file__` for the four check functions | walk every `*.py` in the package directory (`Path(cli_preflight.__file__).parent`), so a later move inside the package cannot hide a check. Add an assert that the scan visited all four check functions (`_check_source_files`, `_check_target_overwrite`, `_check_native`, `_check_capacity`), because the existing asserts accept a subset of codes and any non-empty template set |

How each edit fails if missed:

- `_layers.py` and `test_layout.py`: `ImportError` or `AttributeError` (loud). In `_layers.py` the imports are lazy, so the error comes at gate run time. The gate e2e tests run that path.
- `install_read_spy`: `monkeypatch.setattr` raises on a missing attribute (loud). The spy works only if every caller looks the check up on the module the spy patches. Both `_command.py` and `_layers.py` call `readiness._check_x`, so one patch covers `validate preflight` and the gate. The existing refusal test only asserts an empty read list, which a silent spy also satisfies. So add a control: on a valid input, each route (`validate preflight` and the gate) must record both `_check_source_files` and `_check_capacity` calls through the spy. A route that bypasses the spy turns the control red.
- `test_ci_rule_codes.py`: after the move `__file__` is `__init__.py`, which holds no check. The template half fails loudly (it asserts `templates` is non-empty, L313). The code half (`codes`) has no such assert and would go quiet. Walking the whole package closes both.

`tests/sentry/io_policy/test_pipeline_argument.py` reads `sys.modules[callback.__module__]`. The callback's module becomes `decoy.cli.preflight._command`, which holds the `setup_output` and `resolve_pipeline` calls, so it needs no edit.

Docs: the `src/decoy/cli/gate/_capacity_text.py` docstring says its text is "kept out of `preflight.py` for size". The builder changes it to `cli/preflight/` (comment only). Line anchors in `docs/records/` and dated plans stay as they are.

## Sentries and baselines that move

Re-home each entry to the new file at the same site. Every one-to-one re-key goes through the baseline's top-level `moved_from` map (`{new_key: old_key}`), with the entry byte-identical. The part after the last `::` stays the same in every re-key, as `_ratchet.py` requires. No count rises.

| File | Change |
|---|---|
| `tests/sentry/baselines/module-size.json` | Delete `src/decoy/cli/preflight.py` (max 839). Shrink. |
| `tests/sentry/baselines/package-fanout.json` | `src/decoy/cli` max 28 to 27. |
| `tests/sentry/baselines/lint-debt.json` | 4 keys (7 hits) become 7 keys. See below. |
| `tests/sentry/baselines/engine-reason-code-copies.json` | `moved_from`: `"cli/preflight/_capacity.py::capacity_source_unprofilable": "cli/preflight.py::capacity_source_unprofilable"` (count 1). |
| `tests/sentry/baselines/one-error-emitter.json` | `moved_from`: `"cli/preflight/_render.py::_emit_preflight_result::13b936a5128f": "cli/preflight.py::_emit_preflight_result::13b936a5128f"`, and the same for `::48e0f1638b82`. The hash covers the AST only (`tests/sentry/cli_text/_error_sites.py`), so it does not change. |
| `tests/sentry/baselines/gate-single-entry-allow.json` | `moved_from`: `"decoy.cli.preflight._command::preflight::preflight_check": "decoy.cli.preflight::preflight::preflight_check"`, and the same for `::run_config_only_checks`. The sentry keys a site by `(module, outermost function, rule)`, and the module of the command body changes. |
| `tests/sentry/allowlist-before.json` | The same re-keys and shrinks: L65 (`capacity_source_unprofilable`), L115-116 (gate-single-entry), L132 (module-size, delete), the `src/decoy/cli` package-fanout row (28 to 27). `test_baseline_registry.py` asserts each baseline equals this snapshot. |
| `tests/sentry/test_gate_single_entry.py:366,371` | The seeded file `"cli/preflight.py"` with module `"decoy.cli.preflight"` becomes `"cli/preflight/_command.py"` with `"decoy.cli.preflight._command"`, so the self-test still matches a real allowlist entry. The seeds at L212, L281, L286, L291 and L355 import from `decoy.cli.preflight`. The rule matches the last name only, so they stay valid and need no edit. `test_allowlist_has_reasons_and_unique_identities` (3 entries) is unchanged. |
| `tests/sentry/io_policy/test_output_placement.py:40` | `PREFLIGHT = "cli/preflight.py"` to `"cli/preflight/_checks.py"` (the module that holds `_check_target_overwrite`). If missed, `read_text` raises (loud). |
| `tests/sentry/io_policy/test_engine_base_dir.py:111` | The known call-site file `"cli/preflight.py"` becomes the two files `"cli/preflight/_command.py"` (`run_config_only_checks`) and `"cli/preflight/_capacity.py"` (`estimate_job_capacity`). If missed, the subset assert fails (loud). |
| `tests/sentry/layout/test_module_size.py:74,98` | The meta-tests seed a real legacy file: `LEGACY` (S1 sets it to `preflight.py`) and the key `src/decoy/cli/fit.py` at L98. S2 deletes the `preflight.py` entry, so these must change. Rewrite the three meta-tests to plant a synthetic file (`src/legacy.py`, `LIMIT + 10` lines) in `tmp_path` and pass `census` an allowlist built in the test. The proofs stay the same: grown by one line is red, shrunk asks for a ratchet down, removed from the allowlist is red. This pins no real file, so S3 does not edit this test again. Mutation: change the legacy equality check in a scratch copy of `size_reason` to accept `recorded + 1`; the "grown by one line" test must go red. (A `margin` change cannot do it: a legacy entry above `LIMIT` returns before `margin` is read.) |

No `preflight.py` entry exists in `.importlinter`, `csv-read-allow`, `private-file-sinks`, `canonical-json-allow` or `ci/vendored.toml`. The split adds no cross-layer import: `cli.gate` and `cli.preflight` are both in the `cli` tier.

### Lint-debt: one key becomes several

`ruff check --extend-select` with the `EXTRA_RULES` of `scripts/dev/lintdebt.py` (ruff 0.15.20, the dev lock pin) on `preflight.py` at `d6b9e4c7` gives 7 hits, equal to the baseline:

| Function (line) | Goes to | ANN401 | C901 | PLR0912 | PLR0915 |
|---|---|---|---|---|---|
| `_check_capacity` (351) | `_capacity.py` | | 1 | 1 | |
| `preflight` (588) | `_command.py` | | 1 | | 1 |
| `_emit_preflight_result` (734, `state: Any`) | `_render.py` | 1 | 1 | 1 | |
| Total (= today) | | 1 | 3 | 2 | 1 |

Baseline edits (S1's `split_from` and the existing `moved_from`, both top-level maps):

- `split_from`:
  - `"src/decoy/cli/preflight.py::C901"` to `_capacity.py::C901`, `_command.py::C901`, `_render.py::C901` (each under `src/decoy/cli/preflight/`, count 1 each);
  - `"src/decoy/cli/preflight.py::PLR0912"` to `_capacity.py::PLR0912`, `_render.py::PLR0912` (count 1 each).
- `moved_from`:
  - `"src/decoy/cli/preflight/_render.py::ANN401": "src/decoy/cli/preflight.py::ANN401"` (count 1);
  - `"src/decoy/cli/preflight/_command.py::PLR0915": "src/decoy/cli/preflight.py::PLR0915"` (count 1).

Every new entry keeps the old reason. The builder re-runs `scripts/dev/lintdebt.py` on the head. It must report exactly these 7 keys for the package and no other change. S1's own `split_from` and `moved_from` rows are leftovers by then (their new keys are in the base). They stay, and `_ratchet.py` ignores them.

## Acceptance tests

1. Existing tests pass with no assertion edits. The only test edits are the import paths and sentry tables listed above.
2. Import-compat test (new, kept): `tests/unit/test_cli_split_imports.py`. S2 creates it; S3 adds its cases. One parametrized test asserts that `decoy.cli.preflight.__all__` is exactly the four public names, that each resolves to the object its owning submodule defines (`preflight is _command.preflight`, `CAPACITY_CHECK is _result.CAPACITY_CHECK`), and that `validate.py`'s `_preflight_command` is that same object. It also asserts `not hasattr(decoy.cli.preflight, "_check_capacity")` and that the wildcard-import name set is compared to a base snapshot taken from `git show origin/main:` (names kept or listed). Mutations that must turn it red: re-export `_check_capacity` from `__init__`; bind `_check_capacity` on the package.
3. Golden byte check. A throwaway harness (outside the tree; its script and per-case hash table go in the PR body) runs on the base commit and on the head and compares stdout, stderr and exit code byte for byte for:
   - `decoy validate preflight` on: a clean pipeline; a missing source file; an unreadable source; a target that already exists; a capacity fail and a capacity warn (the configs and injected fixtures in `tests/e2e/test_preflight_capacity.py`: the memory-budget patch and the estimator failure); an uncompilable plan; the native cases from `tests/e2e/test_preflight_native.py` with their companion-status fixtures; a layout refusal (`tests/e2e/project_layout/test_layout_gate.py`, covers the `EXIT_USAGE` layout exit); a YAML error; a schema error. Each with no flag, `--json` and `--quiet`, plus `--fail-on-warning` where a warning exists, and one `--local` run;
   - `decoy validate` (the gate) on the capacity-fail, missing-source and target-exists configs, with and without `--json`;
   - `decoy validate --help` and `decoy validate preflight --help`.
   Each cell applies the same fixture on both revisions and first asserts its expected status and exit code (for example capacity fail exits `EXIT_CAPACITY`), then compares bytes. A cell whose fixture did not take effect fails before the compare. The harness first runs the base tree twice. Any field that differs between those two runs (timestamps, temp paths) is listed and masked. Everything else must match exactly. `--verbose` traceback text is out of scope because it names file paths.
4. Ratchet equal, not raised: the ratchet check against the merge base reports no finding, and the total of the preflight lint-debt counts is 7 before and after. These pass: `tests/sentry/layout/test_module_size.py`, `test_package_fanout.py`, `test_import_layers.py`, `test_codemap_paths.py`, `tests/sentry/test_lint_debt.py`, `test_baseline_registry.py`, `test_ratchet_check.py`, `test_sentry_manifest.py`, `test_gate_single_entry.py`, `tests/sentry/io_policy/` and `tests/unit/test_ci_rule_codes.py`.
5. `ruff check`, `ruff format --check` and `mypy` are clean on the head.
6. Every new module is under 800 lines, and `__init__.py` defines no function (checked at review).

## Enumerations

Every path below keeps its code and its order. The golden check in acceptance test 3 has a cell for each one.

### Exit paths

All exits are in `preflight` and go to `_command.py` unchanged:

- unreadable config: `exit_code_for(exc)` (`src/decoy/cli/preflight.py:661`);
- schema problem or validation error: `EXIT_USAGE` (`src/decoy/cli/preflight.py:677`, `src/decoy/cli/preflight.py:681`);
- plan-compile error: `EXIT_USAGE` (`src/decoy/cli/preflight.py:696`);
- layout failure: `EXIT_USAGE` (`src/decoy/cli/preflight.py:705`);
- capacity insufficient, before the generic fail: `EXIT_CAPACITY` (`src/decoy/cli/preflight.py:727`);
- any other fail: `EXIT_USAGE` (`src/decoy/cli/preflight.py:729`);
- `--fail-on-warning` with a warning: `EXIT_WARNINGS` (`src/decoy/cli/preflight.py:731`);
- clean: exit 0.

### Routes

- `decoy validate preflight` reaches `preflight` through `src/decoy/cli/validate.py:422`.
- `decoy validate` and `decoy run` reach the check functions through the gate's lazy imports (`src/decoy/cli/gate/_layers.py:243`, `src/decoy/cli/gate/_layers.py:393`).

### FK shapes

N/A: the split moves no FK logic. `_check_capacity` passes the config to the engine estimator and reads back its verdict; that call is unchanged.

### Fields

N/A: no `--json` field is added, renamed or removed. The payload is built in `_emit_preflight_result` (`src/decoy/cli/preflight.py:745`) and moves as is.

### Output surfaces

- stdout: the `OK` line and the `--json` payload (`src/decoy/cli/preflight.py:830`).
- stderr: the `warning:` and `fail:` lines, the capacity block and the native block (`src/decoy/cli/preflight.py:792`, `src/decoy/cli/preflight.py:807`, `src/decoy/cli/preflight.py:820`).
- exit code (see Exit paths). Preflight writes no file.

## Reuse inventory

- Ratchet maps: `moved_from` (PR #179) and `split_from` (PR #411) in `tests/sentry/_ratchet.py`. No new tool code.
- Package shape: `src/decoy/cli/run/` and S1's `src/decoy/cli/report/`.
- Lint-debt counting: `scripts/dev/lintdebt.py`, unchanged.
- Golden harness: the same base-twice, mask, compare method as S1. It stays out of the tree.

## Frozen contracts

- The `decoy.cli.preflight` import path and the four names in `__all__`.
- The `decoy validate preflight` CLI: flags, help text, stdout, stderr, `--json` schema and exit codes.
- The gate's preflight findings (names, order, exit codes) seen through `decoy validate` and `decoy run`.
- The sentry allowlist identities, re-keyed only through `moved_from` or `split_from`.

## Defect classes

| # | Class | Applies | Structure | Proof (mutation) |
|---|---|---|---|---|
| 1 | value | N/A: no data path changes; error text stays value-free | existing value-free sentries | acceptance test 3 |
| 2 | cleanup | N/A: preflight writes no file | none | none |
| 3 | state | N/A: `_PreflightAccumulator` is built per call, never shared | none | none |
| 4 | route | Yes: a patch on the package attribute no longer reaches the moved code (`install_read_spy`); an AST walk of `__init__.py` finds nothing (`test_ci_rule_codes.py`) | private names not re-exported; one `readiness` lookup module; patch `readiness`; walk the whole package | on a scratch copy, walk only `_checks.py` in `test_ci_rule_codes.py`; the visited-functions assert (all four) must go red |
| 5 | referential | N/A: no rows change | none | none |
| 6 | untrusted | N/A: no child process or extension | none | none |
| 7 | toctou | N/A: the source checks keep the same reads in the same order | existing `test_layout_gate.py` read-order asserts | acceptance test 1 |
| 8 | weak | Yes: a byte check that masks too much passes anything | mask only fields that differ between two base runs, and list them | change one check message on a scratch copy of the head; the golden check must go red |
| 9 | refactor drift | Yes: output, exit codes, gate finding order, help | golden byte check on base and head | acceptance test 3; swap the native and capacity steps in `preflight` on a scratch copy, the `--json` cells must go red |
| 10 | frozen contract | Yes: the `decoy.cli.preflight` import path and the gate allowlist identities | `__all__`, import-compat test, `moved_from` | acceptance test 2 (both mutations); a gate-single-entry key re-keyed without `moved_from` must fail the ratchet check |

## Design notes

- Principle: split along a reason to change (`architecture.md`, layout). Readiness checks, the capacity verdict, the result printer and the command's step order change for different reasons, and each now has one file.
- Pattern followed: S1 and the `cli/run/` package (thin `__init__`, private sibling modules, `git mv` first, `moved_from` and `split_from` for baselines).
- One place per fact: the two check-name constants and the result types sit in `_result.py`. Every other module reads them from there; the gate reads the constants through the package.
- New structure added: the package (the 800-line cap asks for it) and one import-compat unit test. Nothing else.

## Established solutions

No new design problem: this is a module move. The steps follow Fowler's catalog (Move Module, Move Function, Move Field). The baseline moves use the repo's own ratchet maps (`moved_from` from PR #179, `split_from` from PR #411). The package shape copies `src/decoy/cli/run/` and S1. No external search was needed beyond that catalog, and no custom code is added.

## Slices

One slice, one PR (this plan). It is slice S2 of the CLI-SPLIT row; S1 is #411 and S3 is the fit plan. The five commits under "Size and commits" are steps inside this slice, not separate PRs.

## Blocks on #411, conflicts and merge order

S2 depends on #411 in three ways:

- `split_from` exists only on #411's branch (`tests/sentry/_ratchet.py`). Without it, the C901 and PLR0912 splits would need `approved_growth` rows.
- #411 sets `test_module_size.py` `LEGACY` to `preflight.py` and package-fanout to 28. S2 edits both again.
- S2 edits the same ledgers: `lint-debt.json`, `one-error-emitter.json`, `module-size.json`, `package-fanout.json`, `allowlist-before.json`.

Order: build S2 from `origin/main` after #411 merges. If the builder starts before that, it branches from `feat/cli-split-report` (head `301e703c` at planning time). It opens its PR against `main` only after #411 has merged and the branch is rebased onto main (`git rebase --onto origin/main <#411 head> <S2 branch>`). A PR based on `feat/cli-split-report` is not allowed: a PR merged into a non-main base never ships (#749 on 2026-11-22).

Open PRs on 2026-11-25 (`gh pr list -R decoy-data/decoy --state open`, 16 open): only #411 touches `preflight.py`, `gate/_layers.py` or the ledgers above. Every remote branch with commits after 2026-11-10 that touches `preflight.py`, `fit.py` or `gate/_layers.py` is merged (for example #309, #347, #359, #363, #371, #375, #383, #384, #386, #406).

S3 (`fit.py`) goes after S2. S2 makes the module-size meta-tests synthetic and sets package-fanout to 27; S3 removes the last legacy entry and sets 26. On a rebase conflict in a shared ledger, keep both sides, then re-run the ratchet check.

Builders of any row launched while S2 is open wait for it if the row edits `preflight.py` or `gate/_layers.py`.

## Pre-mortem

If this slice fails, the likely causes are:

- A lazy import in `_layers.py` that still names `decoy.cli.preflight` for a private name, or a direct `from ._checks import` in `_command` that bypasses the `readiness` lookup (the spy control catches it). It fails only at gate run time. The gate e2e tests in acceptance test 1 reach it.
- A circular import if `_result` ever imports from `_command` or `__init__`. The one-way order above prevents it. `python -c "import decoy.cli.preflight._result"` in a fresh process proves it.
- An engine import moved to module top level by accident: `--help` would load the engine. The golden `--help` cell does not measure time, so the builder greps the new modules for top-level `decoy_engine` imports. `preflight.py` has none today, and the package must have none.
- A patch site in a test left on the package path. `monkeypatch.setattr` raises on a missing attribute, but `mock.patch(..., create=True)` does not. S2 has no `create=True` patch on preflight (checked with grep at planning time). The builder repeats that grep on the head.
- A ledger conflict with another branch that re-homes an entry in the same baseline. Keep both sides and re-run the ratchet check.

## Test tier

Moved code, edited sentry tables and `allowlist-before.json` are full-suite triggers. T0: the touched test file per edit. T1 per commit: `tests/e2e/test_preflight_*.py`, `tests/e2e/test_run_preflight_capacity_parity.py`, `tests/e2e/project_layout/`, `tests/unit/project_layout/test_layout.py`, `tests/unit/test_ci_rule_codes.py`, the import-compat test and the sentries in acceptance test 4. Before the merge: one full suite (CLI `gates.sh --full`, or `decoy-vm-t3` default mode) on the exact merge head, failing ids diffed against the saved main baseline. No new logic, so the mutation evidence is the scratch mutations in the defect table.

## Size and commits

One PR. About 900 lines added and 850 removed, nearly all of it the move, so review with `git diff --color-moved=dimmed-zebra -M`. Files: 1 removed and 7 added under `src/decoy/cli/preflight/`; `gate/_layers.py` (two lazy import lines) and `gate/_capacity_text.py` (docstring); 3 test files with import-path edits; 1 new test file; 6 baselines plus the snapshot; 4 sentry test files with table or seed edits; `CODEMAP.md`. No new public names.

Commits (Conventional Commits, last line `cam`, no body unless it explains why):

1. `refactor(preflight): move preflight.py into a preflight package` (the `git mv` only)
2. `refactor(preflight): split the preflight command into modules`
3. `test(sentry): re-home preflight baselines to the new modules`
4. `test(cli): pin the preflight package import surface`
5. `docs(codemap): place the preflight package`

The branch merges squashed. Commits 1 and 2 can leave sentries red until commit 3. The head is what gets gated.

## Owner decisions

None needed. Defaults taken, each open to change in review:

1. `_render.py` is separate from `_command.py`. Joined they would be about 335 lines and still under the cap. They are kept apart because output format and step order change for different reasons, and S1 split its renderers the same way.
2. `CAPACITY_CHECK` and `PLAN_UNCOMPILABLE_CHECK` stay on the package path, and `_layers.py` reads them from there. That keeps the public import surface the same and gives the re-export a named consumer.
