from __future__ import annotations

from tests.library.bearer.helpers import LibraryBearerApiTestCase


class LibraryBearerGroupMutationBoundaryTests(LibraryBearerApiTestCase):
    def setUp(self):
        super().setUp()
        self.use_manager_bearer()
        self.headers = {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def test_privileged_bearer_cannot_create_update_or_delete_groups(self):
        group_url = f"/api/v1/library/groups/{self.public.id}/"

        created = self.bearer.post(
            "/api/v1/library/groups/", {"name": "Bearer Group"}, format="json", **self.headers
        )
        patched = self.bearer.patch(
            group_url, {"description": "Bearer changed"}, format="json", **self.headers
        )
        deleted = self.bearer.delete(group_url, **self.headers)

        self.assertEqual(created.status_code, 403)
        self.assertEqual(patched.status_code, 403)
        self.assertEqual(deleted.status_code, 403)
        self.public.refresh_from_db()
        self.assertEqual(self.public.description, "")

    def test_privileged_bearer_cannot_mutate_assignments_or_memberships(self):
        group_url = f"/api/v1/library/groups/{self.public.id}/"
        books_url = f"{group_url}books/"
        memberships_url = f"{group_url}memberships/"

        added = self.bearer.post(
            books_url,
            {"book_id": str(self.hidden_book.id)},
            format="json",
            **self.headers,
        )
        removed = self.bearer.delete(f"{books_url}{self.visible_one.id}/", **self.headers)
        listed_members = self.bearer.get(memberships_url, **self.headers)
        added_member = self.bearer.post(
            memberships_url,
            {"user_id": str(self.manager.profile.id)},
            format="json",
            **self.headers,
        )
        member_url = f"{memberships_url}{self.reader.profile.id}/"
        patched_member = self.bearer.patch(
            member_url, {"is_curator": True}, format="json", **self.headers
        )
        removed_member = self.bearer.delete(member_url, **self.headers)

        self.assertEqual(added.status_code, 403)
        self.assertEqual(removed.status_code, 403)
        self.assertEqual(listed_members.status_code, 403)
        self.assertEqual(added_member.status_code, 403)
        self.assertEqual(patched_member.status_code, 403)
        self.assertEqual(removed_member.status_code, 403)
        self.assertTrue(self.visible_one.group_assignments.filter(group=self.public).exists())
