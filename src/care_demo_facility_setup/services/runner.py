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
from care_demo_facility_setup.services.seed_context import SeedContext
from care_demo_facility_setup.services.seed_errors import SeedRunExecutionError
from care_demo_facility_setup.services.seed_packs import load_profile, load_seed_pack
from care_demo_facility_setup.services.seed_step_registry import (
    SeedStepDefinition,
    get_executable_seed_step_definitions,
)


class DemoSeedRunner:
    def __init__(self, run: SeedRun):
        self.run = run
        self.pack = load_seed_pack(run.pack_slug)
        profile = load_profile(run.pack_slug, run.profile_slug)
        geo_organization = self._resolve_geo_organization(run, profile)
        self.context = SeedContext(
            client=CareSeedClient(run.requested_by),
            artifacts=SeedArtifactStore(run),
            geo_organization=geo_organization,
            run=run,
            pack=self.pack,
            profile=profile,
        )

    @staticmethod
    def _resolve_geo_organization(run: SeedRun, profile: dict) -> str:
        """Prefer caller-injected geo (attach/sandbox); fall back to profile."""
        payload = run.request_payload or {}
        geo = payload.get("geo_organization_external_id") or profile.get("geo_organization_external_id")
        if not geo:
            raise SeedRunExecutionError("No geo_organization_external_id on the seed run or profile.")
        return str(geo)

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
            for step_definition in get_executable_seed_step_definitions(self.pack["manifest"]):
                step = self._get_step(step_definition.key)
                # Attach mode (and any pre-completed step) must not re-run.
                if step.status in {
                    SeedRunStepStatus.SUCCEEDED,
                    SeedRunStepStatus.SKIPPED,
                }:
                    continue
                self._execute_seed_step(step_definition)
        except Exception as exc:
            self._mark_pending_steps_skipped("Skipped because an earlier step failed.")
            self._mark_run(
                SeedRunStatus.FAILED,
                error=self._safe_error(exc),
                finished=True,
            )
            raise
        self._mark_run(SeedRunStatus.SUCCEEDED, error="", finished=True)

    def _execute_seed_step(self, step_definition: SeedStepDefinition):
        step = self._get_step(step_definition.key)
        self._mark_step(step, SeedRunStepStatus.RUNNING, started=True)
        stats = step_definition.initial_stats()
        try:
            if not step_definition.executor:
                raise SeedRunExecutionError(f"Seed step {step_definition.key} is not executable.")
            result = step_definition.executor(self.context, step)
            self._mark_step(
                step,
                SeedRunStepStatus.SUCCEEDED,
                message=result.message,
                stats=result.stats,
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
