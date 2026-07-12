from __future__ import annotations

from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from tests.library.groups.mutation_helpers import LibraryGroupMutationApiTestCase


class LibraryGroupDeleteApiTests(LibraryGroupMutationApiTestCase):
    def test_manager_and_owner_can_delete_normal_group(self):
        for username in ["manager", "owner"]:
            with self.subTest(username=username):
                group = LibraryGroup.objects.create(name=f"{username} doomed")
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))

                response = self.client.delete(f"/api/v1/library/groups/{group.id}/")

                self.assertEqual(response.status_code, 204)
                self.assertFalse(LibraryGroup.objects.filter(pk=group.pk).exists())

    def test_delete_normal_group_triggers_library_fallback(self):
        book = Book.objects.create(title="Grouped Book")
        doomed = LibraryGroup.objects.create(name="Doomed")
        LibraryGroupMembership.objects.create(user=self.reader, group=doomed)
        BookGroupAssignment.objects.create(book=book, group=doomed, added_by=self.manager)
        self.client.login(username="manager", password="pw")

        response = self.client.delete(f"/api/v1/library/groups/{doomed.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertTrue(LibraryGroupMembership.objects.filter(user=self.reader, group=self.public).exists())
        self.assertTrue(BookGroupAssignment.objects.filter(book=book, group=self.public).exists())

    def test_deleting_public_group_is_rejected(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.delete(f"/api/v1/library/groups/{self.public.id}/")

        self.assertEqual(response.status_code, 400)
        self.assertTrue(LibraryGroup.objects.filter(pk=self.public.pk).exists())

    def test_unauthorized_users_cannot_delete_visible_group(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.delete(f"/api/v1/library/groups/{self.club.id}/")

        self.assertEqual(response.status_code, 403)

    def test_delete_hidden_group_returns_404_before_permission_errors(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.delete(f"/api/v1/library/groups/{self.hidden.id}/")

        self.assertEqual(response.status_code, 404)
