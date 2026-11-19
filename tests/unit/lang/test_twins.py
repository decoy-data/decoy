"""Each bundled template has a `.decoy` twin that must compile to the same config."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from decoy.lang import compile_text, emit_yaml
from decoy.templates import get_template, template_names

_TWINS = Path(__file__).parent / "twins"
_NAMES = sorted(path.stem for path in _TWINS.glob("*.decoy"))


def _twin(name: str) -> str:
    return (_TWINS / f"{name}.decoy").read_text(encoding="utf-8")


def test_every_bundled_template_has_a_twin() -> None:
    assert _NAMES == sorted(template_names())


@pytest.mark.parametrize("name", _NAMES)
def test_twin_compiles_to_the_template_config(name: str) -> None:
    assert compile_text(_twin(name)).config == yaml.safe_load(get_template(name).body)


@pytest.mark.parametrize("name", _NAMES)
def test_emitted_yaml_loads_back_to_the_same_config(name: str) -> None:
    config = compile_text(_twin(name)).config
    assert yaml.safe_load(emit_yaml(config)) == config


@pytest.mark.parametrize("name", _NAMES)
def test_compiling_twice_gives_identical_yaml(name: str) -> None:
    assert emit_yaml(compile_text(_twin(name)).config) == emit_yaml(
        compile_text(_twin(name)).config
    )


@pytest.mark.parametrize("name", _NAMES)
def test_twin_is_shorter_than_the_template(name: str) -> None:
    def lines(text: str) -> int:
        return sum(
            1 for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")
        )

    assert lines(_twin(name)) < lines(get_template(name).body) / 2
