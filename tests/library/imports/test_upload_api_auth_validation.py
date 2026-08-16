from __future__ import annotations

from unittest.mock import patch

from library.models import Book
from library.imports.views import MAX_IMPORT_UPLOAD_BYTES
from tests.library.imports.helpers import metadata_xml, minimal_epub_bytes, zip_bytes
from tests.library.imports.upload_api_helpers import (
    LibraryImportUploadApiTestCase,
    upload_file,
)
from tests.testenv.filesystem import IsolatedMediaRootMixin


class LibraryImportUploadAuthValidationTests(
    IsolatedMediaRootMixin,
    LibraryImportUploadApiTestCase,
):
    def test_web_upload_ceiling_is_256_mib(self):
        self.assertEqual(MAX_IMPORT_UPLOAD_BYTES, 256 * 1024 * 1024)

    def test_unauthenticated_upload_is_rejected(self):
        response = self.client.post(
            self.url,
            {"file": upload_file("sample.epub", minimal_epub_bytes())},
        )

        self.assertEqual(response.status_code, 403)

    def test_reader_upload_is_rejected(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.post(
            self.url,
            {"file": upload_file("sample.epub", minimal_epub_bytes())},
        )

        self.assertEqual(response.status_code, 403)

    def test_librarian_manager_and_owner_can_upload_epub(self):
        for username in ["librarian", "manager", "owner"]:
            with self.subTest(username=username):
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))

                response = self.client.post(
                    self.url,
                    {
                        "file": upload_file(
                            f"{username}.epub",
                            minimal_epub_bytes(metadata_xml=metadata_xml(username)),
                        )
                    },
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["counts"]["imported"], 1)

    def test_librarian_can_upload_zip(self):
        self.login_librarian()

        response = self.client.post(
            self.url,
            {
                "file": upload_file(
                    "books.zip",
                    zip_bytes(("sample.epub", minimal_epub_bytes())).getvalue(),
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_type"], "zip")

    def test_uppercase_extensions_are_accepted(self):
        self.login_librarian()

        epub_response = self.client.post(
            self.url,
            {"file": upload_file("SAMPLE.EPUB", minimal_epub_bytes())},
        )
        zip_response = self.client.post(
            self.url,
            {
                "file": upload_file(
                    "BOOKS.ZIP",
                    zip_bytes(("sample.epub", minimal_epub_bytes())).getvalue(),
                )
            },
        )

        self.assertEqual(epub_response.status_code, 200)
        self.assertEqual(zip_response.status_code, 200)

    def test_missing_file_returns_400(self):
        self.login_librarian()

        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, 400)

    def test_unsupported_file_returns_400(self):
        self.login_librarian()

        response = self.client.post(
            self.url,
            {"file": upload_file("notes.txt", b"notes")},
        )

        self.assertEqual(response.status_code, 400)

    def test_multiple_uploaded_files_return_400(self):
        self.login_librarian()

        response = self.client.post(
            self.url,
            {
                "file": [
                    upload_file("one.epub", minimal_epub_bytes(metadata_xml=metadata_xml("One"))),
                    upload_file("two.epub", minimal_epub_bytes(metadata_xml=metadata_xml("Two"))),
                ]
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Book.objects.exists())

    def test_oversized_upload_returns_400(self):
        self.login_librarian()

        with patch("library.imports.views.MAX_IMPORT_UPLOAD_BYTES", 1):
            response = self.client.post(
                self.url,
                {"file": upload_file("sample.epub", minimal_epub_bytes())},
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Book.objects.exists())
