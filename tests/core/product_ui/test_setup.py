"""Setup flow tests for first-run product UI."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from accounts.models import UserProfile
from core import server_settings
from core.server_settings import clear_server_settings_cache
from library.groups.public_group import get_public_group
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

    def setUp(self):
        cache.clear()
        clear_server_settings_cache()

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
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="first_name"')
        self.assertContains(response, 'name="last_name"')
        self.assertContains(response, 'name="email"')
        self.assertContains(response, 'name="password1"')
        self.assertContains(response, 'name="password2"')

    def test_setup_advanced_groups_default_off(self):
        response = self.client.get("/setup/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="advanced_library_groups_enabled"')
        self.assertNotContains(
            response,
            'name="advanced_library_groups_enabled" checked',
        )

    def test_setup_advanced_groups_compact_default_off_copy(self):
        response = self.client.get("/setup/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Advanced library groups default to off.",
        )
        self.assertContains(
            response,
            "Leave this disabled. Consult documentation and help for more information.",
        )

    def test_setup_advanced_groups_modal_warning_and_enable_markup(self):
        response = self.client.get("/setup/")
        content = response.content.decode("utf-8")
        advanced_fieldset = content.split(
            '<fieldset class="setup-section setup-section--advanced">',
            maxsplit=1,
        )[1].split("<dialog", maxsplit=1)[0]

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="setup-advanced-groups-open"')
        self.assertContains(response, "Enable advanced library groups")
        self.assertContains(response, 'id="setup-advanced-groups-dialog"')
        self.assertContains(response, "Keep disabled")
        self.assertContains(response, "Enable advanced groups")
        self.assertContains(response, 'class="setup-dialog__actions"')
        self.assertContains(
            response,
            '<button class="button button--danger" value="enable">Enable advanced groups</button>',
            html=False,
        )
        self.assertContains(
            response,
            '<button class="button button--success-outline" value="cancel">Keep disabled</button>',
            html=False,
        )
        self.assertContains(response, 'id="setup-advanced-groups-enabled-status"')
        self.assertContains(response, "Disable before setup")
        self.assertContains(
            response,
            (
                "Advanced Library Groups allows for additional groups to be "
                "created and assigned their own members and book restrictions."
            ),
        )
        self.assertContains(
            response,
            (
                "Disabling this feature is an Admin Recovery Action that is "
                "intentionally difficult to get to."
            ),
        )
        self.assertContains(
            response,
            "Please see documentation and help files for further information.",
        )
        self.assertContains(
            response,
            "data-advanced-groups-actions",
        )
        self.assertLess(
            content.index('value="enable">Enable advanced groups'),
            content.index('value="cancel">Keep disabled'),
        )
        self.assertNotIn("Admin Recovery Action", advanced_fieldset)
        self.assertNotIn("documentation and help files", advanced_fieldset)

    def test_setup_advanced_groups_final_submit_confirmation_markup(self):
        response = self.client.get("/setup/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-advanced-groups-confirm")
        self.assertContains(response, "window.confirm")
        self.assertContains(response, "checkbox.checked")

    def test_setup_submit_with_advanced_groups_off_keeps_feature_disabled(self):
        response = self.client.post("/setup/", self.setup_data, follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/")
        self.assertFalse(server_settings.get_advanced_library_groups_enabled())

    def test_setup_submit_with_advanced_groups_on_enables_feature(self):
        response = self.client.post(
            "/setup/",
            {
                **self.setup_data,
                "advanced_library_groups_enabled": "on",
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api-auth/login/")
        self.assertTrue(server_settings.get_advanced_library_groups_enabled())

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
