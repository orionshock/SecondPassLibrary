import uuid

from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .server_setting_labels import server_setting_display_name


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(UUIDModel):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class ServerIdentity(models.Model):
    """Immutable, non-secret identity for this server database."""

    SINGLETON_ID = 1

    id = models.PositiveSmallIntegerField(
        primary_key=True,
        default=SINGLETON_ID,
        editable=False,
    )
    server_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1),
                name="server_identity_is_singleton",
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk != self.SINGLETON_ID:
            raise ValidationError("Only one Server identity row is allowed.")
        if not self._state.adding:
            stored_id = type(self).objects.values_list("server_id", flat=True).get(
                pk=self.pk
            )
            if stored_id != self.server_id:
                raise ValidationError({"server_id": "The Server ID is immutable."})
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("The Server identity cannot be deleted.")

    def __str__(self):
        return str(self.server_id)


class ServerSetting(TimeStampedModel):
    """
    Server-wide (instance-wide) settings stored in the database.

    Notes:
    - This is not intended for secrets.
    - Access should go through core.server_settings for its freshness policy.
    """

    key = models.CharField(max_length=128, unique=True)
    value = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["key"]

    @property
    def display_key(self):
        return server_setting_display_name(self.key)

    def __str__(self):
        return str(self.display_key)


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
