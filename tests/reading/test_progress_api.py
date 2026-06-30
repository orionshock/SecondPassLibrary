from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response

from reading.models import ReadingProgress, ReadingSession
from reading.profile import (
    CURRENT_READING_PROFILE_VERSION,
    MAX_CURRENT_LOCATION_JSON_BYTES,
)
from tests.reading.api_test_base import ReadingAPITestBase, ReadingClientBearerAPITestBase


User = get_user_model()


def _response_data_dict(response: Response) -> dict[str, Any]:
    data = response.data
    assert data is not None
    assert isinstance(data, dict)
    return cast(dict[str, Any], data)


def _response_data_list(response: Response) -> list[Any]:
    data = response.data
    assert data is not None
    if isinstance(data, dict) and "results" in data:
        results = data["results"]
        assert isinstance(results, list)
        return cast(list[Any], results)
    assert isinstance(data, list)
    return cast(list[Any], data)

class ReadingProgressAPITest(ReadingAPITestBase):
    def test_active_session_progress_get_still_lazily_creates_progress(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        resp = cast(
            Response,
            self.client.get(f"/api/v1/reading/sessions/{session.id}/progress/"),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(ReadingProgress.objects.filter(session=session).exists())
        data = _response_data_dict(resp)
        self.assertEqual(str(data["session"]), str(session.id))
        self.assertEqual(data["current_location"], {})
        self.assertIsNone(data["progression"])
        self.assertEqual(data["profile_version"], CURRENT_READING_PROFILE_VERSION)

    def test_closed_session_progress_get_does_not_create_progress(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(
            user=self.user1,
            book=self.book,
            status=ReadingSession.STATUS_COMPLETED,
            is_active=False,
        )
        before_updated_at = session.updated_at

        resp = cast(
            Response,
            self.client.get(f"/api/v1/reading/sessions/{session.id}/progress/"),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(ReadingProgress.objects.filter(session=session).exists())
        session.refresh_from_db()
        self.assertEqual(session.updated_at, before_updated_at)
        data = _response_data_dict(resp)
        self.assertEqual(str(data["session"]), str(session.id))
        self.assertEqual(data["current_location"], {})
        self.assertIsNone(data["progression"])
        self.assertEqual(data["profile_version"], CURRENT_READING_PROFILE_VERSION)

    def test_progress_put_round_trips_current_location(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        resp = cast(
            Response,
            self.client.put(
                f"/api/v1/reading/sessions/{session.id}/progress/",
                data={"current_location": {"cfi": "/6/4"}, "progression": 0.5},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = _response_data_dict(resp)
        self.assertEqual(str(data["session"]), str(session.id))
        self.assertEqual(data["current_location"]["format"], "epub")
        self.assertEqual(data["current_location"]["cfi"], "/6/4")
        self.assertEqual(data["progression"], 0.5)
        self.assertEqual(data["profile_version"], CURRENT_READING_PROFILE_VERSION)


    def test_progress_update_rejects_unsupported_profile_version(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        resp = cast(
            Response,
            self.client.put(
                f"/api/v1/reading/sessions/{session.id}/progress/",
                data={"current_location": {"cfi": "/6/2"}, "profile_version": "9.9.9"},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class ReadingProgressBearerAPITest(ReadingClientBearerAPITestBase):
    def test_progress_update_rejects_unknown_field(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        resp = cast(
            Response,
            self.client.put(
                f"/api/v1/reading/sessions/{session.id}/progress/",
                data={"current_location": {"cfi": "/6/2"}, "weird": 1},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


    def test_progress_current_location_size_limit_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        big = "x" * (MAX_CURRENT_LOCATION_JSON_BYTES + 1024)
        resp = cast(
            Response,
            self.client.put(
                f"/api/v1/reading/sessions/{session.id}/progress/",
                data={"current_location": {"cfi": "/6/2", "href": big}},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

