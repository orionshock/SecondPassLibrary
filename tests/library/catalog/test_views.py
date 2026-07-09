from __future__ import annotations

from django.test import TestCase

from tests.library.helpers import LibraryCatalogApiFixtureMixin, response_titles


class LibraryReWrite2607CatalogBookViewTests(LibraryCatalogApiFixtureMixin, TestCase):
    def test_visible_book_list_excludes_books_outside_user_groups(self):
        response = self.client.get("/api/v1/library/books/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response_titles(response),
            ["Multi Group", "Visible One", "Visible Three", "Visible Two"],
        )

    def test_broad_role_can_list_all_books(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.get("/api/v1/library/books/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response_titles(response),
            ["Hidden Dresden", "Multi Group", "Visible One", "Visible Three", "Visible Two"],
        )

    def test_retrieve_visible_book_succeeds(self):
        response = self.client.get(f"/api/v1/library/books/{self.visible_one.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Visible One")
        self.assertEqual(response.json()["description"], "dresden case file")

    def test_retrieve_invisible_book_returns_404(self):
        response = self.client.get(f"/api/v1/library/books/{self.hidden_book.id}/")

        self.assertEqual(response.status_code, 404)

    def test_overlapping_group_visibility_does_not_duplicate_rows(self):
        response = self.client.get("/api/v1/library/books/", {"q": "multi"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Multi Group"])
