from __future__ import annotations

from django.test import TestCase

from tests.library.helpers import LibraryCatalogApiFixtureMixin, response_titles


class LibraryReWrite2607CatalogBookOrderingTests(LibraryCatalogApiFixtureMixin, TestCase):
    def test_ordering_supports_allowed_book_axes_in_both_directions(self):
        cases = [
            ("title", ["Multi Group", "Visible One", "Visible Three", "Visible Two"]),
            ("-title", ["Visible Two", "Visible Three", "Visible One", "Multi Group"]),
            ("author", ["Multi Group", "Visible Two", "Visible One", "Visible Three"]),
            ("-author", ["Visible Three", "Visible One", "Visible Two", "Multi Group"]),
            ("series", ["Visible Two", "Visible One", "Visible Three", "Multi Group"]),
            ("-series", ["Visible Three", "Visible Two", "Visible One", "Multi Group"]),
            ("series_index", ["Visible Three", "Visible Two", "Visible One", "Multi Group"]),
            ("-series_index", ["Visible One", "Visible Two", "Visible Three", "Multi Group"]),
            ("publisher", ["Visible Two", "Visible One", "Visible Three", "Multi Group"]),
            ("-publisher", ["Visible Three", "Visible One", "Visible Two", "Multi Group"]),
        ]

        for ordering, expected in cases:
            with self.subTest(ordering=ordering):
                response = self.client.get("/api/v1/library/books/", {"ordering": ordering})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response_titles(response), expected)

    def test_invalid_ordering_returns_400(self):
        response = self.client.get("/api/v1/library/books/", {"ordering": "created_at"})

        self.assertEqual(response.status_code, 400)

    def test_internal_field_orderings_are_rejected(self):
        rejected = [
            "file_format",
            "checksum",
            "file_size",
            "source_filename",
            "book_file",
            "identifiers",
            "created_at",
            "updated_at",
            "published_year",
        ]

        for ordering in rejected:
            with self.subTest(ordering=ordering):
                response = self.client.get("/api/v1/library/books/", {"ordering": ordering})
                self.assertEqual(response.status_code, 400)

    def test_pagination_plus_ordering(self):
        response = self.client.get(
            "/api/v1/library/books/",
            {"ordering": "-author", "page_size": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Visible Three", "Visible One"])
        self.assertIsNotNone(response.json()["next"])
