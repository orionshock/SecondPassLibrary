from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from library.group_services import add_book_to_group, ensure_book_public_assignment, ensure_user_public_membership, get_public_group
from library.models import Book, LibraryGroup, LibraryGroupMembership
from shelves.models import Shelf


User = get_user_model()


class ShelvesAPITest(APITestCase):
    def setUp(self):
        self.public = get_public_group()

        self.owner = User.objects.create_superuser(username="owner", password="pw", email="o@example.com")
        ensure_user_public_membership(user=self.owner)

        self.reader = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.reader)
        profile, _ = UserProfile.objects.get_or_create(user=self.reader)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])

        self.other = User.objects.create_user(username="other", password="pw")
        ensure_user_public_membership(user=self.other)

        self.group = LibraryGroup.objects.create(name="G")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.group, role=LibraryGroupMembership.ROLE_READER)

        self.book_in_group = Book.objects.create(title="B1")
        add_book_to_group(actor=self.owner, book=self.book_in_group, group=self.group)

        self.book_public = Book.objects.create(title="PB")
        ensure_book_public_assignment(book=self.book_public, added_by=None)

        self.hidden_group = LibraryGroup.objects.create(name="Hidden")
        self.book_hidden = Book.objects.create(title="HB")
        add_book_to_group(actor=self.owner, book=self.book_hidden, group=self.hidden_group)

    def test_create_user_shelf_and_list_visibility_private_vs_listed(self):
        self.client.login(username="reader", password="pw")
        r1 = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "Private", "owner_type": "user"}, format="json"))
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        private_id = cast(Mapping[str, Any], r1.data)["id"]

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

    def test_group_shelf_visibility(self):
        # Owner can create a group shelf.
        self.client.login(username="owner", password="pw")
        create = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "GS", "owner_type": "group", "owner_group": str(self.group.id)}, format="json"))
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        shelf_id = cast(Mapping[str, Any], create.data)["id"]

        # Member can see it in list.
        self.client.logout()
        self.client.login(username="reader", password="pw")
        list_resp = cast(Response, self.client.get("/api/v1/shelves/"))
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        results = cast(list[dict[str, Any]], cast(Mapping[str, Any], list_resp.data)["results"])
        self.assertIn(shelf_id, {r["id"] for r in results})

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
