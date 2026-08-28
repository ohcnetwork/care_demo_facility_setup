from __future__ import annotations

from care_demo_facility_setup.services.validators.base import (
    SeedValidationContext,
    ValidationAccumulator,
)

ALLOWED_RESOURCE_TYPES = frozenset({"practitioner", "location", "healthcare_service"})


def validate_token_categories(context: SeedValidationContext, accumulator: ValidationAccumulator) -> None:
    categories_config = context.pack.get("token_categories")
    category_entries = categories_config.get("categories") if isinstance(categories_config, dict) else None
    expected = context.counts.get("token_categories")

    if not isinstance(category_entries, list):
        accumulator.error("The seed pack must contain token_categories.json with a categories list.")
        return

    if expected is not None and len(category_entries) != expected:
        accumulator.error(f"The seed pack must contain exactly {expected} token category templates.")

    refs: set[str] = set()
    defaults_by_resource_type: dict[str, str] = {}
    for index, entry in enumerate(category_entries, start=1):
        if not isinstance(entry, dict):
            accumulator.error(f"token_categories[{index}] must be an object.")
            continue

        ref = entry.get("ref")
        if not isinstance(ref, str) or not ref:
            accumulator.error(f"token_categories[{index}] must define a non-empty ref.")
            label = f"token_categories[{index}]"
        elif ref in refs:
            accumulator.error(f"token_categories.json contains duplicate ref {ref}.")
            label = ref
        else:
            refs.add(ref)
            label = ref

        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            accumulator.error(f"{label} must define a non-empty name.")

        shorthand = entry.get("shorthand")
        if not isinstance(shorthand, str) or not shorthand.strip():
            accumulator.error(f"{label} must define a non-empty shorthand.")
        elif len(shorthand) > 5:
            accumulator.error(f"{label} shorthand must be at most 5 characters.")

        resource_type = entry.get("resource_type")
        if resource_type not in ALLOWED_RESOURCE_TYPES:
            accumulator.error(f"{label} resource_type must be one of: {', '.join(sorted(ALLOWED_RESOURCE_TYPES))}.")

        if entry.get("default") is True:
            if not isinstance(resource_type, str):
                continue
            existing = defaults_by_resource_type.get(resource_type)
            if existing:
                accumulator.error(
                    f"token_categories.json has multiple default:true entries for resource_type "
                    f"{resource_type} ({existing} and {label})."
                )
            else:
                defaults_by_resource_type[resource_type] = label
