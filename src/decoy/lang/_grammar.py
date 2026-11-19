"""The grammar of the Decoy language, version 1 (pipeline settings, sources, targets, masking).

Block structure follows HCL (named blocks in braces); calls take `key: value` options as in Swift
and Kotlin. Keywords are contextual: a column may be called `seed` or `table`, because the lexer
only offers a keyword where the parser can accept one. Inside a table that leaves a few reserved
words (the statement words `keep`, `where`, `sort`, `limit`, `dedupe`, `drop`, the rule words `in`,
`deterministic`, `vaulted`, `when`, and inside an expression `and`, `or`, `not`, `if`, `else`); a
column with one of those names, or with a space in it, is written in single quotes. Where a value is expected, single and double quotes
both give a string.

Layout is free: spaces and line breaks only separate words, as in JSON or C.
"""

from __future__ import annotations

# A keyword must not match the front of a longer word (`in` inside `input`).
_KEYWORDS = (
    "decoy pipeline seed secret ref unconfigured columns let table from to keep in "
    "deterministic vaulted when and or not if else true false "
    "where sort by asc desc limit dedupe on drop orphans"
).split()

GRAMMAR = r"""
start: DECOY NUMBER pipeline

pipeline: PIPELINE [name] "{" item* "}"

?item: seed | secret | unconfigured | let | table

seed: SEED NUMBER
secret: SECRET REF "(" (DQ_STRING | SQ_STRING) ")"
unconfigured: UNCONFIGURED COLUMNS name
let: LET name "=" treatment

table: TABLE name FROM call TO call "{" statement* "}"

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
?primary: NUMBER | DQ_STRING | SQ_STRING | NAME | e_call | e_group | e_list
!e_call: (NAME | IF) "(" [e_argument ("," e_argument)*] ")"
?e_argument: expression | e_option
e_option: NAME ":" expression
e_group: "(" expression ")"
e_list: "[" [expression ("," expression)*] "]"

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

NAME: /[A-Za-z_][A-Za-z0-9_]*/
DQ_STRING: /"([^"\\\n]|\\.)*"/
SQ_STRING: /'([^'\\\n]|\\.)*'/
NUMBER: /-?[0-9][0-9_]*(\.[0-9]+)?/
OPERATOR: "==" | "!=" | "<=" | ">=" | "<" | ">" | "+" | "*" | "//" | "/"
MINUS: "-"
ARROW: "<-"
COMMENT: /#[^\n]*/

%import common.WS
%ignore WS
%ignore COMMENT
""" + "\n".join(f"{word.upper()}.2: /{word}(?![A-Za-z0-9_])/" for word in _KEYWORDS)

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
    "DOT": "`.`",
    "$END": "the end of the file",
}
