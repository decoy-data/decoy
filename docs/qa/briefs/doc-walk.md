# Doc walk brief

Status: current

You walk the public docs for one feature group. The coordinator tells you the page set. Run it
only when the group is V1 complete.
Before you start, run `decoy --version`. Keep a plain list of what you tried so the
debrief is easy. Use a fresh `DECOY_HOME` and a fresh output folder for each experiment.

## Mission

Read each page in order, as a new user would. Run every command and example exactly as written.
Compare what happens with what the page says. A page that is wrong, missing a step or unclear is
a finding. Mark a finding as confusing when the text is correct but a new user would not
understand it. Cite the page and line for each one.

## Time box

One page set per session. Stop at 2 hours of agent time and report the pages you did not reach.

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
