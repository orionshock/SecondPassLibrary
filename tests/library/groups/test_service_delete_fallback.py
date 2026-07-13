from __future__ import annotations

from uuid import uuid4

from core.server_settings import set_server_setting
from library.groups.memberships import add_user_to_group
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING, is_public_group
from library.groups.services import (
    add_book_to_group,
    create_library_group,
    delete_library_group,
)
from library.models import BookGroupAssignment, LibraryGroupMembership
from tests.library.groups.service_helpers import LibraryGroupServiceTestCase


class LibraryGroupDeleteFallbackServiceTests(LibraryGroupServiceTestCase):
    def test_deleting_group_restores_affected_users_and_books_to_public(self):
        group = create_library_group(name="Club")
        add_user_to_group(user=self.user, group=group)
        add_book_to_group(book=self.book, group=group, actor=self.actor)

        delete_library_group(group=group, actor=self.actor)

        self.assertTrue(LibraryGroupMembership.objects.filter(user=self.user, group=self.public).exists())
        assignment = BookGroupAssignment.objects.get(book=self.book, group=self.public)
        self.assertEqual(assignment.added_by, self.actor)

    def test_deleting_group_does_not_add_public_for_users_or_books_with_other_groups(self):
        group = create_library_group(name="Club")
        other = create_library_group(name="Other")
        add_user_to_group(user=self.user, group=group)
        add_user_to_group(user=self.user, group=other)
        add_book_to_group(book=self.book, group=group, actor=self.actor)
        add_book_to_group(book=self.book, group=other, actor=self.actor)

        delete_library_group(group=group, actor=self.actor)

        self.assertFalse(
            LibraryGroupMembership.objects.filter(user=self.user, group=self.public).exists()
        )
        self.assertFalse(BookGroupAssignment.objects.filter(book=self.book, group=self.public).exists())
        self.assertTrue(LibraryGroupMembership.objects.filter(user=self.user, group=other).exists())
        self.assertTrue(BookGroupAssignment.objects.filter(book=self.book, group=other).exists())

    def test_stale_public_setting_during_delete_group_fallback_self_heals(self):
        group = create_library_group(name="Club")
        add_user_to_group(user=self.user, group=group)
        add_book_to_group(book=self.book, group=group, actor=self.actor)
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(uuid4()),
            description="Public/Common Room group id.",
        )

        delete_library_group(group=group, actor=self.actor)

        membership = LibraryGroupMembership.objects.get(user=self.user)
        assignment = BookGroupAssignment.objects.get(book=self.book)
        self.assertTrue(is_public_group(membership.group))
        self.assertTrue(is_public_group(assignment.group))
