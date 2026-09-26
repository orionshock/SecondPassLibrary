from __future__ import annotations

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from core.server_settings import (
    set_advanced_library_groups_enabled,
    set_server_setting,
)
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.catalog.book_queries import book_row_queryset
from library.catalog.serializers.books import BookListSerializer
from library.models import Book, BookAuthor, BookCatalogTag, LibraryGroupMembership
from tests.library.helpers import LibraryCatalogApiFixtureMixin, response_titles


class LibraryCatalogBookViewTests(LibraryCatalogApiFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(self.public.id),
            description="Public/Common Room group id.",
        )

    def test_visible_book_list_excludes_books_outside_user_groups(self):
        response = self.client.get("/api/v1/library/books/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response_titles(response),
            ["Multi Group", "Visible One", "Visible Three", "Visible Two"],
        )

    def test_book_list_rows_use_compact_catalog_tag_and_file_format_shape(self):
        response = self.client.get("/api/v1/library/books/", {"q": "Visible One"})

        self.assertEqual(response.status_code, 200)
        row = response.json()["results"][0]
        self.assertEqual([tag["name"] for tag in row["catalog_tags"]], ["Fantasy"])
        self.assertNotIn("tags", row)
        self.assertEqual(row["file_format"], "epub")
        for detail_field in (
            "description",
            "identifiers",
            "groups",
            "file",
            "download_url",
            "file_size",
            "checksum",
            "book_file",
            "storage_path",
            "source_filename",
        ):
            self.assertNotIn(detail_field, row)

    def test_broad_role_can_list_all_books(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.get("/api/v1/library/books/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response_titles(response),
            ["Hidden Dresden", "Multi Group", "Visible One", "Visible Three", "Visible Two"],
        )

    def test_retrieve_visible_book_succeeds(self):
        response = self.client.get(f"/api/v1/library/books/{self.visible_one.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Visible One")
        self.assertEqual(response.json()["description"], "dresden case file")

    def test_book_detail_uses_catalog_tags_and_file_object_without_row_aliases(self):
        response = self.client.get(f"/api/v1/library/books/{self.visible_one.id}/")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([tag["name"] for tag in payload["catalog_tags"]], ["Fantasy"])
        self.assertIn("identifiers", payload)
        self.assertIn("groups", payload)
        self.assertEqual(payload["file"], None)
        self.assertNotIn("tags", payload)
        self.assertNotIn("file_format", payload)

    def test_book_row_relationship_projection_is_ordered_and_query_bounded(self):
        BookAuthor.objects.create(
            book=self.visible_one,
            author=self.alpha,
            position=1,
        )
        BookCatalogTag.objects.create(
            book=self.visible_one,
            catalog_tag=self.mystery,
        )

        with CaptureQueriesContext(connection) as captured:
            serialized = BookListSerializer(
                book_row_queryset(Book.objects.all()),
                many=True,
            ).data

        self.assertLessEqual(len(captured), 3)
        rows = {row["title"]: row for row in serialized}
        row = rows["Visible One"]
        self.assertEqual(
            [author["name"] for author in row["authors"]],
            ["Beta Author", "Alpha Author"],
        )
        self.assertEqual(
            [tag["name"] for tag in row["catalog_tags"]],
            ["Fantasy", "Mystery"],
        )
        self.assertEqual(row["series"]["name"], "First Series")
        self.assertEqual(row["series"]["series_index"], "2.00")

    def test_book_detail_includes_only_reader_visible_group_summaries(self):
        set_advanced_library_groups_enabled(True)

        response = self.client.get(f"/api/v1/library/books/{self.multi_group.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["groups"],
            [
                {
                    "id": str(self.public.id),
                    "name": "Common Room",
                    "description": "",
                    "is_public_group": True,
                }
            ],
        )

    def test_book_detail_includes_visible_custom_group_in_advanced_mode(self):
        set_advanced_library_groups_enabled(True)
        LibraryGroupMembership.objects.create(user=self.reader, group=self.hidden)

        response = self.client.get(f"/api/v1/library/books/{self.multi_group.id}/")

        self.assertEqual(
            {group["name"] for group in response.json()["groups"]},
            {"Common Room", "Hidden"},
        )

    def test_broad_role_book_detail_includes_all_assignments_in_advanced_mode(self):
        set_advanced_library_groups_enabled(True)
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.get(f"/api/v1/library/books/{self.multi_group.id}/")

        self.assertEqual(
            {group["name"] for group in response.json()["groups"]},
            {"Common Room", "Hidden"},
        )

    def test_simple_mode_book_detail_keeps_group_projection_for_frontend_gating(self):
        set_advanced_library_groups_enabled(False)
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.get(f"/api/v1/library/books/{self.multi_group.id}/")

        self.assertEqual(
            {group["name"] for group in response.json()["groups"]},
            {"Common Room", "Hidden"},
        )

    def test_book_list_rows_do_not_include_groups(self):
        response = self.client.get("/api/v1/library/books/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["results"])
        self.assertTrue(all("groups" not in row for row in response.json()["results"]))

    def test_retrieve_invisible_book_returns_404(self):
        response = self.client.get(f"/api/v1/library/books/{self.hidden_book.id}/")

        self.assertEqual(response.status_code, 404)

    def test_overlapping_group_visibility_does_not_duplicate_rows(self):
        response = self.client.get("/api/v1/library/books/", {"q": "multi"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_titles(response), ["Multi Group"])
