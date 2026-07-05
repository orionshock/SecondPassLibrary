from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.core.exceptions import ValidationError

from reading.models import (
    Annotation,
    ReadingProgress,
    ReadingSession,
    SELECTOR_KIND_EPUB_CFI,
)
from tests.testenv.filesystem import IsolatedUserdataMixin
from tests.utils.books import create_file_backed_book


User = get_user_model()


class ReadingModelsTest(IsolatedUserdataMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reader", password="testpass", email="reader@example.com"
        )
        self.book = create_file_backed_book(title="Test Book").book

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
            book=self.book,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            selector_kind=SELECTOR_KIND_EPUB_CFI,
            selector_value="epubcfi(/6/2[chap]!/4/2/6)",
            highlight_text="Hello world",
        )
        self.assertIn("Highlight", str(annotation))
        self.assertIn("Test Book", str(annotation))

    def test_annotation_motivation_choices(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)

        highlight = Annotation.objects.create(
            session=session,
            book=self.book,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            selector_kind=SELECTOR_KIND_EPUB_CFI,
            selector_value="epubcfi(/6/2)",
            highlight_text="yellow",
        )
        highlight_with_note = Annotation.objects.create(
            session=session,
            book=self.book,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            selector_kind=SELECTOR_KIND_EPUB_CFI,
            selector_value="epubcfi(/6/4)",
            highlight_text="sel",
            comment_text="n",
        )
        bookmark = Annotation.objects.create(
            session=session,
            book=self.book,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            anchor_kind=Annotation.ANCHOR_KIND_BOOKMARK,
            selector_kind=SELECTOR_KIND_EPUB_CFI,
            selector_value="epubcfi(/6/6)",
        )

        self.assertEqual(highlight.anchor_kind, Annotation.ANCHOR_KIND_HIGHLIGHT)
        self.assertEqual(
            highlight_with_note.anchor_kind, Annotation.ANCHOR_KIND_HIGHLIGHT
        )
        self.assertEqual(bookmark.anchor_kind, Annotation.ANCHOR_KIND_BOOKMARK)

    def test_annotation_full_clean_rejects_unsupported_selector_kind(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)
        ann = Annotation(
            session=session,
            book=self.book,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            selector_kind="weird_kind",
            selector_value="epubcfi(/6/2)",
        )
        with self.assertRaises(ValidationError):
            ann.full_clean()

    def test_annotation_full_clean_rejects_book_mismatch(self):
        other = create_file_backed_book(title="Other Book").book
        session = ReadingSession.objects.create(user=self.user, book=self.book)
        ann = Annotation(
            session=session,
            book=other,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            selector_kind=SELECTOR_KIND_EPUB_CFI,
            selector_value="epubcfi(/6/2)",
        )
        with self.assertRaises(ValidationError):
            ann.full_clean()
