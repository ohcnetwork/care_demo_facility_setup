from django.db import models
from django.conf import settings

from care.utils.models.base import BaseModel


class SeedRunStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    VALIDATING = "validating", "Validating"
    RUNNING = "running", "Running"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    VALIDATION_FAILED = "validation_failed", "Validation failed"


class SeedRunStepStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    RUNNING = "running", "Running"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class SeedRun(BaseModel):
    pack_slug = models.CharField(max_length=128, db_index=True)
    profile_slug = models.CharField(max_length=128, db_index=True)
    status = models.CharField(
        max_length=32,
        choices=SeedRunStatus.choices,
        default=SeedRunStatus.QUEUED,
        db_index=True,
    )
    dry_run = models.BooleanField(default=False)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="demo_facility_seed_runs",
    )
    request_payload = models.JSONField(default=dict, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    started_date = models.DateTimeField(null=True, blank=True)
    finished_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_date",)

    def __str__(self):
        return f"{self.pack_slug}/{self.profile_slug} ({self.status})"


class SeedRunStep(BaseModel):
    run = models.ForeignKey(
        SeedRun,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    order = models.PositiveIntegerField()
    key = models.CharField(max_length=128)
    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=32,
        choices=SeedRunStepStatus.choices,
        default=SeedRunStepStatus.PENDING,
        db_index=True,
    )
    message = models.TextField(blank=True)
    stats = models.JSONField(default=dict, blank=True)
    started_date = models.DateTimeField(null=True, blank=True)
    finished_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("run", "order")
        unique_together = (("run", "key"), ("run", "order"))

    def __str__(self):
        return f"{self.run_id}: {self.key} ({self.status})"


class SeedRunArtifact(BaseModel):
    run = models.ForeignKey(
        SeedRun,
        on_delete=models.CASCADE,
        related_name="artifacts",
    )
    step = models.ForeignKey(
        SeedRunStep,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="artifacts",
    )
    ref = models.CharField(max_length=255, db_index=True)
    resource_type = models.CharField(max_length=128, db_index=True)
    resource_external_id = models.UUIDField(null=True, blank=True, db_index=True)
    slug = models.CharField(max_length=255, blank=True, db_index=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("created_date",)
        unique_together = (("run", "ref"),)

    def __str__(self):
        return f"{self.ref} -> {self.resource_type}"
