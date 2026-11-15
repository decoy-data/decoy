# V1 QA readiness map: engine QA sections against the roadmap

Status: record

Date: 2026-11-14. Inputs: engine `docs/qa/README.md` and `docs/qa/01` to `18` at engine main
`1926e90e` (18 sections, 225 checks); CLI `docs/ROADMAP.md` section 5.3 at CLI main `fe07336`.

Owner rule (2026-11-11, standing): QA runs only on a feature group that is V1 complete, meaning
every roadmap row it depends on is closed. A row counts as closed only when its State starts
with MERGED or DONE; DEFERRED rows (9, 55) are out of V1 by owner decision. The roadmap says
every row in section 5.3 ships in CLI 1.0, so Phase 2 and Phase 3 rows (groups H and I) count as
V1 dependencies.

## Result

No section is COMPLETE. Every one of the 18 sections depends on at least one open V1 row, so no
section was run (task step 2 does not apply). No checks were executed and no FAIL rows are
proposed.

The closest are section 16 (vault and unmask) and section 10 (expressions and `when:`), with
two or three open rows each.

## Mapping

A dependency is an open row whose build changes behaviour that the section's checks test. Release
and repin rows (18, 76, 77, 94) are left out: they ship code but do not change what a check
expects. Several dependency calls are judgment; the ones that decide a section's result are
marked OPEN in the notes below.

| Section | Checks | Depends on (open rows) | State |
|---|---|---|---|
| 01 Config and validation | 12 | 22 CONFIG-EXPLICIT (E2 slices), 24b QA-GATE, 24e CLI-QA1, 24zf DUP-FREEZE (one config loader, E2), 24zh DUP-DEST (CL2) | WAITING |
| 02 Sources and file I/O | 12 | 22 (SRC-01 to SRC-05), 59 F22 and 61 DELIV (SRC-11, SRC-12 transactional sink), 63a RUN-STREAM (SRC-10 auto-chunk), 64 CLI-CLOUD, 64b CLI-DB-SRC, 87 F02 (SFTP), 24zh | WAITING |
| 03 Pre-scan, profiling, detection | 12 | 27, 29, 30, 31, 32 (SCAN-MULTI and follow-ons), 32a SCAN-ML, 32c SCAN-ML-MD (SCAN-07, SCAN-08), 80 F15, 81 F16 (disguises in the engine, SCAN-10, SCAN-11) | WAITING |
| 04 Plan compile | 11 | 24b, 24e (`validate compile`), 24zf (seed derivations, E2), 68 F36 | WAITING |
| 05 Keys, determinism, namespaces | 13 | 24zf E2 (engine #582 open, one seed path), 24zb DATE-SHIFT-UNKEYED (KEY-09), 83 F13 adapters (KEY-07 provider schemes), 78 F10 and 79 F09 (`key_version`, rotation, KEY-13) | WAITING |
| 06 Mask core strategies | 16 | 24z FAKER-POOL-DISTINCT (MASK-08 to MASK-11), 24za ENGINE-DOCS-TRUTH (strategy catalog), 24zh (MASK-15 tokenize vault) | WAITING |
| 07 Mask dates and numbers | 12 | 24zb (DATE-01 to DATE-04 unkeyed `date_shift`), 24za (`format_error` docs for `date_shift` and `bucketize`) | WAITING |
| 08 Mask free text | 12 | 32a SCAN-ML (NER), 32c SCAN-ML-MD (default NER model, TEXT-04, TEXT-05) | WAITING |
| 09 Mask domain strategies | 14 | 24zf E2 (A1 per-group `joint_mask` seeds, DOM-04), 24p GEN-PROVIDERS (A9 identifier locale scope, DOM-13), 24za (catalog misses `group_key`, `grouped_series`) | WAITING |
| 10 Expressions and `when:` | 12 | 24y GEN-FORMULA-SEQ (`formula` reading a `sequence` column, V1 function break), 24n GEN-REL (per-parent `derived_aggregate`) | WAITING (OPEN, note 1) |
| 11 Relationships and subsetting | 13 | 63 SAMPLE (subset CLI half, REL-11 to REL-13), 63a RUN-STREAM (relationship jobs), 58 F25 (out-of-core scratch) | WAITING |
| 12 Generation | 14 | 24n, 24p, 24q GEN-TYPES, 24r GEN-INHERIT, 24s GEN-CATALOG, 24y, 24zf (A1 generate-mode draws) | WAITING |
| 13 Fit, fidelity, DP | 13 | 24zc CERT-PIN-CVES (certified runtime pins, FIT-12, FIT-13), 69 F35 quality contracts (FIT-10, FIT-11) | WAITING (OPEN, note 2) |
| 14 Casting, validators, quarantine | 13 | 22, 61 DELIV (quarantine delivery), 58 F25 (CAST-07 out-of-core), 63a, 68 F36 | WAITING |
| 15 Execution routes and native | 12 | 58 F25, 59 F22, 63a, 84 F24 (ROUTE-10 estimates), 88 F44 and 90 REL-PKG (ROUTE-12 managed bundle) | WAITING |
| 16 Vault and unmask | 11 | 79 F09 (authenticated, versioned vault header: changes what VAULT-08 and VAULT-10 expect), 61 DELIV (kept and orphan vault after a run that does not deliver), 24zh (CL2 open) | WAITING (OPEN, note 3) |
| 17 Security boundaries | 12 | 58 F25 (SEC-11 scratch), 83 F13 adapters (SEC-05 `vault://`), 72 F33, 24y (SEC-10 generate `formula`) | WAITING |
| 18 Evidence, reasons, compat | 11 | 62 RESULT (exit 6, run result), 66 F29 remainder, 24zf (one error shape), 17 WF-R and 16 STORM E1 (registry renames and tombstones, EVID-04) | WAITING |

## Notes

1. Section 10 (OPEN). The `when:`, `derived` and `derived_aggregate` checks have no open row
   behind them: 24zd (A10, NaT and `pd.NA` in derived) and 24k GEN-STRICT are merged. The
   section waits only because it also covers `formula`, and 24y is an open V1 function break in
   a generate `formula`. If the orchestrator rules that 24y belongs to section 12 alone and that
   24n's per-parent aggregate is generation scope, section 10 becomes COMPLETE.
2. Section 13 (OPEN). 24zc changes the certified runtime set, which decides whether a DP fit is
   admitted (FIT-12, FIT-13). Whether F35 changes the quality report and policy that FIT-10 and
   FIT-11 test is a reading of the F35 plan, not checked here.
3. Section 16 (OPEN). Row 11 (vault key floor and `simpleeval>=1.0.5`) reads NOT MERGED, but
   engine #511 merged on 2026-11-12 as `75b81efe`, which is on engine main, and main pins
   `simpleeval>=1.0.5`. The row's State text is stale and needs a correction by the
   orchestrator; this report treats the row as closed. Row 12 (B-6) is DONE. Row 79 F09 is the
   real blocker: an authenticated, versioned header is a format change to the file the
   VAULT-08 and VAULT-10 checks inspect, so running them now would be repeated after F09.
4. Engine QA open points that are not tied to a row (for example the stale `unmask.py`
   docstring on what unmask needs, and the missing old-vault fixture check in section 16) stay
   with the section until it is run.

## Proposed rows

None. No section was run, so there are no FAIL results to classify.
