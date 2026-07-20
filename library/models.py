from __future__ import annotations

from pathlib import Path
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel
from library.catalog.names import normalize_catalog_entity_name


_COVER_FILENAME_RE = re.compile(r"^(?P<sha>[0-9a-f]{64})(?P<ext>\.[A-Za-z0-9]+)?$")

BOOK_DATE_PRECISION_YEAR = "year"
BOOK_DATE_PRECISION_MONTH = "month"
BOOK_DATE_PRECISION_DAY = "day"
BOOK_DATE_PRECISION_CHOICES = [
    (BOOK_DATE_PRECISION_YEAR, "Year"),
    (BOOK_DATE_PRECISION_MONTH, "Month"),
    (BOOK_DATE_PRECISION_DAY, "Day"),
]


def book_cover_upload_path(instance: "Book", filename: str) -> str:
    base = Path(filename).name
    match = _COVER_FILENAME_RE.match(base)
    if not match:
        raise ValueError("Cover filename must be '<sha256>.<ext>' (sha256 hex).")
    sha = match.group("sha")
    ext = (match.group("ext") or "").lower()
    return f"covers/{sha[:2]}/{sha[2:4]}/{sha}{ext}"


def book_file_upload_path(instance: "Book", filename: str) -> str:
    if not instance.checksum:
        raise ValueError("Checksum must be set before saving book_file.")
    ext = Path(filename).suffix.lower() or f".{instance.file_format}"
    checksum = instance.checksum
    return f"books/{checksum[:2]}/{checksum[2:4]}/{checksum}{ext}"


class Author(TimeStampedModel):
    name = models.CharField(max_length=255)
    sort_name = models.CharField(max_length=255, blank=True)
    normalized_name = models.CharField(max_length=255, blank=True, db_index=True)
    biography = models.TextField(blank=True)

    class Meta:
        ordering = ["sort_name", "name", "id"]

    def clean(self) -> None:
        super().clean()
        self.normalized_name = normalize_catalog_entity_name(self.name)

    def __str__(self) -> str:
        return self.name


class Series(TimeStampedModel):
    name = models.CharField(max_length=255)
    sort_name = models.CharField(max_length=255, blank=True)
    normalized_name = models.CharField(max_length=255, blank=True, db_index=True)
    summary = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "series"
        ordering = ["sort_name", "name", "id"]

    def clean(self) -> None:
        super().clean()
        self.normalized_name = normalize_catalog_entity_name(self.name)

    def __str__(self) -> str:
        return self.name


class CatalogTag(TimeStampedModel):
    name = models.CharField(max_length=255)
    sort_name = models.CharField(max_length=255, blank=True)
    normalized_name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=280, unique=True, editable=False, allow_unicode=True)

    class Meta:
        ordering = ["sort_name", "name", "id"]

    def __str__(self) -> str:
        return self.name


class Book(TimeStampedModel):
    FILE_FORMAT_EPUB = "epub"
    FILE_FORMAT_CHOICES = [
        (FILE_FORMAT_EPUB, "EPUB"),
    ]

    DATE_PRECISION_YEAR = BOOK_DATE_PRECISION_YEAR
    DATE_PRECISION_MONTH = BOOK_DATE_PRECISION_MONTH
    DATE_PRECISION_DAY = BOOK_DATE_PRECISION_DAY
    DATE_PRECISION_CHOICES = BOOK_DATE_PRECISION_CHOICES

    title = models.CharField(max_length=512)
    sort_title = models.CharField(max_length=512, blank=True)
    subtitle = models.CharField(max_length=512, blank=True)
    language = models.CharField(max_length=64, blank=True)
    publisher = models.CharField(max_length=255, blank=True)
    published_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(9999)],
    )
    published_month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    published_day = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
    )
    published_date_precision = models.CharField(
        max_length=8,
        choices=DATE_PRECISION_CHOICES,
        blank=True,
    )
    description = models.TextField(blank=True)
    cover_file = models.FileField(blank=True, upload_to=book_cover_upload_path)
    book_file = models.FileField(blank=True, upload_to=book_file_upload_path)
    file_format = models.CharField(
        max_length=16,
        choices=FILE_FORMAT_CHOICES,
        default=FILE_FORMAT_EPUB,
    )
    checksum = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text="Content checksum used for duplicate detection.",
    )
    file_size = models.PositiveBigIntegerField(blank=True, null=True)

    authors = models.ManyToManyField(
        Author,
        through="BookAuthor",
        related_name="books",
        blank=True,
    )
    catalog_tags = models.ManyToManyField(
        CatalogTag,
        through="BookCatalogTag",
        related_name="books",
        blank=True,
    )

    class Meta:
        ordering = ["sort_title", "title", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["checksum"],
                condition=Q(checksum__isnull=False) & ~Q(checksum=""),
                name="unique_book_checksum_when_present",
            ),
            models.CheckConstraint(
                condition=(
                    Q(published_date_precision="")
                    | Q(published_date_precision=BOOK_DATE_PRECISION_YEAR, published_year__isnull=False)
                    | Q(
                        published_date_precision=BOOK_DATE_PRECISION_MONTH,
                        published_year__isnull=False,
                        published_month__isnull=False,
                    )
                    | Q(
                        published_date_precision=BOOK_DATE_PRECISION_DAY,
                        published_year__isnull=False,
                        published_month__isnull=False,
                        published_day__isnull=False,
                    )
                ),
                name="book_published_precision_has_parts",
            ),
            models.CheckConstraint(
                condition=Q(published_month__isnull=True) | Q(published_year__isnull=False),
                name="book_published_month_requires_year",
            ),
            models.CheckConstraint(
                condition=(
                    Q(published_day__isnull=True)
                    | Q(published_year__isnull=False, published_month__isnull=False)
                ),
                name="book_published_day_requires_year_month",
            ),
        ]

    def clean(self) -> None:
        super().clean()
        if self.published_date_precision == self.DATE_PRECISION_YEAR and self.published_year is None:
            raise ValidationError({"published_year": "Year precision requires published_year."})
        if self.published_date_precision == self.DATE_PRECISION_MONTH:
            if self.published_year is None or self.published_month is None:
                raise ValidationError(
                    {"published_month": "Month precision requires published_year and published_month."}
                )
        if self.published_date_precision == self.DATE_PRECISION_DAY:
            if (
                self.published_year is None
                or self.published_month is None
                or self.published_day is None
            ):
                raise ValidationError(
                    {
                        "published_day": (
                            "Day precision requires published_year, published_month, "
                            "and published_day."
                        )
                    }
                )

    def __str__(self) -> str:
        return self.title


class BookAuthor(TimeStampedModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="book_authors")
    author = models.ForeignKey(Author, on_delete=models.PROTECT, related_name="book_authors")
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["book", "position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["book", "author"], name="unique_book_author"),
            models.UniqueConstraint(fields=["book", "position"], name="unique_book_author_position"),
        ]

    def __str__(self) -> str:
        return f"{self.book} - {self.author}"


class BookSeries(TimeStampedModel):
    book = models.OneToOneField(Book, on_delete=models.CASCADE, related_name="book_series")
    series = models.ForeignKey(Series, on_delete=models.PROTECT, related_name="book_series")
    series_index = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name_plural = "book series"
        ordering = ["series__sort_name", "series__name", "series_index", "book__sort_title", "book__title"]

    def __str__(self) -> str:
        return f"{self.book} - {self.series}"


class BookCatalogTag(TimeStampedModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="book_catalog_tags")
    catalog_tag = models.ForeignKey(
        CatalogTag,
        on_delete=models.CASCADE,
        related_name="book_catalog_tags",
    )

    class Meta:
        ordering = ["catalog_tag__sort_name", "catalog_tag__name", "book__sort_title", "book__title"]
        constraints = [
            models.UniqueConstraint(
                fields=["book", "catalog_tag"],
                name="unique_book_catalog_tag",
            )
        ]

    def __str__(self) -> str:
        return f"{self.book} - {self.catalog_tag}"


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

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="identifiers")
    scheme = models.CharField(max_length=32, choices=SCHEME_CHOICES)
    value = models.CharField(max_length=512)
    normalized_value = models.CharField(max_length=512)

    class Meta:
        ordering = ["scheme", "normalized_value", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["scheme", "normalized_value"],
                name="unique_identifier_scheme_normalized_value",
            )
        ]
        indexes = [
            models.Index(fields=["scheme", "normalized_value"], name="idx_identifier_scheme_norm"),
        ]

    def __str__(self) -> str:
        return f"{self.scheme}:{self.value}"


class LibraryGroup(TimeStampedModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return self.name


class LibraryGroupMembership(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="library_group_memberships",
    )
    group = models.ForeignKey(
        LibraryGroup,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    is_curator = models.BooleanField(default=False)

    class Meta:
        ordering = ["group__name", "user__username", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "group"],
                name="unique_user_library_group_membership",
            )
        ]
        indexes = [
            models.Index(fields=["group", "is_curator"], name="idx_group_membership_curator"),
        ]

    def __str__(self) -> str:
        suffix = ", curator" if self.is_curator else ""
        return f"{self.user.get_username()} in {self.group.name}{suffix}"


class BookGroupAssignment(TimeStampedModel):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="group_assignments")
    group = models.ForeignKey(
        LibraryGroup,
        on_delete=models.CASCADE,
        related_name="book_assignments",
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="book_group_assignments_added",
    )

    class Meta:
        ordering = ["group__name", "book__sort_title", "book__title", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["book", "group"],
                name="unique_book_library_group_assignment",
            )
        ]

    def __str__(self) -> str:
        return f"{self.book} -> {self.group}"
