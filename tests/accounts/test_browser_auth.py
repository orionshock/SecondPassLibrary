from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from accounts.login_throttle import (
    LOGIN_SOURCE_ATTEMPT_LIMIT,
    LOGIN_USERNAME_ATTEMPT_LIMIT,
)
from accounts.models import BrowserLoginThrottleSlot


User = get_user_model()
INVALID_LOGIN_MESSAGE = "Please enter a correct username and password."
THROTTLED_LOGIN_MESSAGE = "Too many login attempts."


class BrowserLoginThrottleTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(username="owner", password="OwnerPassw0rd!")
        self.user = User.objects.create_user(username="Reader", password="ReaderPassw0rd!")

    def _post(self, username: str, *, remote_addr: str | None = "192.0.2.10", **extra):
        request_extra = dict(extra)
        if remote_addr is not None:
            request_extra["REMOTE_ADDR"] = remote_addr
        return self.client.post(
            "/login/",
            {"username": username, "password": "wrong-password"},
            **request_extra,
        )

    def test_ordinary_known_and_unknown_login_failures_are_generic(self):
        known = self._post("Reader", remote_addr="192.0.2.10")
        unknown = self._post("does-not-exist", remote_addr="192.0.2.11")

        self.assertEqual(known.status_code, 200)
        self.assertEqual(unknown.status_code, 200)
        self.assertContains(known, INVALID_LOGIN_MESSAGE)
        self.assertContains(unknown, INVALID_LOGIN_MESSAGE)
        self.assertNotContains(known, THROTTLED_LOGIN_MESSAGE)
        self.assertNotContains(unknown, THROTTLED_LOGIN_MESSAGE)

    def test_source_attempt_limit_is_shared_across_usernames(self):
        for index in range(LOGIN_SOURCE_ATTEMPT_LIMIT):
            response = self._post(f"unknown-{index}")
            self.assertContains(response, INVALID_LOGIN_MESSAGE)

        throttled = self._post("another-unknown")

        self.assertContains(throttled, THROTTLED_LOGIN_MESSAGE)
        self.assertEqual(
            BrowserLoginThrottleSlot.objects.filter(
                bucket_type=BrowserLoginThrottleSlot.BUCKET_SOURCE
            ).count(),
            LOGIN_SOURCE_ATTEMPT_LIMIT,
        )

    def test_username_attempt_limit_is_shared_across_sources(self):
        for index in range(LOGIN_USERNAME_ATTEMPT_LIMIT):
            response = self._post("Reader", remote_addr=f"192.0.2.{index + 1}")
            self.assertContains(response, INVALID_LOGIN_MESSAGE)

        throttled = self._post("Reader", remote_addr="192.0.2.99")

        self.assertContains(throttled, THROTTLED_LOGIN_MESSAGE)

    def test_expired_slots_do_not_block_a_new_attempt(self):
        for index in range(LOGIN_USERNAME_ATTEMPT_LIMIT):
            self._post("Reader", remote_addr=f"192.0.2.{index + 1}")
        BrowserLoginThrottleSlot.objects.update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

        response = self._post("Reader", remote_addr="192.0.2.99")

        self.assertContains(response, INVALID_LOGIN_MESSAGE)
        self.assertNotContains(response, THROTTLED_LOGIN_MESSAGE)

    def test_successful_login_clears_source_and_username_failures(self):
        self._post("Reader")
        self._post("Reader")

        response = self.client.post(
            "/login/",
            {"username": "Reader", "password": "ReaderPassw0rd!"},
            REMOTE_ADDR="192.0.2.10",
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(BrowserLoginThrottleSlot.objects.count(), 0)
        self.assertIn("_auth_user_id", self.client.session)

    def test_field_invalid_login_cannot_clear_existing_source_failures(self):
        self._post("first")
        self._post("second")
        before = BrowserLoginThrottleSlot.objects.filter(
            bucket_type=BrowserLoginThrottleSlot.BUCKET_SOURCE
        ).count()

        response = self._post("")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            BrowserLoginThrottleSlot.objects.filter(
                bucket_type=BrowserLoginThrottleSlot.BUCKET_SOURCE
            ).count(),
            before,
        )

    def test_username_case_and_outer_whitespace_share_a_bucket(self):
        variants = ["Reader", "reader", " READER", "reader ", " ReAdEr "]
        for index, username in enumerate(variants):
            self._post(username, remote_addr=f"192.0.2.{index + 1}")

        throttled = self._post("reader", remote_addr="192.0.2.99")

        self.assertContains(throttled, THROTTLED_LOGIN_MESSAGE)
        username_keys = BrowserLoginThrottleSlot.objects.filter(
            bucket_type=BrowserLoginThrottleSlot.BUCKET_USERNAME
        ).values_list("bucket_key", flat=True).distinct()
        self.assertEqual(len(list(username_keys)), 1)

    def test_missing_source_and_ipv4_mapped_ipv6_use_bounded_canonical_buckets(self):
        for index in range(LOGIN_SOURCE_ATTEMPT_LIMIT):
            self._post(f"missing-{index}", remote_addr="")
        missing_throttled = self._post("missing-final", remote_addr="")
        self.assertContains(missing_throttled, THROTTLED_LOGIN_MESSAGE)

        BrowserLoginThrottleSlot.objects.all().delete()
        for index in range(LOGIN_SOURCE_ATTEMPT_LIMIT):
            address = "::ffff:192.0.2.50" if index % 2 else "192.0.2.50"
            self._post(f"mapped-{index}", remote_addr=address)
        mapped_throttled = self._post("mapped-final", remote_addr="192.0.2.50")
        self.assertContains(mapped_throttled, THROTTLED_LOGIN_MESSAGE)

    def test_forwarded_source_is_ignored_by_default(self):
        self._post("first", HTTP_X_FORWARDED_FOR="198.51.100.1")
        self._post("second", HTTP_X_FORWARDED_FOR="198.51.100.2")

        source_keys = BrowserLoginThrottleSlot.objects.filter(
            bucket_type=BrowserLoginThrottleSlot.BUCKET_SOURCE
        ).values_list("bucket_key", flat=True).distinct()
        self.assertEqual(len(list(source_keys)), 1)

    @override_settings(
        TRUST_X_FORWARDED_FOR=True,
        TRUSTED_PROXY_IPS=["192.0.2.10"],
    )
    def test_forwarded_source_is_used_only_for_an_exact_trusted_peer(self):
        self._post("first", HTTP_X_FORWARDED_FOR="198.51.100.1")
        self._post("second", HTTP_X_FORWARDED_FOR="198.51.100.2")
        self._post(
            "third",
            remote_addr="192.0.2.11",
            HTTP_X_FORWARDED_FOR="198.51.100.1",
        )

        source_keys = BrowserLoginThrottleSlot.objects.filter(
            bucket_type=BrowserLoginThrottleSlot.BUCKET_SOURCE
        ).values_list("bucket_key", flat=True).distinct()
        self.assertEqual(len(list(source_keys)), 3)

    def test_threshold_logging_is_once_bounded_and_secret_free(self):
        with self.assertLogs("accounts.operational_logging", level="WARNING") as logs:
            for index in range(LOGIN_USERNAME_ATTEMPT_LIMIT):
                self._post("SensitiveReader", remote_addr=f"192.0.2.{index + 1}")

        joined = "\n".join(logs.output)
        self.assertEqual(len(logs.output), 1)
        self.assertIn("dimension=username", joined)
        self.assertIn(f"count={LOGIN_USERNAME_ATTEMPT_LIMIT}", joined)
        self.assertNotIn("SensitiveReader", joined)
        self.assertNotIn("wrong-password", joined)
        self.assertNotIn("192.0.2", joined)


class ConcurrentBrowserLoginThrottleTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        User.objects.create_superuser(username="owner", password="OwnerPassw0rd!")

    @staticmethod
    def _failed_login(index: int) -> int:
        close_old_connections()
        try:
            response = Client().post(
                "/login/",
                {"username": f"concurrent-{index}", "password": "wrong-password"},
                REMOTE_ADDR="192.0.2.80",
            )
            return response.status_code
        finally:
            close_old_connections()

    def test_concurrent_failures_cannot_exceed_source_slot_limit(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            statuses = list(pool.map(self._failed_login, range(14)))

        self.assertEqual(statuses, [200] * 14)
        self.assertEqual(
            BrowserLoginThrottleSlot.objects.filter(
                bucket_type=BrowserLoginThrottleSlot.BUCKET_SOURCE
            ).count(),
            LOGIN_SOURCE_ATTEMPT_LIMIT,
        )


class BrowserLogoutTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(
            username="owner", password="OwnerPassw0rd!"
        )

    def test_get_logout_is_method_rejected_without_invalidating_session(self):
        self.client.force_login(self.owner)

        response = self.client.get("/logout/")

        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_post_logout_invalidates_session_and_redirects(self):
        self.client.force_login(self.owner)

        response = self.client.post("/logout/")

        self.assertRedirects(response, "/login/", fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_sdk_style_post_logout_returns_no_content(self):
        self.client.force_login(self.owner)

        response = self.client.post("/logout/", HTTP_ACCEPT="application/json")

        self.assertEqual(response.status_code, 204)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_post_logout_requires_csrf_and_failure_keeps_session(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)

        response = client.post("/logout/")

        self.assertEqual(response.status_code, 403)
        self.assertIn("_auth_user_id", client.session)

    def test_post_logout_accepts_a_valid_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        client.get("/login/")
        token = client.cookies["csrftoken"].value

        response = client.post("/logout/", HTTP_X_CSRFTOKEN=token)

        self.assertEqual(response.status_code, 302)
        self.assertNotIn("_auth_user_id", client.session)

    def test_forced_password_user_and_anonymous_client_can_post_logout(self):
        self.owner.profile.must_change_password = True
        self.owner.profile.save(update_fields=["must_change_password"])
        self.client.force_login(self.owner)

        forced = self.client.post("/logout/")
        anonymous = self.client.post("/logout/")

        self.assertEqual(forced.status_code, 302)
        self.assertEqual(anonymous.status_code, 302)
