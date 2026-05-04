from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from library.models import Book

from .models import Annotation, Device, ReadingProgress, ReadingSession


User = get_user_model()


class ReadingAPITest(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="u1", password="pass1", email="u1@example.com"
        )
        self.user2 = User.objects.create_user(
            username="u2", password="pass2", email="u2@example.com"
        )
        self.book = Book.objects.create(title="Book 1")

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

        response = self.client.get(
            f"/api/v1/reading/books/{self.book.id}/active-session/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_create_active_session(self):
        self.client.login(username="u1", password="pass1")
        url = f"/api/v1/reading/books/{self.book.id}/active-session/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["book"], self.book.id)
        self.assertTrue(response.data["is_active"])

        response2 = self.client.get(url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.data["id"], response.data["id"])

    def test_start_over_deactivates_old_and_creates_new(self):
        self.client.login(username="u1", password="pass1")
        active_url = f"/api/v1/reading/books/{self.book.id}/active-session/"
        start_over_url = f"/api/v1/reading/books/{self.book.id}/start-over/"

        first = self.client.get(active_url).data
        response = self.client.post(
            start_over_url, data={"name": "Second pass"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(response.data["id"], first["id"])
        self.assertEqual(response.data["name"], "Second pass")

        old = ReadingSession.objects.get(id=first["id"])
        self.assertFalse(old.is_active)

        current = self.client.get(active_url).data
        self.assertEqual(current["id"], response.data["id"])

    def test_user_cannot_see_others_data(self):
        self.client.login(username="u1", password="pass1")

        response = self.client.get("/api/v1/reading/sessions/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

        response = self.client.get("/api/v1/reading/devices/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

        response = self.client.get("/api/v1/reading/annotations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_user_can_update_progress_for_own_session(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        device = Device.objects.create(
            user=self.user1, name="My device", device_type=Device.TYPE_WEB
        )

        url = f"/api/v1/reading/sessions/{session.id}/progress/"
        response = self.client.patch(
            url,
            data={
                "device": str(device.id),
                "locator": {"cfi": "/6/4"},
                "progression": 0.5,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["session"], session.id)
        self.assertEqual(response.data["device"], device.id)
        self.assertEqual(response.data["locator"]["cfi"], "/6/4")
        self.assertEqual(response.data["progression"], 0.5)

        self.assertTrue(ReadingProgress.objects.filter(session=session).exists())

    def test_user_can_create_and_list_annotations_for_own_session(self):
        self.client.login(username="u1", password="pass1")
        session = ReadingSession.objects.create(user=self.user1, book=self.book)
        device = Device.objects.create(
            user=self.user1, name="My device", device_type=Device.TYPE_WEB
        )

        create = self.client.post(
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
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)

        response = self.client.get(
            f"/api/v1/reading/annotations/?session_id={session.id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["session"], session.id)
