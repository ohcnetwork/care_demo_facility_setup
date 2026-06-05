#!/usr/bin/env python3
"""Convert packaged demo setup CSV sheets into JSON seed pack files.

The CSVs are what ops shared with me, json is easy to handle so converting
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT_DIR / "src" / "care_demo_facility_setup"
DATA_DIR = PACKAGE_DIR / "data"
SEED_PACK_DIR = PACKAGE_DIR / "seed_packs" / "generic_hospital_v1"
RAW_DIR = SEED_PACK_DIR / "raw"

CSV_FILES = {
    "activities": "Sample import sheet - Activity-Lab.csv",
    "charges": "Sample import sheet - Charge Lab.csv",
    "observations": "Sample import sheet - Observation Lab Definition.csv",
    "product_knowledge": "Sample import sheet - Product Knowledge.csv",
    "specimens": "Sample import sheet - Specimen.csv",
}

SNOMED_SYSTEM = "http://snomed.info/sct"

LOCATION_NAME_ALIASES = {
    "Laboratory": "1st Floor Lab",
}


def clean(value: Any) -> str:
    return str(value or "").strip()


def optional(value: Any) -> str | None:
    value = clean(value)
    return value or None


def to_bool(value: Any) -> bool:
    return clean(value).lower() in {"true", "1", "yes", "y"}


def to_float(value: Any) -> float | None:
    value = clean(value)
    if not value:
        return None
    return float(value)


def coding(system: Any, code: Any, display: Any) -> dict[str, str] | None:
    system = clean(system)
    code = clean(code)
    display = clean(display)
    if not code:
        return None
    return {"system": system, "code": code, "display": display}


def coding_list(system: Any, code: Any, display: Any) -> list[dict[str, str]]:
    systems = split_refs(system)
    codes = split_refs(code)
    displays = split_refs(display)
    codings: list[dict[str, str]] = []
    for index, code_value in enumerate(codes):
        codings.append(
            {
                "system": systems[index] if index < len(systems) else (systems[-1] if systems else ""),
                "code": code_value,
                "display": displays[index] if index < len(displays) else "",
            }
        )
    return codings


def alias_location_name(name: str) -> str:
    return LOCATION_NAME_ALIASES.get(name, name)


def _foundation_name_to_ref(entries: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entry in entries:
        name = clean(entry.get("name"))
        ref = clean(entry.get("ref"))
        if name and ref:
            mapping[name] = ref
    return mapping


def load_foundation_refs() -> tuple[dict[str, str], dict[str, str]]:
    foundation = json.loads((SEED_PACK_DIR / "facility_foundation.json").read_text(encoding="utf-8"))
    return (
        _foundation_name_to_ref(foundation.get("locations", [])),
        _foundation_name_to_ref(foundation.get("healthcare_services", [])),
    )


def resolve_location_ref(name: str, location_refs_by_name: dict[str, str]) -> str:
    foundation_name = alias_location_name(clean(name))
    ref = location_refs_by_name.get(foundation_name)
    if not ref:
        raise ValueError(
            f"Activity references location '{name}' (resolved to '{foundation_name}'), "
            "which has no matching ref in facility_foundation.json."
        )
    return ref


def resolve_service_ref(name: str, service_refs_by_name: dict[str, str]) -> str | None:
    name = clean(name)
    if not name:
        return None
    ref = service_refs_by_name.get(name)
    if not ref:
        raise ValueError(
            f"Activity references healthcare service '{name}', "
            "which has no matching ref in facility_foundation.json."
        )
    return ref


def split_refs(value: Any) -> list[str]:
    return [item.strip() for item in clean(value).split(",") if item.strip()]


def slug_key(slug: str) -> str:
    slug = clean(slug)
    if slug.startswith("activity-"):
        return slug.removeprefix("activity-")
    if slug.endswith("-activity"):
        return slug.removesuffix("-activity")
    return slug


def read_csv(name: str) -> list[dict[str, str]]:
    path = DATA_DIR / name
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(csv_file)]


def specimen_payload(row: dict[str, str]) -> dict[str, Any]:
    container: dict[str, Any] = {}
    capacity = to_float(row["container_capacity_value"])
    capacity_unit = coding(
        row["container_capacity_unit_system"],
        row["container_capacity_unit_code"],
        row["container_capacity_unit_display"],
    )
    if capacity is not None and capacity_unit:
        container["capacity"] = {"value": capacity, "unit": capacity_unit}

    minimum_volume = to_float(row["container_minimum_volume_quantity_value"])
    minimum_volume_unit = coding(
        row["container_minimum_volume_quantity_unit_system"],
        row["container_minimum_volume_quantity_unit_code"],
        row["container_minimum_volume_quantity_unit_display"],
    )
    minimum_volume_string = optional(row["container_minimum_volume_string"])
    if minimum_volume is not None and minimum_volume_unit:
        container["minimum_volume"] = {"quantity": {"value": minimum_volume, "unit": minimum_volume_unit}}
    elif minimum_volume_string:
        container["minimum_volume"] = {"string": minimum_volume_string}

    for key, value in {
        "description": optional(row["container_description"]),
        "cap": coding(
            row["container_cap_system"],
            row["container_cap_code"],
            row["container_cap_display"],
        ),
        "preparation": optional(row["container_preparation"]),
    }.items():
        if value:
            container[key] = value

    type_tested: dict[str, Any] = {
        "is_derived": to_bool(row["is_derived"]),
        "preference": row["preference"] or "preferred",
        "single_use": to_bool(row["single_use"]),
    }
    requirement = optional(row["requirement"])
    if requirement:
        type_tested["requirement"] = requirement

    retention_value = to_float(row["retention_value"])
    retention_unit = coding(
        row["retention_unit_system"],
        row["retention_unit_code"],
        row["retention_unit_display"],
    )
    if retention_value is not None and retention_unit:
        type_tested["retention_time"] = {"value": retention_value, "unit": retention_unit}
    if container:
        type_tested["container"] = container

    payload: dict[str, Any] = {
        "title": row["title"],
        "slug_value": row["slug_value"],
        "description": row["description"],
        "type_collected": coding(
            row["type_collected_system"],
            row["type_collected_code"],
            row["type_collected_display"],
        ),
        "collection": coding(
            row["collection_system"],
            row["collection_code"],
            row["collection_display"],
        ),
        "type_tested": type_tested,
    }
    derived_from_uri = optional(row["derived_from_uri"])
    if derived_from_uri:
        payload["derived_from_uri"] = derived_from_uri
    return {key: value for key, value in payload.items() if value not in (None, "")}


def observation_payload(row: dict[str, str]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": row["title"],
        "slug_value": row["slug_value"],
        "description": row["description"],
        "category": row["category"] or "laboratory",
        "status": row["status"] or "active",
        "code": coding(row["code_system"], row["code_value"], row["code_display"]),
        "permitted_data_type": row["permitted_data_type"] or "quantity",
        "qualified_ranges": [],
    }
    for key, value in {
        "body_site": coding(row["body_site_system"], row["body_site_code"], row["body_site_display"]),
        "method": coding(row["method_system"], row["method_code"], row["method_display"]),
        "permitted_unit": coding(
            row["permitted_unit_system"],
            row["permitted_unit_code"],
            row["permitted_unit_display"],
        ),
        "derived_from_uri": optional(row["derived_from_uri"]),
    }.items():
        if value:
            payload[key] = value
    return {key: value for key, value in payload.items() if value not in (None, "")}


def charge_payload(row: dict[str, str]) -> dict[str, Any]:
    price = to_float(row["price"]) or 0.0
    return {
        "title": row["title"],
        "slug_value": row["slug_value"],
        "description": row["description"],
        "purpose": row["purpose"],
        "price_components": [
            {
                "amount": price,
                "monetary_component_type": "base",
            }
        ],
    }


def activity_payload(
    row: dict[str, str],
    location_refs_by_name: dict[str, str],
    service_refs_by_name: dict[str, str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": row["title"],
        "slug_value": row["slug_value"],
        "description": row["description"],
        "usage": row["usage"],
        "status": row["status"] or "active",
        "classification": row["classification"] or "laboratory",
        "kind": "service_request",
        "category_name": row["category_name"] or "Laboratory",
        "code": coding(row["code_system"], row["code_value"], row["code_display"]),
        "diagnostic_report_codes": coding_list(
            row["diagnostic_report_system"],
            row["diagnostic_report_code"],
            row["diagnostic_report_display"],
        ),
        "specimen_refs": split_refs(row["specimen_slugs"]),
        "observation_refs": split_refs(row["observation_slugs"]),
        "charge_item_definition_refs": split_refs(row["charge_item_slugs"]),
        "location_refs": [
            resolve_location_ref(name, location_refs_by_name) for name in split_refs(row["location_names"])
        ],
        "healthcare_service_ref": resolve_service_ref(row["healthcare_service_name"], service_refs_by_name),
    }
    for key, value in {
        "derived_from_uri": optional(row["derived_from_uri"]),
        "body_site": coding(row["body_site_system"], row["body_site_code"], row["body_site_display"]),
    }.items():
        if value:
            payload[key] = value
    return {key: value for key, value in payload.items() if value not in (None, "")}


def product_knowledge_payload(row: dict[str, str]) -> dict[str, Any]:
    names = []
    alternate_name_type = optional(row["alternateNameType"])
    alternate_name_value = optional(row["alternateNameValue"])
    if alternate_name_type and alternate_name_value:
        names.append({"name_type": alternate_name_type, "name": alternate_name_value})

    payload: dict[str, Any] = {
        "name": row["name"],
        "slug_value": row["slug"],
        "status": "active",
        "product_type": row["productType"] or "medication",
        "code": coding(SNOMED_SYSTEM, row["codeValue"], row["codeDisplay"]),
        "base_unit": {
            "system": "http://unitsofmeasure.org",
            "code": row["baseUnitDisplay"],
            "display": row["baseUnitDisplay"],
        },
        "definitional": {
            "dosage_form": coding(SNOMED_SYSTEM, row["dosageFormCode"], row["dosageFormDisplay"]),
            "intended_routes": [coding(SNOMED_SYSTEM, row["routeCode"], row["routeDisplay"])]
            if row["routeCode"] or row["routeDisplay"]
            else [],
        },
    }
    alternate_identifier = optional(row["alternateIdentifier"])
    if alternate_identifier:
        payload["alternate_identifier"] = alternate_identifier
    if names:
        payload["names"] = names
    return payload


def build_seed_pack() -> None:
    rows = {key: read_csv(filename) for key, filename in CSV_FILES.items()}

    specimens = {row["slug_value"]: specimen_payload(row) for row in rows["specimens"]}
    observations = {row["slug_value"]: observation_payload(row) for row in rows["observations"]}
    charges = {row["slug_value"]: charge_payload(row) for row in rows["charges"]}
    charge_item_categories = [
        {"title": "Lab Tests", "slug_value": "lab-tests"},
        {"title": "Bed Charges", "slug_value": "bed-charges"},
        {"title": "Medicine", "slug_value": "medicine"},
    ]
    activity_categories = [
        {"title": "Laboratory", "slug_value": "laboratory"},
    ]

    location_refs_by_name, service_refs_by_name = load_foundation_refs()

    lab_tests = []
    for row in rows["activities"]:
        activity = activity_payload(row, location_refs_by_name, service_refs_by_name)
        inferred_charge = f"charge-{slug_key(row['slug_value'])}"
        charge_refs = activity.get("charge_item_definition_refs") or [inferred_charge]
        lab_tests.append(
            {
                "slug": row["slug_value"],
                "specimens": [specimens[slug] for slug in activity.get("specimen_refs", []) if slug in specimens],
                "observations": [
                    observations[slug] for slug in activity.get("observation_refs", []) if slug in observations
                ],
                "charge_item_definitions": [charges[slug] for slug in charge_refs if slug in charges],
                "activity": activity,
            }
        )

    activity_definitions = []
    for row in rows["activities"]:
        activity = activity_payload(row, location_refs_by_name, service_refs_by_name)
        activity.pop("category_name", None)
        inferred_charge = f"charge-{slug_key(row['slug_value'])}"
        charge_refs = activity.get("charge_item_definition_refs") or [inferred_charge]
        activity["charge_item_definition_refs"] = [ref for ref in charge_refs if ref in charges]
        activity_definitions.append(activity)

    inventory_items = [
        {
            "slug": row["slug"],
            "resource_category_name": row["resourceCategory"] or "Medicines",
            "product_knowledge": product_knowledge_payload(row),
            "product_extras": {"status": "active", "extensions": {}},
            "stock_quantity": 0,
        }
        for row in rows["product_knowledge"]
    ]

    SEED_PACK_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    generated_files = {
        "manifest.json": {
            "slug": "generic_hospital_v1",
            "name": "Generic Hospital Demo Seed Pack",
            "version": "1.0.0",
            "description": "Packaged demo facility seed data converted from the original CSV import sheets.",
            "resources": {
                "specimens": "specimens.json",
                "observations": "observations.json",
                "charge_item_definitions": "charge_item_definitions.json",
                "charge_item_categories": "charge_item_categories.json",
                "activity_definitions": "activity_definitions.json",
                "activity_categories": "activity_categories.json",
                "lab_tests": "lab_tests.json",
                "inventory_items": "inventory_items.json",
            },
            "profiles_dir": "profiles",
            "source_csvs": CSV_FILES,
            "counts": {
                "lab_tests": len(lab_tests),
                "inventory_items": len(inventory_items),
                "specimens": len(specimens),
                "observations": len(observations),
                "charge_item_definitions": len(charges),
                "charge_item_categories": len(charge_item_categories),
                "activity_definitions": len(activity_definitions),
                "activity_categories": len(activity_categories),
            },
        },
        "specimens.json": list(specimens.values()),
        "observations.json": list(observations.values()),
        "charge_item_definitions.json": list(charges.values()),
        "charge_item_categories.json": charge_item_categories,
        "activity_definitions.json": activity_definitions,
        "activity_categories.json": activity_categories,
        "lab_tests.json": lab_tests,
        "inventory_items.json": inventory_items,
    }

    for filename, content in generated_files.items():
        (SEED_PACK_DIR / filename).write_text(
            json.dumps(content, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    for key, content in rows.items():
        (RAW_DIR / f"{key}.json").write_text(
            json.dumps(content, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    build_seed_pack()
