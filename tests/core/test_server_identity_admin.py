from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import path, reverse

from core import server_settings
from core.admin import ServerSettingAdmin
from core.models import ServerSetting


urlpatterns = [path("admin/", admin.site.urls)]


@override_settings(ROOT_URLCONF=__name__)
class ServerIdentityAdminTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="owner",
            password="pw",
        )
        server_settings.ensure_editable_server_settings()
        self.setting = ServerSetting.objects.get(
            key=server_settings.SERVER_NAME_SETTING
        )
        self.client.force_login(self.user)

    def test_identity_settings_have_one_admin_list_entry(self):
        model_admin = ServerSettingAdmin(ServerSetting, admin.site)
        request = RequestFactory().get("/admin/core/serversetting/")
        request.user = self.user

        keys = set(model_admin.get_queryset(request).values_list("key", flat=True))

        self.assertIn(server_settings.SERVER_NAME_SETTING, keys)
        self.assertNotIn(server_settings.SERVER_DESCRIPTION_SETTING, keys)
        self.assertNotIn(server_settings.SERVER_BANNER_MESSAGE_SETTING, keys)

    def test_combined_form_loads_all_identity_values(self):
        server_settings.set_server_name("House Library")
        server_settings.set_server_description("Private library")
        server_settings.set_server_banner_message("Maintenance tonight")
        response = self.client.get(
            reverse("admin:core_serversetting_change", args=(self.setting.pk,))
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["adminform"].form
        self.assertIn("server_name", form.fields)
        self.assertIn("server_description", form.fields)
        self.assertIn("server_banner_message", form.fields)
        self.assertEqual(form.initial["server_name"], "House Library")
        self.assertEqual(form.initial["server_description"], "Private library")
        self.assertEqual(
            form.initial["server_banner_message"], "Maintenance tonight"
        )
    def test_combined_form_updates_all_three_settings(self):
        response = self.client.post(
            reverse("admin:core_serversetting_change", args=(self.setting.pk,)),
            {
                "server_name": "House Library",
                "server_description": "A private family library.",
                "server_banner_message": "Maintenance tonight.",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(server_settings.get_server_name(), "House Library")
        self.assertEqual(
            server_settings.get_server_description(), "A private family library."
        )
        self.assertEqual(
            server_settings.get_server_banner_message(), "Maintenance tonight."
        )

    def test_combined_form_sanitizes_rich_identity_fields(self):
        response = self.client.post(
            reverse("admin:core_serversetting_change", args=(self.setting.pk,)),
            {
                "server_name": "House Library",
                "server_description": (
                    '<p class="lead">A <strong>private</strong> library.</p>'
                    '<script>alert("no")</script>'
                ),
                "server_banner_message": (
                    '<ul><li style="color:red">Maintenance</li></ul>'
                ),
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            server_settings.get_server_description(),
            "<p>A <strong>private</strong> library.</p>",
        )
        self.assertEqual(
            server_settings.get_server_banner_message(),
            "<ul><li>Maintenance</li></ul>",
        )

    def test_invalid_combined_form_does_not_update_any_setting(self):
        original_name = server_settings.get_server_name()
        original_description = server_settings.get_server_description()
        original_banner = server_settings.get_server_banner_message()

        response = self.client.post(
            reverse("admin:core_serversetting_change", args=(self.setting.pk,)),
            {
                "server_name": "x" * (server_settings.SERVER_NAME_MAX_LEN + 1),
                "server_description": "Changed description",
                "server_banner_message": "Changed banner",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(server_settings.get_server_name(), original_name)
        self.assertEqual(server_settings.get_server_description(), original_description)
        self.assertEqual(server_settings.get_server_banner_message(), original_banner)
