from __future__ import annotations

from care_demo_facility_setup.models import SeedRunStep
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.seed_artifacts import SeedArtifactStore
from care_demo_facility_setup.services.seed_payloads import build_specimen_definition_payload


class SpecimenDefinitionSeeder:
    def __init__(
        self,
        *,
        client: CareSeedClient,
        artifacts: SeedArtifactStore,
    ):
        self.client = client
        self.artifacts = artifacts

    def seed(self, *, step: SeedRunStep, specimens_config: list, facility_template: dict) -> tuple[str, dict]:
        facility_id = self.artifacts.external_id(facility_template.get("ref", "facility:main"))
        created = 0
        for specimen_template in specimens_config:
            payload = build_specimen_definition_payload(specimen_template)
            specimen = self.client.create_specimen_definition(facility_id, payload)
            self.artifacts.store(
                step=step,
                ref=specimen_template.get("ref", f"specimen_definition:{specimen_template['slug_value']}"),
                resource_type="SpecimenDefinition",
                payload=specimen,
            )
            created += 1
        return f"Created {created} specimen definitions.", {"created": created}
