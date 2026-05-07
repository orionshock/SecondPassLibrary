from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from .models import UserProfile


User = get_user_model()


class ManagedUsersAPITest(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(username="owner", email="owner@example.com", password="pw")

        self.manager = User.objects.create_user(username="manager", email="manager@example.com", password="pw")
        manager_profile, _ = UserProfile.objects.get_or_create(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.manager2 = User.objects.create_user(username="manager2", email="manager2@example.com", password="pw")
        manager2_profile, _ = UserProfile.objects.get_or_create(user=self.manager2)
        manager2_profile.role = UserProfile.ROLE_MANAGER
        manager2_profile.save(update_fields=["role", "updated_at"])

        self.librarian = User.objects.create_user(username="librarian", email="librarian@example.com", password="pw")
        librarian_profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        librarian_profile.role = UserProfile.ROLE_LIBRARIAN
        librarian_profile.save(update_fields=["role", "updated_at"])

        self.reader = User.objects.create_user(username="reader", email="reader@example.com", password="pw")
        reader_profile, _ = UserProfile.objects.get_or_create(user=self.reader)
        reader_profile.role = UserProfile.ROLE_READER
        reader_profile.save(update_fields=["role", "updated_at"])

    def test_me_endpoint_still_works(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = cast(Mapping[str, Any], response.data)
        self.assertEqual(data["username"], "reader")
        self.assertEqual(data["role"], UserProfile.ROLE_READER)

    def test_reader_and_librarian_cannot_access_user_management_endpoints(self):
        self.client.login(username="reader", password="pw")
        r1 = cast(Response, self.client.get("/api/v1/accounts/users/"))
        self.assertEqual(r1.status_code, status.HTTP_403_FORBIDDEN)
        r2 = cast(Response, self.client.get(f"/api/v1/accounts/users/{self.reader.id}/"))
        self.assertEqual(r2.status_code, status.HTTP_403_FORBIDDEN)

        self.client.logout()
        self.client.login(username="librarian", password="pw")
        r3 = cast(Response, self.client.get("/api/v1/accounts/users/"))
        self.assertEqual(r3.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_list_users_but_owner_is_excluded(self):
        self.client.login(username="manager", password="pw")
        response = cast(Response, self.client.get("/api/v1/accounts/users/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = cast(list[dict[str, Any]], response.data)
        usernames = {u["username"] for u in data}
        self.assertIn("manager", usernames)
        self.assertIn("reader", usernames)
        self.assertIn("librarian", usernames)
        self.assertIn("manager2", usernames)
        self.assertNotIn("owner", usernames)

    def test_owner_can_list_users(self):
        self.client.login(username="owner", password="pw")
        response = cast(Response, self.client.get("/api/v1/accounts/users/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = cast(list[dict[str, Any]], response.data)
        usernames = {u["username"] for u in data}
        self.assertIn("owner", usernames)
        self.assertIn("manager", usernames)

    def test_manager_cannot_retrieve_owner(self):
        self.client.login(username="manager", password="pw")
        response = cast(Response, self.client.get(f"/api/v1/accounts/users/{self.owner.id}/"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_response_does_not_expose_sensitive_auth_fields(self):
        self.client.login(username="owner", password="pw")
        response = cast(Response, self.client.get(f"/api/v1/accounts/users/{self.reader.id}/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = cast(Mapping[str, Any], response.data)
        self.assertNotIn("password", data)
        self.assertNotIn("user_permissions", data)
        self.assertNotIn("groups", data)
        self.assertNotIn("is_superuser", data)

    def test_owner_can_assign_and_demote_manager_role(self):
        self.client.login(username="owner", password="pw")
        promote = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.reader.id}/",
                data={"role": UserProfile.ROLE_MANAGER},
                format="json",
            ),
        )
        self.assertEqual(promote.status_code, status.HTTP_200_OK)
        self.assertEqual(promote.data["role"], UserProfile.ROLE_MANAGER)

        demote = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager2.id}/",
                data={"role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(demote.status_code, status.HTTP_200_OK)
        self.assertEqual(demote.data["role"], UserProfile.ROLE_READER)

    def test_manager_can_assign_librarian_or_reader_but_not_manager(self):
        self.client.login(username="manager", password="pw")
        ok = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.reader.id}/",
                data={"role": UserProfile.ROLE_LIBRARIAN},
                format="json",
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertEqual(ok.data["role"], UserProfile.ROLE_LIBRARIAN)

        denied = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.librarian.id}/",
                data={"role": UserProfile.ROLE_MANAGER},
                format="json",
            ),
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_demote_existing_manager(self):
        self.client.login(username="manager", password="pw")
        response = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager2.id}/",
                data={"role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_edit_another_manager_or_self_role(self):
        self.client.login(username="manager", password="pw")
        other = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager2.id}/",
                data={"email": "new@example.com"},
                format="json",
            ),
        )
        self.assertEqual(other.status_code, status.HTTP_403_FORBIDDEN)

        self_user = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager.id}/",
                data={"role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(self_user.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_user_can_deactivate_self(self):
        self.client.login(username="manager", password="pw")
        response = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager.id}/",
                data={"is_active": False},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.logout()
        self.client.login(username="owner", password="pw")
        response2 = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.owner.id}/",
                data={"is_active": False},
                format="json",
            ),
        )
        self.assertEqual(response2.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_deactivate_reader_or_librarian(self):
        self.client.login(username="manager", password="pw")
        response = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.reader.id}/",
                data={"is_active": False},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.reader.refresh_from_db()
        self.assertFalse(self.reader.is_active)

    def test_owner_can_deactivate_other_user(self):
        self.client.login(username="owner", password="pw")
        response = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager.id}/",
                data={"is_active": False},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.manager.refresh_from_db()
        self.assertFalse(self.manager.is_active)

    def test_invalid_role_returns_400(self):
        self.client.login(username="owner", password="pw")
        response = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.reader.id}/",
                data={"role": "nope"},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

