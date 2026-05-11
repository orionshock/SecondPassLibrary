import uuid

from django.db import models


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
