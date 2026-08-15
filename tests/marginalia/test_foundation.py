from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from library.models import Book
from marginalia.models import Annotation, ReadingSession
from marginalia.sessions.progress import assign_session_progress, clear_session_progress


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

    def test_book_and_session_deletion_cascade_through_dependent_records(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)
        annotation = Annotation.objects.create(
            session=session,
            client_id="owned-bookmark",
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/2)",
        )

        self.assertEqual(annotation.session, session)
        self.assertEqual(annotation.user, self.user)
        self.assertEqual(annotation.book, self.book)
        self.book.delete()
        self.assertFalse(ReadingSession.objects.filter(pk=session.pk).exists())
        self.assertFalse(Annotation.objects.filter(pk=annotation.pk).exists())

    def test_session_can_exist_without_saved_progress(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)

        self.assertEqual(session.progress_cfi, "")
        self.assertEqual(session.progress_location_label, "")
        self.assertIsNone(session.progress_updated_at)

    def test_progress_assignment_preserves_location_and_clears_atomically(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)
        cfi = "  epubcfi(/6/8)  "
        label = "  Chapter 08 · 42% · The Blackstaff  "
        updated_at = timezone.now()

        assign_session_progress(
            session=session,
            cfi=cfi,
            location_label=label,
            updated_at=updated_at,
        )
        session.refresh_from_db()
        self.assertEqual(session.progress_cfi, cfi)
        self.assertEqual(session.progress_location_label, label)
        self.assertEqual(session.progress_updated_at, updated_at)

        clear_session_progress(session=session)
        session.refresh_from_db()
        self.assertEqual(session.progress_cfi, "")
        self.assertEqual(session.progress_location_label, "")
        self.assertIsNone(session.progress_updated_at)

    def test_progress_database_constraint_rejects_incomplete_state(self):
        invalid_values = (
            {"progress_location_label": "Chapter 1"},
            {"progress_updated_at": timezone.now()},
            {"progress_cfi": "epubcfi(/6/8)"},
        )
        for values in invalid_values:
            with self.subTest(values=values), self.assertRaises(
                IntegrityError
            ), transaction.atomic():
                ReadingSession.objects.create(
                    user=self.user,
                    book=self.book,
                    **values,
                )

    def test_progress_label_is_optional(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)

        assign_session_progress(session=session, cfi="epubcfi(/6/8)")

        self.assertEqual(session.progress_location_label, "")

    def test_profile_uri_is_not_stored_per_row(self):
        for model in (ReadingSession, Annotation):
            with self.subTest(model=model.__name__), self.assertRaises(
                FieldDoesNotExist
            ):
                model._meta.get_field("profile_version")

    def test_location_labels_are_optional_and_preserved_on_annotations(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)
        bookmark = Annotation.objects.create(
            session=session,
            client_id="unlabeled-bookmark",
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/2)",
        )
        label = "Location 008 · 42% · Appendix B"
        noted_highlight = Annotation.objects.create(
            session=session,
            client_id="labeled-highlight",
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
                client_id="null-location-label",
                kind=Annotation.KIND_BOOKMARK,
                cfi="epubcfi(/6/6)",
                location_label=None,
            )

    def test_database_rejects_invalid_located_record_shapes(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Annotation.objects.create(
                session=session,
                client_id="missing-cfi",
                kind=Annotation.KIND_BOOKMARK,
                cfi="",
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Annotation.objects.create(
                session=session,
                client_id="missing-highlight-text",
                kind=Annotation.KIND_HIGHLIGHT,
                cfi="epubcfi(/6/2)",
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Annotation.objects.create(
                session=session,
                client_id="bookmark-with-note",
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
                    client_id=f"bookmark-with-{field}",
                    kind=Annotation.KIND_BOOKMARK,
                    cfi="epubcfi(/6/4)",
                    **{field: "not allowed"},
                )

    def test_annotation_client_id_is_required_and_unique_within_session(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)
        other_session = ReadingSession.objects.create(
            user=self.user,
            book=Book.objects.create(title="Other Book"),
        )
        Annotation.objects.create(
            session=session,
            client_id="reader-annotation-1",
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/2)",
        )
        Annotation.objects.create(
            session=other_session,
            client_id="reader-annotation-1",
            kind=Annotation.KIND_BOOKMARK,
            cfi="epubcfi(/6/2)",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Annotation.objects.create(
                session=session,
                client_id="reader-annotation-1",
                kind=Annotation.KIND_BOOKMARK,
                cfi="epubcfi(/6/4)",
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Annotation.objects.create(
                session=session,
                client_id="",
                kind=Annotation.KIND_BOOKMARK,
                cfi="epubcfi(/6/6)",
            )

    def test_closed_session_progress_is_immutable(self):
        session = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now(),
        )

        with self.assertRaises(ValidationError):
            assign_session_progress(session=session, cfi="epubcfi(/6/8)")
