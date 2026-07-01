from __future__ import annotations

from copy import deepcopy
from typing import Any, cast
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.utils import timezone
from jsonschema import Draft202012Validator
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession, UserProfile
from accounts.services import get_or_create_profile
from reading.models import ReadingProgress, ReadingSession
from reading.services import create_annotation
from tests.reading.exports.schema_assertions import (
    assert_valid_marginalia_export,
    load_marginalia_export_schema,
    SchemaValidationError,
)
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
        return "/api/v1/reading/export/"

    def _session_url(self, session=None, book=None):
        session = session or self.session1
        book = book or self.book
        return f"/api/v1/reading/export/books/{book.id}/{session.id}/"

    def _post_book(self, book=None, sessions="all"):
        book = book or self.book
        return self.client.post(
            self._book_url(),
            {"books": [{"book_id": str(book.id), "sessions": sessions}]},
            format="json",
        )

    def test_export_is_nested_and_omits_spl_session_and_annotation_ids(self):
        self.client.force_login(self.user)
        r = cast(Any, self._post_book(sessions=[str(self.session1.id)]))
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
        r = cast(Any, self._post_book(sessions=[str(self.session1.id)]))
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
        r = cast(Any, self._post_book(sessions=[str(self.session1.id)]))
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
        r = cast(Any, self._post_book(sessions=[str(self.session1.id)]))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

        annotations = r.data["books"][0]["sessions"][0]["annotations"]
        self.assertEqual(len(annotations), 1)
        self.assertNotIn("deleted text", str(annotations))


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

    def _url(self):
        return "/api/v1/reading/export/"

    def _body(self, *books):
        return {"books": list(books)}

    def test_export_schema_rejects_local_session_and_annotation_ids(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.post(
            self._url(),
            self._body({"book_id": str(self.book.id), "sessions": [str(self.session1.id)]}),
            format="json",
        ))
        payload = deepcopy(r.data)
        session = payload["books"][0]["sessions"][0]
        annotation = session["annotations"][0]
        session["id"] = str(self.session1.id)
        annotation["database_id"] = "local-annotation-id"

        with self.assertRaises(SchemaValidationError):
            Draft202012Validator(load_marginalia_export_schema()).validate(payload)
