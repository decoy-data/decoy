# CLI QA checklist (V1)

Status: current

Roadmap row 92a (CLI-QA-CHECKLIST). Written 2026-11-15 from CLI `origin/main` `5628920`
(`src/decoy/cli/`, `docs/cli-reference.md`, `README.md`, `docs/`) and roadmap section 5.3. Not yet
run.

This file lists what the V1 `decoy` CLI must do, grouped by feature group, and the check a QA pass
runs for each promise. It sits beside the engine checklist (`E:docs/qa/`, 18 sections), which tests
the engine through its public API. This one tests the CLI surface: commands, flags, exit codes,
project layout, records, install and upgrade. Where a CLI check depends on engine behaviour, the
engine section that owns the behaviour is named in the group's notes.

It is not a roadmap and tracks no work. Results go to a dated record (see "Recording a run").
A check that fails becomes a roadmap row in `docs/ROADMAP.md`, as the 2026-11-08 QA findings did.

## When a group is ready for QA

Owner rule (2026-11-11, standing): QA runs only on a feature group that is V1 complete. A group is
ready when every row in its "Waits on rows" line has a State that starts with `MERGED` or `DONE` in
`docs/ROADMAP.md` section 5.3. Never run part of a group, so no check is run twice. Repo-wide scans
(pip-audit, semgrep, gitleaks) file their findings against the group and wait for its pass.

Some rows never hold a group, although checks cite them:

- Rows 93 (REL-GATE) and 94 (CLI-REL) come after QA and read its records. Checks that cite them are
  marked **RC**: they need the signed release candidate and run at REL-GATE G6 and G7. Until then an
  RC check is recorded as blocked, not failed, and the rest of its group runs as normal.
- Row 77 (later releases and repins) is open-ended by design.
- Rows 6 (WIN-RUNNER) and 89 (WIN-FEAS) decide only the Windows cells. A Windows cell is blocked
  until row 89 clears Windows for V1 and row 6 provides the runner; the other platforms run.
- Rows marked DEFERRED or PARKED by the owner are out of V1.

A check whose surface is not built yet is marked **Not built.** Its command names come from the
row's plan and are corrected here when the row merges, before the group's pass.

## Groups

Sixteen groups, 204 checks.

| # | Group | Ids | Waits on rows |
|---|---|---|---|
| 1 | [Install, version and upgrade](#1-install-version-and-upgrade) | INST-01 to INST-19 | 18, 47, 76, 78, 88, 90, 90a, 91 |
| 2 | [Projects, init and layout](#2-projects-init-and-layout) | PROJ-01 to PROJ-18 | 24, 24e, 24o, 24t, 32b |
| 3 | [Validate and the pre-run gate](#3-validate-and-the-pre-run-gate) | GATE-01 to GATE-19 | 19, 20, 20b, 22, 23, 24a, 24b, 24e, 24k, 24o, 24zf |
| 4 | [Scan](#4-scan) | SCAN-01 to SCAN-17 | 22, 24c, 24e, 27, 29, 30, 31, 32, 32a, 36, 56, 80, 81 |
| 5 | [Mask run](#5-mask-run) | RUN-01 to RUN-20 | 19, 20, 21b, 24d, 24e, 24zb, 24zd, 24zh, 38, 57, 61a, 62, 63, 63a, 90, 95 |
| 6 | [Delivery, run result, resume and connectors](#6-delivery-run-result-resume-and-connectors) | DLV-01 to DLV-12 | 24t, 61, 62, 64, 64b, 66, 85, 86, 87 |
| 7 | [Keys and secrets](#7-keys-and-secrets) | KEY-01 to KEY-09 | 24zb, 65, 73, 79, 83 |
| 8 | [Unmask, tokenize and the vault](#8-unmask-tokenize-and-the-vault) | REV-01 to REV-12 | 21, 24e, 24zh, 79 |
| 9 | [Fit and generation](#9-fit-and-generation) | GEN-01 to GEN-16 | 24e, 24f, 24g, 24j, 24l, 24m, 24o, 24s, 24w, 24x, 24y, 24zc |
| 10 | [Evidence and reports](#10-evidence-and-reports) | EVD-01 to EVD-13 | 21, 24e, 24o, 37, 39, 65, 66, 70, 72 |
| 11 | [Exit codes and the output contract](#11-exit-codes-and-the-output-contract) | EXIT-01 to EXIT-09 | 17, 24a, 24zf, 61, 62 |
| 12 | [Local record library and job logs](#12-local-record-library-and-job-logs) | LIB-01 to LIB-10 | 30, 34, 35, 36, 37, 38, 39, 40, 41, 42 |
| 13 | [CI integration](#13-ci-integration) | CI-01 to CI-06 | 20b, 24e, 62 |
| 14 | [Settings, notifications and telemetry](#14-settings-notifications-and-telemetry) | OPS-01 to OPS-06 | 63a, 65, 66, 71 |
| 15 | [Help, explain and docs truth](#15-help-explain-and-docs-truth) | DOC-01 to DOC-10 | 24e, 24o, 56, 75, 92 |
| 16 | [Release build and repo health](#16-release-build-and-repo-health) | BLD-01 to BLD-08 | 5, 5b, 5c, 7, 18, 24ze, 46, 53, 76 |

The row index at the end lists every section 5.3 row that touches the CLI and the checks that cover
it, and the rows no check covers.

## Conventions for a QA pass

- Run every check through the installed `decoy` command, not from a source checkout. Before REL-GATE
  G5 that is a bundle built from the frozen CLI head (REL-GATE G3) and installed with
  `DECOY_LOCAL_BUNDLE`; RC checks use the signed candidate. A check that passes only from source is a
  finding.
- Use the fixture project below. Its data is made up: short tokens and numbers, never realistic
  personal data.
- "Exit N" means the process exit integer. `decoy.cli.exit_codes` names them: 0 OK, 1 usage,
  2 warnings (also a Click usage error), 3 runtime, 4 findings, 5 capacity, 6 partial delivery
  (reserved until row 61), and 130 for Ctrl-C.
- "Refused" means the command stops before it reads source rows or writes an output, prints an
  `error:` line on stderr, and with `--json` prints one error object on stdout.
- "Value-free" means stdout, stderr, `--json`, evidence, records, notifications and OTel spans name
  tables, columns, files, counts and reason codes, and never a cell value or a secret. Check it with
  the marker sweep below.
- Run each determinism check twice in separate processes and compare output bytes.
- Run each install and file-mode check on every launch platform: `linux-x86_64`, `linux-aarch64`,
  `macos-arm64`, and `windows-x86_64` only once rows 6 and 89 allow it.
- Group 1 before the candidate exists. INST-01, INST-03, INST-04, INST-06 to INST-09 and INST-15 need
  a signed bundle and a signed version document, and a build still carrying the placeholder release
  key has none: `decoy upgrade` refuses with `NoPinnedKeyError` and `_key_unresolved()` silently
  suppresses the INST-15 notice (`src/decoy/__main__.py:196-205`, `:263`). A pre-RC pass therefore
  uses a test key: `packaging_tools/sign_release.py keygen` for a throwaway pair, `sign` for the
  bundle and a test version document served from a local HTTP server, then
  `DECOY_RELEASE_PUBKEY_FILE=<test public key>` for the installer and the CLI
  (`src/decoy/distribution/release_key.py:37-62`, `packaging_tools/install/install.sh:218-223`),
  `DECOY_VERSION_URL=<local document>` for `install.sh` and the notice
  (`install.sh:41`, `src/decoy/_update_check.py:102`), and the hidden `decoy upgrade --url
  <local document>` (`src/decoy/cli/upgrade.py:65`). The override is honored only while the committed
  key is the placeholder, and warns when used. Once REL-GATE G2 commits the owner's key, a bundle
  built from that head ignores it, so on such a head these eight checks run on the signed candidate
  at G6 and are recorded as RC there. The throwaway private key is deleted after the pass and never
  committed.
- The Pass/fail column stays blank in this file. A run record copies the group's table and fills it.

### Fixture project

```console
$ decoy project new qa-proj && cd qa-proj
$ export QA_SECRET="$(head -c 48 /dev/urandom | base64)"   # mask secret, at least 32 bytes
```

No fixture YAML sets `global_settings.mask_secret_ref`. Every command that needs the mask secret gets
`--mask-secret env:QA_SECRET`; a command refuses the flag when the YAML also sets the ref (KEY-02).

| Fixture | Shape | Used by |
|---|---|---|
| `mask-basic` | `data/t1.csv` with a header: `id` (hash, namespace `ids`), `code` (9 digits, `fpe`, namespace `codes`), `contact` (made-up addresses like `qamark0001@example.invalid`, `redact`), `note` (`redact`), `amount` (passthrough) | most groups |
| `mask-abs` | `mask-basic` with its target set to an absolute path of a file that already exists | GATE-09, EXIT-02 |
| `mask-vault` | `mask-basic` with `vault: true` on `code` | REV-03, REV-04, REV-09 |
| `mask-fk` | `data/parent.csv` and `data/child.csv`; `child.parent_id` references `parent.id`, both `hash` in one namespace | RUN, DLV, REV-11 |
| `mask-big` | `mask-basic` over a generated CSV larger than the memory budget given by `--max-memory` | RUN-07, RUN-08, RUN-18 |
| `tok-basic` | `data/t1.csv` with `id` as `strategy: tokenize` | REV-06, REV-07, REV-09, REV-12 |
| `gen-basic` | generate only: `sequence`, `categorical`, `derived`, `formula` and `reference` columns over two tables | GEN |
| Loose files | `data/raw.csv` (three columns, no header); `data/rec.fwf` with `data/layout.yaml`; `data/t1.duckdb` holding table `t1`; `/tmp/qa-out/data.csv` outside any project | SCAN-05, SCAN-06, RUN-15, PROJ-05 |

Marker sweep: every text cell holds `qamark` plus a number, and `data/markers.txt` lists every text
marker and every `code` value (the digits `fpe` reverses carry no text marker). The sweep is
`grep -rFf data/markers.txt <captured files>`, run only on files that exist. Exit 1 (no match) is a
pass; exit 0 is a finding unless the match is in a `passthrough` column of a masked output; exit 2
(missing file) means the check did not run.

Services: the checks that reach an external service get it from a local container where a faithful
one exists, and otherwise from test credentials the owner provides for a throwaway account. Every
service holds only fixture data, credentials go in by environment or secret reference and never into
a run record, and each record names the service and its version.

| Check | Service | How it is provided |
|---|---|---|
| KEY-08 | HashiCorp Vault | `vault server -dev` in a local container |
| KEY-08 | AWS Secrets Manager | a LocalStack container |
| KEY-08 | GCP Secret Manager, Azure Key Vault | owner-provided test credentials (no faithful local emulator) |
| DLV-08 | `s3://` and `gs://` targets | MinIO for S3 and `fake-gcs-server` for GCS, in local containers |
| DLV-09, DLV-10 | PostgreSQL source and target | a local `postgres` container at the version row 64b and row 86 support |
| DLV-11 | SFTP target; cloud source scan and subset | an SFTP server container; MinIO as the cloud source |
| INST-16 | container runtime and the image registry | local Docker; registry pull access per row 90a |

## 1. Install, version and upgrade

What it covers: the signed per-platform bundle, `install.sh`, the offline path, `decoy upgrade`,
`decoy doctor`, the native companion self-check, the container image and the update notice. Engine
section 15 owns the native route itself. Installing from the download host with `curl` is checked by
row 94 after publication.

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| INST-01 | `DECOY_LOCAL_BUNDLE=<bundle> sh install.sh` with the bundle's `.sha256` and `.sig` sidecars beside it, on each launch platform; then `decoy --version` | Installs; prints `decoy` and the bundle's version string (the version the bundle was built at; the 1.0.0 literal is checked only in INST-11); exit 0 | 90 | |
| INST-02 | The same installer on macOS x86_64; on Windows, the PowerShell installer | Refuses with a message naming the platform; nothing under `DECOY_HOME`; non-zero exit. Windows cell per rows 6 and 89 | 89, 90 | |
| INST-03 | Flip one byte of the bundle, then install it | Refused before extract; nothing under `DECOY_HOME` | 88, 90 | |
| INST-04 | INST-01 without the `.sha256` sidecar; then without the `.sig` sidecar | Both refused | 90 | |
| INST-05 | Run `install.sh` again on a host that already has Decoy | Refuses and points at `decoy upgrade` | 90 | |
| INST-06 | `decoy upgrade --check` | Reports current or newer; the `current` runtime link and launcher are unchanged; exit 0 | 88 | |
| INST-07 | `decoy upgrade --version <previous>`, then `decoy upgrade` | Pins back, then returns to latest; each step verified; exit 0 both times | 88 | |
| INST-08 | `decoy upgrade` against a version document whose signature does not verify | `version-document signature INVALID`; exit 3; runtime unchanged | 88 | |
| INST-09 | `decoy upgrade --version <yanked version>` | Refused; the yank is named | 88 | |
| INST-10 | Remove the native companion from the installed runtime, then `decoy scan data/t1.csv --has-header`; then `decoy --version`, `decoy --help`, `decoy upgrade --force` | The scan exits 3 and points at `decoy upgrade --force`; `--version` and `--help` still work; `upgrade --force` repairs and the scan then exits 0 | 88, 90 | |
| INST-11 | **RC.** `decoy --version`; the bundle's Python with `-I` printing `decoy_engine.__version__` | CLI version is the release tag; the engine is the D-4 launch tag | 18, 76, 77, 93, 94 | |
| INST-12 | **RC.** `decoy upgrade --check` on the installed candidate | Runs (no missing pinned key error): the release public key in the bundle is the owner's key, not the placeholder | 90, 93 | |
| INST-13 | **RC.** Bundle contents: `NOTICE`, `LICENSE`, the SBOM | Present; the license is FSL-1.1-ALv2 with the licensor counsel confirmed; the SBOM lists the runtime's packages | 88, 90, 93 | |
| INST-14 | `sh install.sh uninstall` | Removes the runtime and launcher; leaves `qa-proj` untouched | 90 | |
| INST-15 | In an interactive terminal with a newer version on the endpoint and no check inside the cadence window: `decoy info`; then `decoy --no-update-check info` and `DECOY_NO_UPDATE_CHECK=1 decoy info` | One notice line on stderr only in the first; none in the others; the request carries no data, identifiers or telemetry | 91 | |
| INST-16 | Container image: `docker run <image>:1.0.0 --version` with no license variable, then with it; `id -u` inside; the `-ner` tag | **Not built.** Refuses without the license acceptance; runs with it; non-root user; the `-ner` tag carries the NER model; the image is pinned by digest | 90a | |
| INST-17 | INST-01 to INST-06 and INST-14 on the build that carries the `installer.py` split | Same results as before the split | 47 | |
| INST-18 | The CLI environment report from F10 on two hosts | **Not built.** Prints engine compatibility, seed protocol, provider and pool digests; comparing two hosts names each difference | 78 | |
| INST-19 | `decoy doctor`, then `decoy doctor --json`, on a healthy install; again after removing the native companion | Exit 0 with each requirement listed. After the removal both forms are refused by the runtime guard before `doctor` runs: exit 3, a plain-text `decoy: native companion check FAILED ...` line on stderr naming `decoy upgrade --force`, and nothing on stdout, `--json` included (`src/decoy/distribution/runtime_guard.py:23,38-42`, `src/decoy/__main__.py:252-255`). See the EXIT-04 open point | 88, 90 | |

Open points:

- `decoy --version` prints only the CLI version (`src/decoy/__main__.py:210`). INST-11 reads the
  engine version from the runtime. Whether V1 should print both is a REL-GATE question.

## 2. Projects, init and layout

What it covers: projects (`decoy project`), `decoy init` and its wizard, where a run writes
(`out/<pipeline>/<run-id>/`, `LATEST`, `current`), `--out-dir`, `run` with no argument and
`run --all`, and private file modes. Source: `docs/project-layout.md`.

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| PROJ-01 | `decoy project new qa-proj`; delete `out/`; run it again | Makes `decoy.yaml`, `pipelines/`, `out/` (with `.gitignore` holding `*`) and `.decoy/`; the second run fills in only `out/`; exit 0 | 24t | |
| PROJ-02 | `decoy project new ~` and `decoy project new /` | Refused; exit 1 | 24t | |
| PROJ-03 | In `qa-proj`: `decoy init mask-basic --source data/t1.csv --preset minimal --json` | Writes `pipelines/mask-basic/pipeline.yaml` with the source as `../../data/t1.csv`, the target as a bare `t1.masked.csv`, and no `name:` key; no prompt | 24t | |
| PROJ-04 | `decoy init 'bad name!'` | Exit 1, `layout.pipeline_name_invalid` | 24t | |
| PROJ-05 | In `/tmp/qa-out`: `decoy init data.csv`; then `decoy init data.csv -o -` | The first exits 1 with `layout.project_not_found` before reading the file; the second prints YAML on stdout and writes nothing | 24o, 24t | |
| PROJ-06 | PROJ-03 again when the file exists; then with `--yes` | The first is refused (exit 1); the second replaces the file | 24t | |
| PROJ-07 | `decoy run mask-basic --mask-secret env:QA_SECRET`, then `ls -l out/mask-basic` | Output under `out/mask-basic/<run-id>/` with mode 0700; `LATEST` holds the run id; `current` links to it; the summary and `--json` name the folder | 24t | |
| PROJ-08 | Make the run fail (for example remove `data/t1.csv`), then read `LATEST` | Non-zero exit; `LATEST` and `current` still name the previous clean run | 24t | |
| PROJ-09 | `decoy run` with no argument in a project with one pipeline; with two; outside a project | Runs the one pipeline; with two, exit 1 listing both; outside a project, exit 2 (missing argument) | 24t | |
| PROJ-10 | `decoy run --all`, with one pipeline broken; then `decoy run --all mask-basic` and `decoy run --all --vault v.bin` | Each pipeline runs in its own process and the run goes on after a failure; the exit is the first of 3, 5, 1, 4, 2, 0 any child produced; the last two are refused with exit 1. **Changes with RG-X (CLI #270, open).** RG-X makes `run --all` use the `decoy ci` precedence; grade against the order above until #270 merges | 24t | |
| PROJ-11 | `decoy run mask-basic --mask-secret env:QA_SECRET --out-dir build` | Outputs in `build/`, made owner-only if new; no run id, `LATEST` or `current` | 24t | |
| PROJ-12 | A relative target that climbs out of its folder (`../../escape.csv`); then an absolute target | The first is refused with `layout.output_path_escapes`, exit 1; the second is written as given | 24t | |
| PROJ-13 | From another folder: `decoy --project qa-proj run mask-basic --mask-secret env:QA_SECRET`, and the same with `DECOY_PROJECT=qa-proj` instead of `--project` | Both run the project's pipeline and write under its `out/` | 24t | |
| PROJ-14 | `decoy project show --json`; `decoy project list .. --json` | Root and pipelines listed; exit 0 | 24t | |
| PROJ-15 | After groups 4, 5 and 8 run: list the working directory | No loose files: scan output, reports, unmask and detokenize output land in the pipeline folder or next to their input; no stray `logs/` folder | 24e, 24t | |
| PROJ-16 | `decoy init` with no argument in a terminal inside the project; then with `--json` | **Not built.** The wizard scans the source with the selected detectors, writes the YAML and walks each section and column to confirm or reject; `--json` with no name exits 1 | 32b | |
| PROJ-17 | After a run with post-scan findings, the wizard's findings step | **Not built.** Each finding is shown to confirm or reject | 32b | |
| PROJ-18 | `stat` every file Decoy wrote in groups 2 to 10 that can hold values: outputs, vault, token store, `--include-values` snapshot, evidence, records | Files 0600 and folders 0700 on Linux and macOS; on Windows, owner-only ACLs (Windows cell per rows 6 and 89) | 24, 89 | |

## 3. Validate and the pre-run gate

What it covers: `decoy validate` (config, compile, preflight), the gate `decoy run` runs first, the
explicit-config rules and value-free errors. Engine sections 01 and 04 own the rules themselves.
`decoy validate` takes no mask secret option.

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| GATE-01 | `decoy validate mask-basic`, then `decoy validate pipelines/mask-basic/pipeline.yaml` | Config, compile and preflight all pass; exit 0 both times | 23 | |
| GATE-02 | A CSV source with no `has_header` | `validate` and `run` both exit 1 with `source_file.has_header_required`; no run folder is made | 19, 22 | |
| GATE-03 | A headerless CSV with both `column_names` and `column_names_file`; then with neither | Exit 1 at validate in both cases | 22 | |
| GATE-04 | A source column not listed under `columns:` | Exit 1 at validate; the column is named | 22 | |
| GATE-05 | A declared column missing from the source | Exit 1 at validate, never exit 3 at run | 24b | |
| GATE-06 | `fpe` with no namespace | Exit 1 at validate | 24b | |
| GATE-07 | A DP release with no labels for a sampled column | Refused at validate, not at run with `statistical_stats_degenerate` | 24b | |
| GATE-08 | `decoy run <config> --mask-secret env:QA_SECRET` on each config from GATE-02 to GATE-07 | The same exit as `validate`; no source rows read and no output written | 23 | |
| GATE-09 | `decoy validate mask-abs`, then `decoy validate mask-abs --fail-on-warning`, then `decoy run mask-abs --mask-secret env:QA_SECRET` | Exit 0 with a `would_overwrite` warning; exit 2; the run counts the warning on stderr and goes on | 23 | |
| GATE-10 | A target declared `format: parquet` with a `.csv` file name | Exit 1 at validate; `decoy ci check` reports the same contradiction | 20, 20b | |
| GATE-11 | A config whose error would echo a cell value (a `categorical` mapping keyed on a fixture marker), and one with a malformed secret ref; each with and without `--json` | Messages name keys, tables, columns and files only; the marker sweep is clean; `--json` prints one error object (`command`, `status: "error"`, `error`, and `code` when there is one) | 24a, 24zf | |
| GATE-12 | A relationship with no resolvable namespace; a generate-only relationship with no `namespace`; then `decoy validate compile` on `mask-fk` | The first exits 1 with a message and no traceback; the second validates (exit 0, nothing is masked); the compile result lists the declared FK | 24e | |
| GATE-13 | `decoy validate compile --explain` on `mask-basic` and on `gen-basic`; `decoy validate compile --json` | Per-column strategy and rationale for mask and generate tables; the `--json` command name is `validate compile` | 24e, 24o | |
| GATE-14 | `decoy validate compile mask-basic -o plan.yaml`, then `--format json`; then `--profile p.json --no-profile` where `p.json` exists | Writes the frozen plan in each format; the flag pair is refused with exit 1 (a missing `p.json` would exit 2 first) | 24o | |
| GATE-15 | A generate `row_count` over the host's capacity: `decoy validate`, then `decoy run` | Exit 5 at validate and exit 5 at run before any output is written | 24k | |
| GATE-16 | Generate columns with `weigths:`, `null_probability: 2`, `step: 0`, a missing `references` | Exit 1 at validate, naming each column | 24k | |
| GATE-17 | A YAML file that is a list, not a mapping, given to `validate`, `run`, `tokenize`, `unmask` and `report fidelity --config` | The same exit 1 and the same message from every command (one config loader) | 24zf | |
| GATE-18 | `DECOY_DEBUG=maybe` on the EXIT-03 crash setup | Debug stays off: the one-line internal error, no traceback (one flag truthiness rule) | 24zf | |
| GATE-19 | `decoy validate` on a config whose relative target folder does not exist yet | No "output directory does not exist" warning: the run creates it | 24e | |

## 4. Scan

What it covers: `decoy scan SOURCES...`, `scan fields`, `scan show`, `scan diff`, the scan follow-ons
(emit-config, compare, snapshots, drift) and optional ML detectors. Engine section 03 owns detection.

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| SCAN-01 | `decoy scan data/t1.csv --has-header` | Rows, fields, PII candidates labelled as suggestions, reid risk with its unit; exit 0 | 24e, 27 | |
| SCAN-02 | `decoy scan data/t1.csv` with no header flag | Exit 1: scan never guesses | 22, 27 | |
| SCAN-03 | `decoy scan data/parent.csv data/child.csv --has-header --output scan.json`; `decoy scan fields scan.json --table parent --json` | One table per file, named from the file stem; the field list for `parent`; exit 0 | 27 | |
| SCAN-04 | `decoy scan data/t1.csv --has-header --output t1-scan.json`; the marker sweep over it; `decoy scan show t1-scan.json contact --table t1`; then the `scan.json` that `decoy demo` writes | The scan file is the value-free core: no per-value members, sweep clean; `scan show` prints counts and labels only; in the demo's `scan.json`, sensitive columns show `[redacted]` and `redacted_columns` lists them; no flag brings values back | 24c | |
| SCAN-05 | `decoy scan data/raw.csv --no-header --column-names a,b,c`; then `--column-names` with `--has-header` | Named columns; the second is refused (exit 1) | 27 | |
| SCAN-06 | `decoy scan data/rec.fwf --layout data/layout.yaml`; then without `--layout` | Scans; the second exits 1 | 27 | |
| SCAN-07 | `decoy scan diff old.json new.json --strict` where `new` adds a high-PII field; then with no drift; then `- -` | Exit 1 on drift (see open points); exit 0 with no drift; exit 1 when both are stdin | 27 | |
| SCAN-08 | `decoy scan data/t1.csv --has-header --emit-config`; `--compare <baseline>` | **Not built.** A starter pipeline YAML; a drift report against the baseline | 29 | |
| SCAN-09 | Save a scan snapshot to the library, reference it as the pipeline's baseline, run | **Not built.** The run's evidence carries the snapshot hash | 30, 36 | |
| SCAN-10 | Opt-in distribution capture, then a run whose output drifts past the set percentage, in strict mode | **Not built.** The breach blocks publication; outside strict mode it warns | 31 | |
| SCAN-11 | `on_drift: fail` with a source that drifted from the baseline; then `on_drift: warn` | **Not built.** The run refuses at start; with `warn` it warns and runs | 32 | |
| SCAN-12 | Scan with defaults; enable the classifier, then NER, per pipeline; remove spaCy and scan with NER on | **Not built.** Default is regex only and says so; the scan report and run result name each detector, model and version; without spaCy, an install line for the `ner` extra and a non-zero exit | 32a | |
| SCAN-13 | Read every scan, report and help text for STORM wording | **Not built.** V1 names only, as row 56 sets them | 56 | |
| SCAN-14 | A run with strict-drift publication blocking configured and a drifted source | **Not built.** No output is published; the reason is named | 80 | |
| SCAN-15 | `decoy list disguises`; then every id `decoy list templates` prints, given to `decoy init --preset ... --json` | The disguise tip points at `decoy list templates`, not at disguise ids; every template id is accepted | 24e | |
| SCAN-16 | A pipeline that applies a disguise from `decoy list disguises` | **Not built.** The engine applies it, with the selector precedence row 81 sets | 81 | |
| SCAN-17 | The model-install command, online and with a copied model file on an offline host; a NER post-scan finding with the default policy, then with fail opted in | **Not built.** The model installs both ways; the finding warns by default and fails the run only when opted in | 32a | |

Open points:

- `scan diff --strict` exits 1 (usage) on drift (`src/decoy/cli/scan.py:1039`). Drift is a data
  finding, which elsewhere exits 4. The help text documents 1, so this is not a docs mismatch;
  confirm the intended code before the exit codes freeze (row 93).
- Row 24c's text says an opt-in flag keeps scan values. The build chose no scan opt-in flag (plan Q1
  (a), CLI #177). SCAN-04 tests the build; the row text is stale.

## 5. Mask run

What it covers: `decoy run` in mask mode: formats, dialects, atomic writes, routes (streamed,
out-of-core, chunked, native), subset and sample, destination collisions and determinism. Engine
sections 02, 11 and 15 own the routes. Every run below passes `--mask-secret env:QA_SECRET`.

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| RUN-01 | `decoy run mask-basic` with CSV, then Parquet, then fixed-width targets | Each target written by its declared format; summary and `--json` list output paths, rows and warnings; exit 0 | 20 | |
| RUN-02 | A source with `has_header: false`, `column_names` and `delimiter: ";"` | Read as declared; output columns match | 19 | |
| RUN-03 | Make an existing target's folder read-only, then rerun with `--out-dir` pointing at it | Non-zero exit; the old target is whole (staged write, one replace) | 21b | |
| RUN-04 | `decoy run mask-basic --chunked`, failing after the first chunk (source truncated mid-run) | No partial target | 61a | |
| RUN-05 | Run `mask-fk` twice in separate processes with the same seed and secret | Output bytes equal, every strategy including `shuffle` | 24d | |
| RUN-06 | `--chunked` on `mask-basic`; on a fixed-width target; on a config with an ineligible strategy | Byte-identical to a plain run; the other two exit 1 with the reason | 20, 63a | |
| RUN-07 | `decoy run mask-big --max-memory 512MiB --explain-plan` | Streams by itself; the summary names the route and why | 63a | |
| RUN-08 | `mask-fk` scaled past memory, with `--max-memory` and `--threads 2`; then a budget too small to finish | Out-of-core route with the given settings; the too-small budget exits 5 | 63a | |
| RUN-09 | `decoy run mask-basic --native`; `--native` on `gen-basic`; `--native` on a table masked only with passthrough | Runs with compiled-kernel evidence; refused up front (exit 1); refused after the run with no output written (exit 1) | 90 | |
| RUN-10 | A pipeline with a `subset:` block: `decoy run`, then `--no-subset`, then `--chunked` | Masks the subset only; masks every row and prints `subset: not applied (--no-subset)`; `--chunked` refused | 57 | |
| RUN-11 | `decoy subset <pipeline> --dry-run`; `-o subset-out`; `-o` an existing non-empty folder | Counts only, nothing written; Parquet plus `subset-manifest.json`; refused (exit 1) | 57 | |
| RUN-12 | `decoy run mask-basic --sample 100` over CSV, delimited, fixed-width and Parquet sources | **Not built.** Output goes to scratch, never to the targets; same behaviour on every format | 38, 63 | |
| RUN-13 | Two tables whose targets resolve to one file: `validate`, `run`, and Python `decoy.mask()` | Refused before any read, naming both tables | 24zh | |
| RUN-14 | `date_shift` with no mask secret: `decoy run`, `decoy run --chunked`, `decoy.mask()` | Each refused with `keyed_strategy_requires_secret` before reading a source | 24zb | |
| RUN-15 | `decoy run mask-basic --duckdb-source t1=data/t1.duckdb`; add `--evidence-out ev.json` | Unchanged after the run split: reads the relation read-only (the database file's hash is unchanged); the second is refused | 95 | |
| RUN-16 | `--post-validate-enforce` on a run whose validator hard-fails a check | Exit 4; the masked output is still written | 62 | |
| RUN-17 | `--fidelity` and `--explain-plan` on a run | Unchanged after the run split: report only, the exit stays 0 whatever the grade | 95 | |
| RUN-18 | Ctrl-C during `decoy run mask-big` | Exit 130; no partial target; scratch removed | 62 | |
| RUN-19 | For each CLI item marked fixed in `docs/records/2026-11-12-duplication-census/REMEDIATION.md`, its repro | Each copy now agrees with the other | 24zd | |
| RUN-20 | `decoy run mask-fk` | The summary shows rows, files and tables for each table | 24e | |

## 6. Delivery, run result, resume and connectors

What it covers: stage-then-deliver (strict and best-effort), the run result document and exit 6,
table-level resume, cloud targets, PostgreSQL source and target, SFTP. Most of it is **Not built.**
Today the CLI runs with `delivery_mode="in_place"` (`src/decoy/cli/exit_codes.py:131-138`).

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| DLV-01 | `mask-fk` in strict delivery, with the child table's delivery forced to fail | **Not built.** No target is published; staged files removed; non-zero exit | 61 | |
| DLV-02 | The same in best-effort delivery | **Not built.** The parent is delivered and the child withheld; exit 6; the run result lists both | 61, 62 | |
| DLV-03 | `decoy run --all` where one child exits 6 | **Not built.** The summary counts it as 6, not 3 (see open points). **Changes with RG-X (CLI #270, open).** RG-X keeps a child's 6 in `run --all`; a child that exits 6 still needs row 61 | 24t, 61 | |
| DLV-04 | Targets under two different roots in one run | Refused under the local single-root rule | 61 | |
| DLV-05 | `decoy run mask-basic --json`; read the run result document | **Not built.** `decoy-run-result/v1`: status, exit code, reason codes, tables; value-free; the shape matches the REL-GATE snapshot | 62, 66 | |
| DLV-06 | A run whose worker runs out of memory | Exit 5 (capacity widening) | 62 | |
| DLV-07 | `kill -9` a run of `mask-fk` after the parent table finishes; `decoy run --resume <run dir>`; then resume after editing the config | **Not built.** The parent is kept and the child reruns from its start; with a changed config the resume is refused | 85 | |
| DLV-08 | An `s3://` target, then a `gs://` target; then the same with the cloud extra not installed | **Not built.** Staged under the run prefix and published through the conditional pointer; without the extra, exit 1 and the install line | 64 | |
| DLV-09 | A `type: postgres` source with a value-free connection reference | **Not built.** Reads the listed tables; the connection string never appears in any output | 64b | |
| DLV-10 | A PostgreSQL target | **Not built.** Staging, constraints, indexes and sequences restored, atomic publish; the type-mapping report separates exact, normalized, lossy and unsupported | 86 | |
| DLV-11 | An SFTP target; a scan of a cloud source; a subset against cloud | **Not built.** Each works; connector errors name types, not SDK text | 87 | |
| DLV-12 | A run that fails with an engine refusal, with `--json` | The error carries its reason code and a value-free message through the F29 consumers | 66 | |

Open points:

- **Changes with RG-X (CLI #270, open).** The two points below describe `run --all` before RG-X.
  RG-X keeps a child's 6 and gives `run --all` and `decoy ci` one order. Rewrite them, PROJ-10 and
  DLV-03 when #270 merges.
- `decoy run --all` counts any child exit outside 0 to 5 as 3 (`src/decoy/cli/project/_run_all.py:9-12`,
  `_effective`). Once exit 6 is live, a partly delivered child reads as a crash. DLV-03 fails until
  row 61 or a follow-up adds 6 to the order.
- `run --all` ranks 3 above 5 (`3, 5, 1, 4, 2, 0`) while `decoy ci` ranks 5 above 3
  (`src/decoy/ci/contracts.py:125-135`). Settle one order before the exit codes freeze.

## 7. Keys and secrets

What it covers: `--mask-secret` refs, `--master-key` and `--key-label`, refusals when a key is
missing, external secret adapters and key versions. Engine section 05 owns derivation.

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| KEY-01 | `decoy run mask-basic --mask-secret env:QA_SECRET`; then with a 16-byte secret | Runs; the short secret exits 1 and the message names the ref, not the value | 73 | |
| KEY-02 | A copy of `mask-basic` that sets `global_settings.mask_secret_ref: env:QA_SECRET`, run with `--mask-secret env:QA_SECRET` | Exit 1: the secret is set in two places | 73 | |
| KEY-03 | `--mask-secret file:/tmp/qa.key` with the file mode 0644; then 0600 | Refused; then runs | 73 | |
| KEY-04 | `--mask-secret vault://qa/secret` | Refused with `secret_provider_unknown`; no secret shown | 73 | |
| KEY-05 | A keyed strategy with no secret given anywhere | Exit 1 before any source read | 24zb, 73 | |
| KEY-06 | `DECOY_MASTER_KEY=<63 hex chars> decoy run gen-basic --mode generate`; a good key with no `--key-label`; the same key and label on two hosts | Exit 2; exit 2; bitwise-identical generated output. The key never goes on the command line | 73 | |
| KEY-07 | Run groups 5 and 8 with `--verbose`, `--json`, `--evidence-out` and `--notify`; search all output for the secret | The secret appears nowhere | 65, 73 | |
| KEY-08 | A secret ref through each external adapter (HashiCorp Vault, AWS and GCP Secret Manager, Azure Key Vault) | **Not built.** Resolves; a failure names the adapter and ref, never the secret | 83 | |
| KEY-09 | Evidence after a keyed run; a key rotation with impact preview and remap | **Not built.** `key_version` recorded for every keyed strategy; rotation shows the impact before it remaps | 79 | |

## 8. Unmask, tokenize and the vault

What it covers: `decoy unmask`, `decoy run --vault`, `decoy report vault`, `decoy tokenize` and
`decoy detokenize`. Engine section 16 owns the vault format.

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| REV-01 | `decoy unmask pipelines/mask-basic/pipeline.yaml out/mask-basic/current/t1.masked.csv --mask-secret env:QA_SECRET` | Every `fpe` value recovered exactly; output `t1.masked.unmasked.csv` next to the input; exit 0 | 21 | |
| REV-02 | REV-01 with a different secret | **Exploratory.** Record what happens. The engine checklist expects plausible wrong values with no error (VAULT-02) | 21 | |
| REV-03 | `decoy run mask-vault --mask-secret env:QA_SECRET --vault v.bin`; `decoy unmask ... --vault v.bin`; `decoy report vault v.bin --config <pipeline> --mask-secret env:QA_SECRET` | `code` recovered; the vault report shows counts and no values | 21 | |
| REV-04 | REV-03's run again with the same `--vault v.bin` | Refused, exit 1 (`vault_exists`): vaults are create-only | 21 | |
| REV-05 | `--vault` with `--chunked` | Exit 1 | 21 | |
| REV-06 | `decoy tokenize tok-basic --vault tokens.db` with no secret; then with `--mask-secret env:QA_SECRET`; then `decoy detokenize tok-basic <tokenized file> --vault tokens.db` | Exit 1; tokens written; every value restored | 21, 24zh | |
| REV-07 | `decoy tokenize tok-basic` where an output resolves to the `--vault` path | Refused before anything is written | 24zh | |
| REV-08 | `decoy explain vault` | Describes the encrypted run vault and the cleartext local token store as they are built | 24e | |
| REV-09 | The marker sweep over `v.bin`; `grep -c qamark tokens.db`; `stat tokens.db` | No match in the vault; a non-zero count in the token store (cleartext SQLite by design, `src/decoy/cli/_token_vault.py:31-35`); the token store is mode 0600 | 79 | |
| REV-10 | Change one byte of the vault header, then unmask; open a vault from the previous format (stored fixture) | **Not built.** The tampered vault is refused with a named code; the old vault opens or is refused by name | 79 | |
| REV-11 | `decoy unmask` on `mask-fk` without `--table` | Exit 1, naming `--table` | 21 | |
| REV-12 | `decoy detokenize` on a Parquet input `t1.tok.parquet` with no `-o` | Writes `t1.tok.detokenized.parquet` next to the input | 21 | |

## 9. Fit and generation

What it covers: `decoy fit` (plain and DP), `decoy run --mode generate`, the preview, uniqueness,
null shape and the generation catalog. Engine sections 12 and 13 own the generators and DP.

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| GEN-01 | `decoy fit data/t1.csv`; check `data/t1.snapshot.json` exists, then run the marker sweep over it | `value_policy: flagged-redacted/v1` and `redacted_columns`; flagged columns keep no values, a number keeps one range, a date keeps years; withheld column names printed; sweep clean | 24f | |
| GEN-02 | `decoy fit data/t1.csv --include-values` | Values kept; a warning says the file now holds real data | 24f | |
| GEN-03 | `fit` on a file larger than `fit.max_rows`, twice; then `--rows 0` | A seeded sample from the whole file, the same both times; `--rows 0` exits 1 | 24x | |
| GEN-04 | `decoy fit data/t1.csv --epsilon 1 --delta 1e-6 --dp-text note --dp-allow-omit` on a default install; `decoy fit --help` | Exit 3 with a plain message and a next step; the help marks DP as gated | 24g | |
| GEN-05 | The same DP fit on the release bundle's certified runtime | Admitted; the runtime's certifi, cryptography, pyasn1 and urllib3 match `requirements-certified.txt` | 24zc | |
| GEN-06 | `decoy fit data/t1.csv --joint id,amount --joint-max-cells 100`; then a pair over the cap | Exit 1 `contingency_top_k_kind_unsupported`; a truncated pair warns on stderr and `--json` gains `warnings` | 24w | |
| GEN-07 | `decoy run gen-basic --mode generate` | Numeric columns are numeric; `derived` arithmetic on a `sequence` works | 24j | |
| GEN-08 | A `formula` of `round(a/3)` where `a` is a `sequence` | Numbers, no nulls. If it still yields nulls, the run must not exit 0 with only a warning | 24y | |
| GEN-09 | Fit, generate, then `decoy report fidelity data/t1.csv <generated> --generate` | Null and blank rates carried over and scored; numbers keep source precision | 24l | |
| GEN-10 | `unique: true` on a column whose domain is too small; then on one that fits | Exit 1 `uniqueness_impossible`; all values distinct | 24m | |
| GEN-11 | `decoy run gen-basic --rows 20`; with a mask table in the config; with `--vault v.bin` | Prints rows and writes nothing; both others exit 1 | 24o | |
| GEN-12 | `decoy run gen-basic --mode generate --fidelity` (no mask table) | Exit 1 before any engine call | 24o | |
| GEN-13 | A generate run that triggers the fidelity warning, with and without `--json` | The warning reaches stdout and `--json` | 24o | |
| GEN-14 | The catalog command; `decoy list templates` | **Not built.** Every generate type, option and provider from the engine registries; one starter template each for healthcare, banking, insurance, retail, telecom and HR | 24s | |
| GEN-15 | `decoy run gen-basic --mode generate` with and without `DECOY_MASTER_KEY` | With a key, `global_settings.seed` does not change generated tables; without, the seeded path is used and the summary says which | 24o | |
| GEN-16 | `decoy init gen-x --preset generate --json` | The written YAML says `mode: generate` and validates | 24e | |

## 10. Evidence and reports

What it covers: `--evidence-out` and the `decoy report` commands (show, render, verify, diff,
fidelity, integrity), records of evidence, the signature envelope, the support bundle and safe output.
Engine section 18 owns reason codes and the run result model.

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| EVD-01 | `decoy run mask-basic --mask-secret env:QA_SECRET --evidence-out ev.json`; the marker sweep over `ev.json` | Pipeline hash, file fingerprints, `format` and `layout` per file; sweep clean | 21 | |
| EVD-02 | `decoy report verify ev.json`; change one byte of the output; verify again | Exit 0; then exit 4 naming the file | 21 | |
| EVD-03 | `decoy report diff ev-a.json ev-b.json`; then `--require-data` with one output deleted | Fingerprint and data differences; exit 1 with `--require-data` | 21 | |
| EVD-04 | `decoy report show ev.json`; `decoy report render ev.json -o r.html`; `--format markdown -o r.md` | Each renders; sweep clean over both files | 21 | |
| EVD-05 | `decoy report fidelity src.csv out.csv` with `--mode report`, `--mode warn --min-grade A --fail-on-warning`, `--mode fail --min-grade B` on an output that misses both grades | Exit 0, 4, 4; warnings (`null_drift`, `kind_drift`) print in the terminal; no "PASS" beside a failing grade | 24e, 24o | |
| EVD-06 | Copy a masked `mask-basic` output, put one made-up address back into `contact`, then `decoy report integrity <copy> --source data/t1.csv --config pipelines/mask-basic/pipeline.yaml`; then on the clean output | Exit 4 naming `contact` and no value; exit 0 | 24e | |
| EVD-07 | After a run: the evidence and run-result records in the library, then `library show` | **Not built.** Both records exist and display | 37, 39 | |
| EVD-08 | Verify a signed manifest offline with the public key; tamper with it; verify with a revoked key | **Not built.** Passes; fails; refused | 72 | |
| EVD-09 | The support bundle command | **Not built.** A pseudonymised bundle the user can read before sending; never uploaded; sweep clean | 70 | |
| EVD-10 | A failing run whose source holds marker tokens: sweep stdout, stderr, `--json`, evidence, notifications and spans | Sweep clean (shared safe output) | 65 | |
| EVD-11 | A run that fails mid-table with `--json` | One error object with the reason code; progress lines only on stderr | 66 | |
| EVD-12 | `decoy report fidelity` on `mask-fk` source and output | Hashed key columns are marked intended, not flagged as drift; no joint score across id spaces | 24e | |
| EVD-13 | `decoy report integrity` on a `mask-basic` output with `--config`, without `--json` | Configured columns are not called "not configured to be masked"; `source_identity_rate` is shown; column detail appears in the terminal, not only in `--json` | 24e | |

## 11. Exit codes and the output contract

What it covers: the exit-code table, the error shape, `--json` and `--quiet`, the crash handler and
the frozen surfaces REL-GATE snapshots.

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| EXIT-01 | **RC.** `decoy explain exit-codes`; README "Exit codes"; `decoy.cli.exit_codes`; the crash handler | All agree: 0 to 6 as named, 130 for Ctrl-C, and the crash exit EXIT-03 observes. Today the docs omit 130 and give 3 for an unexpected error (see open points), so this fails until fixed. **Changes with RG-X (CLI #270, open).** RG-X adds 130 to both docs and names 1 for an internal error | 93 | |
| EXIT-02 | One trigger per code: clean run (0), bad config (1), `decoy validate mask-abs --fail-on-warning` (2), unwritable output mid-run (3), `report integrity` finding (4), capacity refusal (5), best-effort partial delivery (6, after row 61), Ctrl-C (130) | Each exits with its code | 61, 62 | |
| EXIT-03 | Force an uncaught exception (an engine module that raises on import, in a scratch runtime) | `error: internal error (<Type>)` and the `--verbose` hint; no traceback; exit 1, as `tests/sentry/cli_text/test_no_traceback_escape.py` pins | 24zf | |
| EXIT-04 | Every leaf command with `--json`, on success and on a refusal. Exempt: `decoy ci check` (no `--json`; its `--format json` report is checked in CI-03) | stdout is exactly one JSON object; refusals use the one error shape; progress only on stderr | 24zf | |
| EXIT-05 | Every leaf command with `--quiet`. Exempt: `decoy ci check -o -`, which still writes its report to stdout | stdout empty; the exit code still carries the result | 24zf | |
| EXIT-06 | EXIT-03 with `DECOY_DEBUG=1`; then EXIT-03 with `--verbose` | The raw traceback, with no summary line and no warning; with `--verbose`, the summary line, the row-data warning, then the traceback | 24zf | |
| EXIT-07 | `decoy explain` and every reason code a command prints | No `WORKFLOW_*` code; the explain pointer row 17 fixes is correct | 17 | |
| EXIT-08 | Error text from GATE-11, REV-11 and DLV-12 | Names may show; data values and secrets never do | 24a | |
| EXIT-09 | **RC.** At the release head: exit codes, `--json` shapes, the YAML schema and the run-result schema against the REL-GATE snapshots | No difference | 93 | |

Open points:

- **Changes with RG-X (CLI #270, open).** The first two points below describe the docs before RG-X.
  RG-X lists 130, drops "one of seven" and names 1 for an internal error in both docs. Rewrite them
  and EXIT-01 when #270 merges.
- Docs and code disagree on an uncaught error. `decoy explain exit-codes` and the README say 3 is the
  code for "the engine raised an unexpected error", and `exit_code_for` maps "everything else" to 3.
  The top-level crash handler exits 1 (`src/decoy/__main__.py:143-170`), and
  `tests/sentry/cli_text/test_no_traceback_escape.py` pins 1. EXIT-03 grades the code as built.
- Both docs say every command returns "one of seven" codes. Ctrl-C exits 130
  (`RUN_EXIT_MAP`, `exit_code_for`), which neither lists.
- EXIT-04 and the runtime guard. On a managed install whose native companion was removed or is
  ABI-mismatched, every command except `upgrade` is refused before it runs, in plain text on stderr
  with exit 3, and `--json` prints no error object (`src/decoy/distribution/runtime_guard.py:38-42`,
  `src/decoy/__main__.py:252-255`). EXIT-04 runs on a healthy install; INST-19 records the guarded
  case as built. Whether the guard should honor `--json` is open.

## 12. Local record library and job logs

What it covers: the local record store under `.decoy/` (LIB L1b to L5b). Rows 34 to 42 build it; most
of the surface is **Not built.** Command names come from the LIB plan.

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| LIB-01 | Write records while killing the process mid-write | No torn record; the store opens | 34 | |
| LIB-02 | After any run, list scratch under `.decoy/` | Scratch removed on every exit path, on each OS lane | 34, 38 | |
| LIB-03 | Corrupt one record, then run the library check | **Not built.** The check names the record; the library lists the rest in degraded mode | 35 | |
| LIB-04 | Save two scans to the library | **Not built.** Both stored as scan snapshots and listed | 30, 36 | |
| LIB-05 | A run with evidence | **Not built.** An evidence record and a run-result record are stored | 37 | |
| LIB-06 | A sample run | **Not built.** A sample-run record; its scratch is removed | 38 | |
| LIB-07 | `decoy library list`, `show`, `diff`, `ref`, `export` | **Not built.** Each works on the records from LIB-04 to LIB-06; sweep clean | 39 | |
| LIB-08 | `decoy library prune` and `clean` | **Not built.** A record another record references is kept | 40 | |
| LIB-09 | `decoy run mask-big` in a terminal, then with `--json` | **Not built.** Progress on stderr from the engine progress events; stdout unchanged under `--json` | 41 | |
| LIB-10 | Any run, then read its job log | **Not built.** One log per run; sweep clean and no secret | 42 | |

## 13. CI integration

What it covers: `decoy ci check` and the `decoy-ci/v1` manifest. Contract: `docs/ci-contracts.md`.

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| CI-01 | `decoy ci check` with no `.decoy-ci.yaml` | Exit 1 with a message naming the expected file | 24e | |
| CI-02 | A manifest whose pipeline fails validation; one with only warnings and `fail_on_warning: true` | Exit 1 with status `findings`; exit 2 | 20b | |
| CI-03 | `--format sarif -o report.sarif`; `--format markdown -o -`; `--format json -o r.json` | SARIF 2.1.0; Markdown on stdout; `decoy-ci-report/v1`; sweep clean | 20b | |
| CI-04 | `--context pre-commit` with a staged file holding a made-up secret-shaped literal | Exit 4; the repo-relative path and the pattern id are reported; the literal and the line never are | 20b | |
| CI-05 | A manifest whose checks produce 5, 3, 1, 4 and 2 | The exit follows 5 > 3 > 1 > 6 > 4 > 2 > 0; never 6 | 62 | |
| CI-06 | A manifest pipeline with a format and suffix contradiction | Reported as a finding | 20b | |

## 14. Settings, notifications and telemetry

What it covers: `decoy setup`, memory and thread settings, `--notify` and `--otel-endpoint`.

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| OPS-01 | `decoy setup`; `decoy setup -y --json` | Writes max memory and threads to `$DECOY_HOME/settings.json`; the JSON record shows them | 63a | |
| OPS-02 | Set settings, then `DECOY_MAX_MEMORY`, then `--max-memory` | Flag over environment over settings; the summary names the value used | 63a | |
| OPS-03 | `decoy run mask-basic --mask-secret env:QA_SECRET --notify webhook:http://127.0.0.1:<port>` with `DECOY_NOTIFY_WEBHOOK_SECRET` set; then an unreachable URL | One signed POST after the run; the unreachable channel leaves the exit unchanged; nothing written to `.decoy/workspace.json` | 65 | |
| OPS-04 | `--otel-endpoint http://127.0.0.1:4318/v1/traces` to a local collector | Spans for read, transform, validate and publish; sweep clean and no secret in any span | 71 | |
| OPS-05 | `--otel-endpoint` with credentials in the URL; a non-loopback `http` endpoint with `DECOY_OTEL_HEADERS`; without the `otel` extra | Exit 1 naming the problem; refused; an install line | 71 | |
| OPS-06 | A run that fails, with `--notify` and `--otel-endpoint` | The notification and the error span carry the reason code only | 66 | |

## 15. Help, explain and docs truth

What it covers: `--help`, `decoy explain`, `decoy list` and `decoy show`, `decoy demo`, the generated
reference, the V1 journey and the public docs.

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| DOC-01 | `decoy --help` and `--help` on every command and subcommand | Each renders; `docs/cli-reference.md` matches the release head (`tests/unit/test_cli_surface.py`) | 92 | |
| DOC-02 | `decoy explain`, then every topic it lists; every `--help` | Each renders; no internal names (`_scan`, `_gate`, ticket ids such as FC-1 or S22-CL-V1GRAPHRUNNER, platform doc paths) | 24e | |
| DOC-03 | `decoy explain pipeline`, `transforms`, `yaml`, `generation` | Match the current schema: version, every generate type and option | 24o | |
| DOC-04 | Each example under `Examples:` in every `--help` | Runs as written against the fixture project with the exit it describes | 24e | |
| DOC-05 | The V1 journey, step by step | **Not built.** Each journey id runs end to end; the release smoke cites the ids | 75 | |
| DOC-06 | The public docs install, upgrade, release notes and security contact pages | Present; every command and flag they name exists in `decoy --help` | 92 | |
| DOC-07 | **RC.** License and install wording in the README, `pyproject.toml`, `docs/install.md`, the bundle and the public docs | One license (FSL-1.1-ALv2), one licensor, one install story (the signed bundle) | 92, 93 | |
| DOC-08 | `decoy list strategies` (and each other kind); `decoy show strategy hash`; `decoy show schema`; `decoy schema -o s.json` | Listings come from the engine registries with V1 names; a bad kind exits 1; the schema is the PipelineConfig schema | 56 | |
| DOC-09 | `decoy explain keys` | The key length it states matches what `--master-key` accepts | 24e | |
| DOC-10 | `decoy demo`, then `decoy demo --json` | Runs end to end and exits 0; writes only inside its own folder; sweep clean on its output | 24e | |

## 16. Release build and repo health

What it covers: the gates the release head must pass. The release owner runs them at REL-GATE G0 to
G3, and the RC checks at G6 and G7; QA records them so the CLI pass is complete.

| Id | Command | Expected | Rows | Pass/fail |
|---|---|---|---|---|
| BLD-01 | `scripts/dev/gates.sh` on the release head, Linux with the stored baseline, and on the Mac | No new failing test | 5b, 5c | |
| BLD-02 | CI on the release head | `ci.yml` jobs green: ruff, pytest, layers-gate, fresh-install-smoke, ci-template-lint, certified-profile | 5 | |
| BLD-03 | The file-size, fan-out and import-layer sentries | Pass with no new exemption | 7, 46, 53 | |
| BLD-04 | The duplication guard sentries | Pass with shrink-only baselines | 24ze | |
| BLD-05 | **RC.** The CLI's engine pin and lock | Exactly the D-4 engine tag in `pyproject.toml` and the lock; `scripts/dev/lock.sh --check` passes | 18, 76, 77, 93 | |
| BLD-06 | **RC.** `docs/release/fresh-install-smoke.md`, then the REL-GATE candidate smoke | Every step exits as written; runs recorded in the smoke log | 93, 94 | |
| BLD-07 | **RC.** A filled release-readiness instance | Every row answered and signed off | 93 | |
| BLD-08 | The suite on the Windows lane | Windows cell only: runs once row 89 ships Windows and row 6 provides the runner | 6, 89 | |

## Recording a run

Copy [cli-v1-run-template.md](cli-v1-run-template.md) to `docs/records/YYYY-MM-DD-cli-qa-<group>.md`,
one record per group pass. For each check record: id, CLI and engine versions, platform, pass, fail
or blocked, and for a failure the command, the config and the observed output with values removed. A
check that cannot run as written is recorded as blocked, and the check text is corrected here in the
same change. Each failure becomes a roadmap row.

## Row index

Every section 5.3 row whose Repo column names the CLI, plus rows 6 (infra) and 91 (web) because CLI
checks wait on them. Rows 6, 77, 89, 93 and 94 never hold a group (see "When a group is ready").

| Row | Item | Checks |
|---|---|---|
| 5 | CI-L1 | BLD-02 |
| 5b | CLI-BASELINE | BLD-01 |
| 5c | CLI-MAC-TESTS | BLD-01 |
| 6 | WIN-RUNNER (infra) | BLD-08 (Windows cells) |
| 7 | FILE-SIZE | BLD-03 |
| 17 | WF-R | EXIT-07 |
| 18 | Release R-c and repin | INST-11, BLD-05 |
| 19 | CLI-DIALECT | GATE-02, RUN-02 |
| 20 | CLI-FMT A | GATE-10, RUN-01, RUN-06 |
| 20b | CLI-FMT A2 | GATE-10, CI-02, CI-03, CI-04, CI-06 |
| 21 | CLI-FMT B | REV-01 to REV-06, REV-11, REV-12, EVD-01 to EVD-04 |
| 21b | ATOMIC-OUTPUT | RUN-03 |
| 22 | CONFIG-EXPLICIT | GATE-02 to GATE-04, SCAN-02 |
| 23 | VALIDATE-ALWAYS | GATE-01, GATE-08, GATE-09 |
| 24 | X7c | PROJ-18 |
| 24a | VALUE-FREE-ERRORS | GATE-11, EXIT-08 |
| 24b | QA-GATE | GATE-05 to GATE-07 |
| 24c | QA-SCAN-REDACT | SCAN-04 |
| 24d | QA-SHUFFLE-DET | RUN-05 |
| 24e | CLI-QA1 | PROJ-15, GATE-12, GATE-13, GATE-19, SCAN-01, SCAN-15, RUN-20, REV-08, GEN-16, EVD-05, EVD-06, EVD-12, EVD-13, CI-01, DOC-02, DOC-04, DOC-09, DOC-10 |
| 24f | QA-FIT-REDACT | GEN-01, GEN-02 |
| 24g | QA-DP-GATED | GEN-04 |
| 24j | GEN-C2 | GEN-07 |
| 24k | GEN-STRICT | GATE-15, GATE-16 |
| 24l | GEN-FIT-SHAPE | GEN-09 |
| 24m | GEN-UNIQUE | GEN-10 |
| 24o | GEN-CLI | PROJ-05, GATE-13, GATE-14, GEN-11 to GEN-13, GEN-15, EVD-05, DOC-03 |
| 24s | GEN-CATALOG | GEN-14 |
| 24t | PROJECT-LAYOUT | PROJ-01 to PROJ-15, DLV-03 |
| 24w | GEN-COND-CAP | GEN-06 |
| 24x | FIT-ROWS | GEN-03 |
| 24y | GEN-FORMULA-SEQ | GEN-08 |
| 24zb | DATE-SHIFT-UNKEYED | RUN-14, KEY-05 |
| 24zc | CERT-PIN-CVES | GEN-05 |
| 24zd | DUP-DEFECTS | RUN-19 |
| 24ze | DUP-GUARDS | BLD-04 |
| 24zf | DUP-FREEZE | GATE-11, GATE-17, GATE-18, EXIT-03 to EXIT-06 |
| 24zh | DUP-DEST | RUN-13, REV-06, REV-07 |
| 27 | SCAN-MULTI S1c-cli | SCAN-01 to SCAN-03, SCAN-05 to SCAN-07 |
| 29 | SCAN-MULTI S3-cli | SCAN-08 |
| 30 | SCAN-LIB | SCAN-09, LIB-04 |
| 31 | DIST-INTEGRITY | SCAN-10 |
| 32 | DRIFT | SCAN-11 |
| 32a | SCAN-ML | SCAN-12, SCAN-17 |
| 32b | INIT-WIZARD | PROJ-16, PROJ-17 |
| 34 | LIB L1b-cli | LIB-01, LIB-02 |
| 35 | LIB L1c-cli | LIB-03 |
| 36 | LIB L2-cli | SCAN-09, LIB-04 |
| 37 | LIB L3a-cli | EVD-07, LIB-05 |
| 38 | LIB L3b-cli | RUN-12, LIB-02, LIB-06 |
| 39 | LIB L4a-cli | EVD-07, LIB-07 |
| 40 | LIB L4b-cli | LIB-08 |
| 41 | LIB L5a-cli | LIB-09 |
| 42 | LIB L5b-cli | LIB-10 |
| 46 | H-1 C0 | BLD-03 |
| 47 | H-1 C1 | INST-17 |
| 53 | H-1 C3 | BLD-03 |
| 56 | STORM rename, CLI half | SCAN-13, DOC-08 |
| 57 | SUB-RUN | RUN-10, RUN-11 |
| 61 | CLI delivery | DLV-01 to DLV-04, EXIT-02 |
| 61a | ATOMIC-CHUNKED | RUN-04 |
| 62 | RESULT | RUN-16, RUN-18, DLV-02, DLV-05, DLV-06, EXIT-02, CI-05 |
| 63 | SAMPLE CLI half | RUN-12 |
| 63a | RUN-STREAM | RUN-06 to RUN-08, OPS-01, OPS-02 |
| 64 | CLI-CLOUD | DLV-08 |
| 64b | CLI-DB-SRC | DLV-09 |
| 65 | F31 | KEY-07, EVD-10, OPS-03 |
| 66 | F29 remainder | DLV-05, DLV-12, EVD-11, OPS-06 |
| 70 | F32 remainder | EVD-09 |
| 71 | F30 CLI | OPS-04, OPS-05 |
| 72 | F33 | EVD-08 |
| 73 | F13 slices 3b and 5 | KEY-01 to KEY-07 |
| 75 | One CLI journey | DOC-05 |
| 76 | Release R-d and repin | INST-11, BLD-05 |
| 77 | Later releases and repins | INST-11, BLD-05 (never holds a group) |
| 78 | F10 | INST-18 |
| 79 | F09 | KEY-09, REV-09, REV-10 |
| 80 | F15 | SCAN-14 |
| 81 | F16 | SCAN-16 |
| 83 | F13 external adapters | KEY-08 |
| 85 | F23 resume, CLI half | DLV-07 |
| 86 | F01 | DLV-10 |
| 87 | F02 | DLV-11 |
| 88 | F44 CLI half | INST-03, INST-06 to INST-10, INST-13, INST-19 |
| 89 | WIN-FEAS | INST-02, PROJ-18, BLD-08 (Windows cells) |
| 90 | REL-PKG | INST-01 to INST-05, INST-10, INST-12 to INST-14, INST-19, RUN-09 |
| 90a | REL-IMAGE | INST-16 |
| 91 | REL-WEB (web) | INST-15 |
| 92 | REL-DOCS | DOC-01, DOC-06, DOC-07 |
| 93 | REL-GATE | RC checks: INST-11 to INST-13, EXIT-01, EXIT-09, DOC-07, BLD-05 to BLD-07 |
| 94 | CLI-REL | RC checks: INST-11, BLD-06 |
| 95 | RUN-SPLIT | RUN-15, RUN-17 |

Rows no check covers:

- 9 (X0a-h): DEFERRED off the V1 path by the owner.
- 74 (F26 CLI local cleanup): PARKED until F22 settles and re-scoped by Opus. Its checks are written
  when the re-scope names the command; its overlap with LIB-08 is settled there.
- 92a (this checklist).
