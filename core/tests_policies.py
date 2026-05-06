from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserProfile
from library.group_services import (
    ensure_book_public_assignment,
    ensure_user_public_membership,
    get_public_group,
)
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership, is_public_group
from django.core.exceptions import ValidationError

from . import policies


User = get_user_model()


class PolicyTest(TestCase):
    def setUp(self):
        self.public = get_public_group()
        self.assertTrue(is_public_group(self.public))
        self.assertEqual(self.public.discoverability, LibraryGroup.DISCOVERABILITY_LISTED)

        self.owner = User.objects.create_superuser(username="owner", email="owner@example.com", password="pw")
        self.manager = User.objects.create_user(username="manager", email="manager@example.com", password="pw")
        self.librarian = User.objects.create_user(username="librarian", email="librarian@example.com", password="pw")
        self.reader = User.objects.create_user(username="reader", email="reader@example.com", password="pw")

        for user, role in (
            (self.manager, UserProfile.ROLE_MANAGER),
            (self.librarian, UserProfile.ROLE_LIBRARIAN),
            (self.reader, UserProfile.ROLE_READER),
        ):
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.save(update_fields=["role", "updated_at"])
            ensure_user_public_membership(user=user)

        ensure_user_public_membership(user=self.owner)

        self.book = Book.objects.create(title="Public Book")
        ensure_book_public_assignment(book=self.book)

        self.hidden_group = LibraryGroup.objects.create(name="Hidden", slug="hidden")
        LibraryGroupMembership.objects.create(
            user=self.reader, group=self.hidden_group, role=LibraryGroupMembership.ROLE_READER
        )

        self.hidden_book = Book.objects.create(title="Hidden Book")
        BookGroupAssignment.objects.create(book=self.hidden_book, group=self.hidden_group)

    def test_owner_can_manage_library_and_users(self):
        self.assertTrue(policies.is_owner(self.owner))
        self.assertTrue(policies.can_manage_library(self.owner))
        self.assertTrue(policies.can_manage_users(self.owner))

    def test_manager_can_manage_users_but_not_assign_manager(self):
        self.assertTrue(policies.is_manager(self.manager))
        self.assertTrue(policies.can_manage_users(self.manager))
        self.assertTrue(
            policies.can_assign_global_role(
                actor=self.manager, target_user=self.reader, new_role=UserProfile.ROLE_READER
            )
        )
        self.assertFalse(
            policies.can_assign_global_role(
                actor=self.manager, target_user=self.reader, new_role=UserProfile.ROLE_MANAGER
            )
        )

    def test_librarian_can_manage_library_not_users(self):
        self.assertTrue(policies.is_librarian(self.librarian))
        self.assertTrue(policies.can_manage_library(self.librarian))
        self.assertFalse(policies.can_manage_users(self.librarian))

    def test_reader_cannot_manage_library(self):
        self.assertTrue(policies.is_reader(self.reader))
        self.assertFalse(policies.can_manage_library(self.reader))

    def test_reader_can_view_books_only_in_groups_they_belong_to(self):
        # Public book is visible to all via Public membership.
        self.assertTrue(policies.can_view_book(user=self.reader, book=self.book))
        # Hidden book is visible only if user is in Hidden.
        self.assertTrue(policies.can_view_book(user=self.reader, book=self.hidden_book))

        other_reader = User.objects.create_user(username="other", email="other@example.com", password="pw")
        profile, _ = UserProfile.objects.get_or_create(user=other_reader)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])
        ensure_user_public_membership(user=other_reader)
        self.assertFalse(policies.can_view_book(user=other_reader, book=self.hidden_book))

    def test_group_discoverability_does_not_grant_or_restrict_access(self):
        unlisted = LibraryGroup.objects.create(
            name="Unlisted",
            slug="unlisted",
            discoverability=LibraryGroup.DISCOVERABILITY_UNLISTED,
        )
        LibraryGroupMembership.objects.create(
            user=self.reader, group=unlisted, role=LibraryGroupMembership.ROLE_READER
        )
        unlisted_book = Book.objects.create(title="Unlisted Book")
        BookGroupAssignment.objects.create(book=unlisted_book, group=unlisted)
        self.assertTrue(policies.can_view_book(user=self.reader, book=unlisted_book))

    def test_curator_rules(self):
        fantasy = LibraryGroup.objects.create(name="Fantasy", slug="fantasy")
        LibraryGroupMembership.objects.create(
            user=self.reader, group=fantasy, role=LibraryGroupMembership.ROLE_CURATOR
        )
        self.assertTrue(policies.can_curate_group(user=self.reader, group=fantasy))
        self.assertFalse(policies.can_curate_group(user=self.reader, group=self.public))

    def test_public_group_cannot_have_curators(self):
        with self.assertRaises(ValidationError):
            LibraryGroupMembership.objects.create(
                user=self.reader,
                group=self.public,
                role=LibraryGroupMembership.ROLE_CURATOR,
            )
