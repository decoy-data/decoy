"""The grammar of the Decoy language, version 1 (pipeline settings, sources, targets, masking).

Block structure follows HCL (named blocks in braces); calls take `key: value` options as in Swift
and Kotlin. Keywords are contextual: a column may be called `seed` or `table`, because the lexer
only offers a keyword where the parser can accept one. Any other name can be written in backticks.
"""

from __future__ import annotations

# A keyword must not match the front of a longer word (`in` inside `input`).
_KEYWORDS = (
    "decoy pipeline seed secret ref unconfigured columns let table from to mask with keep in "
    "deterministic vaulted true false"
).split()

GRAMMAR = r"""
start: DECOY NUMBER pipeline

pipeline: PIPELINE [name] "{" item* "}"

?item: seed | secret | unconfigured | let | table

seed: SEED NUMBER
secret: SECRET REF "(" STRING ")"
unconfigured: UNCONFIGURED COLUMNS name
let: LET name "=" treatment

table: TABLE name FROM call TO call "{" statement* "}"

?statement: mask | keep
mask: MASK names WITH treatment
keep: KEEP names
names: name ("," name)*

treatment: call [namespace] [DETERMINISTIC] [VAULTED]
namespace: IN name

call: name [arguments]
arguments: "(" [argument ("," argument)*] ")"
?argument: option | value
option: name ":" value

?value: STRING -> string
      | NUMBER -> number
      | TRUE -> true
      | FALSE -> false
      | name -> word
      | list
list: "[" [value ("," value)*] "]"

name: NAME | QUOTED_NAME

NAME: /[A-Za-z_][A-Za-z0-9_]*/
QUOTED_NAME: /`[^`\n]+`/
STRING: /"([^"\\\n]|\\.)*"/ | /'([^'\\\n]|\\.)*'/
NUMBER: /-?[0-9][0-9_]*(\.[0-9]+)?/
COMMENT: /#[^\n]*/

%import common.WS
%ignore WS
%ignore COMMENT
""" + "\n".join(f"{word.upper()}.2: /{word}(?![A-Za-z0-9_])/" for word in _KEYWORDS)

# How a terminal is named in an error message.
DISPLAY = {
    **{word.upper(): f"`{word}`" for word in _KEYWORDS},
    "NAME": "a name",
    "QUOTED_NAME": "a name",
    "STRING": "a quoted string",
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
    "$END": "the end of the file",
}
