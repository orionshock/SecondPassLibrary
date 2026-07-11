from __future__ import annotations

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from tests.accounts.helpers import create_account_role_users
from tests.utils.responses import assert_response


class MustChangePasswordPatchBoundaryTests(APITestCase):
    def setUp(self):
        users = create_account_role_users()
        self.owner = users.owner
        self.manager = users.manager
        self.manager2 = users.manager2
        self.librarian = users.librarian
        self.reader = users.reader

    def test_me_patch_cannot_change_must_change_password(self):
        self.client.login(username="reader", password="pw")
        denied = assert_response(
            self.client.patch(
                "/api/v1/accounts/me/",
                data={"must_change_password": True},
                format="json",
            ),
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manager_can_patch_must_change_password_for_reader(self):
        self.client.login(username="manager", password="pw")
        ok = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.reader.profile.id}/",
                data={"must_change_password": True},
                format="json",
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertTrue(UserProfile.objects.get(user=self.reader).must_change_password)

    def test_manager_can_patch_must_change_password_for_librarian(self):
        self.client.login(username="manager", password="pw")
        ok = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.librarian.profile.id}/",
                data={"must_change_password": True},
                format="json",
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertTrue(
            UserProfile.objects.get(user=self.librarian).must_change_password
        )

    def test_manager_cannot_patch_must_change_password_for_manager(self):
        self.client.login(username="manager", password="pw")
        denied = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager2.profile.id}/",
                data={"must_change_password": True},
                format="json",
            ),
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_patch_must_change_password_for_owner(self):
        self.client.login(username="manager", password="pw")
        denied = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.owner.profile.id}/",
                data={"must_change_password": True},
                format="json",
            ),
        )
        self.assertIn(
            denied.status_code, {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND}
        )

    def test_owner_can_patch_must_change_password_for_manager(self):
        self.client.login(username="owner", password="pw")
        ok = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager.profile.id}/",
                data={"must_change_password": True},
                format="json",
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertTrue(UserProfile.objects.get(user=self.manager).must_change_password)
