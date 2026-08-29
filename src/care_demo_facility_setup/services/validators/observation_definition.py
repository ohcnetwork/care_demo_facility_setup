from __future__ import annotations

from care_demo_facility_setup.services.validators.base import (
    SeedValidationContext,
    ValidationAccumulator,
)


def validate_observation_definitions(context: SeedValidationContext, accumulator: ValidationAccumulator) -> None:
    observations = context.pack.get("observations")
    expected_observations = context.counts.get("observations")

    if not isinstance(observations, list):
        accumulator.error("The seed pack must contain observations.json with a list of observation definitions.")
        return

    if expected_observations is not None and len(observations) != expected_observations:
        accumulator.error(f"The seed pack must contain exactly {expected_observations} observation definitions.")

    for index, observation in enumerate(observations, start=1):
        if not isinstance(observation, dict):
            accumulator.error(f"Observation definition #{index} must be an object.")
            continue
        for field in ("title", "slug_value", "code", "category", "permitted_data_type"):
            if not observation.get(field):
                accumulator.error(f"Observation definition #{index} is missing {field}.")
