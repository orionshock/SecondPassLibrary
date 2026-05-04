from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from library.models import Book

from .models import Annotation, Device, ReadingProgress, ReadingSession


User = get_user_model()


class ReadingModelsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reader", password="testpass", email="reader@example.com"
        )
        self.book = Book.objects.create(title="Test Book")

    def test_create_device(self):
        device = Device.objects.create(
            user=self.user, name="My Phone", device_type=Device.TYPE_MOBILE
        )
        self.assertIn("My Phone", str(device))
        self.assertIn("Mobile", str(device))

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
        device = Device.objects.create(
            user=self.user, name="Web", device_type=Device.TYPE_WEB
        )
        progress = ReadingProgress.objects.create(
            session=session,
            device=device,
            locator={"chapter": "c1", "offset": 12},
            progression=0.25,
        )
        self.assertIn("Progress:", str(progress))
        self.assertIn("Test Book", str(progress))

    def test_create_annotation(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)
        annotation = Annotation.objects.create(
            session=session,
            kind=Annotation.KIND_HIGHLIGHT,
            locator={"cfi": "/6/2[chap]!/4/2/6"},
            selected_text="Hello world",
            color="yellow",
        )
        self.assertIn("Highlight", str(annotation))
        self.assertIn("Test Book", str(annotation))

    def test_annotation_kind_choices(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)

        highlight = Annotation.objects.create(
            session=session, kind=Annotation.KIND_HIGHLIGHT, locator={"cfi": "/6/2"}
        )
        note = Annotation.objects.create(
            session=session,
            kind=Annotation.KIND_NOTE,
            locator={"cfi": "/6/4"},
            note="n",
        )
        bookmark = Annotation.objects.create(
            session=session, kind=Annotation.KIND_BOOKMARK, locator={"cfi": "/6/6"}
        )

        self.assertEqual(highlight.kind, "highlight")
        self.assertEqual(note.kind, "note")
        self.assertEqual(bookmark.kind, "bookmark")
