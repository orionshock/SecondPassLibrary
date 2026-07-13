from __future__ import annotations

from django.contrib.auth import get_user_model
from unittest.mock import patch
from uuid import uuid4

from core.server_settings import set_server_setting
from library.groups.book_assignments import (
    add_book_to_group,
    ensure_book_public_assignment,
    remove_book_from_group,
)
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING, is_public_group
from library.groups.services import create_library_group
from library.models import BookGroupAssignment
from shelves.models import Shelf, ShelfItem
from tests.library.groups.service_helpers import LibraryGroupServiceTestCase


class LibraryBookAssignmentServiceTests(LibraryGroupServiceTestCase):
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

    def test_remove_book_from_group_cleans_same_group_shelf_items(self):
        group = create_library_group(name="Club")
        add_book_to_group(book=self.book, group=group, actor=self.actor)
        shelf = Shelf.objects.create(
            name="Club Shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=group,
            created_by=self.actor,
        )
        ShelfItem.objects.create(
            shelf=shelf, book=self.book, position=0, added_by=self.actor
        )

        removed = remove_book_from_group(book=self.book, group=group, actor=self.actor)

        self.assertTrue(removed)
        self.assertFalse(ShelfItem.objects.filter(shelf=shelf, book=self.book).exists())

    def test_remove_book_from_group_rolls_back_assignment_when_hook_fails(self):
        group = create_library_group(name="Club")
        add_book_to_group(book=self.book, group=group, actor=self.actor)

        with self.assertRaisesMessage(
            RuntimeError,
            "hook failed",
        ), patch(
            "library.groups.book_assignments.remove_book_from_group_owned_shelves",
            side_effect=RuntimeError("hook failed"),
        ):
            remove_book_from_group(book=self.book, group=group, actor=self.actor)

        self.assertTrue(BookGroupAssignment.objects.filter(book=self.book, group=group).exists())
        self.assertFalse(BookGroupAssignment.objects.filter(book=self.book, group=self.public).exists())

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

    def test_stale_public_setting_during_remove_book_fallback_self_heals(self):
        group = create_library_group(name="Club")
        add_book_to_group(book=self.book, group=group, actor=self.actor)
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(uuid4()),
            description="Public/Common Room group id.",
        )

        remove_book_from_group(book=self.book, group=group, actor=self.actor)

        assignment = BookGroupAssignment.objects.get(book=self.book)
        self.assertTrue(is_public_group(assignment.group))
