from __future__ import annotations

import pytest
from rest_framework import status

from library.models import LibraryGroup
from tests.library.groups.helpers import BaseLibraryGroupsAPITest
from tests.library.helpers import create_manager_user, create_reader_user
from tests.utils.responses import payload_list, response_data_dict, assert_response


pytestmark = [pytest.mark.integration]


class LibraryGroupVisibilityAPITest(BaseLibraryGroupsAPITest):
    def setUp(self):
        super().setUp()

        self.reader = create_reader_user(
            username="reader",
            email="reader@example.com",
            password="pw",
        )

        self.manager = create_manager_user(
            username="manager",
            email="manager@example.com",
            password="pw",
        )

        self.member_group = LibraryGroup.objects.create(name="MemberGroup")
        self.other_group = LibraryGroup.objects.create(name="OtherGroup")
        self.create_membership(user=self.reader, group=self.member_group)

    def test_reader_sees_public_and_member_groups_only(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(self.client.get("/api/v1/library/groups/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        payload = response_data_dict(response)
        data = payload_list(payload, "results")
        names = {g["name"] for g in data}
        self.assertIn("Common Room", names)
        self.assertIn("MemberGroup", names)
        self.assertNotIn("OtherGroup", names)

        public = next(g for g in data if g["is_public_group"])
        self.assertTrue(public["is_public_group"])

    def test_reader_cannot_view_non_member_non_public_group(self):
        self.client.login(username="reader", password="pw")
        response = assert_response(
            self.client.get(f"/api/v1/library/groups/{self.other_group.id}/")
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_manager_sees_all_groups(self):
        self.client.login(username="manager", password="pw")
        response = assert_response(self.client.get("/api/v1/library/groups/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        payload = response_data_dict(response)
        data = payload_list(payload, "results")
        names = {g["name"] for g in data}
        self.assertTrue({"Common Room", "MemberGroup", "OtherGroup"}.issubset(names))

    def test_group_list_ordering_name_and_invalid(self):
        self.client.login(username="manager", password="pw")
        ordered = assert_response(
            self.client.get("/api/v1/library/groups/?ordering=name")
        )
        self.assertEqual(ordered.status_code, status.HTTP_200_OK)
        names = [row["name"] for row in response_data_dict(ordered)["results"]]
        self.assertEqual(names, sorted(names))

        invalid = assert_response(
            self.client.get("/api/v1/library/groups/?ordering=-book_count")
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ordering", response_data_dict(invalid))
