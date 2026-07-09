from __future__ import annotations

from django.test import TestCase

from library.models import Series
from tests.library.helpers import (
    LibraryCatalogApiFixtureMixin,
    create_catalog_book,
    response_book_counts,
    response_names,
)


class LibraryReWrite2607SeriesAxisTests(LibraryCatalogApiFixtureMixin, TestCase):
    def test_list_includes_only_series_with_visible_books(self):
        hidden_only = Series.objects.create(name="Hidden Series", sort_name="Hidden Series")
        create_catalog_book(
            "Hidden Series Book",
            author=self.alpha,
            series=hidden_only,
            group=self.hidden,
        )

        response = self.client.get("/api/v1/library/series/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), ["First Series", "Second Series"])

    def test_book_count_counts_visible_books_only(self):
        response = self.client.get("/api/v1/library/series/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_book_counts(response), {"First Series": 2, "Second Series": 1})

    def test_q_searches_name_and_sort_name(self):
        self.second_series.sort_name = "Storm Sequence"
        self.second_series.save(update_fields=["sort_name", "updated_at"])

        by_name = self.client.get("/api/v1/library/series/", {"q": "first"})
        by_sort_name = self.client.get("/api/v1/library/series/", {"q": "storm"})

        self.assertEqual(response_names(by_name), ["First Series"])
        self.assertEqual(response_names(by_sort_name), ["Second Series"])

    def test_ordering_name_and_book_count(self):
        cases = [
            ("name", ["First Series", "Second Series"]),
            ("-name", ["Second Series", "First Series"]),
            ("book_count", ["Second Series", "First Series"]),
            ("-book_count", ["First Series", "Second Series"]),
        ]

        for ordering, expected in cases:
            with self.subTest(ordering=ordering):
                response = self.client.get("/api/v1/library/series/", {"ordering": ordering})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response_names(response), expected)

    def test_detail_visible_succeeds(self):
        response = self.client.get(f"/api/v1/library/series/{self.first_series.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "First Series")
        self.assertEqual(response.json()["book_count"], 2)

    def test_detail_with_no_visible_books_returns_404(self):
        hidden_only = Series.objects.create(name="Hidden Series", sort_name="Hidden Series")
        create_catalog_book(
            "Hidden Series Book",
            author=self.alpha,
            series=hidden_only,
            group=self.hidden,
        )

        response = self.client.get(f"/api/v1/library/series/{hidden_only.id}/")

        self.assertEqual(response.status_code, 404)

    def test_invalid_ordering_returns_400(self):
        response = self.client.get("/api/v1/library/series/", {"ordering": "created_at"})

        self.assertEqual(response.status_code, 400)
