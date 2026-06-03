# Generated for care_demo_facility_setup V1 seed run tracking.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SeedRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "external_id",
                    models.UUIDField(default=uuid.uuid4, db_index=True, unique=True),
                ),
                (
                    "created_date",
                    models.DateTimeField(auto_now_add=True, blank=True, db_index=True, null=True),
                ),
                (
                    "modified_date",
                    models.DateTimeField(auto_now=True, blank=True, db_index=True, null=True),
                ),
                ("deleted", models.BooleanField(db_index=True, default=False)),
                ("pack_slug", models.CharField(db_index=True, max_length=128)),
                ("profile_slug", models.CharField(db_index=True, max_length=128)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("validating", "Validating"),
                            ("running", "Running"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                            ("validation_failed", "Validation failed"),
                        ],
                        db_index=True,
                        default="queued",
                        max_length=32,
                    ),
                ),
                ("dry_run", models.BooleanField(default=False)),
                ("request_payload", models.JSONField(blank=True, default=dict)),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True)),
                ("started_date", models.DateTimeField(blank=True, null=True)),
                ("finished_date", models.DateTimeField(blank=True, null=True)),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="demo_facility_seed_runs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_date",),
            },
        ),
        migrations.CreateModel(
            name="SeedRunStep",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "external_id",
                    models.UUIDField(default=uuid.uuid4, db_index=True, unique=True),
                ),
                (
                    "created_date",
                    models.DateTimeField(auto_now_add=True, blank=True, db_index=True, null=True),
                ),
                (
                    "modified_date",
                    models.DateTimeField(auto_now=True, blank=True, db_index=True, null=True),
                ),
                ("deleted", models.BooleanField(db_index=True, default=False)),
                ("order", models.PositiveIntegerField()),
                ("key", models.CharField(max_length=128)),
                ("title", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                            ("skipped", "Skipped"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("message", models.TextField(blank=True)),
                ("stats", models.JSONField(blank=True, default=dict)),
                ("started_date", models.DateTimeField(blank=True, null=True)),
                ("finished_date", models.DateTimeField(blank=True, null=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="steps",
                        to="care_demo_facility_setup.seedrun",
                    ),
                ),
            ],
            options={
                "ordering": ("run", "order"),
                "unique_together": {("run", "key"), ("run", "order")},
            },
        ),
        migrations.CreateModel(
            name="SeedRunArtifact",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "external_id",
                    models.UUIDField(default=uuid.uuid4, db_index=True, unique=True),
                ),
                (
                    "created_date",
                    models.DateTimeField(auto_now_add=True, blank=True, db_index=True, null=True),
                ),
                (
                    "modified_date",
                    models.DateTimeField(auto_now=True, blank=True, db_index=True, null=True),
                ),
                ("deleted", models.BooleanField(db_index=True, default=False)),
                ("ref", models.CharField(db_index=True, max_length=255)),
                ("resource_type", models.CharField(db_index=True, max_length=128)),
                (
                    "resource_external_id",
                    models.UUIDField(blank=True, db_index=True, null=True),
                ),
                ("slug", models.CharField(blank=True, db_index=True, max_length=255)),
                ("payload", models.JSONField(blank=True, default=dict)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="artifacts",
                        to="care_demo_facility_setup.seedrun",
                    ),
                ),
                (
                    "step",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="artifacts",
                        to="care_demo_facility_setup.seedrunstep",
                    ),
                ),
            ],
            options={
                "ordering": ("created_date",),
                "unique_together": {("run", "ref")},
            },
        ),
    ]
