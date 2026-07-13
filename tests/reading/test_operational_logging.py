from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from reading.models import ReadingProgress, ReadingSession
from reading.services import create_annotation
from tests.utils.books import create_file_backed_book


User = get_user_model()


class RoutineReadingOperationalLoggingTests(TestCase):
    def test_routine_session_progress_and_annotation_actions_remain_info_silent(self):
        user = User.objects.create_user(username="reader", password="pw")
        book = create_file_backed_book(title="Quiet Book", epub_bytes=b"quiet").book

        with self.assertNoLogs("reading", level="INFO"):
            session = ReadingSession.objects.create(user=user, book=book)
            ReadingProgress.objects.create(
                session=session,
                current_location={"cfi": "epubcfi(/6/2)"},
                progression=0.5,
            )
            create_annotation(
                session=session,
                anchor_kind="highlight",
                selector_kind="epub_cfi",
                selector_value="epubcfi(/6/4)",
                highlight_text="quiet quote",
                comment_text="quiet note",
            )
