from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts import session_control
from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession, UserWebSession
from tests.accounts.client_api.helpers import post_login_request
from tests.accounts.helpers import create_account_role_users
from tests.accounts.web_sessions.helpers import authenticated_tracked_client
from tests.utils.responses import assert_response, response_data_dict


User = get_user_model()


class AccountOperationalLoggingTests(APITestCase):
    def setUp(self):
        users = create_account_role_users()
        self.owner = users.owner
        self.manager = users.manager
        self.reader = users.reader

    def test_managed_user_created_logs_safe_info(self):
        self.client.login(username="manager", password="pw")

        with self.assertLogs("accounts.operational_logging", level="INFO") as logs:
            response = assert_response(
                self.client.post(
                    "/api/v1/accounts/users/",
                    data={
                        "username": "new-reader",
                        "email": "new-reader@example.test",
                        "first_name": "New",
                        "last_name": "Reader",
                        "role": "reader",
                        "is_active": True,
                    },
                    format="json",
                )
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(logs.output), 1)
        message = logs.output[0]
        self.assertIn("Managed user created", message)
        self.assertIn("actor=manager", message)
        self.assertIn("target=new-reader", message)
        self.assertIn("role=reader", message)
        self.assertNotIn("New Reader", message)
        self.assertNotIn("example.test", message)
        self.assertNotIn("temporary_password", message)

    def test_managed_user_update_logs_only_changed_fields(self):
        self.reader.first_name = "Same"
        self.reader.save(update_fields=["first_name"])
        self.client.login(username="manager", password="pw")

        with self.assertLogs("accounts.operational_logging", level="INFO") as logs:
            response = assert_response(
                self.client.patch(
                    f"/api/v1/accounts/users/{self.reader.profile.id}/",
                    data={
                        "first_name": "Same",
                        "last_name": "Changed",
                        "role": "librarian",
                    },
                    format="json",
                )
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        message = self._one_message_containing(logs.output, "Managed user updated")
        self.assertIn("actor=manager", message)
        self.assertIn("target=reader", message)
        self.assertIn("changed_fields=last_name,role", message)
        self.assertNotIn("first_name", message)
        self.assertIn("role_old=reader", message)
        self.assertIn("role_new=librarian", message)
        self.assertNotIn("Changed", message)

    def test_disable_logs_user_change_and_revocation_counts(self):
        self._make_web_sessions(self.reader, username="reader")
        self._make_client_session(self.reader)
        self.client.login(username="manager", password="pw")

        with self.assertLogs("accounts.operational_logging", level="INFO") as logs:
            response = assert_response(
                self.client.patch(
                    f"/api/v1/accounts/users/{self.reader.profile.id}/",
                    data={"is_active": False},
                    format="json",
                )
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        joined = "\n".join(logs.output)
        self.assertIn("Managed user disabled", joined)
        self.assertIn("actor=manager target=reader", joined)
        self.assertIn("revoked_web_sessions=2", joined)
        self.assertIn("revoked_client_sessions=1", joined)
        self.assertIn("Managed user updated", joined)
        self.assertIn("active_old=True", joined)
        self.assertIn("active_new=False", joined)
        self.assertIn("reason=user_disabled count=2", joined)
        self.assertIn("reason=user_disabled count=1", joined)

    def test_self_password_change_logs_event_and_revocation_counts(self):
        self._make_web_sessions(self.reader, username="reader")
        self._make_client_session(self.reader)
        self.client.login(username="reader", password="pw")

        with self.assertLogs("accounts.operational_logging", level="INFO") as logs:
            response = assert_response(
                self.client.post(
                    "/api/v1/accounts/me/change-password/",
                    data={
                        "current_password": "pw",
                        "new_password": "NewPassw0rd!",
                        "confirm_password": "NewPassw0rd!",
                    },
                    format="json",
                )
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        joined = "\n".join(logs.output)
        self.assertIn("Self password changed", joined)
        self.assertIn("reason=password_change", joined)
        self.assertNotIn("NewPassw0rd", joined)

    def test_managed_password_reset_logs_event_and_revocation_counts(self):
        self._make_web_sessions(self.reader, username="reader")
        self._make_client_session(self.reader)
        self.client.login(username="manager", password="pw")

        with self.assertLogs("accounts.operational_logging", level="INFO") as logs:
            response = assert_response(
                self.client.post(
                    f"/api/v1/accounts/users/{self.reader.profile.id}/reset-password/",
                    data={},
                    format="json",
                )
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        joined = "\n".join(logs.output)
        self.assertIn("Managed password reset completed", joined)
        self.assertIn("reason=managed_reset count=2", joined)
        self.assertIn("reason=managed_reset count=1", joined)
        payload = response_data_dict(response)
        self.assertNotIn(str(payload["temporary_password"]), joined)

    def test_explicit_other_web_sessions_revoke_logs_count(self):
        self._make_web_sessions(self.reader, username="reader")
        self.client.login(username="reader", password="pw")

        with self.assertLogs("accounts.operational_logging", level="INFO") as logs:
            response = assert_response(
                self.client.post("/api/v1/accounts/me/web-sessions/logout-others/")
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Web sessions revoked", logs.output[0])
        self.assertIn("reason=manual_revoke", logs.output[0])
        self.assertIn("count=2", logs.output[0])

    def test_manual_client_session_revoke_logs_safe_info(self):
        session = self._make_client_session(self.reader, name="Kitchen Reader")
        self.client.login(username="reader", password="pw")

        with self.assertLogs("accounts.operational_logging", level="INFO") as logs:
            response = self.client.delete(f"/api/v1/accounts/me/client-sessions/{session.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        message = logs.output[0]
        self.assertIn("Client session revoked", message)
        self.assertIn(str(session.id), message)
        self.assertIn("client_type=reader", message)
        self.assertNotIn("Kitchen Reader", message)
        self.assertNotIn(session.token_hash, message)

    def test_client_pairing_lifecycle_logs_safe_info(self):
        response = assert_response(post_login_request(self.client))
        body = response_data_dict(response)
        request_id = str(body["id"])
        code = str(body["code"])
        self.client.force_login(self.reader)

        with self.assertLogs("accounts.operational_logging", level="INFO") as logs:
            approved = self.client.post(
                "/client-api/authorize/",
                data={"code": code, "action": "approve", "client_name": "Phone Reader"},
            )
            polled = assert_response(
                self.client.get(f"/api/v1/client-api/login-requests/{request_id}/poll/")
            )

        self.assertEqual(approved.status_code, status.HTTP_200_OK)
        self.assertEqual(polled.status_code, status.HTTP_200_OK)
        joined = "\n".join(logs.output)
        self.assertIn("Client pairing approved", joined)
        self.assertIn("Client session created from pairing", joined)
        self.assertIn(request_id, joined)
        self.assertIn("client_type=reader", joined)
        self.assertNotIn(code, joined)
        self.assertNotIn("Phone Reader", joined)
        self.assertNotIn(str(response_data_dict(polled)["access_token"]), joined)

    def test_client_pairing_denial_logs_safe_info(self):
        response = assert_response(post_login_request(self.client))
        body = response_data_dict(response)
        code = str(body["code"])
        self.client.force_login(self.reader)

        with self.assertLogs("accounts.operational_logging", level="INFO") as logs:
            denied = self.client.post(
                "/client-api/authorize/",
                data={"code": code, "action": "deny", "client_name": "Phone Reader"},
            )

        self.assertEqual(denied.status_code, status.HTTP_200_OK)
        self.assertIn("Client pairing denied", logs.output[0])
        self.assertIn(str(body["id"]), logs.output[0])
        self.assertNotIn(code, logs.output[0])
        self.assertNotIn("Phone Reader", logs.output[0])

    def test_expected_validation_failures_do_not_emit_error(self):
        self.client.login(username="reader", password="pw")

        with patch("accounts.operational_logging.logger.error") as error:
            response = assert_response(
                self.client.post(
                    "/api/v1/accounts/me/change-password/",
                    data={
                        "current_password": "wrong",
                        "new_password": "NewPassw0rd!",
                        "confirm_password": "NewPassw0rd!",
                    },
                    format="json",
                )
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        error.assert_not_called()

    def test_unexpected_explicit_revoke_failure_logs_one_safe_error(self):
        session = self._make_client_session(self.reader, name="Kitchen Reader")

        with (
            patch(
                "accounts.session_control.UserClientSession.objects.filter",
                side_effect=RuntimeError("secret-token-value"),
            ),
            self.assertLogs("accounts.operational_logging", level="ERROR") as logs,
        ):
            with self.assertRaises(RuntimeError):
                session_control.revoke_client_session(session, actor=self.reader)

        self.assertEqual(len(logs.output), 1)
        message = logs.output[0]
        self.assertIn("exception=RuntimeError", message)
        self.assertIn(str(session.id), message)
        self.assertNotIn("secret-token-value", message)
        self.assertNotIn("Kitchen Reader", message)
        self.assertNotIn(session.token_hash, message)

    def test_unexpected_reset_revocation_failure_logs_one_safe_error(self):
        self.client.login(username="manager", password="pw")

        with (
            patch(
                "accounts.session_control.UserWebSession.objects.filter",
                side_effect=RuntimeError("session-key-secret"),
            ),
            self.assertLogs("accounts.operational_logging", level="ERROR") as logs,
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    f"/api/v1/accounts/users/{self.reader.profile.id}/reset-password/",
                    data={},
                    format="json",
                )

        self.assertEqual(len(logs.output), 1)
        self.assertIn("Web session revocation failed", logs.output[0])
        self.assertIn("exception=RuntimeError", logs.output[0])
        self.assertNotIn("session-key-secret", logs.output[0])

    def _make_web_sessions(self, user, *, username: str) -> None:
        authenticated_tracked_client(self, username=username)
        authenticated_tracked_client(self, username=username)
        self.assertEqual(UserWebSession.objects.filter(user=user).count(), 2)
        self.assertEqual(Session.objects.count(), 2)

    def _make_client_session(self, user, *, name: str = "Reader") -> UserClientSession:
        return UserClientSession.objects.create(
            user=user,
            name=name,
            client_type="reader",
            token_hash=hash_client_secret(f"spl_testtoken_{user.pk}_{name}"),
            last_seen_at=None,
            expires_at=timezone.now() + timedelta(days=1),
            revoked_at=None,
        )

    def _one_message_containing(self, messages: list[str], needle: str) -> str:
        matches = [message for message in messages if needle in message]
        self.assertEqual(len(matches), 1)
        return matches[0]
