from __future__ import annotations

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def _default_expires_at():
    return timezone.now() + timedelta(hours=24)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="IdempotencyRecord",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(max_length=128)),
                ("method", models.CharField(max_length=8)),
                ("path", models.CharField(max_length=400)),
                ("request_hash", models.CharField(max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[("processing", "Processing"), ("completed", "Completed")],
                        default="processing",
                        max_length=16,
                    ),
                ),
                ("response_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("response_body", models.JSONField(blank=True, null=True)),
                ("expires_at", models.DateTimeField(default=_default_expires_at)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="idempotency_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="idempotencyrecord",
            constraint=models.UniqueConstraint(
                fields=("user", "key"), name="unique_idempotency_key_per_user"
            ),
        ),
    ]

