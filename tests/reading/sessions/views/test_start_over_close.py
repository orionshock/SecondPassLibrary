from __future__ import annotations

import pytest
from rest_framework import status

from library.models import BookGroupAssignment, LibraryGroup
from reading.models import Annotation, ReadingSession
from reading.profile.validation import CURRENT_READING_PROFILE_VERSION
from tests.reading.api_test_base import ReadingAPITestBase
from tests.utils.books import create_file_backed_book
from tests.utils.responses import assert_response, response_data_dict


pytestmark = [pytest.mark.integration]


class ReadingSessionStartOverCloseTests(ReadingAPITestBase):
    def test_start_over_requires_book_access(self):
        self.client.login(username="u1", password="pass1")
        group = LibraryGroup.objects.create(name="Hidden")
        restricted = create_file_backed_book(
            title="Restricted3", assign_public=False
        ).book
        BookGroupAssignment.objects.create(book=restricted, group=group)

        url = f"/api/v1/reading/books/{restricted.id}/start-over/"
        resp = assert_response(self.client.post(url, data={}, format="json"))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_start_over_returns_open_response_shape_and_archives_old_active(self):
        self.client.login(username="u1", password="pass1")

        old = ReadingSession.objects.create(
            user=self.user1, book=self.book, is_active=True
        )
        Annotation.objects.create(
            session=old,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            book=self.book,
            selector_value="epubcfi(/6/2)",
        )

        url = f"/api/v1/reading/books/{self.book.id}/start-over/"
        resp = assert_response(
            self.client.post(url, data={"name": "Reread"}, format="json")
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        data = response_data_dict(resp)
        self.assertEqual(data["profile_version"], CURRENT_READING_PROFILE_VERSION)
        self.assertIn("session", data)
        self.assertIn("progress", data)
        self.assertIn("annotations", data)

        new_session_id = data["session"]["id"]
        self.assertNotEqual(str(old.id), str(new_session_id))
        self.assertEqual(str(data["progress"]["session"]), str(new_session_id))
        self.assertEqual(data["annotations"]["results"], [])

        old.refresh_from_db(from_queryset=None)
        self.assertFalse(old.is_active)
        self.assertEqual(old.status, ReadingSession.STATUS_ARCHIVED)

        new = ReadingSession.objects.get(pk=new_session_id)
        self.assertTrue(new.is_active)
        self.assertEqual(new.status, ReadingSession.STATUS_ACTIVE)

    def test_close_session_closes_active_idempotent_and_allows_open_new(self):
        self.client.login(username="u1", password="pass1")

        session = ReadingSession.objects.create(
            user=self.user1, book=self.book, is_active=True
        )
        ann = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            book=self.book,
            selector_value="epubcfi(/6/2)",
        )

        close1 = assert_response(
            self.client.post(
                f"/api/v1/reading/sessions/{session.id}/close/",
                data={},
                format="json",
            )
        )
        self.assertEqual(close1.status_code, status.HTTP_200_OK)
        data1 = response_data_dict(close1)
        self.assertEqual(data1["id"], str(session.id))
        self.assertEqual(data1["status"], ReadingSession.STATUS_COMPLETED)
        self.assertFalse(data1["is_active"])
        self.assertIsNotNone(data1["completed_at"])

        session.refresh_from_db(from_queryset=None)
        completed_at1 = session.completed_at
        self.assertIsNotNone(completed_at1)

        # Idempotent: closing again does not change completed_at.
        close2 = assert_response(
            self.client.post(
                f"/api/v1/reading/sessions/{session.id}/close/",
                data={},
                format="json",
            )
        )
        self.assertEqual(close2.status_code, status.HTTP_200_OK)
        session.refresh_from_db(from_queryset=None)
        self.assertEqual(session.completed_at, completed_at1)

        # After close, progress writes and annotation create/update are rejected.
        prog = assert_response(
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/progress/",
                data={"current_location": {"cfi": "/6/2"}},
                format="json",
            ),
        )
        self.assertEqual(prog.status_code, status.HTTP_400_BAD_REQUEST)

        ann_create = assert_response(
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "kind": "bookmark",
                    "selector": {"kind": "epub_cfi", "value": "epubcfi(/6/4)"},
                },
                format="json",
            ),
        )
        self.assertEqual(ann_create.status_code, status.HTTP_400_BAD_REQUEST)

        ann_update = assert_response(
            self.client.patch(
                f"/api/v1/reading/annotations/{ann.id}/",
                data={
                    "comment_text": "new",
                },
                format="json",
            ),
        )
        self.assertEqual(ann_update.status_code, status.HTTP_400_BAD_REQUEST)

        # Annotation delete is a write and is blocked on closed sessions.
        del_resp = assert_response(
            self.client.delete(f"/api/v1/reading/annotations/{ann.id}/")
        )
        self.assertEqual(del_resp.status_code, status.HTTP_400_BAD_REQUEST)
        ann.refresh_from_db()
        self.assertFalse(ann.is_deleted)

        # Opening the book again creates a new active session (since none is active now).
        open_resp = assert_response(
            self.client.post(
                f"/api/v1/reading/books/{self.book.id}/open/",
                data={},
                format="json",
            )
        )
        self.assertIn(
            open_resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED)
        )
        open_data = response_data_dict(open_resp)
        self.assertNotEqual(open_data["session"]["id"], str(session.id))
        self.assertTrue(open_data["session"]["is_active"])
        self.assertEqual(open_data["session"]["status"], ReadingSession.STATUS_ACTIVE)
