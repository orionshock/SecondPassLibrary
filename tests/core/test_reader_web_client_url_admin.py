from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import path, reverse

from core import server_settings
from core.models import ServerSetting


urlpatterns = [path("admin/", admin.site.urls)]


@override_settings(ROOT_URLCONF=__name__)
class SecondPassReaderWebClientUrlAdminTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="owner",
            password="pw",
        )
        server_settings.ensure_editable_server_settings()
        self.setting = ServerSetting.objects.get(
            key=server_settings.SECOND_PASS_READER_WEB_CLIENT_URL_SETTING
        )
        self.client.force_login(self.user)

    def _change_url(self):
        return reverse("admin:core_serversetting_change", args=(self.setting.pk,))

    def test_admin_uses_single_line_url_input(self):
        response = self.client.get(self._change_url())

        self.assertEqual(response.status_code, 200)
        field = response.context["adminform"].form.fields["value"]
        self.assertEqual(field.widget.input_type, "url")
        self.assertNotEqual(field.widget.__class__.__name__, "Textarea")

    def test_admin_saves_canonical_origin(self):
        response = self.client.post(
            self._change_url(),
            {
                "value": "https://reader.example.com:8443/setup?mode=web#home",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            server_settings.get_second_pass_reader_web_client_url(),
            "https://reader.example.com:8443",
        )

    def test_admin_rejects_relative_url(self):
        response = self.client.post(
            self._change_url(),
            {"value": "/reader", "_save": "Save"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["adminform"].form.errors["value"])
        self.assertEqual(server_settings.get_second_pass_reader_web_client_url(), "")

    @override_settings(
        SECOND_PASS_READER_WEB_CLIENT_URL="https://reader.example.com/deploy"
    )
    def test_environment_owned_value_is_disabled_after_sync(self):
        server_settings.synchronize_deployment_server_settings()

        response = self.client.get(self._change_url())

        self.assertEqual(response.status_code, 200)
        field = response.context["adminform"].form.fields["value"]
        self.assertTrue(field.disabled)
        self.assertEqual(
            server_settings.get_second_pass_reader_web_client_url(),
            "https://reader.example.com",
        )
