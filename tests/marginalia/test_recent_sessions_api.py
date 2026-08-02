from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_api import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from django.db import connection
from library.models import Book
from marginalia.models import Annotation, ReadingSession
from marginalia.sessions.queries import recent_marginalia_sessions_for_user
from marginalia.sessions.serializers import MarginaliaRecentSessionSerializer


User = get_user_model()


class MarginaliaRecentSessionAPITests(APITestCase):
    url = "/api/v1/marginalia/sessions/recent/"

    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.other = User.objects.create_user(username="other", password="testpass")
        self.client.force_login(self.user)
        self.book = Book.objects.create(
            title="Remembered Book",
            cover_file="covers/remembered.jpg",
        )
        self.other_book = Book.objects.create(title="Other Book")
        self.active = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Current pass",
        )
        self.closed = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="First pass",
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now(),
        )
        self.foreign = ReadingSession.objects.create(
            user=self.other,
            book=self.other_book,
            name="Private pass",
        )

    def test_active_default_and_optional_closed_sessions_are_owner_scoped(self):
        default = self.client.get(self.url)
        with_closed = self.client.get(self.url, {"include_closed": "true"})

        self.assertEqual(default.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["id"] for row in default.json()["results"]],
            [str(self.active.id)],
        )
        self.assertEqual(
            {row["id"] for row in with_closed.json()["results"]},
            {str(self.active.id), str(self.closed.id)},
        )
        self.assertNotIn(
            str(self.foreign.id),
            {row["id"] for row in with_closed.json()["results"]},
        )

    def test_activity_order_uses_progress_and_only_non_deleted_annotations(self):
        now = timezone.now()
        progress_book = Book.objects.create(title="Progress Book")
        annotation_book = Book.objects.create(title="Annotation Book")
        deleted_book = Book.objects.create(title="Deleted Annotation Book")
        progress = ReadingSession.objects.create(user=self.user, book=progress_book)
        annotated = ReadingSession.objects.create(user=self.user, book=annotation_book)
        deleted = ReadingSession.objects.create(user=self.user, book=deleted_book)
        oldest = now - timedelta(days=5)
        ReadingSession.objects.filter(
            pk__in=[self.active.pk, progress.pk, annotated.pk, deleted.pk]
        ).update(updated_at=oldest)
        ReadingSession.objects.filter(pk=progress.pk).update(
            progress_cfi="epubcfi(/6/4)",
            progress_updated_at=now - timedelta(days=2),
        )
        visible_annotation = Annotation.objects.create(
            session=annotated,
            client_id="recent-visible",
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/6)",
        )
        Annotation.objects.filter(pk=visible_annotation.pk).update(
            updated_at=now - timedelta(days=1)
        )
        deleted_annotation = Annotation.objects.create(
            session=deleted,
            client_id="recent-deleted",
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/8)",
            is_deleted=True,
        )
        Annotation.objects.filter(pk=deleted_annotation.pk).update(updated_at=now)

        rows = self.client.get(self.url).json()["results"]

        self.assertEqual(rows[0]["id"], str(annotated.id))
        self.assertEqual(parse_datetime(rows[0]["last_activity_at"]), now - timedelta(days=1))
        self.assertEqual(rows[1]["id"], str(progress.id))
        self.assertGreater(
            next(index for index, row in enumerate(rows) if row["id"] == str(deleted.id)),
            1,
        )

    def test_limit_is_validated_and_applied_after_the_active_filter(self):
        newer_closed = ReadingSession.objects.create(
            user=self.user,
            book=Book.objects.create(title="Closed Book"),
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now(),
        )
        second_active = ReadingSession.objects.create(
            user=self.user,
            book=Book.objects.create(title="Second Active Book"),
        )
        ReadingSession.objects.filter(pk=newer_closed.pk).update(
            updated_at=timezone.now() + timedelta(hours=1)
        )

        limited = self.client.get(self.url, {"limit": 2}).json()["results"]

        self.assertEqual({row["id"] for row in limited}, {str(self.active.id), str(second_active.id)})
        self.assertEqual(self.client.get(self.url, {"limit": 0}).status_code, 400)
        self.assertEqual(self.client.get(self.url, {"limit": 51}).status_code, 400)

    def test_default_limit_is_ten_and_sessions_are_not_deduplicated_by_book(self):
        for number in range(11):
            ReadingSession.objects.create(
                user=self.user,
                book=Book.objects.create(title=f"Active Book {number}"),
            )

        default_rows = self.client.get(self.url).json()["results"]
        same_book_rows = self.client.get(
            self.url,
            {"include_closed": "true", "limit": 50},
        ).json()["results"]

        self.assertEqual(len(default_rows), 10)
        self.assertEqual(
            sum(row["book"]["id"] == str(self.book.id) for row in same_book_rows),
            2,
        )

    def test_projection_keeps_inaccessible_book_identity_and_is_bounded(self):
        row = self.client.get(self.url).json()["results"][0]

        self.assertEqual(
            set(row),
            {"id", "name", "status", "last_activity_at", "book"},
        )
        self.assertEqual(set(row["book"]), {"id", "title", "cover_url", "can_open"})
        self.assertEqual(row["book"]["title"], "Remembered Book")
        self.assertTrue(row["book"]["cover_url"].endswith("/media/covers/remembered.jpg"))
        self.assertFalse(row["book"]["can_open"])

    def test_session_and_bearer_authentication_match_and_anonymous_is_rejected(self):
        session_payload = self.client.get(self.url).json()
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        bearer = APIClient()

        response = bearer.get(self.url, HTTP_AUTHORIZATION=f"Bearer {token}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), session_payload)
        self.assertIn(APIClient().get(self.url).status_code, {401, 403})

    def test_query_is_database_limited_bounded_and_get_is_read_only(self):
        before = ReadingSession.objects.get(pk=self.active.pk).updated_at
        queryset = recent_marginalia_sessions_for_user(user=self.user, limit=1)
        self.assertEqual(queryset.query.low_mark, 0)
        self.assertEqual(queryset.query.high_mark, 1)

        with CaptureQueriesContext(connection) as queries:
            rows = MarginaliaRecentSessionSerializer(list(queryset), many=True).data

        self.assertEqual(len(queries), 1)
        self.assertEqual(len(rows), 1)
        self.client.get(self.url)
        self.assertEqual(ReadingSession.objects.get(pk=self.active.pk).updated_at, before)
