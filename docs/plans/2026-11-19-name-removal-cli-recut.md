# NAME-REMOVAL, CLI half: re-cut plan for 1.0 row 56

Status: plan

Repo and branch: CLI (decoy), branch `plan/name-removal-cli-recut`, based on CLI `origin/main` `ccc5540a`.
Engine reads are at engine `origin/main` `9e6547298`. Author: Decoy planner (Opus). Date: 2026-11-19.

Rules consulted: `/home/cam/dev-rules/README.md`, `00-universal.md`, `risk-and-exceptions.md`,
`development-loop.md` (PLAN), `proportionality.md`, `cross-cutting-concerns.md` (choke point plus
guard test), `api-and-compatibility.md`, `testing.md` (Test depth), `documentation.md`,
`workspace-and-vcs.md` (Commit messages); CLI `CODEMAP.md` ("Where Things Go"),
`docs/release/frozen-surfaces.md`, `docs/roadmap/working-rules.md` (engine releases and repins),
`docs/roadmap/decisions.md` (2026-11-05 OQ-2, 2026-11-18 freeze rules); engine
`docs/compatibility-contract.md` section 1. Inputs: engine `plan/storm-removal` revision 3
(`e6a910bb3`, `docs/plans/2026-11-16-storm-removal.md`), platform `plan/storm-rename-recut`
(`dfe7cc6a`, head `55ff97d98`), engine `plan/freeze-batch` revision 3.2 (`cc90937ef`), vault
`10_Projects/decoy/V1-1.0-BUILD-STATE-2026-11-18.md` and `decisions-log.md`.

Risk: R1 for both slices. The work left is doc text, two code comments, the deletion of one
shrink-only baseline, an sdist exclude list and one test that reads the installed engine. No
command, flag, `--json` key, schema, exit code or reason code changes in the CLI. The engine
registry change that this row depends on (two tombstones removed) is already merged as R2 under the
owner's one-time exception (Q1 of 2026-11-16). Approver for the plan: the owner; plan review: one
round (R1, development loop "Proportion").

This plan spells the retired product name, because `docs/plans/` is a history root of the residual
sentry. The roadmap row text in section 17 does not.

## 0. Why a re-cut, and what it changes

Row 56 still reads as the 2026-11-05 cut: "CLI C0 vendors `storm_slice_measure.py`,
`storm_inventory.py`, `slices-cli.json` and drops the platform S2c dependency", after "R-c repin",
from platform `plan/storm-rename-recut` `dfe7cc6a`. That text is stale in three ways:

1. The 2026-11-16 engine plan (`plan/storm-removal` revision 3, Dennis GO after two rounds, owner Q1,
   Q2 and Q11 answered) replaced the platform cut for the engine and the CLI. It dropped the vendored
   scripts and `slices-cli.json` (section 3 of that plan: `git grep -c` measures 340 CLI lines
   directly; two vendored scripts would be larger than the edits they measure) and dropped every
   platform dependency (Q11 version B: no engine code for the parked platform). OQ-2 = B1 ("re-cut
   the CLI half; CLI V1 ships the new names", owner 2026-11-05) is met by that plan; this re-cut
   keeps it.
2. Most of the CLI half has merged: C1 (CLI #292, `7145ce97`), C1b (CLI #293, `49561320`), the
   diagram follow-up (CLI #294, `9c0251a1`) and C2 (CLI #304, `d1a33058`). The engine half, row 16,
   merged as engine #610 (`cdaa3746f`, 2026-11-16).
3. The dependency is not "R-c". It is the first engine release that carries engine #610. Engine
   0.27.0 (`a21ebf47b`, #608) was cut before #610; engine 0.28.0 is open as engine PR #698
   (`chore/release-0.28.0-r4`, `8672d0b84`), which contains #610. The CLI pins
   `decoy-engine==0.27.0` (`pyproject.toml` line 141).

What this re-cut plans is the remainder, split by its one real dependency:

- C3a (no engine dependency): clean the last 34 lines in 13 files, delete the `PENDING` ratchet so
  the residual sentry becomes absolute, keep the CLI history folders out of the sdist, and update the
  roadmap and QA rows. It can start today.
- C3b (after the CLI repin to engine 0.28.0 or later): one test that the installed engine's reason
  registry and installed files hold no old name, so the CLI's SARIF rule-code allowlist holds none.

The old plan's C3 was one slice gated on the repin. Splitting it lets the doc and sentry work land
now and leaves a 75-line slice waiting on the release. The two slices stay separate because they
ship at different times, not for size.

## 1. Frame

### 1.1 History of the name and its removal

- 2026-10-09: owner split the internal package by concern (detection, profiling, verification).
  Engine half merged as engine #329 (A-5) and #349 (close-out, v0.16.0 tombstones).
- 2026-10-29: owner reframe. The name is removed as a concept everywhere, including wire, config,
  route, CLI and doc surfaces (`docs/roadmap/row-detail.md:38`).
- 2026-11-01 to 2026-11-02: platform `plan/storm-rename-recut` (revision 5, 71 build handoffs, CLI
  slices C0 to C4 with vendored measuring scripts). Parked with the platform on 2026-11-05.
- 2026-11-05: owner OQ-2 = B1, OQ-3 = C1 (`docs/roadmap/decisions.md:57`).
- 2026-11-16: owner goal "no V1 user meets the word in the CLI or the engine"; engine
  `plan/storm-removal` revision 3 with Q1 (one-time registry exception), Q2 (release gate B-3 owns
  decoy-web) and Q11 (version B) answered.
- 2026-11-16 to 2026-11-18: engine #610, CLI #292, #293, #294, #304 merged.
- 2026-11-18: roadmap split. The old track moved to
  `docs/archive/2026-11-18-roadmap-before-split.md` (history); the group files were written without
  the name, which is why row 56 reads "an identifier kept in the pre-split snapshot".

Not related to this row: engine `plan/storm-containment-replan` (2026-10-30) is the phase-envelope
containment replan; only its branch name holds the token.

### 1.2 Are the new names settled?

Yes, for row 56. The replacement names were set by the 2026-11-16 plan (section 4.1 there) and have
shipped in C1 and C2. Section 4 of this plan lists them. C3a and C3b add no new public name: their
edits are prose in docs and comments.

The owner decision of 2026-11-12 that did not approve names is about F22: the four `UNCLASSIFIED`
publication reason codes of engine #489 (row 59). Those are not old names of this row and are not
renamed here. FREEZE-SURFACE item (7) asks that the public renames of the detection taxonomy split
and the F22 names be written down and that rows 16, 56 and 59 carry them; section 4 is row 56's part
of that list. Owner question 1 asks the owner to confirm it.

### 1.3 Measurement at CLI `ccc5540a`

Unit: tracked text lines that match the residual sentry's pattern (case-insensitive substring),
outside `HISTORY` (`tests/sentry/release/test_retired_name_residual.py`, `HISTORY` and
`HISTORY_ROOTS`).

| File | Lines | What the lines say |
|---|---|---|
| `CHANGELOG.md` | 13 | 12 under `[Unreleased]` (old verbs `storm analyze`, `storm integrity`, the 0.17.0 symbol map), 1 under `[0.1.0]` (line 755, "retired under storm-reframe-C") |
| `docs/roadmap/row-detail.md` | 4 | the 2026-10-29 reframe paragraph (lines 38 to 44) |
| `CODEMAP.md` | 3 | summary line 5, directory row line 29 (`storm` command), "Where Do I Find" line 96 (`src/decoy/cli/storm.py`, a deleted file) |
| `.tours/1-onboarding.tour` | 2 | a `storm` sub-app that no longer exists; a glossary pointer |
| `SECURITY.md` | 2 | line 3 product summary, line 33 "`decoy storm` writes JSON" |
| `docs/qa/cli-v1-checklist.md` | 2 | SCAN-13 (line 254), row index (line 578) |
| `docs/roadmap/branch-register.md` | 2 | lines 27 and 28, two stale branches |
| `docs/ci-contracts.md` | 1 | line 31, "saved STORM scan pairs" |
| `docs/roadmap/feature-checklist.md` | 1 | line 47, "A-5 is the STORM rename" |
| `docs/roadmap/post-1.0-plan.md` | 1 | line 74, open question 4 |
| `docs/roadmap/release-gates.md` | 1 | line 13, B-3 wording |
| `src/decoy/ci/adapters.py` | 1 | line 144, a section comment |
| `src/decoy/templates/__init__.py` | 1 | line 36, a comment |
| Total | 34 | 13 files; every one is a `PENDING` key with the same count |

The `PENDING` baseline `tests/sentry/baselines/retired-name-pending.json` holds exactly these 13
keys and counts, so the sentry is green on main. No src string literal, help text, test, schema or
generated doc carries the name (C1, C1b, C2 cleaned them; `tests/sentry/cli_text/_banned_text.py:88`
adds the pattern to `BANNED_USER_TEXT`).

Outside tracked files:

- The installed engine 0.27.0 still has the two route tombstones `route.run_storm` and
  `route.run_storm_requested` in `reasons.manifest()`. The CLI builds its SARIF rule-code allowlist
  from that manifest, tombstones included (`src/decoy/ci/rule_codes.py:202` to `:211`). They are
  never emitted and never printed; a V1 user does not read them. They leave with the repin.
- Remote refs: CLI `feat/storm-removal-c1`, `-c1b`, `-c2` (merged), `claude/eager-clarke-14deh1`
  (head now `7bdbdf97`; the register names `d697c6d8`); engine `feat/storm-removal-e1` (squash-merged
  as #610), `plan/storm-removal`, `plan/storm-containment-replan`, tags
  `archive/claude/storm-split-engine` and `archive/plan/a5-storm-rename`. CLI `claude/storm-split-cli`
  (register row 28) is already gone from the remote. Ref names are not files, so no sentry sees
  them (owner question 3).
- decoy-web: owned by release gate B-3 (owner Q2, 2026-11-16). Not in this plan.
- Platform: parked; its own wave (platform plan) owns it. Nothing here waits on it.

### 1.4 Why this is 1.0

The 1.0 bar is function break, data loss or non-admin leak, plus the freeze rule of 2026-11-18:
work that would be a breaking change after 1.0 is done before it. None of the 34 lines breaks a
function, loses data or leaks a value. Row 56 is 1.0 under the freeze rule only: names are frozen at
1.0, and "renames after 1.0 are 2.0" (`docs/roadmap/post-1.0-plan.md`). After C1 and C2 no frozen
name holds the old name, so what is left protects the V1 notes, the shipped docs and the sentry, and
closes the row before REL-GATE G0.

## 2. Guarantee

After C3a merges:

1. No tracked or untracked-unignored file in the CLI repo, path or content, holds the name outside
   the eight `HISTORY` globs. There is no `PENDING` list and no way to add one without a registry
   change that `scripts/dev/ratchet_check.py` and `tests/sentry/test_baseline_registry.py` refuse.
2. A CLI sdist built from the repo holds no file under a `HISTORY_ROOTS` path, so no history file
   ships even if an sdist is published.
3. Behaviour is unchanged: same commands, flags, exit codes, `--json` shapes, `decoy-ci/v1` schema
   and outputs. Only docs and two comments change.

After C3b merges (on a CLI head that pins an engine release with #610):

4. The installed engine's `reasons.manifest()` has no entry whose `code`, `summary`, `owner` or
   `symbol` holds the name, so neither does `validation_codes()`; and no file the installed
   `decoy-engine` distribution lists holds the name in its path or text.

Non-goals: renaming verbs, flags or `--json` keys; dated history files; decoy-web (B-3); the parked
platform; the F22 reason codes; deleting remote refs (owner question 3).

## 3. Established solutions

Search run: the codebase first (both residual sentries, the ratchet registry, the 2026-11-16 plan and
the platform plan), then the general practice for keeping a retired term out of a code base and for
checking what a package installed.

- Forbidden-term check over the real artifact with a fixed allowlist of history roots: already built
  (CLI `tests/sentry/release/test_retired_name_residual.py`, engine
  `tests/sentry/test_no_residual_removed_surface.py`), following the Vale and alex term-list pattern
  the 2026-11-16 plan cited. Reused as is.
- Shrink-only migration list that ends in deletion: the CLI ratchet convention
  (`tests/sentry/_ratchet.py`, `scripts/dev/sentry_registry.toml`). C3a takes the last step the
  convention defines: count to zero, then delete the baseline and its registry row.
- Scanning what ships, not only the repo: engine E1 kept history out of its sdist and docs site;
  C3b checks the installed engine through `importlib.metadata.files`, the standard record of the
  files a wheel installed (the `RECORD` file of the installed-distribution format, PEP 376 and the
  PyPA "Recording installed projects" spec).
- Rejected: the platform plan's vendored `storm_inventory.py`, `storm_slice_measure.py` and
  `slices-cli.json` (row 56's old text). The remaining surface is 34 lines; `git grep -c` and the
  sentry's own count measure it.

Custom code that remains: about 25 lines for `engine_violations`, which reuses `hit_lines` and
`RETIRED_PATTERN` from the same module.

## 4. Old-name surface table (every surface that carried an old name)

Status column: where the name was removed, or which slice removes it. Ids are S-numbers.

| Id | Surface class | Old name or text | New name or text | Status |
|---|---|---|---|---|
| S1 | Command group | `decoy storm` (`analyze`, `integrity`, `test`, `scan` alias) | `decoy scan`; `decoy report integrity` | removed before C1 (CLI redesign S1 and S3, `CHANGELOG.md` `[Unreleased]`) |
| S2 | `explain` topic | `decoy explain storm` | `decoy explain scan`; the old topic is a usage error (`EXIT_USAGE`) with no alias | C1, CLI #292 |
| S3 | Flags | none carry the name today; the old `storm analyze --format`, `--layout` went with S1 | no flag | measured: no flag in `docs/cli-reference.md` or the command tree holds it |
| S4 | Help and Rich text | "STORM (Statistical Top-down Risk Mapping)", "Path to a STORM scan JSON", "JobStormReport", "Storm integrity" title, scan card footnote | "the scan", "saved scan JSON", "integrity report", "Post-scan integrity" | C1, CLI #292 |
| S5 | Run-time output and errors | "Scanning with STORM...", "STORM scan failed: {type}." | "Scanning...", "Scan failed: {type}." | C2, CLI #304 |
| S6 | Scaffolded YAML comments (config text a user keeps) | `# REVIEW: STORM detected X` | `# REVIEW: The scan found X` | C2, CLI #304 |
| S7 | Config keys | engine `run_storm` pipeline field | removed in engine 0.17.0; no replacement key | engine, before this row |
| S8 | JSON keys and wire tags | none in CLI `--json` shapes; engine wire tag `storm-post-mask/v1` and event `storm.scan` | engine verification names; the platform-only remainder is parked | engine residual sentry proves no engine file holds the name; CLI `--json` fixtures hold none |
| S9 | Schema text | `decoy-ci/v1` `DriftCheck` description | "Compare two saved scan JSON files with the `scan diff` categorizer." | C2, CLI #304 |
| S10 | Reason codes | engine tombstones `route.run_storm`, `route.run_storm_requested` | hard delete, no replacement code | engine #610; reach the CLI with the 0.28.0 repin; C3b proves it |
| S11 | Public Python symbols (engine) | `run_storm`, `StormProfile`, `run_storm_post_mask`, `storm_profiles_to_snapshot` | `profile_columns`, `ColumnProfile`, `run_post_mask`, `profiles_to_snapshot` | engine #329; CLI repinned at 0.17.0 |
| S12 | CLI module, symbol and test names | `decoy.ui.storm_animation`, `stormy_multistage`, `_StormyHandle`, `_storm_infer_format`, five `tests/e2e/test_storm_*.py` | `decoy.ui.scan_progress`, `scan_multistage`, `_StageHandle`, `_infer_format`, `tests/e2e/test_scan_*.py` | C1 and C1b, CLI #292, #293 |
| S13 | Docs a user reads | `SECURITY.md`, `docs/ci-contracts.md`, `CHANGELOG.md` (the V1 notes) | prose with "scan", "pre-scan", "post-scan integrity" | C3a |
| S14 | Contributor docs | `CODEMAP.md`, `.tours/1-onboarding.tour` | current command tree and module paths | C3a |
| S15 | Living roadmap and QA docs | `row-detail.md`, `branch-register.md`, `feature-checklist.md`, `post-1.0-plan.md`, `release-gates.md`, `docs/qa/cli-v1-checklist.md` | "the retired product name", row and branch pointers by sha | C3a |
| S16 | Code comments | `src/decoy/ci/adapters.py:144`, `src/decoy/templates/__init__.py:36` | "saved scans"; the history clause dropped | C3a |
| S17 | Packaged history | a CLI sdist would carry `docs/plans`, `docs/records` and the other history roots | excluded | C3a |
| S18 | Generated docs and diagrams | `docs/cli-reference.md`, `docs/diagrams/*.svg` | regenerated | C1, CLI #294 |
| S19 | Engine docs site and sdist | `docs/records/**` pages, history in the engine sdist | excluded | engine #610 |
| S20 | Public website | decoy-web `docs-src/` | release gate B-3 owns it | B-3 (owner Q2, 2026-11-16) |
| S21 | Remote refs | branch and tag names in section 1.3 | deleted or kept by owner call | owner question 3 |

## 5. Design

Design notes: no new structure. No module, abstraction or variant is added; one pure function joins
an existing test module. The one fact (the spelling) stays in `RETIRED_NAME`.

### 5.1 C3a: the last text, then an absolute sentry

1. Rewrite the 34 lines of 1.3. Rules: say what the thing does now ("the scan", "pre-scan
   detection", "post-scan integrity", "saved scan JSON"); where a line describes history, say "the
   retired product name" or drop the clause. Specific edits:
   - `CODEMAP.md:5` summary: "local validation, runs, scans, reports, templates, examples and
     terminal UX". `CODEMAP.md:29`: drop `storm` from the command list and list the current command
     modules from `src/decoy/__main__.py`. `CODEMAP.md:96`: the row points at `src/decoy/cli/scan.py`
     and `src/decoy/cli/scanning/` (the dead `storm.py` path goes). The map path sentry
     (`tests/sentry/layout/test_codemap_paths.py`) checks only "Where Things Go"; the builder checks
     line 96's new paths exist by hand.
   - `.tours/1-onboarding.tour`: the step that lists sub-apps names the current `add_typer` groups
     read from `src/decoy/__main__.py`; the glossary step drops the old pairing. JSON stays valid
     (`python -m json.tool`).
   - `SECURITY.md:3` drops the name from the product list; `SECURITY.md:33` says "`decoy demo` and
     `decoy scan` write JSON output ...".
   - `docs/ci-contracts.md:31`: "saved scan JSON pairs".
   - `CHANGELOG.md`: the twelve `[Unreleased]` lines name the old verbs as "the old scan group" and
     the 0.17.0 symbol map as "every engine call uses the renamed profiling and verification names
     (`profile_columns`, `verification.postmask.run_post_mask`)". Line 755 under `[0.1.0]` becomes
     "the legacy recommender was retired in the scan reframe". `[0.1.0]` was never published ("Not
     yet pushed to the real PyPI index", line 725), so this is a wording fix, not a rewrite of a
     public release note. One new `[Unreleased]` line: "The retired product name is gone from the
     CLI, its docs and its sdist."
   - `docs/roadmap/row-detail.md:38` to `:44`: one short paragraph, "Retired product name (owner
     2026-10-29, 2026-11-16). Decoy is a compiler pipeline with phase-bound scans: pre-scan,
     transform, post-scan. The old name is removed from every CLI and engine surface (rows 16 and
     56); history is in the archived roadmap snapshot."
   - `docs/roadmap/branch-register.md:27`, `:28`: row 28 is deleted (the branch is already gone from
     the remote). Row 27 keeps `claude/eager-clarke-14deh1`, drops the name from its reason ("stale
     rename branch, superseded by rows 16 and 56") and corrects its sha to the live head `7bdbdf97`.
   - `docs/roadmap/feature-checklist.md:47`: "A-5 is the retired-name removal (rows 16 and 56)".
   - `docs/roadmap/post-1.0-plan.md:74`: "Which public renames of the detection taxonomy split and
     the F22 names belong in Before 1.0 freeze? Owned by FREEZE-SURFACE item (7)."
   - `docs/roadmap/release-gates.md:13`: "B-3 Marketing-web currency: `docs-src/` off the retired
     product name and the old command surface".
   - `docs/qa/cli-v1-checklist.md:254`: SCAN-13 reads "Read every scan, report and help text for the
     retired product name"; result column: "Pinned by the residual sentry, the banned-text registry
     and the runtime-output test (row 56)". Line 578: "Retired product name, CLI half".
   - `src/decoy/ci/adapters.py:144`: "Drift (saved scans) over the existing categorizer".
     `src/decoy/templates/__init__.py:36`: the comment keeps its reason and drops the history id:
     "V1 `mode: graph` was retired; the V2 graph builder UI emits a `version: 2` PipelineConfig ..."
     (comments carry reasons, not task history: `documentation.md`).
2. Delete the ratchet in one commit with its carriers:
   - `tests/sentry/baselines/retired-name-pending.json` (deleted),
   - its block in `scripts/dev/sentry_registry.toml` (line 157),
   - its entry in `tests/sentry/test_baseline_registry.py:69`,
   - in the sentry: `_pending()`, the `load_allowlist` import, the `pending` parameter of
     `violations` and the two `PENDING` branches; the module docstring states the sentry is absolute
     and that a new exception needs a `HISTORY_ROOTS` change (a stop line). The test
     `test_no_retired_name_outside_history_and_pending` is renamed
     `test_no_retired_name_outside_history`.
   - `test_pending_count_must_match_in_both_directions` goes with the mechanism it tested. That is a
     test deletion, a full-suite escalation trigger (section 13).
3. CLI sdist: `[tool.hatch.build.targets.sdist] exclude` (`pyproject.toml` line 253) gains one entry
   per `HISTORY_ROOTS` entry: `docs/plans`, `docs/records`, `docs/archive`, `docs/superpowers/plans`,
   `docs/overnight-dev/findings`, `docs/handoffs`, `docs/roadmap/decisions.md`,
   `docs/RECENTLY-SHIPPED.md`. Each entry is the root path itself, so the list is derived from
   `HISTORY_ROOTS` one to one (trailing `/` dropped).
4. AT-C8 in the sentry module checks item 3 (section 8).
5. Roadmap rows: row 16 state becomes "MERGED (engine #610, `cdaa3746`); ships in engine 0.28.0";
   row 56 takes the section 17 text with state "PARTLY MERGED".

### 5.2 C3b: the installed engine

One pure function and two tests in the sentry module:

- `engine_violations(entries, files)`: `entries` is `reasons.manifest()["entries"]`; for each entry,
  each of `code`, `summary`, `owner`, `symbol` that matches `RETIRED_PATTERN` is a violation.
  `files` is a mapping of installed path to bytes from `importlib.metadata.files("decoy-engine")`;
  each path and each text file is checked with the existing `hit_lines` (binary files get the path
  check; a non-binary file that does not decode is a violation, as in the repo scan).
- The live test fails, not skips, when `files("decoy-engine")` returns `None` or a list without
  `decoy_engine/__init__.py`, and when the manifest has fewer entries than a floor the builder reads
  from engine 0.28.0 at build time and writes into the test with that version.
- `validation_codes()` (`src/decoy/ci/rule_codes.py:256`) holds no code that matches the pattern.

No production code changes. `rule_code` (`src/decoy/ci/rule_codes.py:272`) already maps any
non-allowlisted code to `UNKNOWN_CODE`, so a finding that names a removed code after the repin is
reported as `unknown_code`, never echoed.

## 6. Behaviour

| Surface | Before (main `ccc5540a`) | After C3a | After C3b and the repin |
|---|---|---|---|
| `git grep -i` outside history | 34 lines, 13 files | 0 | 0 |
| Residual sentry | passes with a 13-key `PENDING` | absolute; no `PENDING` | absolute, plus the engine check |
| CLI sdist members | include `docs/plans/**` and the other history roots | none under a history root | same |
| SARIF allowlist (`validation_codes()`) | includes the two tombstones (engine 0.27.0) | same (repin not done) | excludes them |
| SARIF `ruleId` for a finding naming a removed code | the code itself | same | `unknown_code` |
| Commands, flags, exit codes, `--json`, `decoy-ci/v1` | unchanged | unchanged | unchanged |

## 7. Failure modes

### 7.1 Class table

| # | Class | Structure that closes it | Proof | Mutation that turns it red |
|---|---|---|---|---|
| 1 | Value-bearing output | sentry messages name a path and a count only, never the matched line, so a seeded file's content never reaches CI logs; C3b adds no CLI output; `rule_code` maps a removed code to the fixed `UNKNOWN_CODE` | AT-S2 message-shape case; existing `tests/sentry/test_ci_output_isolation.py` | make `violations` append the matched line text (the message-shape case fails) |
| 2 | Cleanup missing on an exit path | N/A: C3a and C3b add no file, lock, process or temp state; the sdist evidence build runs in a temp dir on the VM or Mac | the gate's sdist listing (AT-C8b) | none applies |
| 3 | State and concurrency | the `PENDING` baseline, its registry row, the baseline-registry map and the sentry import are four carriers of one state; C3a removes all four in one commit | AT-S2c; `tests/sentry/test_baseline_registry.py` | delete the baseline file but keep its `sentry_registry.toml` row (registry test red) |
| 4 | Route parity and silent fallback | the engine scan fails when `files("decoy-engine")` is `None` or misses `decoy_engine/__init__.py` (an editable or broken install), instead of passing on an empty set | AT-C4 floor cases | return an empty mapping when `files()` is `None` (AT-C4 floor case red) |
| 5 | Referential integrity | every `HISTORY_ROOTS` entry has a matching sdist exclude; every `HISTORY` glob sits under a root; the branch register names live refs only | AT-C8; `test_history_globs_sit_under_the_fixed_roots` | drop `docs/handoffs` from the sdist exclude (AT-C8 red) |
| 6 | Untrusted producer | installed engine files are read as untrusted bytes: binary by the NUL rule, non-UTF-8 text is a violation, never a skip | AT-C4s seed with a Latin-1 file | wrap the decode in `try/except: continue` (the Latin-1 seed passes, so its seed test fails) |
| 7 | Check then use (TOCTOU) | N/A: read-only scans in one process; nothing checked is later used for a decision | none needed | none applies |
| 8 | Weak tests and overclaimed evidence | the sentry scans the real repo artifact; the engine check scans the installed distribution, not the engine repo; seeds per surface stay; floors stop a pass on an empty set | AT-S2 seeds, AT-C4s seeds and AT-C4 floors | narrow the repo scan to `src/` (the doc-page seed passes, so its seed test fails) |
| 9 | Behaviour-preserving refactor drift | edits are prose and two comments; no executable line moves | `tests/unit/test_cli_surface.py`, `tests/e2e/release_freeze/test_json_shapes.py`, `tests/unit/test_ci_manifest.py` green at T1 | turn the `adapters.py:144` comment edit into a code edit (T1 tests on `decoy.ci` go red) |
| 10 | Frozen contract drift | no CLI frozen surface changes; the SARIF allowlist shrinks only through the engine registry exception already approved (owner Q1, 2026-11-16); `decoy-ci/v1` untouched | AT-C4; frozen-surface map sentry `tests/sentry/release/test_frozen_surface_map.py` | add a manifest seed entry whose `summary` holds the name (AT-C4s seed red) |

### 7.2 Enumerations

#### Exit paths

- Sentry failure: `test_no_retired_name_outside_history` fails with `path: n line(s)` lines; the CI
  exit is pytest's.
- `decoy explain <old topic>`: already a usage error through `EXIT_USAGE`
  (`src/decoy/cli/explain.py:23`); C3a and C3b do not touch it.
- SARIF rule code naming a removed tombstone after the repin: `rule_code` returns `UNKNOWN_CODE`
  (`src/decoy/ci/rule_codes.py:272`); the `decoy ci` exit code is unchanged.

#### Routes

- CLI command routing: no command is added, removed or rerouted; `docs/cli-reference.md` is not
  regenerated by this row (no help text changes).
- Engine routing deciders: no change; the two removed codes were never emitted by any engine route
  (engine plan revision 3, section 6.2).

#### FK shapes

N/A: no key, foreign key, vault, relationship or subset code is touched; the change is prose, a
baseline deletion, an sdist exclude list and a read-only test.

#### Fields

- `reasons.manifest()["entries"][*]` fields `code`, `summary`, `owner`, `symbol`: read by C3b, not
  written.
- `[tool.hatch.build.targets.sdist].exclude` in `pyproject.toml`: eight entries added.
- `scripts/dev/sentry_registry.toml` `[[sentry]]` with `id = "retired-name-pending"`: removed, with
  its map entry at `tests/sentry/test_baseline_registry.py:69`.

#### Output surfaces

- SARIF `ruleId`: two fewer allowlisted codes after the repin (`src/decoy/ci/rule_codes.py:202`).
- Docs a user reads: `SECURITY.md:33`, `docs/ci-contracts.md:31`, `CHANGELOG.md` `[Unreleased]`
  (the V1 release notes).
- Contributor docs: `CODEMAP.md:96`, `.tours/1-onboarding.tour`.
- The CLI sdist member list.

## 8. Acceptance tests, red first

Each AT names the mutation that must turn it red. "Red on base" is against CLI `ccc5540a`.

| Id | Test | Red on base | Mutation | Slice | Place |
|---|---|---|---|---|---|
| AT-S2 | `violations(tracked_files())` is empty with no `PENDING` argument; seeds per surface stay; a message names a path and a count, never line text | yes: 34 lines in 13 files once `PENDING` is gone | restore "STORM/FORECAST" in `CODEMAP.md:5` | C3a | `tests/sentry/release/test_retired_name_residual.py` |
| AT-S2c | no baseline file with sentry id `retired-name-pending` exists, `scripts/dev/sentry_registry.toml` has no such row, and the module does not import `load_allowlist` | yes: the baseline exists | re-add the baseline with one key | C3a | same file |
| AT-C8 | every `HISTORY_ROOTS` entry, trailing `/` dropped, is in `[tool.hatch.build.targets.sdist].exclude` (read with `tomllib`), and `tests` stays excluded | yes: `exclude = ["tests"]` | drop `docs/handoffs` from the exclude | C3a | same file |
| AT-C8b | gate evidence, not a unit test: `uv build --sdist` in a temp dir on the VM or Mac; `tar -tzf` lists no member under a history root and no member path with the name; the sdist's text members hold no hit | yes | none; it checks the built artifact once at the C3a gate | C3a gate | build record |
| AT-C4 | `engine_violations(manifest_entries, installed_files)` is empty for the installed engine; floors: `files()` is not `None`, contains `decoy_engine/__init__.py`, the manifest has at least the recorded entry count; `validation_codes()` has no match | yes on engine 0.27.0 (the two tombstones and `reasons/route/_retired.py`) | pin the lock back to 0.27.0 (red); in code: return an empty mapping when `files()` is `None` | C3b | same file |
| AT-C4s | seeds for `engine_violations`: a manifest entry with the name in `code`, one in `summary`, one in `symbol`; an installed path holding it; a text file holding it; a Latin-1 file; `None` for `files()` | yes (the function does not exist) | skip the `summary` field (the summary seed passes, so its seed test fails) | C3b | same file |

Existing tests that change: `test_pending_count_must_match_in_both_directions` is deleted with the
`PENDING` mechanism (C3a); `tests/sentry/test_baseline_registry.py` loses one map entry (C3a). No
assertion is weakened: the sentry's allowed set shrinks from history plus 13 files to history only.
Already in place and unchanged: the banned-text registry (`_banned_text.py:88`) and the runtime-output
test `tests/sentry/cli_text/test_no_retired_name_in_output.py` (scan, report integrity, init, demo,
show schema).

## 9. Reuse inventory

| Need | Reused | From |
|---|---|---|
| repo scan, history globs, seeds, `hit_lines` | the residual sentry as is | `tests/sentry/release/test_retired_name_residual.py` |
| one spelling of the name | `RETIRED_NAME`, `RETIRED_PATTERN` | same file; `_banned_text.py:88` already imports it |
| baseline deletion rules | ratchet registry and its check | `scripts/dev/sentry_registry.toml`, `scripts/dev/ratchet_check.py`, `tests/sentry/test_baseline_registry.py` |
| what the engine installed | `importlib.metadata.files` | standard library |
| engine registry read | `reasons.manifest()`, `validation_codes()` | engine `decoy_engine.reasons`; `src/decoy/ci/rule_codes.py:256` |
| engine repin procedure | the engine repin checklist | `docs/roadmap/working-rules.md` item 3 |

## 10. Placement

| File | Change | Map line that places it | Beside |
|---|---|---|---|
| `tests/sentry/release/test_retired_name_residual.py` | edit: `PENDING` removed (C3a), AT-C8 (C3a), `engine_violations` and AT-C4 (C3b) | CODEMAP "Sentry test": release-gate sentries in `tests/sentry/release/` | `tests/sentry/release/test_frozen_surface_map.py` |
| `tests/sentry/baselines/retired-name-pending.json` | deleted | CODEMAP "Sentry test" (shrink-only baselines) | other baselines |
| `scripts/dev/sentry_registry.toml`, `tests/sentry/test_baseline_registry.py` | one block and one entry deleted | CODEMAP "Developer environment scripts"; "Sentry test" | other registry rows |
| `pyproject.toml` | sdist exclude entries | repo root | other build settings |
| docs in 1.3 | prose edits | CODEMAP "Roadmap, plans, records", "QA checklists and run templates", "CI integration" | in place |

No new file and no new module. No new public name. The sentry module grows from 245 lines to about
290 at the C3b head, under the 800-line module cap.

## 11. Frozen contracts touched

| Contract | Map row | Change | Proof |
|---|---|---|---|
| CLI command and flag set | `docs/release/frozen-surfaces.md` "Command and flag set" | none | `tests/unit/test_cli_surface.py` |
| CLI `--json` success shapes and error object | "`--json` success shapes", "`--json` error object" | none | `tests/e2e/release_freeze/test_json_shapes.py` |
| CI manifest `decoy-ci/v1` | "CI manifest" | none (C2 already changed the description only) | `tests/unit/test_ci_manifest.py` |
| Engine reason registry, as the CLI sees it | engine `docs/frozen-surfaces.md` "Reason registry" | two tombstones gone, through the repin, under the approved exception | AT-C4 |
| CLI engine pin | `pyproject.toml` line 141, `uv.lock` | the 0.28.0 repin PR (not a slice of this plan) | the repin checklist; AT-C4 runs after it |

Names freeze at 1.0. After C3a, the shipped command, flag, topic and `--json` names hold no old name,
so the freeze cannot lock one in. That is why row 56 must close before REL-GATE G0.

## 12. Size budget

Estimated changed lines (added plus deleted) from the measured hit lines at `ccc5540a` and the file
sizes.

| Slice | Docs | Code comments | Tests and baselines | Config | Total | Production files |
|---|---|---|---|---|---|---|
| C3a | about 90 (34 hit lines at about two changed lines each, plus the row-detail paragraph, the tour step and the roadmap rows) | 4 | about 110 (baseline file minus 60, sentry minus 25 and plus 15, AT-C8 25, registry block 5, map entry 1) | 10 (sdist exclude) | about 215 | 3 (`src/decoy/ci/adapters.py`, `src/decoy/templates/__init__.py`, `pyproject.toml`) |
| C3b | about 5 (row 56 closes) | 0 | about 70 (`engine_violations` 25, live test 20, seeds 25) | 0 | about 75 | 0 |

Stop past 400 changed lines or 5 production files in either slice.

## 13. Slices

| Slice | Repo | What | Risk | Depends on | Tests | Review |
|---|---|---|---|---|---|---|
| C3a | CLI | 5.1: the 34 lines, `PENDING` deleted, sdist exclude, AT-S2, AT-S2c, AT-C8, roadmap rows 16 and 56, QA row SCAN-13 | R1 | none | T0 per edit; T1 impact set plus the sentry set (`tests/sentry/release/`, `tests/sentry/cli_text/`, `tests/sentry/test_baseline_registry.py`); full suite on the merge head, because a test is deleted and a registered baseline goes (triggers "moves or deletes test files" and "shared fixtures or test configuration"); AT-C8b sdist build at the gate | Codex |
| C3b | CLI | 5.2: `engine_violations`, AT-C4, AT-C4s; row 56 closes | R1 | the CLI repin to the first engine release with engine #610 (0.28.0, engine PR #698) | T0, T1 plus the sentry set on the repinned head | Codex |

No tests run on the devbox: Mac first, then the VM pool (`~/bin/vm-run`).

Commits follow `workspace-and-vcs.md`: Conventional Commits subject of 72 characters or fewer,
final line `cam`, no other trailers. Example subjects: `docs: drop the retired name from the last
CLI docs`, `test(sentry): make the retired-name sentry absolute`, `test(sentry): check the installed
engine for the retired name`.

### 13.1 Dependencies and order

1. Engine row 16 (E1): MERGED, engine #610. Nothing left.
2. Engine release 0.28.0 (engine PR #698, open, contains #610), then the CLI repin to it, on the
   repin checklist, one repin open at a time (working rules item 3). The repin PR is not part of
   this plan. If 0.28.0 is cut without #610 by mistake, C3b waits for the next daily release.
3. C3a: no dependency. It may merge before or after the repin.
4. C3b: after the repin merges.
5. Freeze batch (engine `plan/freeze-batch` revision 3.2): no file overlap with C3a or C3b. Two
   interactions:
   - S7 writes a "Public renames before 1.0" table in engine `docs/compatibility-contract.md`
     section 1, and AT-S7d wants "each old name in the retired-name residual list" with the mutation
     "drop `run_storm`". Every old name of the taxonomy map contains the retired name, and the
     contract is not a history file in either residual sentry, so that table, as written, turns the
     engine sentry red, and the CLI sentry too if mirrored in a CLI doc. Owner question 2.
   - S2 (CLI) edits `src/decoy/cli/demo.py` and S4 edits `docs/roadmap/groups/health.md`; C3a
     touches neither.
6. FREEZE-SURFACE item (7): section 4 is row 56's list of public renames for it. C3a changes no
   name, so item (7) can be written before or after C3a.
7. REL-GATE (row 93) G0 on 2026-12-04: C3a and C3b merged before G0, so the frozen-surface map and
   the release smoke run on a tree with no old name.

## 14. Stop lines for builders

- Any change to `HISTORY` or `HISTORY_ROOTS`: stop and ask.
- Re-creating a `PENDING` list or any allowlist for the name: stop.
- A rewritten line that still needs the name to make sense: stop and ask (do not add a history
  exception).
- Any edit to a file under a `HISTORY` glob: not needed, do not.
- A sdist exclude that matches anything outside the eight history paths, or any change to the wheel
  target: stop.
- An executable line change in `src/`: out of scope, stop.
- In C3b: an AT-C4 hit on the repinned engine. Stop and report; the fix is in the engine, not a CLI
  exception.
- Either slice past 400 changed lines or 5 production files: stop and split.

## 15. Owner questions (recommended answer first)

1. Confirm the 1.0 name set for row 56. Recommended: yes, the names in section 4 (S2, S4, S5, S6,
   S9, S12) are final for 1.0, they are row 56's entry in the FREEZE-SURFACE item (7) list, and the
   F22 codes (not approved, 2026-11-12) stay with row 59 and item (7), outside row 56. The names are
   settled: they shipped in C1 and C2, and C3a adds none.
2. How does freeze batch S7 record the taxonomy renames without spelling the retired name in a
   living contract? Recommended: (a) the contract section 1 table lists the new names and points to
   the released engine `CHANGELOG.md` sections (0.17.0 and 0.28.0), which are history to the engine
   sentry, for the old ones; AT-S7d becomes "every pair of the taxonomy map has its new name in the
   table, and every old name matches `RETIRED_PATTERN`". Alternatives: (b) add the contract to the
   engine `HISTORY` (rejected: a living frozen contract would be exempt from the sentry, and a
   `HISTORY_ROOTS` change is a stop line); (c) spell old names with a placeholder such as `{n}`, as
   the deleted CLI baseline did (rejected: the published contract would carry an encoding nobody
   reads). The freeze-batch plan makes the change in its next revision; the owner answer unblocks it.
3. Delete the remote refs that hold the name or the stale rename. Recommended: yes, after C3a
   merges, delete CLI `feat/storm-removal-c1`, `feat/storm-removal-c1b`, `feat/storm-removal-c2` (all
   merged) and `claude/eager-clarke-14deh1` (stale; its head moved from `d697c6d8` to `7bdbdf97`, so
   look at it first), and engine `feat/storm-removal-e1` (squash-merged as #610). Keep engine
   `plan/storm-removal`, `plan/storm-containment-replan` and the two `archive/` tags until 1.0 ships,
   then decide with the general branch cleanup. Deleting a remote branch is an owner call.

## 16. Pre-mortem

- Engine 0.28.0 slips or is re-cut without #610. C3b waits; C3a is not blocked. Track on row 56.
- Another branch adds the name to a living doc while C3a is open. Before C3a merges, the `PENDING`
  count mismatch fails it; after, the absolute sentry fails it at T1.
- A builder adds a history row for a hard-to-reword line. Stop line; reword instead.
- `importlib.metadata.files` returns `None` on the CI install (an editable engine). AT-C4 fails
  loudly by design; CI installs the engine from the lock, which records files.
- The sdist exclude also drops a file the build needs. The AT-C8b build at the gate catches it; the
  wheel target is untouched.
- Freeze batch S7 lands its table with old names before owner question 2 is answered. The engine
  sentry turns red on that PR, so it cannot merge silently; the answer settles the form.
- The tour JSON breaks after the edit. `python -m json.tool .tours/1-onboarding.tour` in C3a's
  self-check.

## 17. Roadmap row text (C3a writes it; it must not spell the name)

- Row 16: "NAME-REMOVAL E1 (engine part), registry 1.7.0 | engine | MERGED (engine #610, `cdaa3746`,
  2026-11-16); ships in engine 0.28.0 | engine plan `e6a910bb` (revision 3) | none".
- Row 56: "NAME-REMOVAL, CLI half: retired product name out of every CLI surface. Re-cut 2026-11-19:
  no vendored scripts and no platform dependency (owner OQ-2 = B1 kept). C1, C1b, C2 MERGED (CLI #292,
  #293, #294, #304). Left: C3a (last docs and comments, sentry absolute, sdist history exclude) and
  C3b (installed-engine check) | CLI | PARTLY MERGED | plan `C:plan/name-removal-cli-recut` | C3a none;
  C3b the CLI repin to engine 0.28.0 (engine PR #698)".

## 18. Verification status

Planning only. Measured with `git grep -i` and `git show` at CLI `ccc5540a`, engine `9e6547298`,
engine `chore/release-0.28.0-r4` `8672d0b84` (ancestry of `cdaa3746f` checked), and `git ls-remote`
on both repos on 2026-11-19. No test run and no build. Sizes are estimates, not measured diffs.
