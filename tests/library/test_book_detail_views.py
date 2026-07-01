from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, cast

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from library.group_services import ensure_book_public_assignment
from library.models import Author, BookFile, Series
from library.models import BookGroupAssignment
from library.models import BookIdentifier

from tests.library.helpers import (
    create_manager_user,
    create_reader_user,
)
from tests.library.utils import IsolatedMediaRootMixin, paginated_results
from tests.utils.books import create_file_backed_book, create_fileless_book_for_integrity_edge_case

class BookGroupsSummaryVisibilityAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        from library.group_services import get_public_group
        from library.models import LibraryGroup

        self.public = get_public_group()

        self.reader = create_reader_user(
            username="reader", email="reader@example.com", password="pw"
        )

        self.manager = create_manager_user(
            username="manager", email="manager@example.com", password="pw"
        )

        self.hidden_group = LibraryGroup.objects.create(
            name="Hidden",
        )

        # Book is viewable via Public, but also assigned to an unlisted non-member group.
        self.book = create_file_backed_book(title="Public+Hidden", assign_public=False).book
        ensure_book_public_assignment(book=self.book, added_by=None)
        BookGroupAssignment.objects.create(book=self.book, group=self.hidden_group)

    def test_manager_sees_all_assigned_groups(self):
        self.client.login(username="manager", password="pw")
        response = cast(Response, self.client.get(f"/api/v1/library/books/{self.book.id}/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], response.data)
        groups = cast(list[dict[str, Any]], payload["groups"])
        names = {g["name"] for g in groups}
        self.assertIn("Common Room", names)
        self.assertIn("Hidden", names)

    def test_reader_only_sees_viewable_groups(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get(f"/api/v1/library/books/{self.book.id}/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], response.data)
        groups = cast(list[dict[str, Any]], payload["groups"])
        names = {g["name"] for g in groups}
        self.assertIn("Common Room", names)
        self.assertNotIn("Hidden", names)
