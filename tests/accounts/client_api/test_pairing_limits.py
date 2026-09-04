from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.test import TransactionTestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from accounts.client_sessions.services import (
    MAX_ACTIVE_PENDING_REQUESTS_PER_FINGERPRINT,
    MAX_ACTIVE_PENDING_REQUESTS_PER_IP,
    REQUEST_USER_AGENT_MAX_CHARS,
)
from accounts.models import ClientLoginRequest
from tests.accounts.client_api.helpers import ClientApiTestCase
from tests.testenv.database_connections import orm_worker_connection_scope


class PairingRequestLimitTests(ClientApiTestCase):
    url = "/api/v1/client-api/login-requests/"

    def test_active_pending_requests_are_limited_per_source_ip(self):
        for index in range(MAX_ACTIVE_PENDING_REQUESTS_PER_IP):
            response = self._post(
                client_name=f"Reader {index}",
                remote_addr="192.0.2.10",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        throttled = self._post(client_name="One Too Many", remote_addr="192.0.2.10")

        self.assertEqual(throttled.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(
            throttled.json(),
            {"detail": "Pairing request limit reached. Try again later."},
        )

    def test_terminal_transition_releases_pending_request_capacity(self):
        created = []
        for index in range(MAX_ACTIVE_PENDING_REQUESTS_PER_IP):
            created.append(
                self._post(client_name=f"Reader {index}", remote_addr="192.0.2.10")
            )
        self.client.force_login(self.bootstrap_owner)
        decision = self.client.post(
            "/api/v1/client-api/pairing/decision/",
            {
                "code": created[0].json()["code"],
                "action": "approve",
                "client_name": "Reader 0",
            },
            format="json",
        )

        replacement = self._post(
            client_name="Replacement Reader",
            remote_addr="192.0.2.10",
        )

        self.assertEqual(decision.status_code, status.HTTP_200_OK)
        self.assertEqual(replacement.status_code, status.HTTP_201_CREATED)

    def test_active_pending_requests_are_limited_per_fingerprint(self):
        for index in range(MAX_ACTIVE_PENDING_REQUESTS_PER_FINGERPRINT):
            response = self._post(
                client_name="Same Reader",
                remote_addr=f"192.0.2.{index + 1}",
                user_agent="StableReader/1.0",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        throttled = self._post(
            client_name="Same Reader",
            remote_addr="192.0.2.50",
            user_agent="StableReader/1.0",
        )

        self.assertEqual(throttled.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_forwarded_for_is_ignored_by_default(self):
        response = self._post(
            remote_addr="10.0.0.5",
            forwarded_for="198.51.100.20",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ClientLoginRequest.objects.get().request_ip, "10.0.0.5")

    @override_settings(
        TRUST_X_FORWARDED_FOR=True,
        TRUSTED_PROXY_IPS=["10.0.0.5"],
    )
    def test_forwarded_for_uses_first_ip_from_trusted_peer(self):
        response = self._post(
            remote_addr="10.0.0.5",
            forwarded_for="192.0.2.99, 198.51.100.20",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ClientLoginRequest.objects.get().request_ip, "192.0.2.99")

    @override_settings(
        TRUST_X_FORWARDED_FOR=True,
        TRUSTED_PROXY_IPS=["10.0.0.5"],
    )
    def test_forwarded_for_is_ignored_from_untrusted_peer(self):
        response = self._post(
            remote_addr="10.0.0.6",
            forwarded_for="198.51.100.20",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ClientLoginRequest.objects.get().request_ip, "10.0.0.6")

    def test_stored_user_agent_and_fingerprint_are_bounded(self):
        response = self._post(user_agent="a" * 4000)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        login_request = ClientLoginRequest.objects.get()
        self.assertEqual(len(login_request.request_user_agent), REQUEST_USER_AGENT_MAX_CHARS)
        self.assertEqual(len(login_request.request_fingerprint), 64)
        self.assertNotEqual(login_request.code_hash, response.json()["code"])

    def test_missing_or_malformed_source_uses_one_shared_bounded_bucket(self):
        for index in range(MAX_ACTIVE_PENDING_REQUESTS_PER_IP):
            response = self._post(
                client_name=f"Unknown source {index}",
                remote_addr="not-an-ip",
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        throttled = self._post(client_name="One Too Many", remote_addr="")

        self.assertEqual(throttled.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertFalse(
            ClientLoginRequest.objects.exclude(request_ip__isnull=True).exists()
        )

    def test_ipv4_mapped_ipv6_uses_the_ipv4_source_bucket(self):
        first = self._post(remote_addr="::ffff:192.0.2.44")
        second = self._post(client_name="Other Reader", remote_addr="192.0.2.44")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            set(ClientLoginRequest.objects.values_list("request_ip", flat=True)),
            {"192.0.2.44"},
        )

    def test_unicode_equivalent_client_metadata_has_same_fingerprint(self):
        first = self._post(client_name="Ｒｅａｄｅｒ", remote_addr="192.0.2.1")
        second = self._post(client_name="Reader", remote_addr="192.0.2.2")

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            ClientLoginRequest.objects.values("request_fingerprint").distinct().count(),
            1,
        )

    def test_creation_logs_exclude_codes_and_full_user_agents(self):
        with self.assertLogs("accounts.operational_logging", level="INFO") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                created = self._post(user_agent="secret-user-agent-value" * 20)

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        joined = "\n".join(logs.output)
        self.assertIn("Client pairing request created", joined)
        self.assertNotIn(created.json()["code"], joined)
        self.assertNotIn("secret-user-agent-value", joined)

    def test_throttle_logs_exclude_codes_and_full_user_agents(self):
        responses = []
        with self.assertLogs("accounts.operational_logging", level="INFO") as logs:
            for index in range(MAX_ACTIVE_PENDING_REQUESTS_PER_FINGERPRINT + 1):
                responses.append(
                    self._post(
                        client_name="Same Reader",
                        remote_addr=f"192.0.2.{index + 1}",
                        user_agent="secret-user-agent-value" * 20,
                    )
                )

        self.assertEqual(responses[-1].status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        joined = "\n".join(logs.output)
        self.assertIn("Client pairing request throttled", joined)
        self.assertNotIn("secret-user-agent-value", joined)
        for response in responses[:-1]:
            self.assertNotIn(response.json()["code"], joined)

    def _post(
        self,
        *,
        client_name: str = "Second Pass Reader",
        remote_addr: str = "127.0.0.1",
        forwarded_for: str | None = None,
        user_agent: str = "ReaderClient/1.0",
    ):
        extra = {
            "REMOTE_ADDR": remote_addr,
            "HTTP_USER_AGENT": user_agent,
        }
        if forwarded_for is not None:
            extra["HTTP_X_FORWARDED_FOR"] = forwarded_for
        return self.client.post(
            self.url,
            data={"client_name": client_name, "client_type": "reader"},
            format="json",
            **extra,
        )


class PairingRequestLimitConcurrencyTests(TransactionTestCase):
    reset_sequences = True
    url = "/api/v1/client-api/login-requests/"

    def test_concurrent_requests_cannot_exceed_source_limit(self):
        statuses = self._concurrent_posts(
            count=MAX_ACTIVE_PENDING_REQUESTS_PER_IP + 1,
            payload_for=lambda index: {
                "client_name": f"Reader {index}",
                "client_type": "reader",
            },
            remote_for=lambda _index: "192.0.2.10",
        )

        self.assertEqual(statuses.count(status.HTTP_201_CREATED), 5)
        self.assertEqual(statuses.count(status.HTTP_429_TOO_MANY_REQUESTS), 1)
        self.assertEqual(ClientLoginRequest.objects.count(), 5)

    def test_concurrent_requests_cannot_exceed_fingerprint_limit(self):
        statuses = self._concurrent_posts(
            count=MAX_ACTIVE_PENDING_REQUESTS_PER_FINGERPRINT + 1,
            payload_for=lambda _index: {
                "client_name": "Same Reader",
                "client_type": "reader",
            },
            remote_for=lambda index: f"192.0.2.{index + 1}",
        )

        self.assertEqual(statuses.count(status.HTTP_201_CREATED), 3)
        self.assertEqual(statuses.count(status.HTTP_429_TOO_MANY_REQUESTS), 1)
        self.assertEqual(ClientLoginRequest.objects.count(), 3)

    def _concurrent_posts(self, *, count, payload_for, remote_for):
        barrier = Barrier(count)

        def post(index):
            with orm_worker_connection_scope():
                client = APIClient()
                barrier.wait(timeout=5)
                response = client.post(
                    self.url,
                    data=payload_for(index),
                    format="json",
                    REMOTE_ADDR=remote_for(index),
                    HTTP_USER_AGENT="ReaderClient/1.0",
                )
                return response.status_code

        with ThreadPoolExecutor(max_workers=count) as executor:
            return list(executor.map(post, range(count)))
