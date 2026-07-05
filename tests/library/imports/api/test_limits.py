from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
import zipfile

from core.errors import ErrorCode
from library.models import BookFile
from tests.library.imports.helpers import BaseImportApiTest, mock_epub
from tests.utils.responses import (
    payload_dict,
    response_data_dict,
    payload_list,
    assert_response,
)


pytestmark = [pytest.mark.filesystem, pytest.mark.integration]


class ImportApiLimitsTests(BaseImportApiTest):
    @patch("library.imports.epub.epub.read_epub")
    @patch("library.imports.upload.MAX_SINGLE_EPUB_UPLOAD_BYTES", 4)
    def test_oversized_single_epub_upload_is_rejected_before_import_parse(
        self, mock_read_epub
    ):
        self._login_librarian()

        epub = SimpleUploadedFile(
            "book.epub", b"12345", content_type="application/epub+zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": epub}, format="multipart"
            )
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response_data_dict(response)
        error = payload_dict(data, "error")
        self.assertEqual(error["code"], ErrorCode.INVALID_REQUEST)
        self.assertIn("EPUB upload exceeds", error["detail"])
        mock_read_epub.assert_not_called()
        self.assertEqual(BookFile.objects.count(), 0)

    @patch("library.imports.upload.MAX_ZIP_UPLOAD_BYTES", 4)
    def test_oversized_zip_upload_is_rejected(self):
        self._login_librarian()

        upload = SimpleUploadedFile(
            "bundle.zip", b"12345", content_type="application/zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": upload}, format="multipart"
            )
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response_data_dict(response)
        error = payload_dict(data, "error")
        self.assertEqual(error["code"], ErrorCode.INVALID_REQUEST)
        self.assertIn("ZIP upload exceeds", error["detail"])
        self.assertEqual(BookFile.objects.count(), 0)

    @patch("library.imports.upload.MAX_ZIP_MEMBERS", 1)
    def test_zip_with_too_many_members_is_rejected_safely(self):
        self._login_librarian()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("a.epub", b"a")
            zf.writestr("b.epub", b"b")
        buf.seek(0)

        upload = SimpleUploadedFile(
            "bundle.zip", buf.read(), content_type="application/zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": upload}, format="multipart"
            )
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response_data_dict(response)
        error = payload_dict(data, "error")
        self.assertEqual(error["code"], ErrorCode.INVALID_REQUEST)
        self.assertIn("ZIP contains more than 1 entries", error["detail"])
        self.assertEqual(BookFile.objects.count(), 0)

    @patch("library.imports.epub.epub.read_epub")
    @patch("library.imports.upload.MAX_ZIP_EPUB_MEMBER_BYTES", 4)
    def test_zip_epub_member_over_uncompressed_limit_is_skipped_safely(
        self, mock_read_epub
    ):
        self._login_librarian()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("big.epub", b"12345")
        buf.seek(0)

        upload = SimpleUploadedFile(
            "bundle.zip", buf.read(), content_type="application/zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": upload}, format="multipart"
            )
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)
        self.assertEqual(data["total_found"], 1)
        self.assertEqual(data["imported_count"], 0)
        self.assertEqual(data["failed_count"], 1)
        self.assertIn("uncompressed limit", payload_list(data, "items")[0]["message"])
        mock_read_epub.assert_not_called()

    @patch("library.imports.epub.epub.read_epub")
    @patch("library.imports.upload.MAX_ZIP_EPUB_MEMBER_BYTES", 10)
    @patch("library.imports.upload.MAX_ZIP_TOTAL_EPUB_BYTES", 8)
    def test_zip_total_epub_uncompressed_limit_is_enforced(self, mock_read_epub):
        mock_read_epub.return_value = mock_epub()
        self._login_librarian()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("a.epub", b"1111")
            zf.writestr("b.epub", b"22222")
        buf.seek(0)

        upload = SimpleUploadedFile(
            "bundle.zip", buf.read(), content_type="application/zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": upload}, format="multipart"
            )
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)
        self.assertEqual(data["total_found"], 2)
        self.assertEqual(data["imported_count"], 1)
        self.assertEqual(data["failed_count"], 1)
        self.assertEqual(mock_read_epub.call_count, 1)
        messages = [item["message"] for item in data["items"]]
        self.assertTrue(
            any("total uncompressed limit" in message for message in messages)
        )
