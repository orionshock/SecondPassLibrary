from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel
from library.models import Book, BookFile


SELECTOR_KIND_EPUB_CFI = "epub_cfi"
SELECTOR_KIND_CHOICES = [
    (SELECTOR_KIND_EPUB_CFI, "EPUB CFI"),
]


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
    # Canonical W3C-style session state: current reading location selector/locator.
    #
    # Note: the *storage* field is flexible JSON, but the public Reading API
    # intentionally validates `current_location` with a strict allowlist of keys.
    # Reader clients should not treat this as arbitrary blob storage.
    current_location = models.JSONField(default=dict)
    progression = models.FloatField(blank=True, null=True)
    profile_version = models.CharField(max_length=16, default="0.1.0")

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
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="annotations")
    book_file = models.ForeignKey(
        BookFile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="annotations",
    )
    motivation = models.CharField(
        max_length=32, choices=MOTIVATION_CHOICES, null=True, blank=True
    )

    selector_kind = models.CharField(
        max_length=32,
        choices=SELECTOR_KIND_CHOICES,
        default=SELECTOR_KIND_EPUB_CFI,
    )
    selector_value = models.TextField()

    highlight_text = models.TextField(blank=True, default="")
    highlight_color = models.CharField(max_length=32, blank=True, default="")
    comment_text = models.TextField(blank=True, default="")

    # Internal/server-managed provenance for future import work. Not exposed as a
    # normal client-writable field via the public reading API.
    source_import = models.JSONField(default=dict, blank=True)
    profile_version = models.CharField(max_length=16, default="0.1.0")
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["session", "is_deleted", "created_at"]),
            models.Index(fields=["session", "is_deleted", "updated_at"]),
            models.Index(fields=["book", "is_deleted", "created_at"]),
            models.Index(fields=["book", "is_deleted", "updated_at"]),
        ]

    def __str__(self):
        # Django provides `get_<field>_display()` dynamically for choice fields.
        return f"{self.get_motivation_display()} on {self.session}"  # type: ignore[attr-defined]

    def clean(self):
        super().clean()

        supported_kinds = {SELECTOR_KIND_EPUB_CFI}
        if self.selector_kind and self.selector_kind not in supported_kinds:
            raise ValidationError({"selector_kind": "Unsupported selector_kind."})

        # Defensive integrity: annotation.book should match session.book.
        # Enforced by services for normal writes; keep it true for admin/manual edits too.
        if self.session_id and self.book_id and self.session.book_id != self.book_id:
            raise ValidationError({"book": "book must match session.book."})

    def save(self, *args, **kwargs):
        # Ensure model-level invariants are enforced for normal saves (including admin).
        # Callers can pass skip_full_clean=True for rare internal cases.
        skip_full_clean = bool(kwargs.pop("skip_full_clean", False))
        if not skip_full_clean:
            self.full_clean()
        return super().save(*args, **kwargs)
