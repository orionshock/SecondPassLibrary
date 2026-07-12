from __future__ import annotations

import pytest
from rest_framework import status

from reading.models import ReadingSession
from tests.reading.api_test_base import ReadingAPITestBase
from tests.reading.sessions.helpers import LostBookAccessSessionMixin
from tests.utils.responses import assert_response


pytestmark = [pytest.mark.integration]


class ReadingSessionLostAccessTests(LostBookAccessSessionMixin, ReadingAPITestBase):
    def test_active_session_existing_404s_when_book_access_lost(self):
        _user, restricted, session = self._make_user_with_lost_book_access(
            username="u3", title="Restricted"
        )

        self.client.login(username="u3", password="pass")
        url = f"/api/v1/reading/books/{restricted.id}/active-session/"
        resp = assert_response(self.client.get(url))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ReadingSession.objects.filter(pk=session.pk).exists())

    def test_open_existing_active_session_404s_when_book_access_lost(self):
        _user, restricted, session = self._make_user_with_lost_book_access(
            username="u4", title="RestrictedOpen"
        )

        self.client.login(username="u4", password="pass")
        url = f"/api/v1/reading/books/{restricted.id}/open/"
        resp = assert_response(self.client.post(url, data={}, format="json"))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ReadingSession.objects.filter(pk=session.pk).exists())

    def test_close_active_session_allowed_when_book_access_lost(self):
        _user, _restricted, session = self._make_user_with_lost_book_access(
            username="u5", title="RestrictedClose"
        )

        self.client.login(username="u5", password="pass")
        resp = assert_response(
            self.client.post(
                f"/api/v1/reading/sessions/{session.id}/close/",
                data={},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertFalse(session.is_active)
        self.assertEqual(session.status, ReadingSession.STATUS_COMPLETED)

    def test_patch_active_session_name_notes_allowed_when_book_access_lost(self):
        _user, _restricted, session = self._make_user_with_lost_book_access(
            username="u6", title="RestrictedPatch"
        )

        self.client.login(username="u6", password="pass")
        resp = assert_response(
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/",
                data={"name": "Recovered", "notes": "No access now."},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertEqual(session.name, "Recovered")
        self.assertEqual(session.notes, "No access now.")

    def test_start_over_requires_book_access_after_access_lost(self):
        _user, restricted, session = self._make_user_with_lost_book_access(
            username="u7", title="RestrictedStartOver"
        )

        self.client.login(username="u7", password="pass")
        resp = assert_response(
            self.client.post(
                f"/api/v1/reading/books/{restricted.id}/start-over/",
                data={"name": "Nope"},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            ReadingSession.objects.filter(user=session.user, book=restricted).count(),
            1,
        )
