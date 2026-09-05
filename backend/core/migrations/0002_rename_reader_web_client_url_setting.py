from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import migrations


OLD_KEY = "reading_client_base_url"
NEW_KEY = "second_pass_reader_web_client_url"
DESCRIPTION = "Canonical base URL of the Second Pass Reader web client."


def _normalize(value):
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if len(normalized) > 2048 or "{" in normalized or "}" in normalized:
        raise ValueError("Stored Second Pass Reader Web Client URL is invalid.")
    try:
        parsed = urlsplit(normalized)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Stored Second Pass Reader Web Client URL is invalid.") from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Stored Second Pass Reader Web Client URL is invalid.")
    try:
        URLValidator(schemes=["http", "https"])(normalized)
    except ValidationError as exc:
        raise ValueError("Stored Second Pass Reader Web Client URL is invalid.") from exc

    hostname = parsed.hostname
    if ":" in hostname:
        hostname = f"[{hostname}]"
    netloc = hostname if port is None else f"{hostname}:{port}"
    return f"{parsed.scheme}://{netloc}"


def rename_and_normalize_reader_url(apps, _schema_editor):
    ServerSetting = apps.get_model("core", "ServerSetting")
    old = ServerSetting.objects.filter(key=OLD_KEY).first()
    current = ServerSetting.objects.filter(key=NEW_KEY).first()
    source = old or current
    if source is None:
        return

    normalized = _normalize(source.value)
    if old is not None and current is not None:
        current.value = normalized
        current.description = DESCRIPTION
        current.save(update_fields=["value", "description", "updated_at"])
        old.delete()
        return

    source.key = NEW_KEY
    source.value = normalized
    source.description = DESCRIPTION
    source.save(update_fields=["key", "value", "description", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.RunPython(
            rename_and_normalize_reader_url,
            migrations.RunPython.noop,
        )
    ]
