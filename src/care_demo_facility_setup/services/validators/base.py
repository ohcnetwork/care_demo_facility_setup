from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class ValidationAccumulator:
    """Collects validation errors and warnings while resource validators run."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)


@dataclass(frozen=True)
class SeedValidationContext:
    """Read-only inputs shared by every resource validator."""

    pack: dict
    manifest: dict
    counts: dict


SeedStepValidator = Callable[[SeedValidationContext, ValidationAccumulator], None]
