from __future__ import annotations

from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.client_sessions.services import hash_client_secret
from accounts.models import UserClientSession
from core.server_settings import set_advanced_library_groups_enabled
from library.models import BookIdentifier
from shelves.models import Shelf, ShelfItem
from tests.library.helpers import LibraryCatalogApiFixtureMixin


class UserBookVerseSearchApiTests(LibraryCatalogApiFixtureMixin, TestCase):
    endpoint = "/api/v1/library/search"

    def setUp(self):
        super().setUp()
        set_advanced_library_groups_enabled(True)
        BookIdentifier.objects.create(
            book=self.visible_one,
            scheme=BookIdentifier.SCHEME_OTHER,
            value="VERSE-IDENTIFIER-42",
            normalized_value="verse-identifier-42",
        )

    def _titles(self, response) -> list[str]:
        return [row["title"] for row in response.json()["results"]]

    def test_missing_or_blank_query_returns_empty_paginated_response(self):
        for params in ({}, {"q": ""}, {"q": "   \t"}):
            with self.subTest(params=params):
                response = self.client.get(self.endpoint, params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json(),
                    {"count": 0, "next": None, "previous": None, "results": []},
                )

    def test_search_matches_each_supported_visible_book_field(self):
        cases = {
            "visible one": "Visible One",
            "storm front": "Visible One",
            "beta author": "Visible One",
            "first series": "Visible One",
            "verse-identifier-42": "Visible One",
            "fantasy": "Visible One",
            "beta house": "Visible One",
            "case file": "Visible One",
        }

        for term, expected in cases.items():
            with self.subTest(term=term):
                response = self.client.get(self.endpoint, {"q": term})
                self.assertEqual(response.status_code, 200)
                self.assertIn(expected, self._titles(response))

    def test_search_matches_sort_title_without_changing_books_axis_semantics(self):
        self.visible_one.sort_title = "Unique Sorted Verse"
        self.visible_one.save(update_fields=["sort_title", "updated_at"])

        broad = self.client.get(self.endpoint, {"q": "sorted verse"})
        subtitle_axis = self.client.get("/api/v1/library/books/", {"q": "Storm Front"})

        self.assertEqual(self._titles(broad), ["Visible One"])
        self.assertEqual(subtitle_axis.json()["results"], [])

    def test_hidden_match_does_not_leak_through_results_or_count(self):
        response = self.client.get(self.endpoint, {"q": "hidden dresden"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)
        self.assertEqual(response.json()["results"], [])

    def test_default_and_supported_orderings_are_deterministic(self):
        for book in [
            self.visible_one,
            self.visible_two,
            self.visible_three,
            self.multi_group,
        ]:
            book.description = f"{book.description} BookVerse ordering"
            book.save(update_fields=["description", "updated_at"])

        cases = {
            "title": ["Multi Group", "Visible One", "Visible Three", "Visible Two"],
            "-title": ["Visible Two", "Visible Three", "Visible One", "Multi Group"],
            "author": ["Multi Group", "Visible Two", "Visible One", "Visible Three"],
            "-author": ["Visible Three", "Visible One", "Visible Two", "Multi Group"],
            "series": ["Visible Two", "Visible One", "Visible Three", "Multi Group"],
            "-series": ["Visible Three", "Visible Two", "Visible One", "Multi Group"],
        }

        default = self.client.get(self.endpoint, {"q": "BookVerse ordering"})
        self.assertEqual(self._titles(default), cases["title"])
        for ordering, expected in cases.items():
            with self.subTest(ordering=ordering):
                response = self.client.get(
                    self.endpoint,
                    {"q": "BookVerse ordering", "ordering": ordering},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self._titles(response), expected)

    def test_invalid_ordering_returns_structured_400(self):
        response = self.client.get(
            self.endpoint,
            {"q": "visible", "ordering": "publisher"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("ordering", response.json())

    def test_exclude_shelf_requires_manageable_shelf_and_suppresses_items(self):
        shelf = Shelf.objects.create(
            name="Reader Picker",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.reader,
            visibility=Shelf.VISIBILITY_PRIVATE,
            created_by=self.reader,
        )
        ShelfItem.objects.create(
            shelf=shelf,
            book=self.visible_one,
            position=0,
            added_by=self.reader,
        )

        response = self.client.get(
            self.endpoint,
            {"q": "visible", "exclude_shelf": str(shelf.id)},
        )
        self.assertNotIn("Visible One", self._titles(response))
        self.assertIn("Visible Two", self._titles(response))

        inaccessible = Shelf.objects.create(
            name="Other Shelf",
            owner_type=Shelf.OWNER_TYPE_USER,
            owner_user=self.manager,
            visibility=Shelf.VISIBILITY_LISTED,
            created_by=self.manager,
        )
        for shelf_id in (inaccessible.id, uuid4()):
            with self.subTest(shelf_id=shelf_id):
                denied = self.client.get(
                    self.endpoint,
                    {"q": "visible", "exclude_shelf": str(shelf_id)},
                )
                self.assertEqual(denied.status_code, 404)

    def test_exclude_group_requires_manageable_group_and_suppresses_assignments(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))
        broad = self.client.get(self.endpoint, {"q": "dresden"})
        self.assertEqual(set(self._titles(broad)), {"Visible One", "Hidden Dresden"})
        response = self.client.get(
            self.endpoint,
            {"q": "dresden", "exclude_group": str(self.hidden.id)},
        )
        self.assertEqual(self._titles(response), ["Visible One"])

        unknown = self.client.get(
            self.endpoint,
            {"q": "visible", "exclude_group": str(uuid4())},
        )
        self.assertEqual(unknown.status_code, 404)

        self.assertTrue(self.client.login(username="reader", password="pw"))
        inaccessible = self.client.get(
            self.endpoint,
            {"q": "visible", "exclude_group": str(self.hidden.id)},
        )
        self.assertEqual(inaccessible.status_code, 404)

    def test_session_and_bearer_results_match_and_rows_omit_sensitive_fields(self):
        token = "spl_bookverse_search_test"
        UserClientSession.objects.create(
            user=self.reader,
            name="Search client",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        bearer = APIClient()
        session_response = self.client.get(self.endpoint, {"q": "visible"})
        bearer_response = bearer.get(
            self.endpoint,
            {"q": "visible"},
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(bearer_response.status_code, 200)
        self.assertEqual(bearer_response.json(), session_response.json())
        row = bearer_response.json()["results"][0]
        self.assertEqual(
            set(row),
            {
                "id",
                "title",
                "sort_title",
                "subtitle",
                "authors",
                "series",
                "catalog_tags",
                "language",
                "publisher",
                "published_year",
                "published_month",
                "published_day",
                "published_date_precision",
                "cover_url",
                "file_format",
            },
        )
        for forbidden in (
            "tags",
            "description",
            "identifiers",
            "file",
            "download_url",
            "file_size",
            "checksum",
            "book_file",
            "storage_path",
            "source_filename",
            "groups",
        ):
            self.assertNotIn(forbidden, row)

    def test_anonymous_and_mutation_requests_are_rejected(self):
        self.client.logout()
        anonymous = self.client.get(self.endpoint, {"q": "visible"})
        self.assertIn(anonymous.status_code, {401, 403})

        self.assertTrue(self.client.login(username="reader", password="pw"))
        mutation = self.client.post(self.endpoint, {"q": "visible"})
        self.assertEqual(mutation.status_code, 405)
