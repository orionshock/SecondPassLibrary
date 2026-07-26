from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from shelves.models import Shelf, ShelfItem
from shelves.item_services import add_book_to_shelf
from library.models import LibraryGroup
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book
from tests.utils.library_visibility import (
    ensure_public_book_assignment,
    ensure_public_membership,
)


User = get_user_model()


class ShelfModelTests(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pw")
        ensure_public_membership(self.user)
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
        ensure_public_book_assignment(book)
        ShelfItem.objects.create(shelf=shelf, book=book, position=0, added_by=self.user)
        with self.assertRaises(ValidationError):
            add_book_to_shelf(self.user, shelf=shelf, book=book)
