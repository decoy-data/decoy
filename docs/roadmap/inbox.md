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

- 2026-11-22, header promo video (vault `10_Projects/decoy/header-promo-video-2026-11-22.md`): `decoy scan` does not flag a 16-digit `card_number` column.
- 2026-11-22, header promo video: the run card prints `v` where a check mark is expected.
- 2026-11-22, freeze-surface audit (vault `10_Projects/decoy/freeze-audit-2026-11-22.md`), QA notes: env-var freeze rows; `DECOY_PK_LENIENT` and `DECOY_FK_STRICT_DETERMINISM` are dead; five error classes are never raised; freeze rows for the CLI `settings.json` and the library layout; six spellings of the output flags; the `--post-validate` name; the `--native` and `--no-native` pair; the library gaps in `-y`, `-q`, `-v`, `--json` and `status`; the legacy wire codes `route.legacy_lane` and `safe_output.legacy_withheld`; the mix of stored-tag styles; `register_faker_provider_v2`.
- 2026-11-22, QA (found at CLI #381 CI, exempted in `test_items_error_envelope`): `decoy validate CONFIG --json` reports a bad config as a validation-result document (status error), while `validate config` emits the `decoy-error/v1` envelope. The two disagree.
- 2026-11-22, QA, engine #757 (DELIV E2a): LOW-1 `FD_STAGED_LABELS` placement; LOW-2 a duplicate `os.replace` in `_local` (one `_rename_staged` would keep registry 201); LOW-3 the mode refusal class differs per policy; LOW-4 a pointer of kind `dir` is not refused (unreachable).
- 2026-11-22, V2-LOG, CHUNKED-STRUCT: the `_fk_keys` rebuild has two ways to restore the source type (the declared-type rebuild and the post-cast `_with_source_types`); fold them into one per-column policy. `is_nested_type` misses list views (`pa.types.is_nested` includes them); this predates engine #754.
- 2026-11-22, V2-LOG, NATIVE-MISSING-WARN: the notice uses `any()` over the plan, while unified-slice admission uses `all()` per table, so a partial companion can fall back with no notice; decide per table. Keep one cached probe per process. `run_pipeline_isolated` does not carry `native_fallback_code`. Text-only configs get no warning (Q2).
- 2026-11-22, V2-LOG, DELIV C0 (CLI #378): in `CREATE_ONCE`, an interrupt between REPLACED and the restore leaves a collision window; an existing hard-link collision is adopted through `_same_file`. `publish_local_targets` is about 80 lines with a nested `try` (moved code).
- 2026-11-22, V2-LOG, platform: docs and comments mention engine names that engine #760 removed (`FlagPauseSignal`, `get_default_executor`, `VALIDATION_CODES`): `api/models.py:2960`, `notifications/router.py:53` and `docs/architecture/*`.
- 2026-11-22, V2-LOG: a route-table sentry for the engine route docs (DOC-DRIFT-ROUTES Q1, recommended answer applied). `run_mask_chunked` defaults `native_threads` to 1 (ENGINE-THREADS-DEFAULT Q1).
- 2026-11-24, V2-LOG, FREEZE-OUTPUT O2 (CLI #403, Codex R2): a DataFrame CSV target follows `os.linesep` (`_targets.py`, pandas writer), so Windows writes CRLF where Linux and macOS write LF. Windows is outside the V1 support tier; pin the line terminator when Windows lands.
- 2026-11-22, code-quality handoff ([handoff](../handoffs/2026-11-22-code-quality-audit-and-pre-merge-checks.md)): run one full read-only quality audit at V1 alpha, beside QA, and triage its findings with QA's; a delta pass on the alpha-to-release diff before REL-GATE. Candidate for release-gates R1.
- 2026-11-22, code-quality handoff section 4: a narrow freeze-surface audit now (public names, reason codes, flags, exit codes, `--json` shapes, config keys, env vars, stored formats) for anything rows 24zj and FREEZE-SURFACE miss.
- 2026-11-22, code-quality handoff section 5: standard pre-merge checks in the dev loop (`/simplify` and `/code-review` on every PR diff, `/security-review` and a Windows checklist by area) and a `lintdebt` ratchet step in `gates.sh` for both repos. Owner questions in section 6.
- 2026-11-22, 1.x program ([releases-1x.md](releases-1x.md)): six owner decisions (the `risk-utility-report/v1` tag, the copula DP route, the Faker locales compatibility call, Q15 for F01, the copula snapshot, dark landing). Listed there, not repeated here.
- 2026-11-18, carried from draft CLI #321 (not on main before): freeze, proportionality audit C9: `DateShiftStrategy`, a V1 class never built (two helpers are used); if it is exported, remove it before the freeze. FREEZE-SURFACE holds C10, C16 and J2 but not C9.
- 2026-11-18, carried from CLI #321, outside review (docs PR #319): freeze, drop Python 3.10 and move the certified DP profile to a supported version. Dropping an interpreter after 1.0 refuses an install that works.
- 2026-11-18, carried from CLI #321, outside review: broken today, a generated sequential id came out negative and a date column came out as lorem text; the fidelity report scored that column 1.000, and the run card and the report disagree. A reproduced function break is a 1.0 row.
- 2026-11-18, carried from CLI #321, outside review: broken today, `examples/mask_example.yaml` fails `decoy validate`, and `decoy init --preset generate` fails on the demo's own CSV (EXAMPLES-FIX).
- 2026-11-18, carried from CLI #321, outside review: broken today, the README gives the wrong output location and exit-code meanings (README-FIX). Row 92 (REL-DOCS) may fix it first.
- 2026-11-21, language write-up (owner: go with recommended): `decoy validate` on a `.decoy` file shows an engine schema error with the config path but no line number, while `compile_text` has the line. Fix inside row DECOY-LANG.
- 2026-11-21, language write-up: check that the guide's `date_shift(min_days: -30, max_days: 30)` examples (02-masking.md, cheat-sheet.md, agent-card.md) still compile now that DATE-SHIFT-FORMAT requires `date_format` on text dates; fix the guide in that row if not.
- 2026-11-21, language write-up: `decoy validate` accepts an S3 target that `decoy run` refuses. Cloud buckets are out of 1.0 (owner 2026-11-21), so this goes with row 64 CLI-CLOUD.
- 2026-11-18, engine #695 review (FAKER-MIGRATE S1): masking with Faker `address_city` (and the
  reflected `city`) in locale `it_IT` is not deterministic across processes. The same seed and key
  give different output under different `PYTHONHASHSEED` values, on the real `run_pipeline` route,
  in both deterministic and positional mode. Cause: Faker builds the it_IT city list from a set, so
  its order follows the string hash. en_US is stable. Likely blocks 1.0 (broken today: same-seed
  masking must be reproducible). Separately, unseeded module-level `random` makes `passport_*` and
  some es_ES, es_MX, uk_UA, sv_SE, th and el_GR providers non-reproducible in generation.

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

- 2026-11-19, DECOY-LANG foreign-key experiment (engine 0.28.0 checkout, three-row tables, one run,
  not investigated further): with a parent key masked by `faker` (`person_email`, namespace set,
  `deterministic` off) and a relationship with `orphan_policy: remap`, the orphan child key was
  remapped to the same fake value as an existing parent row, so the orphan joins to a parent it never
  had. With `deterministic: true`, or with `hash`, the orphan got a distinct value. Possible safety
  item (a wrong join reported as success); needs a repro on the pinned engine before triage.

- 2026-11-19, owner question during DECOY-LANG: a fixed-width `layout` can only be written inline
  in the pipeline file; there is no way to keep it in a separate file, as `column_names_file` does
  for a headerless CSV. Idea: an engine source option `layout_file` (and the same on a fixed-width
  target), read where `column_names_file` is read. YAML and `.decoy` would both get it with no
  language change, since options pass through. The engine's fixed-width notes already name a COBOL
  copybook import as a separate later step; this is the plain-file form of the same need. Engine
  work, additive; likely Later.

## Freeze candidates (decide before REL-GATE)

Triaged 2026-11-18. The freeze-list items with no row became the 1.0 rows FREEZE-SURFACE (health),
FREEZE-OUTPUT (run) and FAKER-MIGRATE (mask). The default-on choices (F11, F38, F08, profiling
aggregates, the sibling FK key) stay opt-in and are listed in [2.0-holding.md](2.0-holding.md). The
experimental tier is the 1.0 row EXPERIMENTAL-TIER (release). Nothing is left to triage here.

## Engine speed and route record (promoted 2026-11-19, owner)

The section 9 lines of `E:docs/records/2026-11-19-engine-speed-and-route-completeness.md` (engine
#715). The owner took the recommended answers on 2026-11-19, so each line is placed. Nothing is left
to triage here.

- NONFK-OOM (M1): promoted 2026-11-19 (owner). 1.0 row NONFK-OOM, [run](groups/run.md).
- NATIVE-MISSING-WARN (M3): promoted 2026-11-19 (owner). 1.0 row NATIVE-MISSING-WARN, [run](groups/run.md).
- GEN-WINDOWED-BATCH (F1): promoted 2026-11-19 (owner). 1.0 row GEN-WINDOWED-BATCH, [generate](groups/generate.md).
- ENGINE-THREADS-DEFAULT (F3): promoted 2026-11-19 (owner). 1.0 row ENGINE-THREADS-DEFAULT, [run](groups/run.md).
- FAKER-NATIVE-WIDEN (C1): promoted 2026-11-19 (owner). 1.0 row, made firm V1 on 2026-11-22, [mask](groups/mask.md).
- GEN-VECTOR-STREAMS (C2): promoted 2026-11-19 (owner). Later row, 1.0.x, [generate](groups/generate.md).
- TEXT-REDACT-RUST-SPLICE (C3), FPE-CHECKSUM-NATIVE (C5): promoted 2026-11-19 (owner). Later rows, 1.0.x, [mask](groups/mask.md).
- LARGE-STRING-CAST and UF-DOMAIN (C4): promoted 2026-11-19 (owner). 1.0 row, V1 if a slot is free, else 1.0.x, [mask](groups/mask.md).
- RUN-STREAM M1 scope: promoted 2026-11-19 (owner). Added to row 63a, [run](groups/run.md).
- DOC-DRIFT-ROUTES: promoted 2026-11-19 (owner). 1.0 row DOC-DRIFT-ROUTES, [run](groups/run.md).

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
