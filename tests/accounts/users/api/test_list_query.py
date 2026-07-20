from __future__ import annotations

import pytest
from rest_framework import status

from core import server_settings
from library.models import LibraryGroup, LibraryGroupMembership
from tests.accounts.users.helpers import ManagedUsersApiTestMixin
from tests.utils.responses import assert_response, response_data_dict, response_data_list


pytestmark = [pytest.mark.integration]


class ManagedUsersListQueryAPITest(ManagedUsersApiTestMixin):
    def setUp(self):
        super().setUp()
        self.reader.first_name = "Ada"
        self.reader.last_name = "Lovelace"
        self.reader.save(update_fields=["first_name", "last_name"])

    def get_users(self, query: str = ""):
        self.client.login(username="owner", password="pw")
        return assert_response(self.client.get(f"/api/v1/accounts/users/{query}"))

    def test_q_searches_management_visible_identity_fields(self):
        for query in ("reader", "Ada", "Lovelace", "Ada%20Lovelace", "reader%40example.com"):
            with self.subTest(query=query):
                response = self.get_users(f"?q={query}")
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(
                    [row["username"] for row in response_data_list(response)],
                    ["reader"],
                )

    def test_role_filters_owner_and_profile_roles(self):
        expected = {
            "owner": {"owner"},
            "manager": {"manager", "manager2"},
            "librarian": {"librarian"},
            "reader": {"reader"},
        }
        for role, usernames in expected.items():
            with self.subTest(role=role):
                response = self.get_users(f"?role={role}")
                self.assertEqual(
                    {row["username"] for row in response_data_list(response)},
                    usernames,
                )

    def test_curator_filter_is_derived_and_advanced_mode_only(self):
        group = LibraryGroup.objects.create(name="Curated")
        LibraryGroupMembership.objects.create(
            user=self.reader, group=group, is_curator=True
        )
        disabled = self.get_users("?role=curator")
        self.assertEqual(disabled.status_code, status.HTTP_400_BAD_REQUEST)

        server_settings.enable_advanced_library_groups()
        enabled = self.get_users("?role=curator")
        self.assertEqual(enabled.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [row["username"] for row in response_data_list(enabled)], ["reader"]
        )

    def test_active_and_combined_filters_affect_count(self):
        self.reader.is_active = False
        self.reader.save(update_fields=["is_active"])
        inactive = self.get_users("?is_active=false")
        self.assertEqual(
            {row["username"] for row in response_data_list(inactive)}, {"reader"}
        )
        active = self.get_users("?is_active=true")
        self.assertNotIn(
            "reader", {row["username"] for row in response_data_list(active)}
        )
        combined = self.get_users("?q=Ada&role=reader&is_active=false&page_size=1")
        payload = response_data_dict(combined)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["results"][0]["username"], "reader")

    def test_supported_orderings_are_deterministic(self):
        self.manager.first_name = "Zed"
        self.manager.last_name = "Alpha"
        self.manager.save(update_fields=["first_name", "last_name"])
        self.manager2.first_name = "Amy"
        self.manager2.last_name = "Zulu"
        self.manager2.save(update_fields=["first_name", "last_name"])
        self.reader.is_active = False
        self.reader.save(update_fields=["is_active"])

        expectations = {
            "username": ["librarian", "manager", "manager2", "owner", "reader"],
            "-username": ["reader", "owner", "manager2", "manager", "librarian"],
            "name": ["librarian", "owner", "manager", "reader", "manager2"],
            "-name": ["manager2", "reader", "manager", "owner", "librarian"],
            "role": ["owner", "manager", "manager2", "librarian", "reader"],
            "-role": ["reader", "librarian", "manager2", "manager", "owner"],
            "is_active": ["reader", "librarian", "manager", "manager2", "owner"],
            "-is_active": ["owner", "manager2", "manager", "librarian", "reader"],
        }
        for ordering, usernames in expectations.items():
            with self.subTest(ordering=ordering):
                response = self.get_users(f"?ordering={ordering}")
                self.assertEqual(
                    [row["username"] for row in response_data_list(response)],
                    usernames,
                )

    def test_invalid_filters_return_bounded_400(self):
        for query, field in (
            ("?role=nope", "role"),
            ("?is_active=maybe", "is_active"),
            ("?ordering=email", "ordering"),
        ):
            with self.subTest(query=query):
                response = self.get_users(query)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response_data_dict(response))

    def test_anonymous_cannot_list_managed_users(self):
        response = assert_response(self.client.get("/api/v1/accounts/users/"))
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )
