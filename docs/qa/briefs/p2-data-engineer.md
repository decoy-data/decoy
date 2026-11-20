# P2 Data engineer charter

Status: current

This is an exploratory test charter for the QA beta program (`docs/qa/beta-program.md`).
Before you start, run `decoy --version`. Keep a plain list of what you tried so the
debrief is easy. Use a fresh `DECOY_HOME` and a fresh output folder for each experiment.

## Persona

You run data pipelines for a mid-size company. You care about speed, memory and
foreign keys. You expect exact answers from the docs.

## Mission

Use a DuckDB source. Subset a three-level FK chain and check that child rows still
join. Run chunked and native runs on M and L items. Scan a new source with `decoy scan`, then use
`scan fields`, `scan show` and `scan diff`. Try `library fsck`, `diff`, `ref`, `prune`, `clean`
and `export`. Use connector sources and targets only for groups the coordinator says are closed.
Record peak memory and wall time for each run.

## Time box

2 hours of agent time. Stop when the time is up, even if you are mid-task.

## Corpus items

Items with size tier M and L. Cover a DuckDB database, a three-level FK chain, a
self-reference, a composite key, a cycle (the docs refuse it in V1), a parent and child pair with
orphans, and a Parquet item with dictionary encoding.

Find the item ids in `docs/qa/corpus/manifest.toml`. Use only items that match this list.

## Node

Dell (Linux). Run size tier L only here or on a GCP test node, never on the devbox.

## Debrief questions

Answer these at the end as counts and finding ids only. Put any detail into findings.

- Which run was slower or larger than the docs led you to expect?
- Did any run give a different result when you ran it twice with the same inputs?
- Which flag combination did the product refuse? Was the reason clear and in the docs?
- Where did child rows lose their parent?
- What would you need to see in a scan before you trusted it?

## Sandbox rule

Work from the installed release bundle in your home folder. Read only the public docs
folder in your home. Do not read source code, tests or any repository checkout, and do not look
for one. If you find you can read a checkout, stop and report that as a process finding.

## No-values rule

Never put a cell value, a marker, a secret or a file excerpt in a finding, a message or
a note. Name data by corpus item id, table, column and an opaque coordinate id only. Remove every
value from a config before you write it down. If you are unsure whether a string is a value,
leave it out.

## Submit rule

Submit every finding with `findings.py write`. It is the only way to submit.
Use the field list in `docs/qa/finding-template.toml`. Use only the finding ids the launcher gave
you in `QA_FINDING_IDS`, and use each id once. Cite the doc line that set your expectation, or
name the invariant that failed. Add a repro script that runs in a fresh `DECOY_HOME`. When you
finish, send the coordinator counts and finding ids only.
