from typing import Any, cast

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession
from core import policies
from library.group_services import ensure_book_public_assignment, ensure_user_public_membership
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from reading.models import Annotation, ReadingProgress, ReadingSession
from reading.profile import (
    CURRENT_READING_PROFILE_VERSION,
    MAX_BODY_JSON_BYTES,
    MAX_BODY_VALUE_CHARS,
    MAX_CURRENT_LOCATION_JSON_BYTES,
    MAX_SELECTOR_VALUE_CHARS,
    MAX_TARGET_JSON_BYTES,
)
from tests.reading.utils import IsolatedUserdataMixin


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


class ReadingAPITest(IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="u1", password="pass1", email="u1@example.com"
        )
        self.user2 = User.objects.create_user(
            username="u2", password="pass2", email="u2@example.com"
        )
        self.book = Book.objects.create(title="Book 1")
        ensure_book_public_assignment(book=self.book, added_by=None)

        self.session2 = ReadingSession.objects.create(user=self.user2, book=self.book)
        self.annotation2 = Annotation.objects.create(
            session=self.session2,
            motivation=Annotation.MOTIVATION_COMMENTING,
            target={"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/2)"}},
            body=[{"type": "TextualBody", "purpose": "commenting", "value": "secret"}],
        )

    def test_anonymous_cannot_access_reading_apis(self):
        response = self.client.get(
            f"/api/v1/reading/books/{self.book.id}/active-session/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_create_active_session(self):
        self.client.login(username="u1", password="pass1")
        url = f"/api/v1/reading/books/{self.book.id}/active-session/"
        response = cast(Response, self.client.get(url))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = _response_data_dict(response)
        self.assertEqual(data["book"], self.book.id)
        self.assertTrue(data["is_active"])

        response2 = cast(Response, self.client.get(url))
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        data2 = _response_data_dict(response2)
        self.assertEqual(data2["id"], data["id"])

    def test_open_endpoint_creates_session_progress_and_returns_annotations(self):
        self.client.login(username="u1", password="pass1")
        url = f"/api/v1/reading/books/{self.book.id}/open/"

        resp = cast(Response, self.client.post(url, data={}, format="json"))
        self.assertIn(resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        data = _response_data_dict(resp)
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
            target={"selector": {"value": "epubcfi(/6/2)"}},
            body=[{"type": "TextualBody", "purpose": "commenting", "value": "keep"}],
        )
        deleted = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_COMMENTING,
            target={"selector": {"value": "epubcfi(/6/4)"}},
            body=[{"type": "TextualBody", "purpose": "commenting", "value": "delete"}],
            is_deleted=True,
        )

        resp2 = cast(Response, self.client.post(url, data={}, format="json"))
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        data2 = _response_data_dict(resp2)
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
        data = _response_data_dict(resp)
        self.assertEqual(data["session"]["id"], str(session.id))
        self.assertEqual(
            ReadingSession.objects.filter(user=self.user1, book=self.book, is_active=True).count(),
            1,
        )

    def test_active_session_existing_returned_even_if_book_access_lost(self):
        user = User.objects.create_user(
            username="u3", password="pass3", email="u3@example.com"
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])
        ensure_user_public_membership(user=user)

        group = LibraryGroup.objects.create(name="Private")
        LibraryGroupMembership.objects.create(
            user=user, group=group, role=LibraryGroupMembership.ROLE_READER
        )

        restricted = Book.objects.create(title="Restricted")
        BookGroupAssignment.objects.create(book=restricted, group=group)

        session = ReadingSession.objects.create(user=user, book=restricted, is_active=True)

        LibraryGroupMembership.objects.filter(user=user, group=group).delete()

        self.assertFalse(policies.can_view_book(user=user, book=restricted))

        self.client.login(username="u3", password="pass3")
        url = f"/api/v1/reading/books/{restricted.id}/active-session/"
        resp = cast(Response, self.client.get(url))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = _response_data_dict(resp)
        self.assertEqual(data["id"], str(session.id))

    def test_open_existing_returned_even_if_book_access_lost(self):
        user = User.objects.create_user(
            username="u4", password="pass4", email="u4@example.com"
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])
        ensure_user_public_membership(user=user)

        group = LibraryGroup.objects.create(name="Private2")
        LibraryGroupMembership.objects.create(
            user=user, group=group, role=LibraryGroupMembership.ROLE_READER
        )

        restricted = Book.objects.create(title="RestrictedOpen")
        BookGroupAssignment.objects.create(book=restricted, group=group)

        session = ReadingSession.objects.create(user=user, book=restricted, is_active=True)

        LibraryGroupMembership.objects.filter(user=user, group=group).delete()
        self.assertFalse(policies.can_view_book(user=user, book=restricted))

        self.client.login(username="u4", password="pass4")
        url = f"/api/v1/reading/books/{restricted.id}/open/"
        resp = cast(Response, self.client.post(url, data={}, format="json"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = _response_data_dict(resp)
        self.assertEqual(data["session"]["id"], str(session.id))

    def test_active_session_404_for_inaccessible_book_without_existing_session(self):
        self.client.login(username="u1", password="pass1")
        group = LibraryGroup.objects.create(name="Hidden")
        restricted = Book.objects.create(title="Restricted2")
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
        restricted = Book.objects.create(title="RestrictedOpen404")
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
        restricted = Book.objects.create(title="Restricted3")
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
            target={"selector": {"value": "epubcfi(/6/2)"}},
            body=[],
        )

        url = f"/api/v1/reading/books/{self.book.id}/start-over/"
        resp = cast(Response, self.client.post(url, data={"name": "Reread"}, format="json"))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        data = _response_data_dict(resp)
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
            target={"selector": {"value": "epubcfi(/6/2)"}},
            body=[],
        )

        close1 = cast(Response, self.client.post(f"/api/v1/reading/sessions/{session.id}/close/", data={}, format="json"))
        self.assertEqual(close1.status_code, status.HTTP_200_OK)
        data1 = _response_data_dict(close1)
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
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": "epubcfi(/6/4)"}},
                    "body": [],
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
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": "epubcfi(/6/2)"}},
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(ann_update.status_code, status.HTTP_400_BAD_REQUEST)

        # Soft-delete still works on closed sessions.
        del_resp = cast(Response, self.client.delete(f"/api/v1/reading/annotations/{ann.id}/"))
        self.assertEqual(del_resp.status_code, status.HTTP_204_NO_CONTENT)

        # Opening the book again creates a new active session (since none is active now).
        open_resp = cast(Response, self.client.post(f"/api/v1/reading/books/{self.book.id}/open/", data={}, format="json"))
        self.assertIn(open_resp.status_code, (status.HTTP_200_OK, status.HTTP_201_CREATED))
        open_data = _response_data_dict(open_resp)
        self.assertNotEqual(open_data["session"]["id"], str(session.id))
        self.assertTrue(open_data["session"]["is_active"])
        self.assertEqual(open_data["session"]["status"], ReadingSession.STATUS_ACTIVE)

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

    def test_annotations_create_requires_motivation_target_body(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)

        create = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_HIGHLIGHTING,
                    "target": {"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/6)"}},
                    "body": [{"type": "TextualBody", "purpose": "describing", "value": "hello"}],
                },
                format="json",
            ),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        payload = _response_data_dict(create)
        self.assertEqual(payload["motivation"], Annotation.MOTIVATION_HIGHLIGHTING)
        self.assertIn("target", payload)
        self.assertIn("body", payload)
        self.assertNotIn("source_import", payload)
        self.assertEqual(payload["profile_version"], CURRENT_READING_PROFILE_VERSION)

    def test_invalid_annotation_motivation_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        resp = cast(
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
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_annotation_api_rejects_source_import_field(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/2)"}},
                    "body": [],
                    "source_import": {"provider": "kindle"},
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_annotation_create_rejects_unsupported_profile_version(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": "/6/2"}},
                    "body": [],
                    "profile_version": "9.9.9",
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

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


class ReadingClientBearerAPITest(IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="u1", password="pass1", email="u1@example.com"
        )
        self.user2 = User.objects.create_user(
            username="u2", password="pass2", email="u2@example.com"
        )
        ensure_user_public_membership(user=self.user1)
        ensure_user_public_membership(user=self.user2)

        self.book = Book.objects.create(title="Book 1")
        ensure_book_public_assignment(book=self.book, added_by=None)

        # Cross-user fixtures
        self.session2 = ReadingSession.objects.create(user=self.user2, book=self.book)
        self.annotation2 = Annotation.objects.create(
            session=self.session2,
            motivation=Annotation.MOTIVATION_COMMENTING,
            target={"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/2)"}},
            body=[{"type": "TextualBody", "purpose": "commenting", "value": "secret"}],
        )

        self.token = "spl_testtoken_reading"
        UserClientSession.objects.create(
            user=self.user1,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(self.token),
            last_seen_at=None,
            expires_at=None,
            revoked_at=None,
        )
        self._auth_header = f"Bearer {self.token}"

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

    def test_annotation_target_size_limit_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        big = "x" * (MAX_TARGET_JSON_BYTES + 1024)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"source": {"id": big}},
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_annotation_body_size_limit_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        big = "x" * (MAX_BODY_JSON_BYTES + 1024)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_COMMENTING,
                    "target": {"selector": {"value": "/6/2"}},
                    "body": [{"type": "TextualBody", "purpose": "commenting", "value": big}],
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_annotation_selector_value_length_limit_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        big = "x" * (MAX_SELECTOR_VALUE_CHARS + 1)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"selector": {"value": big}},
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_annotation_body_value_length_limit_rejected(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        big = "x" * (MAX_BODY_VALUE_CHARS + 1)
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_COMMENTING,
                    "target": {"selector": {"value": "/6/2"}},
                    "body": [{"type": "TextualBody", "purpose": "commenting", "value": big}],
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reasonably_long_body_value_under_limit_succeeds(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        # Stay under both the per-string and total JSON size limits.
        ok_len = min(MAX_BODY_VALUE_CHARS - 10, (MAX_BODY_JSON_BYTES // 2))
        ok_value = "x" * ok_len
        resp = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_COMMENTING,
                    "target": {"selector": {"value": "/6/2"}},
                    "body": [{"type": "TextualBody", "purpose": "commenting", "value": ok_value}],
                },
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_soft_deleted_annotations_hidden_by_default_and_opt_in_include_deleted(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        a1 = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_COMMENTING,
            target={"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/2)"}},
            body=[{"type": "TextualBody", "purpose": "commenting", "value": "keep"}],
        )
        a2 = Annotation.objects.create(
            session=session,
            motivation=Annotation.MOTIVATION_COMMENTING,
            target={"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/4)"}},
            body=[{"type": "TextualBody", "purpose": "commenting", "value": "delete"}],
        )

        deleted = cast(Response, self.client.delete(f"/api/v1/reading/annotations/{a2.id}/"))
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        a2.refresh_from_db()
        self.assertTrue(a2.is_deleted)

        listing = cast(
            Response, self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}")
        )
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        data = cast(list[dict[str, Any]], _response_data_list(listing))
        ids = {row["id"] for row in data}
        self.assertIn(str(a1.id), ids)
        self.assertNotIn(str(a2.id), ids)

        listing2 = cast(
            Response,
            self.client.get(
                f"/api/v1/reading/annotations/?session_id={session.id}&include_deleted=true"
            ),
        )
        self.assertEqual(listing2.status_code, status.HTTP_200_OK)
        data2 = cast(list[dict[str, Any]], _response_data_list(listing2))
        ids2 = {row["id"] for row in data2}
        self.assertIn(str(a1.id), ids2)
        self.assertIn(str(a2.id), ids2)

        get_deleted = cast(Response, self.client.get(f"/api/v1/reading/annotations/{a2.id}/"))
        self.assertEqual(get_deleted.status_code, status.HTTP_404_NOT_FOUND)
        get_deleted2 = cast(
            Response, self.client.get(f"/api/v1/reading/annotations/{a2.id}/?include_deleted=true")
        )
        self.assertEqual(get_deleted2.status_code, status.HTTP_200_OK)

    def test_closed_session_rejects_progress_updates_and_annotation_create(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        session.is_active = False
        session.status = ReadingSession.STATUS_COMPLETED
        session.save(update_fields=["is_active", "status", "updated_at"])

        progress = cast(
            Response,
            self.client.put(
                f"/api/v1/reading/sessions/{session.id}/progress/",
                data={"current_location": {"cfi": "/6/2"}},
                format="json",
            ),
        )
        self.assertEqual(progress.status_code, status.HTTP_400_BAD_REQUEST)

        ann = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "motivation": Annotation.MOTIVATION_BOOKMARKING,
                    "target": {"source": {"id": f"urn:uuid:{self.book.id}"}, "selector": {"value": "epubcfi(/6/2)"}},
                    "body": [],
                },
                format="json",
            ),
        )
        self.assertEqual(ann.status_code, status.HTTP_400_BAD_REQUEST)
