from __future__ import annotations

import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.utils.dateparse import parse_datetime
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

    def test_apply_requires_login(self):
        r = self._post_payload(self._payload())
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_apply_rejects_client_bearer_token(self):
        token = "spl_import_apply_token"
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

    def test_apply_invalid_json_returns_400_and_no_writes(self):
        self.client.force_login(self.user)
        r = cast(Any, self._post_payload(b"{not-json"))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["applied"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_apply_schema_invalid_returns_400_and_no_writes(self):
        self.client.force_login(self.user)
        payload = self._payload()
        del payload["books"][0]["sessions"][0]["annotations"][0]["target"]
        r = cast(Any, self._post_payload(payload))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["applied"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_apply_with_valid_token_imports_and_consumes_staged_file(self):
        payload = self._payload()
        token = stage_marginalia_import(user=self.user, payload=payload)
        path = staged_import_path(token)

        self.client.force_login(self.user)
        r = cast(Any, self._post_token(token))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["summary"]["sessions_created"], 1)
        self.assertEqual(ReadingSession.objects.count(), 1)
        self.assertFalse(path.exists())

    def test_apply_with_another_users_token_returns_400_and_no_writes(self):
        other = User.objects.create_user(username="other", password="pw")
        token = stage_marginalia_import(user=other, payload=self._payload())

        self.client.force_login(self.user)
        r = cast(Any, self._post_token(token))

        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["applied"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_apply_with_invalid_or_traversal_token_returns_400_and_no_writes(self):
        self.client.force_login(self.user)
        for token in ["../bad", "bad.json", "short"]:
            r = cast(Any, self._post_token(token))
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertFalse(r.data["applied"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_apply_with_missing_or_expired_token_returns_400_and_no_writes(self):
        token = stage_marginalia_import(user=self.user, payload=self._payload())
        path = staged_import_path(token)
        staged = json.loads(path.read_text(encoding="utf-8"))
        staged["staged_at"] = (timezone.now() - timedelta(hours=25)).isoformat()
        path.write_text(json.dumps(staged), encoding="utf-8")

        self.client.force_login(self.user)
        expired = cast(Any, self._post_token(token))
        missing = cast(Any, self._post_token("A" * 40))

        self.assertEqual(expired.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Import preview expired", expired.data["errors"][0]["message"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)
