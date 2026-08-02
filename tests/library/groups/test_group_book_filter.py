from __future__ import annotations

from uuid import uuid4

from django.test import TestCase

from core.server_settings import (
    set_advanced_library_groups_enabled,
    set_server_setting,
)
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.models import (
    Book,
    BookGroupAssignment,
    LibraryGroup,
    LibraryGroupMembership,
)
from tests.library.helpers import LibraryCatalogApiFixtureMixin


class LibraryGroupBookFilterTests(LibraryCatalogApiFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        set_advanced_library_groups_enabled(True)
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(self.public.id),
            description="Public/Common Room group id.",
        )

        self.club = LibraryGroup.objects.create(name="Readers Club")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.club)
        BookGroupAssignment.objects.create(book=self.multi_group, group=self.club)

    def test_book_filter_returns_only_visible_matching_groups_with_previews(self):
        response = self.client.get(
            "/api/v1/library/groups/",
            {
                "book": str(self.multi_group.id),
                "ordering": "-name",
                "include_preview_books": "true",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 2)
        self.assertEqual(
            [row["name"] for row in payload["results"]],
            ["Readers Club", "Common Room"],
        )
        self.assertEqual(
            len({row["id"] for row in payload["results"]}),
            len(payload["results"]),
        )
        public = next(
            row for row in payload["results"] if row["name"] == "Common Room"
        )
        self.assertTrue(public["is_public_group"])
        for row in payload["results"]:
            self.assertIn("preview_books", row)
            self.assertIn(
                "Multi Group",
                [book["title"] for book in row["preview_books"]],
            )

    def test_book_filter_preserves_pagination_and_ordering(self):
        first_page = self.client.get(
            "/api/v1/library/groups/",
            {
                "book": str(self.multi_group.id),
                "ordering": "-name",
                "page_size": 1,
            },
        )
        second_page = self.client.get(
            "/api/v1/library/groups/",
            {
                "book": str(self.multi_group.id),
                "ordering": "-name",
                "page_size": 1,
                "page": 2,
            },
        )

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(first_page.json()["count"], 2)
        self.assertEqual(
            [row["name"] for row in first_page.json()["results"]],
            ["Readers Club"],
        )
        self.assertEqual(
            [row["name"] for row in second_page.json()["results"]],
            ["Common Room"],
        )

    def test_book_filter_is_no_leakage_for_missing_inaccessible_and_unassigned_books(self):
        unassigned = Book.objects.create(title="Unassigned")

        for book_id in (uuid4(), self.hidden_book.id, unassigned.id):
            with self.subTest(book_id=book_id):
                response = self.client.get(
                    "/api/v1/library/groups/",
                    {"book": str(book_id)},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["count"], 0)
                self.assertEqual(response.json()["results"], [])

    def test_book_filter_rejects_malformed_uuid(self):
        response = self.client.get(
            "/api/v1/library/groups/",
            {"book": "not-a-uuid"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("book", response.json())

    def test_broad_role_sees_matching_group_hidden_from_reader(self):
        reader_response = self.client.get(
            "/api/v1/library/groups/",
            {"book": str(self.hidden_book.id)},
        )
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))
        manager_response = self.client.get(
            "/api/v1/library/groups/",
            {"book": str(self.hidden_book.id)},
        )

        self.assertEqual(reader_response.json()["results"], [])
        self.assertEqual(
            [row["name"] for row in manager_response.json()["results"]],
            ["Hidden"],
        )

    def test_book_filter_does_not_bypass_simple_mode(self):
        set_advanced_library_groups_enabled(False)
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.get(
            "/api/v1/library/groups/",
            {"book": str(self.multi_group.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["name"] for row in response.json()["results"]],
            ["Common Room"],
        )
