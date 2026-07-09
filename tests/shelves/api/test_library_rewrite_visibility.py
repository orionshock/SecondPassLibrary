from __future__ import annotations

import pytest
from rest_framework import status

from library.groups.services import add_book_to_group
from library.models import LibraryGroup, LibraryGroupMembership
from shelves.models import Shelf, ShelfItem
from tests.shelves.helpers import BaseShelvesAPITest
from tests.utils.books import create_file_backed_book
from tests.utils.responses import assert_response, response_data_dict, response_data_list

pytestmark = [pytest.mark.integration]


class ShelfLibraryReWriteVisibilityTests(BaseShelvesAPITest):
    def test_user_owned_shelf_add_uses_global_visible_books(self):
        self.client.login(username="reader", password="pw")
        shelf = self._create_user_shelf()

        visible = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf.id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
            )
        )
        self.assertEqual(visible.status_code, status.HTTP_201_CREATED)

        hidden = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf.id}/items/",
                data={"book": str(self.book_hidden.id)},
                format="json",
            )
        )
        self.assertEqual(hidden.status_code, status.HTTP_403_FORBIDDEN)

    def test_group_owned_shelf_add_uses_owner_group_universe(self):
        other_group = LibraryGroup.objects.create(name="Other group")
        LibraryGroupMembership.objects.create(user=self.curator, group=other_group)
        other_book = create_file_backed_book(title="Other group book", assign_public=False).book
        add_book_to_group(actor=self.owner, book=other_book, group=other_group)

        self.client.login(username="curator", password="pw")
        shelf = self._create_group_shelf()

        owner_group_book = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf.id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
            )
        )
        self.assertEqual(owner_group_book.status_code, status.HTTP_201_CREATED)

        wrong_group_book = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf.id}/items/",
                data={"book": str(other_book.id)},
                format="json",
            )
        )
        self.assertEqual(wrong_group_book.status_code, status.HTTP_403_FORBIDDEN)

    def test_already_on_shelf_book_is_rejected(self):
        self.client.login(username="reader", password="pw")
        shelf = self._create_user_shelf()
        url = f"/api/v1/shelves/{shelf.id}/items/"
        data = {"book": str(self.book_in_group.id)}

        first = assert_response(self.client.post(url, data=data, format="json"))
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        duplicate = assert_response(self.client.post(url, data=data, format="json"))
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

    def test_item_list_excludes_hidden_books(self):
        self.client.login(username="reader", password="pw")
        shelf = self._create_user_shelf()
        ShelfItem.objects.create(
            shelf=shelf, book=self.book_in_group, position=0, added_by=self.reader
        )
        ShelfItem.objects.create(
            shelf=shelf, book=self.book_hidden, position=1, added_by=self.reader
        )

        response = assert_response(self.client.get(f"/api/v1/shelves/{shelf.id}/items/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["book"]["title"] for row in response_data_list(response)],
            [self.book_in_group.title],
        )

    def test_group_shelf_items_are_scoped_to_owner_group(self):
        other_group = LibraryGroup.objects.create(name="Other visible group")
        LibraryGroupMembership.objects.create(user=self.reader, group=other_group)
        other_book = create_file_backed_book(title="Visible elsewhere", assign_public=False).book
        add_book_to_group(actor=self.owner, book=other_book, group=other_group)
        shelf = Shelf.objects.create(
            name="Group shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
            created_by=self.curator,
        )
        ShelfItem.objects.create(
            shelf=shelf, book=self.book_in_group, position=0, added_by=self.curator
        )
        ShelfItem.objects.create(shelf=shelf, book=other_book, position=1, added_by=self.curator)

        self.client.login(username="reader", password="pw")
        detail = assert_response(self.client.get(f"/api/v1/shelves/{shelf.id}/"))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

        items = assert_response(self.client.get(f"/api/v1/shelves/{shelf.id}/items/"))
        self.assertEqual(items.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["book"]["title"] for row in response_data_list(items)],
            [self.book_in_group.title],
        )

    def test_shelf_item_count_excludes_hidden_books(self):
        shelf = Shelf.objects.create(
            name="Mixed shelf",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            created_by=self.reader,
        )
        ShelfItem.objects.create(
            shelf=shelf, book=self.book_in_group, position=0, added_by=self.reader
        )
        ShelfItem.objects.create(
            shelf=shelf, book=self.book_hidden, position=1, added_by=self.reader
        )

        self.client.login(username="reader", password="pw")
        detail = assert_response(self.client.get(f"/api/v1/shelves/{shelf.id}/"))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(detail)["item_count"], 1)

    def test_group_shelf_item_count_excludes_books_removed_from_owner_group(self):
        shelf = Shelf.objects.create(
            name="Group shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
            created_by=self.curator,
        )
        ShelfItem.objects.create(
            shelf=shelf, book=self.book_in_group, position=0, added_by=self.curator
        )
        from library.groups.services import remove_book_from_group

        remove_book_from_group(actor=self.owner, book=self.book_in_group, group=self.group)

        self.client.login(username="reader", password="pw")
        detail = assert_response(self.client.get(f"/api/v1/shelves/{shelf.id}/"))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(detail)["item_count"], 0)
        self.assertTrue(ShelfItem.objects.filter(shelf=shelf, book=self.book_in_group).exists())

    def test_user_shelf_item_count_excludes_books_no_longer_visible_to_user(self):
        shelf = Shelf.objects.create(
            name="Access changed",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            created_by=self.reader,
        )
        ShelfItem.objects.create(
            shelf=shelf, book=self.book_in_group, position=0, added_by=self.reader
        )
        LibraryGroupMembership.objects.filter(user=self.reader, group=self.group).delete()

        self.client.login(username="reader", password="pw")
        detail = assert_response(self.client.get(f"/api/v1/shelves/{shelf.id}/"))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(detail)["item_count"], 0)

    def test_order_by_item_count_uses_visible_item_count(self):
        visible_shelf = Shelf.objects.create(
            name="Visible count",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            created_by=self.reader,
        )
        hidden_shelf = Shelf.objects.create(
            name="Hidden raw count",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            created_by=self.reader,
        )
        ShelfItem.objects.create(
            shelf=visible_shelf, book=self.book_in_group, position=0, added_by=self.reader
        )
        ShelfItem.objects.create(
            shelf=hidden_shelf, book=self.book_hidden, position=0, added_by=self.reader
        )
        hidden_2 = create_file_backed_book(title="Second hidden", assign_public=False).book
        add_book_to_group(actor=self.owner, book=hidden_2, group=self.hidden_group)
        ShelfItem.objects.create(shelf=hidden_shelf, book=hidden_2, position=1, added_by=self.reader)

        self.client.login(username="reader", password="pw")
        response = assert_response(self.client.get("/api/v1/shelves/?ordering=-item_count"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [(row["name"], row["item_count"]) for row in response_data_list(response)],
            [("Visible count", 1), ("Hidden raw count", 0)],
        )

    def _create_user_shelf(self) -> Shelf:
        response = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Personal shelf", "owner_type": Shelf.OWNER_TYPE_USER},
                format="json",
            )
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return Shelf.objects.get(pk=response_data_dict(response)["id"])

    def _create_group_shelf(self) -> Shelf:
        response = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "Group shelf",
                    "owner_type": Shelf.OWNER_TYPE_GROUP,
                    "owner_group": str(self.group.id),
                },
                format="json",
            )
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return Shelf.objects.get(pk=response_data_dict(response)["id"])
