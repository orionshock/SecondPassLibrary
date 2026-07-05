from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

from accounts.models import UserProfile
from tests.library.imports.helpers import BaseImportApiTest, mock_epub
from tests.utils.responses import (
    assert_http_response,
    assert_response,
    response_data_dict,
)


pytestmark = [pytest.mark.filesystem, pytest.mark.integration]


class ImportApiResultsTests(BaseImportApiTest):
    @patch("library.imports.epub.epub.read_epub")
    def test_import_history_endpoints_are_not_supported(self, mock_read_epub):
        mock_read_epub.return_value = mock_epub()
        self.set_user_role(role=UserProfile.ROLE_LIBRARIAN)
        self.client.login(username="u1", password="pw")
        epub = SimpleUploadedFile(
            "book.epub", b"x", content_type="application/epub+zip"
        )
        created = assert_response(
            self.client.post(
                "/api/v1/library/imports/", data={"file": epub}, format="multipart"
            )
        )
        created_data = response_data_dict(created)
        run_id = created_data["run_id"]

        listing = assert_response(self.client.get("/api/v1/library/imports/"))
        self.assertEqual(listing.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        detail = assert_http_response(
            self.client.get(f"/api/v1/library/imports/{run_id}/")
        )
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)
