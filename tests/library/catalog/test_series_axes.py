from __future__ import annotations

from django.test import TestCase

from library.models import Series
from tests.library.helpers import (
    LibraryCatalogApiFixtureMixin,
    assert_axis_detail_ignores_list_params,
    create_catalog_book,
    response_book_counts,
    response_names,
)


def preview_titles(row):
    return [book["title"] for book in row["preview_books"]]


class LibrarySeriesAxisTests(LibraryCatalogApiFixtureMixin, TestCase):
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
        self.first_series.summary = "Summary in list payload."
        self.first_series.save(update_fields=["summary", "updated_at"])
        response = self.client.get("/api/v1/library/series/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_book_counts(response), {"First Series": 2, "Second Series": 1})
        first = next(item for item in response.json()["results"] if item["name"] == "First Series")
        self.assertEqual(first["summary"], "Summary in list payload.")

    def test_preview_books_are_opt_in_limited_and_visibility_scoped(self):
        for index in range(7):
            create_catalog_book(
                f"Series Preview {index:02d}",
                author=self.alpha,
                series=self.first_series,
                series_index=f"{index + 10}.00",
                group=self.public,
            )

        default_response = self.client.get("/api/v1/library/series/")
        preview_response = self.client.get(
            "/api/v1/library/series/",
            {"include_preview_books": "true"},
        )
        detail_response = self.client.get(
            f"/api/v1/library/series/{self.first_series.id}/",
            {"include_preview_books": "true"},
        )

        self.assertEqual(default_response.status_code, 200)
        self.assertNotIn("preview_books", default_response.json()["results"][0])
        self.assertEqual(preview_response.status_code, 200)
        first = next(
            row for row in preview_response.json()["results"] if row["name"] == "First Series"
        )
        self.assertEqual(
            preview_titles(first),
            ["Visible Two", "Visible One", *[f"Series Preview {index:02d}" for index in range(4)]],
        )
        self.assertNotIn("Hidden Dresden", preview_titles(first))
        for preview in first["preview_books"]:
            self.assertEqual(set(preview), {"id", "title", "cover_url"})

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(preview_titles(detail_response.json()), preview_titles(first))

    def test_q_searches_name_and_sort_name(self):
        self.second_series.sort_name = "Storm Sequence"
        self.second_series.save(update_fields=["sort_name", "updated_at"])

        by_name = self.client.get("/api/v1/library/series/", {"q": "first"})
        by_sort_name = self.client.get("/api/v1/library/series/", {"q": "storm"})

        self.assertEqual(response_names(by_name), ["First Series"])
        self.assertEqual(response_names(by_sort_name), ["Second Series"])

    def test_tag_slug_filters_series_and_counts_tagged_visible_books(self):
        response = self.client.get(
            "/api/v1/library/series/", {"tag": self.fantasy.slug}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), ["First Series", "Second Series"])
        self.assertEqual(
            response_book_counts(response), {"First Series": 1, "Second Series": 1}
        )

    def test_unknown_tag_slug_returns_no_series(self):
        response = self.client.get("/api/v1/library/series/", {"tag": "missing"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), [])

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
        self.first_series.summary = "An established catalog summary."
        self.first_series.save(update_fields=["summary", "updated_at"])
        response = self.client.get(f"/api/v1/library/series/{self.first_series.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "First Series")
        self.assertEqual(response.json()["book_count"], 2)
        self.assertEqual(response.json()["summary"], "An established catalog summary.")

    def test_librarian_can_patch_summary(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/series/{self.first_series.id}/",
            data={"name": "Updated Series Name", "summary": "Updated series summary."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.first_series.refresh_from_db()
        self.assertEqual(self.first_series.name, "Updated Series Name")
        self.assertEqual(self.first_series.summary, "Updated series summary.")
        self.assertEqual(response.json()["name"], "Updated Series Name")
        self.assertEqual(response.json()["summary"], "Updated series summary.")

    def test_reader_cannot_patch_summary(self):
        response = self.client.patch(
            f"/api/v1/library/series/{self.first_series.id}/",
            data={"summary": "Forbidden summary."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.first_series.refresh_from_db()
        self.assertEqual(self.first_series.summary, "")

    def test_detail_ignores_list_only_params(self):
        assert_axis_detail_ignores_list_params(
            self,
            url=f"/api/v1/library/series/{self.first_series.id}/",
            expected_name="First Series",
        )

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

    def test_hidden_detail_returns_404_even_with_invalid_ordering(self):
        hidden_only = Series.objects.create(name="Hidden Series", sort_name="Hidden Series")
        create_catalog_book(
            "Hidden Series Book",
            author=self.alpha,
            series=hidden_only,
            group=self.hidden,
        )

        response = self.client.get(
            f"/api/v1/library/series/{hidden_only.id}/",
            {"ordering": "created_at"},
        )

        self.assertEqual(response.status_code, 404)

    def test_invalid_ordering_returns_400(self):
        response = self.client.get("/api/v1/library/series/", {"ordering": "created_at"})

        self.assertEqual(response.status_code, 400)
