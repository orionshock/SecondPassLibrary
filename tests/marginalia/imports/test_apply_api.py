from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TransactionTestCase
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_sessions.services import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from library.models import (
    Book,
    BookGroupAssignment,
    LibraryGroup,
    LibraryGroupMembership,
)
from library.queries import visible_books_for_user
from marginalia.models import Annotation, ImportStage, ReadingSession
from marginalia.imports.apply import apply_import
from marginalia.imports.plan import BOOK_INACCESSIBLE, StagedImportPlan
from marginalia.imports.services import preview_import
from marginalia.imports.staging import stage_file_path
from tests.marginalia.import_helpers import (
    archive_payload,
    archive_session,
    archive_upload,
)
from tests.testenv.database_connections import orm_worker_connection_scope
from tests.testenv.filesystem import IsolatedUserdataMixin


User = get_user_model()


def _bookmark():
    return {
        "clientAnnotationId": "bookmark-1",
        "kind": "bookmark",
        "location": {
            "location": "epubcfi(/6/8!/4/4)",
            "locationLabel": "  Chapter 09 · 47%  ",
        },
        "createdAt": "2026-07-19T12:00:00Z",
        "updatedAt": "2026-07-19T13:00:00Z",
    }


def _archive_book(*, checksum: str, title: str, sessions: list[dict]) -> dict:
    book = archive_payload(
        file_hash=f"sha256:{checksum}",
        sessions=sessions,
    )["books"][0]
    book["title"] = title
    return book


class MarginaliaImportApplyAPITests(IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.other = User.objects.create_user(username="other", password="testpass")
        self.group = LibraryGroup.objects.create(name="Readers")
        LibraryGroupMembership.objects.create(user=self.user, group=self.group)
        self.book = Book.objects.create(title="Archive Book", checksum="a" * 64)
        BookGroupAssignment.objects.create(book=self.book, group=self.group)
        self.preview_url = "/api/v1/marginalia/import/preview/"
        self.apply_url = "/api/v1/marginalia/import/apply/"
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

    def apply(self, token, selections):
        return self.client.post(
            self.apply_url,
            {"import_token": token, "reading_sessions": selections},
            format="json",
        )

    def test_apply_maps_archive_to_new_closed_session_without_touching_active(self):
        source = archive_session()
        source["annotations"].append(_bookmark())
        preview = self.preview(
            archive_payload(file_hash=f"sha256:{'a' * 64}", sessions=[source])
        )
        active = ReadingSession.objects.create(user=self.user, book=self.book)

        response = self.apply(
            preview["import_token"],
            [
                {
                    "candidate_id": "reading-session-000001",
                    "name": "Imported override",
                    "notes": "Imported notes override",
                }
            ],
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("import_token", response.data)
        self.assertEqual(response.data["imported_reading_session_count"], 1)
        self.assertEqual(response.data["imported_annotation_count"], 2)
        row = response.data["reading_sessions"][0]
        imported = ReadingSession.objects.get(pk=row["reading_session_id"])
        active.refresh_from_db()
        self.assertEqual(active.status, ReadingSession.STATUS_ACTIVE)
        self.assertEqual(imported.status, ReadingSession.STATUS_CLOSED)
        self.assertEqual(imported.name, "Imported override")
        self.assertEqual(imported.notes, "Imported notes override")
        self.assertEqual(imported.started_at, parse_datetime(source["startedAt"]))
        self.assertEqual(imported.created_at, parse_datetime(source["createdAt"]))
        self.assertEqual(imported.updated_at, parse_datetime(source["updatedAt"]))
        self.assertEqual(imported.closed_at, parse_datetime(source["updatedAt"]))
        self.assertEqual(imported.progress_location, source["progress"]["location"])
        self.assertEqual(
            imported.progress_location_label,
            source["progress"]["locationLabel"],
        )
        self.assertEqual(
            imported.progress_updated_at,
            parse_datetime(source["progress"]["updatedAt"]),
        )
        annotations = {item.kind: item for item in imported.annotations.all()}
        highlight = annotations[Annotation.KIND_HIGHLIGHT]
        bookmark = annotations[Annotation.KIND_BOOKMARK]
        self.assertEqual(highlight.client_id, "highlight-1")
        self.assertEqual(
            highlight.location, source["annotations"][0]["location"]["location"]
        )
        self.assertEqual(highlight.highlight_text, "Selected passage")
        self.assertEqual(highlight.quote_prefix, "Before ")
        self.assertEqual(highlight.quote_suffix, " after.")
        self.assertEqual(highlight.highlight_color, "yellow")
        self.assertEqual(highlight.comment_text, "Reader note")
        self.assertEqual(
            highlight.created_at,
            parse_datetime(source["annotations"][0]["createdAt"]),
        )
        self.assertEqual(
            highlight.updated_at,
            parse_datetime(source["annotations"][0]["updatedAt"]),
        )
        self.assertEqual(bookmark.client_id, "bookmark-1")
        self.assertEqual(bookmark.highlight_text, "")
        self.assertEqual(bookmark.comment_text, "")
        self.assertNotEqual(str(imported.pk), source["sourceReadingSessionId"])
        self.assertNotEqual(str(highlight.pk), highlight.client_id)

    def test_closed_source_preserves_closed_at_and_duplicate_warning_does_not_block(
        self,
    ):
        source = archive_session(status="closed")
        existing = ReadingSession.objects.create(user=self.user, book=self.book)
        ReadingSession.objects.filter(pk=existing.pk).update(
            name=source["name"],
            started_at=parse_datetime(source["startedAt"]),
        )
        preview = self.preview(
            archive_payload(file_hash=f"sha256:{'a' * 64}", sessions=[source])
        )

        response = self.apply(
            preview["import_token"],
            [{"candidate_id": "reading-session-000001"}],
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        imported = ReadingSession.objects.get(
            pk=response.data["reading_sessions"][0]["reading_session_id"]
        )
        self.assertEqual(imported.closed_at, parse_datetime(source["closedAt"]))
        self.assertEqual(
            response.data["warnings"][0]["code"], "POSSIBLE_DUPLICATE_SESSION"
        )

    def test_selection_is_strict_and_hidden_or_unmatched_candidates_cannot_import(self):
        sessions = [
            archive_session(source_id="visible"),
            archive_session(source_id="hidden-empty", annotations=[]),
        ]
        preview = self.preview(
            archive_payload(file_hash=f"sha256:{'a' * 64}", sessions=sessions)
        )
        token = preview["import_token"]

        empty = self.apply(token, [])
        duplicate = self.apply(
            token,
            [
                {"candidate_id": "reading-session-000001"},
                {"candidate_id": "reading-session-000001"},
            ],
        )
        hidden = self.apply(token, [{"candidate_id": "reading-session-000002"}])
        unknown_field = self.client.post(
            self.apply_url,
            {
                "import_token": token,
                "reading_sessions": [
                    {"candidate_id": "reading-session-000001", "extra": True}
                ],
            },
            format="json",
        )
        oversized_name = self.apply(
            token,
            [{"candidate_id": "reading-session-000001", "name": "x" * 256}],
        )
        oversized_notes = self.apply(
            token,
            [{"candidate_id": "reading-session-000001", "notes": "x" * 65537}],
        )

        for response in (
            empty,
            duplicate,
            hidden,
            unknown_field,
            oversized_name,
            oversized_notes,
        ):
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(ImportStage.objects.get().state, ImportStage.STATE_READY)

        unmatched_payload = archive_payload(file_hash=f"sha256:{'b' * 64}")
        unmatched = self.preview(unmatched_payload)
        rejected = self.apply(
            unmatched["import_token"],
            [{"candidate_id": "reading-session-000001"}],
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ReadingSession.objects.count(), 0)

    def test_model_failure_rolls_back_everything_and_leaves_ready_stage_file(self):
        sessions = [archive_session(source_id="one"), archive_session(source_id="two")]
        preview = self.preview(
            archive_payload(file_hash=f"sha256:{'a' * 64}", sessions=sessions)
        )
        stage = ImportStage.objects.get()
        path = stage_file_path(stage.storage_name)

        with patch(
            "marginalia.imports.apply.Annotation.objects.bulk_create",
            side_effect=IntegrityError,
        ):
            response = self.apply(
                preview["import_token"],
                [
                    {"candidate_id": "reading-session-000001"},
                    {"candidate_id": "reading-session-000002"},
                ],
            )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)
        stage.refresh_from_db()
        self.assertEqual(stage.state, ImportStage.STATE_READY)
        self.assertTrue(path.exists())

    def test_access_loss_partially_applies_and_consumes_stage_replay_safely(self):
        second_checksum = "b" * 64
        second_group = LibraryGroup.objects.create(name="Second group")
        LibraryGroupMembership.objects.create(user=self.user, group=second_group)
        second = Book.objects.create(
            title="Visible database title", checksum=second_checksum
        )
        BookGroupAssignment.objects.create(book=second, group=second_group)
        payload = archive_payload(file_hash=f"sha256:{'a' * 64}")
        payload["books"] = [
            _archive_book(
                checksum="a" * 64,
                title="Lost staged title",
                sessions=[archive_session(source_id="lost")],
            ),
            _archive_book(
                checksum=second_checksum,
                title="Visible staged title",
                sessions=[archive_session(source_id="visible")],
            ),
        ]
        preview = self.preview(payload)
        stage = ImportStage.objects.get()
        path = stage_file_path(stage.storage_name)
        existing = ReadingSession.objects.create(user=self.user, book=self.book)
        existing_annotation = Annotation.objects.create(
            session=existing,
            client_id="existing-bookmark",
            kind=Annotation.KIND_BOOKMARK,
            location="epubcfi(/6/8!/4/6)",
        )
        LibraryGroupMembership.objects.filter(user=self.user, group=self.group).delete()

        selections = [
            {"candidate_id": "reading-session-000001"},
            {"candidate_id": "reading-session-000002"},
        ]
        with (
            self.assertLogs("marginalia.imports.apply", level="INFO") as logs,
            patch(
                "marginalia.imports.apply.visible_books_for_user",
                wraps=visible_books_for_user,
            ) as visibility_query,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.apply(preview["import_token"], selections)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["imported_reading_session_count"], 1)
        self.assertEqual(response.data["unmatched_reading_session_count"], 1)
        self.assertTrue(response.data["unmatched_download_available"])
        self.assertEqual(
            response.data["unmatched_books"],
            [
                {
                    "candidate_id": "book-000001",
                    "title": "Lost staged title",
                    "reason": "book_inaccessible",
                }
            ],
        )
        visibility_query.assert_called_once_with(self.user, cached=False)
        self.assertEqual(ReadingSession.objects.filter(book=second).count(), 1)
        self.assertFalse(
            ReadingSession.objects.filter(book=self.book)
            .exclude(pk=existing.pk)
            .exists()
        )
        self.assertTrue(ReadingSession.objects.filter(pk=existing.pk).exists())
        self.assertTrue(Annotation.objects.filter(pk=existing_annotation.pk).exists())
        detail = self.client.get(f"/api/v1/marginalia/sessions/{existing.pk}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertFalse(detail.data["context"]["book"]["can_open"])
        stage.refresh_from_db()
        self.assertEqual(stage.state, ImportStage.STATE_APPLIED)
        staged_plan = StagedImportPlan.decode(stage.preview)
        candidate = staged_plan.encode()["books"][0]["reading_sessions"][0]
        self.assertEqual(candidate["unmatched_reason"], BOOK_INACCESSIBLE)
        self.assertTrue(path.exists())
        replay = self.apply(preview["import_token"], list(reversed(selections)))
        self.assertEqual(replay.data, response.data)
        self.assertEqual(ReadingSession.objects.filter(book=second).count(), 1)
        self.assertIn("applied_count=1", logs.output[0])
        self.assertIn("inaccessible_count=1", logs.output[0])
        self.assertNotIn("Lost staged title", logs.output[0])
        self.assertNotIn(preview["import_token"], logs.output[0])

    def test_assignment_removal_becomes_successful_unmatched_result(self):
        preview = self.preview(archive_payload(file_hash=f"sha256:{'a' * 64}"))
        BookGroupAssignment.objects.filter(book=self.book, group=self.group).delete()

        response = self.apply(
            preview["import_token"],
            [{"candidate_id": "reading-session-000001"}],
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["imported_reading_session_count"], 0)
        self.assertEqual(response.data["unmatched_reading_session_count"], 1)
        self.assertEqual(
            response.data["unmatched_books"][0]["reason"], "book_inaccessible"
        )
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)
        stage = ImportStage.objects.get()
        self.assertEqual(stage.state, ImportStage.STATE_APPLIED)
        self.assertIsNotNone(stage.result)

    def test_apply_keeps_missing_book_and_malformed_stage_contracts(self):
        missing_preview = self.preview(archive_payload(file_hash=f"sha256:{'a' * 64}"))
        self.book.delete()

        missing = self.apply(
            missing_preview["import_token"],
            [{"candidate_id": "reading-session-000001"}],
        )

        replacement = Book.objects.create(title="Archive Book", checksum="a" * 64)
        BookGroupAssignment.objects.create(book=replacement, group=self.group)
        malformed_preview = self.preview(
            archive_payload(file_hash=f"sha256:{'a' * 64}")
        )
        malformed_stage = ImportStage.objects.order_by("created_at").last()
        stage_file_path(malformed_stage.storage_name).write_bytes(b"{")

        malformed = self.apply(
            malformed_preview["import_token"],
            [{"candidate_id": "reading-session-000001"}],
        )

        for response in (missing, malformed):
            self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
            self.assertEqual(response.data["error"]["code"], "INVALID_REQUEST")
            self.assertEqual(
                response.data["error"]["message"],
                "The staged import archive is no longer usable.",
            )
            self.assertNotIn("inaccessible_books", response.data["error"])
            self.assertNotIn("inaccessible_book_count", response.data["error"])
        self.assertEqual(ReadingSession.objects.count(), 0)
        self.assertEqual(Annotation.objects.count(), 0)
        self.assertFalse(
            ImportStage.objects.exclude(state=ImportStage.STATE_READY).exists()
        )

    def test_corrupt_persisted_plan_fails_through_bounded_apply_contract(self):
        preview = self.preview(archive_payload(file_hash=f"sha256:{'a' * 64}"))
        stage = ImportStage.objects.get()
        stage.preview["summary"]["reading_session_count"] = 99
        stage.save(update_fields=["preview"])

        response = self.apply(
            preview["import_token"],
            [{"candidate_id": "reading-session-000001"}],
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.data["error"]["code"], "INVALID_REQUEST")
        stage.refresh_from_db()
        self.assertEqual(stage.state, ImportStage.STATE_READY)
        self.assertEqual(ReadingSession.objects.count(), 0)

    def test_replay_is_order_independent_and_works_after_stage_file_deletion(self):
        sessions = [archive_session(source_id="one"), archive_session(source_id="two")]
        preview = self.preview(
            archive_payload(file_hash=f"sha256:{'a' * 64}", sessions=sessions)
        )
        selections = [
            {"candidate_id": "reading-session-000002", "name": "Two"},
            {"candidate_id": "reading-session-000001", "name": "One"},
        ]

        with self.captureOnCommitCallbacks(execute=True):
            first = self.apply(preview["import_token"], selections)
        stage = ImportStage.objects.get()
        self.assertEqual(stage.state, ImportStage.STATE_APPLIED)
        self.assertFalse(stage_file_path(stage.storage_name).exists())

        replay = self.apply(preview["import_token"], list(reversed(selections)))
        changed = self.apply(
            preview["import_token"],
            [
                {"candidate_id": "reading-session-000001", "name": "Changed"},
                {"candidate_id": "reading-session-000002", "name": "Two"},
            ],
        )

        self.assertEqual(replay.status_code, status.HTTP_200_OK)
        self.assertEqual(replay.data, first.data)
        self.assertEqual(ReadingSession.objects.count(), 2)
        self.assertEqual(changed.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(ReadingSession.objects.count(), 2)

    def test_post_commit_cleanup_failure_does_not_undo_applied_import(self):
        preview = self.preview(archive_payload(file_hash=f"sha256:{'a' * 64}"))
        stage = ImportStage.objects.get()
        path = stage_file_path(stage.storage_name)

        with (
            patch.object(Path, "unlink", side_effect=OSError),
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.apply(
                preview["import_token"],
                [{"candidate_id": "reading-session-000001"}],
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ReadingSession.objects.count(), 1)
        stage.refresh_from_db()
        self.assertEqual(stage.state, ImportStage.STATE_APPLIED)
        self.assertTrue(path.exists())

    def test_invalid_wrong_user_expired_and_missing_file_are_no_leakage(self):
        previews = [
            self.preview(archive_payload(file_hash=f"sha256:{'a' * 64}"))
            for _ in range(3)
        ]
        stages = list(ImportStage.objects.order_by("created_at"))
        ImportStage.objects.filter(pk=stages[1].pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        stage_file_path(stages[2].storage_name).unlink()
        selection = [{"candidate_id": "reading-session-000001"}]

        invalid = self.apply("x" * 32, selection)
        expired = self.apply(previews[1]["import_token"], selection)
        missing = self.apply(previews[2]["import_token"], selection)
        self.client.force_login(self.other)
        foreign = self.apply(previews[0]["import_token"], selection)

        for response in (invalid, expired, missing, foreign):
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            self.assertEqual(response.data["error"]["code"], "NOT_FOUND")
        self.assertEqual(ReadingSession.objects.count(), 0)

    def test_apply_is_session_authenticated_only(self):
        preview = self.preview(archive_payload(file_hash=f"sha256:{'a' * 64}"))
        body = {
            "import_token": preview["import_token"],
            "reading_sessions": [{"candidate_id": "reading-session-000001"}],
        }
        self.client.logout()
        anonymous = self.client.post(self.apply_url, body, format="json")
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        bearer = APIClient().post(
            self.apply_url,
            body,
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(anonymous.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(bearer.status_code, status.HTTP_403_FORBIDDEN)


class MarginaliaImportApplyConcurrencyTests(IsolatedUserdataMixin, TransactionTestCase):
    reset_sequences = True

    def test_concurrent_identical_apply_converges_on_one_result(self):
        user = User.objects.create_user(username="reader", password="testpass")
        group = LibraryGroup.objects.create(name="Readers")
        LibraryGroupMembership.objects.create(user=user, group=group)
        book = Book.objects.create(title="Archive Book", checksum="a" * 64)
        BookGroupAssignment.objects.create(book=book, group=group)
        preview = preview_import(
            user=user,
            file=archive_upload(archive_payload(file_hash=f"sha256:{'a' * 64}")),
        )
        token = preview["import_token"]
        selections = [{"candidate_id": "reading-session-000001"}]

        def execute():
            with orm_worker_connection_scope():
                thread_user = User.objects.get(pk=user.pk)
                return apply_import(
                    user=thread_user,
                    import_token=token,
                    reading_sessions=selections,
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: execute(), range(2)))

        self.assertEqual(results[0], results[1])
        self.assertEqual(ReadingSession.objects.count(), 1)
        stage = ImportStage.objects.get()
        self.assertEqual(stage.state, ImportStage.STATE_APPLIED)
