from __future__ import annotations

from datetime import datetime, time

from django.conf import settings

from care_demo_facility_setup.services.validators.base import (
    SeedValidationContext,
    ValidationAccumulator,
)


def validate_schedules(context: SeedValidationContext, accumulator: ValidationAccumulator) -> None:
    schedules_config = context.pack.get("schedules")
    schedule_entries = schedules_config.get("schedules") if isinstance(schedules_config, dict) else None
    expected = context.counts.get("schedules")

    if not isinstance(schedule_entries, list):
        accumulator.error("The seed pack must contain schedules.json with a schedules list.")
        return

    if expected is not None and len(schedule_entries) != expected:
        accumulator.error(f"The seed pack must contain exactly {expected} schedule templates.")

    users_config = context.pack.get("users")
    user_refs = set()
    if isinstance(users_config, dict) and isinstance(users_config.get("users"), list):
        user_refs = {
            entry.get("ref")
            for entry in users_config["users"]
            if isinstance(entry, dict) and isinstance(entry.get("ref"), str)
        }

    refs: set[str] = set()
    max_slots = getattr(settings, "MAX_SLOTS_PER_AVAILABILITY", 30)
    for index, entry in enumerate(schedule_entries, start=1):
        if not isinstance(entry, dict):
            accumulator.error(f"schedules[{index}] must be an object.")
            continue

        ref = entry.get("ref")
        if not isinstance(ref, str) or not ref:
            accumulator.error(f"schedules[{index}] must define a non-empty ref.")
        elif ref in refs:
            accumulator.error(f"schedules.json contains duplicate ref {ref}.")
        else:
            refs.add(ref)

        user_ref = entry.get("user_ref")
        if not isinstance(user_ref, str) or not user_ref:
            accumulator.error(f"{ref or f'schedules[{index}]'} must define a non-empty user_ref.")
        elif user_refs and user_ref not in user_refs:
            accumulator.error(f"{ref or f'schedules[{index}]'} references unknown user {user_ref}.")

        availabilities = entry.get("availabilities")
        if not isinstance(availabilities, list) or not availabilities:
            accumulator.error(f"{ref or f'schedules[{index}]'} must define a non-empty availabilities list.")
            continue

        for session_index, session in enumerate(availabilities, start=1):
            _validate_session_math(
                accumulator,
                label=f"{ref or f'schedules[{index}]'} availability[{session_index}]",
                session=session,
                max_slots=max_slots,
            )


def _validate_session_math(
    accumulator: ValidationAccumulator,
    *,
    label: str,
    session,
    max_slots: int,
) -> None:
    if not isinstance(session, dict):
        accumulator.error(f"{label} must be an object.")
        return

    slot_size = session.get("slot_size_in_minutes")
    if not isinstance(slot_size, int) or isinstance(slot_size, bool) or slot_size < 1:
        accumulator.error(f"{label} slot_size_in_minutes must be an integer >= 1.")
        return

    tokens = session.get("tokens_per_slot")
    if not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 1:
        accumulator.error(f"{label} tokens_per_slot must be an integer >= 1.")

    start = _parse_time(session.get("start_time"))
    end = _parse_time(session.get("end_time"))
    if start is None or end is None:
        accumulator.error(f"{label} must define start_time and end_time as HH:MM:SS.")
        return
    if start >= end:
        accumulator.error(f"{label} start_time must be earlier than end_time.")
        return

    duration_seconds = (datetime.combine(datetime.min, end) - datetime.combine(datetime.min, start)).total_seconds()
    slot_seconds = slot_size * 60
    if duration_seconds % slot_seconds != 0:
        accumulator.error(f"{label} duration must be a multiple of slot_size_in_minutes.")
        return

    total_slots = int(duration_seconds // slot_seconds)
    if total_slots > max_slots:
        accumulator.error(
            f"{label} produces {total_slots} slots; maximum allowed is {max_slots} per availability session."
        )

    days = session.get("days_of_week")
    if not isinstance(days, list) or not days:
        accumulator.error(f"{label} must define a non-empty days_of_week list.")
    elif any(not isinstance(day, int) or isinstance(day, bool) or day < 0 or day > 6 for day in days):
        accumulator.error(f"{label} days_of_week entries must be integers from 0 to 6.")


def _parse_time(value) -> time | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return time.fromisoformat(value)
    except ValueError:
        return None
