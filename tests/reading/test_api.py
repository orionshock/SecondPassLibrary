from typing import Any, cast

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from library.group_services import ensure_book_public_assignment, ensure_user_public_membership
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from reading.models import Annotation, Device, ReadingProgress, ReadingSession
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

        self.device2 = Device.objects.create(
            user=self.user2, name="Other device", device_type=Device.TYPE_WEB
        )
        self.session2 = ReadingSession.objects.create(user=self.user2, book=self.book)
        self.annotation2 = Annotation.objects.create(
            session=self.session2,
            device=self.device2,
            kind=Annotation.KIND_NOTE,
            locator={"cfi": "/6/2"},
            note="secret",
        )

    def test_anonymous_cannot_access_reading_apis(self):
        response = self.client.get("/api/v1/reading/devices/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.get(f"/api/v1/reading/books/{self.book.id}/active-session/")
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

    def test_active_session_existing_returned_even_if_book_access_lost(self):
        user = User.objects.create_user(username="u3", password="pass3", email="u3@example.com")
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])
        ensure_user_public_membership(user=user)

        group = LibraryGroup.objects.create(name="Private", slug="private")
        LibraryGroupMembership.objects.create(user=user, group=group, role=LibraryGroupMembership.ROLE_READER)

        restricted = Book.objects.create(title="Restricted")
        BookGroupAssignment.objects.create(book=restricted, group=group)

        session = ReadingSession.objects.create(user=user, book=restricted, is_active=True)

        LibraryGroupMembership.objects.filter(user=user, group=group).delete()

        self.client.login(username="u3", password="pass3")
        url = f"/api/v1/reading/books/{restricted.id}/active-session/"
        resp = cast(Response, self.client.get(url))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = _response_data_dict(resp)
        self.assertEqual(data["id"], str(session.id))

    def test_active_session_404_for_inaccessible_book_without_existing_session(self):
        self.client.login(username="u1", password="pass1")
        group = LibraryGroup.objects.create(name="Hidden", slug="hidden2")
        restricted = Book.objects.create(title="Restricted2")
        BookGroupAssignment.objects.create(book=restricted, group=group)

        url = f"/api/v1/reading/books/{restricted.id}/active-session/"
        resp = cast(Response, self.client.get(url))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(ReadingSession.objects.filter(user=self.user1, book=restricted).exists())

    def test_start_over_404_for_inaccessible_book(self):
        self.client.login(username="u1", password="pass1")
        group = LibraryGroup.objects.create(name="Hidden3", slug="hidden3")
        restricted = Book.objects.create(title="Restricted3")
        BookGroupAssignment.objects.create(book=restricted, group=group)

        url = f"/api/v1/reading/books/{restricted.id}/start-over/"
        resp = cast(Response, self.client.post(url, data={"name": "x"}, format="json"))
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(ReadingSession.objects.filter(user=self.user1, book=restricted).exists())

    def test_start_over_deactivates_old_and_creates_new(self):
        self.client.login(username="u1", password="pass1")
        active_url = f"/api/v1/reading/books/{self.book.id}/active-session/"
        start_over_url = f"/api/v1/reading/books/{self.book.id}/start-over/"

        first = _response_data_dict(cast(Response, self.client.get(active_url)))
        response = cast(Response, self.client.post(start_over_url, data={"name": "Second pass"}, format="json"))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = _response_data_dict(response)
        self.assertNotEqual(data["id"], first["id"])
        self.assertEqual(data["name"], "Second pass")

        old = ReadingSession.objects.get(id=first["id"])
        self.assertFalse(old.is_active)

        current = _response_data_dict(cast(Response, self.client.get(active_url)))
        self.assertEqual(current["id"], data["id"])

    def test_user_cannot_see_others_data(self):
        self.client.login(username="u1", password="pass1")

        response = cast(Response, self.client.get("/api/v1/reading/sessions/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(_response_data_list(response)), 0)

        response = cast(Response, self.client.get("/api/v1/reading/devices/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(_response_data_list(response)), 0)

        response = cast(Response, self.client.get("/api/v1/reading/annotations/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(_response_data_list(response)), 0)

    def test_user_can_update_progress_for_own_session(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        device = Device.objects.create(user=self.user1, name="My device", device_type=Device.TYPE_WEB)

        url = f"/api/v1/reading/sessions/{session.id}/progress/"
        response = cast(
            Response,
            self.client.patch(
                url,
                data={"device": str(device.id), "locator": {"cfi": "/6/4"}, "progression": 0.5},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = _response_data_dict(response)
        self.assertEqual(data["session"], session.id)
        self.assertEqual(data["device"], device.id)
        self.assertEqual(data["locator"]["format"], "epub")
        self.assertEqual(data["locator"]["cfi"], "/6/4")
        self.assertEqual(data["progression"], 0.5)

        self.assertTrue(ReadingProgress.objects.filter(session=session).exists())

    def test_user_can_create_and_list_annotations_for_own_session(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        device = Device.objects.create(user=self.user1, name="My device", device_type=Device.TYPE_WEB)

        create = cast(
            Response,
            self.client.post(
                "/api/v1/reading/annotations/",
                data={
                    "session": str(session.id),
                    "device": str(device.id),
                    "kind": Annotation.KIND_HIGHLIGHT,
                    "locator": {"cfi": "/6/6"},
                    "selected_text": "hello",
                    "color": "yellow",
                },
                format="json",
            ),
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        create_data = _response_data_dict(create)
        self.assertEqual(create_data["locator"]["format"], "epub")
        self.assertEqual(create_data["locator"]["cfi"], "/6/6")

        response = cast(Response, self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = _response_data_list(response)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["session"], session.id)

    def test_reading_sessions_post_is_not_allowed(self):
        self.client.login(username="u1", password="pass1")
        response = cast(
            Response,
            self.client.post(
                "/api/v1/reading/sessions/",
                data={"book": str(self.book.id), "name": "x"},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_reading_sessions_patch_allows_only_name_and_notes(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book, name="a")

        ok = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/",
                data={"name": "New name", "notes": "n"},
                format="json",
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        session.refresh_from_db()
        self.assertEqual(session.name, "New name")
        self.assertEqual(session.notes, "n")

        denied = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/",
                data={"is_active": False},
                format="json",
            ),
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)

        denied2 = cast(
            Response,
            self.client.patch(
                f"/api/v1/reading/sessions/{session.id}/",
                data={"book": str(self.book.id)},
                format="json",
            ),
        )
        self.assertEqual(denied2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_soft_deleted_annotations_hidden_by_default_and_opt_in_include_deleted(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        device = Device.objects.create(user=self.user1, name="d", device_type=Device.TYPE_WEB)
        a1 = Annotation.objects.create(session=session, device=device, kind=Annotation.KIND_NOTE, locator={"cfi": "/6/2"}, note="keep")
        a2 = Annotation.objects.create(session=session, device=device, kind=Annotation.KIND_NOTE, locator={"cfi": "/6/4"}, note="delete")

        deleted = cast(Response, self.client.delete(f"/api/v1/reading/annotations/{a2.id}/"))
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        a2.refresh_from_db()
        self.assertTrue(a2.is_deleted)

        listing = cast(Response, self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}"))
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        data = cast(list[dict[str, Any]], _response_data_list(listing))
        ids = {row["id"] for row in data}
        self.assertIn(str(a1.id), ids)
        self.assertNotIn(str(a2.id), ids)

        listing2 = cast(Response, self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}&include_deleted=true"))
        self.assertEqual(listing2.status_code, status.HTTP_200_OK)
        data2 = cast(list[dict[str, Any]], _response_data_list(listing2))
        ids2 = {row["id"] for row in data2}
        self.assertIn(str(a1.id), ids2)
        self.assertIn(str(a2.id), ids2)

        get_deleted = cast(Response, self.client.get(f"/api/v1/reading/annotations/{a2.id}/"))
        self.assertEqual(get_deleted.status_code, status.HTTP_404_NOT_FOUND)
        get_deleted2 = cast(Response, self.client.get(f"/api/v1/reading/annotations/{a2.id}/?include_deleted=true"))
        self.assertEqual(get_deleted2.status_code, status.HTTP_200_OK)

    def test_annotations_list_is_paginated(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        for i in range(51):
            Annotation.objects.create(session=session, kind=Annotation.KIND_NOTE, locator={"cfi": f"/6/{i}"}, note=str(i))

        response = cast(Response, self.client.get(f"/api/v1/reading/annotations/?session_id={session.id}"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        payload = cast(dict[str, Any], response.data)
        self.assertIn("count", payload)
        self.assertIn("next", payload)
        self.assertIn("previous", payload)
        self.assertIn("results", payload)
        self.assertEqual(payload["count"], 51)
        self.assertEqual(len(cast(list[Any], payload["results"])), 50)

