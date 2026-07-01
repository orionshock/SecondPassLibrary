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

class BookIdentifierCrudAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = User.objects.create_user(username="ident_reader", password="pw")
        ensure_user_public_membership(user=self.reader)

        self.librarian = User.objects.create_user(username="ident_librarian", password="pw")
        ensure_user_public_membership(user=self.librarian)
        profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        self.book = create_file_backed_book(title="Book With Idents", assign_public=False).book
        ensure_book_public_assignment(book=self.book, added_by=None)

    def test_book_payload_identifiers_include_id(self):
        BookIdentifier.objects.create(book=self.book, scheme=BookIdentifier.SCHEME_UUID, value="abc", source="manual")
        self.client.login(username="ident_reader", password="pw")
        resp = cast(Response, self.client.get(f"/api/v1/library/books/{self.book.id}/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], resp.data)
        self.assertIsInstance(payload["identifiers"], list)
        self.assertIn("id", payload["identifiers"][0])

    def test_reader_can_list_identifiers_but_cannot_mutate(self):
        ident = BookIdentifier.objects.create(book=self.book, scheme=BookIdentifier.SCHEME_UUID, value="abc", source="manual")

        self.client.login(username="ident_reader", password="pw")
        r_list = cast(Response, self.client.get(f"/api/v1/library/books/{self.book.id}/identifiers/"))
        self.assertEqual(r_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(cast(list, r_list.data)), 1)

        r_create = cast(
            Response,
            self.client.post(
                f"/api/v1/library/books/{self.book.id}/identifiers/",
                data={"scheme": "uuid", "value": "def", "source": "manual", "is_primary": False},
                format="json",
            ),
        )
        self.assertEqual(r_create.status_code, status.HTTP_403_FORBIDDEN)

        r_patch = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/identifiers/{ident.id}/",
                data={"source": "nope"},
                format="json",
            ),
        )
        self.assertEqual(r_patch.status_code, status.HTTP_403_FORBIDDEN)

        r_delete = cast(Response, self.client.delete(f"/api/v1/library/books/{self.book.id}/identifiers/{ident.id}/"))
        self.assertEqual(r_delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_librarian_can_create_patch_delete_and_duplicates_return_400(self):
        self.client.login(username="ident_librarian", password="pw")

        r1 = cast(
            Response,
            self.client.post(
                f"/api/v1/library/books/{self.book.id}/identifiers/",
                data={"scheme": "isbn_13", "value": "9780123456472", "source": "manual", "is_primary": True},
                format="json",
            ),
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        ident_id = cast(Mapping[str, Any], r1.data)["id"]

        r_dup = cast(
            Response,
            self.client.post(
                f"/api/v1/library/books/{self.book.id}/identifiers/",
                data={"scheme": "isbn_13", "value": "9780123456472", "source": "manual", "is_primary": False},
                format="json",
            ),
        )
        self.assertEqual(r_dup.status_code, status.HTTP_400_BAD_REQUEST)

        r_patch = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/identifiers/{ident_id}/",
                data={"source": "edited"},
                format="json",
            ),
        )
        self.assertEqual(r_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Mapping[str, Any], r_patch.data)["source"], "edited")

        # Identifier edits should not automatically change Book.isbn
        self.book.refresh_from_db()
        self.assertEqual(self.book.isbn, "")

        r_delete = cast(Response, self.client.delete(f"/api/v1/library/books/{self.book.id}/identifiers/{ident_id}/"))
        self.assertEqual(r_delete.status_code, status.HTTP_204_NO_CONTENT)
