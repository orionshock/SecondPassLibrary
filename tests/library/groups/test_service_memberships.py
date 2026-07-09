from __future__ import annotations

from uuid import uuid4

from core.server_settings import set_server_setting
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING, is_public_group
from library.groups.services import (
    add_user_to_group,
    create_library_group,
    ensure_user_public_membership,
    remove_user_from_group,
)
from library.models import LibraryGroupMembership
from tests.library.groups.service_helpers import LibraryGroupServiceTestCase


class LibraryReWrite2607GroupMembershipServiceTests(LibraryGroupServiceTestCase):
    def test_add_user_to_group_is_idempotent(self):
        group = create_library_group(name="Club")

        first = add_user_to_group(user=self.user, group=group, is_curator=True)
        second = add_user_to_group(user=self.user, group=group, is_curator=True)

        self.assertEqual(first.id, second.id)
        self.assertEqual(LibraryGroupMembership.objects.filter(user=self.user, group=group).count(), 1)
        self.assertTrue(second.is_curator)

    def test_remove_user_from_group_removes_membership(self):
        group = create_library_group(name="Club")
        other = create_library_group(name="Other")
        add_user_to_group(user=self.user, group=group)
        add_user_to_group(user=self.user, group=other)

        removed = remove_user_from_group(user=self.user, group=group)

        self.assertTrue(removed)
        self.assertFalse(LibraryGroupMembership.objects.filter(user=self.user, group=group).exists())
        self.assertTrue(LibraryGroupMembership.objects.filter(user=self.user, group=other).exists())

    def test_removing_user_last_group_restores_public_membership(self):
        group = create_library_group(name="Club")
        add_user_to_group(user=self.user, group=group)

        remove_user_from_group(user=self.user, group=group)

        self.assertTrue(LibraryGroupMembership.objects.filter(user=self.user, group=self.public).exists())

    def test_removing_nonexistent_membership_restores_public_if_user_has_no_groups(self):
        group = create_library_group(name="Club")

        removed = remove_user_from_group(user=self.user, group=group)

        self.assertFalse(removed)
        self.assertTrue(LibraryGroupMembership.objects.filter(user=self.user, group=self.public).exists())

    def test_removing_nonexistent_membership_preserves_existing_public(self):
        group = create_library_group(name="Club")
        ensure_user_public_membership(user=self.user)

        removed = remove_user_from_group(user=self.user, group=group)

        self.assertFalse(removed)
        self.assertEqual(
            LibraryGroupMembership.objects.filter(user=self.user, group=self.public).count(),
            1,
        )

    def test_removing_one_of_multiple_memberships_does_not_duplicate_public_membership(self):
        group = create_library_group(name="Club")
        ensure_user_public_membership(user=self.user)
        add_user_to_group(user=self.user, group=group)

        remove_user_from_group(user=self.user, group=group)

        self.assertEqual(LibraryGroupMembership.objects.filter(user=self.user, group=self.public).count(), 1)

    def test_stale_public_setting_during_remove_user_fallback_self_heals(self):
        group = create_library_group(name="Club")
        add_user_to_group(user=self.user, group=group)
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(uuid4()),
            description="LibraryReWrite2607 Public/Common Room group id.",
        )

        remove_user_from_group(user=self.user, group=group)

        membership = LibraryGroupMembership.objects.get(user=self.user)
        self.assertTrue(is_public_group(membership.group))
