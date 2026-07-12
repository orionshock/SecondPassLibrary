import hashlib

from django.db import migrations, models
from django.utils.text import slugify


def populate_catalog_tag_slugs(apps, schema_editor):
    catalog_tag = apps.get_model("library", "CatalogTag")
    used = set()
    for tag in catalog_tag.objects.order_by("id"):
        digest = hashlib.sha256(tag.normalized_name.encode("utf-8")).hexdigest()
        base = slugify(tag.normalized_name, allow_unicode=True)[:255].strip("-")
        slug = base
        if not slug or slug in used:
            stem = base[:246].rstrip("-") if base else "tag"
            for length in range(8, 65, 4):
                slug = f"{stem}-{digest[:length]}"
                if slug not in used:
                    break
        tag.slug = slug
        tag.save(update_fields=["slug"])
        used.add(slug)


class Migration(migrations.Migration):
    dependencies = [("library", "0002_author_biography_series_summary")]

    operations = [
        migrations.AddField(
            model_name="catalogtag",
            name="slug",
            field=models.SlugField(allow_unicode=True, editable=False, max_length=280, null=True),
        ),
        migrations.RunPython(populate_catalog_tag_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="catalogtag",
            name="slug",
            field=models.SlugField(allow_unicode=True, editable=False, max_length=280, unique=True),
        ),
    ]
