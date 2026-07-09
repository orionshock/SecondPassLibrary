from __future__ import annotations

from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.server_settings import set_server_setting
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING, get_public_group, is_public_group
from library.groups.services import (
    add_book_to_group,
    add_user_to_group,
    configure_public_group,
    create_library_group,
    delete_library_group,
    ensure_book_public_assignment,
    ensure_user_public_membership,
    remove_book_from_group,
    remove_user_from_group,
    update_library_group,
)
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership


class LibraryReWrite2607GroupServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.actor = User.objects.create_user(username="actor", password="pw")
        self.user = User.objects.create_user(username="reader", password="pw")
        self.book = Book.objects.create(title="Service Book")
        self.public = configure_public_group(name="Common Room", description="Shared")

    def test_create_group_creates_normal_non_public_group(self):
        group = create_library_group(name="Club", description="Readers")

        self.assertEqual(group.name, "Club")
        self.assertEqual(group.description, "Readers")
        self.assertFalse(is_public_group(group))

    def test_update_group_changes_name_and_description(self):
        group = create_library_group(name="Old", description="Before")

        update_library_group(group=group, name="New", description="After")

        group.refresh_from_db()
        self.assertEqual(group.name, "New")
        self.assertEqual(group.description, "After")

    def test_delete_normal_group_removes_group(self):
        group = create_library_group(name="Temporary")

        deleted = delete_library_group(group=group)

        self.assertTrue(deleted)
        self.assertFalse(LibraryGroup.objects.filter(pk=group.pk).exists())

    def test_delete_public_group_is_refused(self):
        with self.assertRaises(ValidationError):
            delete_library_group(group=self.public)

        self.assertTrue(LibraryGroup.objects.filter(pk=self.public.pk).exists())

    def test_public_identity_is_setting_id_based_and_survives_rename(self):
        self.public.name = "Renamed"
        self.public.save(update_fields=["name", "updated_at"])

        self.assertTrue(is_public_group(self.public))
        self.assertEqual(get_public_group().id, self.public.id)

    def test_stale_public_setting_self_heals(self):
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(uuid4()),
            description="LibraryReWrite2607 Public/Common Room group id.",
        )

        healed = get_public_group()

        self.assertTrue(LibraryGroup.objects.filter(pk=healed.pk).exists())
        self.assertTrue(is_public_group(healed))

    def test_configure_public_group_is_idempotent(self):
        configured = configure_public_group(name="Renamed Public", description="Updated")

        self.assertEqual(configured.id, self.public.id)
        self.assertEqual(LibraryGroup.objects.count(), 1)
        self.assertEqual(configured.name, "Renamed Public")
        self.assertEqual(configured.description, "Updated")
        self.assertTrue(is_public_group(configured))

    def test_renamed_public_group_cannot_be_deleted(self):
        configure_public_group(name="Library Lobby", description="Still public")
        self.public.refresh_from_db()

        with self.assertRaises(ValidationError):
            delete_library_group(group=self.public)

        self.assertTrue(LibraryGroup.objects.filter(pk=self.public.pk).exists())

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

    def test_add_book_to_group_is_idempotent_and_stores_added_by_on_create(self):
        group = create_library_group(name="Club")

        first = add_book_to_group(book=self.book, group=group, actor=self.actor)
        second = add_book_to_group(book=self.book, group=group, actor=None)

        self.assertEqual(first.id, second.id)
        self.assertEqual(BookGroupAssignment.objects.filter(book=self.book, group=group).count(), 1)
        self.assertEqual(first.added_by, self.actor)

    def test_add_book_to_group_does_not_overwrite_existing_added_by(self):
        group = create_library_group(name="Club")
        first = add_book_to_group(book=self.book, group=group, actor=self.actor)
        other_actor = get_user_model().objects.create_user(username="other-actor", password="pw")

        second = add_book_to_group(book=self.book, group=group, actor=other_actor)

        self.assertEqual(first.id, second.id)
        second.refresh_from_db()
        self.assertEqual(second.added_by, self.actor)

    def test_remove_book_from_group_removes_assignment(self):
        group = create_library_group(name="Club")
        other = create_library_group(name="Other")
        add_book_to_group(book=self.book, group=group, actor=self.actor)
        add_book_to_group(book=self.book, group=other, actor=self.actor)

        removed = remove_book_from_group(book=self.book, group=group, actor=self.actor)

        self.assertTrue(removed)
        self.assertFalse(BookGroupAssignment.objects.filter(book=self.book, group=group).exists())
        self.assertTrue(BookGroupAssignment.objects.filter(book=self.book, group=other).exists())

    def test_removing_book_last_group_restores_public_assignment(self):
        group = create_library_group(name="Club")
        add_book_to_group(book=self.book, group=group, actor=self.actor)

        remove_book_from_group(book=self.book, group=group, actor=self.actor)

        self.assertTrue(BookGroupAssignment.objects.filter(book=self.book, group=self.public).exists())

    def test_removing_nonexistent_assignment_restores_public_if_book_has_no_groups(self):
        group = create_library_group(name="Club")

        removed = remove_book_from_group(book=self.book, group=group, actor=self.actor)

        self.assertFalse(removed)
        self.assertTrue(BookGroupAssignment.objects.filter(book=self.book, group=self.public).exists())

    def test_removing_nonexistent_assignment_preserves_existing_public(self):
        group = create_library_group(name="Club")
        ensure_book_public_assignment(book=self.book, added_by=self.actor)

        removed = remove_book_from_group(book=self.book, group=group, actor=self.actor)

        self.assertFalse(removed)
        self.assertEqual(
            BookGroupAssignment.objects.filter(book=self.book, group=self.public).count(),
            1,
        )

    def test_removing_one_of_multiple_assignments_does_not_duplicate_public_assignment(self):
        group = create_library_group(name="Club")
        ensure_book_public_assignment(book=self.book, added_by=self.actor)
        add_book_to_group(book=self.book, group=group, actor=self.actor)

        remove_book_from_group(book=self.book, group=group, actor=self.actor)

        self.assertEqual(BookGroupAssignment.objects.filter(book=self.book, group=self.public).count(), 1)

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

    def test_stale_public_setting_during_remove_book_fallback_self_heals(self):
        group = create_library_group(name="Club")
        add_book_to_group(book=self.book, group=group, actor=self.actor)
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(uuid4()),
            description="LibraryReWrite2607 Public/Common Room group id.",
        )

        remove_book_from_group(book=self.book, group=group, actor=self.actor)

        assignment = BookGroupAssignment.objects.get(book=self.book)
        self.assertTrue(is_public_group(assignment.group))

    def test_stale_public_setting_during_delete_group_fallback_self_heals(self):
        group = create_library_group(name="Club")
        add_user_to_group(user=self.user, group=group)
        add_book_to_group(book=self.book, group=group, actor=self.actor)
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(uuid4()),
            description="LibraryReWrite2607 Public/Common Room group id.",
        )

        delete_library_group(group=group, actor=self.actor)

        membership = LibraryGroupMembership.objects.get(user=self.user)
        assignment = BookGroupAssignment.objects.get(book=self.book)
        self.assertTrue(is_public_group(membership.group))
        self.assertTrue(is_public_group(assignment.group))
