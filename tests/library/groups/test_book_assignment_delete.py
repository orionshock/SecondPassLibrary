from __future__ import annotations

from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured

from library.models import Book, BookGroupAssignment, LibraryGroupMembership
from shelves.models import Shelf, ShelfItem
from tests.library.groups.book_assignment_helpers import LibraryGroupBookAssignmentApiTestCase


class LibraryGroupBookAssignmentDeleteTests(
    LibraryGroupBookAssignmentApiTestCase
):
    def test_librarian_and_exact_curator_can_remove_group_books(self):
        for username in ["librarian", "curator"]:
            with self.subTest(username=username):
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))
                response = self.client.delete(self.group_book_detail_url())
                self.assertEqual(response.status_code, 204)
                self.assertFalse(
                    BookGroupAssignment.objects.filter(
                        book=self.club_book, group=self.club
                    ).exists()
                )
                BookGroupAssignment.objects.create(
                    book=self.club_book, group=self.club, added_by=self.owner
                )

    def test_reader_cannot_delete_visible_group_book_assignment(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.delete(self.group_book_detail_url())

        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            BookGroupAssignment.objects.filter(book=self.club_book, group=self.club).exists()
        )

    def test_hidden_group_returns_404_before_hook_behavior(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.delete(
            self.group_book_detail_url(group=self.hidden, book=self.hidden_book)
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            BookGroupAssignment.objects.filter(book=self.hidden_book, group=self.hidden).exists()
        )

    def test_existing_assignment_delete_removes_assignment(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.delete(self.group_book_detail_url())

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            BookGroupAssignment.objects.filter(book=self.club_book, group=self.club).exists()
        )

    def test_absent_assignment_delete_is_idempotent_204_for_existing_group_and_book(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.delete(self.group_book_detail_url(book=self.source_book))

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            BookGroupAssignment.objects.filter(book=self.source_book, group=self.club).exists()
        )

    def test_unknown_book_delete_returns_404(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.delete(
            f"{self.group_books_url()}00000000-0000-0000-0000-000000000001/"
        )

        self.assertEqual(response.status_code, 404)

    def test_cleanup_conflict_returns_409_and_rolls_back_all_group_book_state(self):
        shelf = Shelf.objects.create(
            name="Club Shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.club,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.manager,
        )
        shelf_item = ShelfItem.objects.create(
            shelf=shelf,
            book=self.club_book,
            position=0,
            added_by=self.manager,
        )
        unrelated = Book.objects.create(
            title="Unrelated",
            checksum="a" * 64,
            book_file="books/aa/aa/unrelated.epub",
            cover_file="covers/bb/bb/unrelated.jpg",
        )
        unrelated_assignment = BookGroupAssignment.objects.create(
            book=unrelated,
            group=self.source,
            added_by=self.owner,
        )
        membership_count = LibraryGroupMembership.objects.count()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        with patch(
            "library.groups.book_assignments.remove_book_from_group_owned_shelves",
            side_effect=ImproperlyConfigured("Shelf cleanup unavailable."),
        ):
            response = self.client.delete(self.group_book_detail_url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"detail": "Shelf cleanup unavailable."})
        self.assertTrue(
            BookGroupAssignment.objects.filter(
                book=self.club_book, group=self.club
            ).exists()
        )
        self.assertTrue(Shelf.objects.filter(pk=shelf.pk).exists())
        self.assertTrue(ShelfItem.objects.filter(pk=shelf_item.pk).exists())
        self.assertTrue(Book.objects.filter(pk=unrelated.pk).exists())
        self.assertTrue(
            BookGroupAssignment.objects.filter(pk=unrelated_assignment.pk).exists()
        )
        unrelated.refresh_from_db()
        self.assertEqual(unrelated.book_file.name, "books/aa/aa/unrelated.epub")
        self.assertEqual(unrelated.cover_file.name, "covers/bb/bb/unrelated.jpg")
        self.assertEqual(LibraryGroupMembership.objects.count(), membership_count)
