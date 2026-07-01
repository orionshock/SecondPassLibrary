from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from library.group_services import ensure_book_public_assignment, ensure_user_public_membership
from library.models import Author, BookFile, Series
from library.models import BookGroupAssignment
from library.models import BookIdentifier

from tests.library.utils import IsolatedMediaRootMixin, paginated_results
from tests.utils.books import create_file_backed_book, create_fileless_book_for_integrity_edge_case

class BaseBookFileDownloadAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        ensure_user_public_membership(user=self.user)
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="testuser", password="testpass")

        self.author = Author.objects.create(name="Test Author")
        # Intentionally fileless: this test sets up a BookFile row with a fixed path/checksum.
        self.book = create_fileless_book_for_integrity_edge_case(title="Test Title", assign_public=False)
        self.book.authors.add(self.author)
        ensure_book_public_assignment(book=self.book, added_by=None)

        self.book_file = BookFile.objects.create(
            book=self.book,
            file="books/aa/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.epub",
            checksum="a" * 64,
            file_size=123,
            source_filename="source.epub",
        )

    def test_download_requires_existing_file(self):
        response = cast(
            Response,
            self.client.get(
                f"/api/v1/library/book-files/{self.book_file.id}/download/"
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

class BookFileDownloadAPITest(BaseBookFileDownloadAPITest):
    pass

class BookFileSerializerAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        ensure_user_public_membership(user=self.user)
        self.author = Author.objects.create(name="Test Author")
        # Intentionally fileless: this test sets up a BookFile row with a fixed path/checksum.
        self.book = create_fileless_book_for_integrity_edge_case(title="Test Title", assign_public=False)
        self.book.authors.add(self.author)
        ensure_book_public_assignment(book=self.book, added_by=None)
        self.book_file = BookFile.objects.create(
            book=self.book,
            file="books/aa/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.epub",
            checksum="a" * 64,
            file_size=123,
            source_filename="source.epub",
        )

    def test_book_file_api_output_hides_file_and_includes_download_url(self):
        self.client.login(username="testuser", password="testpass")
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/book-files/{self.book_file.id}/"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        data = cast(Mapping[str, Any], response.data)
        self.assertNotIn("file", data)
        self.assertIn("download_url", data)
        self.assertEqual(
            data["download_url"],
            f"http://testserver/api/v1/library/book-files/{self.book_file.id}/download/",
        )
