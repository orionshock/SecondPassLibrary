from __future__ import annotations

from django.test import TestCase

from library.models import Author
from tests.library.helpers import (
    LibraryCatalogApiFixtureMixin,
    assert_axis_detail_ignores_list_params,
    create_catalog_book,
    response_book_counts,
    response_names,
)


class LibraryReWrite2607AuthorAxisTests(LibraryCatalogApiFixtureMixin, TestCase):
    def test_list_includes_only_authors_with_visible_books(self):
        hidden_only = Author.objects.create(name="Hidden Only", sort_name="Hidden Only")
        create_catalog_book("Hidden Only Book", author=hidden_only, group=self.hidden)

        response = self.client.get("/api/v1/library/authors/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), ["Alpha Author", "Beta Author", "Zeta Author"])

    def test_book_count_counts_visible_books_only(self):
        response = self.client.get("/api/v1/library/authors/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response_book_counts(response),
            {"Alpha Author": 2, "Beta Author": 1, "Zeta Author": 1},
        )

    def test_q_searches_name_and_sort_name(self):
        self.beta.sort_name = "Storm Writer"
        self.beta.save(update_fields=["sort_name", "updated_at"])

        by_name = self.client.get("/api/v1/library/authors/", {"q": "alpha"})
        by_sort_name = self.client.get("/api/v1/library/authors/", {"q": "storm"})

        self.assertEqual(response_names(by_name), ["Alpha Author"])
        self.assertEqual(response_names(by_sort_name), ["Beta Author"])

    def test_ordering_name_and_book_count(self):
        cases = [
            ("name", ["Alpha Author", "Beta Author", "Zeta Author"]),
            ("-name", ["Zeta Author", "Beta Author", "Alpha Author"]),
            ("book_count", ["Beta Author", "Zeta Author", "Alpha Author"]),
            ("-book_count", ["Alpha Author", "Beta Author", "Zeta Author"]),
        ]

        for ordering, expected in cases:
            with self.subTest(ordering=ordering):
                response = self.client.get("/api/v1/library/authors/", {"ordering": ordering})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response_names(response), expected)

    def test_detail_visible_succeeds(self):
        response = self.client.get(f"/api/v1/library/authors/{self.alpha.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Alpha Author")
        self.assertEqual(response.json()["book_count"], 2)

    def test_detail_ignores_list_only_params(self):
        assert_axis_detail_ignores_list_params(
            self,
            url=f"/api/v1/library/authors/{self.alpha.id}/",
            expected_name="Alpha Author",
        )

    def test_detail_with_no_visible_books_returns_404(self):
        hidden_only = Author.objects.create(name="Hidden Only", sort_name="Hidden Only")
        create_catalog_book("Hidden Only Book", author=hidden_only, group=self.hidden)

        response = self.client.get(f"/api/v1/library/authors/{hidden_only.id}/")

        self.assertEqual(response.status_code, 404)

    def test_hidden_detail_returns_404_even_with_invalid_ordering(self):
        hidden_only = Author.objects.create(name="Hidden Only", sort_name="Hidden Only")
        create_catalog_book("Hidden Only Book", author=hidden_only, group=self.hidden)

        response = self.client.get(
            f"/api/v1/library/authors/{hidden_only.id}/",
            {"ordering": "created_at"},
        )

        self.assertEqual(response.status_code, 404)

    def test_invalid_ordering_returns_400(self):
        response = self.client.get("/api/v1/library/authors/", {"ordering": "created_at"})

        self.assertEqual(response.status_code, 400)

    def test_pagination_composes_with_ordering(self):
        response = self.client.get(
            "/api/v1/library/authors/",
            {"ordering": "-name", "page_size": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), ["Zeta Author", "Beta Author"])
        self.assertIsNotNone(response.json()["next"])
