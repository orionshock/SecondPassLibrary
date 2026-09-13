from __future__ import annotations

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.client_sessions.services import hash_client_secret
from accounts.models import UserClientSession, UserProfile, UserWebSession
from accounts.current_user.services import update_current_user_via_me_api
from accounts.users.services import update_user_via_management_api
from tests.accounts.helpers import create_account_role_users


class AccountManagementServiceTests(TestCase):
    def setUp(self):
        users = create_account_role_users()
        self.manager = users.manager
        self.reader = users.reader

    def test_self_service_profile_update_is_not_manager_gated(self):
        update_current_user_via_me_api(
            user=self.reader,
            email="reader@example.test",
            first_name="Reader",
            last_name="Person",
        )

        self.reader.refresh_from_db()
        self.assertEqual(self.reader.email, "reader@example.test")
        self.assertEqual(self.reader.first_name, "Reader")
        self.assertEqual(self.reader.last_name, "Person")

    def test_managed_update_normalizes_profile_strings(self):
        update_user_via_management_api(
            actor=self.manager,
            target_user=self.reader,
            email="  reader@example.test  ",
            first_name="  Reader  ",
            last_name="  Person  ",
        )

        self.reader.refresh_from_db()
        self.assertEqual(self.reader.email, "reader@example.test")
        self.assertEqual(self.reader.first_name, "Reader")
        self.assertEqual(self.reader.last_name, "Person")

    def test_managed_update_validates_user_before_profile_save(self):
        with self.assertRaises(ValidationError):
            update_user_via_management_api(
                actor=self.manager,
                target_user=self.reader,
                email="not-an-email",
                role=UserProfile.ROLE_LIBRARIAN,
            )

        self.reader.refresh_from_db()
        self.reader.profile.refresh_from_db()
        self.assertEqual(self.reader.email, "")
        self.assertEqual(self.reader.profile.role, UserProfile.ROLE_READER)

    def test_managed_update_validates_profile_before_user_save(self):
        with patch.object(
            UserProfile,
            "full_clean",
            side_effect=ValidationError({"role": "forced failure"}),
        ):
            with self.assertRaises(ValidationError):
                update_user_via_management_api(
                    actor=self.manager,
                    target_user=self.reader,
                    email="reader@example.test",
                    role=UserProfile.ROLE_LIBRARIAN,
                )

        self.reader.refresh_from_db()
        self.reader.profile.refresh_from_db()
        self.assertEqual(self.reader.email, "")
        self.assertEqual(self.reader.profile.role, UserProfile.ROLE_READER)

    def test_disabling_user_revokes_sessions_after_successful_update(self):
        with patch("accounts.session_control.disable_user") as disable_user:
            update_user_via_management_api(
                actor=self.manager,
                target_user=self.reader,
                is_active=False,
            )

        self.reader.refresh_from_db()
        self.assertFalse(self.reader.is_active)
        disable_user.assert_called_once_with(self.reader, actor=self.manager)

    def test_client_revocation_failure_rolls_back_disable_and_web_revocation(self):
        tracked = UserWebSession.objects.create(
            user=self.reader,
            session_key="tracked-before-client-failure",
        )
        client_session = self._make_client_session("client-failure-token")
        original_generation = self.reader.profile.web_session_generation

        with (
            patch(
                "accounts.session_control.revoke_all_api_sessions",
                side_effect=RuntimeError("forced client revocation failure"),
            ),
            self.assertLogs("accounts.operational_logging", level="ERROR") as logs,
            self.assertRaises(RuntimeError),
        ):
            update_user_via_management_api(
                actor=self.manager,
                target_user=self.reader,
                is_active=False,
            )

        self.reader.refresh_from_db()
        self.reader.profile.refresh_from_db()
        client_session.refresh_from_db()
        self.assertTrue(self.reader.is_active)
        self.assertEqual(
            self.reader.profile.web_session_generation,
            original_generation,
        )
        self.assertTrue(UserWebSession.objects.filter(pk=tracked.pk).exists())
        self.assertIsNone(client_session.revoked_at)
        message = " ".join(logs.output)
        self.assertIn("operation=managed_user_disable", message)
        self.assertIn("lifecycle_stage=client_session_revocation", message)
        self.assertIn("transaction=rolled_back", message)
        self.assertIn("retryable=true", message)
        self.assertNotIn("client-failure-token", message)

        update_user_via_management_api(
            actor=self.manager,
            target_user=self.reader,
            is_active=False,
        )

        self.reader.refresh_from_db()
        self.reader.profile.refresh_from_db()
        client_session.refresh_from_db()
        self.assertFalse(self.reader.is_active)
        self.assertEqual(
            self.reader.profile.web_session_generation,
            original_generation + 1,
        )
        self.assertFalse(UserWebSession.objects.filter(pk=tracked.pk).exists())
        self.assertIsNotNone(client_session.revoked_at)

    def test_web_revocation_failure_rolls_back_disable_and_retry_succeeds(self):
        client_session = self._make_client_session("web-failure-token")

        with (
            patch(
                "accounts.session_control.revoke_other_web_sessions",
                side_effect=RuntimeError("forced web revocation failure"),
            ),
            self.assertLogs("accounts.operational_logging", level="ERROR") as logs,
            self.assertRaises(RuntimeError),
        ):
            update_user_via_management_api(
                actor=self.manager,
                target_user=self.reader,
                is_active=False,
            )

        self.reader.refresh_from_db()
        client_session.refresh_from_db()
        self.assertTrue(self.reader.is_active)
        self.assertIsNone(client_session.revoked_at)
        message = " ".join(logs.output)
        self.assertIn("lifecycle_stage=web_session_revocation", message)
        self.assertIn("transaction=rolled_back", message)

        update_user_via_management_api(
            actor=self.manager,
            target_user=self.reader,
            is_active=False,
        )
        self.reader.refresh_from_db()
        client_session.refresh_from_db()
        self.assertFalse(self.reader.is_active)
        self.assertIsNotNone(client_session.revoked_at)

    def test_retrying_explicit_disable_repairs_inactive_user_credentials(self):
        self.reader.is_active = False
        self.reader.save(update_fields=["is_active"])
        tracked = UserWebSession.objects.create(
            user=self.reader,
            session_key="incomplete-disable-session",
        )
        client_session = self._make_client_session("incomplete-disable-token")
        original_generation = self.reader.profile.web_session_generation

        update_user_via_management_api(
            actor=self.manager,
            target_user=self.reader,
            is_active=False,
        )

        self.reader.profile.refresh_from_db()
        client_session.refresh_from_db()
        self.assertEqual(
            self.reader.profile.web_session_generation,
            original_generation + 1,
        )
        self.assertFalse(UserWebSession.objects.filter(pk=tracked.pk).exists())
        self.assertIsNotNone(client_session.revoked_at)

    def test_unrelated_update_preserves_credentials(self):
        tracked = UserWebSession.objects.create(
            user=self.reader,
            session_key="unrelated-update-session",
        )
        client_session = self._make_client_session("unrelated-update-token")
        original_generation = self.reader.profile.web_session_generation

        update_user_via_management_api(
            actor=self.manager,
            target_user=self.reader,
            email="updated@example.test",
        )

        self.reader.refresh_from_db()
        self.reader.profile.refresh_from_db()
        client_session.refresh_from_db()
        self.assertEqual(self.reader.email, "updated@example.test")
        self.assertEqual(
            self.reader.profile.web_session_generation,
            original_generation,
        )
        self.assertTrue(UserWebSession.objects.filter(pk=tracked.pk).exists())
        self.assertIsNone(client_session.revoked_at)

    def _make_client_session(self, token: str) -> UserClientSession:
        return UserClientSession.objects.create(
            user=self.reader,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
