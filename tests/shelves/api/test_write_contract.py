from __future__ import annotations

from uuid import uuid4

import pytest
from rest_framework import status

from library.models import (
    Author,
    BookAuthor,
    BookCatalogTag,
    BookIdentifier,
    BookSeries,
    CatalogTag,
    Series,
)
from tests.shelves.helpers import BaseShelvesAPITest
from tests.utils.responses import assert_response, response_data_dict, response_data_list


pytestmark = [pytest.mark.integration]


class ShelfWriteContractTests(BaseShelvesAPITest):
    def _create_personal_shelf(self) -> str:
        response = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Shelf", "owner_type": "user"},
                format="json",
            )
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return str(response_data_dict(response)["id"])

    def test_shelf_item_book_uses_compact_book_contract(self):
        self.client.login(username="reader", password="pw")
        shelf_id = self._create_personal_shelf()
        book = self.book_in_group
        book.sort_title = "Book, The"
        book.subtitle = "A subtitle"
        book.language = "eng"
        book.publisher = "Publisher"
        book.published_year = 2025
        book.published_month = 2
        book.published_day = 28
        book.published_date_precision = "day"
        book.description = "Sensitive detail text"
        book.save()
        author = Author.objects.create(name="Author")
        BookAuthor.objects.create(book=book, author=author, position=0)
        series = Series.objects.create(name="Series")
        BookSeries.objects.create(book=book, series=series, series_index="1.5")
        tag = CatalogTag.objects.create(name="Catalog Tag")
        BookCatalogTag.objects.create(book=book, catalog_tag=tag)
        BookIdentifier.objects.create(
            book=book,
            scheme=BookIdentifier.SCHEME_OTHER,
            value="private-id",
            normalized_value="private-id",
        )

        added = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(book.id)},
                format="json",
            )
        )
        self.assertEqual(added.status_code, status.HTTP_201_CREATED)
        response = assert_response(
            self.client.get(f"/api/v1/shelves/{shelf_id}/items/")
        )
        nested_book = response_data_list(response)[0]["book"]

        self.assertEqual(
            set(nested_book),
            {
                "id",
                "title",
                "sort_title",
                "subtitle",
                "authors",
                "series",
                "catalog_tags",
                "language",
                "publisher",
                "published_year",
                "published_month",
                "published_day",
                "published_date_precision",
                "cover_url",
                "file_format",
            },
        )
        self.assertEqual(nested_book["series"]["series_index"], "1.5")
        self.assertEqual(nested_book["catalog_tags"][0]["name"], "Catalog Tag")
        self.assertEqual(nested_book["publisher"], "Publisher")
        self.assertEqual(nested_book["file_format"], "epub")
        for excluded in (
            "identifiers",
            "groups",
            "file",
            "checksum",
            "description",
            "storage",
            "source",
            "download_url",
        ):
            self.assertNotIn(excluded, nested_book)

    def test_unknown_shelf_and_item_fields_are_rejected_without_mutation(self):
        self.client.login(username="reader", password="pw")
        create = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Rejected", "owner_type": "user", "random_field": True},
                format="json",
            )
        )
        self.assertEqual(create.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("random_field", response_data_dict(create))

        shelf_id = self._create_personal_shelf()
        patch = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"description": "Changed", "owner_type": "group"},
                format="json",
            )
        )
        self.assertEqual(patch.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("owner_type", response_data_dict(patch))
        detail = response_data_dict(
            assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        )
        self.assertEqual(detail["description"], "")

        item_add = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={
                    "book": str(self.book_in_group.id),
                    "book_id": str(self.book_in_group.id),
                },
                format="json",
            )
        )
        self.assertEqual(item_add.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("book_id", response_data_dict(item_add))

        valid_add = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
            )
        )
        item_id = response_data_dict(valid_add)["id"]
        item_patch = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                data={"move": "up", "random_field": True},
                format="json",
            )
        )
        self.assertEqual(item_patch.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("random_field", response_data_dict(item_patch))

    def test_name_length_is_validated_before_shelf_mutation(self):
        self.client.login(username="reader", password="pw")
        too_long = "x" * 256
        create = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": too_long, "owner_type": "user"},
                format="json",
            )
        )
        self.assertEqual(create.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response_data_dict(create))

        shelf_id = self._create_personal_shelf()
        patch = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": too_long, "description": "Should roll back"},
                format="json",
            )
        )
        self.assertEqual(patch.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response_data_dict(patch))
        detail = response_data_dict(
            assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        )
        self.assertEqual(detail["name"], "Shelf")
        self.assertEqual(detail["description"], "")

    def test_item_add_hides_missing_and_inaccessible_books(self):
        self.client.login(username="reader", password="pw")
        shelf_id = self._create_personal_shelf()
        malformed = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": "not-a-uuid"},
                format="json",
            )
        )
        self.assertEqual(malformed.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("book", response_data_dict(malformed))

        for book_id in (uuid4(), self.book_hidden.id):
            with self.subTest(book_id=book_id):
                response = assert_response(
                    self.client.post(
                        f"/api/v1/shelves/{shelf_id}/items/",
                        data={"book": str(book_id)},
                        format="json",
                    )
                )
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_group_owned_create_requires_owner_group(self):
        self.client.login(username="owner", password="pw")
        missing = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Group Shelf", "owner_type": "group"},
                format="json",
            )
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("owner_group", response_data_dict(missing))

        malformed = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "Group Shelf",
                    "owner_type": "group",
                    "owner_group": "not-a-uuid",
                },
                format="json",
            )
        )
        self.assertEqual(malformed.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("owner_group", response_data_dict(malformed))

        valid = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "Group Shelf",
                    "owner_type": "group",
                    "owner_group": str(self.group.id),
                },
                format="json",
            )
        )
        self.assertEqual(valid.status_code, status.HTTP_201_CREATED)
