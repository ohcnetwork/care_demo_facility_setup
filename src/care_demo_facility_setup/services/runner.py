from __future__ import annotations

from collections import UserDict
from collections.abc import Mapping

from django.utils import timezone

from care_demo_facility_setup.models import (
    SeedRun,
    SeedRunArtifact,
    SeedRunStatus,
    SeedRunStep,
    SeedRunStepStatus,
)
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.seed_packs import load_profile, load_seed_pack


class SeedRunExecutionError(RuntimeError):
    pass


class DemoSeedRunner:
    def __init__(self, run: SeedRun):
        self.run = run
        self.pack = load_seed_pack(run.pack_slug)
        self.profile = load_profile(run.pack_slug, run.profile_slug)
        self.geo_organization = self.profile["geo_organization_external_id"]
        self.client = CareSeedClient(run.requested_by)

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
            payload = self._build_facility_payload()
            facility = self.client.create_facility(self.geo_organization, payload)
            facility_payload = _to_plain(facility)
            SeedRunArtifact.objects.update_or_create(
                run=self.run,
                ref=self.pack["facility"].get("ref", "facility:main"),
                defaults={
                    "step": step,
                    "resource_type": "Facility",
                    "resource_external_id": facility_payload.get("id"),
                    "slug": facility_payload.get("slug", ""),
                    "payload": facility_payload,
                },
            )
            self._mark_step(
                step,
                SeedRunStepStatus.SUCCEEDED,
                message=f"Created facility {facility_payload.get('name', '')}".strip(),
                stats={"created": 1},
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
        created = 0
        try:
            for index, patient_template in enumerate(
                self.pack["patients"]["patients"],
                start=1,
            ):
                payload = self._build_patient_payload(patient_template, index)
                patient = self.client.create_patient(self.geo_organization, payload)
                patient_payload = _to_plain(patient)
                SeedRunArtifact.objects.update_or_create(
                    run=self.run,
                    ref=patient_template.get("ref", f"patient:{index:03d}"),
                    defaults={
                        "step": step,
                        "resource_type": "Patient",
                        "resource_external_id": patient_payload.get("id"),
                        "slug": patient_payload.get("slug", ""),
                        "payload": patient_payload,
                    },
                )
                created += 1
            self._mark_step(
                step,
                SeedRunStepStatus.SUCCEEDED,
                message=f"Created {created} patients.",
                stats={"created": created},
                finished=True,
            )
        except Exception as exc:
            self._mark_step(
                step,
                SeedRunStepStatus.FAILED,
                message=self._safe_error(exc),
                stats={"created": created},
                finished=True,
            )
            raise

    def _build_facility_payload(self) -> dict:
        template = dict(self.pack["facility"])
        run_number = self.run.id
        payload = {
            key: value
            for key, value in template.items()
            if key
            not in {
                "ref",
                "name_template",
                "description_template",
                "phone_number_template",
            }
        }
        payload["name"] = template.get("name_template", "Demo Facility {run_number}").format(
            run_number=run_number,
        )
        payload["description"] = template.get(
            "description_template",
            "Demo facility created by seed run #{run_number}",
        ).format(run_number=run_number)
        payload.setdefault("phone_number", self._facility_phone_number())
        return payload

    def _facility_phone_number(self) -> str:
        local_number = f"9{self.run.id % 1_000_000_000:09d}"
        template = self.pack["facility"].get(
            "phone_number_template",
            "+91{local_number}",
        )
        return template.format(local_number=local_number, run_number=self.run.id)

    def _build_patient_payload(self, template: dict, index: int) -> dict:
        payload = {key: value for key, value in template.items() if key not in {"ref", "first_name", "last_name"}}
        first_name = template.get("first_name", "Demo")
        last_name = template.get("last_name", f"Patient {index}")
        payload.setdefault("name", f"{first_name} {last_name}".strip())
        payload.setdefault("phone_number", self._patient_phone_number(index))
        return payload

    def _patient_phone_number(self, index: int) -> str:
        local_number = f"8{self.run.id % 1000:03d}" f"{index:02d}" f"{((self.run.id * 37) + index) % 10000:04d}"
        template = self.pack["patients"].get(
            "phone_number_template",
            "+91{local_number}",
        )
        return template.format(local_number=local_number, run_number=self.run.id, index=index)

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


def _to_plain(value):
    if isinstance(value, UserDict):
        return {key: _to_plain(item) for key, item in value.data.items()}
    if isinstance(value, Mapping):
        return {key: _to_plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    return value
