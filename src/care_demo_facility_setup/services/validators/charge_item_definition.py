from __future__ import annotations

from care_demo_facility_setup.services.validators.base import (
    SeedValidationContext,
    ValidationAccumulator,
)


def validate_charge_item_definitions(context: SeedValidationContext, accumulator: ValidationAccumulator) -> None:
    charges = context.pack.get("charge_item_definitions")
    expected_charges = context.counts.get("charge_item_definitions")

    categories = context.pack.get("charge_item_categories")
    expected_categories = context.counts.get("charge_item_categories")
    category_slugs: set[str] = set()
    if not isinstance(categories, list) or not categories:
        accumulator.error("The seed pack must contain charge_item_categories.json with at least one resource category.")
    else:
        if expected_categories is not None and len(categories) != expected_categories:
            accumulator.error(f"The seed pack must contain exactly {expected_categories} charge item categories.")
        for index, category in enumerate(categories, start=1):
            if not isinstance(category, dict):
                accumulator.error(f"Charge item category #{index} must be an object.")
                continue
            for field in ("title", "slug_value"):
                if not category.get(field):
                    accumulator.error(f"Charge item category #{index} is missing {field}.")
            if category.get("slug_value"):
                category_slugs.add(category["slug_value"])

    if not isinstance(charges, list):
        accumulator.error(
            "The seed pack must contain charge_item_definitions.json with a list of charge item definitions."
        )
        return

    if expected_charges is not None and len(charges) != expected_charges:
        accumulator.error(f"The seed pack must contain exactly {expected_charges} charge item definitions.")

    for index, charge in enumerate(charges, start=1):
        if not isinstance(charge, dict):
            accumulator.error(f"Charge item definition #{index} must be an object.")
            continue
        for field in ("title", "slug_value", "price_components"):
            if not charge.get(field):
                accumulator.error(f"Charge item definition #{index} is missing {field}.")
        category_ref = charge.get("category")
        if category_ref and category_slugs and category_ref not in category_slugs:
            accumulator.error(f"Charge item definition #{index} references unknown category '{category_ref}'.")
