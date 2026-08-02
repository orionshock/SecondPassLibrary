from __future__ import annotations

import json

from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.utils import timezone
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
from marginalia.archives import parse_archive
from marginalia.imports.unmatched import _safe_key
from marginalia.models import Annotation, ImportStage, ReadingSession
from tests.marginalia.import_helpers import (
    archive_payload,
    archive_session,
    archive_upload,
)
from tests.testenv.filesystem import IsolatedUserdataMixin


User = get_user_model()


def _bookmark():
    return {
        "clientAnnotationId": "bookmark-1",
        "kind": "bookmark",
        "location": {
            "cfi": "  opaque::bookmark  ",
            "locationLabel": "  Chapter 09 · 47%  ",
        },
        "createdAt": "2026-07-19T12:00:00Z",
        "updatedAt": "2026-07-19T13:00:00Z",
    }


def _archive_book(*, file_hash, title, sessions):
    return {
        "fileHash": file_hash,
        "title": title,
        "authors": ["Example Author"],
        "readingSessions": sessions,
    }


class MarginaliaImportUnmatchedAPITests(IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.other = User.objects.create_user(username="other", password="testpass")
        self.group = LibraryGroup.objects.create(name="Readers")
        LibraryGroupMembership.objects.create(user=self.user, group=self.group)
        self.matched_book = Book.objects.create(
            title="Matched Book",
            checksum="a" * 64,
        )
        BookGroupAssignment.objects.create(book=self.matched_book, group=self.group)
        self.preview_url = "/api/v1/marginalia/import/preview/"
        self.apply_url = "/api/v1/marginalia/import/apply/"
        self.unmatched_url = "/api/v1/marginalia/import/unmatched/"
        self.client.force_login(self.user)

    def preview(self, payload, *, include_empty=False):
        response = self.client.post(
            self.preview_url,
            {
                "file": archive_upload(payload),
                "include_empty_sessions": include_empty,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def download(self, token):
        return self.client.get(self.unmatched_url, {"import_token": token})

    def mixed_payload(self):
        payload = archive_payload(
            file_hash=f"sha256:{'a' * 64}",
            sessions=[archive_session(source_id="matched-session")],
        )
        active = archive_session(source_id="source/unmatched:one")
        closed = archive_session(
            source_id="source-unmatched-two",
            status="closed",
            annotations=[_bookmark()],
        )
        payload["books"].append(
            _archive_book(
                file_hash=f"sha256:{'b' * 64}",
                title="Café / Missing Book",
                sessions=[active, closed],
            )
        )
        return payload

    def test_download_is_deterministic_canonical_and_excludes_matched_sessions(self):
        payload = self.mixed_payload()
        preview = self.preview(payload)
        stage = ImportStage.objects.get()
        stage_values = (
            stage.state,
            stage.created_at,
            stage.updated_at,
            stage.expires_at,
        )
        before = (ReadingSession.objects.count(), Annotation.objects.count())

        first = self.download(preview["import_token"])
        second = self.download(preview["import_token"])

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first["Content-Type"], "application/zip")
        self.assertEqual(
            first["Content-Disposition"],
            'attachment; filename="secondpass-marginalia-sessions.zip"',
        )
        self.assertEqual(first.content, second.content)
        stage.refresh_from_db()
        self.assertEqual(
            (stage.state, stage.created_at, stage.updated_at, stage.expires_at),
            stage_values,
        )
        self.assertEqual(
            before,
            (ReadingSession.objects.count(), Annotation.objects.count()),
        )

        with ZipFile(BytesIO(first.content)) as zip_file:
            self.assertEqual(
                zip_file.namelist(),
                [
                    "01-cafe-missing-book/01-01-cafe-missing-book-source-unmatched-one.json",
                    "01-cafe-missing-book/01-02-cafe-missing-book-source-unmatched-two.json",
                ],
            )
            infos = zip_file.infolist()
            raw_members = [zip_file.read(name) for name in zip_file.namelist()]

        self.assertTrue(all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in infos))
        self.assertTrue(all(info.create_system == 3 for info in infos))
        self.assertTrue(
            all((info.external_attr >> 16) & 0o777 == 0o600 for info in infos)
        )
        archives = [parse_archive(raw) for raw in raw_members]
        self.assertEqual(
            [archive.generated_at for archive in archives], [payload["generatedAt"]] * 2
        )
        self.assertEqual([len(archive.books) for archive in archives], [1, 1])
        self.assertEqual(
            [len(archive.books[0].reading_sessions) for archive in archives],
            [1, 1],
        )
        sessions = [archive.books[0].reading_sessions[0] for archive in archives]
        self.assertEqual([session.status for session in sessions], ["active", "closed"])
        self.assertEqual(
            sessions[0].progress.cfi,
            payload["books"][1]["readingSessions"][0]["progress"]["cfi"],
        )
        self.assertEqual(
            sessions[0].progress.location_label,
            payload["books"][1]["readingSessions"][0]["progress"]["locationLabel"],
        )
        highlight = sessions[0].annotations[0]
        self.assertEqual(highlight.client_annotation_id, "highlight-1")
        self.assertEqual(highlight.body.text, "Selected passage")
        self.assertEqual(highlight.body.prefix, "Before ")
        self.assertEqual(highlight.body.suffix, " after.")
        self.assertEqual(highlight.body.color, "yellow")
        self.assertEqual(highlight.body.note, "Reader note")
        self.assertEqual(
            highlight.created_at,
            payload["books"][1]["readingSessions"][0]["annotations"][0]["createdAt"],
        )
        self.assertEqual(sessions[1].annotations[0].client_annotation_id, "bookmark-1")
        for raw in raw_members:
            wire = json.loads(raw)
            self.assertFalse(_contains_bare_id(wire))
            self.assertFalse(_contains_key(wire, "source"))
            self.assertNotIn(str(self.matched_book.pk), raw.decode("utf-8"))

        self.assertEqual(
            preview["unmatched_downloadable_reading_session_count"],
            len(raw_members),
        )

    def test_staged_empty_policy_controls_content_and_omits_empty_books(self):
        nonempty = archive_session(source_id="nonempty")
        empty = archive_session(source_id="empty", annotations=[])
        payload = archive_payload(
            file_hash=f"sha256:{'b' * 64}",
            sessions=[nonempty, empty],
        )
        payload["books"].append(
            _archive_book(
                file_hash=f"sha256:{'c' * 64}",
                title="Only Empty",
                sessions=[archive_session(source_id="only-empty", annotations=[])],
            )
        )

        default = self.preview(payload)
        default_download = self.download(default["import_token"])
        included = self.preview(payload, include_empty=True)
        included_download = self.download(included["import_token"])

        with ZipFile(BytesIO(default_download.content)) as zip_file:
            default_members = zip_file.namelist()
        with ZipFile(BytesIO(included_download.content)) as zip_file:
            included_members = zip_file.namelist()
            included_archives = [
                parse_archive(zip_file.read(name)) for name in included_members
            ]
        self.assertEqual(len(default_members), 1)
        self.assertEqual(len(included_members), 3)
        self.assertEqual(
            included["unmatched_downloadable_reading_session_count"],
            len(included_members),
        )
        empty_exports = [
            archive
            for archive in included_archives
            if not archive.books[0].reading_sessions[0].annotations
        ]
        self.assertEqual(len(empty_exports), 2)
        self.assertFalse(any("only-empty" in name for name in default_members))

    def test_no_unmatched_sessions_returns_conflict(self):
        preview = self.preview(archive_payload(file_hash=f"sha256:{'a' * 64}"))

        response = self.download(preview["import_token"])

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_download_uses_staged_match_even_when_library_access_changes(self):
        preview = self.preview(archive_payload(file_hash=f"sha256:{'b' * 64}"))
        newly_visible = Book.objects.create(title="Now visible", checksum="b" * 64)
        BookGroupAssignment.objects.create(book=newly_visible, group=self.group)

        with patch(
            "marginalia.imports.services.visible_books_for_user",
            side_effect=AssertionError("download must not rematch"),
        ):
            response = self.download(preview["import_token"])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        with ZipFile(BytesIO(response.content)) as zip_file:
            exported = parse_archive(zip_file.read(zip_file.namelist()[0]))
        self.assertEqual(exported.books[0].file_hash, f"sha256:{'b' * 64}")

    def test_download_keeps_ready_stage_applicable_and_applied_missing_file_is_unusable(
        self,
    ):
        preview = self.preview(self.mixed_payload())
        downloaded = self.download(preview["import_token"])
        self.assertEqual(downloaded.status_code, status.HTTP_200_OK)

        with self.captureOnCommitCallbacks(execute=True):
            applied = self.client.post(
                self.apply_url,
                {
                    "import_token": preview["import_token"],
                    "reading_sessions": [{"candidate_id": "reading-session-000001"}],
                },
                format="json",
            )
        unavailable = self.download(preview["import_token"])

        self.assertEqual(applied.status_code, status.HTTP_200_OK)
        self.assertEqual(unavailable.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(ReadingSession.objects.count(), 1)

    def test_invalid_foreign_expired_and_missing_file_stages_are_equivalent(self):
        previews = [
            self.preview(archive_payload(file_hash=f"sha256:{'b' * 64}"))
            for _ in range(3)
        ]
        stages = list(ImportStage.objects.order_by("created_at"))
        ImportStage.objects.filter(pk=stages[1].pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        from marginalia.imports.staging import stage_file_path

        stage_file_path(stages[2].storage_name).unlink()
        invalid = self.download("not-a-token")
        expired = self.download(previews[1]["import_token"])
        missing = self.download(previews[2]["import_token"])
        self.client.force_login(self.other)
        foreign = self.download(previews[0]["import_token"])

        for response in (invalid, expired, missing, foreign):
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            self.assertEqual(response.data["error"]["code"], "NOT_FOUND")

    def test_stage_candidate_mismatch_is_bounded_and_does_not_mutate(self):
        preview = self.preview(archive_payload(file_hash=f"sha256:{'b' * 64}"))
        stage = ImportStage.objects.get()
        stage.preview["books"][0]["reading_sessions"][0][
            "source_reading_session_id"
        ] = "missing-source"
        stage.save(update_fields=["preview"])
        before = (stage.state, stage.updated_at)

        response = self.download(preview["import_token"])

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        stage.refresh_from_db()
        self.assertEqual((stage.state, stage.updated_at), before)

    def test_filename_keys_are_ascii_bounded_reserved_safe_and_collision_stable(self):
        used = set()
        first = _safe_key("../CON", fallback="book-1", used=used)
        second = _safe_key("CON!", fallback="book-2", used=used)
        blank = _safe_key(" ", fallback="book-3", used=used)
        long = _safe_key("é" + "x" * 100, fallback="book-4", used=used)

        self.assertEqual(first, "item-con")
        self.assertEqual(second, "item-con-2")
        self.assertEqual(blank, "book-3")
        self.assertLessEqual(len(long), 60)
        self.assertTrue(all(ord(character) < 128 for character in long))
        self.assertNotIn("/", "".join(used))
        self.assertFalse(any(str(self.matched_book.pk) in key for key in used))

    def test_session_only_authentication_and_required_token(self):
        missing = self.client.get(self.unmatched_url)
        self.assertEqual(missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.client.logout()
        anonymous = self.client.get(
            self.unmatched_url,
            {"import_token": "x" * 32},
        )
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        bearer = APIClient().get(
            self.unmatched_url,
            {"import_token": "x" * 32},
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


def _contains_key(value, key) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False
