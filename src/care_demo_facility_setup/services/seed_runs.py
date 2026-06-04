from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from care_demo_facility_setup.models import (
    SeedRun,
    SeedRunStatus,
    SeedRunStep,
    SeedRunStepStatus,
)
from care_demo_facility_setup.services.seed_packs import validate_seed_request

PLANNED_STEPS = [
    ("validate", "Validate seed request"),
    ("facility", "Create demo facility"),
    ("patients", "Create demo patients"),
    ("facility_foundation", "Create facility foundation"),
]


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

    for index, (key, title) in enumerate(PLANNED_STEPS, start=1):
        status = SeedRunStepStatus.PENDING
        message = ""
        if key == "validate":
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
            key=key,
            title=title,
            status=status,
            message=message,
            stats=validation.summary.get("counts", {}) if key == "validate" else {},
            started_date=now if key == "validate" else None,
            finished_date=(now if key == "validate" or status == SeedRunStepStatus.SKIPPED else None),
        )

    return run


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
