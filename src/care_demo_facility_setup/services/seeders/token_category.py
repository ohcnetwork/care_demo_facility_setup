from __future__ import annotations

from care_demo_facility_setup.models import SeedRunArtifact, SeedRunStep
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.seed_artifacts import SeedArtifactStore, get_value, to_plain


class TokenCategorySeeder:
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
        token_categories_config: dict,
        facility_template: dict,
    ) -> tuple[str, dict]:
        facility_id = self.artifacts.external_id(facility_template.get("ref", "facility:main"))
        stats = {"created": 0, "reused": 0}

        for index, category_template in enumerate(token_categories_config.get("categories", []), start=1):
            ref = category_template.get("ref", f"token_category:{index:03d}")
            if SeedRunArtifact.objects.filter(run=self.artifacts.run, ref=ref).exists():
                stats["reused"] += 1
                continue

            category = self.client.create_token_category(
                facility_id,
                {
                    "name": category_template["name"],
                    "shorthand": category_template["shorthand"],
                    "resource_type": category_template["resource_type"],
                    "metadata": category_template.get("metadata") or {},
                },
            )
            category_id = get_value(category, "id")
            if category_template.get("default"):
                self.client.set_default_token_category(facility_id, category_id)

            self.artifacts.store(
                step=step,
                ref=ref,
                resource_type="TokenCategory",
                payload={
                    **to_plain(category),
                    "id": category_id,
                },
            )
            stats["created"] += 1

        message = (
            f"Ensured {stats['created'] + stats['reused']} token categories "
            f"({stats['created']} created, {stats['reused']} reused)."
        )
        return message, stats
