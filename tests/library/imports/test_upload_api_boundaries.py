from __future__ import annotations

import json

from rest_framework.authentication import SessionAuthentication

from library.groups.public_group import get_public_group
from library.imports.views import ImportUploadView
from library.models import Book, BookGroupAssignment
from tests.library.imports.helpers import (
    epub_with_cover_bytes,
    image_bytes,
    minimal_epub_bytes,
    zip_bytes,
)
from tests.library.imports.upload_api_helpers import (
    LibraryImportUploadApiTestCase,
    upload_file,
)
from tests.testenv.filesystem import IsolatedMediaRootMixin


class LibraryImportUploadBoundaryTests(
    IsolatedMediaRootMixin,
    LibraryImportUploadApiTestCase,
):
    def test_response_omits_operator_detail(self):
        self.login_librarian()

        response = self.client.post(
            self.url,
            {"file": upload_file("bad.epub", b"not an epub")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("operator_detail", json.dumps(response.json()))

    def test_skipped_item_has_no_book_id(self):
        self.login_librarian()

        response = self.client.post(
            self.url,
            {
                "file": upload_file(
                    "collision.zip",
                    zip_bytes(
                        ("dir/book.epub", b"not an epub"),
                        ("dir/./book.epub", minimal_epub_bytes()),
                    ).getvalue(),
                )
            },
        )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["items"][0]["status"], "skipped")
        self.assertNotIn("book_id", payload["items"][0])

    def test_response_does_not_leak_unsafe_zip_member_names(self):
        self.login_librarian()

        response = self.client.post(
            self.url,
            {
                "file": upload_file(
                    "unsafe.zip",
                    zip_bytes(
                        ("../unsafe.epub", b"not an epub"),
                        ("safe.epub", minimal_epub_bytes()),
                    ).getvalue(),
                )
            },
        )

        payload_text = json.dumps(response.json())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("../unsafe.epub", payload_text)
        self.assertNotIn("..", payload_text)

    def test_response_source_label_is_safe_basename(self):
        self.login_librarian()
        upload = upload_file("sample.epub", minimal_epub_bytes())
        upload.name = r"C:\unsafe\sample.epub"

        response = self.client.post(self.url, {"file": upload})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_label"], "sample.epub")
        self.assertEqual(response.json()["items"][0]["source_label"], "sample.epub")

    def test_endpoint_is_session_auth_oriented(self):
        self.assertEqual(ImportUploadView.authentication_classes, [SessionAuthentication])

    def test_public_assignment_happens_through_persistence(self):
        self.login_librarian()

        response = self.client.post(
            self.url,
            {"file": upload_file("sample.epub", minimal_epub_bytes())},
        )

        book = Book.objects.get(id=response.json()["items"][0]["book_id"])
        self.assertTrue(
            BookGroupAssignment.objects.filter(
                book=book,
                group=get_public_group(),
                added_by=self.librarian,
            ).exists()
        )

    def test_upload_api_response_unchanged_while_book_gets_cover(self):
        self.login_librarian()

        response = self.client.post(
            self.url,
            {"file": upload_file("cover.epub", epub_with_cover_bytes(cover_bytes=image_bytes("PNG")))},
        )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("cover_file", json.dumps(payload))
        self.assertNotIn("cover_url", json.dumps(payload))
        book = Book.objects.get(id=payload["items"][0]["book_id"])
        self.assertTrue(book.cover_file.name)
        self.assertTrue(book.book_file.name)
