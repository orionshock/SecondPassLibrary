from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

from accounts.models import UserProfile
from library.models import Book, BookFile
from tests.library.imports.helpers import BaseImportApiTest, mock_epub
from tests.utils.responses import (
    payload_list,
    response_data_dict,
    assert_response,
)


pytestmark = [pytest.mark.filesystem, pytest.mark.integration]


class ImportApiEpubUploadTests(BaseImportApiTest):
    @patch("library.imports.epub.epub.read_epub")
    def test_librarian_can_upload_single_epub_and_receives_transient_result(
        self, mock_read_epub
    ):
        mock_read_epub.return_value = mock_epub()
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")

        epub = SimpleUploadedFile(
            "Original Name.epub", b"same-bytes", content_type="application/epub+zip"
        )
        with self.assertLogs("library.imports.upload", level="INFO") as captured:
            response = assert_response(
                self.client.post(
                    "/api/v1/library/imports/", data={"file": epub}, format="multipart"
                )
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
        item = payload_list(data, "items")[0]
        self.assertEqual(item["status"], "imported")
        self.assertIsNotNone(item["book"])
        self.assertIsNotNone(item["book_file"])
        self.assertEqual(Book.objects.count(), 1)
        self.assertEqual(BookFile.objects.count(), 1)

        messages = [record.getMessage() for record in captured.records]
        self.assertTrue(
            any(
                message.startswith("library import started ")
                and "source_type=epub" in message
                and "source_name=Original Name.epub" in message
                for message in messages
            )
        )
        self.assertTrue(
            any(
                message.startswith("library import finished ")
                and "total_found=1" in message
                and "item_count=1" in message
                and "imported_count=1" in message
                and "duplicate_count=0" in message
                and "failed_count=0" in message
                and "duration_ms=" in message
                for message in messages
            )
        )
        finish_log = next(
            record
            for record in captured.records
            if record.getMessage().startswith("library import finished ")
        )
        self.assertEqual(finish_log.run_id, data["run_id"])
        self.assertEqual(finish_log.source_type, "epub")
        self.assertEqual(finish_log.source_name, "Original Name.epub")
        self.assertEqual(finish_log.status, "completed")
        self.assertEqual(finish_log.total_found, 1)
        self.assertEqual(finish_log.imported_count, 1)
        self.assertEqual(finish_log.duplicate_count, 0)
        self.assertEqual(finish_log.failed_count, 0)

    @patch("library.imports.epub.epub.read_epub")
    def test_duplicate_epub_upload_creates_duplicate_item(self, mock_read_epub):
        mock_read_epub.return_value = mock_epub()
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")

        epub1 = SimpleUploadedFile(
            "book.epub", b"dup-bytes", content_type="application/epub+zip"
        )
        r1 = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": epub1}, format="multipart"
            )
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)

        epub2 = SimpleUploadedFile(
            "book.epub", b"dup-bytes", content_type="application/epub+zip"
        )
        r2 = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": epub2}, format="multipart"
            )
        )
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(r2)
        self.assertEqual(data["duplicate_count"], 1)
        self.assertEqual(data["imported_count"], 0)
        self.assertEqual(data["failed_count"], 0)
        self.assertEqual(payload_list(data, "items")[0]["status"], "duplicate")
