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


def normalize_shelf_descriptions(apps, schema_editor):
    cleaner = nh3.Cleaner(
        tags=LIMITED_RICH_TEXT_TAGS,
        clean_content_tags=LIMITED_RICH_TEXT_CLEAN_CONTENT_TAGS,
        attributes={},
        link_rel=None,
    )
    shelf = apps.get_model("shelves", "Shelf")
    for instance in shelf.objects.exclude(description="").iterator(chunk_size=500):
        sanitized = cleaner.clean(instance.description or "")
        if len(sanitized) > DESCRIPTIVE_PROSE_MAX_LENGTH:
            raise RuntimeError(
                "Shelf.description exceeds the 25,000-character sanitized HTML "
                f"limit for object {instance.pk}."
            )
        if sanitized != instance.description:
            shelf.objects.filter(pk=instance.pk).update(description=sanitized)


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0006_sanitize_group_descriptions_and_validate_prose"),
        ("shelves", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(normalize_shelf_descriptions, migrations.RunPython.noop),
    ]
