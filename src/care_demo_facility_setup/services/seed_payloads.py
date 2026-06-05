from __future__ import annotations


def build_facility_payload(template: dict, run_id: int) -> dict:
    payload = {
        key: value
        for key, value in template.items()
        if key
        not in {
            "ref",
            "name_template",
            "description_template",
            "phone_number_template",
        }
    }
    payload["name"] = template.get("name_template", "Demo Facility {run_number}").format(
        run_number=run_id,
    )
    payload["description"] = template.get(
        "description_template",
        "Demo facility created by seed run #{run_number}",
    ).format(run_number=run_id)
    payload.setdefault("phone_number", facility_phone_number(template, run_id))
    return payload


def facility_phone_number(template: dict, run_id: int) -> str:
    local_number = f"9{run_id % 1_000_000_000:09d}"
    phone_template = template.get(
        "phone_number_template",
        "+91{local_number}",
    )
    return phone_template.format(local_number=local_number, run_number=run_id)


def build_patient_payload(patients_config: dict, template: dict, index: int, run_id: int) -> dict:
    payload = {key: value for key, value in template.items() if key not in {"ref", "first_name", "last_name"}}
    first_name = template.get("first_name", "Demo")
    last_name = template.get("last_name", f"Patient {index}")
    payload.setdefault("name", f"{first_name} {last_name}".strip())
    payload.setdefault("phone_number", patient_phone_number(patients_config, index, run_id))
    return payload


def patient_phone_number(patients_config: dict, index: int, run_id: int) -> str:
    local_number = f"8{run_id % 1000:03d}" f"{index:02d}" f"{((run_id * 37) + index) % 10000:04d}"
    phone_template = patients_config.get(
        "phone_number_template",
        "+91{local_number}",
    )
    return phone_template.format(local_number=local_number, run_number=run_id, index=index)


def build_specimen_definition_payload(template: dict) -> dict:
    payload = {key: value for key, value in template.items() if key != "ref"}
    payload.setdefault("status", "active")
    return payload


def build_observation_definition_payload(template: dict) -> dict:
    payload = {key: value for key, value in template.items() if key != "ref"}
    payload.setdefault("status", "active")
    return payload


def build_charge_item_definition_payload(template: dict) -> dict:
    payload = {key: value for key, value in template.items() if key != "ref"}
    payload.setdefault("status", "active")
    return payload
