from __future__ import annotations

from care_demo_facility_setup.models import SeedRunStep
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.demo_forms import (
    load_demo_form,
    resolve_required_question_ids,
)
from care_demo_facility_setup.services.seed_artifacts import SeedArtifactStore, to_plain
from care_demo_facility_setup.services.seed_errors import SeedRunExecutionError


class QuestionnaireSeeder:
    def __init__(
        self,
        *,
        client: CareSeedClient,
        artifacts: SeedArtifactStore,
        geo_organization: str,
    ):
        self.client = client
        self.artifacts = artifacts
        self.geo_organization = geo_organization

    def seed(self, *, step: SeedRunStep, questionnaires_config: dict) -> tuple[str, dict]:
        forms = questionnaires_config.get("forms") or []
        if not forms:
            raise SeedRunExecutionError("questionnaires.json must define a non-empty forms list.")

        stats = {"created": 0, "reused": 0}
        for form in forms:
            self._ensure_questionnaire(step, form, stats)
        message = f"Ensured {len(forms)} questionnaires ({stats['created']} created, {stats['reused']} reused)."
        return message, stats

    def _ensure_questionnaire(self, step: SeedRunStep, form: dict, stats: dict) -> dict:
        slug = form.get("slug")
        if not isinstance(slug, str) or not slug:
            raise SeedRunExecutionError("Each questionnaires.forms entry must define a non-empty slug.")
        fill_key = form.get("fill_key")
        if not isinstance(fill_key, str) or not fill_key:
            raise SeedRunExecutionError(f"Questionnaire {slug} must define a non-empty fill_key.")
        requirements = form.get("requirements")
        if not isinstance(requirements, list) or not requirements:
            raise SeedRunExecutionError(f"Questionnaire {slug} must define a non-empty requirements list.")

        live = self.client.get_questionnaire(slug)
        if live is None:
            template = load_demo_form(slug)
            create_payload = {key: value for key, value in template.items() if key not in {"organizations"}}
            # CARE questionnaire create freezes version to a string default.
            create_payload["version"] = str(create_payload.get("version") or "1.0")
            live = self.client.create_questionnaire([self.geo_organization], create_payload)
            stats["created"] += 1
        else:
            stats["reused"] += 1

        live_payload = to_plain(live)
        question_ids = self._resolve_question_ids(slug, live_payload, requirements)
        artifact_payload = {
            **live_payload,
            "fill_key": fill_key,
            "slug": slug,
            "question_ids": question_ids,
        }
        self.artifacts.store(
            step=step,
            ref=f"questionnaire:{slug}",
            resource_type="Questionnaire",
            payload=artifact_payload,
        )
        return artifact_payload

    def _resolve_question_ids(
        self,
        slug: str,
        questionnaire: dict,
        requirements: list[dict],
    ) -> dict[str, str]:
        try:
            return resolve_required_question_ids(questionnaire, requirements)
        except ValueError as exc:
            raise SeedRunExecutionError(f"{slug}: {exc}") from exc
