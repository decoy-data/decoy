"""`python -m decoy.lang`: the interim way to use the language, until the commands read `.decoy`.

    python -m decoy.lang pipeline.decoy > pipeline.yaml      compile to the pipeline YAML
    python -m decoy.lang --to-decoy pipeline.yaml > pipeline.decoy     convert a pipeline YAML

Problems go to stderr as `file:line:column: error[code]: message`, without the source line, in
keeping with the CLI's rule that an error never quotes the config. Exit 0 on success, 2 when the
input does not compile or convert, 3 when the file cannot be read.
"""

from __future__ import annotations

import sys
from pathlib import Path

from decoy._config_file import ConfigFileError, load_config_mapping, read_config_text
from decoy.lang import ConvertError, LangError, compile_text, convert_config, emit_yaml, render

USAGE = "usage: python -m decoy.lang <pipeline.decoy>\n       python -m decoy.lang --to-decoy <pipeline.yaml>"
TO_DECOY = "--to-decoy"
EXIT_INVALID = 2
EXIT_UNREADABLE = 3


def _compile(path: Path) -> int:
    try:
        compiled = compile_text(read_config_text(path))
    except LangError as error:
        for diagnostic in error.diagnostics:
            sys.stderr.write(render(diagnostic, filename=path.name) + "\n")
        return EXIT_INVALID
    sys.stdout.write(emit_yaml(compiled.config))
    return 0


def _convert(path: Path) -> int:
    try:
        text = convert_config(load_config_mapping(path))
    except ConvertError as error:
        sys.stderr.write(f"{path.name}: error[lang.convert]: {error}\n")
        return EXIT_INVALID
    sys.stdout.write(text)
    return 0


def main(argv: list[str]) -> int:
    to_decoy = argv[:1] == [TO_DECOY]
    files = argv[1:] if to_decoy else argv
    if len(files) != 1 or files[0].startswith("-"):
        sys.stderr.write(USAGE + "\n")
        return EXIT_INVALID
    path = Path(files[0])
    try:
        return _convert(path) if to_decoy else _compile(path)
    except (OSError, ConfigFileError) as error:
        sys.stderr.write(f"{path.name}: cannot read the file: {type(error).__name__}\n")
        return EXIT_UNREADABLE


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
