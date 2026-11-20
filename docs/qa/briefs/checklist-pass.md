# Checklist pass brief

Status: current

You run one feature group of the CLI checklist (`docs/qa/cli-v1-checklist.md`). The coordinator
tells you the group. Run it only when the group is V1 complete.
Before you start, run `decoy --version`. Keep a plain list of what you tried so the
debrief is easy. Use a fresh `DECOY_HOME` and a fresh output folder for each experiment.

## Mission

Run every check in your group, in order, from the installed bundle. For each check, run the
command as written, compare the exit code and the output with the expected result, and mark it
pass, fail or not run. A failed check is a finding. Also apply the shared invariants from
`docs/qa/beta-program.md` to each run you make. Do not skip a check. Do not run another group.

## Time box

One group per session. Stop at 2 hours of agent time and report which checks are not run.

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
