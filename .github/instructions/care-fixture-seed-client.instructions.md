---
applyTo: "src/care_demo_facility_setup/services/**/*.{py},src/care_demo_facility_setup/tasks.py,src/care_demo_facility_setup/api/**/*.py"
description: "Use when: working on CARE demo seed execution, CareFixtureBase integration, internal APIClient usage, Celery seed runs, or seed runner resource creation."
---

# CARE demo seed client integration notes

## Use `CareFixtureBase` for CARE resource creation

The demo facility setup plugin should create CARE resources through the existing core fixture helper:

- `CareFixtureBase.create_facility(...)`
- `CareFixtureBase.create_patient(...)`
- later resource helpers such as locations, encounters, products, lab tests, etc.

This keeps seed execution aligned with CARE API behavior instead of bypassing serializers, permissions, validation, and side effects through direct model creation.

## Why `SeedAPIClient` exists

`SeedAPIClient` is not a replacement for `CareFixtureBase`.

It is an adapter for the DRF `APIClient` passed into `CareFixtureBase`.

The call flow is:

```text
DemoSeedRunner
→ CareSeedClient.create_facility(...)
→ CareFixtureBase.create_facility(...)
→ CareFixtureBase.post(...)
→ SeedAPIClient.post(...)
→ CARE DRF endpoint
```

`CareFixtureBase` expects `self.client.get/post/patch(...)` to return a DRF response with `.data`.

In Celery/plugin runtime, plain `APIClient` can return Django redirect responses before DRF handles the request. That breaks `CareFixtureBase.post(...)`, because redirect responses do not have `.data`.

## Redirect issues handled by `SeedAPIClient`

`SeedAPIClient` handles two runtime issues.

### Trailing slash redirects

Django can redirect paths missing trailing slashes.

So `SeedAPIClient` normalizes request paths with a trailing slash before calling the parent `APIClient`.

### HTTP to HTTPS redirects

CARE may run with security middleware that redirects insecure internal requests:

```text
http://testserver/api/...
→ https://testserver/api/...
```

So `SeedAPIClient` sets:

```python
secure=True
```

for internal `get`, `post`, and `patch` calls.

This prevents `HttpResponsePermanentRedirect` from reaching `CareFixtureBase`.

## Keep diagnostic response validation

`_ensure_drf_response(...)` should remain in place.

It catches unexpected non-DRF responses early and reports:

- path
- status code
- redirect location, if any

This gives a clear error instead of:

```text
'HttpResponsePermanentRedirect' object has no attribute 'data'
```

## Celery enqueueing must happen after DB commit

CARE uses `ATOMIC_REQUESTS=True`.

When a seed run is created from an API request, the `SeedRun` row is not visible to Celery until the request transaction commits.

Always enqueue real seed runs using:

```python
transaction.on_commit(...)
```

Otherwise the worker can receive the task too early and fail with:

```text
SeedRun.DoesNotExist
```

leaving the run stuck as `queued`.

## Phone number behavior

Do not store fixed real-looking phone numbers in seed JSON.

Use deterministic demo phone numbers generated from `SeedRun.id`:

- facility phone: unique per run
- patient phone: unique per run and patient index

This keeps seed runs reproducible and avoids committing realistic contact data.

## Avoid `care_fixture_context()` in plugin runtime

Do not use `care_fixture_context()` for dashboard-triggered seed execution.

It is development fixture machinery and may:

- create/update the `admin` user
- force-authenticate fixture clients
- sync roles/valuesets
- patch locks

For the plugin, create a controlled `APIClient`, authenticate it with the requesting superuser, and pass it into `CareFixtureBase`.
