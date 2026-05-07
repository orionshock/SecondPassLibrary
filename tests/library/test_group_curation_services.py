from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from accounts.models import UserProfile
from core import policies
from library.group_services import (
    add_book_to_group,
    ensure_book_public_assignment,
    ensure_user_public_membership,
    get_public_group,
    remove_book_from_group,
)
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership, is_public_group


User = get_user_model()


class GroupCurationServicesTest(TestCase):
    def setUp(self):
        self.public = get_public_group()
        self.assertTrue(is_public_group(self.public))
        self.assertEqual(
            self.public.discoverability, LibraryGroup.DISCOVERABILITY_LISTED
        )

        self.owner = User.objects.create_superuser(
            username="owner", email="owner@example.com", password="pw"
        )
        self.manager = User.objects.create_user(
            username="manager", email="manager@example.com", password="pw"
        )
        self.librarian = User.objects.create_user(
            username="librarian", email="librarian@example.com", password="pw"
        )
        self.reader = User.objects.create_user(
            username="reader", email="reader@example.com", password="pw"
        )
        self.curator = User.objects.create_user(
            username="curator", email="curator@example.com", password="pw"
        )

        for user, role in (
            (self.manager, UserProfile.ROLE_MANAGER),
            (self.librarian, UserProfile.ROLE_LIBRARIAN),
            (self.reader, UserProfile.ROLE_READER),
            (self.curator, UserProfile.ROLE_READER),
        ):
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.save(update_fields=["role", "updated_at"])
            ensure_user_public_membership(user=user)

        ensure_user_public_membership(user=self.owner)

        self.group = LibraryGroup.objects.create(name="Group", slug="group")
        LibraryGroupMembership.objects.create(
            user=self.curator,
            group=self.group,
            role=LibraryGroupMembership.ROLE_CURATOR,
        )

        self.group_reader_only = LibraryGroup.objects.create(name="ReaderOnly", slug="reader-only")
        LibraryGroupMembership.objects.create(
            user=self.curator,
            group=self.group_reader_only,
            role=LibraryGroupMembership.ROLE_READER,
        )

        self.book_public = Book.objects.create(title="Public")
        ensure_book_public_assignment(book=self.book_public, added_by=None)

        self.book_hidden = Book.objects.create(title="Hidden")
        hidden_group = LibraryGroup.objects.create(name="Hidden", slug="hidden")
        other_user = User.objects.create_user(username="other", email="other@example.com", password="pw")
        ensure_user_public_membership(user=other_user)
        LibraryGroupMembership.objects.create(user=other_user, group=hidden_group, role=LibraryGroupMembership.ROLE_READER)
        BookGroupAssignment.objects.create(book=self.book_hidden, group=hidden_group, added_by=self.owner)

    def test_manager_can_add_book_to_group(self):
        assignment = add_book_to_group(actor=self.manager, book=self.book_public, group=self.group)
        self.assertEqual(cast(Any, assignment).book_id, self.book_public.id)
        self.assertEqual(cast(Any, assignment).group_id, self.group.id)

    def test_librarian_can_add_book_to_group(self):
        assignment = add_book_to_group(actor=self.librarian, book=self.book_public, group=self.group)
        self.assertEqual(cast(Any, assignment).book_id, self.book_public.id)
        self.assertEqual(cast(Any, assignment).group_id, self.group.id)

    def test_reader_cannot_add_book_to_group(self):
        with self.assertRaises(PermissionDenied):
            add_book_to_group(actor=self.reader, book=self.book_public, group=self.group)

    def test_curator_can_add_visible_book_to_their_non_public_group(self):
        self.assertTrue(policies.can_view_book(user=self.curator, book=self.book_public))
        assignment = add_book_to_group(actor=self.curator, book=self.book_public, group=self.group)
        self.assertEqual(cast(Any, assignment).book_id, self.book_public.id)
        self.assertEqual(cast(Any, assignment).group_id, self.group.id)

    def test_curator_cannot_add_inaccessible_book_to_their_group(self):
        self.assertFalse(policies.can_view_book(user=self.curator, book=self.book_hidden))
        with self.assertRaises(PermissionDenied):
            add_book_to_group(actor=self.curator, book=self.book_hidden, group=self.group)

    def test_curator_cannot_add_book_to_public(self):
        with self.assertRaises(PermissionDenied):
            add_book_to_group(actor=self.curator, book=self.book_public, group=self.public)

    def test_add_existing_assignment_is_idempotent(self):
        a1 = add_book_to_group(actor=self.manager, book=self.book_public, group=self.group)
        a2 = add_book_to_group(actor=self.manager, book=self.book_public, group=self.group)
        self.assertEqual(a1.id, a2.id)
        self.assertEqual(BookGroupAssignment.objects.filter(book=self.book_public, group=self.group).count(), 1)

    def test_curator_can_remove_book_from_their_non_public_group(self):
        add_book_to_group(actor=self.manager, book=self.book_public, group=self.group)
        removed = remove_book_from_group(actor=self.curator, book=self.book_public, group=self.group)
        self.assertTrue(removed)
        self.assertFalse(BookGroupAssignment.objects.filter(book=self.book_public, group=self.group).exists())

    def test_curator_cannot_remove_book_from_public(self):
        self.assertTrue(BookGroupAssignment.objects.filter(book=self.book_public, group=self.public).exists())
        with self.assertRaises(PermissionDenied):
            remove_book_from_group(actor=self.curator, book=self.book_public, group=self.public)

    def test_curator_cannot_remove_book_from_group_where_they_are_only_reader(self):
        add_book_to_group(actor=self.manager, book=self.book_public, group=self.group_reader_only)
        with self.assertRaises(PermissionDenied):
            remove_book_from_group(actor=self.curator, book=self.book_public, group=self.group_reader_only)

    def test_removing_last_assignment_reassigns_public(self):
        book = Book.objects.create(title="OnlyGroup")
        BookGroupAssignment.objects.create(book=book, group=self.group, added_by=self.owner)
        self.assertFalse(BookGroupAssignment.objects.filter(book=book, group=self.public).exists())

        removed = remove_book_from_group(actor=self.manager, book=book, group=self.group)
        self.assertTrue(removed)
        self.assertTrue(BookGroupAssignment.objects.filter(book=book, group=self.public).exists())

    def test_removing_one_of_multiple_assignments_does_not_add_public_unnecessarily(self):
        book = Book.objects.create(title="Multi")
        group_a = LibraryGroup.objects.create(name="A", slug="a")
        group_b = LibraryGroup.objects.create(name="B", slug="b")
        BookGroupAssignment.objects.create(book=book, group=group_a, added_by=self.owner)
        BookGroupAssignment.objects.create(book=book, group=group_b, added_by=self.owner)

        removed = remove_book_from_group(actor=self.manager, book=book, group=group_a)
        self.assertTrue(removed)
        groups = set(BookGroupAssignment.objects.filter(book=book).values_list("group__slug", flat=True))
        self.assertEqual(groups, {"b"})

