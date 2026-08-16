from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class MaintenanceFrequency(models.TextChoices):
    MANUAL = "manual", "Manual only"
    HOURLY = "hourly", "Hourly"
    SIX_HOURS = "6_hours", "Every 6 hours"
    TWELVE_HOURS = "12_hours", "Every 12 hours"
    DAILY = "daily", "Daily"
    WEEKLY = "weekly", "Weekly"

    @property
    def interval(self) -> timedelta | None:
        return {
            "manual": None,
            "hourly": timedelta(hours=1),
            "6_hours": timedelta(hours=6),
            "12_hours": timedelta(hours=12),
            "daily": timedelta(days=1),
            "weekly": timedelta(days=7),
        }[self.value]


class MaintenanceTaskConfig(models.Model):
    task_key = models.CharField(max_length=100, unique=True, editable=False)
    enabled = models.BooleanField(default=False)
    frequency = models.CharField(
        max_length=16,
        choices=MaintenanceFrequency.choices,
        default=MaintenanceFrequency.MANUAL,
    )
    next_due_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_dispatched_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("task_key",)
        constraints = [
            models.CheckConstraint(
                condition=Q(frequency__in=MaintenanceFrequency.values),
                name="maintenance_frequency_is_bounded",
            )
        ]
        verbose_name = "Maintenance Task"
        verbose_name_plural = "Maintenance Tasks"

    def __str__(self):
        return self.task_key

    def clean(self):
        super().clean()
        if self.frequency not in MaintenanceFrequency.values:
            raise ValidationError({"frequency": "Select a supported frequency."})

    def save(self, *args, **kwargs):
        previous = None
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                "enabled", "frequency"
            ).first()
        schedule_changed = previous is None or previous != {
            "enabled": self.enabled,
            "frequency": self.frequency,
        }
        if schedule_changed:
            frequency = MaintenanceFrequency(self.frequency)
            self.next_due_at = (
                timezone.now() + frequency.interval
                if self.enabled and frequency.interval is not None
                else None
            )
        super().save(*args, **kwargs)


class MaintenanceTaskRun(models.Model):
    class Trigger(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        ADMIN = "admin", "Admin Run now"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    configuration = models.ForeignKey(
        MaintenanceTaskConfig,
        on_delete=models.PROTECT,
        related_name="runs",
    )
    task_key = models.CharField(max_length=100, editable=False)
    trigger = models.CharField(max_length=16, choices=Trigger.choices, editable=False)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="requested_maintenance_runs",
        editable=False,
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.QUEUED,
        editable=False,
    )
    queued_at = models.DateTimeField(default=timezone.now, editable=False)
    started_at = models.DateTimeField(null=True, blank=True, editable=False)
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    result_summary = models.TextField(blank=True, editable=False)
    result_counts = models.JSONField(default=dict, blank=True, editable=False)
    failure_summary = models.TextField(blank=True, editable=False)

    class Meta:
        ordering = ("-queued_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("task_key",),
                condition=Q(status__in=("queued", "running")),
                name="maintenance_one_active_run_per_task",
            )
        ]
        indexes = [models.Index(fields=("task_key", "-queued_at"))]
        verbose_name = "Maintenance Task Run"
        verbose_name_plural = "Maintenance Task Runs"

    def __str__(self):
        return f"{self.task_key} ({self.status})"
