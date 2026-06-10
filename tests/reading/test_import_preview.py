from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession
from reading.models import Annotation, ReadingSession
from tests.reading.utils import IsolatedUserdataMixin
from tests.utils.books import create_file_backed_book


User = get_user_model()


class MarginaliaImportPreviewApiTests(IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="pw")
        self.visible = create_file_backed_book(
            title="Visible Match",
            epub_bytes=b"visible-match",
        ).book
        self.visible.authors.create(name="Author One")
        self.hidden = create_file_backed_book(
            title="Hidden Match",
            epub_bytes=b"hidden-match",
            assign_public=False,
        ).book

    def _url(self):
        return "/api/v1/reading/import/preview/"

    def _upload(self, payload):
        if isinstance(payload, bytes):
            content = payload
        else:
            content = json.dumps(payload).encode("utf-8")
        return SimpleUploadedFile("marginalia.json", content, content_type="application/json")

    def _post_payload(self, payload):
        return self.client.post(self._url(), {"file": self._upload(payload)}, format="multipart")

    def _payload(self, *, file_hash=None, title="Visible Match", authors=None, session_status="completed"):
        checksum = file_hash or self.visible.file.checksum
        authors = ["Author One"] if authors is None else authors
        return {
            "type": "SecondPassMarginaliaExport",
            "schema_version": "0.1.0",
            "profile": "https://secondpasslibrary.local/specs/reading-session-annotations/0.1.0",
            "generated_at": "2026-06-07T12:00:00+00:00",
            "generator": "Second Pass Library",
            "scope": {"type": "book", "book": f"book:sha256:{checksum}"},
            "books": [
                {
                    "title": title,
                    "subtitle": "",
                    "authors": authors,
                    "series": "",
                    "series_index": None,
                    "language": "",
                    "isbn": "",
                    "epub_unique_identifier": "",
                    "source": f"book:sha256:{checksum}",
                    "file_hash": f"sha256:{checksum}",
                    "sessions": [
                        {
                            "export_session_id": "session-1",
                            "name": "Imported session",
                            "status": session_status,
                            "started_at": "2026-06-01T12:00:00+00:00",
                            "completed_at": "2026-06-02T12:00:00+00:00",
                            "created_at": "2026-06-01T12:00:00+00:00",
                            "updated_at": "2026-06-02T12:00:00+00:00",
                            "notes": "",
                            "progress": None,
                            "annotations": [
                                self._bookmark(),
                                self._highlight("plain highlight", False),
                                self._highlight("commented highlight", True),
                            ],
                        }
                    ],
                }
            ],
        }

    def _bookmark(self):
        return {
            "motivation": ["bookmarking"],
            "target": {"selector": {"type": "FragmentSelector", "value": "epubcfi(/6/2)"}},
            "body": [],
            "is_deleted": False,
            "created_at": "2026-06-01T12:00:00+00:00",
            "updated_at": "2026-06-01T12:00:00+00:00",
        }

    def _highlight(self, text, commented):
        body = [
            {
                "type": "TextualBody",
                "purpose": "describing",
                "value": text,
                "color": "yellow",
            }
        ]
        motivations = ["highlighting"]
        if commented:
            motivations.append("commenting")
            body.append({"type": "TextualBody", "purpose": "commenting", "value": "note"})
        return {
            "motivation": motivations,
            "target": {"selector": {"type": "FragmentSelector", "value": "epubcfi(/6/4)"}},
            "body": body,
            "is_deleted": False,
            "created_at": "2026-06-01T12:00:00+00:00",
            "updated_at": "2026-06-01T12:00:00+00:00",
        }

    def test_preview_requires_login(self):
        r = self._post_payload(self._payload())
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_preview_rejects_client_bearer_token(self):
        token = "spl_import_preview_token"
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        r = self.client.post(
            self._url(),
            {"file": self._upload(self._payload())},
            format="multipart",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_json_returns_400(self):
        self.client.force_login(self.user)
        r = cast(Any, self._post_payload(b"{not-json"))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["valid"])
        self.assertIn("errors", r.data)

    def test_schema_invalid_export_returns_readable_errors(self):
        self.client.force_login(self.user)
        payload = self._payload()
        del payload["books"][0]["sessions"][0]["annotations"][0]["target"]

        r = cast(Any, self._post_payload(payload))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["valid"])
        self.assertIn("$.books[0].sessions[0].annotations[0]", r.data["errors"][0]["path"])
        self.assertIn("target", r.data["errors"][0]["message"])

    def test_valid_export_returns_summary_counts_and_file_hash_match(self):
        self.client.force_login(self.user)
        r = cast(Any, self._post_payload(self._payload()))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["valid"])
        self.assertRegex(r.data["import_token"], r"^[A-Za-z0-9_-]{32,128}$")
        self.assertTrue(r.data["can_apply"])
        self.assertEqual(r.data["schema_version"], "0.1.0")
        self.assertEqual(r.data["scope"]["type"], "book")
        self.assertEqual(r.data["summary"], {"books": 1, "sessions": 1, "annotations": 3})
        self.assertEqual(
            r.data["apply_plan"],
            {
                "matched_books": 1,
                "skipped_books": 0,
                "sessions_to_create": 1,
                "annotations_to_create": 3,
                "bookmarks_to_create": 1,
                "highlights_to_create": 2,
                "commented_highlights_to_create": 1,
                "active_sessions_will_import_as_historical": 0,
                "possible_duplicate_sessions": 0,
            },
        )

        book = r.data["books"][0]
        self.assertEqual(book["session_count"], 1)
        self.assertEqual(book["annotation_count"], 3)
        self.assertEqual(book["bookmark_count"], 1)
        self.assertEqual(book["highlight_count"], 2)
        self.assertEqual(book["commented_highlight_count"], 1)
        self.assertEqual(book["match"]["status"], "matched")
        self.assertEqual(book["match"]["method"], "file_hash")
        self.assertEqual(book["match"]["book_title"], "Visible Match")
        self.assertTrue(book["will_import"])
        self.assertIsNone(book["skip_reason"])
        self.assertEqual(len(book["sessions"]), 1)
        session = book["sessions"][0]
        self.assertEqual(session["export_session_id"], "session-1")
        self.assertEqual(session["name"], "Imported session")
        self.assertEqual(session["notes"], "")
        self.assertEqual(session["status"], "completed")
        self.assertEqual(session["annotation_count"], 3)
        self.assertEqual(session["bookmark_count"], 1)
        self.assertEqual(session["highlight_count"], 2)
        self.assertEqual(session["commented_highlight_count"], 1)
        self.assertTrue(session["will_import"])
        self.assertFalse(session["active_will_import_as_historical"])

    def test_preview_creates_staged_file_with_user_and_payload(self):
        self.client.force_login(self.user)
        payload = self._payload()
        r = cast(Any, self._post_payload(payload))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        path = Path(settings.IMPORTS_DIR) / "staged" / f"{r.data['import_token']}.json"
        self.assertTrue(path.exists())
        staged = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(staged["user_id"], cast(Any, self.user).id)
        self.assertEqual(staged["payload"], payload)

    def test_preview_does_not_create_sessions_or_annotations(self):
        self.client.force_login(self.user)
        before_sessions = ReadingSession.objects.count()
        before_annotations = Annotation.objects.count()

        r = self._post_payload(self._payload())

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(ReadingSession.objects.count(), before_sessions)
        self.assertEqual(Annotation.objects.count(), before_annotations)

    def test_matching_only_uses_visible_books(self):
        self.client.force_login(self.user)
        r = cast(Any, self._post_payload(self._payload(file_hash=self.hidden.file.checksum, title="Hidden Match")))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["books"][0]["match"]["status"], "unmatched")
        self.assertIsNone(r.data["books"][0]["match"]["book_title"])

    def test_unmatched_book_reported(self):
        self.client.force_login(self.user)
        payload = self._payload(file_hash="0" * 64, title="Missing Book", authors=["Nobody"])

        r = cast(Any, self._post_payload(payload))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertFalse(r.data["can_apply"])
        self.assertEqual(r.data["apply_plan"]["matched_books"], 0)
        self.assertEqual(r.data["apply_plan"]["skipped_books"], 1)
        self.assertEqual(r.data["apply_plan"]["sessions_to_create"], 0)
        self.assertEqual(r.data["books"][0]["match"]["status"], "unmatched")
        self.assertFalse(r.data["books"][0]["will_import"])
        self.assertEqual(r.data["books"][0]["skip_reason"], "unmatched_book")
        self.assertFalse(r.data["books"][0]["sessions"][0]["will_import"])
        self.assertIn("No visible local book matched", r.data["books"][0]["warning"])
        self.assertIn("It will be skipped.", r.data["warnings"][0])

    def test_title_author_match_when_hash_does_not_match(self):
        self.client.force_login(self.user)
        payload = self._payload(file_hash="1" * 64)
        payload["books"][0]["source"] = "book:sha256:" + ("1" * 64)
        payload["books"][0]["file_hash"] = "sha256:" + ("1" * 64)

        r = cast(Any, self._post_payload(payload))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["books"][0]["match"]["method"], "title_author")

    def test_active_exported_sessions_warn_but_can_apply(self):
        self.client.force_login(self.user)
        payload = self._payload(session_status="active")

        r = cast(Any, self._post_payload(payload))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["can_apply"])
        self.assertEqual(r.data["apply_plan"]["active_sessions_will_import_as_historical"], 1)
        self.assertEqual(r.data["books"][0]["active_sessions_will_import_as_historical"], 1)
        self.assertIn("not active sessions", r.data["warnings"][0])

    def test_possible_duplicate_warning_does_not_block_apply(self):
        session = ReadingSession.objects.create(
            user=self.user,
            book=self.visible,
            name="Imported session",
            status=ReadingSession.STATUS_COMPLETED,
            completed_at=parse_datetime("2026-06-02T12:00:00+00:00"),
            is_active=False,
        )
        started_at = parse_datetime("2026-06-01T12:00:00+00:00")
        assert started_at is not None
        session.started_at = started_at
        session.save(update_fields=["started_at", "updated_at"])

        self.client.force_login(self.user)
        r = cast(Any, self._post_payload(self._payload()))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data["can_apply"])
        self.assertEqual(r.data["apply_plan"]["possible_duplicate_sessions"], 1)
        self.assertEqual(r.data["books"][0]["possible_duplicate_sessions"], 1)
        self.assertIn("Possible duplicate sessions", r.data["warnings"][0])
