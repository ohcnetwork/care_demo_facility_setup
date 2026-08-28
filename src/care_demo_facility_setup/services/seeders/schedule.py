from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from care_demo_facility_setup.models import SeedRunArtifact, SeedRunStep
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.seed_artifacts import SeedArtifactStore, get_value, to_plain
from care_demo_facility_setup.services.seed_errors import SeedRunExecutionError
from care_demo_facility_setup.services.seed_payloads import build_schedule_availabilities


class ScheduleSeeder:
    def __init__(
        self,
        *,
        client: CareSeedClient,
        artifacts: SeedArtifactStore,
    ):
        self.client = client
        self.artifacts = artifacts

    def seed(
        self,
        *,
        step: SeedRunStep,
        schedules_config: dict,
        facility_template: dict,
    ) -> tuple[str, dict]:
        facility_id = self.artifacts.external_id(facility_template.get("ref", "facility:main"))
        stats = {"created": 0, "reused": 0}

        for index, schedule_template in enumerate(schedules_config.get("schedules", []), start=1):
            ref = schedule_template.get("ref", f"schedule:{index:03d}")
            if SeedRunArtifact.objects.filter(run=self.artifacts.run, ref=ref).exists():
                stats["reused"] += 1
                continue

            user_ref = schedule_template.get("user_ref")
            if not user_ref:
                raise SeedRunExecutionError(f"Schedule {ref} is missing user_ref.")
            resource_id = self.artifacts.external_id(user_ref)

            # CARE ScheduleCreateSpec compares naive datetimes; keep fixtures-style strings.
            now = timezone.now() + timedelta(seconds=5)
            valid_days = schedule_template.get("valid_days", 365)
            schedule = self.client.create_schedule(
                facility_id,
                schedule_template.get("resource_type", "practitioner"),
                resource_id,
                {
                    "name": schedule_template.get("name", "Demo Schedule"),
                    "is_public": schedule_template.get("is_public", True),
                    "valid_from": now.strftime("%Y-%m-%dT%H:%M:%S"),
                    "valid_to": (now + timedelta(days=valid_days)).strftime("%Y-%m-%dT%H:%M:%S"),
                    "availabilities": build_schedule_availabilities(schedule_template),
                },
            )
            self.artifacts.store(
                step=step,
                ref=ref,
                resource_type="Schedule",
                payload={
                    **to_plain(schedule),
                    "id": get_value(schedule, "id"),
                    "user_ref": user_ref,
                },
            )
            stats["created"] += 1

        message = (
            f"Ensured {stats['created'] + stats['reused']} schedules "
            f"({stats['created']} created, {stats['reused']} reused)."
        )
        return message, stats
