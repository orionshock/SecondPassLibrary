from __future__ import annotations

import json
from unittest.mock import patch

import library.models as library_models
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.authentication import SessionAuthentication

from accounts.models import UserProfile
from core.server_settings import set_server_setting
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING, get_public_group
from library.imports.views import ImportUploadView
from library.models import Book, BookGroupAssignment, BookIdentifier, LibraryGroup
from tests.library.helpers import set_user_role
from tests.library.imports.helpers import metadata_xml, minimal_epub_bytes, zip_bytes
from tests.testenv.filesystem import IsolatedMediaRootMixin


class LibraryImportUploadApiTests(IsolatedMediaRootMixin, TestCase):
    url = "/api/v1/library/imports/"

    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        set_user_role(self.reader, UserProfile.ROLE_READER)
        set_user_role(self.librarian, UserProfile.ROLE_LIBRARIAN)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)
        self.public = LibraryGroup.objects.create(name="Common Room")
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(self.public.id),
            description="LibraryReWrite2607 Public/Common Room group id.",
        )

    def test_unauthenticated_upload_is_rejected(self):
        response = self.client.post(
            self.url,
            {"file": _upload("sample.epub", minimal_epub_bytes())},
        )

        self.assertEqual(response.status_code, 403)

    def test_reader_upload_is_rejected(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.post(
            self.url,
            {"file": _upload("sample.epub", minimal_epub_bytes())},
        )

        self.assertEqual(response.status_code, 403)

    def test_librarian_can_upload_epub(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        response = self.client.post(
            self.url,
            {"file": _upload("sample.epub", minimal_epub_bytes())},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source_type"], "epub")
        self.assertEqual(payload["counts"]["imported"], 1)
        self.assertEqual(payload["items"][0]["status"], "imported")
        self.assertEqual(payload["items"][0]["source_label"], "sample.epub")
        self.assertTrue(payload["items"][0]["book_id"])

    def test_manager_and_owner_can_upload_epub(self):
        for username in ["manager", "owner"]:
            with self.subTest(username=username):
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))

                response = self.client.post(
                    self.url,
                    {"file": _upload(f"{username}.epub", minimal_epub_bytes(metadata_xml=metadata_xml(username)))},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["counts"]["imported"], 1)

    def test_librarian_can_upload_zip(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        response = self.client.post(
            self.url,
            {
                "file": _upload(
                    "books.zip",
                    zip_bytes(("sample.epub", minimal_epub_bytes())).getvalue(),
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source_type"], "zip")
        self.assertEqual(payload["counts"]["imported"], 1)
        self.assertEqual(payload["items"][0]["source_label"], "sample.epub")

    def test_uppercase_epub_extension_is_accepted(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        response = self.client.post(
            self.url,
            {"file": _upload("SAMPLE.EPUB", minimal_epub_bytes())},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["counts"]["imported"], 1)

    def test_uppercase_zip_extension_is_accepted(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        response = self.client.post(
            self.url,
            {
                "file": _upload(
                    "BOOKS.ZIP",
                    zip_bytes(("sample.epub", minimal_epub_bytes())).getvalue(),
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["counts"]["imported"], 1)

    def test_missing_file_returns_400(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        response = self.client.post(self.url, {})

        self.assertEqual(response.status_code, 400)

    def test_unsupported_file_returns_400(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        response = self.client.post(
            self.url,
            {"file": _upload("notes.txt", b"notes")},
        )

        self.assertEqual(response.status_code, 400)

    def test_multiple_uploaded_files_return_400(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        response = self.client.post(
            self.url,
            {
                "file": [
                    _upload("one.epub", minimal_epub_bytes(metadata_xml=metadata_xml("One"))),
                    _upload("two.epub", minimal_epub_bytes(metadata_xml=metadata_xml("Two"))),
                ]
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Book.objects.exists())

    def test_empty_epub_upload_returns_failed_item(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        response = self.client.post(
            self.url,
            {"file": _upload("empty.epub", b"")},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["counts"]["failed"], 1)
        self.assertEqual(payload["items"][0]["status"], "failed")
        self.assertNotIn("book_id", payload["items"][0])

    def test_oversized_upload_returns_400(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        with patch("library.imports.views.MAX_IMPORT_UPLOAD_BYTES", 1):
            response = self.client.post(
                self.url,
                {"file": _upload("sample.epub", minimal_epub_bytes())},
            )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Book.objects.exists())

    def test_duplicate_epub_returns_duplicate_item(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))
        data = minimal_epub_bytes()
        self.client.post(self.url, {"file": _upload("first.epub", data)})

        response = self.client.post(self.url, {"file": _upload("second.epub", data)})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["counts"]["duplicate"], 1)
        self.assertEqual(payload["items"][0]["status"], "duplicate")

    def test_zip_partial_failure_returns_item_level_failure(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        response = self.client.post(
            self.url,
            {
                "file": _upload(
                    "mixed.zip",
                    zip_bytes(
                        ("bad.epub", b"not an epub"),
                        ("good.epub", minimal_epub_bytes(metadata_xml=metadata_xml("Good"))),
                    ).getvalue(),
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["counts"]["failed"], 1)
        self.assertEqual(payload["counts"]["imported"], 1)
        self.assertEqual([item["status"] for item in payload["items"]], ["failed", "imported"])
        self.assertNotIn("book_id", payload["items"][0])
        self.assertTrue(payload["items"][1]["book_id"])

    def test_identifier_conflict_returns_conflict_item(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))
        existing_book = Book.objects.create(title="Existing", checksum="existing")
        BookIdentifier.objects.create(
            book=existing_book,
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="9780000000011",
            normalized_value="9780000000011",
        )
        epub = minimal_epub_bytes(
            metadata_xml="""
            <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"
                      xmlns:opf="http://www.idpf.org/2007/opf">
              <dc:title>Conflict</dc:title>
              <dc:identifier opf:scheme="ISBN">978-0-00-000001-1</dc:identifier>
            </metadata>
            """
        )

        response = self.client.post(
            self.url,
            {"file": _upload("conflict.epub", epub)},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["counts"]["conflict"], 1)
        self.assertEqual(payload["items"][0]["status"], "conflict")

    def test_response_omits_operator_detail(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        response = self.client.post(
            self.url,
            {"file": _upload("bad.epub", b"not an epub")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("operator_detail", json.dumps(response.json()))

    def test_skipped_item_has_no_book_id(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        response = self.client.post(
            self.url,
            {
                "file": _upload(
                    "collision.zip",
                    zip_bytes(
                        ("dir/book.epub", b"not an epub"),
                        ("dir/./book.epub", minimal_epub_bytes()),
                    ).getvalue(),
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["items"][0]["status"], "skipped")
        self.assertNotIn("book_id", payload["items"][0])

    def test_response_does_not_leak_unsafe_zip_member_names(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        response = self.client.post(
            self.url,
            {
                "file": _upload(
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
        self.assertTrue(self.client.login(username="librarian", password="pw"))
        upload = _upload("sample.epub", minimal_epub_bytes())
        upload.name = r"C:\unsafe\sample.epub"

        response = self.client.post(self.url, {"file": upload})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["source_label"], "sample.epub")
        self.assertEqual(response.json()["items"][0]["source_label"], "sample.epub")

    def test_endpoint_is_session_auth_oriented(self):
        self.assertEqual(ImportUploadView.authentication_classes, [SessionAuthentication])

    def test_public_assignment_happens_through_persistence(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        response = self.client.post(
            self.url,
            {"file": _upload("sample.epub", minimal_epub_bytes())},
        )

        book = Book.objects.get(id=response.json()["items"][0]["book_id"])
        self.assertTrue(
            BookGroupAssignment.objects.filter(
                book=book,
                group=get_public_group(),
                added_by=self.librarian,
            ).exists()
        )

    def test_no_bookfile_model_or_object_appears(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        response = self.client.post(
            self.url,
            {"file": _upload("sample.epub", minimal_epub_bytes())},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(hasattr(library_models, "BookFile"))
        self.assertTrue(Book.objects.get().book_file.name)


def _upload(name: str, data: bytes) -> SimpleUploadedFile:
    return SimpleUploadedFile(name, data, content_type="application/octet-stream")
