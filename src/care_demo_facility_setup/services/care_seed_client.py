from __future__ import annotations

from care.fixtures.base import CareFixtureBase
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
        self.base = CareFixtureBase(client)

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
