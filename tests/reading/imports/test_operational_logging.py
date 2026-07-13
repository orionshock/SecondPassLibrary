from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from reading.imports.apply import apply_marginalia_import
from reading.imports.services import MarginaliaImportError
from reading.imports.staging import cleanup_staged_imports
from tests.reading.imports.helpers import MarginaliaImportFixtureMixin
from tests.testenv.filesystem import IsolatedUserdataMixin


class MarginaliaImportOperationalLoggingTests(
    MarginaliaImportFixtureMixin, IsolatedUserdataMixin, APITestCase
):
    def setUp(self):
        self.set_up_import_books()

    def test_successful_import_apply_logs_safe_info_summary(self):
        payload = self.marginalia_payload()

        with self.assertLogs("reading.imports.apply", level="INFO") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                result = apply_marginalia_import(user=self.user, payload=payload)

        output = logs.output[0]
        self.assertEqual(result["summary"]["sessions_created"], 1)
        self.assertIn("Marginalia import applied", output)
        self.assertIn(str(self.user.profile.pk), output)
        self.assertIn("books_matched=1", output)
        self.assertIn("books_skipped=0", output)
        self.assertIn("sessions_created=1", output)
        self.assertIn("annotations_created=3", output)
        self.assertIn("bookmarks_created=1", output)
        self.assertIn("highlights_created=2", output)
        self.assertIn("commented_highlights_created=1", output)
        self.assertIn("warnings=0", output)
        self.assertNotIn("Visible Match", output)
        self.assertNotIn("Imported session", output)
        self.assertNotIn("session notes", output)
        self.assertNotIn("plain highlight", output)
        self.assertNotIn("commented highlight", output)
        self.assertNotIn("epubcfi", output)
        self.assertNotIn(self.visible.checksum, output)

    def test_unmatched_import_logs_info_not_error_and_omits_title(self):
        payload = self.marginalia_payload(checksum="0" * 64, title="Missing Book")

        with patch("reading.imports.apply.logger.error") as error_log:
            with self.assertLogs("reading.imports.apply", level="INFO") as logs:
                with self.captureOnCommitCallbacks(execute=True):
                    result = apply_marginalia_import(user=self.user, payload=payload)

        error_log.assert_not_called()
        output = logs.output[0]
        self.assertEqual(result["summary"]["books_skipped"], 1)
        self.assertIn("books_matched=0", output)
        self.assertIn("books_skipped=1", output)
        self.assertIn("warnings=1", output)
        self.assertNotIn("Missing Book", output)

    def test_expected_validation_error_does_not_emit_error(self):
        payload = self.marginalia_payload()
        payload["type"] = "WrongExport"

        with patch("reading.imports.apply.logger.error") as error_log:
            with self.assertRaises(MarginaliaImportError):
                apply_marginalia_import(user=self.user, payload=payload)

        error_log.assert_not_called()


class MarginaliaStagedCleanupOperationalLoggingTests(IsolatedUserdataMixin, TestCase):
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

    def test_stale_cleanup_logs_aggregate_info_without_filename(self):
        expired = self._write_staged_file("A" * 40, hours_old=25)

        with self.assertLogs("reading.imports.staging", level="INFO") as logs:
            removed = cleanup_staged_imports()

        output = logs.output[0]
        self.assertEqual(removed, 1)
        self.assertFalse(expired.exists())
        self.assertIn("removed=1", output)
        self.assertIn("stale=1", output)
        self.assertIn("corrupt=0", output)
        self.assertIn("cleanup_failures=0", output)
        self.assertNotIn(expired.name, output)
        self.assertNotIn(str(expired), output)

    def test_corrupt_cleanup_logs_aggregate_warning_without_filename(self):
        corrupt = self._staging_dir() / f"{'B' * 40}.json"
        corrupt.write_text("{not-json", encoding="utf-8")

        with self.assertLogs("reading.imports.staging", level="WARNING") as logs:
            removed = cleanup_staged_imports()

        output = logs.output[0]
        self.assertEqual(removed, 1)
        self.assertFalse(corrupt.exists())
        self.assertIn("removed=1", output)
        self.assertIn("corrupt=1", output)
        self.assertIn("cleanup_failures=0", output)
        self.assertNotIn(corrupt.name, output)
        self.assertNotIn(str(corrupt), output)
