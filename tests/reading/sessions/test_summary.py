from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from library.group_services import (
    ensure_book_public_assignment,
)
from reading.models import ReadingSession
from tests.reading.sessions.helpers import (
    SessionBearerFixtureMixin,
    SessionVisibilityFixtureMixin,
)
from tests.utils.books import create_file_backed_book
from tests.utils.responses import response_data_list


class ReadingSessionSummarySessionAuthTests(SessionVisibilityFixtureMixin, APITestCase):
    def setUp(self):
        self.set_up_session_visibility_world()

    def test_list_includes_progression_annotation_count_and_compact_book(self):
        resp = cast(Response, self.client.get("/api/v1/reading/sessions/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = response_data_list(resp)
        by_id = {r["id"]: r for r in results}

        visible = by_id[str(self.session_visible.id)]
        self.assertNotIn("book_title", visible)
        self.assertIn("progression", visible)
        self.assertEqual(visible["progression"], 0.25)
        self.assertEqual(visible["annotation_count"], 1)
        self.assertIn("book", visible)
        book = cast(dict[str, Any], visible["book"])
        self.assertEqual(book["id"], str(self.book.id))
        self.assertEqual(book["title"], "Visible")
        self.assertIsInstance(book["authors"], list)
        self.assertIn("cover_url", book)

    def test_detail_omits_legacy_book_title_field(self):
        resp = cast(
            Response,
            self.client.get(f"/api/v1/reading/sessions/{self.session_visible.id}/"),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = cast(dict[str, Any], resp.data)
        self.assertNotIn("book_title", payload)
        self.assertEqual(payload["book_id"], str(self.book.id))
        self.assertEqual(cast(dict[str, Any], payload["book"])["title"], "Visible")

    def test_list_does_not_leak_hidden_book_metadata(self):
        resp = cast(Response, self.client.get("/api/v1/reading/sessions/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = response_data_list(resp)
        hidden = next(r for r in results if r["id"] == str(self.session_hidden.id))
        book = cast(dict[str, Any], hidden["book"])
        self.assertEqual(book["id"], str(self.hidden_book.id))
        self.assertEqual(book["title"], "")
        self.assertEqual(book["authors"], [])
        self.assertIsNone(book["series"])
        self.assertIsNone(book["cover_url"])

    def test_activity_summary_counts_current_user_visible_books_in_request_order(self):
        zero = create_file_backed_book(title="No Sessions", assign_public=False).book
        ensure_book_public_assignment(book=zero, added_by=None)
        other_session = ReadingSession.objects.create(user=self.owner, book=self.book, is_active=True)
        completed = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            is_active=False,
            status=ReadingSession.STATUS_COMPLETED,
        )
        active = self.session_visible
        active.status = ReadingSession.STATUS_ACTIVE
        active.is_active = True
        active.save(update_fields=["status", "is_active", "updated_at"])

        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/books/activity-summary/",
                data={
                    "books": [
                        str(zero.id),
                        str(self.book.id),
                        str(self.book.id),
                        str(self.hidden_book.id),
                        str(uuid4()),
                    ]
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rows = cast(list[dict[str, Any]], cast(dict[str, Any], resp.data)["results"])
        self.assertEqual([row["book"] for row in rows], [str(zero.id), str(self.book.id)])
        self.assertEqual(rows[0]["session_count"], 0)
        self.assertEqual(rows[0]["active_session_count"], 0)
        self.assertIsNone(rows[0]["active_session_id"])
        self.assertIsNone(rows[0]["latest_session_id"])
        self.assertIsNone(rows[0]["latest_session_updated_at"])

        self.assertEqual(rows[1]["session_count"], 2)
        self.assertEqual(rows[1]["active_session_count"], 1)
        self.assertEqual(rows[1]["active_session_id"], str(active.id))
        self.assertIn(rows[1]["latest_session_id"], {str(active.id), str(completed.id)})
        self.assertIsNotNone(rows[1]["latest_session_updated_at"])
        self.assertNotEqual(rows[1]["session_count"], 3)
        self.assertIsNotNone(other_session.id)

    def test_activity_summary_validation_errors(self):
        missing = cast(Response, self.client.post("/api/v1/reading/books/activity-summary/", data={}, format="json"))
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)

        invalid_type = cast(
            Response,
            self.client.post(
                "/api/v1/reading/books/activity-summary/",
                data={"books": "not-a-list"},
                format="json",
            ),
        )
        self.assertEqual(invalid_type.status_code, status.HTTP_400_BAD_REQUEST)

        malformed = cast(
            Response,
            self.client.post(
                "/api/v1/reading/books/activity-summary/",
                data={"books": ["not-a-uuid"]},
                format="json",
            ),
        )
        self.assertEqual(malformed.status_code, status.HTTP_400_BAD_REQUEST)

        too_many = cast(
            Response,
            self.client.post(
                "/api/v1/reading/books/activity-summary/",
                data={"books": [str(uuid4()) for _ in range(101)]},
                format="json",
            ),
        )
        self.assertEqual(too_many.status_code, status.HTTP_400_BAD_REQUEST)

    def test_activity_summary_does_not_enrich_library_book_payloads(self):
        resp = cast(Response, self.client.get(f"/api/v1/library/books/{self.book.id}/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = cast(dict[str, Any], resp.data)
        for key in [
            "session_count",
            "active_session_count",
            "active_session_id",
            "latest_session_id",
            "latest_session_updated_at",
            "progress",
            "annotation_count",
        ]:
            self.assertNotIn(key, payload)


class ReadingSessionSummaryBearerTests(SessionBearerFixtureMixin, APITestCase):
    def setUp(self):
        self.set_up_session_bearer_world()

    def test_bearer_list_includes_compact_book(self):
        resp = cast(Response, self.client.get("/api/v1/reading/sessions/", HTTP_AUTHORIZATION=self._auth))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = response_data_list(resp)
        self.assertEqual(len(results), 1)
        s0 = results[0]
        self.assertNotIn("book_title", s0)
        self.assertIn("book", s0)
        book = cast(dict[str, Any], s0["book"])
        self.assertEqual(book["id"], str(self.book.id))

    def test_bearer_book_filter_context_and_activity_summary(self):
        list_resp = cast(
            Response,
            self.client.get(
                f"/api/v1/reading/sessions/?book={self.book.id}",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(cast(dict[str, Any], cast(dict[str, Any], list_resp.data)["context"])["book"]["id"], str(self.book.id))

        summary_resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/books/activity-summary/",
                data={"books": [str(self.book.id)]},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(summary_resp.status_code, status.HTTP_200_OK)
        rows = cast(list[dict[str, Any]], cast(dict[str, Any], summary_resp.data)["results"])
        self.assertEqual(rows[0]["book"], str(self.book.id))
        self.assertEqual(rows[0]["session_count"], 1)
