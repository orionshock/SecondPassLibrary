from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import ExternalIdentity, UserProfile
from accounts.services import user_supports_local_password


class UserProfileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")

    def test_user_creation_creates_profile(self):
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.role, UserProfile.ROLE_READER)
        self.assertFalse(profile.must_change_password)
        self.assertIsNone(profile.external_subject_id)

    def test_user_profile_role_helpers(self):
        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.is_reader)
        self.assertFalse(profile.is_manager)
        self.assertFalse(profile.is_librarian)
        profile.role = UserProfile.ROLE_MANAGER
        profile.save()
        profile.refresh_from_db()
        self.assertTrue(profile.is_manager)
        self.assertFalse(profile.is_reader)

    def test_user_profile_str(self):
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(str(profile), "testuser (reader)")
        profile.role = UserProfile.ROLE_MANAGER
        profile.save()
        profile.refresh_from_db()
        self.assertEqual(str(profile), "testuser (manager)")


class UserProfileAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass", email="test@example.com"
        )
        self.client.login(username="testuser", password="testpass")

    def test_authenticated_access(self):
        response = cast(Response, self.client.get("/api/v1/accounts/profiles/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = cast(Mapping[str, Any], response.data)
        profile = cast(list[dict[str, Any]], data["results"])[0]
        self.assertNotIn("external_subject_id", profile)

    def test_profile_api_disallows_protected_field_updates_and_delete(self):
        profile = UserProfile.objects.get(user=self.user)
        original_id = profile.id

        for method, payload in (
            ("patch", {"role": UserProfile.ROLE_MANAGER}),
            ("patch", {"external_subject_id": "subject"}),
            ("patch", {"must_change_password": True}),
            ("put", {"role": UserProfile.ROLE_MANAGER}),
            ("put", {"external_subject_id": "subject"}),
            ("put", {"must_change_password": True}),
        ):
            response = getattr(self.client, method)(
                f"/api/v1/accounts/profiles/{profile.id}/",
                data=payload,
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        delete = self.client.delete(f"/api/v1/accounts/profiles/{profile.id}/")
        self.assertEqual(delete.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        profile.refresh_from_db()
        self.assertEqual(profile.id, original_id)
        self.assertEqual(profile.role, UserProfile.ROLE_READER)
        self.assertIsNone(profile.external_subject_id)
        self.assertFalse(profile.must_change_password)

    def test_safe_me_update_preserves_profile_id(self):
        profile_id = cast(Any, self.user).profile.id
        response = cast(
            Response,
            self.client.patch(
                "/api/v1/accounts/me/",
                data={
                    "email": "updated@example.com",
                    "first_name": "Updated",
                    "last_name": "Reader",
                },
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = cast(Mapping[str, Any], response.data)
        self.assertEqual(data["profile_id"], str(profile_id))
        self.assertEqual(data["email"], "updated@example.com")
        self.assertEqual(data["first_name"], "Updated")
        self.assertEqual(data["last_name"], "Reader")
        self.user.refresh_from_db()
        self.assertEqual(cast(Any, self.user).profile.id, profile_id)

    def test_authenticated_access_me(self):
        response = cast(Response, self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        data = cast(Mapping[str, Any], response.data)
        self.assertEqual(data["username"], "testuser")
        self.assertEqual(data["email"], "test@example.com")
        self.assertEqual(data["first_name"], "")
        self.assertEqual(data["last_name"], "")
        self.assertEqual(data["role"], UserProfile.ROLE_READER)
        self.assertFalse(data["must_change_password"])
        self.assertIn("profile_id", data)

    def test_anonymous_cannot_access_me(self):
        self.client.logout()
        response = self.client.get("/api/v1/accounts/me/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ExternalIdentityModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="external-user")

    def test_multiple_external_identities_can_link_to_one_user(self):
        first = ExternalIdentity.objects.create(
            user=self.user,
            provider="primary",
            issuer="https://id.example.test/",
            subject="subject-1",
            email_at_login="reader@example.test",
            email_verified=True,
            selected_claims={"name": "Reader One"},
        )
        second = ExternalIdentity.objects.create(
            user=self.user,
            provider="secondary",
            issuer="https://login.example.test/",
            subject="subject-2",
        )

        self.assertEqual(first.user, self.user)
        self.assertEqual(second.user, self.user)
        self.assertEqual(cast(Any, self.user).external_identities.count(), 2)

    def test_issuer_and_subject_must_be_unique(self):
        ExternalIdentity.objects.create(
            user=self.user,
            provider="primary",
            issuer="https://id.example.test/",
            subject="shared-subject",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ExternalIdentity.objects.create(
                    user=User.objects.create_user(username="other-user"),
                    provider="primary",
                    issuer="https://id.example.test/",
                    subject="shared-subject",
                )

    def test_same_subject_under_different_issuer_is_allowed(self):
        ExternalIdentity.objects.create(
            user=self.user,
            provider="primary",
            issuer="https://id-one.example.test/",
            subject="shared-subject",
        )
        ExternalIdentity.objects.create(
            user=self.user,
            provider="secondary",
            issuer="https://id-two.example.test/",
            subject="shared-subject",
        )
        self.assertEqual(cast(Any, self.user).external_identities.count(), 2)

    def test_external_identities_are_not_exposed_by_account_apis(self):
        ExternalIdentity.objects.create(
            user=self.user,
            provider="primary",
            issuer="https://id.example.test/",
            subject="private-subject",
        )
        self.user.set_password("pw")
        self.user.save(update_fields=["password"])
        self.client.login(username="external-user", password="pw")

        profile_response = cast(
            Response, self.client.get("/api/v1/accounts/profiles/")
        )
        self.assertNotContains(profile_response, "private-subject")
        me_response = cast(Response, self.client.get("/api/v1/accounts/me/"))
        self.assertNotContains(me_response, "private-subject")


class LocalPasswordCapabilityTest(TestCase):
    def test_normal_local_user_supports_local_password(self):
        user = User.objects.create_user(username="local-user", password="pw")
        self.assertTrue(user_supports_local_password(user))

    def test_unusable_password_user_does_not_support_local_password(self):
        user = User.objects.create_user(username="external-only-user")
        user.set_unusable_password()
        user.save(update_fields=["password"])
        self.assertFalse(user_supports_local_password(user))
