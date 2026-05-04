from typing import TYPE_CHECKING

from django.db import models

from core.models import TimeStampedModel


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
    series_index = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text="Optional position within a series (e.g., 1 for book one).",
    )

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

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="files")
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
