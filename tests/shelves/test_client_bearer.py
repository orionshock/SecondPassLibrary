from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.client_api import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession, UserProfile
from accounts.services import get_or_create_profile
from library.group_services import get_public_group
from library.models import Book, LibraryGroup, LibraryGroupMembership
from tests.utils.books import create_file_backed_book


User = get_user_model()


class ShelvesClientBearerTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="u",
            email="u@example.com",
            password="pw",
            first_name="Uma",
            last_name="User",
        )
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])

        self.other = User.objects.create_user(username="o", email="o@example.com", password="pw")
        other_profile = get_or_create_profile(user=self.other)
        other_profile.role = UserProfile.ROLE_READER
        other_profile.save(update_fields=["role", "updated_at"])

        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="t",
            client_type="test",
            token_hash=hash_client_secret(token),
            last_seen_at=timezone.now(),
        )
        self._auth = f"Bearer {token}"

        self.public_group = get_public_group()
        self.group = LibraryGroup.objects.create(name="G")
        LibraryGroupMembership.objects.create(user=self.user, group=self.group, role=LibraryGroupMembership.ROLE_CURATOR)

        self.book_public = create_file_backed_book(title="Public book", assign_public=False).book
        cast(Any, self.book_public).group_assignments.create(group=self.public_group, added_by=self.user)
        self.book_in_group = create_file_backed_book(title="Group book", assign_public=False).book
        cast(Any, self.book_in_group).group_assignments.create(group=self.group, added_by=self.user)

        self.book_hidden = create_file_backed_book(title="Hidden", assign_public=False).book
        hidden_group = LibraryGroup.objects.create(name="Hidden")
        cast(Any, self.book_hidden).group_assignments.create(group=hidden_group, added_by=self.user)

    def test_bearer_can_create_personal_shelf(self):
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Mine", "owner_type": "user", "visibility": "private"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 201)
        data = cast(dict[str, Any], resp.data)
        self.assertEqual(data["owner_type"], "user")
        owner_user = cast(dict[str, Any], data["owner_user"])
        user_id = cast(int, getattr(self.user, "pk"))
        self.assertEqual(owner_user["id"], user_id)
        self.assertEqual(owner_user["first_name"], "Uma")
        self.assertEqual(owner_user["last_name"], "User")
        self.assertNotIn("email", owner_user)
        created_by = cast(dict[str, Any], data["created_by"])
        self.assertEqual(created_by["id"], user_id)
        self.assertEqual(created_by["first_name"], "Uma")
        self.assertEqual(created_by["last_name"], "User")
        self.assertNotIn("email", created_by)
        self.assertTrue(data["can_edit"])

    def test_bearer_cannot_create_group_shelf(self):
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "GS", "owner_type": "group", "owner_group": str(self.group.id)},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 403)

    def _create_personal_shelf_as_owner(self) -> str:
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "P", "owner_type": "user"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 201)
        data = cast(dict[str, Any], resp.data)
        return str(data["id"])

    def _create_group_shelf_with_item_as_session_user(self) -> tuple[str, str]:
        self.client.force_login(self.user)
        created = cast(
            Response,
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "GS", "owner_type": "group", "owner_group": str(self.group.id)},
                format="json",
            ),
        )
        self.assertEqual(created.status_code, 201)
        shelf_id = str(cast(dict[str, Any], created.data)["id"])

        added = cast(
            Response,
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
            ),
        )
        self.assertEqual(added.status_code, 201)
        item_id = str(cast(dict[str, Any], added.data)["id"])
        self.client.logout()
        return shelf_id, item_id

    def test_bearer_can_patch_own_personal_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()
        resp = cast(
            Response,
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "P2", "description": "d"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 200)
        data = cast(dict[str, Any], resp.data)
        self.assertEqual(data["name"], "P2")
        self.assertTrue(data["can_edit"])

    def test_bearer_put_behaves_like_partial_update_for_own_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()
        # Set initial description via PATCH first.
        patch1 = cast(
            Response,
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"description": "Before", "visibility": "listed"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(patch1.status_code, 200)

        put = cast(
            Response,
            self.client.put(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "After"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(put.status_code, 200)
        data = cast(dict[str, Any], put.data)
        self.assertEqual(data["name"], "After")
        # PUT behaves like PATCH: omitted fields are preserved.
        self.assertEqual(data["description"], "Before")
        self.assertEqual(data["visibility"], "listed")

    def test_bearer_cannot_patch_other_users_shelf(self):
        # Create a listed shelf for other using session auth (baseline behavior).
        self.client.logout()
        self.client.login(username="o", password="pw")
        created = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "O", "owner_type": "user", "visibility": "listed"}, format="json"))
        self.assertEqual(created.status_code, 201)
        shelf_id = str(cast(dict[str, Any], created.data)["id"])
        self.client.logout()

        resp = cast(
            Response,
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "Hacked"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 403)

    def test_bearer_cannot_delete_other_users_shelf(self):
        self.client.logout()
        self.client.login(username="o", password="pw")
        created = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "O", "owner_type": "user", "visibility": "listed"}, format="json"))
        self.assertEqual(created.status_code, 201)
        shelf_id = str(cast(dict[str, Any], created.data)["id"])
        self.client.logout()

        resp = cast(
            Response,
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 403)

    def test_bearer_can_delete_own_personal_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()
        resp = cast(
            Response,
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 204)

    def test_bearer_can_read_listed_other_users_shelf_but_not_edit(self):
        self.client.logout()
        self.client.login(username="o", password="pw")
        created = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "Listed", "owner_type": "user", "visibility": "listed"}, format="json"))
        shelf_id = str(cast(dict[str, Any], created.data)["id"])
        self.client.logout()

        list_resp = cast(Response, self.client.get("/api/v1/shelves/", HTTP_AUTHORIZATION=self._auth))
        self.assertEqual(list_resp.status_code, 200)
        list_data = cast(dict[str, Any], list_resp.data)
        results = cast(list[dict[str, Any]], list_data["results"])
        ids = {str(r["id"]) for r in results}
        self.assertIn(shelf_id, ids)
        row = next(r for r in results if str(r["id"]) == shelf_id)
        self.assertFalse(row["can_edit"])

        detail = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/", HTTP_AUTHORIZATION=self._auth))
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(cast(dict[str, Any], detail.data)["can_edit"])

    def test_bearer_cannot_read_private_other_users_shelf(self):
        self.client.logout()
        self.client.login(username="o", password="pw")
        created = cast(Response, self.client.post("/api/v1/shelves/", data={"name": "Private", "owner_type": "user", "visibility": "private"}, format="json"))
        shelf_id = str(cast(dict[str, Any], created.data)["id"])
        self.client.logout()

        list_resp = cast(Response, self.client.get("/api/v1/shelves/", HTTP_AUTHORIZATION=self._auth))
        self.assertEqual(list_resp.status_code, 200)
        list_data = cast(dict[str, Any], list_resp.data)
        ids = {str(r["id"]) for r in cast(list[dict[str, Any]], list_data["results"])}
        self.assertNotIn(shelf_id, ids)

        detail = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/", HTTP_AUTHORIZATION=self._auth))
        self.assertEqual(detail.status_code, 404)

    def test_bearer_can_read_visible_group_shelf_but_not_edit(self):
        shelf_id, _item_id = self._create_group_shelf_with_item_as_session_user()

        list_resp = cast(Response, self.client.get("/api/v1/shelves/", HTTP_AUTHORIZATION=self._auth))
        self.assertEqual(list_resp.status_code, 200)
        list_data = cast(dict[str, Any], list_resp.data)
        results = cast(list[dict[str, Any]], list_data["results"])
        row = next(r for r in results if str(r["id"]) == shelf_id)
        self.assertFalse(row["can_edit"])

        detail = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/", HTTP_AUTHORIZATION=self._auth))
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(cast(dict[str, Any], detail.data)["can_edit"])

        patch = cast(
            Response,
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "Nope"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(patch.status_code, 403)

        put = cast(
            Response,
            self.client.put(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "Nope2"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(put.status_code, 403)

        delete = cast(
            Response,
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(delete.status_code, 403)

    def test_bearer_cannot_manage_items_on_visible_group_shelf(self):
        shelf_id, item_id = self._create_group_shelf_with_item_as_session_user()

        add = cast(
            Response,
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_public.id)},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(add.status_code, 403)

        move = cast(
            Response,
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                data={"position": 0},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(move.status_code, 403)

        remove = cast(
            Response,
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(remove.status_code, 403)

    def test_session_auth_curator_can_edit_group_shelf(self):
        shelf_id, item_id = self._create_group_shelf_with_item_as_session_user()

        self.client.force_login(self.user)
        detail = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(cast(dict[str, Any], detail.data)["can_edit"])

        patch = cast(
            Response,
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "Session allowed"},
                format="json",
            ),
        )
        self.assertEqual(patch.status_code, 200)

        move = cast(
            Response,
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                data={"position": 0},
                format="json",
            ),
        )
        self.assertEqual(move.status_code, 200)

    def test_bearer_can_add_and_remove_accessible_book_on_own_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()

        add = cast(
            Response,
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(add.status_code, 201)
        item_id = str(cast(dict[str, Any], add.data)["id"])

        items = cast(Response, self.client.get(f"/api/v1/shelves/{shelf_id}/items/", HTTP_AUTHORIZATION=self._auth))
        self.assertEqual(items.status_code, 200)

        rm = cast(
            Response,
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(rm.status_code, 204)

    def test_bearer_cannot_add_inaccessible_book_to_own_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()
        add = cast(
            Response,
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_hidden.id)},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(add.status_code, 403)

    def test_bearer_can_reorder_items_in_own_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()
        add1 = cast(
            Response,
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(add1.status_code, 201)
        item_id = str(cast(dict[str, Any], add1.data)["id"])

        patch = cast(
            Response,
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                data={"position": 5},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(cast(dict[str, Any], patch.data)["position"], 0)
