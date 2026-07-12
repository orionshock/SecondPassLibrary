from __future__ import annotations

from django.core.management import call_command
from django.test import override_settings

from accounts.models import UserProfile
from core import server_settings
from library.groups.public_group import get_public_group
from library.models import LibraryGroup, LibraryGroupMembership
from tests.accounts.management.helpers import SeedDevUsersCommandTestCase, User


class SeedDevUsersRoleTests(SeedDevUsersCommandTestCase):
    @override_settings(DEBUG=True)
    def test_existing_reader_membership_is_not_promoted_to_curator(self):
        self.create_setup_owner()
        server_settings.set_advanced_library_groups_enabled(True)
        existing = User.objects.create_user(
            username="lorem",
            password="private-password",
        )
        profile = UserProfile.objects.get(user=existing)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])
        fantasy = LibraryGroup.objects.create(name="Fantasy Club")
        membership = LibraryGroupMembership.objects.create(
            user=existing,
            group=fantasy,
            is_curator=False,
        )

        call_command(
            "seed_dev_users",
            users=1,
            groups=1,
            skip_shelves=True,
            verbosity=0,
        )

        membership.refresh_from_db()
        self.assertFalse(membership.is_curator)

    @override_settings(DEBUG=True)
    def test_existing_broad_role_membership_is_preserved(self):
        self.create_setup_owner()
        server_settings.set_advanced_library_groups_enabled(True)
        existing = User.objects.create_user(
            username="consectetur",
            password="private-password",
        )
        profile = UserProfile.objects.get(user=existing)
        profile.role = UserProfile.ROLE_MANAGER
        profile.save(update_fields=["role", "updated_at"])
        fantasy = LibraryGroup.objects.create(name="Fantasy Club")
        membership = LibraryGroupMembership.objects.create(
            user=existing,
            group=fantasy,
            is_curator=False,
        )

        call_command(
            "seed_dev_users",
            users=6,
            groups=1,
            skip_shelves=True,
            verbosity=0,
        )

        membership.refresh_from_db()
        self.assertFalse(membership.is_curator)
        self.assertTrue(
            LibraryGroupMembership.objects.filter(
                user=existing,
                group=get_public_group(),
                is_curator=False,
            ).exists()
        )
