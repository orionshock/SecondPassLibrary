from __future__ import annotations

import json

from library.models import LibraryGroup
from tests.library.groups.mutation_helpers import LibraryGroupMutationApiTestCase


class LibraryGroupCreateApiTests(LibraryGroupMutationApiTestCase):
    def test_manager_and_owner_can_create_group(self):
        for username in ["manager", "owner"]:
            with self.subTest(username=username):
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))

                response = self.client.post(
                    "/api/v1/library/groups/",
                    json.dumps({"name": f"{username} group", "description": "Created"}),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 201)
                payload = response.json()
                self.assertEqual(payload["name"], f"{username} group")
                self.assertEqual(payload["description"], "Created")
                self.assertFalse(payload["is_public_group"])

    def test_librarian_and_reader_cannot_create_group(self):
        for username in ["librarian", "reader"]:
            with self.subTest(username=username):
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))

                response = self.client.post(
                    "/api/v1/library/groups/",
                    json.dumps({"name": "Denied"}),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 403)

    def test_create_validates_required_blank_and_unknown_fields(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        missing = self.client.post(
            "/api/v1/library/groups/",
            json.dumps({}),
            content_type="application/json",
        )
        blank = self.client.post(
            "/api/v1/library/groups/",
            json.dumps({"name": "   "}),
            content_type="application/json",
        )
        unknown = self.client.post(
            "/api/v1/library/groups/",
            json.dumps({"name": "Clubhouse", "slug": "clubhouse"}),
            content_type="application/json",
        )

        self.assertEqual(missing.status_code, 400)
        self.assertIn("name", missing.json())
        self.assertEqual(blank.status_code, 400)
        self.assertIn("name", blank.json())
        self.assertEqual(unknown.status_code, 400)
        self.assertIn("slug", unknown.json())

    def test_create_rejects_name_over_model_limit(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.post(
            "/api/v1/library/groups/",
            json.dumps({"name": "x" * 256, "description": "Not persisted"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json())
        self.assertFalse(
            LibraryGroup.objects.filter(description="Not persisted").exists()
        )

    def test_create_allows_duplicate_names(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))
        LibraryGroup.objects.create(name="Duplicate")

        response = self.client.post(
            "/api/v1/library/groups/",
            json.dumps({"name": "Duplicate", "description": "Second"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(LibraryGroup.objects.filter(name="Duplicate").count(), 2)
