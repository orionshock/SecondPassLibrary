from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from library.models import (
    Author,
    Book,
    BookAuthor,
    BookCatalogTag,
    BookGroupAssignment,
    BookIdentifier,
    BookSeries,
    CatalogTag,
    LibraryGroup,
    LibraryGroupMembership,
    Series,
)


class LibraryModelShapeTests(TestCase):
    def test_book_owns_file_fields_directly(self):
        field_names = {field.name for field in Book._meta.get_fields()}

        self.assertIn("book_file", field_names)
        self.assertIn("file_format", field_names)
        self.assertIn("checksum", field_names)
        self.assertIn("file_size", field_names)
        self.assertIn("source_filename", field_names)
        self.assertNotIn("file", field_names)

    def test_file_format_initially_supports_epub_only(self):
        self.assertEqual(Book.FILE_FORMAT_CHOICES, [(Book.FILE_FORMAT_EPUB, "EPUB")])

    def test_no_public_bookfile_model_exists(self):
        self.assertNotIn("BookFile", {model.__name__ for model in Book._meta.apps.get_models()})

    def test_book_author_has_no_role_field(self):
        self.assertEqual(
            {"book", "author", "position"},
            {field.name for field in BookAuthor._meta.fields if field.name not in {"id", "created_at", "updated_at"}},
        )

    def test_book_identifier_has_normalized_value(self):
        self.assertIn("normalized_value", {field.name for field in BookIdentifier._meta.fields})


class LibraryModelConstraintTests(TestCase):
    def test_checksum_is_unique_when_present(self):
        Book.objects.create(title="One", checksum="abc123")

        with self.assertRaises(IntegrityError), transaction.atomic():
            Book.objects.create(title="Two", checksum="abc123")

    def test_blank_or_null_checksums_are_allowed_multiple_times(self):
        Book.objects.create(title="One", checksum=None)
        Book.objects.create(title="Two", checksum=None)
        Book.objects.create(title="Three", checksum="")
        Book.objects.create(title="Four", checksum="")

        self.assertEqual(Book.objects.count(), 4)

    def test_book_has_at_most_one_series(self):
        book = Book.objects.create(title="Book")
        first = Series.objects.create(name="First", sort_name="First")
        second = Series.objects.create(name="Second", sort_name="Second")
        BookSeries.objects.create(book=book, series=first)

        with self.assertRaises(IntegrityError), transaction.atomic():
            BookSeries.objects.create(book=book, series=second)

    def test_book_author_position_is_unique_per_book(self):
        book = Book.objects.create(title="Book")
        first = Author.objects.create(name="First", sort_name="First")
        second = Author.objects.create(name="Second", sort_name="Second")
        BookAuthor.objects.create(book=book, author=first, position=0)

        with self.assertRaises(IntegrityError), transaction.atomic():
            BookAuthor.objects.create(book=book, author=second, position=0)

    def test_catalog_tag_normalized_name_is_unique(self):
        CatalogTag.objects.create(name="Science Fiction", normalized_name="science fiction")

        with self.assertRaises(IntegrityError), transaction.atomic():
            CatalogTag.objects.create(name="Sci-Fi", normalized_name="science fiction")

    def test_book_catalog_tag_is_unique_per_book(self):
        book = Book.objects.create(title="Book")
        tag = CatalogTag.objects.create(name="Fantasy", normalized_name="fantasy")
        BookCatalogTag.objects.create(book=book, catalog_tag=tag)

        with self.assertRaises(IntegrityError), transaction.atomic():
            BookCatalogTag.objects.create(book=book, catalog_tag=tag)

    def test_identifier_is_unique_by_scheme_and_normalized_value(self):
        first = Book.objects.create(title="One")
        second = Book.objects.create(title="Two")
        BookIdentifier.objects.create(
            book=first,
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="978-0000000001",
            normalized_value="9780000000001",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            BookIdentifier.objects.create(
                book=second,
                scheme=BookIdentifier.SCHEME_ISBN_13,
                value="9780000000001",
                normalized_value="9780000000001",
            )

    def test_group_membership_is_unique_per_user_and_group(self):
        User = get_user_model()
        user = User.objects.create_user(username="reader")
        group = LibraryGroup.objects.create(name="Common Room")
        LibraryGroupMembership.objects.create(user=user, group=group)

        with self.assertRaises(IntegrityError), transaction.atomic():
            LibraryGroupMembership.objects.create(user=user, group=group)

    def test_book_group_assignment_is_unique_per_book_and_group(self):
        User = get_user_model()
        user = User.objects.create_user(username="librarian")
        book = Book.objects.create(title="Book")
        group = LibraryGroup.objects.create(name="Common Room")
        BookGroupAssignment.objects.create(book=book, group=group, added_by=user)

        with self.assertRaises(IntegrityError), transaction.atomic():
            BookGroupAssignment.objects.create(book=book, group=group, added_by=user)

    def test_published_date_precision_requires_matching_parts(self):
        with self.assertRaises(ValidationError):
            Book(title="Bad", published_date_precision=Book.DATE_PRECISION_MONTH).full_clean()

        Book(
            title="Good",
            published_year=2026,
            published_month=7,
            published_date_precision=Book.DATE_PRECISION_MONTH,
        ).full_clean()
