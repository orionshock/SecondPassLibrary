from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from accounts.models import UserProfile
from core.server_settings import set_server_setting
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from tests.library.helpers import response_names, set_user_role


class LibraryReWrite2607GroupMutationTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        set_user_role(self.reader, UserProfile.ROLE_READER)
        set_user_role(self.librarian, UserProfile.ROLE_LIBRARIAN)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)

        self.public = LibraryGroup.objects.create(name="Common Room", description="Shared")
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(self.public.id),
            description="LibraryReWrite2607 Public/Common Room group id.",
        )
        self.club = LibraryGroup.objects.create(name="Club", description="Readers")
        self.hidden = LibraryGroup.objects.create(name="Hidden", description="Private")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.public)
        LibraryGroupMembership.objects.create(user=self.reader, group=self.club)

    def test_manager_and_owner_can_create_group(self):
        for username in ["manager", "owner"]:
            with self.subTest(username=username):
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))

                response = self.client.post(
                    "/api/v1/library/groups/",
                    _json({"name": f"{username} group", "description": "Created"}),
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
                    _json({"name": "Denied"}),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 403)

    def test_create_validates_required_blank_and_unknown_fields(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        missing = self.client.post(
            "/api/v1/library/groups/",
            _json({}),
            content_type="application/json",
        )
        blank = self.client.post(
            "/api/v1/library/groups/",
            _json({"name": "   "}),
            content_type="application/json",
        )
        unknown = self.client.post(
            "/api/v1/library/groups/",
            _json({"name": "Clubhouse", "slug": "clubhouse"}),
            content_type="application/json",
        )

        self.assertEqual(missing.status_code, 400)
        self.assertIn("name", missing.json())
        self.assertEqual(blank.status_code, 400)
        self.assertIn("name", blank.json())
        self.assertEqual(unknown.status_code, 400)
        self.assertIn("slug", unknown.json())

    def test_manager_and_owner_can_patch_group_name_and_description(self):
        for username in ["manager", "owner"]:
            with self.subTest(username=username):
                group = LibraryGroup.objects.create(name=f"{username} old", description="Before")
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))

                response = self.client.patch(
                    f"/api/v1/library/groups/{group.id}/",
                    _json({"name": f"{username} new", "description": "After"}),
                    content_type="application/json",
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["name"], f"{username} new")
                self.assertEqual(response.json()["description"], "After")

    def test_unauthorized_users_cannot_patch_visible_group(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.club.id}/",
            _json({"name": "Denied"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    def test_patch_hidden_group_returns_404_before_validation(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.hidden.id}/",
            _json({"name": "   ", "unknown": "field"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_patch_public_group_identity_is_allowed_for_manager(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.public.id}/",
            _json({"name": "Library Lobby", "description": "Still public"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Library Lobby")
        self.assertTrue(response.json()["is_public_group"])

    def test_patch_validates_blank_name_and_ignores_list_params(self):
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/groups/{self.club.id}/?q=no-match&ordering=created_at",
            _json({"name": "   "}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("name", response.json())

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

    def test_get_list_and_detail_still_work_after_mutation_support(self):
        self.assertTrue(self.client.login(username="reader", password="pw"))

        list_response = self.client.get("/api/v1/library/groups/")
        detail_response = self.client.get(f"/api/v1/library/groups/{self.club.id}/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(response_names(list_response), ["Club", "Common Room"])
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["name"], "Club")


def _json(data: dict) -> str:
    return json.dumps(data)
