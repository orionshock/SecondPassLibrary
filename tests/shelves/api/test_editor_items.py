from __future__ import annotations

import pytest
from rest_framework import status

from library.models import (
    Author,
    BookAuthor,
    BookIdentifier,
    BookSeries,
    LibraryGroupMembership,
    Series,
)
from shelves.models import Shelf, ShelfItem
from tests.shelves.helpers import BaseShelvesAPITest
from tests.utils.books import create_file_backed_book
from tests.utils.library_visibility import ensure_public_book_assignment
from tests.utils.responses import assert_response, response_data_dict, response_data_list


pytestmark = [pytest.mark.integration]


class ShelfEditorItemViewTests(BaseShelvesAPITest):
    def _mixed_personal_shelf(self) -> tuple[Shelf, ShelfItem, ShelfItem, ShelfItem]:
        shelf = Shelf.objects.create(
            name="Editor inventory",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            created_by=self.reader,
        )
        first = ShelfItem.objects.create(
            shelf=shelf, book=self.book_public, position=0, added_by=self.reader
        )
        hidden = ShelfItem.objects.create(
            shelf=shelf, book=self.book_in_group, position=1, added_by=self.reader
        )
        last_book = create_file_backed_book(title="Last visible", assign_public=False).book
        ensure_public_book_assignment(last_book)
        last = ShelfItem.objects.create(
            shelf=shelf, book=last_book, position=2, added_by=self.reader
        )
        LibraryGroupMembership.objects.filter(user=self.reader, group=self.group).delete()
        return shelf, first, hidden, last

    def test_edit_view_includes_safe_unavailable_placeholder_and_counts(self):
        shelf, first, hidden, last = self._mixed_personal_shelf()
        author = Author.objects.create(name="Hidden Author")
        series = Series.objects.create(name="Hidden Series")
        BookAuthor.objects.create(book=hidden.book, author=author, position=0)
        BookSeries.objects.create(book=hidden.book, series=series, series_index="2.0")
        identifier = BookIdentifier.objects.create(
            book=hidden.book,
            scheme=BookIdentifier.SCHEME_ASIN,
            value="HIDDEN-IDENTIFIER",
        )

        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.get(f"/api/v1/shelves/{shelf.id}/items/?view=edit&page_size=2")
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response_data_dict(response)
        self.assertEqual(payload["count"], 3)
        self.assertEqual(payload["visible_item_count"], 2)
        self.assertEqual(payload["unavailable_item_count"], 1)
        self.assertIsNotNone(payload["next"])
        rows = response_data_list(response)
        self.assertEqual([row["id"] for row in rows], [str(first.id), str(hidden.id)])
        self.assertFalse(rows[0]["unavailable"])
        self.assertEqual(rows[0]["book"]["id"], str(first.book_id))
        placeholder = rows[1]
        self.assertEqual(
            set(placeholder),
            {"id", "shelf", "book", "position", "unavailable", "added_by"},
        )
        self.assertEqual(placeholder["id"], str(hidden.id))
        self.assertEqual(str(placeholder["shelf"]), str(shelf.id))
        self.assertIsNone(placeholder["book"])
        self.assertEqual(placeholder["position"], 1)
        self.assertTrue(placeholder["unavailable"])
        response_text = response.content.decode("utf-8")
        for private_value in (
            str(hidden.book_id),
            hidden.book.title,
            author.name,
            series.name,
            identifier.value,
        ):
            self.assertNotIn(private_value, response_text)
        self.assertTrue(ShelfItem.objects.filter(pk=last.pk).exists())

    def test_normal_view_still_omits_unavailable_items(self):
        shelf, first, _hidden, last = self._mixed_personal_shelf()
        self.client.login(username="reader", password="pw")

        response = assert_response(self.client.get(f"/api/v1/shelves/{shelf.id}/items/"))

        payload = response_data_dict(response)
        self.assertEqual(payload["count"], 2)
        self.assertNotIn("visible_item_count", payload)
        self.assertEqual(
            [row["id"] for row in response_data_list(response)],
            [str(first.id), str(last.id)],
        )

    def test_non_editor_cannot_request_edit_view_but_unreadable_shelf_is_not_found(self):
        listed = Shelf.objects.create(
            name="Listed",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            visibility=Shelf.VISIBILITY_LISTED,
            created_by=self.reader,
        )
        ShelfItem.objects.create(
            shelf=listed, book=self.book_public, position=0, added_by=self.reader
        )
        private = Shelf.objects.create(
            name="Private",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            created_by=self.reader,
        )
        self.client.login(username="other", password="pw")

        forbidden = assert_response(
            self.client.get(f"/api/v1/shelves/{listed.id}/items/?view=edit")
        )
        missing = assert_response(
            self.client.get(f"/api/v1/shelves/{private.id}/items/?view=edit")
        )

        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_view_and_non_position_edit_ordering_are_rejected(self):
        shelf, *_items = self._mixed_personal_shelf()
        self.client.login(username="reader", password="pw")

        invalid_view = assert_response(
            self.client.get(f"/api/v1/shelves/{shelf.id}/items/?view=editor")
        )
        invalid_order = assert_response(
            self.client.get(
                f"/api/v1/shelves/{shelf.id}/items/?view=edit&ordering=title"
            )
        )

        self.assertEqual(invalid_view.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("view", response_data_dict(invalid_view))
        self.assertEqual(invalid_order.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ordering", response_data_dict(invalid_order))


class ShelfHiddenItemOrderingTests(BaseShelvesAPITest):
    def _mixed_shelf(self) -> tuple[Shelf, ShelfItem, ShelfItem, ShelfItem]:
        shelf = Shelf.objects.create(
            name="Locked slots",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            created_by=self.reader,
        )
        books = []
        for title in ("A", "C"):
            book = create_file_backed_book(title=title, assign_public=False).book
            ensure_public_book_assignment(book)
            books.append(book)
        first = ShelfItem.objects.create(
            shelf=shelf, book=books[0], position=0, added_by=self.reader
        )
        hidden = ShelfItem.objects.create(
            shelf=shelf, book=self.book_in_group, position=1, added_by=self.reader
        )
        last = ShelfItem.objects.create(
            shelf=shelf, book=books[1], position=2, added_by=self.reader
        )
        LibraryGroupMembership.objects.filter(user=self.reader, group=self.group).delete()
        return shelf, first, hidden, last

    def _positions(self, shelf: Shelf) -> dict[object, int]:
        return dict(ShelfItem.objects.filter(shelf=shelf).values_list("id", "position"))

    def test_move_down_and_up_skip_locked_placeholder(self):
        shelf, first, hidden, last = self._mixed_shelf()
        self.client.login(username="reader", password="pw")

        down = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf.id}/items/{first.id}/",
                data={"move": "down"},
                format="json",
            )
        )
        self.assertEqual(down.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self._positions(shelf),
            {first.id: 2, hidden.id: 1, last.id: 0},
        )

        up = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf.id}/items/{first.id}/",
                data={"move": "up"},
                format="json",
            )
        )
        self.assertEqual(up.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self._positions(shelf),
            {first.id: 0, hidden.id: 1, last.id: 2},
        )

    def test_direct_position_and_explicit_add_position_reject_locked_slots(self):
        shelf, first, _hidden, _last = self._mixed_shelf()
        new_book = create_file_backed_book(title="D", assign_public=False).book
        ensure_public_book_assignment(new_book)
        self.client.login(username="reader", password="pw")

        direct = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf.id}/items/{first.id}/",
                data={"position": 2},
                format="json",
            )
        )
        explicit_add = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf.id}/items/",
                data={"book": str(new_book.id), "position": 0},
                format="json",
            )
        )

        self.assertEqual(direct.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("position", response_data_dict(direct))
        self.assertEqual(explicit_add.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("position", response_data_dict(explicit_add))

    def test_positionless_add_appends_after_all_stored_slots(self):
        shelf, _first, hidden, _last = self._mixed_shelf()
        new_book = create_file_backed_book(title="D", assign_public=False).book
        ensure_public_book_assignment(new_book)
        self.client.login(username="reader", password="pw")

        response = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf.id}/items/",
                data={"book": str(new_book.id)},
                format="json",
            )
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response_data_dict(response)["position"], 3)
        self.assertEqual(ShelfItem.objects.get(pk=hidden.pk).position, 1)

    def test_removing_visible_item_compacts_all_stored_slots(self):
        shelf, first, hidden, last = self._mixed_shelf()
        self.client.login(username="reader", password="pw")

        response = assert_response(
            self.client.delete(f"/api/v1/shelves/{shelf.id}/items/{first.id}/")
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            self._positions(shelf),
            {hidden.id: 0, last.id: 1},
        )
