# Roadmap inbox

Status: current

Part of the roadmap: [ROADMAP.md](../ROADMAP.md). Path shorthand (`E:`, `C:`, `P:`, vault) is defined there.

Every new finding, review note, QA result, audit item and idea lands here first, as one line: the
date, where it came from, and what it is. Nothing goes straight into a group file.

Triage empties this page. Each item gets exactly one outcome:

| Outcome | Where it goes |
|---|---|
| Blocks 1.0 | The 1.0 table of its group file. Only if it meets freeze, safety or broken-today (see the roadmap). |
| Later | The Later table of its group file, with its bucket from [post-1.0-plan.md](post-1.0-plan.md). |
| Maintenance | The Maintenance table of its group file. |
| Rejected | Deleted, with one line in [decisions.md](decisions.md) if someone may ask again. |

## Untriaged

- 2026-11-18, engine #695 review (FAKER-MIGRATE S1): masking with Faker `address_city` (and the
  reflected `city`) in locale `it_IT` is not deterministic across processes. The same seed and key
  give different output under different `PYTHONHASHSEED` values, on the real `run_pipeline` route,
  in both deterministic and positional mode. Cause: Faker builds the it_IT city list from a set, so
  its order follows the string hash. en_US is stable. Likely blocks 1.0 (broken today: same-seed
  masking must be reproducible). Separately, unseeded module-level `random` makes `passport_*` and
  some es_ES, es_MX, uk_UA, sv_SE, th and el_GR providers non-reproducible in generation.
- 2026-11-19, engine physical-seam handoff
  ([handoffs/2026-11-19-engine-physical-seam.md](../handoffs/2026-11-19-engine-physical-seam.md)): the
  physical plan and coordinator own only the unified-slice lane; every other route is proven in
  shadow but never activated. Owner decision needed: finish the seam (Task 4.6 activation, then
  delete the superseded routing), keep it as an explainer, or freeze it and delete the scaffolding
  (audit C4, C5, E3). Hold the C4 and C5 deletions until decided. Separately, the unified slice
  declines with no reason code, so `route_summary` and the CLI cannot say why a job fell back to
  pandas (handoff step 1).

Carried from the track on 2026-11-18 (the "V2-LOG" list found at the 2026-11-17 merges):

- 24f one-year bucket: the one-year datetime bucket in a plain fit snapshot (engine #632 review).
- F24 native term: a native-route term for the lifecycle estimate (engine #635 review).
- F24 L1 and L4: two review notes on the lifecycle estimate (engine #635).
- SCAN-ML C2a: a blocked run that cannot write its post-scan report keeps exit 4 and prints a warning (CLI #301).
- F22 L1 and L3: the duplicate writer-type guard, and the adopt path serializing the writer twice (engine #622).
- F16 `canonical_sha256` helper scatter: the `canonical_sha256` helper is spread over several places (engine #631 review).

Carried from the old open-questions list:

- First-user QA (2026-11-08): suggested new commands `secret generate`, `ci init`, `subset init`,
  `report summary`, `run --dry-run`, help panels, `relationships detect`.
- The SBOM lock-mode refusal prints lock package names.
- The engine `vault_key_mismatch` message still says "the config's seed does not decrypt this vault".

## Freeze candidates (decide before REL-GATE)

Triaged 2026-11-18. The freeze-list items with no row became the 1.0 rows FREEZE-SURFACE (health),
FREEZE-OUTPUT (run) and FAKER-MIGRATE (mask). The default-on choices (F11, F38, F08, profiling
aggregates, the sibling FK key) stay opt-in and are listed in [2.0-holding.md](2.0-holding.md). The
experimental tier is the 1.0 row EXPERIMENTAL-TIER (release). Nothing is left to triage here.

## Open owner questions

Carried whole from the old section 5.6.

- First-user QA (2026-11-08, [report](../records/2026-11-08-cli-qa-first-user.md)), answered by the owner
  the same day with the recommended options: scan values redacted by default (row 24c); gate catches
  run-time config errors with exit 1 (row 24b); `shuffle` must be deterministic (row 24d); QA bugs are
  V1 (row 24e). The QA wizard asks (data-aware presets, multi-table, color, `--no-input`) go to
  INIT-WIZARD (row 32b). Suggested new commands (`secret generate`, `ci init`, `subset init`,
  `report summary`, `run --dry-run`, help panels, `relationships detect`) are V1-nice-to-have,
  triaged after the critical path; FK detection across files is SCAN-MULTI. The uncovered-column
  finding is CONFIG-EXPLICIT E2 (row 22, owner rule 2026-11-05).

- The other open H-1 questions (Q3 answered: after CLI V1).
- Phase 1 tracks questions still open from `PHASE1-TRACKS.md`: Q9 (fate of `feat/f25-protected-scratch`;
  recommendation: keep it as the F25 build base) and Q11 (F36-P timing; recommendation: with the
  platform, after CLI V1). Q5 answered 2026-11-08: F35 E1a before F32 E1b.
- Still open from earlier: the SBOM lock-mode refusal that prints lock package names; the engine
  `vault_key_mismatch` message still says "the config's seed does not decrypt this vault"
  (`vault.py:520-524`).
