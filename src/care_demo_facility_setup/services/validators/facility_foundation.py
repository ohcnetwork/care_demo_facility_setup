from __future__ import annotations

from care_demo_facility_setup.services.validators.base import (
    SeedValidationContext,
    ValidationAccumulator,
)


def validate_facility_foundation(context: SeedValidationContext, accumulator: ValidationAccumulator) -> None:
    foundation = context.pack.get("facility_foundation")
    if not isinstance(foundation, dict):
        accumulator.error("The seed pack must contain facility_foundation.json with a foundation object.")
        return
    _validate_foundation_entries(foundation, accumulator, context.counts)


def _validate_foundation_entries(foundation: dict, accumulator: ValidationAccumulator, counts: dict) -> None:
    departments = foundation.get("departments")
    locations = foundation.get("locations")
    healthcare_services = foundation.get("healthcare_services")

    department_refs = _validate_seed_entries(
        "facility_foundation.departments",
        departments,
        accumulator,
        expected_count=counts.get("departments"),
    )
    location_refs = _validate_seed_entries(
        "facility_foundation.locations",
        locations,
        accumulator,
        expected_count=counts.get("locations"),
    )
    _validate_seed_entries(
        "facility_foundation.healthcare_services",
        healthcare_services,
        accumulator,
        expected_count=counts.get("healthcare_services"),
    )

    if isinstance(departments, list):
        administration = next(
            (
                department
                for department in departments
                if isinstance(department, dict) and department.get("ref") == "department:administration"
            ),
            None,
        )
        if not administration:
            accumulator.error("facility_foundation.departments must include department:administration.")
        elif not administration.get("reuse_existing"):
            accumulator.error(
                "department:administration must be marked reuse_existing because CARE creates it with the facility."
            )
        for department in departments:
            if not isinstance(department, dict) or department.get("ref") == "department:administration":
                continue
            if department.get("org_type") != "dept":
                accumulator.error(f"{department.get('ref', 'department entry')} must use org_type='dept'.")

    if isinstance(locations, list):
        seen_locations: set[str] = set()
        parent_refs: set[str] = set()
        locations_by_ref: dict[str, dict] = {}
        for location in locations:
            if not isinstance(location, dict):
                continue
            ref = location.get("ref")
            parent_ref = location.get("parent_ref")
            if location.get("mode") != "kind":
                accumulator.error(f"{ref or 'location entry'} must use mode='kind'.")
            if isinstance(ref, str):
                locations_by_ref[ref] = location
            if isinstance(parent_ref, str):
                parent_refs.add(parent_ref)
                if parent_ref not in seen_locations:
                    accumulator.error(f"{ref or 'location entry'} references parent {parent_ref} before it is defined.")
                elif locations_by_ref.get(parent_ref, {}).get("mode") == "instance":
                    accumulator.error(f"{parent_ref} cannot be mode='instance' because it has children.")
            if isinstance(ref, str):
                seen_locations.add(ref)
        for parent_ref in parent_refs:
            if parent_ref in locations_by_ref and locations_by_ref[parent_ref].get("mode") == "instance":
                accumulator.error(f"{parent_ref} cannot be mode='instance' because it has children.")

    if isinstance(healthcare_services, list):
        for service in healthcare_services:
            if not isinstance(service, dict):
                continue
            org_ref = service.get("managing_organization_ref")
            if org_ref and org_ref not in department_refs:
                accumulator.error(
                    f"{service.get('ref', 'healthcare service entry')} references unknown department {org_ref}."
                )
            for location_ref in service.get("location_refs", []):
                if location_ref not in location_refs:
                    accumulator.error(
                        f"{service.get('ref', 'healthcare service entry')} references unknown location {location_ref}."
                    )


def _validate_seed_entries(
    label: str,
    entries,
    accumulator: ValidationAccumulator,
    *,
    expected_count: int | None = None,
) -> set[str]:
    if not isinstance(entries, list):
        accumulator.error(f"{label} must be a list.")
        return set()
    if expected_count is not None and len(entries) != expected_count:
        accumulator.error(f"{label} must contain exactly {expected_count} entries.")
    refs: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            accumulator.error(f"{label}[{index}] must be an object.")
            continue
        ref = entry.get("ref")
        if not isinstance(ref, str) or not ref:
            accumulator.error(f"{label}[{index}] must define a non-empty ref.")
            continue
        if ref in refs:
            accumulator.error(f"{label} contains duplicate ref {ref}.")
        refs.add(ref)
    return refs
