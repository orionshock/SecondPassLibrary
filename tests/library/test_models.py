from __future__ import annotations

from decimal import Decimal
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
    def test_file_format_initially_supports_epub_only(self):
        self.assertEqual(Book.FILE_FORMAT_CHOICES, [(Book.FILE_FORMAT_EPUB, "EPUB")])


class LibraryModelConstraintTests(TestCase):
    def test_series_index_accepts_only_positive_values_with_at_most_two_decimal_places(self):
        book = Book.objects.create(title="Book")
        series = Series.objects.create(name="Series", sort_name="Series")

        for value in (Decimal("1"), Decimal("1.0"), Decimal("1.25"), Decimal("12.75"), None):
            with self.subTest(value=value):
                BookSeries(book=book, series=series, series_index=value).full_clean()

        for value in (Decimal("0"), Decimal("-1"), Decimal("1.255")):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                BookSeries(book=book, series=series, series_index=value).full_clean()

    def test_series_index_database_constraint_rejects_nonpositive_values(self):
        book = Book.objects.create(title="Book")
        series = Series.objects.create(name="Series", sort_name="Series")

        with self.assertRaises(IntegrityError), transaction.atomic():
            BookSeries.objects.create(book=book, series=series, series_index=Decimal("0"))

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
        CatalogTag.objects.create(name="Science Fiction", normalized_name="science fiction", slug="science-fiction")

        with self.assertRaises(IntegrityError), transaction.atomic():
            CatalogTag.objects.create(name="Sci-Fi", normalized_name="science fiction", slug="sci-fi")

    def test_book_catalog_tag_is_unique_per_book(self):
        book = Book.objects.create(title="Book")
        tag = CatalogTag.objects.create(name="Fantasy", normalized_name="fantasy", slug="fantasy")
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
        membership = LibraryGroupMembership.objects.create(user=user, group=group)

        self.assertIsInstance(membership.pk, int)

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
