# 1. A first pipeline

Status: current

```decoy
decoy 1

pipeline people_export {
  seed 42

  mask people from csv("people.csv", header: true) to csv("out/people.csv") {
    email : faker(person_email)
    ssn   : redact
    keep id, signup_date
  }
}
```

Reading it top to bottom:

- `decoy 1` is the language version. It is always the first line.
- `pipeline people_export { }` holds everything. The name is optional.
- `seed 42` makes a run repeatable: the same seed and input give the same output.
- `mask people from ... to ...` reads one table, masks it and writes it. `people` is the table's
  name in the pipeline.
- Inside, each line is a rule: a column, a colon, and what to do with it. `keep` leaves columns
  as they are. Every column of the file needs a rule or a `keep`.

Layout is free. Spaces and line breaks only separate words, so indentation can never break a file.
Comments start with `#`.

## Running a file

Every `decoy` command that takes a pipeline file takes a `.decoy` file:

```
decoy validate pipeline.decoy
decoy run pipeline.decoy
```

Converting a YAML pipeline and formatting a `.decoy` file are not available from the command
line yet.

A mistake is reported with its line and column, a code, and usually a hint:

```
error: Invalid config: lang.unknown_strategy: line 10, column 18: `redcat` is not a strategy or a `let` name
  hint: did you mean `redact`?
```

`decoy validate --json` carries the same text in each message, with the hint in a `hint` member.

The command decides the kind of a file from the name you type, not from where a symbolic link
points: `pipeline.decoy` is read as `.decoy` even when it links to a `.yaml` file, and the other
way round.

An error never shows a value from your file, only names of the language, strategies, tables and
columns.

## Values

| Written | Is |
|---|---|
| `42`, `1_000_000`, `2.5`, `1e-6` | A number |
| `true`, `false` | A boolean |
| `digits` | A word: the same as `"digits"` |
| `"out/people.csv"` | Text, with the JSON escapes (`\n`, `\"`, `\\`) |
| `'C:\data\people.csv'` | Text taken exactly as written |
| `[zip5, zip3, state]` | A list |
| `{min: 1, max: 9}` | A map |

A table or column name that is a word of the language, or has a space in it, goes in single
quotes: `'First Name' : redact`.
