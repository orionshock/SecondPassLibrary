from __future__ import annotations

import pytest
from rest_framework import status

from library.models import BookGroupAssignment, LibraryGroup
from reading.models import Annotation, ReadingProgress, ReadingSession
from reading.profile.validation import CURRENT_READING_PROFILE_VERSION
from tests.reading.api_test_base import ReadingAPITestBase
from tests.utils.books import create_file_backed_book
from tests.utils.responses import (
    assert_response,
    payload_dict,
    payload_list,
    response_data_dict,
)


pytestmark = [pytest.mark.integration]


class ReadingSessionOpenActiveTests(ReadingAPITestBase):
    def test_get_create_active_session(self):
        self.client.login(username="u1", password="pass1")
        url = f"/api/v1/reading/books/{self.book.id}/active-session/"
        response = assert_response(self.client.get(url))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_dict(response)
        self.assertEqual(data["book"], self.book.id)
        self.assertTrue(data["is_active"])

        response2 = assert_response(self.client.get(url))
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        data2 = response_data_dict(response2)
        self.assertEqual(data2["id"], data["id"])

    def test_open_endpoint_creates_session_progress_and_returns_annotations(self):
        self.client.login(username="u1", password="pass1")
        url = f"/api/v1/reading/books/{self.book.id}/open/"

        resp = assert_response(self.client.post(url, data={}, format="json"))
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        data = response_data_dict(resp)
        self.assertEqual(data["profile_version"], CURRENT_READING_PROFILE_VERSION)
        self.assertIn("session", data)
        self.assertIn("progress", data)
        self.assertIn("annotations", data)

        session_id = data["session"]["id"]
        self.assertTrue(
            ReadingSession.objects.filter(id=session_id, user=self.user1).exists()
        )
        self.assertTrue(ReadingProgress.objects.filter(session_id=session_id).exists())

        # Add annotations (including a deleted one) and confirm /open/ returns non-deleted.
        session = ReadingSession.objects.get(id=session_id)
        keep = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/2)",
            highlight_text="keep",
            comment_text="keep",
        )
        deleted = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/4)",
            highlight_text="delete",
            comment_text="delete",
            is_deleted=True,
        )

        resp2 = assert_response(self.client.post(url, data={}, format="json"))
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        data2 = response_data_dict(resp2)
        results = payload_list(payload_dict(data2, "annotations"), "results")
        ids = {row["id"] for row in results}
        self.assertIn(str(keep.id), ids)
        self.assertNotIn(str(deleted.id), ids)

    def test_open_endpoint_returns_existing_active_session_without_duplication(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(
            user=self.user1, book=self.book, is_active=True
        )

        url = f"/api/v1/reading/books/{self.book.id}/open/"
        resp = assert_response(self.client.post(url, data={}, format="json"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = response_data_dict(resp)
        self.assertEqual(data["session"]["id"], str(session.id))
        self.assertEqual(
            ReadingSession.objects.filter(
                user=self.user1, book=self.book, is_active=True
            ).count(),
            1,
        )

    def test_active_session_404_for_inaccessible_book_without_existing_session(self):
        self.client.login(username="u1", password="pass1")
        group = LibraryGroup.objects.create(name="Hidden")
        restricted = create_file_backed_book(
            title="Restricted2", assign_public=False
        ).book
        BookGroupAssignment.objects.create(book=restricted, group=group)

        url = f"/api/v1/reading/books/{restricted.id}/active-session/"
        resp = assert_response(self.client.get(url))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(
            ReadingSession.objects.filter(user=self.user1, book=restricted).exists()
        )

    def test_open_404_for_inaccessible_book_without_existing_session(self):
        self.client.login(username="u1", password="pass1")
        group = LibraryGroup.objects.create(name="HiddenOpen")
        restricted = create_file_backed_book(
            title="RestrictedOpen404", assign_public=False
        ).book
        BookGroupAssignment.objects.create(book=restricted, group=group)

        url = f"/api/v1/reading/books/{restricted.id}/open/"
        resp = assert_response(self.client.post(url, data={}, format="json"))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(
            ReadingSession.objects.filter(user=self.user1, book=restricted).exists()
        )
