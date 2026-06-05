from __future__ import annotations

from care_demo_facility_setup.services.validators.base import (
    SeedValidationContext,
    ValidationAccumulator,
)


def _catalog_slugs(items) -> set[str]:
    if not isinstance(items, list):
        return set()
    return {item["slug_value"] for item in items if isinstance(item, dict) and item.get("slug_value")}


def validate_activity_definitions(context: SeedValidationContext, accumulator: ValidationAccumulator) -> None:
    activities = context.pack.get("activity_definitions")
    expected_activities = context.counts.get("activity_definitions")

    categories = context.pack.get("activity_categories")
    expected_categories = context.counts.get("activity_categories")
    category_slugs: set[str] = set()
    if not isinstance(categories, list) or not categories:
        accumulator.error("The seed pack must contain activity_categories.json with at least one resource category.")
    else:
        if expected_categories is not None and len(categories) != expected_categories:
            accumulator.error(f"The seed pack must contain exactly {expected_categories} activity categories.")
        for index, category in enumerate(categories, start=1):
            if not isinstance(category, dict):
                accumulator.error(f"Activity category #{index} must be an object.")
                continue
            for field in ("title", "slug_value"):
                if not category.get(field):
                    accumulator.error(f"Activity category #{index} is missing {field}.")
            if category.get("slug_value"):
                category_slugs.add(category["slug_value"])

    specimen_slugs = _catalog_slugs(context.pack.get("specimens"))
    observation_slugs = _catalog_slugs(context.pack.get("observations"))
    charge_slugs = _catalog_slugs(context.pack.get("charge_item_definitions"))

    foundation = context.pack.get("facility_foundation")
    location_refs: set[str] = set()
    service_refs: set[str] = set()
    if isinstance(foundation, dict):
        location_refs = {
            entry["ref"] for entry in foundation.get("locations", []) if isinstance(entry, dict) and entry.get("ref")
        }
        service_refs = {
            entry["ref"]
            for entry in foundation.get("healthcare_services", [])
            if isinstance(entry, dict) and entry.get("ref")
        }

    if not isinstance(activities, list):
        accumulator.error("The seed pack must contain activity_definitions.json with a list of activity definitions.")
        return

    if expected_activities is not None and len(activities) != expected_activities:
        accumulator.error(f"The seed pack must contain exactly {expected_activities} activity definitions.")

    for index, activity in enumerate(activities, start=1):
        if not isinstance(activity, dict):
            accumulator.error(f"Activity definition #{index} must be an object.")
            continue
        for field in ("title", "slug_value", "code", "classification", "kind"):
            if not activity.get(field):
                accumulator.error(f"Activity definition #{index} is missing {field}.")
        category_ref = activity.get("category")
        if category_ref and category_slugs and category_ref not in category_slugs:
            accumulator.error(f"Activity definition #{index} references unknown category '{category_ref}'.")
        for slug in activity.get("specimen_refs", []):
            if specimen_slugs and slug not in specimen_slugs:
                accumulator.error(f"Activity definition #{index} references unknown specimen '{slug}'.")
        for slug in activity.get("observation_refs", []):
            if observation_slugs and slug not in observation_slugs:
                accumulator.error(f"Activity definition #{index} references unknown observation '{slug}'.")
        for slug in activity.get("charge_item_definition_refs", []):
            if charge_slugs and slug not in charge_slugs:
                accumulator.error(f"Activity definition #{index} references unknown charge item definition '{slug}'.")
        for ref in activity.get("location_refs", []):
            if location_refs and ref not in location_refs:
                accumulator.error(f"Activity definition #{index} references unknown location '{ref}'.")
        service_ref = activity.get("healthcare_service_ref")
        if service_ref and service_refs and service_ref not in service_refs:
            accumulator.error(f"Activity definition #{index} references unknown healthcare service '{service_ref}'.")
