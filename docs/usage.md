# Usage

This plugin is normally used through the CARE frontend plugin page. The frontend calls the backend API under `/api/care_demo_facility_setup/`.

For the full backend flow, read [End-to-end backend flow](end-to-end-flow.md). For endpoint details, read [Backend API reference](api.md). For method-by-method details, read [File and method reference](file-and-method-reference.md). For failed/queued run diagnosis, read [Operations and troubleshooting](operations-and-troubleshooting.md).

## Normal admin workflow

1. Open the demo setup frontend page while logged into CARE.
2. Choose a seed pack. The current pack is `generic_hospital_v1`.
3. Choose a profile. For local development, the practical current profile is `local`.
4. Click **Validate setup** to check host, profile, packaged data, and required database prerequisites.
5. Click **Create dry run** to create an auditable validation-only run.
6. Click **Create demo facility** to enqueue a real run.
7. Watch run details until status becomes `succeeded` or `failed`.

## API workflow

All viewset endpoints require authentication. Creating a run with `POST /runs/` also requires the authenticated user to be a superuser.

| Action | Endpoint | What happens |
|---|---|---|
| Health check | `GET /api/care_demo_facility_setup/health` | Returns `OK`. |
| List seed packs | `GET /api/care_demo_facility_setup/seed-packs/` | Reads packaged seed pack manifests. |
| List profiles | `GET /api/care_demo_facility_setup/profiles/?pack_slug=generic_hospital_v1` | Reads profile JSON files for the pack. |
| Validate | `POST /api/care_demo_facility_setup/validate/` | Runs validation only; does not create a run row. |
| List runs | `GET /api/care_demo_facility_setup/runs/` | Returns latest 50 run summaries. |
| Create dry run | `POST /api/care_demo_facility_setup/runs/` with `dry_run: true` | Creates `SeedRun`/`SeedRunStep` rows and marks creation steps skipped. |
| Create real run | `POST /api/care_demo_facility_setup/runs/` with `dry_run: false` | Creates run rows and enqueues Celery after DB commit. |
| Get run details | `GET /api/care_demo_facility_setup/runs/<external_id>/` | Returns one run with steps and artifacts. |

## Request body

Validation and run creation use the same core fields:

```json
{
	"pack_slug": "generic_hospital_v1",
	"profile_slug": "local"
}
```

Run creation adds `dry_run`:

```json
{
	"pack_slug": "generic_hospital_v1",
	"profile_slug": "local",
	"dry_run": false
}
```

## Important profile note

The backend defaults `profile_slug` to `demo` when a request omits it. In the current packaged data, `demo.json` and `teleicu.json` are placeholders that do not define `geo_organization_external_id`, so validation fails for those profiles. Use `local` for local development unless you have updated a profile with a valid government organization external id for your environment.

## What a successful real run creates

The current runner creates:

- 1 demo facility
- 10 demo patients
- 10 facility organizations/departments, including the reused auto-created `Administration` organization
- 35 facility locations
- 4 healthcare services: Pharmacy, X Ray, Laboratory, and OPD

Each created or reused resource is stored as a `SeedRunArtifact` so it can be shown in run details and used by later steps.

## Operational notes

- Real runs are asynchronous and need a running Celery worker.
- Celery is enqueued only after the API request transaction commits.
- The runner creates resources through CARE's DRF APIs via `CareFixtureBase`; it does not directly insert facility/patient/location records.
- Dry runs never create CARE resources.
- If a step fails, the current step is marked `failed`, pending steps are marked `skipped`, and the overall run is marked `failed`.
