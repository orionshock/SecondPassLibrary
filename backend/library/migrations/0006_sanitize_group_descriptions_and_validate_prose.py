import nh3
from django.db import migrations


LIMITED_RICH_TEXT_TAGS = {
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
LIMITED_RICH_TEXT_CLEAN_CONTENT_TAGS = {"script", "style"}
DESCRIPTIVE_PROSE_MAX_LENGTH = 25_000


def normalize_library_prose(apps, schema_editor):
    cleaner = nh3.Cleaner(
        tags=LIMITED_RICH_TEXT_TAGS,
        clean_content_tags=LIMITED_RICH_TEXT_CLEAN_CONTENT_TAGS,
        attributes={},
        link_rel=None,
    )
    for model_name, field_name in (
        ("Book", "description"),
        ("Author", "biography"),
        ("Series", "summary"),
        ("LibraryGroup", "description"),
    ):
        model = apps.get_model("library", model_name)
        for instance in model.objects.exclude(**{field_name: ""}).iterator(chunk_size=500):
            current = getattr(instance, field_name) or ""
            sanitized = cleaner.clean(current)
            if len(sanitized) > DESCRIPTIVE_PROSE_MAX_LENGTH:
                raise RuntimeError(
                    f"{model_name}.{field_name} exceeds the 25,000-character "
                    f"sanitized HTML limit for object {instance.pk}."
                )
            if sanitized != current:
                model.objects.filter(pk=instance.pk).update(**{field_name: sanitized})


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0005_sanitize_author_series_prose"),
    ]

    operations = [
        migrations.RunPython(normalize_library_prose, migrations.RunPython.noop),
    ]
