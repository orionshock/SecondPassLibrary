from __future__ import annotations

import json

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.client_sessions.services import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession
from library.models import Author, Book, BookAuthor
from marginalia.archives import DuplicateBookHashError
from marginalia.exports.services import _export_stats, export_all_marginalia
from marginalia.models import Annotation, ReadingSession


User = get_user_model()
GENERATED_AT = datetime(2026, 7, 30, 22, 15, tzinfo=UTC)


class MarginaliaExportAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.other = User.objects.create_user(username="other", password="testpass")
        self.client.force_login(self.user)
        self.url = "/api/v1/marginalia/export/"

        self.book = Book.objects.create(title="Owned History", checksum="a" * 64)
        self.second_book = Book.objects.create(title="Second Book", checksum="b" * 64)
        self.active = ReadingSession.objects.create(
            user=self.user,
            book=self.second_book,
            name="Active",
            progress_cfi="  opaque::progress  ",
            progress_location_label="  Chapter 08 · 42%  ",
            progress_updated_at=GENERATED_AT - timedelta(hours=1),
        )
        self.closed = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Closed",
            status=ReadingSession.STATUS_CLOSED,
            closed_at=GENERATED_AT - timedelta(days=1),
        )
        self.empty = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Empty",
            status=ReadingSession.STATUS_CLOSED,
            closed_at=GENERATED_AT - timedelta(days=2),
        )
        self.highlight = Annotation.objects.create(
            session=self.active,
            client_id="reader-highlight",
            kind=Annotation.KIND_HIGHLIGHT,
            cfi="opaque::highlight",
            location_label="Chapter 08 · 42%",
            highlight_text="Selected passage",
            quote_prefix="Before ",
            quote_suffix=" after.",
            highlight_color="green",
            comment_text="A note",
        )
        Annotation.objects.create(
            session=self.closed,
            client_id="reader-bookmark",
            kind=Annotation.KIND_BOOKMARK,
            cfi="opaque::bookmark",
            location_label="Chapter 09 · 47%",
        )
        Annotation.objects.create(
            session=self.closed,
            client_id="deleted",
            kind=Annotation.KIND_BOOKMARK,
            cfi="opaque::deleted",
            is_deleted=True,
        )
        foreign_book = Book.objects.create(title="Foreign", checksum="c" * 64)
        self.foreign = ReadingSession.objects.create(
            user=self.other,
            book=foreign_book,
        )
        Annotation.objects.create(
            session=self.foreign,
            client_id="foreign",
            kind=Annotation.KIND_BOOKMARK,
            cfi="opaque::foreign",
        )

    def _payload(self, response):
        return json.loads(response.content)

    @patch("marginalia.exports.services.timezone.now", return_value=GENERATED_AT)
    def test_complete_export_is_canonical_attachment_and_excludes_empty_by_default(
        self, _now
    ):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(
            response["Content-Disposition"],
            'attachment; filename="20260730-second-pass-marginalia.json"',
        )
        payload = self._payload(response)
        self.assertEqual(payload["generatedAt"], "2026-07-30T22:15:00Z")
        self.assertNotIn("scope", payload)
        self.assertEqual(
            [book["fileHash"] for book in payload["books"]],
            [f"sha256:{'a' * 64}", f"sha256:{'b' * 64}"],
        )
        sessions = [
            session
            for book in payload["books"]
            for session in book["readingSessions"]
        ]
        self.assertEqual({row["status"] for row in sessions}, {"active", "closed"})
        self.assertNotIn("Empty", {row["name"] for row in sessions})
        self.assertNotIn(str(self.active.pk), json.dumps(payload))
        self.assertTrue(all(row["sourceReadingSessionId"] for row in sessions))
        active = next(row for row in sessions if row["name"] == "Active")
        self.assertEqual(active["progress"]["cfi"], self.active.progress_cfi)
        self.assertEqual(
            active["progress"]["locationLabel"],
            self.active.progress_location_label,
        )
        annotation = active["annotations"][0]
        self.assertEqual(annotation["clientAnnotationId"], self.highlight.client_id)
        self.assertEqual(annotation["body"]["text"], "Selected passage")
        self.assertFalse(_contains_key(payload, "source"))
        self.assertFalse(_contains_bare_id(payload))
        self.assertNotIn("deleted", json.dumps(payload))
        self.assertNotIn("Foreign", json.dumps(payload))

    def test_complete_export_can_include_empty_sessions(self):
        response = self.client.get(self.url, {"include_empty_sessions": "true"})

        names = {
            session["name"]
            for book in self._payload(response)["books"]
            for session in book["readingSessions"]
        }
        self.assertIn("Empty", names)

    def test_complete_export_is_read_only_and_does_not_require_library_access(self):
        before = (
            ReadingSession.objects.count(),
            Annotation.objects.count(),
            self.active.updated_at,
            self.highlight.updated_at,
        )

        response = self.client.get(self.url)
        self.active.refresh_from_db()
        self.highlight.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            (
                ReadingSession.objects.count(),
                Annotation.objects.count(),
                self.active.updated_at,
                self.highlight.updated_at,
            ),
            before,
        )

    def test_complete_export_rejects_empty_result_and_invalid_query(self):
        Annotation.objects.filter(session__user=self.user).update(is_deleted=True)

        empty = self.client.get(self.url)
        invalid = self.client.get(self.url, {"unexpected": "true"})

        self.assertEqual(empty.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(empty.json()["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("unexpected", invalid.json())

    def test_complete_export_missing_or_duplicate_hash_fails_without_attachment(self):
        self.book.checksum = ""
        self.book.save(update_fields=["checksum"])
        missing = self.client.get(self.url)

        with patch(
            "marginalia.exports.services.serialize_archive",
            side_effect=DuplicateBookHashError,
        ):
            duplicate = self.client.get(self.url)

        self.assertEqual(missing.status_code, status.HTTP_409_CONFLICT)
        self.assertNotIn("Content-Disposition", missing)
        self.assertEqual(duplicate.status_code, status.HTTP_409_CONFLICT)
        self.assertNotIn("Content-Disposition", duplicate)

    def test_selective_export_is_owned_exact_and_canonically_ordered(self):
        response = self.client.post(
            self.url,
            {
                "reading_session_ids": [str(self.active.pk), str(self.closed.pk)],
                "include_empty_sessions": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = self._payload(response)
        self.assertEqual(
            [book["fileHash"] for book in payload["books"]],
            [f"sha256:{'a' * 64}", f"sha256:{'b' * 64}"],
        )
        names = {
            session["name"]
            for book in payload["books"]
            for session in book["readingSessions"]
        }
        self.assertEqual(names, {"Active", "Closed"})

    @patch("marginalia.exports.services.MAX_SELECTED_EXPORT_SESSION_IDS", 2)
    def test_selected_export_at_session_limit_succeeds(self):
        response = self.client.post(
            self.url,
            {"reading_session_ids": [str(self.active.pk), str(self.closed.pk)]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Content-Disposition", response)

    @patch("marginalia.exports.services.MAX_SELECTED_EXPORT_SESSION_IDS", 1)
    def test_selected_export_above_limit_rejects_before_query_or_serialization(self):
        with (
            patch("marginalia.exports.services.ReadingSession.objects.filter") as query,
            patch("marginalia.exports.services.serialize_archive") as serialize,
            self.assertLogs("marginalia.exports.services", level="INFO") as logs,
        ):
            response = self.client.post(
                self.url,
                {
                    "reading_session_ids": [
                        str(self.active.pk),
                        str(self.closed.pk),
                    ]
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        self.assertEqual(response.json()["error"]["code"], "EXPORT_TOO_LARGE")
        self.assertEqual(
            response.json()["error"]["limit"],
            {"kind": "selected_sessions", "maximum": 1},
        )
        self.assertEqual(response.json()["error"]["export_mode"], "selected")
        self.assertTrue(response.json()["error"]["hint"])
        self.assertNotIn(str(self.active.pk), json.dumps(response.json()))
        self.assertNotIn("Content-Disposition", response)
        query.assert_not_called()
        serialize.assert_not_called()
        self.assertNotIn(str(self.active.pk), logs.output[0])

    def test_selective_export_rejects_duplicate_missing_and_foreign_ids(self):
        duplicate = self.client.post(
            self.url,
            {"reading_session_ids": [str(self.active.pk), str(self.active.pk)]},
            format="json",
        )
        foreign = self.client.post(
            self.url,
            {"reading_session_ids": [str(self.foreign.pk)]},
            format="json",
        )
        missing = self.client.post(
            self.url,
            {"reading_session_ids": ["00000000-0000-0000-0000-000000000001"]},
            format="json",
        )
        unknown = self.client.post(
            self.url,
            {
                "reading_session_ids": [str(self.active.pk)],
                "unexpected": True,
            },
            format="json",
        )

        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(foreign.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(missing.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(unknown.status_code, status.HTTP_400_BAD_REQUEST)

    def test_selective_empty_policy_is_consistent(self):
        request = {"reading_session_ids": [str(self.empty.pk)]}

        excluded = self.client.post(self.url, request, format="json")
        included = self.client.post(
            self.url,
            request | {"include_empty_sessions": True},
            format="json",
        )

        self.assertEqual(excluded.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(included.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self._payload(included)["books"][0]["readingSessions"][0]["name"],
            "Empty",
        )

    @patch("marginalia.exports.services.MAX_FULL_EXPORT_SESSIONS", 3)
    def test_full_export_at_session_limit_succeeds(self):
        response = self.client.get(self.url, {"include_empty_sessions": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Content-Disposition", response)

    @patch("marginalia.exports.services.MAX_FULL_EXPORT_SESSIONS", 2)
    def test_full_export_above_session_limit_rejects_before_serialization(self):
        with patch("marginalia.exports.services.serialize_archive") as serialize:
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        self.assertEqual(
            response.json()["error"]["limit"],
            {"kind": "full_sessions", "maximum": 2},
        )
        self.assertEqual(response.json()["error"]["export_mode"], "full")
        self.assertNotIn("Content-Disposition", response)
        serialize.assert_not_called()

    @patch("marginalia.exports.services.MAX_EXPORT_ANNOTATIONS", 1)
    def test_export_annotation_limit_rejects_before_serialization(self):
        with patch("marginalia.exports.services.serialize_archive") as serialize:
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        self.assertEqual(
            response.json()["error"]["limit"],
            {"kind": "annotations", "maximum": 1},
        )
        serialize.assert_not_called()

    @patch("marginalia.exports.services.MAX_EXPORT_BYTES", 100)
    def test_export_estimated_size_limit_rejects_before_serialization(self):
        with (
            patch("marginalia.exports.services.serialize_archive") as serialize,
            patch("marginalia.exports.services.render_archive_json") as render,
        ):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        self.assertEqual(
            response.json()["error"]["limit"],
            {"kind": "estimated_archive_bytes", "maximum": 100},
        )
        serialize.assert_not_called()
        render.assert_not_called()

    def test_export_estimate_includes_distinct_book_titles(self):
        sessions = ReadingSession.objects.filter(user=self.user)
        before = _export_stats(sessions, include_empty_sessions=True)
        previous_length = len(self.second_book.title)
        self.second_book.title = "T" * 512
        self.second_book.save(update_fields=["title"])

        after = _export_stats(sessions, include_empty_sessions=True)

        self.assertEqual(after.book_count, before.book_count)
        self.assertEqual(
            after.estimated_bytes - before.estimated_bytes,
            (512 - previous_length) * 6,
        )

    def test_export_estimate_includes_each_serialized_book_author(self):
        sessions = ReadingSession.objects.filter(user=self.user)
        before = _export_stats(sessions, include_empty_sessions=True)
        names = [f"{index:02d}" + "A" * 253 for index in range(10)]
        for position, name in enumerate(names):
            author = Author.objects.create(name=name)
            BookAuthor.objects.create(
                book=self.second_book,
                author=author,
                position=position,
            )

        after = _export_stats(sessions, include_empty_sessions=True)

        self.assertEqual(after.author_count - before.author_count, len(names))
        self.assertEqual(
            after.estimated_bytes - before.estimated_bytes,
            sum(map(len, names)) * 6 + len(names) * 16,
        )

    def test_export_estimate_counts_book_metadata_once_for_repeated_sessions(self):
        sessions = ReadingSession.objects.filter(book=self.second_book)
        before = _export_stats(sessions, include_empty_sessions=True)
        ReadingSession.objects.create(user=self.other, book=self.second_book)

        after = _export_stats(sessions, include_empty_sessions=True)

        self.assertEqual(after.book_count, before.book_count)
        self.assertEqual(after.author_count, before.author_count)
        self.assertEqual(after.estimated_bytes - before.estimated_bytes, 512)

    def test_book_metadata_estimate_rejects_before_archive_materialization(self):
        sessions = ReadingSession.objects.filter(user=self.user)
        before = _export_stats(sessions, include_empty_sessions=True)
        author = Author.objects.create(name="A" * 255)
        BookAuthor.objects.create(book=self.second_book, author=author)

        with (
            patch(
                "marginalia.exports.services.MAX_EXPORT_BYTES",
                before.estimated_bytes + 1,
            ),
            patch("marginalia.exports.services.serialize_archive") as serialize,
            patch("marginalia.exports.services.render_archive_json") as render,
        ):
            response = self.client.get(self.url, {"include_empty_sessions": "true"})

        self.assertEqual(response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        self.assertEqual(
            response.json()["error"]["limit"]["kind"],
            "estimated_archive_bytes",
        )
        serialize.assert_not_called()
        render.assert_not_called()

    @patch("marginalia.exports.services.MAX_EXPORT_BYTES", 100)
    @patch(
        "marginalia.exports.services._export_stats",
        return_value=SimpleNamespace(
            session_count=3,
            annotation_count=2,
            estimated_bytes=99,
        ),
    )
    def test_final_serialized_size_limit_rejects_without_partial_attachment(
        self,
        _stats,
    ):
        with patch(
            "marginalia.exports.services.render_archive_json",
            return_value=b"x" * 101,
        ):
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        self.assertEqual(response.json()["error"]["code"], "EXPORT_TOO_LARGE")
        self.assertEqual(
            response.json()["error"]["limit"],
            {"kind": "archive_bytes", "maximum": 100},
        )
        self.assertNotIn("Content-Disposition", response)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_selective_export_applies_checksum_integrity_rules(self):
        self.second_book.checksum = ""
        self.second_book.save(update_fields=["checksum"])
        request = {"reading_session_ids": [str(self.active.pk)]}

        missing = self.client.post(self.url, request, format="json")
        with patch(
            "marginalia.exports.services.serialize_archive",
            side_effect=DuplicateBookHashError,
        ):
            duplicate = self.client.post(self.url, request, format="json")

        self.assertEqual(missing.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(duplicate.status_code, status.HTTP_409_CONFLICT)
        self.assertNotIn("Content-Disposition", missing)
        self.assertNotIn("Content-Disposition", duplicate)

    def test_export_is_session_authenticated_only(self):
        anonymous = APIClient()
        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )

        anonymous_response = anonymous.get(self.url)
        bearer_response = anonymous.get(
            self.url,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        bearer_post = anonymous.post(
            self.url,
            {"reading_session_ids": [str(self.active.pk)]},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(anonymous_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(bearer_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(bearer_post.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_codec_query_count_is_bounded(self):
        with self.assertNumQueries(7):
            document = export_all_marginalia(user=self.user)

        self.assertTrue(document.content)


def _contains_bare_id(value) -> bool:
    if isinstance(value, dict):
        return "id" in value or any(_contains_bare_id(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_bare_id(item) for item in value)
    return False


def _contains_key(value, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False
