from __future__ import annotations

from care_demo_facility_setup.models import SeedRunStep
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.seed_artifacts import SeedArtifactStore, get_value
from care_demo_facility_setup.services.seed_errors import SeedRunExecutionError


class FacilityFoundationSeeder:
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
        facility_template: dict,
        foundation: dict,
    ) -> tuple[str, dict]:
        stats = {
            "departments_created": 0,
            "departments_reused": 0,
            "locations_created": 0,
            "healthcare_services_created": 0,
        }
        facility_id = self.artifacts.external_id(facility_template.get("ref", "facility:main"))
        department_ids = self._create_departments(
            step,
            facility_id,
            foundation["departments"],
            stats,
        )
        location_ids = self._create_locations(
            step,
            facility_id,
            foundation["locations"],
            department_ids,
            stats,
        )
        self._create_healthcare_services(
            step,
            facility_id,
            foundation["healthcare_services"],
            department_ids,
            location_ids,
            stats,
        )
        message = (
            f"Created foundation resources: {stats['departments_created']} departments, "
            f"{stats['locations_created']} locations, "
            f"{stats['healthcare_services_created']} healthcare services. "
            f"Reused {stats['departments_reused']} department."
        )
        return message, stats

    def _create_departments(
        self,
        step: SeedRunStep,
        facility_id: str,
        department_templates: list[dict],
        stats: dict,
    ) -> dict[str, str]:
        department_ids = {}
        existing_organizations = self.client.get_facility_organizations(facility_id)
        for department_template in department_templates:
            ref = department_template["ref"]
            if department_template.get("reuse_existing"):
                organization = self._find_facility_organization(
                    existing_organizations,
                    department_template["name"],
                )
                if not organization:
                    raise SeedRunExecutionError(
                        "Could not find auto-created facility organization: " f"{department_template['name']}"
                    )
                organization_payload = self.artifacts.store(
                    step=step,
                    ref=ref,
                    resource_type="FacilityOrganization",
                    payload=organization,
                )
                department_ids[ref] = self.artifacts.payload_external_id(organization_payload, ref)
                stats["departments_reused"] += 1
                continue

            payload = {key: value for key, value in department_template.items() if key not in {"ref", "reuse_existing"}}
            payload.setdefault("org_type", "dept")
            payload.setdefault("active", True)
            payload.setdefault(
                "description",
                f"{payload['name']} department for the demo facility.",
            )
            organization = self.client.create_facility_organization(facility_id, payload)
            organization_payload = self.artifacts.store(
                step=step,
                ref=ref,
                resource_type="FacilityOrganization",
                payload=organization,
            )
            department_ids[ref] = self.artifacts.payload_external_id(organization_payload, ref)
            stats["departments_created"] += 1
        return department_ids

    def _create_locations(
        self,
        step: SeedRunStep,
        facility_id: str,
        location_templates: list[dict],
        department_ids: dict[str, str],
        stats: dict,
    ) -> dict[str, str]:
        location_ids = {}
        for sort_index, location_template in enumerate(location_templates, start=1):
            ref = location_template["ref"]
            payload = {
                key: value
                for key, value in location_template.items()
                if key not in {"ref", "parent_ref", "organization_refs"}
            }
            parent_ref = location_template.get("parent_ref")
            if parent_ref:
                payload["parent"] = location_ids[parent_ref]
            organization_refs = location_template.get("organization_refs") or ["department:administration"]
            payload["organizations"] = [department_ids[organization_ref] for organization_ref in organization_refs]
            payload.setdefault(
                "description",
                f"{payload['name']} location for the demo facility.",
            )
            payload.setdefault("status", "active")
            payload.setdefault("operational_status", "O")
            payload.setdefault("mode", "kind")
            payload.setdefault("sort_index", sort_index * 10)
            location = self.client.create_location(facility_id, payload)
            location_payload = self.artifacts.store(
                step=step,
                ref=ref,
                resource_type="FacilityLocation",
                payload=location,
            )
            location_ids[ref] = self.artifacts.payload_external_id(location_payload, ref)
            for organization_id in payload["organizations"]:
                self.client.add_organization_to_location(
                    facility_id,
                    location_ids[ref],
                    organization_id,
                )
            stats["locations_created"] += 1
        return location_ids

    def _create_healthcare_services(
        self,
        step: SeedRunStep,
        facility_id: str,
        healthcare_service_templates: list[dict],
        department_ids: dict[str, str],
        location_ids: dict[str, str],
        stats: dict,
    ):
        for service_template in healthcare_service_templates:
            ref = service_template["ref"]
            name = service_template["name"]
            payload = {
                key: value
                for key, value in service_template.items()
                if key not in {"ref", "name", "managing_organization_ref", "location_refs"}
            }
            managing_organization_ref = service_template.get("managing_organization_ref")
            payload["managing_organization"] = (
                department_ids[managing_organization_ref] if managing_organization_ref else None
            )
            payload["locations"] = [
                location_ids[location_ref] for location_ref in service_template.get("location_refs", [])
            ]
            payload.setdefault("extra_details", "")
            payload.setdefault("styling_metadata", {})
            service = self.client.create_healthcare_service(facility_id, name, payload)
            self.artifacts.store(
                step=step,
                ref=ref,
                resource_type="HealthcareService",
                payload=service,
            )
            stats["healthcare_services_created"] += 1

    def _find_facility_organization(self, organizations, name: str):
        return next(
            (organization for organization in organizations if get_value(organization, "name") == name),
            None,
        )
