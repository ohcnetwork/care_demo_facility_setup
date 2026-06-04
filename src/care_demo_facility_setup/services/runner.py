from __future__ import annotations

from django.utils import timezone

from care_demo_facility_setup.models import (
    SeedRun,
    SeedRunStatus,
    SeedRunStep,
    SeedRunStepStatus,
)
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.seed_artifacts import SeedArtifactStore
from care_demo_facility_setup.services.seed_errors import SeedRunExecutionError
from care_demo_facility_setup.services.seed_packs import load_profile, load_seed_pack
from care_demo_facility_setup.services.seeders import (
    FacilityFoundationSeeder,
    FacilitySeeder,
    PatientSeeder,
)


class DemoSeedRunner:
    def __init__(self, run: SeedRun):
        self.run = run
        self.pack = load_seed_pack(run.pack_slug)
        self.profile = load_profile(run.pack_slug, run.profile_slug)
        self.geo_organization = self.profile["geo_organization_external_id"]
        self.client = CareSeedClient(run.requested_by)
        self.artifacts = SeedArtifactStore(run)

    def execute(self):
        if self.run.status in {
            SeedRunStatus.SUCCEEDED,
            SeedRunStatus.FAILED,
            SeedRunStatus.VALIDATION_FAILED,
        }:
            return
        if self.run.dry_run:
            raise SeedRunExecutionError("Dry runs cannot be executed.")
        if not self.run.requested_by or not self.run.requested_by.is_superuser:
            raise SeedRunExecutionError("Seed run must be requested by a superuser.")

        self._mark_run(SeedRunStatus.RUNNING, started=True)
        try:
            self._execute_facility_step()
            self._execute_patients_step()
            self._execute_facility_foundation_step()
        except Exception as exc:
            self._mark_pending_steps_skipped("Skipped because an earlier step failed.")
            self._mark_run(
                SeedRunStatus.FAILED,
                error=self._safe_error(exc),
                finished=True,
            )
            raise
        self._mark_run(SeedRunStatus.SUCCEEDED, error="", finished=True)

    def _execute_facility_step(self):
        step = self._get_step("facility")
        self._mark_step(step, SeedRunStepStatus.RUNNING, started=True)
        try:
            message, stats = FacilitySeeder(
                client=self.client,
                artifacts=self.artifacts,
                geo_organization=self.geo_organization,
                run_id=self.run.id,
            ).seed(step=step, facility_template=self.pack["facility"])
            self._mark_step(
                step,
                SeedRunStepStatus.SUCCEEDED,
                message=message,
                stats=stats,
                finished=True,
            )
        except Exception as exc:
            self._mark_step(
                step,
                SeedRunStepStatus.FAILED,
                message=self._safe_error(exc),
                finished=True,
            )
            raise

    def _execute_patients_step(self):
        step = self._get_step("patients")
        self._mark_step(step, SeedRunStepStatus.RUNNING, started=True)
        stats = {"created": 0}
        try:
            message, stats = PatientSeeder(
                client=self.client,
                artifacts=self.artifacts,
                geo_organization=self.geo_organization,
                run_id=self.run.id,
            ).seed(step=step, patients_config=self.pack["patients"])
            self._mark_step(
                step,
                SeedRunStepStatus.SUCCEEDED,
                message=message,
                stats=stats,
                finished=True,
            )
        except Exception as exc:
            self._mark_step(
                step,
                SeedRunStepStatus.FAILED,
                message=self._safe_error(exc),
                stats=stats,
                finished=True,
            )
            raise

    def _execute_facility_foundation_step(self):
        step = self._get_step("facility_foundation")
        self._mark_step(step, SeedRunStepStatus.RUNNING, started=True)
        stats = {
            "departments_created": 0,
            "departments_reused": 0,
            "locations_created": 0,
            "healthcare_services_created": 0,
        }
        try:
            message, stats = FacilityFoundationSeeder(
                client=self.client,
                artifacts=self.artifacts,
            ).seed(
                step=step,
                facility_template=self.pack["facility"],
                foundation=self.pack["facility_foundation"],
            )
            self._mark_step(
                step,
                SeedRunStepStatus.SUCCEEDED,
                message=message,
                stats=stats,
                finished=True,
            )
        except Exception as exc:
            self._mark_step(
                step,
                SeedRunStepStatus.FAILED,
                message=self._safe_error(exc),
                stats=stats,
                finished=True,
            )
            raise

    def _get_step(self, key: str) -> SeedRunStep:
        return SeedRunStep.objects.get(run=self.run, key=key)

    def _mark_run(
        self,
        status: str,
        *,
        error: str | None = None,
        started: bool = False,
        finished: bool = False,
    ):
        updates = {"status": status}
        if error is not None:
            updates["error"] = error
        if started and not self.run.started_date:
            updates["started_date"] = timezone.now()
        if finished:
            updates["finished_date"] = timezone.now()
        SeedRun.objects.filter(pk=self.run.pk).update(**updates)
        for field, value in updates.items():
            setattr(self.run, field, value)

    def _mark_step(
        self,
        step: SeedRunStep,
        status: str,
        *,
        message: str = "",
        stats: dict | None = None,
        started: bool = False,
        finished: bool = False,
    ):
        updates = {"status": status, "message": message}
        if stats is not None:
            updates["stats"] = stats
        if started and not step.started_date:
            updates["started_date"] = timezone.now()
        if finished:
            updates["finished_date"] = timezone.now()
        SeedRunStep.objects.filter(pk=step.pk).update(**updates)
        for field, value in updates.items():
            setattr(step, field, value)

    def _mark_pending_steps_skipped(self, message: str):
        SeedRunStep.objects.filter(
            run=self.run,
            status=SeedRunStepStatus.PENDING,
        ).update(
            status=SeedRunStepStatus.SKIPPED,
            message=message,
            finished_date=timezone.now(),
        )

    def _safe_error(self, exc: Exception) -> str:
        message = str(exc) or exc.__class__.__name__
        return message[:2000]
