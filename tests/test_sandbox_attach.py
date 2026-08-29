"""Unit tests for attach-to-existing-facility sandbox API."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from care_demo_facility_setup.models import SeedRunStatus, SeedRunStepStatus
from care_demo_facility_setup.services.sandbox_attach import summarize_seed_run
from care_demo_facility_setup.services.seed_errors import SeedRunExecutionError


class SummarizeSeedRunTests(TestCase):
    def test_prefers_message_and_formats_stats(self):
        run = SimpleNamespace(
            external_id="11111111-1111-1111-1111-111111111111",
            pack_slug="generic_hospital_v1",
            profile_slug="local",
            steps=SimpleNamespace(
                all=lambda: SimpleNamespace(
                    order_by=lambda *_: [
                        SimpleNamespace(
                            key="validate",
                            status=SeedRunStepStatus.SUCCEEDED,
                            message="ok",
                            stats={"patients": 10},
                        ),
                        SimpleNamespace(
                            key="facility",
                            status=SeedRunStepStatus.SUCCEEDED,
                            message="Attached existing facility Sunrise Clinic",
                            stats={"created": 0, "attached": 1},
                        ),
                        SimpleNamespace(
                            key="patients",
                            status=SeedRunStepStatus.SUCCEEDED,
                            message="",
                            stats={"created": 10},
                        ),
                        SimpleNamespace(
                            key="inventory_items",
                            status=SeedRunStepStatus.SUCCEEDED,
                            message="",
                            stats={
                                "created": 318,
                                "products_received": 318,
                                "transferred": 318,
                            },
                        ),
                        SimpleNamespace(
                            key="clinical_visits",
                            status=SeedRunStepStatus.SUCCEEDED,
                            message=(
                                "Created 25 clinical visits "
                                "(20 closed OP, 3 IP, 2 emergency, 3 beds)."
                            ),
                            stats={
                                "created": 25,
                                "op_closed": 20,
                                "ip_in_progress": 3,
                                "emergency": 2,
                                "beds_assigned": 3,
                            },
                        ),
                        SimpleNamespace(
                            key="questionnaires",
                            status=SeedRunStepStatus.SUCCEEDED,
                            message="",
                            stats={"created": 12, "reused": 3},
                        ),
                        SimpleNamespace(
                            key="facility_foundation",
                            status=SeedRunStepStatus.SUCCEEDED,
                            message="",
                            stats={
                                "departments_created": 4,
                                "departments_reused": 1,
                                "locations_created": 8,
                                "healthcare_services_created": 6,
                            },
                        ),
                        SimpleNamespace(
                            key="schedules",
                            status=SeedRunStepStatus.SUCCEEDED,
                            message="",
                            stats={},
                        ),
                        SimpleNamespace(
                            key="token_categories",
                            status=SeedRunStepStatus.FAILED,
                            message="boom",
                            stats={},
                        ),
                    ]
                )
            ),
        )
        loaded = summarize_seed_run(run)
        self.assertEqual(
            loaded["_meta"],
            {
                "seed_run_id": "11111111-1111-1111-1111-111111111111",
                "pack_slug": "generic_hospital_v1",
                "profile_slug": "local",
            },
        )
        self.assertNotIn("seed_run_id", loaded)
        self.assertNotIn("pack_slug", loaded)
        self.assertNotIn("profile_slug", loaded)
        self.assertNotIn("validate", loaded)
        self.assertNotIn("token_categories", loaded)
        self.assertNotIn("schedules", loaded)
        self.assertEqual(loaded["facility"], "Attached existing facility Sunrise Clinic")
        self.assertEqual(loaded["patients"], "10 created")
        self.assertEqual(
            loaded["product_knowledges"],
            "318 product knowledges · 318 received · 318 transferred",
        )
        self.assertEqual(
            loaded["clinical_visits"],
            "Created 25 clinical visits (20 closed OP, 3 IP, 2 emergency, 3 beds).",
        )
        self.assertEqual(loaded["questionnaires"], "12 created, 3 reused")
        self.assertEqual(
            loaded["facility_foundation"],
            "4 departments · 1 departments reused · 8 locations · 6 services",
        )

    def test_formats_facility_attached_from_stats_without_message(self):
        run = SimpleNamespace(
            external_id="22222222-2222-2222-2222-222222222222",
            pack_slug="generic_hospital_v1",
            profile_slug="local",
            steps=SimpleNamespace(
                all=lambda: SimpleNamespace(
                    order_by=lambda *_: [
                        SimpleNamespace(
                            key="facility",
                            status=SeedRunStepStatus.SUCCEEDED,
                            message="",
                            stats={"created": 0, "attached": 1},
                        ),
                    ]
                )
            ),
        )
        loaded = summarize_seed_run(run)
        self.assertEqual(loaded["facility"], "1 attached")


class SeedExistingFacilityGuardsTests(TestCase):
    def test_requires_superuser(self):
        from care_demo_facility_setup.services.sandbox_attach import seed_existing_facility

        with self.assertRaises(SeedRunExecutionError):
            seed_existing_facility(
                facility_external_id="fac",
                geo_organization_external_id="geo",
                requested_by=SimpleNamespace(is_superuser=False),
            )

    @patch("care_demo_facility_setup.services.sandbox_attach.DemoSeedRunner")
    @patch("care_demo_facility_setup.services.sandbox_attach.create_attached_seed_run")
    def test_executes_runner_sync_not_celery(self, create_run, runner_cls):
        from care_demo_facility_setup.services.sandbox_attach import seed_existing_facility

        run = MagicMock()
        run.status = SeedRunStatus.SUCCEEDED
        create_run.return_value = run
        runner = runner_cls.return_value

        result = seed_existing_facility(
            facility_external_id="fac-id",
            geo_organization_external_id="geo-id",
            requested_by=SimpleNamespace(is_superuser=True),
            pack_slug="generic_hospital_v1",
        )

        create_run.assert_called_once()
        runner_cls.assert_called_once_with(run)
        runner.execute.assert_called_once_with()
        self.assertIs(result, run)


class DemoSeedRunnerAttachModeTests(TestCase):
    @patch("care_demo_facility_setup.services.runner.CareSeedClient")
    @patch("care_demo_facility_setup.services.runner.load_profile")
    @patch("care_demo_facility_setup.services.runner.load_seed_pack")
    @patch("care_demo_facility_setup.services.runner.get_executable_seed_step_definitions")
    def test_skips_already_succeeded_facility_step(
        self,
        get_executable,
        load_pack,
        load_profile,
        _client,
    ):
        from care_demo_facility_setup.services.runner import DemoSeedRunner

        facility_executor = MagicMock()
        patients_executor = MagicMock(return_value=SimpleNamespace(message="ok", stats={"created": 1}))
        get_executable.return_value = [
            SimpleNamespace(key="facility", executor=facility_executor, initial_stats=dict),
            SimpleNamespace(key="patients", executor=patients_executor, initial_stats=dict),
        ]
        load_pack.return_value = {"manifest": {}}
        load_profile.return_value = {
            "slug": "local",
            "geo_organization_external_id": "profile-geo",
        }

        facility_step = SimpleNamespace(
            status=SeedRunStepStatus.SUCCEEDED,
            started_date=None,
            finished_date=None,
            pk=1,
        )
        patients_step = SimpleNamespace(
            status=SeedRunStepStatus.PENDING,
            started_date=None,
            finished_date=None,
            pk=2,
        )

        run = MagicMock()
        run.status = SeedRunStatus.QUEUED
        run.dry_run = False
        run.requested_by = SimpleNamespace(is_superuser=True)
        run.pack_slug = "generic_hospital_v1"
        run.profile_slug = "local"
        run.request_payload = {"geo_organization_external_id": "sandbox-geo"}
        run.pk = 99
        run.started_date = None

        runner = DemoSeedRunner(run)
        self.assertEqual(runner.context.geo_organization, "sandbox-geo")

        with (
            patch.object(runner, "_get_step", side_effect=[facility_step, patients_step, patients_step]),
            patch.object(runner, "_mark_run") as mark_run,
            patch.object(runner, "_mark_step") as mark_step,
            patch("care_demo_facility_setup.services.runner.SeedRunStep.objects") as step_objects,
        ):
            step_objects.filter.return_value.update = MagicMock()
            runner.execute()

        facility_executor.assert_not_called()
        patients_executor.assert_called_once()
        mark_run.assert_any_call(SeedRunStatus.RUNNING, started=True)
        mark_run.assert_any_call(SeedRunStatus.SUCCEEDED, error="", finished=True)
        self.assertTrue(mark_step.called)
