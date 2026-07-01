from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response

from core.models import IdempotencyRecord
from library.group_services import ensure_book_public_assignment
from reading.models import Annotation, ReadingSession
from tests.reading.api_test_base import ReadingAPITestBase, ReadingClientBearerAPITestBase
from tests.utils.books import create_file_backed_book
from tests.utils.responses import response_data_dict
from tests.utils.responses import response_data_list


User = get_user_model()


class ReadingAnnotationIdempotencyAPITest(ReadingAPITestBase):
    def test_annotation_create_idempotency_key_allows_safe_retry(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        payload = {
            "session": str(session.id),
            "motivation": Annotation.MOTIVATION_BOOKMARKING,
            "target": {"selector": {"value": "epubcfi(/6/2)"}},
            "body": [],
        }

        r1 = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data=payload,
                format="json",
                HTTP_IDEMPOTENCY_KEY="abc-123",
            ),
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        a1 = response_data_dict(r1)

        r2 = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data=payload,
                format="json",
                HTTP_IDEMPOTENCY_KEY="abc-123",
            ),
        )
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        a2 = response_data_dict(r2)
        self.assertEqual(a1["id"], a2["id"])
        self.assertEqual(Annotation.objects.filter(session=session).count(), 1)
        self.assertEqual(IdempotencyRecord.objects.filter(user=self.user1, key="abc-123").count(), 1)


    def test_annotation_create_idempotency_key_conflicts_on_different_body(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        r1 = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": "epubcfi(/6/2)"}},
                    "body": [],
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY="same-key",
            ),
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)

        r2 = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": "epubcfi(/6/4)"}},
                    "body": [],
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY="same-key",
            ),
        )
        self.assertEqual(r2.status_code, status.HTTP_409_CONFLICT)


    def test_annotation_create_idempotency_key_invalid_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        too_long = "x" * 129
        r1 = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": "epubcfi(/6/2)"}},
                    "body": [],
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY=too_long,
            ),
        )
        self.assertEqual(r1.status_code, status.HTTP_400_BAD_REQUEST)

        r2 = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": "epubcfi(/6/2)"}},
                    "body": [],
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY="   ",
            ),
        )
        self.assertEqual(r2.status_code, status.HTTP_400_BAD_REQUEST)


    def test_annotation_validation_failure_does_not_store_idempotency_record(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        bad = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": "not-a-real-motivation",
                    "target": {},
                    "body": [],
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY="fixable",
            ),
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(IdempotencyRecord.objects.filter(user=self.user1, key="fixable").exists())

        ok = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": "epubcfi(/6/2)"}},
                    "body": [],
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY="fixable",
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)
        self.assertTrue(IdempotencyRecord.objects.filter(user=self.user1, key="fixable").exists())


    def test_idempotency_key_is_scoped_per_user(self):
        self.client.login(username="u1", password="pass1")
        s1 = ReadingSession.objects.create(user=self.user1, book=self.book)
        r1 = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(s1.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": "epubcfi(/6/2)"}},
                    "body": [],
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY="shared-key",
            ),
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)

        # Same key for a different user is independent.
        self.client.logout()
        self.client.login(username="u2", password="pass2")
        other_book = create_file_backed_book(title="Other Book").book
        ensure_book_public_assignment(book=other_book, added_by=None)
        s2 = ReadingSession.objects.create(user=self.user2, book=other_book)
        r2 = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(s2.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": "epubcfi(/6/2)"}},
                    "body": [],
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY="shared-key",
            ),
        )
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(response_data_dict(r1)["id"], response_data_dict(r2)["id"])


    def test_cross_user_session_with_idempotency_key_does_not_store_record(self):
        self.client.login(username="u1", password="pass1")
        # session2 belongs to user2 (setUp fixture).
        r = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(self.session2.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": "epubcfi(/6/2)"}},
                    "body": [],
                },
                format="json",
                HTTP_IDEMPOTENCY_KEY="no-store",
            ),
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(IdempotencyRecord.objects.filter(user=self.user1, key="no-store").exists())


class ReadingAnnotationIdempotencyBearerAPITest(ReadingClientBearerAPITestBase):
    def test_bearer_annotation_create_idempotency_key(self):
        session1 = ReadingSession.objects.create(user=self.user1, book=self.book)
        payload = {
            "session": str(session1.id),
            "motivation": Annotation.MOTIVATION_BOOKMARKING,
            "target": {"selector": {"value": "epubcfi(/6/2)"}},
            "body": [],
        }
        r1 = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data=payload,
                format="json",
                HTTP_AUTHORIZATION=self._auth_header,
                HTTP_IDEMPOTENCY_KEY="bearer-key-1",
            ),
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        a1 = response_data_dict(r1)

        r2 = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data=payload,
                format="json",
                HTTP_AUTHORIZATION=self._auth_header,
                HTTP_IDEMPOTENCY_KEY="bearer-key-1",
            ),
        )
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        a2 = response_data_dict(r2)
        self.assertEqual(a1["id"], a2["id"])

