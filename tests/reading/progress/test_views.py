from typing import cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response

from accounts.models import UserProfile
from library.group_services import ensure_user_public_membership
from library.models import BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from reading.models import ReadingProgress, ReadingSession
from reading.profile.validation import (
    CURRENT_READING_PROFILE_VERSION,
    MAX_CURRENT_LOCATION_JSON_BYTES,
)
from tests.reading.api_test_base import ReadingAPITestBase, ReadingClientBearerAPITestBase
from tests.utils.books import create_file_backed_book
from tests.utils.responses import response_data_dict


User = get_user_model()


class ReadingProgressAPITest(ReadingAPITestBase):
    def _make_lost_access_session(self):
        user = User.objects.create_user(username="lost", password="pass", email="lost@example.com")
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])
        ensure_user_public_membership(user=user)
        group = LibraryGroup.objects.create(name="Lost Progress Group")
        LibraryGroupMembership.objects.create(user=user, group=group)
        book = create_file_backed_book(title="Lost Progress", assign_public=False).book
        BookGroupAssignment.objects.create(book=book, group=group)
        session = ReadingSession.objects.create(user=user, book=book)
        ReadingProgress.objects.create(
            session=session,
            current_location={"cfi": "epubcfi(/6/2)"},
            progression=0.25,
        )
        LibraryGroupMembership.objects.filter(user=user, group=group).delete()
        return user, session

    def test_active_session_progress_get_still_lazily_creates_progress(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        resp = cast(
            Response,
            self.client.get(f"/api/v1/reading/sessions/{session.id}/progress/"),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(ReadingProgress.objects.filter(session=session).exists())
        data = response_data_dict(resp)
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
        data = response_data_dict(resp)
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
        data = response_data_dict(resp)
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


    def test_progress_update_requires_current_book_access(self):
        _user, session = self._make_lost_access_session()
        self.client.login(username="lost", password="pass")

        resp = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/progress/",
                data={"current_location": {"cfi": "epubcfi(/6/4)"}, "progression": 0.5},
                format="json",
            ),
        )

        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        session.progress.refresh_from_db()
        self.assertEqual(session.progress.current_location["cfi"], "epubcfi(/6/2)")
        self.assertEqual(session.progress.progression, 0.25)


    def test_progress_read_still_allowed_after_book_access_lost(self):
        _user, session = self._make_lost_access_session()
        self.client.login(username="lost", password="pass")

        resp = cast(
            Response,
            self.client.get(f"/api/v1/reading/sessions/{session.id}/progress/"),
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = response_data_dict(resp)
        self.assertEqual(data["current_location"]["cfi"], "epubcfi(/6/2)")
        self.assertEqual(data["progression"], 0.25)


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

