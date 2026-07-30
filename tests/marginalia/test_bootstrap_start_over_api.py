from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.client_api import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from core.models import IdempotencyRecord
from library.models import (
    Book,
    BookGroupAssignment,
    LibraryGroup,
    LibraryGroupMembership,
)
from marginalia.models import Annotation, ReadingSession
from marginalia.sessions.idempotency import normalized_request_hash


User = get_user_model()


class MarginaliaStartOverBootstrapTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.group = LibraryGroup.objects.create(name="Readers")
        LibraryGroupMembership.objects.create(user=self.user, group=self.group)
        self.book = Book.objects.create(title="Start Over Book")
        BookGroupAssignment.objects.create(book=self.book, group=self.group)
        self.active = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Current pass",
            notes="Current notes",
            progress_cfi="epubcfi(/6/8)",
            progress_location_label="Chapter 08",
            progress_updated_at=timezone.now(),
        )
        self.annotation = Annotation.objects.create(
            session=self.active,
            client_id="keep-me",
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/4)",
        )
        self.client.force_login(self.user)
        self.url = f"/api/v1/marginalia/books/{self.book.id}/start-over/"

    def post(self, payload=None, key="start-over-1"):
        headers = {"HTTP_IDEMPOTENCY_KEY": key} if key is not None else {}
        return self.client.post(
            self.url,
            payload or {},
            format="json",
            **headers,
        )

    def test_start_over_atomically_finalizes_old_and_creates_blank_active_session(self):
        before = timezone.now()
        payload = {
            "name": "Finished first read",
            "notes": "Final thoughts",
            "progress": {
                "cfi": "  epubcfi(/6/42)  ",
                "location_label": "  Chapter 42 · 100%  ",
            },
        }

        response = self.post(payload)
        self.active.refresh_from_db()
        new_session = ReadingSession.objects.get(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_ACTIVE,
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.json()["created"])
        self.assertEqual(response.json()["session"]["id"], str(new_session.id))
        self.assertEqual((new_session.name, new_session.notes), ("", ""))
        self.assertEqual(new_session.progress_cfi, "")
        self.assertIsNone(new_session.progress_updated_at)
        self.assertEqual(response.json()["annotations"], [])
        self.assertEqual(self.active.status, ReadingSession.STATUS_CLOSED)
        self.assertEqual((self.active.name, self.active.notes), (payload["name"], payload["notes"]))
        self.assertEqual(self.active.progress_cfi, payload["progress"]["cfi"])
        self.assertEqual(
            self.active.progress_location_label,
            payload["progress"]["location_label"],
        )
        self.assertGreaterEqual(self.active.progress_updated_at, before)
        self.assertEqual(self.active.progress_updated_at, self.active.closed_at)
        self.assertTrue(Annotation.objects.filter(pk=self.annotation.pk, session=self.active).exists())
        self.assertEqual(response.json()["closed_sessions"]["results"][0]["id"], str(self.active.id))

    def test_start_over_replay_returns_stored_response_without_another_session(self):
        first = self.post()
        second = self.post()

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(ReadingSession.objects.filter(user=self.user, book=self.book).count(), 2)
        self.assertEqual(
            IdempotencyRecord.objects.filter(user=self.user, key="start-over-1").count(),
            1,
        )

    def test_same_key_with_different_normalized_request_conflicts(self):
        first = self.post({"notes": "First"})
        replacement_id = first.json()["session"]["id"]
        second = self.post({"notes": "Different"})

        self.assertEqual(second.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(second.json()["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(
            str(ReadingSession.objects.get(status=ReadingSession.STATUS_ACTIVE).id),
            replacement_id,
        )
        self.assertEqual(ReadingSession.objects.filter(user=self.user, book=self.book).count(), 2)

    def test_processing_duplicate_is_bounded_and_does_not_change_lifecycle(self):
        IdempotencyRecord.objects.create(
            user=self.user,
            key="start-over-1",
            method="POST",
            path=self.url,
            request_hash=normalized_request_hash(
                method="POST",
                path=self.url,
                data={},
            ),
        )
        before = (self.active.status, self.active.closed_at)

        response = self.post()
        self.active.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual((self.active.status, self.active.closed_at), before)
        self.assertEqual(ReadingSession.objects.filter(user=self.user, book=self.book).count(), 1)

    def test_missing_or_invalid_idempotency_key_is_rejected_without_changes(self):
        for key in (None, "   ", "x" * 129, "bad\nkey"):
            with self.subTest(key=key):
                response = self.post(key=key)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.assertEqual(ReadingSession.objects.filter(user=self.user, book=self.book).count(), 1)
        self.assertEqual(IdempotencyRecord.objects.filter(user=self.user).count(), 0)

    def test_no_active_session_creates_blank_session_only_without_finalization(self):
        self.active.delete()

        rejected = self.post({"notes": "Nothing to finalize"}, key="with-final")
        created = self.post({}, key="without-final")

        self.assertEqual(rejected.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(created.json()["session"]["name"], "")
        self.assertIsNone(created.json()["session"]["progress"])
        self.assertEqual(ReadingSession.objects.filter(user=self.user, book=self.book).count(), 1)
        self.assertFalse(IdempotencyRecord.objects.filter(user=self.user, key="with-final").exists())

    def test_validation_and_lost_authority_leave_lifecycle_unchanged(self):
        invalid = self.post({"progress": {"location_label": "Missing CFI"}}, key="invalid")
        LibraryGroupMembership.objects.filter(user=self.user, group=self.group).delete()
        denied = self.post({}, key="denied")
        self.active.refresh_from_db()

        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.active.status, ReadingSession.STATUS_ACTIVE)
        self.assertIsNone(self.active.closed_at)
        self.assertEqual(ReadingSession.objects.filter(user=self.user, book=self.book).count(), 1)
        self.assertFalse(IdempotencyRecord.objects.filter(user=self.user, key="denied").exists())

    def test_unknown_fields_are_rejected_at_both_levels(self):
        top = self.post({"unknown": True}, key="top")
        nested = self.post(
            {"progress": {"cfi": "epubcfi(/6/2)", "unknown": True}},
            key="nested",
        )

        self.assertEqual(top.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(nested.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ReadingSession.objects.filter(user=self.user, book=self.book).count(), 1)

    def test_bearer_authentication_can_start_over(self):
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        self.client.logout()

        response = self.client.post(
            self.url,
            {},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_IDEMPOTENCY_KEY="bearer-start-over",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.json()["created"])
