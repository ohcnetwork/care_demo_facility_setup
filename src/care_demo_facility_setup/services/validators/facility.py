from __future__ import annotations

from care_demo_facility_setup.services.validators.base import (
    SeedValidationContext,
    ValidationAccumulator,
)


def validate_facility(context: SeedValidationContext, accumulator: ValidationAccumulator) -> None:
    facility = context.pack.get("facility")
    if not isinstance(facility, dict):
        accumulator.error("The seed pack must contain facility.json with a facility template object.")
