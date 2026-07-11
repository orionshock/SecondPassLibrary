from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import UserProfile
from accounts.services import update_current_user_via_me_api, update_user_via_management_api


User = get_user_model()


class AccountManagementServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.manager.profile.role = UserProfile.ROLE_MANAGER
        self.manager.profile.save(update_fields=["role", "updated_at"])

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
        disable_user.assert_called_once_with(self.reader)
