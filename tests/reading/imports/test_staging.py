from __future__ import annotations

import json
from datetime import timedelta
from io import StringIO
from pathlib import Path
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from reading.imports.staging import cleanup_staged_imports
from tests.testenv.filesystem import IsolatedUserdataMixin
from tests.reading.imports.helpers import MarginaliaImportFixtureMixin


User = get_user_model()


class MarginaliaImportStagingCleanupTests(IsolatedUserdataMixin, TestCase):
    def _staging_dir(self) -> Path:
        path = Path(settings.IMPORTS_DIR) / "staged"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_staged_file(self, token: str, *, hours_old: int) -> Path:
        path = self._staging_dir() / f"{token}.json"
        path.write_text(
            json.dumps(
                {
                    "staged_at": (
                        timezone.now() - timedelta(hours=hours_old)
                    ).isoformat(),
                    "user_id": 1,
                    "payload": {"books": []},
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_expired_staged_import_file_is_removed_by_cleanup(self):
        expired = self._write_staged_file("A" * 40, hours_old=25)

        removed = cleanup_staged_imports()

        self.assertEqual(removed, 1)
        self.assertFalse(expired.exists())

    def test_non_expired_staged_import_file_is_preserved(self):
        current = self._write_staged_file("B" * 40, hours_old=1)

        removed = cleanup_staged_imports()

        self.assertEqual(removed, 0)
        self.assertTrue(current.exists())

    def test_unrelated_file_in_staging_directory_is_preserved(self):
        unrelated = self._staging_dir() / "notes.json"
        unrelated.write_text("not staged marginalia", encoding="utf-8")

        removed = cleanup_staged_imports()

        self.assertEqual(removed, 0)
        self.assertTrue(unrelated.exists())

    def test_malformed_token_filename_is_ignored_safely(self):
        malformed = self._staging_dir() / "..bad.json"
        malformed.write_text("{not-json", encoding="utf-8")

        removed = cleanup_staged_imports()

        self.assertEqual(removed, 0)
        self.assertTrue(malformed.exists())

    def test_cleanup_staged_imports_command_reports_removed_count(self):
        self._write_staged_file("C" * 40, hours_old=25)
        out = StringIO()

        call_command("cleanup_staged_imports", stdout=out)

        self.assertIn(
            "Removed 1 expired staged marginalia import file(s).", out.getvalue()
        )


class MarginaliaImportPreviewApiTests(
    MarginaliaImportFixtureMixin, IsolatedUserdataMixin, APITestCase
):
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
        unmatched = self.preview_marginalia_payload(
            file_hash="0" * 64, title="Missing Book", authors=["Nobody"]
        )["books"][0]
        payload["books"].append(unmatched)

        preview = cast(Any, self.post_preview_payload(payload))
        r = cast(
            Any,
            self.client.get(
                preview.data["unmatched_download_url"],
                HTTP_ACCEPT="text/html,application/xhtml+xml,*/*",
            ),
        )

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
        preview = cast(
            Any,
            self.post_preview_payload(
                self.preview_marginalia_payload(
                    file_hash="0" * 64, title="Missing Book"
                )
            ),
        )

        self.client.force_login(other)
        r = self.client.get(preview.data["unmatched_download_url"])

        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
