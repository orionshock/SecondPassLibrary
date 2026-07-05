from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.client_api import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession, UserProfile
from accounts.services import get_or_create_profile
from tests.testenv.filesystem import IsolatedMediaRootMixin
from library.groups.public_group import get_public_group
from library.models import LibraryGroup, LibraryGroupMembership
from tests.utils.books import create_file_backed_book
from tests.utils.responses import (
    assert_response,
    payload_dict,
    payload_list,
    response_data_dict,
)


User = get_user_model()


class ShelvesClientBearerTests(IsolatedMediaRootMixin, APITestCase):
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

        self.other = User.objects.create_user(
            username="o", email="o@example.com", password="pw"
        )
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
        LibraryGroupMembership.objects.create(
            user=self.user, group=self.group, is_curator=True
        )

        self.book_public = create_file_backed_book(
            title="Public book", assign_public=False
        ).book
        cast(Any, self.book_public).group_assignments.create(
            group=self.public_group, added_by=self.user
        )
        self.book_in_group = create_file_backed_book(
            title="Group book", assign_public=False
        ).book
        cast(Any, self.book_in_group).group_assignments.create(
            group=self.group, added_by=self.user
        )

        self.book_hidden = create_file_backed_book(
            title="Hidden", assign_public=False
        ).book
        hidden_group = LibraryGroup.objects.create(name="Hidden")
        cast(Any, self.book_hidden).group_assignments.create(
            group=hidden_group, added_by=self.user
        )

    def test_bearer_can_create_personal_shelf(self):
        resp = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Mine", "owner_type": "user", "visibility": "private"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 201)
        data = response_data_dict(resp)
        self.assertEqual(data["owner_type"], "user")
        owner_user = payload_dict(data, "owner_user")
        profile = get_or_create_profile(user=self.user)
        self.assertEqual(owner_user["profile_id"], profile.id)
        self.assertEqual(owner_user["first_name"], "Uma")
        self.assertEqual(owner_user["last_name"], "User")
        self.assertNotIn("id", owner_user)
        self.assertNotIn("email", owner_user)
        created_by = payload_dict(data, "created_by")
        self.assertEqual(created_by["profile_id"], profile.id)
        self.assertEqual(created_by["first_name"], "Uma")
        self.assertEqual(created_by["last_name"], "User")
        self.assertNotIn("id", created_by)
        self.assertNotIn("email", created_by)
        self.assertTrue(data["can_edit"])

    def test_bearer_cannot_create_group_shelf(self):
        resp = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "GS",
                    "owner_type": "group",
                    "owner_group": str(self.group.id),
                },
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 403)

    def _create_personal_shelf_as_owner(self) -> str:
        resp = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "P", "owner_type": "user"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 201)
        data = response_data_dict(resp)
        return str(data["id"])

    def _create_group_shelf_with_item_as_session_user(self) -> tuple[str, str]:
        self.client.force_login(self.user)
        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "GS",
                    "owner_type": "group",
                    "owner_group": str(self.group.id),
                },
                format="json",
            ),
        )
        self.assertEqual(created.status_code, 201)
        shelf_id = str(response_data_dict(created)["id"])

        added = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
            ),
        )
        self.assertEqual(added.status_code, 201)
        item_id = str(response_data_dict(added)["id"])
        self.client.logout()
        return shelf_id, item_id

    def test_bearer_can_patch_own_personal_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()
        resp = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "P2", "description": "d"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 200)
        data = response_data_dict(resp)
        self.assertEqual(data["name"], "P2")
        self.assertTrue(data["can_edit"])

    def test_bearer_put_behaves_like_partial_update_for_own_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()
        # Set initial description via PATCH first.
        patch1 = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"description": "Before", "visibility": "listed"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(patch1.status_code, 200)

        put = assert_response(
            self.client.put(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "After"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(put.status_code, 200)
        data = response_data_dict(put)
        self.assertEqual(data["name"], "After")
        # PUT behaves like PATCH: omitted fields are preserved.
        self.assertEqual(data["description"], "Before")
        self.assertEqual(data["visibility"], "listed")

    def test_bearer_cannot_patch_other_users_shelf(self):
        # Create a listed shelf for other using session auth (baseline behavior).
        self.client.logout()
        self.client.login(username="o", password="pw")
        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "O", "owner_type": "user", "visibility": "listed"},
                format="json",
            )
        )
        self.assertEqual(created.status_code, 201)
        shelf_id = str(response_data_dict(created)["id"])
        self.client.logout()

        resp = assert_response(
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
        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "O", "owner_type": "user", "visibility": "listed"},
                format="json",
            )
        )
        self.assertEqual(created.status_code, 201)
        shelf_id = str(response_data_dict(created)["id"])
        self.client.logout()

        resp = assert_response(
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 403)

    def test_bearer_can_delete_own_personal_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()
        resp = assert_response(
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 204)

    def test_bearer_can_read_listed_other_users_shelf_but_not_edit(self):
        self.client.logout()
        self.client.login(username="o", password="pw")
        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Listed", "owner_type": "user", "visibility": "listed"},
                format="json",
            )
        )
        shelf_id = str(response_data_dict(created)["id"])
        self.client.logout()

        list_resp = assert_response(
            self.client.get("/api/v1/shelves/", HTTP_AUTHORIZATION=self._auth)
        )
        self.assertEqual(list_resp.status_code, 200)
        list_data = response_data_dict(list_resp)
        results = payload_list(list_data, "results")
        ids = {str(r["id"]) for r in results}
        self.assertIn(shelf_id, ids)
        row = next(r for r in results if str(r["id"]) == shelf_id)
        self.assertFalse(row["can_edit"])

        detail = assert_response(
            self.client.get(
                f"/api/v1/shelves/{shelf_id}/", HTTP_AUTHORIZATION=self._auth
            )
        )
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(response_data_dict(detail)["can_edit"])

    def test_bearer_scope_filters_preserve_visibility_and_edit_contracts(self):
        personal_shelf_id = self._create_personal_shelf_as_owner()

        self.client.logout()
        self.client.login(username="o", password="pw")
        listed = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "Other Listed",
                    "owner_type": "user",
                    "visibility": "listed",
                },
                format="json",
            ),
        )
        listed_shelf_id = str(response_data_dict(listed)["id"])
        private = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Other Private", "owner_type": "user"},
                format="json",
            ),
        )
        private_shelf_id = str(response_data_dict(private)["id"])
        self.client.logout()
        group_shelf_id, _item_id = self._create_group_shelf_with_item_as_session_user()

        personal_response = assert_response(
            self.client.get(
                "/api/v1/shelves/?scope=personal",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        personal_rows = payload_list(response_data_dict(personal_response), "results")
        self.assertEqual(
            {str(row["id"]) for row in personal_rows},
            {personal_shelf_id},
        )
        self.assertTrue(personal_rows[0]["can_edit"])

        shared_response = assert_response(
            self.client.get(
                "/api/v1/shelves/?scope=shared",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        shared_rows = payload_list(response_data_dict(shared_response), "results")
        shared_by_id = {str(row["id"]): row for row in shared_rows}
        self.assertIn(listed_shelf_id, shared_by_id)
        self.assertIn(group_shelf_id, shared_by_id)
        self.assertNotIn(private_shelf_id, shared_by_id)
        self.assertFalse(shared_by_id[listed_shelf_id]["can_edit"])
        self.assertFalse(shared_by_id[group_shelf_id]["can_edit"])

    def test_bearer_cannot_read_private_other_users_shelf(self):
        self.client.logout()
        self.client.login(username="o", password="pw")
        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "Private", "owner_type": "user", "visibility": "private"},
                format="json",
            )
        )
        shelf_id = str(response_data_dict(created)["id"])
        self.client.logout()

        list_resp = assert_response(
            self.client.get("/api/v1/shelves/", HTTP_AUTHORIZATION=self._auth)
        )
        self.assertEqual(list_resp.status_code, 200)
        list_data = response_data_dict(list_resp)
        ids = {str(r["id"]) for r in payload_list(list_data, "results")}
        self.assertNotIn(shelf_id, ids)

        detail = assert_response(
            self.client.get(
                f"/api/v1/shelves/{shelf_id}/", HTTP_AUTHORIZATION=self._auth
            )
        )
        self.assertEqual(detail.status_code, 404)

    def test_bearer_can_read_visible_group_shelf_but_not_edit(self):
        shelf_id, _item_id = self._create_group_shelf_with_item_as_session_user()

        list_resp = assert_response(
            self.client.get("/api/v1/shelves/", HTTP_AUTHORIZATION=self._auth)
        )
        self.assertEqual(list_resp.status_code, 200)
        list_data = response_data_dict(list_resp)
        results = payload_list(list_data, "results")
        row = next(r for r in results if str(r["id"]) == shelf_id)
        self.assertFalse(row["can_edit"])

        detail = assert_response(
            self.client.get(
                f"/api/v1/shelves/{shelf_id}/", HTTP_AUTHORIZATION=self._auth
            )
        )
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(response_data_dict(detail)["can_edit"])

        patch = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "Nope"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(patch.status_code, 403)

        put = assert_response(
            self.client.put(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "Nope2"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(put.status_code, 403)

        delete = assert_response(
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(delete.status_code, 403)

    def test_bearer_cannot_manage_items_on_visible_group_shelf(self):
        shelf_id, item_id = self._create_group_shelf_with_item_as_session_user()

        add = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_public.id)},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(add.status_code, 403)

        move = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                data={"position": 0},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(move.status_code, 403)

        remove = assert_response(
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(remove.status_code, 403)

    def test_session_auth_curator_can_edit_group_shelf(self):
        shelf_id, item_id = self._create_group_shelf_with_item_as_session_user()

        self.client.force_login(self.user)
        detail = assert_response(self.client.get(f"/api/v1/shelves/{shelf_id}/"))
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(response_data_dict(detail)["can_edit"])

        patch = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/",
                data={"name": "Session allowed"},
                format="json",
            ),
        )
        self.assertEqual(patch.status_code, 200)

        move = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                data={"position": 0},
                format="json",
            ),
        )
        self.assertEqual(move.status_code, 200)

    def test_bearer_can_add_and_remove_accessible_book_on_own_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()

        add = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(add.status_code, 201)
        item_id = str(response_data_dict(add)["id"])

        items = assert_response(
            self.client.get(
                f"/api/v1/shelves/{shelf_id}/items/", HTTP_AUTHORIZATION=self._auth
            )
        )
        self.assertEqual(items.status_code, 200)

        rm = assert_response(
            self.client.delete(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(rm.status_code, 204)

    def test_bearer_cannot_add_inaccessible_book_to_own_shelf(self):
        shelf_id = self._create_personal_shelf_as_owner()
        add = assert_response(
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
        add1 = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(add1.status_code, 201)
        item_id = str(response_data_dict(add1)["id"])

        patch = assert_response(
            self.client.patch(
                f"/api/v1/shelves/{shelf_id}/items/{item_id}/",
                data={"position": 5},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(response_data_dict(patch)["position"], 0)
