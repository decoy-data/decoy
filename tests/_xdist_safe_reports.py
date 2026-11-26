"""Keep pytest-xdist worker reports serializable.

Mirror of the engine's tests/_xdist_safe_reports.py at 0952fbae (CLI-PAR S1). Differences: this
paragraph, and `object` in place of `Any` in three annotations, because the CLI lint-debt ratchet
counts ANN401 and never grows. The behavior is the same.

An xdist worker sends every test report to the controller through execnet, whose serializer
cannot encode a lone surrogate. Several tests log one on purpose (for example '\\ud800' to prove
a log sanitizer), and the captured log lands in the report, so the first such failure aborts the
whole run with an INTERNALERROR. The ``pytest_report_to_serializable`` hook below re-encodes
every string in the report with ``backslashreplace`` before it is sent. It only changes how an
unencodable character prints ('\\ud800' as text); it never touches the test's own behavior.
It runs in the worker only: a plain (serial) run never calls the hook with an xdist worker env.
"""

from __future__ import annotations

import os

import pytest


def _text(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return value.encode("utf-8", "backslashreplace").decode("utf-8")
    return value


def scrub(obj: object) -> object:
    """A copy of ``obj`` with every str (also dict keys) made utf-8 encodable."""
    if isinstance(obj, str):
        return _text(obj)
    if isinstance(obj, dict):
        return {scrub(k): scrub(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub(v) for v in obj]
    if isinstance(obj, tuple):
        return tuple(scrub(v) for v in obj)
    return obj


@pytest.hookimpl(hookwrapper=True)
def pytest_report_to_serializable(config: pytest.Config, report: object):  # type: ignore[no-untyped-def]
    outcome = yield
    if not os.environ.get("PYTEST_XDIST_WORKER"):
        return
    data = outcome.get_result()
    if data is not None:
        outcome.force_result(scrub(data))
