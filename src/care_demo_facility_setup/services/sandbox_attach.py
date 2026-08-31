"""Programmatic attach-to-existing-facility entrypoint for sandbox callers.

Seeds pack content onto a facility that already exists (e.g. Experience sandbox
shell). Does not create a second facility. Runs DemoSeedRunner.execute()
synchronously — never enqueue_seed_run / .delay().
"""

from __future__ import annotations

from care_demo_facility_setup.models import SeedRun, SeedRunStatus, SeedRunStepStatus
from care_demo_facility_setup.services.runner import DemoSeedRunner
from care_demo_facility_setup.services.seed_errors import SeedRunExecutionError
from care_demo_facility_setup.services.seed_packs import DEFAULT_PACK_SLUG
from care_demo_facility_setup.services.seed_runs import create_attached_seed_run

# Clearer panel keys than raw step keys (title-case still works either way).
_SUMMARY_KEYS = {
    "inventory_items": "product_knowledges",
}

_STAT_LABELS = {
    "created": "created",
    "attached": "attached",
    "reused": "reused",
    "products_received": "received",
    "transferred": "transferred",
    "categories_created": "categories",
    "departments_created": "departments",
    "departments_reused": "departments reused",
    "locations_created": "locations",
    "healthcare_services_created": "services",
    "op_closed": "OP",
    "ip_in_progress": "IP",
    "emergency": "emergency",
    "beds_assigned": "beds",
}


def seed_existing_facility(
    *,
    facility_external_id: str,
    geo_organization_external_id: str,
    requested_by,
    pack_slug: str = DEFAULT_PACK_SLUG,
    profile_slug: str = "local",
) -> SeedRun:
    """Attach pack seed data to an existing facility and execute synchronously.

    Returns the SeedRun on SUCCEEDED. Raises SeedRunExecutionError (or the
    underlying step exception) on failure so the sandbox task can mark the job
    failed.
    """
    if not requested_by or not getattr(requested_by, "is_superuser", False):
        raise SeedRunExecutionError("Seed run must be requested by a superuser.")

    run = create_attached_seed_run(
        facility_external_id=str(facility_external_id),
        geo_organization_external_id=str(geo_organization_external_id),
        requested_by=requested_by,
        pack_slug=pack_slug,
        profile_slug=profile_slug,
    )
    DemoSeedRunner(run).execute()
    run.refresh_from_db()
    if run.status != SeedRunStatus.SUCCEEDED:
        raise SeedRunExecutionError(run.error or "Attached seed run did not succeed.")
    return run


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _join_parts(parts: list[str]) -> str | None:
    return " · ".join(parts) if parts else None


def _format_stats_summary(key: str, stats) -> str | None:
    """Build a short labeled string from step stats when message is absent."""
    if stats is True or stats is None or stats == {}:
        return None
    if isinstance(stats, bool):
        return None
    if _is_int(stats):
        return str(stats)
    if not isinstance(stats, dict):
        return None

    if key in {"inventory_items", "product_knowledges"}:
        created = stats.get("created")
        received = stats.get("products_received")
        transferred = stats.get("transferred")
        parts = []
        if _is_int(created):
            parts.append(f"{created} product knowledges")
        if _is_int(received):
            parts.append(f"{received} received")
        if _is_int(transferred):
            parts.append(f"{transferred} transferred")
        if parts:
            return _join_parts(parts)

    if key == "clinical_visits":
        created = stats.get("created")
        if _is_int(created):
            breakdown = []
            for stat_key, label in (
                ("op_closed", "OP"),
                ("ip_in_progress", "IP"),
                ("emergency", "emergency"),
            ):
                value = stats.get(stat_key)
                if _is_int(value) and value:
                    breakdown.append(f"{value} {label}")
            if breakdown:
                return f"{created} ({', '.join(breakdown)})"
            return str(created)

    if key == "facility":
        attached = stats.get("attached")
        created = stats.get("created")
        parts = []
        if _is_int(attached) and attached:
            parts.append(f"{attached} attached")
        if _is_int(created) and created:
            parts.append(f"{created} created")
        if parts:
            return ", ".join(parts)
        if _is_int(attached):
            return "attached" if attached else "0 attached"
        if _is_int(created):
            return f"{created} created"

    if key == "facility_foundation":
        parts = []
        for stat_key, label in (
            ("departments_created", "departments"),
            ("departments_reused", "departments reused"),
            ("locations_created", "locations"),
            ("healthcare_services_created", "services"),
        ):
            value = stats.get(stat_key)
            if _is_int(value) and value:
                parts.append(f"{value} {label}")
        if parts:
            return _join_parts(parts)

    if key == "questionnaires":
        created = stats.get("created")
        reused = stats.get("reused")
        parts = []
        if _is_int(created):
            parts.append(f"{created} created")
        if _is_int(reused):
            parts.append(f"{reused} reused")
        if parts:
            return ", ".join(parts)

    parts = []
    for stat_key, value in stats.items():
        if not _is_int(value):
            continue
        label = _STAT_LABELS.get(stat_key, stat_key.replace("_", " "))
        parts.append(f"{value} {label}")
    return _join_parts(parts)


def _step_summary(step) -> str | None:
    """Human-readable value for one succeeded seed step."""
    message = getattr(step, "message", None)
    if isinstance(message, str) and message.strip():
        return message.strip()
    return _format_stats_summary(step.key, getattr(step, "stats", None))


def summarize_seed_run(run: SeedRun) -> dict:
    """Map SeedRun steps into readable summaries for the Experience sandbox panel.

    Values are short strings (or rarely plain ints) derived from each step's
    seeder ``message`` when present, otherwise from labeled ``stats``. Debug
    identifiers live under ``_meta`` (Experience skips ``_`` keys). Failed
    steps are omitted.
    """
    loaded: dict = {
        "_meta": {
            "seed_run_id": str(run.external_id),
            "pack_slug": run.pack_slug,
            "profile_slug": run.profile_slug,
        },
    }
    for step in run.steps.all().order_by("order"):
        if step.key == "validate":
            continue
        status = step.status.value if hasattr(step.status, "value") else step.status
        if status != SeedRunStepStatus.SUCCEEDED:
            continue
        summary = _step_summary(step)
        if summary is not None:
            loaded[_SUMMARY_KEYS.get(step.key, step.key)] = summary
    return loaded


def _int_or_zero(stats: dict, key: str) -> int:
    value = stats.get(key)
    return value if _is_int(value) else 0


def _has_int(stats: dict, *keys: str) -> bool:
    return any(_is_int(stats.get(key)) for key in keys)


def _created_reused_total(stats: dict) -> int | None:
    """Sum created+reused when either is tracked; else created alone."""
    if not _has_int(stats, "created", "reused"):
        return None
    return _int_or_zero(stats, "created") + _int_or_zero(stats, "reused")


def _emit_counts_from_stats(loaded: dict, key: str, stats) -> None:
    """Map one step's stats into flat resource→int entries (no seeder messages)."""
    if stats is True or stats is None or stats == {}:
        return
    if isinstance(stats, bool):
        return
    if _is_int(stats):
        loaded[key] = stats
        return
    if not isinstance(stats, dict):
        return

    if key == "facility":
        attached = stats.get("attached")
        created = stats.get("created")
        if (_is_int(attached) and attached) or (_is_int(created) and created):
            loaded["facility"] = 1
        return

    if key == "facility_foundation":
        if _has_int(stats, "departments_created", "departments_reused"):
            loaded["departments"] = _int_or_zero(stats, "departments_created") + _int_or_zero(
                stats, "departments_reused"
            )
        if _is_int(stats.get("locations_created")):
            loaded["locations"] = stats["locations_created"]
        if _is_int(stats.get("healthcare_services_created")):
            loaded["healthcare_services"] = stats["healthcare_services_created"]
        return

    if key == "inventory_items":
        if _is_int(stats.get("created")):
            loaded["product_knowledges"] = stats["created"]
        if _is_int(stats.get("products_received")):
            loaded["products"] = stats["products_received"]
        return

    if key in {"patients", "clinical_visits"}:
        created = stats.get("created")
        if _is_int(created):
            loaded[key] = created
        return

    total = _created_reused_total(stats)
    if total is not None:
        loaded[key] = total


def summarize_seed_run_counts(run: SeedRun) -> dict:
    """Map SeedRun steps into flat resource→count ints for Experience Loaded data.

    Ignores seeder ``message`` strings; reads ``stats`` only. Skips ``validate``
    and non-SUCCEEDED steps. Returns only resource→int counts (no ``_meta``).
    Omits transfer/beds noise.
    """
    loaded: dict = {}
    for step in run.steps.all().order_by("order"):
        if step.key == "validate":
            continue
        status = step.status.value if hasattr(step.status, "value") else step.status
        if status != SeedRunStepStatus.SUCCEEDED:
            continue
        _emit_counts_from_stats(loaded, step.key, getattr(step, "stats", None))
    return loaded
