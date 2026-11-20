Status: plan (revision 2, 2026-11-20; Dennis r1 GO-WITH-FIXES remediated)

# QA-BETA: agent beta testing, a shared corpus and a mechanical oracle for the V1 QA pass

Owner: Cam. Author: Opus (plan author, CLI). Date: 2026-11-20. Roadmap row: QA-BETA in `docs/roadmap/groups/release.md` (added by slice S0, owner 2026-11-20).

Sources: owner request 2026-11-20 ("use subagents as beta testers ... a set of input files ... different input file types, different job and file sizes, different settings ... come back with specific issues and we can build QA remediation"; "we'll want a robust QA process to find issues in v1 before the users do ... set it up as needed so we're ready when QA is slotted to begin"). Existing QA: `docs/qa/cli-v1-checklist.md` (row 92a, 16 groups, 204 checks), `docs/qa/cli-v1-journey.md` (row 75), `docs/qa/cli-v1-run-template.md`, engine `E:docs/qa/` (18 sections, about 225 checks), `docs/records/2026-11-14-qa-readiness-map.md`.

Anchors: a path with no prefix is in this repository (decoy CLI); `E:` is decoy-engine. CLI `origin/main` `93ed40fb`; engine `origin/main` `a1058463e`.

Rules consulted: dev-rules `README.md` (routing), `00-universal.md`, `development-loop.md` (PLAN: guarantee, failure modes, acceptance tests first, placement, slices), `risk-and-exceptions.md`, `testing.md` (test depth, oracles, property tests), `verification.md` (claims need evidence), `delegation.md` (bounded subagent tasks, briefs), `security.md` and `config-secrets-and-supply-chain.md` (downloaded data is untrusted, no secrets in reports), `pre-release-audit.md`, `reuse-first.md`, `proportionality.md`, `documentation.md`, `autonomous-operation.md` (unattended agent runs), `catalogs/recurring-defects.md`.

Review history: Dennis r1 (GO-WITH-FIXES, 4 HIGH, 10 MEDIUM, 2 LOW) on revision 1 at `775efe04`. Every finding is closed in this revision; the map is in section 17.

## 1. Current state

The V1 QA pass is planned as a scripted checklist run, one feature group at a time, after every row in the group closes (owner rule 2026-11-11, standing). Three gaps remain:

1. Nothing tests the product the way a new user meets it: from the public docs, with their own data, without a script. The scripted checks test what we thought to write down.
2. There is no shared input corpus. The journey uses one two-table fixture (`tests/fixtures/qa_first_user/`), the checklist builds its own `qamark` data, and the first-user records used ad hoc files. Formats, encodings, sizes and odd shapes are not covered in one place.
3. There is no mechanical oracle shared by all QA. The checklist and the journey each carry their own leak sweep (`docs/qa/cli-v1-checklist.md:125`, `tests/e2e/first_user/journey/test_cli_journey.py:225`), and an agent tester that says "this looks wrong" is weak evidence; past agent reports have claimed fixes and failures that were not real.

## 2. Guarantee and non-goals

Guarantee. When QA is slotted to begin, a tester can be started on any V1-complete feature group within one hour (timed in the S3 dry run), and every finding that reaches the roadmap:

- names the command, the config with values removed, the corpus item, the platform and the versions;
- cites the public doc line that set the expectation, or names the invariant that failed;
- was reproduced from its repro script on a clean node by someone other than the tester;
- holds no cell value, no marker text and no secret.

Non-goals:

- No product code changes. QA-BETA builds test tooling, data and briefs. Remediation of findings is separate roadmap rows through the normal dev loop.
- No QA of an unfinished group. The owner rule stands; prep work may run the product only to test the harness, and anything it finds is filed against its group and held (section 6, F9).
- No runs above 1M rows. Scale above that is extrapolated (owner decision A-2), and `mask-big` (RUN-07, RUN-08) already covers large single runs.
- Not a replacement for the checklists or the journey. They stay the scripted floor; this adds exploration, data breadth and a shared oracle.

## 3. Established solutions

- **Exploratory testing with charters and personas** (Bach and Bolton's session-based test management; Hendrickson, "Explore It!"). A tester gets a mission, a time box and a debrief, not a script. Persona briefs (section 5.3) are charters.
- **Pairwise (all-pairs) combinatorial testing** (NIST combinatorial testing program; Kuhn et al.). Most configuration faults are triggered by one or two settings together, so covering every pair of setting values finds most of them in a few dozen runs instead of thousands. Tool: `allpairspy` (MIT), with constraints for combinations the docs refuse or ignore.
- **Metamorphic and invariant oracles** (Chen et al., "Metamorphic Testing"). When the exact right output is unknown, check relations that must hold: same input and key give the same output, foreign keys still join, rows are accounted for, no original value survives where the strategy replaces it. Section 5.5.
- **Canary values for leak detection** (the checklist's `qamark` markers and the journey's needles; honeytoken practice). A leak is a substring or same-row comparison, not a judgement.
- **Docs as the oracle for user-facing behaviour** (doc-driven QA; the 2026-11 CLI doc audit). A tester who reads only the public docs finds every place where the docs and the product disagree.
- **Bug triage with a reproduction gate** (Mozilla and Chromium triage practice: no repro, no bug). Section 5.7.

## 4. Reuse inventory

| Need | Reuse | Where |
|---|---|---|
| Scripted checks per group | the CLI checklist and its run template | `docs/qa/cli-v1-checklist.md`, `docs/qa/cli-v1-run-template.md` |
| Engine checks | the engine QA sections | `E:docs/qa/` |
| Marker convention and sweep rules | the checklist's `qamark` sweep (exit 1 pass, exit 0 finding unless passthrough, exit 2 not run) | `docs/qa/cli-v1-checklist.md:125` |
| Secret needles | the journey's needle list | `tests/e2e/first_user/journey/test_cli_journey.py:225` |
| External services | the checklist's services table (MinIO, fake-gcs-server, Postgres, SFTP, Vault and LocalStack containers) | `docs/qa/cli-v1-checklist.md:131` |
| Installing a clean bundle | the fresh-install smoke and release smoke | `docs/release/fresh-install-smoke.md`, `packaging_tools/smoke_install.py`, `tests/e2e/test_release_smoke.py` |
| Large single runs | `mask-big` checks | checklist RUN-07, RUN-08 |
| Exit code meanings | the exit registry and `RUN_EXIT_MAP` | `src/decoy/cli/exit_codes.py` |
| Error and CI JSON shapes | the versioned schemas | `docs/schemas/` |
| Running on nodes | `~/bin/vm-run`, node-watch, the Dell, Mac and GCP test nodes | local operations profile |
| Pairwise generation | `allpairspy` (MIT) in the dev dependency group | `pyproject.toml` |
| Synthetic data | NumPy and the standard library only; not Faker, so the corpus is not built by the library the product uses | `scripts/qa/corpus/` |
| Public data | Synthea (Apache-2.0, already used by `decoy-synthea`) and Chinook (MIT) | corpus manifest, section 5.2 |

One shared sweep. The checklist and the journey each have a leak sweep today. S1 builds one module, `scripts/qa/sweep.py`, keeps the checklist's `qamark` prefix and exit meanings, takes the journey's needle list, and adds the secret values as needles. The checklist's sweep step and the journey test then call it, so there is one sweep, not three. Nothing in this plan copies a product mechanism; the harness calls the installed `decoy` binary only.

## 5. Behaviour

### 5.1 Four layers

| Layer | Who runs it | Input | Oracle | When |
|---|---|---|---|---|
| L1 Checklist pass | one Sonnet agent per checklist group | the group's checks, the corpus | the check's expected exit and output, plus invariants | as each group becomes V1 complete |
| L2 Doc walk | one Sonnet agent per public docs page set | every example in the public docs, run as written | the doc text, plus invariants | as each group becomes V1 complete, for that group's pages |
| L3 Persona beta testers | five Sonnet agents, one per persona | a charter, the public docs, the corpus | the docs and the invariants; the agent's judgement only for "confusing" findings | after the V1 build is complete (personas cross groups) |
| L4 Matrix runs | the harness, no agent | the pairwise settings matrices over the corpus | invariants only | after the V1 build is complete; a smoke subset runs in S3 to test the harness |

L4 is scripted on purpose: coverage is cheap and mechanical. Agents (L1 to L3) are used where judgement, docs reading and exploration pay.

Command coverage. L4 covers `decoy run` only, so every other command has a named layer:

| Command | L1 | L2 | L3 persona |
|---|---|---|---|
| `run` (mask, generate, `--all`) | yes | yes | P1, P2, P3, P5 |
| `fit` (incl. `--fanout`), then generate, then `report fidelity` | yes | yes | P1 |
| `scan`, `scan fields`, `scan show`, `scan diff` | yes | yes | P2, P4 |
| `subset` | yes | yes | P2 |
| `report show`, `render`, `verify`, `fidelity`, `integrity`, `diff`, `vault` | yes | yes | P4 |
| `tokenize`, `detokenize`, `unmask` | yes | yes | P4 |
| `validate config`, `compile`, `preflight` | yes | yes | P3, P5 |
| `ci check` | yes | yes | P3 |
| `init`, `demo`, `explain`, `info`, `doctor`, `setup` | yes | yes | P1, P5 |
| `library path`, `schema`, `list`, `show`, `project` | yes | yes | P1 |
| `upgrade` | yes | yes | P1 |

Sandbox. Every tester works from the installed release bundle and reads only the public docs folder. The launcher (S3) starts each tester as its own OS user (Linux and macOS) whose home holds only the bundle, a copy of the public docs and a read-only corpus mount; repository checkouts on the node are not readable by that user. This prevents reads of `src/`, `tests/` and plans instead of detecting them afterwards. Briefs forbid printing cell values in any message.

### 5.2 Corpus

One manifest, `docs/qa/corpus/manifest.toml` (`schema_version = 1`), lists every corpus item: id, origin (public URL or `generated`), license, SHA-256, size tier, format, shape tags and the marker column list. Data never enters git. `scripts/qa/corpus/fetch.py` downloads public items and `scripts/qa/corpus/generate.py` builds generated items, both into `~/decoy-qa-corpus/<id>/` on a node.

Formats: CSV (comma, semicolon, tab, quoted newlines, BOM, Latin-1 and UTF-16 encodings, CRLF), TSV, Parquet (plain and dictionary-encoded), fixed width with a layout file, and a DuckDB database (`--duckdb-source`). Connector sources and targets (Postgres, S3, GCS, SFTP) use the checklist's local containers (`docs/qa/cli-v1-checklist.md:131`) and join the corpus only when their group closes; the checklist marks several as not built (DLV-08 to DLV-11).

Shapes: single table; parent and child; a three-level FK chain; a self-reference; a composite key; a cycle (the docs refuse it in V1); wide (200 columns); free text with names and emails inside; dates in five formats and bad dates; heavy nulls (90%); all-null and constant columns; duplicate keys; a header-only file; an empty file; a malformed file per format.

Size tiers: S 1k rows, M 100k, L 1M. L runs only on the Dell or a GCP test node, never the devbox. Above L is extrapolated from the S to L timings (owner, A-2).

Markers. Every generated text cell holds `qamark` plus a unique number (the checklist's prefix). Public items keep their data; the leak check for them is the same-row comparison in I1, which needs no marker. Each pass also writes a node-local needles file: every marker, plus the secrets the pass uses (mask secret, master key, vault key, webhook signing key, SMTP password). A per-pass salted hash set of input PII cell values is kept node-local for the finding writer (section 5.6); it never leaves the node.

Licenses. An item enters the manifest only with a license that allows internal testing. Nothing from the corpus is redistributed, committed or quoted in a record.

### 5.3 Personas (L3 charters)

Each charter states the persona, the mission, the time box (2 hours of agent time), the corpus items in scope, the node, and the debrief questions. Charters live in `docs/qa/briefs/`.

| Persona | Mission | Node |
|---|---|---|
| P1 Solo developer | install from the download page steps, run the demo, mask a mix of local files, change settings between runs, re-run, `fit` a table then generate from it and grade it with `report fidelity`, upgrade | Mac (macOS arm64), then Dell (Linux) |
| P2 Data engineer | DuckDB sources, subsetting a three-level FK chain, chunked and native runs on M and L items, scans of a new source; connector sources and targets once their group closes | Dell |
| P3 CI engineer | set Decoy up the way a company would in CI: pinned install, secrets from the environment, `decoy ci check`, exit codes as gates, evidence and result files kept as artifacts; write down every step a company would need | GitHub-hosted runner in a private sandbox repo (Q2) |
| P4 Compliance reviewer | evidence records, `decoy report verify`, the vault and `decoy unmask` with and without the vault file and mask secret, post-scan reports, what an auditor can and cannot see | Dell |
| P5 Careless user | wrong flags, wrong file types, missing secret, interrupted runs (Ctrl-C mid-write), full disk, read-only output folder, re-running into an existing output | Dell, Mac |

P3's notes become the draft of a "Running Decoy in CI" guide (owner rule: every built capability is expressed to customers), handed to REL-DOCS row 92 after triage.

### 5.4 Settings matrices (L4)

Two matrices, because generate has no file source. Parameters come from `docs/cli-reference.md` (run options at lines 105 to 129).

Mask matrix:

| Parameter | Values |
|---|---|
| strategy mix | hash only; fpe and date_shift; faker and categorical (with pool_size and categories); bucketize and truncate; text_redact on free text; tokenize with `vault: true`; passthrough mixed in |
| source | csv, tsv, parquet, fixed-width, duckdb |
| size tier | S, M, L |
| `--mask-secret` | absent, `env:` ref |
| chunked | off, `--chunked` |
| native | default, `--native`, `--no-native` |
| threads | default, `--threads 1`, `--threads 4` |
| memory budget | default, `--max-memory` at a quarter of the item size |
| subset | config subset on, `--no-subset`, no subset block |
| post-scan | off, `--post-validate`, `--post-validate-enforce` |
| evidence | off, `--evidence-out` |
| vault | off, `--vault` |
| output | default run folder, `--out-dir` |
| `--json` | off, on |

Generate matrix:

| Parameter | Values |
|---|---|
| key | none (seeded), `--master-key` with `--key-label` |
| rows | config size, `--rows 100` preview |
| tables | single, parent and child, three-level chain |
| output format | csv, parquet |
| native | default, `--no-native` (`--native` is refused up front) |
| evidence | off, `--evidence-out` |
| `--json` | off, on |

Constraints have three kinds, each citing its doc line in `docs/qa/matrix.toml`:

- **refused**: the run must exit with the documented code and a value-free reason. Examples: `--chunked` with `--vault`, with a subset block (even with `--no-subset`), with fixed-width, with `--post-validate`, or with a strategy that is not value-keyed; `--duckdb-source` with `--evidence-out`; `--native` on a generate config; an unkeyed `date_shift`; `--rows` with any flag on its refusal list.
- **ignored**: the run must succeed and its outputs must equal the run without the ignored flag (I3). Examples: `--max-memory` and `--threads` under `--chunked`.
- **refused after the run**: `--native` on a table with no compiled-kernel evidence (FK tables, passthrough/redact/truncate only) must refuse before any output is written.

`allpairspy` covers every value pair not removed by a constraint, about 60 mask runs and 15 generate runs per platform. The generated run list is written per QA pass, not committed.

### 5.5 Invariants (the oracle)

`scripts/qa/invariants/` checks every run's outputs after the fact. A failed invariant is a finding with no judgement needed.

| Id | Invariant | How it is checked |
|---|---|---|
| I1 | No original value survives where the column's strategy replaces it, and no needle (marker or secret) appears on any output surface (section 15.2.5) except the documented exceptions below | per column, by the config's strategy: value-replacing strategies (hash, fpe, faker, categorical, date_shift, bucketize, tokenize, redact) get an exact-cell check and a same-row check (output cell differs from the same row's input cell); `passthrough` is exempt; `truncate` may keep the documented prefix and nothing more; `text_redact` may keep the surrounding text but no detected entity; non-data surfaces get the needles sweep (`scripts/qa/sweep.py`) |
| I2 | Every child key in the output joins to a parent row, for every FK in the config | key set comparison per FK |
| I3 | Re-runs and route pairs give equal outputs exactly where the docs promise it | SHA-256 per output data file, ignoring run ids and timestamps in result and evidence files; pairs and their promises: re-run with `--mask-secret` (`docs/cli-reference.md:108`), `--chunked` vs plain for value-keyed strategies (`:109`), generate with `--master-key` across runs and machines (`:107`), a flag the docs say is ignored vs without it (`:111`, `:112`) |
| I4 | Every input row is accounted for | mask: input rows = output rows + quarantined rows per table; subset: output rows ≤ input rows and I2 holds; generate: rows per table match the config or the `--rows` ratio |
| I5 | Column names, order and types match the docs for the strategy | schema read per output |
| I6 | The exit code means what the registry says (section 15.2.1) | registry check, stderr classification for exit 1, `--json` parsed against `docs/schemas/` |
| I7 | Every refusal and error text holds no value | the needles sweep and the same-row check over stdout, stderr and logs |

Peak RSS and wall time are recorded per run (`/usr/bin/time -v` on Linux, `-l` on macOS) as metrics for the job-time estimate. They are not an invariant: `--max-memory` is a route budget, not an RSS ceiling (`docs/cli-reference.md:111`).

Leak findings cite the surface, the line or cell coordinates and the marker id. They never carry the text, so the finding writer can record them.

### 5.6 Finding record

One file per finding, `findings/<pass>/<id>.toml` in the QA pass folder on the node, with `schema_version = 1` and these fields (section 15.2.4): `id`, `layer`, `persona`, `group`, `platform`, `cli_version`, `engine_version`, `bundle_digest`, `corpus_item`, `command`, `config` (values removed), `expected` (doc path and line, or invariant id), `actual`, `exit`, `repro` (path to a script that re-runs it), `proposed_tier` (V1 or V2-LOG with the V1-bar reason), `confusing` (true when the finding is "the docs or messages confused me", not a failure).

`scripts/qa/findings.py write` refuses a record whose text contains a needle or any token whose salted hash is in the pass's input-value hash set. Patterns are matched with full-match semantics against tokens, not loose search (recurring-defect class 1).

### 5.7 Triage

1. **Collect.** The triager (one Opus agent per pass) reads all finding records and every tester hand-back of the pass.
2. **Sweep our own text.** The needles sweep and the hash-set check run over the pass folder and the tester hand-back text before anything leaves the node; a hit is redacted and logged as a process finding.
3. **Dedupe.** Group findings with the same root cause; keep the clearest repro.
4. **Reproduce.** Run each repro script on a clean node, not the tester's. No repro: closed as not reproduced, kept in the record.
5. **Classify** by the V1 bar (only a function break, data loss, a non-admin leak, or a copy of a central mechanism blocks V1; everything else V2-LOG). Doc-only mismatches go to REL-DOCS row 92 or the docs-truth row.
6. **Class check.** If two or more findings share a class, propose a sentry or choke point, not one patch per finding (owner rule: best practice becomes a sentry).
7. **File.** Each V1 finding becomes a roadmap row in its group file, citing the record. V2-LOG items go to the V2 log.
8. **Record.** The pass record `docs/records/YYYY-MM-DD-qa-beta-<layer>-<group>.md` lists every finding with its triage result, values removed.

Slack posts from a pass carry counts and row ids only.

Remediation follows the owner rule: after the group's QA pass, through the normal dev loop.

### 5.8 Capacity and nodes

Testers count against the builder cap (6 builders and 2 reviewers). One QA pass runs at most 4 testers at once, leaving 2 builder slots for remediation. Tester agents are Sonnet; the triager is Opus. L runs use the Dell first, then the GCP test nodes (local first). macOS runs use the Mac. Windows cells wait for rows 89 and 6, as in the checklist.

## 6. Failure modes

| Id | Failure | Handling |
|---|---|---|
| F1 | An agent reports a failure that is not real | no finding reaches the roadmap without a repro on a clean node (5.7 step 4) |
| F2 | An agent pastes a cell value into a finding, a hand-back or a record | `findings.py write` refuses it (AT-7); the triager sweeps the pass folder and hand-backs before anything leaves the node (5.7 step 2) |
| F3 | A tester reads source or tests and stops behaving like a user | the tester's OS user cannot read repository checkouts (5.1 sandbox); AT-10 checks the launcher's user has no read access to a planted checkout |
| F4 | A corpus download is tampered with or changed | SHA-256 checked on a temp file before rename; mismatch refuses (AT-8); downloads are read only as data, with `python -I` |
| F5 | A large run exhausts a node | L only on the Dell or GCP; the harness sets a per-run timeout and records a stall as a finding of type `stall`; the test stall guard and node-watch stay on |
| F6 | The matrix misses a pair because a constraint removed it | every removed pair is listed with its constraint kind and turns into a refusal check, an ignored-flag equality check, or a documented n/a (AT-6) |
| F7 | An invariant check has a bug and passes everything | every checker has a planted-defect test (AT-2 to AT-5); the leak checker and the finding writer also carry mutations (section 8) |
| F8 | Findings pile up with no owner | the triager files each V1 finding as a roadmap row in the same pass; the board shows the pass with its open count |
| F9 | Prep work QAs an unfinished group | the S3 dry run uses the demo template and one closed group if any; anything found is filed against its group and held until that group's pass |
| F10 | Agent time runs over the budget | each charter has a time box; a pass stops at 4 concurrent testers; usage is checked each tick |
| F11 | Public data license does not allow the use | an item without a recorded license on the allowed list is refused by `fetch.py` (AT-8) |
| F12 | A leak check flags documented behaviour (passthrough, truncate prefix, text_redact context) | I1 rules are per strategy (5.5); AT-2 has a pass case for each exception |
| F13 | An exit is misread (crash as refusal, Ctrl-C as unknown) | I6 classification table (15.2.1), pinned by AT-5 |

## 7. Acceptance tests (red first)

Tests live in `tests/unit/qa/` and run in the normal suite (they test the tooling, not the product). `allpairspy` joins the dev dependency group in S1, so AT-6 runs in CI without a skip.

| Id | Test | Red on main because |
|---|---|---|
| AT-1 | `generate.py` with the same seed writes byte-identical files; every text cell of every generated table holds a `qamark` marker; every FK column joins | `scripts/qa/corpus/generate.py` does not exist |
| AT-2 | The I1 checker flags a planted marker or same-row original in each output surface (CSV, Parquet, stdout JSON, stderr, a log file, an evidence file) and flags a planted secret needle; it passes a passthrough column, a documented truncate prefix and text_redact context, and an fpe value that is a different member of the input set | no checker |
| AT-3 | The I2 FK checker flags one orphan child row and passes a clean pair, for single, chain, self-reference and composite keys | no checker |
| AT-4 | The I3 checker flags one changed data byte between two runs, ignores a changed run id or timestamp in a result file, and passes identical runs | no checker |
| AT-5 | The I6 classifier: exit 1 with a traceback is a crash finding; exit 1 with a documented `error:` reason is a refusal; exit 2 on a Click usage error is a refusal; exit 3 is a finding; exit 6 is a finding; exit 130 after Ctrl-C is a pass; an exit not in the registry is a finding; `--json` that fails its schema is a finding | no classifier |
| AT-6 | The pairwise generator covers every value pair not removed by a constraint (property test over random parameter sets), and lists every removed pair with its kind and doc line | no generator |
| AT-7 | `findings.py write` refuses a record holding a needle or a token whose salted hash is in the input-value set, refuses partial-token tricks by full-match tokenising, and writes a clean record with every field of 5.6 | no writer |
| AT-8 | `fetch.py` refuses an item whose SHA-256 differs, an item with no license, and an item whose license is not on the allowed list; a good item lands only after its hash checks | no fetcher |
| AT-9 | A finding's repro script re-runs its command in a fresh `DECOY_HOME` and returns the recorded exit | no repro tooling |
| AT-10 | Every persona charter and the checklist and doc-walk briefs carry the required fields (mission, time box, corpus items, node, debrief questions, sandbox rule, no-values rule); the launcher's tester user cannot read a planted checkout | no briefs or launcher |
| AT-11 | The checklist's sweep step and the journey test call `scripts/qa/sweep.py`; no second sweep implementation remains | the sweeps are separate today |

## 8. Mutations (gate set)

Core only (owner 2026-11-10): the leak checker, the finding writer and the fetcher.

| Id | Mutation | Must turn red |
|---|---|---|
| M1 | I1 checker skips stderr | AT-2 |
| M2 | `findings.py write` skips the input-value hash lookup | AT-7 |
| M3 | `fetch.py` renames before checking the hash | AT-8 |

## 9. Placement (against `CODEMAP.md`)

| Path | Contents | CODEMAP row |
|---|---|---|
| `docs/qa/beta-program.md` | the method (sections 5.1 to 5.8 as a current doc) | "QA checklists and run templates", `docs/qa/` (extend the row) |
| `docs/qa/briefs/*.md` | five persona charters, the checklist-pass brief, the doc-walk brief, the triager brief | same row |
| `docs/qa/corpus/manifest.toml` | corpus manifest | same row |
| `docs/qa/matrix.toml` | the two matrices, constraints with kinds and doc lines | same row |
| `docs/qa/finding-template.toml` | the finding record fields | same row |
| `scripts/qa/sweep.py` | the one needles sweep, used by the checklist, the journey and QA-BETA | new row "QA tooling (not shipped)", `scripts/qa/`, beside "Release scripts" |
| `scripts/qa/corpus/{fetch,generate}.py` | corpus tools | same new row |
| `scripts/qa/invariants/*.py` | I1 to I7 checkers, one module per invariant | same new row |
| `scripts/qa/{matrix,findings,launch,repro}.py` | pairwise run lists, finding writer, tester launcher, repro runner | same new row |
| `tests/unit/qa/` | AT-1 to AT-11 | new row with the tooling |

Nothing goes under `src/`. `scripts/qa/` is not in the wheel (same as `scripts/release/`). No module over 400 lines.

## 10. Design notes

- **Why agents and a script both.** Agents find what nobody wrote down; the matrices find what agents skip. The oracle keeps both honest.
- **Why our own generator, not Faker.** The product masks with Faker; data generated by the same library could hide a defect that depends on Faker's own patterns.
- **Why per-strategy leak rules.** A blanket "no marker anywhere" fails on documented behaviour (passthrough, truncate, text_redact) and misses same-domain leaks (fpe); the strategy in the config says what may survive.
- **Why docs-only testers.** A tester who reads the code tests the code's intent, not the user's experience. Doc mismatches are real V1 findings (REL-DOCS).
- **Why triage reproduces.** Agent reports have been wrong before (a docs agent claimed fixes not in files; a builder reported a passing ratchet that failed). One clean repro is the gate.

## 11. Owner questions

| Id | Question | Recommendation |
|---|---|---|
| Q1 | Add QA-BETA as a 1.0 row in the release group | Yes (owner 2026-11-20: "do a writeup ... let's add to QA methodology"). Answered. |
| Q2 | The CI persona needs a real CI system. Create a private sandbox repo in the `decoy-data` organization with one GitHub Actions workflow on GitHub-hosted runners? | Yes. Hosted runners are what most companies use, need no runner registration or VM, and give real secret masking, artifacts and re-runs. The minutes fall within the organization's included private-repo minutes. A new repository is an owner call. Fallback if no: the same steps as a shell script on a test node. |
| Q3 | Public data set: Synthea and Chinook | Yes; both licenses allow internal testing; nothing is redistributed. |
| Q4 | Spend | No new spend: L runs fit the Dell and the existing GCP test nodes. |

## 12. Compatibility impact

None. No product surface changes. The tooling reads the exit registry and the schemas; it changes neither. S1 adds `allpairspy` to the dev dependency group (a lock change, so S1 takes a full suite).

## 13. Slices

| Slice | Contents | Risk | Review |
|---|---|---|---|
| S0 | this plan merged; roadmap row QA-BETA in `docs/roadmap/groups/release.md`; `docs/qa/beta-program.md` (method only); pointer from `docs/qa/cli-v1-checklist.md`; CODEMAP rows | R1 docs | Codex |
| S1 | corpus and harness: manifest, `generate.py`, `fetch.py`, `sweep.py` (checklist and journey moved onto it), invariants I1 to I7, `matrix.py` and `matrix.toml`, `findings.py`, `repro.py`, `allpairspy` in the dev group; AT-1 to AT-9, AT-11; M1 to M3 on the final head | R2 (the leak checker is the guarantee) | Dennis then Codex |
| S2 | briefs and launcher: five charters, checklist-pass, doc-walk and triager briefs, finding template, `launch.py` with the per-tester OS user; AT-10 | R1 | Codex |
| S3 | dry run: build the S and M corpus on the Dell and Mac and L on the Dell, run the matrix smoke (about 10 runs on the demo template), run one charter for 30 minutes on the demo only, time the launch, triage it end to end; record `docs/records/2026-MM-DD-qa-beta-dry-run.md`; findings held per F9 | R1 | Codex reads the record |

S1 and S2 can build in parallel after S0. S3 needs both.

## 14. Done when

- S0 to S3 merged; the dry-run record shows one finding (planted, if the product gave none) going from tester to record to repro to triage result, with the needles sweep clean over the pass folder and the hand-backs.
- The dry-run record shows a tester started on a closed group within one hour of the launch command.
- The corpus S, M and L tiers are built and hash-checked on the Dell, S and M on the Mac.
- The board shows QA-BETA closed and each checklist group's "ready for QA" state, so the first L1 pass can start the day a group closes.

## 15. Defect catalog and enumerations

### 15.1 Plan defect catalog classes

| Class | Name | Closing structure | Sentry or property test | Mutation |
|---|---|---|---|---|
| 1 | value leak | `findings.py write` is the only writer of finding records and refuses needles and hashed input values; one sweep module for all QA; the triager sweeps hand-backs | AT-7, AT-2, AT-11 | M2, M1 |
| 2 | cleanup | each run uses a fresh `DECOY_HOME` and output folder under the pass folder, removed after its invariants run unless a finding keeps it | AT-9 checks a fresh home per repro | N/A: no product cleanup path changes; the harness tests cover their own temp use |
| 3 | state | no state shared between runs: per-run `DECOY_HOME`, per-run output folder, corpus read-only | AT-9 | N/A: the corpus is read-only, so there is no shared mutable state to mutate |
| 4 | route | the matrices cover every route the docs name (pandas, native, chunked, out-of-core) and I3 compares routes only where the docs promise equality | AT-6 coverage property, AT-4 | N/A: mutations are core only (owner 2026-11-10); AT-6 is a property test over random parameter sets |
| 5 | referential | I2 checks every FK shape in the corpus | AT-3 | N/A: mutations are core only (owner 2026-11-10); AT-3 plants an orphan per FK shape |
| 6 | untrusted input | downloaded data is untrusted: hash checked, own folder, read as data only with `python -I`; testers run as a user that cannot read checkouts | AT-8, AT-10 | M3 (rename before the hash check) |
| 7 | TOCTOU (check-then-use) | `fetch.py` downloads to a temp file, checks the hash on that file, then renames it; the checked file is the used file | AT-8 | M3 (rename before the hash check) |
| 8 | weak tests | every invariant checker has a planted-defect test and a pass case for each documented exception; AT-6 runs in CI with no skip | AT-2 to AT-6 | M1 (I1 checker skips stderr) |
| 9 | refactor | N/A: no product code is moved or rewritten; the checklist and journey sweeps move onto `sweep.py` with AT-11 pinning it |  |  |
| 10 | frozen contracts | the tooling only reads frozen surfaces (exit registry, schemas); section 15.3; manifest and finding records carry `schema_version` | AT-5 reads the live registry, so a registry change shows up as a test change, not a silent drift | N/A: QA-BETA adds no frozen surface |

### 15.2 Enumerations

#### 15.2.1 Exit paths

I6 classifies every exit the CLI can give:

- `EXIT_OK` 0 (`src/decoy/cli/exit_codes.py:45`): pass when the docs expect success.
- `EXIT_USAGE` 1 (`src/decoy/cli/exit_codes.py:49`): a refusal when stderr carries a documented `error:` reason; a crash finding when stderr carries a traceback or no reason, because the crash handler also exits 1 (`_EXIT_CRASH`, `src/decoy/cli/exit_codes.py:116`).
- 2 (`src/decoy/cli/exit_codes.py:56` as `EXIT_WARNINGS`; also Click's usage error, `("failed", "parameter")` in `RUN_EXIT_MAP`, `src/decoy/cli/exit_codes.py:135`): pass when a documented warning code is present or the docs describe the usage refusal.
- `EXIT_RUNTIME` 3 (`src/decoy/cli/exit_codes.py:66`): always a finding.
- `EXIT_FINDINGS` 4 (`src/decoy/cli/exit_codes.py:74`): pass when the run used `--post-validate-enforce` or a gate and the report names findings.
- `EXIT_CAPACITY` 5 (`src/decoy/cli/exit_codes.py:82`): pass only under a memory budget or full-disk test with the documented message.
- `EXIT_PARTIAL` 6 (`src/decoy/cli/exit_codes.py:103`): always a finding; it is reserved and no path reaches it in V1.
- 130 (`_EXIT_INTERRUPTED`, `src/decoy/cli/exit_codes.py:111`): pass after a Ctrl-C in P5; a finding anywhere else.
- Any other code, or a signal death: a finding.

#### 15.2.2 Routes

- pandas (`--no-native`)
- native (`--native`, and default when the companion is present)
- chunked (`--chunked`)
- out-of-core (a `--max-memory` budget below the item size)
- subset on and off (`--no-subset`)
- installed bundle on Linux x86-64, macOS arm64; Windows after rows 89 and 6

#### 15.2.3 FK shapes

- single parent and child
- three-level chain
- self-reference
- composite key
- cycle (refused in V1 by owner decision; a refusal check)
- child with orphans in the input (the docs' orphan policy and quarantine decide the expected output; I4 counts quarantined rows)

#### 15.2.4 Fields

Finding record fields (section 5.6):

- `schema_version`, `id`, `layer`, `persona`, `group`
- `platform`, `cli_version`, `engine_version`, `bundle_digest`
- `corpus_item`, `command`, `config` (values removed)
- `expected` (doc path and line, or invariant id), `actual`, `exit`
- `repro`, `proposed_tier`, `confusing`

Corpus manifest fields: `schema_version`, `id`, `origin`, `license`, `sha256`, `tier`, `format`, `shapes`, `marker_columns`.

#### 15.2.5 Output surfaces

Every surface I1 and I7 search:

- output data files (CSV, TSV, Parquet, fixed width)
- stdout, including `--json` documents
- stderr
- log files under the project and `DECOY_HOME`
- run result files (`--result`)
- evidence manifests (`--evidence-out`)
- post-scan and integrity reports (`--integrity-out`)
- scan documents (`decoy scan --output`)
- vault files (searched for needles; encrypted values are expected)
- notification payloads (`--notify` to a local sink)
- tester hand-back text, finding records and pass records

Documented exceptions: `passthrough` columns; the documented `truncate` prefix; `text_redact` surrounding text; `unmask` and `detokenize` output files when the run holds the vault file and the mask secret.

### 15.3 Frozen contracts

QA-BETA changes no frozen contract. It reads two: the exit registry (`src/decoy/cli/exit_codes.py`) and the versioned schemas (`docs/schemas/`). If either changes before a pass, the pass uses the new version; AT-5 reads the live registry, so a change shows up in the test, not as silent drift.

## 16. Pre-mortem

Assume the V1 QA pass found too little and users hit bugs in January. Likely causes and the guard for each:

- **Testers stayed on the happy path.** Guard: P5 careless-user charter, refusal checks for every refused pair, and the malformed-file shapes in the corpus.
- **The corpus was too clean.** Guard: Synthea's real-world mess, five date formats, encodings, heavy nulls, duplicates.
- **Findings were lost in triage.** Guard: every finding has a record and a triage result in the pass record; the board shows open counts.
- **Agents invented findings and the real ones were drowned out.** Guard: the repro gate; dedupe by root cause.
- **The oracle had a hole or cried wolf.** Guard: planted-defect tests with pass cases for every documented exception; the class check in triage turns repeated findings into sentries.
- **QA started late.** Guard: S0 to S3 finish before the V1 build ends; L1 starts per group as groups close.
- **The CI story was never tried.** Guard: P3 on a real hosted CI system (Q2), with its notes going to REL-DOCS.

## 17. Review map (Dennis r1)

| Finding | Closed in |
|---|---|
| H1 third leak sweep, no secret needles | 4 (one sweep), 5.2 (needles), AT-2, AT-11 |
| H2 exit classification | 15.2.1, AT-5, F13 |
| H3 leak false positives on documented behaviour | 5.5 I1 per strategy, 15.2.5 exceptions, AT-2, F12 |
| H4 matrix flags and constraints | 5.4 (two matrices, strategy mix, three constraint kinds), AT-6 |
| M1 connectors not built | 5.2, P2 |
| M2 command coverage, fit | 5.1 command table, P1 |
| M3 I3 promises | 5.5 I3 with doc lines, AT-4 |
| M4 I4 not computable | 5.5 I4 |
| M5 I8 not an RSS ceiling | 5.5 (metric only) |
| M6 sandbox and hand-backs | 5.1 sandbox, 5.7 step 2, AT-10, F2, F3 |
| M7 allpairspy in CI | 7, 12 (dev group, full suite on S1) |
| M8 proportionality | 2 (no XL), 5.2 (Synthea and Chinook), 8 (three mutations), 13 (S1 merges corpus and harness) |
| M9 hosted runners | Q2 |
| M10 no admin role | P4, 15.2.5 |
| L1 one-hour guarantee check | 14 |
| L2 schema_version | 5.2, 5.6, 15.2.4 |
