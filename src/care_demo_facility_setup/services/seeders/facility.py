from __future__ import annotations

from care_demo_facility_setup.models import SeedRunStep
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.seed_artifacts import SeedArtifactStore
from care_demo_facility_setup.services.seed_payloads import build_facility_payload


class FacilitySeeder:
    def __init__(
        self,
        *,
        client: CareSeedClient,
        artifacts: SeedArtifactStore,
        geo_organization: str,
        run_id: int,
    ):
        self.client = client
        self.artifacts = artifacts
        self.geo_organization = geo_organization
        self.run_id = run_id

    def seed(self, *, step: SeedRunStep, facility_template: dict) -> tuple[str, dict]:
        payload = build_facility_payload(facility_template, self.run_id)
        facility = self.client.create_facility(self.geo_organization, payload)
        facility_payload = self.artifacts.store(
            step=step,
            ref=facility_template.get("ref", "facility:main"),
            resource_type="Facility",
            payload=facility,
        )
        message = f"Created facility {facility_payload.get('name', '')}".strip()
        return message, {"created": 1}
