from __future__ import annotations

from django.test import TestCase

from tests.library.helpers import LibraryCatalogApiFixtureMixin, response_titles


class LibraryReWrite2607CatalogBookOrderingTests(LibraryCatalogApiFixtureMixin, TestCase):
    def test_ordering_title_author_series_and_series_index(self):
        cases = [
            ("title", ["Multi Group", "Visible One", "Visible Three", "Visible Two"]),
            ("author", ["Multi Group", "Visible Two", "Visible One", "Visible Three"]),
            ("series", ["Visible Two", "Visible One", "Visible Three", "Multi Group"]),
            ("series_index", ["Visible Three", "Visible Two", "Visible One", "Multi Group"]),
        ]

        for ordering, expected in cases:
            with self.subTest(ordering=ordering):
                response = self.client.get("/api/v1/library/books/", {"ordering": ordering})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response_titles(response), expected)

    def test_invalid_ordering_returns_400(self):
        response = self.client.get("/api/v1/library/books/", {"ordering": "created_at"})

        self.assertEqual(response.status_code, 400)

    def test_pagination_plus_ordering(self):
        response = self.client.get(
            "/api/v1/library/books/",
            {"ordering": "author", "page_size": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Multi Group", "Visible Two"])
        self.assertIsNotNone(response.json()["next"])
