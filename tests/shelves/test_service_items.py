from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from library.models import Book, BookGroupAssignment, LibraryGroupMembership
from shelves import item_services
from shelves.models import Shelf, ShelfItem
from shelves.item_queries import visible_shelf_items_for_user
from shelves.item_services import (
    add_book_to_shelf,
    canonicalize_shelf_positions,
    move_shelf_item,
    remove_book_from_shelf,
    set_shelf_item_position,
)
from shelves.services import create_shelf
from tests.shelves.service_helpers import ShelfServiceFixtureMixin
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book
from tests.utils.library_visibility import (
    ensure_public_book_assignment,
    ensure_public_membership,
)


User = get_user_model()


class ShelfServiceItemTests(ShelfServiceFixtureMixin, TestCase):
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

        LibraryGroupMembership.objects.filter(
            user=self.reader, group=self.group
        ).delete()
        # Book remains on shelf, but is hidden until access returns.
        self.assertEqual(visible_shelf_items_for_user(self.reader, shelf).count(), 0)

    def test_user_shelf_rechecks_book_visibility_inside_locked_mutation(self):
        shelf = create_shelf(
            self.reader,
            name="Private",
            owner_type=Shelf.OWNER_TYPE_USER,
            visibility=Shelf.VISIBILITY_PRIVATE,
        )
        original_lock = item_services._lock_shelf_and_items

        def remove_access_after_lock(target_shelf):
            locked = original_lock(target_shelf)
            LibraryGroupMembership.objects.filter(
                user=self.reader,
                group=self.group,
            ).delete()
            return locked

        with patch(
            "shelves.item_services._lock_shelf_and_items",
            side_effect=remove_access_after_lock,
        ):
            with self.assertRaises(PermissionDenied):
                add_book_to_shelf(
                    self.reader,
                    shelf=shelf,
                    book=self.book_in_group,
                )

        self.assertFalse(ShelfItem.objects.filter(shelf=shelf).exists())

    def test_group_shelf_rechecks_exact_assignment_inside_locked_mutation(self):
        shelf = create_shelf(
            self.owner,
            name="Group",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.group,
        )
        original_lock = item_services._lock_shelf_and_items

        def remove_assignment_after_lock(target_shelf):
            locked = original_lock(target_shelf)
            BookGroupAssignment.objects.filter(
                book=self.book_in_group,
                group=self.group,
            ).delete()
            return locked

        with patch(
            "shelves.item_services._lock_shelf_and_items",
            side_effect=remove_assignment_after_lock,
        ):
            with self.assertRaises(PermissionDenied):
                add_book_to_shelf(
                    self.owner,
                    shelf=shelf,
                    book=self.book_in_group,
                )

        self.assertFalse(ShelfItem.objects.filter(shelf=shelf).exists())

    def test_group_shelf_rechecks_actor_authority_inside_locked_mutation(self):
        book = create_file_backed_book(title="Curated Book", assign_public=False).book
        BookGroupAssignment.objects.create(book=book, group=self.curated_group)
        shelf = create_shelf(
            self.curator,
            name="Curated",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.curated_group,
        )
        original_lock = item_services._lock_shelf_and_items

        def remove_authority_after_lock(target_shelf):
            locked = original_lock(target_shelf)
            LibraryGroupMembership.objects.filter(
                user=self.curator,
                group=self.curated_group,
            ).delete()
            return locked

        with patch(
            "shelves.item_services._lock_shelf_and_items",
            side_effect=remove_authority_after_lock,
        ):
            with self.assertRaises(PermissionDenied):
                add_book_to_shelf(self.curator, shelf=shelf, book=book)

        self.assertFalse(ShelfItem.objects.filter(shelf=shelf).exists())


class ShelfPositionServiceTests(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="positions", password="pw")
        ensure_public_membership(self.user)
        self.shelf = create_shelf(
            self.user,
            name="Ordered",
            owner_type=Shelf.OWNER_TYPE_USER,
            visibility=Shelf.VISIBILITY_PRIVATE,
        )

    def _book(self, title: str) -> Book:
        book = create_file_backed_book(title=title, assign_public=False).book
        ensure_public_book_assignment(book)
        return book

    def _items(self) -> list[ShelfItem]:
        return list(
            ShelfItem.objects.select_related("book")
            .filter(shelf=self.shelf)
            .order_by("position")
        )

    def _titles_and_positions(self) -> list[tuple[str, int]]:
        return [(item.book.title, item.position) for item in self._items()]

    def test_canonicalize_resolves_duplicate_positions_by_title_and_bumps_later_items(
        self,
    ):
        ShelfItem.objects.create(
            shelf=self.shelf, book=self._book("Zulu"), position=0, added_by=self.user
        )
        ShelfItem.objects.create(
            shelf=self.shelf, book=self._book("Bravo"), position=1, added_by=self.user
        )
        ShelfItem.objects.create(
            shelf=self.shelf, book=self._book("Alpha"), position=1, added_by=self.user
        )
        ShelfItem.objects.create(
            shelf=self.shelf, book=self._book("Charlie"), position=2, added_by=self.user
        )

        canonicalize_shelf_positions(self.shelf)

        self.assertEqual(
            self._titles_and_positions(),
            [("Zulu", 0), ("Alpha", 1), ("Bravo", 2), ("Charlie", 3)],
        )

    def test_same_title_duplicate_position_uses_stable_book_id_fallback(self):
        book_a = self._book("Same")
        book_b = self._book("Same")
        ShelfItem.objects.create(
            shelf=self.shelf, book=book_b, position=0, added_by=self.user
        )
        ShelfItem.objects.create(
            shelf=self.shelf, book=book_a, position=0, added_by=self.user
        )

        canonicalize_shelf_positions(self.shelf)

        items = self._items()
        self.assertEqual([item.position for item in items], [0, 1])
        self.assertEqual(
            [str(item.book_id) for item in items],
            sorted([str(book_a.id), str(book_b.id)]),
        )

    def test_add_assigns_unique_contiguous_position_after_legacy_duplicates(self):
        ShelfItem.objects.create(
            shelf=self.shelf, book=self._book("Bravo"), position=0, added_by=self.user
        )
        ShelfItem.objects.create(
            shelf=self.shelf, book=self._book("Alpha"), position=0, added_by=self.user
        )

        item = add_book_to_shelf(
            self.user, shelf=self.shelf, book=self._book("Charlie")
        )

        self.assertEqual(item.position, 2)
        self.assertEqual(
            self._titles_and_positions(), [("Alpha", 0), ("Bravo", 1), ("Charlie", 2)]
        )

    def test_add_with_explicit_duplicate_position_is_canonicalized_by_title(self):
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("Zulu"))
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("Bravo"))
        item = add_book_to_shelf(
            self.user, shelf=self.shelf, book=self._book("Alpha"), position=1
        )

        self.assertEqual(item.position, 1)
        self.assertEqual(
            self._titles_and_positions(), [("Zulu", 0), ("Alpha", 1), ("Bravo", 2)]
        )

    def test_remove_compacts_positions(self):
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("A"))
        item_b = add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("B"))
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("C"))

        removed = remove_book_from_shelf(
            self.user, shelf=self.shelf, book_or_item=item_b
        )

        self.assertTrue(removed)
        self.assertEqual(self._titles_and_positions(), [("A", 0), ("C", 1)])

    def test_move_canonicalizes_legacy_duplicates_before_swapping_true_neighbor(self):
        ShelfItem.objects.create(
            shelf=self.shelf, book=self._book("Gamma"), position=0, added_by=self.user
        )
        target = ShelfItem.objects.create(
            shelf=self.shelf, book=self._book("Zulu"), position=1, added_by=self.user
        )
        ShelfItem.objects.create(
            shelf=self.shelf, book=self._book("Alpha"), position=1, added_by=self.user
        )
        ShelfItem.objects.create(
            shelf=self.shelf, book=self._book("Omega"), position=3, added_by=self.user
        )

        moved = move_shelf_item(
            self.user, shelf=self.shelf, item=target, direction="up"
        )

        self.assertEqual(moved.position, 1)
        self.assertEqual(
            self._titles_and_positions(),
            [("Gamma", 0), ("Zulu", 1), ("Alpha", 2), ("Omega", 3)],
        )

    def test_boundary_move_canonicalizes_without_changing_order(self):
        first = add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("A"))
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("B"))

        moved = move_shelf_item(self.user, shelf=self.shelf, item=first, direction="up")

        self.assertEqual(moved.position, 0)
        self.assertEqual(self._titles_and_positions(), [("A", 0), ("B", 1)])

    def test_set_position_moves_item_down_and_shifts_intervening_items_up(self):
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("A"))
        item_b = add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("B"))
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("C"))
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("D"))

        moved = set_shelf_item_position(
            self.user, shelf=self.shelf, item=item_b, position=3
        )

        self.assertEqual(moved.position, 3)
        self.assertEqual(
            self._titles_and_positions(), [("A", 0), ("C", 1), ("D", 2), ("B", 3)]
        )

    def test_set_position_moves_item_up_and_shifts_intervening_items_down(self):
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("A"))
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("B"))
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("C"))
        item_d = add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("D"))

        moved = set_shelf_item_position(
            self.user, shelf=self.shelf, item=item_d, position=1
        )

        self.assertEqual(moved.position, 1)
        self.assertEqual(
            self._titles_and_positions(), [("A", 0), ("D", 1), ("B", 2), ("C", 3)]
        )

    def test_set_position_clamps_out_of_range_targets(self):
        item_a = add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("A"))
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("B"))
        item_c = add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("C"))

        moved_last = set_shelf_item_position(
            self.user, shelf=self.shelf, item=item_a, position=99
        )
        self.assertEqual(moved_last.position, 2)
        self.assertEqual(self._titles_and_positions(), [("B", 0), ("C", 1), ("A", 2)])

        moved_first = set_shelf_item_position(
            self.user, shelf=self.shelf, item=item_c, position=-10
        )
        self.assertEqual(moved_first.position, 0)
        self.assertEqual(self._titles_and_positions(), [("C", 0), ("B", 1), ("A", 2)])
