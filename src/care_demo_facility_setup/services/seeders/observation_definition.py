from __future__ import annotations

from care_demo_facility_setup.models import SeedRunStep
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.seed_artifacts import SeedArtifactStore
from care_demo_facility_setup.services.seed_payloads import build_observation_definition_payload


class ObservationDefinitionSeeder:
    def __init__(
        self,
        *,
        client: CareSeedClient,
        artifacts: SeedArtifactStore,
    ):
        self.client = client
        self.artifacts = artifacts

    def seed(self, *, step: SeedRunStep, observations_config: list, facility_template: dict) -> tuple[str, dict]:
        facility_id = self.artifacts.external_id(facility_template.get("ref", "facility:main"))
        created = 0
        for observation_template in observations_config:
            payload = build_observation_definition_payload(observation_template)
            observation = self.client.create_observation_definition(facility_id, payload)
            self.artifacts.store(
                step=step,
                ref=observation_template.get("ref", f"observation_definition:{observation_template['slug_value']}"),
                resource_type="ObservationDefinition",
                payload=observation,
            )
            created += 1
        return f"Created {created} observation definitions.", {"created": created}
