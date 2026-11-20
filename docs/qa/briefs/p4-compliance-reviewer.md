# P4 Compliance reviewer charter

Status: current

This is an exploratory test charter for the QA beta program (`docs/qa/beta-program.md`).
Before you start, run `decoy --version`. Keep a plain list of what you tried so the
debrief is easy. Use a fresh `DECOY_HOME` and a fresh output folder for each experiment.

## Persona

You review data handling for a company. You need proof of what was masked and
who can undo it. You are careful and you read every doc page on keys and evidence.

## Mission

Check the evidence records and run `decoy report verify`. Use `report show`,
`render`, `fidelity`, `integrity`, `diff` and `vault`. Try the vault and `decoy unmask` with and
without the vault file and with and without the mask secret. Try `tokenize` and `detokenize`. Read
the post-scan reports. Decide what an auditor can see and what an auditor cannot see, and check
that the docs say the same.

## Time box

2 hours of agent time. Stop when the time is up, even if you are mid-task.

## Corpus items

Items with size tier S and M. Use items with free text, names and emails inside,
heavy nulls and duplicate keys.

Find the item ids in `docs/qa/corpus/manifest.toml`. Use only items that match this list.

## Node

Dell (Linux).

## Debrief questions

Answer these at the end as counts and finding ids only. Put any detail into findings.

- What can an auditor prove from the evidence alone?
- What happens to `unmask` when the vault file or the secret is missing? Was it clear?
- Which report line would you not trust? Why?
- Which promise in the docs could you not check?
- Did any output show something it should have hidden? Describe it by coordinate id only.

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
