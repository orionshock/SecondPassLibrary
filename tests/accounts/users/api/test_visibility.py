from __future__ import annotations

import pytest
from rest_framework import status

from accounts.models import UserProfile
from tests.accounts.users.helpers import ManagedUsersApiTestMixin
from tests.utils.responses import (
    assert_response,
    payload_list,
    response_data_dict,
    response_data_list,
)


pytestmark = [pytest.mark.integration]


class ManagedUsersVisibilityAPITest(ManagedUsersApiTestMixin):
    def test_reader_and_librarian_cannot_access_user_management_endpoints(self):
        self.client.login(username="reader", password="pw")
        r1 = assert_response(self.client.get("/api/v1/accounts/users/"))
        self.assertEqual(r1.status_code, status.HTTP_403_FORBIDDEN)
        r2 = assert_response(
            self.client.get(f"/api/v1/accounts/users/{self.reader.profile.id}/")
        )
        self.assertEqual(r2.status_code, status.HTTP_403_FORBIDDEN)

        self.client.logout()
        self.client.login(username="librarian", password="pw")
        r3 = assert_response(self.client.get("/api/v1/accounts/users/"))
        self.assertEqual(r3.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_list_users_but_owner_is_excluded(self):
        self.client.login(username="manager", password="pw")
        response = assert_response(self.client.get("/api/v1/accounts/users/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response_data_dict(response)
        self.assertIn("count", payload)
        self.assertIn("next", payload)
        self.assertIn("previous", payload)
        self.assertIn("results", payload)
        data = payload_list(payload, "results")
        for row in data:
            self.assertIn("profile_id", row)
            self.assertIn("email", row)
            self.assertIn("first_name", row)
            self.assertIn("last_name", row)
            self.assertNotIn("id", row)
        usernames = {u["username"] for u in data}
        self.assertIn("manager", usernames)
        self.assertIn("reader", usernames)
        self.assertIn("librarian", usernames)
        self.assertIn("manager2", usernames)
        self.assertNotIn("owner", usernames)

    def test_owner_can_list_users(self):
        self.client.login(username="owner", password="pw")
        response = assert_response(self.client.get("/api/v1/accounts/users/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_list(response)
        usernames = {u["username"] for u in data}
        self.assertIn("owner", usernames)
        self.assertIn("manager", usernames)

    def test_manager_cannot_retrieve_owner(self):
        self.client.login(username="manager", password="pw")
        response = assert_response(
            self.client.get(f"/api/v1/accounts/users/{self.owner.profile.id}/")
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_response_does_not_expose_sensitive_auth_fields(self):
        self.client.login(username="owner", password="pw")
        response = assert_response(
            self.client.get(f"/api/v1/accounts/users/{self.reader.profile.id}/")
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_dict(response)
        self.assertEqual(
            data["profile_id"], str(UserProfile.objects.get(user=self.reader).id)
        )
        self.assertEqual(data["email"], self.reader.email)
        self.assertIn("first_name", data)
        self.assertIn("last_name", data)
        self.assertNotIn("id", data)
        self.assertNotIn("password", data)
        self.assertNotIn("user_permissions", data)
        self.assertNotIn("is_superuser", data)
        self.assertNotIn("is_staff", data)
