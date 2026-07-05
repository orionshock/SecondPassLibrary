from datetime import timedelta
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from accounts.models import UserProfile
from library import policies
from library.groups.services import ensure_book_public_assignment, ensure_user_public_membership
from library.models import BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from reading.models import Annotation, ReadingProgress, ReadingSession
from reading.profile.validation import (
    CURRENT_READING_PROFILE_VERSION,
)
from tests.reading.api_test_base import ReadingAPITestBase
from tests.utils.books import create_file_backed_book
from tests.utils.responses import response_data_dict


User = get_user_model()


pytestmark = [pytest.mark.integration]


class ReadingSessionsAPITest(ReadingAPITestBase):
    def _make_user_with_lost_book_access(
        self,
        *,
        username: str,
        title: str,
        active: bool = True,
    ) -> tuple[Any, Any, ReadingSession]:
        user = User.objects.create_user(
            username=username, password="pass", email=f"{username}@example.com"
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])
        ensure_user_public_membership(user=user)

        group = LibraryGroup.objects.create(name=f"{title} Group")
        LibraryGroupMembership.objects.create(
            user=user, group=group, is_curator=False
        )

        restricted = create_file_backed_book(title=title, assign_public=False).book
        BookGroupAssignment.objects.create(book=restricted, group=group)

        session = ReadingSession.objects.create(
            user=user,
            book=restricted,
            is_active=active,
            status=(
                ReadingSession.STATUS_ACTIVE
                if active
                else ReadingSession.STATUS_COMPLETED
            ),
        )

        LibraryGroupMembership.objects.filter(user=user, group=group).delete()
        self.assertFalse(policies.can_view_book(user=user, book=restricted))
        return user, restricted, session

    def test_get_create_active_session(self):
        self.client.login(username="u1", password="pass1")
        url = f"/api/v1/reading/books/{self.book.id}/active-session/"
        response = cast(Response, self.client.get(url))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response_data_dict(response)
        self.assertEqual(data["book"], self.book.id)
        self.assertTrue(data["is_active"])

        response2 = cast(Response, self.client.get(url))
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        data2 = response_data_dict(response2)
        self.assertEqual(data2["id"], data["id"])


    def test_open_endpoint_creates_session_progress_and_returns_annotations(self):
        self.client.login(username="u1", password="pass1")
        url = f"/api/v1/reading/books/{self.book.id}/open/"

        resp = cast(Response, self.client.post(url, data={}, format="json"))
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        data = response_data_dict(resp)
        self.assertEqual(data["profile_version"], CURRENT_READING_PROFILE_VERSION)
        self.assertIn("session", data)
        self.assertIn("progress", data)
        self.assertIn("annotations", data)

        session_id = data["session"]["id"]
        self.assertTrue(ReadingSession.objects.filter(id=session_id, user=self.user1).exists())
        self.assertTrue(ReadingProgress.objects.filter(session_id=session_id).exists())

        # Add annotations (including a deleted one) and confirm /open/ returns non-deleted.
        session = ReadingSession.objects.get(id=session_id)
        keep = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/2)",
            highlight_text="keep",
            comment_text="keep",
        )
        deleted = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/4)",
            highlight_text="delete",
            comment_text="delete",
            is_deleted=True,
        )

        resp2 = cast(Response, self.client.post(url, data={}, format="json"))
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        data2 = response_data_dict(resp2)
        results = cast(list[dict[str, Any]], data2["annotations"]["results"])
        ids = {row["id"] for row in results}
        self.assertIn(str(keep.id), ids)
        self.assertNotIn(str(deleted.id), ids)


    def test_open_endpoint_returns_existing_active_session_without_duplication(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book, is_active=True)

        url = f"/api/v1/reading/books/{self.book.id}/open/"
        resp = cast(Response, self.client.post(url, data={}, format="json"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = response_data_dict(resp)
        self.assertEqual(data["session"]["id"], str(session.id))
        self.assertEqual(
            ReadingSession.objects.filter(user=self.user1, book=self.book, is_active=True).count(),
            1,
        )


    def test_active_session_existing_404s_when_book_access_lost(self):
        _user, restricted, session = self._make_user_with_lost_book_access(
            username="u3", title="Restricted"
        )

        self.client.login(username="u3", password="pass")
        url = f"/api/v1/reading/books/{restricted.id}/active-session/"
        resp = cast(Response, self.client.get(url))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ReadingSession.objects.filter(pk=session.pk).exists())


    def test_open_existing_active_session_404s_when_book_access_lost(self):
        _user, restricted, session = self._make_user_with_lost_book_access(
            username="u4", title="RestrictedOpen"
        )

        self.client.login(username="u4", password="pass")
        url = f"/api/v1/reading/books/{restricted.id}/open/"
        resp = cast(Response, self.client.post(url, data={}, format="json"))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ReadingSession.objects.filter(pk=session.pk).exists())


    def test_close_active_session_allowed_when_book_access_lost(self):
        _user, _restricted, session = self._make_user_with_lost_book_access(
            username="u5", title="RestrictedClose"
        )

        self.client.login(username="u5", password="pass")
        resp = cast(
            Response,
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
        resp = cast(
            Response,
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
        resp = cast(
            Response,
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


    def test_active_session_404_for_inaccessible_book_without_existing_session(self):
        self.client.login(username="u1", password="pass1")
        group = LibraryGroup.objects.create(name="Hidden")
        restricted = create_file_backed_book(title="Restricted2", assign_public=False).book
        BookGroupAssignment.objects.create(book=restricted, group=group)

        url = f"/api/v1/reading/books/{restricted.id}/active-session/"
        resp = cast(Response, self.client.get(url))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(
            ReadingSession.objects.filter(user=self.user1, book=restricted).exists()
        )


    def test_open_404_for_inaccessible_book_without_existing_session(self):
        self.client.login(username="u1", password="pass1")
        group = LibraryGroup.objects.create(name="HiddenOpen")
        restricted = create_file_backed_book(title="RestrictedOpen404", assign_public=False).book
        BookGroupAssignment.objects.create(book=restricted, group=group)

        url = f"/api/v1/reading/books/{restricted.id}/open/"
        resp = cast(Response, self.client.post(url, data={}, format="json"))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(
            ReadingSession.objects.filter(user=self.user1, book=restricted).exists()
        )


    def test_start_over_requires_book_access(self):
        self.client.login(username="u1", password="pass1")
        group = LibraryGroup.objects.create(name="Hidden")
        restricted = create_file_backed_book(title="Restricted3", assign_public=False).book
        BookGroupAssignment.objects.create(book=restricted, group=group)

        url = f"/api/v1/reading/books/{restricted.id}/start-over/"
        resp = cast(Response, self.client.post(url, data={}, format="json"))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)


    def test_start_over_returns_open_response_shape_and_archives_old_active(self):
        self.client.login(username="u1", password="pass1")

        old = ReadingSession.objects.create(user=self.user1, book=self.book, is_active=True)
        Annotation.objects.create(
            session=old,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            book=self.book,
            selector_value="epubcfi(/6/2)",
        )

        url = f"/api/v1/reading/books/{self.book.id}/start-over/"
        resp = cast(Response, self.client.post(url, data={"name": "Reread"}, format="json"))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        data = response_data_dict(resp)
        self.assertEqual(data["profile_version"], CURRENT_READING_PROFILE_VERSION)
        self.assertIn("session", data)
        self.assertIn("progress", data)
        self.assertIn("annotations", data)

        new_session_id = data["session"]["id"]
        self.assertNotEqual(str(old.id), str(new_session_id))
        self.assertEqual(str(data["progress"]["session"]), str(new_session_id))
        self.assertEqual(data["annotations"]["results"], [])

        old.refresh_from_db(from_queryset=None)
        self.assertFalse(old.is_active)
        self.assertEqual(old.status, ReadingSession.STATUS_ARCHIVED)

        new = ReadingSession.objects.get(pk=new_session_id)
        self.assertTrue(new.is_active)
        self.assertEqual(new.status, ReadingSession.STATUS_ACTIVE)


    def test_close_session_closes_active_idempotent_and_allows_open_new(self):
        self.client.login(username="u1", password="pass1")

        session = ReadingSession.objects.create(user=self.user1, book=self.book, is_active=True)
        ann = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_BOOKMARKING,
            book=self.book,
            selector_value="epubcfi(/6/2)",
        )

        close1 = cast(Response, self.client.post(f"/api/v1/reading/sessions/{session.id}/close/", data={}, format="json"))
        self.assertEqual(close1.status_code, status.HTTP_200_OK)
        data1 = response_data_dict(close1)
        self.assertEqual(data1["id"], str(session.id))
        self.assertEqual(data1["status"], ReadingSession.STATUS_COMPLETED)
        self.assertFalse(data1["is_active"])
        self.assertIsNotNone(data1["completed_at"])

        session.refresh_from_db(from_queryset=None)
        completed_at1 = session.completed_at
        self.assertIsNotNone(completed_at1)

        # Idempotent: closing again does not change completed_at.
        close2 = cast(Response, self.client.post(f"/api/v1/reading/sessions/{session.id}/close/", data={}, format="json"))
        self.assertEqual(close2.status_code, status.HTTP_200_OK)
        session.refresh_from_db(from_queryset=None)
        self.assertEqual(session.completed_at, completed_at1)

        # After close, progress writes and annotation create/update are rejected.
        prog = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/progress/",
                data={"current_location": {"cfi": "/6/2"}},
                format="json",
            ),
        )
        self.assertEqual(prog.status_code, status.HTTP_400_BAD_REQUEST)

        ann_create = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "kind": "bookmark",
                    "selector": {"kind": "epub_cfi", "value": "epubcfi(/6/4)"},
                },
                format="json",
            ),
        )
        self.assertEqual(ann_create.status_code, status.HTTP_400_BAD_REQUEST)

        ann_update = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/annotations/{ann.id}/",
                data={
                    "comment_text": "new",
                },
                format="json",
            ),
        )
        self.assertEqual(ann_update.status_code, status.HTTP_400_BAD_REQUEST)

        # Annotation delete is a write and is blocked on closed sessions.
        del_resp = cast(Response, self.client.delete(f"/api/v1/reading/annotations/{ann.id}/"))
        self.assertEqual(del_resp.status_code, status.HTTP_400_BAD_REQUEST)
        ann.refresh_from_db()
        self.assertFalse(ann.is_deleted)

        # Opening the book again creates a new active session (since none is active now).
        open_resp = cast(Response, self.client.post(f"/api/v1/reading/books/{self.book.id}/open/", data={}, format="json"))
        self.assertIn(open_resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        open_data = response_data_dict(open_resp)
        self.assertNotEqual(open_data["session"]["id"], str(session.id))
        self.assertTrue(open_data["session"]["is_active"])
        self.assertEqual(open_data["session"]["status"], ReadingSession.STATUS_ACTIVE)


    def test_recent_sessions_endpoint_limits_filters_active_and_orders_by_last_activity(self):
        self.client.login(username="u1", password="pass1")

        book2 = create_file_backed_book(title="Book 2").book
        ensure_book_public_assignment(book=book2, added_by=None)

        from io import BytesIO
        from PIL import Image
        from library.cover_services import set_book_cover_from_bytes

        img = Image.new("RGB", (20, 30), color=(1, 2, 3))
        bio = BytesIO()
        img.save(bio, format="PNG")
        set_book_cover_from_bytes(book=book2, data=bio.getvalue(), source="manual")

        s1 = ReadingSession.objects.create(user=self.user1, book=self.book, is_active=True, status=ReadingSession.STATUS_ACTIVE)
        s2 = ReadingSession.objects.create(user=self.user1, book=book2, is_active=True, status=ReadingSession.STATUS_ACTIVE)

        # Exclude closed sessions.
        closed = ReadingSession.objects.create(user=self.user1, book=book2, is_active=False, status=ReadingSession.STATUS_COMPLETED)

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
        Annotation.objects.filter(pk=a.pk).update(updated_at=timezone.now() + timedelta(seconds=5))

        r = cast(Response, self.client.get("/api/v1/reading/sessions/recent/"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = cast(dict[str, Any], r.data)
        self.assertIn("count", body)
        self.assertIn("results", body)
        results = cast(list[dict[str, Any]], body["results"])
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
        self.assertTrue(str(results[0]["book"]["cover_url"]).startswith("http://testserver/"))
        self.assertEqual(results[1]["book"]["cover_url"], None)

        r2 = cast(Response, self.client.get("/api/v1/reading/sessions/recent/?limit=1"))
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        results2 = cast(list[dict[str, Any]], cast(dict[str, Any], r2.data)["results"])
        self.assertEqual(len(results2), 1)

        bad = cast(Response, self.client.get("/api/v1/reading/sessions/recent/?limit=0"))
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
