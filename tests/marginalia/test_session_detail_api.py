from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_api import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from library.models import Book
from marginalia.detail_serializers import MarginaliaSessionDetailEnvelopeSerializer
from marginalia.models import Annotation, ReadingSession
from marginalia.progress_services import assign_session_progress
from marginalia.queries import marginalia_books_for_user, marginalia_session_for_user


User = get_user_model()


class MarginaliaSessionDetailAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.other = User.objects.create_user(username="other", password="testpass")
        self.book = Book.objects.create(title="Historical Book")
        self.active = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Current pass",
            notes="Original notes",
        )
        self.closed = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Earlier pass",
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now(),
        )
        self.foreign = ReadingSession.objects.create(
            user=self.other,
            book=self.book,
            name="Private pass",
        )
        self.client.force_login(self.user)

    def url(self, session: ReadingSession) -> str:
        return f"/api/v1/marginalia/sessions/{session.id}/"

    def test_owner_reads_active_and_closed_history_without_library_access(self):
        active = self.client.get(self.url(self.active))
        closed = self.client.get(self.url(self.closed))

        self.assertEqual(active.status_code, status.HTTP_200_OK)
        self.assertEqual(closed.status_code, status.HTTP_200_OK)
        self.assertEqual(active.json()["session"]["status"], "active")
        self.assertEqual(closed.json()["session"]["status"], "closed")
        self.assertFalse(active.json()["context"]["book"]["can_open"])

    def test_missing_and_foreign_sessions_have_equivalent_no_leakage_responses(self):
        foreign = self.client.get(self.url(self.foreign))
        missing = self.client.get(
            "/api/v1/marginalia/sessions/"
            "00000000-0000-0000-0000-000000000000/"
        )

        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(foreign.json(), missing.json())

    def test_detail_has_canonical_book_context_and_bounded_session_shape(self):
        payload = self.client.get(self.url(self.active)).json()
        book = self.client.get(f"/api/v1/marginalia/books/{self.book.id}/").json()

        self.assertEqual(payload["context"]["book"], book)
        self.assertEqual(
            set(payload["session"]),
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
                "progress",
            },
        )
        self.assertIsNone(payload["session"]["progress"])
        self.assertNotIn("progression", payload["session"])
        self.assertNotIn("profile_version", payload["session"])

    def test_progress_annotation_count_and_activity_are_projected(self):
        session_at = timezone.now() - timedelta(hours=3)
        progress_at = timezone.now() - timedelta(hours=2)
        annotation_at = timezone.now() - timedelta(hours=1)
        cfi = "  epubcfi(/6/8!/4/2)  "
        label = "  Chapter 08 · 42%  "
        ReadingSession.objects.filter(pk=self.active.pk).update(updated_at=session_at)
        assign_session_progress(
            session=self.active,
            cfi=cfi,
            location_label=label,
            updated_at=progress_at,
        )
        annotation = Annotation.objects.create(
            session=self.active,
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/10)",
        )
        Annotation.objects.filter(pk=annotation.pk).update(updated_at=annotation_at)

        session = self.client.get(self.url(self.active)).json()["session"]

        self.assertEqual(session["annotation_count"], 1)
        self.assertEqual(session["progress"]["cfi"], cfi)
        self.assertEqual(session["progress"]["location_label"], label)
        self.assertEqual(
            parse_datetime(session["progress"]["updated_at"]),
            progress_at,
        )
        self.assertEqual(parse_datetime(session["last_activity_at"]), annotation_at)

    def test_active_metadata_patch_is_partial_and_returns_detail_shape(self):
        previous_update = timezone.now() - timedelta(days=1)
        ReadingSession.objects.filter(pk=self.active.pk).update(
            updated_at=previous_update
        )
        response = self.client.patch(
            self.url(self.active),
            {"name": "Renamed pass"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["session"]["name"], "Renamed pass")
        self.assertEqual(response.json()["session"]["notes"], "Original notes")
        self.assertGreater(
            parse_datetime(response.json()["session"]["updated_at"]),
            previous_update,
        )
        self.assertEqual(
            response.json()["session"]["last_activity_at"],
            response.json()["session"]["updated_at"],
        )
        self.assertEqual(response.json(), self.client.get(self.url(self.active)).json())

        notes = self.client.patch(
            self.url(self.active),
            {"notes": "Updated notes"},
            format="json",
        )
        self.assertEqual(notes.json()["session"]["notes"], "Updated notes")
        self.assertEqual(notes.json()["session"]["name"], "Renamed pass")

    def test_closed_metadata_patch_is_rejected_without_mutation(self):
        response = self.client.patch(
            self.url(self.closed),
            {"name": "Should not save", "notes": "Should not save"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.closed.refresh_from_db()
        self.assertEqual(self.closed.name, "Earlier pass")
        self.assertEqual(self.closed.notes, "")

    def test_unsupported_patch_fields_are_rejected(self):
        response = self.client.patch(
            self.url(self.active),
            {"status": "closed"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("status", response.json())

    def test_session_and_bearer_authentication_return_the_same_detail(self):
        session_payload = self.client.get(self.url(self.active)).json()
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        bearer = APIClient()

        response = bearer.get(
            self.url(self.active),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), session_payload)

        patched = bearer.patch(
            self.url(self.active),
            {"notes": "Bearer update"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(patched.json()["session"]["notes"], "Bearer update")

    def test_get_is_read_only(self):
        before = self.active.updated_at

        response = self.client.get(self.url(self.active))
        self.active.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.active.updated_at, before)

    def test_detail_query_and_serialization_are_bounded(self):
        with self.assertNumQueries(3):
            session = marginalia_session_for_user(
                user=self.user,
                session_id=self.active.id,
            ).get()
            book = marginalia_books_for_user(user=self.user).get(pk=self.book.id)
            payload = MarginaliaSessionDetailEnvelopeSerializer(
                {"context": {"book": book}, "session": session}
            ).data

        self.assertEqual(payload["session"]["id"], str(self.active.id))
