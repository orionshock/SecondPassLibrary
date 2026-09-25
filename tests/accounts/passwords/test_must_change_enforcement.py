from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_sessions.services import hash_client_secret
from accounts.models import UserClientSession, UserProfile, UserWebSession
from accounts.request_actor import RequestActorContext
from tests.accounts.helpers import create_account_role_users
from tests.accounts.web_sessions.helpers import authenticated_tracked_client
from tests.utils.library_visibility import ensure_public_membership


User = get_user_model()


class MustChangePasswordEnforcementTests(APITestCase):
    def setUp(self):
        users = create_account_role_users()
        self.owner = users.owner
        self.manager = users.manager
        self.librarian = users.librarian
        self.reader = users.reader
        ensure_public_membership(self.reader)

    def test_flagged_reader_session_cannot_use_application_apis(self):
        self._flag_and_login(self.reader)

        requests = (
            self.client.get("/api/v1/library/books/"),
            self.client.post(
                "/api/v1/shelves/",
                {"name": "Blocked", "owner_type": "user"},
                format="json",
            ),
            self.client.get("/api/v1/marginalia/books/"),
            self.client.post(
                "/api/v1/marginalia/books/00000000-0000-0000-0000-000000000001/open/",
                {},
                format="json",
            ),
            self.client.get("/api/v1/marginalia/export/"),
            self.client.get("/api/v1/library/groups/"),
            self.client.patch(
                "/api/v1/accounts/me/",
                {"first_name": "Blocked"},
                format="json",
            ),
        )

        for response in requests:
            with self.subTest(path=response.wsgi_request.path):
                self._assert_password_change_required(response)

    def test_flagged_librarian_cannot_import_or_mutate_library(self):
        self._flag_and_login(self.librarian)

        upload = self.client.post("/api/v1/library/imports/", {}, format="multipart")
        mutation = self.client.patch(
            "/api/v1/library/books/00000000-0000-0000-0000-000000000001/",
            {"title": "Blocked"},
            format="json",
        )

        self._assert_password_change_required(upload)
        self._assert_password_change_required(mutation)

    def test_flagged_manager_cannot_use_management_or_server_settings(self):
        self._flag_and_login(self.manager)

        users = self.client.get("/api/v1/accounts/users/")
        settings = self.client.get("/api/v1/server/settings/")

        self._assert_password_change_required(users)
        self._assert_password_change_required(settings)

    def test_minimal_bootstrap_reads_remain_available(self):
        self._flag_and_login(self.reader)

        me = self.client.get("/api/v1/accounts/me/")
        server = self.client.get("/api/v1/server/info/")

        self.assertEqual(me.status_code, status.HTTP_200_OK)
        self.assertTrue(me.json()["must_change_password"])
        self.assertEqual(server.status_code, status.HTTP_200_OK)

    def test_password_change_clears_flag_and_immediately_restores_access(self):
        self._flag_and_login(self.reader)

        with self.assertLogs("accounts.operational_logging", level="INFO") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                changed = self.client.post(
                    "/api/v1/accounts/me/change-password/",
                    {
                        "current_password": "pw",
                        "new_password": "NewPassw0rd!",
                        "confirm_password": "NewPassw0rd!",
                    },
                    format="json",
                )
        restored = self.client.get("/api/v1/library/books/")

        self.assertEqual(changed.status_code, status.HTTP_200_OK)
        self.assertEqual(restored.status_code, status.HTTP_200_OK)
        self.reader.profile.refresh_from_db()
        self.assertFalse(self.reader.profile.must_change_password)
        self.assertIn("_auth_user_id", self.client.session)
        joined = "\n".join(logs.output)
        self.assertIn("Self password changed", joined)
        self.assertIn("forced=True", joined)
        self.assertNotIn("NewPassw0rd", joined)

    def test_flagged_user_can_log_out(self):
        self._flag_and_login(self.reader)

        response = self.client.post("/logout/")

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response["Location"], "/login/")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_product_shell_password_route_and_static_asset_remain_reachable(self):
        self._flag_and_login(self.reader)
        with TemporaryDirectory() as directory:
            product_ui = Path(directory)
            (product_ui / "index.html").write_text(
                '<!doctype html><div id="root"></div>',
                encoding="utf-8",
            )
            (product_ui / "collected-static").mkdir()
            with override_settings(
                PRODUCT_UI_DIR=product_ui,
                STATIC_ROOT=product_ui / "collected-static",
                WHITENOISE_USE_FINDERS=True,
            ):
                password_page = self.client.get("/profile/password")
                other_shell = self.client.get("/library")
                static_asset = self.client.get("/static/web/app.css")

        self.assertEqual(password_page.status_code, status.HTTP_200_OK)
        self.assertEqual(other_shell.status_code, status.HTTP_200_OK)
        self.assertEqual(static_asset.status_code, status.HTTP_200_OK)

    def test_bearer_authentication_is_not_restricted_by_session_policy(self):
        self._flag(self.reader)
        token = "spl_must_change_bearer"
        UserClientSession.objects.create(
            user=self.reader,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )

        with patch("accounts.middleware.get_request_actor_context") as acquire:
            response = APIClient().get(
                "/api/v1/library/books/",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        acquire.assert_not_called()

    def test_anonymous_login_and_setup_behavior_is_unchanged(self):
        login = self.client.get("/login/")
        setup = self.client.get("/setup/")

        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertEqual(setup.status_code, status.HTTP_302_FOUND)
        self.assertEqual(setup["Location"], "/login/")

    def test_enforcement_runs_after_session_user_authentication(self):
        self._flag_and_login(self.reader)

        with self.assertLogs("accounts.operational_logging", level="DEBUG") as logs:
            response = self.client.get("/api/v1/library/books/")

        self._assert_password_change_required(response)
        self.assertIn(f"actor={self.reader.profile.pk}", logs.output[0])
        self.assertIn("area=library", logs.output[0])

    def test_api_classification_uses_path_info_and_returns_json(self):
        self._flag_and_login(self.reader)

        exact_api = self.client.get("/api")
        prefixed = self.client.get(
            "/api/v1/not-a-route/",
            SCRIPT_NAME="/secondpass",
        )
        unknown = self.client.get("/api/v1/not-a-route/")

        self._assert_password_change_required(exact_api)
        self._assert_password_change_required(prefixed)
        self._assert_password_change_required(unknown)
        self.assertEqual(prefixed.wsgi_request.path, "/secondpass/api/v1/not-a-route/")
        self.assertEqual(prefixed.wsgi_request.path_info, "/api/v1/not-a-route/")

    def test_browser_and_lookalike_paths_redirect_to_password_change(self):
        self._flag_and_login(self.reader)

        for path in ("/not-an-api", "/profileevil"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, status.HTTP_302_FOUND)
                self.assertEqual(response["Location"], "/profile/password")

    def test_api_policy_lookup_failure_is_bounded_json_and_stops_dispatch(self):
        self._flag_and_login(self.reader)
        actor = RequestActorContext(
            user_id=self.reader.pk,
            username=self.reader.username,
            first_name=self.reader.first_name,
            last_name=self.reader.last_name,
            profile_id=self.reader.profile.id,
            role=self.reader.profile.role,
            web_session_generation=self.reader.profile.web_session_generation,
            must_change_password=True,
        )

        with (
            patch(
                "accounts.middleware.get_request_actor_context",
                side_effect=[actor, RuntimeError("secret policy failure")],
            ),
            patch("library.catalog.views.BookListView.get_queryset") as dispatched,
            self.assertLogs("accounts.operational_logging", level="ERROR") as logs,
        ):
            response = self.client.get("/api/v1/library/books/")

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(
            response.json(),
            {
                "detail": "Unable to verify password-change policy.",
                "code": "password_policy_check_failed",
            },
        )
        dispatched.assert_not_called()
        self.assertNotIn("secret policy failure", response.content.decode("utf-8"))
        self.assertNotIn("secret policy failure", "\n".join(logs.output))

    def test_browser_policy_lookup_failure_uses_normal_error_boundary(self):
        self._flag_and_login(self.reader)
        actor = RequestActorContext(
            user_id=self.reader.pk,
            username=self.reader.username,
            first_name=self.reader.first_name,
            last_name=self.reader.last_name,
            profile_id=self.reader.profile.id,
            role=self.reader.profile.role,
            web_session_generation=self.reader.profile.web_session_generation,
            must_change_password=True,
        )

        with (
            patch(
                "accounts.middleware.get_request_actor_context",
                side_effect=[actor, RuntimeError("secret browser failure")],
            ),
            self.assertLogs("accounts.operational_logging", level="ERROR") as logs,
        ):
            with self.assertRaisesRegex(RuntimeError, "secret browser failure"):
                self.client.get("/profile/password")

        self.assertNotIn("secret browser failure", "\n".join(logs.output))

    def _flag_and_login(self, user) -> None:
        self._flag(user)
        self.client.force_login(user)

    @staticmethod
    def _flag(user) -> None:
        UserProfile.objects.filter(user=user).update(must_change_password=True)
        user.profile.refresh_from_db()

    def _assert_password_change_required(self, response) -> None:
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.json(),
            {
                "detail": "Password change required.",
                "code": "password_change_required",
            },
        )


class ManagedResetPasswordEnforcementTests(APITestCase):
    def test_reset_revokes_credentials_then_temporary_login_is_restricted(self):
        owner = User.objects.create_superuser(username="owner", password="pw")
        target = User.objects.create_user(username="target", password="pw")
        ensure_public_membership(target)
        _tracked, session_key = authenticated_tracked_client(self, username="target")
        token = "spl_reset_target"
        client_session = UserClientSession.objects.create(
            user=target,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        actor = APIClient()
        actor.force_login(owner)

        with self.captureOnCommitCallbacks(execute=True):
            reset = actor.post(
                f"/api/v1/accounts/users/{target.profile.pk}/reset-password/",
                {},
                format="json",
            )

        self.assertEqual(reset.status_code, status.HTTP_200_OK)
        self.assertFalse(Session.objects.filter(session_key=session_key).exists())
        self.assertFalse(UserWebSession.objects.filter(user=target).exists())
        client_session.refresh_from_db()
        self.assertIsNotNone(client_session.revoked_at)
        target.profile.refresh_from_db()
        self.assertTrue(target.profile.must_change_password)

        temporary_password = reset.json()["temporary_password"]
        login = APIClient()
        self.assertTrue(login.login(username="target", password=temporary_password))
        blocked = login.get("/api/v1/library/books/")
        self.assertEqual(blocked.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(blocked.json()["code"], "password_change_required")
