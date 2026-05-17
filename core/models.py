import uuid

from datetime import timedelta
from django.db import models
from django.conf import settings
from django.utils import timezone


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(UUIDModel):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ServerSetting(TimeStampedModel):
    """
    Server-wide (instance-wide) settings stored in the database.

    Notes:
    - This is not intended for secrets.
    - Access should go through core.server_settings for caching.
    """

    key = models.CharField(max_length=128, unique=True)
    value = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key


def _default_idempotency_expires_at():
    return timezone.now() + timedelta(hours=24)


class IdempotencyRecord(TimeStampedModel):
    """
    Stores a short-lived idempotency key record for safe retries.

    Notes:
    - This is request metadata, not user data. Do not treat it as durable domain state.
    - Used selectively by endpoints that opt-in (not global middleware).
    """

    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="idempotency_records",
    )
    key = models.CharField(max_length=128)
    method = models.CharField(max_length=8)
    path = models.CharField(max_length=400)
    request_hash = models.CharField(max_length=64)

    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PROCESSING
    )
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)

    expires_at = models.DateTimeField(default=_default_idempotency_expires_at)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "key"], name="unique_idempotency_key_per_user"
            )
        ]
        ordering = ["-created_at"]
