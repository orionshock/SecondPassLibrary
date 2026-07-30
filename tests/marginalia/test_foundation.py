from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from library.models import Book
from marginalia.models import Annotation, ReadingSession, SessionProgress
from marginalia.services import (
    close_session,
    open_session,
)


User = get_user_model()


class MarginaliaFoundationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.book = Book.objects.create(title="Foundation Book")

    def test_session_ownership_and_active_uniqueness(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)

        self.assertEqual(session.user, self.user)
        self.assertEqual(session.book, self.book)
        self.assertTrue(session.is_active)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReadingSession.objects.create(user=self.user, book=self.book)

    def test_multiple_closed_sessions_are_valid(self):
        closed_at = timezone.now()
        first = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_CLOSED,
            closed_at=closed_at,
        )
        second = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_CLOSED,
            closed_at=closed_at,
        )

        self.assertFalse(first.is_active)
        self.assertFalse(second.is_active)
        self.assertEqual(
            ReadingSession.objects.filter(user=self.user, book=self.book).count(),
            2,
        )
        self.assertFalse(
            ReadingSession.objects.filter(
                user=self.user,
                book=self.book,
                status=ReadingSession.STATUS_ACTIVE,
            ).exists()
        )

    def test_database_enforces_the_two_state_lifecycle(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReadingSession.objects.create(
                user=self.user,
                book=self.book,
                status="archived",
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReadingSession.objects.create(
                user=self.user,
                book=self.book,
                status=ReadingSession.STATUS_CLOSED,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReadingSession.objects.create(
                user=self.user,
                book=self.book,
                status=ReadingSession.STATUS_ACTIVE,
                closed_at=timezone.now(),
            )

    def test_session_protects_book_and_owns_dependent_records(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)
        progress = SessionProgress.objects.create(session=session)
        annotation = Annotation.objects.create(
            session=session,
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/2)",
        )

        self.assertEqual(progress.session, session)
        self.assertEqual(annotation.session, session)
        self.assertEqual(annotation.user, self.user)
        self.assertEqual(annotation.book, self.book)
        with self.assertRaises(ProtectedError):
            self.book.delete()

        session.delete()
        self.assertFalse(SessionProgress.objects.filter(pk=progress.pk).exists())
        self.assertFalse(Annotation.objects.filter(pk=annotation.pk).exists())

    def test_progress_is_one_to_one_and_preserves_locations(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)
        label = "  Chapter 08 · 42% · The Blackstaff  "
        progress = SessionProgress.objects.create(
            session=session,
            cfi="  epubcfi(/6/8)  ",
            location_label=label,
            progression=0.42,
        )

        progress.refresh_from_db()
        self.assertEqual(progress.cfi, "  epubcfi(/6/8)  ")
        self.assertEqual(progress.location_label, label)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SessionProgress.objects.create(session=session)

    def test_location_labels_are_optional_and_preserved_on_annotations(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)
        bookmark = Annotation.objects.create(
            session=session,
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/2)",
        )
        label = "Location 008 · 42% · Appendix B"
        noted_highlight = Annotation.objects.create(
            session=session,
            kind=Annotation.KIND_HIGHLIGHT,
            cfi="epubcfi(/6/4)",
            location_label=label,
            highlight_text="Selected text.",
            comment_text="Remember this.",
        )

        self.assertEqual(bookmark.location_label, "")
        noted_highlight.refresh_from_db()
        self.assertEqual(noted_highlight.location_label, label)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Annotation.objects.create(
                session=session,
                kind=Annotation.KIND_BOOKMARK,
                cfi="epubcfi(/6/6)",
                location_label=None,
            )

    def test_database_rejects_invalid_located_record_shapes(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Annotation.objects.create(
                session=session,
                kind=Annotation.KIND_BOOKMARK,
                cfi="",
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Annotation.objects.create(
                session=session,
                kind=Annotation.KIND_HIGHLIGHT,
                cfi="epubcfi(/6/2)",
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Annotation.objects.create(
                session=session,
                kind=Annotation.KIND_BOOKMARK,
                cfi="epubcfi(/6/4)",
                comment_text="Not valid bookmark content.",
            )
        for field in (
            "highlight_text",
            "quote_prefix",
            "quote_suffix",
            "highlight_color",
        ):
            with self.subTest(field=field), self.assertRaises(
                IntegrityError
            ), transaction.atomic():
                Annotation.objects.create(
                    session=session,
                    kind=Annotation.KIND_BOOKMARK,
                    cfi="epubcfi(/6/4)",
                    **{field: "not allowed"},
                )
        with self.assertRaises(IntegrityError), transaction.atomic():
            SessionProgress.objects.create(session=session, progression=1.1)


class MarginaliaLifecycleServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.book = Book.objects.create(title="Service Book")

    def test_open_session_reuses_the_existing_open_session_without_mutating_it(self):
        first = open_session(user=self.user, book=self.book, name="First pass")
        second = open_session(user=self.user, book=self.book, name="Replacement")

        self.assertEqual(second, first)
        self.assertEqual(second.name, "First pass")
        self.assertEqual(second.status, ReadingSession.STATUS_ACTIVE)
        self.assertIsNone(second.closed_at)

    def test_new_session_requires_the_previous_session_to_be_deliberately_closed(self):
        previous = open_session(user=self.user, book=self.book, name="First pass")
        close_session(session=previous)
        previous_closed_at = previous.closed_at

        current = open_session(user=self.user, book=self.book, name="Second pass")

        previous.refresh_from_db()
        self.assertEqual(previous.status, ReadingSession.STATUS_CLOSED)
        self.assertEqual(previous.closed_at, previous_closed_at)
        self.assertNotEqual(current, previous)
        self.assertEqual(current.status, ReadingSession.STATUS_ACTIVE)
        self.assertEqual(current.name, "Second pass")

    def test_closing_a_session_is_idempotent(self):
        session = open_session(user=self.user, book=self.book)

        closed = close_session(session=session)
        closed_at = closed.closed_at
        closed_again = close_session(session=closed)

        self.assertEqual(closed_again.status, ReadingSession.STATUS_CLOSED)
        self.assertEqual(closed_again.closed_at, closed_at)
