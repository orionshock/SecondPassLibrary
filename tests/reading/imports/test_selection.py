from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, cast
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession
from reading.import_apply_services import apply_marginalia_import
from reading.import_services import preview_marginalia_import
from reading.import_staging import stage_marginalia_import, staged_import_path
from reading.models import Annotation, ReadingSession
from tests.reading.utils import IsolatedUserdataMixin
from tests.utils.books import create_file_backed_book


User = get_user_model()

class MarginaliaImportApplyApiTests(IsolatedUserdataMixin, APITestCase):
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
        return "/api/v1/reading/import/apply/"

    def _upload(self, payload):
        if isinstance(payload, bytes):
            content = payload
        else:
            content = json.dumps(payload).encode("utf-8")
        return SimpleUploadedFile("marginalia.json", content, content_type="application/json")

    def _post_payload(self, payload, *, selection=None):
        data: dict[str, Any] = {"file": self._upload(payload)}
        if selection is not None:
            data["selection"] = selection if isinstance(selection, str) else json.dumps(selection)
        return self.client.post(self._url(), data, format="multipart")

    def _post_token(self, token, *, selection=None):
        data: dict[str, Any] = {"import_token": token}
        if selection is not None:
            data["selection"] = selection if isinstance(selection, str) else json.dumps(selection)
        return self.client.post(self._url(), data, format="multipart")

    def _payload(self, *, checksum=None, title="Visible Match", status_value="completed"):
        checksum = checksum or self.visible.file.checksum
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
                    "authors": ["Author One"],
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
                            "status": status_value,
                            "started_at": "2026-06-01T12:00:00+00:00",
                            "completed_at": None if status_value == "active" else "2026-06-02T12:00:00+00:00",
                            "created_at": "2026-06-01T12:00:00+00:00",
                            "updated_at": "2026-06-03T12:00:00+00:00",
                            "notes": "session notes",
                            "progress": None,
                            "annotations": [
                                self._bookmark(),
                                self._highlight(),
                                self._commented_highlight(),
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

    def _highlight(self):
        return {
            "motivation": ["highlighting"],
            "target": {
                "selector": [
                    {"type": "FragmentSelector", "value": "epubcfi(/6/4)"},
                    {
                        "type": "TextQuoteSelector",
                        "exact": "plain highlight",
                        "prefix": "before ",
                        "suffix": " after",
                    },
                ]
            },
            "body": [
                {
                    "type": "TextualBody",
                    "purpose": "describing",
                    "value": "plain highlight",
                    "color": "green",
                }
            ],
            "is_deleted": False,
            "created_at": "2026-06-01T12:00:00+00:00",
            "updated_at": "2026-06-01T12:00:00+00:00",
        }

    def _commented_highlight(self):
        return {
            "motivation": ["highlighting", "commenting"],
            "target": {"selector": {"type": "FragmentSelector", "value": "epubcfi(/6/8)"}},
            "body": [
                {
                    "type": "TextualBody",
                    "purpose": "describing",
                    "value": "commented highlight",
                    "color": "yellow",
                },
                {"type": "TextualBody", "purpose": "commenting", "value": "note"},
            ],
            "is_deleted": False,
            "created_at": "2026-06-01T12:00:00+00:00",
            "updated_at": "2026-06-01T12:00:00+00:00",
        }

    def test_apply_with_selection_imports_only_selected_sessions_with_overrides(self):
        payload = self._payload()
        second = dict(payload["books"][0]["sessions"][0])
        second["export_session_id"] = "session-2"
        second["name"] = "Skipped"
        payload["books"][0]["sessions"].append(second)
        selection = {
            "books": [
                {
                    "source": payload["books"][0]["source"],
                    "sessions": [
                        {
                            "export_session_id": "session-1",
                            "selected": True,
                            "name": "  Custom import name  ",
                            "notes": "  Custom notes  ",
                        },
                        {"export_session_id": "session-2", "selected": False},
                    ],
                }
            ]
        }

        self.client.force_login(self.user)
        r = cast(Any, self._post_payload(payload, selection=selection))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["summary"]["sessions_created"], 1)
        session = ReadingSession.objects.get()
        self.assertEqual(session.name, "Custom import name")
        self.assertEqual(session.notes, "Custom notes")
        self.assertEqual(Annotation.objects.count(), 3)

    def test_apply_malformed_selection_returns_400_and_no_writes(self):
        self.client.force_login(self.user)
        r = cast(Any, self._post_payload(self._payload(), selection="{not-json"))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["applied"])
        self.assertIn("selection", r.data["errors"][0]["path"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_apply_nonexistent_selected_session_returns_400_and_no_writes(self):
        payload = self._payload()
        selection = {
            "books": [
                {
                    "source": payload["books"][0]["source"],
                    "sessions": [{"export_session_id": "missing", "selected": True}],
                }
            ]
        }

        self.client.force_login(self.user)
        r = cast(Any, self._post_payload(payload, selection=selection))

        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["applied"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_apply_selected_unmatched_book_returns_400_and_no_writes(self):
        payload = self._payload(checksum="0" * 64, title="Missing Book")
        selection = {
            "books": [
                {
                    "source": payload["books"][0]["source"],
                    "sessions": [{"export_session_id": "session-1", "selected": True}],
                }
            ]
        }

        self.client.force_login(self.user)
        r = cast(Any, self._post_payload(payload, selection=selection))

        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["applied"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)
