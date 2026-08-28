from __future__ import annotations

from care.fixtures.base import CareFixtureBase, FixtureError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


class SeedAPIClient(APIClient):
    def get(self, path, data=None, follow=False, **extra):
        extra.setdefault("secure", True)
        response = super().get(
            _with_trailing_slash(path),
            data=data,
            follow=follow,
            **extra,
        )
        return _ensure_drf_response(path, response)

    def post(self, path, data=None, format=None, content_type=None, follow=False, **extra):
        extra.setdefault("secure", True)
        response = super().post(
            _with_trailing_slash(path),
            data=data,
            format=format,
            content_type=content_type,
            follow=follow,
            **extra,
        )
        return _ensure_drf_response(path, response)

    def patch(self, path, data=None, format=None, content_type=None, follow=False, **extra):
        extra.setdefault("secure", True)
        response = super().patch(
            _with_trailing_slash(path),
            data=data,
            format=format,
            content_type=content_type,
            follow=follow,
            **extra,
        )
        return _ensure_drf_response(path, response)


class CareSeedClient:
    """Thin wrapper around CARE fixture helpers for controlled seed execution."""

    def __init__(self, user):
        client = SeedAPIClient()
        client.force_authenticate(user=user)
        self.user = user
        self.base = CareFixtureBase(client)

    @property
    def requested_by_external_id(self) -> str:
        return str(self.user.external_id)

    def create_facility(self, geo_organization: str, payload: dict):
        return self.base.create_facility(geo_organization, **payload)

    def get_facility_organizations(self, facility_id: str):
        return self.base.get_facility_organizations(facility_id)

    def create_facility_organization(self, facility_id: str, payload: dict):
        return self.base.create_facility_organization(facility_id, **payload)

    def create_location(self, facility_id: str, payload: dict):
        return self.base.create_location(facility_id, **payload)

    def add_organization_to_location(
        self,
        facility_id: str,
        location_id: str,
        organization_id: str,
    ):
        return self.base.add_organization_to_location(
            facility_id,
            location_id,
            organization_id,
        )

    def create_healthcare_service(self, facility_id: str, name: str, payload: dict):
        return self.base.create_healthcare_service(facility_id, name, **payload)

    def create_patient(self, geo_organization: str, payload: dict):
        return self.base.create_patient(geo_organization, **payload)

    def create_specimen_definition(self, facility_id: str, payload: dict):
        return self.base.create_specimen_definition(facility_id, **payload)

    def create_observation_definition(self, facility_id: str, payload: dict):
        return self.base.create_observation_definition(facility=facility_id, **payload)

    def create_charge_item_definition(self, facility_id: str, payload: dict):
        return self.base.create_charge_item_definition(facility_id, **payload)

    def create_resource_category(self, facility_id: str, payload: dict):
        return self.base.create_resource_category(facility_id, **payload)

    def create_activity_definition(self, facility_id: str, payload: dict):
        return self.base.create_activity_definition(facility_id, **payload)

    def create_organization(self, payload: dict):
        return self.base.create_organization(**payload)

    def create_product_knowledge(self, payload: dict):
        return self.base.create_product_knowledge(**payload)

    def create_product(self, facility_id: str, payload: dict):
        return self.base.create_product(facility_id, **payload)

    def create_request_order(self, facility_id: str, payload: dict):
        return self.base.create_request_order(facility_id, **payload)

    def update_request_order(self, facility_id: str, order_id: str, payload: dict):
        return self.base.update_request_order(facility_id, order_id, **payload)

    def create_supply_request(self, payload: dict):
        return self.base.create_supply_request(**payload)

    def create_delivery_order(self, facility_id: str, payload: dict):
        return self.base.create_delivery_order(facility_id, **payload)

    def update_delivery_order(self, facility_id: str, order_id: str, payload: dict):
        return self.base.update_delivery_order(facility_id, order_id, **payload)

    def create_supply_delivery(self, payload: dict):
        return self.base.create_supply_delivery(**payload)

    def update_supply_delivery(self, delivery_id: str, payload: dict):
        return self.base.update_supply_delivery(delivery_id, **payload)

    def list_inventory_items(self, facility_id: str, location_id: str, **params):
        return self.base.list_inventory_items(facility_id, location_id, **params)

    def create_encounter(self, payload: dict):
        return self.base.create_encounter(
            payload["patient"],
            payload["facility"],
            organizations=payload.get("organizations"),
            **{key: value for key, value in payload.items() if key not in {"patient", "facility", "organizations"}},
        )

    def update_encounter(self, encounter_id: str, payload: dict):
        url = reverse("encounter-detail", kwargs={"external_id": encounter_id})
        return self.base.patch(url, payload)

    def get_questionnaire(self, slug: str):
        url = reverse("questionnaire-detail", kwargs={"slug": slug})
        response = self.base.client.get(url, format="json")
        if response.status_code == status.HTTP_404_NOT_FOUND:
            return None
        if response.status_code != status.HTTP_200_OK:
            raise FixtureError(f"GET {url} failed ({response.status_code}): {response.data}")
        return response.data

    def create_questionnaire(self, organizations: list[str], payload: dict):
        return self.base.create_questionnaire(organizations, payload)

    def submit_questionnaire(self, slug: str, payload: dict):
        url = reverse("questionnaire-submit", kwargs={"slug": slug})
        return self.base.post(url, payload)

    def upsert_symptoms(self, patient_id: str, datapoints: list[dict]):
        url = reverse("symptom-upsert", kwargs={"patient_external_id": patient_id})
        return self.base.post(url, {"datapoints": datapoints})

    def upsert_diagnosis(self, patient_id: str, datapoints: list[dict]):
        url = reverse("diagnosis-upsert", kwargs={"patient_external_id": patient_id})
        return self.base.post(url, {"datapoints": datapoints})

    def upsert_medication_request(self, patient_id: str, datapoints: list[dict]):
        url = reverse("medication-request-upsert", kwargs={"patient_external_id": patient_id})
        return self.base.post(url, {"datapoints": datapoints})

    def create_location_association(self, facility_id: str, location_id: str, payload: dict):
        url = reverse(
            "association-list",
            kwargs={
                "facility_external_id": facility_id,
                "location_external_id": location_id,
            },
        )
        return self.base.post(url, payload)

    def get_roles(self):
        return self.base.get_roles()

    def create_user(self, geo_organization: str, payload: dict):
        return self.base.create_user(geo_organization, **payload)

    def add_user_to_facility_organization(
        self,
        facility_id: str,
        facility_organization_id: str,
        user_id: str,
        role_id: str,
    ):
        return self.base.add_user_to_facility_organization(
            facility_id,
            facility_organization_id,
            user_id,
            role_id,
        )

    def create_schedule(self, facility_id: str, resource_type: str, resource_id: str, payload: dict):
        return self.base.create_schedule(facility_id, resource_type, resource_id, **payload)

    def create_token_category(self, facility_id: str, payload: dict):
        resource_type = payload["resource_type"]
        return self.base.create_token_category(
            facility_id,
            resource_type,
            **{key: value for key, value in payload.items() if key != "resource_type"},
        )

    def set_default_token_category(self, facility_id: str, category_id: str):
        url = reverse(
            "token-category-set-default",
            kwargs={
                "facility_external_id": facility_id,
                "external_id": category_id,
            },
        )
        return self.base.post(url, {})


def _with_trailing_slash(path):
    path = str(path)
    base, separator, query = path.partition("?")
    if not base.endswith("/"):
        base = f"{base}/"
    return f"{base}{separator}{query}"


def _ensure_drf_response(path, response):
    if hasattr(response, "data"):
        return response
    location = response.get("Location") if hasattr(response, "get") else None
    raise RuntimeError(
        "Internal CARE API request did not return a DRF response: "
        f"path={path}, status={getattr(response, 'status_code', 'unknown')}, "
        f"location={location or '-'}"
    )
