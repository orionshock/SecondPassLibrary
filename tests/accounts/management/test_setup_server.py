from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from accounts.models import UserProfile
from core import server_settings
from core.models import ServerSetting
from library.groups.public_group import get_public_group
from library.models import LibraryGroup, LibraryGroupMembership


User = get_user_model()
RAW_PASSWORD = "Correct-Horse-Battery-47"


class SetupServerCommandTests(TestCase):
    def _run_with_stdin(self, value: str, **options):
        output = StringIO()
        with patch(
            "accounts.management.commands.setup_server.sys.stdin",
            StringIO(value),
        ):
            call_command(
                "setup_server",
                username=options.pop("username", "owner"),
                stdout=output,
                **options,
            )
        return output.getvalue()

    @patch("accounts.management.commands.setup_server.create_first_owner")
    @patch(
        "accounts.management.commands.setup_server.getpass.getpass",
        side_effect=[RAW_PASSWORD, RAW_PASSWORD],
    )
    def test_interactive_setup_passes_hidden_password_to_shared_workflow(
        self,
        getpass_mock,
        create_first_owner_mock,
    ):
        create_first_owner_mock.return_value.get_username.return_value = "owner"

        output = StringIO()
        call_command(
            "setup_server",
            username="owner",
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            stdout=output,
        )

        self.assertEqual(getpass_mock.call_count, 2)
        create_first_owner_mock.assert_called_once_with(
            username="owner",
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            server_name="Second Pass Library",
            server_description="",
            public_group_name="Common Room",
            public_group_description="Main Public Library Room for everyone",
            advanced_library_groups_enabled=False,
            password=RAW_PASSWORD,
            encoded_password=None,
        )
        self.assertNotIn(RAW_PASSWORD, output.getvalue())

    def test_password_stdin_creates_complete_owner_and_login_works(self):
        output = self._run_with_stdin(
            RAW_PASSWORD,
            password_stdin=True,
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            server_name="Family Library",
            server_description="Shared at home.",
            public_group_name="Reading Room",
            public_group_description="Books for everyone.",
        )

        owner = User.objects.get(username="owner")
        self.assertTrue(owner.check_password(RAW_PASSWORD))
        self.assertEqual(owner.first_name, "Ada")
        self.assertEqual(owner.last_name, "Lovelace")
        self.assertEqual(owner.email, "ada@example.com")
        self.assertEqual(owner.profile.role, UserProfile.ROLE_MANAGER)
        self.assertEqual(server_settings.get_server_name(), "Family Library")
        self.assertEqual(get_public_group().name, "Reading Room")
        self.assertNotIn(RAW_PASSWORD, output)

        response = self.client.post(
            "/login/",
            {"username": "owner", "password": RAW_PASSWORD},
        )
        self.assertEqual(response.status_code, 302)

    @override_settings(
        AUTH_PASSWORD_VALIDATORS=[
            {
                "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
                "OPTIONS": {"min_length": 20},
            }
        ]
    )
    def test_password_stdin_uses_normal_password_validation(self):
        with self.assertRaisesRegex(CommandError, "at least 20 characters"):
            self._run_with_stdin("too-short", password_stdin=True)

        self.assertFalse(User.objects.exists())

    def test_account_fields_use_normal_model_validation(self):
        with self.assertRaisesRegex(CommandError, "email"):
            self._run_with_stdin(
                RAW_PASSWORD,
                password_stdin=True,
                email="not-an-email",
            )

        self.assertFalse(User.objects.exists())

    def test_encoded_password_stdin_is_stored_unchanged_and_login_works(self):
        encoded_password = make_password(RAW_PASSWORD)

        output = self._run_with_stdin(
            encoded_password + "\n",
            encoded_password_stdin=True,
        )

        owner = User.objects.get(username="owner")
        self.assertEqual(owner.password, encoded_password)
        self.assertNotIn(encoded_password, output)
        self.assertTrue(
            self.client.login(username="owner", password=RAW_PASSWORD)
        )

    def test_encoded_password_stdin_rejects_malformed_or_unrecognized_format(self):
        invalid_values = (
            "not-a-django-password",
            "pbkdf2_sha256$malformed",
        )
        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(CommandError, "not recognized by Django"):
                    self._run_with_stdin(
                        value,
                        encoded_password_stdin=True,
                    )

        self.assertFalse(User.objects.exists())

    def test_stdin_modes_reject_empty_input(self):
        for option in ("password_stdin", "encoded_password_stdin"):
            with self.subTest(option=option):
                with self.assertRaisesRegex(CommandError, "cannot be empty"):
                    self._run_with_stdin("", **{option: True})

        self.assertFalse(User.objects.exists())

    def test_stdin_password_modes_are_mutually_exclusive(self):
        with self.assertRaisesRegex(CommandError, "not allowed with argument"):
            call_command(
                "setup_server",
                "--username",
                "owner",
                "--password-stdin",
                "--encoded-password-stdin",
            )

    def test_already_initialized_server_refuses_without_mutation(self):
        self._run_with_stdin(RAW_PASSWORD, password_stdin=True)
        before = {
            "users": User.objects.count(),
            "groups": LibraryGroup.objects.count(),
            "memberships": LibraryGroupMembership.objects.count(),
            "settings": ServerSetting.objects.count(),
        }

        with self.assertRaisesRegex(CommandError, "already complete"):
            self._run_with_stdin(
                "Another-Correct-Password-48",
                username="owner-two",
                password_stdin=True,
            )

        self.assertEqual(User.objects.count(), before["users"])
        self.assertEqual(LibraryGroup.objects.count(), before["groups"])
        self.assertEqual(
            LibraryGroupMembership.objects.count(),
            before["memberships"],
        )
        self.assertEqual(ServerSetting.objects.count(), before["settings"])

    def test_late_setup_failure_rolls_back_every_mutation(self):
        with patch(
            "accounts.first_owner_setup.ensure_user_public_membership",
            side_effect=RuntimeError("late setup failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "late setup failure"):
                self._run_with_stdin(RAW_PASSWORD, password_stdin=True)

        self.assertFalse(User.objects.exists())
        self.assertFalse(LibraryGroup.objects.exists())
        self.assertFalse(LibraryGroupMembership.objects.exists())
        self.assertFalse(ServerSetting.objects.exists())


class BrowserSetupSharedWorkflowTests(TestCase):
    @patch("web.views.create_first_owner")
    def test_browser_setup_delegates_to_shared_workflow(self, create_first_owner_mock):
        response = self.client.post(
            "/setup/",
            {
                "server_name": "Second Pass Library",
                "server_description": "",
                "public_group_name": "Common Room",
                "public_group_description": "Main Public Library Room for everyone",
                "username": "owner",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "email": "ada@example.com",
                "password1": RAW_PASSWORD,
                "password2": RAW_PASSWORD,
            },
        )

        self.assertEqual(response.status_code, 302)
        create_first_owner_mock.assert_called_once()
        self.assertEqual(
            create_first_owner_mock.call_args.kwargs["password"],
            RAW_PASSWORD,
        )
