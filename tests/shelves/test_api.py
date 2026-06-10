from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from library.group_services import add_book_to_group, ensure_book_public_assignment, ensure_user_public_membership, get_public_group
from library.cover_services import set_book_cover_from_bytes
from library.models import Book, LibraryGroup, LibraryGroupMembership
from shelves.models import Shelf, ShelfItem
from tests.utils.books import create_file_backed_book


User = get_user_model()


class ShelvesAPITest(APITestCase):
    def setUp(self):
        self.public = get_public_group()

        self.owner = User.objects.create_superuser(
            username="owner",
            password="pw",
            email="o@example.com",
            first_name="Olivia",
            last_name="Owner",
        )
        ensure_user_public_membership(user=self.owner)

        self.reader = User.objects.create_user(
            username="reader",
            password="pw",
            email="reader@example.com",
            first_name="Riley",
            last_name="Reader",
        )
        ensure_user_public_membership(user=self.reader)
        profile, _ = UserProfile.objects.get_or_create(user=self.reader)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])

        self.other = User.objects.create_user(username="other", password="pw", first_name="Owen", last_name="Other")
        ensure_user_public_membership(user=self.other)

        self.group = LibraryGroup.objects.create(name="G")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.group, role=LibraryGroupMembership.ROLE_READER)
        self.curator = User.objects.create_user(username="curator", password="pw")
        ensure_user_public_membership(user=self.curator)
        LibraryGroupMembership.objects.create(
            user=self.curator,
            group=self.group,
            role=LibraryGroupMembership.ROLE_CURATOR,
        )

        self.librarian = User.objects.create_user(username="librarian", password="pw")
        ensure_user_public_membership(user=self.librarian)
        profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        self.book_in_group = create_file_backed_book(title="B1", assign_public=False).book
        add_book_to_group(actor=self.owner, book=self.book_in_group, group=self.group)

        self.book_public = create_file_backed_book(title="PB", assign_public=False).book
        ensure_book_public_assignment(book=self.book_public, added_by=None)

        self.hidden_group = LibraryGroup.objects.create(name="Hidden")
        self.book_hidden = create_file_backed_book(title="HB", assign_public=False).book
        add_book_to_group(actor=self.owner, book=self.book_hidden, group=self.hidden_group)

    def _assert_compact_user_payload(
        self,
        payload: Mapping[str, Any],
        *,
        user,
    ) -> None:
        self.assertEqual(payload["id"], user.pk)
        self.assertEqual(payload["username"], user.get_username())
        self.assertEqual(payload["first_name"], user.first_name or "")
        self.assertEqual(payload["last_name"], user.last_name or "")
        self.assertNotIn("email", payload)

    def _png_bytes(self, *, size=(12, 16)) -> bytes:
        from PIL import Image
        from io import BytesIO

        img = Image.new("RGB", size, color=(1, 2, 3))
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def test_create_user_shelf_and_list_visibility_private_vs_listed(self):
        self.client.login(username="reader", password="pw")
        r1 = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "Private", "owner_type": "user"}, format="json"))
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        private_id = cast(Mapping[str, Any], r1.data)["id"]
        private_owner = cast(Mapping[str, Any], cast(Mapping[str, Any], r1.data)["owner_user"])
        private_creator = cast(Mapping[str, Any], cast(Mapping[str, Any], r1.data)["created_by"])
        self._assert_compact_user_payload(private_owner, user=self.reader)
        self._assert_compact_user_payload(private_creator, user=self.reader)
        private_detail = cast(Response, self.client.get(f"/api/v1/shelves/{private_id}/"))
        self.assertEqual(private_detail.status_code, status.HTTP_200_OK)
        private_detail_payload = cast(Mapping[str, Any], private_detail.data)
        self._assert_compact_user_payload(cast(Mapping[str, Any], private_detail_payload["owner_user"]), user=self.reader)
        self._assert_compact_user_payload(cast(Mapping[str, Any], private_detail_payload["created_by"]), user=self.reader)

        r2 = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "Listed", "owner_type": "user", "visibility": "listed"}, format="json"))
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        listed_id = cast(Mapping[str, Any], r2.data)["id"]

        self.client.logout()
        self.client.login(username="other", password="pw")
        list_resp = cast(Response, self.client.get("/api/v1/shelves/"))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], list_resp.data)
        results = cast(list[dict[str, Any]], payload["results"])
        ids = {row["id"] for row in results}
        self.assertIn(listed_id, ids)
        self.assertNotIn(private_id, ids)
        listed_row = next(row for row in results if row["id"] == listed_id)
        owner_user = cast(Mapping[str, Any], listed_row["owner_user"])
        created_by = cast(Mapping[str, Any], listed_row["created_by"])
        self._assert_compact_user_payload(owner_user, user=self.reader)
        self._assert_compact_user_payload(created_by, user=self.reader)

    def test_group_shelf_visibility(self):
        # Owner can create a group shelf.
        self.client.login(username="owner", password="pw")
        create = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "GS", "owner_type": "group", "owner_group": str(self.group.id)}, format="json"))
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        shelf_id = cast(Mapping[str, Any], create.data)["id"]
        create_payload = cast(Mapping[str, Any], create.data)
        self.assertIsNone(create_payload["owner_user"])
        self._assert_compact_user_payload(cast(Mapping[str, Any], create_payload["created_by"]), user=self.owner)

        # Member can see it in list.
        self.client.logout()
        self.client.login(username="reader", password="pw")
        list_resp = cast(Response, self.client.get("/api/v1/shelves/"))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = cast(list[dict[str, Any]], cast(Mapping[str, Any], list_resp.data)["results"])
        self.assertIn(shelf_id, {r["id"] for r in results})
        group_row = next(row for row in results if row["id"] == shelf_id)
        self.assertIsNone(group_row["owner_user"])
        self._assert_compact_user_payload(cast(Mapping[str, Any], group_row["created_by"]), user=self.owner)
        detail = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        detail_payload = cast(Mapping[str, Any], detail.data)
        self.assertIsNone(detail_payload["owner_user"])
        self._assert_compact_user_payload(cast(Mapping[str, Any], detail_payload["created_by"]), user=self.owner)

        # Non-member cannot retrieve it (404).
        self.client.logout()
        self.client.login(username="other", password="pw")
        detail = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_filter_owner_group(self):
        self.client.login(username="owner", password="pw")
        created = cast(
            Response,
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "GS", "owner_type": "group", "owner_group": str(self.group.id)},
                format="json",
            ),
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        shelf_id = cast(Mapping[str, Any], created.data)["id"]

        list_resp = cast(Response, self.client.get(f"/api/v1/shelves/?owner_group={self.group.id}"))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = cast(list[dict[str, Any]], cast(Mapping[str, Any], list_resp.data)["results"])
        self.assertIn(shelf_id, {r["id"] for r in results})

    def test_list_filter_book_does_not_leak_private_user_shelves(self):
        # Create a private user shelf for reader and add book_in_group.
        self.client.login(username="reader", password="pw")
        created = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "P", "owner_type": "user"}, format="json"))
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        shelf_id = cast(Mapping[str, Any], created.data)["id"]
        add = cast(Response, self.client.post(f"/api/v1/shelves/{shelf_id}/items/", data={"book": str(self.book_in_group.id)}, format="json"))
        self.assertEqual(add.status_code, status.HTTP_201_CREATED)

        # Other user can view the book (Public membership), but must not see reader's private shelf.
        self.client.logout()
        self.client.login(username="other", password="pw")
        list_resp = cast(Response, self.client.get(f"/api/v1/shelves/?book={self.book_in_group.id}"))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = cast(list[dict[str, Any]], cast(Mapping[str, Any], list_resp.data)["results"])
        self.assertNotIn(shelf_id, {r["id"] for r in results})

    def test_list_filter_book_includes_matched_item_id(self):
        self.client.login(username="reader", password="pw")
        created = cast(
            Response,
            self.client.post("/api/v1/shelves/", data={"name": "S", "owner_type": "user"}, format="json"),
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        shelf_id = cast(Mapping[str, Any], created.data)["id"]

        add = cast(
            Response,
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_public.id)},
                format="json",
            ),
        )
        self.assertEqual(add.status_code, status.HTTP_201_CREATED)
        item_id = cast(Mapping[str, Any], add.data)["id"]

        list_resp = cast(Response, self.client.get(f"/api/v1/shelves/?book={self.book_public.id}"))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = cast(list[dict[str, Any]], cast(Mapping[str, Any], list_resp.data)["results"])

        row = next((r for r in results if r.get("id") == shelf_id), None)
        self.assertIsNotNone(row)
        self.assertEqual(cast(dict[str, Any], row).get("matched_item_id"), item_id)

    def test_can_edit_user_shelf_owner_true_other_false(self):
        self.client.login(username="reader", password="pw")
        created = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "P", "owner_type": "user"}, format="json"))
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        shelf_id = cast(Mapping[str, Any], created.data)["id"]

        detail = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Mapping[str, Any], detail.data)["can_edit"], True)

        self.client.logout()
        self.client.login(username="other", password="pw")
        detail2 = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail2.status_code, status.HTTP_404_NOT_FOUND)

        # Listed shelf should be visible but not editable to other users.
        self.client.logout()
        self.client.login(username="reader", password="pw")
        created2 = cast(
            Response,
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "L", "owner_type": "user", "visibility": "listed"},
                format="json",
            ),
        )
        self.assertEqual(created2.status_code, status.HTTP_201_CREATED)
        shelf2_id = cast(Mapping[str, Any], created2.data)["id"]

        self.client.logout()
        self.client.login(username="other", password="pw")
        detail3 = cast(Response, self.client.get(f"/api/v1/shelves/{shelf2_id}/"))
        self.assertEqual(detail3.status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Mapping[str, Any], detail3.data)["can_edit"], False)

    def test_put_shelf_behaves_like_partial_update(self):
        self.client.login(username="reader", password="pw")
        created = cast(
            Response,
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "Before",
                    "description": "Desc",
                    "owner_type": "user",
                    "visibility": "listed",
                },
                format="json",
            ),
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        shelf_id = cast(Mapping[str, Any], created.data)["id"]

        put = cast(
            Response,
            self.client.put(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "After"},
                format="json",
            ),
        )
        self.assertEqual(put.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], put.data)
        self.assertEqual(payload["name"], "After")
        # PUT behaves like PATCH here: omitted fields are preserved.
        self.assertEqual(payload["description"], "Desc")
        self.assertEqual(payload["visibility"], "listed")

    def test_can_edit_group_shelf_curator_true_reader_false(self):
        self.client.login(username="owner", password="pw")
        created = cast(
            Response,
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "GS", "owner_type": "group", "owner_group": str(self.group.id)},
                format="json",
            ),
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        shelf_id = cast(Mapping[str, Any], created.data)["id"]

        self.client.logout()
        self.client.login(username="curator", password="pw")
        detail = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Mapping[str, Any], detail.data)["can_edit"], True)

        self.client.logout()
        self.client.login(username="reader", password="pw")
        detail2 = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail2.status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Mapping[str, Any], detail2.data)["can_edit"], False)

    def test_can_edit_public_group_shelf_reader_false_librarian_true(self):
        self.client.login(username="owner", password="pw")
        created = cast(
            Response,
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "PGS", "owner_type": "group", "owner_group": str(self.public.id)},
                format="json",
            ),
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        shelf_id = cast(Mapping[str, Any], created.data)["id"]

        self.client.logout()
        self.client.login(username="reader", password="pw")
        detail = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Mapping[str, Any], detail.data)["can_edit"], False)

        self.client.logout()
        self.client.login(username="librarian", password="pw")
        detail2 = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail2.status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Mapping[str, Any], detail2.data)["can_edit"], True)

    def test_reader_cannot_create_group_shelf(self):
        self.client.login(username="reader", password="pw")
        resp = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "GS", "owner_type": "group", "owner_group": str(self.group.id)}, format="json"))
        self.assertIn(resp.status_code, {status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST})

    def test_group_shelf_with_listed_visibility_returns_400(self):
        self.client.login(username="owner", password="pw")
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "GS",
                    "owner_type": "group",
                    "owner_group": str(self.group.id),
                    "visibility": "listed",
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_group_filter_does_not_leak_to_non_member(self):
        self.client.login(username="owner", password="pw")
        create = cast(
            Response,
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "HiddenShelf", "owner_type": "group", "owner_group": str(self.hidden_group.id)},
                format="json",
            ),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)

        self.client.logout()
        self.client.login(username="reader", password="pw")
        list_resp = cast(Response, self.client.get(f"/api/v1/shelves/?owner_group={self.hidden_group.id}"))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = cast(list[dict[str, Any]], cast(Mapping[str, Any], list_resp.data)["results"])
        self.assertEqual(results, [])

    def test_add_and_list_items_filters_by_access(self):
        self.client.login(username="reader", password="pw")
        create = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "S", "owner_type": "user"}, format="json"))
        shelf_id = cast(Mapping[str, Any], create.data)["id"]

        add_ok = cast(Response, self.client.post(f"/api/v1/shelves/{shelf_id}/items/", data={"book": str(self.book_in_group.id)}, format="json"))
        self.assertEqual(add_ok.status_code, status.HTTP_201_CREATED)

        # Reader cannot add a book they cannot view.
        add_denied = cast(Response, self.client.post(f"/api/v1/shelves/{shelf_id}/items/", data={"book": str(self.book_hidden.id)}, format="json"))
        self.assertEqual(add_denied.status_code, status.HTTP_403_FORBIDDEN)

        items = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/items/"))
        self.assertEqual(items.status_code, status.HTTP_200_OK)
        items_payload = cast(Mapping[str, Any], items.data)
        results = cast(list[dict[str, Any]], items_payload["results"])
        self.assertEqual(len(results), 1)

    def test_shelf_items_include_book_cover_url_when_present(self):
        self.client.login(username="reader", password="pw")
        create = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "S", "owner_type": "user"}, format="json"))
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        shelf_id = cast(Mapping[str, Any], create.data)["id"]

        set_book_cover_from_bytes(book=self.book_in_group, data=self._png_bytes(), source="manual")

        add_ok = cast(Response, self.client.post(f"/api/v1/shelves/{shelf_id}/items/", data={"book": str(self.book_in_group.id)}, format="json"))
        self.assertEqual(add_ok.status_code, status.HTTP_201_CREATED)

        items = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/items/"))
        self.assertEqual(items.status_code, status.HTTP_200_OK)
        results = cast(list[dict[str, Any]], cast(Mapping[str, Any], items.data)["results"])
        self.assertEqual(len(results), 1)
        book = cast(dict[str, Any], results[0]["book"])
        self.assertIn("cover_url", book)
        self.assertIsInstance(book["cover_url"], str)
        self.assertTrue(str(book["cover_url"]).startswith("http://testserver/"))

    def test_item_patch_duplicate_position_canonicalizes_response_and_list(self):
        self.client.login(username="reader", password="pw")
        create = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "S", "owner_type": "user"}, format="json"))
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        shelf_id = cast(Mapping[str, Any], create.data)["id"]

        book_z = create_file_backed_book(title="Zulu", assign_public=False).book
        ensure_book_public_assignment(book=book_z, added_by=None)
        book_a = create_file_backed_book(title="Alpha", assign_public=False).book
        ensure_book_public_assignment(book=book_a, added_by=None)

        add_z = cast(Response, self.client.post(f"/api/v1/shelves/{shelf_id}/items/", data={"book": str(book_z.id)}, format="json"))
        self.assertEqual(add_z.status_code, status.HTTP_201_CREATED)
        add_a = cast(Response, self.client.post(f"/api/v1/shelves/{shelf_id}/items/", data={"book": str(book_a.id)}, format="json"))
        self.assertEqual(add_a.status_code, status.HTTP_201_CREATED)
        item_a_id = cast(Mapping[str, Any], add_a.data)["id"]

        patch = cast(
            Response,
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/items/{item_a_id}/",
                data={"position": 0},
                format="json",
            ),
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Mapping[str, Any], patch.data)["position"], 0)

        items = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/items/"))
        results = cast(list[dict[str, Any]], cast(Mapping[str, Any], items.data)["results"])
        self.assertEqual([(row["book"]["title"], row["position"]) for row in results], [("Alpha", 0), ("Zulu", 1)])

    def test_item_patch_position_moves_item_down_and_shifts_intervening_items(self):
        self.client.login(username="reader", password="pw")
        create = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "S", "owner_type": "user"}, format="json"))
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        shelf_id = cast(Mapping[str, Any], create.data)["id"]

        item_ids: dict[str, str] = {}
        for title in ["A", "B", "C", "D"]:
            book = create_file_backed_book(title=title, assign_public=False).book
            ensure_book_public_assignment(book=book, added_by=None)
            added = cast(
                Response,
                self.client.post(
                    f"/api/v1/shelves/{shelf_id}/items/",
                    data={"book": str(book.id)},
                    format="json",
                ),
            )
            self.assertEqual(added.status_code, status.HTTP_201_CREATED)
            item_ids[title] = str(cast(Mapping[str, Any], added.data)["id"])

        patch = cast(
            Response,
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/items/{item_ids['B']}/",
                data={"position": 3},
                format="json",
            ),
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Mapping[str, Any], patch.data)["position"], 3)

        items = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/items/"))
        results = cast(list[dict[str, Any]], cast(Mapping[str, Any], items.data)["results"])
        self.assertEqual(
            [(row["book"]["title"], row["position"]) for row in results],
            [("A", 0), ("C", 1), ("D", 2), ("B", 3)],
        )

    def test_item_patch_move_canonicalizes_legacy_duplicates_before_swapping(self):
        self.client.login(username="reader", password="pw")
        create = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "S", "owner_type": "user"}, format="json"))
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        shelf = Shelf.objects.get(pk=cast(Mapping[str, Any], create.data)["id"])

        books = [
            create_file_backed_book(title=title, assign_public=False).book
            for title in ["Gamma", "Zulu", "Alpha", "Omega"]
        ]
        for book in books:
            ensure_book_public_assignment(book=book, added_by=None)

        ShelfItem.objects.create(shelf=shelf, book=books[0], position=0, added_by=self.reader)
        target = ShelfItem.objects.create(shelf=shelf, book=books[1], position=1, added_by=self.reader)
        ShelfItem.objects.create(shelf=shelf, book=books[2], position=1, added_by=self.reader)
        ShelfItem.objects.create(shelf=shelf, book=books[3], position=3, added_by=self.reader)

        patch = cast(
            Response,
            self.client.patch(
                f"/api/v1/shelves/{shelf.id}/items/{target.id}/",
                data={"move": "up"},
                format="json",
            ),
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Mapping[str, Any], patch.data)["position"], 1)

        items = cast(Response, self.client.get(f"/api/v1/shelves/{shelf.id}/items/"))
        results = cast(list[dict[str, Any]], cast(Mapping[str, Any], items.data)["results"])
        self.assertEqual(
            [(row["book"]["title"], row["position"]) for row in results],
            [("Gamma", 0), ("Zulu", 1), ("Alpha", 2), ("Omega", 3)],
        )
