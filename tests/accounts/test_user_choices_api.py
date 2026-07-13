from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession, UserProfile
from library.models import LibraryGroup, LibraryGroupMembership
from tests.utils.responses import assert_response, response_data_dict
from tests.utils.users import set_user_role


User = get_user_model()


class UserChoiceApiTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.alice = User.objects.create_user(
            username="alice",
            email="alice@example.test",
            first_name="Alice",
            last_name="Example",
            password="pw",
        )
        self.alicia = User.objects.create_user(username="alicia", password="pw")
        self.inactive = User.objects.create_user(
            username="alice-inactive", password="pw", is_active=False
        )
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)
        set_user_role(self.librarian, UserProfile.ROLE_LIBRARIAN)
        set_user_role(self.reader, UserProfile.ROLE_READER)
        self.group = LibraryGroup.objects.create(name="Choice exclusion")
        LibraryGroupMembership.objects.create(user=self.alicia, group=self.group)

    def _results(self, response):
        payload = response_data_dict(assert_response(response))
        self.assertIn("count", payload)
        self.assertIn("next", payload)
        self.assertIn("previous", payload)
        return payload["results"]

    def test_manager_and_owner_receive_only_active_username_choices(self):
        for username in ("manager", "owner"):
            with self.subTest(username=username):
                self.client.logout()
                self.client.login(username=username, password="pw")
                response = self.client.get("/api/v1/accounts/user-choices/?q=alice")

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                results = self._results(response)
                self.assertEqual(
                    {row["username"] for row in results}, {"alice"}
                )
                self.assertEqual(
                    set(results[0]), {"profile_id", "username"}
                )

    def test_searches_username_and_excludes_existing_group_members(self):
        self.client.login(username="owner", password="pw")
        response = self.client.get(
            "/api/v1/accounts/user-choices/",
            {"q": "ali", "exclude_group": str(self.group.id)},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self._results(response)
        self.assertEqual([row["username"] for row in results], ["alice"])

    def test_invalid_exclude_group_uuid_is_rejected(self):
        self.client.login(username="manager", password="pw")
        response = self.client.get(
            "/api/v1/accounts/user-choices/?exclude_group=not-a-uuid"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("exclude_group", response.json())

    def test_reader_librarian_and_bearer_are_denied(self):
        for username in ("reader", "librarian"):
            with self.subTest(username=username):
                self.client.logout()
                self.client.login(username=username, password="pw")
                response = self.client.get("/api/v1/accounts/user-choices/?q=ali")
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        token = "spl_user_choice_test"
        UserClientSession.objects.create(
            user=self.manager,
            name="Reader client",
            client_type="reader",
            token_hash=hash_client_secret(token),
        )
        bearer_client = APIClient()
        response = bearer_client.get(
            "/api/v1/accounts/user-choices/?q=ali",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
