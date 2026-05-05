from collections.abc import Mapping
from typing import Any, cast

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.response import Response

from .models import UserProfile


class UserProfileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")

    def test_user_creation_creates_profile(self):
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.role, UserProfile.ROLE_READER)
        self.assertIsNone(profile.external_subject_id)

    def test_user_profile_role_helpers(self):
        profile = UserProfile.objects.get(user=self.user)
        self.assertTrue(profile.is_reader)
        self.assertFalse(profile.is_manager)
        self.assertFalse(profile.is_librarian)
        self.assertFalse(profile.is_app_admin)
        profile.role = UserProfile.ROLE_MANAGER
        profile.save()
        profile.refresh_from_db()
        self.assertTrue(profile.is_manager)
        self.assertTrue(profile.is_app_admin)
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
        response = self.client.get("/api/v1/accounts/profiles/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_authenticated_access_me(self):
        response = cast(Response, self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        data = cast(Mapping[str, Any], response.data)
        self.assertEqual(data["username"], "testuser")
        self.assertEqual(data["email"], "test@example.com")
        self.assertEqual(data["role"], UserProfile.ROLE_READER)
        self.assertIn("profile_id", data)

    def test_anonymous_cannot_access_me(self):
        self.client.logout()
        response = self.client.get("/api/v1/accounts/me/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
