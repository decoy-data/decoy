"""`python -m decoy.lang pipeline.decoy`: compile a `.decoy` program and print its pipeline YAML.

The experimental way to use the language before any `decoy` command reads `.decoy` files: the
output is an ordinary pipeline config for `decoy validate` and `decoy run`.

    python -m decoy.lang pipeline.decoy > pipeline.yaml

Problems go to stderr as `file:line:column: error[code]: message`, without the source line, in
keeping with the CLI's rule that an error never quotes the config. Exit 0 on success, 2 when the
program does not compile, 3 when the file cannot be read.
"""

from __future__ import annotations

import sys
from pathlib import Path

from decoy._config_file import ConfigFileError, read_config_text
from decoy.lang import LangError, compile_text, emit_yaml, render

USAGE = "usage: python -m decoy.lang <pipeline.decoy>"
EXIT_INVALID = 2
EXIT_UNREADABLE = 3


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0].startswith("-"):
        sys.stderr.write(USAGE + "\n")
        return EXIT_INVALID
    path = Path(argv[0])
    try:
        text = read_config_text(path)
    except (OSError, ConfigFileError) as error:
        sys.stderr.write(
            f"{path.name}: cannot read the file as UTF-8 text: {type(error).__name__}\n"
        )
        return EXIT_UNREADABLE
    try:
        compiled = compile_text(text)
    except LangError as error:
        for diagnostic in error.diagnostics:
            sys.stderr.write(render(diagnostic, filename=path.name) + "\n")
        return EXIT_INVALID
    sys.stdout.write(emit_yaml(compiled.config))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
