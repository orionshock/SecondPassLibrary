from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from reading.models import ReadingSession
from tests.utils.books import create_file_backed_book


User = get_user_model()


class ReadingSessionPatchActiveOnlyTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="pw", email="u@example.com")
        self.client.login(username="u", password="pw")
        self.book = create_file_backed_book(title="B").book

    def test_active_session_patch_name_succeeds(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book, status=ReadingSession.STATUS_ACTIVE, is_active=True)
        resp = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/",
                data={"name": "Renamed"},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = cast(dict[str, Any], resp.data)
        self.assertEqual(payload["name"], "Renamed")

    def test_active_session_patch_notes_succeeds(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book, status=ReadingSession.STATUS_ACTIVE, is_active=True)
        resp = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/",
                data={"notes": "Some notes"},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = cast(dict[str, Any], resp.data)
        self.assertEqual(payload["notes"], "Some notes")

    def test_completed_session_patch_is_rejected(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book, status=ReadingSession.STATUS_COMPLETED, is_active=False)
        resp = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/",
                data={"name": "Nope", "notes": "Nope"},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_archived_session_patch_is_rejected(self):
        session = ReadingSession.objects.create(user=self.user, book=self.book, status=ReadingSession.STATUS_ARCHIVED, is_active=False)
        resp = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/",
                data={"name": "Nope"},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

