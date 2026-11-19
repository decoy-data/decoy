Status: record

# Decoy language agent trial (milestone 6)

Date: 2026-11-19. Plan: [../plans/2026-11-19-decoy-language-completion.md](../plans/2026-11-19-decoy-language-completion.md).

## Question

Does a coding agent get a pipeline right on the first attempt more often in `.decoy` than in YAML?

## Result

| | `.decoy` | YAML |
|---|---|---|
| Files that validate, of 20 | 20 | 20 |
| Files that validate and do what the task asked, of 20 | 20 | 19 |
| Lines written, all 20 files | 243 | 678 |
| Reference material given | one page, 9.5 KB | 15 files, 220 KB |

**The trial does not show that `.decoy` is more often valid.** Both agents produced 20 valid files.
The one YAML miss (task 15) guessed a provider name that does not exist; the engine does not check
provider names when it validates a config, so the file validated and would have failed at run. One
task is not a difference to rely on.

What the trial does show: the same correctness from a reference 23 times smaller, in about a third
of the lines. Where the YAML agent was unsure, it was about names it could not find in 220 KB of
reference (the composite provider, the vault flag, whether `from_parent` is usable). Where the
`.decoy` agent was unsure, it was about option names the one page did not list (`truncate`'s
`length`), which the page now gives.

So the plan's bar "more often valid in `.decoy`" is **not met as worded**. The case for the
language rests on size, readability and the smaller reference, not on a validity gap, at least for
a capable agent that is given the full documentation.

## Method

- Twenty tasks, below, from one masked CSV to three tables with foreign keys, a subset and checks.
- Two fresh agents of the same model, one per format, each closed-book and first-attempt: no code,
  compiler or validator could be run, and nothing outside the given reference could be read.
- The `.decoy` agent had `docs/guides/decoy-language/agent-card.md` as it stood at commit
  `074d4f0`. The YAML agent had the engine's `recipes.md`, `strategies.md` and `relationships.md`,
  the eleven bundled templates and the config JSON schema.
- Grading was automatic. Valid: `compile_text` succeeds, or `parse_pipeline_config` accepts the
  YAML. Does what was asked: a per-task check on the resulting config (the strategies, namespaces,
  options, shaping steps and relationships the task names). The same checks ran on both formats.
  Reference answers written beforehand scored 20 of 20.

## Limits

- One run of each arm, one model, twenty tasks. No repeat, no variance estimate.
- "Valid" is config validation. Neither format was compiled to a plan or run, so a wrong provider
  name or an expression the engine refuses later counts as valid in both.
- Both agents were stopped by a container restart before writing any file and resumed from their
  saved transcripts, so the time and token figures of the two runs are not comparable and are not
  reported.
- The YAML agent's first directory listing showed the names of the other trial folders; it reported
  that it did not open them.
- The task wording uses the engine's vocabulary (`hash`, `namespace`, "format-preserving"), which
  helps both formats equally and may hide a difference a less guided task would show.
- The tasks, the grader and the reference answers were written by the author of the language.

## A harder trial, if one is wanted

A weaker model, a YAML reference cut to the same size as the one page, tasks described in user
terms rather than engine terms, and several runs per arm would each test the claim more severely.

## Tasks

Write one pipeline definition per task. Use seed 11 in every pipeline unless the task says otherwise. Paths are relative.

1. Mask `people.csv` (CSV with a header) into `out/people.csv`. Replace `email` with a fake email, redact `ssn`, and leave `id` unchanged.
2. Mask `transactions.parquet` into `out/transactions.parquet`. Apply format-preserving encryption over digits to `card_number` in the namespace `cards`, redact `cvv`, leave `amount` unchanged.
3. Mask `members.csv`, a pipe-delimited CSV with a header, into `out/members.parquet`. Hash `member_id` in the namespace `members`; replace `name` with a fake person name.
4. Mask `users.csv` into `out/users.csv`. Before masking, drop every row whose `status` is `TEST`. Replace `email` with a fake email; leave `status` unchanged.
5. Mask `staff.csv` into `out/staff.csv`. Add a new column `full_name` computed as first_name, a space, last_name; then replace `full_name` with a fake person name and redact `first_name` and `last_name`.
6. Mask two tables: `customers.csv` into `out/customers.csv` and `orders.csv` into `out/orders.csv`. Hash `customers.customer_id` in the namespace `customer_ids`. `orders.customer_id` is a foreign key to `customers.customer_id` and must keep the join; the run must fail if an order has no matching customer. Leave `orders.total` unchanged.
7. Mask `patients.csv` into `out/patients.csv`. Shift `dob` and `admitted` by a random number of days between -30 and 30, both in the namespace `patient_dates`. Redact `name`.
8. Mask `accounts.csv` into `out/accounts.csv`. Redact `ssn` only for rows where `country` equals `US`. Leave `country` unchanged.
9. Generate a table `customers` with 500 rows into `customers.csv`: `id` is a sequence starting at 1000, `first_name` is a fake first name, and `tier` is one of Bronze (50%), Silver (30%), Gold (20%).
10. Generate two tables: `customers` with 100 rows into `customers.csv` (`id` sequence from 1) and `orders` with 400 rows into `orders.csv` (`order_id` sequence from 1, and `customer_id` drawn from `customers.id`).
11. Mask `signups.csv` into `out/signups.csv`. Before masking: sort by `signup_date` descending, keep only the first 1000 rows, and drop the column `internal_notes`. Replace `email` with a fake email; leave `signup_date` unchanged.
12. Mask a Parquet file on S3 (bucket `acme-landing`, key `raw/claims.parquet`, credentials reference `phi-readonly`) into the local file `out/claims.parquet`. Hash `claim_id` in the namespace `claims`; leave `amount` unchanged.
13. Mask `employees.csv` into `out/employees.csv`. Truncate `postal_code` to 3 characters and shuffle `salary`.
14. Mask `ledger.csv` into `out/ledger.csv`. Replace `account` with a synthetic account number, consistently (the same input always gives the same output) in the namespace `accounts`, and record the mapping in the token vault so it can be reversed. Leave `balance` unchanged.
15. Mask `contacts.csv` into `out/contacts.csv`. Replace `first_name`, `last_name` and `email` together so that they stay consistent with each other within a row, using the composite name-and-email provider.
16. Mask `events.csv` into `out/events.csv`, redacting `payload` and leaving `event_id` unchanged. Turn on post-validation, and make pool exhaustion fail the run.
17. Mask `customers.csv` into `out/customers.csv` and `orders.csv` into `out/orders.csv`, keeping only a referentially intact 5% sample of customers chosen by `customer_id`. Hash `customers.customer_id` in the namespace `customer_ids`; `orders.customer_id` is a foreign key to it (unmatched orders keep their value). Leave `orders.total` unchanged.
18. Mask `customers.csv` into `out/customers.csv`, replacing `email` with a fake email. Add a leak check on `customers.email`, and quarantine failing rows to `out/quarantine.jsonl` when validation fails.
19. Mask `survey.csv` into `out/survey.csv`. Redact the column named `First Name` (with a space) and the column named `limit`.
20. Mask three tables, each a CSV into `out/<name>.csv`: `customers`, `orders`, `order_lines`. Hash `customers.customer_id` in namespace `customer_ids` and `orders.order_id` in namespace `order_ids`. `orders.customer_id` references `customers.customer_id` (unmatched rows keep their value) and `order_lines.order_id` references `orders.order_id` (the run fails on an unmatched row). Leave `order_lines.sku` unchanged.
