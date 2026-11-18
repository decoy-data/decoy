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
  `report summary`, `run --dry-run`, help panels, `relationships detect`.
- The SBOM lock-mode refusal prints lock package names.
- The engine `vault_key_mismatch` message still says "the config's seed does not decrypt this vault".

## Freeze candidates (decide before REL-GATE)

Added 2026-11-18. Each of these is cheap before 1.0 and a breaking change (2.0) after it. Sources:
the "Before 1.0 freeze" and "2.0 only if built the other way" tables of [post-1.0-plan.md](post-1.0-plan.md),
and a read of the engine compatibility contract. "Check" means the fact is not verified yet.

On the freeze list with no 1.0 row:

- Audit C10: two-level strategy base classes with one live subclass. Decide the base class custom providers subclass.
- Audit C16: hidden `--ref` and `--rows` flags of `decoy demo` that only print "deferred". Remove.
- Audit J2: `api.scan` uses a different profile call than the CLI. Make them one before the result freezes.
- Partition-stable `when:` on number-with-blanks columns (precision loss at 2**53 and above). Changes output.
- The `.gz` header can store the staging basename. Changes output bytes.
- `run_mask_chunked` writes a pass-through `large_string` column as `large_string`; other routes write `string`.
- Rename the reason `layout.report_source_ambiguous` out of the `layout.` namespace.
- The detection taxonomy split: the list of public renames is not written down in this repo. Check that rows 16 and 56 carry all of them.
- The F22 publication names: not listed. Check that row 59 settles them.
- Audit B9: 68 of 69 platform reason codes are unreferenced. Row 24zj expects to keep them; that is an owner question.

Decide the default now, so the feature can arrive later as a 1.x option:

- F11 output ordering and byte reproducibility: if it should be the default, it must be the default in 1.0.
- F38 dataset metadata: preserve or strip by default.
- F08 coherent free-text identity binding: default on or off for text masks.
- Whole-file profiling aggregates (DuckDB 9): which profile numbers are part of a versioned report tag.
- Notify and `--url` schemes (DUP-DEFECTS B11): `file://` is accepted today. Restrict the allowed schemes now.
- A sibling column that reads an FK key through `when:`: source key (today) or resolved key.

Structure that buys room later:

- An experimental tier. The contract has none, so every command, flag and API name that ships in 1.0 is frozen on day one. Name the surfaces that are new and unproven (candidates: the `library` commands, the init wizard's generated YAML, the Python API, custom providers) and state that they may change in a minor.
- `when:` reserved names: the contract says any addition after GA is breaking. Reserve now every name the grammar may need.
- Custom provider surface: hardening later may restrict what a provider can do. Narrow it now or put it in the experimental tier.
- Faker version: the launch engine freezes on Faker 40.23.0 and the 40.31 migration is planned after R1. Check whether a Faker upgrade changes deterministic output; if it does, migrate before 1.0 or it waits for 2.0.
- Default NER model and detector set: a better default detector later changes findings for existing configs. Check whether a scan records the detector set version it ran, so a new default can be selected by name.

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
