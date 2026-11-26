# VALIDATE-SUBSET-EDGES (CLI half) plan

Status: plan
Row: VALIDATE-SUBSET-EDGES, config group (`docs/roadmap/groups/config.md:16`), V1 (1.0) row, CLI half only. Risk R1.
Read from: CLI `origin/main` 3df9c13a, engine `origin/main` 0952fbae2 (engine fix 8ee461e0f, #785).

Rules consulted: dev-rules `00-universal.md`, `development-loop.md` (Proportion: R1 gets a one-page plan and one review), `profiles/local-operations.md`, `testing.md` (Test depth T0/T1; mutations only for core logic), `cross-cutting-concerns.md` (one choke point plus a guard), `catalogs/recurring-defects.md` (all 11 classes, table below), `LOCAL-BUILDER-BRIEF.md`, CLI `CODEMAP.md` "Where Things Go", CLI `CLAUDE.md` (the engine owns data rules; the CLI stays thin).

## Release and dependency

The engine half (#785) is on engine main after v0.28.4. It ships in engine **0.28.5** (release PR engine #826, open). The CLI pins `decoy-engine==0.28.3` on main and pin PR #408 (0.28.4) is in review. **The CLI build waits for the 0.28.5 repin PR to merge.** This slice does not change the pin. It ships in CLI 1.0.0 (and 1.0.0-rc.1 if cut).

## Behavior

`decoy validate`, `decoy run` (its always-on gate), `decoy ci check` (both modes) and `decoy validate compile` refuse a `subset:` block whose `edge_directions` names an edge that is not declared (`subset_unknown_edge`) or turns off upward traversal without `allow_dangling` (`subset_dangling_not_acknowledged`). The refusal happens before any source is read, and validate gives the same verdict as run.

Today on 0.28.3 the edge check runs only inside `select_subset` at run time. After the 0.28.5 repin, the engine's `split_subset_config` raises it, so the gate's compile layer (`src/decoy/cli/gate/_layers.py:323`, caught at `src/decoy/cli/gate/_layers.py:345`) reports it with no CLI change. Two routes still miss it:

1. A config with a `cardinality_mode: unique` column: the compile layer returns early with a warning (`src/decoy/cli/gate/_layers.py:303`) and never splits, so `validate` exits 2 or 0 and `run` fails later in the engine.
2. `ci check` config mode (`run_config_gate`, `src/decoy/cli/gate/_layers.py:531`) runs only the config layer.

Change (split once, fix round 1): the config layer (`_run_config_base`, `src/decoy/cli/gate/_layers.py:185`) calls `decoy_engine.subset.split_subset_config(validated)` once, right after `run_config_only_checks` (`src/decoy/cli/gate/_layers.py:224`), looked up on the module so a test can spy it. On `SubsetError` it returns `None, None, (), [GateFinding("config", "error", exc.code, exc.message, location="subset", logical_path="subset")]`, the same short-circuit as the `PlanCompileError` arm beside it. On success it returns the split's `run_config` beside the validated dump: the return grows to `(validated, run_config, checks_run, findings)`. Its two callers (`run_static_gate` at `src/decoy/cli/gate/_layers.py:483`, `run_config_gate` at `src/decoy/cli/gate/_layers.py:531`) unpack the new member. `StaticGate` gains a `run_config` field.

- `_run_compile_layer` takes `run_config` in place of `validated` and passes it straight to `compile_plan`. Its `split_subset_config` call (`src/decoy/cli/gate/_layers.py:323`) and its `except SubsetError` arm are deleted.
- `_run_preflight_layer` takes `run_config` (keyword, default None) in place of `validated`; under `skip_subset` the capacity estimate prices `run_config`. Its split call and `except SubsetError` (`src/decoy/cli/gate/_layers.py:407`) are deleted.
- `GateResult.config` and `check_static_before_acquire` keep returning the validated dump with its `subset:` block (the run applies it); only the layers that priced or compiled the split copy now receive it.

So a passing full gate splits exactly once, with or without `--no-subset`. `decoy validate compile` keeps its own split (`src/decoy/cli/compile_explain.py:247`); it does not enter the gate. The `.decoy` language already writes `follow <edge> <direction>` and `allow dangling` (`src/decoy/lang/_subset.py:81`), so no language change; the `subset` location maps to the block's source line through the existing source map.

Reason codes: the engine's `subset_unknown_edge` and `subset_dangling_not_acknowledged`, passed through as `exc.code`, never copied as CLI literals (`tests/sentry/test_engine_reason_code_copies.py` guards that). No new CLI code. Exit code: `EXIT_USAGE` (1) from `gate_exit_code` (`src/decoy/cli/gate/_layers.py:549`); `run` raises `PreRunCheckError` with `error_kind: validation` and exit 1. No new exit code.

## Choke point

The edge rule has one home: the engine's `split_subset_config` (`decoy-engine src/decoy_engine/subset/_split.py:42`), reached through the public `decoy_engine.subset` facade. The CLI never restates the rule. Inside the CLI, every gate route (validate, run, ci check, ci check config) enters `_run_config_base`, so that is the one CLI call site that decides the verdict. Guard: acceptance test A4 (below) monkeypatches `decoy_engine.subset.split_subset_config` to raise a synthetic `SubsetConfigError` and asserts the config-only gate refuses with that code, and wraps the real split in a counting spy to assert exactly one call on a passing full gate (plain and `--no-subset`). Mutations: delete the new split call in `_run_config_base` (A3, A4 and A5 turn red); add a second `split_subset_config` call back in `_run_compile_layer` or `_run_preflight_layer` (A4's count cell turns red). The existing defensive cell `test_the_gate_turns_a_subset_error_into_a_finding_defensive` (`tests/e2e/test_run_subset.py:291`) stays green unchanged; it now proves the config-layer arm. No new registry (one rule, one engine site).

## Enumerations

### Exit paths

- `decoy validate` aggregate: exit 1, finding code from the engine (`src/decoy/cli/validate.py:314` calls `run_gate`).
- `decoy run`: gate refusal, `PreRunCheckError.from_result`, exit 1, `error_kind: validation` (`src/decoy/cli/gate/_run.py:77`).
- `decoy validate compile`: `split_subset_config` raises at `src/decoy/cli/compile_explain.py:247`, `_compile_error` prints `str(exc)` (`[code] message`), exit 1. Unchanged code; covered by test A6 only.
- `decoy ci check`: the adapter reads the gate result (`src/decoy/ci/adapters.py:119`), exit per its existing map.

### Routes

- Full gate: `run_gate` and `run_gate_on_config` (`src/decoy/cli/gate/_layers.py:483`), used by validate and run.
- Config-only gate: `run_config_gate` (`src/decoy/cli/gate/_layers.py:531`), used by `ci check` config mode.
- `decoy run --no-subset`: the gate's `skip_subset` still enters the config layer, and the engine refuses a bad block under `subset_request="skip"` too, so the two agree. The capacity estimate prices the config layer's `run_config`; no second split.
- `decoy subset` command: already catches `SubsetConfigError` (`src/decoy/cli/subset.py:225`); out of scope.

### FK shapes

- Single-column relationship with a wrong-way or unknown edge name: fixture for A1 to A5.
- Composite relationship: same code path in the engine (edge names come from `build_subset_edges`); no separate CLI cell.

### Fields

- `subset.edge_directions` (map of edge name to `both`, `upward`, `downward`).
- `subset.allow_dangling` (bool; true accepts a downward-only edge).

### Output surfaces

- Human error line through `emit_error` and the gate report table.
- `--json` finding object (`code`, `message`, `location: "subset"`) under `decoy-error-v1`; the shape is unchanged, so `tests/e2e/release_freeze/test_json_shapes.py` stays green with no snapshot edit.

## Reuse inventory

- Engine `split_subset_config` and `SubsetError` (public `decoy_engine.subset`), no CLI copy.
- `GateFinding` and the config-layer short-circuit pattern already used for `PlanCompileError`.
- Test fixtures: the subset config builders in `tests/e2e/test_run_subset.py` and `_unique_column_config` in `tests/e2e/test_validate_gate.py:134`.

## Acceptance tests (red first)

New file `tests/e2e/subset/test_validate_subset_edges.py` (CliRunner), in a new `tests/e2e/subset/` package with an empty `__init__.py` (`tests/e2e/` already holds 99 direct modules). Red on 0.28.3 is expected for A1 and A2 (the engine does not split-check yet); the builder runs them red on the current pin, then green after the 0.28.5 repin. A3 to A5 are red against the 0.28.5 pin without the config-layer change.

| Id | Case | Expect |
|---|---|---|
| A1 | `validate` on a config whose `edge_directions` names an undeclared edge; the source file exists | exit 1, finding code `subset_unknown_edge`, location `subset`; a source-reader spy (on `decoy.cli.preflight._check_source_files` and `decoy.cli._sources.read_source`) records zero calls |
| A2 | `validate` with a `downward` edge and no `allow_dangling` | exit 1, `subset_dangling_not_acknowledged`; same config with `allow_dangling: true` exits 0 |
| A3 | A1's bad edge plus a `cardinality_mode: unique` column | exit 1 with the subset code (today: warning only) |
| A4 | `ci check` config mode on A1's config; the monkeypatched-split guard; a counting spy on the real `split_subset_config` during a passing `validate` and a passing `run --no-subset` gate | refused, finding `rule_id` is `validate.subset_unknown_edge` (engine codes are allowlisted by `src/decoy/ci/rule_codes.py:277`); the spy counts exactly 1 call per passing gate |
| A5 | `run` on A3's config; the source file exists | exit 1, `error_kind: validation`, code equals the code `validate` printed (validate and run agree); the A1 source-reader spy records zero calls |
| A6 | `validate compile` on A1's config | exit 1, output carries `subset_unknown_edge` |
| A7 | `.decoy` twin of A2 (`follow <edge> downward`, no `allow dangling`) | exit 1, same code, location resolves to the subset block line |

Codes are read from `decoy_engine.reasons.config` in the tests, not typed as literals.

## Frozen contracts

No change to exit codes, `decoy-error-v1`, the `--json` shapes snapshot, reason-code names or the CLI surface. A config that passed `validate` before passes now unless it carries a bad edge, which `run` already refused.

## Failure modes

- Gate crash on an unexpected engine exception from the split: only `SubsetError` is caught; anything else propagates to the existing crash handler, as today.
- Duplicate finding: the config layer short-circuits, and the compile layer no longer splits, so one error gives one finding.
- Message content: the engine message names edge identifiers from the user's own config (table and column names), never data values. It goes to the terminal and `--json` only, not to logs; same as the compile-layer finding today.

## Defect classes

| # | Class | Closing structure | Sentry or test | Mutation |
|---|---|---|---|---|
| 1 | value-bearing output | message is the engine's identifier-only text; no values | A1 and A5 source-reader spy: zero calls | N/A: wiring only, no new text built in the CLI |
| 2 | cleanup on failure | N/A: the gate writes nothing before the config layer returns | none | none |
| 3 | state shared across layers | short-circuit returns `None` config | test A3 | drop the `return None` |
| 4 | every route | one call in `_run_config_base`, the shared entry of all routes | A1, A4, A5 | delete the call |
| 5 | referential integrity | engine owns edge resolution | engine `tests/unit/subset/test_split.py` | N/A: no CLI FK logic |
| 6 | untrusted input | config already schema-validated before the split | A1, A2 | N/A: no new parsing |
| 7 | check-then-use (toctou) | N/A: pure function of the parsed config, no filesystem check | none | none |
| 8 | weak test | codes read from the engine registry; A3 fails on today's code | test A3 | delete the call |
| 9 | refactor drift | compile and preflight take the config layer's `run_config`; their split calls go | A4 split count | add a second split |
| 10 | frozen surface | no shape change | `test_json_shapes.py` | N/A: no shape edit |

Catalog classes 1 to 11 of `recurring-defects.md`: anchored regex n/a; strict wire types n/a; no exception context (the finding is built from `exc.code` and `exc.message` inside the `except`, no re-raise, so no context leaks); versioned read models n/a; normalized scanners n/a; no private imports (public `decoy_engine.subset` only); no hidden CI failures n/a; one trust class n/a; mutations on final head (reviewer reruns the delete-the-call mutation); allowlisted helpers n/a; no raised caps (no pin or ratchet moves).

## Placement and size

| File | Kind (CODEMAP row) | Change | Size after |
|---|---|---|---|
| `src/decoy/cli/gate/_layers.py` | Pre-run check gate | +14 lines in `_run_config_base`, about -20 in the compile and preflight layers | about 555 (cap 800) |
| `tests/e2e/subset/__init__.py` | gate tests: new `tests/e2e/subset/` package | new, empty | 0 |
| `tests/e2e/subset/test_validate_subset_edges.py` | gate tests: `tests/e2e/subset/` | new | about 210 |
| `CHANGELOG.md` | release notes | one Fixed entry | n/a |

CHANGELOG (Unreleased, Fixed): "`decoy validate`, `decoy ci check` and the `decoy run` gate now refuse a `subset:` edge direction that names an unknown edge or turns off upward traversal without `allow_dangling`, before any source is read (codes `subset_unknown_edge`, `subset_dangling_not_acknowledged`, exit 1). Before, the check ran only at run time, and a config with a `cardinality_mode: unique` column skipped it at validate. Needs decoy-engine 0.28.5."

## Slices

One slice, one PR: `fix(gate): check subset edge directions in the config layer`. Starts after the 0.28.5 repin merges. T0: `tests/e2e/subset/test_validate_subset_edges.py`; T1: `scripts/dev/gates.sh --keep-going --baseline` via vm-run, plus `tests/e2e/test_validate_gate.py`, `tests/e2e/test_run_subset.py`, `tests/e2e/test_run_validate_always.py`, `tests/e2e/first_user/test_items_preflight.py` (calls `_run_preflight_layer` directly), `tests/unit/test_gate_*.py`.

## Pre-mortem

- The repin slips: the slice waits; A1 and A2 cannot go green on 0.28.4. Do not vendor the rule into the CLI.
- A config-layer refusal changes the order of findings for a config with both a layout fault and a bad edge: the subset error now wins. Acceptable; both are config errors and exit 1.
- `validate compile` prints the bracketed engine text rather than a `code` member in `--json` (it only sets `code` for `PlanCompileError`). Known; logged as a 1.x polish item, not fixed here.

## Owner questions

None. Technical choice taken: refuse in the config layer (not only compile), so validate agrees with run on every route.

## Fix round 1

Outside review (codex-low, GO-WITH-FIXES, no V1 finding). Taken:

- Duplicate split: the config layer splits once and hands `run_config` to compile and to the `--no-subset` preflight; their split calls and `SubsetError` arms go. See Behavior "Change" and Choke point. A4 asserts one split per passing gate; mutation: add a second split.
- Placement: the test moves to the new `tests/e2e/subset/` package. See Placement and size, and the T0 path in Slices.
- A1 and A5 assert zero source reads through a source-reader spy, with the source file present, so a missing-source finding cannot stand in for ordering.
