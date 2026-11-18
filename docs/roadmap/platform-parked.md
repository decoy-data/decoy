# Platform V1: PARKED

Status: parked

Part of the roadmap: [ROADMAP.md](../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there. Moved here whole from the roadmap on 2026-11-18; section and row numbers are the old roadmap's.

Owner, 2026-11-05: "finish out in flight platform work, document completely, pause platform
development. Focus on CLI/engine through the entire roadmap, then once CLI V1 is out, we can work
platform v1." Restart trigger: CLI V1 has shipped.

Pause record: [`P:docs/PARKED.md`](https://github.com/decoy-data/decoy-platform/blob/main/docs/PARKED.md)
(being written on platform branch `docs/platform-parked`) and the vault note
`10_Projects/decoy/platform-pause-2026-11-05.md` (each finish-out merge is recorded there). On
restart, re-check every row against main first: the engine contracts will have moved under the CLI V1
track.

## 6.1 Group 1: merging now

| Item | State (2026-11-05) | Branch and head |
|---|---|---|
| X10a: job-row choke point and pre-scan pricing (two parts) | Dennis GO and Codex GO round 3; VM 6 merge test 0 NEW-FAILING | `feat/x10a-job-row` `78f25309` (A), `feat/x10a-sentries` `0a0e1468` (B) |
| X4a part A: cloud client factories | Dennis GO, Codex GO at `397c290a`; targeted gate clean | `feat/x4a-clients-onmain` `2923ced4` |
| RBAC S0a: record-mode gate baseline per route and role | Dennis delta GO, Codex GO (`c-s0a4`) at `11ce7f14`; full merge test on VM 5 | `feat/rbac-s0a-gate-baseline` `11ce7f14` |
| X9a: notification owner required, broadcast named, scope sentry (two parts) | Codex GO (`c-x9a`); Dennis reviewing | `feat/x9a-notify-scope-a` `eb53fb2a` (A), `feat/x9a-notify-scope` `93a01a8d` (B) |

## 6.2 Parked with work done (from the finish-out list)

| Item | State at the pause | Branch and head |
|---|---|---|
| Operator set-password (pre-V1 recovery command) | Codex GO-WITH-FIXES on `961eec5a`; value-free fix pushed | `feat/operator-set-password-r2` `83ebb404` |
| X0a-h H6: trusted merge check | Codex GO; Dennis GO-WITH-FIXES (2 MEDIUM, 5 LOW) on `2c1bd451`; uncommitted edits in its worktree | `feat/x0a-h-h6-merge-check` `2c1bd451` |
| X0a-h H1 (owner-signed growth), H2 (ratchet integrity), H4 (gate hygiene) | handoffs written (status plan); not built | `p05-x0ah-h1/h2/h4-build-handoff.md` |
| X1a part A: OWNED_MODELS registry | plan double green; builder in progress, not pushed | `feat/x1a-owned-models` (local, `~/vscode/wt-x1a`) |
| Parallel tests (xdist) | 41 VM failures being fixed; local head ahead of origin | `feat/parallel-tests` origin `2804b2af`, local `28507dce` |
| `plan/x0a-h` | redundant (diff to main empty; #181 merged) | `plan/x0a-h` `0a8d55d2` |

## 6.3 Platform rows kept for the restart

Restart order (preserved from the 2026-11-04 sequence):

1. Phase 0.5 platform slices, in the plan's wave order: X1a part B, X3a, X0a-h H3 and H5, X1b to X1f
   (X1b, X1c, X1d1, X1d2, X1e1, X1e2, X1f), X2b, X4a part B, X4b, X4c, X5a, X5c, X6a, X8a onward, WF-R
   backend (before X1d2 and X1e2), RBAC S0b onward (route registry plan `plan/rbac-route-registry`
   GO at `178ce71d`), deactivation S2 onward (plan `plan/user-deactivation` GO at `7ece3622`), CI-P1
   to CI-P3, OUT-PATH, test trust TT-T2 and TT-T4. X2a MERGED (#195, #196).
2. NAME-REMOVAL wave, platform half ((an identifier kept in the pre-split snapshot) `dfe7cc6a`, 71 build handoffs; S0a
   needs (an identifier kept in the pre-split snapshot)).
3. H-1 Wave B platform splits (P0, P11a, P10 `api/jobs/` 37 slices, P5, P4, P7, P8, P2, P3, P1, P6).
4. GEN-API 1f real-host rows (owner run; build MERGED #153, default OFF).
5. Phase 1 platform waves P-1 to P-6: F30 P1b, B-10 S1c, H-1 P0; B-10 S2a, F30 repin, F35 P0; B-10
   S2b and S3, F30 P2a, P2b, D1; F34 P0 to P3, H-1 P11a; F32 platform slices, F29 P1 and P2, F35 P1a
   onward. With PUB-REC, POLICY, the platform halves of DELIV and SAMPLE, the B-6 platform consumer
   slice (changes `_persist_job_vault` at the B-6 repin) and the scheduler finish-and-activate plan
   (`plan/scheduler-state-and-direction` `4fff389e`). The dormant S3A, S3B, cgroup, lease and S13 to
   S17 code is not yet active; it is to be finished and activated, never deleted (owner, 2026-11-02).
6. Phase 2 platform: F14, F13 slice 3a, the F24 reservation model and the B-10 estimate API route,
   F23 platform resume, F36-P.
7. Phase 3 platform: F45 (claim-time re-authorization, SAML, MFA), the F44 platform half (air-gapped
   bundle, container digests, G13, G18), the F01 and F02 platform surfaces.

| Item | Feature | State | Next |
|---|---|---|---|
| WF-R backend: remove workflow models, FKs, DDL, routes, runner, run gate, schedule fields and tests in one migration; replaces X10b | baseline | NOT STARTED | before X1d2 and X1e2 |
| OUT-PATH: non-admin outputs API returns absolute `output_path` (`api/jobs/routes_outputs.py:124,186`); return opaque ids | F45 | NOT STARTED (live bug, not exposed) | on restart |
| CI-P1, CI-P2, CI-P3: self-hosted backend lanes, Postgres test markers, nightly | CI | NOT STARTED | after X0a-h H2 and H4 |
| PUB-REC: per-table publication record on the full-frame route | F22 interim | NOT STARTED | Phase 1, early |
| DELIV platform half (database "deliver nothing" is a staging schema swap, Q11) | F22, F34, F35 | NOT STARTED | after CLI delivery |
| SAMPLE platform half (web wiring is design input D3) | F04 | NOT STARTED | after SUB-RUN |
| POLICY: per-job retry and low-memory route; retry from scratch after a crash (Q21) | F23, F27 | NOT STARTED | owner call Q21 |
| Re-enable pre-scans: flip (an identifier kept in the pre-split snapshot) in `api/jobs/release_gates.py` (off since 2026-08-27) | F15 | NOT STARTED | after X10a and the NAME-REMOVAL platform half |
| SCAN-MULTI platform half (Q25) | F15 | NOT STARTED | with re-enabled pre-scans |
| F21 Studio parity backend: slices 1, 1b, 3a, 5 MERGED (#150, #170, #146, #160); layout store unification and `geo_generalize` UI remain | F21 | plan `plan/f21-studio-parity-backend` `77906360` | on restart |
| F14 wrapping-key rotation (crypto tier): `MultiFernet` with `key_version`, rewrap across all custody targets, SMTP password wrapped (G14), fail closed on a missing key (G23) | F14 | NOT STARTED | Phase 2 |
| F45 finish: claim-time re-authorization (the one item the spec forbids omitting), SAML, MFA; SMTP password encrypted, auth cookie `Secure`; login limit, password policy, CORS (G15); single-process guard (G17) | F45 | NOT STARTED | Phase 3 |
| B-10 estimator S1b onward and an API route for the estimate | F24 | S0, S1m, S1a, S1b MERGED | wave P-2 |
| F31 E0b and the platform slices (moved from CLI row 65, owner 2026-11-12) | F31 | NOT STARTED; plan `E:plan/f31-safe-output` `2340a45b` | on restart |

**Live platform bugs recorded for the restart** (not exposed; the platform is unreleased): SSO can
resolve to the wrong account and does not bind the issuer (X3a fixes it); OUT-PATH.

**Also parked:** X4a part B and X4b call-site conversion; the approved git history scrub of business
docs (run at a quiet point, never mid-stack); the V1 role set (user PATCH accepts only admin or user);
the `sso` license gate is defined but not enforced; the dev license key defaults to the business tier;
flaky tests on platform main (1.x patch backlog); UX map Q19, Q21, Q25; X0a-h H3 and H5. Platform main
known failures live in the stored baseline `baselines/decoy-platform-main.json` in the vault.

## Later candidates (platform only)

Non-breaking ideas, so v1+ by rule. A candidate becomes a row in the table above when a release picks it up.

| Item | Source | Why it does not break |
|---|---|---|
| F27 governed schedules | Council features | Platform trigger path for a pinned pipeline. Companion scope says V1: check. |
| 16 `decoy-admin` log query | DuckDB opportunities (vault `v2/duckdb/`, platform `plan/v2-duckdb-plans`) | New admin command. |
| 17 Archive old logs and audit rows to Parquet | DuckDB opportunities (vault `v2/duckdb/`, platform `plan/v2-duckdb-plans`) | New admin feature. |
| 21 DuckDB-Wasm in-browser preview | DuckDB opportunities (vault `v2/duckdb/`, platform `plan/v2-duckdb-plans`) | New web feature. |
| Login rate limit, lockout and password policy (F45) | findings-register, after V1 | New platform feature. |
| Multi-process API support | findings-register, after V1 | New platform capability. |
| 4 MCP server in the platform (`/mcp`) | Platform V2 candidate plan (`P:docs/backlog/v2-candidate-plan.md`) | New endpoint. |
