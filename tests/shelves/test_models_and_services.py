from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from accounts.models import UserProfile
from library.group_services import (
    add_book_to_group,
    ensure_book_public_assignment,
    ensure_user_public_membership,
    get_public_group,
    remove_book_from_group,
)
from library.models import Book, LibraryGroup, LibraryGroupMembership
from shelves.models import Shelf, ShelfItem
from shelves.services import add_book_to_shelf, create_shelf, visible_shelf_items_for_user
from tests.utils.books import create_file_backed_book


User = get_user_model()


class ShelfModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pw")
        ensure_user_public_membership(user=self.user)
        self.group = LibraryGroup.objects.create(name="G")

    def test_shelf_requires_exactly_one_owner(self):
        shelf = Shelf(name="S", owner_type=Shelf.OWNER_TYPE_USER)
        with self.assertRaises(ValidationError):
            shelf.save()

        shelf2 = Shelf(
            name="S2",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_user=self.user,
            owner_group=self.group,
        )
        with self.assertRaises(ValidationError):
            shelf2.save()

    def test_group_shelf_visibility_must_be_private(self):
        shelf = Shelf(
            name="G",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
            visibility=Shelf.VISIBILITY_LISTED,
        )
        with self.assertRaises(ValidationError):
            shelf.save()

    def test_duplicate_book_on_shelf_is_rejected(self):
        shelf = Shelf.objects.create(
            name="S",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.user,
            visibility=Shelf.VISIBILITY_PRIVATE,
        )
        book = create_file_backed_book(title="B", assign_public=False).book
        ensure_book_public_assignment(book=book, added_by=None)
        ShelfItem.objects.create(shelf=shelf, book=book, position=0, added_by=self.user)
        with self.assertRaises(ValidationError):
            add_book_to_shelf(self.user, shelf=shelf, book=book)


class ShelfServicePolicyTests(TestCase):
    def setUp(self):
        self.public = get_public_group()

        self.owner = User.objects.create_superuser(username="owner", password="pw", email="o@example.com")
        ensure_user_public_membership(user=self.owner)

        self.reader = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.reader)
        profile, _ = UserProfile.objects.get_or_create(user=self.reader)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])

        self.other = User.objects.create_user(username="other", password="pw")
        ensure_user_public_membership(user=self.other)

        self.group = LibraryGroup.objects.create(name="Fantasy Club")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.group, role=LibraryGroupMembership.ROLE_READER)

        self.book_in_group = create_file_backed_book(title="GBook", assign_public=False).book
        add_book_to_group(actor=self.owner, book=self.book_in_group, group=self.group)

        self.book_other = create_file_backed_book(title="OtherBook", assign_public=False).book
        ensure_book_public_assignment(book=self.book_other, added_by=None)

    def test_user_cannot_create_shelf_for_other_user(self):
        with self.assertRaises(PermissionDenied):
            create_shelf(
                self.reader,
                name="S",
                owner_type=Shelf.OWNER_TYPE_USER,
                owner_user=self.other,
            )

    def test_group_shelf_only_allows_books_assigned_to_group(self):
        shelf = create_shelf(
            self.owner,
            name="GroupShelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
        )
        add_book_to_shelf(self.owner, shelf=shelf, book=self.book_in_group)
        with self.assertRaises(PermissionDenied):
            add_book_to_shelf(self.owner, shelf=shelf, book=self.book_other)

    def test_visible_items_filter_books_by_access(self):
        # reader loses access to a book by removing their membership in the owning group.
        shelf = create_shelf(
            self.reader,
            name="MyShelf",
            owner_type=Shelf.OWNER_TYPE_USER,
            visibility=Shelf.VISIBILITY_PRIVATE,
        )
        add_book_to_shelf(self.reader, shelf=shelf, book=self.book_in_group)
        self.assertEqual(visible_shelf_items_for_user(self.reader, shelf).count(), 1)

        LibraryGroupMembership.objects.filter(user=self.reader, group=self.group).delete()
        # Book remains on shelf, but is hidden until access returns.
        self.assertEqual(visible_shelf_items_for_user(self.reader, shelf).count(), 0)

    def test_removing_book_from_group_removes_from_group_shelves(self):
        shelf = create_shelf(
            self.owner,
            name="GroupShelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
        )
        add_book_to_shelf(self.owner, shelf=shelf, book=self.book_in_group)
        self.assertTrue(ShelfItem.objects.filter(shelf=shelf, book=self.book_in_group).exists())

        remove_book_from_group(actor=self.owner, book=self.book_in_group, group=self.group)
        self.assertFalse(ShelfItem.objects.filter(shelf=shelf, book=self.book_in_group).exists())
