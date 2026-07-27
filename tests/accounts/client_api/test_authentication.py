from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from accounts import session_control
from accounts.client_api import hash_client_secret
from accounts.models import ClientLoginRequest, UserClientSession
from tests.accounts.client_api.helpers import ClientApiTestCase, post_login_request
from tests.utils.responses import assert_response, response_data_dict


User = get_user_model()


class ClientApiAuthenticationTests(ClientApiTestCase):
    def test_approve_then_poll_returns_token_once_and_allows_me(self):
        user = User.objects.create_user(
            username="u", password="pw", email="u@example.com"
        )

        # Client creates request (anonymous).
        r = assert_response(post_login_request(self.client))
        body = response_data_dict(r)
        req_id = str(body["id"])
        code = str(body["code"])

        # Browser approves (authenticated session).
        self.client.force_login(user)
        approve = self.client.post(
            "/api/v1/client-api/pairing/decision/",
            data={
                "code": code,
                "action": "approve",
                "client_name": "Second Pass Reader",
            },
            format="json",
        )
        self.assertEqual(approve.status_code, 200)

        obj = ClientLoginRequest.objects.get(pk=req_id)
        self.assertEqual(obj.status, ClientLoginRequest.STATUS_APPROVED)
        self.assertEqual(obj.approved_by, user)

        # Client polls without auth and receives token once.
        poll1 = assert_response(
            self.client.get(f"/api/v1/client-api/login-requests/{req_id}/poll/")
        )
        self.assertEqual(poll1.status_code, 200)
        poll1_data = response_data_dict(poll1)
        self.assertEqual(poll1_data.get("status"), "approved")
        token = poll1_data.get("access_token")
        self.assertTrue(token)
        self.assertEqual(poll1_data.get("token_type"), "Bearer")
        self.assertTrue(poll1_data.get("client_session"))

        # Token is stored hashed only.
        session = UserClientSession.objects.get(pk=poll1_data["client_session"]["id"])
        self.assertNotEqual(session.token_hash, token)
        self.assertEqual(session.token_hash, hash_client_secret(str(token)))
        self.assertEqual(session.name, "Second Pass Reader")

        # Second poll does not return token again.
        poll2 = assert_response(
            self.client.get(f"/api/v1/client-api/login-requests/{req_id}/poll/")
        )
        self.assertEqual(poll2.status_code, 200)
        poll2_data = response_data_dict(poll2)
        self.assertEqual(poll2_data.get("status"), "consumed")
        self.assertFalse("access_token" in poll2_data)

        # Bearer token works for /api/v1/accounts/me/ only.
        api = APIClient()

        me = assert_response(
            api.get(
                "/api/v1/accounts/me/",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            ),
        )
        self.assertEqual(me.status_code, 200)
        me_data = response_data_dict(me)
        self.assertEqual(me_data.get("username"), "u")
        self.assertEqual(me_data.get("email"), user.email)

        me_patch = assert_response(
            api.patch(
                "/api/v1/accounts/me/",
                data={"first_name": "New"},
                format="json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            ),
        )
        self.assertEqual(me_patch.status_code, status.HTTP_403_FORBIDDEN)

        # Management endpoint should not accept bearer in Phase 1.
        users = assert_response(
            api.get(
                "/api/v1/accounts/users/",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            ),
        )
        self.assertIn(
            users.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )

    def test_revoked_token_cannot_call_me(self):
        user = User.objects.create_user(username="u", password="pw")
        UserClientSession.objects.create(
            user=user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret("spl_testtoken"),
            last_seen_at=None,
            expires_at=None,
            revoked_at=None,
        )
        session_control.revoke_all_api_sessions(user)

        me = assert_response(
            self.client.get(
                "/api/v1/accounts/me/",
                HTTP_AUTHORIZATION="Bearer spl_testtoken",
            ),
        )
        self.assertIn(
            me.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )

    def test_inactive_user_token_is_rejected(self):
        user = User.objects.create_user(username="u", password="pw")
        user.is_active = False
        user.save(update_fields=["is_active"])
        UserClientSession.objects.create(
            user=user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret("spl_testtoken2"),
            last_seen_at=None,
            expires_at=None,
            revoked_at=None,
        )
        me = assert_response(
            self.client.get(
                "/api/v1/accounts/me/",
                HTTP_AUTHORIZATION="Bearer spl_testtoken2",
            ),
        )
        self.assertIn(
            me.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        )
