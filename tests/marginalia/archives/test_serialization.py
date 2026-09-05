from __future__ import annotations

import json

from datetime import UTC, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from library.models import Author, Book, BookAuthor
from library.queries import visible_books_for_user
from marginalia.archives import (
    DuplicateBookHashError,
    MissingBookChecksumError,
    render_archive_json,
    serialize_archive,
)
from marginalia.models import Annotation, ReadingSession


User = get_user_model()
GENERATED_AT = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


class MarginaliaArchiveSerializationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.book = Book.objects.create(
            title="Archive Book",
            checksum="a" * 64,
        )
        author = Author.objects.create(name="Example Author")
        BookAuthor.objects.create(book=self.book, author=author, position=0)

    def make_session(
        self,
        *,
        book=None,
        status=ReadingSession.STATUS_CLOSED,
        offset=0,
        progress=False,
    ):
        timestamp = GENERATED_AT - timedelta(days=10 - offset)
        session = ReadingSession.objects.create(
            user=self.user,
            book=book or self.book,
            status=status,
            closed_at=timestamp if status == ReadingSession.STATUS_CLOSED else None,
            name=f"Session {offset}",
            notes="Session notes",
            progress_cfi="  opaque::progress  " if progress else "",
            progress_location_label="  Chapter 08 · 42%  " if progress else "",
            progress_updated_at=timestamp if progress else None,
        )
        ReadingSession.objects.filter(pk=session.pk).update(
            started_at=timestamp - timedelta(days=2),
            created_at=timestamp - timedelta(days=2),
            updated_at=timestamp,
        )
        session.refresh_from_db()
        return session

    def make_highlight(self, session, *, client_id="reader-highlight", label=""):
        annotation = Annotation.objects.create(
            session=session,
            client_id=client_id,
            kind=Annotation.KIND_HIGHLIGHT,
            cfi="  opaque::highlight  ",
            location_label=label,
            highlight_text="Selected passage",
            quote_prefix="Before ",
            quote_suffix=" after.",
            highlight_color="green",
            comment_text="Optional note.",
        )
        return annotation

    def test_serializes_explicit_archive_identities_and_canonical_shapes(self):
        closed = self.make_session(progress=True)
        highlight = self.make_highlight(
            closed,
            label="  Chapter 08 · 42% · The Blackstaff  ",
        )
        bookmark = Annotation.objects.create(
            session=closed,
            client_id="reader-bookmark",
            kind=Annotation.KIND_BOOKMARK,
            cfi="opaque::bookmark",
            location_label="Chapter 09 · 47%",
        )
        active = self.make_session(status=ReadingSession.STATUS_ACTIVE, offset=1)

        payload = json.loads(
            render_archive_json(
                serialize_archive(
                    ReadingSession.objects.filter(pk__in=[closed.pk, active.pk]),
                    generated_at=GENERATED_AT,
                    include_empty_sessions=True,
                )
            )
        )

        self.assertEqual(payload["books"][0]["fileHash"], f"sha256:{'a' * 64}")
        self.assertNotIn("source", payload["books"][0])
        sessions = payload["books"][0]["readingSessions"]
        self.assertEqual({row["status"] for row in sessions}, {"active", "closed"})
        self.assertTrue(
            all(
                row["sourceReadingSessionId"].startswith("source-reading-session-")
                for row in sessions
            )
        )
        rendered = json.dumps(payload)
        self.assertNotIn(str(closed.id), rendered)
        closed_payload = next(row for row in sessions if row["status"] == "closed")
        self.assertEqual(
            closed_payload["progress"],
            {
                "cfi": closed.progress_cfi,
                "locationLabel": closed.progress_location_label,
                "updatedAt": closed.progress_updated_at.isoformat().replace("+00:00", "Z"),
            },
        )
        annotations = {
            row["clientAnnotationId"]: row for row in closed_payload["annotations"]
        }
        self.assertEqual(
            annotations[highlight.client_id]["location"]["locationLabel"],
            highlight.location_label,
        )
        self.assertEqual(
            annotations[highlight.client_id]["body"],
            {
                "text": "Selected passage",
                "color": "green",
                "prefix": "Before ",
                "suffix": " after.",
                "note": "Optional note.",
            },
        )
        self.assertNotIn("body", annotations[bookmark.client_id])
        self.assertNotIn(str(bookmark.id), rendered)
        self.assertFalse(_contains_bare_id(payload))

    def test_empty_and_deleted_annotation_policy_is_explicit(self):
        included = self.make_session(offset=1)
        self.make_highlight(included)
        empty = self.make_session(offset=2)
        deleted_only = self.make_session(offset=3)
        Annotation.objects.create(
            session=deleted_only,
            client_id="deleted",
            kind=Annotation.KIND_BOOKMARK,
            cfi="opaque::deleted",
            is_deleted=True,
        )
        queryset = ReadingSession.objects.filter(
            pk__in=[included.pk, empty.pk, deleted_only.pk]
        )

        default = serialize_archive(queryset, generated_at=GENERATED_AT)
        opted_in = serialize_archive(
            queryset,
            generated_at=GENERATED_AT,
            include_empty_sessions=True,
        )

        self.assertEqual(len(default.books[0].reading_sessions), 1)
        self.assertEqual(len(opted_in.books[0].reading_sessions), 3)
        self.assertTrue(
            all(
                annotation.client_annotation_id != "deleted"
                for session in opted_in.books[0].reading_sessions
                for annotation in session.annotations
            )
        )

    def test_missing_or_duplicate_book_hash_fails_the_complete_serialization(self):
        missing_book = Book.objects.create(title="Missing Hash")
        missing_session = self.make_session(book=missing_book)
        self.make_highlight(missing_session)
        with self.assertRaises(MissingBookChecksumError):
            serialize_archive([missing_session], generated_at=GENERATED_AT)

        other_book = Book.objects.create(title="Other Book", checksum="b" * 64)
        other_session = self.make_session(book=other_book, offset=1)
        self.make_highlight(other_session, client_id="other-highlight")
        first_session = self.make_session(offset=2)
        self.make_highlight(first_session, client_id="first-highlight")
        other_session.book.checksum = self.book.checksum
        with self.assertRaises(DuplicateBookHashError):
            serialize_archive(
                [first_session, other_session],
                generated_at=GENERATED_AT,
            )

    def test_codec_does_not_require_library_access_or_expose_asset_fields(self):
        session = self.make_session()
        self.make_highlight(session)
        self.assertFalse(
            visible_books_for_user(self.user, cached=False)
            .filter(pk=self.book.pk)
            .exists()
        )

        payload = json.loads(
            render_archive_json(serialize_archive([session], generated_at=GENERATED_AT))
        )

        self.assertEqual(
            set(payload["books"][0]),
            {"fileHash", "title", "authors", "readingSessions"},
        )
        self.assertFalse(self.book.book_file)

    def test_ordering_and_rendered_output_are_deterministic(self):
        later_book = Book.objects.create(title="Later Hash", checksum="f" * 64)
        later_session = self.make_session(book=later_book, offset=2)
        self.make_highlight(later_session, client_id="later")
        session = self.make_session(offset=1)
        fixtures = (
            ("blank-b", "", "opaque::b"),
            ("chapter-10", "Chapter 10 · 50%", "opaque::10"),
            ("blank-a", "", "opaque::a"),
            ("chapter-02", "Chapter 02 · 10%", "opaque::02"),
        )
        for client_id, label, cfi in fixtures:
            Annotation.objects.create(
                session=session,
                client_id=client_id,
                kind=Annotation.KIND_BOOKMARK,
                cfi=cfi,
                location_label=label,
            )
        queryset = ReadingSession.objects.filter(pk__in=[later_session.pk, session.pk])

        first = render_archive_json(serialize_archive(queryset, generated_at=GENERATED_AT))
        second = render_archive_json(serialize_archive(queryset, generated_at=GENERATED_AT))
        payload = json.loads(first)

        self.assertEqual(first, second)
        self.assertEqual(
            [book["fileHash"] for book in payload["books"]],
            [f"sha256:{'a' * 64}", f"sha256:{'f' * 64}"],
        )
        self.assertEqual(
            [
                annotation["clientAnnotationId"]
                for annotation in payload["books"][0]["readingSessions"][0][
                    "annotations"
                ]
            ],
            ["chapter-02", "chapter-10", "blank-a", "blank-b"],
        )

    def test_serialization_does_not_mutate_domain_rows(self):
        session = self.make_session(progress=True)
        annotation = self.make_highlight(session)
        before = (
            session.status,
            session.updated_at,
            session.progress_cfi,
            annotation.updated_at,
            Annotation.objects.count(),
        )

        serialize_archive([session], generated_at=GENERATED_AT)
        session.refresh_from_db()
        annotation.refresh_from_db()

        self.assertEqual(
            (
                session.status,
                session.updated_at,
                session.progress_cfi,
                annotation.updated_at,
                Annotation.objects.count(),
            ),
            before,
        )


def _contains_bare_id(value) -> bool:
    if isinstance(value, dict):
        return "id" in value or any(
            _contains_bare_id(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_bare_id(item) for item in value)
    return False
