from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_datetime
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
from marginalia.exceptions import SessionClosedError
from marginalia.sessions.services import replace_progress
from marginalia.models import ReadingSession


User = get_user_model()


class MarginaliaProgressCloseAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.other = User.objects.create_user(username="other", password="testpass")
        self.group = LibraryGroup.objects.create(name="Readers")
        LibraryGroupMembership.objects.create(user=self.user, group=self.group)
        self.book = Book.objects.create(title="Lifecycle Book")
        BookGroupAssignment.objects.create(book=self.book, group=self.group)
        self.session = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Current pass",
            notes="Initial notes",
        )
        self.foreign = ReadingSession.objects.create(user=self.other, book=self.book)
        self.client.force_login(self.user)

    def progress_url(self, session=None):
        target = session or self.session
        return f"/api/v1/marginalia/sessions/{target.id}/progress/"

    def close_url(self, session=None):
        target = session or self.session
        return f"/api/v1/marginalia/sessions/{target.id}/close/"

    def test_progress_get_is_owner_readable_null_safe_and_read_only(self):
        before = self.session.updated_at

        absent = self.client.get(self.progress_url())
        self.session.refresh_from_db()

        self.assertEqual(absent.status_code, status.HTTP_200_OK)
        self.assertEqual(absent.json(), {"progress": None})
        self.assertEqual(self.session.updated_at, before)
        self.assertEqual(self.session.progress_cfi, "")

        cfi = "  epubcfi(/6/8!/4/2)  "
        label = "  Chapter 08 · 42% · The Blackstaff  "
        saved_at = timezone.now() - timedelta(hours=1)
        ReadingSession.objects.filter(pk=self.session.pk).update(
            progress_cfi=cfi,
            progress_location_label=label,
            progress_updated_at=saved_at,
        )
        LibraryGroupMembership.objects.filter(user=self.user, group=self.group).delete()

        present = self.client.get(self.progress_url())

        self.assertEqual(present.status_code, status.HTTP_200_OK)
        self.assertEqual(present.json()["progress"]["cfi"], cfi)
        self.assertEqual(present.json()["progress"]["location_label"], label)
        self.assertEqual(
            parse_datetime(present.json()["progress"]["updated_at"]),
            saved_at,
        )

    def test_closed_progress_and_bearer_reads_match_session_authentication(self):
        saved_at = timezone.now() - timedelta(minutes=5)
        ReadingSession.objects.filter(pk=self.session.pk).update(
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now(),
            progress_cfi="epubcfi(/6/10)",
            progress_updated_at=saved_at,
        )
        session_payload = self.client.get(self.progress_url()).json()
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        bearer = APIClient()

        response = bearer.get(
            self.progress_url(),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), session_payload)

    def test_bearer_authentication_can_write_progress_and_close(self):
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        bearer = APIClient()
        authorization = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        progress = bearer.put(
            self.progress_url(),
            {"cfi": "epubcfi(/6/8)"},
            format="json",
            **authorization,
        )
        closed = bearer.post(
            self.close_url(),
            {},
            format="json",
            **authorization,
        )

        self.assertEqual(progress.status_code, status.HTTP_200_OK)
        self.assertEqual(closed.status_code, status.HTTP_200_OK)
        self.assertEqual(closed.json()["session"]["status"], "closed")

    def test_progress_missing_and_foreign_sessions_do_not_leak(self):
        foreign = self.client.get(self.progress_url(self.foreign))
        missing = self.client.get(
            "/api/v1/marginalia/sessions/"
            "00000000-0000-0000-0000-000000000000/progress/"
        )

        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(foreign.json(), missing.json())

    def test_progress_put_atomically_replaces_location_with_server_timestamp(self):
        old_timestamp = timezone.now() - timedelta(days=1)
        ReadingSession.objects.filter(pk=self.session.pk).update(
            progress_cfi="epubcfi(/6/2)",
            progress_location_label="Old",
            progress_updated_at=old_timestamp,
        )
        before = timezone.now()
        cfi = "  epubcfi(/6/12!/4/2)  "
        label = "  Chapter 12 · 61%  "

        response = self.client.put(
            self.progress_url(),
            {"cfi": cfi, "location_label": label},
            format="json",
        )
        after = timezone.now()
        self.session.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.session.progress_cfi, cfi)
        self.assertEqual(self.session.progress_location_label, label)
        self.assertGreaterEqual(self.session.progress_updated_at, before)
        self.assertLessEqual(self.session.progress_updated_at, after)
        self.assertEqual(
            parse_datetime(response.json()["progress"]["updated_at"]),
            self.session.progress_updated_at,
        )

    def test_progress_put_accepts_omitted_or_blank_label(self):
        omitted = self.client.put(
            self.progress_url(),
            {"cfi": "epubcfi(/6/2)"},
            format="json",
        )
        blank = self.client.put(
            self.progress_url(),
            {"cfi": "epubcfi(/6/4)", "location_label": ""},
            format="json",
        )

        self.assertEqual(omitted.status_code, status.HTTP_200_OK)
        self.assertEqual(omitted.json()["progress"]["location_label"], "")
        self.assertEqual(blank.status_code, status.HTTP_200_OK)
        self.assertEqual(blank.json()["progress"]["location_label"], "")

    def test_progress_route_supports_only_get_and_put(self):
        patched = self.client.patch(
            self.progress_url(),
            {"cfi": "epubcfi(/6/2)"},
            format="json",
        )
        deleted = self.client.delete(self.progress_url())

        self.assertEqual(patched.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(deleted.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_invalid_progress_requests_leave_existing_progress_unchanged(self):
        saved_at = timezone.now() - timedelta(hours=2)
        original = ("epubcfi(/6/2)", "Original", saved_at)
        ReadingSession.objects.filter(pk=self.session.pk).update(
            progress_cfi=original[0],
            progress_location_label=original[1],
            progress_updated_at=original[2],
        )

        for payload in (
            {},
            {"cfi": ""},
            {"cfi": {"value": "epubcfi(/6/4)"}},
            {"cfi": "epubcfi(/6/4)", "unknown": True},
            {"cfi": "epubcfi(/6/4)", "location_label": None},
        ):
            with self.subTest(payload=payload):
                response = self.client.put(self.progress_url(), payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.session.refresh_from_db()
                self.assertEqual(
                    (
                        self.session.progress_cfi,
                        self.session.progress_location_label,
                        self.session.progress_updated_at,
                    ),
                    original,
                )

    def test_progress_write_rechecks_closed_state_and_book_authority(self):
        previous = ("epubcfi(/6/2)", "Original")
        ReadingSession.objects.filter(pk=self.session.pk).update(
            progress_cfi=previous[0],
            progress_location_label=previous[1],
            progress_updated_at=timezone.now(),
        )
        self.session.status = ReadingSession.STATUS_ACTIVE
        ReadingSession.objects.filter(pk=self.session.pk).update(
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now(),
        )

        with self.assertRaises(SessionClosedError):
            replace_progress(
                user=self.user,
                session_id=self.session.pk,
                cfi="epubcfi(/6/4)",
                location_label="New",
            )
        closed = self.client.put(
            self.progress_url(),
            {"cfi": "epubcfi(/6/4)"},
            format="json",
        )
        self.assertEqual(closed.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(closed.json()["error"]["code"], "SESSION_CLOSED")

        active = ReadingSession.objects.create(
            user=self.user,
            book=Book.objects.create(title="No access"),
        )
        denied = self.client.put(
            self.progress_url(active),
            {"cfi": "epubcfi(/6/4)"},
            format="json",
        )
        active.refresh_from_db()
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(active.progress_cfi, "")

    def test_close_updates_final_metadata_and_progress_atomically(self):
        before_count = ReadingSession.objects.count()

        response = self.client.post(
            self.close_url(),
            {
                "name": "Finished first read",
                "notes": "Final thoughts",
                "progress": {
                    "cfi": "  epubcfi(/6/42)  ",
                    "location_label": "  Chapter 42 · 100%  ",
                },
            },
            format="json",
        )
        self.session.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["session"]["status"], "closed")
        self.assertEqual(response.json()["session"]["name"], "Finished first read")
        self.assertEqual(response.json()["session"]["notes"], "Final thoughts")
        self.assertEqual(
            response.json()["session"]["progress"]["cfi"],
            "  epubcfi(/6/42)  ",
        )
        self.assertEqual(self.session.progress_updated_at, self.session.closed_at)
        self.assertEqual(ReadingSession.objects.count(), before_count)

    def test_close_without_progress_works_after_library_access_loss(self):
        LibraryGroupMembership.objects.filter(user=self.user, group=self.group).delete()

        response = self.client.post(
            self.close_url(),
            {"name": "Closed offline", "notes": "Kept history"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["session"]["status"], "closed")
        self.assertEqual(response.json()["session"]["name"], "Closed offline")

    def test_close_with_progress_requires_access_and_rolls_back_everything(self):
        LibraryGroupMembership.objects.filter(user=self.user, group=self.group).delete()

        response = self.client.post(
            self.close_url(),
            {
                "name": "Must not save",
                "notes": "Must not save",
                "progress": {"cfi": "epubcfi(/6/42)"},
            },
            format="json",
        )
        self.session.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.session.status, ReadingSession.STATUS_ACTIVE)
        self.assertEqual(self.session.name, "Current pass")
        self.assertEqual(self.session.notes, "Initial notes")
        self.assertEqual(self.session.progress_cfi, "")

    def test_close_retries_are_idempotent_only_when_values_match(self):
        payload = {
            "name": "Finished",
            "notes": "Done",
            "progress": {
                "cfi": "epubcfi(/6/42)",
                "location_label": "Chapter 42 · 100%",
            },
        }
        first = self.client.post(self.close_url(), payload, format="json")
        closed_at = first.json()["session"]["closed_at"]
        empty_retry = self.client.post(self.close_url(), {}, format="json")
        same_retry = self.client.post(self.close_url(), payload, format="json")
        changed_retry = self.client.post(
            self.close_url(),
            {"notes": "Changed"},
            format="json",
        )

        self.assertEqual(empty_retry.status_code, status.HTTP_200_OK)
        self.assertEqual(same_retry.status_code, status.HTTP_200_OK)
        self.assertEqual(same_retry.json()["session"]["closed_at"], closed_at)
        self.assertEqual(changed_retry.status_code, status.HTTP_409_CONFLICT)
        self.session.refresh_from_db()
        self.assertEqual(self.session.notes, "Done")

    def test_close_rejects_invalid_nested_fields_without_mutation(self):
        for payload in (
            {"status": "closed"},
            {"progress": {"cfi": "epubcfi(/6/4)", "unknown": True}},
            {"progress": {}},
        ):
            with self.subTest(payload=payload):
                response = self.client.post(self.close_url(), payload, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.session.refresh_from_db()
                self.assertEqual(self.session.status, ReadingSession.STATUS_ACTIVE)
                self.assertEqual(self.session.name, "Current pass")

    def test_close_missing_and_foreign_sessions_do_not_leak(self):
        foreign = self.client.post(self.close_url(self.foreign), {}, format="json")
        missing = self.client.post(
            "/api/v1/marginalia/sessions/"
            "00000000-0000-0000-0000-000000000000/close/",
            {},
            format="json",
        )

        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(foreign.json(), missing.json())
