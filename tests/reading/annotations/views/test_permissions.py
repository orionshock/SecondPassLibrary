from __future__ import annotations

import pytest
from rest_framework import status

from reading.models import Annotation, ReadingSession
from tests.reading.annotations.helpers import (
    LostAccessAnnotationMixin,
    bookmark_payload,
)
from tests.reading.api_test_base import ReadingAPITestBase
from tests.utils.responses import assert_response, response_data_list


pytestmark = [pytest.mark.integration]


class ReadingAnnotationsPermissionTests(LostAccessAnnotationMixin, ReadingAPITestBase):
    def test_annotations_list_includes_owned_annotations_after_book_access_lost(self):
        _user, session, annotation = self._make_lost_access_session_with_annotation()
        self.client.login(username="lostann", password="pass")

        resp = assert_response(
            self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}")
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response_data_list(resp)}
        self.assertIn(str(annotation.id), ids)

    def test_annotation_create_requires_current_book_access(self):
        _user, session, _annotation = self._make_lost_access_session_with_annotation()
        self.client.login(username="lostann", password="pass")

        resp = assert_response(
            self.client.post(
                "/api/v1/reading/annotations/",
                data=bookmark_payload(session, "epubcfi(/6/4)"),
                format="json",
            ),
        )

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Annotation.objects.filter(session=session).count(), 1)

    def test_annotation_patch_requires_current_book_access(self):
        _user, _session, annotation = self._make_lost_access_session_with_annotation()
        self.client.login(username="lostann", password="pass")

        resp = assert_response(
            self.client.patch(
                f"/api/v1/reading/annotations/{annotation.id}/",
                data={"comment_text": "new"},
                format="json",
            ),
        )

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        annotation.refresh_from_db()
        self.assertEqual(annotation.comment_text, "old")

    def test_annotation_delete_requires_current_book_access_and_open_session(self):
        _user, session, annotation = self._make_lost_access_session_with_annotation()
        self.client.login(username="lostann", password="pass")

        no_access = assert_response(
            self.client.delete(f"/api/v1/reading/annotations/{annotation.id}/")
        )
        self.assertEqual(no_access.status_code, status.HTTP_403_FORBIDDEN)
        annotation.refresh_from_db()
        self.assertFalse(annotation.is_deleted)

        session.status = ReadingSession.STATUS_COMPLETED
        session.is_active = False
        session.save(update_fields=["status", "is_active", "updated_at"])

        closed = assert_response(
            self.client.delete(f"/api/v1/reading/annotations/{annotation.id}/")
        )
        self.assertEqual(closed.status_code, status.HTTP_400_BAD_REQUEST)
        annotation.refresh_from_db()
        self.assertFalse(annotation.is_deleted)
