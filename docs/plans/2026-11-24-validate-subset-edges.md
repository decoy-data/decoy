Status: plan

# VALIDATE-SUBSET-EDGES: `decoy validate` refuses a bad subset edge before the run does

Owner: Cam. Author: Opus plan agent. Date: 2026-11-24. Roadmap row: VALIDATE-SUBSET-EDGES (`docs/roadmap/groups/config.md:16`). Source finding: `v1-fast-path-audit-2026-11-22.md` (vault), rank 5, sized at one slice.

Rules consulted: dev-rules `README.md`, `00-universal.md`, `risk-and-exceptions.md`, `development-loop.md` (PLAN, Proportion), `cross-cutting-concerns.md` (choke point and guard), `api-and-compatibility.md` (reason codes and messages). Global CLAUDE.md commit and test-depth rules.

Read at CLI `origin/main` `00ed97b2` and engine `origin/main` `3426165fb`. The CLI pins `decoy-engine==0.28.3` (`pyproject.toml:153`).

Risk: R1. A refusal that already exists moves earlier, and two doc examples change. No new reason code, no output bytes, no `--json` shape change. Plan review: one round. Code gate: Codex. Tests: T0 and T1 per slice, then the T2 set. No full-suite trigger (no frozen contract, schema or test-config change).

## 1. Problem

Code facts:

- The edge-direction check is `resolve_edge_directions` (engine `subset/_policy.py:35-59`). It raises `SubsetConfigError` with `subset_unknown_edge` when `edge_directions` names an edge that is not a declared FK link, and `subset_dangling_not_acknowledged` when an edge is `downward` or `none` and `allow_dangling` is false.
- Its only call is `subset/_api.py:118`, inside `_compute`, after `run_subset_preflight` reads the sources. So only `decoy run` and `decoy subset` reach it.
- `decoy validate` runs the gate in `src/decoy/cli/gate/_layers.py`. The config layer (`_run_config_base`, lines 176-261) and the compile layer (lines 264-352) both stop short of it. The compile layer calls `split_subset_config(validated)` (line 314), which builds the request (`subset/_split.py:25-30`, through `subset_request_from_config`, `_api.py:283`) and does not check directions.
- The refusal text says "set allow_dangling=True on the FanOutPolicy" (`_policy.py:54-58`). That is the Python API name. A `.decoy` author writes `allow dangling` (`src/decoy/lang/_subset.py:73-84`, grammar `lang/_grammar.py:75`); a YAML author writes `allow_dangling: true` (engine `config/_subset.py:95`).
- Two shipped guide examples teach the failing pattern: `docs/guides/decoy-language/agent-card.md:189` and `docs/guides/decoy-language/05-checks-and-subsets.md:20` have `follow ... downward` with no `allow dangling`. `cheat-sheet.md:148-150` is correct.

Result today: `decoy validate` passes, then `decoy run` exits 3 after reading the sources, with a hint the author cannot act on.

## 2. Guarantee (pinned)

- G1. A config whose `subset:` block names an unknown edge, or a `downward`/`none` edge without `allow_dangling`, fails `decoy validate` with the same reason code `decoy run` gives today (`subset_unknown_edge` or `subset_dangling_not_acknowledged`), in the config layer, before any source is read. The exit code is the validate config-error exit (`gate_exit_code`, unchanged).
- G2. `decoy run` refuses the same configs with the same codes, before the subset preflight reads a source.
- G3. The dangling refusal names the fix a config author can type: `allow dangling` in a `.decoy` subset block, or `allow_dangling: true` in YAML. The Python API name stays in the text for SDK callers.
- G4. A config that passes the check today passes it after the change. No new refusals for valid configs.
- G5. The two guide examples validate and run clean.

Non-goals:

- No change to which configs are refused. The check, codes and edge-id format stay as they are.
- No change to `decoy subset` or `--sample` beyond what G2 gives. `--sample` builds its own request (`subset/_sample.py:122-150`) and overrides directions on purpose; it does not go through the new site.
- No `.decoy` line and column mapping for this finding beyond what the gate already does for a config-layer finding with a `location`.
- No new reason code and no reason-manifest change (`tests/fixtures/f29/reason-manifest-v1.json:80,86`).

## 3. Failure modes

- F1. Order change: a config with a bad edge AND a missing source now gets the edge refusal first, where today it gets the preflight refusal. Accepted: config errors come before source errors everywhere else in the gate. Tests that pin the old order are updated, not weakened, and the builder lists them.
- F2. `decoy run --no-subset` passes `subset_request="skip"` (`src/decoy/cli/run/_execute.py:474`), and the engine still calls `split_subset_config` (`execution/pipeline/_subset_stage.py:266`). With the check in the split, a `--no-subset` run of a config with a bad edge now refuses. See owner question Q1.
- F3. An edge touching a generated table is dropped by `mask_relationships` (`subset/_edges.py:177-200`) before the check. An `edge_directions` entry naming such an edge is `subset_unknown_edge` at run today; it stays so, now at validate too. The message already lists the valid ids.
- F4. Double report: the compile layer and the capacity step also call `split_subset_config` (`_layers.py:314`, `_layers.py:391-396`). The config layer fails first and returns `None`, so the compile layer does not run (`_run_config_base` contract, lines 186-187). The capacity step already swallows `SubsetError` (line 395). One finding, not two.
- F5. `cardinality_mode: unique` makes the compile layer skip (`_layers.py:291-306`). That is why the CLI check goes in the config layer, not the compile layer.

## 4. Acceptance tests

Engine (slice E1):

- AT-E1. `split_subset_config` on a dump with `edge_directions: {"<edge>": "downward"}` and no `allow_dangling` raises `SubsetConfigError` with code `subset_dangling_not_acknowledged`. The same dump with `allow_dangling: true` returns a split.
- AT-E2. `split_subset_config` with an unknown edge id raises `subset_unknown_edge`.
- AT-E3. `run_pipeline` on a dangling config whose source file does not exist raises `subset_dangling_not_acknowledged`, not a preflight error. This proves G2 "before any read".
- AT-E4. The plan-validation consolidator (`plan/validate/_consolidator.py:96-104`) returns `ok=False` with the dangling code and `path="subset"`.
- AT-E5. The dangling message contains `allow dangling` and `allow_dangling: true`.
- Guard: AT-E1 and AT-E3. Mutation: delete the `resolve_edge_directions` call in `split_subset_config`. Both go red.

CLI (slice C1, after the engine release and repin):

- AT-C1. `decoy validate` on a `.decoy` file with `follow a.k -> b.k downward` and no `allow dangling` exits with the config-error code. The finding has layer `config`, code `subset_dangling_not_acknowledged`, location `subset.edge_directions`, and a hint naming `allow dangling`. No source file exists in the test, so a pass proves no read.
- AT-C2. The same file plus `allow dangling` validates clean.
- AT-C3. A YAML config with an unknown edge id fails validate with `subset_unknown_edge`.
- AT-C4. A config with a dangling edge and a `cardinality_mode: unique` column still fails validate (F5).
- AT-C5. `decoy validate --json` and `decoy ci check` carry exactly one finding with that code (F4).
- AT-C6. The examples in `agent-card.md` and `05-checks-and-subsets.md` validate clean. If a doc-example test already compiles the guide blocks, extend it; otherwise add the two blocks to the existing `.decoy` example test.
- Mutation: remove the new `split_subset_config` call from `_run_config_base`. AT-C4 goes red (AT-C1 alone could still pass through the compile layer).

## 5. Slices

### E1 (engine, R1): check directions in the one split

Files: `src/decoy_engine/subset/_split.py`, `src/decoy_engine/subset/_policy.py` (message text only), engine tests under `tests/unit/subset/`, `CHANGELOG.md`.

- In `split_subset_config`, when `request` is not None, call `resolve_edge_directions(build_subset_edges(request.relationships), request.policy)` before returning, and discard the result. `_compute` keeps its own call, because `select_subset` callers can pass a hand-built request.
- Change the dangling message to name the config spelling first, for example: "... add `allow dangling` to the subset block (YAML: `allow_dangling: true`; Python: `FanOutPolicy(allow_dangling=True)`) to accept orphaned child rows, or set the edge to `both` or `upward`." Keep it value-free (edge ids only, as today).
- Update any test that pins the old message text or the old preflight-before-edge order (F1), and list them in the build report.
- Ships in the next engine release after merge (0.28.4, or whatever is next at merge time), through the engine repin checklist.

Size: about 10 source lines in two files, no new public names.

### C1 (CLI, R1): validate's config layer runs the split; docs fixed

Files: `src/decoy/cli/gate/_layers.py`, the existing gate or validate tests, `docs/guides/decoy-language/agent-card.md`, `docs/guides/decoy-language/05-checks-and-subsets.md`, `CHANGELOG.md`, and the `pyproject.toml` pin only if the repin PR has not landed.

- In `_run_config_base`, after `run_config_only_checks` (line 215), call `split_subset_config(validated)` once. Turn a `SubsetError` into one config-layer `GateFinding` (code `exc.code`, message `exc.message`, location and logical path `subset.edge_directions` for the two direction codes, else `getattr(exc, "path", None)`), and return `None` as the other config refusals do.
- Hint: add the dangling code to `_plan_error_hint` (`_layers.py:94-103`), which is already the value-free hint table for config-fixable refusals. The hint names `allow dangling` and `allow_dangling: true`.
- Docs: add `allow dangling` to the subset block in both examples, plus one sentence in `05-checks-and-subsets.md`: a `downward` or `none` edge needs it, because child rows can point at parents the subset dropped.
- Depends on E1's release. C1 does not carry a CLI-side copy of the check.

Size: about 20 source lines in one file, two doc edits, no new public names.

## 6. Design notes

- Choke point: `split_subset_config` (engine `subset/_split.py:25`). Every config-driven path already goes through it: engine run (`_subset_stage.py:266`), engine plan validation (`_consolidator.py:100`), CLI gate compile and capacity (`_layers.py:314`, `:394`), and CLI `compile_explain.py:247`. With the check there, a new caller gets it by construction. A CLI-side copy would be a second home for the rule, so there is none.
- Guard tests and mutations: section 4.
- No new structure: no new module, class or variant. Design principles: none apply beyond one place per fact.
- Placement: no new files, so no Placement table.

### 6.1 Class table

| # | Class | Where it applies | Structure that closes it | Proof | Mutation that must turn it red |
|---|---|---|---|---|---|
| 1 | Value-bearing output | the refusal message and hint | the message names edge ids (table and column names) only, as today; no row value is read before the check | AT-E5 asserts the text; the test data puts a sentinel value in a source row and asserts it is absent | format a seed value into the message |
| 2 | Cleanup on exit path | none | N/A: the check runs before any file or temp dir is opened | n/a | n/a |
| 3 | State and concurrency | none | N/A: a pure function over the config dump | n/a | n/a |
| 4 | Route parity and silent fallback | run, validate, plan validation, compile explain | one split every config path calls (section 6) | AT-E3, AT-E4, AT-C1, AT-C4 | call the check only in the CLI gate |
| 5 | Referential integrity | the dangling-child guarantee itself | the existing `resolve_edge_directions` rule, unchanged; this change only runs it earlier | AT-E1, AT-C2 | default `allow_dangling` to true |
| 6 | Untrusted producer | the config file | the config is schema-validated (`parse_pipeline_config`) before the split | AT-C3 | pass the raw YAML to the split |
| 7 | Check then use (TOCTOU) | validate passes, run later | run repeats the same check through the same split (G2), so a config edited after validate is still caught | AT-E3 | drop the split call from `_subset_stage.py` |
| 8 | Weak tests | a test that passes because the compile layer catches it | AT-C4 forces the compile layer to skip | AT-C4 | remove the config-layer call |
| 9 | Refactor drift | the old message text | tests that pinned it are updated in E1 and listed | AT-E5 | keep the old FanOutPolicy-only text |
| 10 | Frozen contract drift | reason codes, `--json` finding shape | codes unchanged (reason manifest), finding uses the existing `GateFinding` fields | AT-C5, reason-manifest test | rename a code |

### 6.2 Enumerations

#### Exit paths

- Check passes: the split returns and the gate goes on to the compile layer (unchanged).
- Check fails in the CLI gate: one config-layer finding, `None` returned, later layers skipped.
- Check fails in engine run: `SubsetConfigError` from `resolve_subset`, before the subset stage reads a source; the CLI run maps it as it maps the same error today (exit 3).

#### Routes

Callers of `split_subset_config` (from `git grep` on both repos at the SHAs above):

- engine `execution/pipeline/_subset_stage.py:266` (run, all routes)
- engine `plan/validate/_consolidator.py:100`
- CLI `src/decoy/cli/gate/_layers.py:314` and `:394`
- CLI `src/decoy/cli/compile_explain.py:247`
- new: CLI `_run_config_base`

Not through the split, on purpose: `subset/_sample.py:122` (sample builds its own directions) and `select_subset` with a caller-built request (keeps the `_compute` check).

#### FK shapes

The check reads only each edge id and its direction, so every shape gives the same result:

- single-column and composite FKs: one edge id each, columns joined by commas (`_edges.py:33-39`)
- one parent with many children: one edge per child
- self-reference: one edge with the same table on both ends
- multi-parent child: one edge per parent
- an edge touching a generated table: dropped before the check (F3)

Direction values:

- `both`, `upward`: pass
- `downward`, `none`: need `allow_dangling`
- an id not in the built edges: `subset_unknown_edge`

#### Fields

Read from the validated dump, nothing else:

- `subset.edge_directions`
- `subset.allow_dangling`
- `relationships`
- the table kinds `mask_relationships` uses to drop generated edges

#### Output surfaces

All carry the existing code; only the message and hint text change:

- `decoy validate` text
- `decoy validate --json` and `decoy ci check`
- `decoy run` stderr and `--json` error

### 6.3 Reuse inventory

| Need | Reused |
|---|---|
| The rule | engine `resolve_edge_directions` |
| The edges | engine `build_subset_edges` over `request.relationships` |
| The request | engine `split_subset_config` |
| The finding shape and hint | CLI `GateFinding`, `_plan_error_hint` |

### 6.4 Frozen contracts touched

None. Reason codes and the reason manifest are unchanged. The validate `--json` finding uses existing fields. Message and hint text are not frozen surfaces.

### 6.5 Pre-mortem

- An engine test builds a dangling config to test something downstream and now fails at the split: give it `allow_dangling: true` only if the test is not about the refusal, and list it.
- The CLI finding lands without a location, so `.decoy` users get no line: AT-C1 asserts the location.
- The builder adds the CLI call before the engine release is pinned and the gate imports an engine without the check: C1 waits for the repin; AT-C1 fails on the old engine anyway (the compile layer would not catch the unique case, AT-C4).

## 7. Established solutions

Not needed for R1. The check, its codes and its edge-id format already exist; the change is one call site and one message. The pattern followed is the gate's own: a config-layer refusal returns `None` and stops the later layers.

## 8. Owner questions

- Q1. `decoy run --no-subset` on a config whose subset block has a bad edge (F2). Options:
  - A. Refuse anyway. The config is wrong, `decoy validate` refuses it too, and one split serves every path. (Recommended.)
  - B. Skip the check on `--no-subset`. The engine split would need a flag, or the stage would need to bypass the split, which adds a second path.
  Default if unanswered: A.

## 9. Done when

- E1 is merged and released, and the CLI is repinned to that release.
- C1 is merged with AT-C1 to AT-C6 green and both mutations red.
- Roadmap row VALIDATE-SUBSET-EDGES is closed in `docs/roadmap/groups/config.md`, and the guide fix is in the CHANGELOG.
