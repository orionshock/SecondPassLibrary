from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from library.groups.memberships import ensure_user_public_membership
from reading.models import ReadingSession
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book
from tests.utils.responses import assert_response, response_data_dict


User = get_user_model()


class ReadingSessionPatchActiveOnlyTests(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="u", password="pw", email="u@example.com"
        )
        ensure_user_public_membership(user=self.user)
        self.client.login(username="u", password="pw")
        self.book = create_file_backed_book(title="B").book

    def test_active_session_patch_name_succeeds(self):
        session = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_ACTIVE,
            is_active=True,
        )
        resp = assert_response(
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/",
                data={"name": "Renamed"},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = response_data_dict(resp)
        self.assertEqual(payload["name"], "Renamed")
        self.assertEqual(payload["id"], str(session.id))
        self.assertIn("book", payload)
        self.assertIn("annotation_count", payload)

    def test_active_session_patch_notes_succeeds(self):
        session = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_ACTIVE,
            is_active=True,
        )
        resp = assert_response(
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/",
                data={"notes": "Some notes"},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = response_data_dict(resp)
        self.assertEqual(payload["notes"], "Some notes")

    def test_completed_session_patch_is_rejected(self):
        session = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_COMPLETED,
            is_active=False,
        )
        resp = assert_response(
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/",
                data={"name": "Nope", "notes": "Nope"},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_archived_session_patch_is_rejected(self):
        session = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_ARCHIVED,
            is_active=False,
        )
        resp = assert_response(
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/",
                data={"name": "Nope"},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_session_name_is_trimmed_and_bounded(self):
        session = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            status=ReadingSession.STATUS_ACTIVE,
            is_active=True,
        )

        renamed = assert_response(
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/",
                data={"name": "  Renamed history  "},
                format="json",
            )
        )
        too_long = assert_response(
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/",
                data={"name": "x" * 256},
                format="json",
            )
        )

        self.assertEqual(response_data_dict(renamed)["name"], "Renamed history")
        self.assertEqual(too_long.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_cannot_rename_another_users_session(self):
        other = User.objects.create_user(username="other", password="pw")
        session = ReadingSession.objects.create(
            user=other,
            book=self.book,
            status=ReadingSession.STATUS_COMPLETED,
            is_active=False,
        )

        response = self.client.patch(
            f"/api/v1/reading/sessions/{session.id}/",
            data={"name": "Nope"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
