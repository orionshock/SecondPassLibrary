from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.models import UserProfile, UserWebSession
from tests.accounts.web_sessions.helpers import authenticated_tracked_client
from tests.utils.responses import assert_response


User = get_user_model()


class ManagedResetAndDisableSessionRevocationTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(
            username="owner",
            password="pw",
            email="owner@example.com",
        )

        self.manager = User.objects.create_user(
            username="manager",
            password="pw",
            email="manager@example.com",
        )
        manager_profile = UserProfile.objects.get(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.target = User.objects.create_user(
            username="target",
            password="pw",
            email="target@example.com",
        )

    def _make_target_sessions(self):
        _client1, key1 = authenticated_tracked_client(self, username="target")
        _client2, key2 = authenticated_tracked_client(self, username="target")
        self.assertNotEqual(key1, key2)
        return key1, key2

    def test_managed_password_reset_revokes_all_target_web_sessions(self):
        key1, key2 = self._make_target_sessions()
        self.assertTrue(Session.objects.filter(session_key=key1).exists())
        self.assertTrue(Session.objects.filter(session_key=key2).exists())

        actor = APIClient()
        self.assertTrue(actor.login(username="owner", password="pw"))
        response = assert_response(
            actor.post(
                f"/api/v1/accounts/users/{self.target.profile.id}/reset-password/",
                data={},
                format="json",
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertFalse(Session.objects.filter(session_key=key1).exists())
        self.assertFalse(Session.objects.filter(session_key=key2).exists())
        self.assertEqual(UserWebSession.objects.filter(user=self.target).count(), 0)

    def test_disabling_user_revokes_all_target_web_sessions(self):
        key1, key2 = self._make_target_sessions()

        actor = APIClient()
        self.assertTrue(actor.login(username="manager", password="pw"))
        response = assert_response(
            actor.patch(
                f"/api/v1/accounts/users/{self.target.profile.id}/",
                data={"is_active": False},
                format="json",
            )
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertFalse(Session.objects.filter(session_key=key1).exists())
        self.assertFalse(Session.objects.filter(session_key=key2).exists())
        self.assertEqual(UserWebSession.objects.filter(user=self.target).count(), 0)
