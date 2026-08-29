from __future__ import annotations

from care_demo_facility_setup.services.validators.base import (
    SeedValidationContext,
    ValidationAccumulator,
)


def validate_clinical_visits(context: SeedValidationContext, accumulator: ValidationAccumulator) -> None:
    scenarios = context.pack.get("clinical_scenarios")
    visits = context.pack.get("clinical_visits")
    patients = context.pack.get("patients")
    foundation = context.pack.get("facility_foundation")
    inventory = context.pack.get("inventory_items")
    questionnaires = context.pack.get("questionnaires")

    if not isinstance(scenarios, list) or not scenarios:
        accumulator.error("The seed pack must contain clinical_scenarios.json with a non-empty list.")
        return
    if not isinstance(visits, dict):
        accumulator.error("The seed pack must contain clinical_visits.json with a visit plan object.")
        return

    inventory_slugs = {
        item.get("slug")
        for item in (inventory if isinstance(inventory, list) else [])
        if isinstance(item, dict) and isinstance(item.get("slug"), str)
    }

    for index, scenario in enumerate(scenarios, start=1):
        if not isinstance(scenario, dict):
            accumulator.error(f"clinical_scenarios[{index}] must be an object.")
            continue
        for field in ("name", "history_text", "advice", "vitals", "symptoms", "diagnosis", "medication"):
            if field not in scenario:
                accumulator.error(f"clinical_scenarios[{index}] is missing '{field}'.")
        medication = scenario.get("medication")
        if isinstance(medication, dict):
            pk_slug = medication.get("product_knowledge_slug")
            if not isinstance(pk_slug, str) or not pk_slug:
                accumulator.error(
                    f"clinical_scenarios[{index}].medication must set product_knowledge_slug "
                    "(stocked inventory product)."
                )
            elif inventory_slugs and pk_slug not in inventory_slugs:
                accumulator.error(
                    f"clinical_scenarios[{index}].medication.product_knowledge_slug "
                    f"'{pk_slug}' is not in inventory_items.json."
                )
    patient_refs = {
        patient.get("ref")
        for patient in (patients.get("patients") if isinstance(patients, dict) else []) or []
        if isinstance(patient, dict) and isinstance(patient.get("ref"), str)
    }
    location_refs = {
        location.get("ref")
        for location in (foundation.get("locations") if isinstance(foundation, dict) else []) or []
        if isinstance(location, dict) and isinstance(location.get("ref"), str)
    }
    department_refs = {
        department.get("ref")
        for department in (foundation.get("departments") if isinstance(foundation, dict) else []) or []
        if isinstance(department, dict) and isinstance(department.get("ref"), str)
    }
    questionnaire_form_slugs = {
        form.get("slug")
        for form in (questionnaires.get("forms") if isinstance(questionnaires, dict) else []) or []
        if isinstance(form, dict) and isinstance(form.get("slug"), str)
    }

    op_per_patient = visits.get("op_closed_per_patient")
    if not isinstance(op_per_patient, int) or op_per_patient < 1:
        accumulator.error("clinical_visits.op_closed_per_patient must be a positive integer.")

    op_org_refs = visits.get("op_org_refs")
    if not isinstance(op_org_refs, list) or not op_org_refs:
        accumulator.error("clinical_visits.op_org_refs must be a non-empty list.")
    else:
        for org_ref in op_org_refs:
            if org_ref not in department_refs:
                accumulator.error(f"clinical_visits.op_org_refs references unknown department {org_ref}.")

    ip_rows = visits.get("ip_in_progress")
    if not isinstance(ip_rows, list):
        accumulator.error("clinical_visits.ip_in_progress must be a list.")
        ip_rows = []
    else:
        for index, row in enumerate(ip_rows, start=1):
            if not isinstance(row, dict):
                accumulator.error(f"clinical_visits.ip_in_progress[{index}] must be an object.")
                continue
            _validate_visit_refs(
                f"clinical_visits.ip_in_progress[{index}]",
                row,
                patient_refs,
                department_refs,
                location_refs,
                accumulator,
                require_bed=True,
            )

    emergency_rows = visits.get("emergency")
    if not isinstance(emergency_rows, list):
        accumulator.error("clinical_visits.emergency must be a list.")
        emergency_rows = []
    else:
        for index, row in enumerate(emergency_rows, start=1):
            if not isinstance(row, dict):
                accumulator.error(f"clinical_visits.emergency[{index}] must be an object.")
                continue
            _validate_visit_refs(
                f"clinical_visits.emergency[{index}]",
                row,
                patient_refs,
                department_refs,
                location_refs,
                accumulator,
                require_bed=False,
            )

    questionnaire_slugs = visits.get("questionnaire_slugs")
    if not isinstance(questionnaire_slugs, list):
        accumulator.error("clinical_visits.questionnaire_slugs must be a list.")
    else:
        for slug in questionnaire_slugs:
            if slug not in questionnaire_form_slugs:
                accumulator.error(f"clinical_visits.questionnaire_slugs references unknown questionnaire '{slug}'.")

    expected_visits = context.counts.get("clinical_visits")
    if (
        expected_visits is not None
        and isinstance(op_per_patient, int)
        and isinstance(patients, dict)
        and isinstance(ip_rows, list)
        and isinstance(emergency_rows, list)
    ):
        patient_count = len(patients.get("patients") or [])
        computed = (op_per_patient * patient_count) + len(ip_rows) + len(emergency_rows)
        if computed != expected_visits:
            accumulator.error(
                f"clinical_visits plan expands to {computed} visits but manifest count is {expected_visits}."
            )


def _validate_visit_refs(
    label: str,
    row: dict,
    patient_refs: set,
    department_refs: set,
    location_refs: set,
    accumulator: ValidationAccumulator,
    *,
    require_bed: bool,
) -> None:
    patient_ref = row.get("patient_ref")
    org_ref = row.get("org_ref")
    if patient_ref not in patient_refs:
        accumulator.error(f"{label} references unknown patient {patient_ref}.")
    if org_ref not in department_refs:
        accumulator.error(f"{label} references unknown department {org_ref}.")
    if require_bed:
        bed_ref = row.get("bed_ref")
        if bed_ref not in location_refs:
            accumulator.error(f"{label} references unknown bed {bed_ref}.")
