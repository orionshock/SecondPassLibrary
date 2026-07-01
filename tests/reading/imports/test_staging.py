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

    def test_unmatched_download_returns_only_unmatched_books(self):
        self.client.force_login(self.user)
        payload = self._payload()
        unmatched = self._payload(file_hash="0" * 64, title="Missing Book", authors=["Nobody"])["books"][0]
        payload["books"].append(unmatched)

        preview = cast(Any, self._post_payload(payload))
        r = cast(Any, self.client.get(
            preview.data["unmatched_download_url"],
            HTTP_ACCEPT="text/html,application/xhtml+xml,*/*",
        ))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r["Content-Type"].startswith("application/json"))
        self.assertEqual(
            r["Content-Disposition"],
            'attachment; filename="second-pass-unmatched-marginalia.json"',
        )
        self.assertFalse(r.content.lstrip().startswith(b"<!DOCTYPE html>"))
        parsed = json.loads(r.content.decode("utf-8"))
        self.assertEqual(parsed["type"], "SecondPassMarginaliaExport")
        self.assertEqual(parsed["schema_version"], "0.1.0")
        self.assertEqual(parsed["scope"]["type"], "selected")
        self.assertEqual(parsed["scope"]["books"][0]["session_filter"], "all")
        self.assertEqual([book["title"] for book in parsed["books"]], ["Missing Book"])
        self.assertNotIn("Visible Match", str(parsed))

    def test_unmatched_download_requires_current_user_staged_preview(self):
        self.client.force_login(self.user)
        other = User.objects.create_user(username="other", password="pw")
        preview = cast(Any, self._post_payload(self._payload(file_hash="0" * 64, title="Missing Book")))

        self.client.force_login(other)
        r = self.client.get(preview.data["unmatched_download_url"])

        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
