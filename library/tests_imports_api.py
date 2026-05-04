from __future__ import annotations

import io
import os
import uuid
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test.utils import override_settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from django.core.files.uploadedfile import SimpleUploadedFile

from .models import ImportJob


class IsolatedImportsMixin:
    """
    Isolate staging under TestFiles/ so tests don't pollute real userdata/imports.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
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

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        __import__("shutil").rmtree(cls._imports_root, ignore_errors=True)
        __import__("shutil").rmtree(cls._media_root, ignore_errors=True)
        super().tearDownClass()


def _mock_epub() -> MagicMock:
    mock_book = MagicMock()
    mock_book.get_metadata.side_effect = lambda ns, name: {
        "title": [("Test Title", {})],
        "creator": [("Test Author", {})],
        "language": [("en", {})],
    }.get(name, [])
    return mock_book


class ImportJobsAPITest(IsolatedImportsMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pw")
        self.other = User.objects.create_user(username="u2", password="pw")

    def test_anonymous_cannot_create_or_list(self):
        epub = SimpleUploadedFile("book.epub", b"epub-bytes", content_type="application/epub+zip")
        create = cast_response(self.client.post("/api/v1/library/imports/", data={"file": epub}, format="multipart"))
        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)
        listing = cast_response(self.client.get("/api/v1/library/imports/"))
        self.assertEqual(listing.status_code, status.HTTP_403_FORBIDDEN)

    @patch("library.services.epub.read_epub")
    def test_authenticated_can_upload_single_epub_and_stages_with_generated_name(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        self.client.login(username="u1", password="pw")

        epub = SimpleUploadedFile("Original Name.epub", b"same-bytes", content_type="application/epub+zip")
        response = cast_response(self.client.post("/api/v1/library/imports/", data={"file": epub}, format="multipart"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(response.data)
        data = response.data

        self.assertIn("id", data)
        self.assertEqual(data["source_type"], "epub")
        self.assertEqual(data["source_filename"], "Original Name.epub")
        self.assertNotIn("staged_path", data)
        self.assertIn("items", data)
        self.assertEqual(len(data["items"]), 1)

        job = ImportJob.objects.get(pk=data["id"])
        self.assertTrue(job.staged_path)
        self.assertNotIn("Original Name", job.staged_path)
        self.assertTrue(job.staged_path.endswith(".epub"))

    @patch("library.services.epub.read_epub")
    def test_duplicate_epub_upload_creates_duplicate_item(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        self.client.login(username="u1", password="pw")

        epub1 = SimpleUploadedFile("book.epub", b"dup-bytes", content_type="application/epub+zip")
        r1 = cast_response(self.client.post("/api/v1/library/imports/", data={"file": epub1}, format="multipart"))
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)

        epub2 = SimpleUploadedFile("book.epub", b"dup-bytes", content_type="application/epub+zip")
        r2 = cast_response(self.client.post("/api/v1/library/imports/", data={"file": epub2}, format="multipart"))
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.data["duplicate_count"], 1)
        self.assertEqual(r2.data["imported_count"], 0)
        self.assertEqual(r2.data["failed_count"], 0)
        self.assertEqual(r2.data["items"][0]["status"], "duplicate")

    @patch("library.services.epub.read_epub")
    def test_authenticated_can_upload_zip_with_multiple_epubs_ignores_non_epub_and_path_traversal(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
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
        self.assertEqual(response.data["source_type"], "zip")
        self.assertEqual(response.data["total_found"], 2)
        self.assertEqual(len(response.data["items"]), 2)
        self.assertTrue(all(item["status"] in {"imported", "duplicate", "failed"} for item in response.data["items"]))

    @patch("library.services.epub.read_epub")
    def test_user_cannot_see_another_users_jobs(self, mock_read_epub):
        mock_read_epub.return_value = _mock_epub()
        self.client.login(username="u1", password="pw")
        epub = SimpleUploadedFile("book.epub", b"x", content_type="application/epub+zip")
        created = cast_response(self.client.post("/api/v1/library/imports/", data={"file": epub}, format="multipart"))
        job_id = created.data["id"]

        self.client.logout()
        self.client.login(username="u2", password="pw")
        listing = cast_response(self.client.get("/api/v1/library/imports/"))
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listing.data), 0)

        detail = cast_response(self.client.get(f"/api/v1/library/imports/{job_id}/"))
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)


def cast_response(resp) -> Response:
    return resp  # DRF test client returns Response already
