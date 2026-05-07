from __future__ import annotations

from typing import Any, cast

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase

from library.group_services import ensure_book_public_assignment, ensure_user_public_membership
from library.models import Author, Book, BookFile, Series
from library.models import BookGroupAssignment
from library.models import BookIdentifier


class LibraryModelTest(TestCase):
    def setUp(self):
        self.author = Author.objects.create(name="Test Author")
        self.series = Series.objects.create(name="Test Series")
        self.book = Book.objects.create(title="Test Book")
        self.book.authors.add(self.author)
        self.book.series = self.series
        self.book.series_index = 1
        self.book.save()

    def test_author_str(self):
        self.assertEqual(str(self.author), "Test Author")

    def test_series_str(self):
        self.assertEqual(str(self.series), "Test Series")

    def test_book_str(self):
        self.assertEqual(str(self.book), "Test Book")

    def test_book_multiple_authors(self):
        author2 = Author.objects.create(name="Author 2")
        self.book.authors.add(author2)
        self.assertEqual(self.book.authors.count(), 2)

    def test_book_author_list(self):
        author_a = Author.objects.create(name="A Author")
        author_z = Author.objects.create(name="Z Author")
        self.book.authors.set([author_z, author_a])
        self.assertEqual(self.book.author_list(), "A Author, Z Author")

    def test_book_bibliographic_fields(self):
        self.book.publisher = "Test Publisher"
        self.book.language = "en"
        self.book.isbn = "9781234567890"
        cast(Any, self.book).subjects = ["Fiction"]
        self.book.save()

        reloaded = Book.objects.get(pk=self.book.pk)
        self.assertEqual(reloaded.publisher, "Test Publisher")
        self.assertEqual(reloaded.language, "en")
        self.assertEqual(reloaded.isbn, "9781234567890")
        self.assertEqual(reloaded.subjects, ["Fiction"])

    def test_book_file(self):
        # Note: In a real test, you'd use a test file
        book_file = BookFile.objects.create(
            book=self.book,
            file="test.epub",
            checksum="dummy",
            file_size=123,
            source_filename="original.epub",
        )
        self.assertEqual(str(book_file), "Test Book - dummy...")
        self.assertEqual(book_file.checksum_short(), "dummy")
        self.assertEqual(book_file.file_size_human(), "123 B")

    def test_book_file_str_with_missing_checksum(self):
        book_file = BookFile.objects.create(
            book=self.book,
            file="test.epub",
            checksum=None,
            file_size=123,
            source_filename="original.epub",
        )
        self.assertEqual(str(book_file), "Test Book - no-checksum...")

    def test_book_file_file_size_human_units(self):
        book_file = BookFile.objects.create(
            book=self.book,
            file="test.epub",
            checksum="a" * 64,
            file_size=2048,
            source_filename="original.epub",
        )
        self.assertEqual(book_file.file_size_human(), "2.0 KB")

    def test_book_identifier_unique_constraint(self):
        ident = BookIdentifier.objects.create(
            book=self.book,
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="9780123456472",
        )
        self.assertEqual(str(ident), "isbn_13:9780123456472")
        with self.assertRaises(IntegrityError):
            BookIdentifier.objects.create(
                book=self.book,
                scheme=BookIdentifier.SCHEME_ISBN_13,
                value="9780123456472",
            )


class BookGroupInvariantTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pw")
        ensure_user_public_membership(user=self.user)
        from library.group_services import get_public_group
        from library.models import LibraryGroup

        self.public = get_public_group()
        self.group_a = LibraryGroup.objects.create(name="A", slug="a")
        self.group_b = LibraryGroup.objects.create(name="B", slug="b")
        self.book = Book.objects.create(title="B")

        self.a1 = BookGroupAssignment.objects.create(
            book=self.book, group=self.group_a, added_by=self.user
        )
        self.b1 = BookGroupAssignment.objects.create(
            book=self.book, group=self.group_b, added_by=self.user
        )

    def test_deleting_one_of_multiple_assignments_does_not_force_public(self):
        self.a1.delete()
        groups = set(
            BookGroupAssignment.objects.filter(book=self.book).values_list(
                "group__slug", flat=True
            )
        )
        self.assertEqual(groups, {"b"})

    def test_deleting_last_assignment_reassigns_public(self):
        self.a1.delete()
        self.b1.delete()
        groups = set(
            BookGroupAssignment.objects.filter(book=self.book).values_list(
                "group__slug", flat=True
            )
        )
        self.assertEqual(groups, {"public"})
