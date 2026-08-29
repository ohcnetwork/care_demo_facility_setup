from __future__ import annotations

from care_demo_facility_setup.models import SeedRunStep
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.seed_artifacts import SeedArtifactStore
from care_demo_facility_setup.services.seed_payloads import build_activity_definition_payload

ACTIVITY_RESOURCE_TYPE = "activity_definition"


class ActivityDefinitionSeeder:
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
        activities_config: list,
        facility_template: dict,
        categories_config: list,
    ) -> tuple[str, dict]:
        facility_id = self.artifacts.external_id(facility_template.get("ref", "facility:main"))
        category_slugs = self._ensure_categories(
            step=step, facility_id=facility_id, categories_config=categories_config
        )
        default_category = categories_config[0]["slug_value"]
        created = 0
        for activity_template in activities_config:
            payload = build_activity_definition_payload(activity_template)
            payload["specimen_requirements"] = [
                self.artifacts.slug(f"specimen_definition:{slug}")
                for slug in activity_template.get("specimen_refs", [])
            ]
            payload["observation_result_requirements"] = [
                self.artifacts.slug(f"observation_definition:{slug}")
                for slug in activity_template.get("observation_refs", [])
            ]
            payload["charge_item_definitions"] = [
                self.artifacts.slug(f"charge_item_definition:{slug}")
                for slug in activity_template.get("charge_item_definition_refs", [])
            ]
            payload["locations"] = [
                self.artifacts.external_id(ref) for ref in activity_template.get("location_refs", [])
            ]
            service_ref = activity_template.get("healthcare_service_ref")
            payload["healthcare_service"] = self.artifacts.external_id(service_ref) if service_ref else None
            payload["category"] = category_slugs[activity_template.get("category", default_category)]
            activity = self.client.create_activity_definition(facility_id, payload)
            self.artifacts.store(
                step=step,
                ref=activity_template.get("ref", f"activity_definition:{activity_template['slug_value']}"),
                resource_type="ActivityDefinition",
                payload=activity,
            )
            created += 1
        message = f"Created {len(category_slugs)} resource categories and {created} activity definitions."
        return message, {"created": created, "categories_created": len(category_slugs)}

    def _ensure_categories(self, *, step: SeedRunStep, facility_id: str, categories_config: list) -> dict[str, str]:
        category_slugs: dict[str, str] = {}
        for category_template in categories_config:
            slug_value = category_template["slug_value"]
            payload = {
                "title": category_template["title"],
                "resource_type": ACTIVITY_RESOURCE_TYPE,
                "slug_value": slug_value,
            }
            category = self.client.create_resource_category(facility_id, payload)
            stored = self.artifacts.store(
                step=step,
                ref=f"resource_category:{ACTIVITY_RESOURCE_TYPE}:{slug_value}",
                resource_type="ResourceCategory",
                payload=category,
            )
            category_slugs[slug_value] = stored["slug"]
        return category_slugs
