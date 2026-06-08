# Care Demo Facility Setup documentation

Care Demo Facility Setup is a CARE backend plugin that validates packaged demo data and creates a demo facility through CARE's own API/fixture helpers. It records every run, step, and created resource so administrators can see exactly what happened.

## Start here

- [Backend architecture](backend-architecture.md) — high-level architecture, layers, responsibilities, and API surface.
- [End-to-end backend flow](end-to-end-flow.md) — exact request, dry-run, real-run, Celery, seeder, and polling flow from start to finish.
- [Backend API reference](api.md) — endpoints, request bodies, response shapes, permissions, and status codes.
- [File and method reference](file-and-method-reference.md) — purpose of each backend file and what every method/function does, including who calls it and what it calls next.
- [Data model and seed packs](data-model-and-seed-packs.md) — `SeedRun`, `SeedRunStep`, `SeedRunArtifact`, statuses, packaged JSON, profiles, and validation rules.
- [Operations and troubleshooting](operations-and-troubleshooting.md) — how to reason about queued/failed/skipped runs and common errors.
- [Usage](usage.md) — practical API usage and operational notes.
- [Installation](installation.md) — plugin installation notes.

## Current milestone scope

The current backend implementation creates:

- 1 demo facility
- 10 demo patients
- 10 facility organizations/departments, with `Administration` reused from CARE's auto-created facility organization
- 35 facility locations
- 4 healthcare services

The packaged seed pack also contains lab-test and inventory data for later milestones, but those resources are not created by the current runner yet.
