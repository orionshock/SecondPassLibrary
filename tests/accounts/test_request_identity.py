from __future__ import annotations

from django.test import RequestFactory, SimpleTestCase, override_settings

from accounts.request_identity import get_client_ip


class ClientIpResolutionTests(SimpleTestCase):
    trusted_proxy = "10.0.0.2"

    def _request(self, *, remote_addr=None, forwarded_for=None):
        request = RequestFactory().get("/")
        if remote_addr is None:
            request.META.pop("REMOTE_ADDR", None)
        else:
            request.META["REMOTE_ADDR"] = remote_addr
        if forwarded_for is not None:
            request.META["HTTP_X_FORWARDED_FOR"] = forwarded_for
        return request

    @override_settings(TRUST_X_FORWARDED_FOR=False, TRUSTED_PROXY_IPS=[trusted_proxy])
    def test_disabled_forwarding_ignores_spoofed_header(self):
        request = self._request(
            remote_addr="127.0.0.1",
            forwarded_for="203.0.113.10",
        )

        self.assertEqual(get_client_ip(request), "127.0.0.1")

    @override_settings(TRUST_X_FORWARDED_FOR=True, TRUSTED_PROXY_IPS=[trusted_proxy])
    def test_trusted_forwarding_uses_trimmed_first_value(self):
        request = self._request(
            remote_addr=self.trusted_proxy,
            forwarded_for=" 203.0.113.10 , 10.0.0.2",
        )

        self.assertEqual(get_client_ip(request), "203.0.113.10")

    @override_settings(
        TRUST_X_FORWARDED_FOR=True,
        TRUSTED_PROXY_IPS=["10.20.0.0/16"],
    )
    def test_trusted_forwarding_accepts_peer_in_configured_cidr(self):
        request = self._request(
            remote_addr="10.20.4.8",
            forwarded_for="203.0.113.10",
        )

        self.assertEqual(get_client_ip(request), "203.0.113.10")

    @override_settings(TRUST_X_FORWARDED_FOR=True, TRUSTED_PROXY_IPS=[trusted_proxy])
    def test_invalid_forwarded_value_falls_back_to_remote_address(self):
        request = self._request(
            remote_addr=self.trusted_proxy,
            forwarded_for="unknown, 10.0.0.2",
        )

        self.assertEqual(get_client_ip(request), self.trusted_proxy)

    @override_settings(TRUST_X_FORWARDED_FOR=True, TRUSTED_PROXY_IPS=[trusted_proxy])
    def test_missing_forwarded_value_falls_back_to_remote_address(self):
        request = self._request(remote_addr=self.trusted_proxy)

        self.assertEqual(get_client_ip(request), self.trusted_proxy)

    @override_settings(TRUST_X_FORWARDED_FOR=True, TRUSTED_PROXY_IPS=[trusted_proxy])
    def test_untrusted_peer_cannot_supply_forwarded_address(self):
        request = self._request(
            remote_addr="10.0.0.3",
            forwarded_for="203.0.113.10",
        )

        self.assertEqual(get_client_ip(request), "10.0.0.3")

    def test_invalid_or_missing_remote_address_returns_none(self):
        self.assertIsNone(get_client_ip(self._request(remote_addr="not-an-ip")))
        self.assertIsNone(get_client_ip(self._request()))

    def test_ipv4_and_ipv6_are_normalized(self):
        self.assertEqual(get_client_ip(self._request(remote_addr="192.0.2.1")), "192.0.2.1")
        self.assertEqual(
            get_client_ip(self._request(remote_addr="2001:0db8:0:0::1")),
            "2001:db8::1",
        )
