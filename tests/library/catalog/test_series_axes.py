from __future__ import annotations

from unittest.mock import patch

from django.db.models.deletion import ProtectedError
from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserProfile
from library.models import BookSeries, Series
from tests.library.helpers import (
    LibraryCatalogApiFixtureMixin,
    assert_axis_detail_ignores_list_params,
    create_catalog_book,
    response_book_counts,
    response_names,
)
from tests.utils.users import set_user_role


def preview_titles(row):
    return [book["title"] for book in row["preview_books"]]


class LibrarySeriesAxisTests(LibraryCatalogApiFixtureMixin, TestCase):
    def test_manager_can_create_and_retrieve_unattached_series_by_default(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))
        created = self.client.post(
            "/api/v1/library/series/",
            data={"name": "New Series", "sort_name": "Series, New", "summary": "Summary"},
            content_type="application/json",
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(
            set(created.json()), {"id", "name", "sort_name", "summary", "book_count"}
        )
        series = Series.objects.get(pk=created.json()["id"])
        self.assertEqual(series.normalized_name, "new series")
        detail = self.client.get(f"/api/v1/library/series/{series.id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["book_count"], 0)

    def test_manager_default_reads_include_hidden_series_and_total_counts(self):
        hidden_only = Series.objects.create(name="Hidden Series", sort_name="Hidden Series")
        create_catalog_book(
            "Hidden Series Book",
            author=self.alpha,
            series=hidden_only,
            group=self.hidden,
            tag=self.fantasy,
        )
        hidden_prolific = Series.objects.create(
            name="Hidden Prolific Series", sort_name="Hidden Prolific Series"
        )
        for index, title in enumerate(("Hidden Series One", "Hidden Series Two"), start=1):
            create_catalog_book(
                title,
                author=self.alpha,
                series=hidden_prolific,
                series_index=str(index),
                group=self.hidden,
                tag=self.fantasy,
            )
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        listed = self.client.get("/api/v1/library/series/")
        detail = self.client.get(f"/api/v1/library/series/{hidden_only.id}/")
        filtered = self.client.get(
            "/api/v1/library/series/",
            {"tag": self.fantasy.slug, "q": "hidden", "ordering": "-book_count"},
        )
        previews = self.client.get(
            "/api/v1/library/series/",
            {"q": "second", "include_preview_books": "true"},
        )

        self.assertIn("Hidden Series", response_names(listed))
        self.assertEqual(response_book_counts(listed)["Second Series"], 2)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["book_count"], 1)
        self.assertEqual(
            response_names(filtered),
            ["Hidden Prolific Series", "Hidden Series"],
        )
        self.assertEqual(
            response_book_counts(filtered),
            {"Hidden Prolific Series": 2, "Hidden Series": 1},
        )
        self.assertIn("Hidden Dresden", preview_titles(previews.json()["results"][0]))

    def test_duplicate_normalized_series_names_are_allowed(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))
        for name in ("Shared Name", "  shared   name "):
            response = self.client.post(
                "/api/v1/library/series/",
                data={"name": name},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Series.objects.filter(normalized_name="shared name").count(), 2
        )

    def test_create_and_patch_reject_unknown_fields(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        created = self.client.post(
            "/api/v1/library/series/",
            data={"name": "Rejected Series", "preview_books": [], "random_field": True},
            content_type="application/json",
        )
        patched = self.client.patch(
            f"/api/v1/library/series/{self.first_series.id}/",
            data={"name": "Should Not Persist", "books": []},
            content_type="application/json",
        )

        self.assertEqual(created.status_code, 400)
        self.assertEqual(
            created.json(),
            {"preview_books": ["Unknown field."], "random_field": ["Unknown field."]},
        )
        self.assertFalse(Series.objects.filter(name="Rejected Series").exists())
        self.assertEqual(patched.status_code, 400)
        self.assertEqual(patched.json(), {"books": ["Unknown field."]})
        self.first_series.refresh_from_db()
        self.assertEqual(self.first_series.name, "First Series")

    def test_patch_sort_name_controls_ordering(self):
        first = Series.objects.create(name="Lifecycle Alpha", sort_name="Lifecycle Alpha")
        second = Series.objects.create(name="Lifecycle Beta", sort_name="Lifecycle Beta")
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/series/{first.id}/",
            data={"sort_name": "Zulu Lifecycle"},
            content_type="application/json",
        )
        ordered = self.client.get(
            "/api/v1/library/series/", {"q": "lifecycle", "ordering": "name"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sort_name"], "Zulu Lifecycle")
        self.assertEqual(response_names(ordered), [second.name, first.name])

    def test_patch_blank_sort_name_defaults_to_name_and_omission_preserves_it(self):
        self.first_series.sort_name = "Preserved Sort"
        self.first_series.save(update_fields=["sort_name", "updated_at"])
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        renamed = self.client.patch(
            f"/api/v1/library/series/{self.first_series.id}/",
            data={"name": "Renamed Series"},
            content_type="application/json",
        )
        blanked = self.client.patch(
            f"/api/v1/library/series/{self.first_series.id}/",
            data={"sort_name": ""},
            content_type="application/json",
        )

        self.assertEqual(renamed.json()["sort_name"], "Preserved Sort")
        self.assertEqual(blanked.json()["sort_name"], "Renamed Series")
        self.first_series.refresh_from_db()
        self.assertEqual(self.first_series.sort_name, "Renamed Series")

    def test_put_is_not_supported(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.put(
            f"/api/v1/library/series/{self.first_series.id}/",
            data={"name": "Replacement"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 405)

    def test_reader_cannot_create_or_delete_series(self):
        created = self.client.post(
            "/api/v1/library/series/",
            data={"name": "Forbidden"},
            content_type="application/json",
        )
        deleted = self.client.delete(f"/api/v1/library/series/{self.first_series.id}/")
        self.assertEqual(created.status_code, 403)
        self.assertEqual(deleted.status_code, 403)

    def test_safe_delete_series(self):
        unattached = Series.objects.create(
            name="Disposable", sort_name="Disposable", normalized_name="disposable"
        )
        User = get_user_model()
        librarian = User.objects.create_user(username="delete-librarian", password="pw")
        set_user_role(librarian, UserProfile.ROLE_LIBRARIAN)
        self.client.logout()
        self.assertTrue(self.client.login(username="delete-librarian", password="pw"))

        deleted = self.client.delete(f"/api/v1/library/series/{unattached.id}/")
        blocked = self.client.delete(f"/api/v1/library/series/{self.first_series.id}/")

        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(
            blocked.json()["error"],
            {
                "code": "series_has_books",
                "message": "Series cannot be deleted because 2 Books are attached.",
                "details": {"book_count": 2},
            },
        )
        self.assertTrue(Series.objects.filter(pk=self.first_series.pk).exists())
        self.assertTrue(BookSeries.objects.filter(series=self.first_series).exists())
        self.assertTrue(
            BookSeries.objects.filter(series=self.first_series, book=self.visible_two).exists()
        )

    def test_late_series_protection_failure_uses_the_same_bounded_conflict(self):
        unattached = Series.objects.create(name="Raced", sort_name="Raced")
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        with patch.object(
            Series,
            "delete",
            side_effect=ProtectedError("protected", [object()]),
        ):
            response = self.client.delete(f"/api/v1/library/series/{unattached.id}/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "series_has_books")
        self.assertEqual(response.json()["error"]["details"], {"book_count": 1})
        self.assertTrue(Series.objects.filter(pk=unattached.pk).exists())

    def test_list_includes_only_series_with_visible_books(self):
        Series.objects.create(name="Unattached", sort_name="Unattached")
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

    def test_preview_limit_preserves_exact_series_order_and_total_count(self):
        limited = Series.objects.create(name="Limited Preview Series")
        indexes = ["1.01", "1.10", "1.25", "2.00", *[f"{value}.00" for value in range(3, 24)]]
        for offset, series_index in enumerate(indexes):
            create_catalog_book(
                f"Indexed Preview {offset:02d}",
                author=self.alpha,
                series=limited,
                series_index=series_index,
                group=self.public,
            )

        for limit in (1, 6, 12, 24):
            with self.subTest(limit=limit):
                response = self.client.get(
                    "/api/v1/library/series/", {"preview_limit": str(limit)}
                )
                row = next(
                    item for item in response.json()["results"] if item["id"] == str(limited.id)
                )
                self.assertEqual(row["book_count"], 25)
                self.assertEqual(
                    preview_titles(row),
                    [f"Indexed Preview {offset:02d}" for offset in range(limit)],
                )

        default_response = self.client.get(
            "/api/v1/library/series/", {"include_preview_books": "true"}
        )
        default_row = next(
            row for row in default_response.json()["results"] if row["id"] == str(limited.id)
        )
        self.assertEqual(len(default_row["preview_books"]), 6)

        disabled = self.client.get(
            "/api/v1/library/series/", {"preview_limit": "0"}
        )
        disabled_row = next(
            row for row in disabled.json()["results"] if row["id"] == str(limited.id)
        )
        self.assertNotIn("preview_books", disabled_row)
        self.assertEqual(disabled_row["book_count"], 25)

        for value in ("25", "-1", "invalid", "1.5"):
            with self.subTest(value=value):
                response = self.client.get(
                    "/api/v1/library/series/", {"preview_limit": value}
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(set(response.json()), {"preview_limit"})

    def test_q_searches_name_and_sort_name(self):
        self.second_series.sort_name = "Storm Sequence"
        self.second_series.save(update_fields=["sort_name", "updated_at"])

        by_name = self.client.get("/api/v1/library/series/", {"q": "first"})
        by_sort_name = self.client.get("/api/v1/library/series/", {"q": "storm"})

        self.assertEqual(response_names(by_name), ["First Series"])
        self.assertEqual(response_names(by_sort_name), ["Second Series"])

    def test_q_normalizes_the_normalized_name_search_term(self):
        self.second_series.normalized_name = "normalized series"
        self.second_series.save(update_fields=["normalized_name", "updated_at"])

        response = self.client.get(
            "/api/v1/library/series/", {"q": "  ＮORMALIZED   SERIES "}
        )

        self.assertEqual(response_names(response), ["Second Series"])

    def test_search_can_exclude_one_series_id(self):
        response = self.client.get(
            "/api/v1/library/series/",
            {"q": "series", "exclude_id": self.first_series.id, "page_size": 10},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            str(self.first_series.id),
            [row["id"] for row in response.json()["results"]],
        )

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
        series_id = self.first_series.id
        related_books = dict(
            BookSeries.objects.filter(series=self.first_series).values_list(
                "book_id", "series_index"
            )
        )

        response = self.client.patch(
            f"/api/v1/library/series/{self.first_series.id}/",
            data={"name": "Updated Series Name", "summary": "Updated series summary."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.first_series.refresh_from_db()
        self.assertEqual(self.first_series.id, series_id)
        self.assertEqual(
            dict(
                BookSeries.objects.filter(series=self.first_series).values_list(
                    "book_id", "series_index"
                )
            ),
            related_books,
        )
        self.assertEqual(self.first_series.name, "Updated Series Name")
        self.assertEqual(self.first_series.summary, "Updated series summary.")
        self.assertEqual(self.first_series.normalized_name, "updated series name")
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
        unattached = Series.objects.create(name="Unattached", sort_name="Unattached")
        hidden_only = Series.objects.create(name="Hidden Series", sort_name="Hidden Series")
        create_catalog_book(
            "Hidden Series Book",
            author=self.alpha,
            series=hidden_only,
            group=self.hidden,
        )

        for series in (unattached, hidden_only):
            with self.subTest(series=series.name):
                response = self.client.get(f"/api/v1/library/series/{series.id}/")
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
