from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from library.models import Book
from reading.models import Annotation, ReadingProgress, ReadingSession
from tests.reading.utils import IsolatedUserdataMixin


User = get_user_model()


class ReadingModelsTest(IsolatedUserdataMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reader", password="testpass", email="reader@example.com"
        )
        self.book = Book.objects.create(title="Test Book")

    def test_create_reading_session(self):
        session = ReadingSession.objects.create(
            user=self.user, book=self.book, name="First pass"
        )
        self.assertIn("reader", str(session))
        self.assertIn("Test Book", str(session))
        self.assertIn("First pass", str(session))

    def test_unique_active_session_per_book(self):
        ReadingSession.objects.create(user=self.user, book=self.book)
        with self.assertRaises(IntegrityError):
            ReadingSession.objects.create(user=self.user, book=self.book)

    def test_completed_session_allowed(self):
        ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_COMPLETED,
            is_active=False,
        )

    def test_archived_session_allowed(self):
        ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_ARCHIVED,
            is_active=False,
        )

    def test_create_progress_for_session(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)
        progress = ReadingProgress.objects.create(
            session=session,
            current_location={"chapter": "c1", "offset": 12},
            progression=0.25,
        )
        self.assertIn("Progress:", str(progress))
        self.assertIn("Test Book", str(progress))

    def test_create_annotation(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)
        annotation = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            target={"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/2[chap]!/4/2/6)"}},
            body=[{"type": "TextualBody", "purpose": "describing", "value": "Hello world"}],
        )
        self.assertIn("Highlighting", str(annotation))
        self.assertIn("Test Book", str(annotation))

    def test_annotation_motivation_choices(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)

        highlight = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            target={"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/2)"}},
            body=[{"type": "TextualBody", "purpose": "highlighting", "value": "yellow"}],
        )
        note = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_COMMENTING,
            target={"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/4)"}},
            body=[{"type": "TextualBody", "purpose": "commenting", "value": "n"}],
        )
        bookmark = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            target={"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/6)"}},
            body=[],
        )

        self.assertEqual(highlight.motivation, "highlighting")
        self.assertEqual(note.motivation, "commenting")
        self.assertEqual(bookmark.motivation, "bookmarking")
