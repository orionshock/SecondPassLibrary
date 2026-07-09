from __future__ import annotations

from django.test import TestCase

from library.models import CatalogTag
from tests.library.helpers import (
    LibraryCatalogApiFixtureMixin,
    create_catalog_book,
    response_book_counts,
    response_names,
)


class LibraryReWrite2607TagAxisTests(LibraryCatalogApiFixtureMixin, TestCase):
    def test_list_includes_only_tags_with_visible_books(self):
        hidden_only = CatalogTag.objects.create(name="Hidden Tag", normalized_name="hidden")
        create_catalog_book("Hidden Tag Book", author=self.alpha, tag=hidden_only, group=self.hidden)

        response = self.client.get("/api/v1/library/tags/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), ["Fantasy", "Mystery"])

    def test_book_count_counts_visible_books_only(self):
        response = self.client.get("/api/v1/library/tags/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_book_counts(response), {"Fantasy": 2, "Mystery": 1})

    def test_q_searches_name_sort_name_and_normalized_name(self):
        self.fantasy.sort_name = "Speculative"
        self.fantasy.save(update_fields=["sort_name", "updated_at"])

        by_name = self.client.get("/api/v1/library/tags/", {"q": "mystery"})
        by_sort_name = self.client.get("/api/v1/library/tags/", {"q": "speculative"})
        by_normalized = self.client.get("/api/v1/library/tags/", {"q": "fantasy"})

        self.assertEqual(response_names(by_name), ["Mystery"])
        self.assertEqual(response_names(by_sort_name), ["Fantasy"])
        self.assertEqual(response_names(by_normalized), ["Fantasy"])

    def test_ordering_name_and_book_count(self):
        cases = [
            ("name", ["Fantasy", "Mystery"]),
            ("-name", ["Mystery", "Fantasy"]),
            ("book_count", ["Mystery", "Fantasy"]),
            ("-book_count", ["Fantasy", "Mystery"]),
        ]

        for ordering, expected in cases:
            with self.subTest(ordering=ordering):
                response = self.client.get("/api/v1/library/tags/", {"ordering": ordering})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response_names(response), expected)

    def test_detail_visible_succeeds(self):
        response = self.client.get(f"/api/v1/library/tags/{self.fantasy.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Fantasy")
        self.assertEqual(response.json()["normalized_name"], "fantasy")
        self.assertEqual(response.json()["book_count"], 2)

    def test_detail_with_no_visible_books_returns_404(self):
        hidden_only = CatalogTag.objects.create(name="Hidden Tag", normalized_name="hidden")
        create_catalog_book("Hidden Tag Book", author=self.alpha, tag=hidden_only, group=self.hidden)

        response = self.client.get(f"/api/v1/library/tags/{hidden_only.id}/")

        self.assertEqual(response.status_code, 404)

    def test_invalid_ordering_returns_400(self):
        response = self.client.get("/api/v1/library/tags/", {"ordering": "created_at"})

        self.assertEqual(response.status_code, 400)
