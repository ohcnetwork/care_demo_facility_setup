from __future__ import annotations

import random
from datetime import timedelta

from django.utils import timezone

from care_demo_facility_setup.models import SeedRunArtifact, SeedRunStep
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.seed_artifacts import SeedArtifactStore, get_value, to_plain
from care_demo_facility_setup.services.seed_errors import SeedRunExecutionError

SNOMED = "http://snomed.info/sct"
UCUM = "http://unitsofmeasure.org"
TIMING_SYSTEM = "http://terminology.hl7.org/CodeSystem/v3-GTSAbbreviation"


class ClinicalVisitSeeder:
    def __init__(
        self,
        *,
        client: CareSeedClient,
        artifacts: SeedArtifactStore,
        run_id: int,
        requester_external_id: str,
    ):
        self.client = client
        self.artifacts = artifacts
        self.run_id = run_id
        self.requester_external_id = requester_external_id
        self._rng = random.Random(run_id)

    def seed(
        self,
        *,
        step: SeedRunStep,
        visits_plan: dict,
        scenarios: list,
        facility_template: dict,
        patients_config: dict,
        questionnaires_config: dict,
    ) -> tuple[str, dict]:
        if not scenarios:
            raise SeedRunExecutionError("clinical_scenarios.json must contain at least one scenario.")

        facility_id = self.artifacts.external_id(facility_template.get("ref", "facility:main"))
        form_profiles = self._form_profiles(questionnaires_config)
        question_maps = self._load_question_maps(visits_plan, form_profiles)
        visits = self._expand_visits(visits_plan, patients_config)

        stats = {
            "created": 0,
            "op_closed": 0,
            "ip_in_progress": 0,
            "emergency": 0,
            "beds_assigned": 0,
        }
        for index, visit in enumerate(visits):
            ref = visit["ref"]
            if SeedRunArtifact.objects.filter(run=self.artifacts.run, ref=ref).exists():
                continue

            scenario = scenarios[index % len(scenarios)]
            start = timezone.now() - timedelta(hours=index)
            encounter = self._create_encounter(
                facility_id=facility_id,
                patient_id=self.artifacts.external_id(visit["patient_ref"]),
                org_id=self.artifacts.external_id(visit["org_ref"]),
                encounter_class=visit["encounter_class"],
                start=start,
            )
            encounter_id = get_value(encounter, "id")
            patient_id = self.artifacts.external_id(visit["patient_ref"])

            self._upsert_clinical(patient_id, encounter_id, scenario, visit["encounter_class"], start)
            self._submit_forms(patient_id, encounter_id, scenario, question_maps)

            if visit.get("bed_ref"):
                self._assign_bed(facility_id, encounter_id, visit["bed_ref"], start)
                stats["beds_assigned"] += 1

            if visit["close"]:
                end = start + timedelta(minutes=45)
                self.client.update_encounter(
                    encounter_id,
                    {
                        "status": "completed",
                        "encounter_class": visit["encounter_class"],
                        "priority": "routine",
                        "period": {"start": start.isoformat(), "end": end.isoformat()},
                    },
                )
                stats["op_closed"] += 1
            elif visit["encounter_class"] == "imp":
                stats["ip_in_progress"] += 1
            elif visit["encounter_class"] == "emer":
                stats["emergency"] += 1

            self.artifacts.store(
                step=step,
                ref=ref,
                resource_type="Encounter",
                payload={
                    **to_plain(encounter),
                    "id": encounter_id,
                    "visit_kind": visit["kind"],
                    "patient_ref": visit["patient_ref"],
                    "scenario": scenario.get("name"),
                },
            )
            stats["created"] += 1

        message = (
            f"Created {stats['created']} clinical visits "
            f"({stats['op_closed']} closed OP, {stats['ip_in_progress']} IP, "
            f"{stats['emergency']} emergency, {stats['beds_assigned']} beds)."
        )
        return message, stats

    def _form_profiles(self, questionnaires_config: dict) -> dict[str, str]:
        profiles: dict[str, str] = {}
        for form in questionnaires_config.get("forms") or []:
            slug = form.get("slug")
            fill_key = form.get("fill_key")
            if isinstance(slug, str) and slug and isinstance(fill_key, str) and fill_key:
                profiles[slug] = fill_key
        return profiles

    def _load_question_maps(
        self,
        visits_plan: dict,
        form_profiles: dict[str, str],
    ) -> list[dict]:
        slugs = visits_plan.get("questionnaire_slugs") or []
        if not isinstance(slugs, list) or not slugs:
            raise SeedRunExecutionError("clinical_visits.questionnaire_slugs must be a non-empty list.")

        maps: list[dict] = []
        for slug in slugs:
            fill_key = form_profiles.get(slug)
            if not fill_key:
                raise SeedRunExecutionError(
                    f"Visit plan questionnaire slug '{slug}' is not declared in questionnaires.json."
                )
            artifact = SeedRunArtifact.objects.filter(
                run=self.artifacts.run,
                ref=f"questionnaire:{slug}",
            ).first()
            if not artifact or not isinstance(artifact.payload, dict):
                raise SeedRunExecutionError(
                    f"Missing questionnaire artifact for {slug}. Run the questionnaires step first."
                )
            question_ids = artifact.payload.get("question_ids")
            if not isinstance(question_ids, dict) or not question_ids:
                raise SeedRunExecutionError(f"Questionnaire artifact {slug} is missing resolved question_ids.")
            maps.append(
                {
                    "slug": slug,
                    "fill_key": fill_key,
                    "question_ids": {key: str(value) for key, value in question_ids.items()},
                }
            )
        return maps

    def _expand_visits(self, visits_plan: dict, patients_config: dict) -> list[dict]:
        patients = patients_config.get("patients") or []
        if not patients:
            raise SeedRunExecutionError("patients.json must define patients for clinical visits.")

        op_per_patient = int(visits_plan.get("op_closed_per_patient") or 0)
        op_org_refs = visits_plan.get("op_org_refs") or ["department:medical_surgical"]
        visits: list[dict] = []

        op_index = 0
        for patient in patients:
            patient_ref = patient["ref"]
            for visit_num in range(1, op_per_patient + 1):
                visits.append(
                    {
                        "ref": f"encounter:op:{patient_ref}:{visit_num}",
                        "kind": "op_closed",
                        "patient_ref": patient_ref,
                        "org_ref": op_org_refs[op_index % len(op_org_refs)],
                        "encounter_class": "amb",
                        "close": True,
                        "bed_ref": None,
                    }
                )
                op_index += 1

        for index, row in enumerate(visits_plan.get("ip_in_progress") or [], start=1):
            visits.append(
                {
                    "ref": f"encounter:ip:{row['patient_ref']}:{index}",
                    "kind": "ip_in_progress",
                    "patient_ref": row["patient_ref"],
                    "org_ref": row["org_ref"],
                    "encounter_class": "imp",
                    "close": False,
                    "bed_ref": row["bed_ref"],
                }
            )

        for index, row in enumerate(visits_plan.get("emergency") or [], start=1):
            visits.append(
                {
                    "ref": f"encounter:emer:{row['patient_ref']}:{index}",
                    "kind": "emergency",
                    "patient_ref": row["patient_ref"],
                    "org_ref": row["org_ref"],
                    "encounter_class": "emer",
                    "close": False,
                    "bed_ref": None,
                }
            )
        return visits

    def _create_encounter(
        self,
        *,
        facility_id: str,
        patient_id: str,
        org_id: str,
        encounter_class: str,
        start,
    ):
        return self.client.create_encounter(
            {
                "patient": patient_id,
                "facility": facility_id,
                "status": "in_progress",
                "encounter_class": encounter_class,
                "priority": "routine",
                "organizations": [org_id],
                "period": {"start": start.isoformat()},
            }
        )

    def _upsert_clinical(self, patient_id: str, encounter_id: str, scenario: dict, encounter_class: str, start):
        onset = start.date().isoformat()
        symptoms = [
            {
                "code": {
                    "code": item["code"],
                    "display": item["display"],
                    "system": SNOMED,
                },
                "clinical_status": "active",
                "verification_status": "confirmed",
                "severity": item["severity"],
                "category": "problem_list_item",
                "onset": {"onset_datetime": onset},
                "encounter": encounter_id,
            }
            for item in scenario.get("symptoms") or []
        ]
        if symptoms:
            self.client.upsert_symptoms(patient_id, symptoms)

        diagnoses = [
            {
                "code": {
                    "code": item["code"],
                    "display": item["display"],
                    "system": SNOMED,
                },
                "clinical_status": "active",
                "verification_status": "confirmed",
                "severity": item["severity"],
                "category": "encounter_diagnosis",
                "onset": {"onset_datetime": onset},
                "dirty": True,
                "encounter": encounter_id,
            }
            for item in scenario.get("diagnosis") or []
        ]
        if diagnoses:
            self.client.upsert_diagnosis(patient_id, diagnoses)

        medication = scenario.get("medication")
        if medication:
            category = "inpatient" if encounter_class == "imp" else "outpatient"
            prescription_id = f"{encounter_id}-{start.strftime('%Y%m%d%H%M%S')}"
            # Pharmacy dispense looks up stock via requested_product (ProductKnowledge).
            # CARE forbids setting both requested_product and free-text medication coding.
            pk_slug = medication.get("product_knowledge_slug")
            if not pk_slug:
                raise SeedRunExecutionError(
                    f"Scenario '{scenario.get('name')}' medication must set product_knowledge_slug "
                    "to a stocked inventory product_knowledge slug."
                )
            requested_product = self.artifacts.external_id(f"product_knowledge:{pk_slug}")
            self.client.upsert_medication_request(
                patient_id,
                [
                    {
                        "do_not_perform": False,
                        "dosage_instruction": [
                            {
                                "as_needed_boolean": False,
                                "dose_and_rate": {
                                    "type": "ordered",
                                    "dose_quantity": {
                                        "value": medication["dose_value"],
                                        "unit": {
                                            "code": medication["dose_unit_code"],
                                            "display": medication["dose_unit_display"],
                                            "system": UCUM,
                                        },
                                    },
                                },
                                "timing": {
                                    "repeat": {
                                        "frequency": medication["frequency"],
                                        "period": medication["period"],
                                        "period_unit": medication["period_unit"],
                                        "bounds_duration": {
                                            "value": medication["duration_value"],
                                            "unit": medication["duration_unit"],
                                        },
                                    },
                                    "code": {
                                        "code": medication["timing_code"],
                                        "display": medication["timing_display"],
                                        "system": TIMING_SYSTEM,
                                    },
                                },
                                "text": medication["text"],
                            }
                        ],
                        "requested_product": requested_product,
                        "status": "active",
                        "intent": "order",
                        "priority": "routine",
                        "category": category,
                        "authored_on": start.isoformat(),
                        "requester": self.requester_external_id,
                        "dirty": True,
                        "create_prescription": {
                            "status": "active",
                            "alternate_identifier": prescription_id,
                        },
                        "encounter": encounter_id,
                        "patient": patient_id,
                    }
                ],
            )

    def _submit_forms(self, patient_id: str, encounter_id: str, scenario: dict, question_maps: list[dict]):
        for form in question_maps:
            fill_key = form["fill_key"]
            slug = form["slug"]
            question_ids = form["question_ids"]
            if fill_key == "vitals":
                results = self._vitals_results(question_ids, scenario)
            elif fill_key == "op_consultation":
                results = self._op_consultation_results(question_ids, scenario)
            else:
                raise SeedRunExecutionError(
                    f"Unknown questionnaire fill_key '{fill_key}' for slug '{slug}'. "
                    "Supported fill keys: vitals, op_consultation."
                )
            self.client.submit_questionnaire(
                slug,
                {
                    "resource_id": encounter_id,
                    "encounter": encounter_id,
                    "patient": patient_id,
                    "results": results,
                },
            )

    def _vitals_results(self, question_ids: dict[str, str], scenario: dict) -> list[dict]:
        vitals = scenario.get("vitals") or {}
        return [
            _result(question_ids["temperature"], self._rand_int(vitals, "temp")),
            _result(question_ids["pulse"], self._rand_int(vitals, "pulse")),
            _result(question_ids["respiratory"], self._rand_int(vitals, "resp")),
            _result(question_ids["spo2"], self._rand_int(vitals, "spo2")),
            _result(question_ids["systolic"], self._rand_int(vitals, "sys_bp")),
            _result(question_ids["diastolic"], self._rand_int(vitals, "dia_bp")),
            _result(question_ids["grbs"], self._rng.randint(90, 140)),
        ]

    def _op_consultation_results(self, question_ids: dict[str, str], scenario: dict) -> list[dict]:
        medication = scenario.get("medication") or {}
        ongoing = medication.get("display") or medication.get("text") or ""
        return [
            _result(question_ids["history"], scenario.get("history_text") or ""),
            _result(question_ids["ongoing_med"], ongoing),
            _result(question_ids["admission"], "false"),
            _result(question_ids["advice"], scenario.get("advice") or ""),
        ]

    def _assign_bed(self, facility_id: str, encounter_id: str, bed_ref: str, start):
        bed_id = self.artifacts.external_id(bed_ref)
        self.client.create_location_association(
            facility_id,
            bed_id,
            {
                "status": "active",
                "encounter": encounter_id,
                "start_datetime": start.isoformat(),
                "end_datetime": None,
            },
        )

    def _rand_int(self, vitals: dict, prefix: str) -> int:
        low = int(vitals.get(f"{prefix}_min", 0))
        high = int(vitals.get(f"{prefix}_max", low))
        if high < low:
            low, high = high, low
        return self._rng.randint(low, high)


def _result(question_id: str, value) -> dict:
    return {"question_id": question_id, "values": [{"value": str(value)}]}
