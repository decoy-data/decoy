"""The grammar of the Decoy language, version 1 (pipeline settings, sources, targets, masking).

Block structure follows HCL (named blocks in braces); calls take `key: value` options as in Swift
and Kotlin. Keywords are contextual: a column may be called `seed` or `mask`, because the lexer
only offers a keyword where the parser can accept one. Inside a table that leaves the words
that start or continue a statement there (`keep`, `where`, `sort`, `limit`, `dedupe`, `drop`, `in`,
`deterministic`, `vaulted`, `when`, `orphans`, `on`, `asc`, `desc`, and inside an expression `and`,
`or`, `not`, `if`, `else`); a column with one of those names, or with a space in it, is written in
single quotes. Text in single quotes is taken as written; text in double quotes takes the JSON
escapes.

Layout is free: spaces and line breaks only separate words, as in JSON or C.
"""

from __future__ import annotations

# A keyword must not match the front of a longer word (`in` inside `input`).
_KEYWORDS = (
    "decoy pipeline seed secret ref unconfigured columns let mask from to keep in "
    "deterministic vaulted when and or not if else true false "
    "where sort by asc desc limit dedupe on drop orphans generate rows unique "
    "settings options scan before after expect quarantine baseline delivery namespace for "
    "subset start sample keys follow budget allow dangling is null"
).split()

NAME_PATTERN = "[A-Za-z_][A-Za-z0-9_]*"

GRAMMAR = (
    r"""
start: DECOY NUMBER pipeline

pipeline: PIPELINE [name] "{" item* "}"

?item: seed | secret | unconfigured | settings | options | let | table | generate
     | scan | expect | block | declare | subset

seed: SEED NUMBER
secret: SECRET REF "(" (DQ_STRING | SQ_STRING) ")"
unconfigured: UNCONFIGURED COLUMNS name
let: LET name "=" treatment

// `settings` holds any pipeline setting by its engine name. `options` is the escape hatch: any
// top-level config block that has no syntax of its own yet, written as plain values.
settings: SETTINGS "{" (pair ","?)* "}"
options: OPTIONS "{" (pair ","?)* "}"

table: MASK name FROM call TO call "{" statement* "}"

// Checks and safety. Each is a word and call-style arguments; `table.column` names a column.
scan: SCAN (BEFORE | AFTER) [check_args]
expect: EXPECT name [check_args]
block: (QUARANTINE | BASELINE | DELIVERY) check_args
declare: NAMESPACE name FOR ref ("," ref)*
check_args: "(" [check_arg ("," check_arg)*] ")"
?check_arg: option | ref | value
ref: name "." name

// Subsetting: where the slice starts, which links it follows, and how far it may grow.
subset: SUBSET "{" subset_statement* "}"
?subset_statement: subset_seed | follow | budget | dangling
subset_seed: START name (sample | filter | keys)
sample: SAMPLE NUMBER (PERCENT_SIGN | ROWS) BY names
filter: WHERE test ("," test)*
// `column`, not `name`: LALR gives every use of one rule the same lookahead set, and a name
// followed by an operator here would make `<` a possible token after any name, ahead of `<-`.
test: column OPERATOR value -> compare
    | column IN list -> member
    | column IS NULL -> is_null
    | column IS NOT NULL -> is_not_null
column: NAME | SQ_STRING
keys: KEYS names IN list
follow: FOLLOW edge_end ARROW_RIGHT edge_end name
edge_end: name "." link_key
budget: BUDGET check_args
dangling: ALLOW DANGLING

// A generated table: every column is defined with `=`, by a generator call or an expression.
generate: GENERATE name ROWS NUMBER TO call "{" gen_statement* "}"
?gen_statement: define | gen_link | unique
gen_link: name ARROW name "." name
unique: UNIQUE "(" names ")"

?statement: mask | group | link | keep | where | define | sort | limit | dedupe | drop
mask: names ":" treatment
keep: KEEP names

// `{a, b} : rule` keeps the columns consistent with each other within a row.
group: "{" names "}" ":" treatment

// `child <- parent_table.key`: the child columns take the parent key's masked values.
link: names ARROW name "." link_key [namespace] [orphans]
link_key: name | "(" names ")"
orphans: ORPHANS name
names: name ("," name)*

// Table shaping. These run before masking, in the order written.
where: WHERE expression
define: name "=" expression
sort: SORT BY sort_key ("," sort_key)*
sort_key: name [ASC | DESC]
limit: LIMIT NUMBER
dedupe: DEDUPE [ON names]
drop: DROP names

treatment: call [namespace] [DETERMINISTIC] [VAULTED] [condition]
namespace: IN name
condition: WHEN expression

// Expressions are only delimited here, not given a meaning: any run of operands and operators
// parses, and the engine's closed grammars decide what is valid where.
expression: operand (operator operand)*
!operator: OPERATOR | MINUS | AND | OR | IN | NOT IN | IF | ELSE
operand: prefix* primary
!prefix: NOT | MINUS
?primary: NUMBER | DQ_STRING | SQ_STRING | NAME | e_call | e_group | e_list | e_map
!e_call: (NAME | IF) "(" [e_argument ("," e_argument)*] ")"
?e_argument: expression | e_option
e_option: (NAME | SQ_STRING) ":" expression
e_group: "(" expression ")"
e_list: "[" [expression ("," expression)*] "]"
// Maps and `key: value` arguments only occur in generator calls; an expression has neither.
e_map: "{" [e_pair ("," e_pair)*] "}"
e_pair: (NAME | DQ_STRING | SQ_STRING) ":" expression

call: name [arguments]
arguments: "(" [argument ("," argument)*] ")"
?argument: option | value
option: name ":" value

?value: (DQ_STRING | SQ_STRING) -> string
      | NUMBER -> number
      | TRUE -> true
      | FALSE -> false
      | NAME -> word
      | list
      | map
list: "[" [value ("," value)*] "]"
map: "{" [pair ("," pair)*] "}"
pair: (NAME | DQ_STRING | SQ_STRING) ":" value

name: NAME | SQ_STRING

NAME: /NAME_PATTERN_HERE/
DQ_STRING: /"([^"\\\n]|\\.)*"/
SQ_STRING: /'[^'\n]*'/
NUMBER: /-?[0-9][0-9_]*(\.[0-9]+)?([eE][+-]?[0-9]+)?/
OPERATOR: "==" | "!=" | "<=" | ">=" | "<" | ">" | "+" | "*" | "//" | "/"
MINUS: "-"
ARROW: "<-"
ARROW_RIGHT: "->"
PERCENT_SIGN: "%"
COMMENT: /#[^\n]*/

%import common.WS
%ignore WS
%ignore COMMENT
""".replace("NAME_PATTERN_HERE", NAME_PATTERN)
    + "\n".join(f"{word.upper()}.2: /{word}(?![A-Za-z0-9_])/" for word in _KEYWORDS)
)

KEYWORD_TERMINALS = frozenset(word.upper() for word in _KEYWORDS)

# How a terminal is named in an error message.
DISPLAY = {
    **{word.upper(): f"`{word}`" for word in _KEYWORDS},
    "NAME": "a name",
    "DQ_STRING": "a quoted string",
    "SQ_STRING": "a 'quoted' name or string",
    "NUMBER": "a number",
    "LBRACE": "`{`",
    "RBRACE": "`}`",
    "LPAR": "`(`",
    "RPAR": "`)`",
    "LSQB": "`[`",
    "RSQB": "`]`",
    "COMMA": "`,`",
    "COLON": "`:`",
    "EQUAL": "`=`",
    "OPERATOR": "an operator",
    "MINUS": "`-`",
    "ARROW": "`<-`",
    "ARROW_RIGHT": "`->`",
    "PERCENT_SIGN": "`%`",
    "DOT": "`.`",
    "$END": "the end of the file",
}
