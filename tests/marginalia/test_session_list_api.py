from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_api import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from library.models import (
    Author,
    Book,
    BookAuthor,
    BookGroupAssignment,
    BookSeries,
    LibraryGroup,
    LibraryGroupMembership,
    Series,
)
from marginalia.models import Annotation, ReadingSession
from marginalia.queries import marginalia_sessions_for_user
from marginalia.serializers import MarginaliaGlobalSessionSummarySerializer


User = get_user_model()


class MarginaliaSessionListAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.other = User.objects.create_user(username="other", password="testpass")
        self.client.force_login(self.user)

        group = LibraryGroup.objects.create(name="Visible Library")
        LibraryGroupMembership.objects.create(user=self.user, group=group)
        self.visible_book = Book.objects.create(title="Visible Book")
        BookGroupAssignment.objects.create(book=self.visible_book, group=group)
        self.hidden_book = Book.objects.create(
            title="Historical Book",
            cover_file="covers/historical-book.jpg",
        )
        self.other_book = Book.objects.create(title="Other User Secret Book")

        author = Author.objects.create(name="Searchable Author")
        BookAuthor.objects.create(book=self.visible_book, author=author, position=0)
        series = Series.objects.create(name="Searchable Series")
        BookSeries.objects.create(book=self.hidden_book, series=series, series_index="2.0")

        self.active = ReadingSession.objects.create(
            user=self.user,
            book=self.visible_book,
            name="Current journey",
            notes="Active notes phrase",
        )
        self.closed = ReadingSession.objects.create(
            user=self.user,
            book=self.hidden_book,
            name="Finished journey",
            notes="Closed notes phrase",
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now(),
        )
        self.older_closed = ReadingSession.objects.create(
            user=self.user,
            book=self.visible_book,
            name="Earlier journey",
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now() - timedelta(days=10),
        )
        self.other_session = ReadingSession.objects.create(
            user=self.other,
            book=self.hidden_book,
            name="Other user session",
        )
        ReadingSession.objects.create(user=self.other, book=self.other_book)
        self.url = "/api/v1/marginalia/sessions/"

    def test_returns_only_caller_owned_sessions_across_books(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["count"], 3)
        self.assertEqual(
            {row["id"] for row in payload["results"]},
            {str(self.active.id), str(self.closed.id), str(self.older_closed.id)},
        )
        self.assertNotIn(
            str(self.other_session.id),
            {row["id"] for row in payload["results"]},
        )

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

    def test_searches_session_and_bounded_book_identity(self):
        cases = (
            ("Current journey", {self.active.id}),
            ("Closed notes phrase", {self.closed.id}),
            ("Visible Book", {self.active.id, self.older_closed.id}),
            ("Searchable Author", {self.active.id, self.older_closed.id}),
            ("Searchable Series", {self.closed.id}),
        )
        for term, expected_ids in cases:
            with self.subTest(term=term):
                rows = self.client.get(self.url, {"q": term}).json()["results"]
                self.assertEqual(
                    {row["id"] for row in rows},
                    {str(session_id) for session_id in expected_ids},
                )

    def test_search_does_not_leak_other_user_books_or_sessions(self):
        by_book = self.client.get(
            self.url,
            {"q": "Other User Secret Book"},
        ).json()["results"]
        by_session = self.client.get(
            self.url,
            {"q": "Other user session"},
        ).json()["results"]

        self.assertEqual(by_book, [])
        self.assertEqual(by_session, [])

    def test_pagination_count_is_session_level_and_caller_scoped(self):
        first = self.client.get(self.url, {"page_size": 1})
        second = self.client.get(self.url, {"page_size": 1, "page": 2})

        self.assertEqual(first.json()["count"], 3)
        self.assertEqual(second.json()["count"], 3)
        self.assertEqual(len(first.json()["results"]), 1)
        self.assertEqual(len(second.json()["results"]), 1)

    def test_default_order_uses_session_progress_and_annotation_activity(self):
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
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/2)",
        )
        Annotation.objects.filter(pk=annotation.pk).update(updated_at=newest)

        rows = self.client.get(self.url).json()["results"]

        self.assertEqual(rows[0]["id"], str(self.closed.id))
        self.assertEqual(parse_datetime(rows[0]["last_activity_at"]), newest)
        self.assertEqual(rows[1]["id"], str(self.active.id))
        self.assertEqual(parse_datetime(rows[1]["last_activity_at"]), middle)

    def test_book_reference_is_bounded_and_keeps_historical_identity(self):
        rows = {
            row["id"]: row for row in self.client.get(self.url).json()["results"]
        }
        hidden = rows[str(self.closed.id)]["book"]
        visible = rows[str(self.active.id)]["book"]

        self.assertEqual(
            set(hidden),
            {"id", "title", "cover_url", "can_open"},
        )
        self.assertEqual(hidden["title"], "Historical Book")
        self.assertTrue(hidden["cover_url"].endswith("/media/covers/historical-book.jpg"))
        self.assertFalse(hidden["can_open"])
        self.assertTrue(visible["can_open"])
        self.assertEqual(
            set(rows[str(self.closed.id)]),
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
                "book",
            },
        )

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

    def test_projection_query_does_not_grow_per_session(self):
        with self.assertNumQueries(1):
            sessions = list(marginalia_sessions_for_user(user=self.user))
            rows = MarginaliaGlobalSessionSummarySerializer(sessions, many=True).data

        self.assertEqual(len(rows), 3)

    def test_route_is_read_only(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
