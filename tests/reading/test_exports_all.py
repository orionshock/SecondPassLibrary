from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession, UserProfile
from accounts.services import get_or_create_profile
from reading.models import ReadingSession
from reading.services import create_annotation
from tests.reading.export_schema import assert_valid_marginalia_export
from tests.reading.utils import IsolatedUserdataMixin
from tests.utils.books import create_file_backed_book


User = get_user_model()


class AllMarginaliaExportApiTests(IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pw")
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        self.other = User.objects.create_user(username="u2", password="pw")

        self.book1 = create_file_backed_book(title="Alpha Book", epub_bytes=b"alpha").book
        self.book2 = create_file_backed_book(title="Beta Book", epub_bytes=b"beta").book
        self.no_session_book = create_file_backed_book(
            title="No Session Book", epub_bytes=b"none"
        ).book
        self.other_only_book = create_file_backed_book(
            title="Other User Book", epub_bytes=b"other"
        ).book

        self.session1 = ReadingSession.objects.create(
            user=self.user, book=self.book1, name="Alpha session"
        )
        self.session2 = ReadingSession.objects.create(
            user=self.user, book=self.book2, name="Beta session"
        )
        self.other_session = ReadingSession.objects.create(
            user=self.other, book=self.other_only_book, name="Other session"
        )

        create_annotation(
            session=self.session1,
            anchor_kind="highlight",
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/2)",
            highlight_text="alpha quote",
            highlight_color="yellow",
        )

    def _url(self):
        return "/api/v1/reading/export/"

    def test_all_export_requires_session_auth(self):
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_all_export_rejects_client_bearer_token(self):
        token = "spl_all_export_token"
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )

        r = self.client.get(self._url(), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_all_export_download_header_and_scope(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.get(self._url()))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        assert_valid_marginalia_export(r.data)
        self.assertEqual(r["Content-Type"], "application/json")
        self.assertEqual(
            r["Content-Disposition"],
            'attachment; filename="second-pass-marginalia.json"',
        )
        self.assertIn(b'\n  "type"', r.content)
        self.assertEqual(r.data["scope"], {"type": "all"})

    def test_all_export_includes_current_user_visible_books_with_sessions(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.get(self._url()))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        books = r.data["books"]
        titles = [book["title"] for book in books]
        self.assertEqual(titles, ["Alpha Book", "Beta Book"])
        self.assertNotIn("No Session Book", titles)
        self.assertNotIn("Other User Book", titles)

        self.assertEqual(books[0]["sessions"][0]["export_session_id"], "session-1")
        self.assertEqual(books[1]["sessions"][0]["export_session_id"], "session-1")
        self.assertEqual(books[0]["sessions"][0]["annotations"][0]["body"][0]["value"], "alpha quote")
        self.assertNotIn(str(self.other_session.id), str(r.data))

    def test_all_export_uses_nested_shape_without_spl_session_ids(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.get(self._url()))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        book = r.data["books"][0]
        session = book["sessions"][0]
        annotation = session["annotations"][0]
        self.assertIn("sessions", book)
        self.assertIn("annotations", session)
        self.assertNotIn("id", session)
        self.assertNotIn("id", annotation)
        self.assertNotIn("session", annotation)
