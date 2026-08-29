from __future__ import annotations

from care_demo_facility_setup.services.validators.base import (
    SeedValidationContext,
    ValidationAccumulator,
)


def validate_patients(context: SeedValidationContext, accumulator: ValidationAccumulator) -> None:
    patients = context.pack.get("patients")
    patient_entries = patients.get("patients") if isinstance(patients, dict) else None
    patient_count = patients.get("count") if isinstance(patients, dict) else None
    expected_patients = context.counts.get("patients")

    if not isinstance(patient_entries, list):
        accumulator.error("The seed pack must contain patients.json with a patients list.")
    elif expected_patients is not None and len(patient_entries) != expected_patients:
        accumulator.error(f"The seed pack must contain exactly {expected_patients} patient templates.")

    if expected_patients is not None and patient_count is not None and patient_count != expected_patients:
        accumulator.error(f"patients.json count must be {expected_patients}.")
