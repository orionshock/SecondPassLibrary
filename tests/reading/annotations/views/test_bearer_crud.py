from __future__ import annotations

import pytest
from rest_framework import status

from library.models import LibraryGroupMembership
from reading.models import Annotation, ReadingSession
from tests.reading.annotations.helpers import bookmark_payload, highlight_payload
from tests.reading.api_test_base import ReadingClientBearerAPITestBase
from tests.utils.responses import assert_response, response_data_dict, response_data_list


pytestmark = [pytest.mark.integration]


class ReadingBearerAnnotationCrudTests(ReadingClientBearerAPITestBase):
    def test_bearer_batch_is_user_scoped_and_requires_book_visibility(self):
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        response = assert_response(
            self.client.post(
                "/api/v1/reading/annotations/batch/",
                data={
                    "session": str(session.id),
                    "annotations": [
                        {
                            "client_id": "reader-1",
                            "kind": "bookmark",
                            "selector": {
                                "kind": "epub_cfi",
                                "value": "epubcfi(/6/2)",
                            },
                        }
                    ],
                },
                format="json",
                HTTP_AUTHORIZATION=self._auth_header,
            )
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        rows = response_data_dict(response)["annotations"]
        self.assertEqual(rows[0]["client_id"], "reader-1")
        self.assertEqual(Annotation.objects.filter(session=session).count(), 1)

        other_user = self.client.post(
            "/api/v1/reading/annotations/batch/",
            data={
                "session": str(self.session2.id),
                "annotations": [
                    {
                        "kind": "bookmark",
                        "selector": {
                            "kind": "epub_cfi",
                            "value": "epubcfi(/6/4)",
                        },
                    }
                ],
            },
            format="json",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(other_user.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Annotation.objects.filter(session=self.session2).count(), 1)

        LibraryGroupMembership.objects.filter(user=self.user1).delete()
        inaccessible = self.client.post(
            "/api/v1/reading/annotations/batch/",
            data={
                "session": str(session.id),
                "annotations": [
                    {
                        "kind": "bookmark",
                        "selector": {
                            "kind": "epub_cfi",
                            "value": "epubcfi(/6/6)",
                        },
                    }
                ],
            },
            format="json",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(inaccessible.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Annotation.objects.filter(session=session).count(), 1)

    def test_bearer_annotations_are_user_scoped(self):
        session1 = ReadingSession.objects.create(user=self.user1, book=self.book)

        create = assert_response(
            self.client.post(
                "/api/v1/reading/annotations/",
                data=highlight_payload(session1),
                format="json",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        ann_id = response_data_dict(create)["id"]

        list_all = assert_response(
            self.client.get(
                "/api/v1/reading/annotations/",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(list_all.status_code, status.HTTP_200_OK)
        ids = {a["id"] for a in response_data_list(list_all)}
        self.assertIn(ann_id, ids)
        self.assertNotIn(str(self.annotation2.id), ids)

        other_get = self.client.get(
            f"/api/v1/reading/annotations/{self.annotation2.id}/",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(other_get.status_code, status.HTTP_404_NOT_FOUND)
        other_del = self.client.delete(
            f"/api/v1/reading/annotations/{self.annotation2.id}/",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(other_del.status_code, status.HTTP_404_NOT_FOUND)

        bad_create = self.client.post(
            "/api/v1/reading/annotations/",
            data=highlight_payload(self.session2),
            format="json",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(bad_create.status_code, status.HTTP_400_BAD_REQUEST)

        bad_device_field = self.client.post(
            "/api/v1/reading/annotations/",
            data={**bookmark_payload(session1), "device": "nope"},
            format="json",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(bad_device_field.status_code, status.HTTP_400_BAD_REQUEST)
