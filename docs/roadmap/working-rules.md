# Working rules: how work moves, develop correctly, sequencing

Status: current

Part of the roadmap: [ROADMAP.md](../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

Moved here whole from the roadmap on 2026-11-18. Section numbers in the text (3, 4, 5.2, 5.3, 6) are the old roadmap's; the old text is in the [snapshot](../archive/2026-11-18-roadmap-before-split.md). Which row is in 1.0 is decided by the group files, not by this page.

## 3. How work moves (dev loop and merge rule)

Every row runs the dev loop in `~/dev-rules/development-loop.md` (FRAME, PLAN, build, gate, merge,
DOCUMENT), with risk from `~/dev-rules/risk-and-exceptions.md` and tests from
`~/dev-rules/testing.md`. The PLAN names the behavior, the failure modes and the acceptance tests
first. Plans are authored by Opus and gated by Dennis, then Codex; code gets Codex plus one Dennis
(no OpenRouter gates). The orchestrator merges on double gate green: Codex GO, Dennis GO or APPROVE,
0 V1 findings, a clean trial merge, the head re-verified, a plain squash PR, never `--admin` or
force. Test depth: T0 the touched file's tests per edit, T1 impact-selected per commit, T2 on the
exact merge head; the full suite runs only on an escalation trigger from `testing.md` (registry,
schema, dependency lock, pin, test tooling and the rest) and is diffed against the saved main
baseline, never a second main run. Slices that need a full suite may ride a merge train (owner
2026-11-10, `~/dev-rules/profiles/local-operations.md`): reviewed heads merge into one batch branch
2 or 3 times a day, the suite runs once on the batch head, then each PR merges in order. Gates run locally and on self-hosted runners; hosted GitHub CI
is off for billing. The V1 bar: only a function break, data loss or a non-admin leak blocks a merge;
everything else goes to the corrective backlog (vault `handoffs/V2-CORRECTIVE-BACKLOG.md`), where each entry is tagged 1.x or 2.0 ([post-1.0-plan.md](post-1.0-plan.md)). A
slice is done when this roadmap and the shipped log ([`RECENTLY-SHIPPED.md`](../RECENTLY-SHIPPED.md))
say so. Commits and PR titles follow Conventional Commits (`~/dev-rules/workspace-and-vcs.md`).

## 4. Develop correctly (standing)

Owner (2026-11-05): "make sure we still plan to develop correctly: central registries for any cross
cutting concerns and correctly sized files and file directories." These rules apply to every row
and every plan. Source rules: `~/dev-rules/cross-cutting-concerns.md` and
`~/dev-rules/architecture.md`.

**4.1 One registry or choke point per cross-cutting concern.** A rule that many call sites must
follow (a reason code, a file write mode, a path check, an outbound client limit, a redaction rule)
lives in one place that every site must pass through, so forgetting it fails a test instead of
failing silently. Each choke point has a guard test that walks the real artifact (the import graph,
the syntax tree, the registry manifest), not a list the author remembers. Known exceptions sit in a
ratchet allowlist that can shrink but never grows without a reviewed change (the X0a ratchet
manifest: engine #378, #379; CLI #81, #82).

Choke points the CLI V1 track builds on or adds:

| Concern | Choke point | Guard | Row |
|---|---|---|---|
| Reason codes | `E:src/decoy_engine/reasons/_registry.py`, append-only, versioned | registry and release-pin tests; REG-RENUMBER `--check` at merge | every registry row |
| Safe output and redaction | F31 `SafeEvent` and closed error labels (engine #368) | F31 sentries and the secret-injection corpus | F31 |
| File access | engine file-access policy (A-4, engine #361) | file-access sentry baselines | all source readers |
| Outbound clients | engine connector client limits (X4d, engine #384, #385) | construction sentry | CLI-CLOUD, F02 |
| Private file writes | engine `_private_file` (X7b, engine #382); CLI `_private_file.py` | write-mode sentries | X7c |
| CLI source readers | `C:src/decoy/cli/_sources.py` (`read_source`, `iter_source_chunks`) | CLI-DIALECT tests | CLI-DIALECT |
| CLI target writers and readers | writers in `C:src/decoy/cli/io/_targets.py`, readers in `C:src/decoy/cli/_sources.py` (`read_file`) | `C:tests/sentry/io_policy/test_target_writes.py` (G-ONE-TARGET-WRITE) and the widened G-ONE-CSV-READ | CLI-FMT A, A2, B (merged #101 to #103) |
| Local record library writes | one library writer (LIB L1b; the shared atomic writer `C:src/decoy/_atomic.py` merged in #85) | `C:tests/sentry/test_atomic_writer.py` (G-ONE-ATOMIC-WRITER) | LIB rows |
| Scratch and quotas | the F25 scratch manager | registration sentry | F25 |
| Publication and delivery | F22 publication descriptor, DELIV transactional sink | delivery tests | F22, CLI delivery |
| Module size | the size census per repo | `test_module_size.py` | FILE-SIZE |

A plan that adds a call site names the choke point it goes through. A plan that adds a new concern
names its registry and its guard test, or says why none is needed. A review finding that is a class
of bug (the same mistake possible at many sites) gets a choke point and a sentry, not only a patch.

**4.2 File and directory size.** Source files stay at about 800 lines or fewer. The engine census is
stricter and stays as it is (`E:tests/sentry/test_module_size.py`: goal 600, ceiling 700, exact-match
allowlist). A touched file that is already over the limit must not grow; a slice that needs to add
to it splits it first or moves the new code into a new module. Splits follow the reason to change and
produce cohesive packages, not size-only cuts (H-1). A package that collects too many modules gets
subpackages: `E:src/decoy_engine/execution/` holds 93 modules today (H-1 E8). Oversize today
(2026-11-05): CLI `report.py` 2373, `run.py` 1717, `scan.py` 1405, `preflight.py` 886 lines (the CLI
has no size sentry yet); engine (an identifier kept in the pre-split snapshot) 1046, `execution/native/_draw_site_providers.py`
985, (an identifier kept in the pre-split snapshot) 976, `execution/_chunked_fk.py` 970, `execution/native/_determinism_protocol.py`
928, `quality/synth_report.py` 863. A slice is at most about 800 hand-written lines including tests;
bigger work is split into stacked parts.

**4.3 The owner's review question.** Owner (2026-11-05): every plan, build and gate asks "is this
doing something that every other class does differently? could it be rolled into a central location
to make it easier to change later?" A yes means the plan adds or reuses a choke point (4.1) before
the slice adds another copy. Builders read `~/dev-rules/00-universal.md`,
`~/dev-rules/cross-cutting-concerns.md`, `~/dev-rules/architecture.md` and `~/dev-rules/testing.md`
before they write code, and every build handoff says so.

**4.4 Plans name both.** Every PLAN states (a) the registry or choke point for each cross-cutting
rule it touches, and (b) each file it adds or grows, with its line count before and after and the
package it lands in. A gate that finds a plan missing either sends it back.

## 5.2 Sequencing rules

1. **Reason registry chain.** SUB-STOP takes 1.6.0, NAME-REMOVAL E1 takes 1.7.0, then every other
   registry-touching row takes the next free minor in merge order (owner OQ-3 = C1, 2026-11-05).
   Once REG-RENUMBER merges, registry slices may build in parallel; they still merge one at a time,
   and the tool renumbers each slice to `main + 1` at merge (owner, 2026-11-05). Until it merges, the
   chain is strictly serial by build order (owner rule, 2026-11-03).
2. **One writer per hot module** (takes effect when RUN-SPLIT, row 95, merges; until then one
   branch at a time writes `C:src/decoy/cli/run.py`, and the run.py rows are CLI-DIALECT, CLI-FMT
   A, VALIDATE-ALWAYS, SUB-RUN CLI half, CLI delivery, RESULT, SAMPLE, LIB L3a, L3b, L5a, L5b, F23
   resume, F29 C1, F30 C1b). `decoy run` lives in `C:src/decoy/cli/run/`. One branch at a time
   writes each module there; two rows that write different modules build in parallel.
   `__init__.py` (the options) is shared: a row adds its option as one additive hunk and rebases at
   merge, and a row that changes an existing option takes the module like any other. Rows and the
   modules they write:
   - SUB-RUN CLI half: `_prepare.py`, `_execute.py`, plus an option.
   - CLI delivery: `_execute.py` (stage then deliver, the chunked path through the same sink).
   - RESULT: `_errors.py` (exit 6, capacity widening), `_render.py` (the run result summary).
   - SAMPLE: `_execute.py` (`--sample` through the subset, output to scratch), plus an option.
   - LIB L3a: `_evidence.py` (evidence and run-result records).
   - LIB L3b: `_flow.py` (scratch lifecycle), `_evidence.py` (sample-run records).
   - LIB L5a: `_execute.py` (the `ProgressSink` on `run_pipeline`), `_flow.py` (the spinner).
   - LIB L5b: `_flow.py`, `_notify.py` (job logs).
   - F23 resume: `_execute.py` (table-level resume), plus `--resume`.
   - F29 C1: `_errors.py`, `_render.py` (error and progress consumers).
   - F30 C1b: `_notify.py` (spans and the exit flush on `_otel`), `_flow.py`.
   - Done and out of the lane: CLI-DIALECT, CLI-FMT A, VALIDATE-ALWAYS.

   Hot pairs: `_execute.py` (SUB-RUN, CLI delivery, SAMPLE, L5a, F23) and `_flow.py` (L3b, L5a,
   L5b, F30 C1b) stay single-writer. One branch at a time writes `C:src/decoy/cli/scan.py`: SCAN-MULTI
   S1c, H-1 C3, NAME-REMOVAL CLI half; in 1.x also S3-cli, LIB L2 and L5b (owner 2026-11-22). CLI-CLOUD's plan must say whether it
   enters the `run.py` lane (after RUN-SPLIT: which `run/` modules it writes). The plan for each
   row names its modules; the module list above is the RUN-SPLIT plan's reading of the row titles.
3. **Engine releases.** One release and one CLI repin open at a time. A CLI half that needs new
   engine code waits for the release and the repin (engine repin checklist: compatibility, fences,
   frozen surfaces, docs, `PIN_PREFIX`, the Dockerfile `ARG`, the catalog).
4. **Release cadence.** Cut an engine release from main every day while engine rows are merging
   (owner, daily engine release train D4, 2026-11-09), carrying whatever has merged (owner may release without per-release confirmation). The
   CLI repins once per release, cumulatively: one repin carries every engine change since the last.
   Named releases below (R-c, R-d) list what each must contain at minimum; the cadence decides when.
5. **LIB.** L1a-engine, then an engine release and the CLI repin, then L1b, then L1c. L2, L3a, L3b,
   L4a, L4b, L5a and L5b follow L1c and their feature rows, in parallel on files that do not
   overlap.
6. **SCAN-MULTI.** S1a and S1b ship in one engine release. CLI-DIALECT lands before S1c, and S1c
   before LIB L2 (L2 replaces the plan's S1d). CONFIG-EXPLICIT lands before S3-engine; S3-engine is
   released, then S3-cli. LIB L2 and S3-cli are 1.1 (owner 2026-11-22), so only S1c is in 1.0.
7. **CLI-FMT.** DONE 2026-11-07: A, A2 and B merged in order (#101 to #103) after one T3 on B's head.
   ATOMIC-OUTPUT (row 21b) DONE 2026-11-07 (#105).
8. **Publication chain.** F25 before F22 (owner, 2026-10-30); F22 and POSTSCAN-STREAM before CLI
   delivery; SUB-STOP before SUB-RUN; SUB-RUN before SAMPLE; F22 and CLI delivery before F23 resume.
9. **H-1** slices move only files no live branch touches, behavior-preserving, characterization
   tests first.
10. **Close partly merged rows first** (owner, 2026-11-10). A row whose engine half is merged gets
    its CLI half built before any new row starts. No new row plan starts while 5 or more partly
    merged rows wait only on a CLI half.
