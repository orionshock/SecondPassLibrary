from __future__ import annotations

import json

from library.models import LibraryGroup, LibraryGroupMembership
from tests.library.groups.mutation_helpers import LibraryGroupMutationApiTestCase


class LibraryGroupPatchApiTests(LibraryGroupMutationApiTestCase):
    def test_librarian_can_patch_group_description_but_not_name(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        description = self.client.patch(
            f"/api/v1/library/groups/{self.club.id}/",
            json.dumps({"description": "Curated"}),
            content_type="application/json",
        )
        rename = self.client.patch(
            f"/api/v1/library/groups/{self.club.id}/",
            json.dumps({"name": "Denied"}),
            content_type="application/json",
        )

        self.assertEqual(description.status_code, 200)
        self.assertEqual(description.json()["description"], "Curated")
        self.assertEqual(rename.status_code, 403)

    def test_reader_curator_can_patch_exact_group_description_only(self):
        LibraryGroupMembership.objects.filter(
            user=self.reader, group=self.club
        ).update(is_curator=True)
        LibraryGroupMembership.objects.create(user=self.reader, group=self.hidden)
        self.assertTrue(self.client.login(username="reader", password="pw"))

        exact = self.client.patch(
            f"/api/v1/library/groups/{self.club.id}/",
            json.dumps({"description": "Reader curated"}),
            content_type="application/json",
        )
        other = self.client.patch(
            f"/api/v1/library/groups/{self.hidden.id}/",
            json.dumps({"description": "Denied"}),
            content_type="application/json",
        )

        self.assertEqual(exact.status_code, 200)
        self.assertEqual(exact.json()["description"], "Reader curated")
        self.assertEqual(other.status_code, 403)

    def test_librarian_can_patch_public_description(self):
        self.assertTrue(self.client.login(username="librarian", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.public.id}/",
            json.dumps({"description": "Shared by everyone"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["description"], "Shared by everyone")

    def test_manager_and_owner_can_patch_group_name_and_description(self):
        for username in ["manager", "owner"]:
            with self.subTest(username=username):
                group = LibraryGroup.objects.create(name=f"{username} old", description="Before")
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))

                response = self.client.patch(
                    f"/api/v1/library/groups/{group.id}/",
                    json.dumps({"name": f"{username} new", "description": "After"}),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["name"], f"{username} new")
                self.assertEqual(response.json()["description"], "After")

    def test_unauthorized_users_cannot_patch_visible_group(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.club.id}/",
            json.dumps({"name": "Denied"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_patch_hidden_group_returns_404_before_validation(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.hidden.id}/",
            json.dumps({"name": "   ", "unknown": "field"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_patch_public_group_identity_is_allowed_for_manager(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.public.id}/",
            json.dumps({"name": "Library Lobby", "description": "Still public"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Library Lobby")
        self.assertTrue(response.json()["is_public_group"])

    def test_patch_validates_blank_name_and_ignores_list_params(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.club.id}/?q=no-match&ordering=created_at",
            json.dumps({"name": "   "}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json())
