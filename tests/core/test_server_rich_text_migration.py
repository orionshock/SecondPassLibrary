from importlib import import_module

from django.apps import apps
from django.test import TestCase

from core.models import ServerSetting


class ServerRichTextMigrationTests(TestCase):
    def test_sanitizes_existing_identity_html_without_touching_other_settings(self):
        description = ServerSetting.objects.create(
            key="server_description",
            value='<p class="lead">About <strong>SPL</strong></p><script>bad()</script>',
        )
        banner = ServerSetting.objects.create(
            key="server_banner_message",
            value='<ul><li onclick="bad()">Notice</li></ul>',
        )
        other = ServerSetting.objects.create(key="unrelated", value="<script>keep</script>")

        migration = import_module("core.migrations.0003_sanitize_server_identity_html")
        migration.sanitize_server_identity_html(apps, schema_editor=None)

        description.refresh_from_db()
        banner.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(description.value, "<p>About <strong>SPL</strong></p>")
        self.assertEqual(banner.value, "<ul><li>Notice</li></ul>")
        self.assertEqual(other.value, "<script>keep</script>")
