from __future__ import annotations

from rest_framework import status
from rest_framework.test import APITestCase

from library.groups.services import ensure_book_public_assignment
from library.models import BookIdentifier

from tests.library.helpers import (
    create_librarian_user,
    create_reader_user,
)
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book
from tests.utils.responses import (
    assert_response,
    response_data_dict,
    response_data_list,
)


class BookIdentifierCrudAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = create_reader_user(username="ident_reader", password="pw")

        self.librarian = create_librarian_user(
            username="ident_librarian", password="pw"
        )

        self.book = create_file_backed_book(
            title="Book With Idents", assign_public=False
        ).book
        ensure_book_public_assignment(book=self.book, added_by=None)

    def test_book_payload_identifiers_include_id(self):
        BookIdentifier.objects.create(
            book=self.book,
            scheme=BookIdentifier.SCHEME_UUID,
            value="abc",
            source="manual",
        )
        self.client.login(username="ident_reader", password="pw")
        resp = assert_response(
            self.client.get(f"/api/v1/library/books/{self.book.id}/")
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = response_data_dict(resp)
        self.assertIsInstance(payload["identifiers"], list)
        self.assertIn("id", payload["identifiers"][0])

    def test_reader_can_list_identifiers_but_cannot_mutate(self):
        ident = BookIdentifier.objects.create(
            book=self.book,
            scheme=BookIdentifier.SCHEME_UUID,
            value="abc",
            source="manual",
        )

        self.client.login(username="ident_reader", password="pw")
        r_list = assert_response(
            self.client.get(f"/api/v1/library/books/{self.book.id}/identifiers/")
        )
        self.assertEqual(r_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_data_list(r_list)), 1)

        r_create = assert_response(
            self.client.post(
                f"/api/v1/library/books/{self.book.id}/identifiers/",
                data={
                    "scheme": "uuid",
                    "value": "def",
                    "source": "manual",
                    "is_primary": False,
                },
                format="json",
            ),
        )
        self.assertEqual(r_create.status_code, status.HTTP_403_FORBIDDEN)

        r_patch = assert_response(
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/identifiers/{ident.id}/",
                data={"source": "nope"},
                format="json",
            ),
        )
        self.assertEqual(r_patch.status_code, status.HTTP_403_FORBIDDEN)

        r_delete = assert_response(
            self.client.delete(
                f"/api/v1/library/books/{self.book.id}/identifiers/{ident.id}/"
            )
        )
        self.assertEqual(r_delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_librarian_can_create_patch_delete_and_duplicates_return_400(self):
        self.client.login(username="ident_librarian", password="pw")

        r1 = assert_response(
            self.client.post(
                f"/api/v1/library/books/{self.book.id}/identifiers/",
                data={
                    "scheme": "isbn_13",
                    "value": "9780123456472",
                    "source": "manual",
                    "is_primary": True,
                },
                format="json",
            ),
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        ident_id = response_data_dict(r1)["id"]

        r_dup = assert_response(
            self.client.post(
                f"/api/v1/library/books/{self.book.id}/identifiers/",
                data={
                    "scheme": "isbn_13",
                    "value": "9780123456472",
                    "source": "manual",
                    "is_primary": False,
                },
                format="json",
            ),
        )
        self.assertEqual(r_dup.status_code, status.HTTP_400_BAD_REQUEST)

        r_patch = assert_response(
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/identifiers/{ident_id}/",
                data={"source": "edited"},
                format="json",
            ),
        )
        self.assertEqual(r_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(r_patch)["source"], "edited")

        # Identifier edits should not automatically change Book.isbn
        self.book.refresh_from_db()
        self.assertEqual(self.book.isbn, "")

        r_delete = assert_response(
            self.client.delete(
                f"/api/v1/library/books/{self.book.id}/identifiers/{ident_id}/"
            )
        )
        self.assertEqual(r_delete.status_code, status.HTTP_204_NO_CONTENT)
