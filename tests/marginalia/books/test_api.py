from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_sessions.services import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from library.cover_objects import canonical_cover_storage_name
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
from marginalia.books.queries import marginalia_books_for_user
from marginalia.books.serializers import MarginaliaBookSummarySerializer


User = get_user_model()


class MarginaliaBookAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.other = User.objects.create_user(username="other", password="testpass")
        self.client.force_login(self.user)

        self.visible_group = LibraryGroup.objects.create(name="Readers")
        LibraryGroupMembership.objects.create(user=self.user, group=self.visible_group)

        self.visible = Book.objects.create(title="Visible Storm")
        BookGroupAssignment.objects.create(book=self.visible, group=self.visible_group)
        self.hidden = Book.objects.create(
            title="Hidden Archive",
            cover_file=canonical_cover_storage_name(digest="4" * 64, extension=".jpg"),
        )
        self.other_only = Book.objects.create(title="Someone Else's Notes")
        self.no_sessions = Book.objects.create(title="No Marginalia")

        self.visible_session = ReadingSession.objects.create(
            user=self.user,
            book=self.visible,
        )
        self.hidden_closed = ReadingSession.objects.create(
            user=self.user,
            book=self.hidden,
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now(),
        )
        self.hidden_older_closed = ReadingSession.objects.create(
            user=self.user,
            book=self.hidden,
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now(),
        )
        ReadingSession.objects.create(user=self.other, book=self.hidden)
        ReadingSession.objects.create(user=self.other, book=self.other_only)

    def test_list_is_owned_book_projection_with_caller_scoped_counts(self):
        response = self.client.get("/api/v1/marginalia/books/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        rows = {row["id"]: row for row in payload["results"]}
        self.assertEqual(set(rows), {str(self.visible.id), str(self.hidden.id)})
        self.assertEqual(rows[str(self.hidden.id)]["session_count"], 2)
        self.assertEqual(rows[str(self.hidden.id)]["active_session_count"], 0)
        self.assertEqual(rows[str(self.visible.id)]["active_session_count"], 1)

    def test_pagination_counts_distinct_books_with_multiple_sessions(self):
        response = self.client.get(
            "/api/v1/marginalia/books/",
            {"page_size": 1},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["count"], 2)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertIsNotNone(response.json()["next"])

    def test_projection_query_count_does_not_scale_per_book(self):
        queryset = marginalia_books_for_user(user=self.user)

        with self.assertNumQueries(2):
            books = list(queryset)
            payload = MarginaliaBookSummarySerializer(books, many=True).data

        self.assertEqual(len(payload), 2)

    def test_historical_projection_is_bounded_and_open_authority_is_independent(self):
        response = self.client.get(f"/api/v1/marginalia/books/{self.hidden.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.json()
        self.assertFalse(row["can_open"])
        self.assertTrue(
            row["cover_url"].endswith(f"/media/{self.hidden.cover_file.name}")
        )
        self.assertEqual(
            set(row),
            {
                "id",
                "title",
                "authors",
                "series",
                "cover_url",
                "can_open",
                "session_count",
                "active_session_count",
                "last_activity_at",
            },
        )

        visible = self.client.get(f"/api/v1/marginalia/books/{self.visible.id}/")
        self.assertTrue(visible.json()["can_open"])

    def test_last_activity_includes_progress_and_annotations_and_orders_newest_first(
        self,
    ):
        now = timezone.now()
        older = now - timedelta(days=3)
        middle = now - timedelta(days=2)
        newest = now - timedelta(days=1)
        ReadingSession.objects.filter(pk=self.visible_session.pk).update(
            updated_at=middle
        )
        ReadingSession.objects.filter(pk=self.hidden_closed.pk).update(updated_at=older)
        ReadingSession.objects.filter(pk=self.hidden_older_closed.pk).update(
            updated_at=older
        )
        ReadingSession.objects.filter(pk=self.visible_session.pk).update(
            progress_location="epubcfi(/6/4)",
            progress_updated_at=middle,
        )
        annotation = Annotation.objects.create(
            session=self.hidden_closed,
            client_id="book-activity",
            kind=Annotation.KIND_BOOKMARK,
            location="epubcfi(/6/2)",
        )
        Annotation.objects.filter(pk=annotation.pk).update(updated_at=newest)

        rows = self.client.get("/api/v1/marginalia/books/").json()["results"]

        self.assertEqual(rows[0]["id"], str(self.hidden.id))
        self.assertEqual(parse_datetime(rows[0]["last_activity_at"]), newest)

    def test_search_uses_title_author_and_series_only(self):
        author = Author.objects.create(name="Octavia Butler")
        BookAuthor.objects.create(book=self.visible, author=author, position=0)
        series = Series.objects.create(name="Patternist")
        BookSeries.objects.create(book=self.hidden, series=series, series_index="2.50")

        for term, expected_id in (
            ("Visible Storm", self.visible.id),
            ("Octavia", self.visible.id),
            ("Patternist", self.hidden.id),
        ):
            with self.subTest(term=term):
                rows = self.client.get("/api/v1/marginalia/books/", {"q": term}).json()[
                    "results"
                ]
                self.assertEqual([row["id"] for row in rows], [str(expected_id)])

        self.visible_session.notes = "private search phrase"
        self.visible_session.save(update_fields=["notes", "updated_at"])
        self.assertEqual(
            self.client.get(
                "/api/v1/marginalia/books/", {"q": "private search phrase"}
            ).json()["results"],
            [],
        )

    def test_authors_and_series_use_the_canonical_summary_shape(self):
        first = Author.objects.create(name="First Author")
        second = Author.objects.create(name="Second Author")
        BookAuthor.objects.create(book=self.hidden, author=second, position=1)
        BookAuthor.objects.create(book=self.hidden, author=first, position=0)
        series = Series.objects.create(name="Archive Cycle")
        BookSeries.objects.create(book=self.hidden, series=series, series_index="3.50")

        row = self.client.get(f"/api/v1/marginalia/books/{self.hidden.id}/").json()

        self.assertEqual(
            row["authors"],
            [
                {"id": str(first.id), "name": "First Author"},
                {"id": str(second.id), "name": "Second Author"},
            ],
        )
        self.assertEqual(
            row["series"],
            {
                "id": str(series.id),
                "name": "Archive Cycle",
                "series_index": "3.50",
            },
        )

    def test_detail_uses_no_leakage_not_found_for_unowned_and_missing_books(self):
        unowned = self.client.get(f"/api/v1/marginalia/books/{self.other_only.id}/")
        missing = self.client.get(
            "/api/v1/marginalia/books/00000000-0000-0000-0000-000000000000/"
        )

        self.assertEqual(unowned.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(unowned.json(), missing.json())

    def test_session_and_bearer_authentication_return_the_same_projection(self):
        session_payload = self.client.get("/api/v1/marginalia/books/").json()
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        bearer = APIClient()

        bearer_response = bearer.get(
            "/api/v1/marginalia/books/",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(bearer_response.status_code, status.HTTP_200_OK)
        self.assertEqual(bearer_response.json(), session_payload)

    def test_anonymous_access_is_rejected(self):
        self.client.logout()

        response = self.client.get("/api/v1/marginalia/books/")

        self.assertIn(
            response.status_code,
            {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN},
        )

    def test_book_routes_are_read_only(self):
        listed = self.client.post("/api/v1/marginalia/books/", {}, format="json")
        detailed = self.client.patch(
            f"/api/v1/marginalia/books/{self.visible.id}/",
            {"title": "No"},
            format="json",
        )

        self.assertEqual(listed.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(detailed.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
