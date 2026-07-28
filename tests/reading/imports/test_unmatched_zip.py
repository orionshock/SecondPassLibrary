from __future__ import annotations

import json
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from reading.imports.services import _archive_key
from reading.imports.staging import stage_marginalia_import, staged_import_path
from tests.reading.imports.helpers import MarginaliaImportFixtureMixin
from tests.testenv.filesystem import IsolatedUserdataMixin


User = get_user_model()


class MarginaliaImportUnmatchedZipTests(
    MarginaliaImportFixtureMixin, IsolatedUserdataMixin, APITestCase
):
    def setUp(self):
        self.set_up_import_books()
        self.client.force_login(self.user)

    def _download(self, payload, *, user=None):
        token = stage_marginalia_import(user=user or self.user, payload=payload)
        response = self.client.get(
            "/api/v1/reading/import/unmatched/", {"import_token": token}
        )
        return token, response

    def test_download_splits_nonempty_unmatched_sessions_into_stable_mini_exports(self):
        payload = self.preview_marginalia_payload(
            file_hash="1" * 64, title="Café / Missing Book"
        )
        first = payload["books"][0]["sessions"][0]
        second = deepcopy(first)
        second["export_session_id"] = "session-2"
        second["started_at"] = "2026-06-03T12:00:00+00:00"
        second["name"] = "Second"
        payload["books"][0]["sessions"].append(second)

        token, response = self._download(payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="secondpass-marginalia-sessions.zip"',
        )
        repeated = self.client.get(
            "/api/v1/reading/import/unmatched/", {"import_token": token}
        )
        self.assertEqual(repeated.content, response.content)
        with ZipFile(BytesIO(response.content)) as archive:
            self.assertEqual(
                archive.namelist(),
                [
                    "01-cafe-missing-book/01-01-cafe-missing-book-2026-06-01t12-00-00-00-00.json",
                    "01-cafe-missing-book/01-02-cafe-missing-book-2026-06-03t12-00-00-00-00.json",
                ],
            )
            exports = [json.loads(archive.read(name)) for name in archive.namelist()]

        self.assertEqual(
            [item["generator"] for item in exports], [payload["generator"]] * 2
        )
        self.assertEqual(
            set(exports[0]),
            {
                "type",
                "schema_version",
                "profile",
                "generated_at",
                "generator",
                "scope",
                "books",
            },
        )
        self.assertEqual([len(item["books"]) for item in exports], [1, 1])
        self.assertEqual(
            [len(item["books"][0]["sessions"]) for item in exports], [1, 1]
        )
        self.assertEqual(
            [item["books"][0]["sessions"][0]["export_session_id"] for item in exports],
            ["session-1", "session-2"],
        )

    def test_download_excludes_empty_sessions_empty_books_and_matched_sessions(self):
        payload = self.preview_marginalia_payload(file_hash="1" * 64, title="Missing")
        empty = deepcopy(payload["books"][0]["sessions"][0])
        empty["export_session_id"] = "empty"
        empty["annotations"] = []
        payload["books"][0]["sessions"].append(empty)
        empty_book = deepcopy(payload["books"][0])
        empty_book["title"] = "Empty Book"
        empty_book["file_hash"] = "sha256:" + ("2" * 64)
        empty_book["source"] = "book:sha256:" + ("2" * 64)
        empty_book["sessions"] = [empty]
        matched = deepcopy(self.preview_marginalia_payload()["books"][0])
        payload["books"].extend([empty_book, matched])

        _, response = self._download(payload)

        with ZipFile(BytesIO(response.content)) as archive:
            self.assertEqual(len(archive.namelist()), 1)
            exported = json.loads(archive.read(archive.namelist()[0]))
        self.assertEqual(exported["books"][0]["title"], "Missing")
        self.assertEqual(
            exported["books"][0]["sessions"][0]["export_session_id"], "session-1"
        )

    def test_preview_count_uses_the_same_nonempty_session_rule(self):
        payload = self.preview_marginalia_payload(file_hash="1" * 64)
        empty = deepcopy(payload["books"][0]["sessions"][0])
        empty["export_session_id"] = "empty"
        empty["annotations"] = []
        payload["books"][0]["sessions"].append(empty)

        response = self.post_preview_payload(payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["unmatched_downloadable_session_count"], 1)
        self.assertIn("unmatched_download_url", response.data)

    def test_no_downloadable_sessions_returns_conflict_without_empty_zip(self):
        payload = self.preview_marginalia_payload(file_hash="1" * 64)
        payload["books"][0]["sessions"][0]["annotations"] = []

        _, response = self._download(payload)

        self.assertEqual(
            response.status_code, status.HTTP_409_CONFLICT, msg=response.data
        )
        self.assertFalse(response.data["valid"])
        preview = self.post_preview_payload(payload)
        self.assertEqual(preview.data["unmatched_downloadable_session_count"], 0)
        self.assertNotIn("unmatched_download_url", preview.data)

    def test_invalid_expired_and_wrong_user_tokens_use_bounded_import_errors(self):
        missing = self.client.get(
            "/api/v1/reading/import/unmatched/", {"import_token": "not-a-token"}
        )
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(missing.data["valid"])

        expired_token = stage_marginalia_import(
            user=self.user,
            payload=self.preview_marginalia_payload(file_hash="1" * 64),
        )
        path = staged_import_path(expired_token)
        staged = json.loads(path.read_text(encoding="utf-8"))
        staged["staged_at"] = "2000-01-01T00:00:00+00:00"
        path.write_text(json.dumps(staged), encoding="utf-8")
        expired = self.client.get(
            "/api/v1/reading/import/unmatched/", {"import_token": expired_token}
        )
        self.assertEqual(expired.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(expired.data["valid"])

        other = User.objects.create_user(username="other", password="pw")
        token = stage_marginalia_import(
            user=other,
            payload=self.preview_marginalia_payload(file_hash="1" * 64),
        )
        wrong_user = self.client.get(
            "/api/v1/reading/import/unmatched/", {"import_token": token}
        )
        self.assertEqual(wrong_user.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(wrong_user.data["valid"])

    def test_download_does_not_consume_token_before_apply(self):
        payload = self.preview_marginalia_payload()
        invalid = deepcopy(payload["books"][0]["sessions"][0])
        invalid["export_session_id"] = "reader-session"
        invalid["annotations"][0]["target"]["selector"]["value"] = "invalid"
        payload["books"][0]["sessions"].append(invalid)
        token, response = self._download(payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        applied = self.post_apply_token(token)

        self.assertEqual(applied.status_code, status.HTTP_200_OK)
        self.assertEqual(applied.data["summary"]["sessions_created"], 1)

    def test_archive_key_priority_sanitization_and_truncation(self):
        self.assertEqual(
            _archive_key(
                "Primary ID", "Other", "Title", fallback="book-1"
            ),
            "primary-id",
        )
        self.assertEqual(
            _archive_key(
                None, "Bøøk ID", "Title", fallback="book-1"
            ),
            "bk-id",
        )
        self.assertEqual(
            _archive_key(
                "  ", "Book ID", "Title", fallback="book-1"
            ),
            "book-id",
        )
        self.assertEqual(
            _archive_key(None, "", None, fallback="session-2"),
            "session-2",
        )
        self.assertLessEqual(
            len(_archive_key("x" * 100, fallback="book-1")), 60
        )
