from __future__ import annotations

from unittest.mock import patch

from library.groups.services import (
    add_book_to_group,
    add_user_to_group,
    create_library_group,
    remove_book_from_group,
    remove_user_from_group,
)
from library.models import BookGroupAssignment, LibraryGroupMembership
from library.queries import visible_books_for_user
from tests.library.groups.service_helpers import LibraryGroupServiceTestCase
from tests.library.helpers import queryset_titles


class LibraryReWrite2607GroupServiceCacheInvalidationTests(LibraryGroupServiceTestCase):
    def test_add_book_to_group_invalidates_cached_visibility(self):
        group = create_library_group(name="Club")
        LibraryGroupMembership.objects.create(user=self.user, group=group)
        self.assertEqual(queryset_titles(visible_books_for_user(self.user, cached=True)), [])

        with self.captureOnCommitCallbacks(execute=True):
            add_book_to_group(book=self.book, group=group, actor=self.actor)

        self.assertEqual(
            queryset_titles(visible_books_for_user(self.user, cached=True)),
            ["Service Book"],
        )

    def test_remove_book_from_group_invalidates_cached_visibility(self):
        group = create_library_group(name="Club")
        LibraryGroupMembership.objects.create(user=self.user, group=group)
        BookGroupAssignment.objects.create(book=self.book, group=group)
        self.assertEqual(
            queryset_titles(visible_books_for_user(self.user, cached=True)),
            ["Service Book"],
        )

        with self.captureOnCommitCallbacks(execute=True):
            remove_book_from_group(book=self.book, group=group, actor=self.actor)

        self.assertEqual(queryset_titles(visible_books_for_user(self.user, cached=True)), [])

    def test_add_user_to_group_invalidates_cached_visibility(self):
        group = create_library_group(name="Club")
        BookGroupAssignment.objects.create(book=self.book, group=group)
        self.assertEqual(queryset_titles(visible_books_for_user(self.user, cached=True)), [])

        with self.captureOnCommitCallbacks(execute=True):
            add_user_to_group(user=self.user, group=group)

        self.assertEqual(
            queryset_titles(visible_books_for_user(self.user, cached=True)),
            ["Service Book"],
        )

    def test_remove_user_from_group_invalidates_cached_visibility(self):
        group = create_library_group(name="Club")
        LibraryGroupMembership.objects.create(user=self.user, group=group)
        BookGroupAssignment.objects.create(book=self.book, group=group)
        self.assertEqual(
            queryset_titles(visible_books_for_user(self.user, cached=True)),
            ["Service Book"],
        )

        with self.captureOnCommitCallbacks(execute=True):
            remove_user_from_group(user=self.user, group=group)

        self.assertEqual(queryset_titles(visible_books_for_user(self.user, cached=True)), [])

    def test_failed_remove_book_hook_does_not_invalidate_cache(self):
        group = create_library_group(name="Club")
        LibraryGroupMembership.objects.create(user=self.user, group=group)
        BookGroupAssignment.objects.create(book=self.book, group=group)

        with patch(
            "library.groups.services.invalidate_visible_books_cache"
        ) as invalidate, patch(
            "library.groups.services.remove_book_from_group_owned_shelves",
            side_effect=RuntimeError("hook failed"),
        ):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                with self.assertRaisesMessage(RuntimeError, "hook failed"):
                    remove_book_from_group(book=self.book, group=group, actor=self.actor)

        self.assertEqual(callbacks, [])
        invalidate.assert_not_called()
        self.assertTrue(BookGroupAssignment.objects.filter(book=self.book, group=group).exists())
