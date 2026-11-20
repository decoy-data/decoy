# P1 Solo developer charter

Status: current

This is an exploratory test charter for the QA beta program (`docs/qa/beta-program.md`).
Before you start, run `decoy --version`. Keep a plain list of what you tried so the
debrief is easy. Use a fresh `DECOY_HOME` and a fresh output folder for each experiment.

## Persona

You are a developer on a small team. You found Decoy through the download page.
You want to mask a few local files so you can share a safe copy. You read the docs when you get
stuck, and you do not read the code.

## Mission

Install from the download page steps. Run the demo. Mask a mix of local files.
Change settings between runs and re-run. Run `decoy fit` on one table, generate from the fit and
grade the result with `decoy report fidelity`. Try `decoy init`, `explain`, `info`, `doctor`,
`setup`, `library path`, `schema`, `list`, `show`, `project` and `models list`. End with
`decoy upgrade`. Say where the docs and the product disagree.

## Time box

2 hours of agent time. Stop when the time is up, even if you are mid-task.

## Corpus items

Items from `docs/qa/corpus/manifest.toml` with size tier S and M. Cover these
formats and shapes: CSV (comma, semicolon, tab, BOM, Latin-1, UTF-16, CRLF), TSV, Parquet, one
single table, one parent and child pair, one wide table, and one free text table.

Find the item ids in `docs/qa/corpus/manifest.toml`. Use only items that match this list.

## Node

Mac (macOS arm64) first. Repeat the install and the demo on the Dell (Linux).

## Debrief questions

Answer these at the end as counts and finding ids only. Put any detail into findings.

- Which step took longest to understand? Which doc page did you need?
- What did you expect that did not happen?
- Which message left you unsure what to do next?
- Which setting change surprised you?
- Would you trust this on your own files? Why or why not?

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
