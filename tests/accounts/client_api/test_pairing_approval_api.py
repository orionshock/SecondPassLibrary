from rest_framework import status

from accounts.models import ClientLoginRequest
from tests.accounts.client_api.helpers import ClientApiTestCase, post_login_request


class ClientPairingApprovalApiTests(ClientApiTestCase):
    def test_pairing_lookup_and_approval_use_authenticated_json_api(self):
        created = post_login_request(self.client)
        code = created.json()["code"]
        request_id = created.json()["id"]

        self.client.force_login(self.bootstrap_owner)
        lookup = self.client.post(
            "/api/v1/client-api/pairing/lookup/", {"code": code}, format="json"
        )
        self.assertEqual(lookup.status_code, status.HTTP_200_OK)
        self.assertEqual(lookup.json()["client_name"], "Second Pass Reader")
        self.assertNotIn("access_token", lookup.json())

        decision = self.client.post(
            "/api/v1/client-api/pairing/decision/",
            {"code": code, "action": "approve", "client_name": "My Reader"},
            format="json",
        )
        self.assertEqual(decision.status_code, status.HTTP_200_OK)
        self.assertEqual(decision.json(), {"status": "approved"})
        paired = ClientLoginRequest.objects.get(pk=request_id)
        self.assertEqual(paired.client_name, "My Reader")
        self.assertEqual(paired.approved_by, self.bootstrap_owner)
        self.assertEqual(paired.request_user_agent, "")
        self.assertEqual(paired.request_fingerprint, "")
        self.assertIsNone(paired.request_ip)

    def test_pairing_approval_requires_session_authentication(self):
        created = post_login_request(self.client)
        code = created.json()["code"]
        response = self.client.post(
            "/api/v1/client-api/pairing/lookup/", {"code": code}, format="json"
        )
        self.assertIn(response.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})

    def test_pairing_denial_does_not_return_a_token(self):
        created = post_login_request(self.client)
        code = created.json()["code"]
        self.client.force_login(self.bootstrap_owner)
        response = self.client.post(
            "/api/v1/client-api/pairing/decision/",
            {"code": code, "action": "deny"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "denied"})
