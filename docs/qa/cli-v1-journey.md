# CLI V1 journey

Status: current

Roadmap row 75. One journey through the V1 pipeline baseline on the CLI: source, subset, pre-scan,
mask per table, post-scan, delivery, plus the vault. It sits beside [cli-v1-checklist.md](cli-v1-checklist.md),
which checks each feature group on its own. This file checks that the groups work in one line.

The user is one person with two related tables on disk, `customers` and `orders`
(`orders.customer_id` references `customers.id`). The project keeps them as CSV in `data/` and as
Parquet in `data/parquet/`, written from the same rows. A pipeline `subset:` reads relationship
tables from Parquet, and `decoy report integrity` reads CSV.

Every step below has one test in `tests/e2e/first_user/journey/test_cli_journey.py` that cites its
id. The test reads the exit codes from this file. The release smoke (`tests/e2e/test_release_smoke.py`)
cites the ids its cells cover. `tests/sentry/release/test_journey_ids.py` keeps this file, the
citations and the exit registry in step.

## Run it

Source checkout (default): `pytest tests/e2e/first_user/journey`.

Installed bundle (QA and release candidate): set `DECOY_JOURNEY_BIN` to the installed `decoy`
launcher and `DECOY_JOURNEY_HOME` to the `DECOY_HOME` of that install, both together, then run the
same command. The test runs with a cleaned environment from a temp folder and refuses to start
unless the bundle's `decoy` and `decoy_engine`, not the checkout's, are what it imports.

## Fixture

Paths are relative to the project folder `shop/`. The test writes three pipelines before the steps
that use them: `shop` (Parquet sources from `data/parquet/`, CSV targets, the foreign key and a
`subset:` block sampling `customers`), `bad` (CJ-05) and `vaulted` (`customers` only, `vault: true`
on one `hash` column). Every text cell carries `jmark` plus a number, and the mask secret is 48
random bytes in `JOURNEY_SECRET`. No step prints a cell value or the secret.

## Step format

Each step is a level-3 heading `### CJ-NN: <title>` and exactly these labelled lines, once each:

- `**Stage:**` one of `install`, `project`, `source`, `subset`, `pre-scan`, `mask`, `post-scan`,
  `delivery`, `evidence`, `vault`, `refusal`.
- `**Command:**` one or more commands, each one backtick span that starts with `decoy `, in the
  order they run. A backtick span that does not start with `decoy ` is not a command.
- `**Exit:**` one exit code per command, in the same order, comma separated. Each code is one of
  the `EXIT_` values or a `RUN_EXIT_MAP` value in `src/decoy/cli/exit_codes.py`.
- `**Expected:**` what the user sees, value-free: tables, columns, files, counts and reason codes.
- `**Lands with:**` `main`, or `row <N>` when the step's behaviour is not on main yet. A step that
  is not on main is a strict expected failure in the test. The change that lands the row sets this
  line to `main`.

## Steps

### CJ-01: Install check

**Stage:** install

**Command:** `decoy --version`

**Exit:** 0

**Expected:** Prints `decoy` and a version.

**Lands with:** main

### CJ-02: Start a project

**Stage:** project

**Command:** `decoy project new shop --json`

**Exit:** 0

**Expected:** The JSON names the project root, and the folders `pipelines/`, `out/` and `.decoy/` exist.

**Lands with:** main

### CJ-03: Scaffold a pipeline from a file

**Stage:** source

**Command:** `decoy init customers --source data/customers.csv --json -y`

**Exit:** 0

**Expected:** `pipelines/customers/pipeline.yaml` is written; the record names the column count and the source.

**Lands with:** main

### CJ-04: Scan the sources before masking

**Stage:** pre-scan

**Command:** `decoy scan data/customers.csv data/orders.csv --has-header --json`

**Exit:** 0

**Expected:** One table per file with row and field counts, PII candidates as suggestions and a re-identification risk score; no cell value.

**Lands with:** main

### CJ-05: A bad pipeline is refused

**Stage:** refusal

**Command:** `decoy validate bad --json`, where `pipelines/bad/pipeline.yaml` has an unknown key and a wrong-typed value that carries a marker

**Exit:** 1

**Expected:** The validation envelope has `status` `error` and a message for the unknown key and one for the wrong-typed value, each with its code and location. The marker is not in the envelope, and no run folder is made.

**Lands with:** main

### CJ-06: A good pipeline passes validation

**Stage:** source

**Command:** `decoy validate shop`

**Exit:** 0

**Expected:** The config, compile and preflight layers each report passed.

**Lands with:** main

### CJ-07: Subset while masking

**Stage:** subset

**Command:** `decoy run shop --mask-secret env:JOURNEY_SECRET --out-dir jout/shop --evidence-out jout/shop-evidence.json --json`, with a `subset:` block sampling `customers`

**Exit:** 0

**Expected:** The JSON has a `subset` object with kept and total counts per table. Fewer than all `customers` are kept, and every kept `orders` row has its parent.

**Lands with:** main

### CJ-08: Masked outputs are right

**Stage:** mask

**Command:** `decoy run shop --mask-secret env:JOURNEY_SECRET --out-dir jout/shop --evidence-out jout/shop-evidence.json --json`, the CJ-07 run; this step checks its outputs and does not run again

**Exit:** 0

**Expected:** The CSV targets exist. Masked columns differ from the input, passthrough columns match, row counts match the subset, and the input files are unchanged.

**Lands with:** main

### CJ-09: Post-scan the masked output

**Stage:** post-scan

**Command:** `decoy report integrity jout/shop/customers.csv --source data/customers.csv --config shop --allow-source-mismatch --json`

**Exit:** 0

**Expected:** No residual PII finding. The report holds names and counts only.

**Lands with:** main

### CJ-10: Evidence catches a changed file

**Stage:** evidence

**Command:** `decoy report verify jout/shop-evidence.json --json`, then `decoy report verify jout/shop-evidence.json --json` after one byte of `jout/shop/orders.csv` changes

**Exit:** 0, 4

**Expected:** The first run finds every fingerprint matching. The second names the changed file and reports a fingerprint mismatch.

**Lands with:** main

### CJ-11: Vault round trip

**Stage:** vault

**Command:** `decoy run vaulted --mask-secret env:JOURNEY_SECRET --vault jout/vault.bin --out-dir jout/vaulted --json`, then `decoy unmask pipelines/vaulted/pipeline.yaml jout/vaulted/customers.csv --mask-secret env:JOURNEY_SECRET --vault jout/vault.bin -o jout/customers.unmasked.csv --json`

**Exit:** 0, 0

**Expected:** The recovered column equals the input. The test checks this and never prints it.

**Lands with:** main

### CJ-12: Strict delivery

**Stage:** delivery

**Command:** `decoy run shop --mask-secret env:JOURNEY_SECRET --out-dir jout/strict --json`, where `jout/strict/orders.csv` is an existing folder, so the `orders` write fails

**Exit:** 3

**Expected:** No target file of the run is left under `jout/strict/`. The error names the table and a reason code.

**Lands with:** row 61
