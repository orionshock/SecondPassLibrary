from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.client_api import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from library.group_services import (
    add_book_to_group,
    ensure_book_public_assignment,
    ensure_user_public_membership,
)
from library.models import Author, LibraryGroup, LibraryGroupMembership, Series
from reading.models import Annotation, ReadingProgress, ReadingSession
from tests.utils.books import create_file_backed_book


User = get_user_model()


def _results(resp: Response) -> list[dict[str, Any]]:
    payload = cast(dict[str, Any], resp.data)
    return cast(list[dict[str, Any]], payload.get("results") or [])


class ReadingSessionSummarySessionAuthTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(username="owner", password="pw", email="o@example.com")
        ensure_user_public_membership(user=self.owner)

        self.user = User.objects.create_user(username="u", password="pw", email="u@example.com")
        ensure_user_public_membership(user=self.user)
        self.client.login(username="u", password="pw")

        self.book = create_file_backed_book(title="Visible").book

        self.hidden_group = LibraryGroup.objects.create(name="Hidden")
        other = User.objects.create_user(username="other", password="pw", email="o@example.com")
        ensure_user_public_membership(user=other)
        LibraryGroupMembership.objects.create(user=other, group=self.hidden_group, is_curator=False)

        self.hidden_book = create_file_backed_book(title="Hidden", assign_public=False).book
        add_book_to_group(actor=self.owner, book=self.hidden_book, group=self.hidden_group)

        self.session_visible = ReadingSession.objects.create(user=self.user, book=self.book, name="S1")
        ReadingProgress.objects.create(session=self.session_visible, current_location={"cfi": "/6/2"}, progression=0.25)
        Annotation.objects.create(
            session=self.session_visible,
            book=self.book,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/2)",
            highlight_text="hi",
        )
        Annotation.objects.create(
            session=self.session_visible,
            book=self.book,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/4)",
            highlight_text="deleted",
            comment_text="deleted",
            is_deleted=True,
        )

        self.session_hidden = ReadingSession.objects.create(user=self.user, book=self.hidden_book, name="Secret")

    def test_list_includes_progression_annotation_count_and_compact_book(self):
        resp = cast(Response, self.client.get("/api/v1/reading/sessions/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = _results(resp)
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
        results = _results(resp)
        hidden = next(r for r in results if r["id"] == str(self.session_hidden.id))
        book = cast(dict[str, Any], hidden["book"])
        self.assertEqual(book["id"], str(self.hidden_book.id))
        self.assertEqual(book["title"], "")
        self.assertEqual(book["authors"], [])
        self.assertIsNone(book["series"])
        self.assertIsNone(book["cover_url"])

    def test_filters_book_status_is_active(self):
        self.session_visible.status = ReadingSession.STATUS_COMPLETED
        self.session_visible.is_active = False
        self.session_visible.save(update_fields=["status", "is_active", "updated_at"])

        r_book = cast(Response, self.client.get(f"/api/v1/reading/sessions/?book={self.book.id}"))
        self.assertEqual(r_book.status_code, 200)
        self.assertEqual({s["id"] for s in _results(r_book)}, {str(self.session_visible.id)})

        r_status = cast(Response, self.client.get("/api/v1/reading/sessions/?status=completed"))
        self.assertEqual(r_status.status_code, 200)
        self.assertIn(str(self.session_visible.id), {s["id"] for s in _results(r_status)})

        r_active = cast(Response, self.client.get("/api/v1/reading/sessions/?is_active=false"))
        self.assertEqual(r_active.status_code, 200)
        self.assertIn(str(self.session_visible.id), {s["id"] for s in _results(r_active)})

    def test_q_matches_session_name(self):
        self.session_visible.name = "Late night reread"
        self.session_visible.save(update_fields=["name", "updated_at"])

        resp = cast(Response, self.client.get("/api/v1/reading/sessions/?q=reread"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual({s["id"] for s in _results(resp)}, {str(self.session_visible.id)})

    def test_q_matches_session_notes(self):
        self.session_visible.notes = "Track notes for chapter pacing."
        self.session_visible.save(update_fields=["notes", "updated_at"])

        resp = cast(Response, self.client.get("/api/v1/reading/sessions/?q=pacing"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual({s["id"] for s in _results(resp)}, {str(self.session_visible.id)})

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
                    {s["id"] for s in _results(resp)},
                    {str(self.session_visible.id)},
                )

    def test_q_no_matches_returns_empty_results(self):
        resp = cast(Response, self.client.get("/api/v1/reading/sessions/?q=nomatch"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(_results(resp), [])

    def test_whitespace_q_behaves_like_no_q(self):
        no_q = cast(Response, self.client.get("/api/v1/reading/sessions/"))
        whitespace = cast(Response, self.client.get("/api/v1/reading/sessions/?q=%20%20"))
        self.assertEqual(whitespace.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {s["id"] for s in _results(whitespace)},
            {s["id"] for s in _results(no_q)},
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
        self.assertEqual({s["id"] for s in _results(status_resp)}, {str(completed_match.id)})

        active_resp = cast(
            Response,
            self.client.get("/api/v1/reading/sessions/?q=marker&is_active=true"),
        )
        self.assertEqual(active_resp.status_code, status.HTTP_200_OK)
        self.assertEqual({s["id"] for s in _results(active_resp)}, {str(active_match.id)})

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
        self.assertEqual({s["id"] for s in _results(resp)}, {str(self.session_visible.id)})

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
                self.assertNotIn(str(self.session_hidden.id), {s["id"] for s in _results(resp)})

        by_session_name = cast(
            Response,
            self.client.get("/api/v1/reading/sessions/?q=secret"),
        )
        self.assertEqual(by_session_name.status_code, status.HTTP_200_OK)
        hidden = next(s for s in _results(by_session_name) if s["id"] == str(self.session_hidden.id))
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
        self.assertEqual({s["id"] for s in _results(resp)}, {str(self.session_visible.id)})

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


class ReadingSessionSummaryBearerTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pw", email="u@example.com")
        ensure_user_public_membership(user=self.user)

        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        self._auth = f"Bearer {token}"

        self.book = create_file_backed_book(title="Visible").book
        self.session = ReadingSession.objects.create(user=self.user, book=self.book)

    def test_bearer_list_includes_compact_book(self):
        resp = cast(Response, self.client.get("/api/v1/reading/sessions/", HTTP_AUTHORIZATION=self._auth))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = _results(resp)
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
        self.assertEqual({s["id"] for s in _results(resp)}, {str(self.session.id)})
