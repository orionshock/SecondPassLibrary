from __future__ import annotations

from django.test import TestCase

from library.models import Author, CatalogTag, Series
from tests.library.helpers import (
    LibraryCatalogApiFixtureMixin,
    create_catalog_book,
    response_book_counts,
    response_names,
)


class LibraryReadAxisContractTests(LibraryCatalogApiFixtureMixin, TestCase):
    def test_lists_apply_visibility_counts_and_entity_payloads(self):
        self.alpha.biography = "Biography in list payload."
        self.alpha.save(update_fields=["biography", "updated_at"])
        self.first_series.summary = "Summary in list payload."
        self.first_series.save(update_fields=["summary", "updated_at"])

        Author.objects.create(name="Unattached Author", sort_name="Unattached Author")
        hidden_author = Author.objects.create(
            name="Hidden Author", sort_name="Hidden Author"
        )
        create_catalog_book(
            "Hidden Author Book",
            author=hidden_author,
            group=self.hidden,
        )

        Series.objects.create(name="Unattached Series", sort_name="Unattached Series")
        hidden_series = Series.objects.create(
            name="Hidden Series", sort_name="Hidden Series"
        )
        create_catalog_book(
            "Hidden Series Book",
            author=self.alpha,
            series=hidden_series,
            group=self.hidden,
        )

        CatalogTag.objects.create(
            name="Unattached Tag",
            normalized_name="unattached tag",
            slug="unattached-tag",
        )
        hidden_tag = CatalogTag.objects.create(
            name="Hidden Tag",
            normalized_name="hidden tag",
            slug="hidden-tag",
        )
        create_catalog_book(
            "Hidden Tag Book",
            author=self.alpha,
            tag=hidden_tag,
            group=self.hidden,
        )

        cases = (
            (
                "authors",
                ["Alpha Author", "Beta Author", "Zeta Author"],
                {"Alpha Author": 2, "Beta Author": 1, "Zeta Author": 1},
            ),
            (
                "series",
                ["First Series", "Second Series"],
                {"First Series": 2, "Second Series": 1},
            ),
            (
                "tags",
                ["Fantasy", "Mystery"],
                {"Fantasy": 2, "Mystery": 1},
            ),
        )
        for axis, expected_names, expected_counts in cases:
            with self.subTest(axis=axis):
                response = self.client.get(f"/api/v1/library/{axis}/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response_names(response), expected_names)
                self.assertEqual(response_book_counts(response), expected_counts)

                first = response.json()["results"][0]
                if axis == "authors":
                    self.assertEqual(first["biography"], "Biography in list payload.")
                elif axis == "series":
                    self.assertEqual(first["summary"], "Summary in list payload.")
                else:
                    self.assertEqual(
                        set(first),
                        {"id", "name", "slug", "book_count"},
                    )

    def test_searches_name_sort_name_and_normalized_name_for_each_axis(self):
        self.beta.sort_name = "Storm Writer"
        self.beta.normalized_name = "normalized author"
        self.beta.save(update_fields=["sort_name", "normalized_name", "updated_at"])
        self.second_series.sort_name = "Storm Sequence"
        self.second_series.normalized_name = "normalized series"
        self.second_series.save(
            update_fields=["sort_name", "normalized_name", "updated_at"]
        )
        self.fantasy.sort_name = "Speculative"
        self.fantasy.save(update_fields=["sort_name", "updated_at"])

        cases = (
            (
                "authors",
                (
                    ("alpha", ["Alpha Author"]),
                    ("storm", ["Beta Author"]),
                    ("normalized author", ["Beta Author"]),
                ),
            ),
            (
                "series",
                (
                    ("first", ["First Series"]),
                    ("storm", ["Second Series"]),
                    ("normalized series", ["Second Series"]),
                ),
            ),
            (
                "tags",
                (
                    ("mystery", ["Mystery"]),
                    ("speculative", ["Fantasy"]),
                    ("fantasy", ["Fantasy"]),
                ),
            ),
        )
        for axis, queries in cases:
            for query, expected in queries:
                with self.subTest(axis=axis, query=query):
                    response = self.client.get(
                        f"/api/v1/library/{axis}/",
                        {"q": f"  {query.upper()}  "},
                    )
                    self.assertEqual(response_names(response), expected)

    def test_orders_each_axis_by_name_and_visible_book_count(self):
        cases = (
            ("authors", ["Alpha Author", "Beta Author", "Zeta Author"]),
            ("series", ["First Series", "Second Series"]),
            ("tags", ["Fantasy", "Mystery"]),
        )
        for axis, names in cases:
            expected = {
                "name": names,
                "-name": list(reversed(names)),
                "book_count": names[1:] + names[:1],
                "-book_count": names[:1] + names[1:],
            }
            if axis == "authors":
                expected["book_count"] = ["Beta Author", "Zeta Author", "Alpha Author"]
                expected["-book_count"] = ["Alpha Author", "Beta Author", "Zeta Author"]
            for ordering, expected_names in expected.items():
                with self.subTest(axis=axis, ordering=ordering):
                    response = self.client.get(
                        f"/api/v1/library/{axis}/",
                        {"ordering": ordering},
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response_names(response), expected_names)

    def test_list_validation_and_detail_precedence_for_each_axis(self):
        hidden_author = Author.objects.create(
            name="Hidden Author", sort_name="Hidden Author"
        )
        create_catalog_book(
            "Hidden Author Book", author=hidden_author, group=self.hidden
        )
        hidden_series = Series.objects.create(
            name="Hidden Series", sort_name="Hidden Series"
        )
        create_catalog_book(
            "Hidden Series Book",
            author=self.alpha,
            series=hidden_series,
            group=self.hidden,
        )
        hidden_tag = CatalogTag.objects.create(
            name="Hidden Tag",
            normalized_name="hidden tag",
            slug="hidden-tag",
        )
        create_catalog_book(
            "Hidden Tag Book",
            author=self.alpha,
            tag=hidden_tag,
            group=self.hidden,
        )

        cases = (
            ("authors", self.alpha.id, "Alpha Author", hidden_author.id),
            ("series", self.first_series.id, "First Series", hidden_series.id),
            ("tags", self.fantasy.id, "Fantasy", hidden_tag.id),
        )
        for axis, visible_id, expected_name, hidden_id in cases:
            with self.subTest(axis=axis, contract="detail-ignores-list-params"):
                for params in (
                    {"q": "definitely-no-match"},
                    {"ordering": "created_at"},
                ):
                    response = self.client.get(
                        f"/api/v1/library/{axis}/{visible_id}/",
                        params,
                    )
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["name"], expected_name)

            with self.subTest(axis=axis, contract="hidden-precedes-invalid-query"):
                response = self.client.get(
                    f"/api/v1/library/{axis}/{hidden_id}/",
                    {"ordering": "created_at"},
                )
                self.assertEqual(response.status_code, 404)

            with self.subTest(axis=axis, contract="invalid-list-ordering"):
                response = self.client.get(
                    f"/api/v1/library/{axis}/",
                    {"ordering": "created_at"},
                )
                self.assertEqual(response.status_code, 400)
