"""Check result types and the two public check-name constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# The capacity check's name; `decoy.cli.gate` keys its chunked-route rule on it.
CAPACITY_CHECK = "capacity.out_of_core_fk"
# A plan the engine cannot compile, found while pricing capacity. Not CAPACITY_CHECK, so the
# chunked-route downgrade leaves it a FAIL.
PLAN_UNCOMPILABLE_CHECK = "capacity.plan_uncompilable"


@dataclass
class _CheckResult:
    name: str
    status: str  # "pass" | "warn" | "fail"
    message: str
    location: str | None = None
    # OOM checker v1: the engine's capacity-refusal code (a member of its capacity set),
    # carried as its own field so a --json caller can assert on it directly
    # instead of parsing `message` text (R9).
    code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "status": self.status,
            "message": self.message,
        }
        if self.location is not None:
            d["location"] = self.location
        if self.code is not None:
            d["code"] = self.code
        return d


@dataclass
class _PreflightAccumulator:
    checks: list[_CheckResult] = field(default_factory=list)
    # OOM checker v1 (T7): an INSUFFICIENT capacity verdict must exit
    # EXIT_CAPACITY, not fold into the generic has_failures -> EXIT_USAGE
    # path -- tracked separately from `checks` status so the two exit
    # reasons can never be confused with each other.
    capacity_insufficient: bool = False

    def add_pass(
        self, name: str, message: str, location: str | None = None, code: str | None = None
    ) -> None:
        self.checks.append(
            _CheckResult(name=name, status="pass", message=message, location=location, code=code)
        )

    def add_warn(
        self, name: str, message: str, location: str | None = None, code: str | None = None
    ) -> None:
        self.checks.append(
            _CheckResult(name=name, status="warn", message=message, location=location, code=code)
        )

    def add_fail(
        self, name: str, message: str, location: str | None = None, code: str | None = None
    ) -> None:
        self.checks.append(
            _CheckResult(name=name, status="fail", message=message, location=location, code=code)
        )

    @property
    def has_failures(self) -> bool:
        return any(c.status == "fail" for c in self.checks)

    @property
    def has_warnings(self) -> bool:
        return any(c.status == "warn" for c in self.checks)

    def to_dicts(self) -> list[dict[str, Any]]:
        return [c.to_dict() for c in self.checks]
