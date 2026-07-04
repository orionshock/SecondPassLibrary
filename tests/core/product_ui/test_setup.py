"""Setup flow tests for first-run product UI."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from accounts.models import UserProfile
from core import server_settings
from library.public_group import get_public_group
from library.models import LibraryGroupMembership


User = get_user_model()


class FirstRunProductUiTests(TestCase):
    setup_data = {
        "server_name": "Second Pass Library",
        "server_description": "",
        "public_group_name": "Common Room",
        "public_group_description": "Main Public Library Room for everyone",
        "username": "owner",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "",
        "password1": "Correct-Horse-Battery-47",
        "password2": "Correct-Horse-Battery-47",
    }

    def test_setup_page_is_available_without_active_owner(self):
        response = self.client.get("/setup/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Set up your library")
        self.assertContains(response, 'class="setup-layout"')
        self.assertContains(response, "Server")
        self.assertContains(response, "Public Space")
        self.assertContains(response, "Owner Account")
        self.assertContains(response, "Advanced")
        self.assertContains(response, 'name="server_name"')
        self.assertContains(response, 'value="Second Pass Library"')
        self.assertContains(response, 'name="server_description"')
        self.assertContains(response, 'name="public_group_name"')
        self.assertContains(response, 'value="Common Room"')
        self.assertContains(response, 'name="public_group_description"')
        self.assertContains(response, "Main Public Library Room for everyone")
        self.assertContains(response, 'name="advanced_library_groups_enabled"')
        self.assertContains(
            response,
            (
                "Advanced library groups let you create separate curator-managed "
                "library rooms with their own memberships and group-owned shelves. "
                "Leave this off if you only need the Common Room, managed by librarians "
                "as the shared public library space."
            ),
        )
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="first_name"')
        self.assertContains(response, 'name="last_name"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="password1"')
        self.assertContains(response, 'name="password2"')
        self.assertNotContains(
            response,
            'name="advanced_library_groups_enabled" checked',
        )

    @override_settings(DEBUG=False)
    def test_setup_page_is_available_in_production_mode(self):
        response = self.client.get("/setup/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Set up your library")

    def test_root_app_and_login_direct_to_setup_without_active_owner(self):
        for path in ("/", "/dashboard/", "/api-auth/login/"):
            with self.subTest(path=path):
                response = self.client.get(path, follow=False)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response["Location"], "/setup/")

    def test_successful_setup_redirects_to_login_and_login_works(self):
        response = self.client.post("/setup/", self.setup_data, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/")

        owner = User.objects.get(username="owner")
        profile = UserProfile.objects.get(user=owner)
        public_group = get_public_group()
        self.assertTrue(owner.is_active)
        self.assertTrue(owner.is_staff)
        self.assertTrue(owner.is_superuser)
        self.assertEqual(profile.role, UserProfile.ROLE_MANAGER)
        self.assertEqual(server_settings.get_server_name(), "Second Pass Library")
        self.assertEqual(server_settings.get_server_description(), "")
        self.assertEqual(public_group.name, "Common Room")
        self.assertEqual(
            public_group.description,
            "Main Public Library Room for everyone",
        )
        self.assertFalse(server_settings.get_advanced_library_groups_enabled())
        self.assertTrue(
            LibraryGroupMembership.objects.filter(
                user=owner,
                group=public_group,
                is_curator=False,
            ).exists()
        )

        login_response = self.client.post(
            "/api-auth/login/",
            {
                "username": "owner",
                "password": "Correct-Horse-Battery-47",
                "next": "/dashboard/",
            },
            follow=False,
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response["Location"], "/dashboard/")

    def test_setup_redirects_to_login_after_completion(self):
        User.objects.create_superuser(
            username="owner", email="owner@example.com", password="pw"
        )
        response = self.client.get("/setup/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/")

    def test_second_setup_post_does_not_create_another_owner(self):
        first = self.client.post("/setup/", self.setup_data, follow=False)
        self.assertEqual(first.status_code, 302)

        second_data = {
            **self.setup_data,
            "username": "owner-two",
            "password1": "Another-Correct-Password-48",
            "password2": "Another-Correct-Password-48",
        }
        second = self.client.post("/setup/", second_data, follow=False)

        self.assertEqual(second.status_code, 302)
        self.assertEqual(second["Location"], "/api-auth/login/")
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)
