from __future__ import annotations

import hashlib
import json

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_api import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from library.models import (
    Book,
    BookGroupAssignment,
    LibraryGroup,
    LibraryGroupMembership,
)
from marginalia.imports.staging import import_stage_root, stage_file_path
from marginalia.models import Annotation, ImportStage, ReadingSession
from tests.marginalia.import_helpers import (
    archive_payload,
    archive_session,
    archive_upload,
)
from tests.testenv.filesystem import IsolatedUserdataMixin


User = get_user_model()
NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


class MarginaliaImportPreviewAPITests(IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.other = User.objects.create_user(username="other", password="testpass")
        self.group = LibraryGroup.objects.create(name="Readers")
        LibraryGroupMembership.objects.create(user=self.user, group=self.group)
        self.other_group = LibraryGroup.objects.create(name="Other Readers")
        LibraryGroupMembership.objects.create(user=self.other, group=self.other_group)
        self.book = Book.objects.create(title="Archive Book", checksum="a" * 64)
        BookGroupAssignment.objects.create(book=self.book, group=self.group)
        self.hidden_book = Book.objects.create(title="Archive Book", checksum="b" * 64)
        BookGroupAssignment.objects.create(book=self.hidden_book, group=self.other_group)
        self.url = "/api/v1/marginalia/import/preview/"
        self.client.force_login(self.user)

    def post_preview(self, payload, **fields):
        return self.client.post(
            self.url,
            {"file": archive_upload(payload), **fields},
            format="multipart",
        )

    @patch("marginalia.imports.staging.timezone.now", return_value=NOW)
    def test_valid_preview_stages_digest_owned_archive_for_exactly_two_hours(
        self, _now
    ):
        payload = archive_payload(file_hash=f"sha256:{'a' * 64}")
        before = (ReadingSession.objects.count(), Annotation.objects.count())

        response = self.post_preview(payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        stage = ImportStage.objects.get()
        token = response.data["import_token"]
        self.assertNotEqual(stage.token_digest, token)
        self.assertEqual(
            stage.token_digest,
            hashlib.sha256(token.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(stage.expires_at, NOW.replace(hour=14))
        self.assertEqual(stage.state, ImportStage.STATE_READY)
        self.assertFalse(stage.include_empty_sessions)
        self.assertRegex(stage.storage_name, r"^[0-9a-f]{64}\.json$")
        self.assertNotIn("user supplied name", stage.storage_name)
        self.assertEqual(
            stage_file_path(stage.storage_name).read_bytes(),
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )
        self.assertEqual(import_stage_root().parent.name, "staged")
        self.assertEqual(
            before, (ReadingSession.objects.count(), Annotation.objects.count())
        )

    def test_preview_contract_uses_explicit_candidates_and_exact_accessible_hash_match(
        self,
    ):
        response = self.post_preview(archive_payload(file_hash=f"sha256:{'a' * 64}"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.data
        self.assertTrue(payload["can_apply"])
        self.assertEqual(
            payload["summary"],
            {
                "book_count": 1,
                "reading_session_count": 1,
                "annotation_count": 1,
            },
        )
        self.assertEqual(payload["matched_book_count"], 1)
        book = payload["books"][0]
        session = book["reading_sessions"][0]
        self.assertEqual(book["candidate_id"], "book-000001")
        self.assertEqual(
            book["match"], {"status": "matched", "book_id": str(self.book.pk)}
        )
        self.assertEqual(session["candidate_id"], "reading-session-000001")
        self.assertEqual(session["source_reading_session_id"], "source-session-1")
        self.assertEqual(session["source_status"], "active")
        self.assertEqual(session["will_import_as_status"], "closed")
        self.assertTrue(session["will_import"])
        self.assertFalse(_contains_bare_id(payload))
        self.assertNotIn("path", json.dumps(payload).lower())
        self.assertNotIn("download_url", json.dumps(payload))

    def test_unmatched_and_inaccessible_books_remain_reviewable_but_not_importable(
        self,
    ):
        response = self.post_preview(archive_payload(file_hash=f"sha256:{'b' * 64}"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["can_apply"])
        self.assertEqual(response.data["unmatched_book_count"], 1)
        self.assertEqual(response.data["unmatched_reading_session_count"], 1)
        self.assertEqual(
            response.data["unmatched_downloadable_reading_session_count"], 1
        )
        self.assertEqual(response.data["books"][0]["match"], {"status": "unmatched"})
        self.assertFalse(
            response.data["books"][0]["reading_sessions"][0]["will_import"]
        )

    def test_empty_policy_defaults_to_exclusion_and_opt_in_includes(self):
        sessions = [
            archive_session(source_id="nonempty"),
            archive_session(source_id="empty", annotations=[]),
        ]
        payload = archive_payload(file_hash=f"sha256:{'a' * 64}", sessions=sessions)

        default = self.post_preview(payload)
        opted_in = self.post_preview(payload, include_empty_sessions="true")

        self.assertEqual(default.data["summary"]["reading_session_count"], 1)
        self.assertEqual(len(default.data["books"][0]["reading_sessions"]), 1)
        self.assertFalse(default.data["include_empty_sessions"])
        self.assertEqual(opted_in.data["summary"]["reading_session_count"], 2)
        self.assertTrue(opted_in.data["include_empty_sessions"])
        self.assertTrue(opted_in.data["books"][0]["reading_sessions"][1]["will_import"])

    def test_all_empty_default_is_bounded_and_creates_no_stage_or_file(self):
        payload = archive_payload(
            file_hash=f"sha256:{'a' * 64}",
            sessions=[archive_session(annotations=[])],
        )

        response = self.post_preview(payload)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(ImportStage.objects.count(), 0)
        self.assertFalse(import_stage_root().exists())

    def test_possible_duplicate_is_warning_only_and_remains_selectable(self):
        existing = ReadingSession.objects.create(
            user=self.user, book=self.book, name="Second pass"
        )
        ReadingSession.objects.filter(pk=existing.pk).update(
            started_at=parse_datetime("2026-07-01T12:00:00Z")
        )

        response = self.post_preview(archive_payload(file_hash=f"sha256:{'a' * 64}"))

        session = response.data["books"][0]["reading_sessions"][0]
        self.assertTrue(session["possible_duplicate"])
        self.assertTrue(session["will_import"])
        self.assertEqual(
            response.data["warnings"][0]["code"], "POSSIBLE_DUPLICATE_SESSION"
        )

    def test_invalid_archives_unknown_fields_and_size_fail_without_staging(self):
        staged_files_before = set(import_stage_root().glob("*.json"))
        invalid = self.client.post(
            self.url,
            {
                "file": archive_upload(archive_payload(file_hash=f"sha256:{'a' * 64}")),
                "unexpected": "x",
            },
            format="multipart",
        )
        malformed = self.client.post(
            self.url,
            {"file": archive_upload({}, name="bad.json")},
            format="multipart",
        )
        with patch("marginalia.imports.services.MAX_IMPORT_BYTES", 4):
            oversized = self.post_preview(
                archive_payload(file_hash=f"sha256:{'a' * 64}")
            )

        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(malformed.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(oversized.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ImportStage.objects.count(), 0)
        self.assertEqual(set(import_stage_root().glob("*.json")), staged_files_before)

    def test_duplicate_accessible_library_hash_is_integrity_failure(self):
        duplicate_rows = [
            SimpleNamespace(pk="one", checksum="a" * 64),
            SimpleNamespace(pk="two", checksum="a" * 64),
        ]
        fake_queryset = SimpleNamespace(filter=lambda **_kwargs: duplicate_rows)
        with patch(
            "marginalia.imports.services.visible_books_for_user",
            return_value=fake_queryset,
        ):
            response = self.post_preview(
                archive_payload(file_hash=f"sha256:{'a' * 64}")
            )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(ImportStage.objects.count(), 0)

    def test_session_only_authentication(self):
        self.client.logout()
        anonymous = self.post_preview(archive_payload(file_hash=f"sha256:{'a' * 64}"))
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        bearer = APIClient().post(
            self.url,
            {"file": archive_upload(archive_payload(file_hash=f"sha256:{'a' * 64}"))},
            format="multipart",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(anonymous.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(bearer.status_code, status.HTTP_403_FORBIDDEN)


def _contains_bare_id(value) -> bool:
    if isinstance(value, dict):
        return "id" in value or any(_contains_bare_id(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_bare_id(item) for item in value)
    return False
