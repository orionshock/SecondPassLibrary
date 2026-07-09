from __future__ import annotations

from django.test import TestCase

from tests.library.helpers import LibraryCatalogApiFixtureMixin, response_titles


class LibraryReWrite2607CatalogBookFilterTests(LibraryCatalogApiFixtureMixin, TestCase):
    def test_q_searches_visible_books_only(self):
        response = self.client.get("/api/v1/library/books/", {"q": "dresden"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Visible One"])

    def test_author_filter(self):
        response = self.client.get("/api/v1/library/books/", {"author": self.alpha.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Multi Group", "Visible Two"])

    def test_series_filter(self):
        response = self.client.get("/api/v1/library/books/", {"series": self.first_series.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Visible Two", "Visible One"])

    def test_tag_filter(self):
        response = self.client.get("/api/v1/library/books/", {"tag": self.fantasy.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Visible One", "Visible Three"])

    def test_filters_compose(self):
        response = self.client.get(
            "/api/v1/library/books/",
            {"author": self.beta.id, "tag": self.fantasy.id, "q": "visible"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Visible One"])
