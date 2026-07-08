# Generated for LibraryReWrite2607 model baseline.

import django.core.validators
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q

import library.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Author",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("sort_name", models.CharField(blank=True, max_length=255)),
            ],
            options={"ordering": ["sort_name", "name", "id"]},
        ),
        migrations.CreateModel(
            name="CatalogTag",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("sort_name", models.CharField(blank=True, max_length=255)),
                ("normalized_name", models.CharField(max_length=255, unique=True)),
            ],
            options={"ordering": ["sort_name", "name", "id"]},
        ),
        migrations.CreateModel(
            name="LibraryGroup",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
            ],
            options={"ordering": ["name", "id"]},
        ),
        migrations.CreateModel(
            name="Series",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(max_length=255)),
                ("sort_name", models.CharField(blank=True, max_length=255)),
            ],
            options={"verbose_name_plural": "series", "ordering": ["sort_name", "name", "id"]},
        ),
        migrations.CreateModel(
            name="Book",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=512)),
                ("sort_title", models.CharField(blank=True, max_length=512)),
                ("subtitle", models.CharField(blank=True, max_length=512)),
                ("language", models.CharField(blank=True, max_length=64)),
                ("publisher", models.CharField(blank=True, max_length=255)),
                (
                    "published_year",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(9999),
                        ],
                    ),
                ),
                (
                    "published_month",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(12),
                        ],
                    ),
                ),
                (
                    "published_day",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(31),
                        ],
                    ),
                ),
                (
                    "published_date_precision",
                    models.CharField(
                        blank=True,
                        choices=[("year", "Year"), ("month", "Month"), ("day", "Day")],
                        max_length=8,
                    ),
                ),
                ("description", models.TextField(blank=True)),
                ("cover_file", models.FileField(blank=True, upload_to=library.models.book_cover_upload_path)),
                ("book_file", models.FileField(blank=True, upload_to=library.models.book_file_upload_path)),
                ("file_format", models.CharField(choices=[("epub", "EPUB")], default="epub", max_length=16)),
                (
                    "checksum",
                    models.CharField(
                        blank=True,
                        help_text="Content checksum used for duplicate detection.",
                        max_length=128,
                        null=True,
                    ),
                ),
                ("file_size", models.PositiveBigIntegerField(blank=True, null=True)),
                ("source_filename", models.CharField(blank=True, max_length=255)),
            ],
            options={"ordering": ["sort_title", "title", "id"]},
        ),
        migrations.CreateModel(
            name="BookAuthor",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("position", models.PositiveSmallIntegerField(default=0)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="book_authors", to="library.author")),
                ("book", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="book_authors", to="library.book")),
            ],
            options={
                "ordering": ["book", "position", "id"],
                "constraints": [
                    models.UniqueConstraint(fields=("book", "author"), name="unique_book_author"),
                    models.UniqueConstraint(fields=("book", "position"), name="unique_book_author_position"),
                ],
            },
        ),
        migrations.CreateModel(
            name="BookSeries",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("series_index", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
                ("book", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="book_series", to="library.book")),
                ("series", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="book_series", to="library.series")),
            ],
            options={
                "verbose_name_plural": "book series",
                "ordering": ["series__sort_name", "series__name", "series_index", "book__sort_title", "book__title"],
            },
        ),
        migrations.CreateModel(
            name="BookCatalogTag",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("book", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="book_catalog_tags", to="library.book")),
                ("catalog_tag", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="book_catalog_tags", to="library.catalogtag")),
            ],
            options={
                "ordering": ["catalog_tag__sort_name", "catalog_tag__name", "book__sort_title", "book__title"],
                "constraints": [
                    models.UniqueConstraint(fields=("book", "catalog_tag"), name="unique_book_catalog_tag"),
                ],
            },
        ),
        migrations.AddField(
            model_name="book",
            name="authors",
            field=models.ManyToManyField(blank=True, related_name="books", through="library.BookAuthor", to="library.author"),
        ),
        migrations.AddField(
            model_name="book",
            name="catalog_tags",
            field=models.ManyToManyField(blank=True, related_name="books", through="library.BookCatalogTag", to="library.catalogtag"),
        ),
        migrations.CreateModel(
            name="BookIdentifier",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "scheme",
                    models.CharField(
                        choices=[
                            ("isbn_10", "ISBN-10"),
                            ("isbn_13", "ISBN-13"),
                            ("asin", "ASIN"),
                            ("doi", "DOI"),
                            ("oclc", "OCLC"),
                            ("lccn", "LCCN"),
                            ("openlibrary", "Open Library"),
                            ("calibre", "Calibre"),
                            ("epub_uid", "EPUB UID"),
                            ("publisher", "Publisher"),
                            ("uri", "URI/URN"),
                            ("uuid", "UUID"),
                            ("other", "Other"),
                        ],
                        max_length=32,
                    ),
                ),
                ("value", models.CharField(max_length=512)),
                ("normalized_value", models.CharField(max_length=512)),
                ("book", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="identifiers", to="library.book")),
            ],
            options={
                "ordering": ["scheme", "normalized_value", "id"],
                "indexes": [
                    models.Index(fields=["scheme", "normalized_value"], name="idx_identifier_scheme_norm"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("scheme", "normalized_value"), name="unique_identifier_scheme_normalized_value"),
                ],
            },
        ),
        migrations.CreateModel(
            name="BookGroupAssignment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("added_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="book_group_assignments_added", to=settings.AUTH_USER_MODEL)),
                ("book", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="group_assignments", to="library.book")),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="book_assignments", to="library.librarygroup")),
            ],
            options={
                "ordering": ["group__name", "book__sort_title", "book__title", "id"],
                "constraints": [
                    models.UniqueConstraint(fields=("book", "group"), name="unique_book_library_group_assignment"),
                ],
            },
        ),
        migrations.CreateModel(
            name="LibraryGroupMembership",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_curator", models.BooleanField(default=False)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="library.librarygroup")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="library_group_memberships", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["group__name", "user__username", "id"],
                "indexes": [
                    models.Index(fields=["group", "is_curator"], name="idx_group_membership_curator"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("user", "group"), name="unique_user_library_group_membership"),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="book",
            constraint=models.UniqueConstraint(
                fields=("checksum",),
                condition=Q(checksum__isnull=False) & ~Q(checksum=""),
                name="unique_book_checksum_when_present",
            ),
        ),
        migrations.AddConstraint(
            model_name="book",
            constraint=models.CheckConstraint(
                condition=(
                    Q(published_date_precision="")
                    | Q(published_date_precision="year", published_year__isnull=False)
                    | Q(
                        published_date_precision="month",
                        published_month__isnull=False,
                        published_year__isnull=False,
                    )
                    | Q(
                        published_date_precision="day",
                        published_day__isnull=False,
                        published_month__isnull=False,
                        published_year__isnull=False,
                    )
                ),
                name="book_published_precision_has_parts",
            ),
        ),
        migrations.AddConstraint(
            model_name="book",
            constraint=models.CheckConstraint(
                condition=Q(published_month__isnull=True) | Q(published_year__isnull=False),
                name="book_published_month_requires_year",
            ),
        ),
        migrations.AddConstraint(
            model_name="book",
            constraint=models.CheckConstraint(
                condition=Q(published_day__isnull=True)
                | Q(published_month__isnull=False, published_year__isnull=False),
                name="book_published_day_requires_year_month",
            ),
        ),
    ]
