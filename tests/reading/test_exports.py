from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession, UserProfile
from accounts.services import get_or_create_profile
from reading.models import ReadingProgress, ReadingSession
from reading.services import create_annotation
from tests.reading.export_schema import assert_valid_marginalia_export
from tests.reading.utils import IsolatedUserdataMixin
from tests.utils.books import create_file_backed_book


User = get_user_model()


class ReadingExportApiTests(IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pw")
        profile = get_or_create_profile(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        self.other = User.objects.create_user(username="u2", password="pw")
        other_profile = get_or_create_profile(user=self.other)
        other_profile.role = UserProfile.ROLE_LIBRARIAN
        other_profile.save(update_fields=["role", "updated_at"])

        self.book = create_file_backed_book(title="Export Book", epub_bytes=b"export-book").book
        self.other_book = create_file_backed_book(title="Other Book", epub_bytes=b"other-book").book

        self.session1 = ReadingSession.objects.create(
            user=self.user, book=self.book, name="First pass", notes="Session notes"
        )
        self.other_user_session = ReadingSession.objects.create(user=self.other, book=self.book)
        self.other_book_session = ReadingSession.objects.create(user=self.user, book=self.other_book)

        ReadingProgress.objects.create(
            session=self.session1,
            current_location={
                "format": "epub",
                "href": "Text/ch1.xhtml",
                "cfi": "epubcfi(/6/2)",
            },
            progression=0.42,
        )

        self.highlight = create_annotation(
            session=self.session1,
            anchor_kind="highlight",
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/2[chapter]!/4/2)",
            highlight_text="selected text",
            quote_prefix="before ",
            quote_suffix=" after",
            highlight_color="green",
            comment_text="reader note",
        )
        self.deleted = create_annotation(
            session=self.session1,
            anchor_kind="highlight",
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/10)",
            highlight_text="deleted text",
            highlight_color="yellow",
        )
        self.deleted.is_deleted = True
        self.deleted.save(update_fields=["is_deleted", "updated_at"])

        self.session1.is_active = False
        self.session1.status = ReadingSession.STATUS_ARCHIVED
        self.session1.save(update_fields=["is_active", "status", "updated_at"])

        self.session2 = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Second pass",
        )
        self.bookmark = create_annotation(
            session=self.session2,
            anchor_kind="bookmark",
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/8)",
        )
        self.session2.is_active = False
        self.session2.status = ReadingSession.STATUS_COMPLETED
        self.session2.completed_at = timezone.now()
        self.session2.save(update_fields=["is_active", "status", "completed_at", "updated_at"])

    def _book_url(self):
        return f"/api/v1/reading/export/books/{self.book.id}/"

    def _session_url(self, session=None, book=None):
        session = session or self.session1
        book = book or self.book
        return f"/api/v1/reading/export/books/{book.id}/{session.id}/"

    def test_export_requires_session_auth(self):
        r = self.client.get(self._book_url())
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_rejects_client_bearer_token(self):
        token = "spl_export_token"
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )

        r = self.client.get(self._book_url(), HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_book_export_includes_only_request_user_sessions_for_book(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.get(self._book_url()))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        assert_valid_marginalia_export(r.data)
        self.assertEqual(r["Content-Type"], "application/json")
        self.assertEqual(
            r["Content-Disposition"],
            'attachment; filename="Export-Book-all-sessions-marginalia.json"',
        )
        self.assertIn(b'\n  "type"', r.content)
        self.assertIn(b'\n  "books"', r.content)

        data = r.data
        self.assertEqual(data["type"], "SecondPassMarginaliaExport")
        self.assertEqual(data["schema_version"], "0.1.0")
        self.assertIn("profile", data)
        self.assertIn("generated_at", data)
        self.assertIn("generator", data)
        self.assertEqual(data["scope"]["type"], "book")
        self.assertEqual(len(data["books"]), 1)

        book = data["books"][0]
        self.assertEqual(book["title"], "Export Book")
        self.assertTrue(book["source"].startswith("book:sha256:"))
        self.assertTrue(book["file_hash"].startswith("sha256:"))
        self.assertLess(list(book.keys()).index("source"), list(book.keys()).index("sessions"))
        self.assertLess(list(book.keys()).index("file_hash"), list(book.keys()).index("sessions"))
        sessions = book["sessions"]
        self.assertEqual([s["export_session_id"] for s in sessions], ["session-1", "session-2"])
        self.assertEqual({s["name"] for s in sessions}, {"First pass", "Second pass"})
        self.assertNotIn(str(self.other_user_session.id), str(data))
        self.assertNotIn(str(self.other_book_session.id), str(data))

    def test_session_export_includes_only_selected_session(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.get(self._session_url(self.session1)))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        assert_valid_marginalia_export(r.data)
        self.assertEqual(r["Content-Type"], "application/json")
        self.assertEqual(
            r["Content-Disposition"],
            'attachment; filename="Export-Book-First-pass-marginalia.json"',
        )

        sessions = r.data["books"][0]["sessions"]
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["export_session_id"], "session-1")
        self.assertEqual(sessions[0]["name"], "First pass")

    def test_session_export_filename_uses_generic_session_label_when_name_blank(self):
        self.client.force_login(self.user)
        blank_session = ReadingSession.objects.create(user=self.user, book=self.book)

        r = self.client.get(self._session_url(blank_session))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(
            r["Content-Disposition"],
            'attachment; filename="Export-Book-session-marginalia.json"',
        )
        self.assertNotIn(str(blank_session.id), r["Content-Disposition"])

    def test_cannot_export_another_users_session(self):
        self.client.force_login(self.user)
        r = self.client.get(self._session_url(self.other_user_session))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_mismatched_book_session_route_returns_404(self):
        self.client.force_login(self.user)
        r = self.client.get(self._session_url(self.session1, self.other_book))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_export_requires_current_book_visibility(self):
        reader = User.objects.create_user(username="reader", password="pw")
        hidden = create_file_backed_book(
            title="Hidden",
            epub_bytes=b"hidden-book",
            assign_public=False,
        ).book
        ReadingSession.objects.create(user=reader, book=hidden)

        self.client.force_login(reader)
        r = self.client.get(f"/api/v1/reading/export/books/{hidden.id}/")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_export_is_nested_and_omits_spl_session_and_annotation_ids(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.get(self._session_url(self.session1)))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        session = r.data["books"][0]["sessions"][0]
        annotation = session["annotations"][0]
        self.assertIn("progress", session)
        self.assertIn("annotations", session)
        self.assertNotIn("id", session)
        self.assertNotIn("session", annotation)
        self.assertNotIn("id", annotation)

    def test_export_contract_key_sets(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.get(self._session_url(self.session1)))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        top = r.data
        self.assertEqual(
            set(top.keys()),
            {"type", "schema_version", "profile", "generated_at", "generator", "scope", "books"},
        )
        book = top["books"][0]
        self.assertEqual(
            set(book.keys()),
            {
                "title",
                "subtitle",
                "authors",
                "series",
                "series_index",
                "language",
                "isbn",
                "epub_unique_identifier",
                "source",
                "file_hash",
                "sessions",
            },
        )
        session = book["sessions"][0]
        self.assertEqual(
            set(session.keys()),
            {
                "export_session_id",
                "name",
                "status",
                "started_at",
                "completed_at",
                "created_at",
                "updated_at",
                "notes",
                "progress",
                "annotations",
            },
        )
        self.assertEqual(
            set(session["progress"].keys()),
            {"current_location", "progression", "profile_version", "updated_at"},
        )
        self.assertEqual(
            set(session["annotations"][0].keys()),
            {"motivation", "target", "body", "is_deleted", "created_at", "updated_at"},
        )

    def test_text_quote_selector_context_exports_when_present(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.get(self._session_url(self.session1)))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        selector = r.data["books"][0]["sessions"][0]["annotations"][0]["target"]["selector"]
        self.assertIsInstance(selector, list)
        self.assertEqual(selector[0]["type"], "FragmentSelector")
        self.assertNotIn("conformsTo", selector[0])
        self.assertEqual(selector[1]["type"], "TextQuoteSelector")
        self.assertEqual(selector[1]["exact"], "selected text")
        self.assertEqual(selector[1]["prefix"], "before ")
        self.assertEqual(selector[1]["suffix"], " after")

    def test_deleted_annotations_excluded(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.get(self._session_url(self.session1)))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        annotations = r.data["books"][0]["sessions"][0]["annotations"]
        self.assertEqual(len(annotations), 1)
        self.assertNotIn("deleted text", str(annotations))
