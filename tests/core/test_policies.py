from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import UserProfile
from accounts import policies as account_policies
from library import policies as library_policies
from library.groups.services import (
    ensure_book_public_assignment,
    ensure_user_public_membership,
)
from library.models import (
    BookGroupAssignment,
    LibraryGroup,
    LibraryGroupMembership,
)
from library.groups.public_group import get_public_group, is_public_group
from tests.utils.books import create_file_backed_book


User = get_user_model()


class PolicyTest(TestCase):
    def setUp(self):
        self.public = get_public_group()
        self.assertTrue(is_public_group(self.public))

        self.owner = User.objects.create_superuser(
            username="owner", email="owner@example.com", password="pw"
        )
        self.manager = User.objects.create_user(
            username="manager", email="manager@example.com", password="pw"
        )
        self.manager2 = User.objects.create_user(
            username="manager2", email="manager2@example.com", password="pw"
        )
        self.librarian = User.objects.create_user(
            username="librarian", email="librarian@example.com", password="pw"
        )
        self.reader = User.objects.create_user(
            username="reader", email="reader@example.com", password="pw"
        )

        for user, role in (
            (self.manager, UserProfile.ROLE_MANAGER),
            (self.manager2, UserProfile.ROLE_MANAGER),
            (self.librarian, UserProfile.ROLE_LIBRARIAN),
            (self.reader, UserProfile.ROLE_READER),
        ):
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.save(update_fields=["role", "updated_at"])
            ensure_user_public_membership(user=user)

        ensure_user_public_membership(user=self.owner)

        self.book = create_file_backed_book(title="Public Book", assign_public=False).book
        ensure_book_public_assignment(book=self.book)

        self.hidden_group = LibraryGroup.objects.create(name="Hidden")
        LibraryGroupMembership.objects.create(
            user=self.reader,
            group=self.hidden_group,
        )

        self.hidden_book = create_file_backed_book(title="Hidden Book", assign_public=False).book
        BookGroupAssignment.objects.create(book=self.hidden_book, group=self.hidden_group)

    def test_owner_can_manage_library_and_users(self):
        self.assertTrue(account_policies.is_owner(self.owner))
        self.assertTrue(library_policies.can_manage_library(self.owner))
        self.assertTrue(account_policies.can_manage_users(self.owner))

    def test_manager_can_manage_users_but_not_assign_manager(self):
        self.assertTrue(account_policies.is_manager(self.manager))
        self.assertTrue(account_policies.can_manage_users(self.manager))
        self.assertTrue(
            account_policies.can_assign_global_role(
                actor=self.manager,
                target_user=self.reader,
                new_role=UserProfile.ROLE_READER,
            )
        )
        self.assertFalse(
            account_policies.can_assign_global_role(
                actor=self.manager,
                target_user=self.reader,
                new_role=UserProfile.ROLE_MANAGER,
            )
        )

    def test_owner_can_promote_and_demote_manager(self):
        target = User.objects.create_user(
            username="target", email="target@example.com", password="pw"
        )
        ensure_user_public_membership(user=target)
        profile, _ = UserProfile.objects.get_or_create(user=target)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])

        self.assertTrue(
            account_policies.can_assign_global_role(
                actor=self.owner, target_user=target, new_role=UserProfile.ROLE_MANAGER
            )
        )
        self.assertFalse(
            account_policies.can_assign_global_role(
                actor=self.manager, target_user=target, new_role=UserProfile.ROLE_MANAGER
            )
        )

        # Only Owner can demote an existing Manager.
        profile.role = UserProfile.ROLE_MANAGER
        profile.save(update_fields=["role", "updated_at"])
        self.assertTrue(
            account_policies.can_assign_global_role(
                actor=self.owner, target_user=target, new_role=UserProfile.ROLE_READER
            )
        )
        self.assertFalse(
            account_policies.can_assign_global_role(
                actor=self.manager, target_user=target, new_role=UserProfile.ROLE_READER
            )
        )

    def test_manager_can_manage_user_only_if_target_is_not_owner_or_manager(self):
        self.assertFalse(account_policies.can_manage_user(actor=self.manager, target_user=self.owner))
        self.assertFalse(
            account_policies.can_manage_user(actor=self.manager, target_user=self.manager2)
        )
        self.assertTrue(
            account_policies.can_manage_user(actor=self.manager, target_user=self.reader)
        )
        self.assertFalse(
            account_policies.can_manage_user(actor=self.librarian, target_user=self.reader)
        )

    def test_librarian_can_manage_library_not_users(self):
        self.assertTrue(account_policies.is_librarian(self.librarian))
        self.assertTrue(library_policies.can_manage_library(self.librarian))
        self.assertFalse(account_policies.can_manage_users(self.librarian))
        self.assertFalse(library_policies.can_create_library_group(self.librarian))

    def test_reader_cannot_manage_library(self):
        self.assertTrue(account_policies.is_reader(self.reader))
        self.assertFalse(library_policies.can_manage_library(self.reader))
        self.assertFalse(library_policies.can_create_library_group(self.reader))

    def test_manager_and_owner_can_create_library_groups(self):
        self.assertTrue(library_policies.can_create_library_group(self.owner))
        self.assertTrue(library_policies.can_create_library_group(self.manager))

    def test_reader_can_view_books_only_in_groups_they_belong_to(self):
        # Public book is visible only via Public membership.
        self.assertTrue(library_policies.can_view_book(user=self.reader, book=self.book))
        # Hidden book is visible only if user is in Hidden.
        self.assertTrue(library_policies.can_view_book(user=self.reader, book=self.hidden_book))

        other_reader = User.objects.create_user(
            username="other", email="other@example.com", password="pw"
        )
        profile, _ = UserProfile.objects.get_or_create(user=other_reader)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])
        ensure_user_public_membership(user=other_reader)
        self.assertFalse(library_policies.can_view_book(user=other_reader, book=self.hidden_book))

    def test_user_without_public_membership_cannot_view_public_only_books(self):
        fantasy = LibraryGroup.objects.create(name="Fantasy")
        book_public_only = create_file_backed_book(title="Public Only", assign_public=False).book
        ensure_book_public_assignment(book=book_public_only)

        book_fantasy = create_file_backed_book(title="Fantasy Only", assign_public=False).book
        BookGroupAssignment.objects.create(book=book_fantasy, group=fantasy)

        u = User.objects.create_user(username="fantasy", email="fantasy@example.com", password="pw")
        profile, _ = UserProfile.objects.get_or_create(user=u)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])

        # Add a non-Public membership, then remove Public so the user remains in at least one group.
        LibraryGroupMembership.objects.create(user=u, group=fantasy)
        LibraryGroupMembership.objects.filter(user=u, group=self.public).delete()
        self.assertFalse(LibraryGroupMembership.objects.filter(user=u, group=self.public).exists())

        self.assertFalse(library_policies.can_view_book(user=u, book=book_public_only))
        self.assertTrue(library_policies.can_view_book(user=u, book=book_fantasy))

    def test_group_visibility_is_membership_based(self):
        other = LibraryGroup.objects.create(name="Other")
        self.assertTrue(library_policies.can_view_library_group(user=self.reader, group=self.public))
        self.assertTrue(library_policies.can_view_library_group(user=self.reader, group=self.hidden_group))
        self.assertFalse(library_policies.can_view_library_group(user=self.reader, group=other))

    def test_group_management_helpers(self):
        group = LibraryGroup.objects.create(name="G")

        # Identity: Owner/Manager only; Public identity is protected.
        self.assertTrue(library_policies.can_manage_group_identity(user=self.owner, group=group))
        self.assertTrue(
            library_policies.can_manage_group_identity(user=self.manager, group=group)
        )
        self.assertFalse(
            library_policies.can_manage_group_identity(user=self.librarian, group=group)
        )
        self.assertFalse(library_policies.can_manage_group_identity(user=self.reader, group=group))
        self.assertFalse(library_policies.can_manage_group_identity(user=self.owner, group=self.public))

        # Membership: Owner/Manager only.
        self.assertTrue(
            library_policies.can_manage_group_membership(user=self.owner, group=group)
        )
        self.assertTrue(
            library_policies.can_manage_group_membership(user=self.manager, group=group)
        )
        self.assertFalse(
            library_policies.can_manage_group_membership(user=self.librarian, group=group)
        )

        # Presentation (description): Owner/Manager/Librarian, or Curator for their group; never for Public.
        LibraryGroupMembership.objects.create(
            user=self.reader, group=group, is_curator=True
        )
        self.assertTrue(library_policies.can_edit_group_presentation(user=self.librarian, group=group))
        self.assertTrue(library_policies.can_edit_group_presentation(user=self.reader, group=group))

        # Description: Public description is editable by Owner/Manager/Librarian, but not Reader/Curator.
        self.assertTrue(library_policies.can_edit_group_description(user=self.owner, group=self.public))
        self.assertTrue(
            library_policies.can_edit_group_description(user=self.manager, group=self.public)
        )
        self.assertTrue(
            library_policies.can_edit_group_description(user=self.librarian, group=self.public)
        )
        self.assertFalse(
            library_policies.can_edit_group_description(user=self.reader, group=self.public)
        )

    def test_curator_rules(self):
        fantasy = LibraryGroup.objects.create(name="Fantasy")
        LibraryGroupMembership.objects.create(
            user=self.reader, group=fantasy, is_curator=True
        )
        self.assertTrue(library_policies.can_curate_group(user=self.reader, group=fantasy))
        self.assertFalse(library_policies.can_curate_group(user=self.reader, group=self.public))
        self.assertTrue(library_policies.can_curate_group(user=self.owner, group=self.public))
        self.assertTrue(library_policies.can_curate_group(user=self.manager, group=self.public))
        self.assertTrue(library_policies.can_curate_group(user=self.librarian, group=self.public))

    def test_curator_authority_is_exact_group_scoped(self):
        fantasy = LibraryGroup.objects.create(name="Fantasy")
        mystery = LibraryGroup.objects.create(name="Mystery")
        LibraryGroupMembership.objects.create(
            user=self.reader, group=fantasy, is_curator=True
        )
        LibraryGroupMembership.objects.create(user=self.reader, group=mystery)

        self.assertTrue(library_policies.can_curate_group(user=self.reader, group=fantasy))
        self.assertFalse(library_policies.can_curate_group(user=self.reader, group=mystery))
        self.assertTrue(library_policies.can_manage_group_books(user=self.reader, group=fantasy))
        self.assertFalse(library_policies.can_manage_group_books(user=self.reader, group=mystery))

    def test_broad_roles_retain_group_book_authority_without_curator_flag(self):
        group = LibraryGroup.objects.create(name="G")
        self.assertTrue(library_policies.can_manage_group_books(user=self.owner, group=group))
        self.assertTrue(library_policies.can_manage_group_books(user=self.manager, group=group))
        self.assertTrue(library_policies.can_manage_group_books(user=self.librarian, group=group))
        self.assertTrue(library_policies.can_curate_group(user=self.owner, group=group))
        self.assertTrue(library_policies.can_curate_group(user=self.manager, group=group))
        self.assertTrue(library_policies.can_curate_group(user=self.librarian, group=group))

    def test_public_group_cannot_have_curators(self):
        with self.assertRaises(ValidationError):
            LibraryGroupMembership.objects.create(
                user=self.reader,
                group=self.public,
                is_curator=True,
            )
