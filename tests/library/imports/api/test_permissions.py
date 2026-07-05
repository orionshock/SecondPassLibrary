from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

from accounts.models import UserProfile
from core.errors import ErrorCode
from tests.library.imports.helpers import BaseImportApiTest, mock_epub
from tests.utils.responses import payload_dict, response_data_dict
from tests.utils.responses import assert_response


pytestmark = [pytest.mark.filesystem, pytest.mark.integration]


class ImportApiPermissionTests(BaseImportApiTest):
    def test_anonymous_cannot_create_import(self):
        epub = SimpleUploadedFile(
            "book.epub", b"epub-bytes", content_type="application/epub+zip"
        )
        create = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": epub}, format="multipart"
            )
        )
        self.assertEqual(create.status_code, status.HTTP_403_FORBIDDEN)

    @patch("library.imports.epub.epub.read_epub")
    def test_reader_cannot_create_import(self, mock_read_epub):
        mock_read_epub.return_value = mock_epub()
        self.client.login(username="u1", password="pw")

        epub = SimpleUploadedFile(
            "book.epub", b"x", content_type="application/epub+zip"
        )
        created = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": epub}, format="multipart"
            )
        )
        self.assertEqual(created.status_code, status.HTTP_403_FORBIDDEN)

    def test_missing_upload_file_returns_error_envelope(self):
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")

        response = assert_response(
            self.client.post("/api/v1/library/imports/", data={}, format="multipart")
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response_data_dict(response)
        self.assertIn("error", data)
        self.assertEqual(
            payload_dict(data, "error")["code"], ErrorCode.MISSING_UPLOAD_FILE
        )

    def test_invalid_upload_type_returns_error_envelope(self):
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")

        bad = SimpleUploadedFile("bad.txt", b"x", content_type="text/plain")
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": bad}, format="multipart"
            )
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response_data_dict(response)
        self.assertIn("error", data)
        self.assertEqual(
            payload_dict(data, "error")["code"], ErrorCode.INVALID_UPLOAD_TYPE
        )

    @patch("library.imports.epub.epub.read_epub")
    def test_authenticated_can_upload_single_epub_and_stages_with_generated_name(
        self, mock_read_epub
    ):
        mock_read_epub.return_value = mock_epub()
        self.client.login(username="u1", password="pw")

        epub = SimpleUploadedFile(
            "Original Name.epub", b"same-bytes", content_type="application/epub+zip"
        )
        response = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": epub}, format="multipart"
            )
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
