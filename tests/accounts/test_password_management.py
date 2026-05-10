from __future__ import annotations

from typing import cast

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import UserProfile


User = get_user_model()


class ChangePasswordApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pw", email="u@example.com")
        profile = UserProfile.objects.get(user=self.user)
        profile.must_change_password = True
        profile.save(update_fields=["must_change_password", "updated_at"])
        self.client.login(username="u", password="pw")

    def test_change_password_requires_current_password(self):
        response = cast(
            Response,
            self.client.post(
                "/api/v1/accounts/me/change-password/",
                data={
                    "current_password": "wrong",
                    "new_password": "NewPassw0rd!",
                    "confirm_password": "NewPassw0rd!",
                },
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_fails_when_confirm_password_does_not_match(self):
        response = cast(
            Response,
            self.client.post(
                "/api/v1/accounts/me/change-password/",
                data={
                    "current_password": "pw",
                    "new_password": "NewPassw0rd!",
                    "confirm_password": "DifferentPassw0rd!",
                },
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_updates_password_and_clears_must_change_password(self):
        response = cast(
            Response,
            self.client.post(
                "/api/v1/accounts/me/change-password/",
                data={
                    "current_password": "pw",
                    "new_password": "NewPassw0rd!",
                    "confirm_password": "NewPassw0rd!",
                },
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Session stays valid.
        me = cast(Response, self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(me.status_code, status.HTTP_200_OK)

        profile = UserProfile.objects.get(user=self.user)
        self.assertFalse(profile.must_change_password)

        self.client.logout()
        ok = self.client.login(username="u", password="NewPassw0rd!")
        self.assertTrue(ok)


class ManagedResetPasswordApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(username="owner", password="pw")

        self.manager = User.objects.create_user(username="manager", password="pw")
        manager_profile = UserProfile.objects.get(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.manager2 = User.objects.create_user(username="manager2", password="pw")
        manager2_profile = UserProfile.objects.get(user=self.manager2)
        manager2_profile.role = UserProfile.ROLE_MANAGER
        manager2_profile.save(update_fields=["role", "updated_at"])

        self.librarian = User.objects.create_user(username="librarian", password="pw")
        librarian_profile = UserProfile.objects.get(user=self.librarian)
        librarian_profile.role = UserProfile.ROLE_LIBRARIAN
        librarian_profile.save(update_fields=["role", "updated_at"])

        self.reader = User.objects.create_user(username="reader", password="pw")
        reader_profile = UserProfile.objects.get(user=self.reader)
        reader_profile.role = UserProfile.ROLE_READER
        reader_profile.save(update_fields=["role", "updated_at"])

    def test_managed_reset_returns_password_and_sets_must_change_password(self):
        self.client.login(username="manager", password="pw")
        response = cast(
            Response,
            self.client.post(
                f"/api/v1/accounts/users/{self.reader.pk}/reset-password/",
                data={},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("temporary_password", response.data)
        self.assertIn("copy_block", response.data)
        self.assertIn("message", response.data)
        temp_pw = str(response.data["temporary_password"])
        self.assertIn("Username:", str(response.data["copy_block"]))
        self.assertIn("Password:", str(response.data["copy_block"]))

        profile = UserProfile.objects.get(user=self.reader)
        self.assertTrue(profile.must_change_password)

        self.client.logout()
        ok = self.client.login(username="reader", password=temp_pw)
        self.assertTrue(ok)

    def test_manager_can_reset_reader_and_librarian(self):
        self.client.login(username="manager", password="pw")
        r1 = cast(Response, self.client.post(f"/api/v1/accounts/users/{self.reader.pk}/reset-password/"))
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.client.logout()
        self.client.login(username="manager", password="pw")
        r2 = cast(Response, self.client.post(f"/api/v1/accounts/users/{self.librarian.pk}/reset-password/"))
        self.assertEqual(r2.status_code, status.HTTP_200_OK)

    def test_manager_cannot_reset_manager(self):
        self.client.login(username="manager", password="pw")
        denied = cast(
            Response,
            self.client.post(f"/api/v1/accounts/users/{self.manager2.pk}/reset-password/"),
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_reset_owner(self):
        self.client.login(username="manager", password="pw")
        denied = cast(
            Response,
            self.client.post(f"/api/v1/accounts/users/{self.owner.pk}/reset-password/"),
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_reset_manager(self):
        self.client.login(username="owner", password="pw")
        ok = cast(
            Response,
            self.client.post(f"/api/v1/accounts/users/{self.manager.pk}/reset-password/"),
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)

    def test_managed_reset_cannot_reset_self(self):
        self.client.login(username="manager", password="pw")
        denied = cast(
            Response,
            self.client.post(f"/api/v1/accounts/users/{self.manager.pk}/reset-password/"),
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)


class MustChangePasswordPatchBoundaryTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(username="owner", password="pw")

        self.manager = User.objects.create_user(username="manager", password="pw")
        manager_profile = UserProfile.objects.get(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.manager2 = User.objects.create_user(username="manager2", password="pw")
        manager2_profile = UserProfile.objects.get(user=self.manager2)
        manager2_profile.role = UserProfile.ROLE_MANAGER
        manager2_profile.save(update_fields=["role", "updated_at"])

        self.librarian = User.objects.create_user(username="librarian", password="pw")
        librarian_profile = UserProfile.objects.get(user=self.librarian)
        librarian_profile.role = UserProfile.ROLE_LIBRARIAN
        librarian_profile.save(update_fields=["role", "updated_at"])

        self.reader = User.objects.create_user(username="reader", password="pw")
        reader_profile = UserProfile.objects.get(user=self.reader)
        reader_profile.role = UserProfile.ROLE_READER
        reader_profile.save(update_fields=["role", "updated_at"])

    def test_me_patch_cannot_change_must_change_password(self):
        self.client.login(username="reader", password="pw")
        denied = cast(
            Response,
            self.client.patch(
                "/api/v1/accounts/me/",
                data={"must_change_password": True},
                format="json",
            ),
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manager_can_patch_must_change_password_for_reader(self):
        self.client.login(username="manager", password="pw")
        ok = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.reader.pk}/",
                data={"must_change_password": True},
                format="json",
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertTrue(UserProfile.objects.get(user=self.reader).must_change_password)

    def test_manager_can_patch_must_change_password_for_librarian(self):
        self.client.login(username="manager", password="pw")
        ok = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.librarian.pk}/",
                data={"must_change_password": True},
                format="json",
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertTrue(UserProfile.objects.get(user=self.librarian).must_change_password)

    def test_manager_cannot_patch_must_change_password_for_manager(self):
        self.client.login(username="manager", password="pw")
        denied = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager2.pk}/",
                data={"must_change_password": True},
                format="json",
            ),
        )
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_patch_must_change_password_for_owner(self):
        self.client.login(username="manager", password="pw")
        denied = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.owner.pk}/",
                data={"must_change_password": True},
                format="json",
            ),
        )
        # Managers should not be able to access/modify Owner via product APIs.
        # Implementation returns 404 to avoid existence leaks.
        self.assertIn(denied.status_code, {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND})

    def test_owner_can_patch_must_change_password_for_manager(self):
        self.client.login(username="owner", password="pw")
        ok = cast(
            Response,
            self.client.patch(
                f"/api/v1/accounts/users/{self.manager.pk}/",
                data={"must_change_password": True},
                format="json",
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertTrue(UserProfile.objects.get(user=self.manager).must_change_password)


class UserSerializerDoesNotLeakPasswordsTests(TestCase):
    def test_managed_user_payload_never_contains_password_fields(self):
        # Smoke check: serializer field list should not include password.
        from accounts.serializers import ManagedUserSerializer

        self.assertNotIn("password", ManagedUserSerializer().fields)
        self.assertNotIn("temporary_password", ManagedUserSerializer().fields)
