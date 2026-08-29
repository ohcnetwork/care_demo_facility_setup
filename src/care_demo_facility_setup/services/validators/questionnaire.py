from __future__ import annotations

from care_demo_facility_setup.services.demo_forms import load_demo_form
from care_demo_facility_setup.services.validators.base import (
    SeedValidationContext,
    ValidationAccumulator,
)


def validate_questionnaires(context: SeedValidationContext, accumulator: ValidationAccumulator) -> None:
    questionnaires = context.pack.get("questionnaires")
    forms = questionnaires.get("forms") if isinstance(questionnaires, dict) else None
    expected = context.counts.get("questionnaires")

    if not isinstance(forms, list) or not forms:
        accumulator.error("The seed pack must contain questionnaires.json with a non-empty forms list.")
        return

    if expected is not None and len(forms) != expected:
        accumulator.error(f"The seed pack must contain exactly {expected} questionnaire forms.")

    slugs: set[str] = set()
    for index, form in enumerate(forms, start=1):
        if not isinstance(form, dict):
            accumulator.error(f"questionnaires.forms[{index}] must be an object.")
            continue

        slug = form.get("slug")
        if not isinstance(slug, str) or not slug:
            accumulator.error(f"questionnaires.forms[{index}] must define a non-empty slug.")
            continue
        if slug in slugs:
            accumulator.error(f"questionnaires.json contains duplicate slug {slug}.")
        else:
            slugs.add(slug)

        fill_key = form.get("fill_key")
        if not isinstance(fill_key, str) or not fill_key:
            accumulator.error(f"questionnaires.forms[{index}] ({slug}) must define a non-empty fill_key.")

        requirements = form.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            accumulator.error(f"questionnaires.forms[{index}] ({slug}) must define a non-empty requirements list.")
        else:
            for req_index, requirement in enumerate(requirements, start=1):
                if not isinstance(requirement, dict):
                    accumulator.error(f"questionnaires.forms[{index}].requirements[{req_index}] must be an object.")
                    continue
                key = requirement.get("key")
                if not isinstance(key, str) or not key:
                    accumulator.error(f"questionnaires.forms[{index}].requirements[{req_index}] must define a key.")
                if not requirement.get("loinc") and not requirement.get("link_id"):
                    accumulator.error(
                        f"questionnaires.forms[{index}].requirements[{req_index}] must set loinc and/or link_id."
                    )

        try:
            load_demo_form(slug)
        except (FileNotFoundError, ValueError, OSError) as exc:
            accumulator.error(f"Demo questionnaire '{slug}' is invalid: {exc}")
