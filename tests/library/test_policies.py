from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from accounts.models import UserProfile
from core.server_settings import set_server_setting
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from library.policies import (
    can_add_book_to_group,
    can_create_library_group,
    can_curate_group,
    can_delete_library_group,
    can_download_book,
    can_edit_group_description,
    can_edit_group_presentation,
    can_import_books,
    can_manage_group_books,
    can_manage_group_identity,
    can_manage_group_membership,
    can_remove_book_from_group,
    can_view_book,
    can_view_library_group,
)
from library.queries import visible_books_for_user
from tests.library.helpers import set_user_role


class LibraryReWrite2607PolicyTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.curator = User.objects.create_user(username="curator", password="pw")
        self.other = User.objects.create_user(username="other", password="pw")
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        for user in [self.reader, self.curator, self.other]:
            set_user_role(user, UserProfile.ROLE_READER)
        set_user_role(self.librarian, UserProfile.ROLE_LIBRARIAN)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)

        self.public = LibraryGroup.objects.create(name="Common Room")
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(self.public.id),
            description="LibraryReWrite2607 Public/Common Room group id.",
        )
        self.club = LibraryGroup.objects.create(name="Club")
        self.source = LibraryGroup.objects.create(name="Source")
        self.hidden = LibraryGroup.objects.create(name="Hidden")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.club)
        LibraryGroupMembership.objects.create(user=self.curator, group=self.club, is_curator=True)
        LibraryGroupMembership.objects.create(user=self.curator, group=self.source)

        self.club_book = Book.objects.create(title="Club Book")
        self.source_book = Book.objects.create(title="Source Book")
        self.hidden_book = Book.objects.create(title="Hidden Book")
        BookGroupAssignment.objects.create(book=self.club_book, group=self.club)
        BookGroupAssignment.objects.create(book=self.source_book, group=self.source)
        BookGroupAssignment.objects.create(book=self.hidden_book, group=self.hidden)

    def test_can_view_book_uses_uncached_visibility(self):
        self.assertEqual(list(visible_books_for_user(self.reader, cached=True)), [self.club_book])
        BookGroupAssignment.objects.filter(book=self.club_book, group=self.club).delete()

        self.assertFalse(can_view_book(user=self.reader, book=self.club_book))

    def test_can_download_book_matches_view_book(self):
        self.assertTrue(can_download_book(user=self.reader, book=self.club_book))
        self.assertFalse(can_download_book(user=self.reader, book=self.hidden_book))

    def test_can_import_books_role_behavior(self):
        self.assertFalse(can_import_books(self.reader))
        self.assertTrue(can_import_books(self.librarian))
        self.assertTrue(can_import_books(self.manager))
        self.assertTrue(can_import_books(self.owner))

    def test_group_create_delete_identity_and_membership_role_behavior(self):
        for user in [self.reader, self.librarian]:
            with self.subTest(user=user.username):
                self.assertFalse(can_create_library_group(user))
                self.assertFalse(can_delete_library_group(user, self.club))
                self.assertFalse(can_manage_group_identity(user=user, group=self.club))
                self.assertFalse(can_manage_group_membership(user=user, group=self.club))

        for user in [self.manager, self.owner]:
            with self.subTest(user=user.username):
                self.assertTrue(can_create_library_group(user))
                self.assertTrue(can_delete_library_group(user, self.club))
                self.assertTrue(can_manage_group_identity(user=user, group=self.club))
                self.assertTrue(can_manage_group_membership(user=user, group=self.club))

    def test_public_group_delete_is_protected(self):
        self.assertFalse(can_delete_library_group(self.manager, self.public))
        self.assertFalse(can_delete_library_group(self.owner, self.public))

    def test_can_view_library_group_visible_and_invisible_behavior(self):
        self.assertTrue(can_view_library_group(user=self.reader, group=self.club))
        self.assertFalse(can_view_library_group(user=self.reader, group=self.hidden))
        self.assertTrue(can_view_library_group(user=self.manager, group=self.hidden))

    def test_can_curate_group_for_curator_and_broad_roles(self):
        self.assertTrue(can_curate_group(user=self.curator, group=self.club))
        self.assertFalse(can_curate_group(user=self.reader, group=self.club))
        self.assertTrue(can_curate_group(user=self.librarian, group=self.club))
        self.assertTrue(can_curate_group(user=self.manager, group=self.club))
        self.assertTrue(can_curate_group(user=self.owner, group=self.club))

    def test_public_group_curator_membership_does_not_grant_curation(self):
        LibraryGroupMembership.objects.create(user=self.other, group=self.public, is_curator=True)

        self.assertFalse(can_curate_group(user=self.other, group=self.public))

    def test_group_book_presentation_and_description_policies_follow_curation(self):
        for policy in [
            can_manage_group_books,
            can_edit_group_presentation,
            can_edit_group_description,
        ]:
            with self.subTest(policy=policy.__name__):
                self.assertTrue(policy(user=self.curator, group=self.club))
                self.assertFalse(policy(user=self.reader, group=self.club))

    def test_can_add_book_to_group_broad_role_allowed(self):
        self.assertTrue(
            can_add_book_to_group(user=self.librarian, book=self.hidden_book, group=self.club)
        )
        self.assertTrue(
            can_add_book_to_group(user=self.manager, book=self.hidden_book, group=self.club)
        )
        self.assertTrue(can_add_book_to_group(user=self.owner, book=self.hidden_book, group=self.club))

    def test_can_add_book_to_group_curator_requires_current_book_visibility(self):
        self.assertTrue(can_add_book_to_group(user=self.curator, book=self.source_book, group=self.club))
        BookGroupAssignment.objects.filter(book=self.source_book, group=self.source).delete()

        self.assertFalse(can_add_book_to_group(user=self.curator, book=self.source_book, group=self.club))
        self.assertFalse(can_add_book_to_group(user=self.curator, book=self.hidden_book, group=self.club))

    def test_can_remove_book_from_group_curator_and_broad_role_behavior(self):
        self.assertFalse(can_remove_book_from_group(user=self.reader, book=self.club_book, group=self.club))
        self.assertTrue(can_remove_book_from_group(user=self.curator, book=self.club_book, group=self.club))
        self.assertTrue(can_remove_book_from_group(user=self.librarian, book=self.club_book, group=self.club))
        self.assertTrue(can_remove_book_from_group(user=self.manager, book=self.club_book, group=self.club))
        self.assertTrue(can_remove_book_from_group(user=self.owner, book=self.club_book, group=self.club))
