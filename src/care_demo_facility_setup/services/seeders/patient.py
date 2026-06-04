from __future__ import annotations

from care_demo_facility_setup.models import SeedRunStep
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.seed_artifacts import SeedArtifactStore
from care_demo_facility_setup.services.seed_payloads import build_patient_payload


class PatientSeeder:
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

    def seed(self, *, step: SeedRunStep, patients_config: dict) -> tuple[str, dict]:
        created = 0
        for index, patient_template in enumerate(patients_config["patients"], start=1):
            payload = build_patient_payload(patients_config, patient_template, index, self.run_id)
            patient = self.client.create_patient(self.geo_organization, payload)
            self.artifacts.store(
                step=step,
                ref=patient_template.get("ref", f"patient:{index:03d}"),
                resource_type="Patient",
                payload=patient,
            )
            created += 1
        return f"Created {created} patients.", {"created": created}
