from __future__ import annotations

from collections import UserDict
from collections.abc import Mapping

from care_demo_facility_setup.models import SeedRun, SeedRunArtifact, SeedRunStep
from care_demo_facility_setup.services.seed_errors import SeedRunExecutionError


class SeedArtifactStore:
    def __init__(self, run: SeedRun):
        self.run = run

    def external_id(self, ref: str) -> str:
        try:
            artifact = SeedRunArtifact.objects.get(run=self.run, ref=ref)
        except SeedRunArtifact.DoesNotExist as exc:
            raise SeedRunExecutionError(f"Missing required artifact: {ref}") from exc
        if not artifact.resource_external_id:
            raise SeedRunExecutionError(f"Artifact {ref} does not contain a resource id.")
        return str(artifact.resource_external_id)

    def store(
        self,
        *,
        step: SeedRunStep,
        ref: str,
        resource_type: str,
        payload,
    ) -> dict:
        plain_payload = to_plain(payload)
        SeedRunArtifact.objects.update_or_create(
            run=self.run,
            ref=ref,
            defaults={
                "step": step,
                "resource_type": resource_type,
                "resource_external_id": plain_payload.get("id"),
                "slug": plain_payload.get("slug", ""),
                "payload": plain_payload,
            },
        )
        return plain_payload

    def payload_external_id(self, payload: dict, ref: str) -> str:
        resource_id = payload.get("id")
        if not resource_id:
            raise SeedRunExecutionError(f"CARE API response for {ref} did not include an id.")
        return str(resource_id)


def to_plain(value):
    if isinstance(value, UserDict):
        return {key: to_plain(item) for key, item in value.data.items()}
    if isinstance(value, Mapping):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    return value


def get_value(value, key: str, default=None):
    if isinstance(value, UserDict):
        return value.data.get(key, default)
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)
