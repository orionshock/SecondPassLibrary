from typing import TYPE_CHECKING
import re
from pathlib import Path

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from core.server_settings import get_server_setting

from core.models import TimeStampedModel


PUBLIC_GROUP_ID_SETTING = "public_group_id"


_COVER_FILENAME_RE = re.compile(r"^(?P<sha>[0-9a-f]{64})(?P<ext>\.[A-Za-z0-9]+)?$")


def book_cover_upload_path(instance, filename):
    base = Path(filename).name
    m = _COVER_FILENAME_RE.match(base)
    if not m:
        raise ValueError("Cover filename must be '<sha256>.<ext>' (sha256 hex).")
    sha = m.group("sha")
    ext = (m.group("ext") or "").lower()
    return f"covers/{sha[:2]}/{sha[2:4]}/{sha}{ext}"


class Author(TimeStampedModel):
    name = models.CharField(max_length=255)
    biography = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Series(TimeStampedModel):
    name = models.CharField(max_length=255)
    summary = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "series"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Book(TimeStampedModel):
    if TYPE_CHECKING:
        file: "BookFile"

    title = models.CharField(max_length=512)
    subtitle = models.CharField(max_length=512, blank=True)
    summary = models.TextField(blank=True)
    publisher = models.CharField(max_length=255, blank=True)
    language = models.CharField(max_length=64, blank=True)
    published_date = models.DateField(null=True, blank=True)
    isbn = models.CharField(max_length=64, blank=True)
    subjects = models.JSONField(  # pyright: ignore[reportAssignmentType]
        blank=True,
        null=True,
        default=list,
    )
    authors = models.ManyToManyField(Author, related_name="books", blank=True)
    series = models.ForeignKey(
        Series,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="books",
    )
    series_index = models.DecimalField(
        blank=True,
        null=True,
        max_digits=6,
        decimal_places=1,
        validators=[MinValueValidator(0)],
        help_text="Optional position within a series (e.g., 1, 5.1). One decimal place max.",
    )

    cover_file = models.FileField(blank=True, upload_to=book_cover_upload_path)
    cover_source = models.CharField(max_length=32, blank=True)
    cover_mime = models.CharField(max_length=64, blank=True)
    cover_width = models.PositiveIntegerField(null=True, blank=True)
    cover_height = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def author_list(self):
        authors = self.authors.order_by("name").values_list("name", flat=True)
        return ", ".join(authors)


def book_file_upload_path(instance, filename):
    if not instance.checksum:
        raise ValueError("Checksum must be set before saving BookFile")
    first2 = instance.checksum[:2]
    next2 = instance.checksum[2:4]
    return f"books/{first2}/{next2}/{instance.checksum}.epub"


class BookFile(TimeStampedModel):
    FORMAT_EPUB = "epub"
    FORMAT_CHOICES = [
        (FORMAT_EPUB, "EPUB"),
    ]

    book = models.OneToOneField(Book, on_delete=models.CASCADE, related_name="file")
    file = models.FileField(upload_to=book_file_upload_path)
    format = models.CharField(
        max_length=32, choices=FORMAT_CHOICES, default=FORMAT_EPUB
    )
    checksum = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text="SHA-256 hash for duplicate detection",
    )
    file_size = models.PositiveBigIntegerField(
        blank=True, null=True, help_text="File size in bytes"
    )
    source_filename = models.CharField(
        max_length=255,
        blank=True,
        help_text="Original filename for diagnostic purposes",
    )

    class Meta:
        ordering = ["book", "created_at"]

    def __str__(self):
        checksum_display = self.checksum_short(8) or "no-checksum"
        return f"{self.book.title} - {checksum_display}..."

    def checksum_short(self, length=8):
        if not self.checksum:
            return ""
        return self.checksum[:length]

    def file_size_human(self):
        if self.file_size is None:
            return ""

        size = float(self.file_size)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024 or unit == "TB":
                if unit == "B":
                    return f"{int(size)} {unit}"
                return f"{size:.1f} {unit}"
            size /= 1024


class BookIdentifier(TimeStampedModel):
    SCHEME_ISBN_10 = "isbn_10"
    SCHEME_ISBN_13 = "isbn_13"
    SCHEME_ASIN = "asin"
    SCHEME_DOI = "doi"
    SCHEME_OCLC = "oclc"
    SCHEME_LCCN = "lccn"
    SCHEME_OPENLIBRARY = "openlibrary"
    SCHEME_CALIBRE = "calibre"
    SCHEME_EPUB_UID = "epub_uid"
    SCHEME_PUBLISHER = "publisher"
    SCHEME_URI = "uri"
    SCHEME_UUID = "uuid"
    SCHEME_OTHER = "other"

    SCHEME_CHOICES = [
        (SCHEME_ISBN_10, "ISBN-10"),
        (SCHEME_ISBN_13, "ISBN-13"),
        (SCHEME_ASIN, "ASIN"),
        (SCHEME_DOI, "DOI"),
        (SCHEME_OCLC, "OCLC"),
        (SCHEME_LCCN, "LCCN"),
        (SCHEME_OPENLIBRARY, "Open Library"),
        (SCHEME_CALIBRE, "Calibre"),
        (SCHEME_EPUB_UID, "EPUB UID"),
        (SCHEME_PUBLISHER, "Publisher"),
        (SCHEME_URI, "URI/URN"),
        (SCHEME_UUID, "UUID"),
        (SCHEME_OTHER, "Other"),
    ]

    book = models.ForeignKey(
        Book, on_delete=models.CASCADE, related_name="identifiers"
    )
    scheme = models.CharField(max_length=32, choices=SCHEME_CHOICES)
    value = models.CharField(max_length=512)
    source = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["scheme", "value"]
        constraints = [
            models.UniqueConstraint(
                fields=["book", "scheme", "value"],
                name="unique_book_identifier_scheme_value",
            )
        ]
        indexes = [
            models.Index(fields=["scheme", "value"], name="idx_identifier_scheme_value"),
        ]

    def __str__(self):
        return f"{self.scheme}:{self.value}"


class LibraryGroup(TimeStampedModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

def is_public_group(group: LibraryGroup | None) -> bool:
    if group is None:
        return False

    # Prefer a repair-safe public group id read. This avoids silently treating Public
    # as non-Public if the ServerSetting is missing/malformed.
    try:
        from .group_services import get_public_group, get_public_group_id

        public_id = get_public_group_id()
        if public_id is None:
            # Trigger repair and retry once.
            get_public_group()
            public_id = get_public_group_id()
    except Exception:
        public_id = get_server_setting(PUBLIC_GROUP_ID_SETTING, default=None)

    if public_id is None or public_id == "":
        return False
    return str(getattr(group, "id", "")) == str(public_id)


class LibraryGroupMembership(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="library_group_memberships"
    )
    group = models.ForeignKey(
        LibraryGroup, on_delete=models.CASCADE, related_name="memberships"
    )
    is_curator = models.BooleanField(default=False)

    class Meta:
        ordering = ["group__name", "user__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "group"],
                name="unique_user_library_group_membership",
            )
        ]
        indexes = [
            models.Index(fields=["group", "is_curator"], name="idx_group_membership_curator"),
        ]

    def clean(self):
        group_id = getattr(self, "group_id", None)
        if group_id and self.is_curator:
            group = self.group
            if is_public_group(group):
                raise ValidationError({"is_curator": "Public group cannot have curators."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        suffix = ", curator" if self.is_curator else ""
        return f"{self.user.get_username()} in {self.group.name}{suffix}"


class BookGroupAssignment(TimeStampedModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="group_assignments")
    group = models.ForeignKey(LibraryGroup, on_delete=models.CASCADE, related_name="book_assignments")
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="book_group_assignments_added",
    )

    class Meta:
        ordering = ["group__name", "book__title"]
        constraints = [
            models.UniqueConstraint(
                fields=["book", "group"],
                name="unique_book_library_group_assignment",
            )
        ]

    def __str__(self):
        return f"{self.book.title} -> {self.group.name}"


class ImportJob(TimeStampedModel):
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    SOURCE_EPUB = "epub"
    SOURCE_ZIP = "zip"

    SOURCE_TYPE_CHOICES = [
        (SOURCE_EPUB, "EPUB"),
        (SOURCE_ZIP, "ZIP"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="import_jobs",
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    source_type = models.CharField(max_length=8, choices=SOURCE_TYPE_CHOICES)
    source_filename = models.CharField(
        max_length=255,
        blank=True,
        help_text="Original uploaded filename (diagnostic only).",
    )
    staged_path = models.CharField(
        max_length=512,
        blank=True,
        help_text="Internal staging path relative to userdata/imports (diagnostic).",
    )
    total_found = models.PositiveIntegerField(default=0)
    imported_count = models.PositiveIntegerField(default=0)
    duplicate_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"ImportJob {self.id} ({self.user.get_username()})"


class ImportJobItem(TimeStampedModel):
    STATUS_IMPORTED = "imported"
    STATUS_DUPLICATE = "duplicate"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_IMPORTED, "Imported"),
        (STATUS_DUPLICATE, "Duplicate"),
        (STATUS_FAILED, "Failed"),
    ]

    job = models.ForeignKey(
        ImportJob, on_delete=models.CASCADE, related_name="items"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    source_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Original filename within ZIP or upload (diagnostic only).",
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_job_items",
    )
    book_file = models.ForeignKey(
        BookFile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_job_items",
    )
    message = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"ImportJobItem {self.id} ({self.status})"
