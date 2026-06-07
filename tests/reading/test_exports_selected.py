from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession, UserProfile
from accounts.services import get_or_create_profile
from reading.models import ReadingSession
from reading.services import create_annotation
from tests.reading.utils import IsolatedUserdataMixin
from tests.utils.books import create_file_backed_book


User = get_user_model()


class SelectedBookMarginaliaExportApiTests(IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pw")
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        self.other = User.objects.create_user(username="u2", password="pw")
        other_profile = get_or_create_profile(user=self.other)
        other_profile.role = UserProfile.ROLE_LIBRARIAN
        other_profile.save(update_fields=["role", "updated_at"])

        self.book = create_file_backed_book(title="Selected Export", epub_bytes=b"selected").book
        self.other_book = create_file_backed_book(title="Other Book", epub_bytes=b"other").book

        self.session1 = ReadingSession.objects.create(user=self.user, book=self.book, name="First")
        create_annotation(
            session=self.session1,
            anchor_kind="highlight",
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/2)",
            highlight_text="first quote",
        )
        self.session1.is_active = False
        self.session1.status = ReadingSession.STATUS_ARCHIVED
        self.session1.save(update_fields=["is_active", "status", "updated_at"])

        self.session2 = ReadingSession.objects.create(user=self.user, book=self.book, name="Second")
        create_annotation(
            session=self.session2,
            anchor_kind="bookmark",
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/4)",
        )
        self.session2.is_active = False
        self.session2.status = ReadingSession.STATUS_COMPLETED
        self.session2.completed_at = timezone.now()
        self.session2.save(update_fields=["is_active", "status", "completed_at", "updated_at"])

        self.other_user_session = ReadingSession.objects.create(user=self.other, book=self.book)
        self.other_book_session = ReadingSession.objects.create(user=self.user, book=self.other_book)

    def _url(self, *session_ids):
        base = f"/api/v1/reading/export/books/{self.book.id}/"
        if not session_ids:
            return base
        query = "&".join(f"session={session_id}" for session_id in session_ids)
        return f"{base}?{query}"

    def test_selected_book_export_includes_only_requested_sessions(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.get(self._url(self.session2.id)))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(
            r["Content-Disposition"],
            'attachment; filename="Selected-Export-selected-sessions-marginalia.json"',
        )
        self.assertEqual(
            r.data["scope"],
            {"type": "book", "book": r.data["books"][0]["source"], "session_filter": "selected"},
        )

        sessions = r.data["books"][0]["sessions"]
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["export_session_id"], "session-1")
        self.assertEqual(sessions[0]["name"], "Second")
        self.assertEqual(sessions[0]["annotations"][0]["motivation"], ["bookmarking"])
        self.assertNotIn("First", str(r.data))

    def test_selected_book_export_preserves_query_order(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.get(self._url(self.session2.id, self.session1.id)))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        names = [session["name"] for session in r.data["books"][0]["sessions"]]
        self.assertEqual(names, ["Second", "First"])

    def test_book_export_without_session_params_still_exports_all_sessions(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.get(self._url()))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["scope"]["type"], "book")
        self.assertNotIn("session_filter", r.data["scope"])
        names = {session["name"] for session in r.data["books"][0]["sessions"]}
        self.assertEqual(names, {"First", "Second"})

    def test_selected_book_export_returns_404_for_invalid_session_id(self):
        self.client.force_login(self.user)
        r = self.client.get(self._url("not-a-uuid"))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_selected_book_export_returns_404_for_missing_session_id(self):
        self.client.force_login(self.user)
        r = self.client.get(self._url(uuid4()))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_selected_book_export_returns_404_for_mismatched_book_session(self):
        self.client.force_login(self.user)
        r = self.client.get(self._url(self.other_book_session.id))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_selected_book_export_returns_404_for_another_users_session(self):
        self.client.force_login(self.user)
        r = self.client.get(self._url(self.other_user_session.id))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_selected_book_export_rejects_client_bearer_token(self):
        token = "spl_selected_export_token"
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )

        r = self.client.get(
            self._url(self.session1.id),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
