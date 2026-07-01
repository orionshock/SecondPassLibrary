from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from library.models import Author, BookFile, Series
from library.models import BookGroupAssignment
from library.models import BookIdentifier

from tests.library.helpers import (
    create_reader_user,
)
from tests.library.utils import IsolatedMediaRootMixin, paginated_results
from tests.utils.books import create_file_backed_book, create_fileless_book_for_integrity_edge_case

class LibraryAPITest(APITestCase):
    def setUp(self):
        self.user = create_reader_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")

    def test_authenticated_access_books(self):
        response = self.client.get("/api/v1/library/books/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_authenticated_access_authors(self):
        response = self.client.get("/api/v1/library/authors/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
