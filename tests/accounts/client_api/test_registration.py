from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status

from accounts.client_api import hash_client_secret, normalize_human_code
from accounts.models import ClientLoginRequest, UserClientSession
from tests.accounts.client_api.helpers import ClientApiTestCase, post_login_request
from tests.utils.responses import assert_response, response_data_dict


User = get_user_model()


class ClientApiRegistrationTests(ClientApiTestCase):
    def test_client_api_discovery_keeps_pairing_route_manifest(self):
        r = assert_response(self.client.get("/api/v1/client-api/discovery/"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        body = response_data_dict(r)

        self.assertEqual(body.get("discovery_version"), "0.1")
        self.assertEqual(body.get("server_name"), "Second Pass Library")
        self.assertEqual(body.get("server_description"), "")
        self.assertEqual(body.get("api_base_url"), "http://testserver/api/v1/")
        self.assertEqual(
            body.get("login_request_endpoint"),
            "http://testserver/api/v1/client-api/login-requests/",
        )
        self.assertNotIn("authorize_url", body)
        self.assertEqual(
            body.get("poll_endpoint_template"),
            "http://testserver/api/v1/client-api/login-requests/%7Bid%7D/poll/",
        )
        self.assertEqual(body.get("token_type"), "Bearer")
        self.assertEqual(body.get("server_base_url"), "http://testserver/")

    def test_create_login_request_is_anonymous_and_stores_only_hash(self):
        r = assert_response(post_login_request(self.client))
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        body = response_data_dict(r)

        req_id = body.get("id")
        code = body.get("code")
        self.assertTrue(req_id)
        self.assertTrue(code)
        self.assertEqual(
            body.get("authorize_url"),
            f"http://testserver/profile/client-pairing?code={code}",
        )
        self.assertIn("poll_url", body)

        obj = ClientLoginRequest.objects.get(pk=req_id)
        self.assertEqual(obj.status, ClientLoginRequest.STATUS_PENDING)
        self.assertNotEqual(obj.code_hash, code)
        self.assertEqual(
            obj.code_hash, hash_client_secret(normalize_human_code(str(code)))
        )

    def test_pairing_api_allows_editing_client_name_before_approval(self):
        user = User.objects.create_user(
            username="u", password="pw", email="u@example.com"
        )

        r = assert_response(post_login_request(self.client))
        body = response_data_dict(r)
        req_id = str(body["id"])
        code = str(body["code"])

        self.client.force_login(user)

        approve = self.client.post(
            "/api/v1/client-api/pairing/decision/",
            data={"code": code, "action": "approve", "client_name": "My Phone Reader"},
            format="json",
        )
        self.assertEqual(approve.status_code, 200)

        poll1 = assert_response(
            self.client.get(f"/api/v1/client-api/login-requests/{req_id}/poll/")
        )
        poll1_data = response_data_dict(poll1)
        self.assertEqual(poll1_data.get("status"), "approved")
        token = poll1_data.get("access_token")
        self.assertTrue(token)

        session = UserClientSession.objects.get(pk=poll1_data["client_session"]["id"])
        self.assertEqual(session.name, "My Phone Reader")
        self.assertEqual(poll1_data["client_session"]["name"], "My Phone Reader")

    def test_blank_edited_client_name_is_rejected_and_request_remains_pending(self):
        user = User.objects.create_user(
            username="u", password="pw", email="u@example.com"
        )

        r = assert_response(post_login_request(self.client))
        body = response_data_dict(r)
        req_id = str(body["id"])
        code = str(body["code"])

        self.client.force_login(user)
        approve = self.client.post(
            "/api/v1/client-api/pairing/decision/",
            data={"code": code, "action": "approve", "client_name": "   "},
            format="json",
        )
        self.assertEqual(approve.status_code, status.HTTP_400_BAD_REQUEST)

        obj = ClientLoginRequest.objects.get(pk=req_id)
        self.assertEqual(obj.status, ClientLoginRequest.STATUS_PENDING)

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
        r = self.client.post(
            "/api/v1/client-api/pairing/decision/",
            data={"code": "CODE", "action": "approve", "client_name": "Reader"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

        # Pylance/Django stubs sometimes mis-type the optional `from_queryset` arg;
        # be explicit to avoid type-checker noise.
        obj.refresh_from_db(from_queryset=None)
        self.assertEqual(obj.status, ClientLoginRequest.STATUS_PENDING)
        self.assertIsNone(obj.approved_by)
