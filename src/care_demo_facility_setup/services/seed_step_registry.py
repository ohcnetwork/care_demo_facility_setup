from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from care_demo_facility_setup.models import SeedRunStep
from care_demo_facility_setup.services.seeders import (
    FacilityFoundationSeeder,
    FacilitySeeder,
    PatientSeeder,
)

SeedStepExecutor = Callable[[object, SeedRunStep], tuple[str, dict]]
InitialStatsFactory = Callable[[], dict]


class SeedStepRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class SeedStepDefinition:
    key: str
    title: str
    resource_key: str | None = None
    depends_on: tuple[str, ...] = ()
    executor: SeedStepExecutor | None = None
    initial_stats: InitialStatsFactory = dict

    @property
    def executable(self) -> bool:
        return self.executor is not None


def _seed_facility(context: object, step: SeedRunStep) -> tuple[str, dict]:
    return FacilitySeeder(
        client=context.client,
        artifacts=context.artifacts,
        geo_organization=context.geo_organization,
        run_id=context.run.id,
    ).seed(step=step, facility_template=context.pack["facility"])


def _seed_patients(context: object, step: SeedRunStep) -> tuple[str, dict]:
    return PatientSeeder(
        client=context.client,
        artifacts=context.artifacts,
        geo_organization=context.geo_organization,
        run_id=context.run.id,
    ).seed(step=step, patients_config=context.pack["patients"])


def _facility_foundation_initial_stats() -> dict:
    return {
        "departments_created": 0,
        "departments_reused": 0,
        "locations_created": 0,
        "healthcare_services_created": 0,
    }


def _seed_facility_foundation(context: object, step: SeedRunStep) -> tuple[str, dict]:
    return FacilityFoundationSeeder(
        client=context.client,
        artifacts=context.artifacts,
    ).seed(
        step=step,
        facility_template=context.pack["facility"],
        foundation=context.pack["facility_foundation"],
    )


DEFAULT_STEP_KEYS = (
    "validate",
    "facility",
    "patients",
    "facility_foundation",
)

AVAILABLE_SEED_STEPS = (
    SeedStepDefinition(
        key="validate",
        title="Validate seed request",
    ),
    SeedStepDefinition(
        key="facility",
        title="Create demo facility",
        resource_key="facility",
        depends_on=("validate",),
        executor=_seed_facility,
    ),
    SeedStepDefinition(
        key="patients",
        title="Create demo patients",
        resource_key="patients",
        depends_on=("facility",),
        executor=_seed_patients,
        initial_stats=lambda: {"created": 0},
    ),
    SeedStepDefinition(
        key="facility_foundation",
        title="Create facility foundation",
        resource_key="facility_foundation",
        depends_on=("facility",),
        executor=_seed_facility_foundation,
        initial_stats=_facility_foundation_initial_stats,
    ),
)

AVAILABLE_SEED_STEPS_BY_KEY = {step.key: step for step in AVAILABLE_SEED_STEPS}


def get_seed_step_definitions(manifest: Mapping[str, object] | None = None) -> tuple[SeedStepDefinition, ...]:
    return tuple(get_seed_step_definition(step_key) for step_key in get_seed_step_keys(manifest))


def get_executable_seed_step_definitions(
    manifest: Mapping[str, object] | None = None,
) -> tuple[SeedStepDefinition, ...]:
    return tuple(step for step in get_seed_step_definitions(manifest) if step.executable)


def get_seed_step_definition(key: str) -> SeedStepDefinition:
    try:
        return AVAILABLE_SEED_STEPS_BY_KEY[key]
    except KeyError as exc:
        raise SeedStepRegistryError(f"Unknown seed step: {key}") from exc


def get_seed_step_keys(manifest: Mapping[str, object] | None = None) -> tuple[str, ...]:
    configured_steps = manifest.get("steps") if manifest else None
    if configured_steps is None:
        return DEFAULT_STEP_KEYS
    if not isinstance(configured_steps, Sequence) or isinstance(configured_steps, str | bytes):
        raise SeedStepRegistryError("Seed pack manifest steps must be a list of step keys.")

    step_keys = []
    for step_key in configured_steps:
        if not isinstance(step_key, str) or not step_key:
            raise SeedStepRegistryError("Seed pack manifest steps must contain non-empty string step keys.")
        if step_key in step_keys:
            raise SeedStepRegistryError(f"Seed pack manifest contains duplicate step: {step_key}")
        step_keys.append(step_key)

    if "validate" not in step_keys:
        step_keys.insert(0, "validate")

    for step_key in step_keys:
        get_seed_step_definition(step_key)

    return tuple(step_keys)
