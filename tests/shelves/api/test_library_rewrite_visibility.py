from __future__ import annotations

import pytest
from rest_framework import status

from library.groups.book_assignments import add_book_to_group
from library.models import (
    Author,
    BookAuthor,
    BookIdentifier,
    BookSeries,
    LibraryGroup,
    LibraryGroupMembership,
    Series,
)
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
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)

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
        self.assertEqual(wrong_group_book.status_code, status.HTTP_404_NOT_FOUND)

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

    def test_owner_patch_of_retained_unavailable_item_returns_not_found_without_book_data(self):
        self.client.login(username="reader", password="pw")
        shelf = self._create_user_shelf()
        author = Author.objects.create(name="Private Author")
        series = Series.objects.create(name="Private Series")
        BookAuthor.objects.create(book=self.book_in_group, author=author, position=0)
        BookSeries.objects.create(
            book=self.book_in_group,
            series=series,
            series_index="4.00",
        )
        identifier = BookIdentifier.objects.create(
            book=self.book_in_group,
            scheme=BookIdentifier.SCHEME_ASIN,
            value="PRIVATE-IDENTIFIER",
        )
        self.book_in_group.cover_file = "covers/private-cover.jpg"
        self.book_in_group.save(update_fields=["cover_file", "updated_at"])
        item = ShelfItem.objects.create(
            shelf=shelf,
            book=self.book_in_group,
            position=0,
            added_by=self.reader,
        )
        LibraryGroupMembership.objects.filter(user=self.reader, group=self.group).delete()

        response = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf.id}/items/{item.id}/",
                data={"position": 0},
                format="json",
            )
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response_data_dict(response), {"detail": "Not found."})
        response_text = response.content.decode("utf-8")
        for private_value in (
            str(self.book_in_group.id),
            self.book_in_group.title,
            author.name,
            series.name,
            self.book_in_group.cover_file.name,
            identifier.value,
        ):
            self.assertNotIn(private_value, response_text)
        self.assertTrue(ShelfItem.objects.filter(pk=item.pk).exists())

    def test_owner_delete_of_retained_unavailable_item_succeeds_without_disclosure(self):
        self.client.login(username="reader", password="pw")
        shelf = self._create_user_shelf()
        item = ShelfItem.objects.create(
            shelf=shelf,
            book=self.book_in_group,
            position=0,
            added_by=self.reader,
        )
        LibraryGroupMembership.objects.filter(user=self.reader, group=self.group).delete()

        response = assert_response(
            self.client.delete(f"/api/v1/shelves/{shelf.id}/items/{item.id}/")
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(response.content, b"")
        self.assertFalse(ShelfItem.objects.filter(pk=item.pk).exists())

    def test_non_owner_cannot_mutate_retained_unavailable_item(self):
        shelf = Shelf.objects.create(
            name="Listed owner shelf",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            visibility=Shelf.VISIBILITY_LISTED,
            created_by=self.reader,
        )
        item = ShelfItem.objects.create(
            shelf=shelf,
            book=self.book_in_group,
            position=0,
            added_by=self.reader,
        )
        LibraryGroupMembership.objects.filter(user=self.reader, group=self.group).delete()
        self.client.login(username="other", password="pw")

        patch_response = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf.id}/items/{item.id}/",
                data={"position": 0},
                format="json",
            )
        )
        delete_response = assert_response(
            self.client.delete(f"/api/v1/shelves/{shelf.id}/items/{item.id}/")
        )

        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(ShelfItem.objects.filter(pk=item.pk).exists())

    def test_retained_item_reappears_when_owner_visibility_returns_before_cleanup(self):
        self.client.login(username="reader", password="pw")
        shelf = self._create_user_shelf()
        item = ShelfItem.objects.create(
            shelf=shelf,
            book=self.book_in_group,
            position=0,
            added_by=self.reader,
        )
        LibraryGroupMembership.objects.filter(user=self.reader, group=self.group).delete()

        hidden = assert_response(self.client.get(f"/api/v1/shelves/{shelf.id}/items/"))
        self.assertEqual(response_data_list(hidden), [])
        self.assertTrue(ShelfItem.objects.filter(pk=item.pk).exists())

        LibraryGroupMembership.objects.create(user=self.reader, group=self.group)
        restored = assert_response(self.client.get(f"/api/v1/shelves/{shelf.id}/items/"))

        rows = response_data_list(restored)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], str(item.id))
        self.assertEqual(rows[0]["book"]["id"], str(self.book_in_group.id))

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
        from library.groups.book_assignments import remove_book_from_group

        remove_book_from_group(actor=self.owner, book=self.book_in_group, group=self.group)

        self.client.login(username="reader", password="pw")
        detail = assert_response(self.client.get(f"/api/v1/shelves/{shelf.id}/"))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_dict(detail)["item_count"], 0)
        self.assertFalse(ShelfItem.objects.filter(shelf=shelf, book=self.book_in_group).exists())

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

    def test_book_filter_does_not_match_hidden_shelf_item(self):
        shelf = Shelf.objects.create(
            name="Hidden item shelf",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            created_by=self.reader,
        )
        ShelfItem.objects.create(
            shelf=shelf, book=self.book_hidden, position=0, added_by=self.reader
        )

        self.client.login(username="reader", password="pw")
        response = assert_response(self.client.get(f"/api/v1/shelves/?book={self.book_hidden.id}"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response_data_list(response)
        self.assertEqual(rows, [])
        self.assertFalse(any(row.get("matched_item_id") for row in rows))

    def test_public_group_shelf_is_not_visible_after_public_membership_removed(self):
        shelf = Shelf.objects.create(
            name="Public shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.public,
            created_by=self.owner,
        )
        ShelfItem.objects.create(
            shelf=shelf, book=self.book_public, position=0, added_by=self.owner
        )
        LibraryGroupMembership.objects.filter(user=self.reader, group=self.public).delete()
        self.assertTrue(
            LibraryGroupMembership.objects.filter(user=self.reader, group=self.group).exists()
        )

        self.client.login(username="reader", password="pw")
        list_response = assert_response(self.client.get("/api/v1/shelves/"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertNotIn(str(shelf.id), {row["id"] for row in response_data_list(list_response)})

        book_response = assert_response(self.client.get(f"/api/v1/shelves/?book={self.book_public.id}"))
        self.assertEqual(book_response.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_list(book_response), [])

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
