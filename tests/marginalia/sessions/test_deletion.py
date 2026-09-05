from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.operational_logging import user_uuid
from library.models import (
    Book,
    BookGroupAssignment,
    LibraryGroup,
    LibraryGroupMembership,
)
from library.queries import visible_books_for_user
from marginalia.models import Annotation, ReadingSession
from marginalia.sessions.deletion import delete_owned_session


User = get_user_model()


class DeleteOwnedSessionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="testpass")
        self.other = User.objects.create_user(username="other", password="testpass")
        self.group = LibraryGroup.objects.create(name="Readers")
        self.membership = LibraryGroupMembership.objects.create(
            user=self.user,
            group=self.group,
        )
        self.book = Book.objects.create(title="Deletion Book")
        BookGroupAssignment.objects.create(book=self.book, group=self.group)
        self.active = ReadingSession.objects.create(user=self.user, book=self.book)
        self.closed = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_CLOSED,
            closed_at=timezone.now(),
        )
        self.active_annotation = self._annotation(self.active, "active")
        self.soft_deleted_annotation = self._annotation(
            self.active,
            "soft-deleted",
            is_deleted=True,
        )
        self.closed_annotation = self._annotation(self.closed, "closed")

    def _annotation(
        self,
        session: ReadingSession,
        client_id: str,
        *,
        is_deleted: bool = False,
    ) -> Annotation:
        return Annotation.objects.create(
            session=session,
            client_id=client_id,
            kind=Annotation.KIND_BOOKMARK,
            cfi=f"epubcfi(/6/{client_id})",
            is_deleted=is_deleted,
        )

    def test_owner_deletes_active_session_with_only_its_cascading_annotations(self):
        active_id = self.active.pk
        result = delete_owned_session(user=self.user, session_id=self.active.pk)

        self.assertIsNone(result)
        self.assertFalse(ReadingSession.objects.filter(pk=active_id).exists())
        self.assertFalse(
            Annotation.objects.filter(
                pk__in=[self.active_annotation.pk, self.soft_deleted_annotation.pk]
            ).exists()
        )
        self.assertTrue(Book.objects.filter(pk=self.book.pk).exists())
        self.closed.refresh_from_db()
        self.assertEqual(self.closed.status, ReadingSession.STATUS_CLOSED)
        self.assertTrue(Annotation.objects.filter(pk=self.closed_annotation.pk).exists())
        self.assertFalse(
            ReadingSession.objects.filter(
                user=self.user,
                book=self.book,
                status=ReadingSession.STATUS_ACTIVE,
            ).exists()
        )

        replacement = ReadingSession.objects.create(user=self.user, book=self.book)
        self.assertEqual(replacement.status, ReadingSession.STATUS_ACTIVE)
        self.assertEqual(
            ReadingSession.objects.filter(user=self.user, book=self.book).count(),
            2,
        )

    def test_owner_deletes_closed_session_without_mutating_active_session(self):
        closed_id = self.closed.pk
        active_updated_at = self.active.updated_at

        delete_owned_session(user=self.user, session_id=self.closed.pk)

        self.assertFalse(ReadingSession.objects.filter(pk=closed_id).exists())
        self.assertFalse(Annotation.objects.filter(pk=self.closed_annotation.pk).exists())
        self.active.refresh_from_db()
        self.assertEqual(self.active.status, ReadingSession.STATUS_ACTIVE)
        self.assertEqual(self.active.updated_at, active_updated_at)

    def test_owner_deletes_session_after_losing_book_visibility(self):
        active_id = self.active.pk
        self.membership.delete()
        self.assertFalse(
            visible_books_for_user(self.user, cached=False)
            .filter(pk=self.book.pk)
            .exists()
        )

        delete_owned_session(user=self.user, session_id=self.active.pk)

        self.assertFalse(ReadingSession.objects.filter(pk=active_id).exists())
        self.assertTrue(Book.objects.filter(pk=self.book.pk).exists())

    def test_foreign_and_missing_sessions_raise_the_same_owned_lookup_error(self):
        foreign = ReadingSession.objects.create(user=self.other, book=self.book)
        missing_id = "00000000-0000-0000-0000-000000000000"

        with self.assertRaises(ReadingSession.DoesNotExist) as foreign_error:
            delete_owned_session(user=self.user, session_id=foreign.pk)
        with self.assertRaises(ReadingSession.DoesNotExist) as missing_error:
            delete_owned_session(user=self.user, session_id=missing_id)

        self.assertEqual(str(foreign_error.exception), str(missing_error.exception))
        self.assertTrue(ReadingSession.objects.filter(pk=foreign.pk).exists())

    def test_success_log_is_deferred_until_commit_and_uses_cascade_count(self):
        session_id = str(self.active.pk)
        book_id = str(self.book.pk)
        owner_id = user_uuid(self.user)

        with patch("marginalia.sessions.deletion.logger.info") as log_info:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                delete_owned_session(user=self.user, session_id=self.active.pk)

            log_info.assert_not_called()
            self.assertEqual(len(callbacks), 1)
            callbacks[0]()
            log_info.assert_called_once_with(
                "Marginalia Reading Session deleted: session=%s owner=%s book=%s "
                "previous_status=%s annotation_count=%d",
                session_id,
                owner_id,
                book_id,
                ReadingSession.STATUS_ACTIVE,
                2,
            )
