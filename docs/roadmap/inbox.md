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

Carried from the track on 2026-11-18 (the "V2-LOG" list found at the 2026-11-17 merges):

- 24f one-year bucket: the one-year datetime bucket in a plain fit snapshot (engine #632 review).
- F24 native term: a native-route term for the lifecycle estimate (engine #635 review).
- F24 L1 and L4: two review notes on the lifecycle estimate (engine #635).
- SCAN-ML C2a: a blocked run that cannot write its post-scan report keeps exit 4 and prints a warning (CLI #301).
- F22 L1 and L3: the duplicate writer-type guard, and the adopt path serializing the writer twice (engine #622).
- F16 `canonical_sha256` helper scatter: the `canonical_sha256` helper is spread over several places (engine #631 review).

Carried from the old open-questions list:

- First-user QA (2026-11-08): suggested new commands `secret generate`, `ci init`, `subset init`,
  `report summary`, help panels, `relationships detect`. (`run --dry-run` is now Later row DRY-RUN in
  [groups/run.md](groups/run.md).)
- The SBOM lock-mode refusal prints lock package names.
- The engine `vault_key_mismatch` message still says "the config's seed does not decrypt this vault".

Before the 1.0 freeze (2026-11-18, from [post-1.0-plan.md](post-1.0-plan.md), the outside review in docs PR #319
and the 1.x schedule). Each one is free before row 93 (REL-GATE) and 2.0 after it. Triage makes it a 1.0 row or
accepts it as a 2.0 item in [releases-1x.md](releases-1x.md):

- Proportionality audit C9 (`DateShiftStrategy`), C10 (two-level strategy base classes), C16 (hidden `decoy demo`
  flags), J2 (`api.scan` profile call): none of rows 24zi to 24zk holds them.
- The taxonomy split under the retired product name: its public renames (owner question 4 in post-1.0-plan; NAME-REMOVAL rows 16 and 56 hold the rename work).
- Partition-stable `when:` on number-with-blanks columns (platform plan 12): fixing it changes output on integers of
  2**53 or more.
- Atomic output: the `.gz` header can store the staging basename.
- `run_mask_chunked` writes a pass-through `large_string` column where the other routes write `string`.
- CLI reason registry: move `layout.report_source_ambiguous` out of the `layout.` namespace.
- Outside review: a generated sequential id came out negative and a date column came out as lorem text; the fidelity
  report scored that column 1.000 and the run card and report disagree. V1 QA decides; a reproduced function break is
  a V1 row.
- Outside review: drop Python 3.10 and move the certified DP profile to a supported version.
- The update channel: `decoy upgrade` trusts one release key pinned in the build and accepts only the exact
  `cli-version-document/v1` schema. A key rotation path has to ship in 1.0 to help 1.0 installs
  ([releases-1x.md](releases-1x.md), "The upgrade path").
- Corrective backlog (vault): the 10 `[check:` entries and the 16 `[V1` entries need a look at the next triage.

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
