# Handoff: the engine's physical seam, where it stands and how to finish it

Status: current. Written 2026-11-19. For the owner, the orchestrator, and any builder who picks up
engine execution or routing work. It explains what the physical seam is, how much of it runs in
production today, what the original plan said "finished" means, and a proposed path to get there.

Path shorthand as in the roadmap: `E:` is `decoy-engine/src/decoy_engine/`, `ET:` is
`decoy-engine/tests/`, `C:` is `decoy/src/decoy/`.

## In one page

- The **physical seam** (`E:execution/physical/`) is a second compiler plus a coordinator. The logical
  `Plan` says *what* happens to each column. The `PhysicalPlan` says *how* it runs: which driver owns
  each table, which operator owns each column, and why every other option was rejected.
- **It is built and tested, but owns one slice of production.** Only the unified-slice lane
  (`E:execution/_unified_slice.py`) uses it: one table, no foreign keys, data already in memory, and
  every column bound to an allowed operator. The lane is on by default (`unified_slice_enabled=True`
  since 2026-09-20). Every other route still makes its own decisions and runs its own executor.
- **Every other route is already proven in shadow mode.** Task 4.6 of the consolidation program merged
  shadow-parity slices for chunked, out-of-core FK, Group B and C operators, pure, mixed and FK
  generation, and the global strategies. None of them is wired to production. They run in tests only.
- **The original goal was one physical plan for all production execution.** That is the unfinished
  part: activate the remaining routes on the seam, then delete the duplicate decision code.
- **No roadmap row covers it.** It is not a 1.0 blocker under the roadmap's three tests, because the
  intended outcome changes no output. It is v1+ (1.x patch, or 1.x minor where it adds evidence).
- **An open conflict needs an owner decision first.** The 2026-11-15 proportionality audit recommends
  deleting parts of the seam that exist only for a later compiler (items C4 and C5). Finishing the
  seam needs those parts. Both cannot happen. See "Decision needed".
- **Users usually cannot see the lane today.** It declines silently, with no reason code. The CLI does
  not ship the native companion yet, and a table with a Faker or hash column needs it. Packaging is
  roadmap row 90 REL-PKG (1.0).

## What the seam is

```
pipeline.yaml -> PipelineConfig -> compile_plan -> Plan               (logical: what to do per column)
                                                    |
                    run facts (profile, sizes, flags, resident sources)
                                                    v
                         build_live_physical_plan_inputs -> PhysicalPlanInputs (frozen)
                                                    v
                         compile_physical_plan -> PhysicalPlan        (physical: driver per table,
                                                    |                  operator per column, rejected
                                                    v                  alternatives with codes)
                         ShadowCoordinator.run -> ExecutionResult
```

| Piece | Where | Role |
|---|---|---|
| Compiler | `E:execution/physical/_compiler.py` | `compile_physical_plan`. Pure. Picks one driver (FULL_FRAME, SEQUENTIAL, CHUNKED, OUT_OF_CORE) by calling the live routing functions (`decide_execution_route`, `classify_job`), never a copy of them. Records rejected alternatives with stable codes. |
| Plan types | `_plan.py`, `_types.py` | `PhysicalPlan` -> `PhysicalTable` -> `PhysicalNode` -> `ExecutionBinding`. All frozen. |
| Inputs | `_inputs.py`, `_live_inputs.py`, `_snapshot.py` | The frozen snapshot of every fact routing reads. Production builds it from facts `run_pipeline` already has. Tests rebuild it independently. |
| Coordinator | `_shadow_coordinator.py` and the `_shadow_*.py` modules | Runs a `PhysicalPlan`: the per-node batch loop, plus dispatch branches for synthesis, mixed, out-of-core and global full-frame plans. |
| Drivers | `drivers/` | Adapters that delegate to today's route executors ("wrap today's executors", the approved Task 4.2 design). |
| Reasons | `_reasons.py`, `_shadow_diff_codes.py` | Driver and route decision codes, and shadow difference codes. |
| Production entry | `E:execution/_unified_slice.py`, `_unified_slice_admission.py` | The only production importer. Two admission stages: `cheap_admission` (no I/O) and `resident_contract_admission` (every node bound and allowed). Any doubt declines to the pandas full-frame route. |
| Guard | `ET:sentry/test_physical_seam_disconnection.py` | Fails if any module other than the unified-slice files imports the seam. |

Size on engine main (`20847850`): about 6,700 lines in `E:execution/physical/`, and 62 test files
(about 28,000 lines) in `ET:physical/`.

## How it got here

| Date | Step | Source |
|---|---|---|
| 2026-09-09 | Execution consolidation program written. Goal 4.3.1: "Produce one internal physical plan for production execution." | engine `docs/plans/2026-09-09-execution-consolidation-and-native-throughput.md` |
| 2026-09-13 | Task 4.1: physical-plan design approved (two-level driver and operator model, invariants, rejection catalog) | `docs/plans/2026-09-13-physical-plan-design.md` (engine) |
| 2026-09-15 | Tasks 4.2 to 4.5 merged: adapters (#138), compiler (#139), shadow coordinator (#140), unified-slice lane behind a flag (#141) | program plan, Phase 4 outcome notes |
| 2026-09-16 | Task 4.6 shadow slices 1 to 6 merged (#143 to #154). Every route proven in shadow. Production activation was deferred behind an owner gate. | same |
| 2026-09-20 | Unified-slice lane made the production default, after the D9 performance certification | `docs/plans/2026-09-20-unified-slice-activation.md` (engine) |
| 2026-09-20 | Task 4.7: deleted the old standalone native routing lane (#166). The other routes were not deleted, because they were never moved. | `docs/plans/2026-09-20-task-4.7-delete-native-route.md` (engine) |
| 2026-09-30 | The Rust engine program took over the speed goal. It added native kernels **inside each route** (chunked dispatcher, sequential native, out-of-core native hash), not through the seam. | `docs/plans/2026-09-30-rust-engine-program.md` (engine) |
| 2026-10 | The seam kept growing for the unified slice: Faker, `when:`, route evidence, timings, the R4 coordinator split (#271) | engine `docs/records/` |
| 2026-11-15 | The proportionality audit listed seam scaffolding with no production caller for deletion | `docs/records/2026-11-15-proportionality-audit/REMEDIATION.md` |

So the speed half of the program was delivered route by route. The consolidation half, one decision
path and one coordinator for every route, stopped after one slice.

## What "finished" meant in the original plan

From the consolidation program, sections 4.3, 7 and 8, and Tasks 4.6, 4.7, 6.2 and 6.3:

1. One immutable physical plan for every production job, compiled once at preflight.
2. Backend selection per operator at preflight, with no backend change mid-run and no fallback after
   output is published.
3. One coordinator that owns input, prepasses, execution, diagnostics, staging and publication.
4. Every route moved onto it in dependency order: deterministic Faker, single-table chunked,
   out-of-core FK, Group B and C operators, generation, then the global and hard-tail strategies.
5. Superseded routing and its duplicate eligibility logic deleted (Task 4.7, applied to every moved
   route).
6. The pandas oracle limited to parity tests and approved small jobs, with large unsupported work
   refused with a reason (Task 6.2).
7. Durable docs: a decision record, `CODEMAP.md`, the capability matrix and execution-backends page,
   and the plans archived (Task 6.3).

The payoff that remains is not speed, which the Rust program already delivered per route. It is:

- **One place that decides.** Routing logic sits in `_pipeline_routing.py`, `_planner.py`,
  `_pipeline_context.py::decide_route`, each route's own admission checks, and the unified-slice
  admission. The compiler already calls the live functions, so moving routes onto it removes the
  per-route dispatch code instead of adding another copy.
- **One evidence shape.** Every run would report its driver, each column's operator, and coded reasons
  for every rejected alternative, from the same `PhysicalPlan`. Today the unified slice records rich
  per-column evidence and the other routes record different, thinner shapes.
- **Fewer places to change.** One coordinator and one publication contract, instead of one per route.

## What I verified (2026-11-19)

Everything below was run in a clean environment on engine `0.28.0` (main `20847850`) and CLI main
`ccc5540`, without the native companion installed.

1. **The lane works when admitted.** The engine's own scenario `ff_unified_admitted`
   (`ET:unit/execution/_r3_scenarios.py`) records
   `quality_metrics["unified_slice_activation"] = {"activated": True, ...}`. With
   `unified_slice_enabled=False`, the key is absent.
2. **An ordinary CLI job declines silently.** A one-table CSV with `passthrough`, `faker` and `redact`
   columns compiled to this physical plan:
   ```
   driver full_frame | rejected: chunked "chunked_source_below_threshold;chunked_strategy_conditions_unmet"
     people:id:scalar:passthrough   native       native_passthrough
     people:email:scalar:faker      python_only  (no operator binding)
     people:ssn:scalar:redact       native       native_redact
   ```
   `resident_contract_admission` returned `None` because the Faker node has no binding. The run fell
   back to pandas. `route_summary(quality_metrics)` reported `route='full_frame'`, `native=None`, and
   nothing about the decline. The CLI run card said `Route: pandas (legacy adapter)`. The admission
   code lists `faker` among the operators that need the compiled companion, so the missing companion
   is the likely cause. I did not confirm this with the companion installed.
3. **The decline has no reason code by design.** `cheap_admission` says "Returns `None` on ANY doubt
   ... the coded reason is a nice-to-have for a future telemetry pass". The CLI keeps a 90-line copy of
   the admission rules (`C:_native_gate.py:212-303`, audit item J3) to guess what the engine will do.
4. **Docs were stale.** The compiler docstring and package map said "default-OFF", and the activation
   plan said "Status: plan". These are fixed on engine branch `claude/clever-albattani-6iq27c` (commit
   `4868796a`, not yet in a pull request). Still stale and not fixed:
   - the program plan header ("draft for Cam approval");
   - `docs/plans/2026-10-16-r4-shadow-coordinator-split.md` ("Status: plan", but merged as #271).

## Decision needed: finish it or shrink it

The proportionality audit (`docs/records/2026-11-15-proportionality-audit/REMEDIATION.md`) lists:

| Id | Item | What it says | Today's placement |
|---|---|---|---|
| C4 | `E:execution/physical/_protocols.py:58-137` | Five operator Protocols, kept "so a later compiler has a named shape". Delete. | Maintenance candidate (health) |
| C5 | `E:execution/physical/drivers/_chunked.py`, `_sequential.py` | Pass-through adapters instantiated only in tests. Delete. | Maintenance candidate |
| E3 | `ET:sentry/test_physical_seam_disconnection.py:290` | A byte-identical diff gate on `execution/` with about 720 lines of allowlist. Keep the import-direction tests, delete the diff gate. | Owner-decided 2026-11-15 in row 24zl (PROP-GUARDS, maintenance). Not a conflict: the import-direction tests stay, and they are the guard route activation changes. |
| A5, A6 | `E:execution/_unified_slice.py:359`, `E:execution/physical/_compiler.py:444` | Broad `except` that reruns on pandas, or returns `None`. Catch the coded errors only. | Maintenance candidate |

C4 and C5 are the parts route migration would use. E3 goes ahead under row 24zl under every option. Deleting them is right if the seam stays at one
slice, and wasted work if it is finished. A builder who picks up the health candidates should not
delete them before this is decided.

| Option | What it means | Cost | Result |
|---|---|---|---|
| A. Finish the seam | Activate the shadow-proven routes one by one, then delete the duplicate routing (the original Phase 4 end state) | Large: about six activation slices plus deletion, each with the parity, failure, publication, performance and review gates the program set | One decision path and one evidence shape for every route |
| B. Freeze at one slice | Keep the unified-slice lane. Delete the dormant shadow branches, C4 and C5. Record the decision. | Small, and removes a large share of the 28,000 test lines | Simpler code. Two styles of routing stay for good. |
| C. Keep it as an explainer | Keep the compiler as a pure "what would run and why" tool for every route, with evidence and coded declines everywhere. Keep execution where it is. Delete the dormant execution branches. | Medium | One explanation path without moving execution |

**Recommendation: decide A or C before 1.0 freeze, and do the evidence work (step 1 below) either
way.** Step 1 is small, is useful under every option, and fixes a real user problem: a decline nobody
can see.

## Proposed path for option A

This is a proposal, not an approved plan. Each step would get its own plan in engine `docs/plans/` and
go through the usual gates.

| Step | Work | Depends on | Bucket |
|---|---|---|---|
| 0 | Owner decision above. Record it in `docs/roadmap/decisions.md`. Place a row through the inbox. | none | none |
| 1 | **Coded declines.** Both admission stages return a reason (registered in `E:reasons/`) instead of `None`. `quality_metrics` and `route_summary` carry it. The CLI shows it and deletes its admission copy (J3). Also fix A5 and A6. | none | 1.x minor (new reason codes and evidence fields); can land before 1.0 |
| 2 | **Ship the companion to CLI users.** Without it, tables with Faker or hash columns never take the lane. | row 90 REL-PKG (1.0) | 1.0 (already planned) |
| 3 | **Route evidence from the plan for every route.** Compile a `PhysicalPlan` for every job (pure, no execution change) and record its driver, operators and rejected alternatives. This is option C, and A's first step. It needs a rule to let more callers import the seam. | 1 | 1.x minor |
| 4 | **Activate routes in the program's order**, one slice each, behind a rollback flag: single-table chunked, out-of-core FK, Group B and C operators, pure generation, mixed and FK generation, global strategies. Each slice must show byte parity with the pandas oracle, identical failures and publication, a declared memory ceiling, no slowdown, and review. Coordinate with RUN-STREAM (row 63a), which is changing the same routing files now. | 3; 63a settled | 1.x patch per slice if output bytes are identical |
| 5 | **Delete superseded routing** per activated route (Task 4.7 applied route by route). Shrink the disconnection sentry's single-entry allowlist into "every route goes through the seam". | 4, per route | 1.x patch |
| 6 | **Oracle role and docs.** Program Tasks 6.2 and 6.3: limit the oracle, write the decision record, update `CODEMAP.md` and `docs/execution-backends.md`, archive the plans. | 5 | 1.x patch |

**Contract check.** Using the tests in `docs/roadmap/post-1.0-plan.md`: steps 3 to 6 are 1.x as long
as output bytes, exit codes and reasons stay the same, and evidence only gains fields. If a slice
cannot keep a decline identical (for example, it would turn a refusal into a success or a success
into a refusal), it is 1.x minor or 2.0 under that page's rules. That has to be stated in the
slice's plan.

## Risks and things to know before building

- **Two programs touch the same code.** The Rust program put native kernels inside each route. Moving a
  route onto the coordinator must keep those kernels and their evidence. The coordinator's drivers
  wrap the route executors, so this should hold, but each slice has to prove it.
- **Shadow parity was proven in September.** Routes have changed a lot since then: auto-chunk, B6 sinks,
  transforms, `when:`, declared casting, CONFIG-EXPLICIT. Re-run the shadow-parity suite on current
  main before relying on it.
- **Module size.** `_shadow_coordinator.py` was at the 600-line cap before R4 split it. New dispatch
  goes in its own `_shadow_*.py` module, the same pattern R4 used.
- **The disconnection sentry is the guard rail.** Change its allowlist deliberately, in the same slice
  that activates a route, never ahead of it.
- **Platform.** The platform worker calls `run_pipeline` with a sink. The 2026-09-20 activation had to
  make an unused sink acceptable to admission. Each route activation must check the platform's call
  shape in `P:`, even while Platform V1 is parked.

## Where to read next

| To learn | Read |
|---|---|
| The original program and its end state | engine `docs/plans/2026-09-09-execution-consolidation-and-native-throughput.md`, sections 4, 7, 8, 10 (Phase 4 and 6), and the outcome notes at the end |
| The physical-plan model and invariants | engine `docs/plans/2026-09-13-physical-plan-design.md` |
| Why speed went route by route | engine `docs/plans/2026-09-30-rust-engine-program.md` |
| What runs on which route today | engine `docs/execution-backends.md` |
| The code, in order | `E:execution/_unified_slice.py` -> `_unified_slice_admission.py` -> `physical/_live_inputs.py` -> `physical/_compiler.py` -> `physical/_shadow_coordinator.py` |
| The deletion case | `docs/records/2026-11-15-proportionality-audit/REMEDIATION.md`, items C4, C5, E3, A5, A6, J3 |
