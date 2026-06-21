from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import UserProfile
from library.group_services import get_public_group
from library.models import LibraryGroup, LibraryGroupMembership


User = get_user_model()


class SeedDevUsersCommandTests(TestCase):
    @override_settings(DEBUG=False)
    def test_refuses_when_debug_false(self):
        with patch(
            "accounts.management.commands.seed_dev_users.call_command"
        ) as migrate_command:
            with self.assertRaises(CommandError):
                call_command("seed_dev_users")

        migrate_command.assert_not_called()

    @override_settings(DEBUG=True)
    def test_applies_migrations_before_seeding(self):
        with patch(
            "accounts.management.commands.seed_dev_users.call_command",
            wraps=call_command,
        ) as migrate_command:
            call_command("seed_dev_users", verbosity=0)

        migrate_command.assert_called_once_with(
            "migrate",
            interactive=False,
            verbosity=0,
        )

    @override_settings(DEBUG=True)
    def test_idempotent_creates_expected_users_groups_and_memberships(self):
        call_command("seed_dev_users")

        owner = User.objects.get(username="owner")
        owner.first_name = "Stale"
        owner.last_name = "Name"
        owner.email = "stale@example.test"
        owner.save(update_fields=["first_name", "last_name", "email"])

        call_command("seed_dev_users")

        for username, first_name, last_name, email, role in (
            ("owner", "Lorem", "Ipsum", "lorem.ipsum@example.test", UserProfile.ROLE_MANAGER),
            ("manager", "Dolor", "Sit", "dolor.sit@example.test", UserProfile.ROLE_MANAGER),
            (
                "librarian",
                "Amet",
                "Consectetur",
                "amet.consectetur@example.test",
                UserProfile.ROLE_LIBRARIAN,
            ),
            ("reader", "Adipiscing", "Elit", "adipiscing.elit@example.test", UserProfile.ROLE_READER),
            ("curator", "Sed", "Eiusmod", "sed.eiusmod@example.test", UserProfile.ROLE_READER),
            (
                "outsider",
                "Tempor",
                "Incididunt",
                "tempor.incididunt@example.test",
                UserProfile.ROLE_READER,
            ),
        ):
            user = User.objects.get(username=username)
            profile = UserProfile.objects.get(user=user)
            self.assertEqual(user.first_name, first_name)
            self.assertEqual(user.last_name, last_name)
            self.assertEqual(user.email, email)
            self.assertEqual(profile.role, role)

        public = get_public_group()
        self.assertEqual(public.name, "Common Room")

        fantasy = LibraryGroup.objects.get(name="Fantasy Club")
        self.assertTrue(LibraryGroup.objects.filter(name="Kids Books").exists())

        curator = User.objects.get(username="curator")
        reader = User.objects.get(username="reader")

        curator_role = LibraryGroupMembership.objects.get(user=curator, group=fantasy).role
        reader_role = LibraryGroupMembership.objects.get(user=reader, group=fantasy).role
        self.assertEqual(curator_role, LibraryGroupMembership.ROLE_CURATOR)
        self.assertEqual(reader_role, LibraryGroupMembership.ROLE_READER)

        # Public membership exists for all seed users (role reader).
        for username in ("owner", "manager", "librarian", "reader", "curator", "outsider"):
            user = User.objects.get(username=username)
            role = LibraryGroupMembership.objects.get(user=user, group=public).role
            self.assertEqual(role, LibraryGroupMembership.ROLE_READER)
