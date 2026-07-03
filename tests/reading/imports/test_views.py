from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, cast
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession
from reading.import_staging import stage_marginalia_import, staged_import_path
from reading.models import Annotation, ReadingSession
from tests.reading.utils import IsolatedUserdataMixin
from tests.reading.imports.helpers import MarginaliaImportFixtureMixin


User = get_user_model()

class MarginaliaImportPreviewApiTests(MarginaliaImportFixtureMixin, IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.set_up_import_books()

    def _url(self):
        return "/api/v1/reading/import/preview/"

    def test_preview_requires_login(self):
        r = self.post_preview_payload(self.preview_marginalia_payload())
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
            {"file": self.upload_payload(self.preview_marginalia_payload())},
            format="multipart",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_json_returns_400(self):
        self.client.force_login(self.user)
        r = cast(Any, self.post_preview_payload(b"{not-json"))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["valid"])
        self.assertIn("errors", r.data)

    @patch("reading.import_services.MAX_MARGINALIA_IMPORT_BYTES", 4)
    def test_oversized_marginalia_json_preview_upload_is_rejected_before_staging(self):
        self.client.force_login(self.user)
        r = cast(Any, self.post_preview_payload(b'{"x":1}'))

        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["valid"])
        self.assertFalse(r.data["can_apply"])
        self.assertNotIn("import_token", r.data)
        self.assertIn("limit", r.data["errors"][0]["message"])

    def test_schema_invalid_export_returns_readable_errors(self):
        self.client.force_login(self.user)
        payload = self.preview_marginalia_payload()
        del payload["books"][0]["sessions"][0]["annotations"][0]["target"]

        r = cast(Any, self.post_preview_payload(payload))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["valid"])
        self.assertIn("$.books[0].sessions[0].annotations[0]", r.data["errors"][0]["path"])
        self.assertIn("target", r.data["errors"][0]["message"])


class MarginaliaImportApplyApiTests(MarginaliaImportFixtureMixin, IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.set_up_import_books()

    def _url(self):
        return "/api/v1/reading/import/apply/"

    def test_apply_requires_login(self):
        r = self.post_apply_payload(self.marginalia_payload())
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
            {"file": self.upload_payload(self.marginalia_payload())},
            format="multipart",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_apply_without_import_token_returns_400_and_no_writes(self):
        self.client.force_login(self.user)
        r = cast(Any, self.client.post(self._url(), {}, format="multipart"))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["applied"])
        self.assertIn("import_token", r.data["errors"][0]["message"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_apply_with_uploaded_file_but_no_import_token_returns_400_and_no_writes(self):
        self.client.force_login(self.user)
        payload = self.marginalia_payload()
        r = cast(Any, self.post_apply_payload(payload))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["applied"])
        self.assertIn("import_token", r.data["errors"][0]["message"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_apply_schema_invalid_staged_payload_returns_400_and_no_writes(self):
        self.client.force_login(self.user)
        payload = self.marginalia_payload()
        del payload["books"][0]["sessions"][0]["annotations"][0]["target"]
        token = stage_marginalia_import(user=self.user, payload=payload)
        r = cast(Any, self.post_apply_token(token))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["applied"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_apply_with_valid_token_imports_and_consumes_staged_file(self):
        payload = self.marginalia_payload()
        token = stage_marginalia_import(user=self.user, payload=payload)
        path = staged_import_path(token)

        self.client.force_login(self.user)
        r = cast(Any, self.post_apply_token(token))

        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["summary"]["sessions_created"], 1)
        self.assertEqual(ReadingSession.objects.count(), 1)
        self.assertFalse(path.exists())

    def test_apply_with_another_users_token_returns_400_and_no_writes(self):
        other = User.objects.create_user(username="other", password="pw")
        token = stage_marginalia_import(user=other, payload=self.marginalia_payload())

        self.client.force_login(self.user)
        r = cast(Any, self.post_apply_token(token))

        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(r.data["applied"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_apply_with_invalid_or_traversal_token_returns_400_and_no_writes(self):
        self.client.force_login(self.user)
        for token in ["../bad", "bad.json", "short"]:
            r = cast(Any, self.post_apply_token(token))
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertFalse(r.data["applied"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)

    def test_apply_with_missing_or_expired_token_returns_400_and_no_writes(self):
        token = stage_marginalia_import(user=self.user, payload=self.marginalia_payload())
        path = staged_import_path(token)
        staged = json.loads(path.read_text(encoding="utf-8"))
        staged["staged_at"] = (timezone.now() - timedelta(hours=25)).isoformat()
        path.write_text(json.dumps(staged), encoding="utf-8")

        self.client.force_login(self.user)
        expired = cast(Any, self.post_apply_token(token))
        missing = cast(Any, self.post_apply_token("A" * 40))

        self.assertEqual(expired.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Import preview expired", expired.data["errors"][0]["message"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)
