from __future__ import annotations

from tests.library.groups.mutation_helpers import LibraryGroupMutationApiTestCase
from tests.library.helpers import response_names


class LibraryReWrite2607GroupMutationReadRegressionTests(LibraryGroupMutationApiTestCase):
    def test_get_list_and_detail_still_work_after_mutation_support(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        list_response = self.client.get("/api/v1/library/groups/")
        detail_response = self.client.get(f"/api/v1/library/groups/{self.club.id}/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(response_names(list_response), ["Club", "Common Room"])
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["name"], "Club")
