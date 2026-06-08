# Operations and troubleshooting

This document explains how to reason about seed runs when something is queued, failed, skipped, or not visible in the UI.

## Runtime requirements

A real seed run needs:

- CARE backend running with the plugin installed;
- authenticated user session;
- superuser account for `POST /runs/`;
- a valid profile whose `allowed_hosts` includes the request host;
- a profile with `geo_organization_external_id` pointing to an existing government organization;
- Celery worker running for real runs;
- packaged seed JSON files available as package data.

## Which profile should be used locally?

Use the `local` profile for local development.

Why:

- the frontend defaults to `local`;
- `local` allows `localhost` and `127.0.0.1`;
- `local` currently includes `geo_organization_external_id`;
- current validation and runner require that field.

The backend service default profile is `demo` when the request omits `profile_slug`, but current `demo` seed data does not include `geo_organization_external_id`. So omit `profile_slug` only if the default profile has been updated.

## Run status troubleshooting

| Status | What it means | What to check |
| --- | --- | --- |
| `validation_failed` | Backend validation failed before resource creation. | Inspect `SeedRun.error` or API response `errors`. Check host, profile, geo organization, and seed JSON counts. |
| `queued` | Run passed validation and should be picked by Celery. | Confirm Celery is running and `transaction.on_commit()` executed. Check task logs. |
| `running` | Celery started execution. | Poll run detail and inspect step statuses. |
| `failed` | Enqueue or execution failed. | Inspect run `error`, failed step `message`, and Celery logs. |
| `succeeded` with `dry_run=true` | Validation passed; no resources were created. | This is expected for dry runs. |
| `succeeded` with `dry_run=false` | All current resource creation steps completed. | Inspect artifacts for created resource IDs. |

## Step status troubleshooting

| Step | Common issue | Where to look |
| --- | --- | --- |
| `validate` | Invalid profile/host/data. | `services/seed_packs.py`, API validation response. |
| `facility` | CARE facility creation failed. | `FacilitySeeder.seed()`, `build_facility_payload()`, `CareSeedClient.create_facility()`. |
| `patients` | One patient template/API call failed. | `PatientSeeder.seed()`, current step stats/message. |
| `facility_foundation` | Missing facility artifact, missing Administration org, invalid parent refs, CARE creation failure. | `FacilityFoundationSeeder.seed()` and helper methods. |

## Why `transaction.on_commit()` is used

CARE uses request transactions. When the API creates a `SeedRun`, the row may not be visible to Celery until the request transaction commits.

The API therefore does this for real runs:

```text
transaction.on_commit(lambda: enqueue_seed_run(run.external_id))
```

Without this guard, a Celery worker could receive the task early and fail with `SeedRun.DoesNotExist`, leaving the run stuck or failed incorrectly.

## Why `SeedAPIClient` normalizes requests

The runner creates CARE resources through internal DRF API calls. The helper chain is:

```text
Seeder
→ CareSeedClient
→ CareFixtureBase
→ SeedAPIClient
→ CARE DRF endpoint
```

`SeedAPIClient` adds two safeguards:

1. It appends a trailing slash to paths so Django does not return a redirect.
2. It sets `secure=True` so security middleware does not redirect internal `http://testserver/...` requests to HTTPS.

It also checks that the response has `.data`. If it does not, `_ensure_drf_response()` raises a diagnostic error with the path, status code, and redirect location.

## Common errors

### Host is not allowed

Likely message:

```text
Host '<host>' is not allowed for profile '<profile>'.
```

Cause:

- selected profile's `allowed_hosts` does not include the backend request host.

Fix:

- select a profile matching the environment; or
- update the profile's `allowed_hosts` list.

### Missing `geo_organization_external_id`

Likely message:

```text
Profile '<profile>' does not define geo_organization_external_id.
```

Cause:

- the selected profile has only a placeholder reference and not the actual CARE organization UUID required by current code.

Fix:

- use the `local` profile locally; or
- add the correct `geo_organization_external_id` for the environment.

### Government organization not found

Likely message:

```text
Profile geo_organization_external_id does not match an existing govt organization.
```

Cause:

- profile UUID does not exist in the database;
- or it exists but is not an organization with `org_type='govt'`.

Fix:

- update the profile UUID to match the target database;
- or load the expected fixture data.

### Dry run reached Celery

Likely message:

```text
Dry runs cannot be executed.
```

Cause:

- a dry run was accidentally enqueued or manually executed.

Expected behavior:

- dry runs should finish synchronously in `create_seed_run()` and should never call `DemoSeedRunner.execute()`.

### Missing required artifact

Likely message:

```text
Missing required artifact: facility:main
```

Cause:

- a later step needs an artifact from an earlier step, but the earlier step did not store it.

Fix:

- check whether the earlier step failed;
- ensure the template ref matches the ref used by later steps;
- ensure every seeder stores created resources with `SeedArtifactStore.store()`.

### CARE API response did not include an ID

Likely message:

```text
CARE API response for <ref> did not include an id.
```

Cause:

- CARE endpoint returned a response shape that does not include `id`;
- or the wrong object was passed to `SeedArtifactStore.payload_external_id()`.

Fix:

- inspect the artifact payload and CARE fixture helper response shape;
- update the seeder or fixture helper usage.

### Internal CARE API request did not return a DRF response

Likely message:

```text
Internal CARE API request did not return a DRF response: path=..., status=..., location=...
```

Cause:

- redirect or non-DRF response reached `CareFixtureBase`.

Fix:

- check the path passed by `CareFixtureBase`;
- confirm `SeedAPIClient` is being used;
- inspect the reported `Location` header if present.

## Safe extension checklist

When adding a new seed step:

- add seed data to the seed pack;
- validate the data before creating any resources;
- use `CareSeedClient` / `CareFixtureBase` instead of direct model creation;
- store every created or reused resource as a `SeedRunArtifact`;
- use stable refs in JSON and artifacts;
- register the step in the seed step registry (`services/seed_step_registry.py`) and, if needed, list it in the manifest `steps`;
- mark step stats and messages clearly;
- keep errors safe and useful;
- ensure the new step is skipped correctly on dry runs and validation failures.
