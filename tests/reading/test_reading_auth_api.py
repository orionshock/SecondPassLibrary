from typing import Any, cast

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from accounts.models import UserClientSession
from reading.models import Annotation, ReadingSession
from reading.profile import (
    CURRENT_READING_PROFILE_VERSION,
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

class ReadingAuthenticationAPITest(ReadingAPITestBase):
    def test_anonymous_cannot_access_reading_apis(self):
        response = self.client.get(
            f"/api/v1/reading/books/{self.book.id}/active-session/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ReadingBearerAuthenticationAPITest(ReadingClientBearerAPITestBase):
    def test_bearer_sessions_active_session_start_over_and_progress(self):
        # Active session requires book access (Public assignment makes it accessible here).
        active = cast(
            Response,
            self.client.get(
                f"/api/v1/reading/books/{self.book.id}/active-session/",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(active.status_code, status.HTTP_200_OK)
        session_id = _response_data_dict(active)["id"]

        sessions = cast(
            Response,
            self.client.get(
                "/api/v1/reading/sessions/",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(sessions.status_code, status.HTTP_200_OK)
        sess_ids = {s["id"] for s in _response_data_list(sessions)}
        self.assertIn(session_id, sess_ids)

        other = self.client.get(
            f"/api/v1/reading/sessions/{self.session2.id}/",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(other.status_code, status.HTTP_404_NOT_FOUND)
        ok = cast(
            Response,
            self.client.put(
                f"/api/v1/reading/sessions/{session_id}/progress/",
                data={"current_location": {"cfi": "/6/2"}, "progression": 0.1},
                format="json",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)

        start_over = cast(
            Response,
            self.client.post(
                f"/api/v1/reading/books/{self.book.id}/start-over/",
                data={"name": "Reread"},
                format="json",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(start_over.status_code, status.HTTP_201_CREATED)
        start_over_data = _response_data_dict(start_over)
        self.assertEqual(start_over_data["profile_version"], CURRENT_READING_PROFILE_VERSION)
        self.assertIn("session", start_over_data)
        self.assertIn("progress", start_over_data)
        self.assertIn("annotations", start_over_data)
        self.assertEqual(start_over_data["annotations"]["results"], [])

        # Progress writes should reject unsupported fields (including legacy device field).
        bad_progress = self.client.put(
            f"/api/v1/reading/sessions/{session_id}/progress/",
            data={"device": "nope", "current_location": {"cfi": "/6/2"}},
            format="json",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(bad_progress.status_code, status.HTTP_400_BAD_REQUEST)


    def test_bearer_can_close_own_session_and_cannot_close_cross_user(self):
        session1 = ReadingSession.objects.create(user=self.user1, book=self.book, is_active=True)

        ok = cast(
            Response,
            self.client.post(
                f"/api/v1/reading/sessions/{session1.id}/close/",
                data={},
                format="json",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        data = _response_data_dict(ok)
        self.assertEqual(data["id"], str(session1.id))
        self.assertEqual(data["status"], ReadingSession.STATUS_COMPLETED)
        self.assertFalse(data["is_active"])
        self.assertIsNotNone(data["completed_at"])

        cross = cast(
            Response,
            self.client.post(
                f"/api/v1/reading/sessions/{self.session2.id}/close/",
                data={},
                format="json",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(cross.status_code, status.HTTP_404_NOT_FOUND)


    def test_bearer_can_call_recent_sessions(self):
        s1 = ReadingSession.objects.create(user=self.user1, book=self.book, is_active=True, status=ReadingSession.STATUS_ACTIVE)
        r = cast(
            Response,
            self.client.get(
                "/api/v1/reading/sessions/recent/",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        payload = cast(dict[str, Any], r.data)
        results = cast(list[dict[str, Any]], payload["results"])
        ids = {row["session"]["id"] for row in results}
        self.assertIn(str(s1.id), ids)
        # Shape includes session name and progress summary.
        if results:
            self.assertIn("name", results[0]["session"])
            self.assertIn("progression", results[0]["session"])
        # Cross-user session should not appear.
        self.assertNotIn(str(self.session2.id), ids)


    def test_bearer_can_open_endpoint(self):
        resp = cast(
            Response,
            self.client.post(
                f"/api/v1/reading/books/{self.book.id}/open/",
                data={},
                format="json",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        data = _response_data_dict(resp)
        self.assertEqual(data["profile_version"], CURRENT_READING_PROFILE_VERSION)
        self.assertEqual(data["session"]["book"], self.book.id)
        self.assertEqual(str(data["progress"]["session"]), str(data["session"]["id"]))
        self.assertIn("results", data["annotations"])


    def test_bearer_annotations_are_user_scoped(self):
        session1 = ReadingSession.objects.create(user=self.user1, book=self.book)

        create = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session1.id),
                    "motivation": Annotation.MOTIVATION_HIGHLIGHTING,
                    "target": {"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/6)"}},
                    "body": [{"type": "TextualBody", "purpose": "describing", "value": "hello"}],
                },
                format="json",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        ann_id = _response_data_dict(create)["id"]

        list_all = cast(
            Response,
            self.client.get(
                "/api/v1/reading/annotations/",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(list_all.status_code, status.HTTP_200_OK)
        ids = {a["id"] for a in _response_data_list(list_all)}
        self.assertIn(ann_id, ids)
        self.assertNotIn(str(self.annotation2.id), ids)

        # Cross-user detail and delete should 404.
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

        # Cross-user creation should be rejected by serializer validation (invalid session).
        bad_create = self.client.post(
            "/api/v1/reading/annotations/",
            data={
                "session": str(self.session2.id),
                "motivation": Annotation.MOTIVATION_HIGHLIGHTING,
                "target": {"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/6)"}},
                "body": [],
            },
            format="json",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(bad_create.status_code, status.HTTP_400_BAD_REQUEST)

        # Legacy device field should be rejected as unknown.
        bad_device_field = self.client.post(
            "/api/v1/reading/annotations/",
            data={
                "session": str(session1.id),
                "device": "nope",
                "motivation": Annotation.MOTIVATION_BOOKMARKING,
                "target": {"selector": {"value": "/6/2"}},
                "body": [],
            },
            format="json",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(bad_device_field.status_code, status.HTTP_400_BAD_REQUEST)


    def test_revoked_and_inactive_bearer_token_rejected(self):
        UserClientSession.objects.filter(user=self.user1).update(revoked_at=timezone.now())
        r = self.client.get(
            "/api/v1/reading/sessions/",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertIn(r.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

        self.user1.is_active = False
        self.user1.save(update_fields=["is_active"])
        UserClientSession.objects.filter(user=self.user1).update(revoked_at=None)
        r2 = self.client.get(
            "/api/v1/reading/sessions/",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertIn(r2.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

