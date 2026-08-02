from __future__ import annotations

from django.test import TestCase

from library.models import Author, Book, BookAuthor, BookGroupAssignment, Series
from tests.library.helpers import LibraryCatalogApiFixtureMixin, create_catalog_book, response_titles


class LibraryCatalogBookOrderingTests(LibraryCatalogApiFixtureMixin, TestCase):
    def test_author_ordering_uses_lowest_position_and_is_stable_across_search_and_pagination(self):
        alpha = Author.objects.create(name="Alpha Secondary", sort_name="Alpha, Secondary")
        middle = Author.objects.create(name="Middle Primary", sort_name="Middle, Primary")
        zeta = Author.objects.create(name="Zeta Primary", sort_name="Zeta, Primary")
        book_a = create_catalog_book("Primary Ordering A", author=zeta, group=self.public)
        BookAuthor.objects.create(book=book_a, author=alpha, position=1)
        create_catalog_book("Primary Ordering B", author=middle, group=self.public)
        create_catalog_book("Primary Ordering C", author=middle, group=self.public)
        no_author = Book.objects.create(title="Primary Ordering No Author")
        BookGroupAssignment.objects.create(book=no_author, group=self.public)

        expected = [
            "Primary Ordering B",
            "Primary Ordering C",
            "Primary Ordering A",
            "Primary Ordering No Author",
        ]
        library = self.client.get(
            "/api/v1/library/books/",
            {"q": "Primary Ordering", "ordering": "author"},
        )
        search = self.client.get(
            "/api/v1/library/search",
            {"q": "Primary Ordering", "ordering": "author"},
        )
        first_page = self.client.get(
            "/api/v1/library/books/",
            {"q": "Primary Ordering", "ordering": "author", "page_size": 2},
        )
        second_page = self.client.get(first_page.json()["next"])

        self.assertEqual(response_titles(library), expected)
        self.assertEqual(response_titles(search), expected)
        self.assertEqual(response_titles(first_page) + response_titles(second_page), expected)

        primary = BookAuthor.objects.get(book=book_a, author=zeta)
        secondary = BookAuthor.objects.get(book=book_a, author=alpha)
        primary.position = 2
        primary.save(update_fields=["position"])
        secondary.position = 0
        secondary.save(update_fields=["position"])
        reordered = self.client.get(
            "/api/v1/library/books/",
            {"q": "Primary Ordering", "ordering": "author"},
        )
        self.assertEqual(response_titles(reordered)[0], "Primary Ordering A")

    def test_series_index_ordering_uses_exact_decimals_and_deterministic_fallbacks(self):
        series = Series.objects.create(name="Decimal Series", sort_name="Decimal Series")
        for title, index in (
            ("Index 1.01", "1.01"),
            ("Index 1.10", "1.10"),
            ("Index 1.25 A", "1.25"),
            ("Index 1.25 B", "1.25"),
            ("Index 2.00", "2.00"),
            ("Index Unknown", None),
        ):
            create_catalog_book(
                title,
                author=self.alpha,
                series=series,
                series_index=index,
                group=self.public,
            )

        response = self.client.get(
            "/api/v1/library/books/",
            {"series": str(series.id)},
        )

        self.assertEqual(
            response_titles(response),
            [
                "Index 1.01",
                "Index 1.10",
                "Index 1.25 A",
                "Index 1.25 B",
                "Index 2.00",
                "Index Unknown",
            ],
        )

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
