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
    local_number = f"8{run_id % 1000:03d}{index:02d}{((run_id * 37) + index) % 10000:04d}"
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


def build_activity_definition_payload(template: dict) -> dict:
    resolution_keys = {
        "ref",
        "category",
        "category_name",
        "specimen_refs",
        "observation_refs",
        "charge_item_definition_refs",
        "location_names",
        "healthcare_service_name",
    }
    payload = {key: value for key, value in template.items() if key not in resolution_keys}
    payload.setdefault("status", "active")
    return payload


def build_user_payload(users_config: dict, template: dict, index: int, run_id: int) -> dict:
    username_prefix = template.get("username_prefix", f"demo_user_{index}")
    email_local = template.get("email_local", username_prefix)
    email_domain = users_config.get("email_domain", "care.demo")
    return {
        "username": f"{username_prefix}_{run_id}",
        "first_name": template.get("first_name", "Demo"),
        "last_name": template.get("last_name", f"User{index}"),
        "email": f"{email_local}_{run_id}@{email_domain}",
        "password": users_config.get("password", "Ohcn@123"),
        "phone_number": user_phone_number(users_config, index, run_id),
        "gender": template.get("gender", "female"),
        "role_orgs": [],
    }


def user_phone_number(users_config: dict, index: int, run_id: int) -> str:
    local_number = f"7{run_id % 1000:03d}{index:02d}{((run_id * 41) + index) % 10000:04d}"
    phone_template = users_config.get(
        "phone_number_template",
        "+91{local_number}",
    )
    return phone_template.format(local_number=local_number, run_number=run_id, index=index)


def build_schedule_availabilities(template: dict) -> list[dict]:
    availabilities = []
    for session in template.get("availabilities", []):
        days_of_week = session.get("days_of_week", [])
        start_time = session["start_time"]
        end_time = session["end_time"]
        availabilities.append(
            {
                "name": session["name"],
                "slot_type": session.get("slot_type", "appointment"),
                "slot_size_in_minutes": session["slot_size_in_minutes"],
                "tokens_per_slot": session["tokens_per_slot"],
                "availability": [
                    {
                        "day_of_week": day,
                        "start_time": start_time,
                        "end_time": end_time,
                    }
                    for day in days_of_week
                ],
            }
        )
    return availabilities
