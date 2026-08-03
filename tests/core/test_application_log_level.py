import logging
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import OperationalError
from django.test import RequestFactory, TestCase

from core import server_settings
from core.admin import ServerSettingAdmin
from core.models import ServerSetting


class ApplicationLogLevelTests(TestCase):
    def setUp(self):
        server_settings.clear_server_settings_cache()
        server_settings.apply_application_log_level("INFO")

    def tearDown(self):
        server_settings.apply_application_log_level("INFO")
        server_settings.clear_server_settings_cache()

    def test_missing_setting_resolves_to_info(self):
        self.assertEqual(server_settings.get_application_log_level(), "INFO")

    def test_malformed_setting_resolves_to_info(self):
        ServerSetting.objects.create(
            key=server_settings.APPLICATION_LOG_LEVEL_SETTING,
            value={"level": "DEBUG"},
        )

        self.assertEqual(server_settings.get_application_log_level(), "INFO")

        self.setting = ServerSetting.objects.get(
            key=server_settings.APPLICATION_LOG_LEVEL_SETTING
        )
        self.setting.value = "debug"
        self.setting.save(update_fields=["value", "updated_at"])
        self.assertEqual(server_settings.get_application_log_level(), "INFO")

    def test_each_allowed_level_resolves_and_changes_application_logger(self):
        logger = logging.getLogger("library.catalog.example")

        for level_name in server_settings.APPLICATION_LOG_LEVELS:
            with self.subTest(level=level_name):
                server_settings.set_application_log_level(level_name)
                self.assertEqual(server_settings.get_application_log_level(), level_name)
                self.assertEqual(logger.getEffectiveLevel(), getattr(logging, level_name))

    def test_logger_inventory_uses_current_domain_names(self):
        self.assertEqual(
            server_settings.APPLICATION_LOGGER_NAMES,
            (
                "accounts",
                "core",
                "library",
                "marginalia",
                "shelves",
                "web",
            ),
        )

    def test_application_level_does_not_reduce_django_security_logger(self):
        security_logger = logging.getLogger("django.security")
        original_level = security_logger.level
        security_logger.setLevel(logging.ERROR)
        self.addCleanup(security_logger.setLevel, original_level)

        server_settings.set_application_log_level("DEBUG")

        self.assertEqual(security_logger.getEffectiveLevel(), logging.ERROR)

    @patch("core.server_settings.get_server_setting", side_effect=OperationalError("missing table"))
    def test_database_unavailable_falls_back_without_crashing(self, get_setting):
        self.assertEqual(server_settings.get_application_log_level(), "INFO")


class ApplicationLogLevelAdminTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(
            username="owner",
            password="pw",
        )
        self.request = RequestFactory().post("/admin/core/serversetting/")
        self.request.user = self.owner
        self.setting = ServerSetting.objects.create(
            key=server_settings.APPLICATION_LOG_LEVEL_SETTING,
            value="INFO",
        )
        self.model_admin = ServerSettingAdmin(ServerSetting, admin.site)

    def tearDown(self):
        server_settings.apply_application_log_level("INFO")
        server_settings.clear_server_settings_cache()

    def test_admin_offers_only_semantic_levels_and_keeps_key_read_only(self):
        form_class = self.model_admin.get_form(self.request, self.setting)
        form = form_class(instance=self.setting)

        self.assertEqual(
            list(form.fields["value"].choices),
            [(level, level) for level in server_settings.APPLICATION_LOG_LEVELS],
        )
        self.assertIn(
            "key",
            self.model_admin.get_readonly_fields(self.request, self.setting),
        )

    def test_admin_save_invalidates_cache_and_applies_without_restart(self):
        self.assertEqual(server_settings.get_application_log_level(), "INFO")
        form_class = self.model_admin.get_form(self.request, self.setting)
        form = form_class(data={"value": "ERROR"}, instance=self.setting)
        self.assertTrue(form.is_valid(), form.errors)
        obj = form.save(commit=False)

        self.model_admin.save_model(self.request, obj, form, change=True)

        self.assertEqual(server_settings.get_application_log_level(), "ERROR")
        self.assertEqual(logging.getLogger("shelves.cleanup").getEffectiveLevel(), logging.ERROR)

    def test_admin_rejects_values_outside_the_four_choices(self):
        form_class = self.model_admin.get_form(self.request, self.setting)
        form = form_class(data={"value": "CRITICAL"}, instance=self.setting)

        self.assertFalse(form.is_valid())
        self.assertIn("Select a valid choice", form.errors["value"][0])
