from django.test import TestCase

from library.models import BookAuthor, BookCatalogTag
from tests.library.helpers import LibraryCatalogApiFixtureMixin


def aggregate_counts(response):
    return {row["name"]: row["book_count"] for row in response.json()["catalog_tags"]}


class CatalogResultTagAggregateTests(LibraryCatalogApiFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        BookCatalogTag.objects.create(book=self.visible_one, catalog_tag=self.mystery)

    def test_book_aggregates_follow_filters_not_pagination(self):
        endpoint = "/api/v1/library/books/"
        BookAuthor.objects.create(
            book=self.visible_one,
            author=self.alpha,
            position=1,
        )

        first_page = self.client.get(
            endpoint,
            {"q": "visible", "page_size": 1, "page": 1},
        )
        second_page = self.client.get(
            endpoint,
            {"q": "visible", "page_size": 1, "page": 2},
        )
        selected = self.client.get(endpoint, {"tag": "fantasy", "page_size": 1})

        self.assertEqual(aggregate_counts(first_page), {"Fantasy": 2, "Mystery": 2})
        self.assertEqual(aggregate_counts(second_page), aggregate_counts(first_page))
        self.assertEqual(aggregate_counts(selected), {"Fantasy": 2, "Mystery": 1})

    def test_book_search_aggregates_use_broad_search_and_selected_tag(self):
        response = self.client.get(
            "/api/v1/library/search",
            {"q": "beta", "tag": "fantasy"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(aggregate_counts(response), {"Fantasy": 1, "Mystery": 1})

    def test_author_aggregates_count_distinct_books_for_matching_authors(self):
        response = self.client.get("/api/v1/library/authors/", {"q": "alpha"})
        selected = self.client.get(
            "/api/v1/library/authors/",
            {"q": "beta", "tag": "fantasy"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(aggregate_counts(response), {"Mystery": 1})
        self.assertEqual(aggregate_counts(selected), {"Fantasy": 1, "Mystery": 1})

    def test_series_aggregates_count_distinct_books_for_matching_series(self):
        response = self.client.get("/api/v1/library/series/", {"q": "first"})
        selected = self.client.get(
            "/api/v1/library/series/",
            {"q": "first", "tag": "mystery"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(aggregate_counts(response), {"Fantasy": 1, "Mystery": 2})
        self.assertEqual(aggregate_counts(selected), {"Fantasy": 1, "Mystery": 2})

    def test_group_scope_matches_only_books_in_requested_group(self):
        paths = {
            "books/": {"Fantasy": 2, "Mystery": 2},
            "search?q=visible": {"Fantasy": 2, "Mystery": 2},
            "authors/?q=alpha": {"Mystery": 1},
            "series/?q=first": {"Fantasy": 1, "Mystery": 2},
        }

        for suffix, expected in paths.items():
            with self.subTest(suffix=suffix):
                response = self.client.get(
                    f"/api/v1/library/groups/{self.public.id}/{suffix}"
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(aggregate_counts(response), expected)

    def test_empty_results_include_empty_aggregate_list(self):
        for endpoint in (
            "/api/v1/library/books/",
            "/api/v1/library/search",
            "/api/v1/library/authors/",
            "/api/v1/library/series/",
        ):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint, {"q": "no such result"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["catalog_tags"], [])

    def test_tags_scope_total_contract_is_unchanged(self):
        response = self.client.get("/api/v1/library/tags/", {"page_size": 1})

        self.assertNotIn("catalog_tags", response.json())
        self.assertEqual(response.json()["results"][0]["name"], "Fantasy")
