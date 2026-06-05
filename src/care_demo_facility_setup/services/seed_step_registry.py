from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from care_demo_facility_setup.models import SeedRunStep
from care_demo_facility_setup.services.seed_context import SeedContext, SeedResult
from care_demo_facility_setup.services.seeders import (
    ActivityDefinitionSeeder,
    ChargeItemDefinitionSeeder,
    FacilityFoundationSeeder,
    FacilitySeeder,
    ObservationDefinitionSeeder,
    PatientSeeder,
    SpecimenDefinitionSeeder,
)
from care_demo_facility_setup.services.validators import (
    SeedStepValidator,
    validate_activity_definitions,
    validate_charge_item_definitions,
    validate_facility,
    validate_facility_foundation,
    validate_observation_definitions,
    validate_patients,
    validate_specimen_definitions,
)

SeedStepExecutor = Callable[[SeedContext, SeedRunStep], SeedResult]
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
    validator: SeedStepValidator | None = None
    initial_stats: InitialStatsFactory = dict

    @property
    def executable(self) -> bool:
        return self.executor is not None


def _seed_facility(context: SeedContext, step: SeedRunStep) -> SeedResult:
    message, stats = FacilitySeeder(
        client=context.client,
        artifacts=context.artifacts,
        geo_organization=context.geo_organization,
        run_id=context.run.id,
    ).seed(step=step, facility_template=context.pack["facility"])
    return SeedResult(message=message, stats=stats)


def _seed_patients(context: SeedContext, step: SeedRunStep) -> SeedResult:
    message, stats = PatientSeeder(
        client=context.client,
        artifacts=context.artifacts,
        geo_organization=context.geo_organization,
        run_id=context.run.id,
    ).seed(step=step, patients_config=context.pack["patients"])
    return SeedResult(message=message, stats=stats)


def _facility_foundation_initial_stats() -> dict:
    return {
        "departments_created": 0,
        "departments_reused": 0,
        "locations_created": 0,
        "healthcare_services_created": 0,
    }


def _seed_facility_foundation(context: SeedContext, step: SeedRunStep) -> SeedResult:
    message, stats = FacilityFoundationSeeder(
        client=context.client,
        artifacts=context.artifacts,
    ).seed(
        step=step,
        facility_template=context.pack["facility"],
        foundation=context.pack["facility_foundation"],
    )
    return SeedResult(message=message, stats=stats)


def _seed_specimen_definitions(context: SeedContext, step: SeedRunStep) -> SeedResult:
    message, stats = SpecimenDefinitionSeeder(
        client=context.client,
        artifacts=context.artifacts,
    ).seed(
        step=step,
        specimens_config=context.pack["specimens"],
        facility_template=context.pack["facility"],
    )
    return SeedResult(message=message, stats=stats)


def _seed_observation_definitions(context: SeedContext, step: SeedRunStep) -> SeedResult:
    message, stats = ObservationDefinitionSeeder(
        client=context.client,
        artifacts=context.artifacts,
    ).seed(
        step=step,
        observations_config=context.pack["observations"],
        facility_template=context.pack["facility"],
    )
    return SeedResult(message=message, stats=stats)


def _seed_charge_item_definitions(context: SeedContext, step: SeedRunStep) -> SeedResult:
    message, stats = ChargeItemDefinitionSeeder(
        client=context.client,
        artifacts=context.artifacts,
    ).seed(
        step=step,
        charges_config=context.pack["charge_item_definitions"],
        facility_template=context.pack["facility"],
        categories_config=context.pack.get(
            "charge_item_categories",
            [{"title": "Lab Tests", "slug_value": "lab-tests"}],
        ),
    )
    return SeedResult(message=message, stats=stats)


def _seed_activity_definitions(context: SeedContext, step: SeedRunStep) -> SeedResult:
    message, stats = ActivityDefinitionSeeder(
        client=context.client,
        artifacts=context.artifacts,
    ).seed(
        step=step,
        activities_config=context.pack["activity_definitions"],
        facility_template=context.pack["facility"],
        categories_config=context.pack.get(
            "activity_categories",
            [{"title": "Laboratory", "slug_value": "laboratory"}],
        ),
    )
    return SeedResult(message=message, stats=stats)


DEFAULT_STEP_KEYS = (
    "validate",
    "facility",
    "patients",
    "facility_foundation",
    "specimen_definitions",
    "observation_definitions",
    "charge_item_definitions",
    "activity_definitions",
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
        validator=validate_facility,
    ),
    SeedStepDefinition(
        key="patients",
        title="Create demo patients",
        resource_key="patients",
        depends_on=("facility",),
        executor=_seed_patients,
        validator=validate_patients,
        initial_stats=lambda: {"created": 0},
    ),
    SeedStepDefinition(
        key="facility_foundation",
        title="Create facility foundation",
        resource_key="facility_foundation",
        depends_on=("facility",),
        executor=_seed_facility_foundation,
        validator=validate_facility_foundation,
        initial_stats=_facility_foundation_initial_stats,
    ),
    SeedStepDefinition(
        key="specimen_definitions",
        title="Create specimen definitions",
        resource_key="specimens",
        depends_on=("facility",),
        executor=_seed_specimen_definitions,
        validator=validate_specimen_definitions,
        initial_stats=lambda: {"created": 0},
    ),
    SeedStepDefinition(
        key="observation_definitions",
        title="Create observation definitions",
        resource_key="observations",
        depends_on=("facility",),
        executor=_seed_observation_definitions,
        validator=validate_observation_definitions,
        initial_stats=lambda: {"created": 0},
    ),
    SeedStepDefinition(
        key="charge_item_definitions",
        title="Create charge item definitions",
        resource_key="charge_item_definitions",
        depends_on=("facility",),
        executor=_seed_charge_item_definitions,
        validator=validate_charge_item_definitions,
        initial_stats=lambda: {"created": 0, "categories_created": 0},
    ),
    SeedStepDefinition(
        key="activity_definitions",
        title="Create activity definitions",
        resource_key="activity_definitions",
        depends_on=(
            "facility",
            "facility_foundation",
            "specimen_definitions",
            "observation_definitions",
            "charge_item_definitions",
        ),
        executor=_seed_activity_definitions,
        validator=validate_activity_definitions,
        initial_stats=lambda: {"created": 0, "categories_created": 0},
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
