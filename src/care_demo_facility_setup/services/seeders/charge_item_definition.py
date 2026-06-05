from __future__ import annotations

from care_demo_facility_setup.models import SeedRunStep
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.seed_artifacts import SeedArtifactStore
from care_demo_facility_setup.services.seed_payloads import build_charge_item_definition_payload

CHARGE_RESOURCE_TYPE = "charge_item_definition"


class ChargeItemDefinitionSeeder:
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
        charges_config: list,
        facility_template: dict,
        categories_config: list,
    ) -> tuple[str, dict]:
        facility_id = self.artifacts.external_id(facility_template.get("ref", "facility:main"))
        category_slugs = self._ensure_categories(
            step=step, facility_id=facility_id, categories_config=categories_config
        )
        default_category = categories_config[0]["slug_value"]
        created = 0
        for charge_template in charges_config:
            payload = build_charge_item_definition_payload(charge_template)
            payload["category"] = category_slugs[charge_template.get("category", default_category)]
            charge = self.client.create_charge_item_definition(facility_id, payload)
            self.artifacts.store(
                step=step,
                ref=charge_template.get("ref", f"charge_item_definition:{charge_template['slug_value']}"),
                resource_type="ChargeItemDefinition",
                payload=charge,
            )
            created += 1
        message = f"Created {len(category_slugs)} resource categories and {created} charge item definitions."
        return message, {"created": created, "categories_created": len(category_slugs)}

    def _ensure_categories(self, *, step: SeedRunStep, facility_id: str, categories_config: list) -> dict[str, str]:
        category_slugs: dict[str, str] = {}
        for category_template in categories_config:
            slug_value = category_template["slug_value"]
            payload = {
                "title": category_template["title"],
                "resource_type": CHARGE_RESOURCE_TYPE,
                "slug_value": slug_value,
            }
            category = self.client.create_resource_category(facility_id, payload)
            stored = self.artifacts.store(
                step=step,
                ref=f"resource_category:{CHARGE_RESOURCE_TYPE}:{slug_value}",
                resource_type="ResourceCategory",
                payload=category,
            )
            category_slugs[slug_value] = stored["slug"]
        return category_slugs
