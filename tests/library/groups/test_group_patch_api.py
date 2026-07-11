from __future__ import annotations

from library.models import LibraryGroup
from tests.library.groups.mutation_helpers import LibraryGroupMutationApiTestCase, json_body


class LibraryReWrite2607GroupPatchApiTests(LibraryGroupMutationApiTestCase):
    def test_manager_and_owner_can_patch_group_name_and_description(self):
        for username in ["manager", "owner"]:
            with self.subTest(username=username):
                group = LibraryGroup.objects.create(name=f"{username} old", description="Before")
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))

                response = self.client.patch(
                    f"/api/v1/library/groups/{group.id}/",
                    json_body({"name": f"{username} new", "description": "After"}),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["name"], f"{username} new")
                self.assertEqual(response.json()["description"], "After")

    def test_unauthorized_users_cannot_patch_visible_group(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.club.id}/",
            json_body({"name": "Denied"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_patch_hidden_group_returns_404_before_validation(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.hidden.id}/",
            json_body({"name": "   ", "unknown": "field"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_patch_public_group_identity_is_allowed_for_manager(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.public.id}/",
            json_body({"name": "Library Lobby", "description": "Still public"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Library Lobby")
        self.assertTrue(response.json()["is_public_group"])

    def test_patch_validates_blank_name_and_ignores_list_params(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.club.id}/?q=no-match&ordering=created_at",
            json_body({"name": "   "}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json())
