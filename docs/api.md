# Backend API reference

All endpoints in this document are mounted under the plugin base path:

```text
/api/care_demo_facility_setup/
```

These routes are mounted by CARE's plugin URL loader, not by the core `/api/v1/` router.

## Authentication and permissions

The API viewset uses `IsAuthenticated`, so every endpoint requires an authenticated CARE user.

Additional rule:

- `POST /runs/` requires `request.user.is_superuser`.

If a non-superuser attempts to create a run, the backend returns HTTP `403` with:

```json
{
  "detail": "Only superusers can create demo seed runs."
}
```

## Endpoint summary

| Method | Path | View method | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | `healthy()` | Lightweight health check returning `OK`. |
| `GET` | `/hello/` | `BaseViewSet.hello()` | Simple plugin smoke-test endpoint. |
| `GET` | `/seed-packs/` | `BaseViewSet.seed_packs()` | List packaged seed packs. |
| `GET` | `/profiles/?pack_slug=<slug>` | `BaseViewSet.profiles()` | List profiles for a seed pack. |
| `POST` | `/validate/` | `BaseViewSet.validate()` | Validate pack/profile/environment without creating a `SeedRun`. |
| `GET` | `/runs/` | `BaseViewSet.runs()` | List latest 50 seed runs. |
| `POST` | `/runs/` | `BaseViewSet.runs()` | Create a dry run or enqueue a real run. |
| `GET` | `/runs/{external_id}/` | `BaseViewSet.run_detail()` | Return one seed run with steps and artifacts. |

## `GET /health`

Purpose: quick health check for the plugin URL module.

Backend method:

```text
healthy(request)
```

Response:

```text
OK
```

## `GET /hello/`

Purpose: simple smoke test that confirms the viewset is reachable.

Backend method:

```text
BaseViewSet.hello()
```

Response:

```json
{
  "message": "Hello from care_demo_facility_setup plugin!"
}
```

## `GET /seed-packs/`

Purpose: list available seed packs from packaged JSON resources.

Backend method flow:

```text
BaseViewSet.seed_packs()
→ list_seed_packs()
```

Response shape:

```json
{
  "results": [
    {
      "slug": "generic_hospital_v1",
      "name": "Generic Hospital Demo Seed Pack",
      "version": "1.0.0",
      "description": "Packaged demo facility seed data converted from the original CSV import sheets.",
      "counts": {
        "facility": 1,
        "patients": 10,
        "departments": 10,
        "locations": 35,
        "healthcare_services": 4,
        "lab_tests": 33,
        "inventory_items": 318
      }
    }
  ]
}
```

## `GET /profiles/`

Purpose: list profiles for the selected seed pack.

Query params:

| Param | Required | Default | Meaning |
| --- | --- | --- | --- |
| `pack_slug` | No | `generic_hospital_v1` | Seed pack to inspect. |

Backend method flow:

```text
BaseViewSet.profiles()
→ list_profiles(pack_slug)
```

Success response shape:

```json
{
  "results": [
    {
      "slug": "local",
      "name": "Local Development",
      "description": "Local CARE backend profile for creating the first demo facility seed run.",
      "allowed_hosts": ["localhost", "127.0.0.1"]
    }
  ]
}
```

If the pack cannot be loaded, the backend returns HTTP `404`:

```json
{
  "detail": "Missing seed pack file: manifest.json"
}
```

The exact message depends on the `SeedPackError`.

## `POST /validate/`

Purpose: validate a pack/profile against the current backend host and database.

Request body:

```json
{
  "pack_slug": "generic_hospital_v1",
  "profile_slug": "local"
}
```

Optional fields:

| Field | Default | Meaning |
| --- | --- | --- |
| `pack_slug` | `generic_hospital_v1` | Seed pack slug. |
| `profile_slug` | `demo` | Profile slug. |
| `care_base_url` | `null` | Optional fallback URL used only if request host is not available. |

Backend method flow:

```text
BaseViewSet.validate()
→ BaseViewSet._current_host(request)
→ validate_seed_request(...)
→ ValidationResult.to_dict()
```

HTTP status:

| Validation result | HTTP status |
| --- | --- |
| Valid | `200 OK` |
| Invalid | `400 Bad Request` |

Response shape:

```json
{
  "valid": true,
  "errors": [],
  "warnings": [],
  "summary": {
    "pack_slug": "generic_hospital_v1",
    "pack_name": "Generic Hospital Demo Seed Pack",
    "pack_version": "1.0.0",
    "profile_slug": "local",
    "profile_name": "Local Development",
    "host": "localhost",
    "counts": {
      "facility": 1,
      "patients": 10,
      "departments": 10,
      "locations": 35,
      "healthcare_services": 4
    },
    "geo_organization_external_id": "...",
    "resource_categories": {}
  }
}
```

Current profile caveat:

- The frontend defaults to `local`.
- The backend service default is `demo` when `profile_slug` is omitted.
- Current validation requires `geo_organization_external_id` in the selected profile. In the current seed data, `local` has this field; `demo` and `teleicu` use placeholder-style refs and will fail until updated.

## `GET /runs/`

Purpose: return latest run summaries for the UI.

Backend method flow:

```text
BaseViewSet.runs() for GET
→ SeedRun.objects.prefetch_related("steps", "artifacts").all()[:50]
→ serialize_seed_run(run)
```

Response shape:

```json
{
  "results": [
    {
      "id": "run-external-uuid",
      "pack_slug": "generic_hospital_v1",
      "profile_slug": "local",
      "status": "succeeded",
      "dry_run": false,
      "summary": {},
      "error": "",
      "created_date": "2026-06-04T...",
      "started_date": "2026-06-04T...",
      "finished_date": "2026-06-04T..."
    }
  ]
}
```

Summaries do not include step/artifact details. Use `GET /runs/{id}/` for details.

## `POST /runs/`

Purpose: create a dry run or real seed run.

Request body:

```json
{
  "pack_slug": "generic_hospital_v1",
  "profile_slug": "local",
  "dry_run": false
}
```

Field behavior:

| Field | Default in backend | Meaning |
| --- | --- | --- |
| `pack_slug` | `generic_hospital_v1` | Seed pack slug. |
| `profile_slug` | `demo` | Profile slug. |
| `dry_run` | `true` | If true, validate and record skipped resource steps; if false, enqueue real creation. |

Backend method flow for valid real run:

```text
BaseViewSet.runs() for POST
→ superuser check
→ create_seed_run(...)
→ validate_seed_request(...)
→ create SeedRun + SeedRunStep rows
→ if status == queued:
    transaction.on_commit(enqueue_seed_run)
→ run.refresh_from_db()
→ serialize_seed_run(run, include_details=True)
```

HTTP status:

| Result | HTTP status |
| --- | --- |
| Run created or dry run created | `201 Created` |
| Validation failed | `400 Bad Request` |
| Authenticated user is not a superuser | `403 Forbidden` |

Dry-run response behavior:

- If valid, run status is `succeeded`.
- Resource creation steps are `skipped` with a dry-run message.
- No Celery task is enqueued.

Real-run response behavior:

- If valid, run status is initially `queued`.
- Celery is scheduled after the database transaction commits.
- The frontend should poll `GET /runs/{id}/` until the status becomes terminal.

## `GET /runs/{external_id}/`

Purpose: return one run with all details.

Backend method flow:

```text
BaseViewSet.run_detail()
→ SeedRun.objects.prefetch_related("steps", "artifacts").get(external_id=external_id)
→ serialize_seed_run(run, include_details=True)
```

Success response includes the run summary plus:

- `request_payload`;
- `steps`;
- `artifacts`.

If the run does not exist, the backend returns HTTP `404`:

```json
{
  "detail": "Seed run not found"
}
```

## Detailed response objects

### Run object

| Field | Meaning |
| --- | --- |
| `id` | Public `SeedRun.external_id`. |
| `pack_slug` | Selected seed pack. |
| `profile_slug` | Selected profile. |
| `status` | Run status string. |
| `dry_run` | Whether no resource creation was attempted. |
| `summary` | Validation summary. |
| `error` | Validation or execution error text. |
| `created_date` | When the run row was created. |
| `started_date` | When validation/dry-run or execution started. |
| `finished_date` | When validation/dry-run or execution finished. |
| `request_payload` | Original request body; only returned by detail responses. |
| `steps` | Step list; only returned by detail responses. |
| `artifacts` | Created/reused resources; only returned by detail responses. |

### Step object

| Field | Meaning |
| --- | --- |
| `id` | Public `SeedRunStep.external_id`. |
| `order` | Step order. |
| `key` | Stable step key. |
| `title` | Human-readable title. |
| `status` | Step status string. |
| `message` | Success/failure/skip message. |
| `stats` | Step-specific counters. |
| `started_date` | Step start timestamp. |
| `finished_date` | Step finish timestamp. |

### Artifact object

| Field | Meaning |
| --- | --- |
| `id` | Public `SeedRunArtifact.external_id`. |
| `ref` | Stable seed ref, such as `facility:main`. |
| `resource_type` | CARE resource type label used by this plugin. |
| `resource_external_id` | CARE resource UUID returned by the API. |
| `slug` | Resource slug if the API response has one. |
| `payload` | Plain JSON copy of the CARE API response. |
