from __future__ import annotations

from care_demo_facility_setup.models import SeedRunArtifact, SeedRunStep
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.seed_artifacts import SeedArtifactStore, get_value, to_plain
from care_demo_facility_setup.services.seed_errors import SeedRunExecutionError
from care_demo_facility_setup.services.seed_payloads import build_user_payload


class UserSeeder:
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

    def seed(
        self,
        *,
        step: SeedRunStep,
        users_config: dict,
        facility_template: dict,
    ) -> tuple[str, dict]:
        facility_id = self.artifacts.external_id(facility_template.get("ref", "facility:main"))
        roles = self.client.get_roles()
        stats = {"created": 0, "reused": 0}

        for index, user_template in enumerate(users_config.get("users", []), start=1):
            ref = user_template.get("ref", f"user:{index:03d}")
            if SeedRunArtifact.objects.filter(run=self.artifacts.run, ref=ref).exists():
                stats["reused"] += 1
                continue

            role_name = user_template.get("role_name")
            role = roles.get(role_name) if role_name else None
            if not role:
                raise SeedRunExecutionError(f"Role '{role_name}' not found for {ref}.")

            org_ref = user_template.get("org_ref")
            if not org_ref:
                raise SeedRunExecutionError(f"User {ref} is missing org_ref.")
            org_id = self.artifacts.external_id(org_ref)

            payload = build_user_payload(users_config, user_template, index, self.run_id)
            user = self.client.create_user(self.geo_organization, payload)
            user_id = get_value(user, "id")
            self.client.add_user_to_facility_organization(
                facility_id,
                org_id,
                user_id,
                get_value(role, "id"),
            )
            self.artifacts.store(
                step=step,
                ref=ref,
                resource_type="User",
                payload={
                    **to_plain(user),
                    "id": user_id,
                    "username": payload["username"],
                    "role_name": role_name,
                    "org_ref": org_ref,
                },
            )
            stats["created"] += 1

        message = (
            f"Ensured {stats['created'] + stats['reused']} facility users "
            f"({stats['created']} created, {stats['reused']} reused)."
        )
        return message, stats
