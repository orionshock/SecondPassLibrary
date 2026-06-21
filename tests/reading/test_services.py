from django.contrib.auth import get_user_model
from django.test import TestCase

from reading.models import ReadingProgress, ReadingSession
from reading.services import (
    get_or_create_active_session,
    get_or_create_progress,
    start_over_book,
    update_progress,
)
from tests.reading.utils import IsolatedUserdataMixin
from tests.utils.books import create_file_backed_book


User = get_user_model()


class ReadingServicesTest(IsolatedUserdataMixin, TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reader", password="testpass", email="reader@example.com"
        )
        self.book = create_file_backed_book(title="Test Book").book

    def test_get_or_create_active_session_is_idempotent(self):
        s1 = get_or_create_active_session(user=self.user, book=self.book)
        self.assertTrue(s1.is_active)
        self.assertEqual(s1.status, ReadingSession.STATUS_ACTIVE)

        s2 = get_or_create_active_session(user=self.user, book=self.book)
        self.assertEqual(s2.id, s1.id)

    def test_start_over_archives_old_and_creates_new(self):
        old = get_or_create_active_session(user=self.user, book=self.book)
        ReadingProgress.objects.create(session=old, current_location={"cfi": "/6/2"})

        new = start_over_book(user=self.user, book=self.book, name="Second pass")
        self.assertNotEqual(new.id, old.id)
        self.assertTrue(new.is_active)
        self.assertEqual(new.name, "Second pass")

        old.refresh_from_db()
        self.assertFalse(old.is_active)
        self.assertEqual(old.status, ReadingSession.STATUS_ARCHIVED)
        self.assertTrue(ReadingProgress.objects.filter(session=old).exists())

    def test_get_or_create_progress_is_idempotent(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)
        p1 = get_or_create_progress(session=session)
        self.assertEqual(p1.current_location, {})

        p2 = get_or_create_progress(session=session)
        self.assertEqual(p2.id, p1.id)

    def test_update_progress_creates_and_updates(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book)

        progress = update_progress(
            session=session,
            current_location={"cfi": "/6/4"},
            progression=0.5,
        )
        self.assertEqual(progress.session.id, session.id)
        self.assertEqual(progress.current_location["format"], "epub")
        self.assertEqual(progress.current_location["cfi"], "/6/4")
        self.assertEqual(progress.progression, 0.5)

        progress2 = update_progress(
            session=session,
            current_location={"cfi": "/6/6"},
            progression=0.75,
        )
        self.assertEqual(progress2.id, progress.id)
        self.assertEqual(progress2.current_location["format"], "epub")
        self.assertEqual(progress2.current_location["cfi"], "/6/6")
        self.assertEqual(progress2.progression, 0.75)
