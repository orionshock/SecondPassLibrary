from __future__ import annotations

from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.client_api import hash_client_secret
from accounts.models import ClientLoginRequest
from accounts.pairing_cleanup import cleanup_client_pairing_requests


class CleanupClientPairingRequestsTests(TestCase):
    def test_dry_run_changes_nothing(self):
        expired = self._request(
            status=ClientLoginRequest.STATUS_PENDING,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        result = cleanup_client_pairing_requests(dry_run=True)

        self.assertEqual(result.eligible_count, 1)
        self.assertEqual(result.selected_count, 1)
        self.assertEqual(result.would_delete_count, 1)
        self.assertEqual(result.deleted_count, 0)
        self.assertEqual(result.skipped_limit_count, 0)
        self.assertEqual(result.retained_count, 1)
        self.assertTrue(ClientLoginRequest.objects.filter(pk=expired.pk).exists())

    def test_cleanup_removes_expired_and_retained_terminal_rows(self):
        now = timezone.now()
        removable = [
            self._request(
                status=ClientLoginRequest.STATUS_PENDING,
                expires_at=now - timedelta(minutes=1),
            ),
            self._request(
                status=ClientLoginRequest.STATUS_APPROVED,
                expires_at=now - timedelta(minutes=1),
            ),
            self._request(status=ClientLoginRequest.STATUS_DENIED),
            self._request(status=ClientLoginRequest.STATUS_CONSUMED),
            self._request(status=ClientLoginRequest.STATUS_EXPIRED),
        ]
        old = now - timedelta(hours=25)
        ClientLoginRequest.objects.filter(
            pk__in=[request.pk for request in removable[2:]]
        ).update(updated_at=old)

        result = cleanup_client_pairing_requests()

        self.assertEqual(result.deleted_count, len(removable))
        self.assertFalse(
            ClientLoginRequest.objects.filter(
                pk__in=[request.pk for request in removable]
            ).exists()
        )

    def test_cleanup_preserves_active_pending_and_recent_terminal_rows(self):
        now = timezone.now()
        active = self._request(
            status=ClientLoginRequest.STATUS_PENDING,
            expires_at=now + timedelta(minutes=5),
        )
        recent_denied = self._request(status=ClientLoginRequest.STATUS_DENIED)

        result = cleanup_client_pairing_requests()

        self.assertEqual(result.deleted_count, 0)
        self.assertEqual(result.retained_count, 2)
        self.assertTrue(ClientLoginRequest.objects.filter(pk=active.pk).exists())
        self.assertTrue(ClientLoginRequest.objects.filter(pk=recent_denied.pk).exists())

    def test_cleanup_is_idempotent_and_command_reports_bounded_summary(self):
        self._request(
            status=ClientLoginRequest.STATUS_PENDING,
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        output = StringIO()

        call_command("cleanup_client_pairing_requests", stdout=output)
        second = cleanup_client_pairing_requests()

        self.assertIn(
            "dry_run=False eligible=1 selected=1 would_delete=0 deleted=1 "
            "skipped_limit=0 retained=0",
            output.getvalue(),
        )
        self.assertEqual(second.eligible_count, 0)
        self.assertEqual(second.selected_count, 0)
        self.assertEqual(second.deleted_count, 0)

    def test_cleanup_command_honors_batch_limit(self):
        for _index in range(2):
            self._request(
                status=ClientLoginRequest.STATUS_PENDING,
                expires_at=timezone.now() - timedelta(minutes=1),
            )

        output = StringIO()
        call_command("cleanup_client_pairing_requests", limit=1, stdout=output)

        self.assertEqual(ClientLoginRequest.objects.count(), 1)
        self.assertIn(
            "eligible=2 selected=1 would_delete=0 deleted=1 skipped_limit=1 retained=1",
            output.getvalue(),
        )

    def test_cleanup_logs_do_not_include_pairing_secrets(self):
        code = "PAIR-CODE"
        self._request(
            status=ClientLoginRequest.STATUS_PENDING,
            expires_at=timezone.now() - timedelta(minutes=1),
            code=code,
        )

        with self.assertLogs("accounts.operational_logging", level="INFO") as logs:
            cleanup_client_pairing_requests()

        joined = "\n".join(logs.output)
        self.assertIn("Client pairing cleanup completed", joined)
        self.assertNotIn(code, joined)
        self.assertNotIn(hash_client_secret(code), joined)

    def _request(
        self,
        *,
        status: str,
        expires_at=None,
        code: str = "CODE",
    ) -> ClientLoginRequest:
        return ClientLoginRequest.objects.create(
            code_hash=hash_client_secret(f"{code}-{ClientLoginRequest.objects.count()}"),
            client_name="Reader",
            client_type="reader",
            status=status,
            expires_at=expires_at or timezone.now() + timedelta(minutes=5),
        )
