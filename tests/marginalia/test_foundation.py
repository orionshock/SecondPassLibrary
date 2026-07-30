from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone

from library.models import Book
from marginalia.models import Annotation, ReadingSession, SessionProgress
from marginalia.services import (
    close_session,
    get_or_create_active_session,
    start_new_session,
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

    def test_multiple_historical_sessions_are_valid(self):
        completed_at = timezone.now()
        first = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_COMPLETED,
            completed_at=completed_at,
        )
        second = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_ARCHIVED,
        )

        self.assertFalse(first.is_active)
        self.assertFalse(second.is_active)
        self.assertEqual(
            ReadingSession.objects.filter(user=self.user, book=self.book).count(),
            2,
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
        with self.assertRaises(IntegrityError), transaction.atomic():
            SessionProgress.objects.create(session=session, progression=1.1)


class MarginaliaLifecycleServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.book = Book.objects.create(title="Service Book")

    def test_active_session_service_reuses_the_one_active_session(self):
        first = get_or_create_active_session(user=self.user, book=self.book)
        second = get_or_create_active_session(user=self.user, book=self.book)

        self.assertEqual(second, first)

    def test_starting_again_archives_the_previous_session(self):
        previous = get_or_create_active_session(user=self.user, book=self.book)

        current = start_new_session(user=self.user, book=self.book, name="Second pass")

        previous.refresh_from_db()
        self.assertEqual(previous.status, ReadingSession.STATUS_ARCHIVED)
        self.assertEqual(current.status, ReadingSession.STATUS_ACTIVE)
        self.assertEqual(current.name, "Second pass")

    def test_closing_a_session_is_idempotent(self):
        session = get_or_create_active_session(user=self.user, book=self.book)

        closed = close_session(session=session)
        completed_at = closed.completed_at
        closed_again = close_session(session=closed)

        self.assertEqual(closed_again.status, ReadingSession.STATUS_COMPLETED)
        self.assertEqual(closed_again.completed_at, completed_at)
