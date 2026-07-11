from __future__ import annotations

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from tests.accounts.helpers import create_account_role_users
from tests.utils.responses import assert_response, response_data_dict


class ManagedResetPasswordApiTests(APITestCase):
    def setUp(self):
        users = create_account_role_users()
        self.owner = users.owner
        self.manager = users.manager
        self.manager2 = users.manager2
        self.librarian = users.librarian
        self.reader = users.reader

    def test_managed_reset_returns_password_and_sets_must_change_password(self):
        self.client.login(username="manager", password="pw")
        response = assert_response(
            self.client.post(
                f"/api/v1/accounts/users/{self.reader.profile.id}/reset-password/",
                data={},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response_data_dict(response)
        self.assertIn("temporary_password", payload)
        self.assertIn("copy_block", payload)
        self.assertIn("message", payload)
        temp_pw = str(payload["temporary_password"])
        self.assertIn("Username:", str(payload["copy_block"]))
        self.assertIn("Password:", str(payload["copy_block"]))

        profile = UserProfile.objects.get(user=self.reader)
        self.assertTrue(profile.must_change_password)

        self.client.logout()
        ok = self.client.login(username="reader", password=temp_pw)
        self.assertTrue(ok)

    def test_manager_can_reset_reader_and_librarian(self):
        self.client.login(username="manager", password="pw")
        r1 = assert_response(
            self.client.post(
                f"/api/v1/accounts/users/{self.reader.profile.id}/reset-password/"
            )
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.client.logout()
        self.client.login(username="manager", password="pw")
        r2 = assert_response(
            self.client.post(
                f"/api/v1/accounts/users/{self.librarian.profile.id}/reset-password/"
            )
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)

    def test_manager_cannot_reset_manager(self):
        self.client.login(username="manager", password="pw")
        denied = assert_response(
            self.client.post(
                f"/api/v1/accounts/users/{self.manager2.profile.id}/reset-password/"
            ),
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_reset_owner(self):
        self.client.login(username="manager", password="pw")
        denied = assert_response(
            self.client.post(
                f"/api/v1/accounts/users/{self.owner.profile.id}/reset-password/"
            ),
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_reset_manager(self):
        self.client.login(username="owner", password="pw")
        ok = assert_response(
            self.client.post(
                f"/api/v1/accounts/users/{self.manager.profile.id}/reset-password/"
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)

    def test_managed_reset_cannot_reset_self(self):
        self.client.login(username="manager", password="pw")
        denied = assert_response(
            self.client.post(
                f"/api/v1/accounts/users/{self.manager.profile.id}/reset-password/"
            ),
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
