from __future__ import annotations

from io import BytesIO
import hashlib
import zipfile

from rest_framework import status
from rest_framework.test import APITestCase

from django.core.files.uploadedfile import SimpleUploadedFile

from library.book_file_services import repair_book_file_for_book
from library.groups.services import ensure_book_public_assignment
from library.models import Author, BookFile

from tests.library.helpers import (
    create_librarian_user,
    create_reader_user,
)
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.books import create_fileless_book_for_integrity_edge_case
from tests.utils.responses import (
    assert_http_response,
    assert_response,
    response_data_dict,
)


def _epub_bytes(label: str = "book") -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", f"<container>{label}</container>")
    return buffer.getvalue()


class BaseBookFileDownloadAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.user = create_librarian_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")

        self.author = Author.objects.create(name="Test Author")
        # Intentionally fileless: this test sets up a BookFile row with a fixed path/checksum.
        self.book = create_fileless_book_for_integrity_edge_case(
            title="Test Title", assign_public=False
        )
        self.book.authors.add(self.author)
        ensure_book_public_assignment(book=self.book, added_by=None)

        self.book_file = BookFile.objects.create(
            book=self.book,
            file="books/aa/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.epub",
            checksum="a" * 64,
            file_size=123,
            source_filename="source.epub",
        )

    def test_download_requires_existing_file(self):
        response = assert_http_response(
            self.client.get(
                f"/api/v1/library/book-files/{self.book_file.id}/download/"
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_succeeds_after_missing_file_is_repaired(self):
        epub_bytes = _epub_bytes("restored")
        checksum = hashlib.sha256(epub_bytes).hexdigest()
        self.book_file.checksum = checksum
        self.book_file.save(update_fields=["checksum", "updated_at"])

        before = assert_http_response(
            self.client.get(
                f"/api/v1/library/book-files/{self.book_file.id}/download/"
            ),
        )
        self.assertEqual(before.status_code, status.HTTP_404_NOT_FOUND)

        repair_book_file_for_book(
            book=self.book,
            upload=SimpleUploadedFile(
                "restored.epub",
                epub_bytes,
                content_type="application/epub+zip",
            ),
        )

        after = self.client.get(
            f"/api/v1/library/book-files/{self.book_file.id}/download/"
        )
        self.assertEqual(after.status_code, status.HTTP_200_OK)
        self.assertEqual(after.get("Content-Type"), "application/epub+zip")
        after.close()


class BookFileDownloadAPITest(BaseBookFileDownloadAPITest):
    pass


class BookFileSerializerAPITest(APITestCase):
    def setUp(self):
        self.user = create_reader_user(username="testuser", password="testpass")
        self.author = Author.objects.create(name="Test Author")
        # Intentionally fileless: this test sets up a BookFile row with a fixed path/checksum.
        self.book = create_fileless_book_for_integrity_edge_case(
            title="Test Title", assign_public=False
        )
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
        response = assert_response(
            self.client.get(f"/api/v1/library/book-files/{self.book_file.id}/"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_dict(response)
        self.assertNotIn("file", data)
        self.assertIn("download_url", data)
        self.assertEqual(
            data["download_url"],
            f"http://testserver/api/v1/library/book-files/{self.book_file.id}/download/",
        )
