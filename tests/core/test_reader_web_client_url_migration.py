from importlib import import_module

from django.apps import apps
from django.test import TestCase

from core.models import ServerSetting


class SecondPassReaderWebClientUrlMigrationTests(TestCase):
    def test_old_row_is_renamed_normalized_and_removed(self):
        ServerSetting.objects.filter(
            key="second_pass_reader_web_client_url"
        ).delete()
        ServerSetting.objects.create(
            key="reading_client_base_url",
            value="https://reader.example.com:8443/reader?mode=web#home",
            description="Old setting",
        )
        migration = import_module(
            "core.migrations.0002_rename_reader_web_client_url_setting"
        )

        migration.rename_and_normalize_reader_url(apps, None)

        self.assertFalse(
            ServerSetting.objects.filter(key="reading_client_base_url").exists()
        )
        self.assertEqual(
            ServerSetting.objects.get(
                key="second_pass_reader_web_client_url"
            ).value,
            "https://reader.example.com:8443",
        )
