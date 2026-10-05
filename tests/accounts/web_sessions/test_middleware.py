from __future__ import annotations

from unittest.mock import patch
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection
from django.db.models import F
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserProfile, UserWebSession
from accounts.middleware import UserWebSessionMiddleware
from tests.utils.responses import assert_response


User = get_user_model()


class UserWebSessionMiddlewareTests(APITestCase):
    def test_bounded_user_agent_tracking_preserves_the_existing_error_response(self):
        user = User.objects.create_user(username="agent", password="pw")
        self.client.force_login(user)
        response = self.client.get("/api/v1/not-a-route/", HTTP_USER_AGENT="a" * 4500)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        tracked = UserWebSession.objects.get(session_key=self.client.session.session_key)
        self.assertEqual(tracked.user_agent, "a" * 4000)

    def test_missing_persisted_session_skips_tracking_and_actor_lookup(self):
        user = User.objects.create_user(username="unpersisted")
        response = HttpResponse(b"unchanged", status=418, headers={"X-Adapter-Test": "preserved"})
        middleware = UserWebSessionMiddleware(lambda request: response)
        for session in (None, {}, SimpleNamespace(session_key="")):
            with self.subTest(session=session):
                request = RequestFactory().get("/api/v1/accounts/me/")
                request.user = user
                request.session = session
                with (
                    patch("accounts.middleware.get_request_actor_context") as acquire,
                    patch("accounts.middleware.track_web_session") as tracking,
                ):
                    self.assertIs(middleware(request), response)
                acquire.assert_not_called()
                tracking.assert_not_called()

    def test_tracking_failure_preserves_the_exact_http_response(self):
        user = User.objects.create_user(username="response-preservation")
        request = RequestFactory().get("/api/v1/accounts/me/")
        request.user = user
        request.session = SimpleNamespace(session_key="persisted")
        response = HttpResponse(b"original body", status=418, headers={"X-Adapter-Test": "preserved"})
        middleware = UserWebSessionMiddleware(lambda request: response)
        with patch("accounts.middleware.track_web_session", side_effect=DatabaseError("private detail")):
            self.assertIs(middleware(request), response)
        self.assertEqual(response.content, b"original body")
        self.assertEqual(response.status_code, 418)
        self.assertEqual(response["X-Adapter-Test"], "preserved")

    def test_authenticated_me_request_tracks_session_with_bounded_queries(self):
        user = User.objects.create_user(username="query-user", password="pw")
        self.client.login(username="query-user", password="pw")
        self.client.get("/api/v1/not-a-route/")

        with CaptureQueriesContext(connection) as captured:
            response = self.client.get("/api/v1/accounts/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(captured), 8)
        self.assertEqual(
            UserWebSession.objects.get(
                session_key=self.client.session.session_key
            ).user_id,
            user.pk,
        )

    def test_next_request_observes_web_session_generation_advancement(self):
        user = User.objects.create_user(username="revoked", password="pw")
        self.client.force_login(user)
        self.assertEqual(
            self.client.get("/api/v1/accounts/me/").status_code,
            status.HTTP_200_OK,
        )

        UserProfile.objects.filter(user=user).update(
            web_session_generation=F("web_session_generation") + 1
        )
        response = self.client.get("/api/v1/accounts/me/")

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_next_request_observes_must_change_password_change(self):
        user = User.objects.create_user(username="forced-change", password="pw")
        self.client.force_login(user)
        self.assertEqual(
            self.client.get("/api/v1/not-a-route/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

        UserProfile.objects.filter(user=user).update(must_change_password=True)
        response = self.client.get("/api/v1/not-a-route/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()["code"], "password_change_required")

    def test_existing_tracking_row_reassigns_owner_with_bounded_queries(self):
        user = User.objects.create_user(username="current", password="pw")
        previous_user = User.objects.create_user(username="previous", password="pw")
        self.client.force_login(user)
        session_key = self.client.session.session_key
        UserWebSession.objects.create(user=previous_user, session_key=session_key)

        with CaptureQueriesContext(connection) as captured:
            response = self.client.get("/api/v1/not-a-route/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        tracked = UserWebSession.objects.get(session_key=session_key)
        self.assertEqual(tracked.user_id, user.pk)
        self.assertLessEqual(len(captured), 8)

    def test_tracking_failure_does_not_override_enforced_account_facts(self):
        user = User.objects.create_user(username="tracking-failure", password="pw")
        self.client.force_login(user)
        UserProfile.objects.filter(user=user).update(must_change_password=True)

        with patch(
            "accounts.middleware.track_web_session",
            side_effect=RuntimeError("tracking unavailable"),
        ) as tracking:
            response = self.client.get("/api/v1/accounts/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.json()["must_change_password"])
        self.assertIn("_auth_user_id", self.client.session)
        tracking.assert_called_once()

    def test_authenticated_request_tracks_user_web_session(self):
        user = User.objects.create_user(username="u", password="pw")
        self.client.login(username="u", password="pw")

        response = assert_response(self.client.get("/api/v1/accounts/me/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        session_key = self.client.session.session_key
        self.assertTrue(session_key)

        tracked = UserWebSession.objects.get(session_key=session_key)
        self.assertEqual(tracked.user.pk, user.pk)

    @override_settings(
        TRUST_X_FORWARDED_FOR=True,
        TRUSTED_PROXY_IPS=["10.0.0.2"],
    )
    def test_tracks_effective_client_ip_from_trusted_proxy(self):
        User.objects.create_user(username="u", password="pw")
        self.client.login(username="u", password="pw")

        response = assert_response(
            self.client.get(
                "/api/v1/accounts/me/",
                REMOTE_ADDR="10.0.0.2",
                HTTP_X_FORWARDED_FOR="203.0.113.10, 10.0.0.2",
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tracked = UserWebSession.objects.get(session_key=self.client.session.session_key)
        self.assertEqual(tracked.ip_address, "203.0.113.10")

    def test_tracks_valid_remote_address_and_ignores_untrusted_forwarding(self):
        User.objects.create_user(username="u", password="pw")
        self.client.login(username="u", password="pw")

        response = assert_response(
            self.client.get(
                "/api/v1/accounts/me/",
                REMOTE_ADDR="2001:0db8:0:0::1",
                HTTP_X_FORWARDED_FOR="203.0.113.10",
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tracked = UserWebSession.objects.get(session_key=self.client.session.session_key)
        self.assertEqual(tracked.ip_address, "2001:db8::1")

    def test_anonymous_request_does_not_track_user_web_session(self):
        with patch("accounts.middleware.get_request_actor_context") as acquire:
            response = assert_response(self.client.get("/api/v1/accounts/me/"))

        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
        self.assertEqual(UserWebSession.objects.count(), 0)
        acquire.assert_not_called()

    def test_session_generation_lookup_failure_fails_closed_with_bounded_response(self):
        User.objects.create_user(username="u", password="pw")
        self.client.login(username="u", password="pw")

        with patch(
            "accounts.request_actor.UserProfile.objects.values",
            side_effect=RuntimeError("database detail"),
        ):
            response = self.client.get("/api/v1/accounts/me/")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertNotIn("database detail", response.content.decode())
