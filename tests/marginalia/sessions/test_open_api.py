from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_sessions.services import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from library.models import (
    Book,
    BookGroupAssignment,
    LibraryGroup,
    LibraryGroupMembership,
)
from marginalia.models import Annotation, ReadingSession
from marginalia.sessions.envelopes import bootstrap_envelope


User = get_user_model()


class MarginaliaOpenActiveBootstrapTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.other = User.objects.create_user(username="other", password="testpass")
        self.group = LibraryGroup.objects.create(name="Readers")
        LibraryGroupMembership.objects.create(user=self.user, group=self.group)
        self.book = Book.objects.create(title="Bootstrap Book")
        BookGroupAssignment.objects.create(book=self.book, group=self.group)
        self.client.force_login(self.user)

    @property
    def open_url(self):
        return f"/api/v1/marginalia/books/{self.book.id}/open/"

    @property
    def active_url(self):
        return f"/api/v1/marginalia/books/{self.book.id}/active-session/"

    def test_open_creates_one_active_session_with_creation_defaults(self):
        response = self.client.post(
            self.open_url,
            {"name": "First pass", "notes": "Initial notes"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        payload = response.json()
        self.assertTrue(payload["created"])
        self.assertEqual(payload["session"]["name"], "First pass")
        self.assertEqual(payload["session"]["notes"], "Initial notes")
        self.assertIsNone(payload["session"]["progress"])
        self.assertEqual(payload["annotations"], [])
        self.assertEqual(payload["closed_sessions"]["results"], [])
        self.assertEqual(
            ReadingSession.objects.filter(
                user=self.user,
                book=self.book,
                status=ReadingSession.STATUS_ACTIVE,
            ).count(),
            1,
        )

    def test_open_reuses_without_mutating_the_existing_session(self):
        existing = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Existing",
            notes="Keep me",
        )
        before = existing.updated_at

        response = self.client.post(
            self.open_url,
            {"name": "Replacement", "notes": "Do not use"},
            format="json",
        )
        existing.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.json()["created"])
        self.assertEqual(response.json()["session"]["id"], str(existing.id))
        self.assertEqual((existing.name, existing.notes), ("Existing", "Keep me"))
        self.assertEqual(existing.updated_at, before)
        self.assertEqual(
            ReadingSession.objects.filter(user=self.user, book=self.book).count(), 1
        )

    def test_bootstrap_contains_complete_ordered_annotations_and_closed_page(self):
        active = ReadingSession.objects.create(user=self.user, book=self.book)
        progress_updated_at = timezone.now()
        ReadingSession.objects.filter(pk=active.pk).update(
            progress_location="epubcfi(/6/6)",
            progress_location_label="Chapter 06",
            progress_updated_at=progress_updated_at,
        )
        for index in range(21):
            ReadingSession.objects.create(
                user=self.user,
                book=self.book,
                status=ReadingSession.STATUS_CLOSED,
                closed_at=timezone.now(),
                name=f"Closed {index}",
            )
        later = Annotation.objects.create(
            session=active,
            client_id="later",
            kind=Annotation.KIND_BOOKMARK,
            location="epubcfi(/6/10)",
            location_label="Chapter 10",
        )
        earlier = Annotation.objects.create(
            session=active,
            client_id="earlier",
            kind=Annotation.KIND_BOOKMARK,
            location="epubcfi(/6/2)",
            location_label="Chapter 02",
        )
        Annotation.objects.create(
            session=active,
            client_id="deleted",
            kind=Annotation.KIND_BOOKMARK,
            location="epubcfi(/6/1)",
            location_label="Chapter 01",
            is_deleted=True,
        )

        payload = self.client.get(self.active_url).json()

        self.assertEqual(payload["session"]["progress"]["location"], "epubcfi(/6/6)")
        self.assertEqual(
            payload["session"]["progress"]["location_label"],
            "Chapter 06",
        )
        self.assertEqual(
            [row["id"] for row in payload["annotations"]],
            [str(earlier.id), str(later.id)],
        )
        self.assertEqual(payload["closed_sessions"]["count"], 21)
        self.assertEqual(len(payload["closed_sessions"]["results"]), 20)
        self.assertEqual(payload["closed_sessions"]["previous"], None)
        self.assertIn(
            f"/api/v1/marginalia/books/{self.book.id}/sessions/?status=closed&page=2",
            payload["closed_sessions"]["next"],
        )
        self.assertEqual(
            set(payload["context"]["book"]),
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

    def test_active_session_is_read_only_and_returns_history_when_none_is_active(self):
        closed = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now(),
        )
        before = closed.updated_at

        response = self.client.get(self.active_url)
        closed.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.json()["created"])
        self.assertIsNone(response.json()["session"])
        self.assertEqual(response.json()["annotations"], [])
        self.assertEqual(response.json()["closed_sessions"]["count"], 1)
        self.assertEqual(closed.updated_at, before)
        self.assertEqual(
            ReadingSession.objects.filter(user=self.user, book=self.book).count(), 1
        )

    def test_active_session_supports_an_authorized_book_with_no_history(self):
        response = self.client.get(self.active_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.json()["session"])
        self.assertEqual(response.json()["annotations"], [])
        self.assertEqual(response.json()["closed_sessions"]["count"], 0)
        self.assertEqual(response.json()["context"]["book"]["session_count"], 0)
        self.assertIsNone(response.json()["context"]["book"]["last_activity_at"])
        self.assertFalse(
            ReadingSession.objects.filter(user=self.user, book=self.book).exists()
        )

    def test_authority_is_required_without_inspecting_book_asset_state(self):
        inaccessible = Book.objects.create(title="Hidden")
        hidden_url = f"/api/v1/marginalia/books/{inaccessible.id}/open/"

        denied = self.client.post(hidden_url, {}, format="json")
        denied_active = self.client.get(
            f"/api/v1/marginalia/books/{inaccessible.id}/active-session/"
        )
        allowed = self.client.post(self.open_url, {}, format="json")

        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(denied_active.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(allowed.status_code, status.HTTP_201_CREATED)

    def test_foreign_data_is_excluded_and_bearer_auth_matches_session_auth(self):
        own = ReadingSession.objects.create(user=self.user, book=self.book)
        ReadingSession.objects.create(
            user=self.other,
            book=self.book,
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now(),
        )
        session_payload = self.client.get(self.active_url).json()
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        bearer = APIClient()

        response = bearer.get(
            self.active_url,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), session_payload)
        self.assertEqual(response.json()["session"]["id"], str(own.id))
        self.assertEqual(response.json()["closed_sessions"]["count"], 0)

    def test_open_rejects_unknown_fields(self):
        response = self.client.post(
            self.open_url,
            {"progress": {"location": "epubcfi(/6/2)"}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            ReadingSession.objects.filter(user=self.user, book=self.book).exists()
        )

    def test_bootstrap_query_count_is_bounded(self):
        active = ReadingSession.objects.create(user=self.user, book=self.book)
        Annotation.objects.create(
            session=active,
            client_id="one",
            kind=Annotation.KIND_BOOKMARK,
            location="epubcfi(/6/2)",
        )
        request = RequestFactory().get(self.active_url)
        request.user = self.user

        with CaptureQueriesContext(connection) as queries:
            payload = bootstrap_envelope(
                request=request,
                book_id=self.book.id,
                session_id=active.id,
                created=False,
            )

        self.assertLessEqual(len(queries), 6)
        self.assertEqual(payload["session"]["id"], str(active.id))
