from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status

from accounts.client_sessions.services import consume_login_request, hash_client_secret
from accounts.models import ClientLoginRequest, UserClientSession
from tests.accounts.client_api.helpers import ClientApiTestCase, post_login_request
from tests.testenv.database_connections import orm_worker_connection_scope


User = get_user_model()


class PairingHttpLifecycleTests(ClientApiTestCase):
    def test_pairing_state_and_consumption_responses_are_private_no_store(self):
        created = post_login_request(self.client)
        request_id = created.json()["id"]
        code = created.json()["code"]
        invalid_create = self.client.post(
            "/api/v1/client-api/login-requests/",
            data={},
            format="json",
        )
        pending_get = self.client.get(
            f"/api/v1/client-api/login-requests/{request_id}/poll/"
        )
        pending_post = self.client.post(
            f"/api/v1/client-api/login-requests/{request_id}/poll/"
        )

        self.client.force_login(self.bootstrap_owner)
        lookup = self.client.post(
            "/api/v1/client-api/pairing/lookup/",
            {"code": code},
            format="json",
        )
        invalid_decision = self.client.post(
            "/api/v1/client-api/pairing/decision/",
            {"code": code, "action": "invalid"},
            format="json",
        )

        for response in (
            created,
            invalid_create,
            pending_get,
            pending_post,
            lookup,
            invalid_decision,
        ):
            with self.subTest(status_code=response.status_code):
                self.assertEqual(response["Cache-Control"], "no-store, private")
                self.assertEqual(response["Pragma"], "no-cache")

    def test_get_and_post_report_terminal_states_without_credentials(self):
        now = timezone.now()
        cases = (
            (ClientLoginRequest.STATUS_PENDING, now - timedelta(seconds=1), "expired"),
            (ClientLoginRequest.STATUS_DENIED, now + timedelta(minutes=5), "denied"),
            (ClientLoginRequest.STATUS_EXPIRED, now - timedelta(minutes=5), "expired"),
            (ClientLoginRequest.STATUS_CONSUMED, now + timedelta(minutes=5), "consumed"),
        )
        for index, (request_status, expires_at, expected) in enumerate(cases):
            login_request = ClientLoginRequest.objects.create(
                code_hash=hash_client_secret(f"CODE-{index}"),
                client_name="Reader",
                client_type="reader",
                status=request_status,
                expires_at=expires_at,
            )
            for method in (self.client.get, self.client.post):
                with self.subTest(status=request_status, method=method.__name__):
                    response = method(
                        f"/api/v1/client-api/login-requests/{login_request.pk}/poll/"
                    )
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.json(), {"status": expected})
                    self.assertEqual(response["Cache-Control"], "no-store, private")
                    self.assertEqual(response["Pragma"], "no-cache")

        self.assertFalse(UserClientSession.objects.exists())

    def test_successful_consumption_response_is_private_no_store(self):
        created = post_login_request(self.client)
        self.client.force_login(self.bootstrap_owner)
        self.client.post(
            "/api/v1/client-api/pairing/decision/",
            {
                "code": created.json()["code"],
                "action": "approve",
                "client_name": "Reader",
            },
            format="json",
        )

        response = self.client.post(
            f"/api/v1/client-api/login-requests/{created.json()['id']}/poll/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], ClientLoginRequest.STATUS_CONSUMED)
        self.assertIn("access_token", response.json())
        self.assertEqual(response["Cache-Control"], "no-store, private")
        self.assertEqual(response["Pragma"], "no-cache")

    def test_inactive_approver_expires_request_without_creating_session(self):
        login_request = self._approved_request(self.bootstrap_owner)
        self.bootstrap_owner.is_active = False
        self.bootstrap_owner.save(update_fields=["is_active"])

        result = consume_login_request(login_request=login_request)

        self.assertIsNone(result)
        login_request.refresh_from_db()
        self.assertEqual(login_request.status, ClientLoginRequest.STATUS_EXPIRED)
        self.assertIsNone(login_request.consumed_at)
        self.assertFalse(UserClientSession.objects.exists())

    def test_deleted_approver_expires_request_without_creating_session(self):
        login_request = self._approved_request(self.bootstrap_owner)
        self.bootstrap_owner.delete()

        result = consume_login_request(login_request=login_request)

        self.assertIsNone(result)
        login_request.refresh_from_db()
        self.assertEqual(login_request.status, ClientLoginRequest.STATUS_EXPIRED)
        self.assertIsNone(login_request.consumed_at)
        self.assertFalse(UserClientSession.objects.exists())

    def test_session_creation_failure_rolls_back_consumed_claim(self):
        login_request = self._approved_request(self.bootstrap_owner)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with patch(
                "accounts.client_sessions.services.UserClientSession.objects.create",
                side_effect=RuntimeError("simulated failure"),
            ):
                with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                    consume_login_request(login_request=login_request)

        self.assertEqual(callbacks, [])
        login_request.refresh_from_db()
        self.assertEqual(login_request.status, ClientLoginRequest.STATUS_APPROVED)
        self.assertIsNone(login_request.consumed_at)
        self.assertFalse(UserClientSession.objects.exists())

    @staticmethod
    def _approved_request(user):
        return ClientLoginRequest.objects.create(
            code_hash=hash_client_secret("APPROVED"),
            client_name="Reader",
            client_type="reader",
            status=ClientLoginRequest.STATUS_APPROVED,
            approved_by=user,
            approved_at=timezone.now(),
            expires_at=timezone.now() + timedelta(minutes=5),
        )


class PairingConsumptionConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_consumption_creates_at_most_one_session_and_token(self):
        user = User.objects.create_user(username="pairing-user", password="pw")
        login_request = ClientLoginRequest.objects.create(
            code_hash=hash_client_secret("CONCURRENT"),
            client_name="Reader",
            client_type="reader",
            status=ClientLoginRequest.STATUS_APPROVED,
            approved_by=user,
            approved_at=timezone.now(),
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        barrier = Barrier(2)

        def consume():
            with orm_worker_connection_scope():
                request = ClientLoginRequest.objects.get(pk=login_request.pk)
                barrier.wait(timeout=5)
                return consume_login_request(login_request=request)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: consume(), range(2)))

        issued = [result for result in results if result is not None]
        self.assertEqual(len(issued), 1)
        self.assertEqual(UserClientSession.objects.count(), 1)
        login_request.refresh_from_db()
        self.assertEqual(login_request.status, ClientLoginRequest.STATUS_CONSUMED)
