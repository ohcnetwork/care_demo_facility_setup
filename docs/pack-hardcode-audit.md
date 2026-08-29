# Pack-story hardcode audit

**Goal:** Make `care_demo_facility_setup` a **pack-agnostic engine**: Python validates structure/consistency and executes pack JSON; it does not encode one hospital’s demo story (counts, named locations, fixed patients, required forms).

**Scope:** Validators, seeders, and related services under `src/care_demo_facility_setup/services/`. Pack JSON under `seed_packs/` is *data* (allowed to tell a story). Shared form files under `data/` are a reusable library (OK); Python mandating *which* forms every pack must use is not.

**Date:** 2026-08-29 (code as present in workspace).

---

## Summary

| Area | Severity | Hardcode | Why it blocks other packs | Suggested direction |
|------|----------|----------|---------------------------|---------------------|
| Facility foundation validator | **High** | `bed_count < 3` | Clinic / TeleICU / single-ward packs with 0–2 beds fail validation | Drop fixed floor; optionally require `bed_count >= len(ip_in_progress)` when clinical_visits present |
| Inventory seeder | **High** | `STORE_REF` / `PHARMACY_REF` = `location:main_store` / `location:main_pharmacy` | Any pack without those exact location refs cannot run inventory | Read receive/transfer location refs from pack config (e.g. `inventory_items` meta or foundation roles) |
| Clinical visit seeder | **Med** | Only `fill_key` ∈ `{vitals, op_consultation}`; fixed question key sets | New form shapes need Python changes; packs cannot invent fill strategies in JSON alone | Keep small fill registry; document required keys per `fill_key`; allow empty `questionnaire_slugs` |
| Clinical visit seeder | **Med** | Fallback `op_org_refs → ["department:medical_surgical"]` | Assumes generic-hospital dept naming if plan omits refs | Remove fallback; require pack list (validator already does) |
| Clinical visit validator | **Med** | `op_closed_per_patient` must be **≥ 1** | OP-free packs (IP/ED only) cannot validate | Allow `0` when OP expansion is unused |
| Clinical visit seeder | **Med** | `questionnaire_slugs` must be **non-empty** | Packs that skip questionnaires still fail at seed time | Allow empty list; skip `_submit_forms` |
| Clinical scenarios validator | **Med** | Every scenario must include `medication` (+ full field set) | Non-pharmacy / symptom-only packs fail | Make `medication` optional; only validate `product_knowledge_slug` when present |
| Facility foundation validator | **Med** | Must include `department:administration` + `reuse_existing` | Packs must use that exact ref string | Keep CARE reuse rule; allow configurable ref via pack convention or `reuse_existing` flag alone |
| Seed step registry | **Med** | Default categories `Lab Tests` / `laboratory` if pack omits category JSON | Silent story defaults when resources missing | Fail if categories file missing when step runs; no hardcoded titles |
| Inventory seeder | **Low–Med** | Default category `"Medicines"`; India CGST/SGST 2.5%; pharmacy transfer qty formula | India hospital inventory story baked into engine | Pack overrides for tax/transfer; require `resource_category_name` |
| Facility foundation seeder | **Low** | Default `organization_refs → ["department:administration"]` | Locations without orgs silently attach to admin | Require `organization_refs` in pack or fail |
| Seed payloads / seeders | **Low** | Fallbacks: `facility:main`, `patient:NNN`, `Ohcn@123`, `care.demo`, `+91…` | Soft defaults if pack omits fields | Prefer pack-required fields; keep phone templates as OK defaults |
| Default pack slug | **Low** | `DEFAULT_PACK_SLUG = "generic_hospital_v1"` | API/default selection only | OK as default; not a validator story lock |

---

## Findings (detail)

### 1. [High] Minimum three beds in foundation validator

**File:** `services/validators/facility_foundation.py`

```90:91:src/care_demo_facility_setup/services/validators/facility_foundation.py
        if bed_count < 3:
            accumulator.error("facility_foundation.locations must include at least 3 beds (form='bd').")
```

Tied to `generic_hospital_v1`’s three IP beds (`clinical_visits.json` → three `ip_in_progress` rows). A pack with one bed, or zero inpatient beds, fails before seed.

**Direction:** Remove the floor. Cross-check only: each `ip_in_progress[].bed_ref` exists and `form == "bd"` (and optionally `bed_count >= len(ip_in_progress)`).

`form == "bd"` / `mode == "instance"|"kind"` checks above this block are CARE location enums — **OK**, not pack-story.

---

### 2. [High] Inventory always receives at Main Store and transfers to Main Pharmacy

**File:** `services/seeders/inventory.py`

```18:19:src/care_demo_facility_setup/services/seeders/inventory.py
STORE_REF = "location:main_store"
PHARMACY_REF = "location:main_pharmacy"
```

```42:43:src/care_demo_facility_setup/services/seeders/inventory.py
        store_id = self.artifacts.external_id(STORE_REF)
        pharmacy_id = self.artifacts.external_id(PHARMACY_REF)
```

User-facing messages and errors also name “Main Store” / “Main Pharmacy” (lines 216–217, 280–283). Those refs exist only because `generic_hospital_v1/facility_foundation.json` defines them — the **engine** assumes them.

**Direction:** Pack declares `receive_location_ref` / `pharmacy_location_ref` (or roles on locations). Validator ensures those refs exist in foundation. Seeder reads them. No Python constants for store/pharmacy names.

Inventory **validator** does not currently require those locations — gap: pack can omit them and still “validate”, then fail at seed.

---

### 3. [Med] Questionnaire fill strategies are a fixed Python enum

**File:** `services/seeders/clinical_visit.py`

```354:361:src/care_demo_facility_setup/services/seeders/clinical_visit.py
            if fill_key == "vitals":
                results = self._vitals_results(question_ids, scenario)
            elif fill_key == "op_consultation":
                results = self._op_consultation_results(question_ids, scenario)
            else:
                raise SeedRunExecutionError(
                    f"Unknown questionnaire fill_key '{fill_key}' for slug '{slug}'. "
                    "Supported fill keys: vitals, op_consultation."
                )
```

`_vitals_results` / `_op_consultation_results` hardcode question **keys** (`temperature`, `pulse`, … / `history`, `admission`, …) and story bits (e.g. `admission` → `"false"`, `grbs` → `randint(90, 140)`).

Packs may choose which shared `data/{slug}.json` forms to list, but any new clinical form shape still requires a new Python `fill_key` handler. Acceptable as a **documented fill registry**; still a remaining engine constraint after the pack-agnostic clinical work.

**Direction:** Document required keys per `fill_key`. Optionally validate that pack `requirements[].key` match the fill handler’s expected set. Allow packs to omit questionnaires entirely (see finding 5).

---

### 4. [Med] Soft fallback to `department:medical_surgical` for OP orgs

**File:** `services/seeders/clinical_visit.py`

```170:171:src/care_demo_facility_setup/services/seeders/clinical_visit.py
        op_per_patient = int(visits_plan.get("op_closed_per_patient") or 0)
        op_org_refs = visits_plan.get("op_org_refs") or ["department:medical_surgical"]
```

Validator already requires a non-empty pack `op_org_refs` list, so this fallback is mostly dead after validate — but it still encodes the generic-hospital department slug in the seeder.

**Direction:** Delete the fallback; fail if missing (mirror validator).

---

### 5. [Med] Clinical visit plan still assumes “always OP + always questionnaires”

**Validator** (`services/validators/clinical_visit.py`):

```71:73:src/care_demo_facility_setup/services/validators/clinical_visit.py
    op_per_patient = visits.get("op_closed_per_patient")
    if not isinstance(op_per_patient, int) or op_per_patient < 1:
        accumulator.error("clinical_visits.op_closed_per_patient must be a positive integer.")
```

**Seeder** (`services/seeders/clinical_visit.py`):

```134:136:src/care_demo_facility_setup/services/seeders/clinical_visit.py
        slugs = visits_plan.get("questionnaire_slugs") or []
        if not isinstance(slugs, list) or not slugs:
            raise SeedRunExecutionError("clinical_visits.questionnaire_slugs must be a non-empty list.")
```

Blocks: IP-only packs (`op_closed_per_patient: 0`); packs with clinical visits but no questionnaire step / empty `questionnaire_slugs`.

**Direction:** Allow `op_closed_per_patient >= 0`. Allow empty `questionnaire_slugs` and skip form submit.

---

### 6. [Med] Clinical scenarios require a full “hospital story” shape including medication

**File:** `services/validators/clinical_visit.py`

```34:36:src/care_demo_facility_setup/services/validators/clinical_visit.py
        for field in ("name", "history_text", "advice", "vitals", "symptoms", "diagnosis", "medication"):
            if field not in scenario:
                accumulator.error(f"clinical_scenarios[{index}] is missing '{field}'.")
```

Plus mandatory `product_knowledge_slug` ∈ inventory when `medication` is present (lines 39–48). A pack without inventory/pharmacy cannot author scenarios without fake medication entries.

**Direction:** Require a smaller core (`name`, clinical lists as needed); make `medication` / `vitals` / `advice` optional depending on fill keys used.

---

### 7. [Med] Fixed `department:administration` ref in foundation validator

**File:** `services/validators/facility_foundation.py`

```42:55:src/care_demo_facility_setup/services/validators/facility_foundation.py
        administration = next(
            (
                department
                for department in departments
                if isinstance(department, dict) and department.get("ref") == "department:administration"
            ),
            None,
        )
        if not administration:
            accumulator.error("facility_foundation.departments must include department:administration.")
        elif not administration.get("reuse_existing"):
            accumulator.error(
                "department:administration must be marked reuse_existing because CARE creates it with the facility."
            )
```

**Platform fact (OK):** CARE auto-creates an Administration facility org; seed must reuse it.

**Pack-story smell:** The engine locks the artifact **ref** to `department:administration`. Seeder also defaults location orgs to that ref:

```129:129:src/care_demo_facility_setup/services/seeders/facility_foundation.py
            organization_refs = location_template.get("organization_refs") or ["department:administration"]
```

**Direction:** Require exactly one `reuse_existing: true` department (match by name/policy if needed); do not mandate the ref string. Require explicit `organization_refs` on locations.

---

### 8. [Med] Hardcoded default lab category titles when pack omits category files

**File:** `services/seed_step_registry.py`

```136:139:src/care_demo_facility_setup/services/seed_step_registry.py
        categories_config=context.pack.get(
            "charge_item_categories",
            [{"title": "Lab Tests", "slug_value": "lab-tests"}],
        ),
```

```152:155:src/care_demo_facility_setup/services/seed_step_registry.py
        categories_config=context.pack.get(
            "activity_categories",
            [{"title": "Laboratory", "slug_value": "laboratory"}],
        ),
```

These are the generic-hospital lab story. A pack that runs charge/activity steps without category JSON silently gets those labels.

**Direction:** No defaults; require pack resources (validators already expect category files when those steps validate).

---

### 9. [Low–Med] Inventory pricing / transfer / category defaults

**File:** `services/seeders/inventory.py`

| Snippet | Lines | Notes |
|---------|-------|--------|
| `or "Medicines"` | 67, 230 | Default product category name |
| `_pharmacy_transfer_quantity` (`>= 1000` → min 500, else `//4`) | 310–313 | Arbitrary stock story math |
| CGST/SGST `factor: 2.5` | 366–374 | India GST split baked into charge payload |

**Direction:** Prefer pack fields; defaults OK only if documented as India-demo helpers and overridable.

---

### 10. [Low] Soft ref / credential / locale defaults

Not story locks if packs always set fields, but they encode “demo India hospital” assumptions:

| Location | Hardcode | Severity |
|----------|----------|----------|
| Many seeders | `facility_template.get("ref", "facility:main")` | Low |
| `seeders/patient.py:30` | `patient:{index:03d}` fallback | Low |
| `seed_payloads.py` | `password` default `Ohcn@123`, `email_domain` `care.demo`, `+91{local_number}` phone templates | Low |
| `seed_packs.py:7` | `DEFAULT_PACK_SLUG = "generic_hospital_v1"` | Low (API default only) |

---

## What is OK (not pack-story hardcodes)

- **Manifest `counts` vs list lengths** — pack declares its own expected sizes; validators enforce consistency with *that* pack’s manifest, not a global N.
- **CARE API enums** — e.g. location `form='bd'`, `mode`, token `resource_type` ∈ `{practitioner, location, healthcare_service}`, encounter classes `amb`/`imp`/`emer`, schedule day 0–6, slot math vs `MAX_SLOTS_PER_AVAILABILITY`.
- **Structural / ref integrity** — unique refs, required fields, `user_ref` ∈ users, activity refs ∈ specimens/observations/charges/locations/services, inventory slug uniqueness, positive `stock_quantity`.
- **Pack-driven loops** — catalogue seeders walk pack JSON; questionnaire seeder loops pack `forms`; clinical visit expansion uses pack `ip_in_progress` / `emergency` / `op_org_refs` / `questionnaire_slugs`.
- **Shared `data/*.json` form library** — OK; pack chooses slugs via `questionnaires.json`.
- **Models / runner / client** — status enums, API wrappers; no hospital story.

---

## Already fixed (do not re-litigate)

From the pack-agnostic clinical / token-category work (see plans under `~/.cursor/plans/`, implemented in tree):

| Topic | Status |
|-------|--------|
| Questionnaires | Pack `questionnaires.json` drives forms; no `DEMO_QUESTIONNAIRE_SLUGS` forcing both demo forms |
| Clinical visit counts | No fixed “exactly 3 IP / 2 emergency”; lists may be empty; refs validated against pack |
| Visit math | Dynamic: `op_per_patient × patients + len(ip) + len(emergency)` vs manifest count — **not** hard-coded `op×n+3+2` |
| Forced `patient:001` / `department:emergency` on emergency rows | Removed from validator |
| Hardcoded form slug constants in clinical seeder | Removed; uses pack `questionnaire_slugs` + `fill_key` |
| Token categories | Pack JSON is source of truth; no Python OP/SP-only set |
| Step registry / manifest steps | Steps selectable via pack manifest; not a fixed hospital narrative |

Remaining clinical debt is listed above (fill_key registry, OP≥1, non-empty questionnaires, mandatory medication, bed≥3, inventory location refs).

---

## Recommended next cleanup order

1. **Inventory location refs** — pack-driven store/pharmacy; validate refs against foundation; drop `STORE_REF`/`PHARMACY_REF` constants.
2. **Bed floor** — remove `bed_count < 3`; optional consistency with IP bed refs only.
3. **Clinical plan flexibility** — allow `op_closed_per_patient == 0` and empty `questionnaire_slugs`; remove `department:medical_surgical` fallback.
4. **Scenario shape** — optional `medication` (and related fields); validate PK slug only when medication present.
5. **Category defaults** — remove Lab Tests / Laboratory / Medicines silent defaults; require pack data.
6. **Administration reuse** — keep CARE reuse rule; stop requiring the exact `department:administration` ref string if a clearer pack convention exists.
7. **Document fill_key registry** — vitals / op_consultation required keys; treat new fill keys as explicit engine extensions.

---

## Quick reference: primary files scanned

- `services/validators/*.py` (all)
- `services/seeders/*.py` (all)
- `services/demo_forms.py`, `seed_payloads.py`, `seed_step_registry.py`, `seed_validation.py`, `care_seed_client.py`, `seed_packs.py`, `runner.py`
- Models: no pack-story hardcodes
- Pack data cited only to show where engine assumptions align with `generic_hospital_v1`
