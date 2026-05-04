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

from .models import Author, Book, BookFile, Series
from .services import ImportStatus, import_epub


class IsolatedMediaRootMixin:
    """
    Ensure FileField writes during tests go to a temp MEDIA_ROOT.

    Avoid polluting the real `userdata/media` directory during test runs.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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
        super().tearDownClass()


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


class BaseBookFileDownloadAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        self.author = Author.objects.create(name="Jane / Doe")
        self.series = Series.objects.create(name="My * Series")
        self.book = Book.objects.create(
            title="The: Title",
            series=self.series,
            series_index=2,
        )
        self.book.authors.add(self.author)

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
        self.author = Author.objects.create(name="Test Author")
        self.book = Book.objects.create(title="Test Title")
        self.book.authors.add(self.author)
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
        self.assertEqual(author.name, "Test Author")

        self.assertEqual(book_file.source_filename, "test.epub")
        self.assertIsNotNone(book_file.file_size)
        self.assertIsNotNone(book_file.checksum)
        checksum = cast(str, book_file.checksum)
        # Check file path
        expected_path = f"books/{checksum[:2]}/{checksum[2:4]}/{checksum}.epub"
        actual_name = book_file.file.name.replace("\\", "/")
        self.assertTrue(actual_name.endswith(expected_path))
