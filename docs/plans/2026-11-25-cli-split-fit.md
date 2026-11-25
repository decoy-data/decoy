# CLI-SPLIT S3: split `cli/fit.py` into a package

Status: plan

Row: CLI-SPLIT (`docs/roadmap/groups/health.md`, PR #410), slice S3 of 3. S1 is `cli/report.py` (PR #411), S2 is `cli/preflight.py` (`docs/plans/2026-11-25-cli-split-preflight.md`).

Base: `origin/main` at `d6b9e4c7`. `src/decoy/cli/fit.py` is 811 lines there. All line numbers below are from that commit.
Risk: R1 (a move of private code with the public import path kept; no tool change). One Codex review. The test tier is still a full suite, because moved code and shared baselines are escalation triggers (see Test tier).
Rules consulted: `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md` (PLAN), `refactoring.md`, `architecture.md` (layout), `proportionality.md`, `testing.md` (Test depth), `workspace-and-vcs.md` (commit messages).

Pattern: S1 (PR #411) and S2. S3 uses the `split_from` ratchet map that S1 adds. It adds no tool code of its own.

## Guarantee

The change moves code and nothing else. After it:

- `decoy fit` prints the same bytes to stdout and stderr, writes the same snapshot file, and exits with the same code as before, for every input and flag.
- `decoy fit --help` and `decoy --help` are byte-identical.
- `from decoy.cli.fit import fit, FIT_EPILOG` keeps working. Their consumer is `src/decoy/__main__.py:25-26`.
- Named and wildcard imports keep working for every non-underscore name the old module bound. The old module had no `__all__`, so `from decoy.cli.fit import *` and `from decoy.cli.fit import read_fit_csv` reached the names it imported as well as the ones it defined. The package keeps that set exactly. The set at `origin/main` (`d0826aa9`), computed with `{n for n in vars(module) if not n.startswith("_")}`, is: `Any`, `AtomicWriteError`, `EXIT_RUNTIME`, `EXIT_USAGE`, `FIT_EPILOG`, `FIT_SAMPLE_SEED`, `FitSourceError`, `OutputMode`, `Path`, `ResourceError`, `WriteMode`, `annotations`, `code`, `describe`, `emit_error`, `emit_json`, `exit_code_for`, `fit`, `fit_exact_snapshot`, `hint`, `json`, `math`, `read_fit_csv`, `read_fit_max_rows`, `setup_output`, `side_file_default`, `strict_csv`, `success`, `typer`, `warn`, `write_local_target`. `__init__.py` binds each one from the submodule that uses it (`_command` or `_args`) and sets `__all__` to the same sorted list, so a wildcard import gives the same names as before. Only `fit` and `FIT_EPILOG` have an importer today (`src/decoy/__main__.py:25-26`); the rest are kept because a user script might use them.
- Keeping these names on the package brings back one risk: a test that patches `decoy.cli.fit.read_fit_csv` sets an attribute that `fit` never reads, so the patch does nothing and the test still passes. The import-compat test therefore scans `tests/` for patch-target strings (`mock.patch("...")`, `monkeypatch.setattr("...")`) that name `decoy.cli.fit.<attr>` directly on the package and fails on any it finds. Patch targets must name the submodule where `fit` looks the name up (`decoy.cli.fit._command.read_fit_csv`), as the patch-site table below does.
- No sentry count or ceiling goes up. Two go down: module-size loses its last entry (`fit.py`), and package-fanout for `src/decoy/cli` goes from 27 (after S2) to 26.

Non-goals (recorded follow-ups, not blockers):

- No function body changes. `fit` stays one 556-line function (L253-808) with its nested helpers `_emit_error`, `_emit_dp_refused` and `_unreadable`. Extract Function on it is a separate row (see Owner decisions).
- No lint-debt fixes, no renames. The two `except Exception` blocks (L597, L686) stay as they are.
- The `dp_numeric_domain_invalid` and `row_count` string copies stay. Their engine-reason-code entries move unchanged.

## Module map

`src/decoy/cli/fit.py` becomes `src/decoy/cli/fit/`. Each function, class and constant moves verbatim (Fowler: Move Module, then Move Function and Move Field). Each module imports only the names it uses.

| Module | Holds (line ranges at `d6b9e4c7`) | Reason to change | Est. lines |
|---|---|---|---|
| `__init__.py` | Module docstring (L1-31), re-exports of the base name set, `__all__` | the public surface | ~65 |
| `_args.py` | `_FitUsageError`, `_parse_dp_number_spec`, `_parse_rows`, `_build_column_schema`, `_FLAG_TRUE_TOKENS`, `_FLAG_FALSE_TOKENS`, `_map_flag_token`, `_build_typed_frame` (L113-250) | how a flag value or a declared column type is parsed and checked | ~160 |
| `_command.py` | `_DP_REFUSED_LINE`, `_DP_REFUSED_HINT` (L55-62), `_FIT_EPILOG` (L64-110), `fit` (L253-808), `FIT_EPILOG = _FIT_EPILOG` (L811) | the fit command flow: read, fit, refuse, write, report | ~640 |

Both modules are under the 800-line cap. `_command.py` stays large because `fit` is one function. Splitting it further means Extract Function on `fit`, which changes code and is out of scope.

Imports run one way: `_args` is a leaf; `_command` imports from `_args`; `__init__` imports from `_command`. No module imports `__init__`. The lazy imports inside `fit` (`decoy_engine`, `decoy_engine.quality.*`, `decoy.ui.summary`) and inside `_map_flag_token` (`pandas`) stay inside the function bodies, so `--help` does not load the engine or pandas.

`__init__.py` stays thin: no function definitions. It re-exports the base name set from the Guarantee section (`fit` and `FIT_EPILOG` are the two with an importer). Private names (`_FitUsageError`, `_build_typed_frame`, `_map_flag_token` and others) are not re-exported. A re-exported private name invites a test to patch the package attribute, which the moved code no longer reads, so the patch would do nothing without failing.

Do the move as `git mv src/decoy/cli/fit.py src/decoy/cli/fit/__init__.py` first, then cut the modules out of it, so `git log --follow` and `git blame -C` keep the history.

## Placement

| New file | Directory | CODEMAP "Where Things Go" line | Sits beside |
|---|---|---|---|
| `__init__.py`, `_args.py`, `_command.py` | `src/decoy/cli/fit/` | "Command-private helpers" (S1 and S2 add `src/decoy/cli/report/` and `src/decoy/cli/preflight/` there). S3 adds `src/decoy/cli/fit/` (the `decoy fit` command package) to the same line. | `src/decoy/cli/preflight/`, `src/decoy/cli/gen/` |

S3 adds cases to `tests/unit/test_cli_split_imports.py`, which S2 creates. It adds no test file.

## Importers

Keep the package path (no edit): `src/decoy/__main__.py:25-26` (`FIT_EPILOG`, `fit as fit_command`). The docstring at `src/decoy/cli/gen/_fit.py:5` names `cli/fit.py`; the builder changes it to `cli/fit/` (comment only).

Import-path edits only (no assertion changes). Each one reaches a private name, or patches or parses a name where the moved code now is:

| Site | Today | After | If missed |
|---|---|---|---|
| `tests/e2e/test_fit_command.py:35` | `from decoy.cli.fit import _build_typed_frame, _map_flag_token` | from `decoy.cli.fit._args` | `ImportError` (loud) |
| `tests/e2e/test_fit_command.py:1053` | parses `decoy.cli.fit.__file__` for engine imports | parse every `*.py` in the package directory | `__init__.py` holds no engine import, so the `any(...)` assert fails (loud). Walking the package keeps the "no private engine import" half over `_args.py` too. |
| `tests/e2e/first_user/test_fit_rows.py:339-348` | subclasses and patches `fit_module._FitUsageError` | subclass `decoy.cli.fit._args._FitUsageError`; patch `_FitUsageError` on both `_args` and `_command` | the raise at L534 and the `except` at L535 are in `_command`, so a patch on the package does nothing; `raised` stays empty and the test fails (loud). Both are patched so a raise in `_args` and the `except` in `_command` see the same class. |
| `tests/e2e/test_cl4_exit_owner_commands.py:88-90` | `mock.patch("decoy.cli.fit.exit_code_for", create=True)` and `mock.patch("decoy.cli.fit.fit_exact_snapshot")` | both on `decoy.cli.fit._command` | the second patch raises `AttributeError` (loud). The first one has `create=True`, so on its own it would patch nothing and stay quiet. Both must move together. The builder proves the first patch fires: on a scratch copy, set its `return_value` to a different code, and the test must go red. |
| `tests/e2e/first_user/test_fit_fanout.py:115-116` | `monkeypatch.setattr("decoy.cli.fit.read_fit_csv", ...)` and `"decoy.cli.fit.fit_exact_snapshot"` | both on `decoy.cli.fit._command` | `monkeypatch.setattr` raises on a missing attribute (loud) |

Comments and docstrings that name `fit.py` in `tests/unit/test_report_fidelity.py:108,347` and `tests/e2e/test_fit_command.py:336,394,448` describe history and stay as they are.

## Sentries and baselines that move

Re-home each entry to the new file at the same site. Every one-to-one re-key goes through the baseline's top-level `moved_from` map (`{new_key: old_key}`), with the entry byte-identical. The part after the last `::` stays the same in every re-key. No count rises.

| File | Change |
|---|---|
| `tests/sentry/baselines/module-size.json` | Delete `src/decoy/cli/fit.py` (max 811). `entries` becomes `{}`. Empty baselines already exist (`exit-code-owner.json`, `output-name-allow.json`). |
| `tests/sentry/baselines/package-fanout.json` | `src/decoy/cli` max 27 to 26. |
| `tests/sentry/baselines/lint-debt.json` | 5 keys (8 hits) become 6 keys. See below. |
| `tests/sentry/baselines/engine-reason-code-copies.json` | `moved_from`: `"cli/fit/_args.py::dp_numeric_domain_invalid": "cli/fit.py::dp_numeric_domain_invalid"` (count 2, L148 and L153), and `"cli/fit/_command.py::row_count": "cli/fit.py::row_count"` (count 2, both on L749). |
| `tests/sentry/allowlist-before.json` | The same re-keys and shrinks: L61-62 (engine-reason-code), L131 (module-size, delete), the `src/decoy/cli` package-fanout row (27 to 26). |
| `tests/sentry/baselines/csv-read-allow.json` | No edit. Its `moved_from` value `"cli/fit.py::fit"` is a leftover from an earlier move; `_ratchet.py` ignores leftovers. |
| `tests/sentry/test_csv_read_choke_point.py:104` | `FIT_READER_CALLERS`: `("cli/fit.py", "fit")` to `("cli/fit/_command.py", "fit")`. If missed, the exact-set assert fails (loud). |
| `tests/sentry/io_policy/test_private_files.py:139` | `"cli/fit.py::fit::write_local_target::1"` to `"cli/fit/_command.py::fit::write_local_target::1"`. If missed, the site table and the scan disagree (loud). |
| `tests/sentry/io_policy/test_fit_value_redaction.py:24,59,63` | `FIT` points at one file and is read twice. The negative check (L58-59, no sensitivity name) scans every `*.py` under `src/decoy/cli/fit/`, with the message changed to `cli/fit/`. The positive check (L63, `fit` reads `redacted_columns` from the engine's document) points at `src/decoy/cli/fit/_command.py` only, the module that holds the read (`src/decoy/cli/fit.py:712` today). It changes from a substring check to a check for the call `snapshot.get("redacted_columns")`, because the JSON output key at `fit.py:760` alone would satisfy the substring. A package-wide search would also match the docstring at `fit.py:14`, which moves to `__init__.py`. The module docstring (L11) changes to match. If missed, `read_text` raises (loud). Mutations: put `pii_score` in `_args.py` on a scratch copy, the negative check must go red; on a scratch copy, replace only the read at L712 with `[]`, the positive check must go red. |

`tests/sentry/layout/test_module_size.py` needs no edit: S2 makes its meta-tests synthetic. No `fit.py` entry exists in `.importlinter`, `one-error-emitter`, `gate-single-entry-allow`, `private-file-sinks`, `canonical-json-allow` or `ci/vendored.toml`.

### Lint-debt: one key becomes several

`ruff check --extend-select` with the `EXTRA_RULES` of `scripts/dev/lintdebt.py` (ruff 0.15.20) on `fit.py` at `d6b9e4c7` gives 8 hits, equal to the baseline:

| Function (line) | Goes to | ANN401 | BLE001 | C901 | PLR0912 | PLR0915 |
|---|---|---|---|---|---|---|
| `_build_typed_frame` (231, `df: Any` and `-> Any`) | `_args.py` | 2 | | | | |
| `fit` (253; nested `_emit_dp_refused(refusal: Any)` at 417; `except Exception` at 597 and 686) | `_command.py` | 1 | 2 | 1 | 1 | 1 |
| Total (= today) | | 3 | 2 | 1 | 1 | 1 |

Baseline edits:

- `split_from`: `"src/decoy/cli/fit.py::ANN401"` to `src/decoy/cli/fit/_args.py::ANN401` (count 2) and `src/decoy/cli/fit/_command.py::ANN401` (count 1).
- `moved_from`: `src/decoy/cli/fit/_command.py::BLE001`, `::C901`, `::PLR0912` and `::PLR0915`, each from the same rule on `src/decoy/cli/fit.py`, counts unchanged.

Every new entry keeps the old reason. The builder re-runs `scripts/dev/lintdebt.py` on the head. It must report exactly these 6 keys for the package and no other change.

## Enumerations

Every path below keeps its code and its order. The golden check in acceptance test 3 has a cell for each one.

### Exit paths

All exits are in `fit` and go to `_command.py` unchanged:

- a bad `--joint` spec or `--joint-max-cells` without `--joint`: `EXIT_USAGE` (`src/decoy/cli/fit.py:435`, `src/decoy/cli/fit.py:442`);
- a usage error from flag parsing (`_FitUsageError`): `EXIT_USAGE` (`src/decoy/cli/fit.py:452`, `src/decoy/cli/fit.py:537`);
- a bad `--joint-max-cells` value, an unreadable CSV, undeclared or missing DP columns, a CSV that changed between reads: `EXIT_USAGE` (`src/decoy/cli/fit.py:564`, `src/decoy/cli/fit.py:570`, `src/decoy/cli/fit.py:616`, `src/decoy/cli/fit.py:638`, `src/decoy/cli/fit.py:698`);
- a DP refusal, an engine fit error and a source error: `exit_code_for(exc)` (`src/decoy/cli/fit.py:649`, `src/decoy/cli/fit.py:652`, `src/decoy/cli/fit.py:674`, `src/decoy/cli/fit.py:707`, `src/decoy/cli/fit.py:710`);
- a failed snapshot write: `EXIT_RUNTIME` (`src/decoy/cli/fit.py:721`);
- success: exit 0.

### Routes

- `decoy fit` reaches `fit` through `src/decoy/__main__.py:26`.
- The exact path (`fit_exact_snapshot`) and the DP path (`fit_dp_snapshot`) both stay inside `fit`. Both have golden cells.

### FK shapes

N/A: `decoy fit` reads one CSV and has no foreign keys. The split moves no FK logic.

### Fields

N/A: no `--json` field is added, renamed or removed. The payload is built inside `fit` (`src/decoy/cli/fit.py:749`) and moves as is.

### Output surfaces

- the snapshot file, written once through `write_local_target` (`src/decoy/cli/fit.py:716`);
- stdout: the `OK` line, the summary lines and the `--json` payload (`src/decoy/cli/fit.py:764`, `src/decoy/cli/fit.py:769`);
- stderr: errors through `emit_error`, the DP refusal block, the omission notice and the warning lines (`src/decoy/cli/fit.py:423`, `src/decoy/cli/fit.py:623`, `src/decoy/cli/fit.py:732`);
- exit code (see Exit paths).

## Reuse inventory

- Ratchet maps: `moved_from` (PR #179) and `split_from` (PR #411) in `tests/sentry/_ratchet.py`. No new tool code.
- Package shape: `src/decoy/cli/run/`, S1's `src/decoy/cli/report/`, S2's `src/decoy/cli/preflight/`.
- Lint-debt counting: `scripts/dev/lintdebt.py`, unchanged.
- Import-compat test: S2's `tests/unit/test_cli_split_imports.py`, extended with a `fit` case.
- Golden harness: the same base-twice, mask, compare method as S1 and S2. It stays out of the tree.

## Frozen contracts

- The `decoy.cli.fit` import path and the base name set in `__all__` (named and wildcard imports).
- The `decoy fit` CLI: flags, help text, stdout, stderr, `--json` schema, the snapshot file bytes, and exit codes.
- The sentry allowlist identities, re-keyed only through `moved_from` or `split_from`.

## Acceptance tests

1. Existing tests pass with no assertion edits. The only test edits are the import paths, patch targets and sentry tables listed above.
2. Import-compat test: add a `fit` case to `tests/unit/test_cli_split_imports.py`. It asserts that `decoy.cli.fit.__all__` and the package's non-underscore names both equal the frozen base list in the Guarantee section, that `from decoy.cli.fit import *` in a fresh namespace binds that same list, that each name is the same object the base bound (`read_fit_csv is decoy.cli.gen.read_fit_csv`, `fit is _command.fit`), and that `decoy.__main__`'s `fit_command` is that same object. It also asserts that no private name is bound on the package: `not hasattr(decoy.cli.fit, name)` for `_FitUsageError`, `_build_typed_frame` and `_map_flag_token`. It runs the patch-target scan from the Guarantee section. Mutations that must turn it red: re-export `_FitUsageError` from `__init__`; drop `read_fit_csv` from `__init__`; add a test string `monkeypatch.setattr("decoy.cli.fit.read_fit_csv", ...)`.
3. Golden byte check. A throwaway harness (outside the tree; its script and per-case hash table go in the PR body) runs on the base commit and on the head and compares stdout, stderr, exit code and the snapshot file bytes for:
   - a clean exact fit, with no flag, `--json` and `--quiet`, and with `--rows`, `--joint` and `--parse-dates`;
   - a DP fit (`--epsilon`, `--delta`, `--dp-number`, `--dp-flag`) with the deterministic doubles from `tests/e2e/test_fit_command.py:822-830` (`_pass_gate` and a stub `decoy_engine.quality.dp.fit_dp_snapshot`), which must exit 0 and write a snapshot on both trees; the real certified-install refusal on this host as its own case; an undeclared DP column (with and without `--dp-allow-omit`) and a declared column missing from the CSV;
   - a DP request error raised at `check_dp_fit_request` (`src/decoy/cli/fit.py:646`, before the full read). Then, with the request gate passed (`_pass_gate`), two cases at `fit_dp_snapshot` (`:702`, after the full read): a `ProvenanceError` (the refused path, `:707`) and a `DpError` (the error path, `:710`), each injected with a double on the engine name. The real install refusal exits at `:649` before either handler, so it does not cover them. Each case asserts its diagnostic text, exit code and error code, and that no snapshot file exists;
   - the changed-header case (`tests/e2e/test_fit_command.py:1091`, the header changes between the check read and the full read);
   - a bad `--joint` spec, `--joint-max-cells` without `--joint`, and an out-of-range `--joint-max-cells`;
   - each usage error the existing e2e tests raise: a bad `--rows`, a bad `--dp-number` spec, an empty column name, a bad setting, an unreadable CSV;
   - an existing output: `fit` writes with `WriteMode.REPLACE` (`src/decoy/cli/fit.py:717`), so this is a success case. Seed the destination with known bytes and assert it is replaced, with exit 0, on both trees;
   - a failed snapshot write (read-only output directory);
   - `decoy fit --help` and `decoy --help`.
   The harness runs in process through Typer's `CliRunner`, so it can apply the doubles. Every double targets an engine name (`decoy_engine.quality.*`) or the read spy from the e2e test, so the same patch applies on both trees. Before it compares bytes, each case asserts its expected exit code, error code and whether a snapshot exists. A case whose double did not take effect fails there, so two identical wrong outputs cannot pass.
   The harness first runs the base tree twice. Any field that differs between those two runs (timestamps, temp paths) is listed and masked. Everything else must match exactly.
4. Ratchet equal, not raised: the ratchet check against the merge base reports no finding, and the total of the fit lint-debt counts is 8 before and after. These pass: `tests/sentry/layout/test_module_size.py`, `test_package_fanout.py`, `test_import_layers.py`, `test_codemap_paths.py`, `tests/sentry/test_lint_debt.py`, `test_baseline_registry.py`, `test_ratchet_check.py`, `test_sentry_manifest.py`, `test_csv_read_choke_point.py` and `tests/sentry/io_policy/`.
5. `ruff check`, `ruff format --check` and `mypy` are clean on the head.
6. Every new module is under 800 lines, and `__init__.py` defines no function (checked at review). `module-size.json` has no entries left.

## Defect classes

| # | Class | Applies | Structure | Proof (mutation) |
|---|---|---|---|---|
| 1 | value | N/A: no data path changes; `test_fit_value_redaction.py` keeps guarding the package | the redaction sentry, widened to every package module | put `pii_score` in `_args.py` on a scratch copy; the sentry must go red |
| 2 | cleanup | N/A: the snapshot write keeps the same `write_local_target` call and mode | existing `test_private_files.py` site table | acceptance test 3, failed-write cell |
| 3 | state | N/A: `fit` holds no module state; each call builds its own | none | none |
| 4 | route | Yes: a patch on the package attribute no longer reaches the moved code (`create=True` in `test_cl4_exit_owner_commands.py`) | private names not re-exported; patch the owning submodule | change the patched `return_value` on a scratch copy; the test must go red |
| 5 | referential | N/A: one CSV, no rows linked across tables | none | none |
| 6 | untrusted | N/A: no child process or extension | none | none |
| 7 | toctou | N/A: the read, fit and write order inside `fit` is unchanged | the function moves as one block | acceptance test 3 |
| 8 | weak | Yes: a byte check that masks too much passes anything | mask only fields that differ between two base runs, and list them | change one error message on a scratch copy of the head; the golden check must go red |
| 9 | refactor drift | Yes: output, snapshot bytes, exit codes, help | golden byte check on base and head | acceptance test 3; on a scratch copy, change `EXIT_USAGE` to `EXIT_RUNTIME` in the `_FitUsageError` handler (`src/decoy/cli/fit.py:535-537`, the only handler in that block); the bad-setting cell must go red |
| 10 | frozen contract | Yes: the `decoy.cli.fit` import path and the sentry identities | `__all__`, import-compat test, `moved_from` and `split_from` | acceptance test 2; a lint-debt key re-keyed without `moved_from` must fail the ratchet check |

## Pre-mortem

If this slice fails, the likely causes are:

- A `mock.patch(..., create=True)` left on the package path. It patches nothing and the test may still pass. The builder greps the tests for `decoy.cli.fit.` patch strings on the head; every hit must name `_args` or `_command`.
- `_FitUsageError` patched on only one module in `test_fit_rows.py`, so a raise and the matching `except` see different classes.
- An import cycle if `_args` ever imports from `_command`. `python -c "import decoy.cli.fit._args"` in a fresh process proves the order.
- `pandas` or an engine module imported at the top of a new module by accident. `--help` would then load it. The builder greps the new modules for top-level `pandas` and `decoy_engine` imports; there must be none.
- A ledger conflict with another branch that re-homes an entry in the same baseline. Keep both sides and re-run the ratchet check.

## Design notes

- Principle: split along a reason to change (`architecture.md`, layout). Flag parsing and type checks change when a flag changes; the command flow changes when the fit steps change. Each now has one file.
- Pattern followed: S1, S2 and the `cli/run/` package (thin `__init__`, private sibling modules, `git mv` first, `moved_from` and `split_from` for baselines).
- One place per fact: `_FitUsageError` is defined in `_args.py` only; `_command.py` imports it.
- New structure added: the package, which the 800-line cap asks for. No new test file.

## Established solutions

No new design problem: this is a module move. The steps follow Fowler's catalog (Move Module, Move Function, Move Field). The baseline moves use the repo's own ratchet maps. The package shape copies `src/decoy/cli/run/`, S1 and S2. No custom code is added.

## Slices

One slice, one PR (this plan). It is slice S3 of the CLI-SPLIT row and the last one. The commits under "Size and commits" are steps inside this slice. The row closes when S3 merges and `module-size.json` is empty.

## Blocks on S2, conflicts and merge order

S3 depends on both earlier slices. #411 is merged; S2 is not:

- `split_from` (`tests/sentry/_ratchet.py`). Satisfied: #411 merged to main as `d0826aa9`; between the #411 head these plans read (`301e703c`) and main, nothing changed that alters a fact in this plan.
- S2 makes the module-size meta-tests synthetic. Without that, deleting the `fit.py` entry turns the meta-tests red.
- S2 sets package-fanout to 27 and creates `tests/unit/test_cli_split_imports.py`, both of which S3 edits.
- All three slices edit the same ledgers: `lint-debt.json`, `module-size.json`, `package-fanout.json`, `allowlist-before.json`. S2 and S3 also both edit `engine-reason-code-copies.json`; #411 does not touch it (its fit entries at L37 and L41 are unchanged there).

Order: build S3 from `origin/main` after S2 merges. If the builder starts earlier, it branches from the S2 branch and opens its PR against `main` only after S2 has merged and the branch is rebased onto main (`git rebase --onto origin/main <S2 head> <S3 branch>`). A PR based on the S2 or #411 branch is not allowed: a PR merged into a non-main base never ships (#749 on 2026-11-22).

Open PRs on 2026-11-25 (`gh pr list -R decoy-data/decoy --state open`, 16 open, before #411 merged): only #411 touched `fit.py` or the ledgers above. Every remote branch with commits after 2026-11-10 that touches `fit.py` is merged. On a rebase conflict in a shared ledger, keep both sides, then re-run the ratchet check.

Builders of any row launched while S3 is open wait for it if the row edits `fit.py`.

## Test tier

Moved code, edited sentry tables and `allowlist-before.json` are full-suite triggers. T0: the touched test file per edit. T1 per commit: `tests/e2e/test_fit_command.py`, `tests/e2e/first_user/test_fit_*.py`, `tests/e2e/test_cl4_exit_owner_commands.py`, `tests/unit/test_report_fidelity.py`, the import-compat test and the sentries in acceptance test 4. Before the merge: one full suite (CLI `gates.sh --full`, or `decoy-vm-t3` default mode) on the exact merge head, failing ids diffed against the saved main baseline. No new logic, so the mutation evidence is the scratch mutations in the defect table.

## Size and commits

One PR. About 850 lines added and 815 removed, nearly all of it the move, so review with `git diff --color-moved=dimmed-zebra -M`. Files: 1 removed and 3 added under `src/decoy/cli/fit/`; `cli/gen/_fit.py` (docstring); 4 test files with import or patch edits; 1 test file extended; 4 baselines plus the snapshot; 3 sentry test files with table edits; `CODEMAP.md`. No new public names.

Commits (Conventional Commits, last line `cam`, no body unless it explains why):

1. `refactor(fit): move fit.py into a fit package` (the `git mv` only)
2. `refactor(fit): split flag parsing out of the fit command`
3. `test(sentry): re-home fit baselines to the new modules`
4. `test(cli): pin the fit package import surface`
5. `docs(codemap): place the fit package`

The branch merges squashed. Commits 1 and 2 can leave sentries red until commit 3. The head is what gets gated.

## Owner decisions

Defaults taken, open to change in review, and one follow-up:

1. The package keeps every non-underscore name the old module bound, imported names included, for named and wildcard import parity (Guarantee). The owner can narrow it to `fit` and `FIT_EPILOG` later; that is a separate, visible API change.

2. `fit` is 556 lines in one function, with 6 lint-debt hits. Extract Function on it (read, fit exact, fit DP, write, report) would bring `_command.py` well under the cap and clear C901, PLR0912 and PLR0915. That changes code, so it needs its own plan and its own golden check. Default: record it as a follow-up row, not part of CLI-SPLIT.
