# File and method reference

This is a map of the backend files and methods in the current implementation. It focuses on what each file does, who calls each method, and what it calls next in the flow.

## Main runtime files

| File | Purpose | Runtime role |
|---|---|---|
| `src/care_demo_facility_setup/urls.py` | Exposes plugin health and router URLs. | Entry point after CARE includes the plugin at `/api/care_demo_facility_setup/`. |
| `src/care_demo_facility_setup/api/viewsets.py` | REST API viewset for seed packs, profiles, validation, and runs. | First Python layer for frontend/API calls. |
| `src/care_demo_facility_setup/models/care_demo_facility_setup_model.py` | Defines persistent run, step, artifact, and status models. | Stores run state and audit trail. |
| `src/care_demo_facility_setup/services/seed_packs.py` | Loads packaged JSON and validates selected pack/profile. | Used by validation and run creation. |
| `src/care_demo_facility_setup/services/seed_runs.py` | Creates/serializes seed runs and enqueues Celery. | Bridges API request handling and async execution. |
| `src/care_demo_facility_setup/tasks.py` | Celery task entrypoint. | Runs real seed execution asynchronously. |
| `src/care_demo_facility_setup/services/runner.py` | Orchestrates real seed execution step by step. | Marks statuses and calls seeders. |
| `src/care_demo_facility_setup/services/seeders/facility.py` | Creates the demo facility. | First real creation step. |
| `src/care_demo_facility_setup/services/seeders/patient.py` | Creates demo patients. | Second real creation step. |
| `src/care_demo_facility_setup/services/seeders/facility_foundation.py` | Creates/reuses facility organizations, locations, and services. | Third real creation step. |
| `src/care_demo_facility_setup/services/care_seed_client.py` | Adapter around CARE `CareFixtureBase` and DRF `APIClient`. | Ensures seeders create resources through CARE APIs. |
| `src/care_demo_facility_setup/services/seed_artifacts.py` | Stores and resolves created/reused resource artifacts. | Connects steps through stable refs. |
| `src/care_demo_facility_setup/services/seed_payloads.py` | Builds CARE API payloads from JSON templates. | Keeps template-only fields out of API payloads. |
| `src/care_demo_facility_setup/services/seed_errors.py` | Defines seed execution exception type. | Used for controlled flow errors. |

## App and support files

| File | Purpose | Runtime role |
|---|---|---|
| `src/care_demo_facility_setup/apps.py` | Django app configuration. | Imports signals when the app is ready. |
| `src/care_demo_facility_setup/admin.py` | Django admin registrations. | Lets staff inspect `SeedRun`, `SeedRunStep`, and `SeedRunArtifact`. |
| `src/care_demo_facility_setup/settings.py` | Plugin settings helper. | Reads plugin config from CARE settings/env and reloads on setting changes. |
| `src/care_demo_facility_setup/signals.py` | Signal hooks. | Currently contains a no-op patient-created hook. |
| `src/care_demo_facility_setup/models/__init__.py` | Model exports. | Lets callers import models from `care_demo_facility_setup.models`. |
| `src/care_demo_facility_setup/services/seeders/__init__.py` | Seeder exports. | Lets `runner.py` import seeder classes from one package. |
| `src/care_demo_facility_setup/__init__.py` | Package metadata. | No request-time behavior. |
| `src/care_demo_facility_setup/migrations/0001_initial.py` | Initial DB schema for seed run tracking. | Creates the audit tables. |
| `scripts/convert_seed_csvs.py` | Converts source CSV sheets to seed-pack JSON. | Development/data-prep script; not called during requests. |

## `urls.py`

| Method/function | Purpose | Called by | Calls next |
|---|---|---|---|
| `healthy(request)` | Returns plain `OK` for a lightweight plugin health check. | Django URL resolver for `/api/care_demo_facility_setup/health`. | No internal service calls. |

The module also creates a DRF router and registers `BaseViewSet` at the plugin root. In DEBUG it uses `DefaultRouter`; otherwise it uses `SimpleRouter`.

## `api/viewsets.py`

| Method | Purpose | Called by | Calls next |
|---|---|---|---|
| `BaseViewSet._current_host(request)` | Extracts the hostname without port from the current request. | `validate()` and `runs()` POST. | `request.get_host()`. |
| `BaseViewSet.hello(...)` | Returns a static smoke-test message. | `GET /hello/`. | No service calls. |
| `BaseViewSet.seed_packs(...)` | Lists seed packs. | `GET /seed-packs/`. | `list_seed_packs()`. |
| `BaseViewSet.profiles(...)` | Lists profiles for a selected pack. | `GET /profiles/`. | `list_profiles(pack_slug)`; catches `SeedPackError`. |
| `BaseViewSet.validate(...)` | Validates pack/profile without creating a run. | `POST /validate/`. | `_current_host(...)`, `validate_seed_request(...)`, `ValidationResult.to_dict()`. |
| `BaseViewSet.runs(...)` | Handles both run list and run creation. | `GET /runs/` and `POST /runs/`. | For POST: `create_seed_run(...)`, optional `transaction.on_commit(...)`, `enqueue_seed_run(...)`, `serialize_seed_run(...)`. For GET: queries `SeedRun` and calls `serialize_seed_run(...)`. |
| `BaseViewSet.run_detail(...)` | Fetches one run with steps and artifacts. | `GET /runs/<external_id>/`. | `SeedRun.objects.prefetch_related(...).get(...)`, `serialize_seed_run(include_details=True)`. |

## `models/care_demo_facility_setup_model.py`

| Class/method | Purpose | Called by | Calls next |
|---|---|---|---|
| `SeedRunStatus` | Enum for overall run lifecycle. | Models, services, API. | No calls. |
| `SeedRunStepStatus` | Enum for individual step lifecycle. | Models, services, runner. | No calls. |
| `SeedRun.__str__()` | Human-readable run label. | Django admin/shell/logging when object is stringified. | No calls. |
| `SeedRunStep.__str__()` | Human-readable step label. | Django admin/shell/logging when object is stringified. | No calls. |
| `SeedRunArtifact.__str__()` | Human-readable artifact label. | Django admin/shell/logging when object is stringified. | No calls. |

## `services/seed_packs.py`

| Method/function | Purpose | Called by | Calls next |
|---|---|---|---|
| `ValidationResult.to_dict()` | Serializes validation result for API response. | `BaseViewSet.validate()`. | No calls. |
| `_pack_root(pack_slug)` | Resolves a seed pack directory inside package data. | `load_seed_pack()`, `list_profiles()`, `load_profile()`. | `importlib.resources.files(...)`. |
| `_load_json(path)` | Loads JSON and raises `SeedPackError` if missing. | All pack/profile loaders. | `path.is_file()`, `json.loads(...)`. |
| `list_seed_packs()` | Lists pack manifest summaries. | `BaseViewSet.seed_packs()`. | `resources.files(...)`, `_load_json(...)`. |
| `load_seed_pack(pack_slug)` | Loads manifest and every resource file declared in it. | `validate_seed_request()`, `DemoSeedRunner.__init__()`. | `_pack_root(...)`, `_load_json(...)`. |
| `list_profiles(pack_slug)` | Lists profile summaries for a pack. | `BaseViewSet.profiles()`. | `_pack_root(...)`, `_load_json(...)`. |
| `load_profile(pack_slug, profile_slug)` | Loads and validates one profile's slug. | `validate_seed_request()`, `DemoSeedRunner.__init__()`. | `_pack_root(...)`, `_load_json(...)`; may raise `SeedPackError`. |
| `_normalize_host(host_or_url)` | Converts host or URL to lowercase hostname. | `validate_seed_request()`. | `urlparse(...)`. |
| `validate_seed_request(...)` | Validates pack/profile/current host/data shape/database prerequisites. | `BaseViewSet.validate()`, `create_seed_run()`. | `load_seed_pack(...)`, `load_profile(...)`, `_normalize_host(...)`, `Organization.objects.filter(...).exists()`, `_validate_facility_foundation(...)`. |
| `_validate_facility_foundation(foundation, errors)` | Validates departments, locations, healthcare services, refs, parent ordering, and special Administration reuse rule. | `validate_seed_request()`. | `_validate_seed_entries(...)`. |
| `_validate_seed_entries(label, entries, errors, expected_count=...)` | Validates list type, expected count, non-empty unique refs. | `_validate_facility_foundation(...)`. | No external calls. |

## `services/seed_runs.py`

| Method/function | Purpose | Called by | Calls next |
|---|---|---|---|
| `serialize_seed_run(run, include_details=False)` | Converts a `SeedRun` to API response data. | `BaseViewSet.runs()`, `BaseViewSet.run_detail()`. | `_choice_value(...)`; iterates prefetched `steps` and `artifacts` when details are requested. |
| `_choice_value(value)` | Normalizes enum/text values for API output. | `serialize_seed_run(...)`. | No calls. |
| `create_seed_run(...)` | Creates the parent run and all planned step rows after validation. | `BaseViewSet.runs()` POST. | `validate_seed_request(...)`, `SeedRun.objects.create(...)`, `SeedRunStep.objects.create(...)`. |
| `enqueue_seed_run(run_external_id)` | Sends real run to Celery; marks run failed if enqueueing throws. | `BaseViewSet.runs()` inside `transaction.on_commit(...)`. | Imports `execute_seed_run`, calls `execute_seed_run.delay(...)`, or updates `SeedRun` to failed. |

## `tasks.py`

| Method/function | Purpose | Called by | Calls next |
|---|---|---|---|
| `execute_seed_run(run_external_id)` | Celery task that starts real execution. | Celery worker after `execute_seed_run.delay(...)`. | `SeedRun.objects.get(...)`, `DemoSeedRunner(run).execute()`. |
| `setup_periodic_tasks(sender, **kwargs)` | Celery finalize hook placeholder. | Celery app `on_after_finalize` signal. | Currently returns without adding tasks. |

## `services/runner.py`

| Method | Purpose | Called by | Calls next |
|---|---|---|---|
| `DemoSeedRunner.__init__(run)` | Prepares pack, profile, geo organization, authenticated CARE client, and artifact store. | `execute_seed_run(...)`. | `load_seed_pack(...)`, `load_profile(...)`, `CareSeedClient(...)`, `SeedArtifactStore(...)`. |
| `DemoSeedRunner.execute()` | Main real-run orchestration and failure handling. Loops over the executable steps from the seed step registry. | `execute_seed_run(...)`. | `_mark_run(...)`, `get_executable_seed_step_definitions(...)`, `_execute_seed_step(...)`, `_mark_pending_steps_skipped(...)`, `_safe_error(...)`. |
| `_execute_seed_step(step_definition)` | Runs one registry-defined step: marks it running, calls its executor, then marks success/failure. | `execute()`. | `_get_step(...)`, `_mark_step(...)`, `step_definition.initial_stats()`, `step_definition.executor(self, step)`. |
| `_get_step(key)` | Fetches a `SeedRunStep` by key for this run. | `_execute_seed_step(...)`. | `SeedRunStep.objects.get(...)`. |
| `_mark_run(status, ...)` | Updates overall run status, error, timestamps, and in-memory object fields. | `execute()`. | `SeedRun.objects.filter(...).update(...)`, `timezone.now()`. |
| `_mark_step(step, status, ...)` | Updates one step's status, message, stats, timestamps, and in-memory object fields. | `_execute_seed_step(...)`. | `SeedRunStep.objects.filter(...).update(...)`, `timezone.now()`. |
| `_mark_pending_steps_skipped(message)` | Skips any still-pending steps after a failure. | `execute()` failure handler. | `SeedRunStep.objects.filter(...).update(...)`. |
| `_safe_error(exc)` | Converts exception to a bounded error string. | Step failure handlers and run failure handler. | `str(exc)` and slicing. |

## `services/seeders/facility.py`

| Method | Purpose | Called by | Calls next |
|---|---|---|---|
| `FacilitySeeder.__init__(...)` | Stores client, artifact store, geo organization id, and run id. | `_seed_facility(...)` registry executor. | No calls. |
| `FacilitySeeder.seed(step, facility_template)` | Builds facility payload, creates facility through CARE, stores artifact, returns message/stats. | `_seed_facility(...)` registry executor. | `build_facility_payload(...)`, `CareSeedClient.create_facility(...)`, `SeedArtifactStore.store(...)`. |

## `services/seeders/patient.py`

| Method | Purpose | Called by | Calls next |
|---|---|---|---|
| `PatientSeeder.__init__(...)` | Stores client, artifact store, geo organization id, and run id. | `_seed_patients(...)` registry executor. | No calls. |
| `PatientSeeder.seed(step, patients_config)` | Loops over patient templates, creates each patient, stores artifacts, returns message/stats. | `_seed_patients(...)` registry executor. | `build_patient_payload(...)`, `CareSeedClient.create_patient(...)`, `SeedArtifactStore.store(...)`. |

## `services/seeders/facility_foundation.py`

| Method | Purpose | Called by | Calls next |
|---|---|---|---|
| `FacilityFoundationSeeder.__init__(...)` | Stores CARE client and artifact store. | `_seed_facility_foundation(...)` registry executor. | No calls. |
| `FacilityFoundationSeeder.seed(step, facility_template, foundation)` | Orchestrates foundation resources after facility exists. | `_seed_facility_foundation(...)` registry executor. | `SeedArtifactStore.external_id(...)`, `_create_departments(...)`, `_create_locations(...)`, `_create_healthcare_services(...)`. |
| `_create_departments(step, facility_id, department_templates, stats)` | Reuses Administration and creates other facility organizations. | `seed(...)`. | `CareSeedClient.get_facility_organizations(...)`, `_find_facility_organization(...)`, `CareSeedClient.create_facility_organization(...)`, `SeedArtifactStore.store(...)`, `SeedArtifactStore.payload_external_id(...)`. |
| `_create_locations(step, facility_id, location_templates, department_ids, stats)` | Creates location hierarchy and links organizations to locations. | `seed(...)`. | `CareSeedClient.create_location(...)`, `SeedArtifactStore.store(...)`, `SeedArtifactStore.payload_external_id(...)`, `CareSeedClient.add_organization_to_location(...)`. |
| `_create_healthcare_services(step, facility_id, healthcare_service_templates, department_ids, location_ids, stats)` | Creates Pharmacy, X Ray, Laboratory, and OPD services. | `seed(...)`. | `CareSeedClient.create_healthcare_service(...)`, `SeedArtifactStore.store(...)`. |
| `_find_facility_organization(organizations, name)` | Finds an existing organization by name. | `_create_departments(...)`. | `get_value(...)`. |

## `services/care_seed_client.py`

| Method/function | Purpose | Called by | Calls next |
|---|---|---|---|
| `SeedAPIClient.get(...)` | Secure trailing-slash GET wrapper. | `CareFixtureBase` methods. | `_with_trailing_slash(...)`, parent `APIClient.get(...)`, `_ensure_drf_response(...)`. |
| `SeedAPIClient.post(...)` | Secure trailing-slash POST wrapper. | `CareFixtureBase` methods. | `_with_trailing_slash(...)`, parent `APIClient.post(...)`, `_ensure_drf_response(...)`. |
| `SeedAPIClient.patch(...)` | Secure trailing-slash PATCH wrapper. | `CareFixtureBase` methods. | `_with_trailing_slash(...)`, parent `APIClient.patch(...)`, `_ensure_drf_response(...)`. |
| `CareSeedClient.__init__(user)` | Creates authenticated internal API client and wraps it in `CareFixtureBase`. | `DemoSeedRunner.__init__()`. | `SeedAPIClient()`, `force_authenticate(...)`, `CareFixtureBase(...)`. |
| `CareSeedClient.create_facility(...)` | Creates facility via CARE fixture helper. | `FacilitySeeder.seed(...)`. | `CareFixtureBase.create_facility(...)`. |
| `CareSeedClient.get_facility_organizations(...)` | Fetches organizations for a facility. | `FacilityFoundationSeeder._create_departments(...)`. | `CareFixtureBase.get_facility_organizations(...)`. |
| `CareSeedClient.create_facility_organization(...)` | Creates a facility organization/department. | `FacilityFoundationSeeder._create_departments(...)`. | `CareFixtureBase.create_facility_organization(...)`. |
| `CareSeedClient.create_location(...)` | Creates a facility location. | `FacilityFoundationSeeder._create_locations(...)`. | `CareFixtureBase.create_location(...)`. |
| `CareSeedClient.add_organization_to_location(...)` | Links organization to location. | `FacilityFoundationSeeder._create_locations(...)`. | `CareFixtureBase.add_organization_to_location(...)`. |
| `CareSeedClient.create_healthcare_service(...)` | Creates healthcare service. | `FacilityFoundationSeeder._create_healthcare_services(...)`. | `CareFixtureBase.create_healthcare_service(...)`. |
| `CareSeedClient.create_patient(...)` | Creates patient. | `PatientSeeder.seed(...)`. | `CareFixtureBase.create_patient(...)`. |
| `_with_trailing_slash(path)` | Adds trailing slash before query string if missing. | `SeedAPIClient.get/post/patch(...)`. | String parsing. |
| `_ensure_drf_response(path, response)` | Ensures response has `.data`; otherwise raises diagnostic error. | `SeedAPIClient.get/post/patch(...)`. | Reads response status/location if available. |

## `services/seed_artifacts.py`

| Method/function | Purpose | Called by | Calls next |
|---|---|---|---|
| `SeedArtifactStore.__init__(run)` | Stores current run. | `DemoSeedRunner.__init__()`. | No calls. |
| `SeedArtifactStore.external_id(ref)` | Resolves a stored artifact ref to a CARE external id. | `FacilityFoundationSeeder.seed(...)`. | `SeedRunArtifact.objects.get(...)`; raises `SeedRunExecutionError` if missing/invalid. |
| `SeedArtifactStore.store(step, ref, resource_type, payload)` | Converts payload to plain data and upserts an artifact row. | All seeders. | `to_plain(...)`, `SeedRunArtifact.objects.update_or_create(...)`. |
| `SeedArtifactStore.payload_external_id(payload, ref)` | Reads `id` from an API payload or raises a controlled error. | `FacilityFoundationSeeder` helper methods. | No external calls. |
| `to_plain(value)` | Converts DRF/serializer `UserDict`, mappings, and lists to plain Python data. | `SeedArtifactStore.store(...)`. | Recursive calls to itself. |
| `get_value(value, key, default=None)` | Reads a key from `UserDict`, mapping, or object attribute. | `FacilityFoundationSeeder._find_facility_organization(...)`. | No external calls. |

## `services/seed_payloads.py`

| Method/function | Purpose | Called by | Calls next |
|---|---|---|---|
| `build_facility_payload(template, run_id)` | Converts facility template into CARE facility API payload. | `FacilitySeeder.seed(...)`. | `facility_phone_number(...)`. |
| `facility_phone_number(template, run_id)` | Generates deterministic facility phone number. | `build_facility_payload(...)`. | String formatting. |
| `build_patient_payload(patients_config, template, index, run_id)` | Converts patient template into CARE patient API payload. | `PatientSeeder.seed(...)`. | `patient_phone_number(...)`. |
| `patient_phone_number(patients_config, index, run_id)` | Generates deterministic patient phone number. | `build_patient_payload(...)`. | String formatting. |

## `services/seed_errors.py`

| Class | Purpose | Called by | Calls next |
|---|---|---|---|
| `SeedRunExecutionError` | Controlled runtime exception for expected seed execution failures. | Runner, artifact store, foundation seeder. | No calls. |

## `apps.py`

| Method | Purpose | Called by | Calls next |
|---|---|---|---|
| `CareDemoFacilitySetupConfig.ready()` | Imports signal handlers when Django app registry is ready. | Django app loading. | `import care_demo_facility_setup.signals`. |

## `settings.py`

| Method/function | Purpose | Called by | Calls next |
|---|---|---|---|
| `PluginSettings.__init__(...)` | Initializes plugin settings defaults/import/required setting metadata. | Module-level `plugin_settings = PluginSettings(...)`. | `validate()`. |
| `PluginSettings.__getattr__(attr)` | Lazy-loads a setting from plugin config, environment, or defaults. | Any code accessing `plugin_settings.<SETTING>`. | `user_settings`, `env(...)`, `perform_import(...)` for import strings. |
| `PluginSettings.user_settings` | Loads this plugin's config from CARE `PLUGIN_CONFIGS`. | `__getattr__(...)`. | `getattr(settings, "PLUGIN_CONFIGS", {})`. |
| `PluginSettings.validate()` | Checks required settings are truthy. | `__init__(...)`. | `getattr(self, setting)` for each required setting. |
| `PluginSettings.reload()` | Clears cached setting attributes and user settings. | `reload_plugin_settings(...)`. | `delattr(...)`. |
| `reload_plugin_settings(*args, **kwargs)` | Reloads plugin settings when Django's `PLUGIN_CONFIGS` setting changes. | Django `setting_changed` signal. | `plugin_settings.reload()`. |

## `signals.py`

| Method/function | Purpose | Called by | Calls next |
|---|---|---|---|
| `hook_patient_created(sender, instance, created, **kwargs)` | Placeholder hook for newly created CARE `Patient` records. | Django `post_save` signal for `Patient`. | Currently no-op when `created` is true. |

## `admin.py`

| Class | Purpose | Called by | Calls next |
|---|---|---|---|
| `SeedRunStepInline` | Shows run steps inline on a run admin page. | Django admin. | No custom methods. |
| `SeedRunArtifactInline` | Shows artifacts inline on a run admin page. | Django admin. | No custom methods. |
| `SeedRunAdmin` | Admin list/filter/search/detail configuration for runs. | Django admin. | No custom methods. |
| `SeedRunStepAdmin` | Admin list/filter/search/detail configuration for steps. | Django admin. | No custom methods. |
| `SeedRunArtifactAdmin` | Admin list/filter/search/detail configuration for artifacts. | Django admin. | No custom methods. |

## `scripts/convert_seed_csvs.py`

This script is not part of the request-time backend flow. It is a data-preparation helper for converting source CSV sheets into JSON seed-pack files.

| Method/function | Purpose | Called by | Calls next |
|---|---|---|---|
| `clean(value)` | Converts value to stripped string. | Most script helpers. | No calls. |
| `optional(value)` | Returns stripped string or `None`. | Payload builders. | `clean(...)`. |
| `to_bool(value)` | Parses common truthy strings. | `specimen_payload(...)`. | `clean(...)`. |
| `to_float(value)` | Parses a float or returns `None`. | `specimen_payload(...)`, `charge_payload(...)`. | `clean(...)`, `float(...)`. |
| `coding(system, code, display)` | Builds a coding dict if any coding field exists. | Payload builders. | `clean(...)`. |
| `split_refs(value)` | Splits comma-separated refs. | `activity_payload(...)`. | `clean(...)`. |
| `slug_key(slug)` | Normalizes activity slug for charge inference. | `build_seed_pack()`. | `clean(...)`. |
| `read_csv(name)` | Reads one source CSV into cleaned row dicts. | `build_seed_pack()`. | `csv.DictReader(...)`. |
| `specimen_payload(row)` | Converts specimen CSV row to JSON payload. | `build_seed_pack()`. | `to_float(...)`, `coding(...)`, `optional(...)`, `to_bool(...)`. |
| `observation_payload(row)` | Converts observation CSV row to JSON payload. | `build_seed_pack()`. | `coding(...)`, `optional(...)`. |
| `charge_payload(row)` | Converts charge CSV row to JSON payload. | `build_seed_pack()`. | `to_float(...)`. |
| `activity_payload(row)` | Converts activity CSV row to JSON payload. | `build_seed_pack()`. | `coding(...)`, `split_refs(...)`, `optional(...)`. |
| `product_knowledge_payload(row)` | Converts product knowledge CSV row to JSON payload. | `build_seed_pack()`. | `optional(...)`, `coding(...)`. |
| `build_seed_pack()` | Reads all CSVs and writes `manifest.json`, `lab_tests.json`, `inventory_items.json`, and raw JSON files. | Script `if __name__ == "__main__"`. | All helper functions plus filesystem writes. |

## Seed pack JSON files

| File/group | Purpose | Runtime use |
|---|---|---|
| `seed_packs/__init__.py` | Makes seed packs importable as package data. | Required by `importlib.resources`. |
| `seed_packs/generic_hospital_v1/__init__.py` | Makes the concrete pack importable as package data. | Required by `importlib.resources`. |
| `manifest.json` | Declares resource files and counts. | Loaded by `load_seed_pack()` and profile listing. |
| `profiles/*.json` | Environment guardrails and IDs. | Loaded by `load_profile()`. |
| `facility.json` | Facility template. | Used by `FacilitySeeder`. |
| `patients.json` | Patient templates. | Used by `PatientSeeder`. |
| `facility_foundation.json` | Departments, locations, healthcare services. | Used by `FacilityFoundationSeeder`. |
| `lab_tests.json` | Future lab-test resources. | Loaded and warning-checked only. |
| `inventory_items.json` | Future inventory resources. | Loaded and warning-checked only. |
| `raw/*.json` | Raw converted CSV rows. | Traceability only in current runtime. |

## Tests

| File/method | Purpose | Runtime use |
|---|---|---|
| `tests/test_care_hello.py` | Placeholder generated test module. | Not used by backend runtime. |
| `setUp()` | Placeholder setup hook. | Test framework only. |
| `tearDown()` | Placeholder teardown hook. | Test framework only. |
| `test_example_feature()` | Placeholder assertion. | Test framework only. |
