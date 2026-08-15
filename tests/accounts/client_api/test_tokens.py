from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.client_sessions.services import consume_login_request, hash_client_secret
from accounts.models import ClientLoginRequest, UserClientSession
from tests.accounts.client_api.helpers import ClientApiTestCase, post_login_request
from tests.utils.responses import assert_response, response_data_dict


User = get_user_model()


class ClientApiTokenTests(ClientApiTestCase):
    def test_get_inspects_approved_state_without_consuming_or_returning_token(self):
        user = User.objects.create_user(
            username="u", password="pw", email="u@example.com"
        )

        r = assert_response(post_login_request(self.client))
        body = response_data_dict(r)
        req_id = str(body["id"])
        code = str(body["code"])

        self.client.force_login(user)
        self.client.post(
            "/api/v1/client-api/pairing/decision/",
            data={
                "code": code,
                "action": "approve",
                "client_name": "Second Pass Reader",
            },
            format="json",
        )
        self.client.logout()

        inspected = assert_response(
            self.client.get(f"/api/v1/client-api/login-requests/{req_id}/poll/")
        )
        inspected_data = response_data_dict(inspected)
        self.assertEqual(inspected_data.get("status"), "approved")
        self.assertNotIn("access_token", inspected_data)
        self.assertEqual(inspected["Cache-Control"], "no-store, private")
        self.assertEqual(inspected["Pragma"], "no-cache")
        self.assertFalse(UserClientSession.objects.exists())
        obj = ClientLoginRequest.objects.get(pk=req_id)
        self.assertEqual(obj.status, ClientLoginRequest.STATUS_APPROVED)

        consumed = assert_response(
            self.client.post(f"/api/v1/client-api/login-requests/{req_id}/poll/")
        )
        consumed_data = response_data_dict(consumed)
        self.assertEqual(consumed_data.get("status"), "consumed")
        self.assertTrue(consumed_data.get("access_token"))
        self.assertEqual(consumed["Cache-Control"], "no-store, private")
        self.assertEqual(consumed["Pragma"], "no-cache")

        replay = assert_response(
            self.client.post(f"/api/v1/client-api/login-requests/{req_id}/poll/")
        )
        replay_data = response_data_dict(replay)
        self.assertEqual(replay_data.get("status"), "consumed")
        self.assertNotIn("access_token", replay_data)
        self.assertEqual(replay["Cache-Control"], "no-store, private")
        self.assertEqual(replay["Pragma"], "no-cache")
        self.assertEqual(UserClientSession.objects.count(), 1)

    def test_consume_is_idempotent_and_issues_token_once(self):
        user = User.objects.create_user(
            username="u", password="pw", email="u@example.com"
        )
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
