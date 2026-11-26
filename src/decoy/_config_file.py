"""The one reader of a user's pipeline file, `.yaml`, `.yml` or `.decoy`.

Eleven commands read the same YAML with their own except lists, and a file that was not UTF-8
reached the crash guard from six of them. Every command now loads through here, so a file that
cannot be read as a pipeline gets one code and one text on every surface. `load_pipeline` is the
choke point: it picks the kind from the file name and returns the same `PipelineFile` for both.

A YAML file fails in one of these steps:

| Step | Failure | Code |
|---|---|---|
| read the bytes | `OSError` | none: re-raised as it is (the environment failed, not the config) |
| strict UTF-8 decode | `UnicodeDecodeError` | `yaml.not_utf8` |
| `yaml.safe_load` | `YAMLError` | `yaml.parse_error` |
| empty document | `None` | `yaml.empty` |
| not a mapping | any non-`dict` | `yaml.not_mapping` |

A `.decoy` file has `lang.not_utf8` and `lang.empty` for the first and third steps, then the
language's own `lang.*` problems, one `ConfigProblem` each. A rule still marked `?` is not a
failure of the load: `PipelineFile.unreviewed` holds the marks, and `load_config_mapping` (for a
command that only needs the mapping) refuses a file that has any.

The file is opened once and the parser sees those bytes, so nothing re-opens the path after the
checks. A `ConfigFileError` is raised after the handler that caught the decode or parse failure
has closed, so it carries no `__context__`, and its text names no byte, line or value of the
file: PyYAML's own text quotes the offending line and a `UnicodeDecodeError` quotes the byte.

`decoy.lang` is imported inside the `.decoy` branch only, so a YAML run never loads the
compiler or `lark`.

Other YAML a command reads (the CI manifest, a policy file, a layout file, text the CLI wrote
itself) is a different kind of input and stays on the allowlist in
`tests/sentry/io_policy/test_config_load_choke_point.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from decoy._source_positions import DecoyPositionIndex, Position, YamlPositionIndex
from decoy._yaml_errors import sanitize_yaml_error

# The one table of pipeline file suffixes and the one kind check. Completion and the path test
# for a pipeline argument import these, so a new suffix is added here and nowhere else.
_DECOY_SUFFIX = ".decoy"
PIPELINE_SUFFIXES = (".yaml", ".yml", _DECOY_SUFFIX)

NOT_UTF8 = "Pipeline YAML is not UTF-8 text."
EMPTY = "Pipeline YAML is empty."
_DECOY_NOT_UTF8 = "Pipeline file is not UTF-8 text."
_DECOY_EMPTY = "Pipeline file is empty."

Locate = Callable[[str | None], Position | None]


@dataclass(frozen=True)
class ConfigProblem:
    """One reason a pipeline file cannot be used. `message` and `hint` hold no value from the
    file: a hint names strategies and words of the language, never data."""

    code: str  # yaml.* or lang.*
    message: str
    position: Position | None = None
    hint: str | None = None

    @property
    def text(self) -> str:
        """The message, led by its place in the file when it has one."""
        if self.position is None or self.position.line is None:
            return self.message
        where = f"line {self.position.line}"
        if self.position.column is not None:
            where += f", column {self.position.column}"
        return f"{where}: {self.message}"


class ConfigFileError(Exception):
    """A pipeline file that cannot be used. `problems` is at least one, in source order with the
    review marks last; `code` and `message` are the first problem's, so a caller that knows
    nothing of the list still gets one code and one text. `message` holds no part of the file."""

    def __init__(self, code: str, message: str, position: Position | None = None) -> None:
        self._set((ConfigProblem(code, message, position),))

    @classmethod
    def from_problems(cls, problems: tuple[ConfigProblem, ...]) -> ConfigFileError:
        error = cls(problems[0].code, problems[0].message, problems[0].position)
        error._set(problems)
        return error

    def _set(self, problems: tuple[ConfigProblem, ...]) -> None:
        self.problems = problems
        self.code = problems[0].code
        more = len(problems) - 1
        self.message = problems[0].message + (
            f" ({more} more; `decoy validate FILE` lists them)" if more else ""
        )
        super().__init__(self.message)


@dataclass(frozen=True)
class PipelineFile:
    """A pipeline file as every command sees it, whatever its kind."""

    config: dict[str, Any]
    # A dotted config path to its place in the file, or None. Built on first call.
    locate: Locate
    # `lang.unreviewed` for each rule still ending with `?`; always () for YAML.
    unreviewed: tuple[ConfigProblem, ...]


def is_decoy_path(path: str | Path) -> bool:
    """True when `path` names a `.decoy` file. Every other path is YAML."""
    return str(path).lower().endswith(_DECOY_SUFFIX)


def read_config_bytes(path: Path) -> bytes:
    """The file's bytes, read once. `decoy run` hashes these exact bytes (`config_sha256`) and
    parses them through `load_pipeline`, so the hash and the config agree, CRLF included.

    An `OSError` from the read passes through unchanged."""
    return path.read_bytes()


def _decode(data: bytes) -> str | None:
    """`data` as strict UTF-8 with a leading BOM dropped, or None when it is not UTF-8.

    The one decoder behind both file kinds. It returns instead of raising so each caller raises
    its own code after the handler has closed, and the error has no `__context__`."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None


def decode_config_bytes(data: bytes) -> str:
    """`data` decoded as strict UTF-8 with a leading BOM dropped, or `yaml.not_utf8`."""
    text = _decode(data)
    if text is None:
        raise ConfigFileError("yaml.not_utf8", NOT_UTF8)
    return text


def _decode_decoy_bytes(data: bytes) -> str:
    text = _decode(data)
    if text is None:
        raise ConfigFileError("lang.not_utf8", _DECOY_NOT_UTF8)
    return text


def read_config_text(path: Path) -> str:
    """A YAML file's text: its bytes read once, decoded as strict UTF-8, a leading BOM dropped.

    An `OSError` from the read passes through unchanged."""
    return decode_config_bytes(read_config_bytes(path))


def read_decoy_text(path: Path) -> str:
    """A `.decoy` file's text, decoded like `read_config_text` but refused as `lang.not_utf8`."""
    return _decode_decoy_bytes(read_config_bytes(path))


def _parse_yaml_mapping(text: str) -> dict[str, Any]:
    """The YAML mapping in `text`, or a `ConfigFileError` naming which check failed."""
    parse_failure: str | None = None
    raw: Any = None
    try:
        raw = yaml.safe_load(text)
    except (
        yaml.YAMLError,
        ValueError,
        LookupError,
        TypeError,
        AttributeError,
        ArithmeticError,
        RecursionError,
    ) as exc:
        # Not only YAMLError: a tag constructor (`!!int x`) raises ValueError, `!!bool x` a
        # KeyError and a malformed `!!timestamp` an AttributeError, and their texts can quote
        # the scalar. sanitize_yaml_error reads only the mark.
        # MemoryError stays out of the tuple: resource exhaustion is not malformed YAML.
        parse_failure = sanitize_yaml_error(exc)
    if parse_failure is not None:
        raise ConfigFileError("yaml.parse_error", parse_failure)
    if raw is None:
        raise ConfigFileError("yaml.empty", EMPTY)
    if not isinstance(raw, dict):
        raise ConfigFileError(
            "yaml.not_mapping",
            f"Pipeline YAML must be a YAML mapping (object), not {type(raw).__name__}.",
        )
    return raw


def _lazy_yaml_locate(text: str) -> Locate:
    """`locate` for a YAML file. The index is built on the first call, so a command that never
    asks for a position never pays for the second parse."""
    built: list[YamlPositionIndex] = []

    def locate(logical_path: str | None) -> Position | None:
        if not built:
            built.append(YamlPositionIndex.from_text(text))
        return built[0].locate(logical_path)

    return locate


def _load_yaml(text: str) -> PipelineFile:
    return PipelineFile(_parse_yaml_mapping(text), _lazy_yaml_locate(text), ())


def _problem(diagnostic: Any) -> ConfigProblem:
    span = diagnostic.span
    place = None
    if span is not None:
        place = Position(span.line, span.column, span.end_line, span.end_column)
    return ConfigProblem(diagnostic.code, diagnostic.message, place, diagnostic.hint)


def _load_decoy(text: str) -> PipelineFile:
    # Imported here so a YAML run never loads the compiler or `lark`.
    from decoy.lang import LangError, lower_text

    if not text.strip():
        raise ConfigFileError("lang.empty", _DECOY_EMPTY)
    problems: tuple[ConfigProblem, ...] | None = None
    lowered = None
    try:
        lowered = lower_text(text)
    except LangError as exc:
        problems = tuple(_problem(d) for d in exc.diagnostics)
    # Raised after the handler closes, so the error carries neither the `LangError` nor a context.
    if problems is not None:
        raise ConfigFileError.from_problems(problems)
    assert lowered is not None
    index = DecoyPositionIndex(lowered.config, lowered.source_map)
    return PipelineFile(
        lowered.config, index.locate, tuple(_problem(d) for d in lowered.unreviewed)
    )


def load_pipeline(path: Path, *, text: str | bytes | None = None) -> PipelineFile:
    """The pipeline file at `path`, YAML or `.decoy` by its name.

    Reads `path` unless `text` is given. A caller that hashes the file reads the bytes once and
    passes them in; they are decoded as the kind's own reader would. An `OSError` from the read
    passes through. Everything else wrong with the file is a `ConfigFileError`."""
    decoy = is_decoy_path(path)
    if text is None:
        text = read_decoy_text(path) if decoy else read_config_text(path)
    elif isinstance(text, bytes):
        if decoy:
            text = _decode_decoy_bytes(text)
        else:
            text = decode_config_bytes(text)
    return _load_decoy(text) if decoy else _load_yaml(text)


def load_config_mapping(path: Path) -> dict[str, Any]:
    """The config mapping of `path`, refused when a rule is still marked `?`: the one load for a
    command that reads no position and runs no gate."""
    pipeline = load_pipeline(path)
    if pipeline.unreviewed:
        raise ConfigFileError.from_problems(pipeline.unreviewed)
    return pipeline.config


def config_refusal(exc: ConfigFileError | OSError) -> dict[str, str | None]:
    """The `message` and `code` a command prints for a failed config load.

    A `ConfigFileError` carries its own, led by the first problem's line and column when it has
    them. An `OSError` (the environment failed, not the config) gets fixed text naming only the
    exception type, never the path or the system message, and no code; its exit is
    `exit_code_for(exc)`, 3."""
    if isinstance(exc, ConfigFileError):
        lead = exc.problems[0]
        return {
            "message": ConfigProblem(lead.code, exc.message, lead.position).text,
            "code": exc.code,
        }
    return {"message": f"could not read the config file: {type(exc).__name__}.", "code": None}


__all__ = [
    "PIPELINE_SUFFIXES",
    "ConfigFileError",
    "ConfigProblem",
    "PipelineFile",
    "config_refusal",
    "decode_config_bytes",
    "is_decoy_path",
    "load_config_mapping",
    "load_pipeline",
    "read_config_bytes",
    "read_config_text",
    "read_decoy_text",
]
