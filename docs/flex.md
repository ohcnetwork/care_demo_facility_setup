# Scalability and Flexibility Check-in

**Date:** 2026-06-04
**Scope:** Architecture review only. This document does not change the current V1 implementation plan.

> **Update (2026-06-05):** Two recommendations from this review have since landed:
> the **seed step registry** (`services/seed_step_registry.py`) and **manifest-driven
> counts** (validators read the manifest `counts` block). The affected items below are
> annotated **RESOLVED** / **PARTIALLY RESOLVED** / **DONE**. The "Suggested Evolution
> Path" phase numbers here predate the current Phase 0–3 scale-out roadmap and are kept
> for history; follow that roadmap for the canonical plan.

## Summary

The current `care_demo_facility_setup` backend architecture is good enough for V1 and the current M1/M2 scope. It supports:

- packaged JSON seed packs;
- profile-based validation;
- auditable `SeedRun`, `SeedRunStep`, and `SeedRunArtifact` records;
- async real execution through Celery;
- controlled CARE API execution through `CareFixtureBase` via `CareSeedClient`;
- resource-specific seeders under `services/seeders/`.

However, it is not yet fully scalable or flexible for a large multi-milestone seed system with many optional modules, dependencies, retries, partial re-runs, or multiple seed-pack variants. The current architecture is intentionally simple and mostly fixed-step.

This is acceptable for V1, but the limitations should be known before adding later milestones such as labs, inventory, users, encounters, questionnaires, schedules, and files.

## Current Strengths

### 1. Good execution boundary

The current execution path is clean:

```text
API / Celery
→ DemoSeedRunner
→ services/seeders/*
→ CareSeedClient
→ CareFixtureBase
→ CARE DRF APIs
```

This is a good separation because:

- `DemoSeedRunner` controls run and step lifecycle.
- `services/seeders/*` owns resource-specific creation logic.
- `CareSeedClient` remains a thin adapter over CARE APIs.
- Resource creation still goes through serializers, permissions, validation, and side effects.

### 2. Good audit model

The three tracking models are a solid foundation:

- `SeedRun`
- `SeedRunStep`
- `SeedRunArtifact`

They provide:

- run history;
- dry-run history;
- step status;
- created resource references;
- payload snapshots for debugging.

This is enough for V1 observability.

### 3. Seeders package is a scalable direction

Moving resource-specific logic into:

```text
services/seeders/
  facility.py
  patient.py
  facility_foundation.py
```

is a good pattern.

Future seeders can be added without making `runner.py` huge:

```text
services/seeders/lab.py
services/seeders/inventory.py
services/seeders/clinical_encounter.py
services/seeders/user.py
services/seeders/questionnaire.py
```

### 4. Shared client reuse is correct

`DemoSeedRunner` creates one `CareSeedClient` per seed run and passes it to every seeder.

That keeps:

- one authenticated CARE API context;
- consistent requester permissions;
- fewer internal API client objects;
- clearer execution behavior.

### 5. JSON-first seed packs are appropriate

The seed pack files make demo data reviewable and versionable.

For V1, packaged JSON files are simpler and safer than DB-backed editable seed packs.

## Current Limitations

### 1. Steps are hard-coded — RESOLVED (2026-06-05)

> **Status:** Resolved. Step keys/titles now come from the seed step registry
> (`services/seed_step_registry.py`), and `DemoSeedRunner.execute()` loops the registry
> instead of calling fixed `_execute_*_step()` methods. Original analysis kept for history.

Previously, the planned steps lived in `services/seed_runs.py`:

```python
PLANNED_STEPS = [
	("validate", "Validate seed request"),
	("facility", "Create demo facility"),
	("patients", "Create demo patients"),
	("facility_foundation", "Create facility foundation"),
]
```

Execution order is also hard-coded in `DemoSeedRunner`:

```python
self._execute_facility_step()
self._execute_patients_step()
self._execute_facility_foundation_step()
```

This is fine for V1, but later every new milestone requires code changes in at least two places:

- planned step list;
- runner execution order.

This is not flexible enough for optional seed sections or multiple seed-pack variants.

### 2. No step registry yet — RESOLVED (2026-06-05)

> **Status:** Resolved. `services/seed_step_registry.py` now defines
> `SeedStepDefinition(key, title, resource_key, depends_on, executor, initial_stats)`
> with `AVAILABLE_SEED_STEPS` / `DEFAULT_STEP_KEYS`. The shape below was the proposal;
> the landed version is close to it. Kept for history.

Originally there was no central registry mapping a step key to:

- title;
- seeder class;
- required seed-pack resource;
- dependencies;
- dry-run behavior;
- summary/stat keys.

A registry would reduce duplication and make future steps easier to add.

Potential future shape:

```python
SEED_STEPS = [
	SeedStepDefinition(
		key="facility",
		title="Create demo facility",
		seeder=FacilitySeeder,
		requires=["facility"],
	),
	SeedStepDefinition(
		key="patients",
		title="Create demo patients",
		seeder=PatientSeeder,
		requires=["patients"],
		depends_on=["facility"],
	),
	SeedStepDefinition(
		key="facility_foundation",
		title="Create facility foundation",
		seeder=FacilityFoundationSeeder,
		requires=["facility_foundation"],
		depends_on=["facility"],
	),
]
```

This is not required for V1, but will help after the next few milestones.

### 3. Validation is still too centralized

`services/seed_packs.py` currently handles:

- pack loading;
- profile loading;
- host validation;
- geo organization validation;
- facility validation;
- patient validation;
- foundation validation.

As seed data grows, this file will become difficult to maintain.

Better future split:

```text
services/
  seed_pack_loader.py
  seed_pack_validator.py
  seed_pack_types.py
  validators/
	facility.py
	patient.py
	facility_foundation.py
	lab.py
	inventory.py
	clinical_encounter.py
```

For V1, this can wait. But it should be done before adding many more resource categories.

### 4. Seed validation is fixed-count and milestone-specific — PARTIALLY RESOLVED (2026-06-05)

> **Status:** Partially resolved (Phase 0). Patient, department, location, and
> healthcare-service counts now come from the manifest `counts` block instead of
> hard-coded numbers. Remaining count/presence rules move fully to the manifest in Phase 1.

Validation previously had rules like:

- exactly 10 patients;
- exactly 10 departments;
- exactly 35 locations;
- exactly 4 healthcare services.

This is okay for a fixed demo pack, but it is not flexible for:

- different hospital sizes;
- specialty-specific packs;
- TeleICU variants;
- optional data sections;
- future pack versions.

Eventually counts should move into manifest-driven validation.

Example:

```json
{
  "counts": {
	"patients": 10,
	"departments": 10,
	"locations": 35
  }
}
```

Validators should compare against manifest requirements instead of hard-coded numbers.

### 5. No generic dependency graph

Current dependencies are implicit in execution order.

Example:

- patients run after facility;
- foundation reads `facility:main`;
- locations depend on parent refs;
- healthcare services depend on department/location refs.

For V1 this is manageable.

Later, labs/inventory/clinical data may need richer dependency handling:

- lab tests depend on healthcare services;
- encounters depend on facility, patient, departments, locations;
- questionnaire responses depend on encounters and questionnaires;
- stock depends on stores, products, suppliers.

Eventually, seed steps may need a simple dependency graph or at least a step registry with `depends_on`.

### 6. No idempotency or resume strategy

The current real run creates new resources.

It does not yet support:

- resume from failed step;
- retry only failed resources;
- skip resources already created in a previous run;
- reuse existing facility;
- refresh/update mode.

That is acceptable for V1, because V1 is "create a new demo facility".

For later production-grade demo setup, we may need:

- artifact-based resume;
- idempotency keys;
- unique seed run naming;
- step-level retries;
- resource-level retries.

### 7. Dry run is validation-only, not a full execution simulation

Current dry run:

- validates seed pack/profile;
- creates `SeedRun` and `SeedRunStep` rows;
- skips resource-creation steps.

It does not simulate every payload or dependency resolution.

This is fine for V1, but later a stronger dry run could produce:

- planned refs;
- dependency graph;
- expected artifact count;
- generated names/phone numbers;
- missing dependency warnings.

### 8. No formal seeder interface yet

Seeders currently follow a convention:

```python
seeder.seed(...)
```

But there is no shared interface/base class.

That is okay now. Later, a formal interface could make runner orchestration generic.

Example:

```python
class BaseSeeder(Protocol):
	def seed(self, *, step: SeedRunStep, context: SeedContext) -> SeedResult:
		...
```

Useful future concepts:

- `SeedContext`
- `SeedResult`
- `SeedStats`
- `SeedStepDefinition`

### 9. `SeedRunStep` and execution are still tightly coupled — PARTIALLY RESOLVED (2026-06-05)

> **Status:** Partially resolved. `DemoSeedRunner.execute()` now runs the generic
> `for step_definition in get_executable_seed_step_definitions(manifest): _execute_seed_step(...)`
> loop. Seeders still receive the runner as an untyped `context`; a typed `SeedContext`
> remains a Phase 1 item.

`DemoSeedRunner` owns all step status handling.

This is acceptable today, but a future generic runner could handle all step lifecycle once:

```python
for step_definition in SEED_STEPS:
	run_step(step_definition)
```

Then resource seeders only create resources and return stats.

### 10. No profile-driven behavior beyond host/geo org

Profiles currently validate environment guardrails and geo organization.

Later profiles may need to control:

- enabled seed sections;
- role mappings;
- questionnaire mappings;
- default user password policy;
- feature flags;
- facility type;
- language/localization;
- state/district mappings.

This can be added later without changing V1.

## Is the current architecture scalable enough?

### For V1

Yes.

The current architecture is good enough for:

- one packaged seed pack;
- one fixed execution path;
- one facility;
- patients;
- facility foundation resources;
- auditable Celery execution.

It is simple and understandable, which is the right tradeoff for V1.

### For the next few milestones

Mostly yes, if we continue using `services/seeders/`.

We can add:

- `seeders/lab.py`
- `seeders/inventory.py`
- `seeders/clinical_encounter.py`

without immediately rewriting everything.

With the step registry in place, a new seeder now mainly needs a `SeedStepDefinition` entry plus a manifest `steps`/`counts` entry, rather than edits to `DemoSeedRunner`. The remaining manual touch point is validation in `seed_packs.py`, which the Phase 1 validator split addresses.

### For a long-term flexible seed engine

Not yet.

Before this becomes a general-purpose demo seeding framework, we should add:

1. step registry; *(done \u2014 2026-06-05)*
2. validator split;
3. manifest-driven step discovery/count validation; *(step discovery + counts done; remaining presence rules in Phase 1)*
4. formal seeder interface/context/result;
5. dependency handling;
6. resume/idempotency design.

## Recommended Future Changes

These are future cleanup items only. They do not change the current V1 plan.

### 1. Add a seed step registry — DONE (2026-06-05)

> **Status:** Done. Implemented as `services/seed_step_registry.py`.

Move step definitions out of `seed_runs.py` and `runner.py`.

Potential file:

```text
services/seed_step_registry.py
```

It should define:

- key;
- title;
- seeder;
- dependencies;
- required pack resource;
- whether enabled for current pack/profile.

Benefits:

- one place to add future steps;
- easier dry-run generation;
- easier execution ordering;
- less duplication.

### 2. Split seed-pack loading and validation

Current `seed_packs.py` should become a facade.

Future files:

```text
services/seed_pack_types.py
services/seed_pack_loader.py
services/seed_pack_validator.py
services/validators/facility_foundation.py
services/validators/patient.py
services/validators/lab.py
services/validators/inventory.py
```

Benefits:

- smaller files;
- validators close to resource domains;
- easier to test validation without API logic.

### 3. Introduce `SeedContext`

Seeders currently receive several constructor arguments.

A context object could hold shared state:

```python
@dataclass
class SeedContext:
	run: SeedRun
	pack: dict
	profile: dict
	client: CareSeedClient
	artifacts: SeedArtifactStore
	geo_organization: str
```

Benefits:

- fewer constructor parameters;
- easier to add shared fields later;
- easier generic seeder interface.

### 4. Introduce `SeedResult`

Seeders currently return:

```python
tuple[str, dict]
```

A named result would be clearer:

```python
@dataclass
class SeedResult:
	message: str
	stats: dict
```

Benefits:

- clearer contracts;
- future support for warnings/output refs.

### 5. Make counts manifest-driven — DONE (Phase 0, 2026-06-05)

> **Status:** Done for patients/departments/locations/healthcare services. Validators
> read the manifest `counts` block; remaining presence rules follow in Phase 1.

Avoid hard-coding expected counts inside validators.

Use manifest counts where possible.

Benefits:

- easier future pack variants;
- fewer code changes when seed data changes;
- better alignment between pack metadata and validation.

### 6. Support optional steps later

A future pack may include labs but not inventory, or clinical encounters but not questionnaires.

The registry should support enabling steps based on resources available in the pack.

Example:

```python
enabled = "lab_tests" in pack
```

### 7. Add resume/idempotency later

For V1, creating a new facility per run is fine.

Later, consider:

- artifact-based skip;
- rerun failed step only;
- existing facility mode;
- unique deterministic slugs;
- idempotency keys.

This should be designed carefully and not rushed into V1.

## Suggested Evolution Path

> **Note (2026-06-05):** The phase numbering in this section predates the current
> scale-out roadmap (Phase 0–3) and is kept for history. The registry (old "Phase 3"
> here) has already landed. Follow the Phase 0–3 roadmap for the canonical plan.

### Phase 1: Keep V1 stable

Do not change current scope.

Keep:

- packaged JSON;
- fixed run flow;
- Celery execution;
- seeders package;
- artifact tracking.

### Phase 2: Clean validation structure

Split `seed_packs.py` into loader/types/validator modules.

This is low risk and improves maintainability.

### Phase 3: Add step registry — DONE (2026-06-05)

The step registry has landed (`services/seed_step_registry.py`). `PLANNED_STEPS` and
fixed runner ordering were replaced by registry-driven discovery and a generic
`_execute_seed_step()` loop.

### Phase 4: Add future seeders

Add new resource domains under:

```text
services/seeders/
```

Examples:

- `lab.py`
- `inventory.py`
- `clinical_encounter.py`
- `questionnaire.py`
- `user.py`

### Phase 5: Add advanced execution features

Only after V1/V2 usage is clearer:

- resume;
- refresh existing facility;
- partial reruns;
- optional seed modules;
- generic dependency graph.

## Final Assessment

The current backend architecture is a good V1 architecture.

It is intentionally not a full seed engine yet, and that is okay.

The most important thing is that recent refactoring moved resource creation into `services/seeders/`, which gives us a clean path to grow without bloating `runner.py`.

The next architectural improvement should not be another resource feature. It should be a step registry and validator split once the V1 behavior is stable.
