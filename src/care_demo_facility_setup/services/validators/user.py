from __future__ import annotations

from care_demo_facility_setup.services.validators.base import (
    SeedValidationContext,
    ValidationAccumulator,
)


def validate_users(context: SeedValidationContext, accumulator: ValidationAccumulator) -> None:
    users_config = context.pack.get("users")
    user_entries = users_config.get("users") if isinstance(users_config, dict) else None
    expected = context.counts.get("users")

    if not isinstance(user_entries, list):
        accumulator.error("The seed pack must contain users.json with a users list.")
        return

    if expected is not None and len(user_entries) != expected:
        accumulator.error(f"The seed pack must contain exactly {expected} user templates.")

    foundation = context.pack.get("facility_foundation")
    department_refs = set()
    if isinstance(foundation, dict) and isinstance(foundation.get("departments"), list):
        department_refs = {
            entry.get("ref")
            for entry in foundation["departments"]
            if isinstance(entry, dict) and isinstance(entry.get("ref"), str)
        }

    refs: set[str] = set()
    for index, entry in enumerate(user_entries, start=1):
        if not isinstance(entry, dict):
            accumulator.error(f"users[{index}] must be an object.")
            continue

        ref = entry.get("ref")
        if not isinstance(ref, str) or not ref:
            accumulator.error(f"users[{index}] must define a non-empty ref.")
        elif ref in refs:
            accumulator.error(f"users.json contains duplicate ref {ref}.")
        else:
            refs.add(ref)

        role_name = entry.get("role_name")
        if not isinstance(role_name, str) or not role_name.strip():
            accumulator.error(f"{ref or f'users[{index}]'} must define a non-empty role_name.")

        org_ref = entry.get("org_ref")
        if not isinstance(org_ref, str) or not org_ref:
            accumulator.error(f"{ref or f'users[{index}]'} must define a non-empty org_ref.")
        elif department_refs and org_ref not in department_refs:
            accumulator.error(f"{ref or f'users[{index}]'} references unknown department {org_ref}.")

        for field in ("username_prefix", "email_local", "first_name", "last_name"):
            if not entry.get(field):
                accumulator.error(f"{ref or f'users[{index}]'} is missing {field}.")
