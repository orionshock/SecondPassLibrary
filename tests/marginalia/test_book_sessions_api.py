from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_sessions.services import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from library.models import Book
from marginalia.models import Annotation, ReadingSession
from marginalia.books.queries import marginalia_books_for_user
from marginalia.sessions.queries import marginalia_sessions_for_book
from marginalia.sessions.serializers import (
    MarginaliaBookSummarySerializer,
    MarginaliaSessionSummarySerializer,
)


User = get_user_model()


class MarginaliaBookSessionAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.other = User.objects.create_user(username="other", password="testpass")
        self.client.force_login(self.user)
        self.book = Book.objects.create(
            title="Hidden Session Book",
            cover_file="covers/hidden-session-book.jpg",
        )
        self.unowned = Book.objects.create(title="Unowned Book")
        self.active = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Current pass",
            notes="Active session notes",
        )
        self.closed = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="First pass",
            notes="Remember the ending",
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now(),
        )
        self.older_closed = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Older pass",
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now() - timedelta(days=30),
        )
        self.other_session = ReadingSession.objects.create(
            user=self.other,
            book=self.book,
            name="Other user's pass",
        )
        ReadingSession.objects.create(user=self.other, book=self.unowned)
        self.url = f"/api/v1/marginalia/books/{self.book.id}/sessions/"

    def test_returns_only_caller_owned_sessions_with_bounded_summary(self):
        annotation = Annotation.objects.create(
            session=self.active,
            client_id="visible-bookmark",
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/2)",
        )
        Annotation.objects.create(
            session=self.active,
            client_id="deleted-bookmark",
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/4)",
            is_deleted=True,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["count"], 3)
        rows = {row["id"]: row for row in payload["results"]}
        self.assertNotIn(str(self.other_session.id), rows)
        active = rows[str(self.active.id)]
        self.assertEqual(active["annotation_count"], 1)
        self.assertEqual(
            set(active),
            {
                "id",
                "name",
                "notes",
                "status",
                "started_at",
                "closed_at",
                "updated_at",
                "last_activity_at",
                "annotation_count",
            },
        )
        self.assertNotIn("book", active)
        self.assertNotIn("file", active)
        self.assertTrue(Annotation.objects.filter(pk=annotation.pk).exists())

    def test_parent_context_is_canonical_and_does_not_require_library_access(self):
        response = self.client.get(self.url)
        detail = self.client.get(f"/api/v1/marginalia/books/{self.book.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["context"]["book"], detail.json())
        self.assertFalse(response.json()["context"]["book"]["can_open"])
        self.assertTrue(
            response.json()["context"]["book"]["cover_url"].endswith(
                "/media/covers/hidden-session-book.jpg"
            )
        )

    def test_missing_and_unowned_books_have_the_same_no_leakage_response(self):
        unowned = self.client.get(
            f"/api/v1/marginalia/books/{self.unowned.id}/sessions/"
        )
        missing = self.client.get(
            "/api/v1/marginalia/books/00000000-0000-0000-0000-000000000000/"
            "sessions/"
        )

        self.assertEqual(unowned.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(unowned.json(), missing.json())

    def test_status_filters_all_active_and_closed(self):
        all_rows = self.client.get(self.url).json()["results"]
        active_rows = self.client.get(self.url, {"status": "active"}).json()["results"]
        closed_rows = self.client.get(self.url, {"status": "closed"}).json()["results"]

        self.assertEqual(len(all_rows), 3)
        self.assertEqual([row["id"] for row in active_rows], [str(self.active.id)])
        self.assertEqual(
            {row["id"] for row in closed_rows},
            {str(self.closed.id), str(self.older_closed.id)},
        )

    def test_unsupported_status_is_rejected(self):
        response = self.client.get(self.url, {"status": "archived"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.json())

    def test_search_uses_session_name_and_notes_but_not_parent_book(self):
        by_name = self.client.get(self.url, {"q": "Current pass"}).json()["results"]
        by_notes = self.client.get(
            self.url, {"q": "Remember the ending"}
        ).json()["results"]
        by_book = self.client.get(
            self.url, {"q": "Hidden Session Book"}
        ).json()["results"]

        self.assertEqual([row["id"] for row in by_name], [str(self.active.id)])
        self.assertEqual([row["id"] for row in by_notes], [str(self.closed.id)])
        self.assertEqual(by_book, [])

    def test_pagination_count_is_caller_scoped_and_honest(self):
        first = self.client.get(self.url, {"page_size": 1})
        second = self.client.get(self.url, {"page_size": 1, "page": 2})

        self.assertEqual(first.json()["count"], 3)
        self.assertEqual(second.json()["count"], 3)
        self.assertEqual(len(first.json()["results"]), 1)
        self.assertEqual(len(second.json()["results"]), 1)

    def test_default_order_uses_latest_session_progress_or_annotation_activity(self):
        now = timezone.now()
        oldest = now - timedelta(days=4)
        middle = now - timedelta(days=3)
        newest = now - timedelta(days=2)
        ReadingSession.objects.filter(
            pk__in=[self.active.pk, self.closed.pk, self.older_closed.pk]
        ).update(updated_at=oldest)
        ReadingSession.objects.filter(pk=self.active.pk).update(
            progress_cfi="epubcfi(/6/4)",
            progress_updated_at=middle,
        )
        annotation = Annotation.objects.create(
            session=self.closed,
            client_id="closed-activity",
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/8)",
        )
        Annotation.objects.filter(pk=annotation.pk).update(updated_at=newest)

        rows = self.client.get(self.url).json()["results"]

        self.assertEqual(rows[0]["id"], str(self.closed.id))
        self.assertEqual(parse_datetime(rows[0]["last_activity_at"]), newest)
        self.assertEqual(rows[1]["id"], str(self.active.id))
        self.assertEqual(parse_datetime(rows[1]["last_activity_at"]), middle)

    def test_empty_filtered_page_retains_parent_context(self):
        payload = self.client.get(self.url, {"q": "no such session"}).json()

        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["results"], [])
        self.assertEqual(payload["context"]["book"]["id"], str(self.book.id))

    def test_session_and_bearer_authentication_return_the_same_page(self):
        session_payload = self.client.get(self.url).json()
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        bearer = APIClient()

        bearer_response = bearer.get(
            self.url,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(bearer_response.status_code, status.HTTP_200_OK)
        self.assertEqual(bearer_response.json(), session_payload)

    def test_projection_queries_do_not_grow_per_session(self):
        with self.assertNumQueries(3):
            book = marginalia_books_for_user(user=self.user).get(pk=self.book.pk)
            sessions = list(marginalia_sessions_for_book(user=self.user, book=book))
            context = MarginaliaBookSummarySerializer(book).data
            rows = MarginaliaSessionSummarySerializer(sessions, many=True).data

        self.assertEqual(context["id"], str(self.book.id))
        self.assertEqual(len(rows), 3)

    def test_route_is_read_only(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
