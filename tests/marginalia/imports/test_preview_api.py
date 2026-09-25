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

from accounts.client_sessions.services import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from library.cover_objects import canonical_cover_storage_name
from library.models import (
    Author,
    Book,
    BookAuthor,
    BookGroupAssignment,
    BookIdentifier,
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
        self.book = Book.objects.create(
            title="Archive Book",
            checksum="a" * 64,
            cover_file=canonical_cover_storage_name(digest="5" * 64, extension=".jpg"),
        )
        BookGroupAssignment.objects.create(book=self.book, group=self.group)
        self.hidden_book = Book.objects.create(title="Archive Book", checksum="b" * 64)
        BookGroupAssignment.objects.create(
            book=self.hidden_book, group=self.other_group
        )
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

    def test_preview_rejects_unsupported_durable_cfi_before_staging(self):
        payload = archive_payload(file_hash=f"sha256:{'a' * 64}")
        payload["books"][0]["readingSessions"][0]["annotations"][0]["location"][
            "location"
        ] = "epubcfi(/6/8!/4/3:2[bad^x])"

        response = self.post_preview(payload)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(ImportStage.objects.exists())

    def test_preview_accepts_historical_step_id_assertion(self):
        payload = archive_payload(file_hash=f"sha256:{'a' * 64}")
        location = "epubcfi(/6/18!/4[chapter-identifier-01]/2,/708/1:0,/710/1:119)"
        payload["books"][0]["readingSessions"][0]["annotations"][0]["location"][
            "location"
        ] = location

        response = self.post_preview(payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        staged = json.loads(
            stage_file_path(ImportStage.objects.get().storage_name).read_bytes()
        )
        self.assertEqual(
            staged["books"][0]["readingSessions"][0]["annotations"][0]["location"][
                "location"
            ],
            location,
        )

    def test_preview_contract_uses_explicit_candidates_and_exact_accessible_hash_match(
        self,
    ):
        payload = archive_payload(file_hash=f"sha256:{'a' * 64}")
        payload["books"][0]["title"] = "Different title"
        payload["books"][0]["authors"] = ["Different Author"]

        response = self.post_preview(payload)

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
        self.assertEqual(book["match"]["status"], "matched")
        self.assertEqual(book["match"]["book_id"], str(self.book.pk))
        self.assertTrue(
            book["match"]["cover_url"].endswith(f"/media/{self.book.cover_file.name}")
        )
        self.assertEqual(session["candidate_id"], "reading-session-000001")
        self.assertEqual(session["source_reading_session_id"], "source-session-1")
        self.assertEqual(session["source_status"], "active")
        self.assertEqual(session["will_import_as_status"], "closed")
        self.assertTrue(session["will_import"])
        self.assertFalse(_contains_bare_id(payload))
        self.assertNotIn("path", json.dumps(payload).lower())
        self.assertNotIn("download_url", json.dumps(payload))

    def test_same_title_author_and_library_identifiers_do_not_replace_checksum(self):
        author = Author.objects.create(name="Example Author")
        BookAuthor.objects.create(book=self.book, author=author, position=0)
        BookIdentifier.objects.create(
            book=self.book,
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="9780000000001",
            normalized_value="9780000000001",
        )

        response = self.post_preview(archive_payload(file_hash=f"sha256:{'c' * 64}"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["books"][0]["match"],
            {"status": "unmatched", "reason": "not_found"},
        )
        self.assertFalse(response.data["can_apply"])

    def test_missing_file_hash_is_unmatched_without_metadata_lookup(self):
        payload = archive_payload(file_hash=f"sha256:{'a' * 64}")
        payload["books"][0].pop("fileHash")

        response = self.post_preview(payload)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["books"][0]["match"],
            {"status": "unmatched", "reason": "not_found"},
        )
        self.assertEqual(response.data["books"][0]["file_hash"], "")
        self.assertFalse(response.data["can_apply"])

    def test_inaccessible_book_is_unmatched_with_staged_metadata_only(self):
        staged = archive_payload(file_hash=f"sha256:{'b' * 64}")
        staged["books"][0]["title"] = "Staged hidden title"
        staged["books"][0]["authors"] = ["Staged author"]
        response = self.post_preview(staged)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["can_apply"])
        self.assertEqual(response.data["unmatched_book_count"], 1)
        self.assertEqual(response.data["unmatched_reading_session_count"], 1)
        self.assertEqual(
            response.data["unmatched_downloadable_reading_session_count"], 1
        )
        book = response.data["books"][0]
        self.assertEqual(
            book["match"],
            {"status": "unmatched", "reason": "book_inaccessible"},
        )
        self.assertEqual(book["title"], "Staged hidden title")
        self.assertEqual(book["authors"], ["Staged author"])
        self.assertNotIn(str(self.hidden_book.pk), json.dumps(response.data))
        self.assertNotIn(self.hidden_book.title, json.dumps(response.data))
        self.assertFalse(
            response.data["books"][0]["reading_sessions"][0]["will_import"]
        )

    def test_missing_book_has_distinct_unmatched_reason(self):
        with self.assertLogs("marginalia.imports.services", level="INFO") as logs:
            response = self.post_preview(
                archive_payload(file_hash=f"sha256:{'c' * 64}")
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["books"][0]["match"],
            {"status": "unmatched", "reason": "not_found"},
        )
        diagnostic = next(
            message for message in logs.output if "Book match evaluated" in message
        )
        self.assertIn("source_method=web", diagnostic)
        self.assertIn("file_hash_present=true", diagnostic)
        self.assertIn("hash_algorithm=sha256", diagnostic)
        self.assertIn("visible_checksum_matches=0", diagnostic)
        self.assertIn("metadata_fallback_attempted=false", diagnostic)
        self.assertIn("outcome=not_found", diagnostic)
        self.assertNotIn("Archive Book", diagnostic)
        self.assertNotIn("c" * 64, diagnostic)
        self.assertNotIn("books/", diagnostic)

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

    def test_ambiguous_accessible_hash_is_unmatched_and_not_selectable(self):
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

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["books"][0]["match"],
            {"status": "unmatched", "reason": "ambiguous_match"},
        )
        self.assertFalse(
            response.data["books"][0]["reading_sessions"][0]["will_import"]
        )
        self.assertEqual(ImportStage.objects.count(), 1)

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
