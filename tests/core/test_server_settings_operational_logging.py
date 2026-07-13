from __future__ import annotations

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from core import server_settings


class ServerSettingOperationalLoggingTests(TestCase):
    def setUp(self):
        cache.clear()
        server_settings.clear_server_settings_cache()
        server_settings.apply_application_log_level("INFO")

    def tearDown(self):
        server_settings.apply_application_log_level("INFO")
        server_settings.clear_server_settings_cache()

    def test_free_text_setting_logs_key_and_changed_fields_only(self):
        secret_name = "Private Family Library"
        secret_description = "A private server description"
        secret_banner = "Private outage message"

        with self.assertLogs("core.server_settings", level="INFO") as logs:
            server_settings.set_server_name(secret_name)
            server_settings.set_server_description(secret_description)
            server_settings.set_server_banner_message(secret_banner)

        output = "\n".join(logs.output)
        self.assertIn("setting_key=server_name", output)
        self.assertIn("setting_key=server_description", output)
        self.assertIn("setting_key=server_banner_message", output)
        self.assertIn("changed_fields=value", output)
        self.assertNotIn(secret_name, output)
        self.assertNotIn(secret_description, output)
        self.assertNotIn(secret_banner, output)

    def test_application_log_level_change_logs_safe_enum_values(self):
        with self.assertLogs("core.server_settings", level="INFO") as logs:
            server_settings.set_application_log_level("DEBUG")

        output = "\n".join(logs.output)
        self.assertIn("setting_key=application_log_level", output)
        self.assertIn("old=INFO", output)
        self.assertIn("new=DEBUG", output)

    def test_advanced_groups_enable_logs_semantic_event(self):
        with self.assertLogs("core.server_settings", level="INFO") as logs:
            server_settings.enable_advanced_library_groups()

        output = "\n".join(logs.output)
        self.assertIn("setting_key=advanced_library_groups_enabled", output)
        self.assertIn("Advanced library groups enabled", output)
        self.assertIn("old=False", output)
        self.assertIn("new=True", output)

    def test_idempotent_server_setting_save_stays_quiet(self):
        server_settings.set_server_banner_message("Shown once")

        with patch("core.server_settings.logger.info") as info_log:
            server_settings.set_server_banner_message("Shown once")

        info_log.assert_not_called()

    def test_expected_invalid_server_setting_value_does_not_emit_error(self):
        with patch("core.server_settings.logger.error") as error_log:
            with self.assertRaises(ValueError):
                server_settings.set_application_log_level("TRACE")
            with self.assertRaises(ValueError):
                server_settings.set_server_banner_message("x" * 501)

        error_log.assert_not_called()
