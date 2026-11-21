"""Every `lang.*` diagnostic of the Decoy language, in one place.

`CODES` maps each public code to a one-line meaning. A `Code` is one fixed message for a code
(a code may have more than one message). Every diagnostic is built from a `Code` through
`_errors.fail` or `_errors.diagnostic`, so a message is written once, holds only words of the
language and the names the caller passes in, and never a config value. No module writes a `lang.`
string or builds a `Diagnostic` itself; `tests/unit/lang/test_codes.py` fails when one does.

This module imports nothing.
"""

from __future__ import annotations


class Code:
    """One public code and one fixed message template. `{name}` fields are filled by the caller."""

    __slots__ = ("code", "message")

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message


CODES: dict[str, str] = {
    "lang.block_arguments": "A statement was given more plain values than it takes",
    "lang.block_repeated": "A statement that may appear once appears twice",
    "lang.column_repeated": "A column has two rules, or two links",
    "lang.config": "The engine refused the compiled pipeline; its own code is in brackets",
    "lang.connector_arguments": "A source or target was given the wrong number of plain values",
    "lang.connector_option_required": "A `csv` source does not say `header: true` or `header: false`; the language has no default",
    "lang.convert": "A YAML pipeline cannot be written as a `.decoy` program; the message names the block or gives the compiler's reason",
    "lang.empty": "The pipeline file has no text",
    "lang.expect_argument": "A check was given a plain value",
    "lang.expression": "An expression cannot be held by the language",
    "lang.format": "Formatting would have changed the program; the file is left alone",
    "lang.format_unknown": "The format of an `s3` or `gcs` object cannot be told from its name",
    "lang.generator_argument": "A generator was given a computed value, or written without its call",
    "lang.generator_arguments": "A generator was given more plain values than it takes",
    "lang.generator_in_masked_table": "A masked table defines a column with a generator",
    "lang.group_too_small": "`{...}` has one column",
    "lang.let_modified": "A `let` name was given options or words",
    "lang.let_repeated": "A `let` name is defined twice",
    "lang.let_shadows_strategy": "A `let` has a strategy's name",
    "lang.link_arity": "The child and parent keys have different numbers of columns",
    "lang.link_needs_namespace": "The parent key has no namespace",
    "lang.link_unknown_column": "The parent table has no rule for that key",
    "lang.link_unknown_table": "The parent table is not in the pipeline",
    "lang.name_empty": "A quoted name is empty",
    "lang.nesting": "Lists, maps or brackets are nested too deeply",
    "lang.not_utf8": "The pipeline file is not UTF-8 text",
    "lang.number": "A number is too large to hold",
    "lang.option_not_allowed": "The option has its own syntax, or is set by the statement itself",
    "lang.option_repeated": "An option or map key is given twice",
    "lang.orphans_missing": "The link does not say what happens to unmatched rows",
    "lang.positional_after_option": "A plain value follows a `key: value`",
    "lang.reference_not_allowed": "A `table.column` was given where the statement takes none",
    "lang.sample_rows": "A row count is not a whole number",
    "lang.seed_missing": "The pipeline has no seed",
    "lang.setting_repeated": "A setting is given twice",
    "lang.strategy_arguments": "A strategy was given more than one plain value",
    "lang.string_escape": "A backslash sequence in double quotes is not one the language reads",
    "lang.subset_condition": "A test uses an operator a subset cannot filter on",
    "lang.syntax": "A word or symbol is not where the language expects one",
    "lang.table_repeated": "Two tables have the same name",
    "lang.unknown_connector": "The source or target is not one the language has",
    "lang.unknown_generator": "The call is not a generator",
    "lang.unknown_strategy": "The name after `:` is not a strategy or a `let`",
    "lang.unprintable_name": "A name has a quote or a line break and cannot be written",
    "lang.unprintable_number": "A number is not finite and cannot be written",
    "lang.unreviewed": "A rule still ends with `?`",
    "lang.version": "The first line is not `decoy 1`",
}

# Codes of the pipeline-file loader (`decoy._config_file`), which reads the bytes before any
# language code can apply and so writes these two itself. It cannot import this module without
# loading the compiler for every YAML file.
LOADER_CODES = frozenset({"lang.empty", "lang.not_utf8"})

NUMBER_TOO_LARGE = Code("lang.number", "this number is too large to hold")
STRING_ESCAPE = Code("lang.string_escape", "this backslash sequence is not one the language reads")
STRING_ESCAPE_HALF = Code("lang.string_escape", "this `\\u` escape is half of a character")
SYNTAX_UNEXPECTED = Code("lang.syntax", "unexpected {found}")
SYNTAX_MAP_IN_EXPRESSION = Code("lang.syntax", "an expression cannot hold a `{{...}}` map")
VERSION = Code("lang.version", "this language version is not supported")
NAME_EMPTY = Code("lang.name_empty", "a name cannot be empty")
NESTING = Code("lang.nesting", "the program is nested too deeply")
SEED_MISSING = Code("lang.seed_missing", "the pipeline has no seed")
SETTING_REPEATED = Code("lang.setting_repeated", "`{setting}` is set twice")
TABLE_REPEATED = Code("lang.table_repeated", "table `{table}` is declared twice")
BLOCK_REPEATED = Code("lang.block_repeated", "`{kind}` is written twice")
BLOCK_REPEATED_NAMESPACE = Code("lang.block_repeated", "namespace `{name}` is declared twice")
BLOCK_REPEATED_LINK = Code("lang.block_repeated", "this link already has a direction")
BLOCK_ARGUMENTS = Code("lang.block_arguments", "`{kind}` takes {count} plain value(s): {takes}")
BLOCK_ARGUMENTS_BUDGET = Code("lang.block_arguments", "`budget` takes `key: value` options only")
REFERENCE_NOT_ALLOWED = Code(
    "lang.reference_not_allowed", "`{kind}` does not take a `table.column`"
)
EXPECT_ARGUMENT = Code("lang.expect_argument", "a check takes columns and settings")
OPTION_NOT_AN_OPTION = Code("lang.option_not_allowed", "`{key}` is not an option")
OPTION_NOT_AS_OPTION = Code("lang.option_not_allowed", "`{key}` is not written as an option")
OPTION_NOT_IN_SETTINGS = Code("lang.option_not_allowed", "`{key}` is not written in `settings`")
OPTION_NOT_IN_OPTIONS = Code("lang.option_not_allowed", "`{key}` is not written in `options`")
OPTION_SET_BY_CONNECTOR = Code("lang.option_not_allowed", "`{key}` is set by `{connector}` itself")
OPTION_REPEATED = Code("lang.option_repeated", "`{key}` is given twice")
OPTION_SET_BY_STATEMENT = Code("lang.option_repeated", "`{key}` is already set by this statement")
MAP_KEY_REPEATED = Code("lang.option_repeated", "a key is given twice in this map")
POSITIONAL_AFTER_OPTION = Code(
    "lang.positional_after_option", "a plain value cannot follow a `key: value` option"
)
UNKNOWN_STRATEGY = Code("lang.unknown_strategy", "`{name}` is not a strategy or a `let` name")
STRATEGY_ARGUMENTS = Code(
    "lang.strategy_arguments", "`{strategy}` takes at most one plain value, the provider"
)
COLUMN_REPEATED = Code(
    "lang.column_repeated", "column `{column}` already has a {what} on line {line}"
)
COLUMN_REPEATED_GENERATED = Code(
    "lang.column_repeated", "column `{column}` is already defined on line {line}"
)
GROUP_TOO_SMALL = Code("lang.group_too_small", "a `{{...}}` group needs at least two columns")
LET_REPEATED = Code("lang.let_repeated", "`{name}` is defined twice")
LET_SHADOWS_STRATEGY = Code(
    "lang.let_shadows_strategy", "`{name}` is a strategy and cannot be reused as a `let` name"
)
LET_MODIFIED = Code("lang.let_modified", "`{name}` is a `let` name and is used as it is")
UNKNOWN_CONNECTOR = Code(
    "lang.unknown_connector", "`{connector}` is not a {role} this version of the language can write"
)
CONNECTOR_OPTION_REQUIRED = Code(
    "lang.connector_option_required",
    "`{connector}` as a source must say `{written}: true` or `{written}: false`",
)
CONNECTOR_ARGUMENTS = Code(
    "lang.connector_arguments", "`{connector}` takes {count} plain value(s): {wanted}"
)
FORMAT_UNKNOWN = Code(
    "lang.format_unknown", "cannot tell the file format of this {role} from its name"
)
GENERATOR_IN_MASKED_TABLE = Code(
    "lang.generator_in_masked_table", "a masked table can only define a column from an expression"
)
GENERATOR_IN_MASKED_TABLE_CALL = Code(
    "lang.generator_in_masked_table",
    "`{called}` is a generator; a masked table can only define a column from an expression",
)
LINK_UNKNOWN_TABLE = Code("lang.link_unknown_table", "`{parent}` is not a table of this pipeline")
LINK_UNKNOWN_COLUMN = Code(
    "lang.link_unknown_column", "table `{parent}` has no rule for column `{column}`"
)
LINK_ARITY = Code("lang.link_arity", "{columns} column(s) cannot follow a key of {keys} column(s)")
LINK_NEEDS_NAMESPACE = Code(
    "lang.link_needs_namespace", "the parent key `{parent}.{key}` has no namespace"
)
ORPHANS_MISSING = Code(
    "lang.orphans_missing", "this link does not say what happens to rows with no matching parent"
)
UNKNOWN_GENERATOR = Code("lang.unknown_generator", "`{word}` is not a generator")
GENERATOR_ARGUMENTS = Code(
    "lang.generator_arguments", "`{kind}` takes at most {count} plain value(s): {takes}"
)
GENERATOR_ARGUMENT_BARE = Code(
    "lang.generator_argument", "`{word}` is a generator and is written as a call with plain values"
)
GENERATOR_ARGUMENT_OPTIONS = Code(
    "lang.generator_argument", "`key: value` options and `{{...}}` maps belong to a generator call"
)
GENERATOR_ARGUMENT_VALUES = Code(
    "lang.generator_argument",
    "a generator takes plain values: numbers, text, words, lists and maps",
)
SAMPLE_ROWS = Code("lang.sample_rows", "a row count is a whole number")
SUBSET_CONDITION = Code(
    "lang.subset_condition", "`{operator}` is not a comparison a subset can filter on"
)
CONFIG = Code("lang.config", "{text}")
EXPRESSION = Code("lang.expression", "this expression cannot be written in the language")
UNREVIEWED = Code("lang.unreviewed", "this rule was inferred and has not been reviewed")
FORMAT = Code("lang.format", "formatting would change this program; the file is left as it is")
CONVERT_MAP_KEY = Code("lang.convert", "a map key that is not text cannot be written")
CONVERT_VALUE_NULL = Code("lang.convert", "a null or non-finite value cannot be written")
CONVERT_VALUE_KIND = Code("lang.convert", "this kind of value cannot be written")
CONVERT_EXPRESSION_TEXT = Code("lang.convert", "an expression must be text")
CONVERT_EXPRESSION = Code("lang.convert", "this expression cannot be written in the language")
CONVERT_EXPRESSION_CHANGED = Code(
    "lang.convert",
    "this expression holds a comment or a number spelling the language does not keep",
)
CONVERT_NO_CONNECTOR = Code(
    "lang.convert", "this kind of source or target has no connector in the language"
)
CONVERT_PROVIDER_CLASH = Code(
    "lang.convert", "a provider option with the name of a column setting cannot be written"
)
CONVERT_SORT_DIRECTIONS = Code("lang.convert", "a sort needs one direction for each key")
CONVERT_NEEDS_SOURCE_TARGET = Code(
    "lang.convert", "a masked table needs both a source and a target"
)
CONVERT_GENERATED_TABLE = Code(
    "lang.convert", "a generated table needs a target and takes no transforms"
)
CONVERT_SETTING_ONE_VALUE = Code("lang.convert", "this setting has one value in the language")
CONVERT_NAMESPACE = Code("lang.convert", "a namespace is declared for `table.column` names")
CONVERT_SEED_KIND = Code("lang.convert", "a subset seed of this kind cannot be written")
CONVERT_TEST_KIND = Code("lang.convert", "a test of this kind cannot be written")
CONVERT_TEST_SHAPE = Code("lang.convert", "this test cannot be written")
CONVERT_EDGE = Code("lang.convert", "an edge is `parent.key -> child.key`")
CONVERT_VERSION = Code("lang.convert", "only config version {version} can be converted")
CONVERT_STRAY = Code("lang.convert", "this entry is for a table that is not declared")
CONVERT_INVALID = Code("lang.convert", "the config does not validate")
CONVERT_LANGUAGE = Code("lang.convert", "the language cannot write this config: {reason}")
CONVERT_NESTING = Code("lang.convert", "the config is nested too deeply to write")
CONVERT_SHAPE = Code("lang.convert", "the config has a shape this writer cannot read")
CONVERT_DIFFERS = Code("lang.convert", "the program for this would not compile back to it")
UNPRINTABLE_NAME_EMPTY = Code("lang.unprintable_name", "a name cannot be empty")
UNPRINTABLE_NAME_CHARS = Code(
    "lang.unprintable_name", "a name with a quote or a line break cannot be written"
)
UNPRINTABLE_NUMBER = Code(
    "lang.unprintable_number", "a number that is not finite cannot be written"
)

DESCRIPTORS: tuple[Code, ...] = (
    NUMBER_TOO_LARGE,
    STRING_ESCAPE,
    STRING_ESCAPE_HALF,
    SYNTAX_UNEXPECTED,
    SYNTAX_MAP_IN_EXPRESSION,
    VERSION,
    NAME_EMPTY,
    NESTING,
    SEED_MISSING,
    SETTING_REPEATED,
    TABLE_REPEATED,
    BLOCK_REPEATED,
    BLOCK_REPEATED_NAMESPACE,
    BLOCK_REPEATED_LINK,
    BLOCK_ARGUMENTS,
    BLOCK_ARGUMENTS_BUDGET,
    REFERENCE_NOT_ALLOWED,
    EXPECT_ARGUMENT,
    OPTION_NOT_AN_OPTION,
    OPTION_NOT_AS_OPTION,
    OPTION_NOT_IN_SETTINGS,
    OPTION_NOT_IN_OPTIONS,
    OPTION_SET_BY_CONNECTOR,
    OPTION_REPEATED,
    OPTION_SET_BY_STATEMENT,
    MAP_KEY_REPEATED,
    POSITIONAL_AFTER_OPTION,
    UNKNOWN_STRATEGY,
    STRATEGY_ARGUMENTS,
    COLUMN_REPEATED,
    COLUMN_REPEATED_GENERATED,
    GROUP_TOO_SMALL,
    LET_REPEATED,
    LET_SHADOWS_STRATEGY,
    LET_MODIFIED,
    UNKNOWN_CONNECTOR,
    CONNECTOR_OPTION_REQUIRED,
    CONNECTOR_ARGUMENTS,
    FORMAT_UNKNOWN,
    GENERATOR_IN_MASKED_TABLE,
    GENERATOR_IN_MASKED_TABLE_CALL,
    LINK_UNKNOWN_TABLE,
    LINK_UNKNOWN_COLUMN,
    LINK_ARITY,
    LINK_NEEDS_NAMESPACE,
    ORPHANS_MISSING,
    UNKNOWN_GENERATOR,
    GENERATOR_ARGUMENTS,
    GENERATOR_ARGUMENT_BARE,
    GENERATOR_ARGUMENT_OPTIONS,
    GENERATOR_ARGUMENT_VALUES,
    SAMPLE_ROWS,
    SUBSET_CONDITION,
    CONFIG,
    EXPRESSION,
    UNREVIEWED,
    FORMAT,
    CONVERT_MAP_KEY,
    CONVERT_VALUE_NULL,
    CONVERT_VALUE_KIND,
    CONVERT_EXPRESSION_TEXT,
    CONVERT_EXPRESSION,
    CONVERT_EXPRESSION_CHANGED,
    CONVERT_NO_CONNECTOR,
    CONVERT_PROVIDER_CLASH,
    CONVERT_SORT_DIRECTIONS,
    CONVERT_NEEDS_SOURCE_TARGET,
    CONVERT_GENERATED_TABLE,
    CONVERT_SETTING_ONE_VALUE,
    CONVERT_NAMESPACE,
    CONVERT_SEED_KIND,
    CONVERT_TEST_KIND,
    CONVERT_TEST_SHAPE,
    CONVERT_EDGE,
    CONVERT_VERSION,
    CONVERT_STRAY,
    CONVERT_INVALID,
    CONVERT_LANGUAGE,
    CONVERT_NESTING,
    CONVERT_SHAPE,
    CONVERT_DIFFERS,
    UNPRINTABLE_NAME_EMPTY,
    UNPRINTABLE_NAME_CHARS,
    UNPRINTABLE_NUMBER,
)
