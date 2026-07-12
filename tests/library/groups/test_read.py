from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from accounts.models import UserProfile
from core.server_settings import set_server_setting
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.models import LibraryGroup, LibraryGroupMembership
from tests.library.helpers import response_names, set_user_role


class LibraryGroupReadTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        set_user_role(self.reader, UserProfile.ROLE_READER)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)
        set_user_role(self.librarian, UserProfile.ROLE_LIBRARIAN)

        self.public = LibraryGroup.objects.create(name="Public Renamed", description="Shared")
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(self.public.id),
            description="Public/Common Room group id.",
        )
        self.club = LibraryGroup.objects.create(name="Club", description="Dresden readers")
        self.family = LibraryGroup.objects.create(name="Family", description="Household")
        self.hidden = LibraryGroup.objects.create(name="Hidden", description="Private")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.public)
        LibraryGroupMembership.objects.create(user=self.reader, group=self.club)

        self.assertTrue(self.client.login(username="reader", password="pw"))

    def test_reader_sees_public_and_membership_groups(self):
        response = self.client.get("/api/v1/library/groups/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), ["Club", "Public Renamed"])
        public = next(row for row in response.json()["results"] if row["name"] == "Public Renamed")
        self.assertTrue(public["is_public_group"])

    def test_reader_does_not_see_unrelated_groups(self):
        response = self.client.get("/api/v1/library/groups/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Hidden", response_names(response))
        self.assertNotIn("Family", response_names(response))

    def test_broad_roles_see_all_groups(self):
        expected = ["Club", "Family", "Hidden", "Public Renamed"]

        for username in ["manager", "librarian", "owner"]:
            with self.subTest(username=username):
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))
                response = self.client.get("/api/v1/library/groups/")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response_names(response), expected)

    def test_detail_hidden_group_returns_404(self):
        response = self.client.get(f"/api/v1/library/groups/{self.hidden.id}/")

        self.assertEqual(response.status_code, 404)

    def test_list_q_and_ordering(self):
        q_response = self.client.get("/api/v1/library/groups/", {"q": "dresden"})
        desc_response = self.client.get("/api/v1/library/groups/", {"ordering": "-name"})

        self.assertEqual(q_response.status_code, 200)
        self.assertEqual(response_names(q_response), ["Club"])
        self.assertEqual(desc_response.status_code, 200)
        self.assertEqual(response_names(desc_response), ["Public Renamed", "Club"])

    def test_invalid_ordering_returns_400(self):
        response = self.client.get("/api/v1/library/groups/", {"ordering": "created_at"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("ordering", response.json())

    def test_detail_ignores_q_and_ordering_params(self):
        q_response = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/",
            {"q": "definitely-no-match"},
        )
        invalid_ordering_response = self.client.get(
            f"/api/v1/library/groups/{self.club.id}/",
            {"ordering": "created_at"},
        )

        self.assertEqual(q_response.status_code, 200)
        self.assertEqual(q_response.json()["name"], "Club")
        self.assertEqual(invalid_ordering_response.status_code, 200)
        self.assertEqual(invalid_ordering_response.json()["name"], "Club")

    def test_hidden_detail_ignores_invalid_ordering_and_returns_404(self):
        response = self.client.get(
            f"/api/v1/library/groups/{self.hidden.id}/",
            {"ordering": "created_at"},
        )

        self.assertEqual(response.status_code, 404)
