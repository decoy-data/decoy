# P5 Careless user charter

Status: current

This is an exploratory test charter for the QA beta program (`docs/qa/beta-program.md`).
Before you start, run `decoy --version`. Keep a plain list of what you tried so the
debrief is easy. Use a fresh `DECOY_HOME` and a fresh output folder for each experiment.

## Persona

You are in a hurry and you make mistakes. You mistype flags, pass the wrong
file, forget a secret and press Ctrl-C. You expect the tool to say what went wrong and to leave no
half-written output.

## Mission

Break things on purpose, one at a time. Use wrong flags and wrong file types.
Leave out a required secret. Interrupt a run with Ctrl-C while it writes. Fill the disk, if the
node lets you do it safely. Point output at a read-only folder. Re-run into an existing output
folder. After each mistake, check three things: the exit code, whether the message is clear and
value-free, and whether any partial output looks like a finished result. Also try `init`, `demo`,
`explain` and `validate config` with bad input.

## Time box

2 hours of agent time. Stop when the time is up, even if you are mid-task.

## Corpus items

Items with size tier S. Cover the malformed file for each format, a header-only
file, an empty file, bad dates, and an item with a different encoding than the config says.

Find the item ids in `docs/qa/corpus/manifest.toml`. Use only items that match this list.

## Node

Dell (Linux) and Mac (macOS arm64).

## Debrief questions

Answer these at the end as counts and finding ids only. Put any detail into findings.

- Which mistake gave a message that did not help?
- Which mistake left output that looked finished but was not?
- Did any message show a value from your data? Describe it by coordinate id only.
- Which exit code did not match what the docs say?
- Which recovery step was missing from the docs?

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
