import nh3
from django.db import migrations


RICH_TEXT_SETTING_KEYS = {"server_description", "server_banner_message"}
RICH_TEXT_TAGS = {
    "b",
    "br",
    "em",
    "i",
    "li",
    "ol",
    "p",
    "strong",
    "ul",
}


def sanitize_server_identity_html(apps, schema_editor):
    ServerSetting = apps.get_model("core", "ServerSetting")
    cleaner = nh3.Cleaner(
        tags=RICH_TEXT_TAGS,
        clean_content_tags={"script", "style"},
        attributes={},
        link_rel=None,
    )
    for setting in ServerSetting.objects.filter(key__in=RICH_TEXT_SETTING_KEYS):
        sanitized = cleaner.clean(str(setting.value or "")).strip()
        if sanitized != setting.value:
            setting.value = sanitized
            setting.save(update_fields=["value"])


class Migration(migrations.Migration):
    dependencies = [("core", "0002_rename_reader_web_client_url_setting")]

    operations = [
        migrations.RunPython(sanitize_server_identity_html, migrations.RunPython.noop),
    ]
