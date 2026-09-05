from __future__ import annotations

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from tests.utils.responses import (
    assert_response,
    response_data_list,
)


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

class UserProfileAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass", email="test@example.com"
        )
        self.client.login(username="testuser", password="testpass")

    def test_authenticated_access(self):
        response = assert_response(self.client.get("/api/v1/accounts/profiles/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile = response_data_list(response)[0]
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
