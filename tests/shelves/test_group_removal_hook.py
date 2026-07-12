from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from library.groups.services import add_book_to_group, remove_book_from_group
from library.models import BookGroupAssignment, LibraryGroup
from shelves.models import Shelf, ShelfItem
from shelves.services import add_book_to_shelf, create_shelf, visible_shelf_items_for_user
from tests.shelves.service_helpers import ShelfServiceFixtureMixin
from tests.utils.books import create_file_backed_book


class ShelfGroupRemovalHookTests(ShelfServiceFixtureMixin, TestCase):
    def test_removing_book_from_group_removes_item_from_same_group_shelf(self):
        shelf = create_shelf(
            self.owner,
            name="GroupShelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
        )
        add_book_to_shelf(self.owner, shelf=shelf, book=self.book_in_group)
        self.assertTrue(
            ShelfItem.objects.filter(shelf=shelf, book=self.book_in_group).exists()
        )

        remove_book_from_group(
            actor=self.owner, book=self.book_in_group, group=self.group
        )
        self.assertFalse(
            ShelfItem.objects.filter(shelf=shelf, book=self.book_in_group).exists()
        )
        self.assertEqual(visible_shelf_items_for_user(self.owner, shelf).count(), 0)

    def test_group_removal_hook_leaves_user_and_other_group_shelves_untouched(self):
        user_shelf = create_shelf(
            self.reader,
            name="UserShelf",
            owner_type=Shelf.OWNER_TYPE_USER,
            visibility=Shelf.VISIBILITY_PRIVATE,
        )
        add_book_to_shelf(self.reader, shelf=user_shelf, book=self.book_in_group)

        other_group = LibraryGroup.objects.create(name="Other Group")
        add_book_to_group(actor=self.owner, book=self.book_in_group, group=other_group)
        other_group_shelf = create_shelf(
            self.owner,
            name="OtherGroupShelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=other_group,
        )
        add_book_to_shelf(self.owner, shelf=other_group_shelf, book=self.book_in_group)

        remove_book_from_group(
            actor=self.owner, book=self.book_in_group, group=self.group
        )

        self.assertTrue(
            ShelfItem.objects.filter(shelf=user_shelf, book=self.book_in_group).exists()
        )
        self.assertTrue(
            ShelfItem.objects.filter(
                shelf=other_group_shelf, book=self.book_in_group
            ).exists()
        )

    def test_group_removal_hook_canonicalizes_positions(self):
        books = [self.book_in_group]
        for title in ("Second", "Third"):
            book = create_file_backed_book(title=title, assign_public=False).book
            add_book_to_group(actor=self.owner, book=book, group=self.group)
            books.append(book)
        shelf = create_shelf(
            self.owner,
            name="GroupShelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
        )
        for position, book in enumerate(books):
            ShelfItem.objects.create(
                shelf=shelf, book=book, position=position, added_by=self.owner
            )

        remove_book_from_group(actor=self.owner, book=books[1], group=self.group)

        self.assertEqual(
            list(
                ShelfItem.objects.filter(shelf=shelf)
                .order_by("position")
                .values_list("position", flat=True)
            ),
            [0, 1],
        )
        self.assertFalse(ShelfItem.objects.filter(shelf=shelf, book=books[1]).exists())

    def test_public_group_shelf_item_is_removed_only_when_public_assignment_removed(self):
        add_book_to_group(actor=self.owner, book=self.book_other, group=self.group)
        public_shelf = create_shelf(
            self.owner,
            name="PublicShelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.public,
        )
        group_shelf = create_shelf(
            self.owner,
            name="GroupShelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
        )
        ShelfItem.objects.create(
            shelf=public_shelf, book=self.book_other, position=0, added_by=self.owner
        )
        ShelfItem.objects.create(
            shelf=group_shelf, book=self.book_other, position=0, added_by=self.owner
        )

        remove_book_from_group(actor=self.owner, book=self.book_other, group=self.group)
        self.assertTrue(
            ShelfItem.objects.filter(shelf=public_shelf, book=self.book_other).exists()
        )
        self.assertFalse(
            ShelfItem.objects.filter(shelf=group_shelf, book=self.book_other).exists()
        )

        remove_book_from_group(actor=self.owner, book=self.book_other, group=self.public)
        self.assertFalse(
            ShelfItem.objects.filter(shelf=public_shelf, book=self.book_other).exists()
        )

    def test_group_removal_hook_is_idempotent(self):
        shelf = create_shelf(
            self.owner,
            name="GroupShelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
        )
        add_book_to_shelf(self.owner, shelf=shelf, book=self.book_in_group)

        remove_book_from_group(actor=self.owner, book=self.book_in_group, group=self.group)
        removed_again = remove_book_from_group(
            actor=self.owner, book=self.book_in_group, group=self.group
        )

        self.assertFalse(removed_again)
        self.assertFalse(
            ShelfItem.objects.filter(shelf=shelf, book=self.book_in_group).exists()
        )

    def test_group_removal_rolls_back_assignment_when_hook_fails(self):
        shelf = create_shelf(
            self.owner,
            name="GroupShelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
        )
        add_book_to_shelf(self.owner, shelf=shelf, book=self.book_in_group)

        with patch(
            "library.groups.services.remove_book_from_group_owned_shelves",
            side_effect=RuntimeError("boom"),
        ):
            with self.assertRaises(RuntimeError):
                remove_book_from_group(
                    actor=self.owner, book=self.book_in_group, group=self.group
                )

        self.assertTrue(
            BookGroupAssignment.objects.filter(
                book=self.book_in_group, group=self.group
            ).exists()
        )
        self.assertTrue(
            ShelfItem.objects.filter(shelf=shelf, book=self.book_in_group).exists()
        )
