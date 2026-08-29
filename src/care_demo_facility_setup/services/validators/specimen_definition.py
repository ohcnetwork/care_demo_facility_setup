from __future__ import annotations

from care_demo_facility_setup.services.validators.base import (
    SeedValidationContext,
    ValidationAccumulator,
)


def validate_specimen_definitions(context: SeedValidationContext, accumulator: ValidationAccumulator) -> None:
    specimens = context.pack.get("specimens")
    expected_specimens = context.counts.get("specimens")

    if not isinstance(specimens, list):
        accumulator.error("The seed pack must contain specimens.json with a list of specimen definitions.")
        return

    if expected_specimens is not None and len(specimens) != expected_specimens:
        accumulator.error(f"The seed pack must contain exactly {expected_specimens} specimen definitions.")

    for index, specimen in enumerate(specimens, start=1):
        if not isinstance(specimen, dict):
            accumulator.error(f"Specimen definition #{index} must be an object.")
            continue
        for field in ("title", "slug_value", "type_collected"):
            if not specimen.get(field):
                accumulator.error(f"Specimen definition #{index} is missing {field}.")
