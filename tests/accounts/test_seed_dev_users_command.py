from __future__ import annotations

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
        with self.assertRaises(CommandError):
            call_command("seed_dev_users")

    @override_settings(DEBUG=True)
    def test_idempotent_creates_expected_users_groups_and_memberships(self):
        call_command("seed_dev_users")
        call_command("seed_dev_users")

        for username, role in (
            ("owner", UserProfile.ROLE_MANAGER),
            ("manager", UserProfile.ROLE_MANAGER),
            ("librarian", UserProfile.ROLE_LIBRARIAN),
            ("reader", UserProfile.ROLE_READER),
            ("curator", UserProfile.ROLE_READER),
            ("outsider", UserProfile.ROLE_READER),
        ):
            user = User.objects.get(username=username)
            profile = UserProfile.objects.get(user=user)
            self.assertEqual(profile.role, role)

        public = get_public_group()
        self.assertEqual(public.slug, "public")

        fantasy = LibraryGroup.objects.get(slug="fantasy-club")
        kids = LibraryGroup.objects.get(slug="kids-books")
        self.assertEqual(fantasy.discoverability, LibraryGroup.DISCOVERABILITY_LISTED)
        self.assertEqual(kids.discoverability, LibraryGroup.DISCOVERABILITY_UNLISTED)

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

