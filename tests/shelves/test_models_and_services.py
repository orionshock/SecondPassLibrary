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
from shelves.services import (
    add_book_to_shelf,
    canonicalize_shelf_positions,
    create_shelf,
    move_shelf_item,
    remove_book_from_shelf,
    set_shelf_item_position,
    visible_shelf_items_for_user,
)
from shelves.policies import can_create_shelf
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
        self.curated_group = LibraryGroup.objects.create(name="Curated")
        self.curator = User.objects.create_user(username="curator", password="pw")
        LibraryGroupMembership.objects.create(
            user=self.curator,
            group=self.curated_group,
            role=LibraryGroupMembership.ROLE_CURATOR,
        )

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

    def test_group_shelf_create_policy_is_group_specific(self):
        self.assertTrue(
            can_create_shelf(
                user=self.curator,
                owner_type=Shelf.OWNER_TYPE_GROUP,
                owner_group=self.curated_group,
            )
        )
        self.assertFalse(
            can_create_shelf(
                user=self.curator,
                owner_type=Shelf.OWNER_TYPE_GROUP,
                owner_group=self.group,
            )
        )
        self.assertFalse(
            can_create_shelf(
                user=self.curator,
                owner_type=Shelf.OWNER_TYPE_GROUP,
                owner_group=self.public,
            )
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


class ShelfPositionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="positions", password="pw")
        ensure_user_public_membership(user=self.user)
        self.shelf = create_shelf(
            self.user,
            name="Ordered",
            owner_type=Shelf.OWNER_TYPE_USER,
            visibility=Shelf.VISIBILITY_PRIVATE,
        )

    def _book(self, title: str) -> Book:
        book = create_file_backed_book(title=title, assign_public=False).book
        ensure_book_public_assignment(book=book, added_by=None)
        return book

    def _items(self) -> list[ShelfItem]:
        return list(ShelfItem.objects.select_related("book").filter(shelf=self.shelf).order_by("position"))

    def _titles_and_positions(self) -> list[tuple[str, int]]:
        return [(item.book.title, item.position) for item in self._items()]

    def test_canonicalize_resolves_duplicate_positions_by_title_and_bumps_later_items(self):
        ShelfItem.objects.create(shelf=self.shelf, book=self._book("Zulu"), position=0, added_by=self.user)
        ShelfItem.objects.create(shelf=self.shelf, book=self._book("Bravo"), position=1, added_by=self.user)
        ShelfItem.objects.create(shelf=self.shelf, book=self._book("Alpha"), position=1, added_by=self.user)
        ShelfItem.objects.create(shelf=self.shelf, book=self._book("Charlie"), position=2, added_by=self.user)

        canonicalize_shelf_positions(self.shelf)

        self.assertEqual(
            self._titles_and_positions(),
            [("Zulu", 0), ("Alpha", 1), ("Bravo", 2), ("Charlie", 3)],
        )

    def test_same_title_duplicate_position_uses_stable_book_id_fallback(self):
        book_a = self._book("Same")
        book_b = self._book("Same")
        ShelfItem.objects.create(shelf=self.shelf, book=book_b, position=0, added_by=self.user)
        ShelfItem.objects.create(shelf=self.shelf, book=book_a, position=0, added_by=self.user)

        canonicalize_shelf_positions(self.shelf)

        items = self._items()
        self.assertEqual([item.position for item in items], [0, 1])
        self.assertEqual([str(item.book_id) for item in items], sorted([str(book_a.id), str(book_b.id)]))

    def test_add_assigns_unique_contiguous_position_after_legacy_duplicates(self):
        ShelfItem.objects.create(shelf=self.shelf, book=self._book("Bravo"), position=0, added_by=self.user)
        ShelfItem.objects.create(shelf=self.shelf, book=self._book("Alpha"), position=0, added_by=self.user)

        item = add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("Charlie"))

        self.assertEqual(item.position, 2)
        self.assertEqual(self._titles_and_positions(), [("Alpha", 0), ("Bravo", 1), ("Charlie", 2)])

    def test_add_with_explicit_duplicate_position_is_canonicalized_by_title(self):
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("Zulu"))
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("Bravo"))
        item = add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("Alpha"), position=1)

        self.assertEqual(item.position, 1)
        self.assertEqual(self._titles_and_positions(), [("Zulu", 0), ("Alpha", 1), ("Bravo", 2)])

    def test_remove_compacts_positions(self):
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("A"))
        item_b = add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("B"))
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("C"))

        removed = remove_book_from_shelf(self.user, shelf=self.shelf, book_or_item=item_b)

        self.assertTrue(removed)
        self.assertEqual(self._titles_and_positions(), [("A", 0), ("C", 1)])

    def test_move_canonicalizes_legacy_duplicates_before_swapping_true_neighbor(self):
        ShelfItem.objects.create(shelf=self.shelf, book=self._book("Gamma"), position=0, added_by=self.user)
        target = ShelfItem.objects.create(shelf=self.shelf, book=self._book("Zulu"), position=1, added_by=self.user)
        ShelfItem.objects.create(shelf=self.shelf, book=self._book("Alpha"), position=1, added_by=self.user)
        ShelfItem.objects.create(shelf=self.shelf, book=self._book("Omega"), position=3, added_by=self.user)

        moved = move_shelf_item(self.user, shelf=self.shelf, item=target, direction="up")

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

        moved = set_shelf_item_position(self.user, shelf=self.shelf, item=item_b, position=3)

        self.assertEqual(moved.position, 3)
        self.assertEqual(self._titles_and_positions(), [("A", 0), ("C", 1), ("D", 2), ("B", 3)])

    def test_set_position_moves_item_up_and_shifts_intervening_items_down(self):
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("A"))
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("B"))
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("C"))
        item_d = add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("D"))

        moved = set_shelf_item_position(self.user, shelf=self.shelf, item=item_d, position=1)

        self.assertEqual(moved.position, 1)
        self.assertEqual(self._titles_and_positions(), [("A", 0), ("D", 1), ("B", 2), ("C", 3)])

    def test_set_position_clamps_out_of_range_targets(self):
        item_a = add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("A"))
        add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("B"))
        item_c = add_book_to_shelf(self.user, shelf=self.shelf, book=self._book("C"))

        moved_last = set_shelf_item_position(self.user, shelf=self.shelf, item=item_a, position=99)
        self.assertEqual(moved_last.position, 2)
        self.assertEqual(self._titles_and_positions(), [("B", 0), ("C", 1), ("A", 2)])

        moved_first = set_shelf_item_position(self.user, shelf=self.shelf, item=item_c, position=-10)
        self.assertEqual(moved_first.position, 0)
        self.assertEqual(self._titles_and_positions(), [("C", 0), ("B", 1), ("A", 2)])
