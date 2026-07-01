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
from tests.reading.imports.helpers import MarginaliaImportFixtureMixin
from tests.utils.books import create_file_backed_book


User = get_user_model()

class MarginaliaImportPreviewApiTests(MarginaliaImportFixtureMixin, IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.set_up_import_books()

    def _url(self):
        return "/api/v1/reading/import/preview/"

    def test_preview_creates_staged_file_with_user_and_payload(self):
        self.client.force_login(self.user)
        payload = self.preview_marginalia_payload()
        r = cast(Any, self.post_preview_payload(payload))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        path = Path(settings.IMPORTS_DIR) / "staged" / f"{r.data['import_token']}.json"
        self.assertTrue(path.exists())
        staged = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(staged["user_id"], cast(Any, self.user).id)
        self.assertEqual(staged["payload"], payload)

    def test_unmatched_download_returns_only_unmatched_books(self):
        self.client.force_login(self.user)
        payload = self.preview_marginalia_payload()
        unmatched = self.preview_marginalia_payload(file_hash="0" * 64, title="Missing Book", authors=["Nobody"])["books"][0]
        payload["books"].append(unmatched)

        preview = cast(Any, self.post_preview_payload(payload))
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
        preview = cast(Any, self.post_preview_payload(self.preview_marginalia_payload(file_hash="0" * 64, title="Missing Book")))

        self.client.force_login(other)
        r = self.client.get(preview.data["unmatched_download_url"])

        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
