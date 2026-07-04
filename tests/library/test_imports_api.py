from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any, cast
import uuid
import zipfile
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.utils import override_settings
import django.core.files.storage as storage
from django.utils.functional import empty
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from library.group_services import ensure_user_public_membership
from library.import_services import ImportResourceLimitError, _copy_fileobj_capped
from library.models import Book, BookFile
from core.errors import ErrorCode
from tests.utils.responses import response_data_dict


class IsolatedImportsMixin:
    """
    Isolate staging under TestFiles/ so tests don't pollute real userdata/imports.
    """

    @classmethod
    def setUpClass(cls):
        parent_set_up = getattr(super(), "setUpClass", None)
        if callable(parent_set_up):
            parent_set_up()
        temp_root = Path(settings.BASE_DIR) / "TestFiles"
        temp_root.mkdir(parents=True, exist_ok=True)
        cls._imports_root = str(temp_root / f"tmp_imports_{uuid.uuid4().hex}")
        cls._media_root = str(temp_root / f"tmp_media_{uuid.uuid4().hex}")
        os.makedirs(cls._imports_root, exist_ok=True)
        os.makedirs(cls._media_root, exist_ok=True)
        cls._override = override_settings(
            IMPORTS_DIR=Path(cls._imports_root),
            MEDIA_ROOT=cls._media_root,
        )
        cls._override.enable()

        handler = cast(Any, getattr(storage, "storages"))
        handler._storages = {}
        handler._backends = None
        setattr(cast(Any, storage.default_storage), "_wrapped", empty)

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        __import__("shutil").rmtree(cls._imports_root, ignore_errors=True)
        __import__("shutil").rmtree(cls._media_root, ignore_errors=True)
        parent_tear_down = getattr(super(), "tearDownClass", None)
        if callable(parent_tear_down):
            parent_tear_down()


def _mock_epub() -> MagicMock:
    mock_book = MagicMock()
    mock_book.get_metadata.side_effect = lambda ns, name: {
        "title": [("Test Title", {})],
        "creator": [("Test Author", {})],
        "language": [("en", {})],
    }.get(name, [])
    return mock_book


def _png_bytes(*, size: tuple[int, int] = (32, 48)) -> bytes:
    from PIL import Image

    img = Image.new("RGB", size, color=(4, 5, 6))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _epub_with_embedded_cover_bytes(*, cover_size: tuple[int, int] = (10, 12)) -> bytes:
    """
    Minimal EPUB zip bytes that embedded cover extraction can read.
    """
    cover_bytes = _png_bytes(size=cover_size)
    container_xml = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="3.0">
  <manifest>
    <item id="c1" href="images/cover.png" media-type="image/png" properties="cover-image"/>
  </manifest>
</package>
"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml", container_xml)
        zf.writestr("OEBPS/content.opf", opf_xml)
        zf.writestr("OEBPS/images/cover.png", cover_bytes)
    return buf.getvalue()


class ImportApiTest(IsolatedImportsMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pw")
        self.other = User.objects.create_user(username="u2", password="pw")
        ensure_user_public_membership(user=self.user)
        ensure_user_public_membership(user=self.other)

    def _login_librarian(self) -> None:
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")

    def test_anonymous_cannot_create_import(self):
        epub = SimpleUploadedFile(
            "book.epub", b"epub-bytes", content_type="application/epub+zip"
        )
        create = cast_response(
            self.client.post("/api/v1/library/imports/", data={"file": epub}, format="multipart")
        )
        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)

    @patch("library.services.epub.read_epub")
    def test_reader_cannot_create_import(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        self.client.login(username="u1", password="pw")

        epub = SimpleUploadedFile("book.epub", b"x", content_type="application/epub+zip")
        created = cast_response(
            self.client.post("/api/v1/library/imports/", data={"file": epub}, format="multipart")
        )
        self.assertEqual(created.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_upload_file_returns_error_envelope(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")

        response = cast_response(
            self.client.post("/api/v1/library/imports/", data={}, format="multipart")
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response_data_dict(response)
        self.assertIn("error", data)
        self.assertEqual(cast(dict[str, Any], data["error"])["code"], ErrorCode.MISSING_UPLOAD_FILE)

    def test_invalid_upload_type_returns_error_envelope(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")

        bad = SimpleUploadedFile("bad.txt", b"x", content_type="text/plain")
        response = cast_response(
            self.client.post("/api/v1/library/imports/", data={"file": bad}, format="multipart")
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response_data_dict(response)
        self.assertIn("error", data)
        self.assertEqual(cast(dict[str, Any], data["error"])["code"], ErrorCode.INVALID_UPLOAD_TYPE)

    @patch("library.services.epub.read_epub")
    def test_single_epub_failure_message_does_not_expose_temp_path(self, mock_read_epub):
        mock_read_epub.side_effect = ValueError(
            r"Failed parsing C:\projects\SecondPassLibrary\userdata\imports\jobs\secret\bad.epub"
        )
        self._login_librarian()

        epub = SimpleUploadedFile("bad.epub", b"not-an-epub", content_type="application/epub+zip")
        response = cast_response(
            self.client.post("/api/v1/library/imports/", data={"file": epub}, format="multipart")
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)
        item = cast(list[dict[str, Any]], data["items"])[0]
        self.assertEqual(item["status"], "failed")
        self.assertEqual(item["message"], "Invalid or unsupported EPUB file.")
        self.assertNotIn("SecondPassLibrary", item["message"])
        self.assertNotIn("userdata", item["message"])
        self.assertNotIn("bad.epub", item["message"])

    @patch("library.services.epub.read_epub")
    def test_zip_member_failure_message_does_not_expose_member_path_or_temp_path(self, mock_read_epub):
        mock_read_epub.side_effect = ValueError(
            r"Failed parsing member private/nested/leaky.epub at C:\tmp\jobs\abc\extracted\file.epub"
        )
        self._login_librarian()

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("private/nested/leaky.epub", b"not-an-epub")
        buf.seek(0)

        upload = SimpleUploadedFile("bundle.zip", buf.read(), content_type="application/zip")
        with self.assertLogs("library.import_services", level="WARNING") as captured:
            response = cast_response(
                self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart")
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)
        item = cast(list[dict[str, Any]], data["items"])[0]
        self.assertEqual(item["status"], "failed")
        self.assertEqual(item["source_name"], "leaky.epub")
        self.assertEqual(item["message"], "Invalid or unsupported EPUB file.")
        self.assertNotIn("private/nested", item["message"])
        self.assertNotIn("C:\\tmp", item["message"])
        self.assertNotIn("leaky.epub", item["message"])

        failed_item_logs = [
            record
            for record in captured.records
            if record.getMessage() == "library import item failed"
        ]
        self.assertEqual(len(failed_item_logs), 1)
        failed_item_log = failed_item_logs[0]
        self.assertEqual(failed_item_log.item_source_name, "leaky.epub")
        self.assertEqual(
            failed_item_log.safe_message,
            "Invalid or unsupported EPUB file.",
        )
        safe_log_text = (
            f"{failed_item_log.getMessage()} "
            f"{failed_item_log.item_source_name} "
            f"{failed_item_log.safe_message}"
        )
        self.assertNotIn("private/nested", safe_log_text)
        self.assertNotIn("C:\\tmp", safe_log_text)

    @patch("library.services.epub.read_epub")
    @patch("library.import_services.MAX_SINGLE_EPUB_UPLOAD_BYTES", 4)
    def test_oversized_single_epub_upload_is_rejected_before_import_parse(self, mock_read_epub):
        self._login_librarian()

        epub = SimpleUploadedFile("book.epub", b"12345", content_type="application/epub+zip")
        response = cast_response(
            self.client.post("/api/v1/library/imports/", data={"file": epub}, format="multipart")
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response_data_dict(response)
        self.assertEqual(cast(dict[str, Any], data["error"])["code"], ErrorCode.INVALID_REQUEST)
        self.assertIn("EPUB upload exceeds", cast(dict[str, Any], data["error"])["detail"])
        mock_read_epub.assert_not_called()
        self.assertEqual(BookFile.objects.count(), 0)

    @patch("library.import_services.MAX_ZIP_UPLOAD_BYTES", 4)
    def test_oversized_zip_upload_is_rejected(self):
        self._login_librarian()

        upload = SimpleUploadedFile("bundle.zip", b"12345", content_type="application/zip")
        response = cast_response(
            self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart")
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response_data_dict(response)
        self.assertEqual(cast(dict[str, Any], data["error"])["code"], ErrorCode.INVALID_REQUEST)
        self.assertIn("ZIP upload exceeds", cast(dict[str, Any], data["error"])["detail"])
        self.assertEqual(BookFile.objects.count(), 0)

    @patch("library.import_services.MAX_ZIP_MEMBERS", 1)
    def test_zip_with_too_many_members_is_rejected_safely(self):
        self._login_librarian()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("a.epub", b"a")
            zf.writestr("b.epub", b"b")
        buf.seek(0)

        upload = SimpleUploadedFile("bundle.zip", buf.read(), content_type="application/zip")
        response = cast_response(
            self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart")
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response_data_dict(response)
        self.assertEqual(cast(dict[str, Any], data["error"])["code"], ErrorCode.INVALID_REQUEST)
        self.assertIn("ZIP contains more than 1 entries", cast(dict[str, Any], data["error"])["detail"])
        self.assertEqual(BookFile.objects.count(), 0)

    @patch("library.services.epub.read_epub")
    @patch("library.import_services.MAX_ZIP_EPUB_MEMBER_BYTES", 4)
    def test_zip_epub_member_over_uncompressed_limit_is_skipped_safely(self, mock_read_epub):
        self._login_librarian()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("big.epub", b"12345")
        buf.seek(0)

        upload = SimpleUploadedFile("bundle.zip", buf.read(), content_type="application/zip")
        response = cast_response(
            self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart")
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)
        self.assertEqual(data["total_found"], 1)
        self.assertEqual(data["imported_count"], 0)
        self.assertEqual(data["failed_count"], 1)
        self.assertIn("uncompressed limit", cast(list[dict[str, Any]], data["items"])[0]["message"])
        mock_read_epub.assert_not_called()

    @patch("library.services.epub.read_epub")
    @patch("library.import_services.MAX_ZIP_EPUB_MEMBER_BYTES", 10)
    @patch("library.import_services.MAX_ZIP_TOTAL_EPUB_BYTES", 8)
    def test_zip_total_epub_uncompressed_limit_is_enforced(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        self._login_librarian()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("a.epub", b"1111")
            zf.writestr("b.epub", b"22222")
        buf.seek(0)

        upload = SimpleUploadedFile("bundle.zip", buf.read(), content_type="application/zip")
        response = cast_response(
            self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart")
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)
        self.assertEqual(data["total_found"], 2)
        self.assertEqual(data["imported_count"], 1)
        self.assertEqual(data["failed_count"], 1)
        self.assertEqual(mock_read_epub.call_count, 1)
        messages = [item["message"] for item in cast(list[dict[str, Any]], data["items"])]
        self.assertTrue(any("total uncompressed limit" in message for message in messages))

    @patch("library.services.epub.read_epub")
    def test_authenticated_can_upload_single_epub_and_stages_with_generated_name(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        self.client.login(username="u1", password="pw")

        epub = SimpleUploadedFile("Original Name.epub", b"same-bytes", content_type="application/epub+zip")
        response = cast_response(
            self.client.post("/api/v1/library/imports/", data={"file": epub}, format="multipart")
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("library.services.epub.read_epub")
    def test_librarian_can_upload_single_epub_and_receives_transient_result(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")

        epub = SimpleUploadedFile("Original Name.epub", b"same-bytes", content_type="application/epub+zip")
        with self.assertLogs("library.import_services", level="INFO") as captured:
            response = cast_response(
                self.client.post("/api/v1/library/imports/", data={"file": epub}, format="multipart")
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)

        self.assertNotIn("id", data)
        self.assertRegex(str(data["run_id"]), r"^[0-9a-f-]{36}$")
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["source_type"], "epub")
        self.assertEqual(data["source_filename"], "Original Name.epub")
        self.assertNotIn("staged_path", data)
        self.assertIn("items", data)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["total_found"], 1)
        self.assertEqual(data["imported_count"], 1)
        self.assertEqual(data["duplicate_count"], 0)
        self.assertEqual(data["failed_count"], 0)
        item = cast(list[dict[str, Any]], data["items"])[0]
        self.assertEqual(item["status"], "imported")
        self.assertIsNotNone(item["book"])
        self.assertIsNotNone(item["book_file"])
        self.assertEqual(Book.objects.count(), 1)
        self.assertEqual(BookFile.objects.count(), 1)

        messages = [record.getMessage() for record in captured.records]
        self.assertIn("library import started", messages)
        self.assertIn("library import finished", messages)
        finish_log = next(
            record
            for record in captured.records
            if record.getMessage() == "library import finished"
        )
        self.assertEqual(finish_log.run_id, data["run_id"])
        self.assertEqual(finish_log.source_type, "epub")
        self.assertEqual(finish_log.source_name, "Original Name.epub")
        self.assertEqual(finish_log.status, "completed")
        self.assertEqual(finish_log.total_found, 1)
        self.assertEqual(finish_log.imported_count, 1)
        self.assertEqual(finish_log.duplicate_count, 0)
        self.assertEqual(finish_log.failed_count, 0)

    @patch("library.services.epub.read_epub")
    def test_duplicate_epub_upload_creates_duplicate_item(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")

        epub1 = SimpleUploadedFile("book.epub", b"dup-bytes", content_type="application/epub+zip")
        r1 = cast_response(self.client.post("/api/v1/library/imports/", data={"file": epub1}, format="multipart"))
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)

        epub2 = SimpleUploadedFile("book.epub", b"dup-bytes", content_type="application/epub+zip")
        r2 = cast_response(self.client.post("/api/v1/library/imports/", data={"file": epub2}, format="multipart"))
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(r2)
        self.assertEqual(data["duplicate_count"], 1)
        self.assertEqual(data["imported_count"], 0)
        self.assertEqual(data["failed_count"], 0)
        self.assertEqual(cast(list[dict[str, Any]], data["items"])[0]["status"], "duplicate")

    @patch("library.services.epub.read_epub")
    def test_authenticated_can_upload_zip_with_multiple_epubs_ignores_non_epub_and_path_traversal(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("a.epub", b"bytes-a")
            zf.writestr("notes.txt", b"ignore")
            zf.writestr("../evil.epub", b"nope")
            zf.writestr("nested/b.epub", b"bytes-b")
        buf.seek(0)

        upload = SimpleUploadedFile("bundle.zip", buf.read(), content_type="application/zip")
        response = cast_response(self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)
        self.assertEqual(data["source_type"], "zip")
        self.assertEqual(data["total_found"], 2)
        self.assertEqual(len(cast(list[Any], data["items"])), 2)
        self.assertTrue(
            all(item["status"] in {"imported", "duplicate", "failed"} for item in cast(list[dict[str, Any]], data["items"]))
        )

    @patch("library.services.epub.read_epub")
    def test_zip_member_dot_segment_is_normalized_for_sidecar_matching(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")

        opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Dot Segment OPF Title</dc:title>
    <meta name="cover" content="cov"/>
  </metadata>
  <manifest>
    <item id="cov" href="cover.png" media-type="image/png"/>
  </manifest>
</package>
"""

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Some ZIP tools include harmless "./" segments; importer should normalize these.
            zf.writestr("dir/./Book.epub", b"epub-bytes")
            zf.writestr("dir/metadata.opf", opf_xml)
            zf.writestr("dir/cover.png", _png_bytes())
        buf.seek(0)

        upload = SimpleUploadedFile("bundle.zip", buf.read(), content_type="application/zip")
        response = cast_response(self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)
        self.assertEqual(data["total_found"], 1)

        book = Book.objects.get(title="Dot Segment OPF Title")
        self.assertTrue(bool(book.cover_file))
        self.assertEqual(book.cover_source, "opf_sidecar")

    @patch("library.services.epub.read_epub")
    def test_zip_member_normalization_collision_is_skipped_safely(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # These normalize to the same member name.
            zf.writestr("dir/book.epub", b"bytes-a")
            zf.writestr("dir/./book.epub", b"bytes-b")
        buf.seek(0)

        upload = SimpleUploadedFile("bundle.zip", buf.read(), content_type="application/zip")
        response = cast_response(self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)
        # Ambiguous/unsafe normalized paths are skipped (no items created).
        self.assertEqual(data["total_found"], 0)
        self.assertEqual(len(cast(list[Any], data["items"])), 0)

    @patch("library.services.epub.read_epub")
    def test_zip_sidecar_metadata_opf_precedence_and_cover(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")

        opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>OPF Title</dc:title>
    <dc:creator>OPF Author</dc:creator>
    <dc:publisher>OPF Pub</dc:publisher>
    <dc:language>en</dc:language>
    <dc:subject>Fantasy</dc:subject>
    <dc:description>OPF Summary</dc:description>
    <meta name="calibre:series" content="Dresden Files"/>
    <meta name="calibre:series_index" content="3"/>
    <meta name="cover" content="cov"/>
  </metadata>
  <manifest>
    <item id="cov" href="cover.png" media-type="image/png"/>
  </manifest>
</package>
"""

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("CalibreLibrary/Jim Butcher/Academ's Fury (126)/Academ's Fury - Jim Butcher.epub", b"epub-bytes")
            zf.writestr("CalibreLibrary/Jim Butcher/Academ's Fury (126)/metadata.opf", opf_xml)
            zf.writestr("CalibreLibrary/Jim Butcher/Academ's Fury (126)/cover.png", _png_bytes())
        buf.seek(0)

        upload = SimpleUploadedFile("calibre.zip", buf.read(), content_type="application/zip")
        response = cast_response(self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        book = Book.objects.get(title="OPF Title")
        self.assertEqual(book.publisher, "OPF Pub")
        self.assertEqual(book.summary, "OPF Summary")
        self.assertEqual(book.language, "en")
        self.assertIn("Fantasy", book.subjects or [])
        self.assertIsNotNone(book.series)
        assert book.series is not None
        self.assertEqual(book.series.name, "Dresden Files")
        self.assertEqual(str(book.series_index), "3.0")
        self.assertTrue(bool(book.cover_file))
        self.assertEqual(book.cover_source, "opf_sidecar")

    @patch("library.services.epub.read_epub")
    def test_zip_sidecar_metadata_opf_detection_order_prefers_metadata_opf(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")

        meta_opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Meta OPF Title</dc:title>
</metadata></package>
"""
        base_opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Basename OPF Title</dc:title>
</metadata></package>
"""

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dir/Foo.epub", b"epub-bytes")
            zf.writestr("dir/metadata.opf", meta_opf)
            zf.writestr("dir/Foo.opf", base_opf)
        buf.seek(0)

        upload = SimpleUploadedFile("bundle.zip", buf.read(), content_type="application/zip")
        response = cast_response(self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Book.objects.filter(title="Meta OPF Title").exists())
        self.assertFalse(Book.objects.filter(title="Basename OPF Title").exists())

    @patch("library.services.epub.read_epub")
    def test_zip_sidecar_metadata_opf_detection_same_basename_fallback(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")

        base_opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Basename Only</dc:title>
</metadata></package>
"""

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dir/Foo.epub", b"epub-bytes")
            zf.writestr("dir/Foo.opf", base_opf)
        buf.seek(0)

        upload = SimpleUploadedFile("bundle.zip", buf.read(), content_type="application/zip")
        response = cast_response(self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Book.objects.filter(title="Basename Only").exists())

    @patch("library.services.epub.read_epub")
    def test_zip_sidecar_metadata_opf_detection_unique_opf_fallback(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")

        lone_opf = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Only OPF</dc:title>
</metadata></package>
"""

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dir/Book.epub", b"epub-bytes")
            zf.writestr("dir/random.opf", lone_opf)
        buf.seek(0)

        upload = SimpleUploadedFile("bundle.zip", buf.read(), content_type="application/zip")
        response = cast_response(self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Book.objects.filter(title="Only OPF").exists())

    @patch("library.services.epub.read_epub")
    def test_zip_sidecar_cover_invalid_falls_back_to_embedded_epub_cover(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")

        opf_xml = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>OPF Title 2</dc:title>
    <meta name="cover" content="cov"/>
  </metadata>
  <manifest>
    <item id="cov" href="cover.svg" media-type="image/svg+xml"/>
  </manifest>
</package>
"""

        epub_bytes = _epub_with_embedded_cover_bytes(cover_size=(9, 10))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dir/book.epub", epub_bytes)
            zf.writestr("dir/metadata.opf", opf_xml)
            zf.writestr("dir/cover.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>")
        buf.seek(0)

        upload = SimpleUploadedFile("bundle.zip", buf.read(), content_type="application/zip")
        response = cast_response(self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        book = Book.objects.get(title="OPF Title 2")
        self.assertTrue(bool(book.cover_file))
        self.assertEqual(book.cover_source, "epub")
        self.assertEqual(book.cover_width, 9)
        self.assertEqual(book.cover_height, 10)

    @patch("library.services.epub.read_epub")
    def test_zip_sidecar_security_bad_href_and_malformed_or_too_big_opf_ignored(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")

        bad_href_opf = """<?xml version="1.0"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>OPF Bad Href</dc:title>
    <meta name="cover" content="cov"/>
  </metadata>
  <manifest>
    <item id="cov" href="../cover.png" media-type="image/png"/>
  </manifest>
</package>
"""
        malformed_opf = "<package><metadata"  # invalid XML
        too_big = ("x" * (1024 * 1024 + 10)).encode("utf-8")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("a/book.epub", b"epub-bytes-a")
            zf.writestr("a/metadata.opf", bad_href_opf)
            zf.writestr("a/cover.png", _png_bytes())

            zf.writestr("b/book.epub", b"epub-bytes-b")
            zf.writestr("b/metadata.opf", malformed_opf)

            zf.writestr("c/book.epub", b"epub-bytes-c")
            zf.writestr("c/metadata.opf", too_big)
        buf.seek(0)

        upload = SimpleUploadedFile("bundle.zip", buf.read(), content_type="application/zip")
        response = cast_response(self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        b1 = Book.objects.get(title="OPF Bad Href")
        self.assertFalse(bool(b1.cover_file))

        # Malformed/too-big OPFs should fall back to EPUB metadata from _mock_epub.
        self.assertTrue(Book.objects.filter(title="Test Title").exists())

    @patch("library.services.epub.read_epub")
    def test_zip_sidecar_opf_with_doctype_entity_is_ignored_safely(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        self._login_librarian()

        unsafe_opf = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE package [
  <!ENTITY unsafe "Unsafe OPF Title">
]>
<package xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>&unsafe;</dc:title>
  </metadata>
</package>
"""

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("dir/book.epub", b"epub-bytes")
            zf.writestr("dir/metadata.opf", unsafe_opf)
        buf.seek(0)

        upload = SimpleUploadedFile("bundle.zip", buf.read(), content_type="application/zip")
        response = cast_response(
            self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart")
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(Book.objects.filter(title="Unsafe OPF Title").exists())
        self.assertTrue(Book.objects.filter(title="Test Title").exists())

    @patch("library.services.epub.read_epub")
    def test_zip_duplicate_epub_does_not_refresh_metadata_from_sidecar_opf(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")

        opf1 = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>First Title</dc:title>
</metadata></package>
"""
        opf2 = """<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
  <dc:title>Second Title</dc:title>
</metadata></package>
"""

        def upload_zip(opf_xml: str):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("dir/book.epub", b"dup-bytes")
                zf.writestr("dir/metadata.opf", opf_xml)
            buf.seek(0)
            upload = SimpleUploadedFile("bundle.zip", buf.read(), content_type="application/zip")
            return cast_response(self.client.post("/api/v1/library/imports/", data={"file": upload}, format="multipart"))

        r1 = upload_zip(opf1)
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Book.objects.filter(title="First Title").exists())

        r2 = upload_zip(opf2)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        data2 = response_data_dict(r2)
        self.assertEqual(data2["duplicate_count"], 1)
        self.assertTrue(Book.objects.filter(title="First Title").exists())
        self.assertFalse(Book.objects.filter(title="Second Title").exists())

    @patch("library.services.epub.read_epub")
    def test_import_history_endpoints_are_not_supported(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="u1", password="pw")
        epub = SimpleUploadedFile("book.epub", b"x", content_type="application/epub+zip")
        created = cast_response(self.client.post("/api/v1/library/imports/", data={"file": epub}, format="multipart"))
        created_data = response_data_dict(created)
        run_id = created_data["run_id"]

        listing = cast_response(self.client.get("/api/v1/library/imports/"))
        self.assertEqual(listing.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        detail = cast_response(self.client.get(f"/api/v1/library/imports/{run_id}/"))
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)


class CappedZipCopyTests(IsolatedImportsMixin, APITestCase):
    def test_capped_copy_failure_removes_partial_extracted_file(self):
        destination = Path(self._imports_root) / "partial.epub"

        with self.assertRaises(ImportResourceLimitError):
            _copy_fileobj_capped(src=io.BytesIO(b"12345"), dst_path=destination, max_bytes=4)

        self.assertFalse(destination.exists())


def cast_response(resp) -> Response:
    return resp  # DRF test client returns Response already
