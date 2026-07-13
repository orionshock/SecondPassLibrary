from __future__ import annotations

import pytest
from rest_framework import status

from accounts.models import UserProfile
from library.models import LibraryGroupMembership
from tests.accounts.users.helpers import ManagedUsersApiTestMixin
from tests.utils.responses import (
    assert_response,
    payload_dict,
    response_data_dict,
    response_data_list,
)


pytestmark = [pytest.mark.integration]


class ManagedUsersMutationsAPITest(ManagedUsersApiTestMixin):
    def test_owner_can_create_manager_and_response_includes_temporary_password_once(
        self,
    ):
        self.client.login(username="owner", password="pw")
        response = assert_response(
            self.client.post(
                "/api/v1/accounts/users/",
                data={
                    "username": "newmanager",
                    "email": "nm@example.com",
                    "first_name": "New",
                    "last_name": "Manager",
                    "role": UserProfile.ROLE_MANAGER,
                    "is_active": True,
                },
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(response)
        self.assertIn("user", data)
        self.assertIn("temporary_password", data)
        self.assertIn("message", data)
        self.assertTrue(str(data["temporary_password"]))

        user_payload = payload_dict(data, "user")
        self.assertEqual(
            user_payload["profile_id"],
            str(UserProfile.objects.get(user__username="newmanager").id),
        )
        self.assertNotIn("id", user_payload)
        self.assertEqual(user_payload["username"], "newmanager")
        self.assertEqual(user_payload["first_name"], "New")
        self.assertEqual(user_payload["last_name"], "Manager")
        self.assertEqual(user_payload["role"], UserProfile.ROLE_MANAGER)
        self.assertNotIn("temporary_password", user_payload)
        self.assertNotIn("password", user_payload)

        created_user = UserProfile.objects.get(user__username="newmanager").user
        created_profile = UserProfile.objects.get(user=created_user)
        self.assertEqual(created_profile.role, UserProfile.ROLE_MANAGER)
        self.assertTrue(created_profile.must_change_password)

        self.assertTrue(
            LibraryGroupMembership.objects.filter(
                user=created_user, group=self.public
            ).exists()
        )

        temp_pw = str(data["temporary_password"])
        self.client.logout()
        ok = self.client.login(username="newmanager", password=temp_pw)
        self.assertTrue(ok)

        list_response = assert_response(self.client.get("/api/v1/accounts/users/"))
        self.assertIn(
            list_response.status_code, {status.HTTP_200_OK, status.HTTP_403_FORBIDDEN}
        )
        if list_response.status_code == status.HTTP_200_OK:
            results = response_data_list(list_response)
            for row in results:
                self.assertNotIn("temporary_password", row)
                self.assertNotIn("password", row)

        detail_response = assert_response(
            self.client.get(f"/api/v1/accounts/users/{created_user.profile.id}/")
        )
        self.assertIn(
            detail_response.status_code,
            {status.HTTP_200_OK, status.HTTP_403_FORBIDDEN},
        )
        if detail_response.status_code == status.HTTP_200_OK:
            detail_payload = response_data_dict(detail_response)
            self.assertNotIn("temporary_password", detail_payload)
            self.assertNotIn("password", detail_payload)
            self.assertNotIn("id", detail_payload)

        integer_detail_response = assert_response(
            self.client.get(f"/api/v1/accounts/users/{created_user.pk}/")
        )
        self.assertIn(
            integer_detail_response.status_code,
            {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND},
        )

    def test_owner_can_create_librarian_and_reader(self):
        self.client.login(username="owner", password="pw")
        r1 = assert_response(
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "lib1", "role": UserProfile.ROLE_LIBRARIAN},
                format="json",
            ),
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        r2 = assert_response(
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "reader1", "role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            UserProfile.objects.get(user__username="lib1").role,
            UserProfile.ROLE_LIBRARIAN,
        )
        self.assertEqual(
            UserProfile.objects.get(user__username="reader1").role,
            UserProfile.ROLE_READER,
        )
        self.assertTrue(
            UserProfile.objects.get(user__username="lib1").must_change_password
        )
        self.assertTrue(
            UserProfile.objects.get(user__username="reader1").must_change_password
        )

    def test_manager_can_create_librarian_or_reader_but_not_manager(self):
        self.client.login(username="manager", password="pw")
        ok = assert_response(
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "oklib", "role": UserProfile.ROLE_LIBRARIAN},
                format="json",
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)

        denied = assert_response(
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "badmgr", "role": UserProfile.ROLE_MANAGER},
                format="json",
            ),
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_librarian_and_reader_cannot_create_users(self):
        self.client.login(username="librarian", password="pw")
        denied1 = assert_response(
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "nope1", "role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(denied1.status_code, status.HTTP_403_FORBIDDEN)

        self.client.logout()
        self.client.login(username="reader", password="pw")
        denied2 = assert_response(
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "nope2", "role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(denied2.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicate_username_returns_400(self):
        self.client.login(username="owner", password="pw")
        first = assert_response(
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "dupe", "role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = assert_response(
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "dupe", "role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
