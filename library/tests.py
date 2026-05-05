from collections.abc import Mapping
import shutil
from typing import Any, cast

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.response import Response
import os
from unittest.mock import patch, MagicMock
from pathlib import Path
import uuid

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import UserProfile
from .models import Author, Book, BookFile, Series
from .models import BookIdentifier
from .services import ImportStatus, import_epub
from .group_services import ensure_book_public_assignment, ensure_user_public_membership


class IsolatedMediaRootMixin:
    """
    Ensure FileField writes during tests go to a temp MEDIA_ROOT.

    Avoid polluting the real `userdata/media` directory during test runs.
    """

    @classmethod
    def setUpClass(cls):
        parent_set_up = getattr(super(), "setUpClass", None)
        if callable(parent_set_up):
            parent_set_up()
        temp_root = Path(settings.BASE_DIR) / "TestFiles"
        temp_root.mkdir(parents=True, exist_ok=True)
        cls._media_root = str(temp_root / f"tmp_media_{uuid.uuid4().hex}")
        os.makedirs(cls._media_root, exist_ok=True)
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)
        parent_tear_down = getattr(super(), "tearDownClass", None)
        if callable(parent_tear_down):
            parent_tear_down()


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

        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            BookIdentifier.objects.create(
                book=self.book,
                scheme=BookIdentifier.SCHEME_ISBN_13,
                value="9780123456472",
            )


class LibraryAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")

    def test_authenticated_access_books(self):
        response = self.client.get("/api/v1/library/books/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_authenticated_access_authors(self):
        response = self.client.get("/api/v1/library/authors/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BookListErgonomicsAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        ensure_user_public_membership(user=self.user)
        self.client.login(username="testuser", password="testpass")

        self.author = Author.objects.create(name="A Author")
        self.series = Series.objects.create(name="S Series")
        self.book = Book.objects.create(title="T", series=self.series, series_index=1)
        self.book.authors.add(self.author)
        ensure_book_public_assignment(book=self.book, added_by=None)
        BookIdentifier.objects.create(
            book=self.book,
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="9780123456472",
            source="epub",
            is_primary=True,
        )
        uploaded = SimpleUploadedFile(
            "ignored.epub",
            b"epub-bytes",
            content_type="application/epub+zip",
        )
        BookFile.objects.create(
            book=self.book,
            file=uploaded,
            checksum="a" * 64,
            file_size=9,
            source_filename="SOURCE_NAME.epub",
        )

    def test_book_list_includes_nested_summaries_and_no_raw_file_paths(self):
        response = cast(Response, self.client.get("/api/v1/library/books/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = cast(list[dict[str, Any]], response.data)
        self.assertEqual(len(data), 1)
        book = data[0]

        self.assertIsInstance(book["authors"], list)
        self.assertEqual(book["authors"][0]["id"], str(self.author.id))
        self.assertEqual(book["authors"][0]["name"], "A Author")

        self.assertIsInstance(book["series"], dict)
        self.assertEqual(book["series"]["id"], str(self.series.id))
        self.assertEqual(book["series"]["name"], "S Series")

        self.assertIsInstance(book["identifiers"], list)
        self.assertEqual(book["identifiers"][0]["scheme"], "isbn_13")
        self.assertEqual(book["identifiers"][0]["source"], "epub")

        self.assertIsInstance(book["files"], list)
        file0 = book["files"][0]
        self.assertIn("download_url", file0)
        self.assertNotIn("file", file0)
        self.assertNotIn("books/", str(file0))


class BookBrowseFiltersAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        ensure_user_public_membership(user=self.user)
        self.client.login(username="testuser", password="testpass")

        self.author_a = Author.objects.create(name="Alice Author")
        self.author_b = Author.objects.create(name="Bob Writer")
        self.series_s = Series.objects.create(name="Saga Series")

        self.book1 = Book.objects.create(title="Alpha", language="en", series=self.series_s)
        self.book1.authors.add(self.author_a)
        ensure_book_public_assignment(book=self.book1, added_by=None)
        BookIdentifier.objects.create(book=self.book1, scheme="other", value="ID-XYZ", source="epub")

        self.book2 = Book.objects.create(title="Beta", language="fr")
        self.book2.authors.add(self.author_b)
        ensure_book_public_assignment(book=self.book2, added_by=None)

        uploaded = SimpleUploadedFile("ignored.epub", b"epub-bytes", content_type="application/epub+zip")
        BookFile.objects.create(
            book=self.book2,
            file=uploaded,
            checksum="b" * 64,
            file_size=9,
            source_filename="b.epub",
        )

    def _titles(self, response):
        data = cast(list[dict[str, Any]], response.data)
        return sorted([b["title"] for b in data])

    def test_q_matches_title(self):
        response = cast(Response, self.client.get("/api/v1/library/books/?q=Alp"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Alpha"])

    def test_q_matches_author(self):
        response = cast(Response, self.client.get("/api/v1/library/books/?q=bob"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Beta"])

    def test_q_matches_identifier_value(self):
        response = cast(Response, self.client.get("/api/v1/library/books/?q=xyz"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Alpha"])

    def test_filter_by_author(self):
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/books/?author={self.author_a.id}"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Alpha"])

    def test_filter_by_series(self):
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/books/?series={self.series_s.id}"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Alpha"])

    def test_filter_by_language(self):
        response = cast(Response, self.client.get("/api/v1/library/books/?language=en"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Alpha"])

    def test_filter_has_files_true(self):
        response = cast(Response, self.client.get("/api/v1/library/books/?has_files=true"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Beta"])
        data = cast(list[dict[str, Any]], response.data)
        files = data[0]["files"]
        self.assertEqual(len(files), 1)
        self.assertIn("download_url", files[0])
        self.assertNotIn("file", files[0])
        self.assertNotIn("books/", str(files[0]))


class LibraryPermissionsAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.reader)
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        ensure_user_public_membership(user=self.librarian)
        profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

    def test_reader_cannot_create_book(self):
        self.client.login(username="reader", password="pw")
        response = cast(
            Response,
            self.client.post(
                "/api/v1/library/books/",
                data={"title": "X", "authors": [], "subjects": []},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_librarian_can_create_book(self):
        self.client.login(username="librarian", password="pw")
        response = cast(
            Response,
            self.client.post(
                "/api/v1/library/books/",
                data={"title": "X", "authors": [], "subjects": []},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class LibraryVisibilityAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.reader)
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        ensure_user_public_membership(user=self.librarian)
        librarian_profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        librarian_profile.role = UserProfile.ROLE_LIBRARIAN
        librarian_profile.save(update_fields=["role", "updated_at"])

        self.manager = User.objects.create_user(username="manager", password="pw")
        ensure_user_public_membership(user=self.manager)
        manager_profile, _ = UserProfile.objects.get_or_create(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.owner = User.objects.create_superuser(username="owner", password="pw")
        ensure_user_public_membership(user=self.owner)

        from .models import LibraryGroup, LibraryGroupMembership, BookGroupAssignment
        from .group_services import get_public_group

        self.public = get_public_group()
        self.group_a = LibraryGroup.objects.create(name="Group A", slug="group-a")
        self.group_b = LibraryGroup.objects.create(name="Group B", slug="group-b")

        LibraryGroupMembership.objects.create(
            user=self.reader, group=self.group_a, role=LibraryGroupMembership.ROLE_READER
        )

        self.public_book = Book.objects.create(title="Public Book")
        ensure_book_public_assignment(book=self.public_book, added_by=None)

        self.group_a_book = Book.objects.create(title="Group A Book")
        BookGroupAssignment.objects.create(book=self.group_a_book, group=self.group_a)

        self.group_b_book = Book.objects.create(title="Group B Book")
        BookGroupAssignment.objects.create(book=self.group_b_book, group=self.group_b)

        uploaded = SimpleUploadedFile("b.epub", b"epub-bytes", content_type="application/epub+zip")
        self.group_b_file = BookFile.objects.create(
            book=self.group_b_book,
            file=uploaded,
            checksum="c" * 64,
            file_size=9,
            source_filename="c.epub",
        )

    def test_reader_can_list_public_books(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get("/api/v1/library/books/?q=Public"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [b["title"] for b in cast(list[dict[str, Any]], response.data)]
        self.assertIn("Public Book", titles)

    def test_reader_can_list_books_in_group_they_belong_to(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get("/api/v1/library/books/?q=Group A"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [b["title"] for b in cast(list[dict[str, Any]], response.data)]
        self.assertIn("Group A Book", titles)

    def test_reader_cannot_list_books_in_group_they_do_not_belong_to(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get("/api/v1/library/books/?q=Group B"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [b["title"] for b in cast(list[dict[str, Any]], response.data)]
        self.assertNotIn("Group B Book", titles)

    def test_reader_cannot_retrieve_inaccessible_book(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get(f"/api/v1/library/books/{self.group_b_book.id}/"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reader_cannot_download_inaccessible_book_file(self):
        self.client.login(username="reader", password="pw")
        response = self.client.get(f"/api/v1/library/book-files/{self.group_b_file.id}/download/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_librarian_manager_owner_can_see_all_books(self):
        for username in ["librarian", "manager", "owner"]:
            self.client.logout()
            self.client.login(username=username, password="pw")
            response = cast(Response, self.client.get("/api/v1/library/books/"))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            titles = sorted([b["title"] for b in cast(list[dict[str, Any]], response.data)])
            self.assertEqual(titles, ["Group A Book", "Group B Book", "Public Book"])


class AuthorSeriesVisibilityAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.reader)
        self.client.login(username="reader", password="pw")

        from .models import LibraryGroup, LibraryGroupMembership, BookGroupAssignment

        self.group_x = LibraryGroup.objects.create(name="X", slug="x")
        LibraryGroupMembership.objects.create(
            user=self.reader, group=self.group_x, role=LibraryGroupMembership.ROLE_READER
        )
        self.group_y = LibraryGroup.objects.create(name="Y", slug="y")

        self.author_public = Author.objects.create(name="Public Author")
        self.series_public = Series.objects.create(name="Public Series")
        self.book_public = Book.objects.create(title="PB", series=self.series_public)
        self.book_public.authors.add(self.author_public)
        ensure_book_public_assignment(book=self.book_public, added_by=None)

        self.author_x = Author.objects.create(name="X Author")
        self.series_x = Series.objects.create(name="X Series")
        self.book_x = Book.objects.create(title="XB", series=self.series_x)
        self.book_x.authors.add(self.author_x)
        BookGroupAssignment.objects.create(book=self.book_x, group=self.group_x)

        self.author_hidden = Author.objects.create(name="Hidden Author")
        self.series_hidden = Series.objects.create(name="Hidden Series")
        self.book_hidden = Book.objects.create(title="HB", series=self.series_hidden)
        self.book_hidden.authors.add(self.author_hidden)
        BookGroupAssignment.objects.create(book=self.book_hidden, group=self.group_y)

    def test_reader_author_list_filtered(self):
        response = cast(Response, self.client.get("/api/v1/library/authors/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = sorted([a["name"] for a in cast(list[dict[str, Any]], response.data)])
        self.assertEqual(names, ["Public Author", "X Author"])

    def test_reader_author_retrieve_404_for_inaccessible_only(self):
        response = self.client.get(f"/api/v1/library/authors/{self.author_hidden.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reader_series_list_filtered(self):
        response = cast(Response, self.client.get("/api/v1/library/series/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = sorted([s["name"] for s in cast(list[dict[str, Any]], response.data)])
        self.assertEqual(names, ["Public Series", "X Series"])

    def test_reader_series_retrieve_404_for_inaccessible_only(self):
        response = self.client.get(f"/api/v1/library/series/{self.series_hidden.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class BookGroupInvariantTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pw")
        ensure_user_public_membership(user=self.user)
        from .models import LibraryGroup, BookGroupAssignment
        from .group_services import get_public_group

        self.public = get_public_group()
        self.group_a = LibraryGroup.objects.create(name="A", slug="a")
        self.group_b = LibraryGroup.objects.create(name="B", slug="b")
        self.book = Book.objects.create(title="B")

        self.a1 = BookGroupAssignment.objects.create(book=self.book, group=self.group_a, added_by=self.user)
        self.b1 = BookGroupAssignment.objects.create(book=self.book, group=self.group_b, added_by=self.user)

    def test_deleting_one_of_multiple_assignments_does_not_force_public(self):
        from .models import BookGroupAssignment

        self.a1.delete()
        groups = set(BookGroupAssignment.objects.filter(book=self.book).values_list("group__slug", flat=True))
        self.assertEqual(groups, {"b"})

    def test_deleting_last_assignment_reassigns_public(self):
        from .models import BookGroupAssignment

        self.a1.delete()
        self.b1.delete()
        groups = set(BookGroupAssignment.objects.filter(book=self.book).values_list("group__slug", flat=True))
        self.assertEqual(groups, {"public"})


class BaseBookFileDownloadAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        ensure_user_public_membership(user=self.user)
        self.author = Author.objects.create(name="Jane / Doe")
        self.series = Series.objects.create(name="My * Series")
        self.book = Book.objects.create(
            title="The: Title",
            series=self.series,
            series_index=2,
        )
        self.book.authors.add(self.author)
        ensure_book_public_assignment(book=self.book, added_by=None)

        uploaded = SimpleUploadedFile(
            "ignored.epub",
            b"epub-bytes",
            content_type="application/epub+zip",
        )
        self.book_file = BookFile.objects.create(
            book=self.book,
            file=uploaded,
            checksum="a" * 64,
            file_size=9,
            source_filename="SOURCE_NAME.epub",
        )

    def test_anonymous_user_cannot_download(self):
        response = self.client.get(
            f"/api/v1/library/book-files/{self.book_file.id}/download/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_user_can_download_with_metadata_filename(self):
        self.client.login(username="testuser", password="testpass")
        response = self.client.get(
            f"/api/v1/library/book-files/{self.book_file.id}/download/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        content_disposition = response.get("Content-Disposition", "")
        self.assertTrue(content_disposition.startswith("attachment;"))
        self.assertIn("Jane _ Doe", content_disposition)
        self.assertIn("My _ Series 2", content_disposition)
        self.assertIn("The_ Title", content_disposition)
        self.assertNotIn("SOURCE_NAME", content_disposition)
        self.assertNotIn(self.book_file.checksum, content_disposition)

    def test_missing_stored_file_returns_404(self):
        self.client.login(username="testuser", password="testpass")
        storage = self.book_file.file.storage
        storage.delete(self.book_file.file.name)

        response = self.client.get(
            f"/api/v1/library/book-files/{self.book_file.id}/download/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class BookFileSerializerAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        ensure_user_public_membership(user=self.user)
        self.author = Author.objects.create(name="Test Author")
        self.book = Book.objects.create(title="Test Title")
        self.book.authors.add(self.author)
        ensure_book_public_assignment(book=self.book, added_by=None)
        self.book_file = BookFile.objects.create(
            book=self.book,
            file="books/aa/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.epub",
            checksum="a" * 64,
            file_size=123,
            source_filename="source.epub",
        )

    def test_book_file_api_output_hides_file_and_includes_download_url(self):
        self.client.login(username="testuser", password="testpass")
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/book-files/{self.book_file.id}/"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        data = cast(Mapping[str, Any], response.data)
        self.assertNotIn("file", data)
        self.assertIn("download_url", data)
        self.assertEqual(
            data["download_url"],
            f"http://testserver/api/v1/library/book-files/{self.book_file.id}/download/",
        )


class BookFileDownloadAPITest(IsolatedMediaRootMixin, BaseBookFileDownloadAPITest):
    pass


class EPUBImportTest(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        # Create a temporary EPUB file for testing
        temp_root = Path(settings.BASE_DIR) / "TestFiles"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = str(temp_root / f"tmp_epub_{uuid.uuid4().hex}")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.epub_path = os.path.join(self.temp_dir, "test.epub")
        with open(self.epub_path, "wb") as f:
            f.write(uuid.uuid4().hex.encode("utf-8"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("library.services.epub.read_epub")
    def test_checksum_calculation(self, mock_read_epub):
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = []
        mock_read_epub.return_value = mock_book

        import hashlib

        with open(self.epub_path, "rb") as f:
            expected_checksum = hashlib.sha256(f.read()).hexdigest()

        result = import_epub(self.epub_path)
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        self.assertEqual(result.checksum, expected_checksum)

    def test_invalid_extension(self):
        invalid_path = os.path.join(self.temp_dir, "test.txt")
        with open(invalid_path, "w") as f:
            f.write("not epub")
        with self.assertRaises(ValueError) as cm:
            import_epub(invalid_path)
        self.assertIn("must have .epub extension", str(cm.exception))

    def test_file_not_exists(self):
        non_existent = os.path.join(self.temp_dir, "nonexistent.epub")
        with self.assertRaises(ValueError) as cm:
            import_epub(non_existent)
        self.assertIn("does not exist", str(cm.exception))

    @patch("library.services.epub.read_epub")
    def test_duplicate_detection(self, mock_read_epub):
        # Mock the epub object
        mock_book = MagicMock()
        mock_book.get_metadata.return_value = []
        mock_read_epub.return_value = mock_book

        # Calculate the actual checksum of the temp file
        import hashlib

        with open(self.epub_path, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        # Create a BookFile with the same checksum
        book = Book.objects.create(title="Existing Book")
        BookFile.objects.create(
            book=book,
            file="existing.epub",
            checksum=checksum,
            file_size=123,
            source_filename="existing.epub",
        )

        # Try to import again - should return existing
        result = import_epub(self.epub_path)
        self.assertEqual(result.status, ImportStatus.DUPLICATE)
        self.assertEqual(result.checksum, checksum)
        book_file = result.book_file
        assert book_file is not None

        book = result.book
        assert book is not None
        self.assertEqual(book.title, "Existing Book")

    @patch("library.services.epub.read_epub")
    def test_import_minimal_epub(self, mock_read_epub):
        # Mock the epub object with minimal metadata
        mock_book = MagicMock()
        mock_book.get_metadata.side_effect = lambda ns, name: {
            "title": [("Test Title", {})],
            "creator": [("Test Author", {})],
            "language": [("en", {})],
        }.get(name, [])
        mock_read_epub.return_value = mock_book

        import hashlib

        with open(self.epub_path, "rb") as f:
            expected_checksum = hashlib.sha256(f.read()).hexdigest()

        result = import_epub(self.epub_path)
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        self.assertEqual(result.checksum, expected_checksum)
        book_file = result.book_file
        assert book_file is not None

        book = result.book
        assert book is not None
        self.assertEqual(book.title, "Test Title")
        self.assertEqual(book.language, "en")

        author = book.authors.first()
        assert author is not None

    @patch("library.services.epub.read_epub")
    def test_import_creates_identifiers_prefers_isbn13_and_cleans_metadata(
        self, mock_read_epub
    ):
        mock_book = MagicMock()
        mock_book.get_metadata.side_effect = lambda ns, name: {
            "title": [("  Main Title  ", {}), ("Subtitle", {})],
            "creator": [(" Author A ", {}), ("author a", {}), ("", {})],
            "language": [("EN-US", {})],
            "publisher": [("  Pub  ", {})],
            "description": [("  Summary text  ", {})],
            "subject": [("Fiction", {}), ("fiction", {}), ("", {})],
            "identifier": [
                ("ISBN: 0-123456-47-9", {}),
                ("978-0-123456-47-2", {"scheme": "ISBN"}),
                ("doi:10.5555/123", {}),
                ("B00TEST123", {}),
                ("B00TEST123", {"scheme": "ASIN"}),
                ("urn:uuid:123e4567-e89b-12d3-a456-426614174000", {}),
                ("Some-Other-ID", {}),
            ],
        }.get(name, [])
        mock_read_epub.return_value = mock_book

        result = import_epub(self.epub_path)
        self.assertEqual(result.status, ImportStatus.IMPORTED)
        book = result.book
        assert book is not None

        book.refresh_from_db()
        self.assertEqual(book.title, "Main Title")
        self.assertEqual(book.subtitle, "Subtitle")
        self.assertEqual(book.summary, "Summary text")
        self.assertEqual(book.language, "en-us")
        self.assertEqual(book.publisher, "Pub")
        self.assertEqual(book.subjects, ["Fiction"])

        # Prefer ISBN-13 for Book.isbn when present.
        self.assertEqual(book.isbn, "9780123456472")

        # ISBNs and non-ISBN identifiers are preserved.
        identifiers = list(
            cast(Any, book)
            .identifiers.order_by("scheme", "value")
            .values_list("scheme", "value")
        )
        self.assertIn((BookIdentifier.SCHEME_ISBN_10, "0123456479"), identifiers)
        self.assertIn((BookIdentifier.SCHEME_ISBN_13, "9780123456472"), identifiers)
        self.assertIn((BookIdentifier.SCHEME_DOI, "10.5555/123"), identifiers)
        self.assertIn(
            (
                BookIdentifier.SCHEME_UUID,
                "urn:uuid:123e4567-e89b-12d3-a456-426614174000",
            ),
            identifiers,
        )
        self.assertIn((BookIdentifier.SCHEME_OTHER, "B00TEST123"), identifiers)
        self.assertIn((BookIdentifier.SCHEME_ASIN, "B00TEST123"), identifiers)
        self.assertIn((BookIdentifier.SCHEME_OTHER, "Some-Other-ID"), identifiers)

        # All identifiers derived from EPUB metadata should record provenance.
        sources = set(cast(Any, book).identifiers.values_list("source", flat=True))
        self.assertEqual(sources, {"epub"})
