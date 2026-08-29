from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from care.emr.models import Organization

from care_demo_facility_setup.services.seed_packs import (
    DEFAULT_PACK_SLUG,
    SeedPackError,
    load_profile,
    load_seed_pack,
)
from care_demo_facility_setup.services.seed_step_registry import (
    SeedStepRegistryError,
    get_seed_step_definitions,
)
from care_demo_facility_setup.services.validators import (
    SeedValidationContext,
    ValidationAccumulator,
)


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
    accumulator = ValidationAccumulator()

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
    counts = manifest.get("counts", {})

    try:
        step_definitions = get_seed_step_definitions(manifest)
    except SeedStepRegistryError as exc:
        accumulator.error(str(exc))
        step_definitions = ()

    host = _normalize_host(current_host) or _normalize_host(care_base_url)
    _validate_host(host, profile, profile_slug, accumulator)
    geo_organization_external_id = _validate_geo_organization(profile, profile_slug, accumulator)

    context = SeedValidationContext(pack=pack, manifest=manifest, counts=counts)
    for step_definition in step_definitions:
        if step_definition.validator is not None:
            step_definition.validator(context, accumulator)

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
        valid=not accumulator.errors,
        errors=accumulator.errors,
        warnings=accumulator.warnings,
        summary=summary,
    )


def _validate_host(
    host: str | None,
    profile: dict,
    profile_slug: str,
    accumulator: ValidationAccumulator,
) -> None:
    allowed_hosts = profile.get("allowed_hosts", [])
    if host and allowed_hosts and host not in allowed_hosts:
        accumulator.error(
            f"Host '{host}' is not allowed for profile '{profile_slug}'. "
            "Choose the matching profile or update the profile allowed_hosts list."
        )
    elif not host:
        accumulator.warning("No request host was supplied; host/profile validation was skipped.")


def _validate_geo_organization(
    profile: dict,
    profile_slug: str,
    accumulator: ValidationAccumulator,
) -> str | None:
    geo_organization_external_id = profile.get("geo_organization_external_id")
    if not geo_organization_external_id:
        accumulator.error(f"Profile '{profile_slug}' does not define geo_organization_external_id.")
    elif not Organization.objects.filter(
        external_id=geo_organization_external_id,
        org_type="govt",
    ).exists():
        accumulator.error("Profile geo_organization_external_id does not match an existing govt organization.")
    return geo_organization_external_id
