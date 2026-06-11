from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from library.group_services import get_public_group
from library.models import LibraryGroup, LibraryGroupMembership


User = get_user_model()


class ManagedUsersAPITest(APITestCase):
    def setUp(self):
        self.public = get_public_group()
        self.owner = User.objects.create_superuser(
            username="owner", email="owner@example.com", password="pw"
        )

        self.manager = User.objects.create_user(
            username="manager", email="manager@example.com", password="pw"
        )
        manager_profile, _ = UserProfile.objects.get_or_create(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.manager2 = User.objects.create_user(
            username="manager2", email="manager2@example.com", password="pw"
        )
        manager2_profile, _ = UserProfile.objects.get_or_create(user=self.manager2)
        manager2_profile.role = UserProfile.ROLE_MANAGER
        manager2_profile.save(update_fields=["role", "updated_at"])

        self.librarian = User.objects.create_user(
            username="librarian", email="librarian@example.com", password="pw"
        )
        librarian_profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        librarian_profile.role = UserProfile.ROLE_LIBRARIAN
        librarian_profile.save(update_fields=["role", "updated_at"])

        self.reader = User.objects.create_user(
            username="reader", email="reader@example.com", password="pw"
        )
        reader_profile, _ = UserProfile.objects.get_or_create(user=self.reader)
        reader_profile.role = UserProfile.ROLE_READER
        reader_profile.save(update_fields=["role", "updated_at"])

    def test_me_endpoint_still_works(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = cast(Mapping[str, Any], response.data)
        self.assertEqual(data["username"], "reader")
        self.assertEqual(data["profile_id"], str(self.reader.profile.id))
        self.assertEqual(data["role"], UserProfile.ROLE_READER)
        self.assertFalse(data["is_owner"])
        self.assertNotIn("id", data)
        self.assertIn("capabilities", data)
        capabilities = cast(Mapping[str, Any], data["capabilities"])
        self.assertFalse(capabilities["can_manage_users"])
        self.assertFalse(capabilities["can_manage_library"])
        self.assertFalse(capabilities["can_import_books"])
        self.assertFalse(capabilities["can_create_library_groups"])
        self.assertFalse(capabilities["can_manage_group_memberships"])
        self.assertFalse(capabilities["can_manage_group_identity"])
        self.assertFalse(capabilities["can_edit_group_presentation"])
        self.assertFalse(capabilities["can_access_imports"])

        groups = cast(list[dict[str, Any]], data["groups"])
        self.assertGreaterEqual(len(groups), 1)
        public_groups = [g for g in groups if g["is_public_group"]]
        self.assertEqual(len(public_groups), 1)
        self.assertTrue(public_groups[0]["is_public_group"])
        self.assertEqual(public_groups[0]["membership_role"], LibraryGroupMembership.ROLE_READER)
        self.assertEqual(data["curated_group_ids"], [])

    def test_me_capabilities_manager(self):
        self.client.login(username="manager", password="pw")
        response = cast(Response, self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = cast(Mapping[str, Any], response.data)
        self.assertFalse(data["is_owner"])
        capabilities = cast(Mapping[str, Any], data["capabilities"])
        self.assertTrue(capabilities["can_manage_users"])
        self.assertTrue(capabilities["can_manage_library"])
        self.assertTrue(capabilities["can_import_books"])
        self.assertTrue(capabilities["can_create_library_groups"])
        self.assertTrue(capabilities["can_manage_group_memberships"])
        self.assertTrue(capabilities["can_manage_group_identity"])
        self.assertTrue(capabilities["can_edit_group_presentation"])
        self.assertTrue(capabilities["can_access_imports"])

    def test_me_capabilities_owner(self):
        self.client.login(username="owner", password="pw")
        response = cast(Response, self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = cast(Mapping[str, Any], response.data)
        self.assertTrue(data["is_owner"])
        capabilities = cast(Mapping[str, Any], data["capabilities"])
        self.assertTrue(capabilities["can_manage_users"])
        self.assertTrue(capabilities["can_manage_library"])
        self.assertTrue(capabilities["can_import_books"])
        self.assertTrue(capabilities["can_create_library_groups"])
        self.assertTrue(capabilities["can_manage_group_memberships"])
        self.assertTrue(capabilities["can_manage_group_identity"])
        self.assertTrue(capabilities["can_edit_group_presentation"])
        self.assertTrue(capabilities["can_access_imports"])

    def test_me_curator_reader_has_scoped_group_presentation_power(self):
        group = LibraryGroup.objects.create(
            name="Fantasy Club",
        )
        LibraryGroupMembership.objects.create(
            user=self.reader,
            group=group,
            role=LibraryGroupMembership.ROLE_CURATOR,
        )

        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = cast(Mapping[str, Any], response.data)
        self.assertEqual(data["role"], UserProfile.ROLE_READER)

        capabilities = cast(Mapping[str, Any], data["capabilities"])
        self.assertFalse(capabilities["can_manage_library"])
        self.assertFalse(capabilities["can_manage_users"])
        self.assertTrue(capabilities["can_edit_group_presentation"])

        curated_group_ids = cast(list[str], data["curated_group_ids"])
        self.assertIn(str(group.id), curated_group_ids)

    def test_reader_and_librarian_cannot_access_user_management_endpoints(self):
        self.client.login(username="reader", password="pw")
        r1 = cast(Response, self.client.get("/api/v1/accounts/users/"))
        self.assertEqual(r1.status_code, status.HTTP_403_FORBIDDEN)
        r2 = cast(Response, self.client.get(f"/api/v1/accounts/users/{self.reader.pk}/"))
        self.assertEqual(r2.status_code, status.HTTP_403_FORBIDDEN)

        self.client.logout()
        self.client.login(username="librarian", password="pw")
        r3 = cast(Response, self.client.get("/api/v1/accounts/users/"))
        self.assertEqual(r3.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_list_users_but_owner_is_excluded(self):
        self.client.login(username="manager", password="pw")
        response = cast(Response, self.client.get("/api/v1/accounts/users/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        payload = cast(Mapping[str, Any], response.data)
        self.assertIn("count", payload)
        self.assertIn("next", payload)
        self.assertIn("previous", payload)
        self.assertIn("results", payload)
        data = cast(list[dict[str, Any]], payload["results"])
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
        self.assertIsNotNone(response.data)
        payload = cast(Mapping[str, Any], response.data)
        data = cast(list[dict[str, Any]], payload["results"])
        usernames = {u["username"] for u in data}
        self.assertIn("owner", usernames)
        self.assertIn("manager", usernames)

    def test_manager_cannot_retrieve_owner(self):
        self.client.login(username="manager", password="pw")
        response = cast(
            Response, self.client.get(f"/api/v1/accounts/users/{self.owner.pk}/")
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_response_does_not_expose_sensitive_auth_fields(self):
        self.client.login(username="owner", password="pw")
        response = cast(
            Response, self.client.get(f"/api/v1/accounts/users/{self.reader.pk}/")
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = cast(Mapping[str, Any], response.data)
        self.assertNotIn("password", data)
        self.assertNotIn("user_permissions", data)
        self.assertNotIn("is_superuser", data)
        self.assertNotIn("is_staff", data)

    def test_owner_can_assign_and_demote_manager_role(self):
        self.client.login(username="owner", password="pw")
        promote = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.reader.pk}/",
                data={"role": UserProfile.ROLE_MANAGER},
                format="json",
            ),
        )
        self.assertEqual(promote.status_code, status.HTTP_200_OK)
        promote_data = cast(Mapping[str, Any], promote.data)
        self.assertEqual(promote_data["role"], UserProfile.ROLE_MANAGER)

        demote = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager2.pk}/",
                data={"role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(demote.status_code, status.HTTP_200_OK)
        demote_data = cast(Mapping[str, Any], demote.data)
        self.assertEqual(demote_data["role"], UserProfile.ROLE_READER)

    def test_manager_can_assign_librarian_or_reader_but_not_manager(self):
        self.client.login(username="manager", password="pw")
        ok = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.reader.pk}/",
                data={"role": UserProfile.ROLE_LIBRARIAN},
                format="json",
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        ok_data = cast(Mapping[str, Any], ok.data)
        self.assertEqual(ok_data["role"], UserProfile.ROLE_LIBRARIAN)

        denied = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.librarian.pk}/",
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
                f"/api/v1/accounts/users/{self.manager2.pk}/",
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
                f"/api/v1/accounts/users/{self.manager2.pk}/",
                data={"email": "new@example.com"},
                format="json",
            ),
        )
        self.assertEqual(other.status_code, status.HTTP_403_FORBIDDEN)

        self_user = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager.pk}/",
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
                f"/api/v1/accounts/users/{self.manager.pk}/",
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
                f"/api/v1/accounts/users/{self.owner.pk}/",
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
                f"/api/v1/accounts/users/{self.reader.pk}/",
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
                f"/api/v1/accounts/users/{self.manager.pk}/",
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
                f"/api/v1/accounts/users/{self.reader.pk}/",
                data={"role": "nope"},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_can_create_manager_and_response_includes_temporary_password_once(self):
        self.client.login(username="owner", password="pw")
        response = cast(
            Response,
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
        data = cast(Mapping[str, Any], response.data)
        self.assertIn("user", data)
        self.assertIn("temporary_password", data)
        self.assertIn("message", data)
        self.assertTrue(str(data["temporary_password"]))

        user_payload = cast(Mapping[str, Any], data["user"])
        self.assertEqual(user_payload["username"], "newmanager")
        self.assertEqual(user_payload["role"], UserProfile.ROLE_MANAGER)
        self.assertNotIn("temporary_password", user_payload)
        self.assertNotIn("password", user_payload)

        created_user = User.objects.get(username="newmanager")
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

        list_response = cast(Response, self.client.get("/api/v1/accounts/users/"))
        self.assertIn(list_response.status_code, {status.HTTP_200_OK, status.HTTP_403_FORBIDDEN})
        if list_response.status_code == status.HTTP_200_OK:
            list_payload = cast(Mapping[str, Any], list_response.data)
            results = cast(list[dict[str, Any]], list_payload["results"])
            for row in results:
                self.assertNotIn("temporary_password", row)
                self.assertNotIn("password", row)

        detail_response = cast(
            Response, self.client.get(f"/api/v1/accounts/users/{created_user.pk}/")
        )
        self.assertIn(detail_response.status_code, {status.HTTP_200_OK, status.HTTP_403_FORBIDDEN})
        if detail_response.status_code == status.HTTP_200_OK:
            detail_payload = cast(Mapping[str, Any], detail_response.data)
            self.assertNotIn("temporary_password", detail_payload)
            self.assertNotIn("password", detail_payload)

    def test_owner_can_create_librarian_and_reader(self):
        self.client.login(username="owner", password="pw")
        r1 = cast(
            Response,
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "lib1", "role": UserProfile.ROLE_LIBRARIAN},
                format="json",
            ),
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        r2 = cast(
            Response,
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "reader1", "role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(UserProfile.objects.get(user__username="lib1").role, UserProfile.ROLE_LIBRARIAN)
        self.assertEqual(UserProfile.objects.get(user__username="reader1").role, UserProfile.ROLE_READER)
        self.assertTrue(UserProfile.objects.get(user__username="lib1").must_change_password)
        self.assertTrue(UserProfile.objects.get(user__username="reader1").must_change_password)

    def test_manager_can_create_librarian_or_reader_but_not_manager(self):
        self.client.login(username="manager", password="pw")
        ok = cast(
            Response,
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "oklib", "role": UserProfile.ROLE_LIBRARIAN},
                format="json",
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)

        denied = cast(
            Response,
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "badmgr", "role": UserProfile.ROLE_MANAGER},
                format="json",
            ),
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_librarian_and_reader_cannot_create_users(self):
        self.client.login(username="librarian", password="pw")
        denied1 = cast(
            Response,
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "nope1", "role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(denied1.status_code, status.HTTP_403_FORBIDDEN)

        self.client.logout()
        self.client.login(username="reader", password="pw")
        denied2 = cast(
            Response,
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "nope2", "role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(denied2.status_code, status.HTTP_403_FORBIDDEN)

    def test_duplicate_username_returns_400(self):
        self.client.login(username="owner", password="pw")
        first = cast(
            Response,
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "dupe", "role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = cast(
            Response,
            self.client.post(
                "/api/v1/accounts/users/",
                data={"username": "dupe", "role": UserProfile.ROLE_READER},
                format="json",
            ),
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
