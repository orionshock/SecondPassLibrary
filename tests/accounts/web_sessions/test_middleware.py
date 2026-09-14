from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models import F
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import UserProfile, UserWebSession
from tests.utils.responses import assert_response


User = get_user_model()


class UserWebSessionMiddlewareTests(APITestCase):
    def test_authenticated_me_request_has_one_account_facts_query(self):
        user = User.objects.create_user(username="query-user", password="pw")
        self.client.login(username="query-user", password="pw")
        self.client.get("/api/v1/health/")

        with CaptureQueriesContext(connection) as captured:
            response = self.client.get("/api/v1/accounts/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        account_selects = [
            query["sql"]
            for query in captured.captured_queries
            if query["sql"].lstrip().upper().startswith("SELECT")
            and any(
                table in query["sql"]
                for table in (
                    '"auth_user"',
                    '"accounts_userprofile"',
                    '"accounts_userwebsession"',
                )
            )
        ]
        self.assertEqual(len(account_selects), 3)
        self.assertEqual(
            sum('"accounts_userprofile"' in query for query in account_selects),
            1,
        )
        self.assertEqual(
            sum('"auth_user"' in query for query in account_selects),
            1,
        )
        self.assertEqual(
            sum('"accounts_userwebsession"' in query for query in account_selects),
            1,
        )
        self.assertEqual(
            UserWebSession.objects.get(
                session_key=self.client.session.session_key
            ).user_id,
            user.pk,
        )

    def test_next_request_observes_web_session_generation_advancement(self):
        user = User.objects.create_user(username="revoked", password="pw")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/api/v1/health/").status_code, status.HTTP_200_OK)

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

    def test_existing_tracking_row_checks_fk_ownership_without_related_user_fetch(self):
        user = User.objects.create_user(username="current", password="pw")
        previous_user = User.objects.create_user(username="previous", password="pw")
        self.client.force_login(user)
        session_key = self.client.session.session_key
        UserWebSession.objects.create(user=previous_user, session_key=session_key)

        with CaptureQueriesContext(connection) as captured:
            response = self.client.get("/api/v1/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tracked = UserWebSession.objects.get(session_key=session_key)
        self.assertEqual(tracked.user_id, user.pk)
        auth_user_selects = [
            query["sql"]
            for query in captured.captured_queries
            if query["sql"].lstrip().upper().startswith("SELECT")
            and '"auth_user"' in query["sql"]
        ]
        self.assertEqual(len(auth_user_selects), 1)

    def test_tracking_failure_does_not_override_enforced_account_facts(self):
        user = User.objects.create_user(username="tracking-failure", password="pw")
        self.client.force_login(user)
        UserProfile.objects.filter(user=user).update(must_change_password=True)

        with patch(
            "accounts.middleware.UserWebSession.objects.get_or_create",
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
