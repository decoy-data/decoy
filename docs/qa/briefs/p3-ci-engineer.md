# P3 CI engineer charter

Status: current

This is an exploratory test charter for the QA beta program (`docs/qa/beta-program.md`).
Before you start, run `decoy --version`. Keep a plain list of what you tried so the
debrief is easy. Use a fresh `DECOY_HOME` and a fresh output folder for each experiment.

## Persona

You set up tools for a company's build system. You pin versions, keep secrets
out of logs and treat exit codes as gates. You write down every step so a teammate can repeat it.

## Mission

Set up Decoy the way a company would in CI. Pin the install. Read the mask secret from
the test secret file named by `QA_SECRET_FILE`. It holds a random test secret, never a real one.
Read it only inside your CI steps. Never print it, never put it on a command line and never copy it
into a finding. Run `decoy validate config`, `compile` and `preflight`, then `decoy ci check`.
Use the exit codes as gates. Keep the evidence and result files as artifacts. Write down every
step a company would need, in order, with the exact command. Those notes become the draft of a
"Running Decoy in CI" guide, so write them for a reader who has not seen Decoy. Submit the notes through `findings.py write`,
one finding for each step the docs leave out. Set `confusing = true`, start `actual` with `doc-gap:`
and keep every value out of it.

## Time box

2 hours of agent time. Stop when the time is up, even if you are mid-task.

## Corpus items

Items with size tier S. Use one single table and one parent and child pair. Add
one malformed file so a gate has something to fail on.

Find the item ids in `docs/qa/corpus/manifest.toml`. Use only items that match this list.

## Node

A GitHub-hosted runner in the private sandbox repo, if the owner approved it. If
not, run the same steps as a shell script on a test node.

## Debrief questions

Answer these at the end as counts and finding ids only. Put any detail into findings.

- Which step could a company not guess from the docs?
- Which exit code did you use as a gate? Was its meaning in the docs?
- What did the log show that you did not want in a shared CI log?
- Which artifact would an auditor ask for?
- How long did the setup take from nothing to a passing gate?

## Sandbox rule

Work from the installed release bundle in your home folder. Read only the public docs
folder in your home. Do not read source code, tests or any repository checkout, and do not look
for one. Your shell starts in your own workspace. Stay in it. If you find you can read a checkout, stop and report that as a process finding.

## No-values rule

Never put a cell value, a marker, a secret or a file excerpt in a finding, a message or
a note. Name data by corpus item id, table, column and an opaque coordinate id only. Remove every
value from a config before you write it down. If you are unsure whether a string is a value,
leave it out.

## Submit rule

Submit every finding with `findings.py write`. It is the only way to submit.
Use the field list in `docs/qa/finding-template.toml`. Use only the finding ids the launcher gave
you in `QA_FINDING_IDS`, and use each id once. Cite the doc line that set your expectation, or
name the invariant that failed. Findings go into your inbox (`QA_INBOX`), which only you can read.
Add a repro script that runs in a fresh `DECOY_HOME`. When you
finish, send the coordinator counts and finding ids only.
