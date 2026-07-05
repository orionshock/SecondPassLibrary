from __future__ import annotations

from rest_framework import status
from rest_framework.test import APITestCase

from library.groups.services import ensure_book_public_assignment
from library.models import Author

from tests.library.helpers import (
    create_librarian_user,
    create_reader_user,
)
from tests.library.utils import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book
from tests.utils.responses import assert_response, response_data_dict


class LibraryPermissionsAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = create_reader_user(username="reader", password="pw")
        self.librarian = create_librarian_user(username="librarian", password="pw")

    def test_reader_cannot_create_book(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.post(
                "/api/v1/library/books/",
                data={"title": "X", "authors": [], "subjects": []},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_librarian_cannot_create_book(self):
        self.client.login(username="librarian", password="pw")
        response = assert_response(
            self.client.post(
                "/api/v1/library/books/",
                data={"title": "X", "authors": [], "subjects": []},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class BookPatchPermissionsAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.author = Author.objects.create(name="A Author")
        self.book = create_file_backed_book(
            title="Original title",
            assign_public=False,
            book_fields={"language": "en"},
        ).book
        self.book.authors.add(self.author)
        ensure_book_public_assignment(book=self.book, added_by=None)

        self.reader = create_reader_user(username="reader", password="pw")

        self.librarian = create_librarian_user(username="librarian", password="pw")

    def test_reader_cannot_patch_book_metadata(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={"title": "Nope"},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_librarian_can_patch_basic_book_metadata(self):
        self.client.login(username="librarian", password="pw")
        response = assert_response(
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={
                    "title": "Updated title",
                    "publisher": "Pub",
                    "published_date": "2018-01-23",
                    "subjects": ["A", "B"],
                    "series_index": 2,
                },
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_dict(response)
        self.assertEqual(data["title"], "Updated title")
        self.assertEqual(data["publisher"], "Pub")
        self.assertEqual(data["published_date"], "2018-01-23")
        self.assertEqual(data["subjects"], ["A", "B"])
        self.assertEqual(data["series_index"], "2.0")

    def test_librarian_can_patch_blank_subtitle(self):
        self.client.login(username="librarian", password="pw")
        response = assert_response(
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={"subtitle": ""},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response_data_dict(response)
        self.assertEqual(payload["subtitle"], "")

    def test_series_index_accepts_integer_or_one_decimal_and_rejects_invalid(self):
        self.client.login(username="librarian", password="pw")

        r1 = assert_response(
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={"series_index": 5},
                format="json",
            ),
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(r1)["series_index"], "5.0")

        r2 = assert_response(
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={"series_index": "5.1"},
                format="json",
            ),
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(r2)["series_index"], "5.1")

        r3 = assert_response(
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={"series_index": None},
                format="json",
            ),
        )
        self.assertEqual(r3.status_code, status.HTTP_200_OK)
        self.assertIsNone(response_data_dict(r3)["series_index"])

        r4 = assert_response(
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={"series_index": "5.12"},
                format="json",
            ),
        )
        self.assertEqual(r4.status_code, status.HTTP_400_BAD_REQUEST)

        r5 = assert_response(
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={"series_index": -1},
                format="json",
            ),
        )
        self.assertEqual(r5.status_code, status.HTTP_400_BAD_REQUEST)
