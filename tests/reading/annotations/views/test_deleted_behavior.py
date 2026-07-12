from __future__ import annotations

import pytest
from rest_framework import status

from reading.models import Annotation, ReadingSession
from tests.reading.api_test_base import ReadingClientBearerAPITestBase
from tests.utils.responses import assert_response, response_data_list


pytestmark = [pytest.mark.integration]


class ReadingAnnotationsDeletedBehaviorTests(ReadingClientBearerAPITestBase):
    def test_soft_deleted_annotations_hidden_by_default_and_opt_in_include_deleted(
        self,
    ):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        a1 = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/2)",
            highlight_text="keep",
            comment_text="keep",
        )
        a2 = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/4)",
            highlight_text="delete",
            comment_text="delete",
        )

        deleted = assert_response(
            self.client.delete(f"/api/v1/reading/annotations/{a2.id}/")
        )
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        a2.refresh_from_db()
        self.assertTrue(a2.is_deleted)

        listing = assert_response(
            self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}")
        )
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response_data_list(listing)}
        self.assertIn(str(a1.id), ids)
        self.assertNotIn(str(a2.id), ids)

        listing2 = assert_response(
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&include_deleted=true"
            ),
        )
        self.assertEqual(listing2.status_code, status.HTTP_200_OK)
        ids2 = {row["id"] for row in response_data_list(listing2)}
        self.assertIn(str(a1.id), ids2)
        self.assertIn(str(a2.id), ids2)

        self.assertEqual(
            self.client.get(f"/api/v1/reading/annotations/{a2.id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(
                f"/api/v1/reading/annotations/{a2.id}/?include_deleted=true"
            ).status_code,
            status.HTTP_200_OK,
        )
