from __future__ import annotations

import pytest
from rest_framework import status

from accounts.models import UserProfile
from tests.accounts.users.helpers import ManagedUsersApiTestMixin
from tests.utils.responses import assert_response, response_data_dict


pytestmark = [pytest.mark.integration]


class ManagedUsersRoleAndActivationPermissionsAPITest(ManagedUsersApiTestMixin):
    def test_owner_can_assign_and_demote_manager_role(self):
        self.client.login(username="owner", password="pw")
        promote = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.reader.profile.id}/",
                data={"role": UserProfile.ROLE_MANAGER},
                format="json",
            ),
        )
        self.assertEqual(promote.status_code, status.HTTP_200_OK)
        promote_data = response_data_dict(promote)
        self.assertEqual(promote_data["role"], UserProfile.ROLE_MANAGER)

        demote = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager2.profile.id}/",
                data={"role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(demote.status_code, status.HTTP_200_OK)
        demote_data = response_data_dict(demote)
        self.assertEqual(demote_data["role"], UserProfile.ROLE_READER)

    def test_manager_can_assign_librarian_or_reader_but_not_manager(self):
        self.client.login(username="manager", password="pw")
        ok = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.reader.profile.id}/",
                data={"role": UserProfile.ROLE_LIBRARIAN},
                format="json",
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        ok_data = response_data_dict(ok)
        self.assertEqual(ok_data["role"], UserProfile.ROLE_LIBRARIAN)

        denied = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.librarian.profile.id}/",
                data={"role": UserProfile.ROLE_MANAGER},
                format="json",
            ),
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_demote_existing_manager(self):
        self.client.login(username="manager", password="pw")
        response = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager2.profile.id}/",
                data={"role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_edit_another_manager_or_self_role(self):
        self.client.login(username="manager", password="pw")
        other = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager2.profile.id}/",
                data={"email": "new@example.com"},
                format="json",
            ),
        )
        self.assertEqual(other.status_code, status.HTTP_403_FORBIDDEN)

        self_user = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager.profile.id}/",
                data={"role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(self_user.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_user_can_deactivate_self(self):
        self.client.login(username="manager", password="pw")
        response = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager.profile.id}/",
                data={"is_active": False},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.logout()
        self.client.login(username="owner", password="pw")
        response2 = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.owner.profile.id}/",
                data={"is_active": False},
                format="json",
            ),
        )
        self.assertEqual(response2.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_deactivate_reader_or_librarian(self):
        self.client.login(username="manager", password="pw")
        response = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.reader.profile.id}/",
                data={"is_active": False},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.reader.refresh_from_db()
        self.assertFalse(self.reader.is_active)

    def test_owner_can_deactivate_other_user(self):
        self.client.login(username="owner", password="pw")
        response = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager.profile.id}/",
                data={"is_active": False},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.manager.refresh_from_db()
        self.assertFalse(self.manager.is_active)

    def test_invalid_role_returns_400(self):
        self.client.login(username="owner", password="pw")
        response = assert_response(
            self.client.patch(
                f"/api/v1/accounts/users/{self.reader.profile.id}/",
                data={"role": "nope"},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
