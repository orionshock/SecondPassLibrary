from __future__ import annotations

from library.models import Author, CatalogTag, Series
from tests.library.bearer.helpers import LibraryBearerApiTestCase
from tests.library.helpers import create_catalog_book


class LibraryBearerCatalogReadTests(LibraryBearerApiTestCase):
    def test_lists_and_retrieves_visible_catalog_records(self):
        cases = [
            ("books", self.visible_one.id, "title", "Visible One"),
            ("authors", self.alpha.id, "name", "Alpha Author"),
            ("series", self.first_series.id, "name", "First Series"),
            ("tags", self.fantasy.id, "name", "Fantasy"),
        ]

        for axis, object_id, field, expected in cases:
            with self.subTest(axis=axis):
                listed = self.bearer_get(f"/api/v1/library/{axis}/")
                detail = self.bearer_get(f"/api/v1/library/{axis}/{object_id}/")
                self.assertEqual(listed.status_code, 200)
                self.assertEqual(detail.status_code, 200)
                self.assertEqual(detail.json()[field], expected)

    def test_book_detail_includes_same_visibility_scoped_group_summaries(self):
        response = self.bearer_get(f"/api/v1/library/books/{self.multi_group.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [group["name"] for group in response.json()["groups"]],
            ["Common Room"],
        )
        self.assertEqual(
            set(response.json()["groups"][0]),
            {"id", "name", "description", "is_public_group"},
        )
        self.assertIn("catalog_tags", response.json())
        self.assertIn("identifiers", response.json())
        self.assertIn("file", response.json())
        self.assertNotIn("tags", response.json())
        self.assertNotIn("file_format", response.json())

    def test_hidden_only_catalog_details_are_404(self):
        hidden_author = Author.objects.create(name="Hidden Only", sort_name="Hidden Only")
        hidden_series = Series.objects.create(name="Hidden Only", sort_name="Hidden Only")
        hidden_tag = CatalogTag.objects.create(
            name="Hidden Only", normalized_name="hidden only", slug="hidden-only"
        )
        hidden_book = create_catalog_book(
            "Bearer Hidden Only",
            author=hidden_author,
            series=hidden_series,
            tag=hidden_tag,
            group=self.hidden,
        )

        for axis, object_id in [
            ("books", hidden_book.id),
            ("authors", hidden_author.id),
            ("series", hidden_series.id),
            ("tags", hidden_tag.id),
        ]:
            with self.subTest(axis=axis):
                response = self.bearer_get(f"/api/v1/library/{axis}/{object_id}/")
                self.assertEqual(response.status_code, 404)

    def test_privileged_account_bearer_keeps_its_real_broad_read_role(self):
        self.use_manager_bearer()

        response = self.bearer_get(f"/api/v1/library/books/{self.hidden_book.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Hidden Dresden")

    def test_privileged_bearer_cannot_see_unattached_catalog_entities(self):
        self.use_manager_bearer()
        author = Author.objects.create(
            name="Unattached", sort_name="Unattached", normalized_name="unattached"
        )
        series = Series.objects.create(
            name="Unattached", sort_name="Unattached", normalized_name="unattached"
        )

        authors = self.bearer_get("/api/v1/library/authors/")
        series_list = self.bearer_get("/api/v1/library/series/")

        self.assertNotIn("Unattached", [row["name"] for row in authors.json()["results"]])
        self.assertNotIn("Unattached", [row["name"] for row in series_list.json()["results"]])
        self.assertEqual(self.bearer_get(f"/api/v1/library/authors/{author.id}/").status_code, 404)
        self.assertEqual(self.bearer_get(f"/api/v1/library/series/{series.id}/").status_code, 404)

    def test_filters_counts_and_pagination_remain_visibility_scoped(self):
        books = self.bearer_get(
            "/api/v1/library/books/",
            {"tag": self.fantasy.slug, "page_size": 1},
        )
        authors = self.bearer_get(
            "/api/v1/library/authors/",
            {"tag": self.fantasy.slug, "page_size": 1},
        )
        tags = self.bearer_get("/api/v1/library/tags/")

        self.assertEqual(books.status_code, 200)
        self.assertEqual(books.json()["count"], 2)
        self.assertEqual(len(books.json()["results"]), 1)
        self.assertIsNotNone(books.json()["next"])
        self.assertNotIn("Hidden Dresden", [row["title"] for row in books.json()["results"]])
        self.assertEqual(authors.status_code, 200)
        self.assertEqual(authors.json()["count"], 2)
        self.assertTrue(all(row["book_count"] > 0 for row in authors.json()["results"]))
        self.assertEqual(tags.status_code, 200)
        self.assertEqual(
            {row["name"]: row["book_count"] for row in tags.json()["results"]},
            {"Fantasy": 2, "Mystery": 1},
        )

    def test_author_and_series_preview_books_are_bearer_visibility_scoped(self):
        authors = self.bearer_get(
            "/api/v1/library/authors/",
            {"include_preview_books": "true"},
        )
        series = self.bearer_get(
            "/api/v1/library/series/",
            {"include_preview_books": "true"},
        )

        self.assertEqual(authors.status_code, 200)
        alpha = next(row for row in authors.json()["results"] if row["name"] == "Alpha Author")
        self.assertIn("preview_books", alpha)
        self.assertNotIn(
            "Hidden Dresden",
            [book["title"] for book in alpha["preview_books"]],
        )
        for preview in alpha["preview_books"]:
            self.assertEqual(set(preview), {"id", "title", "cover_url"})

        self.assertEqual(series.status_code, 200)
        second = next(row for row in series.json()["results"] if row["name"] == "Second Series")
        self.assertIn("Visible Three", [book["title"] for book in second["preview_books"]])
        self.assertNotIn(
            "Hidden Dresden",
            [book["title"] for book in second["preview_books"]],
        )

    def test_book_file_metadata_exposes_download_route_without_storage_path(self):
        self.visible_one.book_file.name = "books/aa/private.epub"
        self.visible_one.checksum = "a" * 64
        self.visible_one.file_size = 123
        self.visible_one.save(
            update_fields=["book_file", "checksum", "file_size", "updated_at"]
        )

        response = self.bearer_get(f"/api/v1/library/books/{self.visible_one.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["file"],
            {
                "format": "epub",
                "file_size": 123,
                "checksum": "a" * 64,
                "download_url": (
                    f"http://testserver/api/v1/library/books/{self.visible_one.id}/download/"
                ),
            },
        )
        self.assertNotIn("book_file", response.json()["file"])
