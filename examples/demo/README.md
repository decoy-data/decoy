# 15-minute demo kit

One story: give developers a safe copy of customers and orders. The data is
fictional: 200 customers with SSNs, Luhn-valid card numbers and free-text notes,
and 800 orders. `python3 make_data.py sample-data` rebuilds it (seed 7).

Every step below was run in this order on CLI 0.1.0 and engine 0.27.0 with the
certified pins. The exit code after each step is the one to expect.

## Before you start

Run from this folder, with the signed bundle installed:

```sh
export DECOY_MASK_SECRET=$(openssl rand -hex 32)
mkdir -p evidence   # --evidence-out does not create its folder
decoy doctor
```

## Run sheet

| Time | Show | Command | Exit |
| --- | --- | --- | --- |
| 0:00 | The problem | open `sample-data/customers.csv` | |
| 1:30 | Find the PII | `decoy scan sample-data/customers.csv --has-header` | 0 |
| 3:30 | Starter config | `decoy init sample-data/customers.csv --output starter.yaml` | 0 |
| 4:30 | The real pipeline | `decoy validate pipeline.yaml` then `decoy run pipeline.yaml --evidence-out evidence/run1.json` | 0 |
| 7:30 | Joins survive | `head out/pipeline/current/out/orders.csv` | |
| 8:30 | Same input, same output | `decoy run pipeline.yaml --evidence-out evidence/run2.json` then `decoy report diff evidence/run1.json evidence/run2.json` | 0 |
| 9:30 | A forgotten column | `decoy run forgot_notes.yaml` | 1 |
| 10:15 | A leak caught | `decoy run leaky.yaml` then `decoy report integrity out/leaky/current/out/customers.csv --source sample-data/customers.csv` | 0, then 4 |
| 11:00 | Synthetic data | `decoy run ../generate_example.yaml --rows 5` | 0 |
| 12:30 | CI and audit | `decoy ci check .decoy-ci.yaml` and `decoy report verify evidence/run1.json` | 0 |

`.decoy-ci.yaml` checks `evidence/run1.json`, so run the 4:30 step first.

## Watch out

- Use the signed bundle. An unpinned `pip install` pulls DuckDB 2.0, and the FK
  gate then fails with "A Post-scan check raised before producing a result".
- Keep `hash` IDs full length. Truncated hashes match the MRN detector, and the
  strict gate withholds a correct run.
- Show `forgot_notes.yaml` with `decoy run`. `decoy validate` reports it as
  "internal error (PipelineValidationError)".
- The in-run gate trusts an explicit `passthrough`, so `leaky.yaml` exits 0. The
  leak shows in `decoy report integrity` without `--config`.
- `decoy init --preset generate` gives poor first output (lorem-ipsum IDs,
  negative amounts). Use `../generate_example.yaml`.
- `--evidence-out` must point outside the `out/` folder.

Generated files (`out/`, `evidence/`, `starter.yaml`) are not part of the kit.
