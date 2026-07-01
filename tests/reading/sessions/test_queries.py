from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from library.group_services import (
    ensure_book_public_assignment,
)
from library.models import Author, Series
from reading.models import ReadingProgress, ReadingSession
from reading.services import list_sessions_for_book
from tests.reading.sessions.helpers import (
    SessionBearerFixtureMixin,
    SessionVisibilityFixtureMixin,
)
from tests.utils.books import create_file_backed_book
from tests.utils.responses import response_data_list


class ReadingSessionSummarySessionAuthTests(SessionVisibilityFixtureMixin, APITestCase):
    def setUp(self):
        self.set_up_session_visibility_world()

    def test_filters_book_status_is_active(self):
        self.session_visible.status = ReadingSession.STATUS_COMPLETED
        self.session_visible.is_active = False
        self.session_visible.save(update_fields=["status", "is_active", "updated_at"])

        r_book = cast(Response, self.client.get(f"/api/v1/reading/sessions/?book={self.book.id}"))
        self.assertEqual(r_book.status_code, 200)
        self.assertEqual({s["id"] for s in response_data_list(r_book)}, {str(self.session_visible.id)})

        r_status = cast(Response, self.client.get("/api/v1/reading/sessions/?status=completed"))
        self.assertEqual(r_status.status_code, 200)
        self.assertIn(str(self.session_visible.id), {s["id"] for s in response_data_list(r_status)})

        r_active = cast(Response, self.client.get("/api/v1/reading/sessions/?is_active=false"))
        self.assertEqual(r_active.status_code, 200)
        self.assertIn(str(self.session_visible.id), {s["id"] for s in response_data_list(r_active)})

    def test_closed_session_progress_get_does_not_reorder_book_sessions(self):
        target = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Historical target",
            status=ReadingSession.STATUS_COMPLETED,
            is_active=False,
        )
        other_closed = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Historical other",
            status=ReadingSession.STATUS_COMPLETED,
            is_active=False,
        )

        before = [row["id"] for row in list_sessions_for_book(user=self.user, book=self.book)]
        self.assertIn(str(target.id), before)
        self.assertIn(str(other_closed.id), before)
        self.assertFalse(ReadingProgress.objects.filter(session=target).exists())

        resp = cast(
            Response,
            self.client.get(f"/api/v1/reading/sessions/{target.id}/progress/"),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(ReadingProgress.objects.filter(session=target).exists())
        after = [row["id"] for row in list_sessions_for_book(user=self.user, book=self.book)]
        self.assertEqual(after, before)

    def test_q_matches_session_name(self):
        self.session_visible.name = "Late night reread"
        self.session_visible.save(update_fields=["name", "updated_at"])

        resp = cast(Response, self.client.get("/api/v1/reading/sessions/?q=reread"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual({s["id"] for s in response_data_list(resp)}, {str(self.session_visible.id)})

    def test_q_matches_session_notes(self):
        self.session_visible.notes = "Track notes for chapter pacing."
        self.session_visible.save(update_fields=["notes", "updated_at"])

        resp = cast(Response, self.client.get("/api/v1/reading/sessions/?q=pacing"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual({s["id"] for s in response_data_list(resp)}, {str(self.session_visible.id)})

    def test_q_matches_visible_book_title_subtitle_author_and_series(self):
        author = Author.objects.create(name="Jim Butcher")
        series = Series.objects.create(name="Dresden Files")
        self.book.title = "Blood Rites"
        self.book.subtitle = "A Dresden Case"
        self.book.series = series
        self.book.save(update_fields=["title", "subtitle", "series", "updated_at"])
        self.book.authors.add(author)

        cases = ["blood", "case", "butcher", "dresden"]
        for q in cases:
            with self.subTest(q=q):
                resp = cast(Response, self.client.get(f"/api/v1/reading/sessions/?q={q}"))
                self.assertEqual(resp.status_code, status.HTTP_200_OK)
                self.assertEqual(
                    {s["id"] for s in response_data_list(resp)},
                    {str(self.session_visible.id)},
                )

    def test_q_no_matches_returns_emptyresponse_data_list(self):
        resp = cast(Response, self.client.get("/api/v1/reading/sessions/?q=nomatch"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(response_data_list(resp), [])

    def test_whitespace_q_behaves_like_no_q(self):
        no_q = cast(Response, self.client.get("/api/v1/reading/sessions/"))
        whitespace = cast(Response, self.client.get("/api/v1/reading/sessions/?q=%20%20"))
        self.assertEqual(whitespace.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {s["id"] for s in response_data_list(whitespace)},
            {s["id"] for s in response_data_list(no_q)},
        )

    def test_q_combines_with_status_and_is_active_filters(self):
        active_match = self.session_visible
        active_match.name = "Shared marker"
        active_match.status = ReadingSession.STATUS_ACTIVE
        active_match.is_active = True
        active_match.save(update_fields=["name", "status", "is_active", "updated_at"])

        completed_match = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Shared marker",
            status=ReadingSession.STATUS_COMPLETED,
            is_active=False,
        )

        status_resp = cast(
            Response,
            self.client.get("/api/v1/reading/sessions/?q=marker&status=completed"),
        )
        self.assertEqual(status_resp.status_code, status.HTTP_200_OK)
        self.assertEqual({s["id"] for s in response_data_list(status_resp)}, {str(completed_match.id)})

        active_resp = cast(
            Response,
            self.client.get("/api/v1/reading/sessions/?q=marker&is_active=true"),
        )
        self.assertEqual(active_resp.status_code, status.HTTP_200_OK)
        self.assertEqual({s["id"] for s in response_data_list(active_resp)}, {str(active_match.id)})

    def test_q_combines_with_book_filter_and_keeps_context(self):
        self.session_visible.notes = "Notes for this visible book."
        self.session_visible.save(update_fields=["notes", "updated_at"])

        resp = cast(
            Response,
            self.client.get(f"/api/v1/reading/sessions/?book={self.book.id}&q=visible"),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = cast(dict[str, Any], resp.data)
        self.assertEqual(cast(dict[str, Any], payload["context"])["book"]["id"], str(self.book.id))
        self.assertEqual({s["id"] for s in response_data_list(resp)}, {str(self.session_visible.id)})

    def test_q_with_book_filter_can_return_zero_results_with_context(self):
        resp = cast(
            Response,
            self.client.get(f"/api/v1/reading/sessions/?book={self.book.id}&q=nomatch"),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = cast(dict[str, Any], resp.data)
        self.assertEqual(payload["results"], [])
        self.assertEqual(cast(dict[str, Any], payload["context"])["book"]["id"], str(self.book.id))

    def test_q_does_not_match_inaccessible_book_metadata_but_can_match_session_metadata(self):
        hidden_author = Author.objects.create(name="Private Author")
        hidden_series = Series.objects.create(name="Private Series")
        self.hidden_book.title = "Private Title"
        self.hidden_book.subtitle = "Private Subtitle"
        self.hidden_book.series = hidden_series
        self.hidden_book.save(update_fields=["title", "subtitle", "series", "updated_at"])
        self.hidden_book.authors.add(hidden_author)
        self.session_hidden.name = "Owned secret session"
        self.session_hidden.notes = "Personal reread note"
        self.session_hidden.save(update_fields=["name", "notes", "updated_at"])

        for q in ["Private%20Title", "Private%20Subtitle", "Private%20Author", "Private%20Series"]:
            with self.subTest(q=q):
                resp = cast(Response, self.client.get(f"/api/v1/reading/sessions/?q={q}"))
                self.assertEqual(resp.status_code, status.HTTP_200_OK)
                self.assertNotIn(str(self.session_hidden.id), {s["id"] for s in response_data_list(resp)})

        by_session_name = cast(
            Response,
            self.client.get("/api/v1/reading/sessions/?q=secret"),
        )
        self.assertEqual(by_session_name.status_code, status.HTTP_200_OK)
        hidden = next(s for s in response_data_list(by_session_name) if s["id"] == str(self.session_hidden.id))
        book = cast(dict[str, Any], hidden["book"])
        self.assertEqual(book["id"], str(self.hidden_book.id))
        self.assertEqual(book["title"], "")
        self.assertEqual(book["authors"], [])
        self.assertIsNone(book["series"])

    def test_book_filter_includes_context_for_visible_book(self):
        author = Author.objects.create(name="Jim Butcher")
        series = Series.objects.create(name="Dresden Files")
        self.book.title = "Blood Rites"
        self.book.series = series
        self.book.series_index = "6.0" # type: ignore
        self.book.save(update_fields=["title", "series", "series_index", "updated_at"])
        self.book.authors.add(author)

        resp = cast(Response, self.client.get(f"/api/v1/reading/sessions/?book={self.book.id}"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = cast(dict[str, Any], resp.data)
        context = cast(dict[str, Any], payload["context"])
        book = cast(dict[str, Any], context["book"])
        self.assertEqual(book["id"], str(self.book.id))
        self.assertEqual(book["title"], "Blood Rites")
        self.assertEqual(book["authors"], ["Jim Butcher"])
        self.assertEqual(book["series"], {"id": str(series.id), "name": "Dresden Files"})
        self.assertEqual(book["series_index"], "6.0")
        self.assertIn("cover_url", book)
        self.assertEqual({s["id"] for s in response_data_list(resp)}, {str(self.session_visible.id)})

    def test_book_filter_context_present_when_visible_book_has_zero_sessions(self):
        zero = create_file_backed_book(title="No Sessions", assign_public=False).book
        ensure_book_public_assignment(book=zero, added_by=None)

        resp = cast(Response, self.client.get(f"/api/v1/reading/sessions/?book={zero.id}"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = cast(dict[str, Any], resp.data)
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["results"], [])
        self.assertEqual(cast(dict[str, Any], payload["context"])["book"]["title"], "No Sessions")

    def test_book_filter_404s_for_nonexistent_or_inaccessible_book(self):
        nonexistent = cast(Response, self.client.get(f"/api/v1/reading/sessions/?book={uuid4()}"))
        self.assertEqual(nonexistent.status_code, status.HTTP_404_NOT_FOUND)

        inaccessible = cast(Response, self.client.get(f"/api/v1/reading/sessions/?book={self.hidden_book.id}"))
        self.assertEqual(inaccessible.status_code, status.HTTP_404_NOT_FOUND)

    def test_unfiltered_sessions_list_has_no_context(self):
        resp = cast(Response, self.client.get("/api/v1/reading/sessions/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn("context", cast(dict[str, Any], resp.data))

    def test_invalid_filters_return_400(self):
        bad_book = cast(Response, self.client.get("/api/v1/reading/sessions/?book=not-a-uuid"))
        self.assertEqual(bad_book.status_code, status.HTTP_400_BAD_REQUEST)

        bad_status = cast(Response, self.client.get("/api/v1/reading/sessions/?status=nope"))
        self.assertEqual(bad_status.status_code, status.HTTP_400_BAD_REQUEST)

        bad_active = cast(Response, self.client.get("/api/v1/reading/sessions/?is_active=maybe"))
        self.assertEqual(bad_active.status_code, status.HTTP_400_BAD_REQUEST)


class ReadingSessionSummaryBearerTests(SessionBearerFixtureMixin, APITestCase):
    def setUp(self):
        self.set_up_session_bearer_world()

    def test_bearer_can_search_sessions_with_q(self):
        self.session.name = "Bearer reread"
        self.session.save(update_fields=["name", "updated_at"])

        resp = cast(
            Response,
            self.client.get(
                "/api/v1/reading/sessions/?q=reread",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual({s["id"] for s in response_data_list(resp)}, {str(self.session.id)})
