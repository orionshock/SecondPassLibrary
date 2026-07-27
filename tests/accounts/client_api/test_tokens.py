from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.client_api import consume_login_request, hash_client_secret
from accounts.models import ClientLoginRequest
from tests.accounts.client_api.helpers import ClientApiTestCase, post_login_request
from tests.utils.responses import assert_response, response_data_dict


User = get_user_model()


class ClientApiTokenTests(ClientApiTestCase):
    def test_poll_returns_consumed_not_approved_without_token(self):
        """
        Contract guardrail: poll must never return `approved` without `access_token`.

        Simulate the "already consumed" case and ensure the second poll yields `consumed`.
        """
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

        poll1 = assert_response(
            self.client.get(f"/api/v1/client-api/login-requests/{req_id}/poll/")
        )
        poll1_data = response_data_dict(poll1)
        self.assertEqual(poll1_data.get("status"), "approved")
        self.assertTrue(poll1_data.get("access_token"))

        poll2 = assert_response(
            self.client.get(f"/api/v1/client-api/login-requests/{req_id}/poll/")
        )
        poll2_data = response_data_dict(poll2)
        self.assertEqual(poll2_data.get("status"), "consumed")
        self.assertFalse("access_token" in poll2_data)

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
