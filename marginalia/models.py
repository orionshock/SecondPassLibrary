from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel
from library.models import Book


if TYPE_CHECKING:
    from uuid import UUID

    from django.contrib.auth.models import AbstractUser


MAX_CFI_LENGTH = 8 * 1024
MAX_LOCATION_LABEL_LENGTH = 255
MARGINALIA_PROFILE_VERSION = "0.1.0"

HIGHLIGHT_COLOR_YELLOW = "yellow"
HIGHLIGHT_COLOR_GREEN = "green"
HIGHLIGHT_COLOR_BLUE = "blue"
HIGHLIGHT_COLOR_PINK = "pink"
HIGHLIGHT_COLOR_PURPLE = "purple"
HIGHLIGHT_COLOR_ORANGE = "orange"
HIGHLIGHT_COLOR_CHOICES = [
    (HIGHLIGHT_COLOR_YELLOW, "Yellow"),
    (HIGHLIGHT_COLOR_GREEN, "Green"),
    (HIGHLIGHT_COLOR_BLUE, "Blue"),
    (HIGHLIGHT_COLOR_PINK, "Pink"),
    (HIGHLIGHT_COLOR_PURPLE, "Purple"),
    (HIGHLIGHT_COLOR_ORANGE, "Orange"),
]


class ReadingSession(TimeStampedModel):
    STATUS_ACTIVE = "active"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_CLOSED, "Closed"),
    ]

    if TYPE_CHECKING:
        id: UUID
        user: AbstractUser
        user_id: int
        book_id: UUID

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="marginalia_sessions",
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.PROTECT,
        related_name="marginalia_sessions",
    )
    name = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["active", "closed"]),
                name="marginalia_session_status_is_valid",
            ),
            models.UniqueConstraint(
                fields=["user", "book"],
                condition=Q(status="active"),
                name="marginalia_one_active_session_per_user_book",
            ),
            models.CheckConstraint(
                condition=Q(status="closed", closed_at__isnull=False)
                | ~Q(status="closed"),
                name="marginalia_closed_session_has_timestamp",
            ),
            models.CheckConstraint(
                condition=Q(status="active", closed_at__isnull=True)
                | ~Q(status="active"),
                name="marginalia_active_session_has_no_closed_at",
            ),
        ]

    @property
    def is_active(self) -> bool:
        return self.status == self.STATUS_ACTIVE

    def __str__(self) -> str:
        label = self.name.strip() if self.name else ""
        suffix = f" ({label})" if label else ""
        return f"{self.user.get_username()}: {self.book.title}{suffix}"


class SessionProgress(TimeStampedModel):
    session = models.OneToOneField(
        ReadingSession,
        on_delete=models.CASCADE,
        related_name="progress",
    )
    cfi = models.TextField(max_length=MAX_CFI_LENGTH, blank=True, default="")
    location_label = models.CharField(
        max_length=MAX_LOCATION_LABEL_LENGTH,
        blank=True,
        default="",
    )
    progression = models.FloatField(blank=True, null=True)
    profile_version = models.CharField(
        max_length=16,
        default=MARGINALIA_PROFILE_VERSION,
    )

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(progression__isnull=True)
                | Q(progression__gte=0.0, progression__lte=1.0),
                name="marginalia_progression_in_unit_interval",
            )
        ]

    def __str__(self) -> str:
        return f"Progress: {self.session}"


class Annotation(TimeStampedModel):
    KIND_BOOKMARK = "bookmark"
    KIND_HIGHLIGHT = "highlight"
    KIND_CHOICES = [
        (KIND_BOOKMARK, "Bookmark"),
        (KIND_HIGHLIGHT, "Highlight"),
    ]

    session = models.ForeignKey(
        ReadingSession,
        on_delete=models.CASCADE,
        related_name="annotations",
    )
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    cfi = models.TextField(max_length=MAX_CFI_LENGTH)
    location_label = models.CharField(
        max_length=MAX_LOCATION_LABEL_LENGTH,
        blank=True,
        default="",
    )
    highlight_text = models.TextField(blank=True, default="")
    comment_text = models.TextField(blank=True, default="")
    quote_prefix = models.TextField(blank=True, default="")
    quote_suffix = models.TextField(blank=True, default="")
    highlight_color = models.CharField(
        max_length=16,
        choices=HIGHLIGHT_COLOR_CHOICES,
        blank=True,
        default="",
    )
    profile_version = models.CharField(
        max_length=16,
        default=MARGINALIA_PROFILE_VERSION,
    )
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["session", "is_deleted", "created_at"],
                name="marg_sess_del_created_idx",
            ),
            models.Index(
                fields=["session", "is_deleted", "updated_at"],
                name="marg_sess_del_updated_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(kind__in=["bookmark", "highlight"]),
                name="marginalia_annotation_kind_is_valid",
            ),
            models.CheckConstraint(
                condition=~Q(cfi=""),
                name="marginalia_annotation_has_cfi",
            ),
            models.CheckConstraint(
                condition=~Q(kind="highlight") | ~Q(highlight_text=""),
                name="marginalia_highlight_has_text",
            ),
            models.CheckConstraint(
                condition=~Q(kind="bookmark")
                | Q(
                    highlight_text="",
                    quote_prefix="",
                    quote_suffix="",
                    comment_text="",
                    highlight_color="",
                ),
                name="marginalia_bookmark_has_no_content",
            ),
        ]

    @property
    def book(self) -> Book:
        return self.session.book

    @property
    def user(self):
        return self.session.user

    def clean(self) -> None:
        super().clean()
        if not self.cfi:
            raise ValidationError({"cfi": "A located annotation requires a CFI."})

        if self.kind == self.KIND_HIGHLIGHT:
            if not self.highlight_text:
                raise ValidationError(
                    {"highlight_text": "Highlight text is required for highlights."}
                )
            if not self.highlight_color:
                self.highlight_color = HIGHLIGHT_COLOR_YELLOW
        elif self.kind == self.KIND_BOOKMARK:
            if (
                self.highlight_text
                or self.quote_prefix
                or self.quote_suffix
                or self.comment_text
                or self.highlight_color
            ):
                raise ValidationError(
                    {"kind": "Bookmarks cannot carry highlight content."}
                )

    def __str__(self) -> str:
        return f"{self.get_kind_display()} in {self.session.book.title}"
