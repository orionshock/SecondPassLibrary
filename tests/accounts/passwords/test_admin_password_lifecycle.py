from __future__ import annotations

import importlib
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.test import TestCase, override_settings
from django.urls import clear_url_caches, set_urlconf

import secondpass.urls

from accounts.models import UserClientSession, UserProfile
from tests.accounts.web_sessions.helpers import authenticated_tracked_client


def _reload_project_urls() -> None:
    clear_url_caches()
    set_urlconf(None)
    importlib.reload(secondpass.urls)


@override_settings(SECOND_PASS_ENABLE_DJANGO_ADMIN=True)
class AdminPasswordLifecycleTests(TestCase):
    def setUp(self):
        _reload_project_urls()
        self.owner = User.objects.create_superuser(
            username="owner", password="owner-pw"
        )
        self.target = User.objects.create_user(username="target", password="old-pw")
        self.owner_client, _ = authenticated_tracked_client(
            self, username="owner", password="owner-pw"
        )
        self.target_client, self.target_web_key = authenticated_tracked_client(
            self, username="target", password="old-pw"
        )
        self.bearer = UserClientSession.objects.create(
            user=self.target,
            name="Reader",
            client_type="reader",
            token_hash="a" * 64,
        )

    def tearDown(self):
        _reload_project_urls()
        super().tearDown()

    def _change_password(self):
        return self.owner_client.post(
            f"/admin/auth/user/{self.target.pk}/password/",
            {
                "password1": "NewPassw0rd!",
                "password2": "NewPassw0rd!",
                "set_usable_password": "true",
            },
        )

    def test_admin_password_change_uses_managed_revocation_lifecycle(self):
        response = self._change_password()

        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.bearer.refresh_from_db()
        profile = UserProfile.objects.get(user=self.target)
        self.assertTrue(self.target.check_password("NewPassw0rd!"))
        self.assertTrue(profile.must_change_password)
        self.assertIsNotNone(self.bearer.revoked_at)
        self.assertFalse(
            Session.objects.filter(session_key=self.target_web_key).exists()
        )

    def test_admin_password_change_rolls_back_when_revocation_fails(self):
        with patch(
            "accounts.session_control.revoke_all_api_sessions",
            side_effect=RuntimeError("revocation failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "revocation failed"):
                self._change_password()

        self.target.refresh_from_db()
        self.bearer.refresh_from_db()
        profile = UserProfile.objects.get(user=self.target)
        self.assertTrue(self.target.check_password("old-pw"))
        self.assertFalse(profile.must_change_password)
        self.assertIsNone(self.bearer.revoked_at)
        self.assertTrue(
            Session.objects.filter(session_key=self.target_web_key).exists()
        )
