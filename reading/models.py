from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel
from library.models import Book


class Device(TimeStampedModel):
    TYPE_WEB = "web"
    TYPE_MOBILE = "mobile"
    TYPE_TABLET = "tablet"
    TYPE_EREADER = "ereader"
    TYPE_OTHER = "other"

    TYPE_CHOICES = [
        (TYPE_WEB, "Web"),
        (TYPE_MOBILE, "Mobile"),
        (TYPE_TABLET, "Tablet"),
        (TYPE_EREADER, "E-Reader"),
        (TYPE_OTHER, "Other"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="devices",
    )
    name = models.CharField(max_length=255)
    device_type = models.CharField(
        max_length=16, choices=TYPE_CHOICES, default=TYPE_OTHER
    )
    last_seen_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-updated_at", "name"]

    def __str__(self):
        # Django provides `get_<field>_display()` dynamically for choice fields.
        return f"{self.name} ({self.get_device_type_display()})"  # type: ignore[attr-defined]


class ReadingSession(TimeStampedModel):
    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reading_sessions",
    )
    book = models.ForeignKey(
        Book, on_delete=models.CASCADE, related_name="reading_sessions"
    )
    name = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "book"],
                condition=Q(is_active=True),
                name="unique_active_reading_session_per_user_book",
            )
        ]

    def __str__(self):
        label = self.name.strip() if self.name else ""
        if label:
            return f"{self.user.get_username()}: {self.book.title} ({label})"
        return f"{self.user.get_username()}: {self.book.title}"


class ReadingProgress(TimeStampedModel):
    session = models.OneToOneField(
        ReadingSession, on_delete=models.CASCADE, related_name="progress"
    )
    device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reading_progresses",
    )
    # Canonical W3C-style session state: current reading location selector/locator.
    # This is intentionally flexible JSON and should preserve unknown fields.
    current_location = models.JSONField(default=dict)
    progression = models.FloatField(blank=True, null=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        if self.progression is None:
            return f"Progress: {self.session}"
        return f"Progress: {self.session} ({self.progression:.3f})"


class Annotation(TimeStampedModel):
    MOTIVATION_HIGHLIGHTING = "highlighting"
    MOTIVATION_COMMENTING = "commenting"
    MOTIVATION_BOOKMARKING = "bookmarking"

    MOTIVATION_CHOICES = [
        (MOTIVATION_HIGHLIGHTING, "Highlighting"),
        (MOTIVATION_COMMENTING, "Commenting"),
        (MOTIVATION_BOOKMARKING, "Bookmarking"),
    ]

    session = models.ForeignKey(
        ReadingSession, on_delete=models.CASCADE, related_name="annotations"
    )
    device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="annotations",
    )
    motivation = models.CharField(
        max_length=32, choices=MOTIVATION_CHOICES, null=True, blank=True
    )
    target = models.JSONField(default=dict)
    body = models.JSONField(default=list, blank=True)
    source_import = models.JSONField(default=dict, blank=True)
    derived_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derived_annotations",
    )
    source_session = models.ForeignKey(
        ReadingSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promoted_annotations",
    )
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        # Django provides `get_<field>_display()` dynamically for choice fields.
        return f"{self.get_motivation_display()} on {self.session}"  # type: ignore[attr-defined]
