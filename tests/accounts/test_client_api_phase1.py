from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.client_api import hash_client_secret, normalize_human_code
from accounts.models import ClientLoginRequest, UserClientSession
from accounts import session_control


User = get_user_model()


class ClientApiPhase1Tests(APITestCase):
    def test_create_login_request_is_anonymous_and_stores_only_hash(self):
        r = cast(
            Any,
            self.client.post(
                "/api/v1/client-api/login-requests/",
                data={"client_name": "Second Pass Reader", "client_type": "reader"},
                format="json",
            ),
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        body = cast(dict[str, Any], getattr(r, "data", {}))

        req_id = body.get("id")
        code = body.get("code")
        self.assertTrue(req_id)
        self.assertTrue(code)
        self.assertIn("authorize_url", body)
        self.assertIn("poll_url", body)

        obj = ClientLoginRequest.objects.get(pk=req_id)
        self.assertEqual(obj.status, ClientLoginRequest.STATUS_PENDING)
        self.assertNotEqual(obj.code_hash, code)
        self.assertEqual(obj.code_hash, hash_client_secret(normalize_human_code(str(code))))

    def test_authorize_page_requires_login(self):
        response = self.client.get("/client-api/authorize/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/api-auth/login/", response["Location"])

    def test_authorize_page_preserves_code_through_login_redirect(self):
        response = self.client.get("/client-api/authorize/?code=ABCD-1234", follow=False)
        self.assertEqual(response.status_code, 302)
        loc = str(response["Location"])
        self.assertIn("/api-auth/login/", loc)
        # Django should preserve the full URL (including query string) via `next=`.
        self.assertIn("next=/client-api/authorize/%3Fcode%3DABCD-1234", loc)

    def test_approve_then_poll_returns_token_once_and_allows_me(self):
        user = User.objects.create_user(username="u", password="pw", email="u@example.com")

        # Client creates request (anonymous).
        r = cast(
            Any,
            self.client.post(
                "/api/v1/client-api/login-requests/",
                data={"client_name": "Second Pass Reader", "client_type": "reader"},
                format="json",
            ),
        )
        body = cast(dict[str, Any], r.data)
        req_id = str(body["id"])
        code = str(body["code"])

        # Browser approves (authenticated session).
        self.client.force_login(user)
        approve = self.client.post(
            "/client-api/authorize/",
            data={"code": code, "action": "approve"},
            follow=True,
        )
        self.assertEqual(approve.status_code, 200)

        obj = ClientLoginRequest.objects.get(pk=req_id)
        self.assertEqual(obj.status, ClientLoginRequest.STATUS_APPROVED)
        self.assertEqual(obj.approved_by, user)

        # Client polls without auth and receives token once.
        poll1 = cast(Any, self.client.get(f"/api/v1/client-api/login-requests/{req_id}/poll/"))
        self.assertEqual(poll1.status_code, 200)
        self.assertEqual(poll1.data.get("status"), "approved")
        token = poll1.data.get("access_token")
        self.assertTrue(token)

        # Token is stored hashed only.
        session = UserClientSession.objects.get(pk=poll1.data["client_session"]["id"])
        self.assertNotEqual(session.token_hash, token)
        self.assertEqual(session.token_hash, hash_client_secret(str(token)))

        # Second poll does not return token again.
        poll2 = cast(Any, self.client.get(f"/api/v1/client-api/login-requests/{req_id}/poll/"))
        self.assertEqual(poll2.status_code, 200)
        self.assertEqual(poll2.data.get("status"), "consumed")
        self.assertFalse("access_token" in poll2.data)

        # Bearer token works for /api/v1/accounts/me/ only.
        from rest_framework.test import APIClient

        api = APIClient()

        me = cast(
            Any,
            api.get(
                "/api/v1/accounts/me/",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            ),
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data.get("username"), "u")

        me_patch = cast(
            Any,
            api.patch(
                "/api/v1/accounts/me/",
                data={"first_name": "New"},
                format="json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            ),
        )
        self.assertEqual(me_patch.status_code, status.HTTP_403_FORBIDDEN)

        # Management endpoint should not accept bearer in Phase 1.
        users = cast(
            Any,
            self.client.get(
                "/api/v1/accounts/users/",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            ),
        )
        self.assertIn(users.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

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

        me = cast(
            Any,
            self.client.get(
                "/api/v1/accounts/me/",
                HTTP_AUTHORIZATION="Bearer spl_testtoken",
            ),
        )
        self.assertIn(me.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

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
        me = cast(
            Any,
            self.client.get(
                "/api/v1/accounts/me/",
                HTTP_AUTHORIZATION="Bearer spl_testtoken2",
            ),
        )
        self.assertIn(me.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_expired_code_cannot_be_approved(self):
        user = User.objects.create_user(username="u", password="pw")
        obj = ClientLoginRequest.objects.create(
            code_hash=hash_client_secret("CODE"),
            client_name="Reader",
            client_type="reader",
            status=ClientLoginRequest.STATUS_PENDING,
            expires_at=timezone.now() - timedelta(seconds=1),
            request_user_agent="",
            request_ip=None,
        )

        self.client.force_login(user)
        r = self.client.post("/client-api/authorize/", data={"code": "CODE", "action": "approve"})
        self.assertEqual(r.status_code, 200)

        obj.refresh_from_db()
        self.assertEqual(obj.status, ClientLoginRequest.STATUS_PENDING)
        self.assertIsNone(obj.approved_by)
