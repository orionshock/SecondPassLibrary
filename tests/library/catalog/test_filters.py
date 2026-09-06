from __future__ import annotations

from uuid import uuid4

from django.test import TestCase

from library.models import Author, BookIdentifier, CatalogTag, Series
from tests.library.helpers import (
    LibraryCatalogApiFixtureMixin,
    create_catalog_book,
    response_titles,
)


class LibraryCatalogBookFilterTests(LibraryCatalogApiFixtureMixin, TestCase):
    def assert_empty_book_page(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "count": 0,
                "next": None,
                "previous": None,
                "results": [],
                "catalog_tags": [],
            },
        )

    def test_q_searches_visible_books_only(self):
        visible = self.client.get("/api/v1/library/books/", {"q": "visible one"})
        hidden = self.client.get("/api/v1/library/books/", {"q": "hidden dresden"})

        self.assertEqual(visible.status_code, 200)
        self.assertEqual(response_titles(visible), ["Visible One"])
        self.assertEqual(response_titles(hidden), [])

    def test_q_search_matches_sort_title(self):
        self.visible_three.sort_title = "Catalog Alias"
        self.visible_three.save(update_fields=["sort_title", "updated_at"])

        response = self.client.get("/api/v1/library/books/", {"q": "catalog alias"})

        self.assertEqual(response_titles(response), ["Visible Three"])

    def test_q_search_does_not_match_non_title_metadata(self):
        BookIdentifier.objects.create(
            book=self.visible_three,
            scheme=BookIdentifier.SCHEME_ASIN,
            value="B0CATALOG123",
        )

        for term in ("storm", "case file", "zeta house", "mystery", "catalog123"):
            with self.subTest(term=term):
                response = self.client.get("/api/v1/library/books/", {"q": term})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response_titles(response), [])

    def test_author_filter_defaults_to_title_ordering(self):
        response = self.client.get("/api/v1/library/books/", {"author": self.alpha.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Multi Group", "Visible Two"])

    def test_series_filter_defaults_to_series_index_ordering(self):
        response = self.client.get("/api/v1/library/books/", {"series": self.first_series.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Visible Two", "Visible One"])

    def test_author_and_series_context_pagination_is_stable_without_duplicates(self):
        author_pages = [
            self.client.get(
                "/api/v1/library/books/",
                {"author": self.alpha.id, "ordering": "title", "page_size": 1, "page": page},
            )
            for page in (1, 2)
        ]
        series_pages = [
            self.client.get(
                "/api/v1/library/books/",
                {
                    "series": self.first_series.id,
                    "ordering": "series_index",
                    "page_size": 1,
                    "page": page,
                },
            )
            for page in (1, 2)
        ]

        self.assertEqual([response.json()["count"] for response in author_pages], [2, 2])
        self.assertEqual([response_titles(response) for response in author_pages], [["Multi Group"], ["Visible Two"]])
        self.assertEqual([response.json()["count"] for response in series_pages], [2, 2])
        self.assertEqual([response_titles(response) for response in series_pages], [["Visible Two"], ["Visible One"]])
        for pages in (author_pages, series_pages):
            ids = [response.json()["results"][0]["id"] for response in pages]
            self.assertEqual(len(ids), len(set(ids)))

    def test_malformed_author_id_returns_validation_error(self):
        response = self.client.get("/api/v1/library/books/", {"author": "not-a-uuid"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"author": "Invalid id."})

    def test_valid_missing_and_deleted_author_ids_return_empty_pages(self):
        deleted = Author.objects.create(name="Deleted Author")
        deleted_id = deleted.id
        deleted.delete()

        for author_id in (uuid4(), deleted_id):
            with self.subTest(author_id=author_id):
                response = self.client.get(
                    "/api/v1/library/books/", {"author": author_id}
                )
                self.assert_empty_book_page(response)

    def test_hidden_only_author_id_returns_empty_page(self):
        hidden_author = Author.objects.create(name="Hidden Only Author")
        create_catalog_book(
            "Hidden Author Book",
            author=hidden_author,
            group=self.hidden,
        )

        response = self.client.get(
            "/api/v1/library/books/", {"author": hidden_author.id}
        )

        self.assert_empty_book_page(response)

    def test_author_filter_composes_with_tag_and_search_to_empty_page(self):
        response = self.client.get(
            "/api/v1/library/books/",
            {
                "author": self.alpha.id,
                "tag": self.fantasy.slug,
                "q": "visible",
            },
        )

        self.assert_empty_book_page(response)

    def test_malformed_series_id_returns_validation_error(self):
        response = self.client.get("/api/v1/library/books/", {"series": "not-a-uuid"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"series": "Invalid id."})

    def test_valid_missing_and_deleted_series_ids_return_empty_pages(self):
        deleted = Series.objects.create(name="Deleted Series")
        deleted_id = deleted.id
        deleted.delete()

        for series_id in (uuid4(), deleted_id):
            with self.subTest(series_id=series_id):
                response = self.client.get(
                    "/api/v1/library/books/", {"series": series_id}
                )
                self.assert_empty_book_page(response)

    def test_hidden_only_series_id_returns_empty_page(self):
        hidden_series = Series.objects.create(name="Hidden Only Series")
        create_catalog_book(
            "Hidden Series Book",
            author=self.alpha,
            series=hidden_series,
            series_index="1.00",
            group=self.hidden,
        )

        response = self.client.get(
            "/api/v1/library/books/", {"series": hidden_series.id}
        )

        self.assert_empty_book_page(response)

    def test_series_filter_composes_with_tag_and_search_to_empty_page(self):
        response = self.client.get(
            "/api/v1/library/books/",
            {
                "series": self.first_series.id,
                "tag": self.fantasy.slug,
                "q": "definitely-no-match",
            },
        )

        self.assert_empty_book_page(response)

    def test_tag_filter_uses_slug(self):
        response = self.client.get("/api/v1/library/books/", {"tag": self.fantasy.slug})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Visible One", "Visible Three"])

    def test_tag_filter_unknown_hidden_and_uuid_values_return_empty(self):
        hidden_tag = CatalogTag.objects.create(
            name="Hidden Filter", normalized_name="hidden filter", slug="hidden-filter"
        )
        create_catalog_book(
            "Hidden Filter Book", author=self.alpha, tag=hidden_tag, group=self.hidden
        )

        for value in ("missing-tag", hidden_tag.slug, str(self.fantasy.id)):
            with self.subTest(value=value):
                response = self.client.get("/api/v1/library/books/", {"tag": value})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response_titles(response), [])

    def test_publisher_filter(self):
        response = self.client.get("/api/v1/library/books/", {"publisher": "Alpha House"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Visible Two"])

    def test_filters_compose(self):
        response = self.client.get(
            "/api/v1/library/books/",
            {
                "author": self.beta.id,
                "publisher": "Beta House",
                "tag": self.fantasy.slug,
                "q": "visible",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Visible One"])
