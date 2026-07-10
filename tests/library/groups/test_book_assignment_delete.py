from __future__ import annotations

from shelves.library_hooks import SHELVES_GROUP_BOOK_REMOVAL_PENDING_MESSAGE

from library.models import BookGroupAssignment
from tests.library.groups.book_assignment_helpers import LibraryGroupBookAssignmentApiTestCase


class LibraryReWrite2607GroupBookAssignmentDeleteTests(
    LibraryGroupBookAssignmentApiTestCase
):
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

    def test_existing_assignment_returns_409_while_shelves_hook_is_pending(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.delete(self.group_book_detail_url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], SHELVES_GROUP_BOOK_REMOVAL_PENDING_MESSAGE)

    def test_hook_failure_leaves_assignment_in_place(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.delete(self.group_book_detail_url())

        self.assertEqual(response.status_code, 409)
        self.assertTrue(
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
