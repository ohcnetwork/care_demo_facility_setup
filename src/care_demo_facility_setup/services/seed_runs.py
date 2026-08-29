from __future__ import annotations

from care.emr.models.organization import Organization
from care.facility.models import Facility
from django.db import transaction
from django.utils import timezone

from care_demo_facility_setup.models import (
    SeedRun,
    SeedRunArtifact,
    SeedRunStatus,
    SeedRunStep,
    SeedRunStepStatus,
)
from care_demo_facility_setup.services.seed_errors import SeedRunExecutionError
from care_demo_facility_setup.services.seed_packs import (
    DEFAULT_PACK_SLUG,
    SeedPackError,
    load_profile,
    load_seed_pack,
)
from care_demo_facility_setup.services.seed_step_registry import SeedStepRegistryError, get_seed_step_definitions
from care_demo_facility_setup.services.seed_validation import validate_seed_request


def serialize_seed_run(run: SeedRun, include_details: bool = False) -> dict:
    data = {
        "id": str(run.external_id),
        "pack_slug": run.pack_slug,
        "profile_slug": run.profile_slug,
        "status": _choice_value(run.status),
        "dry_run": run.dry_run,
        "summary": run.summary,
        "error": run.error,
        "created_date": run.created_date.isoformat() if run.created_date else None,
        "started_date": run.started_date.isoformat() if run.started_date else None,
        "finished_date": run.finished_date.isoformat() if run.finished_date else None,
    }
    if include_details:
        data["request_payload"] = run.request_payload
        data["steps"] = [
            {
                "id": str(step.external_id),
                "order": step.order,
                "key": step.key,
                "title": step.title,
                "status": _choice_value(step.status),
                "message": step.message,
                "stats": step.stats,
                "started_date": step.started_date.isoformat() if step.started_date else None,
                "finished_date": step.finished_date.isoformat() if step.finished_date else None,
            }
            for step in run.steps.all()
        ]
        data["artifacts"] = [
            {
                "id": str(artifact.external_id),
                "ref": artifact.ref,
                "resource_type": artifact.resource_type,
                "resource_external_id": str(artifact.resource_external_id) if artifact.resource_external_id else None,
                "slug": artifact.slug,
                "payload": artifact.payload,
            }
            for artifact in run.artifacts.all()
        ]
    return data


def _choice_value(value):
    return value.value if hasattr(value, "value") else value


@transaction.atomic
def create_seed_run(
    *,
    request_payload: dict,
    requested_by=None,
    current_host: str | None = None,
) -> SeedRun:
    pack_slug = request_payload.get("pack_slug") or "generic_hospital_v1"
    profile_slug = request_payload.get("profile_slug") or "demo"
    dry_run = bool(request_payload.get("dry_run", True))
    validation = validate_seed_request(
        pack_slug=pack_slug,
        profile_slug=profile_slug,
        care_base_url=request_payload.get("care_base_url"),
        current_host=current_host,
    )

    now = timezone.now()
    run = SeedRun.objects.create(
        pack_slug=pack_slug,
        profile_slug=profile_slug,
        dry_run=dry_run,
        requested_by=requested_by if getattr(requested_by, "is_authenticated", False) else None,
        request_payload=request_payload,
        summary=validation.summary,
        status=SeedRunStatus.SUCCEEDED
        if dry_run and validation.valid
        else SeedRunStatus.QUEUED
        if validation.valid
        else SeedRunStatus.VALIDATION_FAILED,
        error="\n".join(validation.errors),
        started_date=now if dry_run or not validation.valid else None,
        finished_date=now if dry_run or not validation.valid else None,
    )

    for index, step_definition in enumerate(_planned_steps_for_pack(pack_slug), start=1):
        status = SeedRunStepStatus.PENDING
        message = ""
        if step_definition.key == "validate":
            status = SeedRunStepStatus.SUCCEEDED if validation.valid else SeedRunStepStatus.FAILED
            message = "Validation passed" if validation.valid else "Validation failed"
        elif dry_run and validation.valid:
            status = SeedRunStepStatus.SKIPPED
            message = "Dry run only; resource creation was not executed."
        elif not validation.valid:
            status = SeedRunStepStatus.SKIPPED
            message = "Skipped because validation failed."

        SeedRunStep.objects.create(
            run=run,
            order=index,
            key=step_definition.key,
            title=step_definition.title,
            status=status,
            message=message,
            stats=validation.summary.get("counts", {}) if step_definition.key == "validate" else {},
            started_date=now if step_definition.key == "validate" else None,
            finished_date=(now if step_definition.key == "validate" or status == SeedRunStepStatus.SKIPPED else None),
        )

    return run


def _planned_steps_for_pack(pack_slug: str):
    try:
        manifest = load_seed_pack(pack_slug)["manifest"]
        return get_seed_step_definitions(manifest)
    except (SeedPackError, SeedStepRegistryError):
        return get_seed_step_definitions()


def enqueue_seed_run(run_external_id: str):
    try:
        from care_demo_facility_setup.tasks import execute_seed_run

        execute_seed_run.delay(run_external_id)
    except Exception as exc:
        SeedRun.objects.filter(external_id=run_external_id).update(
            status=SeedRunStatus.FAILED,
            error=f"Could not enqueue seed run: {exc}",
            finished_date=timezone.now(),
        )


@transaction.atomic
def create_attached_seed_run(
    *,
    facility_external_id: str,
    geo_organization_external_id: str,
    requested_by,
    pack_slug: str = DEFAULT_PACK_SLUG,
    profile_slug: str = "local",
) -> SeedRun:
    """Create a SeedRun that attaches pack content to an existing facility.

    Skips host/profile geo validation: the caller supplies geo and facility ids.
    Pre-stores ``facility:main`` and marks the facility step succeeded so
    FacilitySeeder is never called. Standalone ``create_seed_run`` is unchanged.
    """
    try:
        pack = load_seed_pack(pack_slug)
        profile = load_profile(pack_slug, profile_slug)
    except SeedPackError as exc:
        raise SeedRunExecutionError(str(exc)) from exc

    if not Organization.objects.filter(
        external_id=geo_organization_external_id,
        org_type="govt",
    ).exists():
        raise SeedRunExecutionError("geo_organization_external_id does not match an existing govt organization.")

    try:
        facility = Facility.objects.get(external_id=facility_external_id)
    except Facility.DoesNotExist as exc:
        raise SeedRunExecutionError(f"Facility {facility_external_id} does not exist.") from exc

    facility_ref = pack.get("facility", {}).get("ref", "facility:main")
    manifest = pack["manifest"]
    now = timezone.now()
    request_payload = {
        "pack_slug": pack_slug,
        "profile_slug": profile_slug,
        "dry_run": False,
        "attach_existing_facility": True,
        "facility_external_id": str(facility_external_id),
        "geo_organization_external_id": str(geo_organization_external_id),
    }
    summary = {
        "pack_slug": manifest["slug"],
        "pack_name": manifest["name"],
        "pack_version": manifest["version"],
        "profile_slug": profile["slug"],
        "profile_name": profile["name"],
        "counts": manifest.get("counts", {}),
        "geo_organization_external_id": str(geo_organization_external_id),
        "facility_external_id": str(facility_external_id),
        "attach_existing_facility": True,
        "resource_categories": profile.get("resource_categories", {}),
    }

    run = SeedRun.objects.create(
        pack_slug=pack_slug,
        profile_slug=profile_slug,
        dry_run=False,
        requested_by=requested_by,
        request_payload=request_payload,
        summary=summary,
        status=SeedRunStatus.QUEUED,
        error="",
    )

    facility_step = None
    for index, step_definition in enumerate(_planned_steps_for_pack(pack_slug), start=1):
        if step_definition.key == "validate":
            status = SeedRunStepStatus.SUCCEEDED
            message = "Attach-mode validation passed (geo and facility injected)."
            started = now
            finished = now
            stats = summary.get("counts", {})
        elif step_definition.key == "facility":
            status = SeedRunStepStatus.SUCCEEDED
            message = f"Attached existing facility {facility.name}"
            started = now
            finished = now
            stats = {"created": 0, "attached": 1}
        else:
            status = SeedRunStepStatus.PENDING
            message = ""
            started = None
            finished = None
            stats = {}

        step = SeedRunStep.objects.create(
            run=run,
            order=index,
            key=step_definition.key,
            title=step_definition.title,
            status=status,
            message=message,
            stats=stats,
            started_date=started,
            finished_date=finished,
        )
        if step_definition.key == "facility":
            facility_step = step

    SeedRunArtifact.objects.create(
        run=run,
        step=facility_step,
        ref=facility_ref,
        resource_type="Facility",
        resource_external_id=facility.external_id,
        slug=getattr(facility, "slug", "") or "",
        payload={
            "id": str(facility.external_id),
            "name": facility.name,
            "attached": True,
        },
    )
    return run
