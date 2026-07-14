from __future__ import annotations

from django.test import TestCase

from library.models import BookIdentifier, CatalogTag
from tests.library.helpers import (
    LibraryCatalogApiFixtureMixin,
    create_catalog_book,
    response_titles,
)


class LibraryCatalogBookFilterTests(LibraryCatalogApiFixtureMixin, TestCase):
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

    def test_author_filter(self):
        response = self.client.get("/api/v1/library/books/", {"author": self.alpha.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Multi Group", "Visible Two"])

    def test_series_filter(self):
        response = self.client.get("/api/v1/library/books/", {"series": self.first_series.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Visible Two", "Visible One"])

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
