from __future__ import annotations

import pytest
from rest_framework import status

from reading.models import Annotation, ReadingSession
from tests.reading.api_test_base import ReadingAPITestBase
from tests.utils.responses import assert_response, response_data_dict


pytestmark = [pytest.mark.integration]


class ReadingAnnotationsBatchTests(ReadingAPITestBase):
    def test_batch_create_multiple_annotations(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        resp = assert_response(
            self.client.post(
                "/api/v1/reading/annotations/batch/",
                data={
                    "session": str(session.id),
                    "annotations": [
                        {
                            "client_id": "a",
                            "kind": "bookmark",
                            "selector": {"kind": "epub_cfi", "value": "/6/2"},
                        },
                        {
                            "client_id": "b",
                            "kind": "highlight",
                            "selector": {"kind": "epub_cfi", "value": "/6/4"},
                            "highlight_text": "hello",
                        },
                    ],
                },
                format="json",
            ),
        )

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        data = response_data_dict(resp)
        self.assertEqual([row["client_id"] for row in data["annotations"]], ["a", "b"])
        self.assertEqual(Annotation.objects.filter(session=session).count(), 2)

    def test_batch_create_is_all_or_nothing(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        resp = assert_response(
            self.client.post(
                "/api/v1/reading/annotations/batch/",
                data={
                    "session": str(session.id),
                    "annotations": [
                        {
                            "kind": "bookmark",
                            "selector": {"kind": "epub_cfi", "value": "/6/2"},
                        },
                        {
                            "kind": "highlight",
                            "selector": {"kind": "epub_cfi", "value": "/6/4"},
                        },
                    ],
                },
                format="json",
            ),
        )

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Annotation.objects.filter(session=session).count(), 0)
