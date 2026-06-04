from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from urllib.parse import urlparse

from care.emr.models import Organization

PACKAGE = "care_demo_facility_setup.seed_packs"
DEFAULT_PACK_SLUG = "generic_hospital_v1"


class SeedPackError(ValueError):
    pass


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str]
    warnings: list[str]
    summary: dict

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "summary": self.summary,
        }


def _pack_root(pack_slug: str):
    try:
        return resources.files(PACKAGE).joinpath(pack_slug)
    except ModuleNotFoundError as exc:
        raise SeedPackError("Seed pack package data is not available") from exc


def _load_json(path) -> dict | list:
    if not path.is_file():
        raise SeedPackError(f"Missing seed pack file: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_seed_packs() -> list[dict]:
    package_root = resources.files(PACKAGE)
    packs = []
    for pack_dir in package_root.iterdir():
        if not pack_dir.is_dir():
            continue
        manifest_path = pack_dir.joinpath("manifest.json")
        if not manifest_path.is_file():
            continue
        manifest = _load_json(manifest_path)
        packs.append(
            {
                "slug": manifest["slug"],
                "name": manifest["name"],
                "version": manifest["version"],
                "description": manifest.get("description", ""),
                "counts": manifest.get("counts", {}),
            }
        )
    return sorted(packs, key=lambda pack: pack["slug"])


def load_seed_pack(pack_slug: str = DEFAULT_PACK_SLUG) -> dict:
    pack_root = _pack_root(pack_slug)
    manifest = _load_json(pack_root.joinpath("manifest.json"))
    resources_config = manifest.get("resources", {})
    pack = {"manifest": manifest}
    for resource_key, resource_path in resources_config.items():
        pack[resource_key] = _load_json(pack_root.joinpath(resource_path))
    return pack


def list_profiles(pack_slug: str = DEFAULT_PACK_SLUG) -> list[dict]:
    pack_root = _pack_root(pack_slug)
    manifest = _load_json(pack_root.joinpath("manifest.json"))
    profiles_dir = pack_root.joinpath(manifest.get("profiles_dir", "profiles"))
    profiles = []
    if not profiles_dir.is_dir():
        return profiles
    for profile_path in profiles_dir.iterdir():
        if profile_path.name.endswith(".json"):
            profile = _load_json(profile_path)
            profiles.append(
                {
                    "slug": profile["slug"],
                    "name": profile["name"],
                    "description": profile.get("description", ""),
                    "allowed_hosts": profile.get("allowed_hosts", []),
                }
            )
    return sorted(profiles, key=lambda profile: profile["slug"])


def load_profile(pack_slug: str, profile_slug: str) -> dict:
    pack_root = _pack_root(pack_slug)
    manifest = _load_json(pack_root.joinpath("manifest.json"))
    profile_path = pack_root.joinpath(
        manifest.get("profiles_dir", "profiles"),
        f"{profile_slug}.json",
    )
    profile = _load_json(profile_path)
    if profile.get("slug") != profile_slug:
        raise SeedPackError("Profile slug does not match the requested profile")
    return profile


def _normalize_host(host_or_url: str | None) -> str | None:
    if not host_or_url:
        return None
    parsed = urlparse(host_or_url if "://" in host_or_url else f"https://{host_or_url}")
    host = parsed.hostname or host_or_url.split(":", 1)[0]
    return host.lower() if host else None


def validate_seed_request(
    *,
    pack_slug: str = DEFAULT_PACK_SLUG,
    profile_slug: str = "demo",
    care_base_url: str | None = None,
    current_host: str | None = None,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []

    try:
        pack = load_seed_pack(pack_slug)
        profile = load_profile(pack_slug, profile_slug)
    except SeedPackError as exc:
        return ValidationResult(
            valid=False,
            errors=[str(exc)],
            warnings=[],
            summary={"pack_slug": pack_slug, "profile_slug": profile_slug},
        )

    manifest = pack["manifest"]
    host = _normalize_host(current_host) or _normalize_host(care_base_url)
    allowed_hosts = profile.get("allowed_hosts", [])
    if host and allowed_hosts and host not in allowed_hosts:
        errors.append(
            f"Host '{host}' is not allowed for profile '{profile_slug}'. "
            "Choose the matching profile or update the profile allowed_hosts list."
        )
    elif not host:
        warnings.append("No request host was supplied; host/profile validation was skipped.")

    geo_organization_external_id = profile.get("geo_organization_external_id")
    if not geo_organization_external_id:
        errors.append(f"Profile '{profile_slug}' does not define geo_organization_external_id.")
    elif not Organization.objects.filter(
        external_id=geo_organization_external_id,
        org_type="govt",
    ).exists():
        errors.append("Profile geo_organization_external_id does not match an existing govt organization.")

    facility = pack.get("facility")
    if not isinstance(facility, dict):
        errors.append("The seed pack must contain facility.json with a facility template object.")

    patients = pack.get("patients")
    patient_entries = patients.get("patients") if isinstance(patients, dict) else None
    patient_count = patients.get("count") if isinstance(patients, dict) else None
    if not isinstance(patient_entries, list):
        errors.append("The seed pack must contain patients.json with a patients list.")
    elif len(patient_entries) != 10:
        errors.append("Milestone 1 requires exactly 10 patient templates.")
    if patient_count is not None and patient_count != 10:
        errors.append("Milestone 1 patients.json count must be 10.")

    foundation = pack.get("facility_foundation")
    if not isinstance(foundation, dict):
        errors.append("The seed pack must contain facility_foundation.json with a foundation object.")
    else:
        _validate_facility_foundation(foundation, errors)

    if not pack.get("lab_tests"):
        warnings.append("The seed pack does not contain any lab tests for later milestones.")
    if not pack.get("inventory_items"):
        warnings.append("The seed pack does not contain any inventory items for later milestones.")

    summary = {
        "pack_slug": manifest["slug"],
        "pack_name": manifest["name"],
        "pack_version": manifest["version"],
        "profile_slug": profile["slug"],
        "profile_name": profile["name"],
        "host": host,
        "counts": manifest.get("counts", {}),
        "geo_organization_external_id": geo_organization_external_id,
        "resource_categories": profile.get("resource_categories", {}),
    }
    return ValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        summary=summary,
    )


def _validate_facility_foundation(foundation: dict, errors: list[str]):
    departments = foundation.get("departments")
    locations = foundation.get("locations")
    healthcare_services = foundation.get("healthcare_services")

    department_refs = _validate_seed_entries(
        "facility_foundation.departments",
        departments,
        errors,
        expected_count=10,
    )
    location_refs = _validate_seed_entries(
        "facility_foundation.locations",
        locations,
        errors,
        expected_count=35,
    )
    _validate_seed_entries(
        "facility_foundation.healthcare_services",
        healthcare_services,
        errors,
        expected_count=4,
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
            errors.append("facility_foundation.departments must include department:administration.")
        elif not administration.get("reuse_existing"):
            errors.append(
                "department:administration must be marked reuse_existing because CARE creates it with the facility."
            )
        for department in departments:
            if not isinstance(department, dict) or department.get("ref") == "department:administration":
                continue
            if department.get("org_type") != "dept":
                errors.append(f"{department.get('ref', 'department entry')} must use org_type='dept'.")

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
                errors.append(f"{ref or 'location entry'} must use mode='kind'.")
            if isinstance(ref, str):
                locations_by_ref[ref] = location
            if isinstance(parent_ref, str):
                parent_refs.add(parent_ref)
                if parent_ref not in seen_locations:
                    errors.append(f"{ref or 'location entry'} references parent {parent_ref} before it is defined.")
                elif locations_by_ref.get(parent_ref, {}).get("mode") == "instance":
                    errors.append(f"{parent_ref} cannot be mode='instance' because it has children.")
            if isinstance(ref, str):
                seen_locations.add(ref)
        for parent_ref in parent_refs:
            if parent_ref in locations_by_ref and locations_by_ref[parent_ref].get("mode") == "instance":
                errors.append(f"{parent_ref} cannot be mode='instance' because it has children.")

    if isinstance(healthcare_services, list):
        for service in healthcare_services:
            if not isinstance(service, dict):
                continue
            org_ref = service.get("managing_organization_ref")
            if org_ref and org_ref not in department_refs:
                errors.append(
                    f"{service.get('ref', 'healthcare service entry')} references unknown department {org_ref}."
                )
            for location_ref in service.get("location_refs", []):
                if location_ref not in location_refs:
                    errors.append(
                        f"{service.get('ref', 'healthcare service entry')} references unknown location {location_ref}."
                    )


def _validate_seed_entries(
    label: str,
    entries,
    errors: list[str],
    *,
    expected_count: int,
) -> set[str]:
    if not isinstance(entries, list):
        errors.append(f"{label} must be a list.")
        return set()
    if len(entries) != expected_count:
        errors.append(f"{label} must contain exactly {expected_count} entries.")
    refs: set[str] = set()
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            errors.append(f"{label}[{index}] must be an object.")
            continue
        ref = entry.get("ref")
        if not isinstance(ref, str) or not ref:
            errors.append(f"{label}[{index}] must define a non-empty ref.")
            continue
        if ref in refs:
            errors.append(f"{label} contains duplicate ref {ref}.")
        refs.add(ref)
    return refs
