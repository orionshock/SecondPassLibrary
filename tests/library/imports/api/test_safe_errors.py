from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
import zipfile

from tests.library.imports.helpers import BaseImportApiTest
from tests.utils.responses import payload_list, response_data_dict, assert_response


pytestmark = [pytest.mark.filesystem, pytest.mark.integration]


class ImportApiSafeErrorTests(BaseImportApiTest):
    @patch("library.imports.epub.epub.read_epub")
    def test_single_epub_failure_message_does_not_expose_temp_path(
        self, mock_read_epub
    ):
        mock_read_epub.side_effect = ValueError(
            r"Failed parsing C:\projects\SecondPassLibrary\userdata\imports\jobs\secret\bad.epub"
        )
        self._login_librarian()

        epub = SimpleUploadedFile(
            "bad.epub", b"not-an-epub", content_type="application/epub+zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": epub}, format="multipart"
            )
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)
        item = payload_list(data, "items")[0]
        self.assertEqual(item["status"], "failed")
        self.assertEqual(item["message"], "Invalid or unsupported EPUB file.")
        self.assertNotIn("SecondPassLibrary", item["message"])
        self.assertNotIn("userdata", item["message"])
        self.assertNotIn("bad.epub", item["message"])

    @patch("library.imports.epub.epub.read_epub")
    def test_zip_member_failure_message_does_not_expose_member_path_or_temp_path(
        self, mock_read_epub
    ):
        mock_read_epub.side_effect = ValueError(
            r"Failed parsing member private/nested/leaky.epub at C:\tmp\jobs\abc\extracted\file.epub"
        )
        self._login_librarian()

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("private/nested/leaky.epub", b"not-an-epub")
        buf.seek(0)

        upload = SimpleUploadedFile(
            "bundle.zip", buf.read(), content_type="application/zip"
        )
        with self.assertLogs("library.imports.upload", level="WARNING") as captured:
            response = assert_response(
                self.client.post(
                    "/api/v1/library/imports/",
                    data={"file": upload},
                    format="multipart",
                )
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)
        item = payload_list(data, "items")[0]
        self.assertEqual(item["status"], "failed")
        self.assertEqual(item["source_name"], "leaky.epub")
        self.assertEqual(item["message"], "Invalid or unsupported EPUB file.")
        self.assertNotIn("private/nested", item["message"])
        self.assertNotIn("C:\\tmp", item["message"])
        self.assertNotIn("leaky.epub", item["message"])

        failed_item_logs = [
            record
            for record in captured.records
            if record.getMessage().startswith("library import item failed ")
        ]
        self.assertEqual(len(failed_item_logs), 1)
        failed_item_log = failed_item_logs[0]
        self.assertIn("source_name=leaky.epub", failed_item_log.getMessage())
        self.assertIn("status=failed", failed_item_log.getMessage())
        self.assertIn(
            "message=Invalid or unsupported EPUB file.", failed_item_log.getMessage()
        )
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
