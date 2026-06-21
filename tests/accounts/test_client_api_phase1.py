from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.client_api import hash_client_secret, normalize_human_code, consume_login_request
from accounts.models import ClientLoginRequest, UserClientSession
from accounts import session_control


User = get_user_model()


class ClientApiPhase1Tests(APITestCase):
    def setUp(self):
        self.bootstrap_owner = User.objects.create_superuser(
            username="bootstrap-owner",
            password="pw",
        )

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
        self.assertEqual(poll1.data.get("token_type"), "Bearer")
        self.assertTrue(poll1.data.get("client_session"))

        # Token is stored hashed only.
        session = UserClientSession.objects.get(pk=poll1.data["client_session"]["id"])
        self.assertNotEqual(session.token_hash, token)
        self.assertEqual(session.token_hash, hash_client_secret(str(token)))
        self.assertEqual(session.name, "Second Pass Reader")

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

    def test_authorize_page_allows_editing_client_name_before_approval(self):
        user = User.objects.create_user(username="u", password="pw", email="u@example.com")

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

        self.client.force_login(user)

        page = self.client.get(f"/client-api/authorize/?code={code}")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'name="client_name"')
        self.assertContains(page, "Second Pass Reader")
        self.assertContains(page, "reader")

        approve = self.client.post(
            "/client-api/authorize/",
            data={"code": code, "action": "approve", "client_name": "My Phone Reader"},
            follow=True,
        )
        self.assertEqual(approve.status_code, 200)

        poll1 = cast(Any, self.client.get(f"/api/v1/client-api/login-requests/{req_id}/poll/"))
        self.assertEqual(poll1.data.get("status"), "approved")
        token = poll1.data.get("access_token")
        self.assertTrue(token)

        session = UserClientSession.objects.get(pk=poll1.data["client_session"]["id"])
        self.assertEqual(session.name, "My Phone Reader")
        self.assertEqual(poll1.data["client_session"]["name"], "My Phone Reader")

    def test_blank_edited_client_name_is_rejected_and_request_remains_pending(self):
        user = User.objects.create_user(username="u", password="pw", email="u@example.com")

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

        self.client.force_login(user)
        approve = self.client.post(
            "/client-api/authorize/",
            data={"code": code, "action": "approve", "client_name": "   "},
            follow=True,
        )
        self.assertEqual(approve.status_code, 200)

        obj = ClientLoginRequest.objects.get(pk=req_id)
        self.assertEqual(obj.status, ClientLoginRequest.STATUS_PENDING)

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

        # Pylance/Django stubs sometimes mis-type the optional `from_queryset` arg;
        # be explicit to avoid type-checker noise.
        obj.refresh_from_db(from_queryset=None)
        self.assertEqual(obj.status, ClientLoginRequest.STATUS_PENDING)
        self.assertIsNone(obj.approved_by)

    def test_poll_returns_consumed_not_approved_without_token(self):
        """
        Contract guardrail: poll must never return `approved` without `access_token`.

        Simulate the "already consumed" case and ensure the second poll yields `consumed`.
        """
        user = User.objects.create_user(username="u", password="pw", email="u@example.com")

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

        self.client.force_login(user)
        self.client.post("/client-api/authorize/", data={"code": code, "action": "approve"})

        poll1 = cast(Any, self.client.get(f"/api/v1/client-api/login-requests/{req_id}/poll/"))
        self.assertEqual(poll1.data.get("status"), "approved")
        self.assertTrue(poll1.data.get("access_token"))

        poll2 = cast(Any, self.client.get(f"/api/v1/client-api/login-requests/{req_id}/poll/"))
        self.assertEqual(poll2.data.get("status"), "consumed")
        self.assertFalse("access_token" in poll2.data)

    def test_consume_is_idempotent_and_issues_token_once(self):
        user = User.objects.create_user(username="u", password="pw", email="u@example.com")
        obj = ClientLoginRequest.objects.create(
            code_hash=hash_client_secret("CODE"),
            client_name="Second Pass Reader",
            client_type="reader",
            status=ClientLoginRequest.STATUS_APPROVED,
            approved_by=user,
            expires_at=timezone.now() + timedelta(minutes=10),
            request_user_agent="",
            request_ip=None,
        )

        first = consume_login_request(login_request=obj)
        self.assertIsNotNone(first)
        second = consume_login_request(login_request=obj)
        self.assertIsNone(second)
