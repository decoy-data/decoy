Status: plan (revision 1, 2026-11-20)

# QA-BETA: agent beta testing, a shared corpus and a mechanical oracle for the V1 QA pass

Owner: Cam. Author: Opus (plan author, CLI). Date: 2026-11-20. Roadmap row: QA-BETA in `docs/roadmap/groups/release.md` (added by slice S0, owner 2026-11-20).

Sources: owner request 2026-11-20 ("use subagents as beta testers ... a set of input files ... different input file types, different job and file sizes, different settings ... come back with specific issues and we can build QA remediation"; "we'll want a robust QA process to find issues in v1 before the users do ... set it up as needed so we're ready when QA is slotted to begin"). Existing QA: `docs/qa/cli-v1-checklist.md` (row 92a, 16 groups, 204 checks), `docs/qa/cli-v1-journey.md` (row 75), `docs/qa/cli-v1-run-template.md`, engine `E:docs/qa/` (18 sections, about 225 checks), `docs/records/2026-11-14-qa-readiness-map.md`.

Anchors: a path with no prefix is in this repository (decoy CLI); `E:` is decoy-engine. CLI `origin/main` `93ed40fb`; engine `origin/main` `bbb5c8337`.

Rules consulted: dev-rules `README.md` (routing), `00-universal.md`, `development-loop.md` (PLAN: guarantee, failure modes, acceptance tests first, placement, slices), `risk-and-exceptions.md`, `testing.md` (test depth, oracles, property tests), `verification.md` (claims need evidence), `delegation.md` (bounded subagent tasks, briefs), `security.md` and `config-secrets-and-supply-chain.md` (downloaded data is untrusted, no secrets in reports), `pre-release-audit.md`, `reuse-first.md`, `proportionality.md`, `documentation.md`, `autonomous-operation.md` (unattended agent runs).

## 1. Current state

The V1 QA pass is planned as a scripted checklist run, one feature group at a time, after every row in the group closes (owner rule 2026-11-11, standing). Three gaps remain:

1. Nothing tests the product the way a new user meets it: from the public docs, with their own data, without a script. The scripted checks test what we thought to write down.
2. There is no shared input corpus. The journey uses one two-table fixture (`tests/fixtures/qa_first_user/`), and the first-user records used ad hoc files. Formats, encodings, sizes and odd shapes are not covered in one place.
3. There is no mechanical oracle. A checklist check is judged by the tester reading output. An agent tester that says "this looks wrong" is weak evidence; past agent reports have claimed fixes and failures that were not real.

## 2. Guarantee and non-goals

Guarantee. When QA is slotted to begin, a tester can be started on any V1-complete feature group within one hour, and every finding that reaches the roadmap:

- names the command, the config with values removed, the corpus item, the platform and the versions;
- cites the public doc line that set the expectation, or names the invariant that failed;
- was reproduced from its repro script on a clean node by someone other than the tester;
- holds no cell value, no marker value and no secret.

Non-goals:

- No product code changes. QA-BETA builds test tooling, data and briefs. Remediation of findings is separate roadmap rows through the normal dev loop.
- No QA of an unfinished group. The owner rule stands; prep work may run the product only to test the harness, and anything it finds is filed against its group and held (section 6, F9).
- No load or 100M-row runs. Scale above 10M rows is extrapolated (owner decision, A-2).
- Not a replacement for the checklists or the journey. They stay the scripted floor; this adds exploration, data breadth and an oracle.

## 3. Established solutions

- **Exploratory testing with charters and personas** (Bach and Bolton's session-based test management; Hendrickson, "Explore It!"). A tester gets a mission, a time box and a debrief, not a script. Persona briefs (section 5.3) are charters.
- **Pairwise (all-pairs) combinatorial testing** (NIST combinatorial testing program; Kuhn et al.). Most configuration faults are triggered by one or two settings together, so covering every pair of setting values finds most of them in a few dozen runs instead of thousands. Tool: `allpairspy` (MIT), with constraints for combinations the docs refuse.
- **Metamorphic and invariant oracles** (Chen et al., "Metamorphic Testing"). When the exact right output is unknown, check relations that must hold: same input and key give the same output, foreign keys still join, row counts hold, no original value survives. Section 5.5.
- **Canary values for leak detection** (the journey's `jmark` markers; honeytoken practice). Every text cell carries a unique marker, so a leak is a substring search, not a judgement.
- **Docs as the oracle for user-facing behaviour** (doc-driven QA; the 2026-11 CLI doc audit). A tester who reads only the public docs finds every place where the docs and the product disagree.
- **Bug triage with a reproduction gate** (Mozilla and Chromium triage practice: no repro, no bug). Section 5.7.

## 4. Reuse inventory

| Need | Reuse | Where |
|---|---|---|
| Scripted checks per group | the CLI checklist and its run template | `docs/qa/cli-v1-checklist.md`, `docs/qa/cli-v1-run-template.md` |
| Engine checks | the engine QA sections | `E:docs/qa/` |
| End-to-end scripted path, marker convention | the CLI journey and its test | `docs/qa/cli-v1-journey.md`, `tests/e2e/first_user/journey/test_cli_journey.py` |
| Installing a clean bundle | the fresh-install smoke and release smoke | `docs/release/fresh-install-smoke.md`, `packaging_tools/smoke_install.py`, `tests/e2e/test_release_smoke.py` |
| Exit code meanings | the exit registry | `src/decoy/cli/exit_codes.py` |
| Error and CI JSON shapes | the versioned schemas | `docs/schemas/` |
| Running on nodes | `~/bin/vm-run`, node-watch, the Dell, Mac and GCP test nodes | local operations profile |
| Pairwise generation | `allpairspy` (MIT), QA-only requirements file, not a product dependency | `scripts/qa/requirements.txt` |
| Synthetic data | NumPy and the standard library only; not Faker, so the corpus is not built by the library the product uses | `scripts/qa/corpus/` |
| Public data | Synthea (Apache-2.0, already used by `decoy-synthea`), NYC TLC trip records, UCI Adult (CC BY 4.0), Chinook sample database (MIT) | corpus manifest, section 5.2 |

Nothing in this plan builds a second copy of a product mechanism. The harness calls the installed `decoy` binary only.

## 5. Behaviour

### 5.1 Four layers

| Layer | Who runs it | Input | Oracle | When |
|---|---|---|---|---|
| L1 Checklist pass | one Sonnet agent per checklist group | the group's checks, the corpus | the check's expected exit and output, plus invariants | as each group becomes V1 complete |
| L2 Doc walk | one Sonnet agent per public docs page set | every example in the public docs, run as written | the doc text, plus invariants | as each group becomes V1 complete, for that group's pages |
| L3 Persona beta testers | five Sonnet agents, one per persona | a charter, the public docs, the corpus | the docs and the invariants; the agent's judgement only for "confusing" findings | after the V1 build is complete (personas cross groups) |
| L4 Matrix runs | the harness, no agent | the pairwise settings matrix over the corpus | invariants only | after the V1 build is complete; a smoke subset runs in S4 to test the harness |

L4 is scripted on purpose: coverage is cheap and mechanical. Agents (L1 to L3) are used where judgement, docs reading and exploration pay.

Every tester works from the installed release bundle in a clean environment and reads only the public docs folder. Testers do not read `src/`, `tests/` or plans. The launcher (S3) gives each tester a sandbox folder holding the bundle, a copy of the public docs and a read-only link to the corpus; the triager checks each tester transcript for reads outside it (section 6, F3).

### 5.2 Corpus

One manifest, `docs/qa/corpus/manifest.toml`, lists every corpus item: id, origin (public URL or `generated`), license, SHA-256, size tier, format, shape tags and the marker column list. Data never enters git. `scripts/qa/corpus/fetch.py` downloads public items and `scripts/qa/corpus/generate.py` builds generated items, both into `~/decoy-qa-corpus/<id>/` on a node.

Formats: CSV (comma, semicolon, tab, quoted newlines, BOM, Latin-1 and UTF-16 encodings, CRLF), TSV, Parquet (plain, dictionary, nested types refused by the docs), fixed width with a layout file, DuckDB database (`--duckdb-source`), Postgres (a local container on the node), S3 and GCS buckets (the test buckets the owner allowed 2026-11-12).

Shapes: single table; parent and child; a three-level FK chain; a self-reference; a composite key; a cycle (the docs refuse it in V1); wide (200 columns); free text with names and emails inside; dates in five formats and bad dates; heavy nulls (90%); all-null and constant columns; duplicate keys; a header-only file; an empty file; a malformed file per format.

Size tiers: S 1k rows, M 100k, L 1M, XL 10M. XL runs only on the Dell or a GCP test node, never the devbox. Above XL is extrapolated from the S to XL timings (owner, A-2).

Markers. Every generated text cell holds `qamk` plus a unique number; every generated numeric PII column holds values from a recorded set; public items get a marker column added at fetch time and their PII columns' original values are hashed into a leak dictionary `~/decoy-qa-corpus/<id>/leak.sha256` (hashes only, so the dictionary itself holds no value).

Licenses. An item enters the manifest only with a license that allows internal testing. Nothing from the corpus is redistributed, committed or quoted in a record.

### 5.3 Personas (L3 charters)

Each charter states the persona, the mission, the time box (2 hours of agent time), the corpus items in scope, the node, and the debrief questions. Charters live in `docs/qa/briefs/`.

| Persona | Mission | Node |
|---|---|---|
| P1 Solo developer | install from the download page steps, run the demo, mask a mix of local files, change settings between runs, re-run, upgrade | Mac (macOS arm64), then Dell (Linux) |
| P2 Data engineer | DuckDB and Postgres sources, S3 and GCS, subsetting a three-level FK chain, chunked and native runs on L and XL items | Dell |
| P3 CI engineer | set Decoy up the way a company would in CI: pinned install, secrets from the environment, `decoy ci check`, exit codes as gates, evidence and result files kept as artifacts; write down every step a company would need | a GCP test node (Q2) |
| P4 Compliance reviewer | evidence records, `decoy report verify`, the vault and `decoy unmask` as admin and as non-admin, post-scan reports, what an auditor can and cannot see | Dell |
| P5 Careless user | wrong flags, wrong file types, missing secret, interrupted runs (Ctrl-C mid-write), full disk, read-only output folder, re-running into an existing output | Dell, Mac |

P3's notes become the draft of a "Running Decoy in CI" guide (owner rule: every built capability is expressed to customers), handed to REL-DOCS row 92 after triage.

### 5.4 Settings matrix (L4)

Parameters and values (from `docs/cli-reference.md`):

| Parameter | Values |
|---|---|
| mode | mask, generate |
| source | csv, tsv, parquet, fixed-width, duckdb |
| size tier | S, M, L (XL in a separate small set) |
| chunked | off, `--chunked` |
| native | default, `--native`, `--no-native` |
| threads | default, `--threads 1`, `--threads 4` |
| memory cap | none, `--max-memory` at a quarter of the item size |
| subset | config subset on, `--no-subset` |
| post-scan | off, `--post-validate`, `--post-validate-enforce` |
| evidence | off, `--evidence-out` |
| vault | off, on (one `hash` column with `vault: true`) |

Constraints remove combinations the docs refuse; each refused combination is instead run once as a refusal check that must exit with the documented code and a value-free message. `allpairspy` gives about 40 runs per platform for every value pair. The matrix file `docs/qa/matrix.toml` is the input; the generated run list is written per QA pass, not committed.

### 5.5 Invariants (the oracle)

`scripts/qa/invariants/` checks every run's outputs after the fact. A failed invariant is a finding with no judgement needed.

| Id | Invariant | How it is checked |
|---|---|---|
| I1 | No marker and no leak-dictionary value appears in any output surface (section 15.2.5), except detokenize and unmask output for an admin | substring search for `qamk`, hash lookup of every output cell of a PII column |
| I2 | Every child key in the output joins to a parent row, for every FK in the config | key set comparison per FK |
| I3 | Same input, config, key and settings give byte-identical outputs on a re-run; chunked and non-chunked, and native and pandas, give the same outputs where the docs say they do | SHA-256 per output file |
| I4 | Row counts per table match the input (mask), the config (generate) or the subset result the docs describe | count per table |
| I5 | Column names, order and types match the docs for the strategy | schema read per output |
| I6 | The exit code is one of `src/decoy/cli/exit_codes.py`; exit 3 (runtime) is always a finding; `--json` output parses against `docs/schemas/` | registry and schema check |
| I7 | Every refusal and error text holds no value: no marker, no leak-dictionary value | as I1, on stdout, stderr and logs |
| I8 | Peak memory stays under `--max-memory` when it is set; wall time is recorded for the job-time estimate | `/usr/bin/time -v` on Linux, `-l` on macOS |

### 5.6 Finding record

One file per finding, `findings/<pass>/<id>.toml` in the QA pass folder on the node, with these fields (section 15.2.4): `id`, `layer`, `persona`, `group`, `platform`, `cli_version`, `engine_version`, `bundle_digest`, `corpus_item`, `command`, `config` (values removed), `expected` (doc path and line, or invariant id), `actual`, `exit`, `repro` (path to a script that re-runs it), `proposed_tier` (V1 or V2-LOG with the V1-bar reason), `confusing` (true when the finding is "the docs or messages confused me", not a failure).

`scripts/qa/findings.py write` refuses a record whose text matches a marker or a leak-dictionary hash (I1 applied to our own reports).

### 5.7 Triage

1. **Collect.** The triager (one Opus agent per pass) reads all finding records of the pass.
2. **Dedupe.** Group findings with the same root cause; keep the clearest repro.
3. **Reproduce.** Run each repro script on a clean node, not the tester's. No repro: closed as not reproduced, kept in the record.
4. **Classify** by the V1 bar (only a function break, data loss, a non-admin leak, or a copy of a central mechanism blocks V1; everything else V2-LOG). Doc-only mismatches go to REL-DOCS row 92 or the docs-truth row.
5. **Class check.** If two or more findings share a class, propose a sentry or choke point, not one patch per finding (owner rule: best practice becomes a sentry).
6. **File.** Each V1 finding becomes a roadmap row in its group file, citing the record. V2-LOG items go to the V2 log.
7. **Record.** The pass record `docs/records/YYYY-MM-DD-qa-beta-<layer>-<group>.md` lists every finding with its triage result, values removed.

Remediation follows the owner rule: after the group's QA pass, through the normal dev loop.

### 5.8 Capacity and nodes

Testers count against the builder cap (6 builders and 2 reviewers). One QA pass runs at most 4 testers at once, leaving 2 builder slots for remediation. Tester agents are Sonnet; the triager is Opus. XL runs use the Dell first, then the GCP test nodes (local first). macOS runs use the Mac. Windows cells wait for rows 89 and 6, as in the checklist.

## 6. Failure modes

| Id | Failure | Handling |
|---|---|---|
| F1 | An agent reports a failure that is not real | no finding reaches the roadmap without a repro on a clean node (5.7 step 3) |
| F2 | An agent pastes a cell value into a finding or record | `findings.py write` refuses it (AT-7); the triager re-runs the I1 search over the pass folder before the record is committed |
| F3 | A tester reads source or tests and stops behaving like a user | sandbox folder holds only bundle, docs and corpus; the triager scans the transcript for paths outside it; findings from such a session are re-run by a fresh tester |
| F4 | A corpus download is tampered with or changed | SHA-256 checked against the manifest after download into a temp folder, then renamed; mismatch refuses (AT-8); downloads are read only as data, with `python -I` |
| F5 | A large run exhausts a node | XL only on the Dell or GCP; the harness sets a per-run timeout and records a stall as a finding of type `stall`; the existing test stall guard and node-watch stay on |
| F6 | The matrix misses a pair because a constraint removed it | the generator reports every removed pair; each removed pair has a refusal check instead (AT-6) |
| F7 | An invariant check has a bug and passes everything | every checker has a planted-defect test (AT-2 to AT-5) and a mutation (section 8) |
| F8 | Findings pile up with no owner | the triager files each V1 finding as a roadmap row in the same pass; the board shows the pass with its open count |
| F9 | Prep work QAs an unfinished group | S4 runs only the harness smoke on the demo template and one closed group if any; anything found is filed against its group and held until that group's pass |
| F10 | Agent time runs over the budget | each charter has a time box; a pass stops at 4 concurrent testers; usage is checked each tick |
| F11 | Public data license does not allow the use | an item without a recorded license that allows internal testing is refused by `fetch.py` (AT-8) |

## 7. Acceptance tests (red first)

Tests live in `tests/unit/qa/` and run in the normal suite (they test the tooling, not the product).

| Id | Test | Red on main because |
|---|---|---|
| AT-1 | `generate.py` with the same seed writes byte-identical files; every text cell of every generated table holds a `qamk` marker; every FK column joins | `scripts/qa/corpus/generate.py` does not exist |
| AT-2 | The I1 leak checker flags a planted marker in each output surface (CSV, Parquet, stdout JSON, stderr, a log file, an evidence file) and passes the same files without it | no checker |
| AT-3 | The I2 FK checker flags one orphan child row and passes a clean pair, for single, chain, self-reference and composite keys | no checker |
| AT-4 | The I3 checker flags one changed byte between two runs and passes identical runs | no checker |
| AT-5 | The I6 checker flags exit 3, flags an exit not in the registry, flags `--json` output that fails its schema, and passes a registry exit with valid JSON | no checker |
| AT-6 | The pairwise generator covers every value pair not removed by a constraint (property test over random parameter sets), and lists every removed pair as a refusal check | no generator |
| AT-7 | `findings.py write` refuses a record holding a marker or a value whose hash is in the leak dictionary, and writes a clean record with every field of 5.6 | no writer |
| AT-8 | `fetch.py` refuses an item whose SHA-256 differs, an item with no license, and an item whose license is not on the allowed list; a good item lands only after its hash checks | no fetcher |
| AT-9 | A finding's repro script re-runs its command in a fresh `DECOY_HOME` and returns the recorded exit | no repro tooling |
| AT-10 | Every persona charter and the checklist and doc-walk briefs carry the required fields (mission, time box, corpus items, node, debrief questions, sandbox rule, no-values rule) | no briefs; a structure test reads `docs/qa/briefs/` |

## 8. Mutations (gate set)

| Id | Mutation | Must turn red |
|---|---|---|
| M1 | I1 checker skips stderr | AT-2 |
| M2 | I2 checker ignores composite keys | AT-3 |
| M3 | I3 checker compares file sizes instead of hashes | AT-4 |
| M4 | I6 checker treats exit 3 as a pass | AT-5 |
| M5 | pairwise generator drops the last parameter | AT-6 |
| M6 | `findings.py write` skips the leak-dictionary lookup | AT-7 |
| M7 | `fetch.py` renames before checking the hash | AT-8 |
| M8 | `generate.py` seeds from time | AT-1 |

## 9. Placement (against `CODEMAP.md`)

| Path | Contents | CODEMAP row |
|---|---|---|
| `docs/qa/beta-program.md` | the method (sections 5.1 to 5.8 as a current doc) | "QA checklists and run templates", `docs/qa/` (extend the row) |
| `docs/qa/briefs/*.md` | five persona charters, the checklist-pass brief, the doc-walk brief, the triager brief | same row |
| `docs/qa/corpus/manifest.toml` | corpus manifest | same row |
| `docs/qa/matrix.toml` | settings matrix parameters and constraints | same row |
| `docs/qa/finding-template.toml` | the finding record fields | same row |
| `scripts/qa/corpus/{fetch,generate}.py` | corpus tools | new row "QA tooling (not shipped)", `scripts/qa/`, beside "Release scripts" |
| `scripts/qa/invariants/*.py` | I1 to I8 checkers, one module per invariant | same new row |
| `scripts/qa/{matrix,findings,launch,repro}.py` | pairwise run list, finding writer, tester sandbox launcher, repro runner | same new row |
| `scripts/qa/requirements.txt` | `allpairspy`, pinned; installed only on QA nodes | same new row |
| `tests/unit/qa/` | AT-1 to AT-10 | new row with the tooling |

Nothing goes under `src/`. `scripts/qa/` is not in the wheel (same as `scripts/release/`). No module over 400 lines.

## 10. Design notes

- **Why agents and a script both.** Agents find what nobody wrote down; the matrix finds what agents skip. The oracle keeps both honest.
- **Why our own generator, not Faker.** The product masks with Faker; data generated by the same library could hide a defect that depends on Faker's own patterns.
- **Why markers, not "looks masked".** A substring search is exact and cheap. Agents never decide whether a value leaked.
- **Why docs-only testers.** A tester who reads the code tests the code's intent, not the user's experience. Doc mismatches are real V1 findings (REL-DOCS).
- **Why triage reproduces.** Agent reports have been wrong before (memory: docs agent claimed fixes not in files; builders reported a passing ratchet that failed). One clean repro is the gate.

## 11. Owner questions

| Id | Question | Recommendation |
|---|---|---|
| Q1 | Add QA-BETA as a 1.0 row in the release group | Yes (owner 2026-11-20: "do a writeup ... let's add to QA methodology"). Answered. |
| Q2 | The CI persona needs a real CI system. Create a private sandbox repo in the `decoy-data` organization with one GitHub Actions workflow running on a self-hosted runner on a GCP test node? | Yes: it is the only way to see what a company sees. A new repo and a runner registration are owner calls. Fallback if no: run the same steps as a shell script on the node, which loses real Actions behaviour (secrets masking, artifacts, re-runs). |
| Q3 | Public data set: Synthea, NYC TLC trips, UCI Adult, Chinook | Yes; each license allows internal testing; nothing is redistributed. |
| Q4 | Spend | No new spend: XL runs fit the existing two GCP nodes and the Dell. |

## 12. Compatibility impact

None. No product surface changes. The tooling reads the exit registry and the schemas; it changes neither.

## 13. Slices

| Slice | Contents | Risk | Review |
|---|---|---|---|
| S0 | this plan merged; roadmap row QA-BETA in `docs/roadmap/groups/release.md`; `docs/qa/beta-program.md` (method only); pointer from `docs/qa/cli-v1-checklist.md`; CODEMAP rows | R1 docs | Codex |
| S1 | corpus: manifest, `generate.py`, `fetch.py`, leak dictionary; AT-1, AT-8; M7, M8 | R1 | Codex |
| S2 | harness: invariants I1 to I8, `matrix.py`, `matrix.toml`, `findings.py`, `repro.py`; AT-2 to AT-7, AT-9; M1 to M6 | R2 (leak checker is the guarantee) | Dennis then Codex |
| S3 | briefs and launcher: five charters, checklist-pass, doc-walk and triager briefs, finding template, `launch.py` sandbox; AT-10 | R1 | Codex |
| S4 | dry run: build the S and M corpus on the Dell and Mac, run the matrix smoke (about 10 runs on the demo template), run one charter for 30 minutes on the demo only, triage it end to end; record `docs/records/2026-MM-DD-qa-beta-dry-run.md`; findings held per F9 | R1 | Codex reads the record |

S1 to S3 can build in parallel after S0. S4 needs all three.

## 14. Done when

- S0 to S4 merged; the dry-run record shows one finding (planted, if the product gave none) going from tester to record to repro to triage result, with I1 clean over the whole pass folder.
- The corpus S, M and L tiers are built and hash-checked on the Dell and the Mac; XL on the Dell.
- The board shows QA-BETA closed and each checklist group's "ready for QA" state, so the first L1 pass can start the day a group closes.

## 15. Defect catalog and enumerations

### 15.1 Plan defect catalog classes

| Class | Name | Closing structure | Sentry or property test | Mutation |
|---|---|---|---|---|
| 1 | value leak | `findings.py write` is the only writer of finding records and refuses markers and leak-dictionary hits; the triager re-runs I1 over the pass folder | AT-7, and AT-2 for product outputs | M6, M1 |
| 2 | cleanup | each run uses a fresh `DECOY_HOME` and output folder under the pass folder, removed after its invariants run unless a finding keeps it | AT-9 checks a fresh home per repro | N/A: no product cleanup path changes; the harness tests cover their own temp use |
| 3 | state | no state shared between runs: per-run `DECOY_HOME`, per-run output folder, corpus read-only | AT-9 | N/A: the corpus is read-only, so there is no shared mutable state to mutate |
| 4 | route | the matrix covers every route the docs name (pandas, native, chunked, out-of-core under a memory cap) and I3 compares routes where the docs say they agree | AT-6 coverage property | M5 (generator drops a parameter) |
| 5 | referential | I2 checks every FK shape in the corpus | AT-3 | M2 (composite keys ignored) |
| 6 | untrusted input | downloaded data is untrusted: hash checked, own folder, read as data only with `python -I` | AT-8 | M7 (rename before the hash check) |
| 7 | TOCTOU (check-then-use) | `fetch.py` downloads to a temp file, checks the hash on that file, then renames it; the checked file is the used file | AT-8 | M7 (rename before the hash check) |
| 8 | weak tests | every invariant checker has a planted-defect test, so a checker that passes everything turns red | AT-2 to AT-5 | M1 to M4 |
| 9 | refactor | N/A: no product code is moved or rewritten; tooling is new code under `scripts/qa/` |  |  |
| 10 | frozen contracts | the tooling only reads frozen surfaces (exit registry, schemas); section 15.3 | AT-5 reads the live registry, so a registry change shows up as a test change, not a silent drift | N/A: QA-BETA adds no frozen surface |

### 15.2 Enumerations

#### 15.2.1 Exit paths

The harness and I6 classify every exit the CLI can give:

- `EXIT_OK` 0 (`src/decoy/cli/exit_codes.py:45`): pass when the docs expect success.
- `EXIT_USAGE` 1 (`src/decoy/cli/exit_codes.py:49`): pass only for a refusal the docs describe; otherwise a finding.
- `EXIT_WARNINGS` 2 (`src/decoy/cli/exit_codes.py:56`): pass when a documented warning code is present.
- `EXIT_RUNTIME` 3 (`src/decoy/cli/exit_codes.py:66`): always a finding.
- `EXIT_FINDINGS` 4 (`src/decoy/cli/exit_codes.py:74`): pass when the run used `--post-validate-enforce` or a gate and the report names findings.
- `EXIT_CAPACITY` 5 (`src/decoy/cli/exit_codes.py:82`): pass only under a memory cap or full-disk test with the documented message.
- `EXIT_PARTIAL` 6 (`src/decoy/cli/exit_codes.py:103`): pass only in the interrupted-delivery tests of P5.
- `decoy run` outcomes map through `RUN_EXIT_MAP` (`src/decoy/cli/exit_codes.py:135`); the cancelled outcome is checked in P5.
- Any other code, or a signal death: a finding.

#### 15.2.2 Routes

- pandas (default, and `--no-native`)
- native (`--native`, and default when the companion is present)
- chunked (`--chunked`)
- out-of-core (a `--max-memory` cap below the item size)
- subset on and off (`--no-subset`)
- installed bundle on Linux x86-64, macOS arm64; Windows after rows 89 and 6

#### 15.2.3 FK shapes

- single parent and child
- three-level chain
- self-reference
- composite key
- cycle (refused in V1 by owner decision; a refusal check)
- child with orphans in the input (the docs' orphan policy decides the expected output)

#### 15.2.4 Fields

Finding record fields (section 5.6):

- `id`, `layer`, `persona`, `group`
- `platform`, `cli_version`, `engine_version`, `bundle_digest`
- `corpus_item`, `command`, `config` (values removed)
- `expected` (doc path and line, or invariant id), `actual`, `exit`
- `repro`, `proposed_tier`, `confusing`

Corpus manifest fields: `id`, `origin`, `license`, `sha256`, `tier`, `format`, `shapes`, `marker_columns`.

#### 15.2.5 Output surfaces

Every surface I1 and I7 search:

- output data files (CSV, TSV, Parquet, fixed width, DuckDB target)
- stdout, including `--json` documents
- stderr
- log files under the project and `DECOY_HOME`
- run result files (`--result`)
- evidence manifests (`--evidence-out`)
- post-scan and integrity reports (`--integrity-out`)
- scan documents (`decoy scan --output`)
- vault files (searched for markers; hashed values are expected)
- notification payloads (`--notify` to a local sink)
- the finding records and pass records themselves

### 15.3 Frozen contracts

QA-BETA changes no frozen contract. It reads two: the exit registry (`src/decoy/cli/exit_codes.py`) and the versioned schemas (`docs/schemas/`). If either changes before a pass, the pass uses the new version; AT-5 reads the live registry, so a change shows up in the test, not as silent drift.

## 16. Pre-mortem

Assume the V1 QA pass found too little and users hit bugs in January. Likely causes and the guard for each:

- **Testers stayed on the happy path.** Guard: P5 careless-user charter, refusal checks for every constrained pair, and the malformed-file shapes in the corpus.
- **The corpus was too clean.** Guard: public data with real-world mess (Synthea, TLC), five date formats, encodings, heavy nulls, duplicates.
- **Findings were lost in triage.** Guard: every finding has a record and a triage result in the pass record; the board shows open counts.
- **Agents invented findings and the real ones were drowned out.** Guard: the repro gate; dedupe by root cause.
- **The oracle had a hole.** Guard: planted-defect tests and mutations for every checker; the class check in triage turns repeated findings into sentries.
- **QA started late.** Guard: S0 to S4 finish before the V1 build ends; L1 starts per group as groups close.
- **The CI story was never tried.** Guard: P3 on a real CI system (Q2), with its notes going to REL-DOCS.
