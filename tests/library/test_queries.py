from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from accounts.models import UserProfile
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from library.queries import visible_books_for_group, visible_books_for_user
from tests.library.helpers import queryset_titles, set_user_role


class LibraryReWrite2607QueryTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader")
        self.other = User.objects.create_user(username="other")
        self.manager = User.objects.create_user(username="manager")
        self.librarian = User.objects.create_user(username="librarian")
        self.owner = User.objects.create_superuser(username="owner")

        set_user_role(self.reader, UserProfile.ROLE_READER)
        set_user_role(self.other, UserProfile.ROLE_READER)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)
        set_user_role(self.librarian, UserProfile.ROLE_LIBRARIAN)

        self.public = LibraryGroup.objects.create(name="Common Room")
        self.club = LibraryGroup.objects.create(name="Club")
        self.hidden = LibraryGroup.objects.create(name="Hidden")

        LibraryGroupMembership.objects.create(user=self.reader, group=self.public)
        LibraryGroupMembership.objects.create(user=self.reader, group=self.club)
        LibraryGroupMembership.objects.create(user=self.other, group=self.hidden)

        self.public_book = Book.objects.create(title="Public Book")
        self.club_book = Book.objects.create(title="Club Book")
        self.hidden_book = Book.objects.create(title="Hidden Book")
        self.multi_book = Book.objects.create(title="Multi Book")

        BookGroupAssignment.objects.create(book=self.public_book, group=self.public)
        BookGroupAssignment.objects.create(book=self.club_book, group=self.club)
        BookGroupAssignment.objects.create(book=self.hidden_book, group=self.hidden)
        BookGroupAssignment.objects.create(book=self.multi_book, group=self.public)
        BookGroupAssignment.objects.create(book=self.multi_book, group=self.club)

    def test_user_sees_books_assigned_to_any_group_they_belong_to(self):
        self.assertEqual(
            queryset_titles(visible_books_for_user(self.reader, cached=False)),
            ["Club Book", "Multi Book", "Public Book"],
        )

    def test_user_does_not_see_books_only_in_unrelated_groups(self):
        self.assertNotIn(
            "Hidden Book",
            queryset_titles(visible_books_for_user(self.reader, cached=False)),
        )

    def test_manager_librarian_and_owner_have_broad_access(self):
        expected = ["Club Book", "Hidden Book", "Multi Book", "Public Book"]

        self.assertEqual(queryset_titles(visible_books_for_user(self.manager, cached=False)), expected)
        self.assertEqual(queryset_titles(visible_books_for_user(self.librarian, cached=False)), expected)
        self.assertEqual(queryset_titles(visible_books_for_user(self.owner, cached=False)), expected)

    def test_group_scoped_visibility_only_returns_books_assigned_to_that_group(self):
        self.assertEqual(
            queryset_titles(visible_books_for_group(self.reader, self.club, cached=False)),
            ["Club Book", "Multi Book"],
        )

    def test_group_scoped_visibility_hides_unviewable_groups(self):
        self.assertEqual(queryset_titles(visible_books_for_group(self.reader, self.hidden, cached=False)), [])

    def test_duplicate_group_intersections_do_not_duplicate_books(self):
        self.assertEqual(
            queryset_titles(visible_books_for_user(self.reader, cached=False)).count("Multi Book"),
            1,
        )

    def test_cached_true_reuses_cached_visible_book_ids(self):
        self.assertEqual(
            queryset_titles(visible_books_for_user(self.reader, cached=True)),
            ["Club Book", "Multi Book", "Public Book"],
        )

        new_book = Book.objects.create(title="New Book")
        BookGroupAssignment.objects.create(book=new_book, group=self.public)

        self.assertEqual(
            queryset_titles(visible_books_for_user(self.reader, cached=True)),
            ["Club Book", "Multi Book", "Public Book"],
        )

    def test_cached_false_recomputes_current_visibility(self):
        self.assertEqual(
            queryset_titles(visible_books_for_user(self.reader, cached=True)),
            ["Club Book", "Multi Book", "Public Book"],
        )

        new_book = Book.objects.create(title="New Book")
        BookGroupAssignment.objects.create(book=new_book, group=self.public)

        self.assertEqual(
            queryset_titles(visible_books_for_user(self.reader, cached=False)),
            ["Club Book", "Multi Book", "New Book", "Public Book"],
        )

    def test_cache_staleness_is_accepted_for_browse(self):
        self.assertEqual(
            queryset_titles(visible_books_for_user(self.reader, cached=True)),
            ["Club Book", "Multi Book", "Public Book"],
        )

        LibraryGroupMembership.objects.filter(user=self.reader, group=self.club).delete()

        self.assertEqual(
            queryset_titles(visible_books_for_user(self.reader, cached=True)),
            ["Club Book", "Multi Book", "Public Book"],
        )

    def test_uncached_visibility_supports_authorization_sensitive_callers(self):
        self.assertEqual(
            queryset_titles(visible_books_for_user(self.reader, cached=True)),
            ["Club Book", "Multi Book", "Public Book"],
        )

        LibraryGroupMembership.objects.filter(user=self.reader, group=self.club).delete()

        self.assertEqual(
            queryset_titles(visible_books_for_user(self.reader, cached=False)),
            ["Multi Book", "Public Book"],
        )
