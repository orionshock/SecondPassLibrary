from __future__ import annotations

from datetime import timedelta
from io import BytesIO

import pytest
from PIL import Image
from django.utils import timezone
from rest_framework import status

from library.cover_services import set_book_cover_from_bytes
from library.groups.book_assignments import ensure_book_public_assignment
from reading.models import Annotation, ReadingProgress, ReadingSession
from tests.reading.api_test_base import ReadingAPITestBase
from tests.utils.books import create_file_backed_book
from tests.utils.responses import assert_response, payload_list, response_data_dict


pytestmark = [pytest.mark.integration]


class ReadingSessionRecentTests(ReadingAPITestBase):
    def test_recent_sessions_endpoint_limits_filters_active_and_orders_by_last_activity(
        self,
    ):
        self.client.login(username="u1", password="pass1")

        book2 = create_file_backed_book(title="Book 2").book
        ensure_book_public_assignment(book=book2, added_by=None)

        img = Image.new("RGB", (20, 30), color=(1, 2, 3))
        bio = BytesIO()
        img.save(bio, format="PNG")
        set_book_cover_from_bytes(book=book2, data=bio.getvalue(), source="manual")

        s1 = ReadingSession.objects.create(
            user=self.user1,
            book=self.book,
            is_active=True,
            status=ReadingSession.STATUS_ACTIVE,
        )
        s2 = ReadingSession.objects.create(
            user=self.user1,
            book=book2,
            is_active=True,
            status=ReadingSession.STATUS_ACTIVE,
        )

        # Exclude closed sessions.
        closed = ReadingSession.objects.create(
            user=self.user1,
            book=book2,
            is_active=False,
            status=ReadingSession.STATUS_COMPLETED,
        )

        # Make s1 more recent via progress.
        ReadingProgress.objects.create(session=s1, current_location={"cfi": "/6/2"})
        ReadingProgress.objects.filter(session=s1).update(updated_at=timezone.now())

        # Make s2 more recent via annotation.
        a = Annotation.objects.create(
            session=s2,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            book=book2,
            selector_value="epubcfi(/6/4)",
        )
        Annotation.objects.filter(pk=a.pk).update(
            updated_at=timezone.now() + timedelta(seconds=5)
        )

        r = assert_response(self.client.get("/api/v1/reading/sessions/recent/"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = response_data_dict(r)
        self.assertIn("count", body)
        self.assertIn("results", body)
        results = payload_list(body, "results")
        self.assertLessEqual(len(results), 10)

        # Active-only and unique-by-book.
        session_ids = {row["session"]["id"] for row in results}
        self.assertNotIn(str(closed.id), session_ids)

        # Ordered: s2 should come before s1 due to newer annotation.
        self.assertEqual(results[0]["session"]["id"], str(s2.id))
        self.assertEqual(results[1]["session"]["id"], str(s1.id))
        self.assertIn("name", results[0]["session"])
        self.assertIn("progression", results[0]["session"])
        self.assertIsInstance(results[0]["book"]["cover_url"], str)
        self.assertTrue(
            str(results[0]["book"]["cover_url"]).startswith("http://testserver/")
        )
        self.assertEqual(results[1]["book"]["cover_url"], None)

        r2 = assert_response(
            self.client.get("/api/v1/reading/sessions/recent/?limit=1")
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        results2 = payload_list(response_data_dict(r2), "results")
        self.assertEqual(len(results2), 1)

        bad = assert_response(
            self.client.get("/api/v1/reading/sessions/recent/?limit=0")
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
